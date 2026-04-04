"""
Smart Align Pro - Screen-Space Snap Engine
升級版：CAD 2.0 風格的 screen-space nearest candidate solver

核心改進：
1. 不是直接拿 ray hit 當吸附點，而是先找目標物件，再掃描候選點集合
2. 候選點以螢幕距離 + 類型權重評分
3. 支援 sticky / hysteresis，避免高光亂跳
4. 支援 expected_object / exclude_objects，避免 self-snap 與意圖跑掉
"""

import bpy
from math import hypot
from mathutils import Vector
from bpy_extras import view3d_utils
from typing import Optional, List, Iterable


TYPE_WEIGHTS = {
    # 幾何特徵優先：角點 > 邊 > 中心/面
    # 這樣滑鼠靠近角落或邊時，不會被 face hit 搶走。
    "VERTEX": 1.18,
    "MIDPOINT": 1.08,
    "EDGE": 1.00,
    "FACE_CENTER": 0.64,
    "FACE": 0.42,
    "ORIGIN": 0.72,
    "CENTER": 0.68,
    "BBOX": 0.66,
    "RAY": 0.10,
}

TYPE_RADII = {
    "VERTEX": 34.0,
    "MIDPOINT": 30.0,
    "EDGE": 28.0,
    "FACE_CENTER": 30.0,
    "FACE": 24.0,
    "ORIGIN": 28.0,
    "CENTER": 28.0,
    "BBOX": 26.0,
    "RAY": 0.0,
}

TYPE_ALIASES = {
    "MIDPOINT": {"MIDPOINT", "EDGE_MID", "EDGE_MIDDLE"},
    "EDGE": {"EDGE", "MIDPOINT", "EDGE_MID", "EDGE_MIDDLE"},
    "FACE": {"FACE", "FACE_CENTER"},
    "FACE_CENTER": {"FACE_CENTER", "FACE"},
    "CENTER": {"CENTER", "ORIGIN", "FACE_CENTER"},
    "ORIGIN": {"ORIGIN", "CENTER"},
    "BBOX": {"BBOX"},
    "VERTEX": {"VERTEX"},
    "ALL": {"ALL"},
}


class SnapCandidate:
    """吸附候選點。欄位盡量與舊版相容。"""
    def __init__(
        self,
        location: Vector,
        snap_type: str,
        object=None,
        screen_distance: float = 0.0,
        normal: Optional[Vector] = None,
        face_index: int = -1,
        matrix=None,
        element=None,
    ):
        self.location = location
        self.snap_type = snap_type
        self.object = object
        self.obj = object
        self.screen_distance = screen_distance
        self.score = 0.0
        self.normal = normal if normal is not None else Vector((0.0, 0.0, 1.0))
        self.face_index = face_index
        self.matrix = matrix
        self.element = element
        self.screen_pos = None

    def calculate_score(self) -> float:
        radius = TYPE_RADII.get(self.snap_type, 30.0)
        if radius <= 0.0:
            self.score = 0.0
            return self.score

        distance_score = max(0.0, 1.0 - (self.screen_distance / radius) ** 1.45)
        type_weight = TYPE_WEIGHTS.get(self.snap_type, 0.5)
        proximity_bonus = max(0.0, 1.0 - self.screen_distance / 18.0) * 0.18
        self.score = (distance_score * type_weight) + proximity_bonus
        return self.score


class CandidateCache:
    """候選點快取 + hysteresis，避免高光跳動。"""
    def __init__(self):
        self.current_target: Optional[SnapCandidate] = None
        self.last_best: Optional[SnapCandidate] = None
        self.hysteresis_factor = 1.12
        self.sticky_radius = 18.0
        self.release_radius = 52.0

    def can_keep_current(self, mouse_x: float, mouse_y: float) -> bool:
        current = self.current_target
        if current is None:
            return False
        return current.screen_distance <= self.release_radius

    def should_switch_target(self, new_candidate: SnapCandidate) -> bool:
        current = self.current_target
        if current is None:
            return True

        # 同一個點就不用切
        if (
            current.object == new_candidate.object
            and current.snap_type == new_candidate.snap_type
            and (current.location - new_candidate.location).length <= 1e-6
        ):
            return True

        # 若目前仍在很近的 sticky 區域內，保持當前點
        if current.screen_distance <= self.sticky_radius:
            return False

        # 新目標要明顯更好才切換
        return new_candidate.score > (current.score * self.hysteresis_factor)

    def update_target(self, candidate: Optional[SnapCandidate]):
        self.current_target = candidate
        if candidate is not None:
            self.last_best = candidate

    def reset(self):
        self.current_target = None
        self.last_best = None


