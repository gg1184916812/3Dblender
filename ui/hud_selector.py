"""
Smart Align Pro - HUD Selector 系統
極簡高速版本 - 專為低配電腦優化 + 滑鼠中心位置
"""

import bpy
import blf
from bpy.types import SpaceView3D


class SmartAlignHUDSelector:
    """Smart Align HUD 十字方向選單系統 - 極簡高速版 + 滑鼠中心 + 分離狀態"""
    
    def __init__(self):
        self._handle = None
        self.current_mode = "TWO_POINT"
        self.current_direction = ""  # 分離方向狀態，使用空字串表示無方向
        self.start_mouse_position = (0, 0)
        self.is_active = False
        self.context = None
        
        # HUD 中心位置 - 滑鼠位置
        self.center_x = 0
        self.center_y = 0
        
        # Cancel deadzone 配置
        self.cancel_radius = 30  # 取消半徑（像素）
        
        # 低配模式 - 預設開啟
        self.LOW_PERFORMANCE_MODE = True
        
        # 模式類型 - "ALIGNMENT" 或 "CAD"
        self.mode_type = "ALIGNMENT"
        
        # 對齊模式配置
        self.alignment_directions = {
            "UP": {
                "mode": "SURFACE_NORMAL",
                "text": "表面法線",
                "offset_x": 0,
                "offset_y": 80
            },
            "RIGHT": {
                "mode": "TWO_POINT", 
                "text": "兩點對齊",
                "offset_x": 110,  # 調整為滑鼠中心相對位置
                "offset_y": 0
            },
            "DOWN": {
                "mode": "CONTACT_ALIGN",
                "text": "接觸對齊",
                "offset_x": 0,
                "offset_y": -80
            },
            "LEFT": {
                "mode": "THREE_POINT",
                "text": "三點對齊",
                "offset_x": -110,  # 調整為滑鼠中心相對位置
                "offset_y": 0
            },
            "CANCEL": {
                "mode": "CANCEL",
                "text": "取消",
                "offset_x": 0,
                "offset_y": 0
            }
        }
        
        # ADVANCED 模式配置（Alt+Z 選單）
        self.advanced_directions = {
            "UP": {
                "mode": "MULTI_OBJECT_ALIGN",
                "text": "多物件對齊",
                "offset_x": 0,
                "offset_y": 80
            },
            "RIGHT": {
                "mode": "PIVOT_ALIGN",
                "text": "支點對齊",
                "offset_x": 110,
                "offset_y": 0
            },
            "DOWN": {
                "mode": "VECTOR_CONSTRAINT",
                "text": "向量約束",
                "offset_x": 0,
                "offset_y": -80
            },
            "LEFT": {
                "mode": "PREVIEW_ALIGN",
                "text": "預覽對齊",
                "offset_x": -110,
                "offset_y": 0
            },
            "CANCEL": {
                "mode": "CANCEL",
                "text": "取消",
                "offset_x": 0,
                "offset_y": 0
            }
        }

        # CAD 模式配置
        self.cad_directions = {
            "UP": {
                "mode": "EDGE_ALIGN",
                "text": "邊面對齊",
                "offset_x": 0,
                "offset_y": 80
            },
            "RIGHT": {
                "mode": "CAD_SNAP",
                "text": "精準貼附",
                "offset_x": 110,
                "offset_y": 0
            },
            "DOWN": {
                "mode": "FACE_ALIGN",
                "text": "平面對齊",
                "offset_x": 0,
                "offset_y": -80
            },
            "LEFT": {
                "mode": "QUICK_SNAP",
                "text": "快速貼附",
                "offset_x": -110,
                "offset_y": 0
            },
            "CANCEL": {
                "mode": "CANCEL",
                "text": "取消",
                "offset_x": 0,
                "offset_y": 0
            }
        }
        
        # 根據模式類型選擇配置
        self.directions = self.alignment_directions
        
        # 顏色配置 - 預設值
        self.active_color = (0.3, 0.8, 1.0, 1.0)      # 高亮藍色
        self.inactive_color = (0.7, 0.7, 0.7, 1.0)   # 灰色
        self.default_color = (0.5, 0.5, 0.5, 1.0)     # 預設狀態顏色（更暗）
        
        # 字型設定 - 初始化一次
        self.font_id = 0
        self.font_size = 16
        self.center_font_size = 12
        
        # 預先計算文字寬度（避免每幀重算）
        self.text_widths = {}
        self._precalculate_text_widths()
    
    def _precalculate_text_widths(self):
        """預先計算所有文字寬度"""
        blf.size(self.font_id, self.font_size)
        for direction, config in self.directions.items():
            text = config["text"]
            self.text_widths[direction] = blf.dimensions(self.font_id, text)[0]
        
        # 中央文字寬度
        blf.size(self.font_id, self.center_font_size)
        for direction, config in self.directions.items():
            text = config["text"]
            self.text_widths[f"center_{direction}"] = blf.dimensions(self.font_id, text)[0]
    
    def start(self, context, mouse_x, mouse_y, mode_type="ALIGNMENT"):
        """啟動 HUD selector - 支援對齊和 CAD 模式"""
        print(f"[SmartAlignPro][HUD DEBUG] start() called with mode_type: {mode_type}")
        print(f"[SmartAlignPro][HUD DEBUG] mouse_position: ({mouse_x}, {mouse_y})")
        
        self.start_mouse_position = (mouse_x, mouse_y)
        self.center_x = mouse_x  # HUD 中心在滑鼠位置
        self.center_y = mouse_y
        self.mode_type = mode_type
        
        # 根據模式類型選擇配置
        if mode_type == "CAD":
            self.directions = self.cad_directions
            self.current_mode = ""
            print(f"[SmartAlignPro][HUD DEBUG] Switched to CAD mode")
        elif mode_type == "ADVANCED":
            self.directions = self.advanced_directions
            self.current_mode = "MULTI_OBJECT_ALIGN"
            print(f"[SmartAlignPro][HUD DEBUG] Switched to ADVANCED mode")
        else:
            self.directions = self.alignment_directions
            self.current_mode = "TWO_POINT"
            print(f"[SmartAlignPro][HUD DEBUG] Switched to ALIGNMENT mode")
            
        self.current_direction = ""  # 預設無方向
        self.is_active = True
        self.context = context
        
        # 重新計算文字寬度
        try:
            self._precalculate_text_widths()
            print(f"[SmartAlignPro][HUD DEBUG] Text widths calculated successfully")
        except Exception as e:
            print(f"[SmartAlignPro][HUD ERROR] Failed to calculate text widths: {e}")
        
        # 添加 draw handler
        try:
            self._handle = SpaceView3D.draw_handler_add(
                self.draw_callback_px,
                (context,),
                'WINDOW',
                'POST_PIXEL'
            )
            print(f"[SmartAlignPro][HUD DEBUG] Draw handler added successfully")
        except Exception as e:
            print(f"[SmartAlignPro][HUD ERROR] Failed to add draw handler: {e}")
            raise
        
        if mode_type == "CAD":
            print("[SmartAlignPro][CAD HUD SELECTOR START] - CAD 模式，方向：未選中")
        else:
            print("[SmartAlignPro][HUD SELECTOR START] - 預設模式：兩點對齊，方向：未選中")
    
    def update_direction(self, direction):
        """更新當前方向 - 分離模式與方向狀態"""
        if direction != self.current_direction:
            old_direction = self.current_direction
            self.current_direction = direction
            self.current_mode = self.directions[direction]["mode"]
            
            print(f"[SmartAlignPro][DIRECTION SELECTED] {direction} -> {self.current_mode}")
            
            # 只有方向真的改變時才 redraw
            if self.context and self.context.area:
                self.context.area.tag_redraw()
    
    def check_cancel_deadzone(self, mouse_x, mouse_y):
        """檢查滑鼠是否在取消死區內"""
        distance = ((mouse_x - self.center_x) ** 2 + (mouse_y - self.center_y) ** 2) ** 0.5
        
        if distance < self.cancel_radius:
            print(f"[SmartAlignPro][HUD CANCEL] Mouse in deadzone: distance={distance:.1f}, radius={self.cancel_radius}")
            self.current_direction = "CANCEL"
            self.current_mode = "CANCEL"
            return True
        
        return False
    
    def get_direction_from_mouse(self, mouse_x, mouse_y):
        """根據滑鼠位置獲取方向，包含取消死區檢查"""
        # 檢查取消死區
        if self.check_cancel_deadzone(mouse_x, mouse_y):
            return "CANCEL"
        
        # 計算相對位置
        dx = mouse_x - self.center_x
        dy = mouse_y - self.center_y
        
        # 判斷方向
        if abs(dx) > abs(dy):
            if dx > 0:
                return "RIGHT"
            else:
                return "LEFT"
        else:
            if dy > 0:
                return "UP"
            else:
                return "DOWN"
    
    def remove_handler(self):
        """移除 draw handler"""
        if self._handle is not None:
            SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
    
    def stop(self):
        """停止 HUD selector"""
        self.remove_handler()
        self.is_active = False
        self.context = None
    
    def draw_callback_px(self, context):
        """繪製回調函數 - 極簡高速版，無 debug print + 分離狀態顯示"""
        if not self.is_active:
            return
        
        if not context.area:
            return
        
        # 使用滑鼠中心位置，不是 viewport 中央
        center_x = self.center_x
        center_y = self.center_y
        
        # 極簡 HUD - 只畫純文字，無背景
        if self.LOW_PERFORMANCE_MODE:
            self._draw_minimal_hud(center_x, center_y)
        else:
            self._draw_full_hud(center_x, center_y)
    
    def _draw_minimal_hud(self, center_x, center_y):
        """極簡 HUD - 只畫純文字 + 分離狀態顯示"""
        # 設置字型大小
        blf.size(self.font_id, self.font_size)
        
        # 畫四個方向文字
        for direction, config in self.directions.items():
            # 計算位置 - 使用滑鼠中心
            text_x = center_x + config["offset_x"]
            text_y = center_y + config["offset_y"]
            
            # 設置顏色 - 分離狀態邏輯
            if self.current_direction == direction:
                # 方向被明確選中
                blf.color(self.font_id, *self.active_color)
            elif self.current_direction == "" and direction == "RIGHT":
                # 預設狀態，右方向用預設顏色（不高亮）
                blf.color(self.font_id, *self.default_color)
            else:
                # 其他方向用灰色
                blf.color(self.font_id, *self.inactive_color)
            
            # 居中文字（使用預計算的寬度）
            text_width = self.text_widths[direction]
            blf.position(self.font_id, text_x - text_width // 2, text_y - self.font_size // 2, 0)
            blf.draw(self.font_id, config["text"])
    
    def _draw_full_hud(self, center_x, center_y):
        """完整 HUD - 包含裝飾元素 + 分離狀態顯示"""
        # 設置字型大小
        blf.size(self.font_id, self.font_size)
        
        # 畫四個方向文字
        for direction, config in self.directions.items():
            # 計算位置 - 使用滑鼠中心
            text_x = center_x + config["offset_x"]
            text_y = center_y + config["offset_y"]
            
            # 設置顏色 - 分離狀態邏輯
            if self.current_direction == direction:
                # 方向被明確選中
                blf.color(self.font_id, *self.active_color)
            elif self.current_direction == "" and direction == "RIGHT":
                # 預設狀態，右方向用預設顏色（不高亮）
                blf.color(self.font_id, *self.default_color)
            else:
                # 其他方向用灰色
                blf.color(self.font_id, *self.inactive_color)
            
            # 居中文字（使用預計算的寬度）
            text_width = self.text_widths[direction]
            blf.position(self.font_id, text_x - text_width // 2, text_y - self.font_size // 2, 0)
            blf.draw(self.font_id, config["text"])
        
        # 畫中央指示器
        blf.size(self.font_id, self.center_font_size)
        blf.color(self.font_id, *self.active_color)
        
        if self.current_direction != "":
            current_config = self.directions[self.current_direction]
            mode_text = current_config["text"]
            text_width = self.text_widths[f"center_{self.current_direction}"]
            blf.position(self.font_id, center_x - text_width // 2, center_y - self.center_font_size // 2, 0)
            blf.draw(self.font_id, mode_text)
        else:
            # 預設狀態顯示
            mode_text = "兩點對齊 (預設)"
            blf.dimensions(self.font_id, mode_text)
            text_width = blf.dimensions(self.font_id, mode_text)[0]
            blf.position(self.font_id, center_x - text_width // 2, center_y - self.center_font_size // 2, 0)
            blf.draw(self.font_id, mode_text)
    
    def get_current_mode(self):
        """獲取當前模式"""
        return self.current_mode
    
    def get_current_direction(self):
        """獲取當前方向"""
        return self.current_direction
    
    def get_mode_name_chinese(self):
        """獲取繁體中文模式名稱"""
        if self.current_direction != "":
            return self.directions[self.current_direction]["text"]
        else:
            if self.mode_type == "CAD":
                return "精準/快速貼附"
            elif self.mode_type == "ADVANCED":
                return "多物件對齊 (預設)"
            else:
                return "兩點對齊 (預設)"


# 全域 HUD selector 實例
hud_selector = SmartAlignHUDSelector()


def determine_direction(dx, dy, current_direction=None, start_x=0, start_y=0):
    """根據滑鼠移動判定方向 - RIGHT 強鎖定版"""
    
    # 獨立門檻 - 右方向更容易觸發
    RIGHT_THRESHOLD = 12
    LEFT_THRESHOLD = 24
    UP_THRESHOLD = 40
    DOWN_THRESHOLD = 40
    
    # 方向切換門檻 - 比「首次選方向」更嚴格
    REVERSE_SWITCH_THRESHOLD = 60
    VERTICAL_SWITCH_THRESHOLD = 70
    
    # 如果還沒有方向，使用首次判定
    if current_direction is None:
        # 右方向優先規則
        if dx > RIGHT_THRESHOLD and abs(dy) < abs(dx) * 1.5:
            return "RIGHT"
        elif abs(dx) > abs(dy) * 1.15:
            if dx > 0 and dx >= RIGHT_THRESHOLD:
                return "RIGHT"
            elif dx < 0 and dx <= -LEFT_THRESHOLD:
                return "LEFT"
        elif abs(dy) > abs(dx) * 1.15:
            if dy > 0 and dy >= UP_THRESHOLD:
                return "UP"
            elif dy < 0 and dy <= -DOWN_THRESHOLD:
                return "DOWN"
        return None
    
    # 方向鎖定機制 - 已有方向時需要更嚴格的門檻才能切換
    if current_direction == "RIGHT":
        # RIGHT 強鎖定機制：只要 dx > 0 且達門檻就維持 RIGHT
        if dx > 0 and abs(dx) >= RIGHT_THRESHOLD:
            return "RIGHT"
        # 需要反向門檻才能切換
        elif dx < -REVERSE_SWITCH_THRESHOLD:
            return "LEFT"
        elif dy > VERTICAL_SWITCH_THRESHOLD:
            return "UP"
        elif dy < -VERTICAL_SWITCH_THRESHOLD:
            return "DOWN"
    
    elif current_direction == "LEFT":
        # LEFT 狀態下：需要反向門檻才能切換
        if dx < 0 and abs(dx) >= LEFT_THRESHOLD:
            return "LEFT"
        elif dx > REVERSE_SWITCH_THRESHOLD:
            return "RIGHT"
        elif dy > VERTICAL_SWITCH_THRESHOLD:
            return "UP"
        elif dy < -VERTICAL_SWITCH_THRESHOLD:
            return "DOWN"
    
    elif current_direction == "UP":
        # UP 狀態下：需要反向門檻才能切換
        if dy > 0 and abs(dy) >= UP_THRESHOLD:
            return "UP"
        elif dy < -REVERSE_SWITCH_THRESHOLD:
            return "DOWN"
        elif dx > VERTICAL_SWITCH_THRESHOLD:
            return "RIGHT"
        elif dx < -VERTICAL_SWITCH_THRESHOLD:
            return "LEFT"
    
    elif current_direction == "DOWN":
        # DOWN 狀態下：需要反向門檻才能切換
        if dy < 0 and abs(dy) >= DOWN_THRESHOLD:
            return "DOWN"
        elif dy > REVERSE_SWITCH_THRESHOLD:
            return "UP"
        elif dx > VERTICAL_SWITCH_THRESHOLD:
            return "RIGHT"
        elif dx < -VERTICAL_SWITCH_THRESHOLD:
            return "LEFT"
    
    # 維持目前方向
    return current_direction


def cycle_direction(current_direction, forward=True):
    """循環切換方向"""
    directions = ["UP", "RIGHT", "DOWN", "LEFT"]
    current_index = directions.index(current_direction)
    
    if forward:
        next_index = (current_index + 1) % len(directions)
    else:
        next_index = (current_index - 1) % len(directions)
    
    return directions[next_index]
