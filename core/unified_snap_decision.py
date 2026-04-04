"""
Smart Align Pro - Unified Snap Decision Layer
統一吸附決策層 - 所有吸附模式共用同一套評分與穩定機制

v7.5 統一版：解決多個 snap engine 並行導致的手感不一致問題
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from mathutils import Vector
import bpy


@dataclass
class SnapCandidate:
    """統一吸附候選點格式 - 所有引擎輸出必須轉換為此格式"""
    position_3d: Vector
    snap_type: str  # 'VERTEX', 'EDGE', 'FACE', 'EDGE_MID', 'FACE_CENTER', 'ORIGIN', 'BBOX', 'CUSTOM'
    source_obj: bpy.types.Object = None
    element_index: int = -1
    feature_type: str = "VERTEX"  # VERTEX, EDGE, FACE, CENTER, BOUNDING_BOX
    screen_pos: Vector = field(default_factory=lambda: Vector((0, 0)))
    screen_dist: float = float('inf')
    normal: Vector = field(default_factory=lambda: Vector((0, 0, 1)))
    priority_base: float = 0.0  # 基礎優先級權重


@dataclass
class SnapScore:
    """統一吸附評分結果"""
    candidate: SnapCandidate
    distance_score: float  # 距離分數 (越小越好)
    priority_bonus: float  # 優先級加成
    stability_bonus: float  # 穩定性加成 (same_object, sticky)
    final_score: float  # 最終總分 (越小越好)


@dataclass
class SnapDecision:
    """統一吸附決策結果"""
    selected_candidate: Optional[SnapCandidate]
    is_snapped: bool
    scores: List[SnapScore] = field(default_factory=list)
    decision_reason: str = ""  # 決策原因說明 (debug用)


class SnapLockState:
    """吸附鎖定狀態 - 跨幀穩定機制"""
    
    def __init__(self):
        self.is_snapped: bool = False
        self.last_candidate: Optional[SnapCandidate] = None
        self.last_object: Optional[bpy.types.Object] = None
        self.consecutive_same_object: int = 0
        self.consecutive_same_point: int = 0
        self.is_sticky: bool = False
        self.attach_threshold: float = 12.0
        self.detach_threshold: float = 24.0
        
    def update_sticky_state(self, candidate: Optional[SnapCandidate]):
        """更新黏性狀態"""
        if candidate is None:
            self.consecutive_same_object = max(0, self.consecutive_same_object - 1)
            self.consecutive_same_point = max(0, self.consecutive_same_point - 1)
            self.is_sticky = False
            return
            
        # 檢查是否同物件
        if self.last_object and candidate.source_obj == self.last_object:
            self.consecutive_same_object += 1
        else:
            self.consecutive_same_object = 0
            self.last_object = candidate.source_obj
            
        # 檢查是否同點
        if self._is_same_point(self.last_candidate, candidate):
            self.consecutive_same_point += 1
        else:
            self.consecutive_same_point = 0
            
        self.last_candidate = candidate
        
        # 啟動黏性模式
        if self.consecutive_same_point >= 2:
            self.is_sticky = True
            
    def _is_same_point(self, a: Optional[SnapCandidate], b: Optional[SnapCandidate]) -> bool:
        """檢查是否為同一點"""
        if a is None or b is None:
            return False
        return (
            a.source_obj == b.source_obj and
            a.snap_type == b.snap_type and
            a.element_index == b.element_index
        )
        
    def get_stability_bonus(self, candidate: SnapCandidate) -> float:
        """計算穩定性加成"""
        bonus = 0.0
        
        # 同物件加成
        if self.last_object and candidate.source_obj == self.last_object:
            bonus += min(self.consecutive_same_object * 1.0, 3.0)
            
        # 黏性加成 (stick to same point)
        if self._is_same_point(self.last_candidate, candidate):
            bonus += 4.0 if self.is_sticky else 2.0
            
        return bonus


class UnifiedSnapDecisionEngine:
    """
    統一吸附決策引擎
    
    所有 snap 模式 (CAD, Ultimate, Soft Snap) 都應將候選點
    轉換為 SnapCandidate 格式，並通過此引擎進行統一決策。
    """
    
    def __init__(self):
        self.lock_state = SnapLockState()
        self.priority_weights = {
            'VERTEX': 100,
            'EDGE': 85,
            'EDGE_MID': 80,
            'FACE': 70,
            'FACE_CENTER': 60,
            'ORIGIN': 40,
            'BBOX': 20,
            'CUSTOM': 10
        }
        
    def decide(self, 
               candidates: List[SnapCandidate],
               mouse_pos: Vector,
               context) -> SnapDecision:
        """
        統一吸附決策入口
        
        Args:
            candidates: 候選點列表 (所有引擎的候選點必須轉換為此格式)
            mouse_pos: 滑鼠螢幕座標
            context: Blender context
            
        Returns:
            SnapDecision: 統一決策結果
        """
        if not candidates:
            self.lock_state.update_sticky_state(None)
            return SnapDecision(None, False, [], "無候選點")
            
        # 計算每個候選點的分數
        scores = self._calculate_scores(candidates, mouse_pos)
        
        if not scores:
            self.lock_state.update_sticky_state(None)
            return SnapDecision(None, False, [], "評分失敗")
            
        # 選擇最佳候選點
        best_score = min(scores, key=lambda s: s.final_score)
        best_candidate = best_score.candidate
        
        # 遲滯邏輯 (Hysteresis)
        if not self.lock_state.is_snapped:
            # 未吸附狀態：需要進入 attach_threshold
            if best_candidate.screen_dist <= self.lock_state.attach_threshold:
                self.lock_state.is_snapped = True
                self.lock_state.update_sticky_state(best_candidate)
                return SnapDecision(best_candidate, True, scores, "進入吸附範圍")
            else:
                self.lock_state.update_sticky_state(None)
                return SnapDecision(None, False, scores, "未進入吸附範圍")
        else:
            # 已吸附狀態：需要離開 detach_threshold 才會脫附
            if best_candidate.screen_dist <= self.lock_state.detach_threshold:
                self.lock_state.update_sticky_state(best_candidate)
                return SnapDecision(best_candidate, True, scores, "維持吸附")
            else:
                self.lock_state.is_snapped = False
                self.lock_state.update_sticky_state(None)
                return SnapDecision(None, False, scores, "脫離吸附範圍")
                
    def _calculate_scores(self, 
                         candidates: List[SnapCandidate],
                         mouse_pos: Vector) -> List[SnapScore]:
        """計算所有候選點的評分"""
        scores = []
        
        for cand in candidates:
            # 更新螢幕距離
            cand.screen_dist = (cand.screen_pos - mouse_pos).length
            
            # 距離分數 (越小越好)
            distance_score = cand.screen_dist
            
            # 優先級加成
            priority_weight = self.priority_weights.get(cand.snap_type, 0)
            priority_bonus = priority_weight * 0.1
            
            # 穩定性加成 (同物件、黏性)
            stability_bonus = self.lock_state.get_stability_bonus(cand)
            
            # 最終分數 = 距離 - 所有加成 (越小越好)
            final_score = distance_score - priority_bonus - stability_bonus
            
            scores.append(SnapScore(
                candidate=cand,
                distance_score=distance_score,
                priority_bonus=priority_bonus,
                stability_bonus=stability_bonus,
                final_score=final_score
            ))
            
        return scores
        
    # ============================================================================
    # v7.4 新增：State Manager 方法 - 委托給 snap_scoring_engine
    # ============================================================================
    
    def evaluate_candidates(self, 
                           candidates: List[SnapCandidate], 
                           scoring_context: Dict[str, Any] = None) -> List[SnapScore]:
        """
        v7.4: 評估候選點 - 委托給 SnapScoringEngine
        
        Args:
            candidates: 候選點列表
            scoring_context: 評分上下文
            
        Returns:
            List[SnapScore]: 評分結果列表
        """
        try:
            from .snap_scoring_engine import SnapScoringEngine, SnapScoringContext, SnapCandidate as EngineSnapCandidate
            
            # 轉換為 SnapScoringEngine 格式
            engine_candidates = []
            for cand in candidates:
                engine_cand = EngineSnapCandidate(
                    world_pos=cand.position_3d,
                    normal=cand.normal,
                    feature_type=cand.feature_type or cand.snap_type,
                    distance_3d=0.0,
                    screen_distance=cand.screen_dist,
                    source_object=cand.source_obj,
                    target_object=cand.source_obj,
                    vertex_index=cand.element_index if cand.snap_type == "VERTEX" else -1,
                    edge_index=cand.element_index if cand.snap_type in {"EDGE", "EDGE_MID"} else -1,
                    face_index=cand.element_index if cand.snap_type in {"FACE", "FACE_CENTER"} else -1,
                )
                engine_candidates.append(engine_cand)
            
            # 使用 SnapScoringEngine 評分
            scores = []
            for cand in engine_candidates:
                score = SnapScoringEngine.score_with_context(
                    cand,
                    scoring_context or SnapScoringContext()
                )
                scores.append(SnapScore(
                    candidate=candidates[engine_candidates.index(cand)],
                    distance_score=score,
                    priority_bonus=0.0,
                    stability_bonus=0.0,
                    final_score=score
                ))
            
            return scores
            
        except Exception as e:
            print(f"[UnifiedSnapDecision] evaluate_candidates error: {e}")
            # Fallback: 使用內部評分
            mouse_pos = Vector((0, 0))
            if isinstance(scoring_context, dict):
                mouse_pos = scoring_context.get('mouse_pos', mouse_pos)
            return self._calculate_scores(candidates, mouse_pos)
    
    def select_stable_target(self, 
                            candidates: List[SnapCandidate], 
                            scoring_context: Dict[str, Any] = None) -> Optional[SnapCandidate]:
        """
        v7.4: 選擇穩定目標
        
        考慮 sticky state、intent bias、axis compatibility
        
        Args:
            candidates: 候選點列表
            scoring_context: 評分上下文
            
        Returns:
            Optional[SnapCandidate]: 最佳穩定候選點
        """
        if not candidates:
            return None
            
        # 評估候選點
        scores = self.evaluate_candidates(candidates, scoring_context)
        
        if not scores:
            return None
            
        # 按分數排序
        scores.sort(key=lambda s: s.final_score)
        best = scores[0]
        
        # 應用遲滯邏輯
        if self.lock_state.is_snapped:
            # 檢查是否應該維持當前選擇
            if best.candidate.screen_dist <= self.lock_state.detach_threshold:
                return best.candidate
            else:
                self.lock_state.is_snapped = False
                return None
        else:
            # 檢查是否應該進入吸附
            if best.candidate.screen_dist <= self.lock_state.attach_threshold:
                self.lock_state.is_snapped = True
                return best.candidate
            else:
                return None
    
    def get_decision_debug_info(self) -> Dict[str, Any]:
        """
        v7.4: 獲取決策調試資訊
        
        Returns:
            Dict: 包含當前決策狀態的調試資訊
        """
        return {
            "is_snapped": self.lock_state.is_snapped,
            "is_sticky": self.lock_state.is_sticky,
            "consecutive_same_object": self.lock_state.consecutive_same_object,
            "consecutive_same_point": self.lock_state.consecutive_same_point,
            "attach_threshold": self.lock_state.attach_threshold,
            "detach_threshold": self.lock_state.detach_threshold,
            "last_object": self.lock_state.last_object.name if self.lock_state.last_object else None,
            "priority_weights": self.priority_weights.copy(),
        }
        
    def reset(self):
        """重置引擎狀態"""
        self.lock_state = SnapLockState()


# 全局統一引擎實例
_unified_engine: Optional[UnifiedSnapDecisionEngine] = None


def get_unified_snap_engine() -> UnifiedSnapDecisionEngine:
    """獲取全局統一吸附決策引擎"""
    global _unified_engine
    if _unified_engine is None:
        _unified_engine = UnifiedSnapDecisionEngine()
    return _unified_engine


def reset_unified_snap_engine():
    """重置全局統一吸附決策引擎"""
    global _unified_engine
    if _unified_engine:
        _unified_engine.reset()
    _unified_engine = None
