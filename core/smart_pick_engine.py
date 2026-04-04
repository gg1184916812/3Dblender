"""
Smart Align Pro - Smart Pick Engine
智慧選點引擎 - 自動判斷來源/目標角色
"""

import bpy
from enum import Enum
from mathutils import Vector
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


class SelectionType(Enum):
    """選取類型枚舉"""
    VERT = "VERT"
    EDGE = "EDGE"
    FACE = "FACE"
    OBJECT = "OBJECT"
    MIXED = "MIXED"


@dataclass
class SelectionIntent:
    """選取意圖資料結構"""
    source_obj: Any = None
    target_obj: Any = None
    source_component: Any = None
    target_component: Any = None
    selection_type: SelectionType = SelectionType.OBJECT
    confidence: float = 0.0


class SmartPickEngine:
    """智慧選點引擎 - 自動判斷來源/目標"""
    
    def __init__(self):
        self.last_intent = None
        self.selection_history = []
    
    def detect_selection_role(self, context) -> SelectionIntent:
        """自動判斷選取角色
        
        規則：
        - Active Object → Target
        - Other Selected Objects → Source
        - Edit Mode: 最後選取元素 → Target
        """
        intent = SelectionIntent()
        
        active = context.active_object
        selected = list(context.selected_objects)
        
        if not active:
            return intent
        
        selected_without_active = [obj for obj in selected if obj != active]
        
        if active.type == 'MESH':
            intent.target_obj = active
            intent.selection_type = SelectionType.OBJECT
            
            if selected_without_active:
                intent.source_obj = selected_without_active[0]
            
            intent.confidence = 0.9
        else:
            intent.target_obj = active
            if selected_without_active:
                intent.source_obj = selected_without_active[0]
            intent.confidence = 0.7
        
        self.last_intent = intent
        return intent
    
    def detect_component_type(self, context, obj) -> SelectionType:
        """偵測元件類型（頂點/邊/面）"""
        if context.mode == 'EDIT_MESH':
            bm = None
            if hasattr(obj, 'data') and hasattr(obj.data, 'bm'):
                bm = obj.data.bm
            
            if bm:
                if any(e.select for e in bm.edges):
                    return SelectionType.EDGE
                if any(f.select for f in bm.faces):
                    return SelectionType.FACE
                if any(v.select for v in bm.verts):
                    return SelectionType.VERT
        
        return SelectionType.OBJECT
    
    def get_selection_context(self, context) -> Dict[str, Any]:
        """獲取選取上下文"""
        return {
            "active_object": context.active_object,
            "selected_objects": list(context.selected_objects),
            "mode": context.mode,
            "active_layer_collection": context.view_layer.active_layer_collection,
        }
    
    def is_valid_for_alignment(self, intent: SelectionIntent) -> bool:
        """驗證是否有效對齊選取"""
        if not intent.target_obj:
            return False
        if not intent.source_obj and not intent.target_component:
            return False
        return intent.confidence > 0.5
    
    def suggest_alignment_mode(self, intent: SelectionIntent) -> str:
        """建議對齊模式"""
        if not intent.source_obj:
            return "SURFACE_NORMAL"
        
        source_bbox = intent.source_obj.bound_box
        target_bbox = intent.target_obj.bound_box
        
        source_size = intent.source_obj.dimensions
        target_size = intent.target_obj.dimensions
        
        if (source_size.length / target_size.length) > 2.0:
            return "CHAIN_ALIGNMENT"
        
        return "TWO_POINT"


smart_pick_engine = SmartPickEngine()


def get_smart_pick_engine() -> SmartPickEngine:
    """獲取智慧選點引擎實例"""
    return smart_pick_engine


def detect_selection_role(context) -> SelectionIntent:
    """自動判斷選取角色 - 供外部調用"""
    return smart_pick_engine.detect_selection_role(context)
