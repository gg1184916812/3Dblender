"""
Smart Align Pro - 測量工具模組
包含測量相關的輔助函數
"""

import bpy
import math
from mathutils import Vector, Matrix


def calculate_distance(obj1, obj2, measurement_type="CENTER"):
    """計算兩個物件之間的距離"""
    if measurement_type == "CENTER":
        from .bbox_utils import get_bbox_center_world
        p1 = get_bbox_center_world(obj1)
        p2 = get_bbox_center_world(obj2)
    elif measurement_type == "ORIGIN":
        p1 = obj1.matrix_world.translation
        p2 = obj2.matrix_world.translation
    else:  # BBOX_CLOSEST
        min_distance = float('inf')
        closest_points = None
        
        bbox1 = [obj1.matrix_world @ Vector(corner) for corner in obj1.bound_box]
        bbox2 = [obj2.matrix_world @ Vector(corner) for corner in obj2.bound_box]
        
        for point1 in bbox1:
            for point2 in bbox2:
                distance = (point1 - point2).length
                if distance < min_distance:
                    min_distance = distance
                    closest_points = (point1, point2)
        
        return min_distance, closest_points
    
    return (p2 - p1).length, (p1, p2)


def calculate_angle(obj1, obj2, obj3, angle_type="INTERNAL"):
    """計算三個物件之間的角度"""
    from .bbox_utils import get_bbox_center_world
    # 獲取三個點位
    if angle_type == "CENTER":
        p1 = get_bbox_center_world(obj1)
        p2 = get_bbox_center_world(obj2)
        p3 = get_bbox_center_world(obj3)
    else:
        p1 = obj1.matrix_world.translation
        p2 = obj2.matrix_world.translation
        p3 = obj3.matrix_world.translation
    
    # 計算向量
    v1 = (p1 - p2).normalized()
    v2 = (p3 - p2).normalized()
    
    # 計算角度
    cos_angle = v1.dot(v2)
    cos_angle = max(-1.0, min(1.0, cos_angle))
    angle_rad = math.acos(cos_angle)
    angle_deg = math.degrees(angle_rad)
    
    return angle_rad, angle_deg, (p1, p2, p3)


def calculate_area(obj):
    """計算物件表面積"""
    if obj.type != "MESH":
        return 0.0
    
    total_area = 0.0
    
    for polygon in obj.data.polygons:
        total_area += polygon.area
    
    # 考慮縮放
    scale_factor = obj.scale.x * obj.scale.y * obj.scale.z
    return total_area * abs(scale_factor)


def calculate_volume(obj):
    """計算物件體積"""
    if obj.type != "MESH":
        return 0.0
    
    # 使用 Blender 的體積計算
    volume = obj.data.volume
    
    # 考慮縮放
    scale_factor = obj.scale.x * obj.scale.y * obj.scale.z
    return volume * abs(scale_factor)


def calculate_bounding_box_info(obj):
    """計算邊界框信息"""
    if obj.type != "MESH":
        return None
    
    bbox = obj.bound_box
    bbox_world = [obj.matrix_world @ Vector(corner) for corner in bbox]
    
    # 計算尺寸
    min_point = Vector((float('inf'),) * 3)
    max_point = Vector((float('-inf'),) * 3)
    
    for point in bbox_world:
        min_point.x = min(min_point.x, point.x)
        min_point.y = min(min_point.y, point.y)
        min_point.z = min(min_point.z, point.z)
        max_point.x = max(max_point.x, point.x)
        max_point.y = max(max_point.y, point.y)
        max_point.z = max(max_point.z, point.z)
    
    dimensions = max_point - min_point
    center = (min_point + max_point) / 2
    
    return {
        'dimensions': dimensions,
        'center': center,
        'min_point': min_point,
        'max_point': max_point,
        'volume': dimensions.x * dimensions.y * dimensions.z,
        'local_bbox': bbox,
        'world_bbox': bbox_world
    }


def analyze_object_complexity(obj):
    """分析物件複雜度"""
    if obj.type != "MESH":
        return {'complexity': 0, 'details': '非網格物件'}
    
    vertex_count = len(obj.data.vertices)
    edge_count = len(obj.data.edges)
    face_count = len(obj.data.polygons)
    
    # 計算複雜度指標
    complexity_score = 0
    
    # 頂點複雜度
    if vertex_count > 1000:
        complexity_score += 3
    elif vertex_count > 500:
        complexity_score += 2
    elif vertex_count > 100:
        complexity_score += 1
    
    # 面複雜度
    if face_count > 2000:
        complexity_score += 3
    elif face_count > 1000:
        complexity_score += 2
    elif face_count > 200:
        complexity_score += 1
    
    # 邊面比
    if vertex_count > 0:
        edge_face_ratio = edge_count / face_count
        if edge_face_ratio > 3:
            complexity_score += 2
        elif edge_face_ratio > 2:
            complexity_score += 1
    
    # 材質複雜度
    material_count = len(obj.data.materials)
    if material_count > 5:
        complexity_score += 2
    elif material_count > 2:
        complexity_score += 1
    
    # 修改器複雜度
    modifier_count = len(obj.modifiers)
    if modifier_count > 5:
        complexity_score += 2
    elif modifier_count > 2:
        complexity_score += 1
    
    # 分類複雜度
    if complexity_score >= 8:
        complexity_level = "HIGH"
        description = "高複雜度物件"
    elif complexity_score >= 4:
        complexity_level = "MEDIUM"
        description = "中等複雜度物件"
    else:
        complexity_level = "LOW"
        description = "低複雜度物件"
    
    return {
        'complexity': complexity_score,
        'level': complexity_level,
        'description': description,
        'vertex_count': vertex_count,
        'edge_count': edge_count,
        'face_count': face_count,
        'material_count': material_count,
        'modifier_count': modifier_count
    }


def format_measurement(value, unit="BLENDER", precision=3):
    """格式化測量值"""
    if unit == "METRIC":
        # 轉換為米（假設 Blender 單位為米）
        return f"{value:.{precision}f} m"
    elif unit == "IMPERIAL":
        # 轉換為英尺
        feet = value * 3.28084
        return f"{feet:.{precision}f} ft"
    else:  # BLENDER
        return f"{value:.{precision}f} bu"


def create_measurement_display(context, measurements):
    """創建測量顯示"""
    # 這裡可以添加創建 3D 文字、測量線等的代碼
    # 目前只是返回測量數據供其他模組使用
    
    display_data = {
        'measurements': measurements,
        'timestamp': bpy.context.scene.frame_current,
        'visible': True
    }
    
    return display_data


def clear_measurement_display(context):
    """清除測量顯示"""
    # 這裡可以添加清除 3D 文字、測量線等的代碼
    pass


def export_measurements(measurements, filepath, format="CSV"):
    """導出測量數據"""
    try:
        if format == "CSV":
            import csv
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['object', 'type', 'value', 'unit', 'timestamp']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for measurement in measurements:
                    writer.writerow(measurement)
        
        elif format == "JSON":
            import json
            
            with open(filepath, 'w', encoding='utf-8') as jsonfile:
                json.dump(measurements, jsonfile, indent=2, ensure_ascii=False)
        
        return True
        
    except Exception as e:
        print(f"[SmartAlignPro] 導出測量數據失敗: {e}")
        return False
