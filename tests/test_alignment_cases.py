"""
Smart Align Pro v7.5.5 - Automated Regression Test Suite
Item 10: 10-case baseline you can run before every release.

Run inside Blender's Python console:
    import sys; sys.path.insert(0, "/path/to/addon/parent")
    from smart_align_pro_v7_5.tests.test_alignment_cases import run_all
    run_all()

Or from the OS shell with Blender's Python:
    blender --background --python smart_align_pro_v7_5/tests/test_alignment_cases.py

All tests operate on temporary scene objects that are created and deleted
automatically — they do NOT touch the user's scene.
"""

# ── bpy stub: makes Blender-free imports work ──────────────────────────────
import sys as _sys
import types as _types
import importlib as _importlib

def _install_bpy_stub():
    """Install a minimal bpy stub so core modules load outside Blender."""
    if "bpy" in _sys.modules:
        return  # already have real bpy (running inside Blender)

    bpy_mock = _types.ModuleType("bpy")
    # Add sub-modules that various files import from
    for sub in ("types", "props", "utils", "context", "app", "data",
                "ops", "path", "msgbus"):
        m = _types.ModuleType(f"bpy.{sub}")
        setattr(bpy_mock, sub.split(".")[-1], m)

    # bpy.props decorators that return identity
    def _noop(**_kw):
        def _decorator(fn): return fn
        return _decorator
    for prop_name in ("StringProperty","IntProperty","FloatProperty","BoolProperty",
                      "EnumProperty","PointerProperty","CollectionProperty","FloatVectorProperty"):
        setattr(bpy_mock.props, prop_name, _noop)

    # bpy.types base classes
    for cls_name in ("Operator","Panel","PropertyGroup","AddonPreferences",
                     "SpaceView3D","WorkSpace"):
        setattr(bpy_mock.types, cls_name, object)

    # bpy.utils stubs
    bpy_mock.utils.register_class   = lambda *a, **kw: None
    bpy_mock.utils.unregister_class = lambda *a, **kw: None

    _sys.modules["bpy"]         = bpy_mock
    _sys.modules["bpy.types"]   = bpy_mock.types
    _sys.modules["bpy.props"]   = bpy_mock.props
    _sys.modules["bpy.utils"]   = bpy_mock.utils

    # mathutils stub (only needed if real mathutils not available)
    if "mathutils" not in _sys.modules:
        import math as _math
        mu = _types.ModuleType("mathutils")

        class _Vec:
            def __init__(self, v=(0,0,0)):
                self._v = list(v)
            def __iter__(self): return iter(self._v)
            def __getitem__(self, i): return self._v[i]
            def __sub__(self, o): return _Vec([a-b for a,b in zip(self._v, o._v)])
            def __add__(self, o): return _Vec([a+b for a,b in zip(self._v, o._v)])
            def __matmul__(self, o):
                if isinstance(o, _Vec): return sum(a*b for a,b in zip(self._v, o._v))
                return o.__rmatmul__(self)
            def __rmul__(self, s): return _Vec([s*x for x in self._v])
            def dot(self, o): return sum(a*b for a,b in zip(self._v, o._v))
            def copy(self): return _Vec(list(self._v))
            def normalized(self):
                n = self.length
                return _Vec([x/n for x in self._v]) if n > 1e-12 else _Vec(list(self._v))
            @property
            def length(self): return _math.sqrt(sum(x*x for x in self._v))
            @property
            def x(self): return self._v[0]
            @property
            def y(self): return self._v[1]
            @property
            def z(self): return self._v[2] if len(self._v)>2 else 0.0
            def __repr__(self): return f"Vector({self._v})"
            def cross(self, o):
                a,b = self._v, o._v
                return _Vec([a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]])

        class _Quat:
            def __init__(self, wxyz_or_axis=(1,0,0,0), angle=None):
                """
                Support both calling conventions:
                  Quaternion((w,x,y,z))        -- 4-tuple
                  Quaternion(axis, angle)       -- axis vector + radians
                """
                import math as _math2
                if angle is not None:
                    # axis-angle form
                    ax = wxyz_or_axis
                    if hasattr(ax, '_v'):
                        ax = ax._v
                    n = _math2.sqrt(sum(v*v for v in ax))
                    if n > 1e-12:
                        ax = [v/n for v in ax]
                    s = _math2.sin(angle/2)
                    self.w = _math2.cos(angle/2)
                    self.x = ax[0]*s; self.y = ax[1]*s; self.z = ax[2]*s
                else:
                    self.w,self.x,self.y,self.z = wxyz_or_axis
            @property
            def _v(self): return (self.w,self.x,self.y,self.z)
            def to_matrix(self):
                import math as _math2
                m = _Mat4x4()
                w,x,y,z = self.w,self.x,self.y,self.z
                m._m[0][0]=1-2*(y*y+z*z); m._m[0][1]=2*(x*y-w*z); m._m[0][2]=2*(x*z+w*y)
                m._m[1][0]=2*(x*y+w*z);   m._m[1][1]=1-2*(x*x+z*z); m._m[1][2]=2*(y*z-w*x)
                m._m[2][0]=2*(x*z-w*y);   m._m[2][1]=2*(y*z+w*x); m._m[2][2]=1-2*(x*x+y*y)
                return m
            def __matmul__(self, v):
                import math as _math2
                qv = _Vec((self.x, self.y, self.z))
                uv = qv.cross(v)
                uuv = qv.cross(uv)
                return _Vec([v._v[i] + 2*(self.w*uv._v[i] + uuv._v[i]) for i in range(3)])

        class _Mat4x4:
            def __init__(self, rows=None):
                if rows is not None:
                    self._m = [list(r) for r in rows]
                else:
                    self._m = [[1 if i==j else 0 for j in range(4)] for i in range(4)]
            def __matmul__(self, o):
                if isinstance(o, _Vec):
                    return _Vec([sum(self._m[r][c]*o._v[c] for c in range(min(4,len(o._v)))) for r in range(3)])
                m = _Mat4x4()
                for i in range(4):
                    for j in range(4):
                        m._m[i][j] = sum(self._m[i][k]*o._m[k][j] for k in range(4))
                return m
            def __getitem__(self, i): return self._m[i]
            def to_4x4(self): return self
            def inverted(self):
                # 4x4 Gauss-Jordan inversion
                import copy as _copy
                n = 4
                a = [row[:] for row in self._m]
                inv = [[1.0 if i==j else 0.0 for j in range(n)] for i in range(n)]
                for col in range(n):
                    pivot = max(range(col,n), key=lambda r: abs(a[r][col]))
                    a[col],a[pivot] = a[pivot],a[col]
                    inv[col],inv[pivot] = inv[pivot],inv[col]
                    d = a[col][col]
                    if abs(d) < 1e-12: return _Mat4x4()
                    a[col] = [x/d for x in a[col]]
                    inv[col] = [x/d for x in inv[col]]
                    for row in range(n):
                        if row == col: continue
                        f = a[row][col]
                        a[row] = [a[row][j]-f*a[col][j] for j in range(n)]
                        inv[row] = [inv[row][j]-f*inv[col][j] for j in range(n)]
                m = _Mat4x4(); m._m = inv; return m
            @staticmethod
            def Translation(v): m = _Mat4x4(); m._m[0][3]=v[0]; m._m[1][3]=v[1]; m._m[2][3]=v[2]; return m
            @staticmethod
            def Rotation(angle, size, axis):
                import math
                m = _Mat4x4()
                c, s = math.cos(angle), math.sin(angle)
                if axis == "Z":
                    m._m[0][0]=c; m._m[0][1]=-s; m._m[1][0]=s; m._m[1][1]=c
                return m

        mu.Vector   = _Vec
        mu.Matrix   = _Mat4x4
        mu.Quaternion = _Quat
        _sys.modules["mathutils"] = mu

    # gpu_extras stub
    if "gpu_extras" not in _sys.modules:
        ge = _types.ModuleType("gpu_extras")
        gb = _types.ModuleType("gpu_extras.batch")
        gb.batch_for_shader = lambda *a, **kw: None
        ge.batch = gb
        _sys.modules["gpu_extras"] = ge
        _sys.modules["gpu_extras.batch"] = gb

    # gpu stub
    if "gpu" not in _sys.modules:
        g = _types.ModuleType("gpu")
        gs = _types.ModuleType("gpu.shader")
        gs.from_builtin = lambda *a, **kw: None
        g.shader = gs
        _sys.modules["gpu"] = g
        _sys.modules["gpu.shader"] = gs

    # blf stub
    if "blf" not in _sys.modules:
        blf = _types.ModuleType("blf")
        for fn in ("position","size","color","draw","enable","disable"):
            setattr(blf, fn, lambda *a,**kw: None)
        _sys.modules["blf"] = blf

    # bgl stub
    if "bgl" not in _sys.modules:
        bgl = _types.ModuleType("bgl")
        for name in ("GL_BLEND","GL_LINE_STIPPLE","GL_DEPTH_TEST"):
            setattr(bgl, name, 0)
        for fn in ("glEnable","glDisable","glLineWidth","glLineStipple","glBlendFunc"):
            setattr(bgl, fn, lambda *a,**kw: None)
        _sys.modules["bgl"] = bgl

    # bpy_extras stub
    if "bpy_extras" not in _sys.modules:
        be = _types.ModuleType("bpy_extras")
        v3 = _types.ModuleType("bpy_extras.view3d_utils")
        v3.region_2d_to_origin_3d   = lambda *a,**kw: _sys.modules["mathutils"].Vector((0,0,0))
        v3.region_2d_to_vector_3d   = lambda *a,**kw: _sys.modules["mathutils"].Vector((0,0,1))
        v3.location_3d_to_region_2d = lambda *a,**kw: None
        be.view3d_utils = v3
        _sys.modules["bpy_extras"] = be
        _sys.modules["bpy_extras.view3d_utils"] = v3

