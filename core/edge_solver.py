"""
Smart Align Pro - 邊對齊求解器
edge-to-edge contact align 實現
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from ..utils.bbox_utils import get_bbox_center_world, get_bbox_corners_world


def solve_edge_direction_align(source_obj, target_obj, source_edge_key, target_edge_key):
    """
    步驟 1：對齊邊的方向
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_edge_key (str): 來源邊鍵值
        target_edge_key (str): 目標邊鍵值
        
    Returns:
        dict: 包含旋轉信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_edge_direction_align")
    print(f"[SmartAlignPro][SOLVER] Source: {source_obj.name}[{source_edge_key}] → {target_obj.name}[{target_edge_key}]")
    
    # 獲取邊的兩個端點
    from ..core.math_utils import get_bbox_world_point
    source_start = get_bbox_world_point(source_obj, source_edge_key[0])
    source_end = get_bbox_world_point(source_obj, source_edge_key[1])
    target_start = get_bbox_world_point(target_obj, target_edge_key[0])
    target_end = get_bbox_world_point(target_obj, target_edge_key[1])
    
    # 計算邊的方向向量
    source_dir = (source_end - source_start).normalized()
    target_dir = (target_end - target_start).normalized()
    
    # 計算旋轉
    rotation = source_dir.rotation_difference(target_dir)
    
    print(f"[SmartAlignPro][SOLVER] Edge direction rotation: {rotation}")
    
    return {
        'rotation': rotation,
        'source_direction': source_dir,
        'target_direction': target_dir,
        'source_edge': (source_start, source_end),
        'target_edge': (target_start, target_end)
    }


def solve_edge_midpoint_align(source_obj, target_obj, source_edge_key, target_edge_key):
    """
    步驟 2：對齊邊的中點
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_edge_key (str): 來源邊鍵值
        target_edge_key (str): 目標邊鍵值
        
    Returns:
        dict: 包含平移信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_edge_midpoint_align")
    
    # 獲取邊的兩個端點
    from ..core.math_utils import get_bbox_world_point
    source_start = get_bbox_world_point(source_obj, source_edge_key[0])
    source_end = get_bbox_world_point(source_obj, source_edge_key[1])
    target_start = get_bbox_world_point(target_obj, target_edge_key[0])
    target_end = get_bbox_world_point(target_obj, target_edge_key[1])
    
    # 計算中點
    source_midpoint = (source_start + source_end) / 2
    target_midpoint = (target_start + target_end) / 2
    
    # 計算平移
    translation = target_midpoint - source_midpoint
    
    print(f"[SmartAlignPro][SOLVER] Edge midpoint translation: {translation}")
    
    return {
        'translation': translation,
        'source_midpoint': source_midpoint,
        'target_midpoint': target_midpoint,
        'source_edge': (source_start, source_end),
        'target_edge': (target_start, target_end)
    }


def solve_edge_contact_offset(source_obj, target_obj, source_edge_key, target_edge_key, offset_distance=0.001):
    """
    步驟 3：求解接觸偏移
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_edge_key (str): 來源邊鍵值
        target_edge_key (str): 目標邊鍵值
        offset_distance (float): 偏移距離
        
    Returns:
        dict: 包含接觸偏移信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_edge_contact_offset")
    
    # 獲取邊的法線方向（垂直於邊的平面）
    from ..core.math_utils import get_bbox_world_point
    source_start = get_bbox_world_point(source_obj, source_edge_key[0])
    source_end = get_bbox_world_point(source_obj, source_edge_key[1])
    target_start = get_bbox_world_point(target_obj, target_edge_key[0])
    target_end = get_bbox_world_point(target_obj, target_edge_key[1])
    
    # 計算邊的方向向量
    source_dir = (source_end - source_start).normalized()
    target_dir = (target_end - target_start).normalized()
    
    # 計算兩個邊之間的最近點方向
    edge_connection = target_start - source_start
    
    # 計算垂直於邊的偏移方向
    offset_dir = edge_connection.cross(source_dir).cross(source_dir).normalized()
    
    # 應用偏移距離
    contact_offset = offset_dir * offset_distance
    
    print(f"[SmartAlignPro][SOLVER] Edge contact offset: {contact_offset}")
    
    return {
        'contact_offset': contact_offset,
        'offset_direction': offset_dir,
        'offset_distance': offset_distance
    }


def solve_edge_to_edge_contact(source_obj, target_obj, source_edge_key, target_edge_key, settings=None):
    """
    完整的 edge-to-edge contact align
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_edge_key (str): 來源邊鍵值
        target_edge_key (str): 目標邊鍵值
        settings: 設置物件
        
    Returns:
        dict: 包含完整變換信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_edge_to_edge_contact")
    print(f"[SmartAlignPro][SOLVER] Full edge-to-edge align: {source_obj.name} → {target_obj.name}")
    
    # 步驟 1：對齊邊的方向
    direction_result = solve_edge_direction_align(source_obj, target_obj, source_edge_key, target_edge_key)
    
    # 應用旋轉
    source_obj.rotation_quaternion = direction_result['rotation'] @ source_obj.rotation_quaternion
    
    # 步驟 2：對齊邊的中點
    midpoint_result = solve_edge_midpoint_align(source_obj, target_obj, source_edge_key, target_edge_key)
    
    # 應用平移
    source_obj.location += midpoint_result['translation']
    
    # 步驟 3：應用接觸偏移
    offset_distance = settings.small_offset if settings and hasattr(settings, 'small_offset') else 0.001
    contact_result = solve_edge_contact_offset(source_obj, target_obj, source_edge_key, target_edge_key, offset_distance)
    
    # 應用接觸偏移
    source_obj.location += contact_result['contact_offset']
    
    # 計算最終變換矩陣
    transform_matrix = Matrix.Translation(midpoint_result['translation'] + contact_result['contact_offset']) @ direction_result['rotation'].to_matrix().to_4x4()
    
    print(f"[SmartAlignPro][SOLVER] Edge-to-edge contact align completed")
    print(f"[SmartAlignPro][SOLVER] Final transform matrix determinant: {transform_matrix.determinant()}")
    
    return {
        'direction_result': direction_result,
        'midpoint_result': midpoint_result,
        'contact_result': contact_result,
        'transform_matrix': transform_matrix,
        'source_edge': direction_result['source_edge'],
        'target_edge': direction_result['target_edge']
    }


def solve_edge_align_cad_picking(source_obj, target_obj, settings):
    """
    CAD 模式的邊對齊，支援互動式點選
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        settings: 設置物件
        
    Returns:
        dict: 對齊結果
    """
    print(f"[SmartAlignPro][SOLVER] solve_edge_align_cad_picking")
    print(f"[SmartAlignPro][SOLVER] CAD edge align: {source_obj.name} → {target_obj.name}")
    
    # 使用預設邊配置（可以根據需要調整）
    source_edge_key = ('0', '1')  # 預設使用邊界框的 0-1 邊
    target_edge_key = ('0', '1')
    
    # 執行完整邊對齊
    result = solve_edge_to_edge_contact(source_obj, target_obj, source_edge_key, target_edge_key, settings)
    
    print(f"[SmartAlignPro][SOLVER] CAD edge align completed")
    
    return result
