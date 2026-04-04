"""
Smart Align Pro - 吸附優先級求解器
實現超越 CAD Transform 的智能優先級系統
"""

import bpy
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
from mathutils import Vector
from .topology_alignment import TopologySnapPoint


class SnapType(Enum):
    """吸附類型枚舉"""
    VERTEX = "VERTEX"
    EDGE = "EDGE"
    FACE = "FACE"
    MIDPOINT = "MIDPOINT"
    CENTER = "CENTER"
    INTERSECTION = "INTERSECTION"
    NORMAL = "NORMAL"


class SnapPriority(Enum):
    """吸附優先級枚舉"""
    HIGHEST = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    LOWEST = 5


@dataclass
class SnapPriorityRule:
    """吸附優先級規則"""
    snap_type: SnapType
    priority: SnapPriority
    distance_weight: float = 1.0
    confidence_weight: float = 1.0
    angle_weight: float = 0.0
    context_multiplier: float = 1.0


@dataclass
class SnapContext:
    """吸附上下文"""
    object_type: str  # "MESH", "CURVE", "EMPTY", etc.
    workflow_mode: str  # "PRECISION", "QUICK", "ARCHITECTURAL", etc.
    user_preference: str  # "VERTEX_FIRST", "EDGE_FIRST", "FACE_FIRST", "AUTO"
    current_tool: str  # "ALIGN", "SNAP", "CONSTRAINT", etc.
    view_mode: str  # "OBJECT", "EDIT", "SCULPT", etc.


