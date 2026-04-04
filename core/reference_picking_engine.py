"""
Smart Align Pro - Reference Picking Engine
實現 CAD Transform 級別的統一參考點拾取系統
這是超越 CAD Transform 的關鍵系統
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatProperty
from mathutils import Vector, Matrix, geometry
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union
import time

from .topology_alignment import topology_alignment_system
from .snap_priority_solver import get_snap_context, solve_snap_priority
from .coordinate_space_solver import get_coordinate_space_solver, CoordinateSpaceType
from .snap_scoring_engine import SnapCandidate, SnapScoringEngine, select_best

from ..utils.bbox_utils import get_bbox_center_world

class ReferencePointType(Enum):
    """參考點類型枚舉"""
    VERTEX = "VERTEX"
    EDGE = "EDGE"
    FACE = "FACE"
    BBOX_CORNER = "BBOX_CORNER"
    BBOX_CENTER = "BBOX_CENTER"
    ORIGIN = "ORIGIN"
    CUSTOM_AXIS = "CUSTOM_AXIS"
    CURSOR = "CURSOR"


class ReferenceRole(Enum):
    """參考點角色枚舉 - 定義每個點在對齊流程中的角色"""
    SOURCE_ANCHOR = 1
    SOURCE_DIRECTION = 2
    SOURCE_PLANE = 3
    TARGET_ANCHOR = 4
    TARGET_DIRECTION = 5
    TARGET_PLANE = 6


class PickingSession:
    """拾取會話類別"""
    def __init__(self):
        self.session_id = time.time()
        self.reference_points = []
        self.picking_mode = "TWO_POINT"  # TWO_POINT, THREE_POINT, NORMAL, SURFACE
        self.current_step = 0
        self.max_points = 4
        self.is_active = False
        self.target_object = None
        self.source_objects = []
        
        # 拾取設置
        self.snap_tolerance = 0.01
        self.enable_topology_snap = True
        self.enable_bbox_snap = True
        self.enable_cursor_snap = True
        
        # 視覺化設置
        self.show_points = True
        self.show_connections = True
        self.show_labels = True
        
        # 歷史記錄
        self.pick_history = []
        self.max_history = 50


class ReferencePoint:
    """參考點類別"""
    def __init__(self, position: Vector, point_type: ReferencePointType, 
                 object=None, element=None, normal=None, label=None):
        self.position = position
        self.point_type = point_type
        self.object = object
        self.element = element
        self.normal = normal
        self.label = label or f"{point_type.value}_{len(self.get_all_points())}"
        self.timestamp = time.time()
        self.is_valid = True
        
        # 額外屬性
        self.confidence = 1.0
        self.distance = 0.0
        self.weight = 1.0
    
    @staticmethod
    def get_all_points():
        """獲取所有點位的靜態方法"""
        return []


class ReferencePickingEngine:
    """參考點拾取引擎 - CAD Transform 級別的統一參考點拾取系統"""
    
    def __init__(self):
        self.current_session = None
        self.context = None
        self.space_solver = get_coordinate_space_solver()
        
        # 拾取模式
        self.picking_modes = {
            "TWO_POINT": {"max_points": 4, "description": "兩點對齊"},
            "THREE_POINT": {"max_points": 6, "description": "三點對齊"},
            "NORMAL": {"max_points": 2, "description": "法線對齊"},
            "SURFACE": {"max_points": 2, "description": "表面對齊"},
            "EDGE_TO_EDGE": {"max_points": 4, "description": "邊對邊"},
            "FACE_TO_FACE": {"max_points": 6, "description": "面對面"},
        }
        
        # 快捷鍵映射
        self.hotkey_map = {
            "ONE": "TWO_POINT",
            "TWO": "THREE_POINT", 
            "THREE": "NORMAL",
            "FOUR": "SURFACE",
            "FIVE": "EDGE_TO_EDGE",
            "SIX": "FACE_TO_FACE",
        }
        
        # 拾取策略
        self.picking_strategies = {
            ReferencePointType.VERTEX: self._pick_vertex,
            ReferencePointType.EDGE: self._pick_edge,
            ReferencePointType.FACE: self._pick_face,
            ReferencePointType.BBOX_CORNER: self._pick_bbox_corner,
            ReferencePointType.BBOX_CENTER: self._pick_bbox_center,
            ReferencePointType.ORIGIN: self._pick_origin,
            ReferencePointType.CUSTOM_AXIS: self._pick_custom_axis,
            ReferencePointType.CURSOR: self._pick_cursor,
        }
        
        # 會話管理
        self.session_history = []
        self.max_sessions = 10
    
    def set_context(self, context):
        """設置上下文"""
        self.context = context
        self.space_solver.set_context(context)
    
    def start_picking_session(self, picking_mode: str, target_object=None, 
                           source_objects=None) -> PickingSession:
        """啟動拾取會話"""
        # 結束之前的會話
        if self.current_session and self.current_session.is_active:
            self.end_picking_session()
        
        # 創建新會話
        session = PickingSession()
        session.picking_mode = picking_mode
        session.target_object = target_object
        session.source_objects = source_objects or []
        
        # 設置最大點位數
        if picking_mode in self.picking_modes:
            session.max_points = self.picking_modes[picking_mode]["max_points"]
        
        # 設置為活動會話
        self.current_session = session
        session.is_active = True
        
        # 記錄會話歷史
        self.session_history.append({
            "session_id": session.session_id,
            "picking_mode": picking_mode,
            "target_object": target_object.name if target_object else None,
            "start_time": session.session_id,
        })
        
        # 限制歷史長度
        if len(self.session_history) > self.max_sessions:
            self.session_history.pop(0)
        
        return session
    
    def end_picking_session(self):
        """結束拾取會話"""
        if self.current_session:
            self.current_session.is_active = False
            self.current_session = None
    
    def pick_reference_point(self, mouse_pos: tuple, view_vector: Vector, 
                          point_types: List[ReferencePointType] = None) -> Optional[ReferencePoint]:
        """拾取參考點 - 統一拾取接口"""
        if not self.current_session or not self.current_session.is_active:
            return None
        
        # 設置默認拾取類型
        if point_types is None:
            point_types = [
                ReferencePointType.VERTEX,
                ReferencePointType.EDGE,
                ReferencePointType.FACE,
                ReferencePointType.BBOX_CORNER,
                ReferencePointType.BBOX_CENTER,
            ]
        
        # 執行所有拾取策略
        candidates = []
        
        for point_type in point_types:
            if point_type in self.picking_strategies:
                point = self.picking_strategies[point_type](mouse_pos, view_vector)
                if point:
                    candidates.append(point)
        
        # 使用優先級求解器排序
        if candidates:
            snap_context = get_snap_context(self.context)
            sorted_candidates = self._sort_candidates_by_priority(candidates, snap_context)
            
            if sorted_candidates:
                best_candidate = sorted_candidates[0]
                
                # 創建參考點
                ref_point = ReferencePoint(
                    position=best_candidate["position"],
                    point_type=best_candidate["type"],
                    object=best_candidate.get("object"),
                    element=best_candidate.get("element"),
                    normal=best_candidate.get("normal"),
                    label=self._generate_point_label(best_candidate["type"])
                )
                
                # 添加到會話
                self.current_session.reference_points.append(ref_point)
                self.current_session.current_step += 1
                
                # 記錄拾取歷史
                self.current_session.pick_history.append({
                    "step": self.current_session.current_step,
                    "point_type": ref_point.point_type.value,
                    "position": ref_point.position,
                    "object": ref_point.object.name if ref_point.object else None,
                    "timestamp": ref_point.timestamp,
                })
                
                return ref_point
        
        return None
    
    def _pick_vertex(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取頂點"""
        # 射線檢測
        hit_result = self.context.scene.ray_cast(self.context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            if hit_obj and hit_obj.type == "MESH":
                # 使用拓撲對齊系統尋找頂點
                topology_points = topology_alignment_system.solver.find_topology_snap_points(
                    self.context, hit_obj, mouse_pos, view_vector
                )
                
                # 過濾頂點
                vertex_points = [p for p in topology_points if p.snap_type.value == "VERTEX"]
                
                if vertex_points:
                    snap_context = get_snap_context(self.context)
                    sorted_points = solve_snap_priority(vertex_points, snap_context)
                    
                    if sorted_points:
                        topo_point = sorted_points[0]
                        return {
                            "position": topo_point.position,
                            "type": ReferencePointType.VERTEX,
                            "object": hit_obj,
                            "element": topo_point.element,
                            "normal": topo_point.normal,
                            "confidence": topo_point.confidence,
                            "distance": topo_point.distance
                        }
        
        return None
    
    def _pick_edge(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取邊緣"""
        hit_result = self.context.scene.ray_cast(self.context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            if hit_obj and hit_obj.type == "MESH":
                # 使用拓撲對齊系統尋找邊緣
                topology_points = topology_alignment_system.solver.find_topology_snap_points(
                    self.context, hit_obj, mouse_pos, view_vector
                )
                
                # 過濾邊緣
                edge_points = [p for p in topology_points if p.snap_type.value == "EDGE"]
                
                if edge_points:
                    snap_context = get_snap_context(self.context)
                    sorted_points = solve_snap_priority(edge_points, snap_context)
                    
                    if sorted_points:
                        topo_point = sorted_points[0]
                        return {
                            "position": topo_point.position,
                            "type": ReferencePointType.EDGE,
                            "object": hit_obj,
                            "element": topo_point.element,
                            "normal": topo_point.normal,
                            "confidence": topo_point.confidence,
                            "distance": topo_point.distance
                        }
        
        return None
    
    def _pick_face(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取面"""
        hit_result = self.context.scene.ray_cast(self.context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            if hit_obj and hit_obj.type == "MESH":
                # 使用拓撲對齊系統尋找面
                topology_points = topology_alignment_system.solver.find_topology_snap_points(
                    self.context, hit_obj, mouse_pos, view_vector
                )
                
                # 過濾面
                face_points = [p for p in topology_points if p.snap_type.value == "FACE"]
                
                if face_points:
                    snap_context = get_snap_context(self.context)
                    sorted_points = solve_snap_priority(face_points, snap_context)
                    
                    if sorted_points:
                        topo_point = sorted_points[0]
                        return {
                            "position": topo_point.position,
                            "type": ReferencePointType.FACE,
                            "object": hit_obj,
                            "element": topo_point.element,
                            "normal": topo_point.normal,
                            "confidence": topo_point.confidence,
                            "distance": topo_point.distance
                        }
        
        return None
    
    def _pick_bbox_corner(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取邊界框角點"""
        hit_result = self.context.scene.ray_cast(self.context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            if hit_obj:
                # 獲取邊界框
                bbox = hit_obj.bound_box
                world_bbox = [hit_obj.matrix_world @ Vector(corner) for corner in bbox]
                
                # 找到最近的角點
                min_distance = float('inf')
                closest_corner = None
                closest_index = -1
                
                for i, corner in enumerate(world_bbox):
                    distance = (corner - hit_point).length
                    if distance < min_distance:
                        min_distance = distance
                        closest_corner = corner
                        closest_index = i
                
                if closest_corner:
                    return {
                        "position": closest_corner,
                        "type": ReferencePointType.BBOX_CORNER,
                        "object": hit_obj,
                        "element": closest_index,
                        "normal": hit_normal,
                        "confidence": 0.9,
                        "distance": min_distance
                    }
        
        return None
    
    def _pick_bbox_center(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取邊界框中心"""
        hit_result = self.context.scene.ray_cast(self.context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj = hit_result[4]
            
            if hit_obj:
                # 計算邊界框中心
                bbox_center = get_bbox_center_world(hit_obj)
                
                return {
                    "position": bbox_center,
                    "type": ReferencePointType.BBOX_CENTER,
                    "object": hit_obj,
                    "element": None,
                    "normal": Vector((0, 0, 1)),
                    "confidence": 0.8,
                    "distance": (bbox_center - hit_result[1]).length
                }
        
        return None
    
    def _pick_origin(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取原點"""
        if self.context.active_object:
            origin = self.context.active_object.matrix_world @ Vector((0, 0, 0))
            
            return {
                "position": origin,
                "type": ReferencePointType.ORIGIN,
                "object": self.context.active_object,
                "element": None,
                "normal": Vector((0, 0, 1)),
                "confidence": 1.0,
                "distance": (origin - self.context.scene.cursor.location).length
            }
        
        return None
    
    def _pick_custom_axis(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取自定義軸"""
        # 這需要用戶預先定義軸
        # 暫時返回原點
        return self._pick_origin(mouse_pos, view_vector)
    
    def _pick_cursor(self, mouse_pos: tuple, view_vector: Vector) -> Optional[Dict[str, Any]]:
        """拾取游標位置"""
        cursor_pos = self.context.scene.cursor.location
        
        return {
            "position": cursor_pos,
            "type": ReferencePointType.CURSOR,
            "object": None,
            "element": None,
            "normal": Vector((0, 0, 1)),
            "confidence": 1.0,
            "distance": 0.0
        }
    
    def _sort_candidates_by_priority(self, candidates: List[Dict[str, Any]], 
                                 snap_context) -> List[Dict[str, Any]]:
        """
        使用 v7.4 統一 Snap 評分引擎排序候選點
        
        這是核心升級：所有評分都走 SnapScoringEngine
        """
        # 將舊候選格式轉換為 SnapCandidate
        snap_candidates = []
        for candidate in candidates:
            feature_type_map = {
                ReferencePointType.VERTEX: "VERTEX",
                ReferencePointType.EDGE: "EDGE", 
                ReferencePointType.FACE: "FACE",
                ReferencePointType.BBOX_CORNER: "BOUNDING_BOX",
                ReferencePointType.BBOX_CENTER: "CENTER",
                ReferencePointType.ORIGIN: "CENTER",
            }
            
            point_type = candidate.get("type")
            feature_type = feature_type_map.get(point_type, "CENTER")
            
            snap_candidate = SnapCandidate(
                world_pos=candidate.get("position"),
                normal=candidate.get("normal", Vector((0, 0, 1))),
                feature_type=feature_type,
                distance_3d=candidate.get("distance", 0.1),
                screen_distance=0.0,  # 需要計算螢幕距離
                topology_weight=candidate.get("confidence", 0.5),
                target_object=candidate.get("object")
            )
            snap_candidates.append(snap_candidate)
        
        # 使用統一評分引擎選擇最佳候選
        best = select_best(snap_candidates)
        
        if best:
            # 找到對應的原始候選
            for i, snap_cand in enumerate(snap_candidates):
                if snap_cand == best:
                    candidates[i]["priority_score"] = best.score
                    return [candidates[i]]
        
        # 如果沒有找到最佳，返回所有候選（按原始順序）
        return candidates
    
    def _generate_point_label(self, point_type: ReferencePointType) -> str:
        """生成點位標籤"""
        if not self.current_session:
            return f"{point_type.value}_0"
        
        count = len(self.current_session.reference_points)
        return f"{point_type.value}_{count}"
    
    def remove_last_point(self):
        """移除最後一個點位"""
        if self.current_session and self.current_session.reference_points:
            removed_point = self.current_session.reference_points.pop()
            self.current_session.current_step = max(0, self.current_session.current_step - 1)
            return removed_point
        return None
    
    def clear_all_points(self):
        """清除所有點位"""
        if self.current_session:
            self.current_session.reference_points.clear()
            self.current_session.current_step = 0
    
    def get_session_info(self) -> Dict[str, Any]:
        """獲取會話信息"""
        if not self.current_session:
            return {"is_active": False}
        
        return {
            "is_active": self.current_session.is_active,
            "session_id": self.current_session.session_id,
            "picking_mode": self.current_session.picking_mode,
            "current_step": self.current_session.current_step,
            "max_points": self.current_session.max_points,
            "points_count": len(self.current_session.reference_points),
            "points": [
                {
                    "label": point.label,
                    "type": point.point_type.value,
                    "position": point.position,
                    "object": point.object.name if point.object else None,
                }
                for point in self.current_session.reference_points
            ],
            "target_object": self.current_session.target_object.name if self.current_session.target_object else None,
            "source_objects": [obj.name for obj in self.current_session.source_objects],
        }
    
    def get_picking_suggestions(self) -> List[str]:
        """獲取拾取建議"""
        if not self.current_session:
            return []
        
        suggestions = []
        mode = self.current_session.picking_mode
        current_step = self.current_session.current_step
        max_points = self.current_session.max_points
        
        if mode == "TWO_POINT":
            if current_step < 2:
                suggestions.append(f"選擇來源點 {current_step + 1}")
            elif current_step < 4:
                suggestions.append(f"選擇目標點 {current_step - 1}")
            else:
                suggestions.append("兩點對齊完成，按 Enter 執行")
        
        elif mode == "THREE_POINT":
            if current_step < 3:
                suggestions.append(f"選擇來源點 {current_step + 1}")
            elif current_step < 6:
                suggestions.append(f"選擇目標點 {current_step - 2}")
            else:
                suggestions.append("三點對齊完成，按 Enter 執行")
        
        return suggestions
    
    def process_hotkey(self, hotkey: str) -> bool:
        """處理快捷鍵"""
        if hotkey in self.hotkey_map:
            mode = self.hotkey_map[hotkey]
            
            # 結束當前會話並啟動新模式
            self.end_picking_session()
            self.start_picking_session(mode)
            
            return True
        
        return False


# 全域參考點拾取引擎實例
reference_picking_engine = ReferencePickingEngine()


def get_reference_picking_engine() -> ReferencePickingEngine:
    """獲取參考點拾取引擎實例"""
    return reference_picking_engine


def start_picking_session(picking_mode: str, target_object=None, 
                       source_objects=None, context=None) -> PickingSession:
    """啟動拾取會話 - 供外部調用"""
    if context:
        reference_picking_engine.set_context(context)
    
    return reference_picking_engine.start_picking_session(picking_mode, target_object, source_objects)


def end_picking_session():
    """結束拾取會話 - 供外部調用"""
    reference_picking_engine.end_picking_session()


def pick_reference_point(mouse_pos: tuple, view_vector: Vector, 
                      point_types: List[ReferencePointType] = None, 
                      context=None) -> Optional[ReferencePoint]:
    """拾取參考點 - 供外部調用"""
    if context:
        reference_picking_engine.set_context(context)
    
    return reference_picking_engine.pick_reference_point(mouse_pos, view_vector, point_types)


def get_picking_session_info(context=None) -> Dict[str, Any]:
    """獲取拾取會話信息 - 供外部調用"""
    if context:
        reference_picking_engine.set_context(context)
    
    return reference_picking_engine.get_session_info()
