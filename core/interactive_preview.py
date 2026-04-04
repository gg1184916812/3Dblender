"""
Smart Align Pro - 互動預覽系統
實現真正的 CAD 級 hover preview transform
這是 CAD Transform 的靈魂功能
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from bpy_extras.view3d_utils import location_3d_to_region_2d
import gpu
from gpu_extras.batch import batch_for_shader


class InteractivePreviewSystem:
    """互動預覽系統核心類"""
    
    def __init__(self):
        self.active = False
        self.preview_objects = []
        self.original_states = {}
        self.transform_matrix = Matrix()
        self.hover_snap_point = None
        self.constraint_axis = None
        self.constraint_plane = None
        self.preview_handlers = []
        self.shader = None
        self.line_batch = None
        
    def activate(self, context, source_objects, target_object):
        """啟動互動預覽系統"""
        self.active = True
        self.source_objects = source_objects
        self.target_object = target_object
        
        # 保存原始狀態
        self.save_original_states()
        
        # 創建預覽物件
        self.create_preview_objects()
        
        # 添加 3D 視圖處理器
        self.add_preview_handlers(context)
        
        print("[SmartAlignPro] 互動預覽系統已啟動")
    
    def deactivate(self, context):
        """停用互動預覽系統"""
        self.active = False
        
        # 恢復原始狀態
        self.restore_original_states()
        
        # 清理預覽物件
        self.cleanup_preview_objects()
        
        # 移除處理器
        self.remove_preview_handlers(context)
        
        print("[SmartAlignPro] 互動預覽系統已停用")
    
    def save_original_states(self):
        """保存物件的原始狀態"""
        self.original_states.clear()
        
        for obj in self.source_objects:
            self.original_states[obj.name] = {
                'matrix_world': obj.matrix_world.copy(),
                'location': obj.location.copy(),
                'rotation': obj.rotation_euler.copy(),
                'scale': obj.scale.copy(),
                'visible': obj.visible_get(),
                'hide_viewport': obj.hide_viewport
            }
    
    def restore_original_states(self):
        """恢復物件的原始狀態"""
        for obj_name, state in self.original_states.items():
            obj = bpy.data.objects.get(obj_name)
            if obj:
                obj.matrix_world = state['matrix_world']
                obj.location = state['location']
                obj.rotation_euler = state['rotation']
                obj.scale = state['scale']
                obj.visible_set(state['visible'])
                obj.hide_viewport = state['hide_viewport']
    
    def create_preview_objects(self):
        """創建預覽物件（半透明複製品）"""
        self.preview_objects.clear()
        
        for obj in self.source_objects:
            # 創建預覽網格
            if obj.type == 'MESH':
                # 複製網格數據
                preview_mesh = obj.data.copy()
                preview_obj = bpy.data.objects.new(
                    f"Preview_{obj.name}", 
                    preview_mesh
                )
                
                # 設置預覽屬性
                preview_obj.matrix_world = obj.matrix_world.copy()
                preview_obj.visible_set(True)
                preview_obj.hide_viewport = False
                
                # 添加到場景
                bpy.context.collection.objects.link(preview_obj)
                
                # 創建預覽材質
                self.create_preview_material(preview_obj)
                
                self.preview_objects.append(preview_obj)
    
    def create_preview_material(self, obj):
        """創建預覽材質"""
        # 創建半透明藍色材質
        mat = bpy.data.materials.new(name="Preview_Material")
        mat.use_nodes = True
        mat.blend_method = 'BLEND'
        
        # 清除現有節點
        mat.node_tree.nodes.clear()
        
        # 創建主要節點
        output = mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
        principled = mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
        
        # 設置預覽顏色
        principled.inputs['Base Color'].default_value = (0.2, 0.6, 1.0, 1.0)
        principled.inputs['Alpha'].default_value = 0.6
        principled.inputs['Roughness'].default_value = 0.3
        principled.inputs['Metallic'].default_value = 0.1
        principled.inputs['Transmission'].default_value = 0.2
        
        # 連接節點
        mat.node_tree.links.new(principled.outputs['BSDF'], output.inputs['Surface'])
        
        # 應用材質
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
    
    def cleanup_preview_objects(self):
        """清理預覽物件"""
        for obj in self.preview_objects:
            try:
                # 從場景中移除
                bpy.context.collection.objects.unlink(obj)
                # 刪除物件
                bpy.data.objects.remove(obj)
            except:
                pass
        self.preview_objects.clear()
    
    def update_preview_transform(self, context, from_point, to_point, constraint_type=None):
        """更新預覽變換"""
        if not self.active or not self.preview_objects:
            return
        
        # 計算變換矩陣
        transform_matrix = self.calculate_transform_matrix(
            from_point, to_point, constraint_type
        )
        
        # 應用到預覽物件
        for i, preview_obj in enumerate(self.preview_objects):
            if i < len(self.source_objects):
                source_obj = self.source_objects[i]
                # 計算相對變換
                relative_transform = transform_matrix @ self.original_states[source_obj.name]['matrix_world']
                preview_obj.matrix_world = relative_transform
        
        # 更新約束可視化
        self.update_constraint_visualization(context, from_point, to_point, constraint_type)
    
    def calculate_transform_matrix(self, from_point, to_point, constraint_type):
        """計算變換矩陣"""
        if constraint_type == 'AXIS':
            # 軸向約束：只沿指定軸移動
            if self.constraint_axis:
                axis_vector = self.get_axis_vector(self.constraint_axis)
                direction = to_point - from_point
                projection = direction.dot(axis_vector) * axis_vector
                translation = Matrix.Translation(projection)
            else:
                translation = Matrix.Translation(to_point - from_point)
        
        elif constraint_type == 'PLANE':
            # 平面約束：在指定平面內移動
            if self.constraint_plane:
                plane_point = self.constraint_plane['point']
                plane_normal = self.constraint_plane['normal']
                
                # 計算在平面上的投影
                direction = to_point - from_point
                projected = from_point + direction - direction.dot(plane_normal) * plane_normal
                translation = Matrix.Translation(projected - from_point)
            else:
                translation = Matrix.Translation(to_point - from_point)
        
        elif constraint_type == 'ROTATION':
            # 旋轉約束：計算旋轉矩陣
            return self.calculate_rotation_matrix(from_point, to_point)
        
        else:
            # 自由變換
            translation = Matrix.Translation(to_point - from_point)
        
        return translation
    
    def calculate_rotation_matrix(self, from_point, to_point):
        """計算旋轉矩陣（用於三點對齊）"""
        # 這裡需要實現更複雜的旋轉求解
        # 目前先返回簡單的平移
        return Matrix.Translation(to_point - from_point)
    
    def get_axis_vector(self, axis):
        """獲取軸向量"""
        axis_vectors = {
            'X': Vector((1, 0, 0)),
            'Y': Vector((0, 1, 0)),
            'Z': Vector((0, 0, 1)),
            '-X': Vector((-1, 0, 0)),
            '-Y': Vector((0, -1, 0)),
            '-Z': Vector((0, 0, -1))
        }
        return axis_vectors.get(axis, Vector((1, 0, 0)))
    
    def update_constraint_visualization(self, context, from_point, to_point, constraint_type):
        """更新約束可視化"""
        # 這裡可以添加約束線、平面等可視化元素
        # 目前先跳過複雜的可視化
        pass
    
    def add_preview_handlers(self, context):
        """添加預覽處理器"""
        self.remove_preview_handlers(context)

        handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_preview_overlay,
            (),
            'WINDOW',
            'POST_PIXEL'
        )
        self.preview_handlers.append(handler)
        self.tag_redraw_all()
    
    def remove_preview_handlers(self, context):
        """移除預覽處理器"""
        for handler in self.preview_handlers:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
            except Exception:
                pass
        self.preview_handlers.clear()
        self.tag_redraw_all()
    
    def tag_redraw_all(self):
        """標記所有 3D 視圖重新繪製"""
        wm = getattr(bpy.context, "window_manager", None)
        if wm is None:
            return
        for window in wm.windows:
            screen = getattr(window, "screen", None)
            if screen is None:
                continue
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    
    def draw_preview_overlay(self):
        """繪製預覽覆蓋層"""
        if not self.active:
            return
        
        context = bpy.context
        if context is None:
            return
        
        # 繪製預覽信息
        import blf
        font_id = 0
        blf.size(font_id, 14)
        blf.color(font_id, 0.2, 0.8, 1.0, 1.0)
        
        # 顯示預覽狀態
        blf.position(font_id, 10, 50, 0)
        blf.draw(font_id, "互動預覽模式")
        
        if self.hover_snap_point:
            blf.position(font_id, 10, 70, 0)
            blf.draw(font_id, f"吸附點: {self.hover_snap_point.snap_type}")
        
        if self.constraint_axis:
            blf.position(font_id, 10, 90, 0)
            blf.draw(font_id, f"約束軸: {self.constraint_axis}")
    
    def apply_transform(self):
        """應用預覽變換到原始物件"""
        if not self.active or not self.preview_objects:
            return
        
        for i, preview_obj in enumerate(self.preview_objects):
            if i < len(self.source_objects):
                source_obj = self.source_objects[i]
                # 將預覽變換應用到原始物件
                source_obj.matrix_world = preview_obj.matrix_world.copy()
        
        print("[SmartAlignPro] 預覽變換已應用")
    
    def set_constraint_axis(self, axis):
        """設置約束軸"""
        self.constraint_axis = axis
    
    def set_constraint_plane(self, plane_point, plane_normal):
        """設置約束平面"""
        self.constraint_plane = {
            'point': plane_point,
            'normal': plane_normal.normalized()
        }
    
    def clear_constraints(self):
        """清除所有約束"""
        self.constraint_axis = None
        self.constraint_plane = None


# 全局互動預覽系統實例
interactive_preview = InteractivePreviewSystem()


class HoverTransformSolver:
    """即時變換求解器"""
    
    def __init__(self):
        self.from_point = None
        self.to_point = None
        self.constraint_type = 'FREE'
        self.constraint_axis = None
        self.constraint_plane = None
        self.transform_type = 'TRANSLATION'  # TRANSLATION, ROTATION, SCALE
        
    def solve_transform(self, from_point, to_point, constraint_type='FREE'):
        """求解變換矩陣"""
        self.from_point = from_point
        self.to_point = to_point
        self.constraint_type = constraint_type
        
        if self.transform_type == 'TRANSLATION':
            return self.solve_translation()
        elif self.transform_type == 'ROTATION':
            return self.solve_rotation()
        elif self.transform_type == 'SCALE':
            return self.solve_scale()
        else:
            return Matrix.Identity(4)
    
    def solve_translation(self):
        """求解平移變換"""
        if self.constraint_type == 'AXIS' and self.constraint_axis:
            # 軸向約束平移
            axis_vector = self.get_axis_vector(self.constraint_axis)
            direction = self.to_point - self.from_point
            projection = direction.dot(axis_vector) * axis_vector
            return Matrix.Translation(projection)
        
        elif self.constraint_type == 'PLANE' and self.constraint_plane:
            # 平面約束平移
            plane_point = self.constraint_plane['point']
            plane_normal = self.constraint_plane['normal']
            
            direction = self.to_point - self.from_point
            # 計算在平面上的投影
            projected_direction = direction - direction.dot(plane_normal) * plane_normal
            return Matrix.Translation(projected_direction)
        
        else:
            # 自由平移
            return Matrix.Translation(self.to_point - self.from_point)
    
    def solve_rotation(self):
        """求解旋轉變換"""
        # 實現三點對齊的旋轉求解
        if self.from_point and self.to_point:
            # 這裡需要更複雜的旋轉計算
            # 目前先返回單位矩陣
            return Matrix.Identity(4)
        
        return Matrix.Identity(4)
    
    def solve_scale(self):
        """求解縮放變換"""
        # 實現縮放求解
        return Matrix.Identity(4)
    
    def get_axis_vector(self, axis):
        """獲取軸向量"""
        axis_vectors = {
            'X': Vector((1, 0, 0)),
            'Y': Vector((0, 1, 0)),
            'Z': Vector((0, 0, 1)),
            '-X': Vector((-1, 0, 0)),
            '-Y': Vector((0, -1, 0)),
            '-Z': Vector((0, 0, -1))
        }
        return axis_vectors.get(axis, Vector((1, 0, 0)))
    
    def set_constraint_axis(self, axis):
        """設置約束軸"""
        self.constraint_axis = axis
        self.constraint_type = 'AXIS'
    
    def set_constraint_plane(self, plane_point, plane_normal):
        """設置約束平面"""
        self.constraint_plane = {
            'point': plane_point,
            'normal': plane_normal.normalized()
        }
        self.constraint_type = 'PLANE'
    
    def clear_constraints(self):
        """清除約束"""
        self.constraint_axis = None
        self.constraint_plane = None
        self.constraint_type = 'FREE'


# 全局變換求解器實例
hover_solver = HoverTransformSolver()
