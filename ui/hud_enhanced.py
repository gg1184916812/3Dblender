"""
Smart Align Pro - 增強 HUD 系統
清晰的使用者語意和操作指引
"""

import bpy
import blf
from bpy_extras import view3d_utils
from typing import Optional, Dict, Any, List
import math
import time


class SmartAlignHUD:
    """Smart Align Pro 增強 HUD 系統"""
    
    def __init__(self):
        self.active = False
        self.hud_handle = None
        
        # HUD 設置
        self.font_size = 14
        self.line_height = 18
        self.margin = 20
        self.bg_color = (0.1, 0.1, 0.1, 0.85)
        self.text_color = (0.9, 0.9, 0.9, 1.0)
        self.highlight_color = (0.2, 0.8, 0.2, 1.0)
        self.warning_color = (0.9, 0.6, 0.2, 1.0)
        self.error_color = (0.9, 0.2, 0.2, 1.0)
        
        # 當前狀態
        self.current_mode = "SELECT_SOURCE"
        self.current_tool = "TWO_POINT"
        self.source_points = []
        self.target_points = []
        self.snap_info = ""
        # Item 6: last valid snap type tracking
        self.last_valid_snap_type: str = ""
        self.snap_state_label: str = ""
        self.snap_state_color: tuple = (0.9, 0.9, 0.9, 1.0)
        self.constraint_info = ""
        self.current_point_index = 0
        self.required_points = {"source": 2, "target": 2}
        
        # 臨時消息
        self.temp_message = ""
        self.temp_message_time = 0
        self.temp_message_duration = 2.0
        
    def register(self):
        """註冊 HUD"""
        if not self.active:
            self.hud_handle = bpy.types.SpaceView3D.draw_handler_add(
                self.draw_callback, (), 'WINDOW', 'POST_PIXEL'
            )
            self.active = True
            
    def unregister(self):
        """註銷 HUD"""
        if self.active and self.hud_handle:
            bpy.types.SpaceView3D.draw_handler_remove(self.hud_handle, 'WINDOW')
            self.active = False
            self.hud_handle = None
            
    def start(self, tool: str):
        """啟動 HUD"""
        self.current_tool = tool
        self.current_mode = "SELECT_SOURCE"
        self.source_points = []
        self.target_points = []
        self.current_point_index = 0
        self.register()
        
    def stop(self):
        """停止 HUD"""
        self.unregister()
        
    def update(self, **kwargs):
        """更新 HUD 狀態"""
        if "modal_state" in kwargs:
            self.current_mode = kwargs["modal_state"]
        if "source_points" in kwargs:
            self.source_points = kwargs["source_points"]
        if "target_points" in kwargs:
            self.target_points = kwargs["target_points"]
        if "snap_info" in kwargs:
            self.snap_info = kwargs["snap_info"]
        if "constraint_info" in kwargs:
            self.constraint_info = kwargs["constraint_info"]
        if "last_valid_snap_type" in kwargs:
            self.last_valid_snap_type = kwargs["last_valid_snap_type"]
        if "snap_state_label" in kwargs:
            self.snap_state_label = kwargs["snap_state_label"]
        if "snap_state_color" in kwargs:
            self.snap_state_color = kwargs["snap_state_color"]
        if "current_point_index" in kwargs:
            self.current_point_index = kwargs["current_point_index"]
        if "required_points" in kwargs:
            self.required_points = kwargs["required_points"]
            
    def show_temp_message(self, message: str, duration: float = 2.0):
        """顯示臨時消息"""
        self.temp_message = message
        self.temp_message_time = time.time()
        self.temp_message_duration = duration
        
    def _get_tool_name(self) -> str:
        """獲取工具名稱"""
        tool_names = {
            "TWO_POINT": "兩點對齊",
            "THREE_POINT": "三點對齊", 
            "CAD_SNAP": "精準貼附",
            "EDGE_ALIGN": "邊對齊",
            "FACE_ALIGN": "面對齊"
        }
        return tool_names.get(self.current_tool, self.current_tool)
        
    def _get_current_step_text(self) -> str:
        """獲取當前步驟文字"""
        if self.current_mode == "SELECT_SOURCE":
            if self.current_tool == "TWO_POINT":
                if len(self.source_points) == 0:
                    return "選擇來源第 1 點 (起點)"
                elif len(self.source_points) == 1:
                    return "選擇來源第 2 點 (終點)"
            elif self.current_tool == "THREE_POINT":
                point_names = ["基準點", "方向點", "平面點"]
                if len(self.source_points) < 3:
                    return f"選擇來源第 {len(self.source_points) + 1} 點 ({point_names[len(self.source_points)]})"
            elif self.current_tool == "CAD_SNAP":
                return "選擇 From 點 (起始參考)"
                
        elif self.current_mode == "SELECT_TARGET":
            if self.current_tool == "TWO_POINT":
                if len(self.target_points) == 0:
                    return "選擇目標第 1 點 (起點)"
                elif len(self.target_points) == 1:
                    return "選擇目標第 2 點 (終點)"
            elif self.current_tool == "THREE_POINT":
                point_names = ["基準點", "方向點", "平面點"]
                if len(self.target_points) < 3:
                    return f"選擇目標第 {len(self.target_points) + 1} 點 ({point_names[len(self.target_points)]})"
            elif self.current_tool == "CAD_SNAP":
                return "選擇 To 點 (目標位置)"
                
        elif self.current_mode == "PREVIEW":
            return "預覽模式 - 確認對齊"
            
        return "準備中..."
        
    def _get_progress_text(self) -> str:
        """獲取進度文字"""
        source_done = len(self.source_points) >= self.required_points.get("source", 2)
        target_done = len(self.target_points) >= self.required_points.get("target", 2)
        
        if self.current_mode == "SELECT_SOURCE":
            return f"來源: {len(self.source_points)}/{self.required_points.get('source', 2)}"
        elif self.current_mode == "SELECT_TARGET":
            return f"目標: {len(self.target_points)}/{self.required_points.get('target', 2)}"
        elif self.current_mode == "PREVIEW":
            if source_done and target_done:
                return "✓ 準備完成"
            else:
                return "✗ 點位不足"
                
        return ""
        
    def _get_constraint_text(self) -> str:
        """獲取約束文字"""
        constraint_names = {
            "NONE": "自由對齊",
            "TRANSLATE_ONLY": "僅平移",
            "ROTATE_ONLY": "僅旋轉",
            "AXIS_LOCK_X": "鎖定 X 軸",
            "AXIS_LOCK_Y": "鎖定 Y 軸", 
            "AXIS_LOCK_Z": "鎖定 Z 軸"
        }
        return constraint_names.get(self.constraint_info, self.constraint_info)
        
    def _get_text_lines(self) -> List[str]:
        """獲取要顯示的文字行"""
        lines = []
        
        # 工具標題
        lines.append(f"【{self._get_tool_name()}】")
        lines.append("")
        
        # 當前步驟
        current_step = self._get_current_step_text()
        lines.append(f"📍 {current_step}")
        
        # 進度
        progress = self._get_progress_text()
        if progress:
            lines.append(f"📊 {progress}")
            
        lines.append("")
        
        # Item 6: snap state + last valid snap type
        if self.snap_state_label:
            lines.append(f"◉ 狀態: {self.snap_state_label}")
        if self.last_valid_snap_type:
            lines.append(f"📌 最後有效吸附: {self.last_valid_snap_type}")
        # 吸附信息
        if self.snap_info:
            lines.append(f"🎯 {self.snap_info}")
            
        # 約束信息
        if self.constraint_info:
            constraint_text = self._get_constraint_text()
            lines.append(f"🔒 {constraint_text}")
            
        lines.append("")
        
        # 操作指引
        lines.append("🎮 操作:")
        if self.current_mode in ["SELECT_SOURCE", "SELECT_TARGET"]:
            lines.append("  左鍵 - 確認點位")
        elif self.current_mode == "PREVIEW":
            lines.append("  Enter - 執行對齊")
            
        lines.append("  ESC - 取消操作")
        lines.append("  Tab - 切換約束")
        
        # 臨時消息
        if self.temp_message and time.time() - self.temp_message_time < self.temp_message_duration:
            lines.append("")
            lines.append(f"⚠️ {self.temp_message}")
            
        return lines
        
    def draw_callback(self):
        """繪製回調函數"""
        if not self.active:
            return
            
        # 獲取區域大小
        region = bpy.context.region
        if not region:
            return
            
        width = region.width
        height = region.height
        
        # HUD 位置（左上角）
        x = self.margin
        y = height - self.margin
        
        # 繪製背景
        self._draw_background(x, y, width)
        
        # 繪製文字
        self._draw_text(x, y)
        
    def _draw_background(self, x: int, y: int, width: int):
        """繪製背景（Blender 4.5 安全版）"""
        # Blender 4.5 下 bgl.glEnable 可能為 NoneType，這裡直接跳過背景，
        # 保留文字 HUD，避免 draw callback 反覆報錯導致互動失效。
        return

    def _draw_text(self, x: int, y: int):
        """繪製文字"""
        font_id = 0
        blf.size(font_id, self.font_size)
        
        lines = self._get_text_lines()
        
        for i, line in enumerate(lines):
            text_y = y - i * self.line_height
            
            # 設置顏色
            if "⚠️" in line:
                blf.color(font_id, *self.warning_color)
            elif "✓" in line:
                blf.color(font_id, *self.highlight_color)
            elif "✗" in line:
                blf.color(font_id, *self.error_color)
            elif "📍" in line:
                blf.color(font_id, *self.highlight_color)
            else:
                blf.color(font_id, *self.text_color)
                
            blf.position(font_id, x, text_y, 0)
            blf.draw(font_id, line)


# 全局 HUD 實例
hud = SmartAlignHUD()


def start(tool: str):
    """啟動 HUD"""
    hud.start(tool)


def stop():
    """停止 HUD"""
    hud.stop()


def update(**kwargs):
    """更新 HUD"""
    hud.update(**kwargs)


def show_temp_message(message: str, duration: float = 2.0):
    """顯示臨時消息"""
    hud.show_temp_message(message, duration)
