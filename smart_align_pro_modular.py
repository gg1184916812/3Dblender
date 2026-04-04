"""
Smart Align Pro - 模組化版本主入口文件
穩定版主入口
"""

import bpy
import sys
import os
import traceback
import importlib


def get_addon_path():
    """獲取插件路徑"""
    return os.path.dirname(os.path.abspath(__file__))


def add_module_path():
    """添加模組路徑"""
    addon_path = get_addon_path()
    if addon_path not in sys.path:
        sys.path.insert(0, addon_path)


def import_modules():
    """導入所有模組 - 穩定版"""
    modules_to_import = [
        ".core.align_engine",
        ".core.math_utils",
        ".core.detection",
        ".core.alignment",
        ".core.two_point_solver",
        ".core.three_point_solver",
        ".core.edge_solver",
        ".core.face_solver",
        ".core.solver_manager",
        ".core.snap_engine",
        ".core.snap_solver_core",
        ".core.selector_state_machine",
        ".core.preview_transform",
        ".core.unified_modal_base",
        ".core.smart_pick_engine",
        ".core.soft_snap_engine",
        ".core.contact_align_engine",
        ".core.zero_mode_controller",
        ".core.axis_locking_system",
        ".core.snap_priority_solver",
        ".core.candidate_types",
        ".core.unified_solver_engine",
        ".operators.alignment_operators",
        ".operators.preview_operators",
        ".operators.utility_operators",
        ".operators.cad_operators",
        ".operators.multi_object_operators",
        ".operators.edge_face_align_operators",
        ".operators.ultimate_modal_operator",
        ".operators.quick_align_operators",
        ".operators.view_oriented_operators",
        ".ui.main_panel",
        ".ui.hud_selector",
        ".utils.bbox_utils",
        ".utils.measurement_utils",
        ".utils.measurement_overlay",
        ".utils.settings",
        ".utils.error_handling",
        ".keymap_manager",
    ]

    for module_name in modules_to_import:
        try:
            if module_name.startswith("."):
                importlib.import_module(module_name, __package__)
            else:
                importlib.import_module(module_name)
            print(f"[SmartAlignPro][STABLE] 模組載入成功: {module_name}")
        except Exception as e:
            print(f"[SmartAlignPro][ERROR] 模組導入失敗: {module_name} -> {e}")
            print("[SmartAlignPro][TRACEBACK]")
            print(traceback.format_exc())
            return False
    return True