_install_bpy_stub()

# Extend bpy stub: add mathutils sub-packages that cad_snap.py needs
import sys as _sys2
import types as _types2
if "mathutils" in _sys2.modules:
    _mu = _sys2.modules["mathutils"]
    if not isinstance(_mu, type(None)):
        # mathutils.bvhtree stub
        _bvh = _types2.ModuleType("mathutils.bvhtree")
        class _BVHTree:
            @staticmethod
            def FromObject(*a,**kw): return _BVHTree()
            def ray_cast(self,*a,**kw): return None,None,None,None
        _bvh.BVHTree = _BVHTree
        _sys2.modules["mathutils.bvhtree"] = _bvh
        setattr(_mu, "bvhtree", _bvh)
        # mathutils.geometry stub
        _geo = _types2.ModuleType("mathutils.geometry")
        _geo.intersect_ray_tri = lambda *a,**kw: None
        _sys2.modules["mathutils.geometry"] = _geo
        setattr(_mu, "geometry", _geo)

# Also stub out heavy modules that core/__init__.py pulls in
_NOOP_MODULES = [
    "smart_align_pro_v7_5.core.alignment",
    "smart_align_pro_v7_5.core.cad_snap",
    "smart_align_pro_v7_5.core.contact_align_engine",
    "smart_align_pro_v7_5.core.coordinate_space_solver",
    "smart_align_pro_v7_5.core.hover_preview_system",
    "smart_align_pro_v7_5.core.interactive_preview",
    "smart_align_pro_v7_5.core.modal_kernel",
    "smart_align_pro_v7_5.core.multi_object_solver",
    "smart_align_pro_v7_5.core.orientation_solver",
    "smart_align_pro_v7_5.core.realtime_preview_engine",
    "smart_align_pro_v7_5.core.reference_picking_engine",
    "smart_align_pro_v7_5.core.smart_align_engine",
    "smart_align_pro_v7_5.core.topology_alignment",
    "smart_align_pro_v7_5.core.unified_modal_base",
    "smart_align_pro_v7_5.core.view_axis_solver",
    "smart_align_pro_v7_5.core.detection",
    "smart_align_pro_v7_5.core.snap_engine",
    "smart_align_pro_v7_5.core.snap_priority_solver",
    "smart_align_pro_v7_5.core.snap_scoring_engine",
    "smart_align_pro_v7_5.core.soft_snap_engine",
    "smart_align_pro_v7_5.core.solver_manager",
    "smart_align_pro_v7_5.core.sticky_intent",
    "smart_align_pro_v7_5.core.align_engine",
    "smart_align_pro_v7_5.core.unified_solver_engine",
    "smart_align_pro_v7_5.core.unified_preview_engine",
    "smart_align_pro_v7_5.core.unified_snap_decision",
    "smart_align_pro_v7_5.core.workflow_router",
    "smart_align_pro_v7_5.core.zero_mode_controller",
    "smart_align_pro_v7_5.core.constraint_plane_system",
    "smart_align_pro_v7_5.core.axis_locking_system",
    "smart_align_pro_v7_5.core.edge_solver",
    "smart_align_pro_v7_5.core.face_solver",
    "smart_align_pro_v7_5.core.preview_transform",
    "smart_align_pro_v7_5.core.three_point_solver",
    "smart_align_pro_v7_5.core.two_point_solver",
]
for _m in _NOOP_MODULES:
    if _m not in _sys2.modules:
        _sys2.modules[_m] = _types2.ModuleType(_m)

