"""
Smart Align Pro - CAD 級操作器
v7.6 — Quick Snap 獨立流程 + CAD Snap 支援 Move/Rotate transform_mode
"""

import bpy
import math
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, StringProperty
from mathutils import Vector, Matrix, Quaternion
from bpy_extras import view3d_utils
from math import hypot

from ..core.snap_engine import snap_engine
from ..core.snap_solver_core import (
    SnapResult, SnapSolverMixin,
    snap_solver_core, snap_radius_for, sticky_radius_for,
    screen_distance as _core_screen_dist,
    INFLUENCE_RADIUS_LIVE, INFLUENCE_RADIUS_STICKY, INFLUENCE_RADIUS_CONFIRM,
)
from ..core.selector_state_machine import SelectorStateMachine, new_sm
from ..core.preview_transform import preview, update_two_point_preview, apply_preview, cancel_preview
from ..core.realtime_preview_engine import (
    activate_realtime_preview, deactivate_realtime_preview,
    update_object_preview, get_realtime_preview_engine,
)
from ..ui.overlays import overlay
from ..ui.hud import hud_manager
from ..utils.icon_safe import safe_icon


def _snap_mode_label(mode):
    return {
        "VERTEX": "頂點", "EDGE": "邊", "MIDPOINT": "邊中點", "FACE": "面",
        "FACE_CENTER": "面中心", "CENTER": "中心", "ORIGIN": "物件原點", "ALL": "全部",
    }.get((mode or "VERTEX").upper(), str(mode))


def _get_bbox_center(obj):
    """取得物件 bounding box 世界座標中心"""
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    center = sum(corners, Vector()) / 8
    return center


def _get_snap_candidate_near_mouse(context, event, snap_type="ALL", expected_object=None, exclude_objects=None):
    """從 snap_engine 取得最佳候選點，帶 snap_type 篩選"""
    raw = snap_engine.find_best_candidate(
        context, event.mouse_region_x, event.mouse_region_y,
        allowed_types=snap_type, expected_object=expected_object, exclude_objects=exclude_objects
    )
    if raw is None:
        return None
    sr = SnapResult.from_candidate(raw)
    if snap_type != "ALL" and not snap_solver_core.filter_by_snap_type(sr, snap_type):
        return None
    return sr


def _set_header(context, text):
    if hasattr(context, "area") and context.area:
        context.area.header_text_set(text)


def _clear_header(context):
    if hasattr(context, "area") and context.area:
        context.area.header_text_set(None)


# ─────────────────────────────────────────────────────────────
# Quick Snap — 真正的一步式快貼流程 (v7.6 全新獨立 modal)
# 不再只是打開 CAD Snap modal，而是：
#   1. 自動以 active object pivot 為來源基準
#   2. 滑鼠即時預覽貼到哪裡
#   3. 左鍵直接完成，Space/Esc 退出
# ─────────────────────────────────────────────────────────────

