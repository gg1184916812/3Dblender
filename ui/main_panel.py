"""
Smart Align Pro - 主面板模組
穩定版 UI 面板
"""

import bpy
from bpy.types import Panel
from ..utils.icon_safe import safe_icon


def get_version_string():
    """獲取插件版本字串"""
    try:
        from .. import bl_info
        return ".".join(str(x) for x in bl_info.get('version', (0, 0, 0)))
    except Exception:
        return "3.0.0"


def get_registered_stats():
    """獲取動態註冊統計資訊"""
    stats = {
        'keymap_count': 0,
        'operator_count': 0,
        'panel_count': 0,
    }
    
    try:
        # 統計已註冊的操作器 (以 smartalignpro 為前綴)
        for attr in dir(bpy.types):
            if attr.startswith('SMARTALIGNPRO_OT_'):
                stats['operator_count'] += 1
                
        # 統計已註冊的面板
        for attr in dir(bpy.types):
            if attr.startswith('SMARTALIGNPRO_PT_'):
                stats['panel_count'] += 1
                
        # 統計快捷鍵 (從 keymap_manager 獲取)
        wm = bpy.context.window_manager
        if wm and wm.keyconfigs:
            addon_keyconfig = wm.keyconfigs.addon
            if addon_keyconfig:
                for km in addon_keyconfig.keymaps:
                    if 'smartalignpro' in km.name.lower():
                        stats['keymap_count'] += len(km.keymap_items)
                        
    except Exception as e:
        print(f"[SmartAlignPro] 統計失敗: {e}")
        
    return stats


def safe_label(layout, text, icon_name=None):
    """安全的 label 函數，處理 icon 為 None 的情況"""
    if icon_name:
        icon = safe_icon(icon_name)
        if icon:
            layout.label(text=text, icon=icon)
            return
    layout.label(text=text)


def safe_operator(layout, operator_name, text=None, icon_name=None):
    """安全的 operator 函數，處理 icon 為 None 的情況"""
    if icon_name:
        icon = safe_icon(icon_name)
        if icon:
            layout.operator(operator_name, text=text, icon=icon)
            return
    layout.operator(operator_name, text=text)


class SMARTALIGNPRO_PT_main_panel(Panel):
    """Smart Align Pro 主面板 - v7.4 超越版"""
    bl_label = "Smart Align Pro"
    bl_idname = "SMARTALIGNPRO_PT_main_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "對齊"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.smartalignpro_settings
        
        # ===== Zone 1: 唯一主入口 - Ultimate Modal =====
        # 這是 Smart Align Pro 的核心工作流，所有對齊操作統一入口
        zone1_box = layout.box()
        zone1_box.label(text="■ 智能對齊 (Ultimate)", icon="PARTICLES")
        
        # 主啟動按鈕 - 加大、加強視覺層級
        row = zone1_box.row(align=True)
        row.scale_y = 2.5
        row.operator("smartalignpro.ultimate_modal", 
                    text="啟動智能對齊", 
                    icon="PARTICLES")
        
        # 快捷鍵提示
        zone1_box.label(text="Alt+A: 快捷啟動 | Tab: 切換模式 | 1/2/3: 吸附優先級", icon="INFO")
        
        # 分隔線
        layout.separator()
        
        # ===== Zone 2: 輔助工具 (預設收合) =====
        # 這些是 Ultimate 的補充，不是主要工作流
        if settings.ui_show_advanced:
            zone2_box = layout.box()
            zone2_box.label(text="■ 快速輔助工具", icon="SNAP_GRID")
            
            row = zone2_box.row(align=True)
            col1 = row.column(align=True)
            col2 = row.column(align=True)
            col1.operator("smartalignpro.quick_align", 
                         text="面中心", icon="SNAP_FACE").align_mode = "FACE_CENTER"
            col1.operator("smartalignpro.quick_align", 
                         text="地面", icon="TRIA_DOWN").align_mode = "GROUND"
            col2.operator("smartalignpro.preset_align", 
                         text="底部中心", icon="IMPORT").preset_type = "BOTTOM_CENTER"
            col2.operator("smartalignpro.surface_align", 
                         text="表面法線", icon="ORIENTATION_NORMAL")
            
            # 視圖導向
            row = zone2_box.row(align=True)
            row.operator("smartalignpro.view_oriented_align", 
                        text="視圖導向", icon="VIEW_ORTHO")
            
            zone2_box.prop(settings, "ui_show_advanced", text="隱藏輔助工具", icon="HIDE_ON")
        else:
            row = layout.row()
            row.prop(settings, "ui_show_advanced", text="顯示輔助工具", icon="HIDE_OFF")
            row.label(text="(非必需)", icon="INFO")
        
        # ===== Zone 3: 進階設定 (預設收合) =====
        if settings.ui_show_cad_tools:
            zone3_box = layout.box()
            zone3_box.label(text="■ 進階設定", icon="PREFERENCES")
            
            zone3_box.prop(settings, "snap_tolerance")
            zone3_box.prop(settings, "sticky_radius")
            zone3_box.prop(settings, "hysteresis_factor")
            zone3_box.prop(settings, "default_constraint")
            
            zone3_box.separator()
            zone3_box.prop(settings, "debug_mode")
            zone3_box.prop(settings, "show_hud")
            zone3_box.prop(settings, "show_preview")
            
            zone3_box.prop(settings, "ui_show_cad_tools", text="隱藏進階設定", icon="HIDE_ON")
        else:
            row = layout.row()
            row.prop(settings, "ui_show_cad_tools", text="顯示進階設定", icon="HIDE_OFF")
        
        # ===== 版本信息 =====
        info_box = layout.box()
        info_box.label(text=f"Smart Align Pro v{get_version_string()}", icon="INFO")


