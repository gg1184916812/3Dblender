"""
Smart Align Pro - Coordinate Space Solver
實現 CAD Transform 級別的坐標空間變換管道
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion, Euler
from enum import Enum
from typing import Optional, Dict, Any, Tuple, List


class CoordinateSpaceType(Enum):
    """坐標空間類型枚舉"""
    GLOBAL = "GLOBAL"
    LOCAL = "LOCAL"
    ACTIVE_OBJECT = "ACTIVE_OBJECT"
    SURFACE_TANGENT = "SURFACE_TANGENT"
    FACE_NORMAL = "FACE_NORMAL"
    EDGE_DIRECTION = "EDGE_DIRECTION"
    CUSTOM_THREE_POINT = "CUSTOM_THREE_POINT"
    VIEW = "VIEW"
    CURSOR = "CURSOR"


class CoordinateSpace:
    """坐標空間類別"""
    
    def __init__(self, space_type: CoordinateSpaceType, context=None):
        self.space_type = space_type
        self.context = context
        self.transform_matrix = Matrix.Identity(4)
        self.inverse_matrix = Matrix.Identity(4)
        self.origin = Vector((0, 0, 0))
        self.axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
        
        # 根據空間類型初始化
        self._initialize_space()
    
    def _initialize_space(self):
        """初始化坐標空間"""
        if self.space_type == CoordinateSpaceType.GLOBAL:
            self._initialize_global_space()
        elif self.space_type == CoordinateSpaceType.LOCAL:
            self._initialize_local_space()
        elif self.space_type == CoordinateSpaceType.ACTIVE_OBJECT:
            self._initialize_active_object_space()
        elif self.space_type == CoordinateSpaceType.SURFACE_TANGENT:
            self._initialize_surface_tangent_space()
        elif self.space_type == CoordinateSpaceType.FACE_NORMAL:
            self._initialize_face_normal_space()
        elif self.space_type == CoordinateSpaceType.EDGE_DIRECTION:
            self._initialize_edge_direction_space()
        elif self.space_type == CoordinateSpaceType.CUSTOM_THREE_POINT:
            self._initialize_custom_three_point_space()
        elif self.space_type == CoordinateSpaceType.VIEW:
            self._initialize_view_space()
        elif self.space_type == CoordinateSpaceType.CURSOR:
            self._initialize_cursor_space()
    
    def _initialize_global_space(self):
        """初始化世界坐標空間"""
        self.transform_matrix = Matrix.Identity(4)
        self.inverse_matrix = Matrix.Identity(4)
        self.origin = Vector((0, 0, 0))
        self.axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    
    def _initialize_local_space(self):
        """初始化本地坐標空間"""
        if self.context and self.context.active_object:
            obj = self.context.active_object
            self.transform_matrix = obj.matrix_world
            self.inverse_matrix = obj.matrix_world.inverted()
            self.origin = obj.matrix_world.translation
            self.axes = [
                obj.matrix_world.to_3x3() @ Vector((1, 0, 0)),
                obj.matrix_world.to_3x3() @ Vector((0, 1, 0)),
                obj.matrix_world.to_3x3() @ Vector((0, 0, 1))
            ]
    
    def _initialize_active_object_space(self):
        """初始化活動物件坐標空間"""
        if self.context and self.context.active_object:
            obj = self.context.active_object
            self.transform_matrix = obj.matrix_world
            self.inverse_matrix = obj.matrix_world.inverted()
            self.origin = obj.matrix_world.translation
            self.axes = [
                obj.matrix_world.to_3x3() @ Vector((1, 0, 0)),
                obj.matrix_world.to_3x3() @ Vector((0, 1, 0)),
                obj.matrix_world.to_3x3() @ Vector((0, 0, 1))
            ]
    
    def _initialize_surface_tangent_space(self):
        """初始化表面切線坐標空間"""
        if self.context and self.context.active_object:
            obj = self.context.active_object
            
            # 獲取物件的邊界框中心作為參考點
            from ..utils.bbox_utils import get_bbox_center_world
            bbox_center = get_bbox_center_world(obj)
            
            # 假設 Z 軸為法線方向，X 和 Y 為切線方向
            # 這裡可以根據具體的表面點來計算更精確的切線空間
            normal = Vector((0, 0, 1))  # 默認向上
            
            # 計算切線向量
            if abs(normal.z) < 0.9:
                tangent_x = normal.cross(Vector((0, 0, 1))).normalized()
            else:
                tangent_x = normal.cross(Vector((1, 0, 0))).normalized()
            
            tangent_y = normal.cross(tangent_x).normalized()
            
            self.origin = bbox_center
            self.axes = [tangent_x, tangent_y, normal]
            
            # 構建變換矩陣
            self.transform_matrix = Matrix.Identity(4)
            self.transform_matrix.translation = self.origin
            self.transform_matrix[0][0:3] = tangent_x
            self.transform_matrix[1][0:3] = tangent_y
            self.transform_matrix[2][0:3] = normal
            
            self.inverse_matrix = self.transform_matrix.inverted()
    
    def _initialize_face_normal_space(self):
        """初始化面法線坐標空間"""
        # 這需要基於具體的面來計算
        # 暫時使用默認值
        self._initialize_global_space()
    
    def _initialize_edge_direction_space(self):
        """初始化邊緣方向坐標空間"""
        # 這需要基於具體的邊緣來計算
        # 暫時使用默認值
        self._initialize_global_space()
    
    def _initialize_custom_three_point_space(self):
        """初始化自定義三點坐標空間"""
        # 這需要基於三個點來計算
        # 暫時使用默認值
        self._initialize_global_space()
    
    def _initialize_view_space(self):
        """初始化視圖坐標空間"""
        if self.context and self.context.space_data and self.context.space_data.region_3d:
            view_matrix = self.context.space_data.region_3d.view_matrix
            self.transform_matrix = view_matrix.inverted()
            self.inverse_matrix = view_matrix
            self.origin = self.transform_matrix.translation
            self.axes = [
                self.transform_matrix.to_3x3() @ Vector((1, 0, 0)),
                self.transform_matrix.to_3x3() @ Vector((0, 1, 0)),
                self.transform_matrix.to_3x3() @ Vector((0, 0, 1))
            ]
    
    def _initialize_cursor_space(self):
        """初始化游標坐標空間"""
        if self.context and self.context.scene:
            cursor_location = self.context.scene.cursor.location
            self.transform_matrix = Matrix.Translation(cursor_location)
            self.inverse_matrix = Matrix.Translation(-cursor_location)
            self.origin = cursor_location
            self.axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    
    def transform_point(self, point: Vector, to_space: bool = True) -> Vector:
        """變換點到/從坐標空間"""
        if to_space:
            return self.inverse_matrix @ point
        else:
            return self.transform_matrix @ point
    
    def transform_vector(self, vector: Vector, to_space: bool = True) -> Vector:
        """變換向量到/從坐標空間"""
        if to_space:
            return self.inverse_matrix.to_3x3() @ vector
        else:
            return self.transform_matrix.to_3x3() @ vector
    
    def transform_matrix(self, matrix: Matrix, to_space: bool = True) -> Matrix:
        """變換矩陣到/從坐標空間"""
        if to_space:
            return self.inverse_matrix @ matrix @ self.transform_matrix
        else:
            return self.transform_matrix @ matrix @ self.inverse_matrix
    
    def get_axis_direction(self, axis_index: int) -> Vector:
        """獲取軸向方向"""
        if 0 <= axis_index < 3:
            return self.axes[axis_index]
        return Vector((0, 0, 0))
    
    def get_plane_normal(self, plane_index: int) -> Vector:
        """獲取平面法線"""
        plane_normals = [
            self.axes[2],  # XY 平面法線 = Z 軸
            self.axes[1],  # XZ 平面法線 = Y 軸
            self.axes[0],  # YZ 平面法線 = X 軸
        ]
        
        if 0 <= plane_index < 3:
            return plane_normals[plane_index]
        return Vector((0, 0, 0))
    
    def update_from_surface_point(self, point: Vector, normal: Vector):
        """從表面點和法線更新坐標空間"""
        self.origin = point
        
        # 計算切線向量
        if abs(normal.z) < 0.9:
            tangent_x = normal.cross(Vector((0, 0, 1))).normalized()
        else:
            tangent_x = normal.cross(Vector((1, 0, 0))).normalized()
        
        tangent_y = normal.cross(tangent_x).normalized()
        
        self.axes = [tangent_x, tangent_y, normal]
        
        # 重建變換矩陣
        self.transform_matrix = Matrix.Identity(4)
        self.transform_matrix.translation = self.origin
        self.transform_matrix[0][0:3] = tangent_x
        self.transform_matrix[1][0:3] = tangent_y
        self.transform_matrix[2][0:3] = normal
        
        self.inverse_matrix = self.transform_matrix.inverted()
    
    def update_from_three_points(self, point_a: Vector, point_b: Vector, point_c: Vector):
        """從三個點更新坐標空間"""
        self.origin = point_a
        
        # 計算兩個向量
        vec_ab = (point_b - point_a).normalized()
        vec_ac = (point_c - point_a).normalized()
        
        # 計算法線
        normal = vec_ab.cross(vec_ac).normalized()
        
        # 計算第二個切線
        tangent_y = normal.cross(vec_ab).normalized()
        
        self.axes = [vec_ab, tangent_y, normal]
        
        # 重建變換矩陣
        self.transform_matrix = Matrix.Identity(4)
        self.transform_matrix.translation = self.origin
        self.transform_matrix[0][0:3] = vec_ab
        self.transform_matrix[1][0:3] = tangent_y
        self.transform_matrix[2][0:3] = normal
        
        self.inverse_matrix = self.transform_matrix.inverted()
    
    def update_from_edge(self, edge_start: Vector, edge_end: Vector):
        """從邊緣更新坐標空間"""
        self.origin = edge_start
        
        # 計算邊緣方向
        edge_direction = (edge_end - edge_start).normalized()
        
        # 計算垂直向量
        if abs(edge_direction.z) < 0.9:
            perpendicular = edge_direction.cross(Vector((0, 0, 1))).normalized()
        else:
            perpendicular = edge_direction.cross(Vector((1, 0, 0))).normalized()
        
        # 計算法線
        normal = edge_direction.cross(perpendicular).normalized()
        
        self.axes = [edge_direction, perpendicular, normal]
        
        # 重建變換矩陣
        self.transform_matrix = Matrix.Identity(4)
        self.transform_matrix.translation = self.origin
        self.transform_matrix[0][0:3] = edge_direction
        self.transform_matrix[1][0:3] = perpendicular
        self.transform_matrix[2][0:3] = normal
        
        self.inverse_matrix = self.transform_matrix.inverted()
    
    def get_space_info(self) -> Dict[str, Any]:
        """獲取坐標空間信息"""
        return {
            "type": self.space_type.value,
            "origin": self.origin,
            "axes": self.axes,
            "transform_matrix": self.transform_matrix,
            "inverse_matrix": self.inverse_matrix
        }


class CoordinateSpaceSolver:
    """坐標空間求解器 - CAD Transform 級別的坐標空間變換管道"""
    
    def __init__(self):
        self.current_space = CoordinateSpaceType.GLOBAL
        self.source_space = None
        self.target_space = None
        self.context = None
        
        # 坐標空間緩存
        self.space_cache: Dict[str, CoordinateSpace] = {}
        
        # 變換歷史
        self.transform_history: List[Dict[str, Any]] = []
    
    def set_context(self, context):
        """設置上下文"""
        self.context = context
        # 清除緩存，因為上下文可能已改變
        self.space_cache.clear()
    
    def get_coordinate_space(self, space_type: CoordinateSpaceType) -> CoordinateSpace:
        """獲取坐標空間"""
        cache_key = space_type.value
        
        if cache_key not in self.space_cache:
            self.space_cache[cache_key] = CoordinateSpace(space_type, self.context)
        
        return self.space_cache[cache_key]
    
    def transform_point_between_spaces(self, point: Vector, 
                                    from_space: CoordinateSpaceType,
                                    to_space: CoordinateSpaceType) -> Vector:
        """在兩個坐標空間之間變換點"""
        # 獲取源坐標空間
        source_space = self.get_coordinate_space(from_space)
        
        # 變換到世界坐標
        world_point = source_space.transform_point(point, to_space=False)
        
        # 獲取目標坐標空間
        target_space = self.get_coordinate_space(to_space)
        
        # 變換到目標坐標
        target_point = target_space.transform_point(world_point, to_space=True)
        
        return target_point
    
    def transform_vector_between_spaces(self, vector: Vector,
                                    from_space: CoordinateSpaceType,
                                    to_space: CoordinateSpaceType) -> Vector:
        """在兩個坐標空間之間變換向量"""
        # 獲取源坐標空間
        source_space = self.get_coordinate_space(from_space)
        
        # 變換到世界坐標
        world_vector = source_space.transform_vector(vector, to_space=False)
        
        # 獲取目標坐標空間
        target_space = self.get_coordinate_space(to_space)
        
        # 變換到目標坐標
        target_vector = target_space.transform_vector(world_vector, to_space=True)
        
        return target_vector
    
    def transform_matrix_between_spaces(self, matrix: Matrix,
                                   from_space: CoordinateSpaceType,
                                   to_space: CoordinateSpaceType) -> Matrix:
        """在兩個坐標空間之間變換矩陣"""
        # 獲取源坐標空間
        source_space = self.get_coordinate_space(from_space)
        
        # 變換到世界坐標
        world_matrix = source_space.transform_matrix(matrix, to_space=False)
        
        # 獲取目標坐標空間
        target_space = self.get_coordinate_space(to_space)
        
        # 變換到目標坐標
        target_matrix = target_space.transform_matrix(world_matrix, to_space=True)
        
        return target_matrix
    
    def create_surface_space(self, point: Vector, normal: Vector) -> CoordinateSpace:
        """創建表面坐標空間"""
        space = CoordinateSpace(CoordinateSpaceType.SURFACE_TANGENT, self.context)
        space.update_from_surface_point(point, normal)
        return space
    
    def create_three_point_space(self, point_a: Vector, point_b: Vector, point_c: Vector) -> CoordinateSpace:
        """創建三點坐標空間"""
        space = CoordinateSpace(CoordinateSpaceType.CUSTOM_THREE_POINT, self.context)
        space.update_from_three_points(point_a, point_b, point_c)
        return space
    
    def create_edge_space(self, edge_start: Vector, edge_end: Vector) -> CoordinateSpace:
        """創建邊緣坐標空間"""
        space = CoordinateSpace(CoordinateSpaceType.EDGE_DIRECTION, self.context)
        space.update_from_edge(edge_start, edge_end)
        return space
    
    def apply_constraint_in_space(self, point: Vector, 
                               constraint_type: str,
                               space_type: CoordinateSpaceType) -> Vector:
        """在指定坐標空間中應用約束"""
        # 獲取坐標空間
        space = self.get_coordinate_space(space_type)
        
        # 變換點到坐標空間
        local_point = space.transform_point(point, to_space=True)
        
        # 應用約束
        if constraint_type == "AXIS_X":
            local_point.y = 0
            local_point.z = 0
        elif constraint_type == "AXIS_Y":
            local_point.x = 0
            local_point.z = 0
        elif constraint_type == "AXIS_Z":
            local_point.x = 0
            local_point.y = 0
        elif constraint_type == "PLANE_XY":
            local_point.z = 0
        elif constraint_type == "PLANE_XZ":
            local_point.y = 0
        elif constraint_type == "PLANE_YZ":
            local_point.x = 0
        
        # 變換回世界坐標
        world_point = space.transform_point(local_point, to_space=False)
        
        return world_point
    
    def get_space_visualization_data(self, space_type: CoordinateSpaceType) -> Dict[str, Any]:
        """獲取坐標空間可視化數據"""
        space = self.get_coordinate_space(space_type)
        
        # 創建坐標軸線
        axis_length = 1.0
        axes_data = []
        
        colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]  # X=紅, Y=綠, Z=藍
        
        for i, (axis, color) in enumerate(zip(space.axes, colors)):
            start = space.origin
            end = space.origin + axis * axis_length
            axes_data.append({
                "start": start,
                "end": end,
                "color": color,
                "axis": f"{'XYZ'[i]}"
            })
        
        # 創建平面網格
        plane_data = []
        plane_size = 0.5
        
        # XY 平面
        xy_corners = [
            space.origin + space.axes[0] * plane_size + space.axes[1] * plane_size,
            space.origin + space.axes[0] * plane_size - space.axes[1] * plane_size,
            space.origin - space.axes[0] * plane_size - space.axes[1] * plane_size,
            space.origin - space.axes[0] * plane_size + space.axes[1] * plane_size,
        ]
        plane_data.append({
            "corners": xy_corners,
            "normal": space.axes[2],
            "color": (0.2, 0.2, 0.8, 0.3),
            "plane": "XY"
        })
        
        return {
            "origin": space.origin,
            "axes": axes_data,
            "planes": plane_data,
            "type": space_type.value
        }
    
    def record_transform(self, from_space: CoordinateSpaceType, 
                       to_space: CoordinateSpaceType,
                       transform_data: Dict[str, Any]):
        """記錄變換歷史"""
        import time
        
        self.transform_history.append({
            "timestamp": time.time(),
            "from_space": from_space.value,
            "to_space": to_space.value,
            "transform_data": transform_data
        })
        
        # 限制歷史記錄長度
        if len(self.transform_history) > 100:
            self.transform_history.pop(0)
    
    def get_transform_history(self) -> List[Dict[str, Any]]:
        """獲取變換歷史"""
        return self.transform_history.copy()
    
    def clear_cache(self):
        """清除坐標空間緩存"""
        self.space_cache.clear()
    
    def get_available_spaces(self) -> List[Dict[str, Any]]:
        """獲取可用的坐標空間列表"""
        spaces = []
        
        for space_type in CoordinateSpaceType:
            space_info = {
                "type": space_type.value,
                "name": self._get_space_display_name(space_type),
                "description": self._get_space_description(space_type)
            }
            spaces.append(space_info)
        
        return spaces
    
    def _get_space_display_name(self, space_type: CoordinateSpaceType) -> str:
        """獲取坐標空間顯示名稱"""
        names = {
            CoordinateSpaceType.GLOBAL: "世界坐標",
            CoordinateSpaceType.LOCAL: "本地坐標",
            CoordinateSpaceType.ACTIVE_OBJECT: "活動物件",
            CoordinateSpaceType.SURFACE_TANGENT: "表面切線",
            CoordinateSpaceType.FACE_NORMAL: "面法線",
            CoordinateSpaceType.EDGE_DIRECTION: "邊緣方向",
            CoordinateSpaceType.CUSTOM_THREE_POINT: "自定義三點",
            CoordinateSpaceType.VIEW: "視圖坐標",
            CoordinateSpaceType.CURSOR: "游標坐標"
        }
        return names.get(space_type, space_type.value)
    
    def _get_space_description(self, space_type: CoordinateSpaceType) -> str:
        """獲取坐標空間描述"""
        descriptions = {
            CoordinateSpaceType.GLOBAL: "使用 Blender 的世界坐標系",
            CoordinateSpaceType.LOCAL: "使用物件的本地坐標系",
            CoordinateSpaceType.ACTIVE_OBJECT: "使用活動物件的坐標系",
            CoordinateSpaceType.SURFACE_TANGENT: "基於表面切線的坐標系",
            CoordinateSpaceType.FACE_NORMAL: "基於面法線的坐標系",
            CoordinateSpaceType.EDGE_DIRECTION: "基於邊緣方向的坐標系",
            CoordinateSpaceType.CUSTOM_THREE_POINT: "基於三個點定義的坐標系",
            CoordinateSpaceType.VIEW: "使用當前視圖的坐標系",
            CoordinateSpaceType.CURSOR: "以 3D 游標為原點的坐標系"
        }
        return descriptions.get(space_type, "未知坐標空間")


# 全域坐標空間求解器實例
coordinate_space_solver = CoordinateSpaceSolver()


def get_coordinate_space_solver() -> CoordinateSpaceSolver:
    """獲取坐標空間求解器實例"""
    return coordinate_space_solver


def transform_point_between_spaces(point: Vector, 
                               from_space: CoordinateSpaceType,
                               to_space: CoordinateSpaceType,
                               context=None) -> Vector:
    """在兩個坐標空間之間變換點 - 供外部調用"""
    if context:
        coordinate_space_solver.set_context(context)
    
    return coordinate_space_solver.transform_point_between_spaces(point, from_space, to_space)


def create_surface_space(point: Vector, normal: Vector, context=None) -> CoordinateSpace:
    """創建表面坐標空間 - 供外部調用"""
    if context:
        coordinate_space_solver.set_context(context)
    
    return coordinate_space_solver.create_surface_space(point, normal)


def create_three_point_space(point_a: Vector, point_b: Vector, point_c: Vector, 
                          context=None) -> CoordinateSpace:
    """創建三點坐標空間 - 供外部調用"""
    if context:
        coordinate_space_solver.set_context(context)
    
    return coordinate_space_solver.create_three_point_space(point_a, point_b, point_c)


def apply_constraint_in_space(point: Vector, constraint_type: str, 
                          space_type: CoordinateSpaceType, context=None) -> Vector:
    """在指定坐標空間中應用約束 - 供外部調用"""
    if context:
        coordinate_space_solver.set_context(context)
    
    return coordinate_space_solver.apply_constraint_in_space(point, constraint_type, space_type)


# ============================================================================
# v7.4 新增：ConstraintDomain 整合
# ============================================================================

def resolve_reference_space(domain) -> Optional[CoordinateSpaceType]:
    """
    從 ConstraintDomain 解析參考座標空間
    
    v7.4: 讓 coordinate_space_solver 讀取 constraint_domain 的參考空間
    
    Args:
        domain: ConstraintDomain 實例或包含 reference_space 的物件
        
    Returns:
        CoordinateSpaceType: 對應的座標空間類型
    """
    if domain is None:
        return CoordinateSpaceType.GLOBAL
    
    # 如果 domain 是 ConstraintDomain 實例
    if hasattr(domain, 'reference_space'):
        ref_space = domain.reference_space
        
        # 將 ConstraintPlaneSystem 的 ReferenceSystem 轉換為 CoordinateSpaceType
        try:
            from .constraint_plane_system import ReferenceSystem
            
            if ref_space == ReferenceSystem.WORLD:
                return CoordinateSpaceType.GLOBAL
            elif ref_space == ReferenceSystem.LOCAL:
                return CoordinateSpaceType.LOCAL
            elif ref_space == ReferenceSystem.VIEW:
                return CoordinateSpaceType.VIEW
            elif ref_space == ReferenceSystem.CUSTOM:
                return CoordinateSpaceType.CUSTOM_THREE_POINT
        except ImportError:
            pass
        
        # 如果 reference_space 已經是字串
        if isinstance(ref_space, str):
            ref_upper = ref_space.upper()
            if ref_upper in ['WORLD', 'GLOBAL']:
                return CoordinateSpaceType.GLOBAL
            elif ref_upper == 'LOCAL':
                return CoordinateSpaceType.LOCAL
            elif ref_upper == 'VIEW':
                return CoordinateSpaceType.VIEW
            elif ref_upper in ['CUSTOM', 'THREE_POINT']:
                return CoordinateSpaceType.CUSTOM_THREE_POINT
    
    # 預設回傳 GLOBAL
    return CoordinateSpaceType.GLOBAL


def create_space_from_domain(domain, context=None) -> Optional[CoordinateSpace]:
    """
    從 ConstraintDomain 創建 CoordinateSpace
    
    v7.4: 根據 constraint domain 的設定創建對應的座標空間
    
    Args:
        domain: ConstraintDomain 實例
        context: 可選的 Blender 上下文
        
    Returns:
        CoordinateSpace: 創建的座標空間
    """
    space_type = resolve_reference_space(domain)
    return CoordinateSpace(space_type, context)


def apply_domain_constraint_to_transform(transform: Matrix, 
                                         domain,
                                         original: Matrix = None) -> Matrix:
    """
    將 ConstraintDomain 的約束應用到變換矩陣
    
    v7.4: 整合 domain 的約束到座標變換
    
    Args:
        transform: 原始變換矩陣
        domain: ConstraintDomain 實例
        original: 原始矩陣（用於軸鎖定時保留其他軸的值）
        
    Returns:
        Matrix: 應用約束後的變換矩陣
    """
    if domain is None or not hasattr(domain, 'is_active'):
        return transform
    
    if not domain.is_active:
        return transform
    
    result = transform.copy()
    
    # 如果有 clamp_transform 方法，優先使用
    if hasattr(domain, 'clamp_transform') and original is not None:
        return domain.clamp_transform(transform, original)
    
    # 手動應用約束
    if hasattr(domain, 'locked_axis') and domain.locked_axis:
        if original is None:
            original = transform
            
        for axis in domain.locked_axis:
            axis = axis.upper()
            if axis == 'X':
                result.translation.y = original.translation.y
                result.translation.z = original.translation.z
            elif axis == 'Y':
                result.translation.x = original.translation.x
                result.translation.z = original.translation.z
            elif axis == 'Z':
                result.translation.x = original.translation.x
                result.translation.y = original.translation.y
    
    # 如果有平面約束，應用投影
    if hasattr(domain, 'project_point') and hasattr(domain, 'pivot_point'):
        if domain.pivot_point:
            # 將位移投影到約束平面
            displacement = result.translation - domain.pivot_point
            constrained_disp = domain.project_vector(displacement)
            result.translation = domain.pivot_point + constrained_disp
    
    return result
