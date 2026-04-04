"""
Smart Align Pro v7.4 - Sticky Intent
黏性意圖系統 - Phase D 核心

作用：避免 hover 抖動造成 solver 切換

核心概念：
- 記錄使用者「最後的明確意圖」
- 滑鼠微抖不應該立刻跳去別的候選
- 提升順手度，這是超越 CAD Transform 的關鍵
"""

import bpy
from mathutils import Vector
from typing import Optional, Dict, Any, List
import time


class StickyCandidate:
    """黏性候選點封裝"""
    def __init__(self, position: Vector, snap_type: str, 
                 source_obj: bpy.types.Object = None, 
                 element_index: int = -1,
                 normal: Vector = None):
        self.position = position.copy()
        self.snap_type = snap_type
        self.source_obj = source_obj
        self.element_index = element_index
        self.normal = normal.copy() if normal else Vector((0, 0, 1))
        
        # 時間戳記
        self.timestamp = time.time()
        self.stick_count = 0  # 黏性計數
        
    def __eq__(self, other):
        """判斷是否為同一候選點"""
        if other is None:
            return False
        return (
            self.source_obj == other.source_obj and
            self.snap_type == other.snap_type and
            self.element_index == other.element_index and
            (self.position - other.position).length < 0.0001
        )
        
    def similarity_score(self, other) -> float:
        """計算相似度分數 (0.0 ~ 1.0)"""
        if other is None:
            return 0.0
            
        score = 0.0
        
        # 同一物件加分
        if self.source_obj == other.source_obj:
            score += 0.3
            
        # 同一類型加分
        if self.snap_type == other.snap_type:
            score += 0.3
            
        # 同一元素加分
        if self.element_index == other.element_index:
            score += 0.2
            
        # 位置接近加分
        dist = (self.position - other.position).length
        if dist < 0.001:
            score += 0.2
        elif dist < 0.01:
            score += 0.1
            
        return score


# ============================================================================
# v7.4 新增：IntentState - 意圖狀態機
# ============================================================================

class IntentState:
    """
    意圖狀態 - v7.4 核心升級
    
    不只是候選點黏性，而是真正的使用者意圖追蹤。
    記錄使用者偏好、方向、模式，形成完整的意圖狀態機。
    """
    
    def __init__(self):
        # 偏好設定
        self.preferred_feature_type: Optional[str] = None
        self.preferred_object = None  # 偏好的物件引用
        self.preferred_direction: Optional[str] = None  # 偏好方向
        self.interaction_mode: Optional[str] = None  # 互動模式
        
        # 狀態數值
        self.confidence: float = 0.0
        self.age: float = 0.0  # 意圖年齡（秒）
        self.last_confirm_time: float = 0.0
        
        # 歷史記錄
        self.history: List[Dict[str, Any]] = []
        self.max_history = 10
        
    def update(self, candidate_type: str, obj=None, direction: str = None, 
               mode: str = None, confidence: float = 0.5):
        """更新意圖狀態"""
        current_time = time.time()
        
        # 如果類型變化，記錄到歷史
        if candidate_type != self.preferred_feature_type:
            self._push_to_history()
            
        # 更新偏好
        self.preferred_feature_type = candidate_type
        if obj is not None:
            self.preferred_object = obj
        if direction is not None:
            self.preferred_direction = direction
        if mode is not None:
            self.interaction_mode = mode
            
        # 更新狀態數值
        self.confidence = confidence
        self.age = current_time - self.last_confirm_time if self.last_confirm_time > 0 else 0
        
    def confirm(self):
        """確認當前意圖（從 commit 調用）"""
        self.last_confirm_time = time.time()
        self.confidence = 1.0
        self._push_to_history(confirmed=True)
        
    def _push_to_history(self, confirmed: bool = False):
        """推送當前狀態到歷史"""
        entry = {
            "feature_type": self.preferred_feature_type,
            "object": self.preferred_object,
            "direction": self.preferred_direction,
            "mode": self.interaction_mode,
            "confidence": self.confidence,
            "timestamp": time.time(),
            "confirmed": confirmed
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)
            
    def get_bias_dict(self) -> Dict[str, Any]:
        """
        獲取 bias 字典 - 供 scoring engine 使用
        
        Returns:
            Dict: 包含偏好設定的字典
        """
        return {
            "preferred_feature_type": self.preferred_feature_type,
            "preferred_object": self.preferred_object,
            "preferred_direction": self.preferred_direction,
            "interaction_mode": self.interaction_mode,
            "confidence": self.confidence,
            "sticky_bonus": self._compute_sticky_bonus(),
            "switch_penalty": self._compute_switch_penalty(),
        }
        
    def _compute_sticky_bonus(self) -> float:
        """計算黏性加成"""
        if self.confidence > 0.7:
            return 2.0
        elif self.confidence > 0.5:
            return 1.0
        return 0.5
        
    def _compute_switch_penalty(self) -> float:
        """計算切換懲罰"""
        # 意圖越新、信心越高，切換成本越高
        if self.age < 0.5 and self.confidence > 0.8:
            return 0.4
        elif self.age < 1.0 and self.confidence > 0.6:
            return 0.25
        return 0.1
        
    def reset(self):
        """重置意圖狀態"""
        self.__init__()


