"""
Smart Align Pro - 拓撲對齊系統
實現 vertex/edge/face snap align，超越 CAD Transform
v7.3: 修正 SnapType 相容、雙重 world transform、bmesh 釋放
"""

import bpy
import bmesh
from enum import Enum
from mathutils import Vector, geometry
from .math_utils import get_closest_point_on_line, get_closest_point_on_triangle


class SnapType(str, Enum):
    VERTEX = "VERTEX"
    EDGE = "EDGE"
    FACE = "FACE"
    RAY = "RAY"


class TopologySnapPoint:
    """拓撲吸附點類別，兼容舊/新呼叫方式"""

    def __init__(self, point=None, snap_type=SnapType.VERTEX, element=None, normal=None, **kwargs):
        if point is None and "position" in kwargs:
            point = kwargs.pop("position")
        self.position = point
        if isinstance(snap_type, str):
            try:
                self.snap_type = SnapType(snap_type)
            except Exception:
                self.snap_type = snap_type
        else:
            self.snap_type = snap_type
        self.object = kwargs.pop("object", None)
        self.element = element if element is not None else kwargs.pop("element", None)
        self.normal = normal
        self.distance = kwargs.pop("distance", 0.0)
        self.confidence = kwargs.pop("confidence", 1.0)

    @property
    def snap_type_name(self):
        return self.snap_type.value if hasattr(self.snap_type, "value") else str(self.snap_type)


class TopologyAlignmentSolver:
    def __init__(self):
        self.tolerance = 0.01
        self.priority_order = [SnapType.VERTEX.value, SnapType.EDGE.value, SnapType.FACE.value]

    def find_topology_snap_points(self, context, obj, mouse_pos, view_vector):
        if obj.type != "MESH":
            return []

        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bm.transform(obj.matrix_world)
            snap_points = []
            ray_result = context.scene.ray_cast(context.view_layer.depsgraph, mouse_pos, view_vector)
            if ray_result[0]:
                hit_point = ray_result[1]
                hit_normal = ray_result[2]
                hit_face_index = ray_result[3]
                hit_face = bm.faces[hit_face_index] if hit_face_index < len(bm.faces) else None
                vertex_snap = self._find_vertex_snap(bm, hit_point, obj)
                if vertex_snap:
                    snap_points.append(vertex_snap)
                edge_snap = self._find_edge_snap(bm, hit_point, obj)
                if edge_snap:
                    snap_points.append(edge_snap)
                if hit_face:
                    face_snap = self._find_face_snap(bm, hit_face, hit_point, obj)
                    if face_snap:
                        snap_points.append(face_snap)
            snap_points.sort(key=lambda x: self._get_priority_score(x))
            return snap_points
        finally:
            bm.free()

    def _find_vertex_snap(self, bm, target_point, obj=None):
        closest_vertex = None
        min_distance = float('inf')
        for vert in bm.verts:
            distance = (vert.co - target_point).length
            if distance < min_distance and distance < self.tolerance:
                min_distance = distance
                closest_vertex = vert
        if closest_vertex:
            snap_point = TopologySnapPoint(point=closest_vertex.co.copy(), snap_type=SnapType.VERTEX, element=closest_vertex, normal=(closest_vertex.normal if closest_vertex.normal else None), object=obj)
            snap_point.distance = min_distance
            snap_point.confidence = 1.0 - (min_distance / self.tolerance)
            return snap_point
        return None

    def _find_edge_snap(self, bm, target_point, obj=None):
        closest_edge = None
        min_distance = float('inf')
        closest_point = None
        for edge in bm.edges:
            edge_point = get_closest_point_on_line(target_point, edge.verts[0].co, edge.verts[1].co)
            distance = (edge_point - target_point).length
            if distance < min_distance and distance < self.tolerance:
                min_distance = distance
                closest_edge = edge
                closest_point = edge_point
        if closest_edge:
            snap_point = TopologySnapPoint(point=closest_point, snap_type=SnapType.EDGE, element=closest_edge, normal=self._calculate_edge_normal(closest_edge), object=obj)
            snap_point.distance = min_distance
            snap_point.confidence = 1.0 - (min_distance / self.tolerance)
            return snap_point
        return None

    def _find_face_snap(self, bm, face, hit_point, obj=None):
        face_center = face.calc_center_median()
        face_normal = face.normal
        if self._is_point_in_face(hit_point, face):
            snap_point = TopologySnapPoint(point=hit_point.copy(), snap_type=SnapType.FACE, element=face, normal=face_normal, object=obj)
            snap_point.distance = (hit_point - face_center).length
            snap_point.confidence = 0.9
            return snap_point
        return None

    def _calculate_edge_normal(self, edge):
        if len(edge.link_faces) >= 2:
            normal = Vector((0, 0, 0))
            for face in edge.link_faces:
                normal += face.normal
            return normal.normalized()
        elif len(edge.link_faces) == 1:
            return edge.link_faces[0].normal
        else:
            edge_dir = (edge.verts[1].co - edge.verts[0].co).normalized()
            fallback = Vector((edge_dir.y, -edge_dir.x, 0))
            if fallback.length == 0:
                fallback = Vector((0, 0, 1))
            return fallback.normalized()

    def _is_point_in_face(self, point, face):
        if len(face.verts) == 3:
            v1, v2, v3 = face.verts[0].co, face.verts[1].co, face.verts[2].co
            return geometry.intersect_point_tri(point, v1, v2, v3) is not None
        elif len(face.verts) == 4:
            v1, v2, v3, v4 = face.verts[0].co, face.verts[1].co, face.verts[2].co, face.verts[3].co
            return (geometry.intersect_point_tri(point, v1, v2, v3) is not None or geometry.intersect_point_tri(point, v1, v3, v4) is not None)
        return False

    def _get_priority_score(self, snap_point):
        snap_name = snap_point.snap_type.value if hasattr(snap_point.snap_type, "value") else str(snap_point.snap_type)
        try:
            base_score = self.priority_order.index(snap_name)
        except ValueError:
            base_score = len(self.priority_order)
        distance_factor = snap_point.distance / self.tolerance if self.tolerance else 0.0
        confidence_factor = snap_point.confidence
        return base_score + distance_factor * 0.3 + confidence_factor * 0.2

    def align_to_topology_point(self, source_obj, target_snap_point, source_snap_point=None):
        if source_snap_point is None:
            from ..utils.bbox_utils import get_bbox_center_world
            source_point = get_bbox_center_world(source_obj)
        else:
            source_point = source_snap_point.position
        translation = target_snap_point.position - source_point
        if (source_snap_point and source_snap_point.normal and target_snap_point.normal):
            rotation = source_snap_point.normal.rotation_difference(target_snap_point.normal)
            source_obj.rotation_euler.rotate(rotation)
        source_obj.location += translation
        return {
            'source_point': source_point,
            'target_point': target_snap_point.position,
            'translation': translation,
            'snap_type': (target_snap_point.snap_type.value if hasattr(target_snap_point.snap_type, "value") else target_snap_point.snap_type),
            'element': target_snap_point.element
        }


