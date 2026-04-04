"""
Smart Align Pro - Snap Scoring Engine
v7.4 超越版 - 統一候選點評分系統

核心設計：所有吸附判斷都走這個評分模型
"""

import bpy
from mathutils import Vector
from typing import List, Dict, Any, Optional, Tuple
import math


class SnapCandidate:
    """吸附候選點 - 統一數據結構"""
    
    def __init__(
        self,
        world_pos: Vector,
        normal: Vector,
        feature_type: str,  # VERTEX, EDGE, FACE, CENTER, BBOX
        distance_3d: float,
        screen_distance: float,
        topology_weight: float = 1.0,
        source_object=None,
        target_object=None,
        face_index: int = -1,
        edge_index: int = -1,
        vertex_index: int = -1,
    ):
        self.world_pos = world_pos
        self.normal = normal.normalized() if normal.length > 0 else Vector((0, 0, 1))
        self.feature_type = feature_type
        self.distance_3d = distance_3d
        self.screen_distance = screen_distance
        self.topology_weight = topology_weight
        self.source_object = source_object
        self.target_object = target_object
        self.face_index = face_index
        self.edge_index = edge_index
        self.vertex_index = vertex_index
        
        # 計算後的分數
        self.score = 0.0
        self.raw_score = 0.0
        self.hysteresis_boost = 1.0
        self.intent_boost = 1.0
        self.axis_boost = 1.0
        self.sticky_boost = 1.0
        
    def __repr__(self):
        return f"SnapCandidate({self.feature_type}, score={self.score:.3f}, 3d={self.distance_3d:.3f})"


class SnapScoringContext:
    """
    v7.4: 評分上下文 - 意圖感知評分所需的完整資訊
    """
    
    def __init__(
        self,
        mouse_velocity: Vector = None,
        axis_lock: str = None,
        mode: str = "AUTO",
        intent_bias: Dict[str, Any] = None,
        current_target: SnapCandidate = None,
        view_axis: str = None,
        interaction_mode: str = None,
    ):
        self.mouse_velocity = mouse_velocity or Vector((0, 0))
        self.axis_lock = axis_lock
        self.mode = mode
        self.intent_bias = intent_bias or {}
        self.current_target = current_target
        self.view_axis = view_axis
        self.interaction_mode = interaction_mode