def get_classes():
    """僅返回所有要註冊的類"""
    from .operators.alignment_operators import (
        SMARTALIGNPRO_OT_two_point_align,
        SMARTALIGNPRO_OT_three_point_align,
        SMARTALIGNPRO_OT_three_point_modal,
        SMARTALIGNPRO_OT_surface_normal_align,
        SMARTALIGNPRO_OT_auto_contact_align,
        SMARTALIGNPRO_OT_align_to_ground,
        SMARTALIGNPRO_OT_align_to_surface,
        SMARTALIGNPRO_OT_smart_align,
        SMARTALIGNPRO_OT_smart_batch_align,
        SMARTALIGNPRO_OT_directional_wheel_selector,
        SMARTALIGNPRO_OT_cad_directional_selector,
        SMARTALIGNPRO_OT_advanced_wheel_selector,
    )
    from .operators.ultimate_modal_operator import (
        SMARTALIGNPRO_OT_ultimate_modal,
    )
    from .operators.cad_operators import (
        SMARTALIGNPRO_OT_cad_snap_modal,
        SMARTALIGNPRO_OT_cad_quick_snap,
    )
    from .modal.modal_two_point_unified import (
        SMARTALIGNPRO_OT_modal_two_point_align,
    )
    from .modal.modal_three_point_unified import (
        SMARTALIGNPRO_OT_modal_three_point_align,
    )
    from .operators.preview_operators import (
        SMARTALIGNPRO_OT_preview_align,
        SMARTALIGNPRO_OT_apply_preview,
        SMARTALIGNPRO_OT_clear_preview,
    )
    from .operators.edge_face_align_operators import (
        SMARTALIGNPRO_OT_edge_align_quick,
        SMARTALIGNPRO_OT_edge_align_cad,
        SMARTALIGNPRO_OT_face_align_quick,
        SMARTALIGNPRO_OT_face_align_cad,
        SMARTALIGNPRO_OT_edge_align,
        SMARTALIGNPRO_OT_face_align,
        SMARTALIGNPRO_OT_copy_rotation_only,
        SMARTALIGNPRO_OT_copy_location_only,
        SMARTALIGNPRO_OT_copy_scale_only,
    )
    from .utils.bbox_utils import (
        SMARTALIGNPRO_OT_cycle_bbox_point,
        SMARTALIGNPRO_OT_toggle_bbox_point_overlay,
    )
    from .operators.utility_operators import (
        SMARTALIGNPRO_OT_analyze_scene,
        SMARTALIGNPRO_OT_measure_distance,
        SMARTALIGNPRO_OT_measure_angle,
        SMARTALIGNPRO_OT_measure_properties,
        SMARTALIGNPRO_OT_clear_measurements,
    )
    from .operators.multi_object_operators import (
        SMARTALIGNPRO_OT_multi_object_align,
        SMARTALIGNPRO_OT_pivot_align,
        SMARTALIGNPRO_OT_vector_constraint_align,
    )
    from .ui.main_panel import (
        SMARTALIGNPRO_PT_main_panel,
        SMARTALIGNPRO_PT_settings_panel,
        SMARTALIGNPRO_PT_info_panel,
    )
    from .operators.quick_align_operators import (
        SMARTALIGNPRO_OT_quick_align,
        SMARTALIGNPRO_OT_surface_align,
        SMARTALIGNPRO_OT_preset_align,
        SMARTALIGNPRO_PT_quick_align_panel,
    )
    from .operators.view_oriented_operators import (
        SMARTALIGNPRO_OT_view_oriented_align,
        SMARTALIGNPRO_OT_view_snap,
        SMARTALIGNPRO_PT_view_oriented_panel,
    )
    from .utils.error_handling import (
        SMARTALIGNPRO_OT_error_helper,
    )

    return [
        SMARTALIGNPRO_OT_two_point_align,
        SMARTALIGNPRO_OT_three_point_align,
        SMARTALIGNPRO_OT_three_point_modal,
        SMARTALIGNPRO_OT_modal_two_point_align,
        SMARTALIGNPRO_OT_modal_three_point_align,
        SMARTALIGNPRO_OT_surface_normal_align,
        SMARTALIGNPRO_OT_auto_contact_align,
        SMARTALIGNPRO_OT_align_to_ground,
        SMARTALIGNPRO_OT_align_to_surface,
        SMARTALIGNPRO_OT_smart_align,
        SMARTALIGNPRO_OT_smart_batch_align,
        SMARTALIGNPRO_OT_directional_wheel_selector,
        SMARTALIGNPRO_OT_cad_directional_selector,
        SMARTALIGNPRO_OT_advanced_wheel_selector,
        SMARTALIGNPRO_OT_cad_snap_modal,
        SMARTALIGNPRO_OT_cad_quick_snap,
        SMARTALIGNPRO_OT_edge_align_quick,
        SMARTALIGNPRO_OT_edge_align_cad,
        SMARTALIGNPRO_OT_face_align_quick,
        SMARTALIGNPRO_OT_face_align_cad,
        SMARTALIGNPRO_OT_edge_align,
        SMARTALIGNPRO_OT_face_align,
        SMARTALIGNPRO_OT_copy_rotation_only,
        SMARTALIGNPRO_OT_copy_location_only,
        SMARTALIGNPRO_OT_copy_scale_only,
        SMARTALIGNPRO_OT_cycle_bbox_point,
        SMARTALIGNPRO_OT_toggle_bbox_point_overlay,
        SMARTALIGNPRO_OT_analyze_scene,
        SMARTALIGNPRO_OT_measure_distance,
        SMARTALIGNPRO_OT_measure_angle,
        SMARTALIGNPRO_OT_measure_properties,
        SMARTALIGNPRO_OT_clear_measurements,
        SMARTALIGNPRO_OT_multi_object_align,
        SMARTALIGNPRO_OT_pivot_align,
        SMARTALIGNPRO_OT_vector_constraint_align,
        SMARTALIGNPRO_OT_preview_align,
        SMARTALIGNPRO_OT_apply_preview,
        SMARTALIGNPRO_OT_clear_preview,
        SMARTALIGNPRO_OT_ultimate_modal,
        SMARTALIGNPRO_PT_main_panel,
        SMARTALIGNPRO_PT_settings_panel,
        SMARTALIGNPRO_PT_info_panel,
        SMARTALIGNPRO_OT_quick_align,
        SMARTALIGNPRO_OT_surface_align,
        SMARTALIGNPRO_OT_preset_align,
        SMARTALIGNPRO_PT_quick_align_panel,
        SMARTALIGNPRO_OT_view_oriented_align,
        SMARTALIGNPRO_OT_view_snap,
        SMARTALIGNPRO_PT_view_oriented_panel,
        SMARTALIGNPRO_OT_error_helper,
    ]


