"""
Smart Align Pro - Hover Preview System
實現 CAD Transform 級別的即時 Ghost Transform Preview
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
from .interactive_preview import interactive_preview


class HoverPreviewSystem:
    """懸停預覽系統 - CAD Transform 級別的即時預覽"""
    
    def __init__(self):
        self.is_active = False
        self.preview_objects = []
        self.transform_matrix = None
        self.source_object = None
        self.shader = None
        self.batches = {}
        self.draw_handlers = []
        
        # 預覽設置
        self.preview_color = (0.2, 0.6, 1.0, 0.3)  # 半透明藍色
        self.wireframe_color = (0.0, 1.0, 1.0, 0.8)  # 青色線框
        self.show_wireframe = True
        self.show_solid = True
        
        # 初始化著色器
        self._init_shader()
    
    def _init_shader(self):
        """初始化著色器"""
        try:
            # 嘗試使用 3D 統一著色器
            self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        except:
            # 如果失敗，使用基本著色器
            self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    
    def activate(self, context):
        """啟動懸停預覽系統"""
        if self.is_active:
            return
        
        self.is_active = True
        
        # 添加繪製處理器
        self.draw_handlers = []
        
        # 3D 視圖繪製處理器
        handler_3d = context.space_data.draw_handler_add(
            self.draw_3d_preview, (), 'WINDOW', 'POST_VIEW'
        )
        self.draw_handlers.append(handler_3d)
        
        # 2D 視圖繪製處理器（用於 UI 元素）
        handler_2d = context.space_data.draw_handler_add(
            self.draw_2d_overlay, (), 'WINDOW', 'POST_PIXEL'
        )
        self.draw_handlers.append(handler_2d)
    
    def deactivate(self, context):
        """停用懸停預覽系統"""
        if not self.is_active:
            return
        
        self.is_active = False
        
        # 移除繪製處理器
        for handler in self.draw_handlers:
            try:
                context.space_data.draw_handler_remove(handler, 'WINDOW')
            except:
                pass
        
        self.draw_handlers.clear()
        
        # 清理預覽物件
        self.clear_preview_objects()
    
    def update_hover_preview(self, context, source_obj, transform_matrix):
        """更新懸停預覽 - 即時 ghost transform"""
        if not self.is_active:
            self.activate(context)
        
        self.source_object = source_obj
        self.transform_matrix = transform_matrix
        
        # 更新預覽物件
        self._update_preview_objects(source_obj, transform_matrix)
    
    def _update_preview_objects(self, source_obj, transform_matrix):
        """更新預覽物件"""
        # 清除舊的預覽物件
        self.clear_preview_objects()
        
        if source_obj is None or transform_matrix is None:
            return
        
        # 創建新的預覽物件
        if source_obj.type == "MESH":
            self._create_mesh_preview(source_obj, transform_matrix)
        elif source_obj.type == "CURVE":
            self._create_curve_preview(source_obj, transform_matrix)
        elif source_obj.type == "EMPTY":
            self._create_empty_preview(source_obj, transform_matrix)
    
    def _create_mesh_preview(self, mesh_obj, transform_matrix):
        """創建網格預覽"""
        # 獲取網格數據
        mesh = mesh_obj.data
        vertices = []
        edges = []
        triangles = []
        
        # 應用變換矩陣到頂點
        for vert in mesh.vertices:
            world_pos = transform_matrix @ mesh_obj.matrix_world @ vert.co
            vertices.append(world_pos)
        
        # 獲取邊緣
        for edge in mesh.edges:
            edges.append((edge.vertices[0], edge.vertices[1]))
        
        # 獲取三角形（如果有多邊形）
        if mesh.polygons:
            for poly in mesh.polygons:
                if len(poly.vertices) == 3:
                    triangles.append(tuple(poly.vertices))
                elif len(poly.vertices) == 4:
                    # 將四邊形分成兩個三角形
                    v = poly.vertices
                    triangles.append((v[0], v[1], v[2]))
                    triangles.append((v[0], v[2], v[3]))
        
        # 創建批次
        if vertices and len(vertices) > 0:
            # 線框批次
            if edges and len(edges) > 0:
                edge_coords = []
                for edge in edges:
                    if edge[0] < len(vertices) and edge[1] < len(vertices):
                        edge_coords.extend([vertices[edge[0]], vertices[edge[1]]])
                
                if edge_coords:
                    self.batches['wireframe'] = batch_for_shader(
                        self.shader, 'LINES', {"pos": edge_coords}
                    )
            
            # 實心批次
            if triangles and len(triangles) > 0:
                tri_coords = []
                for tri in triangles:
                    if (tri[0] < len(vertices) and 
                        tri[1] < len(vertices) and 
                        tri[2] < len(vertices)):
                        tri_coords.extend([vertices[tri[0]], vertices[tri[1]], vertices[tri[2]]])
                
                if tri_coords:
                    self.batches['solid'] = batch_for_shader(
                        self.shader, 'TRIS', {"pos": tri_coords}
                    )
    
    def _create_curve_preview(self, curve_obj, transform_matrix):
        """創建曲線預覽"""
        # 簡化的曲線預覽
        curve = curve_obj.data
        points = []
        
        # 獲取曲線點
        if curve.splines:
            for spline in curve.splines:
                if spline.type == 'BEZIER':
                    for point in spline.bezier_points:
                        world_pos = transform_matrix @ curve_obj.matrix_world @ point.co
                        points.append(world_pos)
                elif spline.type == 'POLY':
                    for point in spline.points:
                        world_pos = transform_matrix @ curve_obj.matrix_world @ point.co
                        points.append(world_pos)
        
        # 創建線段批次
        if len(points) > 1:
            line_coords = []
            for i in range(len(points) - 1):
                line_coords.extend([points[i], points[i + 1]])
            
            self.batches['curve'] = batch_for_shader(
                self.shader, 'LINES', {"pos": line_coords}
            )
    
    def _create_empty_preview(self, empty_obj, transform_matrix):
        """創建空物件預覽"""
        # 空物件的簡單預覽（十字線）
        center = transform_matrix @ empty_obj.matrix_world @ Vector((0, 0, 0))
        
        # 創建十字線
        size = empty_obj.empty_display_size if empty_obj.empty_display_size > 0 else 1.0
        
        # 根據空物件類型創建不同的預覽
        if empty_obj.empty_display_type == 'PLAIN_AXES':
            # 簡單軸線
            axes_coords = []
            for axis in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
                start = center
                end = center + Vector(axis) * size
                axes_coords.extend([start, end])
            
            self.batches['empty'] = batch_for_shader(
                self.shader, 'LINES', {"pos": axes_coords}
            )
        
        elif empty_obj.empty_display_type == 'CUBE':
            # 立方體邊框
            size = size * 0.5
            corners = [
                center + Vector((-size, -size, -size)),
                center + Vector((size, -size, -size)),
                center + Vector((size, size, -size)),
                center + Vector((-size, size, -size)),
                center + Vector((-size, -size, size)),
                center + Vector((size, -size, size)),
                center + Vector((size, size, size)),
                center + Vector((-size, size, size)),
            ]
            
            # 立方體邊
            cube_edges = [
                (0, 1), (1, 2), (2, 3), (3, 0),  # 底面
                (4, 5), (5, 6), (6, 7), (7, 4),  # 頂面
                (0, 4), (1, 5), (2, 6), (3, 7),  # 垂直邊
            ]
            
            edge_coords = []
            for edge in cube_edges:
                edge_coords.extend([corners[edge[0]], corners[edge[1]]])
            
            self.batches['empty'] = batch_for_shader(
                self.shader, 'LINES', {"pos": edge_coords}
            )
    
    def clear_preview_objects(self):
        """清除預覽物件"""
        self.batches.clear()
        self.preview_objects.clear()
    
    def draw_3d_preview(self):
        """繪製 3D 預覽"""
        if not self.is_active or not self.shader:
            return
        
        # 啟用深度測試
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        
        # 繪製實心預覽
        if self.show_solid and 'solid' in self.batches:
            self.shader.bind()
            self.shader.uniform_float("color", self.preview_color)
            self.batches['solid'].draw(self.shader)
        
        # 繪製線框預覽
        if self.show_wireframe and 'wireframe' in self.batches:
            self.shader.bind()
            self.shader.uniform_float("color", self.wireframe_color)
            self.batches['wireframe'].draw(self.shader)
        
        # 繪製曲線預覽
        if 'curve' in self.batches:
            self.shader.bind()
            self.shader.uniform_float("color", self.wireframe_color)
            self.batches['curve'].draw(self.shader)
        
        # 繪製空物件預覽
        if 'empty' in self.batches:
            self.shader.bind()
            self.shader.uniform_float("color", self.wireframe_color)
            self.batches['empty'].draw(self.shader)
        
        # 恢復狀態
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(False)
    
    def draw_2d_overlay(self):
        """繪製 2D 覆蓋層"""
        if not self.is_active:
            return
        
        import blf
        
        # 繪製預覽信息
        font_id = 0
        text = "Hover Preview Active"
        
        if self.source_object:
            text += f" - {self.source_object.name}"
        
        # 設置字體
        blf.size(font_id, 12, 72)
        blf.position(font_id, 15, 15, 0)
        blf.color(font_id, 1.0, 1.0, 1.0, 0.8)
        
        # 繪製文字
        blf.draw(font_id, text)
    
    def set_preview_color(self, color):
        """設置預覽顏色"""
        self.preview_color = color
    
    def set_wireframe_color(self, color):
        """設置線框顏色"""
        self.wireframe_color = color
    
    def set_show_wireframe(self, show):
        """設置是否顯示線框"""
        self.show_wireframe = show
    
    def set_show_solid(self, show):
        """設置是否顯示實心"""
        self.show_solid = show
    
    def is_preview_active(self):
        """檢查預覽是否活躍"""
        return self.is_active and self.source_object is not None


# 全域懸停預覽系統實例
hover_preview_system = HoverPreviewSystem()


def update_hover_preview(context, source_obj, transform_matrix):
    """更新懸停預覽 - 供外部調用"""
    hover_preview_system.update_hover_preview(context, source_obj, transform_matrix)


def activate_hover_preview(context):
    """啟動懸停預覽 - 供外部調用"""
    hover_preview_system.activate(context)


def deactivate_hover_preview(context):
    """停用懸停預覽 - 供外部調用"""
    hover_preview_system.deactivate(context)


def clear_hover_preview():
    """清除懸停預覽 - 供外部調用"""
    hover_preview_system.clear_preview_objects()


def set_hover_preview_settings(color=None, wireframe_color=None, 
                           show_wireframe=None, show_solid=None):
    """設置懸停預覽參數 - 供外部調用"""
    if color is not None:
        hover_preview_system.set_preview_color(color)
    if wireframe_color is not None:
        hover_preview_system.set_wireframe_color(wireframe_color)
    if show_wireframe is not None:
        hover_preview_system.set_show_wireframe(show_wireframe)
    if show_solid is not None:
        hover_preview_system.set_show_solid(show_solid)
