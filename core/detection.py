"""
Smart Align Pro - 物件檢測模組
包含物件類型識別和建議系統
"""

import bpy
import re
from collections import defaultdict


class ObjectDetectionResult:
    """物件檢測結果類"""
    def __init__(self, object_type, confidence, suggested_strategy, reasons):
        self.object_type = object_type
        self.confidence = confidence
        self.suggested_strategy = suggested_strategy
        self.reasons = reasons


def detect_object_type(obj, scene_context=None):
    """
    智能物件檢測 - 從決策核心降級為建議系統
    
    Args:
        obj: 要檢測的 Blender 物件
        scene_context: 場景上下文信息
        
    Returns:
        ObjectDetectionResult: 檢測結果，包含類型、信心度、建議策略和原因
    """
    if obj.type != "MESH":
        return ObjectDetectionResult(
            "UNKNOWN", 0.0, "MANUAL", ["非網格物件，無法智能檢測"]
        )
    
    # 收集物件特徵
    features = _extract_object_features(obj)
    
    # 基於特徵進行分類
    detection_results = []
    
    # 建築物件檢測
    building_result = _detect_building_object(features)
    detection_results.append(building_result)
    
    # 機械物件檢測
    mechanical_result = _detect_mechanical_object(features)
    detection_results.append(mechanical_result)
    
    # 遊戲物件檢測
    game_result = _detect_game_object(features)
    detection_results.append(game_result)
    
    # 選擇信心度最高的結果
    best_result = max(detection_results, key=lambda r: r.confidence)
    
    return best_result


def _extract_object_features(obj):
    """提取物件特徵"""
    features = {
        'name': obj.name.lower(),
        'vertex_count': len(obj.data.vertices),
        'face_count': len(obj.data.polygons),
        'edge_count': len(obj.data.edges),
        'dimensions': obj.dimensions.copy(),
        'volume': obj.data.volume,
        'surface_area': obj.data.area,
        'materials': [mat.name.lower() for mat in obj.data.materials],
        'modifiers': [mod.type for mod in obj.modifiers],
        'parent': obj.parent.name if obj.parent else None,
        'collections': [col.name for col in obj.users_collection],
        'scale': obj.scale.copy(),
        'rotation': obj.rotation_euler.copy(),
        'location': obj.location.copy(),
    }
    
    # 計算形狀特徵
    bbox_ratio = max(obj.dimensions) / min(obj.dimensions) if min(obj.dimensions) > 0 else 0
    features['bbox_ratio'] = bbox_ratio
    
    # 計算複雜度
    if features['vertex_count'] > 0:
        features['complexity'] = features['face_count'] / features['vertex_count']
    else:
        features['complexity'] = 0
    
    return features


def _detect_building_object(features):
    """檢測建築物件"""
    confidence = 0.0
    reasons = []
    
    # 名稱檢測
    building_keywords = ['wall', 'floor', 'ceiling', 'door', 'window', 'column', 'beam', 
                        'roof', 'stairs', 'building', 'architecture', '牆', '地板', '天花板',
                        '門', '窗', '柱', '梁', '屋頂', '樓梯', '建築']
    
    name_matches = sum(1 for keyword in building_keywords if keyword in features['name'])
    if name_matches > 0:
        confidence += name_matches * 0.2
        reasons.append(f"名稱包含建築關鍵詞: {name_matches}個")
    
    # 尺寸檢測
    if features['bbox_ratio'] < 3:  # 相對規則的形狀
        confidence += 0.1
        reasons.append("形狀規則，符合建築特徵")
    
    # 材質檢測
    material_keywords = ['concrete', 'brick', 'wood', 'metal', 'glass', 'stone',
                        '混凝土', '磚', '木材', '金屬', '玻璃', '石材']
    
    material_matches = sum(1 for keyword in material_keywords 
                         for mat in features['materials'] if keyword in mat)
    if material_matches > 0:
        confidence += material_matches * 0.1
        reasons.append(f"材質包含建築材料: {material_matches}個")
    
    # 集合檢測
    collection_keywords = ['architecture', 'building', 'interior', 'exterior',
                          '建築', '室內', '室外']
    
    collection_matches = sum(1 for keyword in collection_keywords 
                           for col in features['collections'] if keyword in col)
    if collection_matches > 0:
        confidence += collection_matches * 0.15
        reasons.append(f"位於建築相關集合: {collection_matches}個")
    
    # 限制信心度
    confidence = min(confidence, 0.9)
    
    if confidence > 0.3:
        suggested_strategy = "ARCHITECTURAL"
    else:
        suggested_strategy = "MANUAL"
    
    return ObjectDetectionResult(
        "BUILDING", confidence, suggested_strategy, reasons
    )


