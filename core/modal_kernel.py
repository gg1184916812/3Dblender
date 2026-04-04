"""
Smart Align Pro - 統一 Modal 核心
CAD Transform 級別的統一互動框架

v7.4 升級：新增 InteractionPipeline - 唯一互動主控中心
"""

import bpy
from bpy.types import Operator
from enum import Enum
from mathutils import Vector, Matrix
from typing import Optional, List, Dict, Any, Callable
import time


class ModalState(Enum):
    """Modal 狀態枚舉"""
    IDLE = "IDLE"
    SELECT_SOURCE = "SELECT_SOURCE"
    SELECT_TARGET = "SELECT_TARGET"
    PREVIEW = "PREVIEW"
    EXECUTE = "EXECUTE"
    CANCEL = "CANCEL"


class AlignmentMode(Enum):
    """對齊模式枚舉"""
    TWO_POINT = "TWO_POINT"
    THREE_POINT = "THREE_POINT"
    SURFACE_NORMAL = "SURFACE_NORMAL"
    CONTACT = "CONTACT"
    TOPOLOGY = "TOPOLOGY"
    PIVOT = "PIVOT"


class CoordinateSpace(Enum):
    """坐標空間枚舉"""
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"
    ACTIVE_OBJECT = "ACTIVE_OBJECT"
    SURFACE_TANGENT = "SURFACE_TANGENT"
    FACE_NORMAL = "FACE_NORMAL"
    EDGE_DIRECTION = "EDGE_DIRECTION"
    CUSTOM_THREE_POINT = "CUSTOM_THREE_POINT"


class ConstraintMode(Enum):
    """約束模式枚舉"""
    NONE = "NONE"
    TRANSLATE_ONLY = "TRANSLATE_ONLY"
    ROTATE_ONLY = "ROTATE_ONLY"
    AXIS_LOCK_X = "AXIS_LOCK_X"
    AXIS_LOCK_Y = "AXIS_LOCK_Y"
    AXIS_LOCK_Z = "AXIS_LOCK_Z"
    PLANE_LOCK_XY = "PLANE_LOCK_XY"
    PLANE_LOCK_XZ = "PLANE_LOCK_XZ"
    PLANE_LOCK_YZ = "PLANE_LOCK_YZ"
    KEEP_HEIGHT = "KEEP_HEIGHT"
    KEEP_XY = "KEEP_XY"
    KEEP_SCALE = "KEEP_SCALE"


# ============================================================================
# v7.4 新增：AlignmentRuntimeContext - 統一運行時上下文
# ============================================================================

