"""
Smart Align Pro - 面對齊求解器
face-to-face contact align 實現
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from ..utils.bbox_utils import get_bbox_center_world, get_bbox_corners_world


def solve_face_normal_align(source_obj, target_obj, source_face_key, target_face_key):
    """
    步驟 1：對齊面的法線
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_face_key (str): 來源面鍵值
        target_face_key (str): 目標面鍵值
        
    Returns:
        dict: 包含旋轉信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_face_normal_align")
    print(f"[SmartAlignPro][SOLVER] Source: {source_obj.name}[{source_face_key}] → {target_obj.name}[{target_face_key}]")
    
    # 計算面的法線
    source_normal = calculate_face_normal(source_obj, source_face_key)
    target_normal = calculate_face_normal(target_obj, target_face_key)
    
    # 計算旋轉
    rotation = source_normal.rotation_difference(target_normal)
    
    print(f"[SmartAlignPro][SOLVER] Face normal rotation: {rotation}")
    
    return {
        'rotation': rotation,
        'source_normal': source_normal,
        'target_normal': target_normal
    }


def solve_face_distance_align(source_obj, target_obj, source_face_key, target_face_key):
    """
    步驟 2：對齊面的距離
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_face_key (str): 來源面鍵值
        target_face_key (str): 目標面鍵值
        
    Returns:
        dict: 包含平移信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_face_distance_align")
    
    # 計算面的中心點
    source_center = calculate_face_center(source_obj, source_face_key)
    target_center = calculate_face_center(target_obj, target_face_key)
    
    # 計算平移
    translation = target_center - source_center
    
    print(f"[SmartAlignPro][SOLVER] Face distance translation: {translation}")
    
    return {
        'translation': translation,
        'source_center': source_center,
        'target_center': target_center
    }


def solve_face_contact_offset(source_obj, target_obj, source_face_key, target_face_key, offset_distance=0.001):
    """
    步驟 3：應用翻譯偏移
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_face_key (str): 來源面鍵值
        target_face_key (str): 目標面鍵值
        offset_distance (float): 偏移距離
        
    Returns:
        dict: 包含偏移信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_face_contact_offset")
    
    # 計算目標面的法線
    target_normal = calculate_face_normal(target_obj, target_face_key)
    
    # 應用偏移（沿法線方向）
    contact_offset = target_normal * offset_distance
    
    print(f"[SmartAlignPro][SOLVER] Face contact offset: {contact_offset}")
    
    return {
        'contact_offset': contact_offset,
        'offset_direction': target_normal,
        'offset_distance': offset_distance
    }


def calculate_face_normal(obj, face_key):
    """
    計算面的法線
    
    Args:
        obj (bpy.types.Object): 物件
        face_key (str): 面鍵值
        
    Returns:
        Vector: 面的法線向量
    """
    # 根據面鍵值獲取三個點位
    from ..core.math_utils import get_bbox_world_point
    
    if face_key == "TOP":
        p1 = get_bbox_world_point(obj, "0")
        p2 = get_bbox_world_point(obj, "1")
        p3 = get_bbox_world_point(obj, "4")
    elif face_key == "BOTTOM":
        p1 = get_bbox_world_point(obj, "2")
        p2 = get_bbox_world_point(obj, "3")
        p3 = get_bbox_world_point(obj, "6")
    elif face_key == "FRONT":
        p1 = get_bbox_world_point(obj, "0")
        p2 = get_bbox_world_point(obj, "3")
        p3 = get_bbox_world_point(obj, "7")
    elif face_key == "BACK":
        p1 = get_bbox_world_point(obj, "1")
        p2 = get_bbox_world_point(obj, "2")
        p3 = get_bbox_world_point(obj, "5")
    elif face_key == "LEFT":
        p1 = get_bbox_world_point(obj, "0")
        p2 = get_bbox_world_point(obj, "4")
        p3 = get_bbox_world_point(obj, "7")
    elif face_key == "RIGHT":
        p1 = get_bbox_world_point(obj, "1")
        p2 = get_bbox_world_point(obj, "5")
        p3 = get_bbox_world_point(obj, "6")
    else:
        # 預設使用頂面
        p1 = get_bbox_world_point(obj, "0")
        p2 = get_bbox_world_point(obj, "1")
        p3 = get_bbox_world_point(obj, "4")
    
    # 計算法線
    v1 = p2 - p1
    v2 = p3 - p1
    normal = v1.cross(v2).normalized()
    
    return normal