class SnapPrioritySolver:
    """吸附優先級求解器 - 這是超越 CAD Transform 的核心"""
    
    def __init__(self):
        self.priority_rules = self._create_default_rules()
        self.context_rules = self._create_context_rules()
        self.user_profiles = self._create_user_profiles()
        
    def _create_default_rules(self) -> Dict[SnapType, SnapPriorityRule]:
        """創建默認優先級規則"""
        return {
            SnapType.VERTEX: SnapPriorityRule(
                SnapType.VERTEX, SnapPriority.HIGHEST, 1.0, 1.0, 0.0, 1.0
            ),
            SnapType.EDGE: SnapPriorityRule(
                SnapType.EDGE, SnapPriority.HIGH, 1.0, 0.9, 0.1, 1.0
            ),
            SnapType.FACE: SnapPriorityRule(
                SnapType.FACE, SnapPriority.MEDIUM, 1.0, 0.8, 0.2, 1.0
            ),
            SnapType.MIDPOINT: SnapPriorityRule(
                SnapType.MIDPOINT, SnapPriority.HIGH, 1.0, 0.95, 0.0, 0.8
            ),
            SnapType.CENTER: SnapPriorityRule(
                SnapType.CENTER, SnapPriority.MEDIUM, 1.0, 0.9, 0.0, 0.9
            ),
            SnapType.INTERSECTION: SnapPriorityRule(
                SnapType.INTERSECTION, SnapPriority.HIGHEST, 1.0, 1.0, 0.0, 1.2
            ),
            SnapType.NORMAL: SnapPriorityRule(
                SnapType.NORMAL, SnapPriority.LOW, 1.0, 0.7, 0.3, 0.7
            ),
        }
    
    def _create_context_rules(self) -> Dict[str, Dict[SnapType, float]]:
        """創建上下文規則"""
        return {
            "PRECISION": {
                SnapType.VERTEX: 1.5,
                SnapType.INTERSECTION: 1.4,
                SnapType.EDGE: 1.2,
                SnapType.MIDPOINT: 1.1,
                SnapType.FACE: 0.8,
                SnapType.CENTER: 0.7,
                SnapType.NORMAL: 0.5,
            },
            "QUICK": {
                SnapType.FACE: 1.3,
                SnapType.CENTER: 1.2,
                SnapType.EDGE: 1.1,
                SnapType.VERTEX: 1.0,
                SnapType.MIDPOINT: 0.9,
                SnapType.NORMAL: 0.7,
                SnapType.INTERSECTION: 0.6,
            },
            "ARCHITECTURAL": {
                SnapType.FACE: 1.4,
                SnapType.CENTER: 1.3,
                SnapType.VERTEX: 1.0,
                SnapType.EDGE: 0.9,
                SnapType.MIDPOINT: 0.8,
                SnapType.NORMAL: 0.6,
                SnapType.INTERSECTION: 0.5,
            },
            "MECHANICAL": {
                SnapType.VERTEX: 1.5,
                SnapType.EDGE: 1.3,
                SnapType.INTERSECTION: 1.2,
                SnapType.MIDPOINT: 1.0,
                SnapType.FACE: 0.8,
                SnapType.CENTER: 0.7,
                SnapType.NORMAL: 0.6,
            },
            "ARTISTIC": {
                SnapType.FACE: 1.5,
                SnapType.CENTER: 1.4,
                SnapType.EDGE: 1.2,
                SnapType.MIDPOINT: 1.1,
                SnapType.VERTEX: 0.9,
                SnapType.NORMAL: 0.8,
                SnapType.INTERSECTION: 0.7,
            }
        }
    
    def _create_user_profiles(self) -> Dict[str, List[SnapType]]:
        """創建用戶配置文件"""
        return {
            "VERTEX_FIRST": [SnapType.VERTEX, SnapType.INTERSECTION, SnapType.MIDPOINT, 
                          SnapType.EDGE, SnapType.FACE, SnapType.CENTER, SnapType.NORMAL],
            "EDGE_FIRST": [SnapType.EDGE, SnapType.MIDPOINT, SnapType.VERTEX, 
                        SnapType.INTERSECTION, SnapType.FACE, SnapType.CENTER, SnapType.NORMAL],
            "FACE_FIRST": [SnapType.FACE, SnapType.CENTER, SnapType.EDGE, SnapType.MIDPOINT,
                        SnapType.VERTEX, SnapType.INTERSECTION, SnapType.NORMAL],
            "BALANCED": [SnapType.VERTEX, SnapType.EDGE, SnapType.FACE, SnapType.MIDPOINT,
                       SnapType.CENTER, SnapType.INTERSECTION, SnapType.NORMAL],
            "PRECISION": [SnapType.VERTEX, SnapType.INTERSECTION, SnapType.MIDPOINT,
                        SnapType.EDGE, SnapType.FACE, SnapType.CENTER, SnapType.NORMAL],
            "SPEED": [SnapType.FACE, SnapType.CENTER, SnapType.EDGE, SnapType.VERTEX,
                     SnapType.MIDPOINT, SnapType.INTERSECTION, SnapType.NORMAL],
        }
    
    def calculate_priority_score(self, snap_point: TopologySnapPoint, 
                             context: SnapContext) -> float:
        """計算吸附點的優先級分數 - 這是超越 CAD Transform 的核心算法"""
        
        # 獲取基礎規則
        base_rule = self.priority_rules.get(snap_point.snap_type)
        if not base_rule:
            return 0.0
        
        # 計算基礎分數
        base_score = (SnapPriority.HIGHEST.value - base_rule.priority.value + 1) * 100
        
        # 距離因子 (距離越近分數越高)
        distance_factor = max(0, 1.0 - snap_point.distance / 0.1)  # 0.1 是最大考慮距離
        distance_score = distance_factor * base_rule.distance_weight * 50
        
        # 信心度因子
        confidence_score = snap_point.confidence * base_rule.confidence_weight * 30
        
        # 角度因子 (如果有法線)
        angle_score = 0.0
        if base_rule.angle_weight > 0 and snap_point.normal:
            # 這裡可以添加更複雜的角度計算
            angle_score = base_rule.angle_weight * 20
        
        # 上下文因子
        context_multiplier = self._get_context_multiplier(snap_point.snap_type, context)
        context_score = base_score * context_multiplier
        
        # 綜合分數
        total_score = (
            base_score * 0.4 +
            distance_score * 0.3 +
            confidence_score * 0.2 +
            angle_score * 0.1
        ) * context_multiplier
        
        return total_score
    
    def _get_context_multiplier(self, snap_type: SnapType, context: SnapContext) -> float:
        """獲取上下文乘數"""
        # 工作流程模式乘數
        workflow_multipliers = self.context_rules.get(context.workflow_mode, {})
        workflow_multiplier = workflow_multipliers.get(snap_type, 1.0)
        
        # 用戶偏好乘數
        user_profile = self.user_profiles.get(context.user_preference, self.user_profiles["BALANCED"])
        user_preference_multiplier = 1.0
        if snap_type in user_profile:
            position = user_profile.index(snap_type)
            user_preference_multiplier = 1.0 + (len(user_profile) - position) * 0.1
        
        # 物件類型乘數
        object_type_multiplier = 1.0
        if context.object_type == "MESH":
            if snap_type in [SnapType.VERTEX, SnapType.EDGE, SnapType.FACE]:
                object_type_multiplier = 1.2
        elif context.object_type == "CURVE":
            if snap_type in [SnapType.VERTEX, SnapType.MIDPOINT]:
                object_type_multiplier = 1.3
        elif context.object_type == "EMPTY":
            if snap_type == SnapType.CENTER:
                object_type_multiplier = 1.5
        
        # 工具模式乘數
        tool_multiplier = 1.0
        if context.current_tool == "ALIGN":
            if snap_type in [SnapType.VERTEX, SnapType.INTERSECTION]:
                tool_multiplier = 1.2
        elif context.current_tool == "SNAP":
            tool_multiplier = 1.1
        
        return workflow_multiplier * user_preference_multiplier * object_type_multiplier * tool_multiplier
    
    def sort_snap_points(self, snap_points: List[TopologySnapPoint], 
                       context: SnapContext) -> List[TopologySnapPoint]:
        """根據優先級排序吸附點"""
        for snap_point in snap_points:
            snap_point.priority_score = self.calculate_priority_score(snap_point, context)
        
        # 按優先級分數排序
        sorted_points = sorted(snap_points, key=lambda x: x.priority_score, reverse=True)
        
        return sorted_points
    
    def get_best_snap_point(self, snap_points: List[TopologySnapPoint], 
                         context: SnapContext) -> Optional[TopologySnapPoint]:
        """獲取最佳吸附點"""
        if not snap_points:
            return None
        
        sorted_points = self.sort_snap_points(snap_points, context)
        return sorted_points[0] if sorted_points else None
    
    def filter_snap_points_by_priority(self, snap_points: List[TopologySnapPoint], 
                                  min_priority: SnapPriority) -> List[TopologySnapPoint]:
        """根據最小優先級過濾吸附點"""
        filtered_points = []
        for snap_point in snap_points:
            rule = self.priority_rules.get(snap_point.snap_type)
            if rule and rule.priority.value <= min_priority.value:
                filtered_points.append(snap_point)
        
        return filtered_points
    
    def update_user_preference(self, user_preference: str):
        """更新用戶偏好"""
        if user_preference in self.user_profiles:
            # 這裡可以保存到設置中
            pass
    
    def get_priority_info(self, snap_type: SnapType) -> Dict[str, any]:
        """獲取優先級信息"""
        rule = self.priority_rules.get(snap_type)
        if not rule:
            return {}
        
        return {
            "type": snap_type.value,
            "priority": rule.priority.name,
            "distance_weight": rule.distance_weight,
            "confidence_weight": rule.confidence_weight,
            "angle_weight": rule.angle_weight,
            "context_multiplier": rule.context_multiplier,
        }
    
    def create_snap_priority_stack(self, snap_points: List[TopologySnapPoint], 
                                context: SnapContext) -> List[Dict[str, any]]:
        """創建吸附優先級堆棧"""
        sorted_points = self.sort_snap_points(snap_points, context)
        
        priority_stack = []
        for i, snap_point in enumerate(sorted_points):
            priority_info = {
                "rank": i + 1,
                "snap_point": snap_point,
                "score": snap_point.priority_score,
                "type": snap_point.snap_type.value,
                "distance": snap_point.distance,
                "confidence": snap_point.confidence,
                "position": snap_point.position,
                "normal": snap_point.normal,
            }
            priority_stack.append(priority_info)
        
        return priority_stack


