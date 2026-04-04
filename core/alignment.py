"""
Smart Align Pro - 核心對齊算法模組
包含所有對齊策略的核心實現
"""

import bpy
from mathutils import Vector
from enum import Enum, auto
from .math_utils import (
    rotation_between_vectors, get_plane_basis, matrix_from_basis,
    rotate_object_around_world_point, get_bbox_world_point,
    ray_cast_to_surface, project_point_to_plane
)
from ..utils.bbox_utils import get_bbox_center_world


class AlignmentResultMode(Enum):
    """對齊結果模式枚舉 - 控制對齊後物件的接觸方式"""
    MATCH = auto()      # 完全重合
    CONTACT = auto()    # 接觸不穿透
    OUTSIDE = auto()   # 外貼
    INSIDE = auto()     # 內貼


def two_point_align(source, target, source_a_key, source_b_key, target_a_key, target_b_key):
    """兩點對齊核心算法"""
    # 獲取來源點位
    src_a = get_bbox_world_point(source, source_a_key)
    src_b = get_bbox_world_point(source, source_b_key)
    
    # 獲取目標點位
    tgt_a = get_bbox_world_point(target, target_a_key)
    tgt_b = get_bbox_world_point(target, target_b_key)
    
    # 計算旋轉
    src_vec = src_b - src_a
    tgt_vec = tgt_b - tgt_a
    
    if src_vec.length < 0.0001 or tgt_vec.length < 0.0001:
        raise ValueError("點位過於接近，無法進行對齊")
    
    rot_q = rotation_between_vectors(src_vec, tgt_vec)
    rotate_object_around_world_point(source, rot_q, src_a)
    
    # 計算平移
    moved_src_a = get_bbox_world_point(source, source_a_key)
    translation = tgt_a - moved_src_a
    source.location += translation
    
    return {
        'source_points': (src_a, src_b),
        'target_points': (tgt_a, tgt_b),
        'rotation': rot_q,
        'translation': translation
    }


def three_point_align(source, target, source_a_key, source_b_key, source_c_key, 
                     target_a_key, target_b_key, target_c_key, settings):
    """三點對齊核心算法"""
    # 獲取來源點位
    src_a = get_bbox_world_point(source, source_a_key)
    src_b = get_bbox_world_point(source, source_b_key)
    src_c = get_bbox_world_point(source, source_c_key)
    
    # 獲取目標點位
    tgt_a = get_bbox_world_point(target, target_a_key)
    tgt_b = get_bbox_world_point(target, target_b_key)
    tgt_c = get_bbox_world_point(target, target_c_key)
    
    # 計算平面基底
    src_x, src_y, src_n = get_plane_basis(src_a, src_b, src_c)
    tgt_x, tgt_y, tgt_n = get_plane_basis(tgt_a, tgt_b, tgt_c)
    
    # 處理翻面選項
    if settings.three_point_flip_target_normal:
        tgt_y = -tgt_y
        tgt_n = -tgt_n
    
    # 構建變換矩陣
    src_basis = matrix_from_basis(src_a, src_x, src_y, src_n)
    tgt_basis = matrix_from_basis(tgt_a, tgt_x, tgt_y, tgt_n)
    
    transform = tgt_basis @ src_basis.inverted()
    source.matrix_world = transform @ source.matrix_world
    
    # 應用微小偏移
    offset_vector = Vector((0, 0, 0))
    if settings.three_point_apply_offset and settings.collision_safe_mode:
        offset_vector = tgt_n.normalized() * settings.small_offset
        source.location += offset_vector
    
    return {
        'source_points': (src_a, src_b, src_c),
        'target_points': (tgt_a, tgt_b, tgt_c),
        'src_normal': src_n,
        'tgt_normal': tgt_n,
        'correction': transform,
        'offset_vector': offset_vector
    }


def surface_normal_align(source, target, hit_location, hit_normal, settings):
    """表面法線對齊核心算法 - 真正互動式命中版本
    
    Args:
        source: 來源物件（要被對齊的物件）
        target: 目標物件（使用者點擊的物件）
        hit_location: 使用者命中的世界座標點
        hit_normal: 使用者命中面的世界座標法線
        settings: 設定物件
    """
    surface_normal = hit_normal.normalized()

    axis_map = {
        "POS_X": Vector((1, 0, 0)),
        "NEG_X": Vector((-1, 0, 0)),
        "POS_Y": Vector((0, 1, 0)),
        "NEG_Y": Vector((0, -1, 0)),
        "POS_Z": Vector((0, 0, 1)),
        "NEG_Z": Vector((0, 0, -1)),
    }
    target_axis = axis_map.get(
        getattr(settings, "normal_align_axis", "POS_Z"),
        Vector((0, 0, 1))
    )

    rotation = rotation_between_vectors(target_axis, surface_normal)
    rot_mat = rotation.to_matrix().to_4x4()
    old_mat = source.rotation_euler.to_matrix().to_4x4()
    source.rotation_euler = (rot_mat @ old_mat).to_euler()

    if getattr(settings, "normal_align_move_to_hit", True):
        offset_distance = getattr(settings, "offset_distance", 0.0)
        source.location = hit_location + surface_normal * offset_distance

    return {
        "surface_normal": surface_normal,
        "target_axis": target_axis,
        "rotation": rotation,
        "hit_point": hit_location,
    }