def _detect_mechanical_object(features):
    """檢測機械物件"""
    confidence = 0.0
    reasons = []
    
    # 名稱檢測
    mechanical_keywords = ['gear', 'shaft', 'bearing', 'piston', 'bolt', 'screw',
                          'engine', 'motor', 'pump', 'valve', 'spring', 'mechanical',
                          '齒輪', '軸', '軸承', '活塞', '螺栓', '螺絲', '引擎', '馬達',
                          '泵', '閥門', '彈簧', '機械']
    
    name_matches = sum(1 for keyword in mechanical_keywords if keyword in features['name'])
    if name_matches > 0:
        confidence += name_matches * 0.25
        reasons.append(f"名稱包含機械關鍵詞: {name_matches}個")
    
    # 複雜度檢測
    if features['complexity'] > 1.5:  # 高複雜度
        confidence += 0.15
        reasons.append("幾何複雜度高，符合機械特徵")
    
    # 尺寸檢測
    if features['bbox_ratio'] > 5:  # 細長形狀
        confidence += 0.1
        reasons.append("細長形狀，符合機械零件特徵")
    
    # 修改器檢測
    mechanical_modifiers = ['SCREW', 'ARRAY', 'BEVEL', 'SUBSURF']
    modifier_matches = sum(1 for mod in features['modifiers'] if mod in mechanical_modifiers)
    if modifier_matches > 0:
        confidence += modifier_matches * 0.1
        reasons.append(f"包含機械常用修改器: {modifier_matches}個")
    
    # 限制信心度
    confidence = min(confidence, 0.9)
    
    if confidence > 0.3:
        suggested_strategy = "MECHANICAL"
    else:
        suggested_strategy = "MANUAL"
    
    return ObjectDetectionResult(
        "MECHANICAL", confidence, suggested_strategy, reasons
    )


def _detect_game_object(features):
    """檢測遊戲物件"""
    confidence = 0.0
    reasons = []
    
    # 名稱檢測
    game_keywords = ['player', 'enemy', 'npc', 'weapon', 'item', 'prop', 'environment',
                    'character', 'vehicle', 'collectible', 'obstacle', 'game',
                    '玩家', '敵人', '武器', '道具', '環境', '角色', '載具', '收集品',
                    '障礙', '遊戲']
    
    name_matches = sum(1 for keyword in game_keywords if keyword in features['name'])
    if name_matches > 0:
        confidence += name_matches * 0.2
        reasons.append(f"名稱包含遊戲關鍵詞: {name_matches}個")
    
    # 集合檢測
    collection_keywords = ['game', 'level', 'props', 'characters', 'environment',
                          '遊戲', '關卡', '道具', '角色', '環境']
    
    collection_matches = sum(1 for keyword in collection_keywords 
                           for col in features['collections'] if keyword in col)
    if collection_matches > 0:
        confidence += collection_matches * 0.2
        reasons.append(f"位於遊戲相關集合: {collection_matches}個")
    
    # 面數檢測（遊戲物件通常有優化的面數）
    if 100 <= features['face_count'] <= 5000:
        confidence += 0.1
        reasons.append("面數範圍符合遊戲物件特徵")
    
    # 材質檢測
    if len(features['materials']) >= 1:
        confidence += 0.05
        reasons.append("包含材質，符合遊戲物件特徵")
    
    # 限制信心度
    confidence = min(confidence, 0.9)
    
    if confidence > 0.3:
        suggested_strategy = "GAME_DEV"
    else:
        suggested_strategy = "MANUAL"
    
    return ObjectDetectionResult(
        "GAME", confidence, suggested_strategy, reasons
    )


def analyze_scene_objects(context):
    """分析場景中的所有物件"""
    scene = context.scene
    objects = [obj for obj in scene.objects if obj.type == "MESH"]
    
    analysis_results = {
        'total_objects': len(objects),
        'object_types': defaultdict(int),
        'suggested_strategies': defaultdict(int),
        'detection_details': []
    }
    
    for obj in objects:
        detection = detect_object_type(obj, scene)
        analysis_results['object_types'][detection.object_type] += 1
        analysis_results['suggested_strategies'][detection.suggested_strategy] += 1
        
        analysis_results['detection_details'].append({
            'object': obj.name,
            'type': detection.object_type,
            'confidence': detection.confidence,
            'suggested_strategy': detection.suggested_strategy,
            'reasons': detection.reasons
        })
    
    return analysis_results


