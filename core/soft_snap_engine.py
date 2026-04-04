"""
Smart Align Pro - Soft Snap Engine
柔和吸附引擎 - 解決吸附黏住問題，讓操作手感更順滑
"""

import bpy
from mathutils import Vector
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class SnapThresholds:
    """各類型吸附釋放閾值"""
    VERTEX: float = 8.0
    EDGE: float = 12.0
    FACE: float = 18.0
    MIDPOINT: float = 10.0
    ORIGIN: float = 25.0
    CENTER: float = 22.0


class SoftSnapState:
    """柔和吸附狀態"""
    def __init__(self):
        self.is_attached = False
        self.attached_point = None
        self.accumulated_distance = 0.0
        self.last_mouse_pos = (0.0, 0.0)


class SoftSnapEngine:
    """柔和吸附引擎 - 解決吸附黏住問題
    
    核心概念：
    - 接近吸附點時，加強吸附
    - 遠離吸附點時，放鬆吸附
    - 超出閾值時，自然釋放
    """
    
    def __init__(self):
        self.thresholds = SnapThresholds()
        self.state = SoftSnapState()
        self.base_strength = 1.0
        
    def get_threshold(self, snap_type: str) -> float:
        """獲取指定類型的釋放閾值"""
        return getattr(self.thresholds, snap_type.upper(), 15.0)
    
    def calculate_snap_strength(self, distance: float, snap_type: str) -> float:
        """計算吸附強度
        
        公式：strength = 1 / (distance + 0.001)
        範圍：[0, 1]
        """
        threshold = self.get_threshold(snap_type)
        
        if distance < 1.0:
            return 1.0
        
        if distance >= threshold:
            return 0.0
        
        normalized = 1.0 - (distance / threshold)
        return max(0.0, min(1.0, normalized))
    
    def apply_soft_snap(self, offset_vector: Vector, distance: float, 
                        snap_type: str) -> Vector:
        """應用柔和吸附到偏移向量
        
        Args:
            offset_vector: 原始偏移向量
            distance: 到吸附點的距離
            snap_type: 吸附類型
            
        Returns:
            調整後的偏移向量
        """
        strength = self.calculate_snap_strength(distance, snap_type)
        
        if strength <= 0.0:
            return offset_vector
        
        if strength >= 1.0:
            return offset_vector
        
        return offset_vector * strength
    
    def should_release(self, mouse_pos: tuple, distance: float, 
                      snap_type: str) -> bool:
        """判斷是否應該釋放當前吸附
        
        條件：
        1. 累積移動距離超過閾值
        2. 當前距離超過該類型的釋放閾值
        """
        if not self.state.is_attached:
            return False
        
        threshold = self.get_threshold(snap_type)
        
        if distance > threshold * 1.5:
            return True
        
        if self.state.accumulated_distance > threshold:
            return True
        
        return False
    
    def update_position(self, mouse_pos: tuple) -> float:
        """更新滑鼠位置，返回移動距離"""
        from math import hypot
        
        dx = mouse_pos[0] - self.state.last_mouse_pos[0]
        dy = mouse_pos[1] - self.state.last_mouse_pos[1]
        distance = hypot(dx, dy)
        
        self.state.accumulated_distance += distance
        self.state.last_mouse_pos = mouse_pos
        
        return distance
    
    def attach(self, point, mouse_pos: tuple):
        """吸附到指定點"""
        self.state.is_attached = True
        self.state.attached_point = point
        self.state.accumulated_distance = 0.0
        self.state.last_mouse_pos = mouse_pos
    
    def release(self):
        """釋放當前吸附"""
        self.state.is_attached = False
        self.state.attached_point = None
        self.state.accumulated_distance = 0.0
    
    def get_state_info(self) -> Dict[str, Any]:
        """獲取當前狀態信息"""
        return {
            "is_attached": self.state.is_attached,
            "accumulated_distance": self.state.accumulated_distance,
            "attached_point": self.state.attached_point,
        }


soft_snap_engine = SoftSnapEngine()


def get_soft_snap_engine() -> SoftSnapEngine:
    """獲取柔和吸附引擎實例"""
    return soft_snap_engine


def calculate_snap_strength(distance: float, snap_type: str) -> float:
    """計算吸附強度 - 供外部調用"""
    return soft_snap_engine.calculate_snap_strength(distance, snap_type)


def should_release_snap(mouse_pos: tuple, distance: float, snap_type: str) -> bool:
    """判斷是否應該釋放吸附 - 供外部調用"""
    return soft_snap_engine.should_release(mouse_pos, distance, snap_type)