class SnapScoringEngine:
    """
    統一 Snap 評分引擎
    
    所有吸附候選點的評分都經過這個系統
    確保手感一致、可預測
    """
    
    # 特徵類型基礎權重 - 頂點最高，bbox 最低
    FEATURE_WEIGHT = {
        "VERTEX": 1.0,
        "EDGE": 0.85,
        "FACE": 0.70,
        "CENTER": 0.60,
        "BOUNDING_BOX": 0.30,
        "GRID": 0.25,
    }
    
    # 距離衰減參數
    DISTANCE_DECAY_3D = 0.5  # 3D 距離衰減係數
    DISTANCE_DECAY_SCREEN = 0.8  # 螢幕距離衰減係數
    
    # 遲滯參數
    HYSTERESIS_FACTOR = 1.15  # 新候選需要比當前好 15%
    STICKY_RADIUS = 18.0  # 黏著半徑（像素）
    
    def __init__(self):
        self.current_target: Optional[SnapCandidate] = None
        self.last_candidate_time = 0
        
    @classmethod
    def score(cls, candidate: SnapCandidate, 
              mouse_velocity: Vector = None,
              axis_lock: str = None,
              mode: str = "AUTO") -> float:
        """
        計算候選點綜合分數
        
        Args:
            candidate: 候選點
            mouse_velocity: 滑鼠移動方向（用於預測意圖）
            axis_lock: 當前軸鎖定狀態
            mode: 當前對齊模式
            
        Returns:
            0.0 ~ 1.0 的分數，越高越好
        """
        # 1. 特徵類型權重 (50%)
        feature_score = cls.FEATURE_WEIGHT.get(candidate.feature_type, 0.2)
        
        # 2. 3D 距離衰減 (20%)
        # 距離越近越好，但使用指數衰減避免極端值
        distance_score = math.exp(-cls.DISTANCE_DECAY_3D * candidate.distance_3d)
        distance_score = max(0.0, min(1.0, distance_score))
        
        # 3. 螢幕距離衰減 (20%)
        # 螢幕上越近越好
        screen_score = math.exp(-cls.DISTANCE_DECAY_SCREEN * candidate.screen_distance / 50.0)
        screen_score = max(0.0, min(1.0, screen_score))
        
        # 4. 拓撲權重加成 (10%)
        topology_score = max(0.0, min(1.0, candidate.topology_weight))
        
        # 組合分數
        total_score = (
            feature_score * 0.50 +
            distance_score * 0.20 +
            screen_score * 0.20 +
            topology_score * 0.10
        )
        
        # 應用遲滯加成
        total_score *= candidate.hysteresis_boost
        
        # 儲存 raw score
        candidate.raw_score = total_score
        
        # 應用模式加成
        if mode == "CONTACT" and candidate.feature_type in ["FACE", "VERTEX"]:
            total_score *= 1.1
        elif mode == "ALIGN" and candidate.feature_type in ["EDGE", "CENTER"]:
            total_score *= 1.05
            
        candidate.score = total_score
        return total_score
    
    @classmethod
    def score_with_context(cls, candidate: SnapCandidate, context: SnapScoringContext) -> float:
        """
        v7.4: 使用完整上下文進行意圖感知評分
        """
        # 先計算基礎分數
        raw_score = cls.score(
            candidate,
            mouse_velocity=context.mouse_velocity,
            axis_lock=context.axis_lock,
            mode=context.mode
        )
        
        # 計算各種加成
        candidate.intent_boost = cls.compute_intent_boost(candidate, context.intent_bias)
        candidate.axis_boost = cls.compute_axis_compatibility_boost(
            candidate, context.axis_lock, context.view_axis
        )
        candidate.sticky_boost = cls.compute_sticky_boost(candidate, context.current_target)
        
        # 組合最終分數
        final_score = (
            candidate.raw_score *
            candidate.hysteresis_boost *
            candidate.intent_boost *
            candidate.axis_boost *
            candidate.sticky_boost
        )
        
        candidate.score = final_score
        return final_score
    
    @classmethod
    def compute_intent_boost(cls, candidate: SnapCandidate, intent_bias: Dict[str, Any]) -> float:
        """計算意圖加成"""
        if not intent_bias:
            return 1.0
            
        boost = 1.0
        
        # 特徵類型匹配加成
        preferred_type = intent_bias.get("preferred_feature_type")
        if preferred_type and candidate.feature_type == preferred_type:
            confidence = intent_bias.get("confidence", 0.5)
            boost += 0.3 * confidence
            
        # 物件匹配加成
        preferred_obj = intent_bias.get("preferred_object")
        if preferred_obj and candidate.target_object == preferred_obj:
            boost += 0.2
            
        # 方向匹配加成
        preferred_dir = intent_bias.get("preferred_direction")
        if preferred_dir:
            boost += 0.1
            
        # 互動模式相關性加成
        interaction_mode = intent_bias.get("interaction_mode")
        if interaction_mode:
            if interaction_mode == "TWO_POINT" and candidate.feature_type in ["VERTEX", "EDGE"]:
                boost += 0.15
            elif interaction_mode == "THREE_POINT" and candidate.feature_type == "FACE":
                boost += 0.15
                
        # 應用黏性加成
        sticky_bonus = intent_bias.get("sticky_bonus", 0)
        boost += sticky_bonus * 0.1
        
        return min(boost, 2.0)  # 上限 2x
    
    @classmethod
    def compute_axis_compatibility_boost(cls, candidate: SnapCandidate, 
                                          axis_lock: str, view_axis: str = None) -> float:
        """計算軸兼容性加成"""
        if not axis_lock or axis_lock == "NONE":
            return 1.0
            
        # view axis 相關加成
        if view_axis and "VIEW" in axis_lock:
            return 1.2
            
        return 1.0
    
    @classmethod
    def compute_sticky_boost(cls, candidate: SnapCandidate, 
                              current_target: SnapCandidate) -> float:
        """計算黏性加成"""
        if current_target is None:
            return 1.0
            
        # 如果是同一候選，給予黏性加成
        if cls._is_same_candidate(candidate, current_target):
            return cls.HYSTERESIS_FACTOR
            
        return 1.0
    
    @classmethod
    def select_best_candidate(
        cls,
        candidates: List[SnapCandidate],
        current_target: Optional[SnapCandidate] = None,
        mouse_x: float = 0,
        mouse_y: float = 0,
        mouse_velocity: Vector = None,
        axis_lock: str = None,
        mode: str = "AUTO"
    ) -> Optional[SnapCandidate]:
        """
        從候選列表中選擇最佳候選
        
        這是統一的選擇邏輯，所有吸附都走這裡
        """
        if not candidates:
            return None

        # 支援直接傳入 SnapScoringContext 作為第二個參數
        scoring_context = None
        if isinstance(current_target, SnapScoringContext):
            scoring_context = current_target
            current_target = scoring_context.current_target
            mouse_velocity = scoring_context.mouse_velocity
            axis_lock = scoring_context.axis_lock
            mode = scoring_context.mode

        # 計算所有候選分數
        for candidate in candidates:
            if scoring_context is not None:
                cls.score_with_context(candidate, scoring_context)
            else:
                cls.score(candidate, mouse_velocity, axis_lock, mode)
        
        # 應用遲滯邏輯
        if current_target is not None:
            for candidate in candidates:
                # 如果是同一個候選，給予遲滯加成
                if cls._is_same_candidate(candidate, current_target):
                    candidate.hysteresis_boost = cls.HYSTERESIS_FACTOR
                    
        # 按分數排序
        candidates.sort(key=lambda c: c.score, reverse=True)
        
        # 檢查是否應該切換目標
        best_candidate = candidates[0]
        
        if current_target is not None:
            # 只有新候選明顯更好時才切換
            if best_candidate.score > current_target.score * cls.HYSTERESIS_FACTOR:
                return best_candidate
            else:
                return current_target
        
        return best_candidate
    
    @classmethod
    def _is_same_candidate(cls, a: SnapCandidate, b: SnapCandidate) -> bool:
        """檢查兩個候選是否指向同一個特徵"""
        if a.feature_type != b.feature_type:
            return False
            
        # 檢查位置接近度
        distance = (a.world_pos - b.world_pos).length
        if distance > 0.01:  # 1cm 容差
            return False
            
        # 檢查索引
        if a.feature_type == "VERTEX" and a.vertex_index == b.vertex_index:
            return True
        if a.feature_type == "EDGE" and a.edge_index == b.edge_index:
            return True
        if a.feature_type == "FACE" and a.face_index == b.face_index:
            return True
            
        return distance < 0.001  # 非常接近就認為是同一個
    
    @classmethod
    def should_release(cls, 
                       current_target: SnapCandidate,
                       mouse_x: float, 
                       mouse_y: float,
                       mouse_velocity: Vector = None) -> bool:
        """
        判斷是否應該釋放當前黏著的候選
        
        這是 Sticky Release 的核心邏輯
        """
        if current_target is None:
            return False
            
        # 計算螢幕距離
        from bpy_extras import view3d_utils
        region = bpy.context.region
        rv3d = bpy.context.space_data.region_3d
        
        if not region or not rv3d:
            return False
            
        screen_pos = view3d_utils.location_3d_to_region_2d(
            region, rv3d, current_target.world_pos
        )
        
        if screen_pos is None:
            return True  # 候選不在視野內，釋放
            
        screen_distance = (Vector((mouse_x, mouse_y)) - screen_pos).length
        
        # 超過黏著半徑就釋放
        if screen_distance > cls.STICKY_RADIUS:
            return True
            
        # 檢查滑鼠移動方向（如果滑鼠快速遠離，提前釋放）
        if mouse_velocity is not None and mouse_velocity.length > 50:
            # 快速移動時放寬釋放條件
            if screen_distance > cls.STICKY_RADIUS * 0.6:
                return True
                
        return False


# 全局評分引擎實例
scoring_engine = SnapScoringEngine()


def score_candidate(candidate: SnapCandidate, **kwargs) -> float:
    """便捷函數：評分單個候選"""
    return SnapScoringEngine.score(candidate, **kwargs)


def select_best(candidates: List[SnapCandidate], **kwargs) -> Optional[SnapCandidate]:
    """便捷函數：選擇最佳候選"""
    return SnapScoringEngine.select_best_candidate(candidates, **kwargs)


def should_release_target(current_target: SnapCandidate, mouse_x: float, mouse_y: float, **kwargs) -> bool:
    """便捷函數：判斷是否釋放"""
    return SnapScoringEngine.should_release(current_target, mouse_x, mouse_y, **kwargs)
