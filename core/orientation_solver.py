"""
Smart Align Pro - 姿態求解系統
實現真正的 CAD 級 orientation solving
這是超越 CAD Transform 的關鍵技術
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from .math_utils import get_plane_basis, rotation_between_vectors
from ..utils.bbox_utils import get_bbox_center_world


class OrientationSolver:
    """姿態求解器核心類"""
    
    def __init__(self):
        self.translation_solver = TranslationSolver()
        self.rotation_solver = RotationSolver()
        self.plane_solver = PlaneSolver()
        self.pivot_solver = PivotSolver()
    
    def solve_two_point_orientation(self, source_obj, target_obj, from_point, to_point):
        """求解兩點對齊的完整姿態"""
        result = {
            'translation': None,
            'rotation': None,
            'scale': None,
            'success': False,
            'error': None
        }
        
        try:
            # 1. 求解平移
            translation_result = self.translation_solver.solve_translation(
                source_obj, from_point, to_point
            )
            result['translation'] = translation_result
            
            # 2. 求解旋轉（可選）
            if hasattr(self, 'solve_rotation_from_points'):
                rotation_result = self.rotation_solver.solve_rotation_from_points(
                    source_obj, from_point, to_point
                )
                result['rotation'] = rotation_result
            
            # 3. 保持原始縮放
            result['scale'] = Matrix.Identity(4)
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_three_point_orientation(self, source_obj, target_obj, 
                                     from_points, to_points):
        """求解三點對齊的完整姿態"""
        result = {
            'translation': None,
            'rotation': None,
            'scale': None,
            'success': False,
            'error': None
        }
        
        try:
            # 解析三點
            src_a, src_b, src_c = from_points
            tgt_a, tgt_b, tgt_c = to_points
            
            # 1. 求解旋轉矩陣
            rotation_result = self.rotation_solver.solve_three_point_rotation(
                src_a, src_b, src_c, tgt_a, tgt_b, tgt_c
            )
            result['rotation'] = rotation_result
            
            # 2. 求解平移
            # 應用旋轉後計算需要的平移
            if rotation_result['success']:
                rotated_src_a = rotation_result['matrix'] @ src_a
                translation_vector = tgt_a - rotated_src_a
                result['translation'] = Matrix.Translation(translation_vector)
            
            # 3. 保持原始縮放
            result['scale'] = Matrix.Identity(4)
            result['success'] = rotation_result['success']
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_surface_normal_orientation(self, source_obj, target_obj, 
                                       surface_normal, alignment_axis):
        """求解表面法線對齊姿態"""
        result = {
            'translation': None,
            'rotation': None,
            'scale': None,
            'success': False,
            'error': None
        }
        
        try:
            # 1. 求解旋轉：對齊指定軸到表面法線
            axis_vectors = {
                'POS_X': Vector((1, 0, 0)),
                'NEG_X': Vector((-1, 0, 0)),
                'POS_Y': Vector((0, 1, 0)),
                'NEG_Y': Vector((0, -1, 0)),
                'POS_Z': Vector((0, 0, 1)),
                'NEG_Z': Vector((0, 0, -1))
            }
            
            target_axis = axis_vectors.get(alignment_axis, Vector((0, 0, 1)))
            rotation = rotation_between_vectors(target_axis, surface_normal.normalized())
            result['rotation'] = rotation.to_matrix().to_4x4()
            
            # 2. 平移保持原位置（可選）
            result['translation'] = Matrix.Identity(4)
            
            # 3. 保持原始縮放
            result['scale'] = Matrix.Identity(4)
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result


class TranslationSolver:
    """平移求解器"""
    
    def solve_translation(self, source_obj, from_point, to_point, constraint=None):
        """求解平移變換"""
        if constraint and constraint['type'] == 'AXIS':
            # 軸向約束平移
            axis_vector = constraint['axis'].normalized()
            direction = to_point - from_point
            projection = direction.dot(axis_vector) * axis_vector
            return Matrix.Translation(projection)
        
        elif constraint and constraint['type'] == 'PLANE':
            # 平面約束平移
            plane_point = constraint['point']
            plane_normal = constraint['normal'].normalized()
            
            direction = to_point - from_point
            # 計算在平面上的投影
            projected_direction = direction - direction.dot(plane_normal) * plane_normal
            return Matrix.Translation(projected_direction)
        
        else:
            # 自由平移
            return Matrix.Translation(to_point - from_point)


class RotationSolver:
    """旋轉求解器"""
    
    def solve_three_point_rotation(self, src_a, src_b, src_c, tgt_a, tgt_b, tgt_c):
        """求解三點對齊的旋轉矩陣"""
        result = {
            'matrix': None,
            'quaternion': None,
            'success': False,
            'error': None
        }
        
        try:
            # 計算來源平面基底
            src_x, src_y, src_n = get_plane_basis(src_a, src_b, src_c)
            
            # 計算目標平面基底
            tgt_x, tgt_y, tgt_n = get_plane_basis(tgt_a, tgt_b, tgt_c)
            
            # 構建來源和目標基底矩陣
            src_basis = self._build_basis_matrix(src_a, src_x, src_y, src_n)
            tgt_basis = self._build_basis_matrix(tgt_a, tgt_x, tgt_y, tgt_n)
            
            # 計算旋轉矩陣
            rotation_matrix = tgt_basis @ src_basis.inverted()
            
            # 轉換為四元數
            rotation_quaternion = rotation_matrix.to_quaternion()
            
            result['matrix'] = rotation_matrix
            result['quaternion'] = rotation_quaternion
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_rotation_from_vectors(self, from_vector, to_vector):
        """從向量求解旋轉"""
        result = {
            'matrix': None,
            'quaternion': None,
            'success': False,
            'error': None
        }
        
        try:
            # 計算旋轉四元數
            rotation_quat = rotation_between_vectors(from_vector, to_vector)
            rotation_matrix = rotation_quat.to_matrix().to_4x4()
            
            result['matrix'] = rotation_matrix
            result['quaternion'] = rotation_quat
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_rotation_from_axis_angle(self, axis, angle):
        """從軸和角度求解旋轉"""
        result = {
            'matrix': None,
            'quaternion': None,
            'success': False,
            'error': None
        }
        
        try:
            # 創建四元數
            rotation_quat = Quaternion(axis.normalized(), angle)
            rotation_matrix = rotation_quat.to_matrix().to_4x4()
            
            result['matrix'] = rotation_matrix
            result['quaternion'] = rotation_quat
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def _build_basis_matrix(self, origin, x_axis, y_axis, z_axis):
        """構建基底矩陣"""
        return Matrix((
            (x_axis.x, y_axis.x, z_axis.x, origin.x),
            (x_axis.y, y_axis.y, z_axis.y, origin.y),
            (x_axis.z, y_axis.z, z_axis.z, origin.z),
            (0, 0, 0, 1)
        ))


class PlaneSolver:
    """平面求解器"""
    
    def solve_plane_from_three_points(self, p1, p2, p3):
        """從三點求解平面"""
        result = {
            'point': None,
            'normal': None,
            'd': None,  # 平面方程 ax + by + cz + d = 0 中的 d
            'success': False,
            'error': None
        }
        
        try:
            # 計算平面法線
            v1 = p2 - p1
            v2 = p3 - p1
            normal = v1.cross(v2).normalized()
            
            # 平面上一點
            point = p1
            
            # 計算平面方程的 d 值
            d = -normal.dot(point)
            
            result['point'] = point
            result['normal'] = normal
            result['d'] = d
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_plane_intersection(self, plane1, plane2, plane3):
        """求解三平面交點"""
        result = {
            'point': None,
            'success': False,
            'error': None
        }
        
        try:
            # 解線性方程組
            # plane1: a1*x + b1*y + c1*z + d1 = 0
            # plane2: a2*x + b2*y + c2*z + d2 = 0
            # plane3: a3*x + b3*y + c3*z + d3 = 0
            
            A = Matrix((
                (plane1['normal'].x, plane1['normal'].y, plane1['normal'].z),
                (plane2['normal'].x, plane2['normal'].y, plane2['normal'].z),
                (plane3['normal'].x, plane3['normal'].y, plane3['normal'].z)
            ))
            
            B = Vector((-plane1['d'], -plane2['d'], -plane3['d']))
            
            # 求解線性方程組
            if abs(A.determinant()) > 1e-6:
                point = A.inverted() @ B
                result['point'] = point
                result['success'] = True
            else:
                result['error'] = "平面平行或重合，無唯一解"
                result['success'] = False
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result


class PivotSolver:
    """支點求解系統"""
    
    def __init__(self):
        self.pivot_types = {
            'VERTEX': self.solve_vertex_pivot,
            'EDGE': self.solve_edge_pivot,
            'FACE': self.solve_face_pivot,
            'CENTER': self.solve_center_pivot,
            'CUSTOM': self.solve_custom_pivot,
            'LOCAL': self.solve_local_pivot,
            'WORLD': self.solve_world_pivot
        }
    
    def solve_pivot(self, obj, pivot_type, pivot_data=None):
        """求解支點"""
        if pivot_type not in self.pivot_types:
            return self.solve_center_pivot(obj)
        
        return self.pivot_types[pivot_type](obj, pivot_data)
    
    def solve_vertex_pivot(self, obj, vertex_index):
        """求解頂點支點"""
        result = {
            'position': None,
            'normal': None,
            'success': False,
            'error': None
        }
        
        try:
            if obj.type != 'MESH':
                result['error'] = "非網格物件"
                return result
            
            # 獲取頂點位置
            vertex = obj.data.vertices[vertex_index]
            position = obj.matrix_world @ vertex.co
            
            # 計算頂點法線
            normal = self._calculate_vertex_normal(obj, vertex_index)
            world_normal = obj.matrix_world.to_3x3() @ normal
            
            result['position'] = position
            result['normal'] = world_normal.normalized()
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_edge_pivot(self, obj, edge_index):
        """求解邊緣支點"""
        result = {
            'position': None,
            'normal': None,
            'direction': None,
            'success': False,
            'error': None
        }
        
        try:
            if obj.type != 'MESH':
                result['error'] = "非網格物件"
                return result
            
            edge = obj.data.edges[edge_index]
            v1, v2 = edge.vertices
            
            # 計算邊緣中點
            p1 = obj.matrix_world @ obj.data.vertices[v1].co
            p2 = obj.matrix_world @ obj.data.vertices[v2].co
            position = (p1 + p2) / 2
            
            # 計算邊緣方向
            direction = (p2 - p1).normalized()
            
            # 計算邊緣法線
            normal = direction.cross(Vector((0, 0, 1))).normalized()
            
            result['position'] = position
            result['normal'] = normal
            result['direction'] = direction
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_face_pivot(self, obj, face_index):
        """求解面支點"""
        result = {
            'position': None,
            'normal': None,
            'success': False,
            'error': None
        }
        
        try:
            if obj.type != 'MESH':
                result['error'] = "非網格物件"
                return result
            
            polygon = obj.data.polygons[face_index]
            
            # 計算面中心
            position = obj.matrix_world @ polygon.center
            
            # 獲取面法線
            normal = obj.matrix_world.to_3x3() @ polygon.normal
            
            result['position'] = position
            result['normal'] = normal.normalized()
            result['success'] = True
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_center_pivot(self, obj, pivot_data=None):
        """求解中心支點"""
        result = {
            'position': None,
            'normal': Vector((0, 0, 1)),
            'success': True,
            'error': None
        }
        
        try:
            # 使用邊界框中心
            position = get_bbox_center_world(obj)
            result['position'] = position
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
        
        return result
    
    def solve_custom_pivot(self, obj, custom_position):
        """求解自定義支點"""
        result = {
            'position': custom_position,
            'normal': Vector((0, 0, 1)),
            'success': True,
            'error': None
        }
        return result
    
    def solve_local_pivot(self, obj, local_position):
        """求解局部坐標支點"""
        result = {
            'position': obj.matrix_world @ local_position,
            'normal': obj.matrix_world.to_3x3() @ Vector((0, 0, 1)),
            'success': True,
            'error': None
        }
        return result
    
    def solve_world_pivot(self, obj, world_position):
        """求解世界坐標支點"""
        result = {
            'position': world_position,
            'normal': Vector((0, 0, 1)),
            'success': True,
            'error': None
        }
        return result
    
    def _calculate_vertex_normal(self, obj, vertex_index):
        """計算頂點法線"""
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


# 全局姿態求解器實例
orientation_solver = OrientationSolver()
