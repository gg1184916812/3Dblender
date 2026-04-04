# Smart Align Pro v7.5.5 — Real-World Test Report

**Generated:** 2026-04-04 06:44  
**Blender:**   N/A (running outside Blender)  
**Python:**    3.12.3  
**OS:**        Linux  
**GPU Backend:**N/A  

---

## 1. Automated Python Test Suite

| Metric | Value |
|--------|-------|
| Total cases | 32 |
| Passed      | 32 |
| Failed      | 0 |
| Pass rate   | 100% |

<details><summary>Test output</summary>

```
============================================================
  Smart Align Pro v7.5.5 — Regression Test Suite
============================================================

============================================================
  snap_solver_core — unit tests  (6/6 passed)
============================================================
  [PASS] SnapResult.is_non_ray (0.0ms)
  [PASS] SnapResult dict round-trip (0.0ms)
  [PASS] filter_by_snap_type ALL/VERTEX/EDGE (0.0ms)
  [PASS] filter_by_snap_type MIDPOINT expanded (0.0ms)
  [PASS] snap/sticky radii positive & sticky≥snap (0.0ms)
  [PASS] score: VERTEX > FACE at same distance (0.0ms)
============================================================

============================================================
  selector_state_machine — unit tests  (7/7 passed)
============================================================
  [PASS] initial state = IDLE (0.0ms)
  [PASS] LIVE_SNAP transition (0.0ms)
  [PASS] STICKY_SNAP transition (0.0ms)
  [PASS] confirm → advance → IDLE (0.0ms)
  [PASS] cancel → IDLE (0.0ms)
  [PASS] sticky → CONFIRM_READY upgrade (0.0ms)
  [PASS] changed flag tracking (0.0ms)
============================================================

============================================================
  SnapSolverMixin — 4-level chain unit tests  (7/7 passed)
============================================================
  [PASS] fresh hit wins over all (0.0ms)
  [PASS] current/sticky fallback when fresh=None (0.0ms)
  [PASS] sticky returned for matching stage (0.0ms)
  [PASS] sticky does NOT bleed across stages (0.0ms)
  [PASS] RAY hit not stored as sticky (0.0ms)
  [PASS] confirm_snap clears sticky, keeps last_valid (0.0ms)
  [PASS] last_valid_type_label zh string (0.0ms)
============================================================

============================================================
  math_utils — plane basis & rotation  (4/4 passed)
============================================================
  [PASS] rotation_between_vectors identity (0.0ms)
  [PASS] rotation_between_vectors 90° (0.0ms)
  [PASS] get_plane_basis orthogonal (0.0ms)
  [PASS] matrix_from_basis invertible (2.0ms)
============================================================

============================================================
  keymap_manager — config validation  (3/3 passed)
============================================================
  [PASS] required keymap keys present (0.0ms)
  [PASS] Alt+A → cad_directional_selector (0.0ms)
  [PASS] all configs have operator+key (0.0ms)
============================================================

============================================================
  sticky chain — integration (simulated MOUSEMOVE sequence)  (5/5 passed)
============================================================
  [PASS] VERTEX → leave → sticky confirm (0.0ms)
  [PASS] RAY hit → no sticky (0.0ms)
  [PASS] advance_stage clears sticky (not last_valid) (0.0ms)
  [PASS] last_valid survives stage advance (0.0ms)
  [PASS] all non-RAY types → sticky (0.1ms)
============================================================

============================================================
  TOTAL: 32 passed, 0 failed
  ✓ ALL TESTS PASSED
============================================================
```

</details>

---

## 2. Blender Real-World Manual Test Cases

**Summary:** 0 PASS / 0 FAIL / 0 SKIP / 10 PENDING  

| ID | Test | Tool | Snap | Status | Notes |
|----|------|------|------|--------|-------|
| RT-01 | Vertex → Vertex (2-point align) | `two_point_align` | VERTEX | ⏳ PENDING |  |
| RT-02 | Edge Midpoint → Edge Midpoint (2-point align) | `two_point_align` | MIDPOINT | ⏳ PENDING |  |
| RT-03 | Face Center → Face Center (2-point align) | `two_point_align` | FACE | ⏳ PENDING |  |
| RT-04 | Leave object then confirm (sticky confirm) | `two_point_align / three_point_modal` | VERTEX | ⏳ PENDING |  |
| RT-05 | Alt+A CAD selector opens and executes | `cad_directional_selector` | — | ⏳ PENDING |  |
| RT-06 | CAD Snap FROM→TO alignment | `cad_snap_modal` | VERTEX | ⏳ PENDING |  |
| RT-07 | Three-point plane preview visible | `three_point_modal` | VERTEX | ⏳ PENDING |  |
| RT-08 | Multi-object batch align | `smart_batch_align` | — | ⏳ PENDING |  |
| RT-09 | Snap state HUD consistency | `two_point_align` | VERTEX | ⏳ PENDING |  |
| RT-10 | Alt+A blocked outside OBJECT mode | `cad_directional_selector` | — | ⏳ PENDING |  |

