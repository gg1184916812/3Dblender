"""
Smart Align Pro - 智慧對齊引擎
超越 CAD Transform 的自動對齊核心
"""

import bpy
import math
from mathutils import Vector, Matrix, Quaternion
from .align_engine import align_engine
from .math_utils import (
    get_closest_point_on_line,
    project_point_to_plane,
    calculate_plane_from_points,
    ray_cast_to_surface
)
from .detection import detect_object_type, get_alignment_strategy_suggestion


class SmartAlignEngine:
    """智慧對齊引擎 - 自動判斷最佳對齊模式"""
    
    def __init__(self):
        self.debug_mode = True
        self.precision = 1e-6
        
        # 對齊模式優先級
        self.alignment_priorities = {
            "VERTEX_SNAP": 1.0,
            "EDGE_SNAP": 0.9,
            "FACE_SNAP": 0.8,
            "PLANE_SNAP": 0.7,
            "NORMAL_SNAP": 0.6,
            "AXIS_SNAP": 0.5
        }
        
        # 幾何分析緩存
        self.geometry_cache = {}

    def log(self, message):
        """調試日誌"""
        if self.debug_mode:
            print(f"[SmartAlignEngine] {message}")

    def smart_align(self, source_obj, target_obj, settings=None):
        """
        智慧對齊 - 自動選擇最佳對齊模式
        
        Args:
            source_obj: 來源物件
            target_obj: 目標物件  
            settings: 設置物件
        """
        self.log(f"開始智慧對齊: {source_obj.name} → {target_obj.name}")
        
        try:
            # 分析物件幾何
            source_analysis = self._analyze_object_geometry(source_obj)
            target_analysis = self._analyze_object_geometry(target_obj)
            
            # 檢測對齊機會
            alignment_opportunities = self._detect_alignment_opportunities(
                source_analysis, target_analysis
            )
            
            # 選擇最佳對齊策略
            best_strategy = self._select_best_alignment_strategy(alignment_opportunities)
            
            if not best_strategy:
                self.log("無法找到合適的對齊策略")
                return False
            
            # 執行智慧對齊
            success = self._execute_smart_alignment(
                source_obj, target_obj, best_strategy, settings
            )
            
            self.log(f"智慧對齊完成: 策略={best_strategy['type']}, 成功={success}")
            return success
            
        except Exception as e:
            self.log(f"智慧對齊失敗: {e}")
            return False

    def _analyze_object_geometry(self, obj):
        """分析物件幾何特徵"""
        if obj.name in self.geometry_cache:
            return self.geometry_cache[obj.name]
        
        analysis = {
            'type': obj.type,
            'bounds': obj.bound_box,
            'center': obj.matrix_world.translation,
            'dimensions': obj.dimensions,
            'volume': obj.dimensions.x * obj.dimensions.y * obj.dimensions.z,
            'surface_area': self._calculate_surface_area(obj),
            'vertices': len(obj.data.vertices) if obj.data else 0,
            'edges': len(obj.data.edges) if obj.data else 0,
            'faces': len(obj.data.polygons) if obj.data else 0,
            'is_regular': self._check_if_regular(obj),
            'dominant_axis': self._find_dominant_axis(obj),
            'symmetry': self._detect_symmetry(obj)
        }
        
        # 緩存分析結果
        self.geometry_cache[obj.name] = analysis
        
        return analysis

    def _calculate_surface_area(self, obj):
        """計算表面積"""
        if not obj.data:
            return 0
        
        total_area = 0
        for polygon in obj.data.polygons:
            total_area += polygon.area
        
        return total_area

    def _check_if_regular(self, obj):
        """檢查是否為規則幾何體"""
        if not obj.data:
            return False
        
        # 簡化檢測：基於邊界框比例
        dims = obj.dimensions
        ratios = [dims.x/dims.y, dims.y/dims.z, dims.x/dims.z]
        
        # 如果比例接近 1，可能是立方體
        if all(abs(ratio - 1.0) < 0.1 for ratio in ratios):
            return True
        
        return False

    def _find_dominant_axis(self, obj):
        """尋找主要軸向"""
        dims = obj.dimensions
        max_dim = max(dims.x, dims.y, dims.z)
        
        if max_dim == dims.x:
            return 'X'
        elif max_dim == dims.y:
            return 'Y'
        else:
            return 'Z'

    def _detect_symmetry(self, obj):
        """檢測對稱性"""
        if not obj.data:
            return None
        
        # 簡化實現：基於邊界框中心
        from ..utils.bbox_utils import get_bbox_center_world
        center_local = get_bbox_center_world(obj)
        center = obj.matrix_world.inverted() @ center_local
        if abs(center.x) < 0.01 and abs(center.y) < 0.01 and abs(center.z) < 0.01:
            return 'CENTRAL'
        
        return None

    def _detect_alignment_opportunities(self, source_analysis, target_analysis):
        """檢測對齊機會"""
        opportunities = []
        
        # 頂點對齊機會
        vertex_opportunities = self._detect_vertex_snap_opportunities(
            source_analysis, target_analysis
        )
        opportunities.extend(vertex_opportunities)
        
        # 邊緣對齊機會
        edge_opportunities = self._detect_edge_snap_opportunities(
            source_analysis, target_analysis
        )
        opportunities.extend(edge_opportunities)
        
        # 面對齊機會
        face_opportunities = self._detect_face_snap_opportunities(
            source_analysis, target_analysis
        )
        opportunities.extend(face_opportunities)
        
        # 平面對齊機會
        plane_opportunities = self._detect_plane_snap_opportunities(
            source_analysis, target_analysis
        )
        opportunities.extend(plane_opportunities)
        
        # 法線對齊機會
        normal_opportunities = self._detect_normal_snap_opportunities(
            source_analysis, target_analysis
        )
        opportunities.extend(normal_opportunities)
        
        # 軸對齊機會
        axis_opportunities = self._detect_axis_snap_opportunities(
            source_analysis, target_analysis
        )
        opportunities.extend(axis_opportunities)
        
        # 按優先級排序
        opportunities.sort(
            key=lambda x: self.alignment_priorities.get(x['type'], 0),
            reverse=True
        )
        
        return opportunities

    def _detect_vertex_snap_opportunities(self, source_analysis, target_analysis):
        """檢測頂點吸附機會"""
        opportunities = []
        
        # 檢查頂點數量
        if source_analysis['vertices'] > 0 and target_analysis['vertices'] > 0:
            # 計算最近頂點距離
            min_distance = self._calculate_min_vertex_distance(
                source_analysis, target_analysis
            )
            
            if min_distance < 1.0:  # 1單位內認為是機會
                opportunities.append({
                    'type': 'VERTEX_SNAP',
                    'confidence': 1.0 - min_distance,
                    'distance': min_distance,
                    'description': f'頂點吸附機會 (距離: {min_distance:.3f})'
                })
        
        return opportunities

    def _detect_edge_snap_opportunities(self, source_analysis, target_analysis):
        """檢測邊緣吸附機會"""
        opportunities = []
        
        if source_analysis['edges'] > 0 and target_analysis['edges'] > 0:
            # 檢查是否有平行邊緣
            parallel_edges = self._find_parallel_edges(
                source_analysis, target_analysis
            )
            
            if parallel_edges:
                opportunities.append({
                    'type': 'EDGE_SNAP',
                    'confidence': 0.9,
                    'edges': parallel_edges,
                    'description': f'邊緣吸附機會 ({len(parallel_edges)} 對平行邊)'
                })
        
        return opportunities

    def _detect_face_snap_opportunities(self, source_analysis, target_analysis):
        """檢測面吸附機會"""
        opportunities = []
        
        if source_analysis['faces'] > 0 and target_analysis['faces'] > 0:
            # 檢查是否有平行面
            parallel_faces = self._find_parallel_faces(
                source_analysis, target_analysis
            )
            
            if parallel_faces:
                opportunities.append({
                    'type': 'FACE_SNAP',
                    'confidence': 0.8,
                    'faces': parallel_faces,
                    'description': f'面吸附機會 ({len(parallel_faces)} 對平行面)'
                })
        
        return opportunities

    def _detect_plane_snap_opportunities(self, source_analysis, target_analysis):
        """檢測平面吸附機會"""
        opportunities = []
        
        # 檢查主要平面
        if source_analysis['is_regular'] and target_analysis['is_regular']:
            opportunities.append({
                'type': 'PLANE_SNAP',
                'confidence': 0.7,
                'description': '規則物體平面對齊'
            })
        
        return opportunities

    def _detect_normal_snap_opportunities(self, source_analysis, target_analysis):
        """檢測法線吸附機會"""
        opportunities = []
        
        # 檢查表面法線對齊
        if source_analysis['surface_area'] > 0 and target_analysis['surface_area'] > 0:
            opportunities.append({
                'type': 'NORMAL_SNAP',
                'confidence': 0.6,
                'description': '表面法線對齊'
            })
        
        return opportunities

    def _detect_axis_snap_opportunities(self, source_analysis, target_analysis):
        """檢測軸對齊機會"""
        opportunities = []
        
        # 檢查主要軸向對齊
        if (source_analysis['dominant_axis'] == target_analysis['dominant_axis'] and
            source_analysis['dominant_axis'] is not None):
            opportunities.append({
                'type': 'AXIS_SNAP',
                'confidence': 0.5,
                'axis': source_analysis['dominant_axis'],
                'description': f'主要軸向對齊 ({source_analysis["dominant_axis"]} 軸)'
            })
        
        return opportunities

    def _calculate_min_vertex_distance(self, source_analysis, target_analysis):
        """計算最小頂點距離"""
        # 簡化實現：使用邊界框距離
        source_center = Vector(source_analysis['center'])
        target_center = Vector(target_analysis['center'])
        
        return (source_center - target_center).length

    def _find_parallel_edges(self, source_analysis, target_analysis):
        """尋找平行邊緣"""
        # 簡化實現：返回模擬數據
        return []

    def _find_parallel_faces(self, source_analysis, target_analysis):
        """尋找平行面"""
        # 簡化實現：返回模擬數據
        return []

    def _select_best_alignment_strategy(self, opportunities):
        """選擇最佳對齊策略"""
        if not opportunities:
            return None
        
        # 選擇置信度最高的策略
        best = opportunities[0]
        
        # 如果有多個相同置信度的策略，選擇距離最近的
        if len(opportunities) > 1:
            same_confidence = [op for op in opportunities 
                            if abs(op['confidence'] - best['confidence']) < 0.01]
            if len(same_confidence) > 1:
                # 選擇距離最近的
                best = min(same_confidence, 
                          key=lambda x: x.get('distance', float('inf')))
        
        return best

    def _execute_smart_alignment(self, source_obj, target_obj, strategy, settings):
        """執行智慧對齊"""
        strategy_type = strategy['type']
        
        try:
            if strategy_type == 'VERTEX_SNAP':
                return self._execute_vertex_snap(source_obj, target_obj, strategy)
            elif strategy_type == 'EDGE_SNAP':
                return self._execute_edge_snap(source_obj, target_obj, strategy)
            elif strategy_type == 'FACE_SNAP':
                return self._execute_face_snap(source_obj, target_obj, strategy)
            elif strategy_type == 'PLANE_SNAP':
                return self._execute_plane_snap(source_obj, target_obj, strategy)
            elif strategy_type == 'NORMAL_SNAP':
                return self._execute_normal_snap(source_obj, target_obj, strategy)
            elif strategy_type == 'AXIS_SNAP':
                return self._execute_axis_snap(source_obj, target_obj, strategy)
            else:
                self.log(f"未知的對齊策略: {strategy_type}")
                return False
                
        except Exception as e:
            self.log(f"執行對齊策略失敗: {e}")
            return False

    def _execute_vertex_snap(self, source_obj, target_obj, strategy):
        """執行頂點吸附"""
        # 簡化實現：移動來源物件到目標物件
        source_obj.location = target_obj.location
        return True

    def _execute_edge_snap(self, source_obj, target_obj, strategy):
        """執行邊緣吸附"""
        # 簡化實現：對齊邊緣
        return align_engine.align_two_point(source_obj, target_obj, "0", "1", "0", "1")

    def _execute_face_snap(self, source_obj, target_obj, strategy):
        """執行面吸附"""
        # 簡化實現：表面法線對齊
        return align_engine.align_surface_normal(source_obj, target_obj)

    def _execute_plane_snap(self, source_obj, target_obj, strategy):
        """執行平面吸附"""
        # 簡化實現：三點對齊
        source_points = [
            source_obj.matrix_world @ Vector((-0.5, -0.5, 0)),
            source_obj.matrix_world @ Vector((0.5, -0.5, 0)),
            source_obj.matrix_world @ Vector((0, 0.5, 0))
        ]
        target_points = [
            target_obj.matrix_world @ Vector((-0.5, -0.5, 0)),
            target_obj.matrix_world @ Vector((0.5, -0.5, 0)),
            target_obj.matrix_world @ Vector((0, 0.5, 0))
        ]
        
        return align_engine.align_three_point(source_obj, target_obj, source_points, target_points)

    def _execute_normal_snap(self, source_obj, target_obj, strategy):
        """執行法線吸附"""
        return align_engine.align_surface_normal(source_obj, target_obj)

    def _execute_axis_snap(self, source_obj, target_obj, strategy):
        """執行軸對齊"""
        axis = strategy.get('axis', 'Z')
        
        # 對齊主要軸向
        if axis == 'X':
            source_obj.rotation_euler.x = target_obj.rotation_euler.x
        elif axis == 'Y':
            source_obj.rotation_euler.y = target_obj.rotation_euler.y
        elif axis == 'Z':
            source_obj.rotation_euler.z = target_obj.rotation_euler.z
        
        return True

    def clear_cache(self):
        """清除幾何緩存"""
        self.geometry_cache.clear()
        self.log("幾何分析緩存已清除")


# 全局智慧對齊引擎實例
smart_align_engine = SmartAlignEngine()


# 公共 API 函數
def smart_align_objects(source_obj, target_obj, settings=None):
    """智慧對齊物件 API"""
    return smart_align_engine.smart_align(source_obj, target_obj, settings)


def smart_align_batch(objects, target_obj, settings=None):
    """批量智慧對齊 API"""
    results = []
    for obj in objects:
        if obj != target_obj:
            success = smart_align_objects(obj, target_obj, settings)
            results.append({"object": obj, "success": success})
    
    return results


def get_alignment_suggestions(source_obj, target_obj):
    """獲取對齊建議"""
    source_analysis = smart_align_engine._analyze_object_geometry(source_obj)
    target_analysis = smart_align_engine._analyze_object_geometry(target_obj)
    
    opportunities = smart_align_engine._detect_alignment_opportunities(
        source_analysis, target_analysis
    )
    
    return opportunities