def get_alignment_strategy_suggestion(detection_result, manual_override=None):
    """
    根據檢測結果獲取對齊策略建議
    
    Args:
        detection_result: ObjectDetectionResult 實例
        manual_override: 手動覆蓋的策略
        
    Returns:
        dict: 包含建議策略和說明的字典
    """
    if manual_override:
        return {
            'strategy': manual_override,
            'reason': '手動指定策略',
            'confidence': 1.0
        }
    
    strategy_map = {
        "BUILDING": {
            'primary': "TWO_POINT",
            'secondary': "SURFACE_NORMAL",
            'reason': '建築物件適用兩點對齊和表面法線對齊',
            'confidence': detection_result.confidence
        },
        "MECHANICAL": {
            'primary': "THREE_POINT",
            'secondary': "TWO_POINT",
            'reason': '機械物件需要精確的三點對齊',
            'confidence': detection_result.confidence
        },
        "GAME": {
            'primary': "AUTO_CONTACT",
            'secondary': "GROUND_ALIGN",
            'reason': '遊戲物件適用接觸對齊和貼地對齊',
            'confidence': detection_result.confidence
        }
    }
    
    strategy_info = strategy_map.get(detection_result.object_type, {
        'primary': "MANUAL",
        'secondary': "TWO_POINT",
        'reason': '未知物件類型，建議手動選擇',
        'confidence': 0.0
    })
    
    return strategy_info


from mathutils import Vector


def _world_vertex(obj, vert_index):
    return obj.matrix_world @ obj.data.vertices[vert_index].co


def find_snap_candidate_on_hit(obj, face_index, hit_location, preferred_mode="AUTO"):
    """在 raycast 命中的面上，依目前 snap mode 找候選點。preferred_mode 可為 AUTO / VERTEX / EDGE / FACE / ORIGIN。"""
    """在 raycast 命中的面上，找最近的頂點 / 邊中點 / 面中心候選點。"""
    try:
        if obj is None or getattr(obj, 'type', None) != 'MESH' or face_index is None or face_index < 0:
            return {
                'location': hit_location.copy() if hit_location is not None else None,
                'type': 'RAY',
                'distance': 0.0,
            }
        mesh = obj.data
        if face_index >= len(mesh.polygons):
            return {
                'location': hit_location.copy() if hit_location is not None else None,
                'type': 'RAY',
                'distance': 0.0,
            }
        poly = mesh.polygons[face_index]
        hit = hit_location.copy()
        mode = (preferred_mode or 'AUTO').upper()
        candidates = []
        verts = list(poly.vertices)

        def add_vertex_candidates():
            for vi in poly.vertices:
                world_co = _world_vertex(obj, vi)
                candidates.append({'location': world_co, 'type': 'VERTEX', 'distance': (world_co - hit).length, 'element': int(vi)})

        def add_edge_candidates():
            for i in range(len(verts)):
                a = _world_vertex(obj, verts[i])
                b = _world_vertex(obj, verts[(i + 1) % len(verts)])
                mid = (a + b) * 0.5
                candidates.append({'location': mid, 'type': 'EDGE_MIDPOINT', 'distance': (mid - hit).length, 'element': [int(verts[i]), int(verts[(i + 1) % len(verts)])]})

        def add_face_candidate():
            center = obj.matrix_world @ poly.center
            candidates.append({'location': center, 'type': 'FACE_CENTER', 'distance': (center - hit).length, 'element': int(face_index)})

        def add_origin_candidate():
            origin = obj.matrix_world.translation.copy()
            candidates.append({'location': origin, 'type': 'ORIGIN', 'distance': (origin - hit).length, 'element': None})

        if mode == 'VERTEX':
            add_vertex_candidates()
        elif mode in {'EDGE', 'EDGE_MIDPOINT'}:
            add_edge_candidates()
        elif mode in {'FACE', 'FACE_CENTER'}:
            add_face_candidate()
        elif mode == 'ORIGIN':
            add_origin_candidate()
        else:
            add_vertex_candidates(); add_edge_candidates(); add_face_candidate()

        best = min(candidates, key=lambda c: c['distance'])
        # 如果最近候選點太遠，退回 ray hit，避免亂跳
        threshold = max(0.0025, obj.dimensions.length * (0.03 if mode != 'AUTO' else 0.015))
        if best['distance'] > threshold:
            return {
                'location': hit,
                'type': 'RAY',
                'distance': 0.0,
                'element': int(face_index),
            }
        return best
    except Exception:
        return {
            'location': hit_location.copy() if hit_location is not None else None,
            'type': 'RAY',
            'distance': 0.0,
        }
