import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from typing import List, Optional, Dict, Any, Tuple

class AlignmentSolverStack:
    """終極對齊求解器堆疊"""
    
    def __init__(self):
        self.source_points: List[Vector] = []
        self.target_points: List[Vector] = []
        self.active_object: Optional[bpy.types.Object] = None
        self.original_matrix: Optional[Matrix] = None
        
    def reset(self):
        self.source_points.clear()
        self.target_points.clear()
        self.active_object = None
        self.original_matrix = None

    def solve_two_point(self, source_a: Vector, source_b: Vector, target_a: Vector, target_b: Vector) -> Matrix:
        """兩點對齊：點到點精確變換"""
        # 1. 平移：將 source_a 移動到 target_a
        translation = target_a - source_a
        
        # 2. 旋轉：將向量 (source_b - source_a) 旋轉到 (target_b - target_a)
        vec_source = (source_b - source_a).normalized()
        vec_target = (target_b - target_a).normalized()
        
        rotation_quat = vec_source.rotation_difference(vec_target)
        
        # 3. 縮放 (可選)：根據兩點間距縮放
        scale_factor = (target_b - target_a).length / (source_b - source_a).length
        
        # 構建變換矩陣 (以 source_a 為旋轉中心)
        mat_trans_to_origin = Matrix.Translation(-source_a)
        mat_rot = rotation_quat.to_matrix().to_4x4()
        mat_scale = Matrix.Diagonal((scale_factor, scale_factor, scale_factor, 1.0))
        mat_trans_back = Matrix.Translation(target_a)
        
        return mat_trans_back @ mat_rot @ mat_scale @ mat_trans_to_origin

    def solve_three_point(self, s_a: Vector, s_b: Vector, s_c: Vector, t_a: Vector, t_b: Vector, t_c: Vector) -> Matrix:
        """三點對齊：平面到平面精確變換"""
        # 構建源坐標系
        s_v1 = (s_b - s_a).normalized()
        s_v2 = (s_c - s_a).normalized()
        s_normal = s_v1.cross(s_v2).normalized()
        s_v2_ortho = s_normal.cross(s_v1).normalized()
        
        mat_source = Matrix((s_v1, s_v2_ortho, s_normal)).transposed().to_4x4()
        mat_source.translation = s_a
        
        # 構建目標坐標系
        t_v1 = (t_b - t_a).normalized()
        t_v2 = (t_c - t_a).normalized()
        t_normal = t_v1.cross(t_v2).normalized()
        t_v2_ortho = t_normal.cross(t_v1).normalized()
        
        mat_target = Matrix((t_v1, t_v2_ortho, t_normal)).transposed().to_4x4()
        mat_target.translation = t_a
        
        # 計算變換矩陣：T = Target * Source_inv
        return mat_target @ mat_source.inverted()

    def solve_vector_alignment(self, source_pos: Vector, source_vec: Vector, target_pos: Vector, target_vec: Vector) -> Matrix:
        """向量對齊：將源物件的指定向量對齊到目標向量"""
        rotation_quat = source_vec.normalized().rotation_difference(target_vec.normalized())
        
        mat_trans_to_origin = Matrix.Translation(-source_pos)
        mat_rot = rotation_quat.to_matrix().to_4x4()
        mat_trans_back = Matrix.Translation(target_pos)
        
        return mat_trans_back @ mat_rot @ mat_trans_to_origin

    def solve_center_of_mass(self, objects: List[bpy.types.Object], target_pos: Vector) -> Matrix:
        """質心對齊：將多個物件的共同質心移動到目標點"""
        if not objects:
            return Matrix.Identity(4)
            
        total_center = Vector((0, 0, 0))
        for obj in objects:
            total_center += obj.matrix_world.translation
        avg_center = total_center / len(objects)
        
        return Matrix.Translation(target_pos - avg_center)

    def solve_principal_axis(self, obj: bpy.types.Object, target_vec: Vector) -> Matrix:
        """主軸對齊：將物件的最長軸對齊到目標向量"""
        # 獲取 Bounding Box 並計算最長軸
        bbox = [Vector(corner) for corner in obj.bound_box]
        # 簡化：假設 X 軸為長軸，實際應計算 PCA 或 BBox 尺寸
        source_vec = (obj.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
        
        rotation_quat = source_vec.rotation_difference(target_vec.normalized())
        
        mat_trans_to_origin = Matrix.Translation(-obj.matrix_world.translation)
        mat_rot = rotation_quat.to_matrix().to_4x4()
        mat_trans_back = Matrix.Translation(obj.matrix_world.translation)
        
        return mat_trans_back @ mat_rot @ mat_trans_to_origin