def calculate_face_center(obj, face_key):
    """
    計算面的中心點
    
    Args:
        obj (bpy.types.Object): 物件
        face_key (str): 面鍵值
        
    Returns:
        Vector: 面的中心點
    """
    # 根據面鍵值獲取四個角點
    from ..core.math_utils import get_bbox_world_point
    
    if face_key == "TOP":
        corners = [get_bbox_world_point(obj, "0"), get_bbox_world_point(obj, "1"), 
                  get_bbox_world_point(obj, "5"), get_bbox_world_point(obj, "4")]
    elif face_key == "BOTTOM":
        corners = [get_bbox_world_point(obj, "2"), get_bbox_world_point(obj, "3"), 
                  get_bbox_world_point(obj, "7"), get_bbox_world_point(obj, "6")]
    elif face_key == "FRONT":
        corners = [get_bbox_world_point(obj, "0"), get_bbox_world_point(obj, "3"), 
                  get_bbox_world_point(obj, "7"), get_bbox_world_point(obj, "4")]
    elif face_key == "BACK":
        corners = [get_bbox_world_point(obj, "1"), get_bbox_world_point(obj, "2"), 
                  get_bbox_world_point(obj, "6"), get_bbox_world_point(obj, "5")]
    elif face_key == "LEFT":
        corners = [get_bbox_world_point(obj, "0"), get_bbox_world_point(obj, "4"), 
                  get_bbox_world_point(obj, "7"), get_bbox_world_point(obj, "3")]
    elif face_key == "RIGHT":
        corners = [get_bbox_world_point(obj, "1"), get_bbox_world_point(obj, "5"), 
                  get_bbox_world_point(obj, "6"), get_bbox_world_point(obj, "2")]
    else:
        # 預設使用頂面
        corners = [get_bbox_world_point(obj, "0"), get_bbox_world_point(obj, "1"), 
                  get_bbox_world_point(obj, "5"), get_bbox_world_point(obj, "4")]
    
    # 計算中心點
    from mathutils import Vector as _V
    center = sum(corners, _V((0.0, 0.0, 0.0))) / len(corners)
    
    return center


def solve_face_to_face_contact(source_obj, target_obj, source_face_key, target_face_key, settings=None):
    """
    完整的 face-to-face contact align
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_face_key (str): 來源面鍵值
        target_face_key (str): 目標面鍵值
        settings: 設置物件
        
    Returns:
        dict: 包含完整變換信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_face_to_face_contact")
    print(f"[SmartAlignPro][SOLVER] Full face-to-face align: {source_obj.name} → {target_obj.name}")
    
    # 步驟 1：對齊面的法線
    normal_result = solve_face_normal_align(source_obj, target_obj, source_face_key, target_face_key)
    
    # 應用旋轉
    source_obj.rotation_quaternion = normal_result['rotation'] @ source_obj.rotation_quaternion
    
    # 步驟 2：對齊面的距離
    distance_result = solve_face_distance_align(source_obj, target_obj, source_face_key, target_face_key)
    
    # 應用平移
    source_obj.location += distance_result['translation']
    
    # 步驟 3：應用接觸偏移
    offset_distance = settings.small_offset if settings and hasattr(settings, 'small_offset') else 0.001
    contact_result = solve_face_contact_offset(source_obj, target_obj, source_face_key, target_face_key, offset_distance)
    
    # 應用接觸偏移
    source_obj.location += contact_result['contact_offset']
    
    # 計算最終變換矩陣
    transform_matrix = Matrix.Translation(distance_result['translation'] + contact_result['contact_offset']) @ normal_result['rotation'].to_matrix().to_4x4()
    
    print(f"[SmartAlignPro][SOLVER] Face-to-face contact align completed")
    print(f"[SmartAlignPro][SOLVER] Final transform matrix determinant: {transform_matrix.determinant()}")
    
    return {
        'normal_result': normal_result,
        'distance_result': distance_result,
        'contact_result': contact_result,
        'transform_matrix': transform_matrix,
        'source_normal': normal_result['source_normal'],
        'target_normal': normal_result['target_normal']
    }


def solve_face_align_cad_picking(source_obj, target_obj, settings):
    """
    CAD 模式的面對齊，支援互動式點選
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        settings: 設置物件
        
    Returns:
        dict: 對齊結果
    """
    print(f"[SmartAlignPro][SOLVER] solve_face_align_cad_picking")
    print(f"[SmartAlignPro][SOLVER] CAD face align: {source_obj.name} → {target_obj.name}")
    
    # 使用預設面配置（可以根據需要調整）
    source_face_key = "TOP"  # 預設使用頂面
    target_face_key = "TOP"
    
    # 執行完整面對齊
    result = solve_face_to_face_contact(source_obj, target_obj, source_face_key, target_face_key, settings)
    
    print(f"[SmartAlignPro][SOLVER] CAD face align completed")
    
    return result