class TopologyAlignmentOperator:
    def __init__(self):
        self.solver = TopologyAlignmentSolver()
        self.source_snap = None
        self.target_snap = None
        self.current_snap_points = []
        self.snap_mode = "VERTEX"

    def set_snap_mode(self, mode):
        self.snap_mode = mode
        if mode == "AUTO":
            self.solver.priority_order = ["VERTEX", "EDGE", "FACE"]
        elif mode == "VERTEX":
            self.solver.priority_order = ["VERTEX", "EDGE", "FACE"]
        elif mode == "EDGE":
            self.solver.priority_order = ["EDGE", "VERTEX", "FACE"]
        elif mode == "FACE":
            self.solver.priority_order = ["FACE", "EDGE", "VERTEX"]

    def find_snap_at_cursor(self, context, obj):
        mouse_pos = (context.region.width // 2, context.region.height // 2)
        view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
        self.current_snap_points = self.solver.find_topology_snap_points(context, obj, mouse_pos, view_vector)
        return self.current_snap_points[0] if self.current_snap_points else None

    def set_source_point(self, snap_point):
        self.source_snap = snap_point
        return snap_point is not None

    def set_target_point(self, snap_point):
        self.target_snap = snap_point
        return snap_point is not None

    def execute_alignment(self, context, source_obj):
        if self.source_snap and self.target_snap:
            result = self.solver.align_to_topology_point(source_obj, self.target_snap, self.source_snap)
            self.source_snap = None
            self.target_snap = None
            self.current_snap_points = []
            return result
        return None


topology_alignment_system = TopologyAlignmentOperator()
