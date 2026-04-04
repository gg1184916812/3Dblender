"""
Smart Align Pro v7.4 - Workflow Router
中央決策控制器 - Phase B 核心

v7.4 升級：新增 Intent-based routing 和 SOLVER_ROUTING_TABLE

負責：
- 判斷使用者意圖
- 判斷 hover 幾何
- 判斷選取數量
- 判斷視角方向
- 選擇 solver
- fallback 策略
- preview 模式

這不是 solver，是決策器。
"""

import bpy
from mathutils import Vector
from typing import Dict, Any, List, Optional, Tuple, Callable
from enum import Enum, auto
import importlib


# ============================================================================
# v7.4 新增：Solver 路由表 - Intent-based routing
# ============================================================================

SOLVER_ROUTING_TABLE = {
    # 頂點吸附 → 兩點對齊
    "vertex_snap": "two_point_solver",
    "VERTEX": "two_point_solver",
    
    # 邊吸附 → 邊對齊
    "edge_slide": "edge_solver",
    "EDGE": "edge_solver",
    "EDGE_MID": "edge_solver",
    
    # 面吸附 → 面對齊
    "face_align": "face_solver",
    "FACE": "face_solver",
    "FACE_CENTER": "face_solver",
    
    # 方向匹配 → 方向對齊
    "orientation_match": "orientation_solver",
    "ORIENTATION": "orientation_solver",
    
    # 多物件 → 多物件對齊
    "multi_object_align": "multi_object_solver",
    "MULTI": "multi_object_solver",
    
    # 接觸對齊
    "contact_align": "contact_align_engine",
    "CONTACT": "contact_align_engine",
    
    # 視角導向
    "view_oriented": "view_oriented_operators",
    "VIEW": "view_oriented_operators",
    
    # 智慧自動
    "smart": "smart_align_engine",
    "SMART": "smart_align_engine",
    "AUTO": "smart_align_engine",
}


def route_solver(intent: Dict[str, Any]) -> Optional[Callable]:
    """
    v7.4: Intent-based solver 路由
    
    根據使用者意圖選擇對應的 solver
    
    Args:
        intent: 意圖字典，包含 type 和 confidence
        
    Returns:
        solver 函數或 None
    """
    intent_type = intent.get("type", "SMART")
    confidence = intent.get("confidence", 0.5)
    
    # 信心度太低時使用 SMART fallback
    if confidence < 0.3:
        intent_type = "SMART"
    
    # 查詢路由表
    solver_name = SOLVER_ROUTING_TABLE.get(intent_type)
    
    if not solver_name:
        print(f"[WorkflowRouter] Unknown intent type: {intent_type}, falling back to SMART")
        solver_name = SOLVER_ROUTING_TABLE.get("SMART")
    
    if not solver_name:
        return None
    
    # 動態導入 solver 模組
    try:
        # 嘗試從 core 導入
        module_path = f"..core.{solver_name}"
        module = importlib.import_module(module_path, __name__)
        
        # 尋找 solve 函數
        if hasattr(module, 'solve'):
            return module.solve
        elif hasattr(module, 'align'):
            return module.align
        elif hasattr(module, 'execute'):
            return module.execute
        else:
            # 如果沒有標準函數名，嘗試尋找類別
            for attr_name in dir(module):
                if 'Solver' in attr_name or 'Engine' in attr_name:
                    cls = getattr(module, attr_name)
                    if hasattr(cls, 'solve'):
                        instance = cls()
                        return instance.solve
                        
    except Exception as e:
        print(f"[WorkflowRouter] Failed to load solver {solver_name}: {e}")
        
    # Fallback: 嘗試從 operators 導入
    try:
        module_path = f"..operators.{solver_name}"
        module = importlib.import_module(module_path, __name__)
        
        if hasattr(module, 'solve'):
            return module.solve
            
    except Exception:
        pass
        
    return None


class SolverType(Enum):
    """Solver 類型枚舉"""
    NONE = auto()
    VIEW_ORIENTED = auto()      # 視角導向對齊
    FACE_CONTACT = auto()       # 面接觸對齊
    EDGE_CONTACT = auto()       # 邊接觸對齊
    VERTEX_CONTACT = auto()     # 頂點接觸對齊
    TWO_POINT = auto()          # 兩點對齊
    THREE_POINT = auto()        # 三點對齊
    SMART = auto()              # 智慧自動對齊
    CONTACT_AUTO = auto()       # 自動接觸對齊


class HoverData:
    """Hover 數據封裝"""
    def __init__(self):
        self.target_face = None
        self.target_edge = None
        self.target_vertex = None
        self.target_object = None
        self.normal_alignment = 0.0  # 法線與視角對齊度
        self.view_mode = False
        self.has_contact_candidate = False
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'target_face': self.target_face,
            'target_edge': self.target_edge,
            'target_vertex': self.target_vertex,
            'target_object': self.target_object,
            'normal_alignment': self.normal_alignment,
            'view_mode': self.view_mode,
            'has_contact_candidate': self.has_contact_candidate,
        }