class StickyIntent:
    """
    黏性意圖系統
    
    避免滑鼠微抖造成候選點跳動，提升吸附穩定性。
    這是超越 CAD Transform 的關鍵手感優化。
    """
    
    # 類級別狀態
    _last_candidate: Optional[StickyCandidate] = None
    _stick_start_time: float = 0.0
    _stick_duration: float = 0.0
    _intent_state = None  # v7.4: IntentState 實例
    
    # 配置參數
    STICK_THRESHOLD = 0.6          # 相似度閾值
    STICK_DURATION_MIN = 0.15      # 最小黏性時間 (秒)
    STICK_DURATION_MAX = 0.5     # 最大黏性時間 (秒)
    RELEASE_DISTANCE = 50.0        # 強制釋放距離 (像素)
    
    @classmethod
    def update(cls, new_candidate: StickyCandidate, 
               mouse_screen_pos: Vector,
               last_screen_pos: Optional[Vector] = None) -> StickyCandidate:
        """
        更新黏性候選點
        
        Args:
            new_candidate: 新的候選點
            mouse_screen_pos: 當前滑鼠螢幕位置
            last_screen_pos: 上次候選點的螢幕位置
            
        Returns:
            應該使用的候選點 (可能是舊的或新的)
        """
        current_time = time.time()
        
        # 如果沒有上次候選，直接接受新的
        if cls._last_candidate is None:
            cls._last_candidate = new_candidate
            cls._stick_start_time = current_time
            cls._stick_duration = 0.0
            return new_candidate
            
        # 如果新候選為 None，檢查是否應該釋放
        if new_candidate is None:
            # 檢查是否超過最大黏性時間
            elapsed = current_time - cls._stick_start_time
            if elapsed > cls.STICK_DURATION_MAX:
                cls._last_candidate = None
                cls._stick_duration = 0.0
            return cls._last_candidate
            
        # 計算相似度
        similarity = cls._last_candidate.similarity_score(new_candidate)
        
        # 如果非常相似，維持舊候選
        if similarity >= cls.STICK_THRESHOLD:
            cls._stick_duration = current_time - cls._stick_start_time
            cls._last_candidate.stick_count += 1
            return cls._last_candidate
            
        # 如果差異較大，檢查是否應該切換
        elapsed = current_time - cls._stick_start_time
        
        # 未達最小黏性時間，維持舊候選
        if elapsed < cls.STICK_DURATION_MIN:
            return cls._last_candidate
            
        # 已達最小黏性時間，允許切換
        cls._last_candidate = new_candidate
        cls._stick_start_time = current_time
        cls._stick_duration = 0.0
        
        return new_candidate
        
    @classmethod
    def should_release(cls, mouse_screen_pos: Vector, 
                       candidate_screen_pos: Vector) -> bool:
        """
        檢查是否應該強制釋放黏性
        
        當滑鼠遠離候選點一定距離時，強制釋放。
        """
        if cls._last_candidate is None:
            return True
            
        dist = (mouse_screen_pos - candidate_screen_pos).length
        return dist > cls.RELEASE_DISTANCE
        
    @classmethod
    def force_release(cls):
        """強制釋放黏性"""
        cls._last_candidate = None
        cls._stick_start_time = 0.0
        cls._stick_duration = 0.0
        
    @classmethod
    def get_current_stick_info(cls) -> Dict[str, Any]:
        """獲取當前黏性資訊 (用於調試)"""
        return {
            'has_sticky': cls._last_candidate is not None,
            'stick_duration': cls._stick_duration,
            'stick_count': cls._last_candidate.stick_count if cls._last_candidate else 0,
            'candidate_type': cls._last_candidate.snap_type if cls._last_candidate else None,
        }
        
    @classmethod
    def get_stick_bonus(cls, candidate: StickyCandidate) -> float:
        """
        獲取黏性加成 (用於吸附評分)
        
        當候選點與黏性目標一致時，給予額外加分。
        這會讓系統更傾向於維持當前選擇。
        """
        if cls._last_candidate is None:
            return 0.0
            
        if candidate == cls._last_candidate:
            # 黏性時間越長，加成越高
            base_bonus = 4.0
            time_multiplier = min(cls._stick_duration / cls.STICK_DURATION_MIN, 2.0)
            return base_bonus * time_multiplier
            
        return 0.0
        
    @classmethod
    def update_intent_state(cls, candidate_type: str, obj=None, direction: str = None, 
                            mode: str = None, confidence: float = 0.5):
        """更新意圖狀態"""
        if cls._intent_state is None:
            cls._intent_state = IntentState()
        cls._intent_state.update(candidate_type, obj, direction, mode, confidence)
        
    @classmethod
    def confirm_intent(cls):
        """確認當前意圖"""
        if cls._intent_state:
            cls._intent_state.confirm()
            
    @classmethod
    def get_intent_bias(cls) -> Dict[str, Any]:
        """獲取意圖偏差"""
        if cls._intent_state:
            return cls._intent_state.get_bias_dict()
        return {}
        
    @classmethod
    def reset_intent_state(cls):
        """重置意圖狀態"""
        if cls._intent_state:
            cls._intent_state.reset()
        cls._intent_state = None


