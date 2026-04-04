"""
Smart Align Pro - 預覽繪製系統
超越 CAD Transform 的視覺反饋系統
"""

import bpy
import bgl
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
from bpy.types import SpaceView3D


class PreviewDrawHandler:
    """預覽繪製處理器 - CAD 等級視覺反饋"""
    
    def __init__(self):
        self.handlers = []
        self.active = False
        self.draw_data = {}
        
        # 預覽元素
        self.ghost_objects = []
        self.alignment_lines = []
        self.snap_points = []
        self.constraint_lines = []
        
        # 著色器
        self.line_shader = None
        self.point_shader = None
        self.text_shader = None
        
        # 顏色設置
        self.colors = {
            'ghost': (0.5, 0.8, 1.0, 0.3),
            'alignment': (0.2, 1.0, 0.5, 0.8),
            'snap': (1.0, 0.8, 0.2, 1.0),
            'constraint': (1.0, 0.2, 0.2, 0.6),
            'text': (1.0, 1.0, 1.0, 1.0)
        }

    def register_handlers(self):
        """註冊繪製處理器"""
        if self.active:
            return
        
        # 為每個 3D 視圖註冊處理器
        for window in bpy.context.window_manager.windows:
            for screen in window.screen.areas:
                if screen.type == 'VIEW_3D':
                    for region in screen.regions:
                        if region.type == 'WINDOW':
                            handler = SpaceView3D.draw_handler_add(
                                self.draw_callback_3d,
                                (),
                                'WINDOW',
                                'POST_VIEW'
                            )
                            self.handlers.append(handler)
        
        self.active = True
        print("[PreviewDrawHandler] 預覽繪製處理器已註冊")

    def unregister_handlers(self):
        """註銷繪製處理器"""
        for handler in self.handlers:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handler, 'WINDOW')
            except:
                pass
        
        self.handlers.clear()
        self.active = False
        print("[PreviewDrawHandler] 預覽繪製處理器已註銷")

    def draw_callback_3d(self):
        """3D 視圖繪製回調"""
        if not self.active:
            return
        
        context = bpy.context
        if context is None:
            return
        
        # 設置 OpenGL 狀態
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glEnable(bgl.GL_LINE_SMOOTH)
        bgl.glDisable(bgl.GL_DEPTH_TEST)
        
        # 繪製所有預覽元素
        self._draw_ghost_objects(context)
        self._draw_alignment_lines(context)
        self._draw_snap_points(context)
        self._draw_constraint_lines(context)
        self._draw_hud_text(context)
        
        # 恢復 OpenGL 狀態
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glDisable(bgl.GL_LINE_SMOOTH)

    def _draw_ghost_objects(self, context):
        """繪製幽靈物件"""
        for ghost_data in self.ghost_objects:
            if 'object' in ghost_data:
                obj = ghost_data['object']
                if obj and obj.type == 'MESH':
                    self._draw_mesh_wireframe(context, obj, self.colors['ghost'])

    def _draw_mesh_wireframe(self, context, obj, color):
        """繪製網格線框"""
        if not obj.data:
            return
        
        # 獲取網格邊緣
        edges = []
        vertices = []
        
        for edge in obj.data.edges:
            if edge.use_loose:
                v1 = obj.matrix_world @ obj.data.vertices[edge.vertices[0]].co
                v2 = obj.matrix_world @ obj.data.vertices[edge.vertices[1]].co
                vertices.extend([v1, v2])
        
        if vertices:
            # 創建著色器
            shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
            shader.bind()
            shader.uniform_float("color", color)
            
            # 創建批次
            batch = batch_for_shader(shader, 'LINES', {"pos": vertices})
            batch.draw(shader)

    def _draw_alignment_lines(self, context):
        """繪製對齊線"""
        for line_data in self.alignment_lines:
            start = line_data.get('start', Vector())
            end = line_data.get('end', Vector())
            color = line_data.get('color', self.colors['alignment'])
            width = line_data.get('width', 2)
            
            self._draw_line_3d(context, start, end, color, width)

    def _draw_line_3d(self, context, start, end, color, width=1):
        """繪製 3D 線條"""
        # 創建著色器
        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        shader.bind()
        shader.uniform_float("color", color)
        
        # 設置線寬
        bgl.glLineWidth(width)
        
        # 創建批次
        batch = batch_for_shader(shader, 'LINES', {"pos": [start, end]})
        batch.draw(shader)

    def _draw_snap_points(self, context):
        """繪製吸附點"""
        for point_data in self.snap_points:
            position = point_data.get('position', Vector())
            color = point_data.get('color', self.colors['snap'])
            size = point_data.get('size', 10)
            snap_type = point_data.get('type', 'POINT')
            
            if snap_type == 'VERTEX':
                self._draw_vertex_point(context, position, color, size)
            elif snap_type == 'EDGE':
                self._draw_edge_point(context, position, color, size)
            elif snap_type == 'FACE':
                self._draw_face_point(context, position, color, size)

    def _draw_vertex_point(self, context, position, color, size):
        """繪製頂點點"""
        # 繪製小立方體表示頂點
        self._draw_cube_marker(context, position, color, size * 0.01)

    def _draw_edge_point(self, context, position, color, size):
        """繪製邊緣點"""
        # 繪製圓球表示邊緣點
        self._draw_sphere_marker(context, position, color, size * 0.01)

    def _draw_face_point(self, context, position, color, size):
        """繪製面點"""
        # 繪製方形表示面點
        self._draw_square_marker(context, position, color, size * 0.01)

    def _draw_cube_marker(self, context, position, color, size):
        """繪製立方體標記"""
        # 立方體頂點
        vertices = [
            position + Vector((-size, -size, -size)),
            position + Vector((size, -size, -size)),
            position + Vector((size, size, -size)),
            position + Vector((-size, size, -size)),
            position + Vector((-size, -size, size)),
            position + Vector((size, -size, size)),
            position + Vector((size, size, size)),
            position + Vector((-size, size, size))
        ]
        
        # 立方體邊緣
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 0),  # 底面
            (4, 5), (5, 6), (6, 7), (7, 4),  # 頂面
            (0, 4), (1, 5), (2, 6), (3, 7)   # 垂直邊
        ]
        
        # 轉換為線條頂點
        line_vertices = []
        for edge in edges:
            line_vertices.extend([vertices[edge[0]], vertices[edge[1]]])
        
        # 繪製線條
        self._draw_line_vertices(context, line_vertices, color)

    def _draw_sphere_marker(self, context, position, color, radius):
        """繪製球體標記"""
        # 簡化實現：繪製圓形輪廓
        segments = 16
        vertices = []
        
        # XY 平面圓
        for i in range(segments):
            angle = 2.0 * 3.14159 * i / segments
            x = position.x + radius * (angle)
            y = position.y + radius * (angle)
            vertices.append(Vector((x, y, position.z)))
        
        # 閉合圓形
        vertices.append(vertices[0])
        
        # 繪製圓形
        self._draw_line_vertices(context, vertices, color)

    def _draw_square_marker(self, context, position, color, size):
        """繪製方形標記"""
        half_size = size / 2
        
        # 方形頂點
        vertices = [
            position + Vector((-half_size, -half_size, 0)),
            position + Vector((half_size, -half_size, 0)),
            position + Vector((half_size, half_size, 0)),
            position + Vector((-half_size, half_size, 0)),
            position + Vector((-half_size, -half_size, 0))  # 閉合
        ]
        
        # 繪製方形
        self._draw_line_vertices(context, vertices, color)

    def _draw_line_vertices(self, context, vertices, color):
        """繪製頂點線條"""
        if not vertices:
            return
        
        # 創建著色器
        shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        shader.bind()
        shader.uniform_float("color", color)
        
        # 創建批次
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": vertices})
        batch.draw(shader)

    def _draw_constraint_lines(self, context):
        """繪製約束線"""
        for constraint_data in self.constraint_lines:
            start = constraint_data.get('start', Vector())
            direction = constraint_data.get('direction', Vector((0, 0, 1)))
            length = constraint_data.get('length', 5.0)
            color = constraint_data.get('color', self.colors['constraint'])
            
            end = start + direction.normalized() * length
            self._draw_line_3d(context, start, end, color, 1)

    def _draw_hud_text(self, context):
        """繪製 HUD 文字"""
        # 這裡需要使用 blf 模組繪製文字
        # 簡化實現，暫時跳過
        pass

    def add_ghost_object(self, obj, transform_matrix=None):
        """添加幽靈物件"""
        ghost_data = {
            'object': obj,
            'transform': transform_matrix or obj.matrix_world.copy()
        }
        self.ghost_objects.append(ghost_data)

    def remove_ghost_object(self, obj):
        """移除幽靈物件"""
        self.ghost_objects = [g for g in self.ghost_objects if g.get('object') != obj]

    def add_alignment_line(self, start, end, color=None):
        """添加對齊線"""
        line_data = {
            'start': start,
            'end': end,
            'color': color or self.colors['alignment']
        }
        self.alignment_lines.append(line_data)

    def clear_alignment_lines(self):
        """清除所有對齊線"""
        self.alignment_lines.clear()

    def add_snap_point(self, position, snap_type='POINT', color=None):
        """添加吸附點"""
        point_data = {
            'position': position,
            'type': snap_type,
            'color': color or self.colors['snap'],
            'size': 10
        }
        self.snap_points.append(point_data)

    def clear_snap_points(self):
        """清除所有吸附點"""
        self.snap_points.clear()

    def add_constraint_line(self, start, direction, length=5.0, color=None):
        """添加約束線"""
        constraint_data = {
            'start': start,
            'direction': direction,
            'length': length,
            'color': color or self.colors['constraint']
        }
        self.constraint_lines.append(constraint_data)

    def clear_constraint_lines(self):
        """清除所有約束線"""
        self.constraint_lines.clear()

    def clear_all(self):
        """清除所有預覽元素"""
        self.ghost_objects.clear()
        self.alignment_lines.clear()
        self.snap_points.clear()
        self.constraint_lines.clear()

    def update_colors(self, color_scheme=None):
        """更新顏色配置"""
        if color_scheme:
            self.colors.update(color_scheme)


# 全局預覽繪製處理器實例
preview_draw_handler = PreviewDrawHandler()


def register_preview_system():
    """註冊預覽系統"""
    preview_draw_handler.register_handlers()


def unregister_preview_system():
    """註銷預覽系統"""
    preview_draw_handler.unregister_handlers()


def get_preview_handler():
    """獲取預覽處理器實例"""
    return preview_draw_handler