class SMARTALIGNPRO_OT_quick_snap(Operator, SnapSolverMixin):
    """快速貼附 — 自動以物件中心為基準，滑鼠指哪貼哪，左鍵完成"""
    bl_idname  = "smartalignpro.quick_snap"
    bl_label   = "快速貼附"
    bl_description = "以物件中心為基準，即時預覽貼附到目標點，左鍵完成（v7.6 獨立流程）"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    snap_type: EnumProperty(
        name="吸附類型",
        items=[
            ("ALL",      "全部",   ""),
            ("VERTEX",   "頂點",   ""),
            ("MIDPOINT", "邊中點", ""),
            ("FACE",     "面",     ""),
            ("FACE_CENTER", "面中心", ""),
            ("ORIGIN",   "物件原點", ""),
        ],
        default="ALL",
    )

    def _build_quick_snap_matrix(self, target_location):
        delta = target_location - self._source_pivot
        return Matrix.Translation(delta) @ self._original_matrix

    def invoke(self, context, event):
        # 規則：
        # 1. 若有 2 個以上選取物件，active_object 視為 target，不拿來當 source
        # 2. source 優先取「不是 active 的那個 selected object」
        # 3. 若只有 1 個物件，才退回 active_object / selected_objects[0]

        active_obj = context.active_object
        selected = list(context.selected_objects)

        source_obj = None

        if active_obj and len(selected) >= 2:
            for obj in selected:
                if obj != active_obj:
                    source_obj = obj
                    break

        if source_obj is None:
            source_obj = active_obj

        if source_obj is None and selected:
            source_obj = selected[0]

        if source_obj is None:
            self.report({"WARNING"}, "請先選取一個物件作為來源")
            return {"CANCELLED"}

        self._source = source_obj
        self._original_matrix = self._source.matrix_world.copy()
        self._source_pivot = _get_bbox_center(self._source)
        self._preview_active = False
        self._preview_engine = get_realtime_preview_engine()
        try:
            activate_realtime_preview(context)
            self._preview_engine.add_preview_object(self._source.name, self._source)
        except Exception:
            self._preview_engine = None

        self.init_snap_state()
        self._sm = new_sm()

        context.window_manager.modal_handler_add(self)
        _set_header(
            context,
            f"快速貼附｜{_snap_mode_label(self.snap_type)}｜滑鼠移到目標點，左鍵貼附｜Space/Esc 取消"
        )
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type in {
            "MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE",
            "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE", "MOUSESMARTZOOM"
        }:
            return {"PASS_THROUGH"}

        if event.alt and event.type in {"LEFTMOUSE", "MIDDLEMOUSE", "RIGHTMOUSE"}:
            return {"PASS_THROUGH"}

        context.area.tag_redraw()

        # 退出
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return self._cancel(context)

        if event.type == "SPACE" and event.value == "PRESS":
            return self._cancel(context)

        # 切換吸附類型
        if event.type == "TAB" and event.value == "PRESS":
            modes = ["ALL", "VERTEX", "MIDPOINT", "FACE_CENTER", "ORIGIN"]
            self.snap_type = modes[(modes.index(self.snap_type) + 1) % len(modes)]
            _set_header(context, f"快速貼附｜{_snap_mode_label(self.snap_type)}｜左鍵貼附｜Space 取消")
            return {"RUNNING_MODAL"}

        # 滑鼠移動：即時預覽
        if event.type == "MOUSEMOVE":
            sr = _get_snap_candidate_near_mouse(
                context, event, self.snap_type,
                expected_object=getattr(context, "active_object", None),
                exclude_objects=[self._source],
            )
            self.store_fresh(sr, "QUICK", event)
            result, src = self.get_effective("QUICK", self.snap_type)
            is_sticky = src in ("sticky", "last_valid")
            sm = self._sm

            if result:
                sm.on_sticky() if is_sticky else (sm.on_live_snap() if result.is_non_ray else sm.on_hover())

                preview_matrix = self._build_quick_snap_matrix(result.location)
                if self._preview_engine:
                    self._preview_engine.add_preview_object(self._source.name, self._source)
                    update_object_preview(self._source.name, preview_matrix)
                self._preview_active = True

                snap_label = _snap_mode_label(result.snap_type)
                lock_icon = "🔒 " if is_sticky else ""
                _set_header(context, f"快速貼附｜{lock_icon}{snap_label}｜左鍵確認貼附｜Space 取消")
            else:
                sm.on_hover()
                if self._preview_active:
                    if self._preview_engine:
                        self._preview_engine.remove_preview_object(self._source.name)
                    self._preview_active = False
                _set_header(context, f"快速貼附｜{_snap_mode_label(self.snap_type)}｜移到目標點｜Space 取消")

            return {"RUNNING_MODAL"}

        # 左鍵確認
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            result, src = self.get_effective("QUICK", self.snap_type)

            if result is None:
                self.report({"WARNING"}, "沒有可吸附的目標點")
                return {"RUNNING_MODAL"}

            final_matrix = self._build_quick_snap_matrix(result.location)
            self._source.matrix_world = final_matrix
            try:
                deactivate_realtime_preview(context)
            except Exception:
                pass

            self.reset_snap_state()
            _clear_header(context)
            self.report({"INFO"}, f"快速貼附完成：{_snap_mode_label(result.snap_type)}")
            return {"FINISHED"}

        return {"RUNNING_MODAL"}

    def _cancel(self, context):
        # 恢復原始位置
        try:
            deactivate_realtime_preview(context)
        except Exception:
            pass
        self.reset_snap_state()
        _clear_header(context)
        return {"CANCELLED"}


