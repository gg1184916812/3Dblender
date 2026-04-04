"""
Smart Align Pro v7.5.5 - Blender Real-World Test Report Generator
TASK 9 from the Final Upgrade Plan.

This script:
  1. Runs the automated Python test suite (test_alignment_cases.py)
  2. Reads a BLENDER_REALWORLD_TEST_CASES.json if present (manual test results)
  3. Merges both into BLENDER_REALWORLD_TEST_REPORT.md

Run inside Blender's Python console:
    exec(open("/path/to/tests/generate_test_report.py").read())

Or from the OS shell:
    python3 generate_test_report.py [--output /path/to/output.md]
"""

import sys
import os
import json
import datetime
import platform
import importlib
import subprocess

# ---------------------------------------------------------------------------
# 10 standard real-world manual test cases (TASK 9 content)
# ---------------------------------------------------------------------------

MANUAL_TEST_CASES = [
    {
        "id":       "RT-01",
        "name":     "Vertex → Vertex (2-point align)",
        "tool":     "two_point_align",
        "snap_type":"VERTEX",
        "scenario": "Select source cube, active = target cube. Alt+1. Click vertex on source, click vertex on target.",
        "expected": "Source cube moved so picked vertices coincide. Axes aligned.",
        "status":   "PENDING",   # PASS / FAIL / SKIP / PENDING
        "notes":    "",
    },
    {
        "id":       "RT-02",
        "name":     "Edge Midpoint → Edge Midpoint (2-point align)",
        "tool":     "two_point_align",
        "snap_type":"MIDPOINT",
        "scenario": "Same setup. Press 2 for edge-midpoint mode. Pick two edge midpoints each side.",
        "expected": "Midpoints aligned. Source rotated to match edge direction.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-03",
        "name":     "Face Center → Face Center (2-point align)",
        "tool":     "two_point_align",
        "snap_type":"FACE",
        "scenario": "Press 3 for face mode. Pick face centers on source and target.",
        "expected": "Face centers aligned.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-04",
        "name":     "Leave object then confirm (sticky confirm)",
        "tool":     "two_point_align / three_point_modal",
        "snap_type":"VERTEX",
        "scenario": "In TARGET_B stage: hover over vertex until LIVE SNAP shown. Move cursor off object. Verify STICKY SNAP label. Click.",
        "expected": "Last valid vertex confirmed. Alignment completes correctly.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-05",
        "name":     "Alt+A CAD selector opens and executes",
        "tool":     "cad_directional_selector",
        "snap_type":"—",
        "scenario": "In Object Mode, 3D View. Press Alt+A. Drag RIGHT. Release A.",
        "expected": "CAD snap modal launches. Selector HUD shows priority legend.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-06",
        "name":     "CAD Snap FROM→TO alignment",
        "tool":     "cad_snap_modal",
        "snap_type":"VERTEX",
        "scenario": "Start cad_snap_modal. Click vertex on source as FROM. Move cursor to target vertex. Verify LIVE SNAP badge. Click TO. Enter.",
        "expected": "Source moved so FROM aligns to TO. Status shows CONFIRMED.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-07",
        "name":     "Three-point plane preview visible",
        "tool":     "three_point_modal",
        "snap_type":"VERTEX",
        "scenario": "Alt+2. Pick 3 source points. Pick 2 target points. Move cursor for 3rd target point.",
        "expected": "Ghost triangle appears showing alignment plane. Normal arrow visible.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-08",
        "name":     "Multi-object batch align",
        "tool":     "smart_batch_align",
        "snap_type":"—",
        "scenario": "Select 3+ objects (one active). Run smart_batch_align.",
        "expected": "All non-active objects aligned to active using strategy.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-09",
        "name":     "Snap state HUD consistency",
        "tool":     "two_point_align",
        "snap_type":"VERTEX",
        "scenario": "During TARGET_B: confirm HUD shows LIVE (green), then STICKY (orange) after leaving, then CONFIRMED (bright green) after click.",
        "expected": "Three distinct colors. Labels match states. Never blank.",
        "status":   "PENDING",
        "notes":    "",
    },
    {
        "id":       "RT-10",
        "name":     "Alt+A blocked outside OBJECT mode",
        "tool":     "cad_directional_selector",
        "snap_type":"—",
        "scenario": "Switch to Edit Mode. Press Alt+A.",
        "expected": "Nothing happens. No operator error. Selector does NOT open.",
        "status":   "PENDING",
        "notes":    "",
    },
]


# ---------------------------------------------------------------------------
# Automated test runner
# ---------------------------------------------------------------------------