class SnapEngine:
    """統一的 Screen-Space Snap Engine"""

    def __init__(self):
        self.candidate_cache = CandidateCache()
        self.snap_radii = dict(TYPE_RADII)
        self._apply_settings()

    def _apply_settings(self):
        try:
            if not hasattr(bpy.context, 'scene') or not bpy.context.scene:
                return
            from ..utils.settings import apply_settings_to_snap_engine
            apply_settings_to_snap_engine(self)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────
    # public API
    # ─────────────────────────────────────────────────────
    def find_best_candidate(
        self,
        context,
        mouse_x: float,
        mouse_y: float,
        allowed_types: Optional[Iterable[str]] = None,
        expected_object=None,
        exclude_objects: Optional[Iterable] = None,
    ) -> Optional[SnapCandidate]:
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None

        exclude_set = set(exclude_objects or [])
        allowed = self._normalize_allowed_types(allowed_types)

        hit = self._raycast(context, mouse_x, mouse_y)
        target_obj = None
        hit_location = None
        hit_normal = None
        hit_face_index = -1
        hit_matrix = None

        if hit is not None:
            _, hit_location, hit_normal, hit_face_index, target_obj, hit_matrix = hit
            if target_obj in exclude_set:
                target_obj = None

        # CAD 2.0 風格：若有 expected_object，優先維持意圖
        if expected_object is not None and expected_object not in exclude_set:
            if target_obj is None:
                target_obj = expected_object
            elif target_obj != expected_object:
                # 滑鼠已滑出預期物件表面，仍以 expected_object 掃描 screen-space 最近點
                target_obj = expected_object
                hit_location = None
                hit_normal = None
                hit_face_index = -1
                hit_matrix = expected_object.matrix_world.copy()

        if target_obj is None:
            current = self.candidate_cache.current_target
            if current is not None and current.object not in exclude_set:
                current.screen_distance = self._get_screen_distance(region, rv3d, current.location, mouse_x, mouse_y)
                if current.screen_distance <= self.candidate_cache.release_radius:
                    current.calculate_score()
                    return current
            self.candidate_cache.update_target(None)
            return None

        candidates = self._collect_candidates_for_object(
            context=context,
            obj=target_obj,
            mouse_x=mouse_x,
            mouse_y=mouse_y,
            allowed=allowed,
            hit_location=hit_location,
            hit_normal=hit_normal,
            hit_face_index=hit_face_index,
            hit_matrix=hit_matrix,
        )

        if not candidates:
            current = self.candidate_cache.current_target
            if current is not None and current.object == target_obj:
                current.screen_distance = self._get_screen_distance(region, rv3d, current.location, mouse_x, mouse_y)
                if current.screen_distance <= self.candidate_cache.release_radius:
                    current.calculate_score()
                    return current
            self.candidate_cache.update_target(None)
            return None

        candidates.sort(key=lambda c: c.score, reverse=True)
        best_candidate = candidates[0]

        current = self.candidate_cache.current_target
        if current is not None:
            current.screen_distance = self._get_screen_distance(region, rv3d, current.location, mouse_x, mouse_y)
            current.calculate_score()

        if self.candidate_cache.should_switch_target(best_candidate):
            self.candidate_cache.update_target(best_candidate)
        elif current is None or current.object != target_obj:
            self.candidate_cache.update_target(best_candidate)

        return self.candidate_cache.current_target or best_candidate

    # ─────────────────────────────────────────────────────
    # internal helpers
    # ─────────────────────────────────────────────────────
    def _normalize_allowed_types(self, allowed_types: Optional[Iterable[str]]) -> set:
        if not allowed_types:
            return {"ALL"}
        if isinstance(allowed_types, str):
            allowed_types = [allowed_types]
        out = set()
        for item in allowed_types:
            key = str(item).upper()
            if key == "ALL":
                return {"ALL"}
            out.update(TYPE_ALIASES.get(key, {key}))
        return out or {"ALL"}

    def _is_allowed(self, snap_type: str, allowed: set) -> bool:
        if "ALL" in allowed:
            return True
        return snap_type.upper() in allowed

    def _raycast(self, context, mouse_x: float, mouse_y: float):
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if region is None or rv3d is None:
            return None

        coord = (mouse_x, mouse_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        hit, location, normal, face_index, obj, matrix = context.scene.ray_cast(depsgraph, origin, direction)
        if not hit:
            return None
        return hit, location, normal, face_index, obj, matrix

    def _nearest_point_on_segment(self, p: Vector, a: Vector, b: Vector) -> Vector:
        ab = b - a
        denom = ab.length_squared
        if denom <= 1e-12:
            return a.copy()
        t = (p - a).dot(ab) / denom
        t = max(0.0, min(1.0, t))
        return a + ab * t

    def _apply_feature_dominance(self, candidates: List[SnapCandidate]) -> List[SnapCandidate]:
        """CAD 風格：角點/邊特徵優先於 face hit。"""
        if not candidates:
            return candidates

        vertices = [c for c in candidates if c.snap_type == "VERTEX"]
        edges = [c for c in candidates if c.snap_type in {"EDGE", "MIDPOINT"}]

        best_vertex = min((c.screen_distance for c in vertices), default=float('inf'))
        best_edge = min((c.screen_distance for c in edges), default=float('inf'))

        filtered = []
        for c in candidates:
            st = c.snap_type
            # 靠近角點時，完全壓制 FACE/FACE_CENTER/ORIGIN/BBOX，避免看起來吸到面內部
            if best_vertex <= 18.0 and st in {"FACE", "FACE_CENTER", "ORIGIN", "CENTER", "BBOX"}:
                continue
            # 靠近邊時，不要讓 face hit 搶走
            if best_edge <= 14.0 and st in {"FACE", "FACE_CENTER"}:
                continue
            filtered.append(c)

        return filtered or candidates

    def _collect_candidates_for_object(
        self,
        context,
        obj,
        mouse_x: float,
        mouse_y: float,
        allowed: set,
        hit_location: Optional[Vector],
        hit_normal: Optional[Vector],
        hit_face_index: int,
        hit_matrix,
    ) -> List[SnapCandidate]:
        region = context.region
        rv3d = getattr(context.space_data, "region_3d", None)
        if obj is None or obj.type != 'MESH' or obj.data is None or region is None or rv3d is None:
            return []

        mesh = obj.data
        mw = obj.matrix_world
        candidates: List[SnapCandidate] = []

        def append_candidate(location: Vector, snap_type: str, normal=None, face_index: int = -1, element=None):
            if not self._is_allowed(snap_type, allowed):
                return
            dist = self._get_screen_distance(region, rv3d, location, mouse_x, mouse_y)
            radius = self.snap_radii.get(snap_type, TYPE_RADII.get(snap_type, 30.0))
            if dist == float('inf') or dist > max(radius * 1.35, 44.0):
                return
            cand = SnapCandidate(
                location=location.copy(),
                snap_type=snap_type,
                object=obj,
                screen_distance=dist,
                normal=normal.copy() if hasattr(normal, 'copy') else (normal or Vector((0.0, 0.0, 1.0))),
                face_index=face_index,
                matrix=hit_matrix if hit_matrix is not None else mw.copy(),
                element=element,
            )
            cand.calculate_score()
            candidates.append(cand)

        # 1) 先針對 ray 命中的那個面，建立「局部幾何特徵候選」
        #    這裡是關鍵：不只加 face hit，還要把最近角點/最近邊投影點一起丟進來。
        if 0 <= hit_face_index < len(mesh.polygons):
            poly = mesh.polygons[hit_face_index]
            poly_normal = (mw.to_3x3() @ poly.normal).normalized() if poly.normal.length > 0 else (hit_normal or Vector((0, 0, 1)))

            if hit_location is not None and self._is_allowed("FACE", allowed):
                append_candidate(hit_location, "FACE", normal=poly_normal, face_index=hit_face_index, element=hit_face_index)

            if self._is_allowed("FACE_CENTER", allowed):
                append_candidate(mw @ poly.center, "FACE_CENTER", normal=poly_normal, face_index=hit_face_index, element=hit_face_index)

            # 命中面上的所有頂點
            world_face_verts = []
            for vi in poly.vertices:
                v_world = mw @ mesh.vertices[vi].co
                world_face_verts.append((vi, v_world))
                append_candidate(v_world, "VERTEX", normal=poly_normal, face_index=hit_face_index, element=vi)

            # 命中面的每條邊：加入 midpoint + nearest point on edge
            for key in poly.edge_keys:
                v1_world = mw @ mesh.vertices[key[0]].co
                v2_world = mw @ mesh.vertices[key[1]].co
                mid_world = (v1_world + v2_world) * 0.5
                append_candidate(mid_world, "MIDPOINT", normal=poly_normal, face_index=hit_face_index, element=tuple(key))
                if self._is_allowed("EDGE", allowed) and hit_location is not None:
                    edge_point = self._nearest_point_on_segment(hit_location, v1_world, v2_world)
                    append_candidate(edge_point, "EDGE", normal=poly_normal, face_index=hit_face_index, element=tuple(key))

        # 2) 若局部候選太少，再擴展到整個物件。
        #    但仍然以 screen-space 篩掉太遠的點，避免整個畫面亂吸。
        if len(candidates) < 4:
            if self._is_allowed("VERTEX", allowed):
                for v in mesh.vertices:
                    append_candidate(mw @ v.co, "VERTEX", element=v.index)

            if self._is_allowed("MIDPOINT", allowed) or self._is_allowed("EDGE", allowed):
                for e in mesh.edges:
                    v1 = mw @ mesh.vertices[e.vertices[0]].co
                    v2 = mw @ mesh.vertices[e.vertices[1]].co
                    append_candidate((v1 + v2) * 0.5, "MIDPOINT", element=e.index)
                    if hit_location is not None and self._is_allowed("EDGE", allowed):
                        append_candidate(self._nearest_point_on_segment(hit_location, v1, v2), "EDGE", element=e.index)

            if self._is_allowed("FACE_CENTER", allowed):
                for p in mesh.polygons:
                    p_normal = (mw.to_3x3() @ p.normal).normalized() if p.normal.length > 0 else Vector((0, 0, 1))
                    append_candidate(mw @ p.center, "FACE_CENTER", normal=p_normal, face_index=p.index, element=p.index)

        # 3) origin / bbox 只作輔助，不再主導結果
        append_candidate(mw.translation.copy(), "ORIGIN", normal=Vector((0.0, 0.0, 1.0)), element=None)
        for idx, corner in enumerate(obj.bound_box):
            append_candidate(mw @ Vector(corner), "BBOX", normal=Vector((0.0, 0.0, 1.0)), element=idx)

        candidates = self._apply_feature_dominance(candidates)
        candidates.sort(key=lambda c: (c.score, -c.screen_distance), reverse=True)
        return candidates

    def _get_screen_distance(self, region, rv3d, location: Vector, mouse_x: float, mouse_y: float) -> float:
        try:
            pt2d = view3d_utils.location_3d_to_region_2d(region, rv3d, location)
            if pt2d is None:
                return float('inf')
            return hypot(pt2d.x - mouse_x, pt2d.y - mouse_y)
        except Exception:
            return float('inf')


snap_engine = SnapEngine()