class StickyIntentManager:
    """
    黏性意圖管理器
    
    整合到吸附系統的高級管理介面。
    """
    
    def __init__(self):
        self.enabled = True
        self.debug_mode = False
        
    def process_candidate(self, candidate_data: Dict[str, Any],
                          mouse_pos: Vector,
                          context: bpy.types.Context) -> Dict[str, Any]:
        """
        處理候選點，應用黏性意圖邏輯
        
        這是整合到吸附系統的主入口。
        """
        if not self.enabled:
            return candidate_data
            
        # 創建黏性候選點
        sticky_candidate = StickyCandidate(
            position=candidate_data.get('position', Vector((0, 0, 0))),
            snap_type=candidate_data.get('snap_type', 'UNKNOWN'),
            source_obj=candidate_data.get('source_obj'),
            element_index=candidate_data.get('element_index', -1),
            normal=candidate_data.get('normal')
        )
        
        # 更新黏性系統
        result = StickyIntent.update(
            sticky_candidate,
            mouse_pos,
            candidate_data.get('screen_pos')
        )
        
        # 檢查是否強制釋放
        if StickyIntent.should_release(
            mouse_pos, 
            candidate_data.get('screen_pos', mouse_pos)
        ):
            StickyIntent.force_release()
            return candidate_data
            
        # 如果黏性系統返回舊候選，使用舊候選的數據
        if result == sticky_candidate:
            return candidate_data
        else:
            # 轉換回字典格式
            return {
                'position': result.position,
                'snap_type': result.snap_type,
                'source_obj': result.source_obj,
                'element_index': result.element_index,
                'normal': result.normal,
                'is_sticky': True,
                'stick_duration': StickyIntent._stick_duration,
            }
            
    def reset(self):
        """重置黏性系統"""
        StickyIntent.force_release()
        
    def get_debug_info(self) -> str:
        """獲取調試資訊"""
        info = StickyIntent.get_current_stick_info()
        if info['has_sticky']:
            return f"[Sticky] {info['candidate_type']} | {info['stick_duration']:.2f}s | {info['stick_count']}"
        return "[Sticky] None"