# Pre-stub smart_align_pro_v7_5.core as a proper package object
import importlib.util as _ilu, os as _os2
_ADDON_DIR = _os2.path.dirname(_os2.path.dirname(_os2.path.abspath(__file__)))
_PARENT_DIR = _os2.path.dirname(_ADDON_DIR)

def _load_module_direct(mod_name, file_path):
    """Load a single .py file as a named module, bypassing package __init__."""
    if mod_name in _sys2.modules:
        return _sys2.modules[mod_name]
    spec = _ilu.spec_from_file_location(mod_name, file_path)
    if spec is None:
        raise ImportError(f"Cannot find {file_path}")
    m = _ilu.module_from_spec(spec)
    _sys2.modules[mod_name] = m
    spec.loader.exec_module(m)
    return m

# Make smart_align_pro_v7_5 a package
_pkg = _types2.ModuleType("smart_align_pro_v7_5")
_pkg.__path__ = [_ADDON_DIR]
_pkg.__package__ = "smart_align_pro_v7_5"
_sys2.modules["smart_align_pro_v7_5"] = _pkg

# Make smart_align_pro_v7_5.core a package (without running its __init__)
_core_pkg = _types2.ModuleType("smart_align_pro_v7_5.core")
_core_pkg.__path__ = [_os2.path.join(_ADDON_DIR, "core")]
_core_pkg.__package__ = "smart_align_pro_v7_5.core"
_sys2.modules["smart_align_pro_v7_5.core"] = _core_pkg
setattr(_pkg, "core", _core_pkg)