---

## 3. Detailed Manual Test Scenarios

### RT-01 — Vertex → Vertex (2-point align)

**Status:** ⏳ PENDING  
**Tool:** `two_point_align`  
**Snap type:** VERTEX  

**Scenario:**  
> Select source cube, active = target cube. Alt+1. Click vertex on source, click vertex on target.

**Expected:**  
> Source cube moved so picked vertices coincide. Axes aligned.

---

### RT-02 — Edge Midpoint → Edge Midpoint (2-point align)

**Status:** ⏳ PENDING  
**Tool:** `two_point_align`  
**Snap type:** MIDPOINT  

**Scenario:**  
> Same setup. Press 2 for edge-midpoint mode. Pick two edge midpoints each side.

**Expected:**  
> Midpoints aligned. Source rotated to match edge direction.

---

### RT-03 — Face Center → Face Center (2-point align)

**Status:** ⏳ PENDING  
**Tool:** `two_point_align`  
**Snap type:** FACE  

**Scenario:**  
> Press 3 for face mode. Pick face centers on source and target.

**Expected:**  
> Face centers aligned.

---

### RT-04 — Leave object then confirm (sticky confirm)

**Status:** ⏳ PENDING  
**Tool:** `two_point_align / three_point_modal`  
**Snap type:** VERTEX  

**Scenario:**  
> In TARGET_B stage: hover over vertex until LIVE SNAP shown. Move cursor off object. Verify STICKY SNAP label. Click.

**Expected:**  
> Last valid vertex confirmed. Alignment completes correctly.

---

### RT-05 — Alt+A CAD selector opens and executes

**Status:** ⏳ PENDING  
**Tool:** `cad_directional_selector`  
**Snap type:** —  

**Scenario:**  
> In Object Mode, 3D View. Press Alt+A. Drag RIGHT. Release A.

**Expected:**  
> CAD snap modal launches. Selector HUD shows priority legend.

---

### RT-06 — CAD Snap FROM→TO alignment

**Status:** ⏳ PENDING  
**Tool:** `cad_snap_modal`  
**Snap type:** VERTEX  

**Scenario:**  
> Start cad_snap_modal. Click vertex on source as FROM. Move cursor to target vertex. Verify LIVE SNAP badge. Click TO. Enter.

**Expected:**  
> Source moved so FROM aligns to TO. Status shows CONFIRMED.

---

### RT-07 — Three-point plane preview visible

**Status:** ⏳ PENDING  
**Tool:** `three_point_modal`  
**Snap type:** VERTEX  

**Scenario:**  
> Alt+2. Pick 3 source points. Pick 2 target points. Move cursor for 3rd target point.

**Expected:**  
> Ghost triangle appears showing alignment plane. Normal arrow visible.

---

### RT-08 — Multi-object batch align

**Status:** ⏳ PENDING  
**Tool:** `smart_batch_align`  
**Snap type:** —  

**Scenario:**  
> Select 3+ objects (one active). Run smart_batch_align.

**Expected:**  
> All non-active objects aligned to active using strategy.

---

### RT-09 — Snap state HUD consistency

**Status:** ⏳ PENDING  
**Tool:** `two_point_align`  
**Snap type:** VERTEX  

**Scenario:**  
> During TARGET_B: confirm HUD shows LIVE (green), then STICKY (orange) after leaving, then CONFIRMED (bright green) after click.

**Expected:**  
> Three distinct colors. Labels match states. Never blank.

---

### RT-10 — Alt+A blocked outside OBJECT mode

**Status:** ⏳ PENDING  
**Tool:** `cad_directional_selector`  
**Snap type:** —  

**Scenario:**  
> Switch to Edit Mode. Press Alt+A.

**Expected:**  
> Nothing happens. No operator error. Selector does NOT open.

---

## 4. Known Limitations

- Snap result depends on Blender's `ray_cast` accuracy at current depsgraph state.
- Alt+A is restricted to `OBJECT` mode and `VIEW_3D` space only.
- Sticky confirm persistence is per-stage; crossing stage boundaries resets sticky.
- Triangle plane preview is screen-space only (no 3D grid).

---

## 5. Instructions for Updating Manual Results

Copy `tests/BLENDER_REALWORLD_TEST_CASES.json.template` to
`tests/BLENDER_REALWORLD_TEST_CASES.json`, fill in each `status` field
(`PASS` / `FAIL` / `SKIP`) and `notes`, then re-run this script.

```bash
python3 tests/generate_test_report.py
```

*Auto-generated by Smart Align Pro v7.5.5 test infrastructure.*