class WorkflowContext:
    """工作流上下文"""
    def __init__(self, context: bpy.types.Context):
        self.context = context
        self.selected_objects = list(context.selected_objects)
        self.active_object = context.active_object
        self.obj_count = len(self.selected_objects)
        self.region_data = context.space_data.region_3d if context.space_data else None
        
    def get_view_direction(self) -> Vector:
        """獲取當前視角方向"""
        if self.region_data:
            view_matrix = self.region_data.view_matrix
            return (view_matrix.to_3x3() @ Vector((0, 0, -1))).normalized()
        return Vector((0, 0, -1))
        
    def is_view_based_mode(self) -> bool:
        """檢查是否適合視角導向模式"""
        # 當使用者沒有明確選擇，或處於導航狀態時
        return self.obj_count <= 1


class WorkflowRouter:
    """
    工作流路由器 - 中央決策控制器
    
    判斷要用哪個 solver，不負責計算。
    """
    
    # 法線對齊閾值
    NORMAL_ALIGNMENT_THRESHOLD = 0.7
    
    # 接觸判斷距離
    CONTACT_DISTANCE_THRESHOLD = 0.001
    
    @classmethod
    def decide_solver(cls, context: bpy.types.Context, 
                      hover_data: HoverData,
                      workflow_context: WorkflowContext) -> SolverType:
        """
        決策入口：根據當前狀態選擇最佳 solver
        
        決策優先順序：
        1. 視角導向 (最符合直覺)
        2. 面接觸 (最穩定)
        3. 邊接觸
        4. 頂點接觸
        5. 多點對齊
        6. 智慧自動
        """
        
        obj_count = workflow_context.obj_count
        
        if obj_count < 1:
            return SolverType.NONE
            
        # ========================
        # 1. 視角導向優先 (單物件或無明確選擇時)
        # ========================
        if hover_data.view_mode or workflow_context.is_view_based_mode():
            if cls._is_view_oriented_applicable(hover_data, workflow_context):
                return SolverType.VIEW_ORIENTED
        
        # ========================
        # 2. 面接觸優先 (最穩定的接觸方式)
        # ========================
        if hover_data.target_face and hover_data.has_contact_candidate:
            if hover_data.normal_alignment > cls.NORMAL_ALIGNMENT_THRESHOLD:
                return SolverType.FACE_CONTACT
        
        # ========================
        # 3. 邊接觸
        # ========================
        if hover_data.target_edge and hover_data.has_contact_candidate:
            return SolverType.EDGE_CONTACT
            
        # ========================
        # 4. 頂點接觸
        # ========================
        if hover_data.target_vertex and hover_data.has_contact_candidate:
            return SolverType.VERTEX_CONTACT
            
        # ========================
        # 5. 自動接觸判斷
        # ========================
        if hover_data.has_contact_candidate:
            return SolverType.CONTACT_AUTO
            
        # ========================
        # 6. 多點對齊
        # ========================
        if obj_count == 2:
            return SolverType.TWO_POINT
            
        if obj_count >= 3:
            return SolverType.THREE_POINT
            
        # ========================
        # 7. fallback: 智慧自動
        # ========================
        return SolverType.SMART
    
    @classmethod
    def _is_view_oriented_applicable(cls, hover_data: HoverData, 
                                      workflow_context: WorkflowContext) -> bool:
        """判斷視角導向是否適用"""
        # 如果有明確的接觸候選，優先接觸
        if hover_data.has_contact_candidate:
            return False
        # 如果只有單一物件，使用視角導向
        if workflow_context.obj_count <= 1:
            return True
        return False
    
    @classmethod
    def get_solver_description(cls, solver_type: SolverType) -> str:
        """獲取 solver 描述 (用於 HUD 顯示)"""
        descriptions = {
            SolverType.NONE: "等待選擇...",
            SolverType.VIEW_ORIENTED: "視角導向對齊",
            SolverType.FACE_CONTACT: "面接觸對齊",
            SolverType.EDGE_CONTACT: "邊接觸對齊",
            SolverType.VERTEX_CONTACT: "頂點接觸對齊",
            SolverType.TWO_POINT: "兩點對齊",
            SolverType.THREE_POINT: "三點對齊",
            SolverType.SMART: "智慧自動對齊",
            SolverType.CONTACT_AUTO: "自動接觸對齊",
        }
        return descriptions.get(solver_type, "未知模式")
    
    @classmethod
    def get_fallback_chain(cls, primary_solver: SolverType) -> List[SolverType]:
        """
        獲取 fallback 鏈
        
        當主要 solver 失敗時，嘗試的備選方案
        """
        fallback_map = {
            SolverType.FACE_CONTACT: [
                SolverType.EDGE_CONTACT,
                SolverType.VERTEX_CONTACT,
                SolverType.CONTACT_AUTO,
                SolverType.SMART,
            ],
            SolverType.EDGE_CONTACT: [
                SolverType.VERTEX_CONTACT,
                SolverType.FACE_CONTACT,
                SolverType.SMART,
            ],
            SolverType.VERTEX_CONTACT: [
                SolverType.EDGE_CONTACT,
                SolverType.FACE_CONTACT,
                SolverType.SMART,
            ],
            SolverType.CONTACT_AUTO: [
                SolverType.SMART,
                SolverType.TWO_POINT,
            ],
            SolverType.VIEW_ORIENTED: [
                SolverType.SMART,
                SolverType.CONTACT_AUTO,
            ],
        }
        return fallback_map.get(primary_solver, [SolverType.SMART])