# 全域優先級求解器實例
snap_priority_solver = SnapPrioritySolver()


def get_snap_context(context) -> SnapContext:
    """獲取當前吸附上下文"""
    settings = context.scene.smartalignpro_settings if hasattr(context.scene, 'smartalignpro_settings') else None
    
    workflow_mode = "PRECISION"
    user_preference = "BALANCED"
    
    if settings:
        workflow_mode = getattr(settings, 'workflow_mode', 'PRECISION')
        user_preference = getattr(settings, 'snap_user_preference', 'BALANCED')
    
    # 獲取活動物件類型
    object_type = "UNKNOWN"
    if context.active_object:
        object_type = context.active_object.type
    
    # 獲取當前工具
    current_tool = context.mode
    
    return SnapContext(
        object_type=object_type,
        workflow_mode=workflow_mode,
        user_preference=user_preference,
        current_tool=current_tool,
        view_mode=context.mode
    )


def solve_snap_priority(snap_points: List[TopologySnapPoint], 
                      context: SnapContext = None) -> List[TopologySnapPoint]:
    """解決吸附優先級 - 供外部調用"""
    if context is None:
        # 使用默認上下文
        context = SnapContext(
            object_type="MESH",
            workflow_mode="PRECISION",
            user_preference="BALANCED",
            current_tool="ALIGN",
            view_mode="OBJECT"
        )
    
    return snap_priority_solver.sort_snap_points(snap_points, context)


def get_best_snap_point(snap_points: List[TopologySnapPoint], 
                      context: SnapContext = None) -> Optional[TopologySnapPoint]:
    """獲取最佳吸附點 - 供外部調用"""
    if context is None:
        context = get_snap_context(bpy.context)
    
    return snap_priority_solver.get_best_snap_point(snap_points, context)