# ─────────────────────────────────────────────────────────────
# CAD Snap Modal — 精準貼附 + transform_mode (MOVE / ROTATE)
# ─────────────────────────────────────────────────────────────

class SMARTALIGNPRO_OT_cad_snap_modal(Operator, SnapSolverMixin):
    """精準貼附 (v7.6 — Move/Rotate transform_mode + 4-level sticky)"""
    bl_idname  = "smartalignpro.cad_snap_modal"
    bl_label   = "精準貼附"
    bl_description = "CAD 級 snap-from/snap-to 精準對齊，支援 Move / Rotate 模式"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    snap_type: EnumProperty(
        name="吸附類型",
        items=[
            ("ALL",         "全部",   ""),
            ("VERTEX",      "頂點",   ""),
            ("EDGE",        "邊緣",   ""),
            ("MIDPOINT",    "中點",   ""),
            ("FACE",        "面",     ""),
            ("FACE_CENTER", "面中心", ""),
            ("CENTER",      "中心",   ""),
            ("ORIGIN",      "原點",   ""),
        ],
        default="ALL",
    )
    constraint_axis: EnumProperty(
        name="約束軸",
        items=[("NONE", "無約束", ""), ("X", "X 軸", ""), ("Y", "Y 軸", ""), ("Z", "Z 軸", "")],
        default="NONE",
    )
    transform_mode: EnumProperty(
        name="變形模式",
        items=[
            ("MOVE",   "移動", "平移物件：FROM 點移到 TO 點"),
            ("ROTATE", "旋轉", "旋轉物件：FROM 方向對齊 TO 法線"),
        ],
        default="MOVE",
    )

    def _current_sm(self):
        return self._sm_from if self.mode == "FROM" else self._sm_to

    def _raw_candidate(self, context, event):
        expected_object = self.source_object if self.mode == "FROM" else self.target_object
        exclude_objects = []
        if self.mode == "TO" and self.source_object is not None:
            exclude_objects.append(self.source_object)

        raw = snap_engine.find_best_candidate(
            context,
            event.mouse_region_x,
            event.mouse_region_y,
            allowed_types=self.snap_type,
            expected_object=expected_object,
            exclude_objects=exclude_objects,
        )
        if raw is None:
            return None

        sr = SnapResult.from_candidate(raw)

        # 先過濾吸附類型
        if not snap_solver_core.filter_by_snap_type(sr, self.snap_type):
            return None

        return raw

    def invoke(self, context, event):
        self.from_point = None
        self.to_point = None
        self.from_normal = None
        self.to_normal = None
        self.source_object = None
        self.target_object = None
        self._sm_from = None
        self._sm_to = None
        self.mode = "FROM"

        selected = list(context.selected_objects)
        active_obj = context.active_object

        if not selected:
            self.report({"WARNING"}, "請先選取物件")
            return {"CANCELLED"}

        # 規則：
        # active_object 視為 TO / target
        # source_object 優先取 selected 中不是 active 的那個
        source_obj = None
        target_obj = active_obj

        if active_obj and len(selected) >= 2:
            for obj in selected:
                if obj != active_obj:
                    source_obj = obj
                    break

        if source_obj is None:
            source_obj = active_obj or selected[0]

        if target_obj is None and selected:
            target_obj = selected[0]

        if source_obj is None:
            self.report({"WARNING"}, "找不到來源物件")
            return {"CANCELLED"}

        self.source_object = source_obj
        self.target_object = target_obj
        self._original_matrix = self.source_object.matrix_world.copy()

        from ..core.preview_transform import activate as pt_activate
        pt_activate(self.source_object, [])
        self._preview_engine = get_realtime_preview_engine()
        try:
            activate_realtime_preview(context)
            self._preview_engine.add_preview_object(self.source_object.name, self.source_object)
        except Exception:
            self._preview_engine = None
        overlay.register()

        self.init_snap_state()
        self._sm_from = new_sm()
        self._sm_to = new_sm()
        self._snap_type_filter = self.snap_type

        context.window_manager.modal_handler_add(self)
        self._update_header(context)
        return {"RUNNING_MODAL"}

    def _update_header(self, context):
        mode_label = {"MOVE": "移動", "ROTATE": "旋轉"}.get(self.transform_mode, self.transform_mode)
        stage_label = {"FROM": "選 FROM 點", "TO": "選 TO 點", "ALIGN": "Enter 確認"}.get(self.mode, self.mode)
        snap_label = _snap_mode_label(self.snap_type)
        _set_header(context, f"精準貼附｜{mode_label}｜{stage_label}｜吸附:{snap_label}｜Tab:切吸附 M:切模式 Space/Esc:取消")

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "ESC":
            self._finish_modal(context, cancel=True); return {"CANCELLED"}
        if event.type == "SPACE" and event.value == "PRESS":
            self._finish_modal(context, cancel=True); return {"CANCELLED"}
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            self._finish_modal(context, cancel=True); return {"CANCELLED"}

        if event.type == "RET" and event.value == "PRESS":
            if self.from_point and self.to_point:
                return self._execute_alignment(context)
            self.report({"WARNING"}, "請先選擇 From 和 To 點")

        if event.type == "TAB" and event.value == "PRESS":
            modes = ["ALL", "VERTEX", "MIDPOINT", "EDGE", "FACE_CENTER", "ORIGIN"]
            self.snap_type = modes[(modes.index(self.snap_type) + 1) % len(modes)]
            self._update_header(context); return {"RUNNING_MODAL"}

        if event.type == "M" and event.value == "PRESS":
            self.transform_mode = "ROTATE" if self.transform_mode == "MOVE" else "MOVE"
            self._update_header(context); return {"RUNNING_MODAL"}

        if event.type == "C" and event.value == "PRESS":
            axes = ["NONE", "X", "Y", "Z"]
            self.constraint_axis = axes[(axes.index(self.constraint_axis) + 1) % len(axes)]
            self._update_header(context); return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE":
            self._handle_mouse_move(context, event)

        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            result = self._handle_click(context, event)
            if result in ({"FINISHED"}, {"CANCELLED"}):
                self._finish_modal(context, cancel=("CANCELLED" in result))
            return result

        return {"RUNNING_MODAL"}

    def _handle_mouse_move(self, context, event):
        raw = self._raw_candidate(context, event)
        stage = self.mode
        if raw is not None:
            self.store_fresh(SnapResult.from_candidate(raw), stage, event)
        else:
            self.store_fresh(None, stage, event)

        result, src = self.get_effective(stage, self.snap_type)
        # TO 階段若 fresh 暫時沒命中，優先保留最後一次有效的 sticky / last_valid
        if self.mode == "TO" and (result is None or getattr(result, "snap_type", None) == "RAY"):
            last_valid = getattr(self, "_snap_last_valid", None)
            if last_valid is not None and getattr(last_valid, "snap_type", None) != "RAY":
                result = last_valid
                src = "last_valid"

        is_sticky = src in ("sticky", "last_valid")
        sm = self._current_sm()

        if result:
            sm.on_sticky() if is_sticky else (sm.on_live_snap() if result.is_non_ray else sm.on_hover())
            snap_r    = snap_radius_for(result.snap_type)
            influence = snap_r * (INFLUENCE_RADIUS_STICKY if is_sticky else INFLUENCE_RADIUS_LIVE)
            overlay.update_hover_candidate(
                result, sticky_active=is_sticky,
                sticky_label=f"🔒 {result.snap_type}" if is_sticky else "",
                snap_radius_px=influence, snap_state=sm.state, snap_state_color=sm.color,
            )
            # 即時預覽（TO 階段且已有 FROM 點時）
            if self.mode == "TO" and self.from_point:
                self._apply_live_preview(result)
        else:
            sm.on_hover()
            overlay.clear_hover_candidate()
            # 恢復原始位置
            if self.mode == "TO" and self._preview_engine and self.source_object:
                self._preview_engine.remove_preview_object(self.source_object.name)

    def _build_move_matrix(self, target_point):
        delta = target_point - self.from_point

        if self.constraint_axis != "NONE":
            ax = {"X": 0, "Y": 1, "Z": 2}[self.constraint_axis]
            constrained = Vector((0.0, 0.0, 0.0))
            constrained[ax] = delta[ax]
            delta = constrained

        return Matrix.Translation(delta) @ self._original_matrix

    def _apply_live_preview(self, result):
        """根據 transform_mode 即時預覽"""
        if not self.source_object:
            return

        if self.transform_mode == "MOVE":
            preview_matrix = self._build_move_matrix(result.location)
            if self._preview_engine:
                self._preview_engine.add_preview_object(self.source_object.name, self.source_object)
                update_object_preview(self.source_object.name, preview_matrix)

        elif self.transform_mode == "ROTATE":
            if self.from_normal and result.normal:
                from_n = self.from_normal.normalized()
                to_n = result.normal.normalized()
                cross = from_n.cross(to_n)

                if cross.length > 1e-6:
                    angle = from_n.angle(to_n)
                    rot = Matrix.Rotation(angle, 4, cross.normalized())
                    pivot = self._original_matrix.translation
                    T = Matrix.Translation(pivot)
                    T_inv = Matrix.Translation(-pivot)
                    preview_matrix = T @ rot @ T_inv @ self._original_matrix
                    if self._preview_engine:
                        self._preview_engine.add_preview_object(self.source_object.name, self.source_object)
                        update_object_preview(self.source_object.name, preview_matrix)

    def _handle_click(self, context, event):
        stage  = self.mode
        result, src = self.get_effective(stage, self.snap_type)

        if not result:
            self.report({"WARNING"}, "目前沒有可確認的吸附點"); return {"RUNNING_MODAL"}

        if self.mode == "FROM":
            self.from_point  = result.location.copy()
            self.from_normal = Vector(result.normal) if result.normal else Vector((0, 0, 1))
            self.mode = "TO"
            self.confirm_snap(); self.advance_stage(); self._sm_to = new_sm()
            self._update_header(context)
            self.report({"INFO"}, f"FROM 點已確認（{_snap_mode_label(result.snap_type)}），請選 TO 點")

        elif self.mode == "TO":
            if self.from_point:
                self.to_point  = result.location.copy()
                self.to_normal = Vector(result.normal) if result.normal else Vector((0, 0, 1))
                self.mode = "ALIGN"
                return self._execute_alignment(context)

        return {"RUNNING_MODAL"}

    def _execute_alignment(self, context):
        try:
            if not (self.from_point and self.to_point and self.source_object):
                self.report({"WARNING"}, "點位不足")
                return {"CANCELLED"}

            if self.transform_mode == "MOVE":
                final_matrix = self._build_move_matrix(self.to_point)
                self.source_object.matrix_world = final_matrix

            elif self.transform_mode == "ROTATE":
                if self.from_normal and self.to_normal:
                    from_n = self.from_normal.normalized()
                    to_n = self.to_normal.normalized()
                    cross = from_n.cross(to_n)

                    if cross.length > 1e-6:
                        angle = from_n.angle(to_n)
                        rot = Matrix.Rotation(angle, 4, cross.normalized())
                        pivot = self._original_matrix.translation
                        T = Matrix.Translation(pivot)
                        T_inv = Matrix.Translation(-pivot)
                        final_matrix = T @ rot @ T_inv @ self._original_matrix
                        self.source_object.matrix_world = final_matrix

            # 關鍵：把 preview state 同步到最後結果，避免 finish 時跳回原位
            try:
                from ..core.preview_transform import preview
                if (
                    preview
                    and preview.state
                    and preview.state.source_object == self.source_object
                ):
                    preview.state.preview_matrix = self.source_object.matrix_world.copy()
                    preview.state.original_matrix = self.source_object.matrix_world.copy()
            except Exception:
                pass

            mode_label = {"MOVE": "移動", "ROTATE": "旋轉"}.get(self.transform_mode, self.transform_mode)
            self.report({"INFO"}, f"精準貼附完成（{mode_label}）")
            return {"FINISHED"}

        except Exception as e:
            if self.source_object and self._original_matrix:
                self.source_object.matrix_world = self._original_matrix.copy()
            self.report({"ERROR"}, f"對齊失敗: {e}")
            return {"CANCELLED"}

    def _finish_modal(self, context, cancel=False):
        self.reset_snap_state()

        try:
            from ..core.preview_transform import preview
        except Exception:
            preview = None

        if cancel:
            if self.source_object and self._original_matrix:
                self.source_object.matrix_world = self._original_matrix.copy()
            try:
                cancel_preview()
            except Exception:
                pass
        else:
            # 成功時不能還原，只能保留最終結果
            try:
                if (
                    preview
                    and preview.state
                    and preview.state.source_object == self.source_object
                ):
                    preview.state.preview_matrix = self.source_object.matrix_world.copy()
                    preview.state.original_matrix = self.source_object.matrix_world.copy()
                    apply_preview()
            except Exception:
                pass

        try:
            deactivate_realtime_preview(context)
        except Exception:
            pass

        try:
            overlay.unregister()
        except Exception:
            pass

        _clear_header(context)

    def cleanup(self, context):
        self._finish_modal(context, cancel=True)


