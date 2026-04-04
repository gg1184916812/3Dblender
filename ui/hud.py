"""
Smart Align Pro - HUD 系統
狀態提示和操作指引
"""

import bpy
import blf
from bpy_extras import view3d_utils
from typing import Optional, Dict, Any, List
import math


class SmartAlignHUD:
    """Smart Align Pro HUD 系統"""
    
    def __init__(self):
        self.active = False
        self.hud_handle = None
        
        # HUD 設置
        self.font_size = 14
        self.line_height = 18
        self.margin = 20
        self.bg_color = (0.1, 0.1, 0.1, 0.8)
        self.text_color = (0.9, 0.9, 0.9, 1.0)
        self.highlight_color = (0.2, 0.8, 0.2, 1.0)
        
        # 當前狀態
        self.current_mode = "FROM"
        self.current_tool = "CAD_SNAP"
        self.source_points = []
        self.target_points = []
        self.snap_info = ""
        self.constraint_info = ""
        
        # 狀態文字
        self.mode_texts = {
            "FROM": "選擇來源點",
            "TO": "選擇目標點", 
            "ALIGN": "確認對齊",
            "SELECT_SOURCE": "選擇來源點",
            "SELECT_TARGET": "選擇目標點",
            "CONFIRM": "確認對齊"
        }
        
        self.tool_texts = {
            "CAD_SNAP": "精準貼附",
            "TWO_POINT": "兩點對齊",
            "THREE_POINT": "三點對齊",
            "EDGE_ALIGN": "邊對齊",
            "FACE_ALIGN": "面對齊"
        }
        
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
            
    def update_mode(self, mode: str):
        """更新當前模式"""
        self.current_mode = mode
        
    def update_tool(self, tool: str):
        """更新當前工具"""
        self.current_tool = tool
        
    def update_source_points(self, points: List):
        """更新來源點"""
        self.source_points = points
        
    def update_target_points(self, points: List):
        """更新目標點"""
        self.target_points = points
        
    def update_snap_info(self, info: str):
        """更新吸附信息"""
        self.snap_info = info
        
    def update_constraint_info(self, info: str):
        """更新約束信息"""
        self.constraint_info = info
        
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
        """繪製背景"""
        # 計算背景大小
        lines = self._get_text_lines()
        bg_width = 300  # 固定寬度
        bg_height = len(lines) * self.line_height + 20
        
        # 繪製半透明背景
        import bgl
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glColor4f(*self.bg_color)
        
        # 簡單的矩形背景（使用 GPU 繪製會更好，但這裡用基礎方法）
        # 注意：這裡需要 GPU batch 繪製，暫時跳過實際繪製
        
        bgl.glDisable(bgl.GL_BLEND)
        
    def _draw_text(self, x: int, y: int):
        """繪製文字"""
        font_id = 0
        blf.size(font_id, self.font_size)
        
        lines = self._get_text_lines()
        
        for i, line in enumerate(lines):
            text_y = y - i * self.line_height
            
            # 設置顏色
            if "→" in line or "完成" in line:
                blf.color(font_id, *self.highlight_color)
            else:
                blf.color(font_id, *self.text_color)
                
            blf.position(font_id, x, text_y, 0)
            blf.draw(font_id, line)
            
    def _get_text_lines(self) -> List[str]:
        """獲取要顯示的文字行"""
        lines = []
        
        # 工具名稱
        tool_name = self.tool_texts.get(self.current_tool, self.current_tool)
        lines.append(f"【{tool_name}】")
        
        # 當前模式
        mode_text = self.mode_texts.get(self.current_mode, self.current_mode)
        lines.append(f"模式: {mode_text}")
        
        # 點位信息
        if self.source_points:
            lines.append(f"來源點: {len(self.source_points)} 個")
        if self.target_points:
            lines.append(f"目標點: {len(self.target_points)} 個")
            
        # 吸附信息
        if self.snap_info:
            lines.append(f"吸附: {self.snap_info}")
            
        # 約束信息
        if self.constraint_info:
            lines.append(f"約束: {self.constraint_info}")
            
        # 操作提示
        lines.append("")
        lines.append("快捷鍵:")
        lines.append("  左鍵 - 確認點位")
        lines.append("  ESC - 取消")
        lines.append("  Tab - 切換約束")
        lines.append("  空格 - 切換模式")
        
        return lines
        
    def show_temp_message(self, message: str, duration: float = 2.0):
        """顯示臨時消息"""
        # 這裡可以實現定時消息顯示
        # 暫時直接更新 snap_info
        self.update_snap_info(message)
        
        # 可以添加定時器來恢復
        # import bpy.app.timers
        # bpy.app.timers.register(lambda: self.update_snap_info(""), first_interval=duration)


class HUDManager:
    """HUD 管理器"""
    
    def __init__(self):
        self.hud = SmartAlignHUD()
        self.active = False
        
    def start(self, tool: str = "CAD_SNAP"):
        """啟動 HUD"""
        if not self.active:
            self.hud.register()
            self.hud.update_tool(tool)
            self.active = True
            
    def stop(self):
        """停止 HUD"""
        if self.active:
            self.hud.unregister()
            self.active = False
            
    def update(self, **kwargs):
        """更新 HUD 狀態"""
        if self.active:
            for key, value in kwargs.items():
                if hasattr(self.hud, f"update_{key}"):
                    getattr(self.hud, f"update_{key}")(value)
                    
    def show_message(self, message: str, duration: float = 2.0):
        """顯示臨時消息"""
        if self.active:
            self.hud.show_temp_message(message, duration)


# 全局 HUD 管理器實例
hud_manager = HUDManager()
