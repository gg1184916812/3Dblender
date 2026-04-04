"""
Smart Align Pro - Realtime Preview Engine
實現 CAD Transform 級別的即時預覽系統
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix, geometry
from typing import Optional, Dict, Any, List, Tuple
import time
import threading


class PreviewObject:
    """預覽物件類別"""
    def __init__(self, original_object: bpy.types.Object):
        self.original_object = original_object
        self.preview_matrix = Matrix.Identity(4)
        self.is_visible = True
        self.preview_color = (0.2, 0.6, 1.0, 0.3)
        self.wireframe_color = (0.0, 1.0, 1.0, 0.8)
        
        # 預覽數據
        self.vertices = []
        self.edges = []
        self.faces = []
        self.batches = {}
        
        # 初始化預覽數據
        self._initialize_preview_data()
    
    def _initialize_preview_data(self):
        """初始化預覽數據"""
        if self.original_object.type == "MESH":
            self._initialize_mesh_preview()
        elif self.original_object.type == "CURVE":
            self._initialize_curve_preview()
        elif self.original_object.type == "EMPTY":
            self._initialize_empty_preview()
    
    def _initialize_mesh_preview(self):
        """初始化網格預覽數據"""
        mesh = self.original_object.data
        
        # 獲取頂點（應用變換）
        self.vertices = []
        for vert in mesh.vertices:
            world_pos = self.original_object.matrix_world @ vert.co
            self.vertices.append(world_pos)
        
        # 獲取邊緣
        self.edges = []
        for edge in mesh.edges:
            self.edges.append((edge.vertices[0], edge.vertices[1]))
        
        # 獲取面
        self.faces = []
        for poly in mesh.polygons:
            if len(poly.vertices) == 3:
                self.faces.append(tuple(poly.vertices))
            elif len(poly.vertices) == 4:
                # 將四邊形分成兩個三角形
                v = poly.vertices
                self.faces.append((v[0], v[1], v[2]))
                self.faces.append((v[0], v[2], v[3]))
    
    def _initialize_curve_preview(self):
        """初始化曲線預覽數據"""
        curve = self.original_object.data
        self.vertices = []
        
        if curve.splines:
            for spline in curve.splines:
                if spline.type == 'BEZIER':
                    for point in spline.bezier_points:
                        world_pos = self.original_object.matrix_world @ point.co
                        self.vertices.append(world_pos)
                elif spline.type == 'POLY':
                    for point in spline.points:
                        world_pos = self.original_object.matrix_world @ point.co
                        self.vertices.append(world_pos)
        
        # 創建線段
        self.edges = []
        for i in range(len(self.vertices) - 1):
            self.edges.append((i, i + 1))
    
    def _initialize_empty_preview(self):
        """初始化空物件預覽數據"""
        center = self.original_object.matrix_world @ Vector((0, 0, 0))
        size = self.original_object.empty_display_size if self.original_object.empty_display_size > 0 else 1.0
        
        if self.original_object.empty_display_type == 'PLAIN_AXES':
            # 創建軸線
            self.vertices = [center]
            for axis in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
                end_point = center + Vector(axis) * size
                self.vertices.append(end_point)
                self.edges.append((0, len(self.vertices) - 1))
        
        elif self.original_object.empty_display_type == 'CUBE':
            # 創建立方體邊框
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
            
            self.vertices = corners
            
            # 立方體邊
            cube_edges = [
                (0, 1), (1, 2), (2, 3), (3, 0),  # 底面
                (4, 5), (5, 6), (6, 7), (7, 4),  # 頂面
                (0, 4), (1, 5), (2, 6), (3, 7),  # 垂直邊
            ]
            self.edges = cube_edges
    
    def update_preview_matrix(self, matrix: Matrix):
        """更新預覽變換矩陣"""
        self.preview_matrix = matrix
        self._update_preview_geometry()
    
    def _update_preview_geometry(self):
        """更新預覽幾何體"""
        if not self.original_object.type == "MESH":
            return
        
        # 重新計算變換後的頂點
        self.vertices = []
        mesh = self.original_object.data
        
        for vert in mesh.vertices:
            original_pos = self.original_object.matrix_world @ vert.co
            transformed_pos = self.preview_matrix @ self.original_object.matrix_world.inverted() @ original_pos
            self.vertices.append(transformed_pos)
        
        # 清除舊的批次
        self.batches.clear()
    
    def create_batches(self, shader):
        """創建渲染批次"""
        if not self.vertices:
            return
        
        # 實心批次
        if self.faces and len(self.faces) > 0:
            tri_coords = []
            for face in self.faces:
                if (face[0] < len(self.vertices) and 
                    face[1] < len(self.vertices) and 
                    face[2] < len(self.vertices)):
                    tri_coords.extend([
                        self.vertices[face[0]], 
                        self.vertices[face[1]], 
                        self.vertices[face[2]]
                    ])
            
            if tri_coords:
                self.batches['solid'] = batch_for_shader(
                    shader, 'TRIS', {"pos": tri_coords}
                )
        
        # 線框批次
        if self.edges and len(self.edges) > 0:
            edge_coords = []
            for edge in self.edges:
                if (edge[0] < len(self.vertices) and 
                    edge[1] < len(self.vertices)):
                    edge_coords.extend([
                        self.vertices[edge[0]], 
                        self.vertices[edge[1]]
                    ])
            
            if edge_coords:
                self.batches['wireframe'] = batch_for_shader(
                    shader, 'LINES', {"pos": edge_coords}
                )
        
        # 點批次
        if self.vertices:
            self.batches['points'] = batch_for_shader(
                shader, 'POINTS', {"pos": self.vertices}
            )
    
    def draw(self, shader):
        """繪製預覽物件"""
        if not self.is_visible or not self.vertices:
            return
        
        # 確保批次已創建
        if not self.batches:
            self.create_batches(shader)
        
        # 繪製實心預覽
        if 'solid' in self.batches:
            shader.bind()
            shader.uniform_float("color", self.preview_color)
            self.batches['solid'].draw(shader)
        
        # 繪製線框
        if 'wireframe' in self.batches:
            shader.bind()
            shader.uniform_float("color", self.wireframe_color)
            self.batches['wireframe'].draw(shader)
        
        # 繪製點
        if 'points' in self.batches:
            shader.bind()
            shader.uniform_float("color", self.wireframe_color)
            gpu.state.point_size_set(5.0)
            self.batches['points'].draw(shader)
            gpu.state.point_size_set(1.0)


class AlignmentPreview:
    """對齊預覽類別"""
    def __init__(self):
        self.source_points = []
        self.target_points = []
        self.alignment_lines = []
        self.transform_matrix = Matrix.Identity(4)
        self.is_active = False
        
        # 預覽設置
        self.show_source_points = True
        self.show_target_points = True
        self.show_alignment_lines = True
        self.show_transform_preview = True
        
        # 顏色設置
        self.source_point_color = (1.0, 0.2, 0.2, 1.0)  # 紅色
        self.target_point_color = (0.2, 1.0, 0.2, 1.0)  # 綠色
        self.alignment_line_color = (1.0, 1.0, 0.2, 0.8)  # 黃色
        self.preview_object_color = (0.2, 0.6, 1.0, 0.3)  # 半透明藍色
    
    def update_alignment_data(self, source_points: List[Vector], 
                           target_points: List[Vector],
                           transform_matrix: Matrix = None):
        """更新對齊數據"""
        self.source_points = source_points
        self.target_points = target_points
        
        if transform_matrix:
            self.transform_matrix = transform_matrix
        
        # 計算對齊線
        self._calculate_alignment_lines()
        
        self.is_active = True
    
    def _calculate_alignment_lines(self):
        """計算對齊線"""
        self.alignment_lines.clear()
        
        # 創建對應點之間的連線
        min_points = min(len(self.source_points), len(self.target_points))
        
        for i in range(min_points):
            self.alignment_lines.append((self.source_points[i], self.target_points[i]))
    
    def draw(self, shader, context=None):
        """繪製對齊預覽"""
        if not self.is_active:
            return
        
        # 繪製來源點
        if self.show_source_points and self.source_points:
            points_batch = batch_for_shader(shader, 'POINTS', {"pos": self.source_points})
            shader.bind()
            shader.uniform_float("color", self.source_point_color)
            gpu.state.point_size_set(8.0)
            points_batch.draw(shader)
            gpu.state.point_size_set(1.0)
        
        # 繪製目標點
        if self.show_target_points and self.target_points:
            points_batch = batch_for_shader(shader, 'POINTS', {"pos": self.target_points})
            shader.bind()
            shader.uniform_float("color", self.target_point_color)
            gpu.state.point_size_set(8.0)
            points_batch.draw(shader)
            gpu.state.point_size_set(1.0)
        
        # 繪製對齊線
        if self.show_alignment_lines and self.alignment_lines:
            line_coords = []
            for start, end in self.alignment_lines:
                line_coords.extend([start, end])
            
            if line_coords:
                lines_batch = batch_for_shader(shader, 'LINES', {"pos": line_coords})
                shader.bind()
                shader.uniform_float("color", self.alignment_line_color)
                lines_batch.draw(shader)


class RealtimePreviewEngine:
    """即時預覽引擎 - CAD Transform 級別的即時預覽系統"""
    
    def __init__(self):
        self.is_active = False
        self.preview_objects: Dict[str, PreviewObject] = {}
        self.alignment_preview = AlignmentPreview()
        
        # 渲染設置
        self.shader = None
        self.draw_handlers = []
        
        # 性能設置
        self.update_rate = 60  # FPS
        self.last_update_time = 0
        self.enable_multithreading = False
        
        # 初始化著色器
        self._initialize_shader()
    
    def _initialize_shader(self):
        """初始化著色器"""
        try:
            self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        except:
            self.shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    
    def activate(self, context):
        """啟動即時預覽引擎"""
        if self.is_active:
            return
        
        self.is_active = True
        
        # 添加繪製處理器
        handler = context.space_data.draw_handler_add(
            self.draw_preview, (), 'WINDOW', 'POST_VIEW'
        )
        self.draw_handlers.append(handler)
    
    def deactivate(self, context):
        """停用即時預覽引擎"""
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
        
        # 清除預覽物件
        self.clear_all_previews()
    
    def add_preview_object(self, obj_name: str, original_object: bpy.types.Object):
        """添加預覽物件"""
        if obj_name not in self.preview_objects:
            self.preview_objects[obj_name] = PreviewObject(original_object)
    
    def remove_preview_object(self, obj_name: str):
        """移除預覽物件"""
        if obj_name in self.preview_objects:
            del self.preview_objects[obj_name]
    
    def update_object_preview(self, obj_name: str, transform_matrix: Matrix):
        """更新物件預覽"""
        if obj_name in self.preview_objects:
            self.preview_objects[obj_name].update_preview_matrix(transform_matrix)
    
    def update_alignment_preview(self, source_points: List[Vector], 
                             target_points: List[Vector],
                             transform_matrix: Matrix = None):
        """更新對齊預覽"""
        self.alignment_preview.update_alignment_data(
            source_points, target_points, transform_matrix
        )
    
    def clear_all_previews(self):
        """清除所有預覽"""
        self.preview_objects.clear()
        self.alignment_preview = AlignmentPreview()
    
    def draw_preview(self):
        """繪製預覽主函數"""
        if not self.is_active or not self.shader:
            return
        
        # 檢查更新率限制
        current_time = time.time()
        if current_time - self.last_update_time < 1.0 / self.update_rate:
            return
        
        self.last_update_time = current_time
        
        # 設置渲染狀態
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set('ALPHA')
        
        # 繪製所有預覽物件
        for preview_obj in self.preview_objects.values():
            if preview_obj.is_visible:
                preview_obj.draw(self.shader)
        
        # 繪製對齊預覽
        self.alignment_preview.draw(self.shader)
        
        # 恢復渲染狀態
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(False)
        gpu.state.blend_set('NONE')
    
    def set_preview_settings(self, show_objects=True, show_alignment=True, 
                          show_lines=True, show_points=True):
        """設置預覽選項"""
        for preview_obj in self.preview_objects.values():
            preview_obj.is_visible = show_objects
        
        self.alignment_preview.show_transform_preview = show_alignment
        self.alignment_preview.show_alignment_lines = show_lines
        self.alignment_preview.show_source_points = show_points
        self.alignment_preview.show_target_points = show_points
    
    def set_preview_colors(self, object_color=None, wireframe_color=None,
                         source_color=None, target_color=None, line_color=None):
        """設置預覽顏色"""
        if object_color:
            for preview_obj in self.preview_objects.values():
                preview_obj.preview_color = object_color
        
        if wireframe_color:
            for preview_obj in self.preview_objects.values():
                preview_obj.wireframe_color = wireframe_color
        
        if source_color:
            self.alignment_preview.source_point_color = source_color
        
        if target_color:
            self.alignment_preview.target_point_color = target_color
        
        if line_color:
            self.alignment_preview.alignment_line_color = line_color
    
    def get_preview_status(self) -> Dict[str, Any]:
        """獲取預覽狀態"""
        return {
            "is_active": self.is_active,
            "object_count": len(self.preview_objects),
            "alignment_active": self.alignment_preview.is_active,
            "update_rate": self.update_rate,
            "last_update": self.last_update_time
        }
    
    def set_update_rate(self, fps: int):
        """設置更新率"""
        self.update_rate = max(1, min(120, fps))
    
    def enable_performance_mode(self, enable: bool):
        """啟用性能模式"""
        if enable:
            self.set_update_rate(30)  # 降低更新率
            # 可以添加其他性能優化
        else:
            self.set_update_rate(60)  # 恢復正常更新率


# 全域即時預覽引擎實例
realtime_preview_engine = RealtimePreviewEngine()


def get_realtime_preview_engine() -> RealtimePreviewEngine:
    """獲取即時預覽引擎實例"""
    return realtime_preview_engine


def activate_realtime_preview(context):
    """啟動即時預覽 - 供外部調用"""
    realtime_preview_engine.activate(context)


def deactivate_realtime_preview(context):
    """停用即時預覽 - 供外部調用"""
    realtime_preview_engine.deactivate(context)


def update_object_preview(obj_name: str, transform_matrix: Matrix):
    """更新物件預覽 - 供外部調用"""
    realtime_preview_engine.update_object_preview(obj_name, transform_matrix)


def update_alignment_preview(source_points: List[Vector], 
                         target_points: List[Vector],
                         transform_matrix: Matrix = None):
    """更新對齊預覽 - 供外部調用"""
    realtime_preview_engine.update_alignment_preview(
        source_points, target_points, transform_matrix
    )


def clear_all_previews():
    """清除所有預覽 - 供外部調用"""
    realtime_preview_engine.clear_all_previews()


def set_preview_settings(show_objects=True, show_alignment=True, 
                      show_lines=True, show_points=True):
    """設置預覽選項 - 供外部調用"""
    realtime_preview_engine.set_preview_settings(
        show_objects, show_alignment, show_lines, show_points
    )


def set_preview_colors(object_color=None, wireframe_color=None,
                     source_color=None, target_color=None, line_color=None):
    """設置預覽顏色 - 供外部調用"""
    realtime_preview_engine.set_preview_colors(
        object_color, wireframe_color, source_color, target_color, line_color
    )
