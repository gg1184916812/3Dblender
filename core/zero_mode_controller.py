"""
Smart Align Pro - Zero Mode System
零模式系統 - 自動判斷對齊模式，使用者不用選
"""

import bpy
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


class AlignmentMode(Enum):
    """對齊模式枚舉"""
    TWO_POINT = "2_POINT"
    THREE_POINT = "3_POINT"
    FACE_ALIGN = "FACE_ALIGN"
    GROUND_ALIGN = "GROUND_ALIGN"
    CONTACT_ALIGN = "CONTACT_ALIGN"
    SURFACE_NORMAL = "SURFACE_NORMAL"
    AUTO_ALIGN = "AUTO_ALIGN"


@dataclass
class ZeroModeContext:
    """零模式上下文"""
    selection_count: int = 0
    selection_types: List[str] = None
    active_object_type: str = ""
    selection_has_rotation: bool = False
    selection_sizes: List = None
    
    def __post_init__(self):
        if self.selection_types is None:
            self.selection_types = []
        if self.selection_sizes is None:
            self.selection_sizes = []


class ZeroModeController:
    """零模式控制器 - 自動判斷對齊模式
    
    使用者流程：
    選來源 → 選目標 → 完成
    不用選模式、不用選方向、不用選來源類型、不用選目標類型
    """
    
    def __init__(self):
        self.current_mode = AlignmentMode.AUTO_ALIGN
        self.confidence_threshold = 0.7
    
    def analyze_context(self, context) -> ZeroModeContext:
        """分析當前選取上下文"""
        selected = list(context.selected_objects)
        active = context.active_object
        
        ctx = ZeroModeContext(
            selection_count=len(selected),
            active_object_type=active.type if active else "",
            selection_has_rotation=self._has_rotation(active) if active else False,
        )
        
        for obj in selected:
            if obj.type == 'MESH':
                ctx.selection_types.append('MESH')
            else:
                ctx.selection_types.append(obj.type)
            
            if hasattr(obj, 'dimensions'):
                ctx.selection_sizes.append(obj.dimensions.length)
        
        return ctx
    
    def _has_rotation(self, obj) -> bool:
        """檢測物件是否有旋轉"""
        if not obj:
            return False
        rotation = obj.rotation_euler
        return rotation.x != 0 or rotation.y != 0 or rotation.z != 0
    
    def auto_detect_alignment_mode(self, context) -> AlignmentMode:
        """自動偵測對齊模式
        
        判斷邏輯：
        1. 根據選取數量
        2. 根據選取類型
        3. 根據物件特性
        """
        ctx = self.analyze_context(context)
        
        if ctx.selection_count == 0:
            return AlignmentMode.AUTO_ALIGN
        
        if ctx.selection_count == 1:
            if ctx.active_object_type == 'MESH':
                return AlignmentMode.GROUND_ALIGN
            return AlignmentMode.AUTO_ALIGN
        
        if ctx.selection_count >= 2:
            if ctx.active_object_type == 'MESH' and 'MESH' in ctx.selection_types:
                if ctx.selection_has_rotation:
                    return AlignmentMode.FACE_ALIGN
                return AlignmentMode.TWO_POINT
        
        return AlignmentMode.AUTO_ALIGN
    
    def get_mode_label(self, mode: AlignmentMode) -> str:
        """獲取模式顯示標籤"""
        labels = {
            AlignmentMode.TWO_POINT: "兩點對齊",
            AlignmentMode.THREE_POINT: "三點對齊",
            AlignmentMode.FACE_ALIGN: "面對齊",
            AlignmentMode.GROUND_ALIGN: "貼地對齊",
            AlignmentMode.CONTACT_ALIGN: "接觸對齊",
            AlignmentMode.SURFACE_NORMAL: "表面法線",
            AlignmentMode.AUTO_ALIGN: "自動對齊",
        }
        return labels.get(mode, mode.value)
    
    def get_required_interaction_steps(self, mode: AlignmentMode) -> int:
        """獲取指定模式需要的互動步驟數"""
        steps = {
            AlignmentMode.TWO_POINT: 4,
            AlignmentMode.THREE_POINT: 6,
            AlignmentMode.FACE_ALIGN: 2,
            AlignmentMode.GROUND_ALIGN: 1,
            AlignmentMode.CONTACT_ALIGN: 2,
            AlignmentMode.SURFACE_NORMAL: 2,
            AlignmentMode.AUTO_ALIGN: 2,
        }
        return steps.get(mode, 4)
    
    def suggest_workflow(self, context) -> Dict[str, Any]:
        """建議工作流程"""
        mode = self.auto_detect_alignment_mode(context)
        ctx = self.analyze_context(context)
        
        return {
            "detected_mode": mode,
            "mode_label": self.get_mode_label(mode),
            "required_steps": self.get_required_interaction_steps(mode),
            "confidence": self._calculate_confidence(ctx, mode),
            "instructions": self._generate_instructions(mode),
        }
    
    def _calculate_confidence(self, ctx: ZeroModeContext, mode: AlignmentMode) -> float:
        """計算偵測信心度"""
        if ctx.selection_count >= 2 and mode in [AlignmentMode.TWO_POINT, AlignmentMode.FACE_ALIGN]:
            return 0.95
        if ctx.selection_count == 1 and mode == AlignmentMode.GROUND_ALIGN:
            return 0.9
        if ctx.selection_has_rotation and mode == AlignmentMode.FACE_ALIGN:
            return 0.85
        return 0.7
    
    def _generate_instructions(self, mode: AlignmentMode) -> List[str]:
        """生成操作指示"""
        instructions = {
            AlignmentMode.TWO_POINT: [
                "1. 選擇來源物件上的一點",
                "2. 選擇來源物件上的第二點",
                "3. 選擇目標物件上的一點",
                "4. 選擇目標物件上的第二點",
            ],
            AlignmentMode.THREE_POINT: [
                "1. 選擇來源基準點",
                "2. 選擇來源方向點",
                "3. 選擇來源平面點",
                "4. 選擇目標基準點",
                "5. 選擇目標方向點",
                "6. 選擇目標平面點",
            ],
            AlignmentMode.FACE_ALIGN: [
                "1. 選擇來源面",
                "2. 選擇目標面",
            ],
            AlignmentMode.GROUND_ALIGN: [
                "1. 選擇要貼地的物件",
            ],
            AlignmentMode.CONTACT_ALIGN: [
                "1. 選擇來源物件",
                "2. 選擇目標物件",
            ],
            AlignmentMode.SURFACE_NORMAL: [
                "1. 選擇來源物件",
                "2. 選擇目標表面",
            ],
        }
        return instructions.get(mode, ["選擇來源物件", "選擇目標物件"])


zero_mode_controller = ZeroModeController()


def get_zero_mode_controller() -> ZeroModeController:
    """獲取零模式控制器實例"""
    return zero_mode_controller


def auto_detect_alignment_mode(context) -> AlignmentMode:
    """自動偵測對齊模式 - 供外部調用"""
    return zero_mode_controller.auto_detect_alignment_mode(context)


def suggest_workflow(context) -> Dict[str, Any]:
    """建議工作流程 - 供外部調用"""
    return zero_mode_controller.suggest_workflow(context)