# ─────────────────────────────────────────────────────────────
# CAD Quick Snap (legacy shim) — 向後相容，現在改為呼叫 quick_snap
# ─────────────────────────────────────────────────────────────

class SMARTALIGNPRO_OT_cad_quick_snap(Operator):
    """快速貼附（舊入口，轉發到新版 quick_snap）"""
    bl_idname  = "smartalignpro.cad_quick_snap"
    bl_label   = "快速貼附"
    bl_description = "自動以物件中心為基準，即時預覽，左鍵直接貼附"
    bl_options = {"REGISTER", "UNDO"}

    snap_type: EnumProperty(
        name="吸附類型",
        items=[
            ("ALL",      "全部",   ""),
            ("VERTEX",   "頂點",   ""),
            ("EDGE",     "邊緣",   ""),
            ("FACE",     "面",     ""),
            ("MIDPOINT", "中點",   ""),
            ("CENTER",   "中心",   ""),
        ],
        default="ALL",
    )

    def execute(self, context):
        print("\n[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] ===== START =====")
        print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] area.type = {context.area.type if context.area else None}")
        print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] mode = {context.mode}")
        print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] active_object = {context.active_object.name if context.active_object else None}")
        print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] selected_objects = {[obj.name for obj in context.selected_objects]}")
        print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] view_layer.active = {context.view_layer.objects.active.name if context.view_layer.objects.active else None}")
        print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] snap_type = {self.snap_type}")

        try:
            result = bpy.ops.smartalignpro.quick_snap("INVOKE_DEFAULT", snap_type=self.snap_type)
            print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] bpy.ops result = {result}")
            print("[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] ==================\n")
            return {"FINISHED"} if "RUNNING_MODAL" in result else result

        except Exception as e:
            print(f"[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] EXCEPTION = {e}")
            print("[SMARTALIGNPRO][CAD QUICK SNAP EXECUTE DEBUG] ==================\n")
            self.report({"ERROR"}, f"無法啟動快速貼附：{e}")
            return {"CANCELLED"}