def _safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
        print(f"[SmartAlignPro][STABLE] 類註銷成功: {cls.__name__}")
        return True
    except RuntimeError as e:
        if 'missing bl_rna' in str(e) or 'not registered' in str(e):
            print(f"[SmartAlignPro][STABLE] 類未註冊，跳過: {cls.__name__}")
            return False
        print(f"[SmartAlignPro][WARNING] 類註銷失敗 {cls.__name__}: {e}")
        return False
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] 類註銷失敗 {cls.__name__}: {e}")
        return False


def _safe_register_class(cls):
    try:
        bpy.utils.register_class(cls)
        print(f"[SmartAlignPro][STABLE] 類註冊成功: {cls.__name__}")
        return True
    except ValueError as e:
        if 'already registered as a subclass' in str(e):
            print(f"[SmartAlignPro][STABLE] 類已存在，先移除: {cls.__name__}")
            _safe_unregister_class(cls)
            bpy.utils.register_class(cls)
            print(f"[SmartAlignPro][STABLE] 類重新註冊成功: {cls.__name__}")
            return True
        print(f"[SmartAlignPro][ERROR] 類註冊失敗 {cls.__name__}: {e}")
        return False
    except Exception as e:
        print(f"[SmartAlignPro][ERROR] 類註冊失敗 {cls.__name__}: {e}")
        print("[SmartAlignPro][TRACEBACK]")
        traceback.print_exc()
        return False


def register_classes():
    classes = get_classes()
    ok = 0
    for cls in classes:
        print(f"[SmartAlignPro][STABLE] 正在註冊類: {cls.__name__}")
        if _safe_register_class(cls):
            ok += 1
    print(f"[SmartAlignPro][STABLE] 成功註冊 {ok} 個類")
    return classes


def unregister_classes():
    try:
        classes = get_classes()
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] 取得類列表失敗，略過類註銷: {e}")
        return
    for cls in reversed(classes):
        print(f"[SmartAlignPro][STABLE] 正在註銷類: {cls.__name__}")
        _safe_unregister_class(cls)
    print("[SmartAlignPro][STABLE] 類註銷流程完成")



def _is_registered_class(cls):
    return hasattr(cls, "bl_rna") and cls.bl_rna is not None


def register_settings():
    from .settings import SMARTALIGNPRO_PG_settings
    if hasattr(bpy.types.Scene, 'smartalignpro_settings'):
        try:
            del bpy.types.Scene.smartalignpro_settings
        except Exception as e:
            print(f"[SmartAlignPro][WARNING] 舊設置屬性清理失敗: {e}")
    if _is_registered_class(SMARTALIGNPRO_PG_settings):
        _safe_unregister_class(SMARTALIGNPRO_PG_settings)
    if not _safe_register_class(SMARTALIGNPRO_PG_settings):
        raise RuntimeError("SMARTALIGNPRO_PG_settings 註冊失敗")
    bpy.types.Scene.smartalignpro_settings = bpy.props.PointerProperty(type=SMARTALIGNPRO_PG_settings)
    print("[SmartAlignPro][STABLE] 設置系統註冊成功")


def unregister_settings():
    from .settings import SMARTALIGNPRO_PG_settings
    if hasattr(bpy.types.Scene, 'smartalignpro_settings'):
        try:
            del bpy.types.Scene.smartalignpro_settings
        except Exception as e:
            print(f"[SmartAlignPro][WARNING] 設置屬性刪除失敗: {e}")
    if _is_registered_class(SMARTALIGNPRO_PG_settings):
        _safe_unregister_class(SMARTALIGNPRO_PG_settings)
    else:
        print("[SmartAlignPro][STABLE] 設置類未註冊，略過註銷")
    print("[SmartAlignPro][STABLE] 設置系統註銷成功")


