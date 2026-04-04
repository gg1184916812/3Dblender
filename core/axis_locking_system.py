"""
Smart Align Pro - Axis Locking System
實現 CAD Transform 級別的軸鎖定系統
"""

import bpy
from mathutils import Vector, Matrix, Quaternion, Euler
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
import time


class AxisLockType(Enum):
    """軸鎖定類型枚舉"""
    NONE = "NONE"
    X = "X"
    Y = "Y"
    Z = "Z"
    XY = "XY"
    XZ = "XZ"
    YZ = "YZ"
    NORMAL = "NORMAL"
    TANGENT = "TANGENT"
    CUSTOM = "CUSTOM"


# ============================================================================
# v7.4 新增：軸來源與約束形式分離
# ============================================================================

class AxisSource(Enum):
    """軸來源枚舉 - v7.4"""
    WORLD = "WORLD"
    LOCAL = "LOCAL"
    VIEW = "VIEW"
    NORMAL = "NORMAL"
    TANGENT = "TANGENT"
    CUSTOM = "CUSTOM"


class AxisConstraintKind(Enum):
    """約束形式枚舉 - v7.4"""
    NONE = "NONE"
    SINGLE_AXIS = "SINGLE_AXIS"
    PLANE = "PLANE"


class AxisLockState:
    """軸鎖定狀態類別 - v7.4 升級"""
    def __init__(self):
        self.lock_type = AxisLockType.NONE
        self.lock_axis = Vector((1, 0, 0))
        self.lock_plane_normal = Vector((0, 0, 1))
        self.reference_point = None
        self.is_active = False
        self.lock_strength = 1.0
        self.soft_lock = False
        
        # v7.4 新增：軸來源與約束形式分離
        self.axis_source = AxisSource.WORLD
        self.constraint_kind = AxisConstraintKind.NONE
        self.axis_name = None  # X, Y, Z, VIEW_LEFT_RIGHT, etc.
        self.view_axis_name = None  # VIEW_LEFT_RIGHT, VIEW_UP_DOWN, etc.
        self.coordinate_space = "WORLD"
        
        # 歷史記錄
        self.lock_history = []
        self.max_history = 20


