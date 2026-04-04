"""
Smart Align Pro - Constraint Plane System
實現 CAD Transform 級別的約束平面系統
"""

import bpy
import math
from mathutils import Vector, Matrix, geometry
from enum import Enum
from typing import Any, Dict, List, Optional


class ConstraintType(Enum):
    """約束類型枚舉"""
    NONE = "NONE"
    AXIS_X = "X"
    AXIS_Y = "Y"
    AXIS_Z = "Z"
    PLANE_XY = "XY"
    PLANE_XZ = "XZ"
    PLANE_YZ = "YZ"
    EDGE = "EDGE"
    FACE = "FACE"
    CUSTOM = "CUSTOM"


class ReferenceSystem(Enum):
    """參考系統枚舉"""
    WORLD = "WORLD"
    LOCAL = "LOCAL"
    CUSTOM = "CUSTOM"
    VIEW = "VIEW"


class ConstraintPlane:
    """約束平面類別"""
    def __init__(self, origin, normal, constraint_type=ConstraintType.NONE):
        self.origin = origin
        self.normal = normal.normalized()
        self.constraint_type = constraint_type
        self.is_active = True
        
    def project_point(self, point):
        """將點投影到平面上"""
        if not self.is_active:
            return point
        
        # 計算點到平面的向量
        to_point = point - self.origin
        # 計算投影距離
        distance = to_point.dot(self.normal)
        # 投影點
        projected = point - distance * self.normal
        return projected
    
    def is_point_on_plane(self, point, tolerance=0.001):
        """檢查點是否在平面上"""
        if not self.is_active:
            return True
        
        distance = abs((point - self.origin).dot(self.normal))
        return distance <= tolerance
    
    def get_closest_point_on_plane(self, point):
        """獲取平面上離給定點最近的點"""
        return self.project_point(point)


class ConstraintAxis:
    """約束軸類別"""
    def __init__(self, origin, direction, constraint_type=ConstraintType.NONE):
        self.origin = origin
        self.direction = direction.normalized()
        self.constraint_type = constraint_type
        self.is_active = True
        
    def project_point(self, point):
        """將點投影到軸上"""
        if not self.is_active:
            return point
        
        # 計算點到軸的向量
        to_point = point - self.origin
        # 計算投影距離
        distance = to_point.dot(self.direction)
        # 投影點
        projected = self.origin + distance * self.direction
        return projected
    
    def get_closest_point_on_axis(self, point):
        """獲取軸上離給定點最近的點"""
        return self.project_point(point)