# Pre-load snap_solver_core and selector_state_machine directly
_snap_solver_path = _os2.path.join(_ADDON_DIR, "core", "snap_solver_core.py")
_sm_path          = _os2.path.join(_ADDON_DIR, "core", "selector_state_machine.py")
_load_module_direct("smart_align_pro_v7_5.core.snap_solver_core", _snap_solver_path)
_load_module_direct("smart_align_pro_v7_5.core.selector_state_machine", _sm_path)
setattr(_core_pkg, "snap_solver_core", _sys2.modules["smart_align_pro_v7_5.core.snap_solver_core"])
setattr(_core_pkg, "selector_state_machine", _sys2.modules["smart_align_pro_v7_5.core.selector_state_machine"])

# Pre-load math_utils directly (needed for TestMathUtils)
_math_utils_path = _os2.path.join(_ADDON_DIR, "core", "math_utils.py")
_load_module_direct("smart_align_pro_v7_5.core.math_utils", _math_utils_path)
setattr(_core_pkg, "math_utils", _sys2.modules["smart_align_pro_v7_5.core.math_utils"])

# Pre-load keymap_manager directly (needed for TestKeymap)
_km_path = _os2.path.join(_ADDON_DIR, "keymap_manager.py")
_load_module_direct("smart_align_pro_v7_5.keymap_manager", _km_path)
setattr(_pkg, "keymap_manager", _sys2.modules["smart_align_pro_v7_5.keymap_manager"])



# ── end bpy stub ─────────────────────────────────────────────────────────────

import sys
import math
import traceback
from typing import List, Tuple, Callable, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Minimal test harness (no external dependencies)
# ─────────────────────────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", duration_ms: float = 0.0):
        self.name       = name
        self.passed     = passed
        self.message    = message
        self.duration_ms = duration_ms

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        ms     = f"{self.duration_ms:.1f}ms"
        base   = f"  [{status}] {self.name} ({ms})"
        return base if self.passed else f"{base}\n         → {self.message}"


class TestSuite:
    def __init__(self, name: str):
        self.name    = name
        self.results: List[TestResult] = []

    def run(self, fn: Callable, label: str) -> TestResult:
        import time
        t0 = time.perf_counter()
        try:
            fn()
            r = TestResult(label, True, duration_ms=(time.perf_counter()-t0)*1000)
        except AssertionError as e:
            r = TestResult(label, False, str(e), duration_ms=(time.perf_counter()-t0)*1000)
        except Exception as e:
            r = TestResult(label, False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}", duration_ms=(time.perf_counter()-t0)*1000)
        self.results.append(r)
        return r

    def summary(self) -> str:
        passed = sum(1 for r in self.results if r.passed)
        total  = len(self.results)
        lines  = [f"\n{'='*60}", f"  {self.name}  ({passed}/{total} passed)", "="*60]
        for r in self.results:
            lines.append(str(r))
        lines.append("="*60)
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — pure math, no Blender dependency
# ─────────────────────────────────────────────────────────────────────────────

def vec3(x=0.0, y=0.0, z=0.0):
    try:
        from mathutils import Vector
        return Vector((x, y, z))
    except ImportError:
        return (x, y, z)

def vec_close(a, b, tol=1e-4) -> bool:
    try:
        from mathutils import Vector
        return (Vector(a) - Vector(b)).length < tol
    except ImportError:
        return all(abs(ai-bi) < tol for ai,bi in zip(a,b))

def assert_vec_close(a, b, tol=1e-4, msg=""):
    assert vec_close(a, b, tol), f"{msg}: {tuple(round(v,6) for v in a)} ≠ {tuple(round(v,6) for v in b)}"


