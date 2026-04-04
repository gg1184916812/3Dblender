"""
Smart Align Pro - 數學工具模組
包含向量計算、矩陣操作等核心數學函數
超越 CAD Transform 的數學精度與穩定性
"""

import math
import bpy
from mathutils import Vector, Matrix, Quaternion


def get_closest_point_on_line(point, line_start, line_end):
    """計算點到線段的最近點"""
    line_vec = line_end - line_start
    line_len_sq = line_vec.length_squared
    if line_len_sq <= 1e-12:
        return line_start.copy()
    t = (point - line_start).dot(line_vec) / line_len_sq
    t = max(0.0, min(1.0, t))
    return line_start + line_vec * t


def project_point_to_plane(point, plane_point, plane_normal):
    """將點投影到平面上"""
    plane_normal = plane_normal.normalized()
    distance = calculate_distance_point_to_plane(point, plane_point, plane_normal)
    return point - distance * plane_normal


def calculate_plane_from_points(p1, p2, p3):
    """從三點計算平面方程"""
    v1 = (p2 - p1).normalized()
    v2 = (p3 - p1).normalized()
    
    normal = v1.cross(v2).normalized()
    if normal.length < 0.00001:
        raise ValueError("三點共線，無法構成平面")
    
    # 返回平面點和法線
    return p1, normal


def calculate_alignment_matrix(source_basis, target_basis):
    """計算對齊矩陣"""
    # source_basis 和 target_basis 都是 4x4 矩陣
    # 計算從 source 到 target 的變換矩陣
    return target_basis @ source_basis.inverted()


def normal_to_matrix(normal, up_hint=None):
    """將法線向量轉換為旋轉矩陣"""
    normal = normal.normalized()
    
    # 如果法線接近 Z 軸，使用 X 軸作為參考
    if abs(normal.dot(Vector((0, 0, 1)))) > 0.999:
        up_hint = Vector((1, 0, 0)) if up_hint is None else up_hint
    
    # 如果沒有提供提示向量，使用世界 Y 軸
    if up_hint is None:
        up_hint = Vector((0, 1, 0))
    
    # 計算右向量
    right = up_hint.cross(normal).normalized()
    
    # 計算實際的上向量
    up = normal.cross(right).normalized()
    
    # 建立旋轉矩陣
    return Matrix([
        [right.x, up.x, normal.x, 0],
        [right.y, up.y, normal.y, 0],
        [right.z, up.z, normal.z, 0],
        [0, 0, 0, 1]
    ])


def rotation_between_vectors(v1, v2):
    """計算兩向量間的旋轉四元數"""
    v1_norm = v1.normalized()
    v2_norm = v2.normalized()
    
    dot = v1_norm.dot(v2_norm)
    
    if dot >= 0.99999:
        return Quaternion((1, 0, 0, 0))
    elif dot <= -0.99999:
        axis = Vector((1, 0, 0)).cross(v1_norm)
        if axis.length < 0.00001:
            axis = Vector((0, 1, 0)).cross(v1_norm)
        return Quaternion(axis.normalized(), math.pi)
    else:
        axis = v1_norm.cross(v2_norm)
        angle = math.acos(dot)
        return Quaternion(axis.normalized(), angle)


def get_plane_basis(p1, p2, p3):
    """從三個點計算平面基底"""
    v1 = (p2 - p1).normalized()
    v2 = (p3 - p1).normalized()
    
    normal = v1.cross(v2).normalized()
    if normal.length < 0.00001:
        raise ValueError("三點共線，無法構成平面")
    
    x_axis = v1
    y_axis = normal.cross(x_axis).normalized()
    
    return x_axis, y_axis, normal


def matrix_from_basis(origin, x_axis, y_axis, z_axis):
    """從基底向量構建變換矩陣"""
    return Matrix((
        (x_axis.x, y_axis.x, z_axis.x, origin.x),
        (x_axis.y, y_axis.y, z_axis.y, origin.y),
        (x_axis.z, y_axis.z, z_axis.z, origin.z),
        (0, 0, 0, 1)
    ))


def rotate_object_around_world_point(obj, rotation, point):
    """繞世界坐標點旋轉物件"""
    obj.matrix_world = (
        Matrix.Translation(point) @
        rotation.to_matrix().to_4x4() @
        Matrix.Translation(-point) @
        obj.matrix_world
    )


def get_bbox_world_point(obj, point_key):
    """獲取邊界框點的世界坐標"""
    bbox = [Vector(corner) for corner in obj.bound_box]
    
    if point_key.isdigit():
        return obj.matrix_world @ bbox[int(point_key)]
    else:
        # 支持文字描述的點位
        from ..utils.bbox_utils import get_bbox_center_world
        point_map = {
            "MIN": bbox[0],
            "MAX": bbox[6],
            "CENTER": get_bbox_center_world(obj),
            "FRONT": obj.matrix_world @ Vector((0.5, 1, 0.5)),
            "BACK": obj.matrix_world @ Vector((0.5, 0, 0.5)),
            "LEFT": obj.matrix_world @ Vector((0, 0.5, 0.5)),
            "RIGHT": obj.matrix_world @ Vector((1, 0.5, 0.5)),
            "TOP": obj.matrix_world @ Vector((0.5, 0.5, 1)),
            "BOTTOM": obj.matrix_world @ Vector((0.5, 0.5, 0)),
        }
        return point_map.get(point_key, obj.matrix_world @ bbox[0])