class ConstraintPlaneSystem:
    """約束平面系統 - CAD Transform 級別的約束解算"""
    
    def __init__(self):
        self.current_constraint = ConstraintType.NONE
        self.reference_system = ReferenceSystem.WORLD
        self.temp_pivot = None
        self.custom_reference_matrix = None
        self.constraint_plane = None
        self.constraint_axis = None
        self.constraint_edge = None
        self.constraint_face = None
        
        # 約束歷史（用於撤銷）
        self.constraint_history = []
        
    def set_constraint_mode(self, constraint_type, context=None):
        """設置約束模式"""
        self.current_constraint = constraint_type
        
        # 根據約束類型創建相應的約束對象
        if constraint_type in [ConstraintType.PLANE_XY, ConstraintType.PLANE_XZ, ConstraintType.PLANE_YZ]:
            self._create_plane_constraint(constraint_type, context)
        elif constraint_type in [ConstraintType.AXIS_X, ConstraintType.AXIS_Y, ConstraintType.AXIS_Z]:
            self._create_axis_constraint(constraint_type, context)
        elif constraint_type == ConstraintType.EDGE:
            self._create_edge_constraint(context)
        elif constraint_type == ConstraintType.FACE:
            self._create_face_constraint(context)
        elif constraint_type == ConstraintType.NONE:
            self.clear_constraint()
    
    def _create_plane_constraint(self, constraint_type, context):
        """創建平面約束"""
        # 確定平面法線
        normals = {
            ConstraintType.PLANE_XY: Vector((0, 0, 1)),
            ConstraintType.PLANE_XZ: Vector((0, 1, 0)),
            ConstraintType.PLANE_YZ: Vector((1, 0, 0)),
        }
        
        normal = normals.get(constraint_type, Vector((0, 0, 1)))
        
        # 確定平面原點
        from ..utils.bbox_utils import get_bbox_center_world
        if self.temp_pivot:
            origin = self.temp_pivot
        elif context and context.active_object:
            origin = get_bbox_center_world(context.active_object)
        else:
            origin = Vector((0, 0, 0))
        
        # 轉換到參考系統
        origin, normal = self._transform_to_reference_system(origin, normal, context)
        
        self.constraint_plane = ConstraintPlane(origin, normal, constraint_type)
        self.constraint_axis = None
        self.constraint_edge = None
        self.constraint_face = None
    
    def _create_axis_constraint(self, constraint_type, context):
        """創建軸約束"""
        # 確定軸方向
        directions = {
            ConstraintType.AXIS_X: Vector((1, 0, 0)),
            ConstraintType.AXIS_Y: Vector((0, 1, 0)),
            ConstraintType.AXIS_Z: Vector((0, 0, 1)),
        }
        
        direction = directions.get(constraint_type, Vector((1, 0, 0)))
        
        # 確定軸原點
        from ..utils.bbox_utils import get_bbox_center_world
        if self.temp_pivot:
            origin = self.temp_pivot
        elif context and context.active_object:
            origin = get_bbox_center_world(context.active_object)
        else:
            origin = Vector((0, 0, 0))
        
        # 轉換到參考系統
        origin, direction = self._transform_to_reference_system(origin, direction, context)
        
        self.constraint_axis = ConstraintAxis(origin, direction, constraint_type)
        self.constraint_plane = None
        self.constraint_edge = None
        self.constraint_face = None
    
    def _create_edge_constraint(self, context):
        """創建邊緣約束"""
        # 這需要從選擇的邊緣獲取信息
        # 暫時使用默認值
        origin = Vector((0, 0, 0))
        direction = Vector((1, 0, 0))
        
        self.constraint_edge = ConstraintAxis(origin, direction, ConstraintType.EDGE)
        self.constraint_plane = None
        self.constraint_axis = None
        self.constraint_face = None
    
    def _create_face_constraint(self, context):
        """創建面約束"""
        # 這需要從選擇的面獲取信息
        # 暫時使用默認值
        origin = Vector((0, 0, 0))
        normal = Vector((0, 0, 1))
        
        self.constraint_face = ConstraintPlane(origin, normal, ConstraintType.FACE)
        self.constraint_plane = None
        self.constraint_axis = None
        self.constraint_edge = None
    
    def _transform_to_reference_system(self, origin, direction, context):
        """轉換到參考系統"""
        if self.reference_system == ReferenceSystem.WORLD:
            return origin, direction
        
        elif self.reference_system == ReferenceSystem.LOCAL:
            if context and context.active_object:
                # 轉換到本地坐標系
                obj = context.active_object
                local_origin = obj.matrix_world.inverted() @ origin
                local_direction = obj.matrix_world.to_3x3().inverted() @ direction
                return local_origin, local_direction
        
        elif self.reference_system == ReferenceSystem.CUSTOM:
            if self.custom_reference_matrix:
                # 轉換到自定義坐標系
                inv_matrix = self.custom_reference_matrix.inverted()
                custom_origin = inv_matrix @ origin
                custom_direction = inv_matrix.to_3x3() @ direction
                return custom_origin, custom_direction
        
        elif self.reference_system == ReferenceSystem.VIEW:
            if context and context.space_data and context.space_data.region_3d:
                # 轉換到視圖坐標系
                view_matrix = context.space_data.region_3d.view_matrix
                view_origin = view_matrix @ origin
                view_direction = view_matrix.to_3x3() @ direction
                return view_origin, view_direction
        
        return origin, direction
    
    def apply_constraint(self, point):
        """應用約束到點"""
        if self.current_constraint == ConstraintType.NONE:
            return point
        
        elif self.constraint_plane:
            return self.constraint_plane.project_point(point)
        
        elif self.constraint_axis:
            return self.constraint_axis.project_point(point)
        
        elif self.constraint_edge:
            return self.constraint_edge.project_point(point)
        
        elif self.constraint_face:
            return self.constraint_face.project_point(point)
        
        return point
    
    def apply_constraint_to_transform(self, matrix):
        """應用約束到變換矩陣"""
        if self.current_constraint == ConstraintType.NONE:
            return matrix
        
        # 提取位置
        location = matrix.to_translation()
        
        # 應用約束到位置
        constrained_location = self.apply_constraint(location)
        
        # 重建變換矩陣
        rotation = matrix.to_quaternion()
        scale = matrix.to_scale()
        
        constrained_matrix = Matrix.LocRotScale(constrained_location, rotation, scale)
        
        return constrained_matrix
    
    def set_reference_system(self, reference_system):
        """設置參考系統"""
        self.reference_system = reference_system
        
        # 重新創建約束對象
        if self.current_constraint != ConstraintType.NONE:
            # 這需要 context 參數，暫時跳過
            pass
    
    def set_temp_pivot(self, pivot):
        """設置臨時支點"""
        self.temp_pivot = pivot
        
        # 重新創建約束對象
        if self.current_constraint != ConstraintType.NONE:
            # 這需要 context 參數，暫時跳過
            pass
    
    def set_custom_reference_matrix(self, matrix):
        """設置自定義參考矩陣"""
        self.custom_reference_matrix = matrix
        
        # 重新創建約束對象
        if self.current_constraint != ConstraintType.NONE:
            # 這需要 context 參數，暫時跳過
            pass
    
    def clear_constraint(self):
        """清除約束"""
        self.current_constraint = ConstraintType.NONE
        self.constraint_plane = None
        self.constraint_axis = None
        self.constraint_edge = None
        self.constraint_face = None
    
    def get_constraint_info(self):
        """獲取約束信息"""
        info = {
            "type": self.current_constraint.value,
            "reference_system": self.reference_system.value,
            "has_temp_pivot": self.temp_pivot is not None,
            "has_custom_reference": self.custom_reference_matrix is not None,
        }
        
        if self.constraint_plane:
            info.update({
                "plane_origin": self.constraint_plane.origin,
                "plane_normal": self.constraint_plane.normal,
            })
        
        if self.constraint_axis:
            info.update({
                "axis_origin": self.constraint_axis.origin,
                "axis_direction": self.constraint_axis.direction,
            })
        
        return info
    
    def is_constrained(self):
        """檢查是否有約束"""
        return self.current_constraint != ConstraintType.NONE
    
    def get_constraint_visual_data(self):
        """獲取約束可視化數據"""
        visual_data = []
        
        if self.constraint_plane:
            # 創建平面可視化（網格）
            visual_data.append(self._create_plane_visual(self.constraint_plane))
        
        if self.constraint_axis:
            # 創建軸可視化（線條）
            visual_data.append(self._create_axis_visual(self.constraint_axis))
        
        if self.constraint_edge:
            # 創建邊緣可視化（線條）
            visual_data.append(self._create_axis_visual(self.constraint_edge))
        
        if self.constraint_face:
            # 創建面可視化（網格）
            visual_data.append(self._create_plane_visual(self.constraint_face))
        
        return visual_data
    
    def _create_plane_visual(self, plane):
        """創建平面可視化數據"""
        size = 2.0  # 平面大小
        
        # 創建平面上的四個點
        # 需要兩個與平面法線垂直的向量
        if abs(plane.normal.z) < 0.9:
            up = Vector((0, 0, 1))
        else:
            up = Vector((1, 0, 0))
        
        right = plane.normal.cross(up).normalized()
        forward = right.cross(plane.normal).normalized()
        
        # 四個角點
        corners = [
            plane.origin + right * size + forward * size,
            plane.origin + right * size - forward * size,
            plane.origin - right * size - forward * size,
            plane.origin - right * size + forward * size,
        ]
        
        return {
            "type": "PLANE",
            "vertices": corners,
            "color": (0.2, 0.8, 0.2, 0.3),
            "normal": plane.normal,
        }
    
    def _create_axis_visual(self, axis):
        """創建軸可視化數據"""
        length = 2.0  # 軸長度
        
        # 軸的兩個端點
        start = axis.origin - axis.direction * length
        end = axis.origin + axis.direction * length
        
        return {
            "type": "AXIS",
            "vertices": [start, end],
            "color": (0.8, 0.2, 0.2, 0.8),
            "direction": axis.direction,
        }