# ─────────────────────────────────────────────────────────────────────────────
# Core math tests (pure Python, no Blender context needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestSnapSolverCore(TestSuite):
    def __init__(self):
        super().__init__("snap_solver_core — unit tests")

    def run_all(self):

        def test_snap_result_non_ray():
            from smart_align_pro_v7_5.core.snap_solver_core import SnapResult
            r = SnapResult(location=vec3(1,2,3), snap_type="VERTEX")
            assert r.is_non_ray, "VERTEX should be non-RAY"
            r2 = SnapResult(location=vec3(), snap_type="RAY")
            assert not r2.is_non_ray, "RAY should NOT be non-RAY"

        def test_snap_result_as_dict():
            from smart_align_pro_v7_5.core.snap_solver_core import SnapResult
            r  = SnapResult(location=vec3(1,0,0), snap_location=vec3(1.1,0,0), snap_type="MIDPOINT")
            d  = r.as_dict()
            r2 = SnapResult.from_dict(d)
            assert_vec_close(r2.snap_location, vec3(1.1,0,0), msg="from_dict round-trip")

        def test_filter_snap_type_all():
            from smart_align_pro_v7_5.core.snap_solver_core import SnapResult, snap_solver_core
            r = SnapResult(location=vec3(), snap_type="VERTEX")
            assert snap_solver_core.filter_by_snap_type(r, "ALL"), "ALL should pass VERTEX"
            assert snap_solver_core.filter_by_snap_type(r, "VERTEX"), "VERTEX filter"
            assert not snap_solver_core.filter_by_snap_type(r, "EDGE"), "EDGE filter should reject VERTEX"

        def test_filter_midpoint_expanded():
            from smart_align_pro_v7_5.core.snap_solver_core import SnapResult, snap_solver_core
            r = SnapResult(location=vec3(), snap_type="EDGE_MID")
            assert snap_solver_core.filter_by_snap_type(r, "MIDPOINT"), "EDGE_MID accepted as MIDPOINT"

        def test_radii_nonzero():
            from smart_align_pro_v7_5.core.snap_solver_core import snap_radius_for, sticky_radius_for
            for t in ["VERTEX","EDGE","FACE","ORIGIN","MIDPOINT","CENTER"]:
                assert snap_radius_for(t)  > 0, f"snap radius {t}"
                assert sticky_radius_for(t) > 0, f"sticky radius {t}"
                assert sticky_radius_for(t) >= snap_radius_for(t), f"sticky >= snap for {t}"

        def test_score_vertex_higher_than_face():
            from smart_align_pro_v7_5.core.snap_solver_core import SnapResult, snap_solver_core
            rv = SnapResult(location=vec3(), snap_type="VERTEX", screen_distance=5.0)
            rf = SnapResult(location=vec3(), snap_type="FACE",   screen_distance=5.0)
            sv = snap_solver_core.score(rv, 0, 0)
            sf = snap_solver_core.score(rf, 0, 0)
            assert sv > sf, f"VERTEX score ({sv:.3f}) should beat FACE ({sf:.3f})"

        self.run(test_snap_result_non_ray,       "SnapResult.is_non_ray")
        self.run(test_snap_result_as_dict,       "SnapResult dict round-trip")
        self.run(test_filter_snap_type_all,      "filter_by_snap_type ALL/VERTEX/EDGE")
        self.run(test_filter_midpoint_expanded,  "filter_by_snap_type MIDPOINT expanded")
        self.run(test_radii_nonzero,             "snap/sticky radii positive & sticky≥snap")
        self.run(test_score_vertex_higher_than_face, "score: VERTEX > FACE at same distance")


class TestSelectorStateMachine(TestSuite):
    def __init__(self):
        super().__init__("selector_state_machine — unit tests")

    def run_all(self):

        def test_initial_state():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm, IDLE
            sm = new_sm()
            assert sm.state == IDLE

        def test_live_snap_transition():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm, LIVE_SNAP
            sm = new_sm(); sm.on_live_snap()
            assert sm.state == LIVE_SNAP; assert sm.is_live; assert sm.has_snap

        def test_sticky_transition():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm, STICKY_SNAP
            sm = new_sm(); sm.on_live_snap(); sm.on_sticky()
            assert sm.state == STICKY_SNAP; assert sm.is_sticky

        def test_confirm_resets_to_idle():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm, CONFIRMED, IDLE
            sm = new_sm(); sm.on_live_snap(); sm.on_confirm(); sm.on_advance()
            assert sm.state == IDLE

        def test_cancel_idle():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm, IDLE
            sm = new_sm(); sm.on_live_snap(); sm.on_cancel()
            assert sm.state == IDLE

        def test_confirm_ready_upgrade():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm, CONFIRM_READY
            sm = new_sm(); sm.on_sticky(); sm.on_confirm_ready()
            assert sm.state == CONFIRM_READY

        def test_state_changed_flag():
            from smart_align_pro_v7_5.core.selector_state_machine import new_sm
            sm = new_sm(); sm.on_hover()
            assert sm.changed
            sm.reset_changed()
            assert not sm.changed
            sm.on_live_snap()
            assert sm.changed

        self.run(test_initial_state,          "initial state = IDLE")
        self.run(test_live_snap_transition,   "LIVE_SNAP transition")
        self.run(test_sticky_transition,      "STICKY_SNAP transition")
        self.run(test_confirm_resets_to_idle, "confirm → advance → IDLE")
        self.run(test_cancel_idle,            "cancel → IDLE")
        self.run(test_confirm_ready_upgrade,  "sticky → CONFIRM_READY upgrade")
        self.run(test_state_changed_flag,     "changed flag tracking")


