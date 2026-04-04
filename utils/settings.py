"""
Smart Align Pro - 參數化調校系統
純輔助函式模組，屬性已合併到 settings.py 的 SMARTALIGNPRO_PG_settings
"""

import bpy
from typing import Dict, Any, Tuple


def get_settings() -> bpy.types.PropertyGroup:
    """獲取當前場景的 Smart Align Pro 設置"""
    if not hasattr(bpy.context, 'scene') or not bpy.context.scene:
        return None
    return getattr(bpy.context.scene, 'smartalignpro_settings', None)


def get_snap_settings() -> Dict[str, Any]:
    """獲取吸附設置"""
    settings = get_settings()
    if settings is None:
        return {
            "snap_tolerance": 20.0,
            "sticky_radius": 18.0,
            "hysteresis_factor": 1.15,
            "release_threshold": 20.0,
            "enable_hysteresis": True,
            "enable_sticky_release": True,
            "outside_tolerance": 0.1
        }
    return {
        "snap_tolerance": settings.snap_tolerance,
        "sticky_radius": settings.sticky_radius,
        "hysteresis_factor": settings.hysteresis_factor,
        "release_threshold": settings.release_threshold,
        "enable_hysteresis": settings.enable_hysteresis,
        "enable_sticky_release": settings.enable_sticky_release,
        "outside_tolerance": settings.outside_tolerance
    }


def get_preview_settings() -> Dict[str, Any]:
    """獲取預覽設置"""
    settings = get_settings()
    return {
        "show_preview": settings.show_preview,
        "preview_opacity": settings.preview_opacity
    }


def get_hud_settings() -> Dict[str, Any]:
    """獲取 HUD 設置"""
    settings = get_settings()
    return {
        "show_hud": settings.show_hud,
        "hudson_position": settings.hud_position
    }


def get_constraint_settings() -> Dict[str, Any]:
    """獲取約束設置"""
    settings = get_settings()
    return {
        "default_constraint": settings.default_constraint
    }


def apply_settings_to_snap_engine(snap_engine) -> None:
    """將設置應用到吸附引擎"""
    snap_settings = get_snap_settings()
    
    snap_engine.snap_radii = {
        "VERTEX": int(snap_settings["snap_tolerance"]),
        "MIDPOINT": int(snap_settings["snap_tolerance"] - 2),
        "EDGE": int(snap_settings["snap_tolerance"] - 6),
        "FACE_CENTER": int(snap_settings["snap_tolerance"] + 2),
        "FACE": int(snap_settings["snap_tolerance"] + 6),
        "ORIGIN": int(snap_settings["snap_tolerance"] + 4)
    }
    
    if hasattr(snap_engine, 'candidate_cache'):
        snap_engine.candidate_cache.sticky_radius = snap_settings["sticky_radius"]
        snap_engine.candidate_cache.hysteresis_factor = snap_settings["hysteresis_factor"]
    
    if hasattr(snap_engine, 'sticky_release'):
        snap_engine.sticky_release.release_threshold = snap_settings["release_threshold"]


def register_properties():
    """註冊屬性（已遷移到 settings.py）"""
    pass


def unregister_properties():
    """註銷屬性（已遷移到 settings.py）"""
    pass