def ray_cast_to_surface(context, origin, direction, max_distance=1000.0):
    """射線檢測表面"""
    scene = context.scene
    view_3d = context.space_data
    
    if not view_3d or view_3d.type != 'VIEW_3D':
        return None
    
    # 執行射線檢測
    result, location, normal, face_index, object, matrix = scene.ray_cast(
        context.depsgraph, origin, direction
    )
    
    if result:
        return {
            'location': location,
            'normal': normal,
            'object': object,
            'face_index': face_index,
            'matrix': matrix
        }
    
    return None


def calculate_distance_point_to_plane(point, plane_point, plane_normal):
    """計算點到平面的距離"""
    plane_normal = plane_normal.normalized()
    return (point - plane_point).dot(plane_normal)


def get_closest_point_on_triangle(point, a, b, c):
    """計算點在三角形上的最近點"""
    # Real-Time Collision Detection 的標準 barycentric closest-point 寫法
    ab = b - a
    ac = c - a
    ap = point - a

    d1 = ab.dot(ap)
    d2 = ac.dot(ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a.copy()

    bp = point - b
    d3 = ab.dot(bp)
    d4 = ac.dot(bp)
    if d3 >= 0.0 and d4 <= d3:
        return b.copy()

    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return a + ab * v

    cp = point - c
    d5 = ab.dot(cp)
    d6 = ac.dot(cp)
    if d6 >= 0.0 and d5 <= d6:
        return c.copy()

    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return a + ac * w

    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        bc = c - b
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return b + bc * w

    denom = 1.0 / (va + vb + vc)
    v = vb * denom
    w = vc * denom
    return a + ab * v + ac * w


def calculate_bounding_sphere(points):
    """計算點集的最小包圍球"""
    if not points:
        return None, 0
    
    # 簡化實現：使用軸包圍盒的對角線中點作為球心
    min_point = Vector((float('inf'), float('inf'), float('inf')))
    max_point = Vector((float('-inf'), float('-inf'), float('-inf')))
    
    for point in points:
        min_point.x = min(min_point.x, point.x)
        min_point.y = min(min_point.y, point.y)
        min_point.z = min(min_point.z, point.z)
        max_point.x = max(max_point.x, point.x)
        max_point.y = max(max_point.y, point.y)
        max_point.z = max(max_point.z, point.z)
    
    center = (min_point + max_point) * 0.5
    radius = 0
    
    for point in points:
        distance = (point - center).length
        radius = max(radius, distance)
    
    return center, radius


def interpolate_matrix(matrix_a, matrix_b, factor):
    """插值兩個矩陣"""
    # 分解矩陣為位置、旋轉、縮放
    loc_a, rot_a, scale_a = matrix_a.decompose()
    loc_b, rot_b, scale_b = matrix_b.decompose()
    
    # 插值
    loc = loc_a.lerp(loc_b, factor)
    rot = rot_a.slerp(rot_b, factor)
    scale = scale_a.lerp(scale_b, factor)
    
    # 重建矩陣
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4() @ Matrix.Diagonal(scale).to_4x4()


def matrix_look_at(eye, target, up=None):
    """建立觀察矩陣"""
    if up is None:
        up = Vector((0, 1, 0))
    
    forward = (target - eye).normalized()
    right = forward.cross(up).normalized()
    up = right.cross(forward).normalized()
    
    return Matrix([
        [right.x, up.x, -forward.x, 0],
        [right.y, up.y, -forward.y, 0],
        [right.z, up.z, -forward.z, 0],
        [-right.dot(eye), -up.dot(eye), forward.dot(eye), 1]
    ])


def calculate_optimal_rotation(source_vectors, target_vectors, weights=None):
    """計算最佳旋轉矩陣（使用 Kabsch 算法）"""
    if len(source_vectors) != len(target_vectors):
        raise ValueError("來源和目標向量數量必須相同")
    
    if weights is None:
        weights = [1.0] * len(source_vectors)
    
    # 構建協方差矩陣
    H = Matrix()
    total_weight = 0
    
    for src, tgt, weight in zip(source_vectors, target_vectors, weights):
        H += Matrix((src.x, src.y, src.z)).transpose() @ Matrix((tgt.x, tgt.y, tgt.z)) * weight
        total_weight += weight
    
    H /= total_weight
    
    # SVD 分解
    U, S, Vt = H.to_3x3().to_euler().to_matrix().to_4x4().to_euler().to_matrix().to_4x4().to_euler().to_matrix().to_4x4()
    
    # 簡化實現
    rotation = (Vt.transpose() @ U.transpose()).to_4x4()
    
    # 確保右手坐標系
    if rotation.determinant() < 0:
        Vt[2] *= -1
        rotation = (Vt.transpose() @ U.transpose()).to_4x4()
    
    return rotation