# 全域約束平面系統實例
constraint_plane_system = ConstraintPlaneSystem()


def set_constraint_mode(constraint_type, context=None):
    """設置約束模式 - 供外部調用"""
    constraint_plane_system.set_constraint_mode(constraint_type, context)


def apply_constraint_to_point(point):
    """應用約束到點 - 供外部調用"""
    return constraint_plane_system.apply_constraint(point)


def apply_constraint_to_transform(matrix):
    """應用約束到變換矩陣 - 供外部調用"""
    return constraint_plane_system.apply_constraint_to_transform(matrix)


def set_reference_system(reference_system):
    """設置參考系統 - 供外部調用"""
    constraint_plane_system.set_reference_system(reference_system)


def set_temp_pivot(pivot):
    """設置臨時支點 - 供外部調用"""
    constraint_plane_system.set_temp_pivot(pivot)


def clear_constraint():
    """清除約束 - 供外部調用"""
    constraint_plane_system.clear_constraint()


def get_constraint_info():
    """獲取約束信息 - 供外部調用"""
    return constraint_plane_system.get_constraint_info()


def get_constraint_visual_data():
    """獲取約束可視化數據 - 供外部調用"""
    return constraint_plane_system.get_constraint_visual_data()


def is_constrained():
    """檢查是否有約束 - 供外部調用"""
    return constraint_plane_system.is_constrained


