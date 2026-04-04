"""
Smart Align Pro - 邊界框工具模組
包含邊界框相關的輔助函數和操作器
"""

import bpy
import bgl
import blf
import math
from bpy.types import Operator, SpaceView3D
from bpy.props import BoolProperty, StringProperty, IntProperty
from mathutils import Vector


def get_bbox_center_world(obj):
    """獲取物件邊界框在世界空間的中心點"""
    center_local = sum(
        (Vector(corner) for corner in obj.bound_box),
        Vector((0.0, 0.0, 0.0))
    ) / 8.0
    return obj.matrix_world @ center_local


def get_bbox_corners_world(obj):
    """獲取物件邊界框八個角點的世界座標"""
    return [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]


# 全域 handler 清單
_bbox_handlers = []


def _tag_redraw_all():
    """標記所有 3D 視圖重新繪製"""
    wm = getattr(bpy.context, 'window_manager', None)
    if wm is None:
        return
    for window in wm.windows:
        screen = getattr(window, 'screen', None)
        if screen is None:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def add_bbox_handler():
    """新增 bbox overlay handler"""
    global _bbox_handlers
    remove_bbox_handler()
    
    handler = SpaceView3D.draw_handler_add(
        _draw_bbox_callback,
        (),
        'WINDOW',
        'POST_PIXEL'
    )
    _bbox_handlers.append(handler)
    _tag_redraw_all()


def remove_bbox_handler():
    """移除 bbox overlay handler"""
    global _bbox_handlers
    for handler in _bbox_handlers:
        try:
            SpaceView3D.draw_handler_remove(handler, 'WINDOW')
        except Exception:
            pass
    _bbox_handlers.clear()
    _tag_redraw_all()


def _draw_bbox_callback():
    """真正的繪製回調函式"""
    context = bpy.context
    if context is None:
        return
    
    scene = getattr(context, 'scene', None)
    if scene is None:
        return
    
    settings = getattr(scene, 'smartalignpro_settings', None)
    if settings is None or not getattr(settings, 'show_bbox_point_overlay', False):
        return
    
    obj = getattr(context, 'active_object', None)
    if obj is None or obj.type != 'MESH':
        return
    
    region = context.region
    space_data = getattr(context, 'space_data', None)
    rv3d = getattr(space_data, 'region_3d', None)
    if region is None or rv3d is None:
        return
    
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    
    corners_world = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    
    screen_points = []
    for corner in corners_world:
        screen_pos = location_3d_to_region_2d(region, rv3d, corner)
        if screen_pos:
            screen_points.append((screen_pos.x, screen_pos.y))
        else:
            screen_points.append(None)
    
    if not any(screen_points):
        return
    
    font_id = 0
    blf.size(font_id, 14)
    
    point_labels = ["0", "1", "2", "3", "4", "5", "6", "7"]
    
    bgl.glEnable(bgl.GL_BLEND)
    
    for i, screen_pos in enumerate(screen_points):
        if screen_pos is None:
            continue
        
        x, y = screen_pos
        
        if i in (0, 7):
            blf.color(font_id, 1.0, 0.2, 0.2, 1.0)
        else:
            blf.color(font_id, 0.8, 0.8, 0.8, 1.0)
        
        blf.position(font_id, x + 10, y + 10, 0)
        blf.draw(font_id, point_labels[i])
        
        _draw_circle(x, y, 8, (1.0, 0.2, 0.2, 1.0) if i in (0, 7) else (0.8, 0.8, 0.8, 1.0))
    
    bgl.glDisable(bgl.GL_BLEND)


def _draw_circle(cx, cy, radius, color, segments=16):
    """繪製點位標記圓圈"""
    bgl.glColor4f(*color)
    bgl.glBegin(bgl.GL_LINE_LOOP)
    
    for i in range(segments):
        angle = 2.0 * math.pi * i / segments
        px = cx + radius * math.cos(angle)
        py = cy + radius * math.sin(angle)
        bgl.glVertex2f(px, py)
    
    bgl.glEnd()


class SMARTALIGNPRO_OT_toggle_bbox_overlay(Operator):
    """切換邊界框點位顯示"""
    bl_idname = "smartalignpro.toggle_bbox_point_overlay"
    bl_label = "顯示邊界點"
    bl_options = {"REGISTER", "UNDO"}
    
    def execute(self, context):
        settings = context.scene.smartalignpro_settings
        settings.show_bbox_point_overlay = not settings.show_bbox_point_overlay
        
        if settings.show_bbox_point_overlay:
            add_bbox_handler()
            self.report({"INFO"}, "邊界框點位顯示已開啟")
        else:
            remove_bbox_handler()
            self.report({"INFO"}, "邊界框點位顯示已關閉")
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_cycle_bbox_point(Operator):
    """循環切換邊界框點位"""
    bl_idname = "smartalignpro.cycle_bbox_point"
    bl_label = "循環點位"
    bl_options = {"REGISTER", "UNDO"}
    
    prop_name: StringProperty(name="屬性名", default="")
    step: IntProperty(name="步長", default=1, min=-7, max=7)
    
    def execute(self, context):
        settings = context.scene.smartalignpro_settings
        
        if not self.prop_name:
            self.report({"ERROR"}, "未指定屬性名")
            return {"CANCELLED"}
        
        if not hasattr(settings, self.prop_name):
            self.report({"ERROR"}, f"找不到屬性: {self.prop_name}")
            return {"CANCELLED"}
        
        current_value = getattr(settings, self.prop_name)
        current_int = int(current_value)
        new_int = (current_int + self.step) % 8
        new_value = str(new_int)
        setattr(settings, self.prop_name, new_value)
        
        if settings.show_bbox_point_overlay:
            _tag_redraw_all()
        
        self.report({"INFO"}, f"{self.prop_name} -> {new_value}")
        return {"FINISHED"}


def get_bbox_point_info(obj, point_index):
    """獲取邊界框點位信息"""
    if obj.type != "MESH":
        return None
    
    if not (0 <= point_index < 8):
        return None
    
    point_descriptions = [
        "MIN (原點角)",
        "點1", "點2", "點3",
        "點4", "點5", "點6",
        "MAX (對角)"
    ]
    
    return {
        'index': point_index,
        'position': obj.matrix_world @ Vector(obj.bound_box[point_index]),
        'description': point_descriptions[point_index]
    }


def analyze_bbox_relationship(source, target):
    """分析兩個物件的邊界框關係"""
    source_center = get_bbox_center_world(source)
    target_center = get_bbox_center_world(target)
    
    relative = target_center - source_center
    
    source_size = source.dimensions
    target_size = target.dimensions
    
    return {
        'source_center': source_center,
        'target_center': target_center,
        'relative_position': relative,
        'distance': relative.length
    }


# v7.3 compatibility aliases for older callers
def remove_bbox_overlay_handler(_context=None):
    remove_bbox_handler()

SMARTALIGNPRO_OT_toggle_bbox_point_overlay = SMARTALIGNPRO_OT_toggle_bbox_overlay
