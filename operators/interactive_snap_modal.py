"""
Smart Align Pro - Interactive Modal Snapping Engine
實現 CAD Transform 級別的即時滑鼠吸附解算
這是 CAD Transform 的靈魂
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatProperty
from mathutils import Vector, Matrix, geometry
from ..core.topology_alignment import topology_alignment_system
from ..core.interactive_preview import interactive_preview
from ..core.snap_priority_solver import get_snap_context, solve_snap_priority


class InteractiveSnapPoint:
    """交互式吸附點"""
    def __init__(self, position, snap_type, element, normal=None, object=None):
        self.position = position
        self.snap_type = snap_type
        self.element = element
        self.normal = normal
        self.object = object
        self.distance = 0.0
        self.confidence = 1.0


class InteractiveSnapEngine:
    """交互式吸附引擎 - CAD Transform 的核心"""
    
    def __init__(self, *args, **kwargs):
        self.tolerance = 0.01
        self.constraint_mode = "NONE"  # NONE, X, Y, Z, XY, XZ, YZ, EDGE, FACE
        self.reference_system = "WORLD"  # WORLD, LOCAL, CUSTOM
        self.temp_pivot = None
        self.custom_reference_matrix = None
        
    def find_snap_points_at_cursor(self, context, mouse_pos, view_vector):
        """在游標位置尋找吸附點"""
        snap_points = []
        
        # 射線檢測
        hit_result = context.scene.ray_cast(context.view_layer.depsgraph, mouse_pos, view_vector)
        
        if hit_result[0]:
            hit_obj, hit_point, hit_normal, hit_face_index = hit_result
            
            if hit_obj and hit_obj.type == "MESH":
                # 尋找拓撲吸附點
                topology_points = topology_alignment_system.solver.find_topology_snap_points(
                    context, hit_obj, mouse_pos, view_vector
                )
                
                # 轉換為交互式吸附點
                for topo_point in topology_points:
                    snap_point = InteractiveSnapPoint(
                        topo_point.position,
                        topo_point.snap_type,
                        topo_point.element,
                        topo_point.normal,
                        hit_obj
                    )
                    snap_point.distance = topo_point.distance
                    snap_point.confidence = topo_point.confidence
                    snap_points.append(snap_point)
                
                # 添加幾何吸附點
                self._add_geometry_snap_points(snap_points, hit_obj, hit_point, hit_normal)
        
        # 應用約束
        if self.constraint_mode != "NONE":
            snap_points = self._apply_constraint(snap_points, context)
        
        # 應用參考系統
        snap_points = self._apply_reference_system(snap_points, context)
        
        # 排序並返回最佳點
        if snap_points:
            snap_context = get_snap_context(context)
            sorted_points = solve_snap_priority(snap_points, snap_context)
            return sorted_points[0] if sorted_points else None
        
        return None
    
    def _add_geometry_snap_points(self, snap_points, obj, hit_point, hit_normal):
        """添加幾何吸附點"""
        # 添加射線擊中點
        ray_snap = InteractiveSnapPoint(hit_point, "RAY", None, hit_normal, obj)
        ray_snap.distance = 0.0
        ray_snap.confidence = 1.0
        snap_points.append(ray_snap)
        
        from ..utils.bbox_utils import get_bbox_center_world
        # 添加物件中心
        obj_center = get_bbox_center_world(obj)
        center_snap = InteractiveSnapPoint(obj_center, "CENTER", None, None, obj)
        center_snap.distance = (obj_center - hit_point).length
        center_snap.confidence = 0.8
        snap_points.append(center_snap)
        
        # 添加邊界框角點
        bbox = obj.bound_box
        for i, corner in enumerate(bbox):
            world_corner = obj.matrix_world @ Vector(corner)
            distance = (world_corner - hit_point).length
            if distance < self.tolerance:
                corner_snap = InteractiveSnapPoint(world_corner, "CORNER", None, None, obj)
                corner_snap.distance = distance
                corner_snap.confidence = 0.9
                snap_points.append(corner_snap)
    
    def _apply_constraint(self, snap_points, context):
        """應用約束"""
        if self.constraint_mode == "NONE":
            return snap_points
        
        constrained_points = []
        
        for snap_point in snap_points:
            constrained_point = self._apply_constraint_to_point(snap_point, context)
            if constrained_point:
                constrained_points.append(constrained_point)
        
        return constrained_points
    
    def _apply_constraint_to_point(self, snap_point, context):
        """對單個點應用約束"""
        pos = snap_point.position
        
        if self.constraint_mode in ["X", "Y", "Z"]:
            # 軸約束
            axis_index = {"X": 0, "Y": 1, "Z": 2}[self.constraint_mode]
            constrained_pos = Vector(pos)
            if self.temp_pivot:
                constrained_pos[axis_index] = self.temp_pivot[axis_index]
            else:
                # 使用游標位置作為約束參考
                constrained_pos[axis_index] = context.scene.cursor.location[axis_index]
            
            snap_point.position = constrained_pos
            return snap_point
            
        elif self.constraint_mode in ["XY", "XZ", "YZ"]:
            # 平面約束
            axes = {"XY": [0, 1], "XZ": [0, 2], "YZ": [1, 2]}[self.constraint_mode]
            constrained_pos = Vector(pos)
            
            if self.temp_pivot:
                for i in range(3):
                    if i not in axes:
                        constrained_pos[i] = self.temp_pivot[i]
            else:
                cursor_pos = context.scene.cursor.location
                for i in range(3):
                    if i not in axes:
                        constrained_pos[i] = cursor_pos[i]
            
            snap_point.position = constrained_pos
            return snap_point
        
        elif self.constraint_mode == "EDGE":
            # 邊緣約束
            if snap_point.snap_type == "EDGE" and snap_point.element:
                # 將點投影到邊緣上
                edge = snap_point.element
                v1, v2 = edge.verts[0].co, edge.verts[1].co
                projected = geometry.intersect_point_line(pos, v1, v2)[0]
                snap_point.position = projected
                return snap_point
        
        elif self.constraint_mode == "FACE":
            # 面約束
            if snap_point.snap_type == "FACE" and snap_point.element:
                # 將點投影到面上
                face = snap_point.element
                if len(face.verts) >= 3:
                    # 使用面的前3個頂點構成平面
                    v1, v2, v3 = face.verts[0].co, face.verts[1].co, face.verts[2].co
                    projected = geometry.intersect_point_tri(pos, v1, v2, v3)
                    if projected:
                        snap_point.position = projected
                        return snap_point
        
        return snap_point
    
    def _apply_reference_system(self, snap_points, context):
        """應用參考系統"""
        if self.reference_system == "WORLD":
            return snap_points
        
        elif self.reference_system == "LOCAL":
            # 轉換到本地坐標系
            if context.active_object:
                obj = context.active_object
                local_matrix = obj.matrix_world.inverted()
                
                for snap_point in snap_points:
                    if snap_point.object == obj:
                        # 轉換到本地坐標
                        local_pos = local_matrix @ snap_point.position
                        # 這裡可以添加本地坐標系的約束
                        # 然後轉換回世界坐標
                        snap_point.position = obj.matrix_world @ local_pos
        
        elif self.reference_system == "CUSTOM":
            # 使用自定義參考矩陣
            if self.custom_reference_matrix:
                inv_matrix = self.custom_reference_matrix.inverted()
                
                for snap_point in snap_points:
                    # 轉換到自定義坐標系
                    custom_pos = inv_matrix @ snap_point.position
                    # 這裡可以添加自定義坐標系的約束
                    # 然後轉換回世界坐標
                    snap_point.position = self.custom_reference_matrix @ custom_pos
        
        return snap_points
    
    def set_constraint_mode(self, mode):
        """設置約束模式"""
        self.constraint_mode = mode
    
    def set_reference_system(self, system):
        """設置參考系統"""
        self.reference_system = system
    
    def set_temp_pivot(self, pivot):
        """設置臨時支點"""
        self.temp_pivot = pivot
    
    def set_custom_reference_matrix(self, matrix):
        """設置自定義參考矩陣"""
        self.custom_reference_matrix = matrix


class SMARTALIGNPRO_OT_interactive_snap_modal(Operator):
    """交互式吸附 Modal - CAD Transform 的靈魂"""
    bl_idname = "smartalignpro.interactive_snap_modal"
    bl_label = "交互式吸附"
    bl_description = "CAD Transform 級別的即時滑鼠吸附解算"
    bl_options = {"REGISTER", "UNDO"}

    # Modal 狀態
    class ModalState:
        SELECT_SOURCE = 1
        SELECT_TARGET = 2
        EXECUTE_ALIGN = 3

    def __init__(self, *args, **kwargs):
        self.state = self.ModalState.SELECT_SOURCE
        self.snap_engine = InteractiveSnapEngine()
        self.source_point = None
        self.target_point = None
        self.current_snap = None
        self.hover_object = None
        self.preview_active = False
        self.transform_matrix = None
        
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
        self.report({"INFO"}, f"選擇來源點 (物件: {self.sources[self.current_source_index].name})")
        
        # 添加 Modal 處理器
        context.window_manager.modal_handler_add(self)
        
        return {"RUNNING_MODAL"}
    
    def modal(self, context, event):
        """Modal 事件處理"""
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
        
        # 約束切換
        if event.type == "X" and event.value == "PRESS":
            return self.toggle_constraint_x(context)
        elif event.type == "Y" and event.value == "PRESS":
            return self.toggle_constraint_y(context)
        elif event.type == "Z" and event.value == "PRESS":
            return self.toggle_constraint_z(context)
        
        # 平面約束
        if event.type == "SHIFT" and event.value == "PRESS":
            return self.toggle_plane_constraint(context)
        
        # 參考系統切換
        if event.type == "O" and event.value == "PRESS":
            return self.toggle_reference_system(context)
        
        # 數字鍵切換來源物件
        if event.type in {"ONE", "TWO", "THREE", "FOUR", "FIVE"} and event.value == "PRESS":
            return self.switch_source_object(context, event)
        
        return {"RUNNING_MODAL"}
    
    def handle_mouse_move(self, context, event):
        """處理滑鼠移動 - 即時吸附解算"""
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
        
        # 尋找吸附點
        self.current_snap = self.snap_engine.find_snap_points_at_cursor(
            context, mouse_pos, view_vector
        )
        
        # 更新懸停物件
        if self.current_snap and self.current_snap.object:
            self.hover_object = self.current_snap.object
        else:
            self.hover_object = None
        
        # 更新預覽
        if self.preview_active and self.source_point and self.current_snap:
            self.update_preview_transform(context)
        
        # 強制重繪
        context.area.tag_redraw()
        
        return {"RUNNING_MODAL"}
    
    def handle_left_click(self, context, event):
        """處理左鍵點擊 - 確認點位選擇"""
        if self.current_snap:
            if self.state == self.ModalState.SELECT_SOURCE:
                self.source_point = self.current_snap
                self.state = self.ModalState.SELECT_TARGET
                self.report({"INFO"}, f"選擇目標點 (物件: {self.target.name})")
                
                # 設置臨時支點為來源點
                self.snap_engine.set_temp_pivot(self.source_point.position)
                
            elif self.state == self.ModalState.SELECT_TARGET:
                self.target_point = self.current_snap
                self.state = self.ModalState.EXECUTE_ALIGN
                self.report({"INFO"}, "按 Enter 執行對齊，或 ESC 取消")
        
        return {"RUNNING_MODAL"}
    
    def handle_right_click(self, context, event):
        """處理右鍵點擊 - 取消當前點"""
        if self.state == self.ModalState.SELECT_TARGET:
            self.source_point = None
            self.state = self.ModalState.SELECT_SOURCE
            self.report({"INFO"}, f"選擇來源點 (物件: {self.sources[self.current_source_index].name})")
        
        return {"RUNNING_MODAL"}
    
    def toggle_constraint_x(self, context):
        """切換 X 軸約束"""
        current = self.snap_engine.constraint_mode
        if current == "X":
            self.snap_engine.set_constraint_mode("NONE")
            self.report({"INFO"}, "約束: 無")
        else:
            self.snap_engine.set_constraint_mode("X")
            self.report({"INFO"}, "約束: X 軸")
        return {"RUNNING_MODAL"}
    
    def toggle_constraint_y(self, context):
        """切換 Y 軸約束"""
        current = self.snap_engine.constraint_mode
        if current == "Y":
            self.snap_engine.set_constraint_mode("NONE")
            self.report({"INFO"}, "約束: 無")
        else:
            self.snap_engine.set_constraint_mode("Y")
            self.report({"INFO"}, "約束: Y 軸")
        return {"RUNNING_MODAL"}
    
    def toggle_constraint_z(self, context):
        """切換 Z 軸約束"""
        current = self.snap_engine.constraint_mode
        if current == "Z":
            self.snap_engine.set_constraint_mode("NONE")
            self.report({"INFO"}, "約束: 無")
        else:
            self.snap_engine.set_constraint_mode("Z")
            self.report({"INFO"}, "約束: Z 軸")
        return {"RUNNING_MODAL"}
    
    def toggle_plane_constraint(self, context):
        """切換平面約束"""
        current = self.snap_engine.constraint_mode
        if current == "XY":
            self.snap_engine.set_constraint_mode("XZ")
            self.report({"INFO"}, "約束: XZ 平面")
        elif current == "XZ":
            self.snap_engine.set_constraint_mode("YZ")
            self.report({"INFO"}, "約束: YZ 平面")
        elif current == "YZ":
            self.snap_engine.set_constraint_mode("NONE")
            self.report({"INFO"}, "約束: 無")
        else:
            self.snap_engine.set_constraint_mode("XY")
            self.report({"INFO"}, "約束: XY 平面")
        return {"RUNNING_MODAL"}
    
    def toggle_reference_system(self, context):
        """切換參考系統"""
        current = self.snap_engine.reference_system
        if current == "WORLD":
            self.snap_engine.set_reference_system("LOCAL")
            self.report({"INFO"}, "參考系統: 本地")
        elif current == "LOCAL":
            self.snap_engine.set_reference_system("CUSTOM")
            self.report({"INFO"}, "參考系統: 自定義")
        else:
            self.snap_engine.set_reference_system("WORLD")
            self.report({"INFO"}, "參考系統: 世界")
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
                self.source_point = None
                self.target_point = None
                self.state = self.ModalState.SELECT_SOURCE
                self.report({"INFO"}, f"切換到來源物件: {self.sources[index].name}")
        
        return {"RUNNING_MODAL"}
    
    def update_preview_transform(self, context):
        """更新預覽變換 - 即時 ghost preview"""
        if self.source_point and self.target_point:
            source_obj = self.sources[self.current_source_index]
            
            # 計算變換矩陣
            from ..utils.bbox_utils import get_bbox_center_world
            source_pos = get_bbox_center_world(source_obj)
            target_pos = self.target_point.position
            
            # 計算平移
            translation = target_pos - source_pos
            
            # 計算旋轉（如果有法線）
            rotation = Matrix.Identity(3)
            if self.source_point.normal and self.target_point.normal:
                rotation = self.source_point.normal.rotation_difference(self.target_point.normal)
            
            # 構建變換矩陣
            transform = Matrix.Translation(translation)
            if rotation != Matrix.Identity(3):
                transform = transform @ rotation.to_4x4()
            
            self.transform_matrix = transform
            
            # 更新預覽
            interactive_preview.update_preview_transform(context, source_obj, transform)
    
    def execute_alignment(self, context):
        """執行對齊"""
        if self.source_point and self.target_point:
            source_obj = self.sources[self.current_source_index]
            
            # 應用變換
            if self.transform_matrix:
                source_obj.matrix_world = self.transform_matrix @ source_obj.matrix_world
            
            self.report({"INFO"}, f"交互式對齊完成: {source_obj.name}")
            
            return self.finish(context)
        else:
            self.report({"WARNING"}, "需要選擇來源點和目標點")
            return {"RUNNING_MODAL"}
    
    def draw_callback(self, context):
        """繪製回調 - 視覺化吸附信息"""
        import blf
        import bgl
        
        # 繪製當前狀態
        font_id = 0
        blf.position(font_id, 15, 50, 0)
        blf.size(font_id, 12, 72)
        
        state_descriptions = {
            self.ModalState.SELECT_SOURCE: f"選擇來源點 (物件: {self.sources[self.current_source_index].name})",
            self.ModalState.SELECT_TARGET: f"選擇目標點 (物件: {self.target.name})",
            self.ModalState.EXECUTE_ALIGN: "按 Enter 執行對齊"
        }
        
        blf.draw(font_id, state_descriptions.get(self.state, ""))
        
        # 繪製約束信息
        constraint_info = f"約束: {self.snap_engine.constraint_mode}"
        ref_info = f"參考: {self.snap_engine.reference_system}"
        
        blf.position(font_id, 15, 70, 0)
        blf.draw(font_id, constraint_info)
        blf.position(font_id, 15, 85, 0)
        blf.draw(font_id, ref_info)
        
        # 繪製吸附點
        if self.current_snap:
            self.draw_snap_point(context, self.current_snap.position, self.current_snap.snap_type)
        
        # 繪製已選擇的點
        if self.source_point:
            self.draw_selected_point(context, self.source_point.position, "S", (1, 0, 0))
        
        if self.target_point:
            self.draw_selected_point(context, self.target_point.position, "T", (0, 1, 0))
    
    def draw_snap_point(self, context, position, snap_type):
        """繪製吸附點"""
        import bgl
        
        # 根據類型設置顏色
        colors = {
            "VERTEX": (1, 0, 0),      # 紅色
            "EDGE": (0, 1, 0),        # 綠色
            "FACE": (0, 0, 1),        # 藍色
            "RAY": (1, 1, 0),         # 黃色
            "CENTER": (1, 0, 1),      # 紫色
            "CORNER": (0, 1, 1),      # 青色
        }
        
        color = colors.get(snap_type, (1, 1, 1))
        
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
        label_text = f"{label}: {position}"
        blf.position(font_id, 15, 100 + len(self.sources) * 15, 0)
        blf.size(font_id, 10, 72)
        blf.draw(font_id, label_text)
        
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
        self.report({"INFO"}, "交互式吸附已取消")
        return self.finish(context)


# 註冊類別
CLASSES = [
    SMARTALIGNPRO_OT_interactive_snap_modal,
]


def register():
    """註冊交互式吸附操作器"""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    """註銷交互式吸附操作器"""
    for cls in CLASSES:
        bpy.utils.unregister_class(cls)
