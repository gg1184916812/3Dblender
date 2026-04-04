import bpy
import bgl
import blf
from enum import Enum, auto
from mathutils import Vector, Matrix
from .modal_base import SmartAlignModalBase
from typing import Optional, Dict, Any
import time


class UltimateWorkflowStage(Enum):
    """終極對齊工作流階段枚舉"""
    # 簡單模式 (預設) - 3步完成
    SIMPLE_SOURCE = auto()      # 選擇來源點
    SIMPLE_TARGET = auto()      # 選擇目標點  
    SIMPLE_PREVIEW = auto()     # 預覽確認
    
    # 進階模式 - 完整控制
    SOURCE_ANCHOR = auto()
    SOURCE_DIRECTION = auto()
    SOURCE_PLANE = auto()
    TARGET_ANCHOR = auto()
    TARGET_DIRECTION = auto()
    TARGET_PLANE = auto()
    ADVANCED_PREVIEW = auto()
    
    FINISH = auto()


class UltimateModeLevel(Enum):
    """操作模式層級 - 雙層架構核心"""
    SIMPLE = auto()      # 簡單模式：source → target → confirm
    ADVANCED = auto()    # 進階模式：direction/plane/axis lock/multi-anchor


class UltimateWorkflowMode(Enum):
    """終極對齊工作流模式枚舉"""
    TWO_POINT = auto()
    THREE_POINT = auto()
    SURFACE_NORMAL = auto()
    CONTACT = auto()
    AUTO = auto()


