"""
Smart Align Pro - Contact Align Engine
智慧接觸對齊引擎 - 自動判斷接觸方式
"""

import bpy
from mathutils import Vector, geometry
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass

from .math_utils import get_closest_point_on_triangle


class ContactType(Enum):
    """接觸類型枚舉"""
    FACE_TO_FACE = "FACE_TO_FACE"
    EDGE_TO_EDGE = "EDGE_TO_EDGE"
    VERT_TO_VERT = "VERT_TO_VERT"
    FACE_TO_EDGE = "FACE_TO_EDGE"
    EDGE_TO_FACE = "EDGE_TO_FACE"
    VERT_TO_FACE = "VERT_TO_FACE"
    VERT_TO_EDGE = "VERT_TO_EDGE"
    AUTO = "AUTO"
    CENTER = "CENTER"
    CYLINDER_TANGENT = "CYLINDER_TANGENT"


@dataclass
class ContactAlignment:
    """接觸對齊結果"""
    contact_type: ContactType
    offset_vector: Vector
    rotation_aligned: bool
    confidence: float
    contact_points: List[Vector]
    penetration_depth: float = 0.0


@dataclass
class ContactCandidate:
    """接觸候選"""
    source_point: Vector
    target_point: Vector
    target_normal: Vector
    feature_type: str
    distance: float


