"""
Smart Align Pro - 增強錯誤回饋系統
商業級的錯誤處理和用戶指引
"""

import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, StringProperty
from typing import List, Dict, Any, Optional
import time

from ..keymap_manager import log_hotkey_trigger, log_hotkey_cancel


class SmartAlignError:
    """智能錯誤處理系統"""
    
    def __init__(self):
        self.error_codes = {
            "NO_ACTIVE_OBJECT": {
                "message": "請先選取一個物件作為 Active Object",
                "solution": "右鍵點擊目標物件，或按住 Shift 選取多個物件",
                "severity": "WARNING"
            },
            "NO_MESH_OBJECTS": {
                "message": "找不到 Mesh 物件",
                "solution": "請確保選取的物件包含幾何體數據",
                "severity": "WARNING"
            },
            "INSUFFICIENT_SOURCE_POINTS": {
                "message": "來源點位不足",
                "solution": "請繼續選擇來源點位，直到滿足要求",
                "severity": "INFO"
            },
            "INSUFFICIENT_TARGET_POINTS": {
                "message": "目標點位不足",
                "solution": "請繼續選擇目標點位，直到滿足要求",
                "severity": "INFO"
            },
            "POINTS_COLINEAR": {
                "message": "三點共線，無法建立平面",
                "solution": "請選擇不共線的三個點，或使用兩點對齊模式",
                "severity": "ERROR"
            },
            "VECTORS_TOO_SHORT": {
                "message": "對齊向量過短",
                "solution": "請選擇距離較遠的點位以獲得更穩定的對齊",
                "severity": "WARNING"
            },
            "CANNOT_ALIGN_TO_SELF": {
                "message": "無法對齊到自身",
                "solution": "請選擇不同的來源和目標物件",
                "severity": "WARNING"
            },
            "NO_VALID_GEOMETRY": {
                "message": "找不到有效的幾何體",
                "solution": "請確保目標物件包含可吸附的頂點、邊或面",
                "severity": "WARNING"
            },
            "TRANSFORM_FAILED": {
                "message": "變換計算失敗",
                "solution": "請檢查物件狀態，或重新啟動對齊操作",
                "severity": "ERROR"
            },
            "PREVIEW_ERROR": {
                "message": "預覽系統錯誤",
                "solution": "請重新啟動對齊操作，或檢查設置",
                "severity": "WARNING"
            },
            "SNAP_ENGINE_ERROR": {
                "message": "吸附引擎錯誤",
                "solution": "請檢查視角和幾何體，或重新啟動操作",
                "severity": "WARNING"
            }
        }
        
    def get_error_info(self, error_code: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """獲取錯誤信息"""
        base_info = self.error_codes.get(error_code, {
            "message": "未知錯誤",
            "solution": "請重新啟動操作",
            "severity": "ERROR"
        })
        
        # 根據上下文調整信息
        if context:
            return self._customize_error_info(base_info, context)
        
        return base_info
    
    def _customize_error_info(self, base_info: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """根據上下文自定義錯誤信息"""
        info = base_info.copy()
        
        # 根據操作類型調整解決方案
        operation = context.get("operation", "")
        if operation == "TWO_POINT":
            if "INSUFFICIENT" in context.get("error_code", ""):
                info["solution"] = "需要選擇 2 個來源點和 2 個目標點"
        elif operation == "THREE_POINT":
            if "INSUFFICIENT" in context.get("error_code", ""):
                info["solution"] = "需要選擇 3 個來源點和 3 個目標點"
        elif operation == "CAD_SNAP":
            if "INSUFFICIENT" in context.get("error_code", ""):
                info["solution"] = "需要選擇 From 點和 To 點"
        
        return info
    
    def format_error_message(self, error_code: str, context: Optional[Dict] = None) -> str:
        """格式化錯誤消息"""
        info = self.get_error_info(error_code, context)
        
        severity_icons = {
            "INFO": "ℹ️",
            "WARNING": "⚠️", 
            "ERROR": "❌"
        }
        
        icon = severity_icons.get(info["severity"], "❓")
        message = f"{icon} {info['message']}"
        
        if info["solution"]:
            message += f"\n💡 解決方案：{info['solution']}"
        
        return message


# 全局錯誤處理器
error_handler = SmartAlignError()


class SmartAlignValidator:
    """智能驗證系統"""
    
    @staticmethod
    def validate_objects(context) -> Dict[str, Any]:
        """驗證物件選擇"""
        active = context.active_object
        selected = context.selected_objects
        
        if not active:
            return {
                "valid": False,
                "error_code": "NO_ACTIVE_OBJECT",
                "context": {"operation": "GENERAL"}
            }
        
        if active.type != "MESH":
            return {
                "valid": False,
                "error_code": "NO_MESH_OBJECTS",
                "context": {"operation": "GENERAL"}
            }
        
        return {"valid": True}
    
    @staticmethod
    def validate_points(source_points: List, target_points: List, operation: str) -> Dict[str, Any]:
        """驗證點位"""
        if operation == "TWO_POINT":
            if len(source_points) < 2:
                return {
                    "valid": False,
                    "error_code": "INSUFFICIENT_SOURCE_POINTS",
                    "context": {"operation": "TWO_POINT", "current": len(source_points), "required": 2}
                }
            if len(target_points) < 2:
                return {
                    "valid": False,
                    "error_code": "INSUFFICIENT_TARGET_POINTS", 
                    "context": {"operation": "TWO_POINT", "current": len(target_points), "required": 2}
                }
        
        elif operation == "THREE_POINT":
            if len(source_points) < 3:
                return {
                    "valid": False,
                    "error_code": "INSUFFICIENT_SOURCE_POINTS",
                    "context": {"operation": "THREE_POINT", "current": len(source_points), "required": 3}
                }
            if len(target_points) < 3:
                return {
                    "valid": False,
                    "error_code": "INSUFFICIENT_TARGET_POINTS",
                    "context": {"operation": "THREE_POINT", "current": len(target_points), "required": 3}
                }
            
            # 檢查三點共線
            if len(source_points) >= 3:
                if SmartAlignValidator._are_points_colinear(source_points[:3]):
                    return {
                        "valid": False,
                        "error_code": "POINTS_COLINEAR",
                        "context": {"operation": "THREE_POINT"}
                    }
        
        return {"valid": True}
    
    @staticmethod
    def _are_points_colinear(points: List) -> bool:
        """檢查三點是否共線"""
        if len(points) < 3:
            return False
        
        from mathutils import Vector
        
        p0, p1, p2 = points[:3]
        v1 = p1 - p0
        v2 = p2 - p0
        
        # 計算叉積
        cross = v1.cross(v2)
        
        # 如果叉積接近零，則共線
        return cross.length < 0.001
    
    @staticmethod
    def validate_vectors(source_points: List, target_points: List) -> Dict[str, Any]:
        """驗證向量"""
        if len(source_points) >= 2 and len(target_points) >= 2:
            source_vec = source_points[1] - source_points[0]
            target_vec = target_points[1] - target_points[0]
            
            if source_vec.length < 0.01 or target_vec.length < 0.01:
                return {
                    "valid": False,
                    "error_code": "VECTORS_TOO_SHORT",
                    "context": {"source_length": source_vec.length, "target_length": target_vec.length}
                }
        
        return {"valid": True}


class SMARTALIGNPRO_OT_error_helper(Operator):
    """錯誤幫助操作器"""
    bl_idname = "smartalignpro.error_helper"
    bl_label = "錯誤幫助"
    bl_description = "顯示詳細的錯誤信息和解決方案"
    bl_options = {"REGISTER"}
    
    error_code: StringProperty(
        name="錯誤代碼",
        description="要顯示的錯誤代碼"
    )
    
    def execute(self, context):
        """執行錯誤幫助"""
        if not self.error_code:
            return {"CANCELLED"}
        
        # 獲取錯誤信息
        error_info = error_handler.get_error_info(self.error_code)
        
        # 顯示詳細信息
        message = error_handler.format_error_message(self.error_code)
        
        # 在 Blender 中顯示彈窗
        def draw_dialog(self, context):
            layout = self.layout
            box = layout.box()
            
            # 錯誤信息
            severity_colors = {
                "INFO": (0.2, 0.8, 0.2, 1.0),
                "WARNING": (0.9, 0.6, 0.2, 1.0),
                "ERROR": (0.9, 0.2, 0.2, 1.0)
            }
            
            color = severity_colors.get(error_info["severity"], (0.5, 0.5, 0.5, 1.0))
            box.label(text=error_info["message"], icon_color=color)
            
            # 解決方案
            if error_info["solution"]:
                box.separator()
                box.label(text="解決方案:", icon="SETTINGS")
                box.label(text=error_info["solution"])
            
            # 操作建議
            box.separator()
            box.label(text="操作建議:", icon="QUESTION")
            
            suggestions = self._get_suggestions(error_info["error_code"])
            for suggestion in suggestions:
                box.label(text=f"• {suggestion}")
        
        # 創建彈窗
        bpy.context.window_manager.invoke_popup(draw_dialog, width=400, height=200)
        
        return {"FINISHED"}
    
    def _get_suggestions(self, error_code: str) -> List[str]:
        """獲取操作建議"""
        suggestions = {
            "NO_ACTIVE_OBJECT": [
                "右鍵點擊目標物件",
                "按住 Shift 選取多個物件",
                "確保在 Object Mode 中操作"
            ],
            "INSUFFICIENT_SOURCE_POINTS": [
                "繼續點擊幾何體添加點位",
                "檢查 HUD 顯示的進度",
                "使用 ESC 取消並重新開始"
            ],
            "POINTS_COLINEAR": [
                "選擇不共線的三個點",
                "使用兩點對齊模式替代",
                "稍微調整點位位置"
            ]
        }
        
        return suggestions.get(error_code, ["請重新啟動操作"])


class SmartAlignErrorHandler:
    """統一的錯誤處理裝飾器"""
    
    @staticmethod
    def handle_operator_error(operator_func):
        """處理操作器錯誤的裝飾器"""
        def wrapper(self, context):
            try:
                return operator_func(self, context)
            except Exception as e:
                # 記錄錯誤
                error_code = f"UNKNOWN_ERROR_{type(e).__name__}"
                log_hotkey_cancel(self.bl_idname, f"error: {str(e)}")
                
                # 顯示錯誤信息
                message = error_handler.format_error_message(error_code)
                self.report({"ERROR"}, message)
                
                return {"CANCELLED"}
        
        return wrapper
    
    @staticmethod
    def validate_and_execute(validator_func, error_code: str):
        """驗證並執行的裝飾器"""
        def decorator(operator_func):
            def wrapper(self, context):
                # 執行驗證
                validation_result = validator_func(context)
                
                if not validation_result["valid"]:
                    # 處理驗證失敗
                    err_code = validation_result["error_code"]
                    err_context = validation_result.get("context", {})
                    
                    # 記錄錯誤
                    log_hotkey_cancel(self.bl_idname, f"validation_failed: {err_code}")
                    
                    # 顯示錯誤信息
                    message = error_handler.format_error_message(err_code, err_context)
                    self.report({"ERROR"}, message)
                    
                    return {"CANCELLED"}
                
                # 驗證通過，執行操作
                return operator_func(self, context)
            
            return wrapper
        return decorator


# 全局驗證器
validator = SmartAlignValidator()