# 全局黏性意圖管理器實例
_sticky_manager: Optional[StickyIntentManager] = None


def get_sticky_manager() -> StickyIntentManager:
    """獲取全局黏性意圖管理器"""
    global _sticky_manager
    if _sticky_manager is None:
        _sticky_manager = StickyIntentManager()
    return _sticky_manager


def reset_sticky_manager():
    """重置全局黏性意圖管理器"""
    global _sticky_manager
    if _sticky_manager:
        _sticky_manager.reset()
    _sticky_manager = None


# ============================================================================
# v7.4 新增：意圖歷史與偏見計算
# ============================================================================

# 意圖歷史緩衝區
INTENT_HISTORY: List[Dict[str, Any]] = []
MAX_INTENT_HISTORY = 8  # 最近 8 次意圖


def push_intent(intent: Dict[str, Any]):
    """
    推送意圖到歷史緩衝區
    
    v7.4: 記錄使用者最近的意圖偏好
    """
    global INTENT_HISTORY
    
    INTENT_HISTORY.append({
        "type": intent.get("type", "UNKNOWN"),
        "confidence": intent.get("confidence", 0.0),
        "timestamp": time.time(),
        "candidate_type": intent.get("candidate_type", "UNKNOWN"),
    })
    
    # 限制歷史長度
    if len(INTENT_HISTORY) > MAX_INTENT_HISTORY:
        INTENT_HISTORY.pop(0)


def compute_intent_bias() -> Dict[str, Any]:
    """
    計算意圖偏差
    
    v7.4: 根據歷史記錄計算使用者偏好哪類 snap。
    為了和 snap_scoring_engine 相容，這裡除了類型權重外，
    也回傳 preferred_feature_type / confidence / sticky_bonus 等鍵。
    """
    global INTENT_HISTORY

    # 先吃 IntentState（若存在）
    state_bias: Dict[str, Any] = StickyIntent.get_intent_bias() or {}

    if not INTENT_HISTORY:
        return state_bias

    weights: Dict[str, float] = {}

    # 計算加權次數 (越新的記錄權重越高)
    for i, intent in enumerate(INTENT_HISTORY):
        intent_type = intent.get("type") or intent.get("candidate_type") or "UNKNOWN"
        confidence = float(intent.get("confidence", 0.5))

        # 時間加權：最近的記錄權重更高
        time_weight = (i + 1) / len(INTENT_HISTORY)
        weight = time_weight * confidence
        weights[intent_type] = weights.get(intent_type, 0.0) + weight

    total_weight = sum(weights.values())
    type_bias: Dict[str, float] = {}
    preferred_type = None
    preferred_score = 0.0

    if total_weight > 0:
        for intent_type, weight in weights.items():
            score = weight / total_weight
            type_bias[intent_type] = score
            if score > preferred_score:
                preferred_score = score
                preferred_type = intent_type

    bias: Dict[str, Any] = dict(state_bias)
    bias.setdefault("type_bias", type_bias)
    bias.setdefault("preferred_feature_type", preferred_type)
    bias.setdefault("confidence", preferred_score if preferred_type else 0.0)
    bias.setdefault("sticky_bonus", 0.0)
    bias.setdefault("switch_penalty", 0.1)
    return bias


