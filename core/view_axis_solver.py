"""
Smart Align Pro v7.4 - View Axis Solver
視圖軸求解器 - v7.4 核心升級

負責：
- 統一處理畫面座標系
- 視圖 basis 計算
- 畫面左/右/上/下 對應到 world vector
- 把 world delta 投影到 view axis
- 讓所有 axis lock / directional align / preview 都走這裡

這是全系統唯一的 view-space 基礎運算來源。
不要再讓各 operator 各自算 view basis。
"""

import bpy
from mathutils import Vector, Matrix
from typing import Dict, Optional, Tuple
from enum import Enum, auto


class ViewAxisName(Enum):
    """視圖軸名稱"""
    LEFT_RIGHT = "VIEW_LEFT_RIGHT"
    UP_DOWN = "VIEW_UP_DOWN"
    DEPTH = "VIEW_DEPTH"
    
    
class ViewPlaneName(Enum):
    """視圖平面名稱"""
    VIEW_PLANE = "VIEW_PLANE"
    HORIZONTAL_PLANE = "VIEW_HORIZONTAL_PLANE"
    VERTICAL_PLANE = "VIEW_VERTICAL_PLANE"


class ViewAxisSolver:
    """
    視圖軸求解器
    
    提供統一的 view-space 座標運算。
    所有 view-oriented 功能都必須調用這個類，不准各自重算。
    """
    
    @staticmethod
    def get_view_basis(context) -> Dict[str, Vector]:
        """
        獲取視圖座標系 basis
        
        Args:
            context: Blender context
            
        Returns:
            dict: 包含 view_forward, view_right, view_up
        """
        region = context.region
        rv3d = context.region_data
        
        if rv3d is None:
            # 沒有 3D 視圖，回傳預設值
            return {
                'view_forward': Vector((0, 0, -1)),
                'view_right': Vector((1, 0, 0)),
                'view_up': Vector((0, 1, 0)),
                'region': region,
                'rv3d': rv3d
            }
        
        # 從 view_matrix 提取方向向量
        view_matrix = rv3d.view_matrix
        
        # view_matrix 把 world 轉換到 view space
        # 所以 view_forward 在 world space 是 view_matrix 的第三列（反向）
        view_forward = -Vector((view_matrix[0][2], view_matrix[1][2], view_matrix[2][2]))
        view_right = Vector((view_matrix[0][0], view_matrix[1][0], view_matrix[2][0]))
        view_up = Vector((view_matrix[0][1], view_matrix[1][1], view_matrix[2][1]))
        
        # 正規化
        view_forward.normalize()
        view_right.normalize()
        view_up.normalize()
        
        return {
            'view_forward': view_forward,
            'view_right': view_right,
            'view_up': view_up,
            'region': region,
            'rv3d': rv3d
        }
    
    @staticmethod
    def get_view_direction_vectors(context) -> Dict[str, Vector]:
        """
        獲取畫面語意方向對應的 world vectors
        
        Returns:
            dict: 包含 LEFT, RIGHT, UP, DOWN, DEPTH_FORWARD, DEPTH_BACK
        """
        basis = ViewAxisSolver.get_view_basis(context)
        
        return {
            'LEFT': -basis['view_right'],
            'RIGHT': basis['view_right'],
            'UP': basis['view_up'],
            'DOWN': -basis['view_up'],
            'DEPTH_FORWARD': -basis['view_forward'],  # 朝向攝影機
            'DEPTH_BACK': basis['view_forward']  # 遠離攝影機
        }
    
    @staticmethod
    def project_world_delta_to_view_axis(delta_world: Vector, 
                                          context, 
                                          axis_name: str) -> Vector:
        """
        將 world delta 投影到指定 view axis
        
        Args:
            delta_world: World space 的位移向量
            context: Blender context
            axis_name: "VIEW_LEFT_RIGHT", "VIEW_UP_DOWN", "VIEW_DEPTH"
            
        Returns:
            Vector: 投影後的位移向量
        """
        directions = ViewAxisSolver.get_view_direction_vectors(context)
        
        # 取得對應方向的單位向量
        if axis_name == ViewAxisName.LEFT_RIGHT.value or axis_name == "LEFT_RIGHT":
            axis_dir = directions['RIGHT']
        elif axis_name == ViewAxisName.UP_DOWN.value or axis_name == "UP_DOWN":
            axis_dir = directions['UP']
        elif axis_name == ViewAxisName.DEPTH.value or axis_name == "DEPTH":
            axis_dir = directions['DEPTH_BACK']
        else:
            # 未知 axis_name，回傳原值
            return delta_world
        
        # 投影 delta_world 到 axis_dir
        # result = (delta · axis) * axis
        projection_length = delta_world.dot(axis_dir)
        return axis_dir * projection_length
    
    @staticmethod
    def constrain_delta_to_view_axis(delta_world: Vector,
                                     context,
                                     axis_name: str) -> Vector:
        """
        將 world delta 限制到指定 view axis（與 project 相同）
        
        Args:
            delta_world: World space 的位移向量
            context: Blender context
            axis_name: "VIEW_LEFT_RIGHT", "VIEW_UP_DOWN", "VIEW_DEPTH"
            
        Returns:
            Vector: 限制後的位移向量
        """
        return ViewAxisSolver.project_world_delta_to_view_axis(
            delta_world, context, axis_name
        )
    
    @staticmethod
    def constrain_delta_to_view_plane(delta_world: Vector,
                                      context,
                                      plane_name: str) -> Vector:
        """
        將 world delta 限制到指定 view plane
        
        Args:
            delta_world: World space 的位移向量
            context: Blender context
            plane_name: "VIEW_PLANE", "VIEW_HORIZONTAL_PLANE", "VIEW_VERTICAL_PLANE"
            
        Returns:
            Vector: 限制後的位移向量
        """
        basis = ViewAxisSolver.get_view_basis(context)
        
        if plane_name == ViewPlaneName.VIEW_PLANE.value or plane_name == "VIEW_PLANE":
            # 限制到 view plane（垂直於 view_forward）
            normal = basis['view_forward']
        elif plane_name == ViewPlaneName.HORIZONTAL_PLANE.value or plane_name == "VIEW_HORIZONTAL_PLANE":
            # 限制到水平面（垂直於 view_up）
            normal = basis['view_up']
        elif plane_name == ViewPlaneName.VERTICAL_PLANE.value or plane_name == "VIEW_VERTICAL_PLANE":
            # 限制到垂直面（垂直於 view_right）
            normal = basis['view_right']
        else:
            return delta_world
        
        # 投影 delta_world 到平面
        # V_plane = V - (V · N) * N
        dot_product = delta_world.dot(normal)
        return delta_world - normal * dot_product
    
    @staticmethod
    def get_axis_vector(context, axis_name: str) -> Optional[Vector]:
        """
        獲取指定 view axis 的 world space 方向向量
        
        Args:
            context: Blender context
            axis_name: view axis 名稱
            
        Returns:
            Vector: 方向向量，或 None
        """
        directions = ViewAxisSolver.get_view_direction_vectors(context)
        
        mapping = {
            ViewAxisName.LEFT_RIGHT.value: directions['RIGHT'],
            ViewAxisName.UP_DOWN.value: directions['UP'],
            ViewAxisName.DEPTH.value: directions['DEPTH_BACK'],
            "VIEW_LEFT": directions['LEFT'],
            "VIEW_RIGHT": directions['RIGHT'],
            "VIEW_UP": directions['UP'],
            "VIEW_DOWN": directions['DOWN'],
            "VIEW_DEPTH_FORWARD": directions['DEPTH_FORWARD'],
            "VIEW_DEPTH_BACK": directions['DEPTH_BACK'],
        }
        
        return mapping.get(axis_name)
    
    @staticmethod
    def get_plane_normal(context, plane_name: str) -> Optional[Vector]:
        """
        獲取指定 view plane 的 world space 法線向量
        
        Args:
            context: Blender context
            plane_name: view plane 名稱
            
        Returns:
            Vector: 法線向量，或 None
        """
        basis = ViewAxisSolver.get_view_basis(context)
        
        if plane_name == ViewPlaneName.VIEW_PLANE.value or plane_name == "VIEW_PLANE":
            return basis['view_forward']
        elif plane_name == ViewPlaneName.HORIZONTAL_PLANE.value or plane_name == "VIEW_HORIZONTAL_PLANE":
            return basis['view_up']
        elif plane_name == ViewPlaneName.VERTICAL_PLANE.value or plane_name == "VIEW_VERTICAL_PLANE":
            return basis['view_right']
        
        return None
    
    @staticmethod
    def is_view_space_available(context) -> bool:
        """檢查是否有可用的 view space"""
        return context.region_data is not None
    
    @staticmethod
    def world_to_screen_direction(context, world_dir: Vector) -> Vector:
        """
        將 world direction 轉換為 screen space direction
        
        Args:
            context: Blender context
            world_dir: World space 方向向量
            
        Returns:
            Vector: Screen space 方向 (2D)
        """
        rv3d = context.region_data
        if rv3d is None:
            return Vector((0, 0))
        
        # 使用 view_matrix 轉換方向
        view_matrix = rv3d.view_matrix
        view_dir = view_matrix @ world_dir.to_4d()
        view_dir = Vector((view_dir.x, view_dir.y))
        
        # 轉換到 screen space
        if view_dir.length > 0:
            view_dir.normalize()
        
        return view_dir
    
    @staticmethod
    def compute_view_aligned_transform(context, 
                                       target_point: Vector,
                                       reference_point: Vector,
                                       axis_name: str = "VIEW_LEFT_RIGHT") -> Matrix:
        """
        計算 view-aligned 的變換矩陣
        
        Args:
            context: Blender context
            target_point: 目標點
            reference_point: 參考點
            axis_name: 對齊軸
            
        Returns:
            Matrix: Translation matrix
        """
        delta = target_point - reference_point
        constrained_delta = ViewAxisSolver.constrain_delta_to_view_axis(
            delta, context, axis_name
        )
        
        return Matrix.Translation(constrained_delta)


