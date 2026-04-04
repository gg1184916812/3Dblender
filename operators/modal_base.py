"""
Smart Align Pro - 統一 Modal 基類
CAD Transform 級別的統一互動框架基礎
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty
from mathutils import Vector, Matrix
from typing import Optional, Dict, Any
import time

from ..core.modal_kernel import (
    ModalKernel, ModalState, AlignmentMode, CoordinateSpace, ConstraintMode,
    get_modal_kernel, start_alignment_modal, process_modal_hotkey,
    get_modal_status, get_next_point_hint
)
from ..core.hover_preview_system import update_hover_preview, activate_hover_preview, deactivate_hover_preview
from ..core.constraint_plane_system import apply_constraint_to_point, get_constraint_visual_data


class SmartAlignModalBase(Operator):
    """Smart Align Pro 統一 Modal 基類"""
    
    # 基礎屬性
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}
    
    # Modal 配置
    show_hud: BoolProperty(
        name="顯示 HUD",
        description="顯示平視顯示器",
        default=True
    )
    
    show_preview: BoolProperty(
        name="顯示預覽",
        description="顯示即時預覽",
        default=True
    )
    
    enable_sound: BoolProperty(
        name="啟用音效",
        description="啟用操作音效",
        default=False
    )
    
    # 狀態管理
    _modal_kernel: Optional[ModalKernel] = None
    _handlers: list = []
    _start_time: float = 0
    _last_update_time: float = 0
    _mouse_pos: tuple = (0, 0)
    _is_active: bool = False
    
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._modal_kernel = get_modal_kernel()
        self._start_time = time.time()
        self._is_active = False
    
    def invoke(self, context, event):
        """啟動 Modal"""
        # 檢查前置條件
        if not self._check_prerequisites(context):
            self.report({"WARNING"}, "前置條件不滿足")
            return {"CANCELLED"}
        
        # 初始化 Modal
        if not self._initialize_modal(context, event):
            self.report({"ERROR"}, "Modal 初始化失敗")
            return {"CANCELLED"}
        
        # 啟動預覽系統
        if self.show_preview:
            activate_hover_preview(context)
        
        # 添加繪製處理器
        self._setup_draw_handlers(context)
        
        # 設置游標
        context.window.cursor_set('CROSSHAIR')
        
        # 添加 Modal 處理器
        context.window_manager.modal_handler_add(self)
        
        # 標記為活躍
        self._is_active = True
        
        # 報告啟動
        self._report_status(context, "Modal 已啟動")
        
        return {"RUNNING_MODAL"}
    
    def modal(self, context, event):
        """Modal 事件處理主循環"""
        if not self._is_active:
            return {"FINISHED"}
        
        # 更新時間
        current_time = time.time()
        self._last_update_time = current_time
        
        # 更新滑鼠位置
        self._mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        
        # 處理系統事件
        if event.type == "ESC" and event.value == "PRESS":
            return self._handle_cancel(context, event)
        
        # 處理執行事件
        if event.type in {"RET", "SPACE"} and event.value == "PRESS":
            return self._handle_execute(context, event)
        
        # 處理滑鼠移動
        if event.type == "MOUSEMOVE":
            return self._handle_mouse_move(context, event)
        
        # 處理左鍵點擊
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            return self._handle_left_click(context, event)
        
        # 處理右鍵點擊
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            return self._handle_right_click(context, event)
        
        # 處理快捷鍵
        hotkey_action = self._build_hotkey_string(event)
        if hotkey_action:
            result = self._handle_hotkey(context, hotkey_action)
            if result:
                return result
        
        # 更新預覽
        if self.show_preview:
            self._update_preview(context)
        
        # 強制重繪
        context.area.tag_redraw()
        
        return {"RUNNING_MODAL"}
    
    def _check_prerequisites(self, context) -> bool:
        """檢查前置條件"""
        # 基礎檢查
        if not context.active_object:
            return False
        
        if context.active_object.type not in {"MESH", "CURVE", "SURFACE", "FONT"}:
            return False
        
        # 子類可覆蓋此方法進行特定檢查
        return self._check_specific_prerequisites(context)
    
    def _check_specific_prerequisites(self, context) -> bool:
        """檢查特定前置條件 - 子類覆蓋"""
        return True
    
    def _initialize_modal(self, context, event) -> bool:
        """初始化 Modal - 子類覆蓋"""
        # 獲取對齊模式
        mode = self._get_alignment_mode()
        
        # 啟動 Modal 核心
        if not start_alignment_modal(mode, context):
            return False
        
        # 設置初始狀態
        self._modal_kernel.show_hud = self.show_hud
        self._modal_kernel.show_preview = self.show_preview
        
        # 子類初始化
        return self._initialize_specific_modal(context, event)
    
    def _get_alignment_mode(self) -> AlignmentMode:
        """獲取對齊模式 - 子類覆蓋"""
        return AlignmentMode.TWO_POINT
    
    def _initialize_specific_modal(self, context, event) -> bool:
        """初始化特定 Modal - 子類覆蓋"""
        return True
    
    def _setup_draw_handlers(self, context):
        """設置繪製處理器"""
        # 3D 視圖繪製處理器
        handler_3d = context.space_data.draw_handler_add(
            self.draw_3d_overlay, (), 'WINDOW', 'POST_VIEW'
        )
        self._handlers.append(handler_3d)
        
        # 2D 視圖繪製處理器
        handler_2d = context.space_data.draw_handler_add(
            self.draw_2d_hud, (), 'WINDOW', 'POST_PIXEL'
        )
        self._handlers.append(handler_2d)
    
    def _handle_cancel(self, context, event):
        """處理取消事件"""
        self._modal_kernel.state = ModalState.CANCEL
        return self._finish_modal(context, "CANCELLED")
    
    def _handle_execute(self, context, event):
        """處理執行事件"""
        if self._modal_kernel.state == ModalState.EXECUTE:
            return self._execute_alignment(context)
        else:
            self._report_status(context, "還未準備好執行")
            return {"RUNNING_MODAL"}
    
    def _handle_mouse_move(self, context, event):
        """處理滑鼠移動事件"""
        # 尋找吸附點
        snap_point = self._find_snap_point(context, event)
        
        # 更新預覽
        if snap_point and self.show_preview:
            self._update_snap_preview(context, snap_point)
        
        return {"RUNNING_MODAL"}
    
    def _handle_left_click(self, context, event):
        """處理左鍵點擊事件"""
        # 尋找吸附點
        snap_point = self._find_snap_point(context, event)
        
        if snap_point:
            # 添加點位
            from ..core.modal_kernel import ModalPoint
            modal_point = ModalPoint(
                position=snap_point.get("position", Vector((0, 0, 0))),
                point_type=snap_point.get("type", "UNKNOWN"),
                object=snap_point.get("object"),
                element=snap_point.get("element"),
                normal=snap_point.get("normal")
            )
            
            if self._modal_kernel.add_point(modal_point):
                self._play_sound("add_point")
                self._report_status(context, f"已添加點位: {modal_point.point_type}")
            else:
                self._report_status(context, "無法添加更多點位")
        else:
            self._report_status(context, "未找到有效的吸附點")
        
        return {"RUNNING_MODAL"}
    
    def _handle_right_click(self, context, event):
        """處理右鍵點擊事件"""
        # 移除最後一個點位
        if self._modal_kernel.points:
            last_point_type = list(self._modal_kernel.points.keys())[-1]
            self._modal_kernel.remove_point(last_point_type)
            self._play_sound("remove_point")
            self._report_status(context, f"已移除點位: {last_point_type}")
        
        return {"RUNNING_MODAL"}
    
    def _build_hotkey_string(self, event) -> Optional[str]:
        """構建快捷鍵字符串"""
        hotkey_parts = []
        
        # 修飾鍵
        if event.shift:
            hotkey_parts.append("SHIFT")
        if event.ctrl:
            hotkey_parts.append("CTRL")
        if event.alt:
            hotkey_parts.append("ALT")
        if event.oskey:
            hotkey_parts.append("OS")
        
        # 主鍵
        if event.type and event.type.isalpha():
            hotkey_parts.append(event.type.upper())
        elif event.type and event.type.isdigit():
            hotkey_parts.append(event.type)
        elif event.type in {"RET", "ESC", "SPACE", "TAB", "BACK_SPACE", "DEL"}:
            hotkey_parts.append(event.type)
        elif event.type in {"X", "Y", "Z", "G", "L", "A", "S", "F", "E", "C", "T", "R", "H", "P", "K", "N", "M", "V", "U", "I"}:
            hotkey_parts.append(event.type.upper())
        
        if hotkey_parts:
            return "_".join(hotkey_parts)
        
        return None
    
    def _handle_hotkey(self, context, hotkey: str):
        """處理快捷鍵"""
        # 處理快捷鍵
        result = process_modal_hotkey(hotkey, context)
        
        if result:
            self._report_status(context, result)
            self._play_sound("hotkey")
            
            # 檢查是否需要執行
            if self._modal_kernel.state == ModalState.EXECUTE and "執行" in result:
                return self._execute_alignment(context)
            
            # 檢查是否需要取消
            if self._modal_kernel.state == ModalState.CANCEL:
                return self._finish_modal(context, "CANCELLED")
        
        return {"RUNNING_MODAL"}
    
    def _find_snap_point(self, context, event) -> Optional[Dict[str, Any]]:
        """尋找吸附點 - 子類覆蓋"""
        # 默認實現：射線檢測
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
        
        # 射線檢測
        hit_result = context.scene.ray_cast(context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            return {
                "position": hit_point,
                "type": "RAY",
                "object": hit_obj,
                "normal": hit_normal,
                "element": hit_face_index
            }
        
        return None
    
    def _update_snap_preview(self, context, snap_point):
        """更新吸附預覽"""
        # 應用約束
        constrained_point = apply_constraint_to_point(snap_point["position"])
        
        # 更新預覽
        if context.active_object:
            # 計算變換矩陣
            transform_matrix = self._calculate_preview_transform(context, constrained_point)
            
            # 更新預覽
            update_hover_preview(context, context.active_object, transform_matrix)
    
    def _calculate_preview_transform(self, context, target_point) -> Optional[Matrix]:
        """計算預覽變換矩陣 - 子類覆蓋"""
        # 默認實現：簡單平移
        if context.active_object:
            current_pos = context.active_object.matrix_world.to_translation()
            translation = target_point - current_pos
            return Matrix.Translation(translation)
        
        return None
    
    def _update_preview(self, context):
        """更新預覽"""
        # 子類可覆蓋此方法進行特定預覽更新
        pass
    
    def _execute_alignment(self, context):
        """執行對齊 - 子類覆蓋"""
        self._report_status(context, "執行對齊")
        return self._finish_modal(context, "FINISHED")
    
    def draw_3d_overlay(self):
        """繪製 3D 覆蓋層"""
        if not self._is_active:
            return
        
        # 繪製約束可視化
        if self._modal_kernel.constraint_active:
            visual_data = get_constraint_visual_data()
            self._draw_constraint_visual(visual_data)
        
        # 繪製點位
        self._draw_points()
        
        # 繪製連線
        self._draw_connections()
        
        # 子類可覆蓋此方法進行特定繪製
        self._draw_specific_3d_overlay()
    
    def draw_2d_hud(self):
        """繪製 2D HUD"""
        if not self._is_active or not self.show_hud:
            return
        
        import blf
        
        font_id = 0
        y_offset = 80
        line_height = 20
        
        # 繪製標題
        self._draw_hud_text("Smart Align Pro", 15, y_offset, (1, 1, 1, 1), 16)
        y_offset += line_height
        
        # 繪製模式
        status = get_modal_status()
        self._draw_hud_text(f"模式: {status['mode']}", 15, y_offset, (0.8, 0.8, 0.8, 1), 14)
        y_offset += line_height
        
        # 繪製坐標空間
        self._draw_hud_text(f"坐標: {status['coordinate_space']}", 15, y_offset, (0.8, 0.8, 0.8, 1), 14)
        y_offset += line_height
        
        # 繪製約束
        if status['constraint_mode'] != 'NONE':
            self._draw_hud_text(f"約束: {status['constraint_mode']}", 15, y_offset, (0.8, 1.0, 0.8, 1), 14)
            y_offset += line_height
        
        # 繪製提示
        hint = get_next_point_hint()
        self._draw_hud_text(hint, 15, y_offset, (1.0, 1.0, 0.5, 1), 14)
        y_offset += line_height
        
        # 繪製點位信息
        if status['points_count'] > 0:
            self._draw_hud_text(f"點位: {status['points_count']}/{status['max_points']}", 15, y_offset, (0.8, 0.8, 0.8, 1), 14)
            y_offset += line_height
            
            # 繪製點位列表
            for point_type, position in status['points'].items():
                self._draw_hud_text(f"  {point_type}: {position}", 15, y_offset, (0.6, 0.6, 0.6, 1), 12)
                y_offset += line_height
        
        # 繪製快捷鍵提示
        if self._modal_kernel.show_hint:
            y_offset = context.region.height - 100
            self._draw_hud_text("快捷鍵:", 15, y_offset, (0.8, 0.8, 0.8, 1), 12)
            y_offset += line_height
            
            shortcuts = [
                "1-6: 切換模式",
                "G/L/A: 坐標空間",
                "X/Y/Z: 軸約束",
                "Enter: 執行",
                "ESC: 取消"
            ]
            
            for shortcut in shortcuts:
                self._draw_hud_text(shortcut, 15, y_offset, (0.6, 0.6, 0.6, 1), 12)
                y_offset += line_height
        
        # 子類可覆蓋此方法進行特定 HUD 繪製
        self._draw_specific_2d_hud()
    
    def _draw_hud_text(self, text, x, y, color, size):
        """繪製 HUD 文字"""
        import blf
        
        font_id = 0
        blf.position(font_id, x, y, 0)
        blf.size(font_id, size, 72)
        blf.color(font_id, *color)
        blf.draw(font_id, text)
    
    def _draw_constraint_visual(self, visual_data):
        """繪製約束可視化"""
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        if not visual_data:
            return
        
        # 使用簡單的線條著色器
        try:
            shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        except:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
        for visual in visual_data:
            if visual["type"] == "AXIS":
                # 繪製軸線
                vertices = visual["vertices"]
                color = visual["color"]
                
                batch = batch_for_shader(shader, 'LINES', {"pos": vertices})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
            
            elif visual["type"] == "PLANE":
                # 繪製平面（簡化為邊框）
                vertices = visual["vertices"]
                color = visual["color"]
                
                # 創建平面邊框
                plane_edges = []
                for i in range(len(vertices)):
                    plane_edges.extend([vertices[i], vertices[(i + 1) % len(vertices)]])
                
                batch = batch_for_shader(shader, 'LINES', {"pos": plane_edges})
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)
    
    def _draw_points(self):
        """繪製點位"""
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        try:
            shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        except:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
        # 繪製已選擇的點位
        for point_type, point in self._modal_kernel.points.items():
            # 根據點位類型設置顏色
            if "SOURCE" in point_type:
                color = (1.0, 0.2, 0.2, 1.0)  # 紅色
            elif "TARGET" in point_type:
                color = (0.2, 1.0, 0.2, 1.0)  # 綠色
            else:
                color = (1.0, 1.0, 0.2, 1.0)  # 黃色
            
            # 繪製點
            batch = batch_for_shader(shader, 'POINTS', {"pos": [point.position]})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
    
    def _draw_connections(self):
        """繪製連線"""
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        try:
            shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        except:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
        # 繪製點位之間的連線
        connections = self._get_point_connections()
        
        for connection in connections:
            start_point = connection[0]
            end_point = connection[1]
            
            # 根據連線類型設置顏色
            if connection[2] == "SOURCE":
                color = (1.0, 0.5, 0.5, 0.8)  # 淺紅色
            elif connection[2] == "TARGET":
                color = (0.5, 1.0, 0.5, 0.8)  # 淺綠色
            else:
                color = (1.0, 1.0, 0.5, 0.8)  # 淺黃色
            
            # 繪製連線
            batch = batch_for_shader(shader, 'LINES', {"pos": [start_point, end_point]})
            shader.bind()
            shader.uniform_float("color", color)
            batch.draw(shader)
    
    def _get_point_connections(self):
        """獲取點位連線 - 子類覆蓋"""
        return []
    
    def _draw_specific_3d_overlay(self):
        """繪製特定 3D 覆蓋層 - 子類覆蓋"""
        pass
    
    def _draw_specific_2d_hud(self):
        """繪製特定 2D HUD - 子類覆蓋"""
        pass
    
    def _play_sound(self, sound_type):
        """播放音效"""
        if not self.enable_sound:
            return
        
        # 這裡可以添加音效播放邏輯
        # 例如：bpy.ops.wm.play_sound(sound_file=sound_file)
        pass
    
    def _report_status(self, context, message):
        """報告狀態"""
        self.report({"INFO"}, message)
    
    def _finish_modal(self, context, result):
        """完成 Modal - v7.5 強制閉環清理
        
        致命差距④修復：確保所有狀態完全清理
        """
        # v7.5: 使用統一預覽引擎進行完整清理
        from ..core.unified_preview_engine import get_preview_engine
        preview_engine = get_preview_engine()
        
        active_obj = getattr(self, 'active_obj', None)
        
        if result == "CANCELLED":
            # 取消時：完全撤銷預覽
            preview_engine.cancel(context, active_obj)
        else:
            # 完成時：提交預覽
            preview_engine.commit(context, active_obj)
        
        # 清理舊式預覽系統
        if self.show_preview:
            deactivate_hover_preview(context)
        
        # 移除繪製處理器
        for handler in self._handlers:
            try:
                context.space_data.draw_handler_remove(handler, 'WINDOW')
            except Exception as e:
                # v7.5: 記錄清理失敗但不中斷
                print(f"[SmartAlignPro][Cleanup] Handler removal failed: {e}")
        
        self._handlers.clear()
        
        # 恢復游標
        context.window.cursor_set('DEFAULT')
        
        # 標記為非活躍
        self._is_active = False
        
        # 重置 Modal 核心
        self._modal_kernel.reset()
        
        # 重置統一決策引擎 (避免狀態殘留)
        from ..core.unified_snap_decision import reset_unified_snap_engine
        reset_unified_snap_engine()
        
        # 報告完成
        if result == "FINISHED":
            self._report_status(context, "對齊完成")
        elif result == "CANCELLED":
            self._report_status(context, "對齊已取消")
        
        return {"FINISHED"} if result == "FINISHED" else {"CANCELLED"}