class TestSnapSolverMixin(TestSuite):
    def __init__(self):
        super().__init__("SnapSolverMixin — 4-level chain unit tests")

    def run_all(self):

        def _make_mixin():
            from smart_align_pro_v7_5.core.snap_solver_core import SnapSolverMixin, SnapResult
            class _Op(SnapSolverMixin): pass
            op = _Op(); op.init_snap_state(); return op, SnapResult

        def test_fresh_wins():
            op, SR = _make_mixin()
            fresh = SR(location=vec3(1,0,0), snap_type="VERTEX")
            op.store_fresh(fresh, "SOURCE_A", None)
            res, src = op.get_effective("SOURCE_A")
            assert src == "fresh", f"expected 'fresh', got '{src}'"
            assert_vec_close(res.location, vec3(1,0,0))

        def test_current_fallback():
            op, SR = _make_mixin()
            # Store a non-RAY result to populate current+sticky
            r = SR(location=vec3(2,0,0), snap_type="VERTEX")
            op.store_fresh(r, "SOURCE_A", None)
            # Now send None (cursor left geometry)
            op.store_fresh(None, "SOURCE_A", None)
            res, src = op.get_effective("SOURCE_A")
            # current is cleared when fresh=None, sticky should have it
            assert src in ("sticky", "last_valid", "current"), f"unexpected src={src}"

        def test_sticky_stage_match():
            op, SR = _make_mixin()
            r = SR(location=vec3(5,0,0), snap_type="EDGE")
            op.store_fresh(r, "STAGE_X", None)
            op.store_fresh(None, "STAGE_X", None)
            res, src = op.get_effective("STAGE_X")
            assert src in ("sticky","last_valid"), f"expected sticky/last_valid, got {src}"

        def test_sticky_stage_mismatch_no_carry():
            op, SR = _make_mixin()
            r = SR(location=vec3(5,0,0), snap_type="EDGE")
            op.store_fresh(r, "STAGE_X", None)
            op.advance_stage()  # clears sticky
            op.store_fresh(None, "STAGE_Y", None)
            # sticky is gone; last_valid might still be there
            res, src = op.get_effective("STAGE_Y")
            # sticky should NOT be used for different stage
            assert src != "sticky", "sticky from old stage should not bleed into new stage"

        def test_ray_not_stored_as_sticky():
            op, SR = _make_mixin()
            r = SR(location=vec3(3,0,0), snap_type="RAY")
            op.store_fresh(r, "STAGE_A", None)
            assert op._snap_sticky is None, "RAY hit should NOT become sticky"

        def test_confirm_clears_sticky():
            op, SR = _make_mixin()
            r = SR(location=vec3(1,0,0), snap_type="VERTEX")
            op.store_fresh(r, "STAGE_A", None)
            op.confirm_snap()
            assert op._snap_sticky is None, "confirm_snap should clear sticky"
            assert op._snap_last_valid is not None, "last_valid survives confirm"

        def test_last_valid_type_label():
            op, SR = _make_mixin()
            r = SR(location=vec3(), snap_type="MIDPOINT")
            op.store_fresh(r, "S", None)
            label = op.last_valid_type_label()
            assert "邊中點" in label, f"expected zh label for MIDPOINT, got '{label}'"

        self.run(test_fresh_wins,                  "fresh hit wins over all")
        self.run(test_current_fallback,            "current/sticky fallback when fresh=None")
        self.run(test_sticky_stage_match,          "sticky returned for matching stage")
        self.run(test_sticky_stage_mismatch_no_carry, "sticky does NOT bleed across stages")
        self.run(test_ray_not_stored_as_sticky,    "RAY hit not stored as sticky")
        self.run(test_confirm_clears_sticky,       "confirm_snap clears sticky, keeps last_valid")
        self.run(test_last_valid_type_label,       "last_valid_type_label zh string")