# ============================================================================
# v7.4 新增：ConstraintDomain - Solver Domain Builder
# ============================================================================

class ConstraintDomain:
    """
    約束域 - 定義 solver 可運算的空間範圍
    
    v7.4 核心升級：讓所有 solver 都在 constraint domain 內運作
    而不是先算完再投影
    """
    
    def __init__(self):
        # 軸鎖定
        self.axis_lock: Optional[ConstraintType] = None
        self.locked_axis: List[str] = []  # 被鎖定的軸 ['X', 'Y', 'Z']
        
        # 平面鎖定
        self.plane_lock: Optional[ConstraintType] = None
        self.locked_planes: List[str] = []  # 被鎖定的平面 ['XY', 'XZ', 'YZ']
        
        # 參考座標系
        self.reference_space: ReferenceSystem = ReferenceSystem.WORLD
        self.reference_matrix: Optional[Matrix] = None
        
        # 約束平面/軸定義
        self.constraint_plane: Optional[ConstraintPlane] = None
        self.constraint_axis: Optional[Vector] = None
        
        # 支點
        self.pivot_point: Optional[Vector] = None
        
        # 是否啟用
        self.is_active: bool = False
        
    def setup_axis_lock(self, axis: str, context: bpy.types.Context = None):
        """設置軸鎖定"""
        axis = axis.upper()
        if axis in ['X', 'Y', 'Z']:
            self.locked_axis.append(axis)
            self.axis_lock = ConstraintType[f"AXIS_{axis}"]
            self.is_active = True
            
            # 設置約束軸方向
            if context:
                if self.reference_space == ReferenceSystem.WORLD:
                    self.constraint_axis = Vector((1, 0, 0)) if axis == 'X' else \
                                         Vector((0, 1, 0)) if axis == 'Y' else \
                                         Vector((0, 0, 1))
                else:
                    # 本地座標系需要參考物件的矩陣
                    active_obj = context.active_object
                    if active_obj:
                        local_axis = Vector((1, 0, 0)) if axis == 'X' else \
                                    Vector((0, 1, 0)) if axis == 'Y' else \
                                    Vector((0, 0, 1))
                        self.constraint_axis = active_obj.matrix_world.to_3x3() @ local_axis
                        
    def setup_plane_lock(self, plane: str, context: bpy.types.Context = None):
        """設置平面鎖定"""
        plane = plane.upper()
        if plane in ['XY', 'XZ', 'YZ', 'ZX', 'YX', 'ZY']:
            # 標準化平面名稱
            if plane in ['ZX']:
                plane = 'XZ'
            elif plane in ['YX']:
                plane = 'XY'
            elif plane in ['ZY']:
                plane = 'YZ'
                
            self.locked_planes.append(plane)
            self.plane_lock = ConstraintType[f"PLANE_{plane}"]
            self.is_active = True
            
            # 設置約束平面法線
            if plane == 'XY':
                normal = Vector((0, 0, 1))
            elif plane == 'XZ':
                normal = Vector((0, 1, 0))
            else:  # YZ
                normal = Vector((1, 0, 0))
                
            if context and self.reference_space != ReferenceSystem.WORLD:
                active_obj = context.active_object
                if active_obj:
                    normal = active_obj.matrix_world.to_3x3() @ normal
                    
            self.constraint_plane = ConstraintPlane(
                origin=self.pivot_point or Vector((0, 0, 0)),
                normal=normal,
                constraint_type=self.plane_lock
            )
            
    def project_vector(self, vector: Vector) -> Vector:
        """將向量投影到約束域內"""
        if not self.is_active:
            return vector
            
        result = vector.copy()
        
        # 如果有平面鎖定，投影到平面
        if self.constraint_plane and self.constraint_plane.is_active:
            result = self.constraint_plane.project_vector(result)
            
        # 如果有軸鎖定，只保留該軸分量
        if self.constraint_axis:
            axis_dir = self.constraint_axis.normalized()
            result = axis_dir * result.dot(axis_dir)
            
        return result
        
    def project_point(self, point: Vector) -> Vector:
        """將點投影到約束域內"""
        if not self.is_active:
            return point
            
        result = point.copy()
        
        # 如果有平面鎖定，投影到平面
        if self.constraint_plane and self.constraint_plane.is_active:
            result = self.constraint_plane.project_point(result)
            
        return result
        
    def clamp_transform(self, transform: Matrix, original: Matrix) -> Matrix:
        """限制變換矩陣在約束域內"""
        if not self.is_active:
            return transform
            
        result = transform.copy()
        
        # 如果有軸鎖定
        if self.locked_axis:
            for axis in self.locked_axis:
                if axis == 'X':
                    # 只保留 X 位移
                    result.translation.y = original.translation.y
                    result.translation.z = original.translation.z
                elif axis == 'Y':
                    # 只保留 Y 位移
                    result.translation.x = original.translation.x
                    result.translation.z = original.translation.z
                elif axis == 'Z':
                    # 只保留 Z 位移
                    result.translation.x = original.translation.x
                    result.translation.y = original.translation.y
                    
        return result
        
    def set_reference_space(self, space: ReferenceSystem, context: bpy.types.Context = None):
        """設置參考座標系"""
        self.reference_space = space
        
        if context and space == ReferenceSystem.LOCAL:
            active_obj = context.active_object
            if active_obj:
                self.reference_matrix = active_obj.matrix_world.copy()
                
    def set_pivot(self, pivot: Vector):
        """設置支點"""
        self.pivot_point = pivot.copy()
        if self.constraint_plane:
            self.constraint_plane.origin = self.pivot_point
            
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典（供序列化）"""
        return {
            "is_active": self.is_active,
            "axis_lock": self.axis_lock.value if self.axis_lock else None,
            "plane_lock": self.plane_lock.value if self.plane_lock else None,
            "reference_space": self.reference_space.value,
            "locked_axis": self.locked_axis,
            "locked_planes": self.locked_planes,
            "has_pivot": self.pivot_point is not None,
        }


def build_constraint_domain(context: bpy.types.Context, 
                            candidate: Dict[str, Any] = None) -> ConstraintDomain:
    """
    建立約束域
    
    v7.4: 根據當前上下文和候選點建立約束域
    
    Args:
        context: Blender 上下文
        candidate: 可選的候選點資訊
        
    Returns:
        ConstraintDomain: 建立的約束域
    """
    domain = ConstraintDomain()
    
    # 從場景設置獲取約束資訊
    scene = context.scene
    
    # 檢查是否有軸鎖定
    # 假設這些屬性存在於場景或工具設置中
    if hasattr(scene, 'smart_align_axis_lock'):
        axis_lock = scene.smart_align_axis_lock
        if axis_lock and axis_lock != 'NONE':
            domain.setup_axis_lock(axis_lock, context)
            
    # 檢查是否有平面鎖定
    if hasattr(scene, 'smart_align_plane_lock'):
        plane_lock = scene.smart_align_plane_lock
        if plane_lock and plane_lock != 'NONE':
            domain.setup_plane_lock(plane_lock, context)
            
    # 設置參考座標系
    # 從變換方向槽獲取
    if context.space_data and hasattr(context.space_data, 'transform_orientation_slots'):
        orient_slot = context.space_data.transform_orientation_slots[0]
        if orient_slot.type == 'LOCAL':
            domain.set_reference_space(ReferenceSystem.LOCAL, context)
        elif orient_slot.type == 'GLOBAL':
            domain.set_reference_space(ReferenceSystem.WORLD)
        elif orient_slot.type == 'VIEW':
            domain.set_reference_space(ReferenceSystem.VIEW)
            
    # 從候選點設置支點
    if candidate and 'position' in candidate:
        domain.set_pivot(candidate['position'])
        
    return domain


# ============================================================================
# 約束平面擴展方法
# ============================================================================

def project_vector_to_constraint(self, vector: Vector) -> Vector:
    """將向量投影到約束平面（ConstraintPlane 的方法）"""
    if not self.is_active:
        return vector
        
    # 計算向量在平面的投影
    # V_parallel = V - (V·N) * N
    dot_product = vector.dot(self.normal)
    return vector - self.normal * dot_product

# 添加方法到 ConstraintPlane 類
ConstraintPlane.project_vector = project_vector_to_constraint