class AxisLockingSystem:
    """軸鎖定系統 - CAD Transform 級別的軸鎖定"""
    
    def __init__(self):
        self.current_lock = AxisLockState()
        self.context = None
        
        # 快捷鍵映射
        self.hotkey_map = {
            "X": AxisLockType.X,
            "Y": AxisLockType.Y,
            "Z": AxisLockType.Z,
            "SHIFT_X": AxisLockType.XY,
            "SHIFT_Y": AxisLockType.XZ,
            "SHIFT_Z": AxisLockType.YZ,
            "N": AxisLockType.NORMAL,
            "T": AxisLockType.TANGENT,
            "C": AxisLockType.CUSTOM,
            "NONE": AxisLockType.NONE,
        }
        
        # 軸向顏色
        self.axis_colors = {
            AxisLockType.X: (1.0, 0.2, 0.2, 0.8),  # 紅色
            AxisLockType.Y: (0.2, 1.0, 0.2, 0.8),  # 綠色
            AxisLockType.Z: (0.2, 0.2, 1.0, 0.8),  # 藍色
            AxisLockType.XY: (1.0, 1.0, 0.2, 0.8),  # 黃色
            AxisLockType.XZ: (1.0, 0.2, 1.0, 0.8),  # 紫色
            AxisLockType.YZ: (0.2, 1.0, 1.0, 0.8),  # 青色
            AxisLockType.NORMAL: (0.8, 0.8, 0.8, 0.8),  # 灰色
            AxisLockType.TANGENT: (1.0, 0.8, 0.2, 0.8),  # 橙色
            AxisLockType.CUSTOM: (0.8, 0.2, 0.8, 0.8),  # 粉色
        }
    
    def set_context(self, context):
        """設置上下文"""
        self.context = context
    
    def set_axis_lock(self, lock_type: AxisLockType, reference_point=None, custom_axis=None):
        """設置軸鎖定"""
        # 記錄歷史
        self._record_lock_state()
        
        # 更新鎖定狀態
        self.current_lock.lock_type = lock_type
        self.current_lock.is_active = (lock_type != AxisLockType.NONE)
        
        if reference_point:
            self.current_lock.reference_point = reference_point
        
        if custom_axis:
            self.current_lock.lock_axis = custom_axis.normalized()
        
        # 根據鎖定類型設置參數
        self._setup_lock_parameters(lock_type)
    
    def _setup_lock_parameters(self, lock_type: AxisLockType):
        """設置鎖定參數"""
        if lock_type == AxisLockType.X:
            self.current_lock.lock_axis = Vector((1, 0, 0))
            self.current_lock.lock_plane_normal = Vector((0, 0, 1))
            
        elif lock_type == AxisLockType.Y:
            self.current_lock.lock_axis = Vector((0, 1, 0))
            self.current_lock.lock_plane_normal = Vector((0, 0, 1))
            
        elif lock_type == AxisLockType.Z:
            self.current_lock.lock_axis = Vector((0, 0, 1))
            self.current_lock.lock_plane_normal = Vector((0, 0, 1))
            
        elif lock_type == AxisLockType.XY:
            self.current_lock.lock_axis = Vector((1, 0, 0))
            self.current_lock.lock_plane_normal = Vector((0, 0, 1))
            
        elif lock_type == AxisLockType.XZ:
            self.current_lock.lock_axis = Vector((1, 0, 0))
            self.current_lock.lock_plane_normal = Vector((0, 1, 0))
            
        elif lock_type == AxisLockType.YZ:
            self.current_lock.lock_axis = Vector((0, 1, 0))
            self.current_lock.lock_plane_normal = Vector((1, 0, 0))
            
        elif lock_type == AxisLockType.NORMAL:
            # 使用當前選擇面的法線
            if self.context and self.context.active_object:
                # 這裡可以獲取當前選擇面的法線
                self.current_lock.lock_plane_normal = Vector((0, 0, 1))
            else:
                self.current_lock.lock_plane_normal = Vector((0, 0, 1))
            
        elif lock_type == AxisLockType.TANGENT:
            # 使用當前選擇面的切線
            if self.context and self.context.active_object:
                # 這裡可以獲取當前選擇面的切線
                self.current_lock.lock_axis = Vector((1, 0, 0))
            else:
                self.current_lock.lock_axis = Vector((1, 0, 0))
    
    def apply_axis_lock(self, point: Vector, transform: Matrix = None) -> Vector:
        """應用軸鎖定到點"""
        if not self.current_lock.is_active:
            return point
        
        if self.current_lock.lock_type == AxisLockType.NONE:
            return point
        
        # 如果有參考點，使用參考點
        if self.current_lock.reference_point:
            return self._apply_lock_with_reference(point)
        
        # 否則使用全局鎖定
        return self._apply_global_lock(point, transform)
    
    def _apply_lock_with_reference(self, point: Vector) -> Vector:
        """使用參考點應用鎖定"""
        if not self.current_lock.reference_point:
            return point
        
        reference = self.current_lock.reference_point
        lock_type = self.current_lock.lock_type
        
        if lock_type in [AxisLockType.X, AxisLockType.Y, AxisLockType.Z]:
            # 單軸鎖定
            axis_index = {"X": 0, "Y": 1, "Z": 2}[lock_type.value]
            locked_point = Vector(point)
            locked_point[axis_index] = reference[axis_index]
            return locked_point
            
        elif lock_type in [AxisLockType.XY, AxisLockType.XZ, AxisLockType.YZ]:
            # 平面鎖定
            locked_axes = {"XY": [2], "XZ": [1], "YZ": [0]}[lock_type.value]
            locked_point = Vector(point)
            for axis in locked_axes:
                locked_point[axis] = reference[axis]
            return locked_point
        
        return point
    
    def _apply_global_lock(self, point: Vector, transform: Matrix = None) -> Vector:
        """應用全局鎖定"""
        lock_type = self.current_lock.lock_type
        
        if transform:
            # 在變換空間中應用鎖定
            local_point = transform.inverted() @ point
            locked_local_point = self._apply_lock_to_local_point(local_point)
            return transform @ locked_local_point
        else:
            # 在世界空間中應用鎖定
            return self._apply_lock_to_local_point(point)
    
    def _apply_lock_to_local_point(self, point: Vector) -> Vector:
        """在本地空間中應用鎖定"""
        lock_type = self.current_lock.lock_type
        
        if lock_type in [AxisLockType.X, AxisLockType.Y, AxisLockType.Z]:
            # 單軸鎖定
            axis_index = {"X": 0, "Y": 1, "Z": 2}[lock_type.value]
            locked_point = Vector(point)
            
            if self.current_lock.soft_lock:
                # 軟鎖定：部分限制
                locked_point[axis_index] = (
                    point[axis_index] * (1.0 - self.current_lock.lock_strength) +
                    locked_point[axis_index] * self.current_lock.lock_strength
                )
            else:
                # 硬鎖定：完全限制
                locked_point[axis_index] = 0  # 相對於原點
            
            return locked_point
            
        elif lock_type in [AxisLockType.XY, AxisLockType.XZ, AxisLockType.YZ]:
            # 平面鎖定
            locked_axes = {"XY": [2], "XZ": [1], "YZ": [0]}[lock_type.value]
            locked_point = Vector(point)
            
            if self.current_lock.soft_lock:
                # 軟鎖定
                for axis in locked_axes:
                    locked_point[axis] = (
                        point[axis] * (1.0 - self.current_lock.lock_strength) +
                        0 * self.current_lock.lock_strength
                    )
            else:
                # 硬鎖定
                for axis in locked_axes:
                    locked_point[axis] = 0
            
            return locked_point
        
        elif lock_type == AxisLockType.NORMAL:
            # 法線鎖定：投影到法線平面
            if self.current_lock.reference_point:
                normal = self.current_lock.lock_plane_normal
                to_point = point - self.current_lock.reference_point
                distance = to_point.dot(normal)
                return point - distance * normal
        
        elif lock_type == AxisLockType.TANGENT:
            # 切線鎖定：投影到切線方向
            if self.current_lock.reference_point:
                tangent = self.current_lock.lock_axis
                to_point = point - self.current_lock.reference_point
                projection_length = to_point.dot(tangent)
                return self.current_lock.reference_point + tangent * projection_length
        
        return point
    
    def apply_axis_lock_to_transform(self, transform: Matrix) -> Matrix:
        """應用軸鎖定到變換矩陣"""
        if not self.current_lock.is_active:
            return transform
        
        lock_type = self.current_lock.lock_type
        
        # 提取變換分量
        translation = transform.to_translation()
        rotation = transform.to_quaternion()
        scale = transform.to_scale()
        
        # 應用鎖定到平移
        locked_translation = self.apply_axis_lock(translation, transform)
        
        # 應用鎖定到旋轉（如果需要）
        locked_rotation = self._apply_lock_to_rotation(rotation)
        
        # 應用鎖定到縮放（如果需要）
        locked_scale = self._apply_lock_to_scale(scale)
        
        # 重建變換矩陣
        return Matrix.LocRotScale(locked_translation, locked_rotation, locked_scale)
    
    def _apply_lock_to_rotation(self, rotation: Quaternion) -> Quaternion:
        """應用鎖定到旋轉"""
        lock_type = self.current_lock.lock_type
        
        if lock_type in [AxisLockType.X, AxisLockType.Y, AxisLockType.Z]:
            # 單軸鎖定：只允許繞該軸旋轉
            axis_index = {"X": 0, "Y": 1, "Z": 2}[lock_type.value]
            
            # 將四元數轉換為歐拉角
            euler = rotation.to_euler()
            
            # 鎖定其他軸的旋轉
            for i in range(3):
                if i != axis_index:
                    euler[i] = 0
            
            return euler.to_quaternion()
        
        return rotation
    
    def _apply_lock_to_scale(self, scale: Vector) -> Vector:
        """應用鎖定到縮放"""
        lock_type = self.current_lock.lock_type
        
        if lock_type in [AxisLockType.X, AxisLockType.Y, AxisLockType.Z]:
            # 單軸鎖定：只允許該軸縮放
            axis_index = {"X": 0, "Y": 1, "Z": 2}[lock_type.value]
            
            locked_scale = Vector(scale)
            for i in range(3):
                if i != axis_index:
                    locked_scale[i] = 1.0
            
            return locked_scale
        
        elif lock_type in [AxisLockType.XY, AxisLockType.XZ, AxisLockType.YZ]:
            # 平面鎖定：只允許平面內縮放
            locked_axes = {"XY": [2], "XZ": [1], "YZ": [0]}[lock_type.value]
            
            locked_scale = Vector(scale)
            for axis in locked_axes:
                locked_scale[axis] = 1.0
            
            return locked_scale
        
        return scale
    
    def process_hotkey(self, hotkey: str, reference_point=None) -> bool:
        """處理快捷鍵"""
        if hotkey in self.hotkey_map:
            lock_type = self.hotkey_map[hotkey]
            self.set_axis_lock(lock_type, reference_point)
            return True
        return False
    
    def toggle_soft_lock(self):
        """切換軟鎖定模式"""
        self.current_lock.soft_lock = not self.current_lock.soft_lock
    
    def set_lock_strength(self, strength: float):
        """設置鎖定強度"""
        self.current_lock.lock_strength = max(0.0, min(1.0, strength))
    
    def get_lock_info(self) -> Dict[str, Any]:
        """獲取鎖定信息"""
        return {
            "lock_type": self.current_lock.lock_type.value,
            "is_active": self.current_lock.is_active,
            "reference_point": self.current_lock.reference_point,
            "lock_axis": self.current_lock.lock_axis,
            "lock_plane_normal": self.current_lock.lock_plane_normal,
            "lock_strength": self.current_lock.lock_strength,
            "soft_lock": self.current_lock.soft_lock,
        }
    
    def get_lock_visualization_data(self) -> Dict[str, Any]:
        """獲取鎖定可視化數據"""
        if not self.current_lock.is_active:
            return {}
        
        lock_type = self.current_lock.lock_type
        color = self.axis_colors.get(lock_type, (0.8, 0.8, 0.8, 0.8))
        
        visual_data = {
            "type": lock_type.value,
            "color": color,
            "reference_point": self.current_lock.reference_point,
        }
        
        if lock_type in [AxisLockType.X, AxisLockType.Y, AxisLockType.Z]:
            # 單軸鎖定可視化
            if self.current_lock.reference_point:
                # 繪製軸線
                axis = self.current_lock.lock_axis
                start = self.current_lock.reference_point
                end = start + axis * 2.0
                
                visual_data.update({
                    "visualization_type": "AXIS",
                    "start": start,
                    "end": end,
                })
        
        elif lock_type in [AxisLockType.XY, AxisLockType.XZ, AxisLockType.YZ]:
            # 平面鎖定可視化
            if self.current_lock.reference_point:
                # 繪製平面網格
                normal = self.current_lock.lock_plane_normal
                center = self.current_lock.reference_point
                size = 1.0
                
                # 創建平面四個角點
                if abs(normal.z) < 0.9:
                    right = Vector((0, 0, 1)).cross(normal).normalized()
                else:
                    right = Vector((1, 0, 0)).cross(normal).normalized()
                
                up = normal.cross(right).normalized()
                
                corners = [
                    center + right * size + up * size,
                    center + right * size - up * size,
                    center - right * size - up * size,
                    center - right * size + up * size,
                ]
                
                visual_data.update({
                    "visualization_type": "PLANE",
                    "corners": corners,
                    "normal": normal,
                })
        
        return visual_data
    
    def _record_lock_state(self):
        """記錄鎖定狀態"""
        import time
        
        state = {
            "timestamp": time.time(),
            "lock_type": self.current_lock.lock_type.value,
            "reference_point": self.current_lock.reference_point,
            "lock_axis": self.current_lock.lock_axis,
            "lock_plane_normal": self.current_lock.lock_plane_normal,
            "lock_strength": self.current_lock.lock_strength,
            "soft_lock": self.current_lock.soft_lock,
        }
        
        self.current_lock.lock_history.append(state)
        
        # 限制歷史記錄長度
        if len(self.current_lock.lock_history) > self.current_lock.max_history:
            self.current_lock.lock_history.pop(0)
    
    def undo_lock(self):
        """撤銷鎖定"""
        if len(self.current_lock.lock_history) > 1:
            self.current_lock.lock_history.pop()  # 移除當前狀態
            previous_state = self.current_lock.lock_history[-1]
            
            # 恢復到上一個狀態
            self.current_lock.lock_type = AxisLockType(previous_state["lock_type"])
            self.current_lock.reference_point = previous_state["reference_point"]
            self.current_lock.lock_axis = previous_state["lock_axis"]
            self.current_lock.lock_plane_normal = previous_state["lock_plane_normal"]
            self.current_lock.lock_strength = previous_state["lock_strength"]
            self.current_lock.soft_lock = previous_state["soft_lock"]
            self.current_lock.is_active = (self.current_lock.lock_type != AxisLockType.NONE)
    
    def clear_lock(self):
        """清除鎖定"""
        self._record_lock_state()
        self.current_lock.lock_type = AxisLockType.NONE
        self.current_lock.is_active = False
        self.current_lock.reference_point = None
    
    def get_lock_history(self) -> List[Dict[str, Any]]:
        """獲取鎖定歷史"""
        return self.current_lock.lock_history.copy()
    
    # ============================================================================
    # v7.4 新增：View Axis 支援方法
    # ============================================================================
    
    def set_view_axis_lock(self, axis_name: str, context=None):
        """
        設置 view axis 鎖定
        
        Args:
            axis_name: VIEW_LEFT_RIGHT, VIEW_UP_DOWN, VIEW_DEPTH
            context: Blender context
        """
        self._record_lock_state()
        
        self.current_lock.axis_source = AxisSource.VIEW
        self.current_lock.constraint_kind = AxisConstraintKind.SINGLE_AXIS
        self.current_lock.view_axis_name = axis_name
        self.current_lock.axis_name = axis_name
        self.current_lock.is_active = True
        
        # 根據 view axis 名稱設置 lock_type
        if "LEFT" in axis_name or "RIGHT" in axis_name:
            self.current_lock.lock_type = AxisLockType.CUSTOM
        elif "UP" in axis_name or "DOWN" in axis_name:
            self.current_lock.lock_type = AxisLockType.CUSTOM
        elif "DEPTH" in axis_name:
            self.current_lock.lock_type = AxisLockType.CUSTOM
        
        if context:
            self.set_context(context)
            # 從 view_axis_solver 獲取實際軸向量
            try:
                from .view_axis_solver import get_view_axis_vector
                axis_vec = get_view_axis_vector(context, axis_name)
                if axis_vec:
                    self.current_lock.lock_axis = axis_vec
            except ImportError:
                pass
    
    def set_view_plane_lock(self, plane_name: str, context=None):
        """
        設置 view plane 鎖定
        
        Args:
            plane_name: VIEW_PLANE, VIEW_HORIZONTAL_PLANE, VIEW_VERTICAL_PLANE
            context: Blender context
        """
        self._record_lock_state()
        
        self.current_lock.axis_source = AxisSource.VIEW
        self.current_lock.constraint_kind = AxisConstraintKind.PLANE
        self.current_lock.is_active = True
        
        if context:
            self.set_context(context)
            try:
                from .view_axis_solver import get_view_plane_normal
                normal = get_view_plane_normal(context, plane_name)
                if normal:
                    self.current_lock.lock_plane_normal = normal
            except ImportError:
                pass
    
    def get_effective_axis_vector(self, context=None) -> Vector:
        """
        獲取有效的軸向量（考慮軸來源）
        
        Returns:
            Vector: 世界空間中的軸向量
        """
        if not self.current_lock.is_active:
            return Vector((1, 0, 0))
        
        # 如果是 view 來源，從 view_axis_solver 獲取
        if self.current_lock.axis_source == AxisSource.VIEW:
            if context:
                try:
                    from .view_axis_solver import get_view_axis_vector
                    axis_vec = get_view_axis_vector(
                        context, 
                        self.current_lock.view_axis_name or "VIEW_LEFT_RIGHT"
                    )
                    if axis_vec:
                        return axis_vec
                except ImportError:
                    pass
        
        return self.current_lock.lock_axis
    
    def get_effective_plane_normal(self, context=None) -> Vector:
        """
        獲取有效的平面法線（考慮軸來源）
        
        Returns:
            Vector: 世界空間中的平面法線
        """
        if not self.current_lock.is_active:
            return Vector((0, 0, 1))
        
        # 如果是 view 來源，從 view_axis_solver 獲取
        if self.current_lock.axis_source == AxisSource.VIEW:
            if context:
                try:
                    from .view_axis_solver import get_view_plane_normal
                    normal = get_view_plane_normal(context, "VIEW_PLANE")
                    if normal:
                        return normal
                except ImportError:
                    pass
        
        return self.current_lock.lock_plane_normal
    
    def apply_axis_constraint_to_delta(self, delta: Vector, context=None) -> Vector:
        """
        將軸約束應用到位移向量 - v7.4 統一接口
        
        Args:
            delta: 原始位移向量
            context: Blender context
            
        Returns:
            Vector: 應用約束後的位移向量
        """
        if not self.current_lock.is_active:
            return delta
        
        constraint_kind = self.current_lock.constraint_kind
        
        if constraint_kind == AxisConstraintKind.SINGLE_AXIS:
            # 單軸約束 - 投影到軸
            axis = self.get_effective_axis_vector(context)
            if axis.length > 0:
                axis = axis.normalized()
                return axis * delta.dot(axis)
                
        elif constraint_kind == AxisConstraintKind.PLANE:
            # 平面約束 - 投影到平面
            normal = self.get_effective_plane_normal(context)
            if normal.length > 0:
                normal = normal.normalized()
                return delta - normal * delta.dot(normal)
        
        # 預設：返回原始 delta
        return delta
    
    def get_axis_lock_info_v74(self) -> Dict[str, Any]:
        """
        v7.4: 獲取詳細的軸鎖定資訊
        
        Returns:
            Dict: 包含 axis_source, constraint_kind, view_axis_name 等
        """
        return {
            "lock_type": self.current_lock.lock_type.value,
            "axis_source": self.current_lock.axis_source.value,
            "constraint_kind": self.current_lock.constraint_kind.value,
            "axis_name": self.current_lock.axis_name,
            "view_axis_name": self.current_lock.view_axis_name,
            "is_active": self.current_lock.is_active,
            "coordinate_space": self.current_lock.coordinate_space,
        }


