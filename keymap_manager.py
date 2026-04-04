"""
Smart Align Pro - Keymap Manager v7.5.2
Alt+A 穩定啟動 + 偵錯輸出強化版
"""

import bpy

addon_keymaps = []
_keymaps_registered = False

KEYMAP_CONFIG = {
    "alt_q": {"operator": "smartalignpro.directional_wheel_selector", "key": "Q", "desc": "智慧對齊選單"},
    "alt_a": {"operator": "smartalignpro.cad_directional_selector", "key": "A", "desc": "CAD 方向選單"},
    "alt_ctrl_z": {"operator": "smartalignpro.advanced_wheel_selector", "key": "Z", "ctrl": True, "desc": "進階工具選單"},
    "alt_1": {"operator": "smartalignpro.two_point_align", "key": "ONE", "desc": "Two Point Align"},
    "alt_2": {"operator": "smartalignpro.three_point_modal", "key": "TWO", "desc": "Three Point Align"},
    "alt_3": {"operator": "smartalignpro.surface_normal_align", "key": "THREE", "desc": "Surface Normal Align"},
    "alt_4": {"operator": "smartalignpro.auto_contact_align", "key": "FOUR", "desc": "Contact Align"},
    "alt_v": {"operator": "smartalignpro.preview_align", "key": "V", "desc": "Preview Align"},
}

def register_keymaps():
    global addon_keymaps, _keymaps_registered

    # 先清理舊 keymap，避免 orphan state
    unregister_keymaps()

    if _keymaps_registered:
        return

    wm = bpy.context.window_manager
    if wm is None or wm.keyconfigs.addon is None:
        print("[SmartAlignPro][KEYMAP] wm or keyconfigs.addon is None, skipping registration")
        return

    # Item 3: 只鎖定 3D View + Object Mode，不影響 UV / Text Editor / Console / Sculpt
    # The operator itself also has a poll() check for context.mode == "OBJECT"
    kc = wm.keyconfigs.addon
    km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")

    for config_key, config in KEYMAP_CONFIG.items():
        try:
            kmi = km.keymap_items.new(
                config["operator"],
                type=config["key"],
                value="PRESS",
                alt=True,
                ctrl=config.get("ctrl", False),
                shift=config.get("shift", False),
                head=True,
            )
            addon_keymaps.append((km, kmi))
            # A-1: 強化偵錯輸出
            print(
                f"[SmartAlignPro][KEYMAP] registered | km={km.name} "
                f"op={config['operator']} key={config['key']} "
                f"alt=True ctrl={config.get('ctrl', False)} "
                f"shift={config.get('shift', False)} head=True"
            )
        except Exception as e:
            print(f"[SmartAlignPro][KEYMAP] register failed: {config} | {e}")

    _keymaps_registered = True
    print(f"[SmartAlignPro][KEYMAP] 共成功註冊 {len(addon_keymaps)} 個快捷鍵（僅限 3D View）")


def unregister_keymaps():
    global addon_keymaps, _keymaps_registered
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    addon_keymaps.clear()
    _keymaps_registered = False


# A-2: 新增衝突偵測工具
def print_keymap_reference():
    """列出 3D View 中所有與 A / Q / Z 有關的 keymap item，用於追蹤衝突"""
    wm = bpy.context.window_manager
    if wm is None:
        print("[SmartAlignPro][KEYMAP REF] wm is None")
        return

    INTEREST_KEYS = {"A", "Q", "Z"}
    sources = []
    if wm.keyconfigs.addon:
        sources.append(("addon", wm.keyconfigs.addon))
    if wm.keyconfigs.user:
        sources.append(("user", wm.keyconfigs.user))

    print("\n[SmartAlignPro][KEYMAP REF] ===== 3D View A/Q/Z 衝突偵測 =====")
    for src_name, kc in sources:
        for km in kc.keymaps:
            if km.name != "3D View":
                continue
            for kmi in km.keymap_items:
                if kmi.type in INTEREST_KEYS:
                    print(
                        f"  [{src_name}] km={km.name} "
                        f"op={kmi.idname} key={kmi.type} "
                        f"alt={kmi.alt} ctrl={kmi.ctrl} shift={kmi.shift} "
                        f"active={kmi.active} value={kmi.value}"
                    )
    print("[SmartAlignPro][KEYMAP REF] ========================================\n")


def print_keymap_help():
    print("\n[SmartAlignPro v7.5.2] Keymaps (Selector First + Sticky Confirm)")
    print("=" * 60)
    print("[HUD / Selector Layer]")
    print("  Alt+A        -> CAD 方向選單")
    print("  Alt+Q        -> 智慧對齊選單")
    print("  Alt+Ctrl+Z   -> 進階工具選單")
    print("")
    print("[Direct Operations]")
    print("  Alt+1        -> Two Point Align")
    print("  Alt+2        -> Three Point Align (Sticky Confirm 升級版)")
    print("  Alt+3        -> Surface Normal Align")
    print("  Alt+4        -> Contact Align")
    print("  Alt+V        -> Preview Align")
    print("[Sticky Confirm 說明]")
    print("  * 吸附到非 RAY 點後，游標離開物件仍保留最後有效點高光")
    print("  * HUD 顯示「🔒 已鎖定最後有效吸附點」提示")
    print("  * 此狀態下左鍵仍可確認最後有效點")
    print("=" * 60 + "\n")


def log_hotkey_trigger(operator_name: str):
    try:
        print(f"[SmartAlignPro][HOTKEY] Triggered: {operator_name}")
    except Exception:
        pass


def log_hotkey_cancel(operator_name: str):
    try:
        print(f"[SmartAlignPro][HOTKEY] Cancelled: {operator_name}")
    except Exception:
        pass