class ContactAlignEngine:
    """
    v7.4 智慧接觸對齊引擎 - 三階段求解器
    
    架構：
    1. Broad Phase: bbox 快速過濾候選
    2. Narrow Phase: vertex-face / edge-edge 精確計算
    3. Offset Solver: 最小位移向量 (MTV)
    """
    
    def __init__(self):
        self.collision_threshold = 0.001
        self.bbox_expansion = 0.1  # bbox 擴展緩衝
        
    # =========================================================================
    # Phase 1: Broad Phase - 快速候選過濾
    # =========================================================================
    
    def broad_phase_candidates(self, source_obj, target_obj) -> List[ContactCandidate]:
        """
        Broad Phase: 使用 bbox 和簡單幾何測試快速過濾候選
        將候選從 O(n*m) 降到 O(k)
        """
        candidates = []
        
        # 獲取目標物件的 bbox（世界座標）
        target_bbox_min, target_bbox_max = self._get_bbox_bounds_world(target_obj)
        target_bbox_min -= Vector((self.bbox_expansion,) * 3)
        target_bbox_max += Vector((self.bbox_expansion,) * 3)
        
        # 遍歷來源物件的所有頂點
        if source_obj.type == 'MESH' and source_obj.data:
            for vertex in source_obj.data.vertices:
                world_vertex = source_obj.matrix_world @ vertex.co
                
                # 快速 bbox 測試
                if self._point_in_bbox(world_vertex, target_bbox_min, target_bbox_max):
                    # 找到最近的目標點
                    closest_point, normal, distance = self._find_closest_point_on_target(
                        world_vertex, target_obj
                    )
                    if closest_point:
                        candidates.append(ContactCandidate(
                            source_point=world_vertex,
                            target_point=closest_point,
                            target_normal=normal,
                            feature_type="VERTEX",
                            distance=distance
                        ))
        
        return candidates
    
    def _get_bbox_bounds_world(self, obj) -> Tuple[Vector, Vector]:
        """獲取物件 bbox 的世界座標邊界"""
        bbox_local = [Vector(corner) for corner in obj.bound_box]
        bbox_world = [obj.matrix_world @ p for p in bbox_local]
        
        min_bound = Vector((
            min(p.x for p in bbox_world),
            min(p.y for p in bbox_world),
            min(p.z for p in bbox_world)
        ))
        max_bound = Vector((
            max(p.x for p in bbox_world),
            max(p.y for p in bbox_world),
            max(p.z for p in bbox_world)
        ))
        
        return min_bound, max_bound
    
    def _point_in_bbox(self, point: Vector, bbox_min: Vector, bbox_max: Vector) -> bool:
        """檢查點是否在 bbox 內"""
        return (bbox_min.x <= point.x <= bbox_max.x and
                bbox_min.y <= point.y <= bbox_max.y and
                bbox_min.z <= point.z <= bbox_max.z)
    
    def _find_closest_point_on_target(self, point: Vector, target_obj) -> Tuple[Optional[Vector], Optional[Vector], float]:
        """在目標物件表面上找到離給定點最近的真正表面點

        v7.5 封頂版：
        1. 不再只投影到 face 平面
        2. 改為逐三角形計算真正的最近點
        3. 投影若落在面外，會自然退回邊或頂點
        """
        if target_obj.type != 'MESH' or not target_obj.data:
            return None, None, float('inf')

        mesh = target_obj.data
        matrix_world = target_obj.matrix_world
        normal_matrix = matrix_world.to_3x3()

        min_distance = float('inf')
        closest_point = None
        closest_normal = None

        for face in mesh.polygons:
            world_indices = list(face.vertices)
            if len(world_indices) < 3:
                continue

            face_world_verts = [
                matrix_world @ mesh.vertices[i].co
                for i in world_indices
            ]

            face_normal_world = (normal_matrix @ face.normal).normalized()

            # 將 ngon / quad 扇形三角化
            base = face_world_verts[0]
            for i in range(1, len(face_world_verts) - 1):
                a = base
                b = face_world_verts[i]
                c = face_world_verts[i + 1]

                tri_closest = get_closest_point_on_triangle(point, a, b, c)
                dist = (tri_closest - point).length

                if dist < min_distance:
                    min_distance = dist
                    closest_point = tri_closest
                    closest_normal = face_normal_world

        return closest_point, closest_normal, min_distance
    
    # =========================================================================
    # Phase 2: Narrow Phase - 精確接觸計算
    # =========================================================================
    
    def compute_vertex_face_contact(self, source_vertex: Vector,
                                     target_face_center: Vector,
                                     target_face_normal: Vector) -> Optional[Vector]:
        """
        計算頂點到面的接觸偏移
        核心算法：計算頂點需要移動多少才能剛好接觸到面
        """
        to_vertex = source_vertex - target_face_center
        signed_distance = to_vertex.dot(target_face_normal)
        
        # 如果頂點已經在面的前方，不需要移動
        if signed_distance > 0:
            return None
            
        # 計算偏移向量
        offset = -signed_distance * target_face_normal
        return offset
    
    def detect_contact_alignment(self, source, target) -> ContactType:
        """
        v7.4 自動判斷接觸類型
        使用 broad phase 候選來判斷最佳接觸類型
        """
        # 使用新的 broad phase 獲取候選
        candidates = self.broad_phase_candidates(source, target)
        
        if not candidates:
            return ContactType.CENTER
            
        # 根據候選類型判斷
        vertex_count = sum(1 for c in candidates if c.feature_type == "VERTEX")
        edge_count = sum(1 for c in candidates if c.feature_type == "EDGE")
        
        if vertex_count > edge_count:
            return ContactType.VERT_TO_FACE
        elif edge_count > 0:
            return ContactType.EDGE_TO_FACE
        else:
            return ContactType.FACE_TO_FACE
    
    def _get_bbox_world_points(self, obj) -> List[Vector]:
        """獲取物件邊界框的世界座標點"""
        bbox_local = [Vector(corner) for corner in obj.bound_box]
        return [obj.matrix_world @ p for p in bbox_local]
    
    def _world_to_local(self, obj, point: Vector) -> Vector:
        """世界座標轉換為本地座標"""
        return obj.matrix_world.inverted() @ point
    
    def _classify_contact(self, source_obj, source_point: Vector,
                         target_obj, target_point: Vector) -> ContactType:
        """分類接觸類型"""
        source_normal = self._estimate_normal_at_point(source_obj, source_point)
        target_normal = self._estimate_normal_at_point(target_obj, target_point)
        
        if source_normal and target_normal:
            angle = abs(source_normal.angle(target_normal))
            
            if angle < 0.1:
                return ContactType.FACE_TO_FACE
            elif angle > 2.5:
                return ContactType.VERT_TO_VERT
        
        return ContactType.CENTER
    
    def _estimate_normal_at_point(self, obj, point: Vector) -> Optional[Vector]:
        """估算點處的法線"""
        if obj.type != 'MESH':
            return Vector((0, 0, 1))
        
        depsgraph = bpy.context.evaluated_depsgraph_get()
        try:
            hit, loc, norm, idx, obj, mat = bpy.context.scene.ray_cast(
                depsgraph,
                point + Vector((0, 0, 1)) * 0.1,
                Vector((0, 0, -1))
            )
            if hit:
                return norm.normalized()
        except Exception:
            pass
        
        return Vector((0, 0, 1))
    
    def compute_contact_offset(self, source, target,
                               contact_type: ContactType = None) -> Vector:
        """計算接觸偏移向量

        v7.6 最後封頂版：
        1. 不再使用 bbox corner 對 bbox corner 當主求解
        2. 改為 source 候選點 -> target 真表面最近點
        3. 真正接上 _find_closest_point_on_target() 的三角形最近點能力
        """
        if contact_type is None:
            contact_type = self.detect_contact_alignment(source, target)

        candidates = self.broad_phase_candidates(source, target)
        if not candidates:
            return self._fallback_bbox_offset(source, target)

        best_distance = float("inf")
        best_offset = None

        source_center = self._get_bbox_center(source)
        target_center = self._get_bbox_center(target)
        center_dir = target_center - source_center

        for cand in candidates:
            source_point = cand.world_pos

            closest_point, closest_normal, dist = self._find_closest_point_on_target(
                source_point,
                target
            )

            if closest_point is None or closest_normal is None:
                continue

            delta = closest_point - source_point

            # 法線方向一致性檢查：避免選到反向或不合理解
            if delta.length > 1e-8:
                if delta.dot(closest_normal) < 0:
                    offset = closest_normal * abs(delta.dot(closest_normal))
                else:
                    offset = delta
            else:
                if center_dir.length > 1e-8:
                    offset = center_dir.normalized() * 0.001
                else:
                    offset = closest_normal * 0.001

            offset_len = offset.length

            # 根據 feature type 做輕量權重偏好
            feature_bias = {
                "VERTEX": 0.0,
                "EDGE": 0.0005,
                "FACE": 0.0010,
                "CENTER": 0.0020,
                "BOUNDING_BOX": 0.0030,
            }.get(getattr(cand, "feature_type", "BOUNDING_BOX"), 0.0030)

            score = offset_len + feature_bias

            if score < best_distance:
                best_distance = score
                best_offset = offset

        if best_offset is None:
            return self._fallback_bbox_offset(source, target)

        return best_offset
    
    def _fallback_bbox_offset(self, source, target) -> Vector:
        """回退方法：使用 bbox 中心計算偏移"""
        source_center = self._get_bbox_center(source)
        target_center = self._get_bbox_center(target)
        
        direction = target_center - source_center
        distance = direction.length
        
        if distance < 0.001:
            return Vector((0, 0, 0))
            
        # 考慮物件尺寸
        source_extent = self._get_max_extent(source)
        target_extent = self._get_max_extent(target)
        
        desired_distance = source_extent + target_extent + 0.001
        offset = direction.normalized() * (distance - desired_distance)
        
        return offset
    
    def _get_bbox_center(self, obj) -> Vector:
        """獲取物件邊界框中心"""
        bbox = self._get_bbox_world_points(obj)
        return sum(bbox, Vector((0, 0, 0))) / 8.0
    
    def _estimate_penetration(self, source, source_point: Vector,
                             target, target_point: Vector) -> float:
        """估算穿透深度"""
        direction = target_point - source_point
        distance = direction.length
        
        if distance < 0.001:
            return 0.0
        
        source_extent = self._get_max_extent(source)
        target_extent = self._get_max_extent(target)
        
        combined_extent = source_extent + target_extent
        
        if distance < combined_extent:
            return combined_extent - distance
        
        return 0.0
    
    # =========================================================================
    # v7.4 新增：Candidate Scoring 評分系統
    # =========================================================================
    
    def score_candidate(self, candidate: ContactCandidate, 
                       view_dir: Vector = None) -> float:
        """
        評分接觸候選點
        
        評分維度：
        1. 法線方向合理度 (與視角對齊度)
        2. 面積穩定性 (大面優先)
        3. 距離合理性
        4. 是否容易穿模
        5. 是否符合當前模式
        
        分數越高越優先選擇
        """
        score = 0.0
        
        # 1. 距離評分 (越近越好)
        distance_score = max(0, 1.0 - candidate.distance / 10.0)
        score += distance_score * 0.3  # 30% 權重
        
        # 2. 法線合理性 (與視角方向對齊度)
        if view_dir:
            normal_alignment = abs(candidate.target_normal.dot(view_dir))
            score += normal_alignment * 0.25  # 25% 權重
        
        # 3. 特徵類型偏好
        feature_scores = {
            "FACE": 0.20,
            "EDGE": 0.15,
            "VERTEX": 0.10,
        }
        score += feature_scores.get(candidate.feature_type, 0.0)
        
        # 4. 穩定性加成 (小位移優先)
        if candidate.distance < 0.1:
            score += 0.15  # 穩定選擇獎勵
        
        return score
    
    def select_best_candidate(self, candidates: List[ContactCandidate],
                            view_dir: Vector = None) -> Optional[ContactCandidate]:
        """
        選擇最佳接觸候選點
        
        使用評分系統選出最適合的候選
        """
        if not candidates:
            return None
        
        best_candidate = None
        best_score = -float('inf')
        
        for candidate in candidates:
            score = self.score_candidate(candidate, view_dir)
            
            if score > best_score:
                best_score = score
                best_candidate = candidate
        
        return best_candidate
    
    def _get_max_extent(self, obj) -> float:
        """獲取物件最大範圍"""
        dimensions = obj.dimensions
        return max(dimensions.x, dimensions.y, dimensions.z)
    
    def solve_contact_alignment(self, source, target,
                                contact_type: ContactType = None,
                                apply_offset: bool = True) -> ContactAlignment:
        """執行接觸對齊求解
        
        v7.4 升級：使用評分系統選擇最佳候選
        
        Returns:
            ContactAlignment: 包含對齊結果的資料類別
        """
        if contact_type is None:
            contact_type = self.detect_contact_alignment(source, target)
        
        # v7.4: 獲取所有候選並評分
        candidates = self.broad_phase_candidates(source, target)
        
        if candidates:
            # 獲取當前視角方向
            context = bpy.context
            view_dir = None
            if context.space_data and context.space_data.region_3d:
                view_matrix = context.space_data.region_3d.view_matrix
                view_dir = (view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))).normalized()
            
            # 選擇最佳候選
            best_candidate = self.select_best_candidate(candidates, view_dir)
            
            if best_candidate:
                # 使用最佳候選計算偏移
                offset = self._compute_offset_from_candidate(best_candidate, target)
            else:
                offset = self.compute_contact_offset(source, target, contact_type)
        else:
            offset = self.compute_contact_offset(source, target, contact_type)
        
        alignment = ContactAlignment(
            contact_type=contact_type,
            offset_vector=offset,
            rotation_aligned=(contact_type in [ContactType.FACE_TO_FACE]),
            confidence=0.85,
            contact_points=[]
        )
        
        if apply_offset:
            source.location += offset
        
        return alignment
    
    def get_contact_preview(self, source, target) -> Dict[str, Any]:
        """獲取接觸預覽信息"""
        contact_type = self.detect_contact_alignment(source, target)
        offset = self.compute_contact_offset(source, target, contact_type)
        
        return {
            "contact_type": contact_type.value,
            "offset": offset,
            "confidence": 0.85,
            "will_collide": offset.length < 0.001,
        }
    
    # ============================================================================
    # v7.4 新增：Tangent Solver 最小可擴充結構
    # ============================================================================
    
    def solve_tangent_contact(self, source, target, contact_type: ContactType):
        """
        v7.4: Tangent Contact Solver 入口
        
        預留架構位置，供未來實現：
        - 圓柱/球對平面切觸
        - 邊對圓柱切觸
        - 圓柱對圓柱外切
        """
        if contact_type == ContactType.CYLINDER_TANGENT:
            return self._solve_cylinder_tangent(source, target)
        
        # Fallback: 使用標準接觸求解
        return self.solve_contact_alignment(source, target, contact_type)
    
    def _solve_cylinder_tangent(self, source, target):
        """
        v7.4: Cylinder Tangent Solver (預留實現)
        
        TODO: 實現圓柱切觸求解
        - 計算 source 圓柱半徑
        - 計算 target 圓柱半徑
        - 計算兩軸最近點
        - 計算外切偏移向量
        """
        # 預留實現：回傳標準接觸結果
        print("[ContactAlignEngine] Cylinder tangent solver not yet implemented, using standard contact")
        return self.solve_contact_alignment(source, target, ContactType.FACE_TO_FACE)
    
    def _solve_plane_tangent(self, source, target):
        """
        v7.4: Plane Tangent Solver (預留實現)
        
        TODO: 實現平面切觸求解
        - 計算 source 圓柱/球到 target 平面的最近點
        - 計算切觸偏移向量
        """
        print("[ContactAlignEngine] Plane tangent solver not yet implemented")
        return None
    
    def _solve_edge_cylinder_tangent(self, source, target):
        """
        v7.4: Edge to Cylinder Tangent Solver (預留實現)
        
        TODO: 實現邊對圓柱切觸
        - 計算邊線到圓柱軸的最近點
        - 計算外切偏移向量
        """
        print("[ContactAlignEngine] Edge-cylinder tangent solver not yet implemented")
        return None


contact_align_engine = ContactAlignEngine()


def get_contact_align_engine() -> ContactAlignEngine:
    """獲取接觸對齊引擎實例"""
    return contact_align_engine


def detect_contact_alignment(source, target) -> ContactType:
    """自動判斷接觸類型 - 供外部調用"""
    return contact_align_engine.detect_contact_alignment(source, target)


def solve_contact_alignment(source, target, 
                           contact_type: ContactType = None) -> ContactAlignment:
    """執行接觸對齊求解 - 供外部調用"""
    return contact_align_engine.solve_contact_alignment(source, target, contact_type)
