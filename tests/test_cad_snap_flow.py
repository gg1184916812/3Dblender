"""
Smart Align Pro - CAD Snap / Quick Snap 回歸測試
v7.6 — 覆蓋 invoke、modal、confirm、cancel、fallback、sticky

執行方式（在 Blender Python console 內）：
    import sys; sys.path.insert(0, "/path/to/addon_parent")
    from smart_align_pro_v7_5_final.tests.test_cad_snap_flow import run_all
    run_all()
"""

import bpy
from mathutils import Vector


# ─── 測試輔助工具 ────────────────────────────────────────────

class _Result:
    def __init__(self, name):
        self.name   = name
        self.passed = True
        self.reason = ""

    def fail(self, reason):
        self.passed = False
        self.reason = reason

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        suffix = f" — {self.reason}" if not self.passed else ""
        return f"  [{status}] {self.name}{suffix}"


def _make_mesh_obj(name="__test_obj__", size=1.0):
    """建立測試用 Mesh 物件，自動清理同名舊物件"""
    if name in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    bpy.ops.mesh.primitive_cube_add(size=size, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    return obj


def _cleanup(*names):
    for name in names:
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)


def _ensure_3d_context():
    """確保有可用的 3D Viewport context"""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    return area, region
    return None, None


# ─── 個別測試 ────────────────────────────────────────────────

def test_quick_snap_operator_exists():
    r = _Result("quick_snap operator 已註冊")
    if not hasattr(bpy.ops.smartalignpro, "quick_snap"):
        r.fail("bpy.ops.smartalignpro.quick_snap 不存在")
    return r


def test_cad_snap_modal_operator_exists():
    r = _Result("cad_snap_modal operator 已註冊")
    if not hasattr(bpy.ops.smartalignpro, "cad_snap_modal"):
        r.fail("bpy.ops.smartalignpro.cad_snap_modal 不存在")
    return r


def test_cad_quick_snap_operator_exists():
    r = _Result("cad_quick_snap (legacy shim) 已註冊")
    if not hasattr(bpy.ops.smartalignpro, "cad_quick_snap"):
        r.fail("bpy.ops.smartalignpro.cad_quick_snap 不存在")
    return r


def test_snap_solver_core_import():
    r = _Result("snap_solver_core 可正常 import")
    try:
        from smart_align_pro_v7_5_final.core.snap_solver_core import (
            SnapResult, SnapSolverMixin, snap_solver_core,
            snap_radius_for, sticky_radius_for,
        )
    except Exception as e:
        r.fail(str(e))
    return r


def test_snap_engine_import():
    r = _Result("snap_engine 可正常 import")
    try:
        from smart_align_pro_v7_5_final.core.snap_engine import snap_engine
    except Exception as e:
        r.fail(str(e))
    return r


def test_evaluated_depsgraph_get():
    r = _Result("evaluated_depsgraph_get() API 正確（不用舊版 ()）")
    try:
        import ast, os
        snap_engine_path = os.path.join(
            os.path.dirname(__file__), "..", "core", "snap_engine.py"
        )
        with open(snap_engine_path, "r") as f:
            src = f.read()
        if "evaluated_depsgraph()" in src:
            r.fail("snap_engine.py 仍有 evaluated_depsgraph()（應為 evaluated_depsgraph_get()）")
        quick_align_path = os.path.join(
            os.path.dirname(__file__), "..", "operators", "quick_align_operators.py"
        )
        with open(quick_align_path, "r") as f:
            src2 = f.read()
        if "evaluated_depsgraph()" in src2:
            r.fail("quick_align_operators.py 仍有 evaluated_depsgraph()（應為 evaluated_depsgraph_get()）")
    except Exception as e:
        r.fail(str(e))
    return r


def test_snap_solver_mixin_init():
    r = _Result("SnapSolverMixin.init_snap_state() 可正常初始化")
    try:
        from smart_align_pro_v7_5_final.core.snap_solver_core import SnapSolverMixin

        class _FakeOp(SnapSolverMixin):
            pass

        op = _FakeOp()
        op.init_snap_state()
        assert op._snap_fresh is None
        assert op._snap_sticky is None
        assert op._snap_last_valid is None
        assert op._snap_state == "IDLE"
    except Exception as e:
        r.fail(str(e))
    return r


def test_snap_result_from_dict():
    r = _Result("SnapResult.from_dict() 可從 dict 建立")
    try:
        from smart_align_pro_v7_5_final.core.snap_solver_core import SnapResult
        d = {
            "location": Vector((1, 2, 3)),
            "snap_location": Vector((1, 2, 3)),
            "snap_type": "VERTEX",
            "normal": Vector((0, 0, 1)),
            "face_index": 0,
            "object": None,
            "matrix": None,
            "screen_distance": 5.0,
        }
        sr = SnapResult.from_dict(d)
        assert sr.snap_type == "VERTEX"
        assert sr.screen_distance == 5.0
    except Exception as e:
        r.fail(str(e))
    return r