class SMARTALIGNPRO_PT_settings_panel(Panel):
    """Smart Align Pro 設置面板"""
    bl_label = "對齊設置"
    bl_idname = "SMARTALIGNPRO_PT_settings_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "對齊"
    bl_parent_id = "SMARTALIGNPRO_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.smartalignpro_settings
        
        # 兩點對齊設置
        box = layout.box()
        safe_label(box, "兩點對齊設置", "EMPTY_AXIS")
        
        col = box.column(align=True)
        col.prop(settings, "two_point_source_a")
        col.prop(settings, "two_point_source_b")
        col.prop(settings, "two_point_target_a")
        col.prop(settings, "two_point_target_b")
        
        # 點位循環按鈕
        row = box.row(align=True)
        row.operator("smartalignpro.cycle_bbox_point", text="源A-").prop_name = "two_point_source_a"
        row.operator("smartalignpro.cycle_bbox_point", text="源A+").prop_name = "two_point_source_a"
        
        row = box.row(align=True)
        row.operator("smartalignpro.cycle_bbox_point", text="源B-").prop_name = "two_point_source_b"
        row.operator("smartalignpro.cycle_bbox_point", text="源B+").prop_name = "two_point_source_b"
        
        row = box.row(align=True)
        row.operator("smartalignpro.cycle_bbox_point", text="目A-").prop_name = "two_point_target_a"
        row.operator("smartalignpro.cycle_bbox_point", text="目A+").prop_name = "two_point_target_a"
        
        row = box.row(align=True)
        row.operator("smartalignpro.cycle_bbox_point", text="目B-").prop_name = "two_point_target_b"
        row.operator("smartalignpro.cycle_bbox_point", text="目B+").prop_name = "two_point_target_b"
        
        # 三點對齊設置
        box = layout.box()
        safe_label(box, "三點對齊設置", "EMPTY_ARROWS")
        
        col = box.column(align=True)
        col.prop(settings, "three_point_source_a")
        col.prop(settings, "three_point_source_b")
        col.prop(settings, "three_point_source_c")
        col.prop(settings, "three_point_target_a")
        col.prop(settings, "three_point_target_b")
        col.prop(settings, "three_point_target_c")
        
        col.prop(settings, "three_point_flip_target_normal")
        col.prop(settings, "three_point_apply_offset")
        
        # 表面法線對齊設置
        box = layout.box()
        safe_label(box, "表面法線對齊設置", "ORIENTATION_NORMAL")
        
        col = box.column(align=True)
        col.prop(settings, "normal_align_axis")
        col.prop(settings, "normal_align_move_to_hit")
        
        # 通用設置
        box = layout.box()
        safe_label(box, "通用設置", "PREFERENCES")
        
        col = box.column(align=True)
        col.prop(settings, "collision_safe_mode")
        col.prop(settings, "small_offset")
        col.prop(settings, "keep_xy_position")
        col.prop(settings, "center_on_target")


class SMARTALIGNPRO_PT_info_panel(Panel):
    """Smart Align Pro 信息面板"""
    bl_label = "詳細資訊"
    bl_idname = "SMARTALIGNPRO_PT_info_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "對齊"
    bl_parent_id = "SMARTALIGNPRO_PT_main_panel"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.smartalignpro_settings
        
        # 版本信息
        box = layout.box()
        safe_label(box, "版本信息", "INFO")
        
        col = box.column(align=True)
        col.label(text=f"Smart Align Pro v{get_version_string()} 穩定版")
        col.label(text="繁體中文版")
        col.label(text="適用 Blender 3.6+")
        
        # 系統信息
        box = layout.box()
        safe_label(box, "系統信息", "SYSTEM")
        
        # 動態獲取統計資訊
        stats = get_registered_stats()
        
        col = box.column(align=True)
        col.label(text=f"已註冊快捷鍵: {stats['keymap_count']} 個")
        col.label(text=f"已註冊操作器: {stats['operator_count']} 個")
        col.label(text=f"UI 面板: {stats['panel_count']} 個")
        
        # 調試信息
        if settings.debug_mode:
            box = layout.box()
            safe_label(box, "調試信息", "CONSOLE")
            
            col = box.column(align=True)
            col.label(text="Console 輸出已啟用")
            col.label(text="快捷鍵偵錯已啟用")
            col.label(text="操作器執行追蹤已啟用")
