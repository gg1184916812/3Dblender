bl_info = {
    "name": "Smart Align Pro",
    "author": "Smart Align Pro Team",
    "version": (7, 5, 9),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > Smart Align",
    "description": "CAD-grade alignment system - 超越 CAD Transform 2.0 (v7.5.9 專注穩定版)",
    "category": "Object",
    "warning": "穩定化專注版",
    "wiki_url": "",
    "tracker_url": ""
}

__version__ = "7.5.9"

def register():
    try:
        from . import smart_align_pro_modular
        result = smart_align_pro_modular.register()
        if not result:
            print("[SmartAlignPro] WARNING: register() returned False")
        return result
    except Exception as e:
        print(f"[SmartAlignPro] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def unregister():
    try:
        from . import smart_align_pro_modular
        smart_align_pro_modular.unregister()
    except Exception as e:
        print(f"[SmartAlignPro] ERROR during unregister: {e}")
        import traceback
        traceback.print_exc()