class AlignmentRuntimeContext:
    """
    對齊運行時上下文 - v7.4 核心升級
    
    統一保存所有 modal、preview、solver 共享的狀態資訊。
    這是統一決策核心的數據中心。
    """
    
    def __init__(self):
        # 互動模式
        self.interaction_mode: Optional[str] = None
        
        # 點位資訊
        self.source_points: List[Vector] = []
        self.target_points: List[Vector] = []
        
        # 候選點與意圖
        self.current_candidate: Optional[Dict[str, Any]] = None
        self.current_intent: Optional[Dict[str, Any]] = None
        self.last_stable_candidate: Optional[Dict[str, Any]] = None
        
        # Solver 與約束
        self.current_solver: Optional[Callable] = None
        self.constraint_mode: Optional[str] = None
        self.axis_lock_state: Optional[Any] = None
        
        # 預覽結果
        self.preview_result: Optional[Any] = None
        self.preview_matrix: Optional[Matrix] = None
        self.original_matrix: Optional[Matrix] = None
        
        # 滑鼠與視圖
        self.mouse_screen_pos: Optional[Vector] = None
        self.mouse_delta: Optional[Vector] = None
        self.view_basis: Optional[Dict[str, Vector]] = None
        
        # 上下文引用
        self.context_ref: Optional[bpy.types.Context] = None
        
        # 時間戳
        self.last_update_time: float = 0.0
        self.frame_count: int = 0
        
    def update_mouse(self, screen_pos: Vector, delta: Vector = None):
        """更新滑鼠位置"""
        self.mouse_screen_pos = screen_pos.copy()
        if delta:
            self.mouse_delta = delta.copy()
        self.last_update_time = time.time()
        self.frame_count += 1
        
    def update_candidate(self, candidate: Dict[str, Any]):
        """更新候選點"""
        # 如果新候選與上次穩定候選相同，保持穩定
        if self._is_same_candidate(candidate, self.last_stable_candidate):
            self.current_candidate = self.last_stable_candidate
        else:
            self.current_candidate = candidate
            # 連續多幀穩定後才設為 last_stable
            if self.frame_count > 3:
                self.last_stable_candidate = candidate
                
    def _is_same_candidate(self, a: Dict, b: Dict) -> bool:
        """檢查是否為同一候選"""
        if a is None or b is None:
            return False
        return (
            a.get('source_obj') == b.get('source_obj') and
            a.get('snap_type') == b.get('snap_type') and
            (a.get('position', Vector()) - b.get('position', Vector())).length < 0.001
        )
        
    def update_view_basis(self, context: bpy.types.Context):
        """更新視圖 basis"""
        try:
            from .view_axis_solver import ViewAxisSolver
            self.view_basis = ViewAxisSolver.get_view_basis(context)
        except ImportError:
            pass
            
    def set_context(self, context: bpy.types.Context):
        """設置上下文引用"""
        self.context_ref = context
        
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典（供調試）"""
        return {
            "interaction_mode": self.interaction_mode,
            "num_source_points": len(self.source_points),
            "num_target_points": len(self.target_points),
            "has_candidate": self.current_candidate is not None,
            "has_intent": self.current_intent is not None,
            "has_preview": self.preview_result is not None,
            "constraint_mode": self.constraint_mode,
            "frame_count": self.frame_count,
        }
        
    def reset(self):
        """重置上下文"""
        self.__init__()


# ============================================================================
# v7.4 新增：InteractionPipeline - 唯一互動主控中心
# ============================================================================

class InteractionPipeline:
    """
    互動管線 - CAD 級 interaction pipeline controller
    
    v7.4 核心升級：從 operator-driven 升級為 pipeline-driven
    
    流程：
    hover update → candidate evaluation → intent inference 
    → solver selection → constraint projection → preview generation → commit execution
    """
    
    def __init__(self, context: bpy.types.Context):
        self.context = context
        self.runtime = AlignmentRuntimeContext()
        self.runtime.set_context(context)
        
        # 當前狀態
        self.current_candidate: Optional[Dict[str, Any]] = None
        self.current_solver: Optional[Callable] = None
        self.current_intent: Optional[Dict[str, Any]] = None
        self.constraint_domain: Optional[Any] = None
        self.preview_result: Optional[Any] = None
        
        # 管線狀態
        self.is_active = False
        self.last_update_time = 0.0
        
    def update_hover(self, hover_data: Dict[str, Any]):
        """
        Step 1: 更新 hover 候選
        
        Args:
            hover_data: 包含候選點資訊的字典
                - position: Vector
                - snap_type: str
                - source_obj: Object
                - element_index: int
                - normal: Vector
        """
        mouse_pos = hover_data.get("screen_pos")
        previous_mouse = self.runtime.mouse_screen_pos.copy() if self.runtime.mouse_screen_pos is not None else None
        mouse_delta = None
        if mouse_pos is not None and previous_mouse is not None:
            mouse_delta = mouse_pos - previous_mouse
        elif mouse_pos is not None:
            mouse_delta = Vector((0, 0))

        self.current_candidate = hover_data
        self.runtime.update_candidate(hover_data)
        if mouse_pos is not None:
            self.runtime.update_mouse(mouse_pos, mouse_delta)
        self.runtime.update_view_basis(self.context)
        self.last_update_time = time.time()
        
    def infer_intent(self) -> Dict[str, Any]:
        """
        Step 2: 推論使用者意圖
        
        使用 sticky_intent 模組進行意圖推論
        """
        if not self.current_candidate:
            return {"type": "NONE", "confidence": 0.0}
        
        # v7.4: 整合 sticky_intent 進行意圖推論
        try:
            from .sticky_intent import infer_user_intent, compute_intent_bias
            
            # 計算意圖偏差
            bias = compute_intent_bias()
            
            # 推論意圖
            intent = infer_user_intent(
                self.current_candidate,
                bias,
                mouse_delta=self.runtime.mouse_delta,
                interaction_mode=self.runtime.interaction_mode or "SMART",
            )
            
            self.current_intent = intent
            self.runtime.current_intent = intent
            return intent
            
        except Exception as e:
            print(f"[InteractionPipeline] Intent inference failed: {e}")
            return {"type": "SMART", "confidence": 0.5}
            
    def select_solver(self, intent: Dict[str, Any]) -> Optional[Callable]:
        """
        Step 3: 根據意圖選擇 solver
        
        使用 workflow_router 進行 solver 路由
        """
        try:
            from .workflow_router import route_solver
            
            solver_func = route_solver(intent)
            self.current_solver = solver_func
            return solver_func
            
        except Exception as e:
            print(f"[InteractionPipeline] Solver selection failed: {e}")
            return None
            
    def apply_constraints(self) -> Optional[Any]:
        """
        Step 4: 建立約束域
        
        使用 constraint_plane_system 建立約束域
        """
        if not self.current_candidate:
            return None
            
        try:
            from .constraint_plane_system import build_constraint_domain
            
            domain = build_constraint_domain(
                self.context,
                self.current_candidate
            )
            
            self.constraint_domain = domain
            return domain
            
        except Exception as e:
            print(f"[InteractionPipeline] Constraint application failed: {e}")
            return None
            
    def compute_preview(self) -> Optional[Any]:
        """
        Step 5: 計算預覽結果
        
        使用 unified_preview_engine 計算預覽
        """
        if not self.current_solver:
            return None
            
        try:
            from .unified_preview_engine import compute_preview_transform
            
            result = compute_preview_transform(
                self.current_solver,
                self.constraint_domain,
                self.current_candidate
            )
            
            self.preview_result = result
            return result
            
        except Exception as e:
            print(f"[InteractionPipeline] Preview computation failed: {e}")
            return None
            
    def commit(self) -> bool:
        """
        Step 6: 執行 commit
        
        使用 preview_result 直接套用，不再重新計算
        """
        if not self.preview_result:
            print("[InteractionPipeline] No preview result to commit")
            return False
            
        try:
            # v7.4: preview = commit，直接套用預覽結果
            if hasattr(self.preview_result, 'apply'):
                self.preview_result.apply()
            elif hasattr(self.preview_result, 'matrix'):
                # 如果有 matrix，套用到活動物件
                active_obj = self.context.active_object
                if active_obj:
                    active_obj.matrix_world = self.preview_result.matrix
            else:
                print("[InteractionPipeline] Preview result has no apply method")
                return False
                
            # 重置意圖歷史
            try:
                from .sticky_intent import confirm_intent_from_commit
                if self.current_intent:
                    confirm_intent_from_commit(self.current_intent)
            except:
                pass
                
            return True
            
        except Exception as e:
            print(f"[InteractionPipeline] Commit failed: {e}")
            return False
            
    def process_full_pipeline(self, hover_data: Dict[str, Any]) -> bool:
        """
        執行完整管線（供 modal 呼叫）
        
        Args:
            hover_data: hover 候選資料
            
        Returns:
            bool: 管線是否成功執行
        """
        # Step 1: 更新 hover
        self.update_hover(hover_data)
        
        # Step 2: 推論意圖
        intent = self.infer_intent()
        
        # Step 3: 選擇 solver
        solver = self.select_solver(intent)
        if not solver:
            return False
            
        # Step 4: 套用約束
        self.apply_constraints()
        
        # Step 5: 計算預覽
        preview = self.compute_preview()
        if not preview:
            return False
            
        return True
        
    def get_pipeline_status(self) -> Dict[str, Any]:
        """獲取管線狀態（供 HUD 顯示）"""
        return {
            "has_candidate": self.current_candidate is not None,
            "has_solver": self.current_solver is not None,
            "has_intent": self.current_intent is not None,
            "has_domain": self.constraint_domain is not None,
            "has_preview": self.preview_result is not None,
            "intent_type": self.current_intent.get("type") if self.current_intent else None,
            "intent_confidence": self.current_intent.get("confidence") if self.current_intent else 0.0,
        }
        
    def reset(self):
        """重置管線"""
        self.current_candidate = None
        self.current_solver = None
        self.current_intent = None
        self.constraint_domain = None
        self.preview_result = None
        self.runtime.reset()
        self.runtime.set_context(self.context)
        self.is_active = False


# ============================================================================
# 原有 ModalKernel 類別（保持向後相容）
# ============================================================================


class ModalPoint:
    """Modal 點位類別"""
    def __init__(self, position: Vector, point_type: str, object=None, element=None, normal=None):
        self.position = position
        self.point_type = point_type  # SOURCE_A, SOURCE_B, TARGET_A, TARGET_B, TARGET_C
        self.object = object
        self.element = element
        self.normal = normal
        self.timestamp = time.time()
        self.is_valid = True


class ModalKernel:
    """統一 Modal 核心 - CAD Transform 級別的互動框架"""
    
    def __init__(self):
        self.state = ModalState.IDLE
        self.mode = AlignmentMode.TWO_POINT
        self.coordinate_space = CoordinateSpace.GLOBAL
        self.constraint_mode = ConstraintMode.NONE
        
        # 點位管理
        self.points: Dict[str, ModalPoint] = {}
        self.max_points = 4  # 根據模式動態調整
        
        # 預覽系統
        self.preview_active = False
        self.preview_matrix = None
        self.preview_object = None
        
        # 約束系統
        self.constraint_active = False
        self.constraint_axis = None
        self.constraint_plane = None
        
        # 互動選項
        self.flip_normal = False
        self.keep_scale = True
        self.minimal_rotation = True
        
        # 歷史記錄
        self.command_history: List[Dict[str, Any]] = []
        self.max_history = 50
        
        # 快捷鍵映射
        self.hotkey_map = self._create_hotkey_map()
        
        # UI 狀態
        self.show_hud = True
        self.show_hint = True
        self.show_preview = True
        
    def _create_hotkey_map(self) -> Dict[str, str]:
        """創建快捷鍵映射"""
        return {
            # 基本操作
            "ESC": "CANCEL",
            "RET": "EXECUTE",
            "SPACE": "EXECUTE",
            
            # 模式切換
            "ONE": "TWO_POINT_MODE",
            "TWO": "THREE_POINT_MODE",
            "THREE": "SURFACE_NORMAL_MODE",
            "FOUR": "CONTACT_MODE",
            "FIVE": "TOPOLOGY_MODE",
            "SIX": "PIVOT_MODE",
            
            # 坐標空間切換
            "G": "GLOBAL_SPACE",
            "L": "LOCAL_SPACE",
            "A": "ACTIVE_OBJECT_SPACE",
            "S": "SURFACE_TANGENT_SPACE",
            "F": "FACE_NORMAL_SPACE",
            "E": "EDGE_DIRECTION_SPACE",
            "C": "CUSTOM_THREE_POINT_SPACE",
            
            # 約束切換
            "X": "AXIS_LOCK_X",
            "Y": "AXIS_LOCK_Y",
            "Z": "AXIS_LOCK_Z",
            "SHIFT_X": "PLANE_LOCK_XY",
            "SHIFT_Y": "PLANE_LOCK_XZ",
            "SHIFT_Z": "PLANE_LOCK_YZ",
            "T": "TRANSLATE_ONLY",
            "R": "ROTATE_ONLY",
            "H": "KEEP_HEIGHT",
            "P": "KEEP_XY",
            "K": "KEEP_SCALE",
            
            # 選項切換
            "N": "FLIP_NORMAL",
            "M": "MINIMAL_ROTATION",
            
            # 預覽控制
            "V": "TOGGLE_PREVIEW",
            "U": "TOGGLE_HUD",
            "I": "TOGGLE_HINT",
            
            # 點位操作
            "BACK_SPACE": "CLEAR_LAST_POINT",
            "DEL": "CLEAR_ALL_POINTS",
            
            # 歷史操作
            "CTRL_Z": "UNDO",
            "CTRL_Y": "REDO",
        }
    
    def start_modal(self, mode: AlignmentMode, context=None):
        """啟動 Modal"""
        self.state = ModalState.SELECT_SOURCE
        self.mode = mode
        self.clear_all_points()
        
        # 根據模式設置最大點位數
        max_points_map = {
            AlignmentMode.TWO_POINT: 4,  # SOURCE_A, SOURCE_B, TARGET_A, TARGET_B
            AlignmentMode.THREE_POINT: 6,  # SOURCE_A, SOURCE_B, SOURCE_C, TARGET_A, TARGET_B, TARGET_C
            AlignmentMode.SURFACE_NORMAL: 2,  # SOURCE, TARGET
            AlignmentMode.CONTACT: 2,  # SOURCE, TARGET
            AlignmentMode.TOPOLOGY: 4,  # SOURCE_A, SOURCE_B, TARGET_A, TARGET_B
            AlignmentMode.PIVOT: 2,  # PIVOT, TARGET
        }
        
        self.max_points = max_points_map.get(mode, 4)
        
        # 記錄命令
        self._record_command("START_MODAL", {"mode": mode.value})
        
        return True
    
    def add_point(self, point: ModalPoint) -> bool:
        """添加點位"""
        if len(self.points) >= self.max_points:
            return False
        
        # 確定點位類型
        point_type = self._get_next_point_type()
        point.point_type = point_type
        
        self.points[point_type] = point
        
        # 檢查是否需要切換狀態
        self._check_state_transition()
        
        # 記錄命令
        self._record_command("ADD_POINT", {
            "type": point_type,
            "position": point.position,
            "object": point.object.name if point.object else None
        })
        
        return True
    
    def _get_next_point_type(self) -> str:
        """獲取下一個點位類型"""
        if self.mode == AlignmentMode.TWO_POINT:
            if "SOURCE_A" not in self.points:
                return "SOURCE_A"
            elif "SOURCE_B" not in self.points:
                return "SOURCE_B"
            elif "TARGET_A" not in self.points:
                return "TARGET_A"
            elif "TARGET_B" not in self.points:
                return "TARGET_B"
        
        elif self.mode == AlignmentMode.THREE_POINT:
            if "SOURCE_A" not in self.points:
                return "SOURCE_A"
            elif "SOURCE_B" not in self.points:
                return "SOURCE_B"
            elif "SOURCE_C" not in self.points:
                return "SOURCE_C"
            elif "TARGET_A" not in self.points:
                return "TARGET_A"
            elif "TARGET_B" not in self.points:
                return "TARGET_B"
            elif "TARGET_C" not in self.points:
                return "TARGET_C"
        
        elif self.mode in [AlignmentMode.SURFACE_NORMAL, AlignmentMode.CONTACT, AlignmentMode.PIVOT]:
            if "SOURCE" not in self.points:
                return "SOURCE"
            elif "TARGET" not in self.points:
                return "TARGET"
        
        elif self.mode == AlignmentMode.TOPOLOGY:
            if "SOURCE_A" not in self.points:
                return "SOURCE_A"
            elif "SOURCE_B" not in self.points:
                return "SOURCE_B"
            elif "TARGET_A" not in self.points:
                return "TARGET_A"
            elif "TARGET_B" not in self.points:
                return "TARGET_B"
        
        return "UNKNOWN"
    
    def _check_state_transition(self):
        """檢查狀態轉換"""
        if self.mode == AlignmentMode.TWO_POINT:
            if "SOURCE_A" in self.points and "SOURCE_B" in self.points:
                self.state = ModalState.SELECT_TARGET
            elif "TARGET_A" in self.points and "TARGET_B" in self.points:
                self.state = ModalState.EXECUTE
        
        elif self.mode == AlignmentMode.THREE_POINT:
            if "SOURCE_A" in self.points and "SOURCE_B" in self.points and "SOURCE_C" in self.points:
                self.state = ModalState.SELECT_TARGET
            elif "TARGET_A" in self.points and "TARGET_B" in self.points and "TARGET_C" in self.points:
                self.state = ModalState.EXECUTE
        
        elif self.mode in [AlignmentMode.SURFACE_NORMAL, AlignmentMode.CONTACT, AlignmentMode.PIVOT]:
            if "SOURCE" in self.points:
                self.state = ModalState.SELECT_TARGET
            elif "TARGET" in self.points:
                self.state = ModalState.EXECUTE
        
        elif self.mode == AlignmentMode.TOPOLOGY:
            if "SOURCE_A" in self.points and "SOURCE_B" in self.points:
                self.state = ModalState.SELECT_TARGET
            elif "TARGET_A" in self.points and "TARGET_B" in self.points:
                self.state = ModalState.EXECUTE
    
    def remove_point(self, point_type: str) -> bool:
        """移除點位"""
        if point_type in self.points:
            del self.points[point_type]
            
            # 可能需要回退狀態
            self._check_state_transition()
            
            # 記錄命令
            self._record_command("REMOVE_POINT", {"type": point_type})
            
            return True
        return False
    
    def clear_all_points(self):
        """清除所有點位"""
        self.points.clear()
        self.state = ModalState.SELECT_SOURCE
        
        # 記錄命令
        self._record_command("CLEAR_ALL_POINTS", {})
    
    def set_mode(self, mode: AlignmentMode):
        """設置對齊模式"""
        self.mode = mode
        self.clear_all_points()
        
        # 記錄命令
        self._record_command("SET_MODE", {"mode": mode.value})
    
    def set_coordinate_space(self, space: CoordinateSpace):
        """設置坐標空間"""
        self.coordinate_space = space
        
        # 記錄命令
        self._record_command("SET_COORDINATE_SPACE", {"space": space.value})
    
    def set_constraint_mode(self, constraint: ConstraintMode):
        """設置約束模式"""
        self.constraint_mode = constraint
        self.constraint_active = (constraint != ConstraintMode.NONE)
        
        # 記錄命令
        self._record_command("SET_CONSTRAINT", {"constraint": constraint.value})
    
    def toggle_option(self, option: str) -> bool:
        """切換選項"""
        if option == "flip_normal":
            self.flip_normal = not self.flip_normal
        elif option == "keep_scale":
            self.keep_scale = not self.keep_scale
        elif option == "minimal_rotation":
            self.minimal_rotation = not self.minimal_rotation
        elif option == "show_hud":
            self.show_hud = not self.show_hud
        elif option == "show_hint":
            self.show_hint = not self.show_hint
        elif option == "show_preview":
            self.show_preview = not self.show_preview
        else:
            return False
        
        # 記錄命令
        self._record_command("TOGGLE_OPTION", {"option": option, "value": getattr(self, option)})
        
        return True
    
    def process_hotkey(self, hotkey: str, context=None) -> Optional[str]:
        """處理快捷鍵"""
        action = self.hotkey_map.get(hotkey)
        
        if not action:
            return None
        
        # 處理模式切換
        if action.endswith("_MODE"):
            mode_map = {
                "TWO_POINT_MODE": AlignmentMode.TWO_POINT,
                "THREE_POINT_MODE": AlignmentMode.THREE_POINT,
                "SURFACE_NORMAL_MODE": AlignmentMode.SURFACE_NORMAL,
                "CONTACT_MODE": AlignmentMode.CONTACT,
                "TOPOLOGY_MODE": AlignmentMode.TOPOLOGY,
                "PIVOT_MODE": AlignmentMode.PIVOT,
            }
            
            if action in mode_map:
                self.set_mode(mode_map[action])
                return f"切換到 {mode_map[action].value} 模式"
        
        # 處理坐標空間切換
        elif action.endswith("_SPACE"):
            space_map = {
                "GLOBAL_SPACE": CoordinateSpace.GLOBAL,
                "LOCAL_SPACE": CoordinateSpace.LOCAL,
                "ACTIVE_OBJECT_SPACE": CoordinateSpace.ACTIVE_OBJECT,
                "SURFACE_TANGENT_SPACE": CoordinateSpace.SURFACE_TANGENT,
                "FACE_NORMAL_SPACE": CoordinateSpace.FACE_NORMAL,
                "EDGE_DIRECTION_SPACE": CoordinateSpace.EDGE_DIRECTION,
                "CUSTOM_THREE_POINT_SPACE": CoordinateSpace.CUSTOM_THREE_POINT,
            }
            
            if action in space_map:
                self.set_coordinate_space(space_map[action])
                return f"切換到 {space_map[action].value} 坐標空間"
        
        # 處理約束切換
        elif action in ["AXIS_LOCK_X", "AXIS_LOCK_Y", "AXIS_LOCK_Z", 
                       "PLANE_LOCK_XY", "PLANE_LOCK_XZ", "PLANE_LOCK_YZ",
                       "TRANSLATE_ONLY", "ROTATE_ONLY", "KEEP_HEIGHT", 
                       "KEEP_XY", "KEEP_SCALE"]:
            
            constraint_map = {
                "AXIS_LOCK_X": ConstraintMode.AXIS_LOCK_X,
                "AXIS_LOCK_Y": ConstraintMode.AXIS_LOCK_Y,
                "AXIS_LOCK_Z": ConstraintMode.AXIS_LOCK_Z,
                "PLANE_LOCK_XY": ConstraintMode.PLANE_LOCK_XY,
                "PLANE_LOCK_XZ": ConstraintMode.PLANE_LOCK_XZ,
                "PLANE_LOCK_YZ": ConstraintMode.PLANE_LOCK_YZ,
                "TRANSLATE_ONLY": ConstraintMode.TRANSLATE_ONLY,
                "ROTATE_ONLY": ConstraintMode.ROTATE_ONLY,
                "KEEP_HEIGHT": ConstraintMode.KEEP_HEIGHT,
                "KEEP_XY": ConstraintMode.KEEP_XY,
                "KEEP_SCALE": ConstraintMode.KEEP_SCALE,
            }
            
            if action in constraint_map:
                self.set_constraint_mode(constraint_map[action])
                return f"設置約束: {constraint_map[action].value}"
        
        # 處理選項切換
        elif action in ["FLIP_NORMAL", "MINIMAL_ROTATION", "TOGGLE_PREVIEW", "TOGGLE_HUD", "TOGGLE_HINT"]:
            option_map = {
                "FLIP_NORMAL": "flip_normal",
                "MINIMAL_ROTATION": "minimal_rotation",
                "TOGGLE_PREVIEW": "show_preview",
                "TOGGLE_HUD": "show_hud",
                "TOGGLE_HINT": "show_hint",
            }
            
            if action in option_map:
                self.toggle_option(option_map[action])
                return f"切換選項: {option_map[action]}"
        
        # 處理點位操作
        elif action == "CLEAR_LAST_POINT":
            if self.points:
                last_point_type = list(self.points.keys())[-1]
                self.remove_point(last_point_type)
                return f"清除最後一個點: {last_point_type}"
        
        elif action == "CLEAR_ALL_POINTS":
            self.clear_all_points()
            return "清除所有點位"
        
        # 處理基本操作
        elif action == "CANCEL":
            self.state = ModalState.CANCEL
            return "取消操作"
        
        elif action == "EXECUTE":
            if self.state == ModalState.EXECUTE:
                return "執行對齊"
            else:
                return "還未準備好執行"
        
        return None
    
    def get_status_info(self) -> Dict[str, Any]:
        """獲取狀態信息"""
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "coordinate_space": self.coordinate_space.value,
            "constraint_mode": self.constraint_mode.value,
            "points_count": len(self.points),
            "max_points": self.max_points,
            "points": {k: v.position for k, v in self.points.items()},
            "flip_normal": self.flip_normal,
            "keep_scale": self.keep_scale,
            "minimal_rotation": self.minimal_rotation,
            "show_hud": self.show_hud,
            "show_preview": self.show_preview,
            "ready_to_execute": self.state == ModalState.EXECUTE,
        }
    
    def get_next_point_hint(self) -> str:
        """獲取下一個點位的提示"""
        if self.state == ModalState.SELECT_SOURCE:
            if self.mode == AlignmentMode.TWO_POINT:
                if "SOURCE_A" not in self.points:
                    return "選擇來源點 A"
                elif "SOURCE_B" not in self.points:
                    return "選擇來源點 B"
            
            elif self.mode == AlignmentMode.THREE_POINT:
                if "SOURCE_A" not in self.points:
                    return "選擇來源點 A"
                elif "SOURCE_B" not in self.points:
                    return "選擇來源點 B"
                elif "SOURCE_C" not in self.points:
                    return "選擇來源點 C"
            
            elif self.mode in [AlignmentMode.SURFACE_NORMAL, AlignmentMode.CONTACT, AlignmentMode.PIVOT]:
                if "SOURCE" not in self.points:
                    return "選擇來源點"
            
            elif self.mode == AlignmentMode.TOPOLOGY:
                if "SOURCE_A" not in self.points:
                    return "選擇來源點 A"
                elif "SOURCE_B" not in self.points:
                    return "選擇來源點 B"
        
        elif self.state == ModalState.SELECT_TARGET:
            if self.mode == AlignmentMode.TWO_POINT:
                if "TARGET_A" not in self.points:
                    return "選擇目標點 A"
                elif "TARGET_B" not in self.points:
                    return "選擇目標點 B"
            
            elif self.mode == AlignmentMode.THREE_POINT:
                if "TARGET_A" not in self.points:
                    return "選擇目標點 A"
                elif "TARGET_B" not in self.points:
                    return "選擇目標點 B"
                elif "TARGET_C" not in self.points:
                    return "選擇目標點 C"
            
            elif self.mode in [AlignmentMode.SURFACE_NORMAL, AlignmentMode.CONTACT, AlignmentMode.PIVOT]:
                if "TARGET" not in self.points:
                    return "選擇目標點"
            
            elif self.mode == AlignmentMode.TOPOLOGY:
                if "TARGET_A" not in self.points:
                    return "選擇目標點 A"
                elif "TARGET_B" not in self.points:
                    return "選擇目標點 B"
        
        elif self.state == ModalState.EXECUTE:
            return "按 Enter 執行對齊"
        
        return "等待操作"
    
    def _record_command(self, command: str, data: Dict[str, Any]):
        """記錄命令"""
        self.command_history.append({
            "command": command,
            "data": data,
            "timestamp": time.time()
        })
        
        # 限制歷史記錄長度
        if len(self.command_history) > self.max_history:
            self.command_history.pop(0)
    
    def get_command_history(self) -> List[Dict[str, Any]]:
        """獲取命令歷史"""
        return self.command_history.copy()
    
    def reset(self):
        """重置 Modal 核心"""
        self.state = ModalState.IDLE
        self.points.clear()
        self.preview_active = False
        self.preview_matrix = None
        self.constraint_active = False
        self.constraint_axis = None
        self.constraint_plane = None
        
        # 記錄命令
        self._record_command("RESET", {})


# 全域 Modal 核心實例
modal_kernel = ModalKernel()


def get_modal_kernel() -> ModalKernel:
    """獲取 Modal 核心實例"""
    return modal_kernel


def start_alignment_modal(mode: AlignmentMode, context=None) -> bool:
    """啟動對齊 Modal - 供外部調用"""
    return modal_kernel.start_modal(mode, context)


def process_modal_hotkey(hotkey: str, context=None) -> Optional[str]:
    """處理 Modal 快捷鍵 - 供外部調用"""
    return modal_kernel.process_hotkey(hotkey, context)


def get_modal_status() -> Dict[str, Any]:
    """獲取 Modal 狀態 - 供外部調用"""
    return modal_kernel.get_status_info()


def get_next_point_hint() -> str:
    """獲取下一個點位提示 - 供外部調用"""
    return modal_kernel.get_next_point_hint()