def test_store_fresh_and_get_effective():
    r = _Result("store_fresh → get_effective 4-level chain 正常")
    try:
        from smart_align_pro_v7_5_final.core.snap_solver_core import SnapResult, SnapSolverMixin

        class _FakeOp(SnapSolverMixin):
            pass

        op = _FakeOp()
        op.init_snap_state()

        # Simulate a fresh VERTEX hit
        sr = SnapResult(
            location=Vector((1, 0, 0)),
            snap_type="VERTEX",
            screen_distance=5.0,
        )
        op.store_fresh(sr, "SOURCE_A", None)
        result, src = op.get_effective("SOURCE_A", "ALL")
        assert result is not None, "get_effective 回傳 None"
        assert src in ("fresh", "current"), f"source 應為 fresh/current，實際為 {src}"

        # Simulate mouse leave (fresh = None) — sticky should kick in
        op.store_fresh(None, "SOURCE_A", None)
        result2, src2 = op.get_effective("SOURCE_A", "ALL")
        assert result2 is not None, "sticky 未保留（None）"
        assert src2 in ("sticky", "last_valid"), f"source 應為 sticky/last_valid，實際為 {src2}"
    except Exception as e:
        r.fail(str(e))
    return r


def test_nearest_candidate_helper_exists():
    r = _Result("_nearest_candidate_on_object helper 已定義在 alignment_operators")
    try:
        import ast, os
        path = os.path.join(os.path.dirname(__file__), "..", "operators", "alignment_operators.py")
        with open(path, "r") as f:
            src = f.read()
        if "_nearest_candidate_on_object" not in src:
            r.fail("_nearest_candidate_on_object 函數不存在")
    except Exception as e:
        r.fail(str(e))
    return r


def test_space_exit_in_two_point():
    r = _Result("two_point_align modal 有 SPACE 退出邏輯")
    try:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "operators", "alignment_operators.py")
        with open(path, "r") as f:
            src = f.read()
        # Check SPACE handler exists
        if 'event.type=="SPACE"' not in src and "event.type == 'SPACE'" not in src and 'event.type==\"SPACE\"' not in src:
            r.fail("alignment_operators.py 中找不到 SPACE 退出邏輯")
    except Exception as e:
        r.fail(str(e))
    return r


def test_quick_snap_has_independent_modal():
    r = _Result("quick_snap 有自己的獨立 modal（不再只呼叫 cad_snap_modal）")
    try:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "operators", "cad_operators.py")
        with open(path, "r") as f:
            src = f.read()
        # Must have SMARTALIGNPRO_OT_quick_snap with its own modal
        if "class SMARTALIGNPRO_OT_quick_snap" not in src:
            r.fail("SMARTALIGNPRO_OT_quick_snap class 不存在")
        if "def modal" not in src:
            r.fail("quick_snap 中沒有 modal 方法")
        # Must NOT use invoke-default of cad_snap_modal inside quick_snap
        qs_section = src[src.find("class SMARTALIGNPRO_OT_quick_snap"):]
        next_class = qs_section.find("\nclass ", 1)
        qs_body = qs_section[:next_class] if next_class > 0 else qs_section
        if 'cad_snap_modal("INVOKE_DEFAULT"' in qs_body:
            r.fail("quick_snap 仍在呼叫 cad_snap_modal INVOKE_DEFAULT（沒有獨立流程）")
    except Exception as e:
        r.fail(str(e))
    return r


def test_cad_snap_has_transform_mode():
    r = _Result("cad_snap_modal 有 transform_mode（MOVE/ROTATE）")
    try:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "operators", "cad_operators.py")
        with open(path, "r") as f:
            src = f.read()
        if "transform_mode" not in src:
            r.fail("cad_snap_modal 沒有 transform_mode 屬性")
        if '"MOVE"' not in src or '"ROTATE"' not in src:
            r.fail("transform_mode 缺少 MOVE 或 ROTATE 選項")
    except Exception as e:
        r.fail(str(e))
    return r


def test_hud_minimal():
    r = _Result("measurement_overlay HUD 已精簡（無 ΔX/ΔY/ΔZ、無來源/目標名稱）")
    try:
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "utils", "measurement_overlay.py")
        with open(path, "r") as f:
            src = f.read()
        banned = ["ΔX:", "ΔY:", "ΔZ:", "來源:", "目標:", "目前座標"]
        for b in banned:
            if b in src and '_draw_pixel' in src:
                # Check if it's inside _draw_pixel
                draw_start = src.find("def _draw_pixel")
                draw_end = src.find("\n    def ", draw_start + 1)
                draw_body = src[draw_start:draw_end]
                if b in draw_body:
                    r.fail(f"_draw_pixel 仍顯示 {b}")
                    return r
    except Exception as e:
        r.fail(str(e))
    return r


# ─── 執行全部測試 ─────────────────────────────────────────────

ALL_TESTS = [
    test_quick_snap_operator_exists,
    test_cad_snap_modal_operator_exists,
    test_cad_quick_snap_operator_exists,
    test_snap_solver_core_import,
    test_snap_engine_import,
    test_evaluated_depsgraph_get,
    test_snap_solver_mixin_init,
    test_snap_result_from_dict,
    test_store_fresh_and_get_effective,
    test_nearest_candidate_helper_exists,
    test_space_exit_in_two_point,
    test_quick_snap_has_independent_modal,
    test_cad_snap_has_transform_mode,
    test_hud_minimal,
]


def run_all(verbose=True):
    results = [t() for t in ALL_TESTS]
    passed  = sum(1 for r in results if r.passed)
    total   = len(results)
    print("\n" + "=" * 56)
    print(f"  SmartAlignPro CAD Snap 回歸測試  v7.6")
    print("=" * 56)
    for r in results:
        print(str(r))
    print("-" * 56)
    print(f"  結果：{passed}/{total} 通過")
    if passed == total:
        print("  ✅ 全部通過！")
    else:
        print(f"  ❌ {total - passed} 項失敗，請檢查上方細節")
    print("=" * 56 + "\n")
    return passed == total


if __name__ == "__main__":
    run_all()
