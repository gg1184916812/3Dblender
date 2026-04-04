"""
Smart Align Pro - CAD 級吸附系統
實現 snap-from/snap-to 和 modal 工作流
"""

import bpy
import math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d
from .math_utils import project_point_to_plane, calculate_distance_point_to_plane


class CADSnapPoint:
    """CAD 吸附點類"""
    def __init__(self, position, normal, snap_type, object_ref, element_ref=None):
        self.position = position
        self.normal = normal
        self.snap_type = snap_type  # 'VERTEX', 'EDGE', 'FACE', 'GRID', 'MIDPOINT'
        self.object_ref = object_ref
        self.element_ref = element_ref  # 頂點/邊/面的索引
        self.distance = 0.0
        self.confidence = 1.0


class CADSnapSystem:
    """CAD 吸附系統核心類"""
    
    def __init__(self):
        self.snap_points = []
        self.active_snap = None
        self.snap_tolerance = 0.1
        self.snap_modes = {
            'VERTEX': True,
            'EDGE': True,
            'FACE': True,
            'MIDPOINT': True,
            'CENTER': True,
            'GRID': True,
            'INTERSECTION': True,
            'PERPENDICULAR': True,
            'TANGENT': True
        }
        self.from_point = None
        self.to_point = None
        self.reference_plane = None
        self.constraint_axis = None
    
    def set_snap_tolerance(self, tolerance):
        """設置吸附容差"""
        self.snap_tolerance = tolerance
    
    def enable_snap_mode(self, mode, enabled=True):
        """啟用/禁用特定吸附模式"""
        if mode in self.snap_modes:
            self.snap_modes[mode] = enabled
    
    def find_snap_points(self, context, mouse_pos, view_vector):
        """尋找所有可能的吸附點"""
        self.snap_points.clear()
        
        # 獲取 3D 射線
        region = context.region
        region_3d = context.space_data.region_3d
        
        # 轉換 2D 鼠標位置到 3D 射線
        ray_origin, ray_direction = self.get_ray_from_mouse(context, mouse_pos)
        
        if not ray_origin:
            return []
        
        # 執行各種吸附檢測
        if self.snap_modes['VERTEX']:
            self.find_vertex_snaps(context, ray_origin, ray_direction)
        
        if self.snap_modes['EDGE']:
            self.find_edge_snaps(context, ray_origin, ray_direction)
        
        if self.snap_modes['FACE']:
            self.find_face_snaps(context, ray_origin, ray_direction)
        
        if self.snap_modes['MIDPOINT']:
            self.find_midpoint_snaps(context, ray_origin, ray_direction)
        
        if self.snap_modes['CENTER']:
            self.find_center_snaps(context, ray_origin, ray_direction)
        
        if self.snap_modes['GRID']:
            self.find_grid_snaps(context, ray_origin, ray_direction)
        
        if self.snap_modes['INTERSECTION']:
            self.find_intersection_snaps(context, ray_origin, ray_direction)
        
        # 計算距離並排序
        for snap_point in self.snap_points:
            snap_point.distance = (snap_point.position - ray_origin).length
        
        # 按距離排序
        self.snap_points.sort(key=lambda sp: sp.distance)
        
        # 應用容差過濾
        filtered_snaps = []
        for snap_point in self.snap_points:
            if snap_point.distance <= self.snap_tolerance * 10:  # 放大容差範圍
                filtered_snaps.append(snap_point)
        
        self.snap_points = filtered_snaps
        return self.snap_points
    
    def get_ray_from_mouse(self, context, mouse_pos):
        """從鼠標位置獲取 3D 射線"""
        region = context.region
        region_3d = context.space_data.region_3d
        
        try:
            # 由 2D 視窗座標建立 3D 射線
            ray_origin = region_2d_to_origin_3d(region, region_3d, mouse_pos)
            ray_direction = region_2d_to_vector_3d(region, region_3d, mouse_pos)

            if ray_origin is not None and ray_direction is not None:
                return ray_origin, ray_direction.normalized()

        except Exception:
            pass
        
        return None, None
    
    def find_vertex_snaps(self, context, ray_origin, ray_direction):
        """尋找頂點吸附點"""
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.hide_get():
                continue
            
            # 轉換射線到物件局部坐標
            obj_matrix_inv = obj.matrix_world.inverted()
            local_ray_origin = obj_matrix_inv @ ray_origin
            local_ray_direction = obj_matrix_inv.to_3x3() @ ray_direction
            
            # 檢查每個頂點
            for vertex in obj.data.vertices:
                vertex_pos = vertex.co
                
                # 計算頂點到射線的距離
                closest_point = self.closest_point_on_ray(vertex_pos, local_ray_origin, local_ray_direction)
                distance = (vertex_pos - closest_point).length
                
                if distance <= self.snap_tolerance:
                    # 轉換回世界坐標
                    world_pos = obj.matrix_world @ vertex_pos
                    
                    # 計算法線（基於相鄰面）
                    normal = self.get_vertex_normal(obj, vertex.index)
                    world_normal = obj.matrix_world.to_3x3() @ normal
                    
                    snap_point = CADSnapPoint(
                        world_pos, world_normal, 'VERTEX', obj, vertex.index
                    )
                    snap_point.distance = distance
                    self.snap_points.append(snap_point)
    
    def find_edge_snaps(self, context, ray_origin, ray_direction):
        """尋找邊緣吸附點"""
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.hide_get():
                continue
            
            obj_matrix_inv = obj.matrix_world.inverted()
            local_ray_origin = obj_matrix_inv @ ray_origin
            local_ray_direction = obj_matrix_inv.to_3x3() @ ray_direction
            
            for edge in obj.data.edges:
                v1, v2 = edge.vertices
                p1 = obj.data.vertices[v1].co
                p2 = obj.data.vertices[v2].co
                
                # 計算邊緣到射線的最近點
                closest_point, distance = self.closest_point_edge_to_ray(
                    p1, p2, local_ray_origin, local_ray_direction
                )
                
                if distance <= self.snap_tolerance:
                    world_pos = obj.matrix_world @ closest_point
                    
                    # 計算邊緣法線
                    edge_vector = (p2 - p1).normalized()
                    normal = edge_vector.cross(local_ray_direction).normalized()
                    world_normal = obj.matrix_world.to_3x3() @ normal
                    
                    snap_point = CADSnapPoint(
                        world_pos, world_normal, 'EDGE', obj, edge.index
                    )
                    snap_point.distance = distance
                    self.snap_points.append(snap_point)
    
    def find_face_snaps(self, context, ray_origin, ray_direction):
        """尋找面吸附點"""
        # 使用 Blender 的射線檢測
        result, location, normal, face_index, obj, matrix = context.scene.ray_cast(
            context.depsgraph, ray_origin, ray_direction
        )
        
        if result and obj and obj.type == 'MESH':
            snap_point = CADSnapPoint(
                location, normal, 'FACE', obj, face_index
            )
            snap_point.distance = (location - ray_origin).length
            self.snap_points.append(snap_point)
    
    def find_midpoint_snaps(self, context, ray_origin, ray_direction):
        """尋找中點吸附點"""
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.hide_get():
                continue
            
            obj_matrix_inv = obj.matrix_world.inverted()
            local_ray_origin = obj_matrix_inv @ ray_origin
            local_ray_direction = obj_matrix_inv.to_3x3() @ ray_direction
            
            for edge in obj.data.edges:
                v1, v2 = edge.vertices
                p1 = obj.data.vertices[v1].co
                p2 = obj.data.vertices[v2].co
                
                # 計算中點
                midpoint = (p1 + p2) / 2
                
                # 計算中點到射線的距離
                closest_point = self.closest_point_on_ray(midpoint, local_ray_origin, local_ray_direction)
                distance = (midpoint - closest_point).length
                
                if distance <= self.snap_tolerance:
                    world_pos = obj.matrix_world @ midpoint
                    
                    # 計算法線
                    edge_vector = (p2 - p1).normalized()
                    normal = edge_vector.cross(local_ray_direction).normalized()
                    world_normal = obj.matrix_world.to_3x3() @ normal
                    
                    snap_point = CADSnapPoint(
                        world_pos, world_normal, 'MIDPOINT', obj, edge.index
                    )
                    snap_point.distance = distance
                    self.snap_points.append(snap_point)
    
    def find_center_snaps(self, context, ray_origin, ray_direction):
        """尋找中心點吸附點"""
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.hide_get():
                continue
            
            # 物件中心
            from ..utils.bbox_utils import get_bbox_center_world
            center = get_bbox_center_world(obj)
            
            # 計算中心到射線的距離
            closest_point = self.closest_point_on_ray(center, ray_origin, ray_direction)
            distance = (center - closest_point).length
            
            if distance <= self.snap_tolerance:
                snap_point = CADSnapPoint(
                    center, Vector((0, 0, 1)), 'CENTER', obj, None
                )
                snap_point.distance = distance
                self.snap_points.append(snap_point)
    
    def find_grid_snaps(self, context, ray_origin, ray_direction):
        """尋找網格吸附點"""
        # 獲取網格設置
        grid_scale = context.space_data.grid_scale
        grid_subdivisions = context.space_data.grid_subdivisions
        
        # 計算射線與 XY 平面的交點
        if abs(ray_direction.z) > 0.001:
            t = -ray_origin.z / ray_direction.z
            if t > 0:
                intersection = ray_origin + t * ray_direction
                
                # 對齊到網格
                grid_size = grid_scale / grid_subdivisions
                grid_x = round(intersection.x / grid_size) * grid_size
                grid_y = round(intersection.y / grid_size) * grid_size
                grid_z = round(intersection.z / grid_size) * grid_size
                
                grid_point = Vector((grid_x, grid_y, grid_z))
                
                distance = (grid_point - ray_origin).length
                if distance <= self.snap_tolerance * 5:  # 網格容差更大
                    snap_point = CADSnapPoint(
                        grid_point, Vector((0, 0, 1)), 'GRID', None, None
                    )
                    snap_point.distance = distance
                    self.snap_points.append(snap_point)
    
    def find_intersection_snaps(self, context, ray_origin, ray_direction):
        """尋找交點吸附點"""
        # 這是一個簡化版本，實際可以更複雜
        # 目前只檢測邊緣與平面的交點
        
        for obj in context.scene.objects:
            if obj.type != 'MESH' or obj.hide_get():
                continue
            
            # 使用 BVHTree 進行精確檢測
            bvh = BVHTree.FromObject(obj, context.depsgraph)
            
            # 尋找邊緣交點（簡化實現）
            for edge in obj.data.edges:
                v1, v2 = edge.vertices
                p1 = obj.matrix_world @ obj.data.vertices[v1].co
                p2 = obj.matrix_world @ obj.data.vertices[v2].co
                
                # 這裡可以添加更複雜的交點計算
                # 目前暫時跳過複雜計算
                pass
    
    def closest_point_on_ray(self, point, ray_origin, ray_direction):
        """計算點到射線的最近點"""
        ray_direction = ray_direction.normalized()
        to_point = point - ray_origin
        projection_length = to_point.dot(ray_direction)
        closest_point = ray_origin + projection_length * ray_direction
        return closest_point
    
    def closest_point_edge_to_ray(self, edge_start, edge_end, ray_origin, ray_direction):
        """計算邊緣到射線的最近點"""
        # 簡化實現：計算邊緣中點到射線的距離
        midpoint = (edge_start + edge_end) / 2
        closest_point = self.closest_point_on_ray(midpoint, ray_origin, ray_direction)
        distance = (midpoint - closest_point).length
        return closest_point, distance
    
    def get_vertex_normal(self, obj, vertex_index):
        """獲取頂點法線"""
        vertex = obj.data.vertices[vertex_index]
        
        # 基於相鄰面的法線計算頂點法線
        normal = Vector((0, 0, 0))
        face_count = 0
        
        for polygon in obj.data.polygons:
            if vertex_index in polygon.vertices:
                normal += polygon.normal
                face_count += 1
        
        if face_count > 0:
            normal /= face_count
            return normal.normalized()
        else:
            return Vector((0, 0, 1))
    
    def get_best_snap(self, mouse_pos):
        """獲取最佳吸附點"""
        if not self.snap_points:
            return None
        
        # 根據優先級選擇最佳吸附點
        priority_order = ['VERTEX', 'EDGE', 'FACE', 'MIDPOINT', 'CENTER', 'GRID']
        
        for snap_type in priority_order:
            for snap_point in self.snap_points:
                if snap_point.snap_type == snap_type:
                    return snap_point
        
        # 如果沒有找到優先級匹配，返回距離最近的
        return self.snap_points[0] if self.snap_points else None
    
    def set_from_point(self, point):
        """設置 from 點"""
        self.from_point = point
    
    def set_to_point(self, point):
        """設置 to 點"""
        self.to_point = point
    
    def set_reference_plane(self, plane_point, plane_normal):
        """設置參考平面"""
        self.reference_plane = {
            'point': plane_point,
            'normal': plane_normal.normalized()
        }
    
    def set_constraint_axis(self, axis):
        """設置約束軸"""
        self.constraint_axis = axis
    
    def apply_constraints(self, point):
        """應用約束到點"""
        if self.constraint_axis:
            # 軸向約束
            if self.from_point:
                if self.constraint_axis == 'X':
                    point.y = self.from_point.y
                    point.z = self.from_point.z
                elif self.constraint_axis == 'Y':
                    point.x = self.from_point.x
                    point.z = self.from_point.z
                elif self.constraint_axis == 'Z':
                    point.x = self.from_point.x
                    point.y = self.from_point.y
        
        if self.reference_plane:
            # 平面約束
            distance = calculate_distance_point_to_plane(
                point, self.reference_plane['point'], self.reference_plane['normal']
            )
            point = project_point_to_plane(
                point, self.reference_plane['point'], self.reference_plane['normal']
            )
        
        return point


# 全局 CAD 吸附系統實例
cad_snap_system = CADSnapSystem()