# ─────────────────────────────────────────────────────────────
# 面板
# ─────────────────────────────────────────────────────────────

class SMARTALIGNPRO_PT_cad_panel(Panel):
    bl_label       = "精準貼附工具"
    bl_idname      = "SMARTALIGNPRO_PT_cad_panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "對齊"
    bl_parent_id   = "SMARTALIGNPRO_PT_main_panel"

    def draw(self, context):
        layout = self.layout

        # ── 快速貼附（一步式）──
        qbox = layout.box()
        qbox.label(text="⚡ 快速貼附", icon=safe_icon("SNAP_EDGE"))
        col = qbox.column(align=True)
        col.scale_y = 1.3
        for st, lb in [("ALL", "自動"), ("VERTEX", "頂點"), ("MIDPOINT", "邊中點"),
                       ("FACE_CENTER", "面中心"), ("ORIGIN", "原點")]:
            col.operator("smartalignpro.quick_snap", text=f"{lb}吸附").snap_type = st

        layout.separator()

        # ── 精準貼附（FROM / TO）──
        pbox = layout.box()
        pbox.label(text="🎯 精準貼附", icon=safe_icon("SNAP_GRID"))
        col = pbox.column(align=True)
        col.scale_y = 1.2
        op = col.operator("smartalignpro.cad_snap_modal", text="精準貼附（移動）")
        op.transform_mode = "MOVE"
        op2 = col.operator("smartalignpro.cad_snap_modal", text="精準貼附（旋轉）")
        op2.transform_mode = "ROTATE"
        pbox.label(text="M:切模式 Tab:切吸附 Space:退出", icon=safe_icon("INFO"))
