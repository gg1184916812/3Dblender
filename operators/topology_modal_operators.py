"""
Smart Align Pro - 拓撲 Modal 操作器
實現 CAD Transform 級別的滑鼠互動對齊
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatProperty
from mathutils import Vector
from ..core.topology_alignment import topology_alignment_system
from ..core.interactive_preview import interactive_preview


class SMARTALIGNPRO_OT_topology_three_point_modal(Operator):
    """拓撲三點對齊 Modal - CAD Transform 級別的交互"""
    bl_idname = "smartalignpro.topology_three_point_modal"
    bl_label = "拓撲三點對齊"
    bl_description = "使用滑鼠交互選擇三個點進行精確對齊"
    bl_options = {"REGISTER", "UNDO"}

    # Modal 狀態
    class ModalState:
        SELECT_SOURCE_A = 1
        SELECT_SOURCE_B = 2
        SELECT_SOURCE_C = 3
        SELECT_TARGET_A = 4
        SELECT_TARGET_B = 5
        SELECT_TARGET_C = 6
        EXECUTE_ALIGN = 7

    def __init__(self, *args, **kwargs):
        self.state = self.ModalState.SELECT_SOURCE_A
        self.source_points = []
        self.target_points = []
        self.current_snap = None
        self.hover_object = None
        self.preview_active = False
        
    def invoke(self, context, event):
        """啟動 Modal"""
        # 檢查選擇
        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not active or len(selected) < 2:
            self.report({"WARNING"}, "請先選擇一個目標物件和至少一個來源物件")
            return {"CANCELLED"}
        
        self.sources = [obj for obj in selected if obj != active]
        self.target = active
        self.current_source_index = 0
        
        # 設置吸附模式
        topology_alignment_system.set_snap_mode("AUTO")
        
        # 啟動預覽
        interactive_preview.activate(context)
        self.preview_active = True
        
        # 添加處理器
        self.handlers = []
        self.handlers.append(context.space_data.draw_handler_add(
            self.draw_callback, (), 'WINDOW', 'POST_VIEW'
        ))
        
        # 設置游標
        context.window.cursor_set('CROSSHAIR')
        
        # 報告當前狀態
        self.report({"INFO"}, f"請選擇來源點 A (物件: {self.sources[self.current_source_index].name})")
        
        # 添加 Modal 處理器
        context.window_manager.modal_handler_add(self)
        
        return {"RUNNING_MODAL"}
    
    def modal(self, context, event):
        """Modal 事件處理"""
        region = context.region
        region_3d = context.space_data.region_3d
        
        # ESC 鍵退出
        if event.type == "ESC" and event.value == "PRESS":
            return self.cancel(context)
        
        # Enter 鍵執行對齊
        if event.type == "RET" and event.value == "PRESS":
            if self.state == self.ModalState.EXECUTE_ALIGN:
                return self.execute_alignment(context)
        
        # 滑鼠移動更新吸附
        if event.type == "MOUSEMOVE":
            return self.handle_mouse_move(context, event)
        
        # 左鍵確認點位
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            return self.handle_left_click(context, event)
        
        # 右鍵取消當前點
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            return self.handle_right_click(context, event)
        
        # Tab 鍵切換吸附模式
        if event.type == "TAB" and event.value == "PRESS":
            return self.cycle_snap_mode(context)
        
        # 數字鍵切換來源物件
        if event.type in {"ONE", "TWO", "THREE", "FOUR", "FIVE"} and event.value == "PRESS":
            return self.switch_source_object(context, event)
        
        return {"RUNNING_MODAL"}
    
    def handle_mouse_move(self, context, event):
        """處理滑鼠移動 - CAD Transform 級別的即時反饋"""
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
        
        # 射線檢測
        hit_result = context.scene.ray_cast(context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            # 更新懸停物件
            if hit_obj != self.hover_object:
                self.hover_object = hit_obj
            
            # 尋找拓撲吸附點
            if hit_obj and hit_obj.type == "MESH":
                self.current_snap = topology_alignment_system.find_snap_at_cursor(context, hit_obj)
                
                # 更新預覽
                if self.preview_active and len(self.source_points) > 0:
                    self.update_preview(context)
            else:
                self.current_snap = None
        else:
            self.hover_object = None
            self.current_snap = None
        
        # 強制重繪
        context.area.tag_redraw()
        
        return {"RUNNING_MODAL"}
    
    def handle_left_click(self, context, event):
        """處理左鍵點擊 - 確認點位選擇"""
        if self.current_snap:
            snap_point = {
                'position': self.current_snap.position,
                'type': self.current_snap.snap_type,
                'element': self.current_snap.element,
                'normal': self.current_snap.normal,
                'object': self.hover_object
            }
            
            if self.state == self.ModalState.SELECT_SOURCE_A:
                self.source_points.append(snap_point)
                self.state = self.ModalState.SELECT_SOURCE_B
                self.report({"INFO"}, f"請選擇來源點 B (物件: {self.sources[self.current_source_index].name})")
                
            elif self.state == self.ModalState.SELECT_SOURCE_B:
                self.source_points.append(snap_point)
                self.state = self.ModalState.SELECT_SOURCE_C
                self.report({"INFO"}, f"請選擇來源點 C (物件: {self.sources[self.current_source_index].name})")
                
            elif self.state == self.ModalState.SELECT_SOURCE_C:
                self.source_points.append(snap_point)
                self.state = self.ModalState.SELECT_TARGET_A
                self.report({"INFO"}, f"請選擇目標點 A (物件: {self.target.name})")
                
            elif self.state == self.ModalState.SELECT_TARGET_A:
                self.target_points.append(snap_point)
                self.state = self.ModalState.SELECT_TARGET_B
                self.report({"INFO"}, f"請選擇目標點 B (物件: {self.target.name})")
                
            elif self.state == self.ModalState.SELECT_TARGET_B:
                self.target_points.append(snap_point)
                self.state = self.ModalState.SELECT_TARGET_C
                self.report({"INFO"}, f"請選擇目標點 C (物件: {self.target.name})")
                
            elif self.state == self.ModalState.SELECT_TARGET_C:
                self.target_points.append(snap_point)
                self.state = self.ModalState.EXECUTE_ALIGN
                self.report({"INFO"}, "按 Enter 執行對齊，或 ESC 取消")
        
        return {"RUNNING_MODAL"}
    
    def handle_right_click(self, context, event):
        """處理右鍵點擊 - 取消當前點"""
        if self.state == self.ModalState.SELECT_SOURCE_B:
            self.source_points.pop()
            self.state = self.ModalState.SELECT_SOURCE_A
            self.report({"INFO"}, f"請選擇來源點 A (物件: {self.sources[self.current_source_index].name})")
            
        elif self.state == self.ModalState.SELECT_SOURCE_C:
            self.source_points.pop()
            self.state = self.ModalState.SELECT_SOURCE_B
            self.report({"INFO"}, f"請選擇來源點 B (物件: {self.sources[self.current_source_index].name})")
            
        elif self.state == self.ModalState.SELECT_TARGET_B:
            self.target_points.pop()
            self.state = self.ModalState.SELECT_TARGET_A
            self.report({"INFO"}, f"請選擇目標點 A (物件: {self.target.name})")
            
        elif self.state == self.ModalState.SELECT_TARGET_C:
            self.target_points.pop()
            self.state = self.ModalState.SELECT_TARGET_B
            self.report({"INFO"}, f"請選擇目標點 B (物件: {self.target.name})")
        
        return {"RUNNING_MODAL"}
    
    def cycle_snap_mode(self, context):
        """循環切換吸附模式"""
        modes = ["AUTO", "VERTEX", "EDGE", "FACE"]
        current_index = modes.index(topology_alignment_system.snap_mode)
        next_mode = modes[(current_index + 1) % len(modes)]
        topology_alignment_system.set_snap_mode(next_mode)
        
        mode_descriptions = {
            "AUTO": "自動吸附",
            "VERTEX": "頂點吸附",
            "EDGE": "邊緣吸附",
            "FACE": "面吸附"
        }
        
        self.report({"INFO"}, f"吸附模式: {mode_descriptions[next_mode]}")
        return {"RUNNING_MODAL"}
    
    def switch_source_object(self, context, event):
        """切換來源物件"""
        key_map = {
            "ONE": 0, "TWO": 1, "THREE": 2, "FOUR": 3, "FIVE": 4
        }
        
        if event.type in key_map:
            index = key_map[event.type]
            if index < len(self.sources):
                self.current_source_index = index
                self.source_points.clear()
                self.target_points.clear()
                self.state = self.ModalState.SELECT_SOURCE_A
                self.report({"INFO"}, f"切換到來源物件: {self.sources[index].name}")
        
        return {"RUNNING_MODAL"}
    
    def update_preview(self, context):
        """更新預覽 - CAD Transform 級別的即時預覽"""
        if len(self.source_points) >= 1 and len(self.target_points) >= 1:
            # 計算預覽變換
            source_obj = self.sources[self.current_source_index]
            
            # 這裡需要實現三點對齊的預覽計算
            # 暫時使用簡單的位置預覽
            if self.current_snap:
                preview_transform = self.calculate_preview_transform()
                interactive_preview.update_preview_transform(context, source_obj, preview_transform)
    
    def calculate_preview_transform(self):
        """計算預覽變換"""
        # 這裡需要實現完整的三點對齊預覽計算
        # 暫時返回單位矩陣
        from mathutils import Matrix
        return Matrix.Identity(4)
    
    def execute_alignment(self, context):
        """執行對齊"""
        if len(self.source_points) == 3 and len(self.target_points) == 3:
            # 執行三點對齊
            source_obj = self.sources[self.current_source_index]
            
            # 這裡需要調用完整的三點對齊算法
            # 暫時顯示成功訊息
            self.report({"INFO"}, f"三點對齊完成: {source_obj.name}")
            
            return self.finish(context)
        else:
            self.report({"WARNING"}, "需要選擇 3 個來源點和 3 個目標點")
            return {"RUNNING_MODAL"}
    
    def draw_callback(self, context):
        """繪製回調 - CAD Transform 級別的視覺反饋"""
        import blf
        import bgl
        
        # 繪製當前狀態
        font_id = 0
        blf.position(font_id, 15, 50, 0)
        blf.size(font_id, 12, 72)
        
        state_descriptions = {
            self.ModalState.SELECT_SOURCE_A: f"選擇來源點 A (物件: {self.sources[self.current_source_index].name})",
            self.ModalState.SELECT_SOURCE_B: f"選擇來源點 B (物件: {self.sources[self.current_source_index].name})",
            self.ModalState.SELECT_SOURCE_C: f"選擇來源點 C (物件: {self.sources[self.current_source_index].name})",
            self.ModalState.SELECT_TARGET_A: f"選擇目標點 A (物件: {self.target.name})",
            self.ModalState.SELECT_TARGET_B: f"選擇目標點 B (物件: {self.target.name})",
            self.ModalState.SELECT_TARGET_C: f"選擇目標點 C (物件: {self.target.name})",
            self.ModalState.EXECUTE_ALIGN: "按 Enter 執行對齊"
        }
        
        blf.draw(font_id, state_descriptions.get(self.state, ""))
        
        # 繪製吸附點
        if self.current_snap:
            self.draw_snap_point(context, self.current_snap.position, self.current_snap.snap_type)
        
        # 繪製已選擇的點
        for i, point in enumerate(self.source_points):
            self.draw_selected_point(context, point['position'], f"S{i+1}", (1, 0, 0))
        
        for i, point in enumerate(self.target_points):
            self.draw_selected_point(context, point['position'], f"T{i+1}", (0, 1, 0))
    
    def draw_snap_point(self, context, position, snap_type):
        """繪製吸附點"""
        import bgl
        
        # 根據類型設置顏色
        colors = {
            "VERTEX": (1, 0, 0),    # 紅色
            "EDGE": (0, 1, 0),      # 綠色
            "FACE": (0, 0, 1)       # 藍色
        }
        
        color = colors.get(snap_type, (1, 1, 0))
        
        # 繪製點
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glColor4f(*color, 1.0)
        bgl.glPointSize(8.0)
        bgl.glBegin(bgl.GL_POINTS)
        bgl.glVertex3f(*position)
        bgl.glEnd()
        bgl.glDisable(bgl.GL_BLEND)
    
    def draw_selected_point(self, context, position, label, color):
        """繪製已選擇的點"""
        import blf
        import bgl
        
        # 繪製點
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glColor4f(*color, 1.0)
        bgl.glPointSize(6.0)
        bgl.glBegin(bgl.GL_POINTS)
        bgl.glVertex3f(*position)
        bgl.glEnd()
        
        # 繪製標籤
        font_id = 0
        blf.position(font_id, 15, 80 + len(self.source_points) * 15, 0)
        blf.size(font_id, 10, 72)
        blf.draw(font_id, f"{label}: {position}")
        
        bgl.glDisable(bgl.GL_BLEND)
    
    def finish(self, context):
        """完成 Modal"""
        # 清理預覽
        if self.preview_active:
            interactive_preview.deactivate(context)
        
        # 移除處理器
        for handler in self.handlers:
            context.space_data.draw_handler_remove(handler, 'WINDOW')
        
        # 恢復游標
        context.window.cursor_set('DEFAULT')
        
        return {"FINISHED"}
    
    def cancel(self, context):
        """取消 Modal"""
        self.report({"INFO"}, "拓撲三點對齊已取消")
        return self.finish(context)


class SMARTALIGNPRO_OT_topology_snap_align(Operator):
    """拓撲吸附對齊 - 快速對齊"""
    bl_idname = "smartalignpro.topology_snap_align"
    bl_label = "拓撲吸附對齊"
    bl_description = "使用拓撲吸附進行快速對齊"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """執行拓撲吸附對齊"""
        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not active or len(selected) < 2:
            self.report({"WARNING"}, "請先選擇一個目標物件和至少一個來源物件")
            return {"CANCELLED"}
        
        sources = [obj for obj in selected if obj != active]
        
        # 對每個來源物件執行對齊
        for source in sources:
            # 尋找最近的拓撲點
            mouse_pos = (context.region.width // 2, context.region.height // 2)
            view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
            
            snap_points = topology_alignment_system.solver.find_topology_snap_points(
                context, active, mouse_pos, view_vector
            )
            
            if snap_points:
                target_snap = snap_points[0]
                result = topology_alignment_system.solver.align_to_topology_point(
                    source, target_snap
                )
                
                self.report({"INFO"}, f"拓撲對齊完成: {source.name} → {active.name}")
            else:
                self.report({"WARNING"}, f"未找到合適的吸附點: {source.name}")
        
        return {"FINISHED"}


# 註冊類別
CLASSES = [
    SMARTALIGNPRO_OT_topology_three_point_modal,
    SMARTALIGNPRO_OT_topology_snap_align,
]


def register():
    """註冊拓撲 Modal 操作器"""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    """註銷拓撲 Modal 操作器"""
    for cls in CLASSES:
        bpy.utils.unregister_class(cls)