def infer_user_intent(candidate: Dict[str, Any], 
                      bias: Dict[str, Any] = None,
                      mouse_delta: Vector = None,
                      interaction_mode: str = None) -> Dict[str, Any]:
    """
    推論使用者意圖
    
    v7.4: 結合當前候選和歷史偏見推論意圖
    
    Args:
        candidate: 當前候選點資訊
        bias: 意圖偏差 (由 compute_intent_bias 計算)
        
    Returns:
        Dict: 包含 type 和 confidence 的意圖字典
    """
    if not candidate:
        return {"type": "NONE", "confidence": 0.0}
    
    snap_type = candidate.get("snap_type", "UNKNOWN")

    # 基礎信心度
    base_confidence = 0.5

    type_bias = (bias or {}).get("type_bias", bias or {}) if bias else {}
    preferred_type = (bias or {}).get("preferred_feature_type") if bias else None
    preferred_direction = (bias or {}).get("preferred_direction") if bias else None

    # 如果有 bias，根據 bias 調整信心度
    if type_bias and snap_type in type_bias:
        bias_bonus = type_bias[snap_type] * 0.3  # bias 最多貢獻 0.3
        base_confidence = min(0.95, base_confidence + bias_bonus)

    if preferred_type and preferred_type == snap_type:
        base_confidence = min(0.98, base_confidence + 0.1)

    inferred_direction = preferred_direction
    if mouse_delta and getattr(mouse_delta, "length", 0.0) > 0:
        if abs(mouse_delta.x) >= abs(mouse_delta.y):
            inferred_direction = "VIEW_LEFT_RIGHT"
        else:
            inferred_direction = "VIEW_UP_DOWN"

    # 更新 sticky intent 狀態，讓 scoring engine 可取用 richer bias
    StickyIntent.update_intent_state(
        candidate_type=snap_type,
        obj=candidate.get("source_obj"),
        direction=inferred_direction,
        mode=interaction_mode,
        confidence=base_confidence,
    )

    # 構建意圖
    intent = {
        "type": snap_type,
        "confidence": base_confidence,
        "candidate_type": snap_type,
        "position": candidate.get("position"),
        "source_obj": candidate.get("source_obj"),
        "preferred_direction": inferred_direction,
        "interaction_mode": interaction_mode,
    }

    # 推送此意圖到歷史
    push_intent(intent)

    return intent


def get_intent_switch_penalty(from_type: str, to_type: str) -> float:
    """
    獲取意圖切換成本
    
    v7.4: 計算從一種意圖切換到另一種的成本
    這會影響 solver 切換的門檻
    
    Args:
        from_type: 當前意圖類型
        to_type: 目標意圖類型
        
    Returns:
        float: 切換成本 (0.0 ~ 1.0，越高越不容易切換)
    """
    # 同類型切換無成本
    if from_type == to_type:
        return 0.0
    
    # 定義切換成本矩陣
    switch_costs = {
        # 從頂點切換到其他
        ("VERTEX", "EDGE"): 0.2,
        ("VERTEX", "FACE"): 0.4,
        ("VERTEX", "SMART"): 0.1,
        
        # 從邊切換到其他
        ("EDGE", "VERTEX"): 0.3,
        ("EDGE", "FACE"): 0.3,
        ("EDGE", "SMART"): 0.1,
        
        # 從面切換到其他
        ("FACE", "VERTEX"): 0.4,
        ("FACE", "EDGE"): 0.2,
        ("FACE", "SMART"): 0.1,
        
        # 從 SMART 切換到其他 (較容易)
        ("SMART", "VERTEX"): 0.1,
        ("SMART", "EDGE"): 0.1,
        ("SMART", "FACE"): 0.1,
    }
    
    # 查找成本，預設為 0.25
    cost = switch_costs.get((from_type, to_type), 0.25)
    
    # 考慮歷史偏見：如果目標類型在歷史中很常見，降低切換成本
    bias = compute_intent_bias()
    if to_type in bias and bias[to_type] > 0.3:
        cost *= 0.7  # 降低 30% 成本
    
    return cost


def confirm_intent_from_commit(intent: Dict[str, Any]):
    """
    從 commit 確認意圖
    
    v7.4: 當使用者確認操作後，強化該類意圖的權重
    這會讓系統「記住」使用者真正想要的東西
    
    Args:
        intent: 被確認的意圖
    """
    # 推送兩次以強化
    intent_confirmed = intent.copy()
    intent_confirmed["confidence"] = 1.0  # commit 後信心度設為最高
    intent_confirmed["confirmed"] = True
    
    push_intent(intent_confirmed)
    push_intent(intent_confirmed)  # 推送兩次以加權


def get_intent_history() -> List[Dict[str, Any]]:
    """
    獲取意圖歷史（供調試）
    
    Returns:
        List[Dict]: 意圖歷史列表
    """
    global INTENT_HISTORY
    return INTENT_HISTORY.copy()


def clear_intent_history():
    """清空意圖歷史"""
    global INTENT_HISTORY
    INTENT_HISTORY.clear()
