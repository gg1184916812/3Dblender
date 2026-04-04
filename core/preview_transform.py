"""
Smart Align Pro - Preview Transform 系統
統一的預覽與套用管理
"""

import bpy
from mathutils import Vector, Matrix
from typing import Optional, Dict, Any, List
import time


class PreviewState:
    """預覽狀態管理"""
    def __init__(self):
        self.original_matrix = None
        self.preview_matrix = None
        self.is_active = False
        self.source_object = None
        self.target_objects = []
        self.start_time = 0
        
    def reset(self):
        """重置狀態"""
        self.original_matrix = None
        self.preview_matrix = None
        self.is_active = False
        self.source_object = None
        self.target_objects = []
        self.start_time = 0


class PreviewEngine:
    """預覽引擎"""
    def __init__(self):
        self.state = PreviewState()
        self.transform_cache = {}
        
    def activate(self, source_object: bpy.types.Object, target_objects: List[bpy.types.Object] = None):
        """啟動預覽"""
        if not source_object:
            return False
            
        self.state.reset()
        self.state.source_object = source_object
        self.state.target_objects = target_objects or []
        self.state.original_matrix = source_object.matrix_world.copy()
        self.state.preview_matrix = self.state.original_matrix.copy()
        self.state.is_active = True
        self.state.start_time = time.time()
        
        return True
        
    def update_preview(self, transform_result: Dict[str, Any]):
        """更新預覽"""
        if not self.state.is_active or not self.state.source_object:
            return False
            
        # 從原始矩陣重新計算預覽
        preview_matrix = self.state.original_matrix.copy()
        
        # 應用平移
        if "translation" in transform_result:
            translation = transform_result["translation"]
            if hasattr(translation, "to_matrix"):
                preview_matrix = translation.to_matrix().to_4x4() @ preview_matrix
            else:
                preview_matrix = Matrix.Translation(translation) @ preview_matrix
                
        # 應用旋轉
        if "rotation" in transform_result:
            rotation = transform_result["rotation"]
            if hasattr(rotation, "to_matrix"):
                preview_matrix = rotation.to_matrix().to_4x4() @ preview_matrix
            else:
                preview_matrix = rotation @ preview_matrix
                
        # 應用縮放
        if "scale" in transform_result:
            scale = transform_result["scale"]
            if isinstance(scale, (list, tuple)) and len(scale) == 3:
                scale_matrix = Matrix.Scale(scale[0], 4, (1, 0, 0)) @ \
                              Matrix.Scale(scale[1], 4, (0, 1, 0)) @ \
                              Matrix.Scale(scale[2], 4, (0, 0, 1))
                preview_matrix = scale_matrix @ preview_matrix
                
        # 更新預覽矩陣
        self.state.preview_matrix = preview_matrix
        
        # 應用到物件（不污染原始矩陣）
        self.state.source_object.matrix_world = preview_matrix
        
        return True
        
    def apply_preview(self):
        """套用預覽到正式狀態"""
        if not self.state.is_active or not self.state.source_object:
            return False
            
        # 正式套用預覽矩陣
        self.state.source_object.matrix_world = self.state.preview_matrix.copy()
        
        # 清理狀態
        self.state.is_active = False
        
        return True
        
    def cancel_preview(self):
        """取消預覽，恢復原始狀態"""
        if not self.state.is_active or not self.state.source_object:
            return False
            
        # 恢復原始矩陣
        self.state.source_object.matrix_world = self.state.original_matrix.copy()
        
        # 清理狀態
        self.state.is_active = False
        
        return True
        
    def is_active(self) -> bool:
        """檢查預覽是否活躍"""
        return self.state.is_active
        
    def get_preview_info(self) -> Dict[str, Any]:
        """獲取預覽資訊"""
        if not self.state.is_active:
            return {}
            
        return {
            "source_object": self.state.source_object.name if self.state.source_object else None,
            "target_objects": [obj.name for obj in self.state.target_objects],
            "is_active": self.state.is_active,
            "duration": time.time() - self.state.start_time
        }


# 全局預覽實例
preview = PreviewEngine()


def activate(source_object: bpy.types.Object, target_objects: List[bpy.types.Object] = None):
    """啟動預覽"""
    return preview.activate(source_object, target_objects)


def update_preview(transform_result: Dict[str, Any]):
    """更新預覽"""
    return preview.update_preview(transform_result)


def update_two_point_preview(source_object: bpy.types.Object, from_point: Vector, to_point: Vector):
    """更新兩點預覽"""
    if not preview.is_active():
        return False

    if from_point is None or to_point is None:
        return False

    # 這裡必須傳 Vector，不要先包成 Matrix.Translation
    translation = to_point - from_point

    return preview.update_preview({"translation": translation})


def update_transform(translation: Optional[Vector] = None, rotation: Optional[Matrix] = None, scale: Optional[Vector] = None):
    """更新變換預覽"""
    transform_result = {}
    
    if translation:
        transform_result["translation"] = translation
    if rotation:
        transform_result["rotation"] = rotation
    if scale:
        transform_result["scale"] = scale
        
    return preview.update_preview(transform_result)


def apply_preview():
    """套用預覽"""
    return preview.apply_preview()


def cancel_preview():
    """取消預覽"""
    return preview.cancel_preview()


def reset():
    """重置預覽"""
    return preview.state.reset()


def get_preview_info() -> Dict[str, Any]:
    """獲取預覽資訊"""
    return preview.get_preview_info()
