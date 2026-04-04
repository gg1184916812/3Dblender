import bpy
import math
from mathutils import Vector, Matrix
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d, region_2d_to_vector_3d
from typing import List, Optional, Dict, Any, Tuple


class SnapCandidate:
    """吸附候選點類別 - v7.5 統一格式，與 unified_snap_decision 相容"""
    def __init__(self, position_3d: Vector, snap_type: str, source_obj: bpy.types.Object = None, element_index: int = -1):
        self.position_3d = position_3d
        self.snap_type = snap_type  # 'VERTEX', 'EDGE_MID', 'FACE_CENTER', 'ORIGIN', 'BBOX', 'CUSTOM'
        self.source_obj = source_obj
        self.element_index = element_index
        self.screen_pos = Vector((0, 0))
        self.screen_dist = float('inf')
        self.priority = 0  # 優先級排序用
        self.normal = Vector((0, 0, 1))
        
        # v7.5 統一格式擴展欄位
        self.feature_type = snap_type  # 與 unified_snap_decision 相容


class UltimateSnapEngine:
    """終極螢幕空間吸附引擎 - v7.5 統一決策版
    
    致命差距②修復：所有吸附決策統一路由至 unified_snap_decision
    """
    
    def __init__(self):
        self.candidates: List[SnapCandidate] = []
        self.active_candidate: Optional[SnapCandidate] = None
        
        # v7.5: 使用統一決策引擎
        self._unified_engine = None
        
    def _get_unified_engine(self):
        """獲取統一決策引擎 (惰性初始化)"""
        if self._unified_engine is None:
            from ..unified_snap_decision import get_unified_snap_engine
            self._unified_engine = get_unified_snap_engine()
        return self._unified_engine

    def update_candidates(self, context):
        """更新場景中的候選點 - 收集階段"""
        self.candidates.clear()
        scene = context.scene
        
        # 遍歷可見物件
        for obj in context.visible_objects:
            if obj.type != 'MESH':
                continue
            
            matrix_world = obj.matrix_world
            mesh = obj.data
            
            # 1. 頂點
            for v in mesh.vertices:
                pos_world = matrix_world @ v.co
                self.candidates.append(SnapCandidate(pos_world, 'VERTEX', obj, v.index))
            
            # 2. 邊中點
            for e in mesh.edges:
                v1 = mesh.vertices[e.vertices[0]].co
                v2 = mesh.vertices[e.vertices[1]].co
                pos_world = matrix_world @ ((v1 + v2) / 2.0)
                self.candidates.append(SnapCandidate(pos_world, 'EDGE_MID', obj, e.index))
            
            # 3. 面中心
            for f in mesh.polygons:
                pos_world = matrix_world @ f.center
                cand = SnapCandidate(pos_world, 'FACE_CENTER', obj, f.index)
                cand.normal = matrix_world.to_3x3() @ f.normal
                self.candidates.append(cand)
            
            # 4. 物件原點
            self.candidates.append(SnapCandidate(matrix_world.translation.copy(), 'ORIGIN', obj))
            
            # 5. Bounding Box 角落
            bbox = [matrix_world @ Vector(corner) for corner in obj.bound_box]
            for corner_pos in bbox:
                self.candidates.append(SnapCandidate(corner_pos, 'BBOX', obj))

    def find_best_snap(self, context, mouse_pos: Vector) -> Optional[SnapCandidate]:
        """v7.5 統一決策入口：將候選點轉換為統一格式，交由 unified_snap_decision 決策"""
        region = context.region
        rv3d = context.space_data.region_3d
        
        # 更新所有候選點的螢幕位置
        for cand in self.candidates:
            screen_pos = location_3d_to_region_2d(region, rv3d, cand.position_3d)
            if screen_pos:
                cand.screen_pos = screen_pos
                cand.screen_dist = (screen_pos - mouse_pos).length
        
        # v7.5 關鍵修復：轉換為統一格式並交由統一引擎決策
        from ..unified_snap_decision import SnapCandidate as UnifiedCandidate
        
        unified_candidates = []
        for cand in self.candidates:
            uc = UnifiedCandidate(
                position_3d=cand.position_3d,
                snap_type=cand.snap_type,
                source_obj=cand.source_obj,
                element_index=cand.element_index,
                feature_type=cand.feature_type,
                screen_pos=cand.screen_pos,
                screen_dist=cand.screen_dist,
                normal=cand.normal,
                priority_base=cand.priority
            )
            unified_candidates.append(uc)
        
        # 呼叫統一決策引擎
        unified_engine = self._get_unified_engine()
        decision = unified_engine.decide(unified_candidates, mouse_pos, context)
        
        # 將決策結果映射回原始候選點
        if decision.selected_candidate:
            # 根據位置找到對應的原始候選點
            for cand in self.candidates:
                if (cand.position_3d == decision.selected_candidate.position_3d and
                    cand.source_obj == decision.selected_candidate.source_obj and
                    cand.snap_type == decision.selected_candidate.snap_type):
                    self.active_candidate = cand
                    return cand
        
        self.active_candidate = None
        return None

    def get_predictive_hint(self, mouse_pos: Vector, mouse_vel: Vector) -> Optional[SnapCandidate]:
        """智慧預測引擎：根據速度向量預測下一個可能的吸附點"""
        if mouse_vel.length < 2.0:
            return None
            
        predicted_pos = mouse_pos + mouse_vel * 5.0 # 預測 5 幀後的位置
        
        best_pred = None
        min_dist = float('inf')
        
        for cand in self.candidates:
            if cand.screen_pos:
                dist = (cand.screen_pos - predicted_pos).length
                if dist < 30.0: # 預測範圍
                    if dist < min_dist:
                        min_dist = dist
                        best_pred = cand
        return best_pred
