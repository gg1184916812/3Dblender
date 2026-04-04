"""
Smart Align Pro - Pick Reference Point Modal
實現 CAD Transform 級別的參考點選取系統
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatProperty
from mathutils import Vector, geometry
from typing import Optional, Dict, Any, List, Tuple
import time

from ..core.topology_alignment import topology_alignment_system
from ..core.snap_priority_solver import get_snap_context, solve_snap_priority
from ..core.coordinate_space_solver import get_coordinate_space_solver, CoordinateSpaceType


class ReferencePoint:
    """參考點類別"""
    def __init__(self, position: Vector, point_type: str, object=None, element=None, normal=None):
        self.position = position
        self.point_type = point_type  # VERTEX, EDGE, FACE, PLANE, AXIS
        self.object = object
        self.element = element
        self.normal = normal
        self.distance = 0.0
        self.confidence = 1.0
        self.timestamp = time.time()


class PickReferencePointModal(Operator):
    """參考點選取 Modal - CAD Transform 級別的參考點選取"""
    
    bl_idname = "smartalignpro.pick_reference_point_modal"
    bl_label = "選取參考點"
    bl_description = "CAD Transform 級別的滑鼠交互式參考點選取"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}
    
    # 參考點類型
    reference_type: EnumProperty(
        name="參考點類型",
        description="選擇參考點的類型",
        items=[
            ("VERTEX", "頂點", "選擇頂點作為參考點"),
            ("EDGE", "邊緣", "選擇邊緣作為參考點"),
            ("FACE", "面", "選擇面作為參考點"),
            ("PLANE", "平面", "定義平面作為參考點"),
            ("AXIS", "軸", "定義軸作為參考點"),
            ("AUTO", "自動", "自動選擇最佳參考點"),
        ],
        default="AUTO",
    )
    
    # 選項
    show_preview: BoolProperty(
        name="顯示預覽",
        description="顯示參考點預覽",
        default=True,
    )
    
    snap_tolerance: FloatProperty(
        name="吸附容差",
        description="吸附容差距離",
        default=0.01,
        min=0.001,
        max=0.1,
        precision=4,
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.reference_points = []
        self.current_snap = None
        self.hover_point = None
        self.is_active = False
        self.start_time = time.time()
        self.last_update_time = 0
        
        # 繪製處理器
        self.draw_handlers = []
        
        # 坐標空間求解器
        self.space_solver = get_coordinate_space_solver()
        
    def invoke(self, context, event):
        """啟動 Modal"""
        # 檢查前置條件
        if not context.active_object:
            self.report({"WARNING"}, "請先選擇一個物件")
            return {"CANCELLED"}
        
        # 設置上下文
        self.space_solver.set_context(context)
        
        # 啟動 Modal
        self.is_active = True
        
        # 添加繪製處理器
        self._setup_draw_handlers(context)
        
        # 設置游標
        context.window.cursor_set('CROSSHAIR')
        
        # 添加 Modal 處理器
        context.window_manager.modal_handler_add(self)
        
        # 報告啟動
        self.report({"INFO"}, f"開始選取 {self.reference_type} 參考點")
        
        return {"RUNNING_MODAL"}
    
    def modal(self, context, event):
        """Modal 事件處理"""
        if not self.is_active:
            return {"FINISHED"}
        
        # ESC 鍵退出
        if event.type == "ESC" and event.value == "PRESS":
            return self._finish_modal(context, "CANCELLED")
        
        # 滑鼠移動更新吸附
        if event.type == "MOUSEMOVE":
            return self._handle_mouse_move(context, event)
        
        # 左鍵確認點位
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            return self._handle_left_click(context, event)
        
        # 右鍵取消當前點
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            return self._handle_right_click(context, event)
        
        # 數字鍵切換參考點類型
        if event.type in {"ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX"} and event.value == "PRESS":
            return self._handle_type_switch(context, event)
        
        # 強制重繪
        context.area.tag_redraw()
        
        return {"RUNNING_MODAL"}
    
    def _handle_mouse_move(self, context, event):
        """處理滑鼠移動"""
        # 尋找吸附點
        snap_point = self._find_snap_point(context, event)
        
        if snap_point:
            self.current_snap = snap_point
            self.hover_point = snap_point
        
        return {"RUNNING_MODAL"}
    
    def _handle_left_click(self, context, event):
        """處理左鍵點擊"""
        if self.current_snap:
            # 創建參考點
            ref_point = ReferencePoint(
                position=self.current_snap.position,
                point_type=self.current_snap.snap_type,
                object=self.current_snap.object,
                element=self.current_snap.element,
                normal=self.current_snap.normal
            )
            
            # 添加到參考點列表
            self.reference_points.append(ref_point)
            
            # 報告選擇
            self.report({"INFO"}, f"已選擇 {ref_point.point_type} 參考點")
            
            # 如果是單點模式，完成選擇
            if self.reference_type != "PLANE" and self.reference_type != "AXIS":
                return self._finish_modal(context, "FINISHED")
        
        return {"RUNNING_MODAL"}
    
    def _handle_right_click(self, context, event):
        """處理右鍵點擊"""
        # 移除最後一個參考點
        if self.reference_points:
            removed_point = self.reference_points.pop()
            self.report({"INFO"}, f"已移除 {removed_point.point_type} 參考點")
        
        return {"RUNNING_MODAL"}
    
    def _handle_type_switch(self, context, event):
        """處理參考點類型切換"""
        type_map = {
            "ONE": "VERTEX",
            "TWO": "EDGE",
            "THREE": "FACE",
            "FOUR": "PLANE",
            "FIVE": "AXIS",
            "SIX": "AUTO",
        }
        
        if event.type in type_map:
            self.reference_type = type_map[event.type]
            self.reference_points.clear()  # 清除之前的參考點
            self.report({"INFO"}, f"切換到 {self.reference_type} 模式")
        
        return {"RUNNING_MODAL"}
    
    def _find_snap_point(self, context, event):
        """尋找吸附點"""
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
        
        # 射線檢測
        hit_result = context.scene.ray_cast(context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            if hit_obj and hit_obj.type == "MESH":
                # 使用拓撲對齊系統尋找精確吸附點
                topology_points = topology_alignment_system.solver.find_topology_snap_points(
                    context, hit_obj, mouse_pos, view_vector
                )
                
                if topology_points:
                    # 根據參考點類型過濾
                    filtered_points = self._filter_points_by_type(topology_points)
                    
                    if filtered_points:
                        # 使用優先級求解器排序
                        snap_context = get_snap_context(context)
                        sorted_points = solve_snap_priority(filtered_points, snap_context)
                        
                        if sorted_points:
                            return sorted_points[0]
                
                # 如果沒有拓撲點，使用射線擊中點
                return self._create_ray_snap_point(hit_obj, hit_point, hit_normal, hit_face_index)
        
        return None
    
    def _filter_points_by_type(self, topology_points):
        """根據參考點類型過濾點位"""
        if self.reference_type == "VERTEX":
            return [p for p in topology_points if ((p.snap_type.value if hasattr(p.snap_type, "value") else p.snap_type) == "VERTEX")]
        elif self.reference_type == "EDGE":
            return [p for p in topology_points if ((p.snap_type.value if hasattr(p.snap_type, "value") else p.snap_type) == "EDGE")]
        elif self.reference_type == "FACE":
            return [p for p in topology_points if ((p.snap_type.value if hasattr(p.snap_type, "value") else p.snap_type) == "FACE")]
        elif self.reference_type == "AUTO":
            return topology_points
        else:
            return topology_points
    
    def _create_ray_snap_point(self, obj, point, normal, face_index):
        """創建射線吸附點"""
        from ..core.topology_alignment import TopologySnapPoint, SnapType
        
        return TopologySnapPoint(
            position=point,
            snap_type=SnapType.RAY,
            element=face_index,
            normal=normal,
            object=obj
        )
    
    def _setup_draw_handlers(self, context):
        """設置繪製處理器"""
        # 3D 視圖繪製處理器
        handler_3d = context.space_data.draw_handler_add(
            self.draw_3d_overlay, (), 'WINDOW', 'POST_VIEW'
        )
        self.draw_handlers.append(handler_3d)
        
        # 2D 視圖繪製處理器
        handler_2d = context.space_data.draw_handler_add(
            self.draw_2d_hud, (), 'WINDOW', 'POST_PIXEL'
        )
        self.draw_handlers.append(handler_2d)
    
    def draw_3d_overlay(self):
        """繪製 3D 覆蓋層"""
        if not self.is_active:
            return
        
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        try:
            shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        except:
            shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        
        # 繪製已選擇的參考點
        for ref_point in self.reference_points:
            self._draw_reference_point(shader, ref_point.position, ref_point.point_type, (1.0, 0.2, 0.2, 1.0))
        
        # 繪製當前懸停點
        if self.current_snap:
            self._draw_reference_point(shader, self.current_snap.position, (self.current_snap.snap_type.value if hasattr(self.current_snap.snap_type, "value") else self.current_snap.snap_type), (0.2, 1.0, 0.2, 1.0))
        
        # 繪製參考線（如果有多個點）
        if len(self.reference_points) > 1:
            self._draw_reference_lines(shader)
    
    def draw_2d_hud(self):
        """繪製 2D HUD"""
        if not self.is_active:
            return
        
        import blf
        
        font_id = 0
        y_offset = 80
        line_height = 20
        
        # 繪製標題
        self._draw_hud_text("參考點選取", 15, y_offset, (1, 1, 1, 1), 16)
        y_offset += line_height
        
        # 繪製當前模式
        self._draw_hud_text(f"類型: {self.reference_type}", 15, y_offset, (0.8, 0.8, 0.8, 1), 14)
        y_offset += line_height
        
        # 繪製已選擇的參考點
        self._draw_hud_text(f"已選擇: {len(self.reference_points)} 個參考點", 15, y_offset, (0.8, 0.8, 0.8, 1), 14)
        y_offset += line_height
        
        # 繪製快捷鍵提示
        self._draw_hud_text("快捷鍵:", 15, y_offset, (0.8, 0.8, 0.8, 1), 12)
        y_offset += line_height
        
        shortcuts = [
            "1-6: 切換類型",
            "左鍵: 選擇點",
            "右鍵: 移除點",
            "ESC: 完成"
        ]
        
        for shortcut in shortcuts:
            self._draw_hud_text(shortcut, 15, y_offset, (0.6, 0.6, 0.6, 1), 12)
            y_offset += line_height
    
    def _draw_reference_point(self, shader, position, point_type, color):
        """繪製參考點"""
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        # 根據類型設置大小和形狀
        if point_type == "VERTEX":
            size = 8.0
            shape = "POINTS"
        elif point_type == "EDGE":
            size = 6.0
            shape = "POINTS"
        elif point_type == "FACE":
            size = 10.0
            shape = "POINTS"
        else:
            size = 6.0
            shape = "POINTS"
        
        # 繪製點
        batch = batch_for_shader(shader, shape, {"pos": [position]})
        shader.bind()
        shader.uniform_float("color", color)
        gpu.state.point_size_set(size)
        batch.draw(shader)
        gpu.state.point_size_set(1.0)
    
    def _draw_reference_lines(self, shader):
        """繪製參考線"""
        import gpu
        from gpu_extras.batch import batch_for_shader
        
        # 創建連線
        line_coords = []
        for i in range(len(self.reference_points) - 1):
            line_coords.extend([
                self.reference_points[i].position,
                self.reference_points[i + 1].position
            ])
        
        if line_coords:
            batch = batch_for_shader(shader, 'LINES', {"pos": line_coords})
            shader.bind()
            shader.uniform_float("color", (1.0, 1.0, 0.2, 0.8))
            batch.draw(shader)
    
    def _draw_hud_text(self, text, x, y, color, size):
        """繪製 HUD 文字"""
        import blf
        
        font_id = 0
        blf.position(font_id, x, y, 0)
        blf.size(font_id, size, 72)
        blf.color(font_id, *color)
        blf.draw(font_id, text)
    
    def _finish_modal(self, context, result):
        """完成 Modal"""
        # 清理繪製處理器
        for handler in self.draw_handlers:
            try:
                context.space_data.draw_handler_remove(handler, 'WINDOW')
            except:
                pass
        
        self.draw_handlers.clear()
        
        # 恢復游標
        context.window.cursor_set('DEFAULT')
        
        # 標記為非活躍
        self.is_active = False
        
        # 報告完成
        if result == "FINISHED":
            self.report({"INFO"}, f"參考點選取完成，共選擇 {len(self.reference_points)} 個點")
        elif result == "CANCELLED":
            self.report({"INFO"}, "參考點選取已取消")
        
        return {"FINISHED"} if result == "FINISHED" else {"CANCELLED"}
    
    def get_reference_points(self):
        """獲取參考點列表"""
        return self.reference_points.copy()
    
    def clear_reference_points(self):
        """清除所有參考點"""
        self.reference_points.clear()


# 註冊類別
CLASSES = [
    PickReferencePointModal,
]


def register():
    """註冊參考點選取操作器"""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    """註銷參考點選取操作器"""
    for cls in CLASSES:
        bpy.utils.unregister_class(cls)