def surface_normal_align_with_raycast(source, target, settings):
    """表面法線對齊核心算法 - 帶 raycast 的版本（向後兼容）
    
    這個版本會從目標物件的方向做 raycast 來獲取命中點和法線。
    如果需要真正的互動式命中，请使用 surface_normal_align() 並自行傳入 hit_location 和 hit_normal。
    """
    target_center = get_bbox_center_world(target)
    
    ray_origin = target_center + Vector((0.0, 0.0, 10.0))
    ray_dir = Vector((0.0, 0.0, -1.0))
    
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        hit, location, normal, face_index, obj, matrix = bpy.context.scene.ray_cast(
            depsgraph, ray_origin, ray_dir
        )
    except Exception as e:
        raise ValueError(f"射線檢測失敗：{e}")
    
    if not hit:
        raise ValueError("無法檢測目標表面法線，請確認物件在場景中可見")
    
    return surface_normal_align(source, target, location, normal, settings)


def auto_contact_align(source, target, settings):
    """智慧接觸對齊核心算法"""
    # 分析物體邊界
    source_bbox = [source.matrix_world @ Vector(corner) for corner in source.bound_box]
    target_bbox = [target.matrix_world @ Vector(corner) for corner in target.bound_box]
    
    # 找到最近接觸點
    min_distance = float('inf')
    best_contact = None
    
    for src_point in source_bbox:
        for tgt_point in target_bbox:
            distance = (src_point - tgt_point).length
            if distance < min_distance:
                min_distance = distance
                best_contact = (src_point, tgt_point)
    
    if not best_contact:
        raise ValueError("無法找到接觸點")
    
    src_contact, tgt_contact = best_contact
    
    # 計算接觸向量
    contact_vector = tgt_contact - src_contact
    source.location += contact_vector
    
    # 應用安全偏移
    if settings.collision_safe_mode:
        source.location += Vector((0, 0, settings.small_offset))
    
    return {
        'source_contact': src_contact,
        'target_contact': tgt_contact,
        'contact_vector': contact_vector,
        'distance': min_distance
    }


def align_to_ground(objects, settings):
    """貼地對齊核心算法"""
    scene = bpy.context.scene
    results = []
    
    for obj in objects:
        # 獲取物件底部中心
        bbox_bottom = min([obj.matrix_world @ Vector(corner) for corner in obj.bound_box], 
                         key=lambda p: p.z)
        
        # 射線檢測地面
        ray_start = bbox_bottom + Vector((0, 0, 10))
        ray_direction = Vector((0, 0, -1))
        
        ray_result = ray_cast_to_surface(bpy.context, ray_start, ray_direction)
        
        if ray_result:
            ground_point = ray_result['location']
            
            # 計算移動距離
            move_distance = ground_point.z - bbox_bottom.z
            obj.location.z += move_distance
            
            # 應用安全偏移
            if settings.collision_safe_mode:
                obj.location.z += settings.small_offset
            
            results.append({
                'object': obj,
                'ground_point': ground_point,
                'move_distance': move_distance
            })
    
    return results


def align_to_surface(objects, settings):
    """表面對齊核心算法"""
    results = []
    
    for obj in objects:
        obj_center = get_bbox_center_world(obj)
        
        # 射線檢測表面
        ray_start = obj_center + Vector((0, 0, 10))
        ray_direction = Vector((0, 0, -1))
        
        ray_result = ray_cast_to_surface(bpy.context, ray_start, ray_direction)
        
        if ray_result:
            surface_point = ray_result['location']
            surface_normal = ray_result['normal']
            
            # 移動到表面
            move_vector = surface_point - obj_center
            obj.location += move_vector
            
            # 對齊法線（可選）
            axis_map = {
                "POS_X": Vector((1, 0, 0)),
                "NEG_X": Vector((-1, 0, 0)),
                "POS_Y": Vector((0, 1, 0)),
                "NEG_Y": Vector((0, -1, 0)),
                "POS_Z": Vector((0, 0, 1)),
                "NEG_Z": Vector((0, 0, -1)),
            }

            target_axis = axis_map.get(
                getattr(settings, "normal_align_axis", "POS_Z"),
                Vector((0, 0, 1))
            )
            rotation = rotation_between_vectors(target_axis, surface_normal)

            current_quat = obj.rotation_euler.to_quaternion()
            new_quat = rotation @ current_quat
            obj.rotation_euler = new_quat.to_euler(obj.rotation_mode)
            
            # 應用安全偏移
            if settings.collision_safe_mode:
                obj.location += surface_normal * settings.small_offset
            
            results.append({
                'object': obj,
                'surface_point': surface_point,
                'surface_normal': surface_normal,
                'move_vector': move_vector
            })
    
    return results
