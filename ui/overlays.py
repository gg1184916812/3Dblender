"""
Smart Align Pro - Overlay 系統
v7.5.5 — sticky visual, snap influence radius circle (item 5), triangle plane preview (item 4)
"""

import bpy
import blf
from mathutils import Vector
from bpy_extras import view3d_utils
from typing import Optional, List
import math

# Use modern GPU API (Blender 3.x+); fall back to bgl for older
try:
    import gpu
    from gpu_extras.batch import batch_for_shader
    _GPU_AVAIL = True
except ImportError:
    _GPU_AVAIL = False


# ─── shader helper ────────────────────────────────────────────────────────────

def _get_shader():
    try:
        return gpu.shader.from_builtin("UNIFORM_COLOR")
    except Exception:
        try:
            import bgl
            return bgl.shader.from_builtin("UNIFORM_COLOR")
        except Exception:
            return None


def _draw_line_strip(shader, points, color):
    if not points or shader is None:
        return
    try:
        batch = batch_for_shader(shader, "LINE_STRIP", {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    except Exception:
        pass


def _draw_lines(shader, points, color):
    if not points or shader is None:
        return
    try:
        batch = batch_for_shader(shader, "LINES", {"pos": points})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
    except Exception:
        pass


# ─── OverlayRenderer ──────────────────────────────────────────────────────────

class OverlayRenderer:

    def __init__(self):
        self._shader = None

    @property
    def shader(self):
        if self._shader is None:
            self._shader = _get_shader()
        return self._shader

    def _screen(self, location):
        try:
            region = bpy.context.region
            rv3d   = bpy.context.space_data.region_3d
            return view3d_utils.location_3d_to_region_2d(region, rv3d, location)
        except Exception:
            return None

    # ── point types ───────────────────────────────────────────

    def draw_point(self, location, color, size=8.0, point_type="VERTEX", dashed=False):
        alpha = (*color[:3], color[3] * (0.65 if dashed else 1.0))
        if point_type == "VERTEX":
            self._circle(location, alpha, size, dashed)
        elif point_type in ("MIDPOINT", "EDGE_MID"):
            self._triangle(location, alpha, size, dashed)
        elif point_type == "EDGE":
            self._hline(location, alpha, size)
        elif point_type in ("FACE_CENTER", "FACE"):
            self._square(location, alpha, size, dashed)
        elif point_type in ("ORIGIN", "CENTER", "OBJECT"):
            self._cross(location, alpha, size)
        else:
            self._circle(location, alpha, size, dashed)

    def _circle(self, location, color, size, dashed=False):
        sp = self._screen(location)
        if not sp: return
        segs = 16; pts = []
        for i in range(segs + 1):
            if dashed and i % 2 == 1: continue
            a = 2 * math.pi * i / segs
            pts.append((sp.x + size * math.cos(a), sp.y + size * math.sin(a)))
        _draw_line_strip(self.shader, pts, color)

    def _triangle(self, location, color, size, dashed=False):
        sp = self._screen(location)
        if not sp: return
        pts = [
            (sp.x, sp.y + size),
            (sp.x - size * 0.866, sp.y - size * 0.5),
            (sp.x + size * 0.866, sp.y - size * 0.5),
            (sp.x, sp.y + size),
        ]
        if dashed: pts = pts[::2] + [pts[0]]
        _draw_line_strip(self.shader, pts, color)

    def _hline(self, location, color, size):
        sp = self._screen(location)
        if not sp: return
        _draw_lines(self.shader, [(sp.x-size,sp.y),(sp.x+size,sp.y)], color)

    def _square(self, location, color, size, dashed=False):
        sp = self._screen(location)
        if not sp: return
        pts = [(sp.x-size,sp.y-size),(sp.x+size,sp.y-size),(sp.x+size,sp.y+size),(sp.x-size,sp.y+size),(sp.x-size,sp.y-size)]
        if dashed: pts = pts[::2]
        _draw_line_strip(self.shader, pts, color)

    def _cross(self, location, color, size):
        sp = self._screen(location)
        if not sp: return
        _draw_lines(self.shader, [(sp.x-size,sp.y),(sp.x+size,sp.y),(sp.x,sp.y-size),(sp.x,sp.y+size)], color)

    # ── snap influence radius circle (Item 5) ─────────────────

    def draw_snap_radius_circle(self, location, color, radius_px, dashed=False):
        """Draw a screen-space circle showing snap influence radius."""
        sp = self._screen(location)
        if not sp or radius_px <= 0: return
        segs = 32; pts = []
        for i in range(segs + 1):
            if dashed and i % 2 == 1: continue
            a = 2 * math.pi * i / segs
            pts.append((sp.x + radius_px * math.cos(a), sp.y + radius_px * math.sin(a)))
        _draw_line_strip(self.shader, pts, (*color[:3], color[3] * 0.4))

    # ── connection line ────────────────────────────────────────

    def draw_connection_line(self, from_loc, to_loc, color, dashed=False):
        f = self._screen(from_loc)
        t = self._screen(to_loc)
        if f and t:
            if dashed:
                # manual dashed: draw short segments
                pts = []
                steps = 16
                for i in range(steps):
                    if i % 2 == 0:
                        pts.extend([
                            (f.x + (t.x-f.x)*i/steps, f.y + (t.y-f.y)*i/steps),
                            (f.x + (t.x-f.x)*(i+1)/steps, f.y + (t.y-f.y)*(i+1)/steps),
                        ])
                _draw_lines(self.shader, pts, color)
            else:
                _draw_lines(self.shader, [(f.x,f.y),(t.x,t.y)], color)

    # ── triangle plane preview (Item 4) ──────────────────────

    def draw_triangle_plane(self, points_3d, color, filled_alpha=0.08):
        """Draw a ghost triangle showing the alignment plane for 3-point align."""
        if len(points_3d) < 3: return
        pts_2d = [self._screen(p) for p in points_3d[:3]]
        if any(p is None for p in pts_2d): return
        a, b, c = pts_2d

        # Outline
        outline = [(a.x,a.y),(b.x,b.y),(c.x,c.y),(a.x,a.y)]
        _draw_line_strip(self.shader, outline, color)

        # Filled (simple triangle fan using LINES approximation)
        fill_color = (*color[:3], filled_alpha)
        center = ((a.x+b.x+c.x)/3, (a.y+b.y+c.y)/3)
        fan_pts = []
        for v in [a, b, c, a]:
            fan_pts.extend([(center[0],center[1]),(v.x,v.y)])
        try:
            _draw_lines(self.shader, fan_pts, fill_color)
        except Exception:
            pass

    # ── label ─────────────────────────────────────────────────

    def draw_label(self, location, text, color, offset_x=14, offset_y=14):
        try:
            sp = self._screen(location)
            if sp:
                blf.position(0, sp.x + offset_x, sp.y + offset_y, 0)
                blf.size(0, 11)
                blf.color(0, *color)
                blf.draw(0, text)
        except Exception:
            pass

    def draw_point_index(self, location, text, color):
        self.draw_label(location, text, color, offset_x=10, offset_y=10)


# ─── SmartAlignOverlay ────────────────────────────────────────────────────────

class SmartAlignOverlay:
    """Smart Align Pro Overlay (v7.5.5 — snap radius + triangle plane preview)"""

    COLORS = {
        "source":       (0.2,  0.85, 0.2,  1.0),
        "target":       (0.85, 0.2,  0.2,  1.0),
        "hover":        (0.85, 0.85, 0.2,  1.0),
        "hover_sticky": (1.0,  0.65, 0.1,  0.9),
        "connection":   (0.5,  0.5,  0.5,  0.7),
        "radius_live":  (0.2,  0.9,  0.2,  0.5),
        "radius_sticky":(1.0,  0.65, 0.1,  0.5),
        "plane_preview":(0.3,  0.6,  1.0,  0.8),
    }

    def __init__(self):
        self.renderer = OverlayRenderer()
        self.active   = False
        self._handle  = None

        self.source_points: List[Vector] = []
        self.target_points: List[Vector] = []
        self.hover_candidate = None
        self.mode = "FROM"

        # Sticky state
        self.sticky_active:    bool  = False
        self.sticky_label:     str   = ""
        self.sticky_candidate_type: str = ""

        # Item 5: snap radius
        self.snap_radius_px:   float = 0.0
        self.snap_state:       str   = "IDLE"
        self.snap_state_color: tuple = (0.5,0.5,0.5,0.8)

        # Item 4: triangle plane preview
        self.plane_preview_points: List[Vector] = []

    def register(self):
        if not self.active:
            self._handle = bpy.types.SpaceView3D.draw_handler_add(
                self._draw, (), "WINDOW", "POST_VIEW"
            )
            self.active = True

    def unregister(self):
        if self.active and self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, "WINDOW")
            self.active = False
            self._handle = None

    def update_source_points(self, points):
        self.source_points = list(points)

    def update_target_points(self, points):
        self.target_points = list(points)

    def update_hover_candidate(self, candidate,
                                sticky_active=False, sticky_label="", sticky_type="",
                                snap_radius_px=0.0, snap_state="IDLE", snap_state_color=None):
        self.hover_candidate    = candidate
        self.sticky_active      = sticky_active
        self.sticky_label       = sticky_label
        self.sticky_candidate_type = sticky_type or (getattr(candidate, "snap_type", "") if candidate else "")
        self.snap_radius_px     = snap_radius_px
        self.snap_state         = snap_state
        self.snap_state_color   = snap_state_color or (0.5,0.5,0.5,0.8)

    def clear_hover_candidate(self):
        self.hover_candidate   = None
        self.sticky_active     = False
        self.sticky_label      = ""
        self.snap_radius_px    = 0.0
        self.snap_state        = "IDLE"
        self.plane_preview_points = []

    def update_mode(self, mode):
        self.mode = mode

    def _draw(self):
        if not self.active: return
        r = self.renderer

        # Source points
        for i, pt in enumerate(self.source_points):
            r.draw_point(pt, self.COLORS["source"], size=8.0, point_type="VERTEX")
            r.draw_point_index(pt, f"S{i+1}", self.COLORS["source"])

        # Target points
        for i, pt in enumerate(self.target_points):
            r.draw_point(pt, self.COLORS["target"], size=8.0, point_type="VERTEX")
            r.draw_point_index(pt, f"T{i+1}", self.COLORS["target"])

        # Hover candidate
        if self.hover_candidate:
            loc       = self.hover_candidate.location
            dashed    = self.sticky_active
            color     = self.COLORS["hover_sticky"] if dashed else self.COLORS["hover"]
            snap_type = getattr(self.hover_candidate, "snap_type", "VERTEX") or "VERTEX"
            r.draw_point(loc, color, size=11.0, point_type=snap_type, dashed=dashed)

            # Sticky label
            if dashed and self.sticky_label:
                r.draw_label(loc, self.sticky_label, color)

            # Item 5: snap influence radius circle
            if self.snap_radius_px > 0:
                rc = self.COLORS["radius_sticky"] if dashed else self.COLORS["radius_live"]
                r.draw_snap_radius_circle(loc, rc, self.snap_radius_px, dashed=dashed)

        # Connection line
        if self.source_points and self.target_points:
            r.draw_connection_line(self.source_points[-1], self.target_points[-1],
                                   self.COLORS["connection"], dashed=True)

        # Item 4: triangle plane preview for 3-point align
        if len(self.plane_preview_points) >= 3:
            r.draw_triangle_plane(self.plane_preview_points[:3], self.COLORS["plane_preview"])

    def _draw_label(self, location, text, color):
        self.renderer.draw_label(location, text, color)


# Global instance
overlay = SmartAlignOverlay()