def pre_register_cleanup():
    """註冊前清理舊設置"""
    from .settings import SMARTALIGNPRO_PG_settings
    if hasattr(bpy.types.Scene, 'smartalignpro_settings'):
        try:
            del bpy.types.Scene.smartalignpro_settings
            print("[SmartAlignPro][STABLE] 舊設置屬性清理成功")
        except Exception as e:
            print(f"[SmartAlignPro][WARNING] 舊設置屬性清理失敗: {e}")
    if _is_registered_class(SMARTALIGNPRO_PG_settings):
        _safe_unregister_class(SMARTALIGNPRO_PG_settings)
    else:
        print("[SmartAlignPro][STABLE] SMARTALIGNPRO_PG_settings 尚未註冊，略過註銷")
    print("[SmartAlignPro][STABLE] 預註冊清理完成")


def register():
    """主註冊函數 - 改進版"""
    print("[SmartAlignPro][STABLE] 開始註冊穩定版本...")
    
    pre_register_cleanup()
    
    add_module_path()
    if not import_modules():
        print("[SmartAlignPro][ERROR] 模組導入失敗，註冊中止")
        return False

    try:
        register_settings()
    except Exception as e:
        print(f"[SmartAlignPro][ERROR] 設置註冊失敗: {e}")
        print("[SmartAlignPro][TRACEBACK]")
        traceback.print_exc()
        return False

    try:
        registered_classes = register_classes()
        print(f"[SmartAlignPro][STABLE] 成功註冊 {len(registered_classes)} 個類")
    except Exception as e:
        print(f"[SmartAlignPro][ERROR] 類註冊失敗: {e}")
        print("[SmartAlignPro][TRACEBACK]")
        traceback.print_exc()
        try:
            unregister_settings()
        except Exception:
            pass
        return False

    keymaps_ok = False
    try:
        from .keymap_manager import register_keymaps, print_keymap_help, print_keymap_reference, unregister_keymaps
        try:
            unregister_keymaps()
            print("[SmartAlignPro][STABLE] 舊快捷鍵清理完成")
        except Exception as e:
            print(f"[SmartAlignPro][WARNING] 舊快捷鍵清理失敗: {e}")

        register_keymaps()
        print_keymap_help()
        # A-3: 列出 3D View 中 A/Q/Z 衝突偵測資訊
        try:
            print_keymap_reference()
        except Exception as e:
            print(f"[SmartAlignPro][WARNING] print_keymap_reference 失敗: {e}")
        keymaps_ok = True
        print("[SmartAlignPro][STABLE] 快捷鍵註冊成功")
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] 快捷鍵註冊失敗（非致命）: {e}")
        print("[SmartAlignPro][TRACEBACK]")
        traceback.print_exc()

    if keymaps_ok:
        print("[SmartAlignPro][STABLE] ✓ 穩定版本註冊完全成功！")
    else:
        print("[SmartAlignPro][STABLE] ⚠ 穩定版本部分註冊成功（快捷鍵異常，但基礎功能可用）")
    
    return True


def unregister():
    """主註銷函數"""
    print("[SmartAlignPro][STABLE] 開始註銷穩定版本...")

    try:
        from .operators.preview_operators import remove_preview_handlers, remove_preview_data
        remove_preview_handlers()
        remove_preview_data()
        print("[SmartAlignPro][STABLE] Preview handlers 清理完成")
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] Preview handlers 清理失敗: {e}")

    try:
        from .utils.bbox_utils import remove_bbox_handler
        remove_bbox_handler()
        print("[SmartAlignPro][STABLE] Bbox overlay 清理完成")
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] Bbox overlay 清理失敗: {e}")

    try:
        from .keymap_manager import unregister_keymaps
        unregister_keymaps()
        print("[SmartAlignPro][STABLE] 快捷鍵清理完成")
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] 快捷鍵清理失敗: {e}")

    try:
        from .ui.hud_selector import hud_selector
        if hud_selector and getattr(hud_selector, 'is_active', False):
            hud_selector.stop()
            print("[SmartAlignPro][STABLE] HUD selector 清理完成")
    except Exception as e:
        print(f"[SmartAlignPro][WARNING] HUD selector 清理失敗: {e}")

    unregister_classes()
    unregister_settings()
    
    print("[SmartAlignPro][STABLE] ✓ 穩定版本註銷完成！")


if __name__ == "__main__":
    register()
