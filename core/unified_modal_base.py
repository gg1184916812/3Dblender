"""
Smart Align Pro - 統一對齊基類
所有對齊功能的統一框架

v7.4 升級：整合 InteractionPipeline - 所有 operator 使用 pipeline
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatVectorProperty, CollectionProperty, FloatProperty, IntProperty
from mathutils import Vector, Matrix
from typing import Optional, List, Dict, Any
import time

from ..core.modal_kernel import ModalState, AlignmentMode, ConstraintMode, CoordinateSpace, InteractionPipeline
from ..core.snap_engine import snap_engine
from ..core.preview_transform import preview
from ..ui.overlays import overlay
from ..ui.hud import hud_manager


class SmartAlignModalBase(Operator):
    """統一對齊 Modal 基類 - v7.4: 使用 InteractionPipeline"""
    
    # 統一狀態機
    modal_state: EnumProperty(
        name="Modal 狀態",
        items=[
            ("IDLE", "待機", "等待操作"),
            ("SELECT_SOURCE", "選擇來源", "選擇來源參考點"),
            ("SELECT_TARGET", "選擇目標", "選擇目標參考點"),
            ("PREVIEW", "預覽", "預覽對齊結果"),
            ("EXECUTE", "執行", "執行對齊"),
            ("CANCEL", "取消", "取消操作"),
        ],
        default="SELECT_SOURCE",
    )
    
    # 對齊模式 - 子類別必須覆蓋
    alignment_mode: EnumProperty(
        name="對齊模式",
        description="對齊模式",
        items=[
            ("TWO_POINT", "兩點對齊", "兩點對齊"),
            ("THREE_POINT", "三點對齊", "三點對齊"),
            ("SURFACE_NORMAL", "表面法線", "表面法線對齊"),
            ("EDGE_ALIGN", "邊對齊", "邊對邊對齊"),
            ("FACE_ALIGN", "面對齊", "面對面對齊"),
        ],
        default="TWO_POINT",
    )
    
    # 約束模式
    constraint_mode: EnumProperty(
        name="約束模式",
        description="約束模式",
        items=[
            ("NONE", "無約束", "自由對齊"),
            ("TRANSLATE_ONLY", "僅平移", "只進行平移"),
            ("ROTATE_ONLY", "僅旋轉", "只進行旋轉"),
            ("AXIS_LOCK_X", "鎖定 X 軸", "鎖定 X 軸"),
            ("AXIS_LOCK_Y", "鎖定 Y 軸", "鎖定 Y 軸"),
            ("AXIS_LOCK_Z", "鎖定 Z 軸", "鎖定 Z 軸"),
        ],
        default="NONE",
    )
    
    # 通用屬性
    show_preview: BoolProperty(default=True)
    preview_active: BoolProperty(default=False)
    snap_tolerance: FloatProperty(default=20.0, min=5.0, max=50.0)
    
    # 內部狀態
    def __init__(self):
        super().__init__()
        self.source_points = []
        self.target_points = []
        self.current_hover_candidate = None
        self.start_time = time.time()
        
        # v7.4: 初始化 InteractionPipeline
        self.pipeline = None
        self._preview_original_matrix = None
        self._last_mouse_pos = None
        
    def _get_alignment_mode(self) -> AlignmentMode:
        """子類別必須實現"""
        return AlignmentMode.TWO_POINT
        
    def _get_required_points(self) -> Dict[str, int]:
        """子類別必須實現 - 返回 {'source': int, 'target': int}"""
        return {"source": 2, "target": 2}
        
    def _solve_alignment(self, source_points: List[Vector], target_points: List[Vector]) -> Dict[str, Any]:
        """v7.4: 可選實現 - Pipeline 現在負責 solver 選擇
        
        保留此方法供 legacy 相容，但新 operator 應依賴 pipeline
        """
        return {"success": False, "error": "Not implemented - use pipeline"}
        
    def _can_execute(self) -> bool:
        """檢查是否可以執行對齊 - v7.4: 也檢查 pipeline 狀態"""
        required = self._get_required_points()
        points_ready = len(self.source_points) >= required["source"] and len(self.target_points) >= required["target"]
        
        # v7.4: 如果 pipeline 存在，也檢查其狀態
        if self.pipeline:
            status = self.pipeline.get_pipeline_status()
            return points_ready or status.get("has_preview", False)
        
        return points_ready
        
    def _get_status_text(self) -> str:
        """獲取狀態文字 - v7.4: 顯示 pipeline 資訊"""
        # v7.4: 優先顯示 pipeline 狀態
        if self.pipeline:
            status = self.pipeline.get_pipeline_status()
            if status.get("has_preview"):
                intent_type = status.get("intent_type", "UNKNOWN")
                confidence = status.get("intent_confidence", 0.0)
                return f"預覽就緒 [{intent_type}] (信心: {confidence:.1%})"
        
        required = self._get_required_points()
        
        if self.modal_state == "SELECT_SOURCE":
            return f"選擇來源點 ({len(self.source_points)}/{required['source']})"
        elif self.modal_state == "SELECT_TARGET":
            return f"選擇目標點 ({len(self.target_points)}/{required['target']})"
        elif self.modal_state == "PREVIEW":
            return "預覽模式 - Enter 執行，ESC 取消"
        else:
            return "準備中..."
            
    def invoke(self, context, event):
        """啟動 Modal - v7.4: 初始化 InteractionPipeline"""
        # 使用子類別的 _get_alignment_mode() 而不是 alignment_mode 屬性
        alignment_mode = self._get_alignment_mode()
        
        # v7.4: 初始化 InteractionPipeline
        self.pipeline = InteractionPipeline(context)
        
        # 初始化視覺系統
        from ..core.preview_transform import preview
        preview.activate(context.active_object, context.selected_objects)
        
        from ..ui.overlays import overlay
        overlay.register()
        
        from ..ui.hud_enhanced import hud
        hud.start(alignment_mode.value)
        
        # 重置狀態
        self.modal_state = "SELECT_SOURCE"
        self.source_points = []
        self.target_points = []
        
        # 添加 modal 處理器
        context.window_manager.modal_handler_add(self)
        
        # 更新 HUD
        from ..ui.hud_enhanced import update
        required = self._get_required_points()
        update(
            modal_state=self.modal_state,
            source_points=self.source_points,
            target_points=self.target_points,
            required_points=required
        )
        
        self.report({"INFO"}, f"{self._get_status_text()}")
        return {"RUNNING_MODAL"}
        
    def modal(self, context, event):
        """統一 Modal 處理 - v7.4: 使用 InteractionPipeline"""
        context.area.tag_redraw()
        
        # ESC 取消
        if event.type == "ESC":
            # v7.4: 清理 pipeline
            if self.pipeline:
                self.pipeline.reset()
            return self._cancel_operation(context)
            
        # Enter 執行
        if event.type == "RET" and event.value == "PRESS":
            if self._can_execute():
                return self._execute_alignment(context)
            else:
                self.report({"WARNING"}, "點位不足，無法執行對齊")
                
        # Tab 切換約束
        if event.type == "TAB" and event.value == "PRESS":
            self._cycle_constraint()
            
        # 滑鼠移動 - 處理吸附和預覽
        if event.type == "MOUSEMOVE":
            return self._handle_mouse_move(context, event)
            
        # 左鍵確認點位
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            return self._handle_click(context, event)
            
        return {"RUNNING_MODAL"}
        
    def _handle_mouse_move(self, context, event):
        """處理滑鼠移動 - v7.4: 優先走統一 stable candidate 路線"""
        current_mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        self.mouse_delta = current_mouse - self._last_mouse_pos if self._last_mouse_pos is not None else Vector((0, 0))
        self._last_mouse_pos = current_mouse.copy()

        candidate = self._resolve_stable_hover_candidate(context, event)
        if candidate is None:
            candidate = snap_engine.find_best_candidate(context, event.mouse_region_x, event.mouse_region_y)

        # 更新 overlay
        overlay.update_hover_candidate(candidate)
        self.current_hover_candidate = candidate
        
        # v7.4: 使用 pipeline 處理完整流程
        if self.pipeline and candidate:
            # 將候選點轉換為 pipeline 格式
            hover_data = {
                "position": candidate.location if hasattr(candidate, 'location') else Vector((0, 0, 0)),
                "snap_type": candidate.snap_type if hasattr(candidate, 'snap_type') else "UNKNOWN",
                "source_obj": candidate.source_obj if hasattr(candidate, 'source_obj') else None,
                "element_index": candidate.element_index if hasattr(candidate, 'element_index') else -1,
                "normal": candidate.normal if hasattr(candidate, 'normal') else Vector((0, 0, 1)),
                "screen_pos": Vector((event.mouse_region_x, event.mouse_region_y)),
            }
            
            # 執行完整管線
            success = self.pipeline.process_full_pipeline(hover_data)
            
            # 如果管線成功，更新預覽
            if success and self.show_preview:
                self._update_preview_from_pipeline(context)
        else:
            # Legacy: 使用舊的預覽更新
            if self._can_preview():
                self._update_preview(context)
            
        # 更新 HUD
        from ..ui.hud_enhanced import update
        snap_info = ""
        if candidate:
            snap_info = f"{candidate.snap_type} ({candidate.screen_distance:.1f}px)"
        
        # v7.4: 添加 pipeline 狀態到 HUD
        pipeline_info = ""
        if self.pipeline:
            status = self.pipeline.get_pipeline_status()
            if status.get("has_solver"):
                pipeline_info = f" | Solver: {status.get('intent_type', 'N/A')}"
            
        required = self._get_required_points()
        update(
            snap_info=snap_info + pipeline_info,
            constraint_info=self.constraint_mode,
            required_points=required
        )
        
    def _handle_click(self, context, event):
        """處理點擊確認 - v7.4: 使用穩定的 hover candidate"""
        # v7.4: 優先使用已儲存的 hover candidate，避免重新抓取導致不一致
        candidate = None
        
        # 首先嘗試使用 current_hover_candidate（由 _handle_mouse_move 更新）
        if self.current_hover_candidate is not None:
            candidate = self.current_hover_candidate
        else:
            # Fallback: 只有當沒有 hover candidate 時才重新抓取
            candidate = snap_engine.find_best_candidate(context, event.mouse_region_x, event.mouse_region_y)
        
        if not candidate:
            return {"RUNNING_MODAL"}
            
        if self.modal_state == "SELECT_SOURCE":
            self.source_points.append(candidate.location)
            overlay.update_source_points(self.source_points)
            
            # 檢查是否完成來源選擇
            required = self._get_required_points()
            if len(self.source_points) >= required["source"]:
                self.modal_state = "SELECT_TARGET"
                
            # 更新 HUD
            from ..ui.hud_enhanced import update
            required = self._get_required_points()
            update(
                modal_state=self.modal_state,
                source_points=self.source_points,
                required_points=required
            )
            
        elif self.modal_state == "SELECT_TARGET":
            self.target_points.append(candidate.location)
            overlay.update_target_points(self.target_points)
            
            # 檢查是否完成目標選擇
            required = self._get_required_points()
            if len(self.target_points) >= required["target"]:
                self.modal_state = "PREVIEW"
                
            # 更新 HUD
            from ..ui.hud_enhanced import update
            required = self._get_required_points()
            update(
                modal_state=self.modal_state,
                target_points=self.target_points,
                required_points=required
            )
            
        self.report({"INFO"}, f"{self._get_status_text()}")
        return {"RUNNING_MODAL"}
        
    # ============================================================================
    # v7.4 新增：Helper 方法 - 統一 hover/click 決策
    # ============================================================================
    
    def _build_hover_context(self, context, event) -> Dict[str, Any]:
        """建立 hover 上下文資訊"""
        return {
            "mouse_x": event.mouse_region_x,
            "mouse_y": event.mouse_region_y,
            "context": context,
            "constraint_mode": self.constraint_mode,
            "interaction_mode": self.alignment_mode,
        }
        
    def _resolve_stable_hover_candidate(self, context, event):
        """
        解析穩定的 hover candidate
        
        v7.4: 整合 scoring + sticky + decision 的統一候選解析
        """
        # 獲取原始 candidates
        if hasattr(snap_engine, "get_candidates"):
            candidates = snap_engine.get_candidates(context, event.mouse_region_x, event.mouse_region_y)
        elif hasattr(snap_engine, "raycast_and_get_candidates"):
            candidates = snap_engine.raycast_and_get_candidates(context, event.mouse_region_x, event.mouse_region_y)
        else:
            candidates = []
        
        if not candidates:
            return None
            
        # 建立 scoring context
        from ..core.snap_scoring_engine import SnapScoringContext, SnapCandidate as ScoringCandidate
        from ..core.sticky_intent import compute_intent_bias
        
        current_target_scoring = None
        if self.current_hover_candidate is not None:
            current_target_scoring = ScoringCandidate(
                world_pos=getattr(self.current_hover_candidate, 'location', Vector((0, 0, 0))),
                normal=getattr(self.current_hover_candidate, 'normal', Vector((0, 0, 1))),
                feature_type=getattr(self.current_hover_candidate, 'snap_type', 'UNKNOWN'),
                distance_3d=0.0,
                screen_distance=getattr(self.current_hover_candidate, 'screen_distance', float('inf')),
                source_object=getattr(self.current_hover_candidate, 'object', None),
                target_object=getattr(self.current_hover_candidate, 'object', None),
            )

        scoring_context = SnapScoringContext(
            mouse_velocity=getattr(self, 'mouse_delta', None),
            axis_lock=self.constraint_mode if self.constraint_mode != "NONE" else None,
            mode=self.alignment_mode,
            intent_bias=compute_intent_bias(),
            current_target=current_target_scoring,
            interaction_mode=self.alignment_mode,
        )
        
        # 將 snap_engine 候選轉換為 scoring engine 候選
        from ..core.snap_scoring_engine import SnapScoringEngine, SnapCandidate as ScoringCandidate
        scoring_candidates = []
        for cand in candidates:
            scoring_candidates.append(ScoringCandidate(
                world_pos=getattr(cand, 'location', Vector((0, 0, 0))),
                normal=getattr(cand, 'normal', Vector((0, 0, 1))),
                feature_type=getattr(cand, 'snap_type', 'UNKNOWN'),
                distance_3d=0.0,
                screen_distance=getattr(cand, 'screen_distance', float('inf')),
                source_object=getattr(cand, 'object', None),
                target_object=getattr(cand, 'object', None),
            ))
        best_candidate = SnapScoringEngine.select_best_candidate(scoring_candidates, scoring_context)
        if best_candidate is None:
            return None

        # 回映射回原始 snap_engine candidate
        try:
            best_index = scoring_candidates.index(best_candidate)
            best_candidate = candidates[best_index]
        except ValueError:
            pass
        
        return best_candidate
        
    def _get_current_axis_lock_state(self):
        """獲取當前軸鎖定狀態"""
        if self.constraint_mode.startswith("AXIS_LOCK_"):
            return self.constraint_mode
        return None
        
    def _can_preview(self) -> bool:
        """檢查是否可以預覽"""
        return len(self.source_points) > 0 and len(self.target_points) > 0
        
    def _update_preview(self, context):
        """更新預覽 - Legacy 方法"""
        if not self._can_preview():
            return
            
        # 獲取來源和目標物件
        source_obj = context.active_object
        target_obj = context.selected_objects[-1] if context.selected_objects else source_obj
        
        if source_obj and target_obj:
            # 使用子類別的求解方法
            result = self._solve_alignment(self.source_points, self.target_points)
            if result.get("success"):
                # 使用統一的 preview_transform 系統
                from ..core.preview_transform import update_preview
                update_preview(result)
                    
    def _update_preview_from_pipeline(self, context):
        """v7.4: 使用 InteractionPipeline 的預覽結果更新預覽"""
        if not self.pipeline:
            return
            
        # 從 pipeline 獲取預覽結果
        preview_result = self.pipeline.preview_result
        if preview_result:
            # 如果 preview_result 有 matrix，直接套用到活動物件
            if hasattr(preview_result, 'matrix') and preview_result.matrix:
                active_obj = context.active_object
                if active_obj:
                    if self._preview_original_matrix is None:
                        self._preview_original_matrix = active_obj.matrix_world.copy()
                    # 每幀都從 original baseline 套用，避免疊算
                    active_obj.matrix_world = preview_result.matrix.copy()
            elif hasattr(preview_result, 'apply_to_object'):
                preview_result.apply_to_object(context.active_object)
                
    def _cycle_constraint(self):
        """循環切換約束"""
        constraints = ["NONE", "TRANSLATE_ONLY", "ROTATE_ONLY", "AXIS_LOCK_X", "AXIS_LOCK_Y", "AXIS_LOCK_Z"]
        current_index = constraints.index(self.constraint_mode)
        self.constraint_mode = constraints[(current_index + 1) % len(constraints)]
        
    def _execute_alignment(self, context):
        """執行對齊 - v7.4: 使用 InteractionPipeline commit"""
        try:
            # v7.4: 優先使用 pipeline 的 commit
            if self.pipeline:
                success = self.pipeline.commit()
                if success:
                    # 清理視覺系統
                    from ..ui.overlays import overlay
                    overlay.unregister()
                    
                    from ..ui.hud_enhanced import hud
                    hud.stop()
                    
                    alignment_mode = self._get_alignment_mode()
                    self.report({"INFO"}, "對齊執行完成 (Pipeline)")
                    return {"FINISHED"}
            
            # Legacy: 使用統一的 preview_transform 系統套用
            from ..core.preview_transform import apply_preview
            apply_preview()
            
            # 清理視覺系統
            from ..ui.overlays import overlay
            overlay.unregister()
            
            from ..ui.hud_enhanced import hud
            hud.stop()
            
            alignment_mode = self._get_alignment_mode()
            self.report({"INFO"}, "對齊執行完成")
            return {"FINISHED"}
            
        except Exception as e:
            # v7.4: 清理 pipeline
            if self.pipeline:
                self.pipeline.reset()
                
            from ..core.preview_transform import cancel_preview
            cancel_preview()
            alignment_mode = self._get_alignment_mode()
            self.report({"ERROR"}, f"對齊失敗: {e}")
            return {"CANCELLED"}
            
    def _cancel_operation(self, context):
        """取消操作 - v7.4: 清理 pipeline"""
        # v7.4: 清理 pipeline
        if self.pipeline:
            self.pipeline.reset()
            self.pipeline = None
        self._preview_original_matrix = None
        self._last_mouse_pos = None
            
        from ..core.preview_transform import cancel_preview
        cancel_preview()
        if self._preview_original_matrix is not None and context.active_object:
            context.active_object.matrix_world = self._preview_original_matrix.copy()
        self._preview_original_matrix = None
        
        # 清理視覺系統
        from ..ui.overlays import overlay
        overlay.unregister()
        
        from ..ui.hud_enhanced import hud
        hud.stop()
        
        alignment_mode = self._get_alignment_mode()
        self.report({"INFO"}, "對齊已取消")
        return {"CANCELLED"}