class SMARTALIGNPRO_OT_ultimate_modal(SmartAlignModalBase):
    """Smart Align Pro Ultimate - 終極對齊操作器
    
    超越 CAD Transform 120% 的 CAD 級對齊體驗
    使用統一的狀態機、智慧選點、柔和吸附、軸鎖定系統
    """
    bl_idname = "smartalignpro.ultimate_modal"
    bl_label = "Smart Align Pro Ultimate"
    bl_description = "超越 CAD Transform 的終極對齊體驗"
    bl_options = {"REGISTER", "UNDO"}

    def _initialize_specific_modal(self, context, event) -> bool:
        """初始化終極引擎 - 整合所有智慧系統
        
        v7.5 雙層模式架構：
        - 預設 Simple Mode: source → target → preview → confirm (3步)
        - 切換 Advanced Mode: direction/plane/axis lock (完整控制)
        """
        # 雙層模式核心：預設簡單模式
        self.mode_level = UltimateModeLevel.SIMPLE
        self.workflow_mode = UltimateWorkflowMode.AUTO
        self.workflow_stage = UltimateWorkflowStage.SIMPLE_SOURCE

        self.points_by_role: Dict[str, Any] = {}
        self.hover_candidate = None
        self.preview_matrix = None

        self.active_obj = context.active_object
        self.original_matrix = self.active_obj.matrix_world.copy() if self.active_obj else None

        from ..core.reference_picking_engine import ReferencePickingEngine
        self.reference_engine = ReferencePickingEngine()
        self.reference_engine.set_context(context)

        from ..core.ultimate.snap_engine import UltimateSnapEngine
        from ..core.ultimate.alignment_solver import AlignmentSolverStack
        self.snap_engine = UltimateSnapEngine()
        self.solver_stack = AlignmentSolverStack()
        self.snap_engine.update_candidates(context)

        from ..core.smart_pick_engine import SmartPickEngine, detect_selection_role
        self.smart_pick = SmartPickEngine()
        self.selection_intent = detect_selection_role(context)

        from ..core.soft_snap_engine import SoftSnapEngine
        self.soft_snap = SoftSnapEngine()

        from ..core.contact_align_engine import ContactAlignEngine
        self.contact_engine = ContactAlignEngine()

        from ..core.zero_mode_controller import ZeroModeController, auto_detect_alignment_mode
        self.zero_mode = ZeroModeController()
        self.zero_mode.current_mode = auto_detect_alignment_mode(context)

        from ..core.axis_locking_system import AxisLockingSystem, AxisLockType
        self.axis_lock = AxisLockingSystem()
        self.axis_lock.set_context(context)

        # v7.4: 整合 Workflow Router - 中央決策控制器
        from ..core.workflow_router import WorkflowRouter, HoverData, WorkflowContext, SolverType
        self.workflow_router = WorkflowRouter()
        self.hover_data = HoverData()
        self.workflow_context = WorkflowContext(context)
        self.active_solver = SolverType.NONE

        # v7.4: 整合 Sticky Intent - 避免 hover 抖動
        from ..core.sticky_intent import get_sticky_manager
        self.sticky_manager = get_sticky_manager()

        self.mouse_prev_pos = Vector((event.mouse_region_x, event.mouse_region_y))
        self.mouse_vel = Vector((0, 0))

        # 雙層模式標籤
        self._stage_labels = {
            # 簡單模式
            "SIMPLE_SOURCE": "第1步：點選來源物件的對齊點",
            "SIMPLE_TARGET": "第2步：點選目標位置",
            "SIMPLE_PREVIEW": "第3步：確認對齊 (Enter確認 / ESC取消)",
            # 進階模式
            "SOURCE_ANCHOR": "進階：來源基準點",
            "SOURCE_DIRECTION": "進階：來源方向點",
            "SOURCE_PLANE": "進階：來源平面點",
            "TARGET_ANCHOR": "進階：目標基準點",
            "TARGET_DIRECTION": "進階：目標方向點",
            "TARGET_PLANE": "進階：目標平面點",
            "ADVANCED_PREVIEW": "進階：預覽確認",
            "FINISH": "完成",
        }
        
        # 模式切換提示
        self._mode_labels = {
            "SIMPLE": "【簡單模式】Tab切換進階",
            "ADVANCED": "【進階模式】Tab切換簡單",
        }

        self._axis_lock_labels = {
            "NONE": "無鎖定",
            "X": "鎖定 X",
            "Y": "鎖定 Y",
            "Z": "鎖定 Z",
            "XY": "鎖定 XY",
            "XZ": "鎖定 XZ",
            "YZ": "鎖定 YZ",
        }

        return True

    def _get_required_roles(self):
        """獲取當前模式需要的角色點位
        
        雙層模式邏輯：
        - Simple Mode: 只需要 SOURCE_ANCHOR, TARGET_ANCHOR
        - Advanced Mode: 根據 workflow_mode 決定完整角色
        """
        # 簡單模式：最小必要點位
        if self.mode_level == UltimateModeLevel.SIMPLE:
            return ["SOURCE_ANCHOR", "TARGET_ANCHOR"]
        
        # 進階模式：完整角色集合
        if self.workflow_mode == UltimateWorkflowMode.TWO_POINT:
            return ["SOURCE_ANCHOR", "SOURCE_DIRECTION", "TARGET_ANCHOR", "TARGET_DIRECTION"]
        elif self.workflow_mode == UltimateWorkflowMode.THREE_POINT:
            return ["SOURCE_ANCHOR", "SOURCE_DIRECTION", "SOURCE_PLANE", "TARGET_ANCHOR", "TARGET_DIRECTION", "TARGET_PLANE"]
        elif self.workflow_mode in [UltimateWorkflowMode.SURFACE_NORMAL, UltimateWorkflowMode.CONTACT, UltimateWorkflowMode.AUTO]:
            return ["SOURCE_ANCHOR", "TARGET_ANCHOR"]
        return []

    def _advance_stage(self):
        """推進工作流階段 - 雙層模式支援"""
        # 簡單模式流程：SIMPLE_SOURCE → SIMPLE_TARGET → SIMPLE_PREVIEW
        if self.mode_level == UltimateModeLevel.SIMPLE:
            if self.workflow_stage == UltimateWorkflowStage.SIMPLE_SOURCE:
                if "SOURCE_ANCHOR" in self.points_by_role:
                    self.workflow_stage = UltimateWorkflowStage.SIMPLE_TARGET
            elif self.workflow_stage == UltimateWorkflowStage.SIMPLE_TARGET:
                if "TARGET_ANCHOR" in self.points_by_role:
                    self.workflow_stage = UltimateWorkflowStage.SIMPLE_PREVIEW
            return
        
        # 進階模式流程：依 roles 順序推進
        roles = self._get_required_roles()
        for role_name in roles:
            if role_name not in self.points_by_role:
                stage_name = role_name  # 直接對應 stage enum
                self.workflow_stage = UltimateWorkflowStage[stage_name]
                return
        self.workflow_stage = UltimateWorkflowStage.ADVANCED_PREVIEW

    def _can_preview(self):
        """檢查是否可以預覽"""
        # 簡單模式：有 source 和 target 即可預覽
        if self.mode_level == UltimateModeLevel.SIMPLE:
            return "SOURCE_ANCHOR" in self.points_by_role and "TARGET_ANCHOR" in self.points_by_role
        
        # 進階模式：需要所有 roles
        roles = self._get_required_roles()
        return all(role in self.points_by_role for role in roles)
        
    def _toggle_mode_level(self):
        """切換簡單/進階模式 - 雙層架構核心"""
        if self.mode_level == UltimateModeLevel.SIMPLE:
            # 切換到進階模式
            self.mode_level = UltimateModeLevel.ADVANCED
            # 保留已選點位，但切換到進階流程
            if "SOURCE_ANCHOR" in self.points_by_role:
                self.workflow_stage = UltimateWorkflowStage.SOURCE_DIRECTION
            else:
                self.workflow_stage = UltimateWorkflowStage.SOURCE_ANCHOR
        else:
            # 切換到簡單模式
            self.mode_level = UltimateModeLevel.SIMPLE
            # 簡化為基本流程
            if "SOURCE_ANCHOR" in self.points_by_role and "TARGET_ANCHOR" in self.points_by_role:
                self.workflow_stage = UltimateWorkflowStage.SIMPLE_PREVIEW
            elif "SOURCE_ANCHOR" in self.points_by_role:
                self.workflow_stage = UltimateWorkflowStage.SIMPLE_TARGET
            else:
                self.workflow_stage = UltimateWorkflowStage.SIMPLE_SOURCE

    def _handle_mouse_move(self, context, event):
        """
        v7.5 處理滑鼠移動：節流優化 + 柔和吸附 + 預測 + HUD 更新
        
        關鍵升級：
        1. 12ms 節流機制 - 避免過度計算
        2. 候選點未變時不重算 solver
        3. Preview matrix 真正改變時才重繪
        """
        import time
        
        # 節流檢查：距離上次更新不足 12ms 則跳過
        current_time = time.time()
        if not hasattr(self, '_last_mousemove_time'):
            self._last_mousemove_time = 0
            self._last_hover_target = None
            self._last_preview_matrix = None
            
        elapsed = (current_time - self._last_mousemove_time) * 1000  # ms
        if elapsed < 12:  # 12ms 節流
            return
            
        self._last_mousemove_time = current_time
        
        mouse_pos = Vector((event.mouse_region_x, event.mouse_region_y))
        self.mouse_vel = mouse_pos - self.mouse_prev_pos
        self.mouse_prev_pos = mouse_pos

        # 更新吸附候選點
        self.snap_engine.update_candidates(context)
        new_snap = self.snap_engine.find_best_snap(context, mouse_pos)
        
        # 檢查 hover target 是否改變
        hover_changed = self._check_hover_changed(self.active_snap, new_snap)
        self.active_snap = new_snap

        self.soft_snap.update_position((mouse_pos.x, mouse_pos.y))

        if self.active_snap and hasattr(self.active_snap, 'screen_dist'):
            if self.soft_snap.should_release((mouse_pos.x, mouse_pos.y), 
                                              self.active_snap.screen_dist,
                                              self.active_snap.snap_type):
                self.active_snap = None
                hover_changed = True

        # 只有需要時才更新預覽
        if self._can_preview():
            if hover_changed or not self._last_preview_matrix:
                self._update_realtime_preview(context)
                # 檢查 preview matrix 是否真正改變
                if self._check_preview_changed():
                    context.area.tag_redraw()
        else:
            # hover preview 模式
            if hover_changed:
                self._update_hover_preview(context, mouse_pos)
                if self._check_preview_changed():
                    context.area.tag_redraw()
                    
    def _check_hover_changed(self, old_snap, new_snap) -> bool:
        """檢查 hover target 是否改變"""
        if old_snap is None and new_snap is None:
            return False
        if old_snap is None or new_snap is None:
            return True
        return (
            old_snap.source_obj != new_snap.source_obj or
            old_snap.snap_type != new_snap.snap_type or
            old_snap.element_index != new_snap.element_index
        )
        
    def _check_preview_changed(self) -> bool:
        """檢查 preview matrix 是否真正改變"""
        if not self.active_obj:
            return False
        current_matrix = self.active_obj.matrix_world.copy()
        if self._last_preview_matrix is None:
            self._last_preview_matrix = current_matrix
            return True
        # 檢查位移是否有顯著變化 (> 0.001)
        delta = (current_matrix.translation - self._last_preview_matrix.translation).length
        if delta > 0.001:
            self._last_preview_matrix = current_matrix
            return True
        return False

    def _update_hover_preview(self, context, mouse_pos):
        """
        v7.5 封頂版：滑鼠懸浮即時預覽
        規則：
        1. 所有 hover 預覽都以 original_matrix 為唯一基準
        2. 不使用 active_obj 當前 location 當基準
        3. 避免預覽過程中的微小漂移與基準污染
        """
        if not self.active_obj or not self.original_matrix:
            return

        if not self.active_snap or not hasattr(self.active_snap, 'position_3d'):
            self.active_obj.matrix_world = self.original_matrix.copy()
            return

        target_pos = self.active_snap.position_3d
        original_translation = self.original_matrix.translation.copy()

        if self.workflow_stage in [
            UltimateWorkflowStage.SOURCE_ANCHOR,
            UltimateWorkflowStage.SOURCE_DIRECTION,
            UltimateWorkflowStage.SOURCE_PLANE,
        ]:
            offset = target_pos - original_translation
            preview_matrix = self.original_matrix.copy()
            preview_matrix.translation = original_translation + offset
            self.active_obj.matrix_world = preview_matrix
        else:
            self._update_realtime_preview(context)

    def _handle_left_click(self, context, event):
        """處理點擊：選點、狀態轉換"""
        if not self.active_snap:
            self._report_status(context, "目前沒有可用吸附點")
            return {"RUNNING_MODAL"}

        role_name = self.workflow_stage.name

        self.points_by_role[role_name] = {
            "position": self.active_snap.position_3d.copy(),
            "object": self.active_snap.source_obj,
            "normal": getattr(self.active_snap, 'normal', Vector((0, 0, 1))),
            "type": self.active_snap.snap_type,
        }

        self.soft_snap.attach(self.active_snap, (event.mouse_region_x, event.mouse_region_y))
        self._play_sound("snap_confirm")
        self._advance_stage()

        if self.workflow_stage == UltimateWorkflowStage.PREVIEW:
            self._update_realtime_preview(context)

        if self.workflow_stage == UltimateWorkflowStage.PREVIEW:
            return self._execute_alignment(context)

        return {"RUNNING_MODAL"}

    def _handle_right_click(self, context, event):
        """右鍵撤回上一個角色點"""
        roles = self._get_required_roles()
        for role_name in reversed(roles):
            if role_name in self.points_by_role:
                self.points_by_role.pop(role_name)
                self.workflow_stage = UltimateWorkflowStage[role_name]
                if self.active_obj and self.original_matrix:
                    self.active_obj.matrix_world = self.original_matrix.copy()
                self._report_status(context, "已撤回上一個參考點")
                self.soft_snap.release()
                return {"RUNNING_MODAL"}

        self._report_status(context, "目前沒有可撤回的參考點")
        return {"RUNNING_MODAL"}

    def _cycle_workflow_mode(self):
        """循環切換工作流模式"""
        ordered = [
            UltimateWorkflowMode.TWO_POINT,
            UltimateWorkflowMode.THREE_POINT,
            UltimateWorkflowMode.SURFACE_NORMAL,
            UltimateWorkflowMode.CONTACT,
            UltimateWorkflowMode.AUTO,
        ]
        idx = ordered.index(self.workflow_mode) if self.workflow_mode in ordered else 0
        self.workflow_mode = ordered[(idx + 1) % len(ordered)]

        self.points_by_role.clear()
        first_role = self._get_required_roles()[0] if self._get_required_roles() else "SOURCE_ANCHOR"
        self.workflow_stage = UltimateWorkflowStage[first_role]
        if self.active_obj and self.original_matrix:
            self.active_obj.matrix_world = self.original_matrix.copy()

        from ..core.zero_mode_controller import AlignmentMode
        if self.workflow_mode == UltimateWorkflowMode.AUTO:
            mode_map = {
                UltimateWorkflowMode.TWO_POINT: AlignmentMode.TWO_POINT,
                UltimateWorkflowMode.THREE_POINT: AlignmentMode.THREE_POINT,
                UltimateWorkflowMode.SURFACE_NORMAL: AlignmentMode.SURFACE_NORMAL,
                UltimateWorkflowMode.CONTACT: AlignmentMode.CONTACT_ALIGN,
            }
            self.zero_mode.current_mode = mode_map.get(self.workflow_mode, AlignmentMode.AUTO_ALIGN)

    def _handle_hotkey(self, context, hotkey: str):
        """處理快捷鍵：模式切換、軸鎖定"""
        from ..core.axis_locking_system import AxisLockType

        if hotkey == "X":
            self.axis_lock.set_axis_lock(AxisLockType.X)
            self._report_status(context, self._axis_lock_labels.get("X", "鎖定 X"))
            return {"RUNNING_MODAL"}
        elif hotkey == "Y":
            self.axis_lock.set_axis_lock(AxisLockType.Y)
            self._report_status(context, self._axis_lock_labels.get("Y", "鎖定 Y"))
            return {"RUNNING_MODAL"}
        elif hotkey == "Z":
            self.axis_lock.set_axis_lock(AxisLockType.Z)
            self._report_status(context, self._axis_lock_labels.get("Z", "鎖定 Z"))
            return {"RUNNING_MODAL"}
        elif hotkey == "SHIFT_X":
            self.axis_lock.set_axis_lock(AxisLockType.XY)
            self._report_status(context, self._axis_lock_labels.get("XY", "鎖定 XY"))
            return {"RUNNING_MODAL"}
        elif hotkey == "SHIFT_Y":
            self.axis_lock.set_axis_lock(AxisLockType.XZ)
            self._report_status(context, self._axis_lock_labels.get("XZ", "鎖定 XZ"))
            return {"RUNNING_MODAL"}
        elif hotkey == "SHIFT_Z":
            self.axis_lock.set_axis_lock(AxisLockType.YZ)
            self._report_status(context, self._axis_lock_labels.get("YZ", "鎖定 YZ"))
            return {"RUNNING_MODAL"}
        elif hotkey == "ESC":
            self.axis_lock.clear_lock()
            self._report_status(context, "軸鎖定已清除")
            return {"RUNNING_MODAL"}
        elif hotkey == "TAB":
            # v7.5: Tab 切換簡單/進階模式 (雙層架構核心)
            self._toggle_mode_level()
            mode_label = self._mode_labels.get(self.mode_level.name, self.mode_level.name)
            self._report_status(context, f"已切換至 {mode_label}")
            return {"RUNNING_MODAL"}
        elif hotkey == "SHIFT_TAB":
            # Shift+Tab 切換 workflow mode (僅在進階模式有意義)
            if self.mode_level == UltimateModeLevel.ADVANCED:
                self._cycle_workflow_mode()
                self._report_status(context, f"進階模式切換為: {self.workflow_mode.name}")
            else:
                self._report_status(context, "請先切換至進階模式 (Tab) 再切換對齊類型")
            return {"RUNNING_MODAL"}
        elif hotkey == "SPACE":
            # v7.5: 支援雙層模式的預覽確認
            if self.workflow_stage in [UltimateWorkflowStage.SIMPLE_PREVIEW, UltimateWorkflowStage.ADVANCED_PREVIEW]:
                return self._execute_alignment(context)
            return {"RUNNING_MODAL"}

        return super()._handle_hotkey(context, hotkey)

    def _apply_axis_lock(self, transform_matrix: Matrix) -> Matrix:
        """應用軸鎖定到變換矩陣"""
        if not self.axis_lock.current_lock.is_active:
            return transform_matrix
        return self.axis_lock.apply_axis_lock_to_transform(transform_matrix)

    def _update_realtime_preview(self, context):
        """更新即時預覽變換"""
        if not self.active_obj or not self.original_matrix:
            return

        if self.workflow_mode == UltimateWorkflowMode.TWO_POINT:
            self._preview_two_point(context)
        elif self.workflow_mode == UltimateWorkflowMode.THREE_POINT:
            self._preview_three_point(context)
        elif self.workflow_mode == UltimateWorkflowMode.SURFACE_NORMAL:
            self._preview_surface_normal(context)
        elif self.workflow_mode == UltimateWorkflowMode.CONTACT:
            self._preview_contact(context)
        elif self.workflow_mode == UltimateWorkflowMode.AUTO:
            self._preview_auto(context)

    def _preview_two_point(self, context):
        """兩點對齊預覽"""
        if len(self.points_by_role) < 4:
            return

        source_a = self.points_by_role["SOURCE_ANCHOR"]["position"]
        source_b = self.points_by_role["SOURCE_DIRECTION"]["position"]
        target_a = self.points_by_role["TARGET_ANCHOR"]["position"]
        target_b = self.points_by_role["TARGET_DIRECTION"]["position"]

        result_mat = self.solver_stack.solve_two_point(source_a, source_b, target_a, target_b)
        result_mat = self._apply_axis_lock(result_mat)
        self.active_obj.matrix_world = result_mat @ self.original_matrix

    def _preview_three_point(self, context):
        """三點對齊預覽"""
        if len(self.points_by_role) < 6:
            return

        source_a = self.points_by_role["SOURCE_ANCHOR"]["position"]
        source_b = self.points_by_role["SOURCE_DIRECTION"]["position"]
        source_c = self.points_by_role["SOURCE_PLANE"]["position"]
        target_a = self.points_by_role["TARGET_ANCHOR"]["position"]
        target_b = self.points_by_role["TARGET_DIRECTION"]["position"]
        target_c = self.points_by_role["TARGET_PLANE"]["position"]

        result_mat = self.solver_stack.solve_three_point(
            source_a, source_b, source_c,
            target_a, target_b, target_c
        )
        result_mat = self._apply_axis_lock(result_mat)
        self.active_obj.matrix_world = result_mat @ self.original_matrix

    def _preview_surface_normal(self, context):
        """表面法線對齊預覽"""
        if len(self.points_by_role) < 2:
            return

        from ..core.alignment import surface_normal_align_with_raycast
        source = self.active_obj
        target = self.points_by_role["TARGET_ANCHOR"].get("object")

        if target:
            settings = context.scene.smartalignpro_settings
            surface_normal_align_with_raycast(source, target, settings)

    def _preview_contact(self, context):
        """接觸對齊預覽 - 預覽階段絕不污染 source 位置"""
        if len(self.points_by_role) < 2:
            return

        source = self.active_obj
        target = self.points_by_role["TARGET_ANCHOR"].get("object")

        if not source or not target or not self.original_matrix:
            return

        contact_result = self.contact_engine.solve_contact_alignment(
            source,
            target,
            apply_offset=False
        )
        if not contact_result:
            return

        preview_matrix = self.original_matrix.copy()
        preview_matrix.translation = (
            self.original_matrix.translation + contact_result.offset_vector
        )

        self.active_obj.matrix_world = preview_matrix

    def _preview_auto(self, context):
        """自動模式預覽"""
        if len(self.points_by_role) < 2:
            return

        from ..core.zero_mode_controller import AlignmentMode
        mode = self.zero_mode.current_mode

        if mode == AlignmentMode.TWO_POINT:
            self._preview_two_point(context)
        elif mode == AlignmentMode.THREE_POINT:
            self._preview_three_point(context)
        elif mode == AlignmentMode.FACE_ALIGN:
            self._preview_contact(context)
        elif mode == AlignmentMode.SURFACE_NORMAL:
            self._preview_surface_normal(context)

    def _execute_alignment(self, context):
        """執行最終對齊並結束 - v7.4 整合 Workflow Router"""
        # v7.4: 使用 Workflow Router 決策執行
        if self.active_solver.value != "NONE":
            self._execute_solver(context)
        else:
            self._update_realtime_preview(context)
            
        self._report_status(context, f"Ultimate Align 完成 [{self.active_solver.name}]")
        self.soft_snap.release()
        
        # 重置 sticky manager
        if hasattr(self, 'sticky_manager'):
            self.sticky_manager.reset()
            
        return self._finish_modal(context, "FINISHED")

    def _execute_solver(self, context):
        """v7.4: 根據 Workflow Router 決策執行對應 solver"""
        from ..core.workflow_router import SolverExecutor, SolverType
        
        success = SolverExecutor.execute(
            self.active_solver,
            context,
            self.hover_data,
            self.workflow_context
        )
        
        if not success:
            # Fallback 到標準預覽
            self._update_realtime_preview(context)
            
    def _update_solver_decision(self, context, mouse_pos: Vector):
        """v7.4: 更新 solver 決策 - Workflow Router 核心整合"""
        # 更新 hover 數據
        if self.active_snap:
            self.hover_data.target_object = getattr(self.active_snap, 'source_obj', None)
            self.hover_data.target_vertex = self.active_snap if getattr(self.active_snap, 'snap_type', '') == 'VERTEX' else None
            self.hover_data.target_edge = self.active_snap if getattr(self.active_snap, 'snap_type', '') in ['EDGE_MID', 'EDGE'] else None
            self.hover_data.target_face = self.active_snap if getattr(self.active_snap, 'snap_type', '') == 'FACE_CENTER' else None
            self.hover_data.has_contact_candidate = True
        else:
            self.hover_data.has_contact_candidate = False
            
        # 更新 workflow context
        self.workflow_context = self.workflow_router.WorkflowContext(context)
        
        # 決策 solver
        self.active_solver = self.workflow_router.decide_solver(
            context,
            self.hover_data,
            self.workflow_context
        )
        
        # 應用 sticky intent
        if hasattr(self, 'sticky_manager') and self.active_snap:
            from ..core.sticky_intent import StickyCandidate
            sticky_candidate = StickyCandidate(
                position=getattr(self.active_snap, 'position_3d', Vector((0, 0, 0))),
                snap_type=getattr(self.active_snap, 'snap_type', 'UNKNOWN'),
                source_obj=getattr(self.active_snap, 'source_obj', None),
                element_index=getattr(self.active_snap, 'element_index', -1),
                normal=getattr(self.active_snap, 'normal', Vector((0, 0, 1)))
            )
            self.sticky_manager.process_candidate(
                {'position': sticky_candidate.position, 'snap_type': sticky_candidate.snap_type},
                mouse_pos,
                context
            )

    def draw_2d_hud(self, context):
        """繪製 HUD"""
        if self.active_snap:
            self._draw_snap_marker(self.active_snap)
        self._draw_status_text(context)
        self._draw_axis_lock_indicator(context)

    def _draw_snap_marker(self, snap):
        """繪製吸附標記"""
        if hasattr(snap, 'screen_pos') and snap.screen_pos:
            pos = snap.screen_pos
            blf.position(0, pos.x + 10, pos.y + 10, 0)
            blf.size(0, 15, 72)
            blf.draw(0, f"SNAP: {snap.snap_type}")

    def _draw_status_text(self, context):
        """繪製狀態 HUD - v7.4 顯示 Workflow Router 決策"""
        stage_label = self._stage_labels.get(self.workflow_stage.name, self.workflow_stage.name)
        lock_info = self._axis_lock_labels.get(
            self.axis_lock.current_lock.lock_type.value, "無鎖定"
        )
        
        # v7.4: 顯示當前 solver 決策
        solver_label = ""
        if hasattr(self, 'active_solver') and self.active_solver.value != "NONE":
            from ..core.workflow_router import WorkflowRouter
            solver_desc = WorkflowRouter.get_solver_description(self.active_solver)
            solver_label = f" | {solver_desc}"

        blf.position(0, 20, 60, 0)
        blf.size(0, 18, 72)
        blf.draw(0, f"ULTIMATE | {self.workflow_mode.name} | {stage_label}{solver_label}")

        blf.position(0, 20, 40, 0)
        blf.size(0, 14, 72)
        blf.draw(0, f"AXIS: {lock_info} | Tab:切換模式 X/Y/Z:軸鎖定")

    def _draw_axis_lock_indicator(self, context):
        """繪製軸鎖定指示器"""
        if self.axis_lock.current_lock.is_active:
            lock_type = self.axis_lock.current_lock.lock_type
            color = self.axis_lock.axis_colors.get(lock_type, (1, 1, 1, 1))