# ============================================================================
# 便捷函式 - 供外部直接使用
# ============================================================================

def get_view_basis(context) -> Dict[str, Vector]:
    """獲取視圖 basis"""
    return ViewAxisSolver.get_view_basis(context)


def get_view_direction_vectors(context) -> Dict[str, Vector]:
    """獲取視圖方向向量"""
    return ViewAxisSolver.get_view_direction_vectors(context)


def project_to_view_axis(delta_world: Vector, context, axis_name: str) -> Vector:
    """投影到 view axis"""
    return ViewAxisSolver.project_world_delta_to_view_axis(delta_world, context, axis_name)


def constrain_to_view_axis(delta_world: Vector, context, axis_name: str) -> Vector:
    """限制到 view axis"""
    return ViewAxisSolver.constrain_delta_to_view_axis(delta_world, context, axis_name)


def constrain_to_view_plane(delta_world: Vector, context, plane_name: str) -> Vector:
    """限制到 view plane"""
    return ViewAxisSolver.constrain_delta_to_view_plane(delta_world, context, plane_name)


def get_view_axis_vector(context, axis_name: str) -> Optional[Vector]:
    """獲取 view axis 向量"""
    return ViewAxisSolver.get_axis_vector(context, axis_name)


def get_view_plane_normal(context, plane_name: str) -> Optional[Vector]:
    """獲取 view plane 法線"""
    return ViewAxisSolver.get_plane_normal(context, plane_name)