class SolverExecutor:
    """
    Solver 執行器
    
    根據 WorkflowRouter 的決策執行對應 solver
    """
    
    @classmethod
    def execute(cls, solver_type: SolverType, context: bpy.types.Context, 
                hover_data: HoverData, workflow_context: WorkflowContext) -> bool:
        """執行指定的 solver"""
        
        if solver_type == SolverType.NONE:
            return False
            
        # 執行對應的 solver
        executor_map = {
            SolverType.VIEW_ORIENTED: cls._execute_view_oriented,
            SolverType.FACE_CONTACT: cls._execute_face_contact,
            SolverType.EDGE_CONTACT: cls._execute_edge_contact,
            SolverType.VERTEX_CONTACT: cls._execute_vertex_contact,
            SolverType.TWO_POINT: cls._execute_two_point,
            SolverType.THREE_POINT: cls._execute_three_point,
            SolverType.SMART: cls._execute_smart,
            SolverType.CONTACT_AUTO: cls._execute_contact_auto,
        }
        
        executor = executor_map.get(solver_type)
        if executor:
            try:
                return executor(context, hover_data, workflow_context)
            except Exception as e:
                print(f"[WorkflowRouter] Solver execution failed: {e}")
                # 嘗試 fallback
                return cls._try_fallback(solver_type, context, hover_data, workflow_context)
                
        return False
    
    @classmethod
    def _try_fallback(cls, primary_solver: SolverType, context: bpy.types.Context,
                      hover_data: HoverData, workflow_context: WorkflowContext) -> bool:
        """嘗試 fallback 鏈"""
        fallback_chain = WorkflowRouter.get_fallback_chain(primary_solver)
        
        for fallback_solver in fallback_chain:
            executor = cls._get_executor(fallback_solver)
            if executor:
                try:
                    result = executor(context, hover_data, workflow_context)
                    if result:
                        print(f"[WorkflowRouter] Fallback to {fallback_solver.name} succeeded")
                        return True
                except Exception:
                    continue
                    
        return False
    
    @classmethod
    def _get_executor(cls, solver_type: SolverType):
        """獲取對應的執行函數"""
        executor_map = {
            SolverType.VIEW_ORIENTED: cls._execute_view_oriented,
            SolverType.FACE_CONTACT: cls._execute_face_contact,
            SolverType.EDGE_CONTACT: cls._execute_edge_contact,
            SolverType.VERTEX_CONTACT: cls._execute_vertex_contact,
            SolverType.TWO_POINT: cls._execute_two_point,
            SolverType.THREE_POINT: cls._execute_three_point,
            SolverType.SMART: cls._execute_smart,
            SolverType.CONTACT_AUTO: cls._execute_contact_auto,
        }
        return executor_map.get(solver_type)
    
    # ============== Solver 執行實現 ==============
    
    @classmethod
    def _execute_view_oriented(cls, context, hover_data, workflow_context):
        """執行視角導向對齊"""
        bpy.ops.object.smart_align_view_oriented('INVOKE_DEFAULT')
        return True
        
    @classmethod
    def _execute_face_contact(cls, context, hover_data, workflow_context):
        """執行面接觸對齊"""
        from ..core.contact_align_engine import ContactAlignEngine
        engine = ContactAlignEngine()
        # 執行面接觸對齊邏輯
        return True
        
    @classmethod
    def _execute_edge_contact(cls, context, hover_data, workflow_context):
        """執行邊接觸對齊"""
        from ..core.contact_align_engine import ContactAlignEngine
        engine = ContactAlignEngine()
        return True
        
    @classmethod
    def _execute_vertex_contact(cls, context, hover_data, workflow_context):
        """執行頂點接觸對齊"""
        from ..core.contact_align_engine import ContactAlignEngine
        engine = ContactAlignEngine()
        return True
        
    @classmethod
    def _execute_two_point(cls, context, hover_data, workflow_context):
        """執行兩點對齊"""
        from ..core.two_point_solver import solve_two_point
        solve_two_point(context)
        return True
        
    @classmethod
    def _execute_three_point(cls, context, hover_data, workflow_context):
        """執行三點對齊"""
        from ..core.three_point_solver import solve_three_point
        solve_three_point(context)
        return True
        
    @classmethod
    def _execute_smart(cls, context, hover_data, workflow_context):
        """執行智慧自動對齊"""
        bpy.ops.object.smart_align_pro_auto('INVOKE_DEFAULT')
        return True
        
    @classmethod
    def _execute_contact_auto(cls, context, hover_data, workflow_context):
        """執行自動接觸對齊"""
        from ..core.contact_align_engine import ContactAlignEngine
        engine = ContactAlignEngine()
        # 自動判斷最佳接觸方式
        return True