class TestMathUtils(TestSuite):
    """Tests for core math_utils functions used in alignment."""

    def __init__(self):
        super().__init__("math_utils — plane basis & rotation")

    def run_all(self):

        def test_rotation_between_vectors_identity():
            from smart_align_pro_v7_5.core.math_utils import rotation_between_vectors
            v = vec3(1, 0, 0)
            q = rotation_between_vectors(v, v)
            # Identity rotation → angle ≈ 0
            angle = 2 * math.acos(min(1.0, abs(q.w)))
            assert angle < 1e-4, f"identity rotation angle should be 0, got {angle}"

        def test_rotation_between_vectors_90():
            from smart_align_pro_v7_5.core.math_utils import rotation_between_vectors
            x = vec3(1, 0, 0); y = vec3(0, 1, 0)
            q = rotation_between_vectors(x, y)
            rotated = q @ x
            assert_vec_close(rotated, y, tol=1e-4, msg="90° rotation")

        def test_get_plane_basis_orthogonal():
            from smart_align_pro_v7_5.core.math_utils import get_plane_basis
            a = vec3(0, 0, 0); b = vec3(1, 0, 0); c = vec3(0, 1, 0)
            bx, by, bn = get_plane_basis(a, b, c)
            dot_xy = bx.dot(by); dot_xn = bx.dot(bn); dot_yn = by.dot(bn)
            assert abs(dot_xy) < 1e-4, f"basis X·Y should be 0, got {dot_xy}"
            assert abs(dot_xn) < 1e-4, f"basis X·N should be 0, got {dot_xn}"
            assert abs(dot_yn) < 1e-4, f"basis Y·N should be 0, got {dot_yn}"

        def test_matrix_from_basis_invertible():
            from smart_align_pro_v7_5.core.math_utils import get_plane_basis, matrix_from_basis
            a = vec3(1, 2, 3); b = vec3(4, 2, 3); c = vec3(1, 5, 3)
            bx, by, bn = get_plane_basis(a, b, c)
            m = matrix_from_basis(a, bx, by, bn)
            mi = m.inverted()
            prod = m @ mi
            for i in range(4):
                for j in range(4):
                    expected = 1.0 if i == j else 0.0
                    assert abs(prod[i][j] - expected) < 1e-4, f"M@M^-1 [{i}][{j}] = {prod[i][j]}"

        self.run(test_rotation_between_vectors_identity, "rotation_between_vectors identity")
        self.run(test_rotation_between_vectors_90,       "rotation_between_vectors 90°")
        self.run(test_get_plane_basis_orthogonal,        "get_plane_basis orthogonal")
        self.run(test_matrix_from_basis_invertible,      "matrix_from_basis invertible")


class TestKeymap(TestSuite):
    """Tests for keymap registration logic."""

    def __init__(self):
        super().__init__("keymap_manager — config validation")

    def run_all(self):

        def test_keymap_config_complete():
            from smart_align_pro_v7_5.keymap_manager import KEYMAP_CONFIG
            required_keys = {"alt_a", "alt_q", "alt_ctrl_z"}
            for k in required_keys:
                assert k in KEYMAP_CONFIG, f"KEYMAP_CONFIG missing key: {k}"

        def test_alt_a_targets_cad_selector():
            from smart_align_pro_v7_5.keymap_manager import KEYMAP_CONFIG
            cfg = KEYMAP_CONFIG["alt_a"]
            assert cfg["key"] == "A", f"alt_a key should be A, got {cfg['key']}"
            assert "cad_directional_selector" in cfg["operator"], \
                f"alt_a should target cad_directional_selector, got {cfg['operator']}"

        def test_all_configs_have_required_fields():
            from smart_align_pro_v7_5.keymap_manager import KEYMAP_CONFIG
            for name, cfg in KEYMAP_CONFIG.items():
                assert "operator" in cfg, f"{name}: missing 'operator'"
                assert "key" in cfg,      f"{name}: missing 'key'"

        self.run(test_keymap_config_complete,      "required keymap keys present")
        self.run(test_alt_a_targets_cad_selector,  "Alt+A → cad_directional_selector")
        self.run(test_all_configs_have_required_fields, "all configs have operator+key")


