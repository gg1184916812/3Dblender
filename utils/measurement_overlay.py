"""
Smart Align Pro - CAD Measurement Overlay Engine
在 3D 視窗中即時顯示 XYZ 位移、距離、角度、模式與階段，
並繪製 CAD 風格的 XYZ tripod、距離線、角度弧與點位標記。
"""

from __future__ import annotations

import math
from typing import Any

import blf
import bpy
import gpu
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
from bpy.types import SpaceView3D


class MeasurementOverlayEngine:
    def __init__(self):
        self._handler_pixel = None
        self._handler_view = None
        self.active = False
        self.data: dict[str, Any] = {}
        self._font_id = 0
        self._shader = None

    def start(self, context, operator_name: str, source=None, target=None, mode_label: str = ''):
        self.stop(context)
        self.active = True
        source_loc = getattr(getattr(source, 'matrix_world', None), 'translation', None)
        target_loc = getattr(getattr(target, 'matrix_world', None), 'translation', None)
        self.data = {
            'operator_name': operator_name,
            'mode_label': mode_label or operator_name,
            'stage_label': '啟動',
            'source_name': getattr(source, 'name', ''),
            'target_name': getattr(target, 'name', ''),
            'source_loc': source_loc.copy() if source_loc else None,
            'target_loc': target_loc.copy() if target_loc else None,
            'current_loc': source_loc.copy() if source_loc else None,
            'distance': None,
            'angle_deg': None,
            'axis_label': '未約束',
            'points': [],
            'flip_normal': False,
            'contact_error': None,
            'draw_tripod': True,
            'draw_distance_line': True,
            'draw_angle_arc': True,
            'candidate_loc': None,
            'candidate_type': '',
            'candidate_object': '',
        }
        self._handler_pixel = SpaceView3D.draw_handler_add(self._draw_pixel, (), 'WINDOW', 'POST_PIXEL')
        self._handler_view = SpaceView3D.draw_handler_add(self._draw_view, (), 'WINDOW', 'POST_VIEW')
        self._tag_redraw(context)

    def stop(self, context=None):
        if self._handler_pixel is not None:
            try:
                SpaceView3D.draw_handler_remove(self._handler_pixel, 'WINDOW')
            except Exception:
                pass
            self._handler_pixel = None
        if self._handler_view is not None:
            try:
                SpaceView3D.draw_handler_remove(self._handler_view, 'WINDOW')
            except Exception:
                pass
            self._handler_view = None
        self.active = False
        self.data = {}
        self._tag_redraw(context)

    def _tag_redraw(self, context=None):
        wm = getattr(bpy.context, 'window_manager', None)
        if wm is None:
            return
        for window in wm.windows:
            screen = window.screen
            if not screen:
                continue
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()

    def update(self, **kwargs):
        if not self.active:
            return
        self.data.update(kwargs)
        self._tag_redraw()

    def update_points(self, points):
        pts = []
        for p in points:
            if p is None:
                continue
            try:
                pts.append(p.copy())
            except Exception:
                pts.append(Vector(p))
        self.update(points=pts)

    def update_transform(self, source_obj=None, target_obj=None, transform=None):
        if not self.active:
            return
        source_loc = None
        target_loc = None
        current_loc = None
        if source_obj is not None:
            source_loc = source_obj.matrix_world.translation.copy()
            current_loc = source_loc.copy()
        if target_obj is not None:
            target_loc = target_obj.matrix_world.translation.copy()
        distance = None
        delta = None
        if source_loc is not None and target_loc is not None:
            delta = target_loc - source_loc
            distance = delta.length
        angle_deg = None
        axis_label = '未約束'
        if transform is not None:
            try:
                q = transform.to_quaternion()
                angle_deg = math.degrees(q.angle)
                axis = q.axis
                axis_label = self._axis_label_from_vector(axis)
            except Exception:
                pass
        self.update(
            source_loc=source_loc,
            target_loc=target_loc,
            current_loc=current_loc,
            delta=delta,
            distance=distance,
            angle_deg=angle_deg,
            axis_label=axis_label,
        )

    def _axis_label_from_vector(self, axis: Vector | None):
        if axis is None:
            return '未約束'
        comps = {'X': abs(axis.x), 'Y': abs(axis.y), 'Z': abs(axis.z)}
        return max(comps, key=comps.get)

    def _tripod_scale(self):
        distance = self.data.get('distance')
        if isinstance(distance, (int, float)) and distance > 1e-6:
            return max(0.25, min(distance * 0.18, 2.0))
        return 0.75

    def _draw_text(self, x, y, text, color, size=14):
        font_id = self._font_id
        blf.size(font_id, float(size))
        blf.position(font_id, float(x), float(y), 0)
        blf.color(font_id, *color)
        blf.draw(font_id, str(text))

    def _draw_pixel(self):
        if not self.active:
            return
        ctx = bpy.context
        area = getattr(ctx, 'area', None)
        region = getattr(ctx, 'region', None)
        if area is None or region is None or area.type != 'VIEW_3D':
            return
        x = 24
        y = region.height - 34
        line_h = 22
        rows = []

        # ── 吸附狀態（最重要，放最上面）──
        snap_state       = self.data.get('snap_state', '')
        snap_state_label = self.data.get('snap_state_label', '')
        last_valid_type  = self.data.get('last_valid_type', '')
        sticky_active    = self.data.get('sticky_active', False)
        snap_mode_label  = self.data.get('snap_mode_label', '')
        stage_label      = self.data.get('stage_label', '')

        state_colors = {
            'IDLE':          (0.5,  0.5,  0.5,  1.0),
            'HOVER':         (0.85, 0.85, 0.25, 1.0),
            'LIVE_SNAP':     (0.2,  0.95, 0.2,  1.0),
            'STICKY_SNAP':   (1.0,  0.65, 0.1,  1.0),
            'CONFIRM_READY': (0.2,  0.6,  1.0,  1.0),
            'CONFIRMED':     (0.2,  1.0,  0.4,  1.0),
        }

        if snap_state:
            sc = state_colors.get(snap_state, (0.9, 0.9, 0.9, 1.0))
            label = snap_state_label or snap_state
            rows.append((f"◉  {label}", sc, 15))
        else:
            rows.append(("◉  READY", (0.5, 0.5, 0.5, 1.0), 15))

        if last_valid_type and last_valid_type != '—':
            lv_color = (1.0, 0.65, 0.1, 1.0) if sticky_active else (0.7, 0.9, 1.0, 1.0)
            rows.append((f"📌 最後有效: {last_valid_type}", lv_color, 13))

        if snap_mode_label:
            rows.append((f"吸附: {snap_mode_label}", (1.0, 0.88, 0.45, 1.0), 13))

        if self.data.get('flip_normal'):
            rows.append(("↕ 法線翻轉: 開啟 (F切換)", (1.0, 0.7, 0.4, 1.0), 12))

        # ── 操作提示（固定在最下面幾行）──
        rows.append(('', (1, 1, 1, 0), 5))
        rows.append(("左鍵確認  |  Space/Esc 取消", (0.6, 0.6, 0.6, 1.0), 12))

        for text, color, size in rows:
            self._draw_text(x, y, text, color, size)
            y -= line_h

        self._draw_screen_annotations(region)

    def _draw_screen_annotations(self, region):
        ctx = bpy.context
        rv3d = getattr(getattr(ctx, 'space_data', None), 'region_3d', None)
        if rv3d is None:
            return
        source_loc = self.data.get('source_loc')
        target_loc = self.data.get('target_loc')
        current_loc = self.data.get('current_loc')
        angle = self.data.get('angle_deg')
        distance = self.data.get('distance')
        delta = self.data.get('delta')

        if isinstance(source_loc, Vector) and isinstance(target_loc, Vector):
            mid = (source_loc + target_loc) * 0.5
            pos = view3d_utils.location_3d_to_region_2d(region, rv3d, mid)
            if pos is not None:
                label = []
                if isinstance(distance, (int, float)):
                    label.append(f"Dist {distance:.4f}")
                if isinstance(angle, (int, float)):
                    label.append(f"Angle {angle:.2f}°")
                if label:
                    self._draw_text(pos.x + 10, pos.y + 10, ' | '.join(label), (1.0, 0.95, 0.45, 1.0), 13)

        if isinstance(current_loc, Vector) and isinstance(delta, Vector):
            base = view3d_utils.location_3d_to_region_2d(region, rv3d, current_loc)
            if base is not None:
                self._draw_text(base.x + 12, base.y - 18, f"Δ({delta.x:.3f}, {delta.y:.3f}, {delta.z:.3f})", (0.85, 0.95, 1.0, 1.0), 12)

        # ── TASK 2: Plane normal arrow for 3-point align ────────────────────
        plane_origin = self.data.get('plane_normal_origin')
        plane_normal = self.data.get('plane_normal_vec')
        if isinstance(plane_origin, Vector) and isinstance(plane_normal, Vector):
            try:
                scale = self.data.get('plane_normal_scale', 0.5)
                tip = plane_origin + plane_normal.normalized() * scale
                self._draw_line_3d(plane_origin, tip, color=(0.3, 0.6, 1.0, 0.9), width=2.5)
                # arrowhead: small crosshair at tip in screen space
                tip_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, tip)
                if tip_2d:
                    self._draw_text(tip_2d.x + 6, tip_2d.y + 4, '▲ 法線', (0.3, 0.7, 1.0, 1.0), 11)
            except Exception:
                pass

        # Plane label: show when 3+ target points picked
        plane_pts = self.data.get('plane_preview_points', [])
        if len(plane_pts) >= 3:
            try:
                centroid = Vector((0, 0, 0))
                for p in plane_pts[:3]:
                    centroid += Vector(p)
                centroid /= 3
                c2d = view3d_utils.location_3d_to_region_2d(region, rv3d, centroid)
                if c2d:
                    self._draw_text(c2d.x + 6, c2d.y + 8, '📐 對齊平面', (0.3, 0.6, 1.0, 0.9), 12)
            except Exception:
                pass

        candidate_loc = self.data.get('candidate_loc')
        candidate_type = self.data.get('candidate_type')
        if isinstance(candidate_loc, Vector):
            pos = view3d_utils.location_3d_to_region_2d(region, rv3d, candidate_loc)
            if pos is not None:
                # TASK 1: show snap state badge (LIVE / STICKY / READY)
                snap_state = self.data.get('snap_state', '')
                sticky_active = self.data.get('sticky_active', False)
                state_badge_colors = {
                    'LIVE_SNAP':     ((0.2, 0.95, 0.2, 1.0),  'Snap: {type} (LIVE)'),
                    'STICKY_SNAP':   ((1.0, 0.65, 0.1, 1.0),  'Snap: {type} (STICKY)'),
                    'CONFIRM_READY': ((0.2, 0.6,  1.0, 1.0),  'Snap: {type} (READY)'),
                }
                badge_color, badge_fmt = state_badge_colors.get(
                    snap_state,
                    ((1.0, 0.9, 0.25, 1.0), '候選: {type}')
                )
                badge_text = badge_fmt.format(type=candidate_type or 'RAY')
                self._draw_text(pos.x + 14, pos.y + 28, badge_text, badge_color, 14)
                if sticky_active:
                    self._draw_text(pos.x + 14, pos.y + 12, '🔒 左鍵可確認最後有效點', (1.0, 0.65, 0.1, 1.0), 12)
                else:
                    self._draw_text(pos.x + 14, pos.y + 12, '左鍵將選這個點', (1.0, 0.85, 0.45, 1.0), 12)
                cursor_char = '🔒' if sticky_active else '◎'
                cursor_color = (1.0, 0.55, 0.1, 1.0) if sticky_active else (0.2, 0.95, 0.2, 1.0)
                self._draw_text(pos.x + 4, pos.y - 4, cursor_char, cursor_color, 20)

    def _ensure_shader(self):
        if self._shader is None:
            self._shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        return self._shader

    def _draw_line_3d(self, p1: Vector, p2: Vector, color=(1,1,1,1), width=2.0):
        shader = self._ensure_shader()
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(width)
        batch = batch_for_shader(shader, 'LINES', {"pos": [tuple(p1), tuple(p2)]})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _draw_arc_3d(self, center: Vector, v_from: Vector, v_to: Vector, radius: float, color=(1.0,0.8,0.2,1.0), segments=24):
        if v_from.length < 1e-6 or v_to.length < 1e-6:
            return
        n = v_from.cross(v_to)
        if n.length < 1e-6:
            return
        n.normalize()
        v_from_n = v_from.normalized() * radius
        angle = v_from.angle(v_to)
        pts = []
        for i in range(segments + 1):
            t = angle * (i / segments)
            rot = Matrix.Rotation(t, 3, n)
            pts.append(tuple(center + (rot @ v_from_n)))
        shader = self._ensure_shader()
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": pts})
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)

    def _draw_view(self):
        if not self.active:
            return
        ctx = bpy.context
        region = getattr(ctx, 'region', None)
        rv3d = getattr(getattr(ctx, 'space_data', None), 'region_3d', None)
        if region is None or rv3d is None:
            return

        source_loc = self.data.get('source_loc')
        current_loc = self.data.get('current_loc') or source_loc
        target_loc = self.data.get('target_loc')
        delta = self.data.get('delta')
        points = self.data.get('points') or []

        # Draw picked points labels
        for i, point in enumerate(points, start=1):
            try:
                pos = view3d_utils.location_3d_to_region_2d(region, rv3d, point)
                if pos is None:
                    continue
                self._draw_text(pos.x + 8, pos.y + 8, f"P{i}", (1.0, 1.0, 0.2, 1.0), 12)
            except Exception:
                continue

        if not isinstance(current_loc, Vector):
            return

        scale = self._tripod_scale()
        if self.data.get('draw_tripod', True):
            axes = [
                (Vector((1, 0, 0)), (1.0, 0.25, 0.25, 0.95), 'X'),
                (Vector((0, 1, 0)), (0.25, 1.0, 0.25, 0.95), 'Y'),
                (Vector((0, 0, 1)), (0.25, 0.6, 1.0, 0.95), 'Z'),
            ]
            for axis_vec, color, label in axes:
                end = current_loc + axis_vec * scale
                self._draw_line_3d(current_loc, end, color, 2.5)
                pos = view3d_utils.location_3d_to_region_2d(region, rv3d, end)
                if pos is not None:
                    self._draw_text(pos.x + 4, pos.y + 4, label, color, 12)

        if self.data.get('draw_distance_line', True) and isinstance(target_loc, Vector):
            self._draw_line_3d(current_loc, target_loc, (1.0, 0.9, 0.3, 0.9), 2.8)

        if self.data.get('draw_angle_arc', True) and isinstance(target_loc, Vector):
            line_vec = target_loc - current_loc
            if line_vec.length > 1e-6:
                base_vec = Vector((1, 0, 0))
                axis_label = self.data.get('axis_label')
                if axis_label == 'Y':
                    base_vec = Vector((0, 1, 0))
                elif axis_label == 'Z':
                    base_vec = Vector((0, 0, 1))
                self._draw_arc_3d(current_loc, base_vec, line_vec, min(scale * 0.75, line_vec.length * 0.25), (1.0, 0.75, 0.2, 0.9), 20)

        candidate_loc = self.data.get('candidate_loc')
        if isinstance(candidate_loc, Vector):
            size = max(scale * 0.16, 0.14)
            self._draw_line_3d(candidate_loc + Vector((size, 0, 0)), candidate_loc - Vector((size, 0, 0)), (1.0, 0.55, 0.1, 0.98), 4.5)
            self._draw_line_3d(candidate_loc + Vector((0, size, 0)), candidate_loc - Vector((0, size, 0)), (1.0, 0.55, 0.1, 0.98), 4.5)
            self._draw_line_3d(candidate_loc + Vector((0, 0, size)), candidate_loc - Vector((0, 0, size)), (1.0, 0.75, 0.25, 0.98), 4.5)
            ring = [tuple(candidate_loc + Vector((math.cos(i * math.tau / 24) * size * 0.9, math.sin(i * math.tau / 24) * size * 0.9, 0))) for i in range(25)]
            shader = self._ensure_shader()
            gpu.state.blend_set('ALPHA')
            gpu.state.line_width_set(2.5)
            batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": ring})
            shader.bind()
            shader.uniform_float("color", (1.0, 0.8, 0.25, 0.9))
            batch.draw(shader)
            gpu.state.line_width_set(1.0)


overlay_engine = MeasurementOverlayEngine()