def _run_automated_tests():
    """Run test_alignment_cases.py and return (total, passed, results_text)."""
    here = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(here, "test_alignment_cases.py")
    if not os.path.exists(test_file):
        return 0, 0, "test_alignment_cases.py not found"

    # Try running as subprocess so we capture stdout cleanly
    try:
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout + result.stderr
        # Parse totals
        total = passed = 0
        for line in output.splitlines():
            if "TOTAL:" in line and "passed" in line:
                parts = line.strip().split()
                for i, p in enumerate(parts):
                    if p == "passed," and i > 0:
                        passed = int(parts[i-1])
                    if p == "failed" and i > 0:
                        failed = int(parts[i-1])
                        total  = passed + failed
        return total, passed, output
    except Exception as e:
        return 0, 0, f"Error running tests: {e}"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(output_path: str = None) -> str:
    """Generate and return the Markdown report string."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # System info
    py_ver = platform.python_version()
    os_name = platform.system()

    # Detect Blender version if available
    try:
        import bpy
        bl_ver = ".".join(str(x) for x in bpy.app.version)
    except ImportError:
        bl_ver = "N/A (running outside Blender)"

    # GPU info
    try:
        import bpy
        gpu_info = bpy.context.preferences.system.gpu_backend
    except Exception:
        gpu_info = "N/A"

    # Run automated tests
    auto_total, auto_passed, auto_output = _run_automated_tests()

    # Load manual results from JSON if present
    manual_cases = list(MANUAL_TEST_CASES)
    here = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(here, "BLENDER_REALWORLD_TEST_CASES.json")
    if os.path.exists(json_path):
        try:
            with open(json_path) as f:
                manual_cases = json.load(f)
            print(f"Loaded manual test results from {json_path}")
        except Exception as e:
            print(f"Warning: could not load {json_path}: {e}")

    # Count manual results
    manual_pass  = sum(1 for c in manual_cases if c.get("status") == "PASS")
    manual_fail  = sum(1 for c in manual_cases if c.get("status") == "FAIL")
    manual_skip  = sum(1 for c in manual_cases if c.get("status") == "SKIP")
    manual_pend  = sum(1 for c in manual_cases if c.get("status") == "PENDING")
    manual_total = len(manual_cases)

    # Build markdown
    lines = []
    lines += [
        "# Smart Align Pro v7.5.5 — Real-World Test Report",
        "",
        f"**Generated:** {now}  ",
        f"**Blender:**   {bl_ver}  ",
        f"**Python:**    {py_ver}  ",
        f"**OS:**        {os_name}  ",
        f"**GPU Backend:**{gpu_info}  ",
        "",
        "---",
        "",
        "## 1. Automated Python Test Suite",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total cases | {auto_total} |",
        f"| Passed      | {auto_passed} |",
        f"| Failed      | {auto_total - auto_passed} |",
        f"| Pass rate   | {100*auto_passed//auto_total if auto_total else 0}% |",
        "",
        "<details><summary>Test output</summary>",
        "",
        "```",
        auto_output.strip(),
        "```",
        "",
        "</details>",
        "",
        "---",
        "",
        "## 2. Blender Real-World Manual Test Cases",
        "",
        f"**Summary:** {manual_pass} PASS / {manual_fail} FAIL / {manual_skip} SKIP / {manual_pend} PENDING  ",
        "",
        "| ID | Test | Tool | Snap | Status | Notes |",
        "|----|------|------|------|--------|-------|",
    ]

    STATUS_EMOJI = {
        "PASS":    "✅ PASS",
        "FAIL":    "❌ FAIL",
        "SKIP":    "⏭️ SKIP",
        "PENDING": "⏳ PENDING",
    }

    for c in manual_cases:
        status_str = STATUS_EMOJI.get(c.get("status", "PENDING"), c.get("status","?"))
        notes = (c.get("notes") or "").replace("|", "\\|")
        lines.append(
            f"| {c['id']} | {c['name']} | `{c['tool']}` | {c['snap_type']} | {status_str} | {notes} |"
        )

    lines += [
        "",
        "---",
        "",
        "## 3. Detailed Manual Test Scenarios",
        "",
    ]
    for c in manual_cases:
        status_str = STATUS_EMOJI.get(c.get("status","PENDING"), c.get("status","?"))
        lines += [
            f"### {c['id']} — {c['name']}",
            "",
            f"**Status:** {status_str}  ",
            f"**Tool:** `{c['tool']}`  ",
            f"**Snap type:** {c['snap_type']}  ",
            "",
            f"**Scenario:**  ",
            f"> {c['scenario']}",
            "",
            f"**Expected:**  ",
            f"> {c['expected']}",
            "",
        ]
        if c.get("notes"):
            lines += [f"**Notes:** {c['notes']}", ""]
        lines.append("---")
        lines.append("")

    lines += [
        "## 4. Known Limitations",
        "",
        "- Snap result depends on Blender's `ray_cast` accuracy at current depsgraph state.",
        "- Alt+A is restricted to `OBJECT` mode and `VIEW_3D` space only.",
        "- Sticky confirm persistence is per-stage; crossing stage boundaries resets sticky.",
        "- Triangle plane preview is screen-space only (no 3D grid).",
        "",
        "---",
        "",
        "## 5. Instructions for Updating Manual Results",
        "",
        "Copy `tests/BLENDER_REALWORLD_TEST_CASES.json.template` to",
        "`tests/BLENDER_REALWORLD_TEST_CASES.json`, fill in each `status` field",
        "(`PASS` / `FAIL` / `SKIP`) and `notes`, then re-run this script.",
        "",
        "```bash",
        "python3 tests/generate_test_report.py",
        "```",
        "",
        "*Auto-generated by Smart Align Pro v7.5.5 test infrastructure.*",
    ]

    report = "\n".join(lines)

    # Write to file
    if output_path is None:
        output_path = os.path.join(here, "..", "BLENDER_REALWORLD_TEST_REPORT.md")
    output_path = os.path.abspath(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[Report] Written to: {output_path}")

    # Also write the JSON template so users can fill in results
    template_path = os.path.join(here, "BLENDER_REALWORLD_TEST_CASES.json.template")
    with open(template_path, "w", encoding="utf-8") as f:
        json.dump(MANUAL_TEST_CASES, f, ensure_ascii=False, indent=2)
    print(f"[Template] Written to: {template_path}")

    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate Smart Align Pro test report")
    ap.add_argument("--output", default=None, help="Output .md path")
    args = ap.parse_args()
    report = generate_report(output_path=args.output)
    # Print summary
    for line in report.splitlines():
        if "PASS" in line or "FAIL" in line or "Summary" in line or "Generated" in line:
            print(line)