class TestStickyChainIntegration(TestSuite):
    """
    Integration-level tests: verifies the 4-level chain behaves correctly
    across a simulated sequence of MOUSEMOVE events including cursor-leave.
    """

    def __init__(self):
        super().__init__("sticky chain — integration (simulated MOUSEMOVE sequence)")

    def run_all(self):

        def _run_sequence(events):
            """
            events: list of (snap_type_or_None, stage) tuples simulating MOUSEMOVE
            Returns list of (result, src) pairs.
            """
            from smart_align_pro_v7_5.core.snap_solver_core import SnapSolverMixin, SnapResult
            class _Op(SnapSolverMixin): pass
            op = _Op(); op.init_snap_state()
            results = []
            for snap_type, stage in events:
                if snap_type is not None:
                    r = SnapResult(location=vec3(1,0,0), snap_type=snap_type)
                    op.store_fresh(r, stage, None)
                else:
                    op.store_fresh(None, stage, None)
                results.append(op.get_effective(stage))
            return results

        def test_vertex_then_leave_then_confirm():
            """Simulate: hover VERTEX → leave geometry → still get sticky → confirm."""
            evts = [
                ("VERTEX", "TARGET_B"),  # live snap
                ("VERTEX", "TARGET_B"),  # still live
                (None,     "TARGET_B"),  # cursor leaves
                (None,     "TARGET_B"),  # still away
            ]
            results = _run_sequence(evts)
            # First two should be fresh/current
            assert results[0][1] in ("fresh","current","sticky"), f"ev0: {results[0][1]}"
            # After leaving, sticky or last_valid must supply the result
            assert results[2][0] is not None, "After leaving geometry, sticky should still provide result"
            assert results[2][1] in ("sticky","last_valid"), f"ev2 src={results[2][1]}"
            assert results[3][0] is not None, "Still sticky on ev3"

        def test_ray_hit_never_sticky():
            """RAY hits should NOT be stored as sticky."""
            evts = [
                ("RAY", "SOURCE_A"),
                (None,  "SOURCE_A"),
            ]
            results = _run_sequence(evts)
            # After RAY then leave, nothing sticky
            assert results[1][0] is None or results[1][1] not in ("sticky",), \
                f"RAY should not become sticky, got src={results[1][1]}"

        def test_stage_advance_clears_sticky():
            """After advance_stage(), old sticky must not bleed into new stage."""
            from smart_align_pro_v7_5.core.snap_solver_core import SnapSolverMixin, SnapResult
            class _Op(SnapSolverMixin): pass
            op = _Op(); op.init_snap_state()
            # Store sticky in stage A
            r = SnapResult(location=vec3(1,0,0), snap_type="VERTEX")
            op.store_fresh(r, "STAGE_A", None)
            op.advance_stage()
            # Now on stage B with no fresh hit
            op.store_fresh(None, "STAGE_B", None)
            res, src = op.get_effective("STAGE_B")
            assert src != "sticky", f"Old sticky from STAGE_A must not bleed to STAGE_B, got src={src}"

        def test_last_valid_survives_stage_advance():
            """last_valid persists even after advance_stage (it is the absolute last resort)."""
            from smart_align_pro_v7_5.core.snap_solver_core import SnapSolverMixin, SnapResult
            class _Op(SnapSolverMixin): pass
            op = _Op(); op.init_snap_state()
            r = SnapResult(location=vec3(7,0,0), snap_type="ORIGIN")
            op.store_fresh(r, "STAGE_A", None)
            op.advance_stage()
            assert op._snap_last_valid is not None, "last_valid should survive advance_stage"

        def test_face_midpoint_origin_all_sticky():
            """All non-RAY snap types must become sticky."""
            from smart_align_pro_v7_5.core.snap_solver_core import SnapSolverMixin, SnapResult
            for stype in ["VERTEX","MIDPOINT","EDGE","FACE_CENTER","FACE","ORIGIN","CENTER"]:
                class _Op(SnapSolverMixin): pass
                op = _Op(); op.init_snap_state()
                r = SnapResult(location=vec3(1,0,0), snap_type=stype)
                op.store_fresh(r, "S", None)
                assert op._snap_sticky is not None, f"{stype} should create sticky"

        self.run(test_vertex_then_leave_then_confirm, "VERTEX → leave → sticky confirm")
        self.run(test_ray_hit_never_sticky,           "RAY hit → no sticky")
        self.run(test_stage_advance_clears_sticky,    "advance_stage clears sticky (not last_valid)")
        self.run(test_last_valid_survives_stage_advance, "last_valid survives stage advance")
        self.run(test_face_midpoint_origin_all_sticky, "all non-RAY types → sticky")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

_ALL_SUITES = [
    TestSnapSolverCore,
    TestSelectorStateMachine,
    TestSnapSolverMixin,
    TestMathUtils,
    TestKeymap,
    TestStickyChainIntegration,
]


def run_all(verbose=True) -> bool:
    """
    Run all test suites. Returns True if every test passed.
    Prints a summary report to stdout.
    """
    print("\n" + "="*60)
    print("  Smart Align Pro v7.5.5 — Regression Test Suite")
    print("="*60)

    all_passed  = True
    total_pass  = 0
    total_fail  = 0

    for SuiteClass in _ALL_SUITES:
        suite = SuiteClass()
        suite.run_all()
        if verbose:
            print(suite.summary())
        pass_count = sum(1 for r in suite.results if r.passed)
        fail_count = len(suite.results) - pass_count
        total_pass += pass_count
        total_fail += fail_count
        if fail_count > 0:
            all_passed = False

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_pass} passed, {total_fail} failed")
    status = "✓ ALL TESTS PASSED" if all_passed else "✗ SOME TESTS FAILED"
    print(f"  {status}")
    print("="*60 + "\n")
    return all_passed


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point (blender --background --python this_file.py)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    # Add addon parent directory to path so imports work
    _here   = os.path.dirname(os.path.abspath(__file__))
    _addon  = os.path.dirname(_here)            # smart_align_pro_v7_5/
    _parent = os.path.dirname(_addon)           # parent of addon folder
    for p in (_parent, _addon):
        if p not in sys.path:
            sys.path.insert(0, p)

    ok = run_all()
    sys.exit(0 if ok else 1)