# 全域軸鎖定系統實例
axis_locking_system = AxisLockingSystem()


def get_axis_locking_system() -> AxisLockingSystem:
    """獲取軸鎖定系統實例"""
    return axis_locking_system


def set_axis_lock(lock_type: AxisLockType, reference_point=None, context=None):
    """設置軸鎖定 - 供外部調用"""
    if context:
        axis_locking_system.set_context(context)
    
    axis_locking_system.set_axis_lock(lock_type, reference_point)


def apply_axis_lock(point: Vector, transform: Matrix = None, context=None) -> Vector:
    """應用軸鎖定到點 - 供外部調用"""
    if context:
        axis_locking_system.set_context(context)
    
    return axis_locking_system.apply_axis_lock(point, transform)


def process_axis_lock_hotkey(hotkey: str, reference_point=None, context=None) -> bool:
    """處理軸鎖定快捷鍵 - 供外部調用"""
    if context:
        axis_locking_system.set_context(context)
    
    return axis_locking_system.process_hotkey(hotkey, reference_point)


def get_axis_lock_info(context=None) -> Dict[str, Any]:
    """獲取軸鎖定信息 - 供外部調用"""
    if context:
        axis_locking_system.set_context(context)
    
    return axis_locking_system.get_lock_info()


def get_axis_lock_visualization_data(context=None) -> Dict[str, Any]:
    """獲取軸鎖定可視化數據 - 供外部調用"""
    if context:
        axis_locking_system.set_context(context)
    
    return axis_locking_system.get_lock_visualization_data()
