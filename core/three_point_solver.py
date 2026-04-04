"""
Smart Align Pro - 三點對齊求解器
真正的剛體變換算法實現
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from ..utils.bbox_utils import get_bbox_center_world


def solve_three_point_transform(source_pts, target_pts):
    """
    求解三點對齊的剛體變換矩陣
    
    Args:
        source_pts (list[Vector]): 來源點列表 [p1, p2, p3]
        target_pts (list[Vector]): 目標點列表 [p1, p2, p3]
        
    Returns:
        dict: 包含旋轉矩陣和平移向量的字典
    """
    print(f"[SmartAlignPro][SOLVER] solve_three_point_transform")
    print(f"[SmartAlignPro][SOLVER] Source points: {source_pts}")
    print(f"[SmartAlignPro][SOLVER] Target points: {target_pts}")
    
    if len(source_pts) != 3 or len(target_pts) != 3:
        raise ValueError("需要恰好三個點位")
    
    # 計算質心
    source_centroid = sum(source_pts) / 3
    target_centroid = sum(target_pts) / 3
    
    # 中心化點位
    centered_source = [p - source_centroid for p in source_pts]
    centered_target = [p - target_centroid for p in target_pts]
    
    # 計算協方差矩陣
    H = Matrix()
    for i in range(3):
        for j in range(3):
            H[i][j] = sum(centered_source[k][i] * centered_target[k][j] for k in range(3))
    
    # 奇異值分解 (SVD)
    try:
        U, S, V = H.svd()
    except:
        # 如果 SVD 失敗，使用簡化的方法
        print("[SmartAlignPro][SOLVER] SVD failed, using simplified method")
        return solve_three_point_transform_simplified(source_pts, target_pts)
    
    # 計算旋轉矩陣
    R = V @ U.transposed()
    
    # 檢查反射
    if R.determinant() < 0:
        print("[SmartAlignPro][SOLVER] Detected reflection, correcting")
        V[2] = -V[2]
        R = V @ U.transposed()
    
    # 計算平移向量
    t = target_centroid - R @ source_centroid
    
    # 構建完整的變換矩陣
    transform_matrix = Matrix.Translation(t) @ R.to_4x4()
    
    print(f"[SmartAlignPro][SOLVER] Rotation matrix: {R}")
    print(f"[SmartAlignPro][SOLVER] Translation vector: {t}")
    print(f"[SmartAlignPro][SOLVER] Transform determinant: {transform_matrix.determinant()}")
    
    return {
        'rotation_matrix': R,
        'translation_vector': t,
        'transform_matrix': transform_matrix,
        'source_centroid': source_centroid,
        'target_centroid': target_centroid,
        'rotation_quaternion': R.to_quaternion()
    }


def solve_three_point_transform_simplified(source_pts, target_pts):
    """
    簡化的三點對齊算法（當 SVD 失敗時使用）
    
    Args:
        source_pts (list[Vector]): 來源點列表
        target_pts (list[Vector]): 目標點列表
        
    Returns:
        dict: 包含變換信息的字典
    """
    print("[SmartAlignPro][SOLVER] Using simplified three-point alignment")
    
    # 計算兩個向量
    source_v1 = source_pts[1] - source_pts[0]
    source_v2 = source_pts[2] - source_pts[0]
    target_v1 = target_pts[1] - target_pts[0]
    target_v2 = target_pts[2] - target_pts[0]
    
    # 計算法線
    source_normal = source_v1.cross(source_v2).normalized()
    target_normal = target_v1.cross(target_v2).normalized()
    
    # 計算旋轉
    rotation = source_normal.rotation_difference(target_normal)
    
    # 計算平移
    translation = target_pts[0] - (rotation @ source_pts[0])
    
    return {
        'rotation_quaternion': rotation,
        'translation_vector': translation,
        'transform_matrix': Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()
    }


def solve_three_point_rigid_transform(source_obj, target_obj, source_keys, target_keys, settings):
    """
    執行完整的三點剛體變換
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        source_keys (list): 來源點位鍵值列表
        target_keys (list): 目標點位鍵值列表
        settings: 設置物件
        
    Returns:
        dict: 變換結果
    """
    print(f"[SmartAlignPro][SOLVER] solve_three_point_rigid_transform")
    print(f"[SmartAlignPro][SOLVER] Source: {source_obj.name} → Target: {target_obj.name}")
    
    # 獲取點位
    from ..core.math_utils import get_bbox_world_point
    
    source_pts = [get_bbox_world_point(source_obj, key) for key in source_keys]
    target_pts = [get_bbox_world_point(target_obj, key) for key in target_keys]
    
    # 處理翻面選項
    if settings.three_point_flip_target_normal:
        # 翻轉目標點位
        target_center = sum(target_pts) / 3
        target_pts = [2 * target_center - pt for pt in target_pts]
        print("[SmartAlignPro][SOLVER] Applied target normal flip")
    
    # 求解變換
    result = solve_three_point_transform(source_pts, target_pts)
    
    # 應用變換到來源物件
    source_obj.matrix_world = result['transform_matrix'] @ source_obj.matrix_world
    
    # 應用微小偏移
    if settings.three_point_apply_offset and settings.collision_safe_mode:
        offset_vector = result['rotation_matrix'].to_quaternion() @ Vector((0, 0, settings.small_offset))
        source_obj.location += offset_vector
        print(f"[SmartAlignPro][SOLVER] Applied collision offset: {offset_vector}")
    
    print(f"[SmartAlignPro][SOLVER] Three-point rigid transform completed")
    
    return result


def solve_three_point_cad_picking(source_obj, target_obj, settings):
    """
    CAD 模式的三點對齊，支援互動式點選
    
    Args:
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        settings: 設置物件
        
    Returns:
        dict: 變換結果
    """
    print(f"[SmartAlignPro][SOLVER] solve_three_point_cad_picking")
    print(f"[SmartAlignPro][SOLVER] CAD mode: {source_obj.name} → {target_obj.name}")
    
    # 使用預設的三點配置
    source_keys = [settings.three_point_source_a, settings.three_point_source_b, settings.three_point_source_c]
    target_keys = [settings.three_point_target_a, settings.three_point_target_b, settings.three_point_target_c]
    
    # 執行剛體變換
    result = solve_three_point_rigid_transform(source_obj, target_obj, source_keys, target_keys, settings)
    
    print(f"[SmartAlignPro][SOLVER] CAD three-point align completed")
    
    return result
