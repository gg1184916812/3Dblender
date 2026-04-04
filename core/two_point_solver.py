"""
Smart Align Pro - 兩點對齊求解器
真正的兩點對齊算法實現
"""

import bpy
from mathutils import Vector, Matrix, Quaternion
from ..utils.bbox_utils import get_bbox_center_world


def solve_two_point_transform(source_point, target_point, source_obj=None):
    """
    求解兩點對齊的變換矩陣
    
    Args:
        source_point (Vector): 來源點（世界坐標）
        target_point (Vector): 目標點（世界坐標）
        source_obj (bpy.types.Object): 來源物件（可選）
        
    Returns:
        dict: 包含變換信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_two_point_transform: {source_point} → {target_point}")
    
    # 計算平移向量
    translation = target_point - source_point
    
    # 如果有來源物件，計算旋轉（基於物件當前朝向）
    rotation = Quaternion((0, 0, 0), 1)  # 預設無旋轉
    if source_obj:
        # 這裡可以根據需求添加旋轉邏輯
        # 例如：根據物件的當前朝向調整
        pass
    
    print(f"[SmartAlignPro][SOLVER] Translation applied: {translation}")
    print(f"[SmartAlignPro][SOLVER] Rotation applied: {rotation}")
    
    return {
        'translation': translation,
        'rotation': rotation,
        'source_point': source_point,
        'target_point': target_point,
        'transform_matrix': Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()
    }


def solve_two_point_directional(source_start, source_end, target_start, target_end, source_obj=None):
    """
    求解兩點方向對齊的變換矩陣
    
    Args:
        source_start (Vector): 來源起點
        source_end (Vector): 來源終點
        target_start (Vector): 目標起點
        target_end (Vector): 目標終點
        source_obj (bpy.types.Object): 來源物件（可選）
        
    Returns:
        dict: 包含變換信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_two_point_directional")
    print(f"[SmartAlignPro][SOLVER] Source: {source_start} → {source_end}")
    print(f"[SmartAlignPro][SOLVER] Target: {target_start} → {target_end}")
    
    # 計算方向向量
    source_dir = (source_end - source_start).normalized()
    target_dir = (target_end - target_start).normalized()
    
    # 計算旋轉
    rotation = source_dir.rotation_difference(target_dir)
    
    # 應用旋轉到來源物件
    if source_obj:
        # 先旋轉物件，使方向對齊
        source_obj.rotation_quaternion = rotation @ source_obj.rotation_quaternion
        
        # 計算旋轉後的起點位置
        rotated_start = source_start + rotation @ (source_start - source_obj.location)
        
        # 計算平移，使旋轉後的起點對齊目標起點
        translation = target_start - rotated_start
        source_obj.location += translation
    else:
        # 如果沒有物件，只返回變換矩陣
        translation = target_start - source_start
    
    print(f"[SmartAlignPro][SOLVER] Rotation applied: {rotation}")
    print(f"[SmartAlignPro][SOLVER] Translation applied: {translation}")
    
    return {
        'rotation': rotation,
        'translation': translation,
        'source_direction': source_dir,
        'target_direction': target_dir,
        'transform_matrix': Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()
    }


def solve_two_point_cad_picking(source_obj, target_obj):
    """
    CAD 模式的兩點對齊，支援互動式點選
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        
    Returns:
        dict: 包含對齊信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_two_point_cad_picking: {source_obj.name} → {target_obj.name}")
    
    # 使用邊界框中心作為預設點位
    source_center = get_bbox_center_world(source_obj)
    target_center = get_bbox_center_world(target_obj)
    
    # 執行兩點對齊
    result = solve_two_point_transform(source_center, target_center, source_obj)
    
    # 應用變換
    if source_obj:
        source_obj.location += result['translation']
        source_obj.rotation_quaternion = result['rotation'] @ source_obj.rotation_quaternion
    
    print(f"[SmartAlignPro][SOLVER] CAD two-point align completed")
    
    return result


def solve_two_point_bbox_align(source_obj, target_obj, source_point_key, target_point_key):
    """
    基於邊界框點位的兩點對齊
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_point_key (str): 來源點位鍵值
        target_point_key (str): 目標點位鍵值
        
    Returns:
        dict: 包含對齊信息的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_two_point_bbox_align")
    print(f"[SmartAlignPro][SOLVER] Source: {source_obj.name}[{source_point_key}] → {target_obj.name}[{target_point_key}]")
    
    # 獲取邊界框點位
    from ..core.math_utils import get_bbox_world_point
    
    source_point = get_bbox_world_point(source_obj, source_point_key)
    target_point = get_bbox_world_point(target_obj, target_point_key)
    
    # 執行兩點對齊
    result = solve_two_point_transform(source_point, target_point, source_obj)
    
    # 應用變換
    if source_obj:
        source_obj.location += result['translation']
        source_obj.rotation_quaternion = result['rotation'] @ source_obj.rotation_quaternion
    
    print(f"[SmartAlignPro][SOLVER] BBox two-point align completed")
    
    return result
