"""
Smart Align Pro - 對齊操作器模組
v7.5.5 — unified 4-level snap chain + selector state machine
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, IntProperty, StringProperty
from bpy_extras import view3d_utils
from math import hypot
from mathutils import Vector, Matrix

from ..core.alignment import (
    two_point_align, three_point_align, surface_normal_align,
    surface_normal_align_with_raycast,
    auto_contact_align, align_to_ground, align_to_surface,
)
from ..core.detection import detect_object_type, get_alignment_strategy_suggestion, find_snap_candidate_on_hit
from ..core.math_utils import rotation_between_vectors, get_plane_basis, matrix_from_basis
from ..core.snap_solver_core import (
    SnapResult, SnapSolverMixin,
    screen_distance as _core_screen_dist,
    snap_solver_core,
)
from ..core.selector_state_machine import SelectorStateMachine, new_sm
from ..utils.debug_logger import (
    debug_log, log_operator_start, log_operator_end, log_object_pair, log_pick_point,
    log_transform_delta, snapshot_object,
)
from ..utils.measurement_overlay import overlay_engine


# ─── helpers ──────────────────────────────────────────────────────────────────

def _raycast_from_mouse(context, event, snap_mode="AUTO"):
    region = context.region
    rv3d   = context.space_data.region_3d if context.space_data else None
    if region is None or rv3d is None:
        return None
    coord     = (event.mouse_region_x, event.mouse_region_y)
    origin    = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
    depsgraph = context.evaluated_depsgraph_get()
    hit, location, normal, face_index, obj, matrix = context.scene.ray_cast(depsgraph, origin, direction)
    if not hit:
        return None
    candidate    = find_snap_candidate_on_hit(obj, face_index, location, snap_mode)
    snap_location = candidate.get("location") if isinstance(candidate, dict) else location.copy()
    return {
        "location":      location.copy(),
        "snap_location": snap_location.copy() if hasattr(snap_location, "copy") else location.copy(),
        "snap_type":     candidate.get("type", "RAY") if isinstance(candidate, dict) else "RAY",
        "snap_distance": candidate.get("distance", 0.0) if isinstance(candidate, dict) else 0.0,
        "normal":        normal.copy(),
        "face_index":    face_index,
        "object":        obj,
        "matrix":        matrix,
    }


def _dict_to_snap_result(hit, context=None, event=None):
    if hit is None:
        return None
    loc  = hit.get("snap_location") or hit.get("location")
    dist = 0.0
    if context and event and loc:
        dist = _core_screen_dist(context, loc, event.mouse_region_x, event.mouse_region_y)
    return SnapResult(
        location      = hit.get("location", Vector()),
        snap_location = loc,
        snap_type     = hit.get("snap_type", "RAY"),
        normal        = hit.get("normal"),
        face_index    = hit.get("face_index", -1),
        obj           = hit.get("object"),
        matrix        = hit.get("matrix"),
        screen_distance = dist,
    )

def _nearest_candidate_on_object(context, event, target_obj, snap_mode="VERTEX"):
    """
    CAD-style intent preservation: when the cursor exits the expected object,
    find the nearest snap candidate on that object by scanning its geometry
    directly. Returns a SnapResult pointing to the closest vertex/midpoint/etc.
    on target_obj, or None if target_obj has no accessible mesh data.
    This prevents the 'jumps back to old point' problem when cursor briefly
    leaves the surface.
    """
    if target_obj is None or not hasattr(target_obj, "data") or target_obj.data is None:
        return None
    try:
        region = context.region
        rv3d   = context.space_data.region_3d if context.space_data else None
        if region is None or rv3d is None:
            return None
        mx = event.mouse_region_x
        my = event.mouse_region_y

        mesh = target_obj.data
        mw   = target_obj.matrix_world
        best_dist = float("inf")
        best_loc  = None
        best_type = "VERTEX"

        # Collect candidate points: vertices + edge midpoints
        verts_world = [mw @ v.co for v in mesh.vertices]

        candidates = []
        # Vertices
        for v in mesh.vertices:
            candidates.append((mw @ v.co, "VERTEX"))
        # Edge midpoints (if snap_mode allows)
        if snap_mode.upper() in ("EDGE", "AUTO", "VERTEX"):
            for e in mesh.edges:
                mid = (mesh.vertices[e.vertices[0]].co + mesh.vertices[e.vertices[1]].co) / 2.0
                candidates.append((mw @ mid, "MIDPOINT"))
        # Face centers
        if snap_mode.upper() in ("FACE", "AUTO"):
            for p in mesh.polygons:
                c = Vector((0, 0, 0))
                for vi in p.vertices:
                    c += mesh.vertices[vi].co
                c /= len(p.vertices)
                candidates.append((mw @ c, "FACE_CENTER"))
        # Object origin
        candidates.append((mw.translation.copy(), "ORIGIN"))

        for loc3d, stype in candidates:
            pt2d = view3d_utils.location_3d_to_region_2d(region, rv3d, loc3d)
            if pt2d is None:
                continue
            d = hypot(pt2d.x - mx, pt2d.y - my)
            if d < best_dist:
                best_dist = d
                best_loc  = loc3d.copy()
                best_type = stype

        # Only return a result if the nearest candidate is within a reasonable radius
        if best_loc is None or best_dist > 80.0:
            return None

        return SnapResult(
            location        = best_loc,
            snap_location   = best_loc,
            snap_type       = best_type,
            obj             = target_obj,
            screen_distance = best_dist,
        )
    except Exception:
        return None


def _set_header(context, text):
    a = getattr(context, "area", None)
    if a: a.header_text_set(text)

def _clear_header(context):
    a = getattr(context, "area", None)
    if a: a.header_text_set(None)

def _snap_debug(action, **payload):
    try:
        debug_log(f"snap_debug_{action}", **payload)
    except Exception as e:
        print(f"[SAP][SNAP DEBUG FAIL] {action}: {e}")

def _next_snap_mode(mode):
    modes = ["VERTEX","EDGE","FACE","ORIGIN"]
    mode  = (mode or modes[0]).upper()
    return modes[(modes.index(mode)+1)%len(modes)] if mode in modes else modes[0]

def _snap_mode_label(mode):
    return {"VERTEX":"頂點","EDGE":"邊中點","FACE":"面中心","ORIGIN":"物件原點","AUTO":"自動"}.get((mode or "AUTO").upper(), str(mode))

def _clear_overlay(context, stage_label=None, snap_mode_label=None):
    try:
        p = {"candidate_loc":None,"candidate_type":"","candidate_object":""}
        if stage_label:    p["stage_label"]    = stage_label
        if snap_mode_label: p["snap_mode_label"] = snap_mode_label
        overlay_engine.update(**p)
        if getattr(context,"area",None): context.area.tag_redraw()
    except Exception:
        pass

def _push_overlay(context, result, stage_label, snap_mode_label, sm, is_sticky,
                   flip_normal=False, preview_points=None, operator=None):
    """Feed the full snap state into overlay_engine (measurement_overlay + overlays).
    operator: the calling Operator instance (for last_valid_type_label)."""
    if result is None:
        _clear_overlay(context, stage_label=stage_label, snap_mode_label=snap_mode_label)
        return
    loc = result.snap_location or result.location

    # Compose the display label: adds SM state badge when sticky
    if is_sticky:
        display = f"{stage_label}  {sm.label}"
    else:
        display = stage_label

    # last_valid label from the mixin
    lv_label = operator.last_valid_type_label() if operator is not None else "—"

    p = {
        "stage_label":       display,
        "candidate_loc":     loc,
        "candidate_type":    result.snap_type,
        "candidate_object":  getattr(result.object, "name", ""),
        "snap_mode_label":   snap_mode_label,
        "sticky_active":     is_sticky,
        "sticky_label":      f"已鎖定: {result.snap_type}" if is_sticky else "",
        # TASK 1: snap state fields
        "snap_state":        sm.state,
        "snap_state_label":  sm.label,
        "snap_state_color":  sm.color,
        "last_valid_type":   lv_label,
        # TASK 3: always show priority legend in HUD
        "show_snap_priority": True,
    }
    if preview_points is not None:
        p["points"] = preview_points
    if flip_normal is not None:
        p["flip_normal"] = flip_normal
    try:
        overlay_engine.update(**p)
    except Exception:
        try:
            overlay_engine.update(stage_label=display, candidate_loc=loc,
                                  candidate_type=result.snap_type,
                                  candidate_object=getattr(result.object, "name", ""),
                                  snap_mode_label=snap_mode_label)
        except Exception:
            pass


# ─── mixin ────────────────────────────────────────────────────────────────────

class _InteractiveAlignMixin:
    def _validate_exact_two_mesh(self, context, op_name):
        active   = context.active_object
        selected = [o for o in context.selected_objects if o.type=="MESH"]
        if active is None or active.type!="MESH":
            self.report({"WARNING"},"請先選取目標 Mesh 物件作為 Active Object"); return None
        if len(selected)!=2:
            self.report({"WARNING"},"互動版目前需要剛好選取 2 個 Mesh：來源 + 目標（Active）"); return None
        source = next((o for o in selected if o!=active),None)
        if source is None:
            self.report({"WARNING"},"找不到來源物件"); return None
        return source, active
    def _restore_source(self):
        if getattr(self,"source",None) and getattr(self,"_original_matrix",None):
            self.source.matrix_world = self._original_matrix.copy()
    def _apply_preview_matrix(self, matrix):
        if getattr(self,"source",None) is None or getattr(self,"_original_matrix",None) is None: return
        self.source.matrix_world  = matrix @ self._original_matrix
        self._preview_transform   = matrix.copy()
    def _finish(self, context, message=None):
        _clear_header(context)
        if message: self.report({"INFO"},message)
        return {"FINISHED"}
    def _cancel(self, context, message=None):
        self._restore_source(); _clear_header(context)
        if message: self.report({"INFO"},message)
        return {"CANCELLED"}


# ─── TWO-POINT ALIGN ─────────────────────────────────────────────────────────

class SMARTALIGNPRO_OT_two_point_align(Operator, _InteractiveAlignMixin, SnapSolverMixin):
    """兩點對齊（v7.5.5 — 4-level sticky confirm）"""
    bl_idname="smartalignpro.two_point_align"; bl_label="兩點對齊"
    bl_description="點來源兩點、再點目標兩點；目標第二點即時預覽，離開物件仍可確認"
    bl_options={"REGISTER","UNDO","BLOCKING"}

    def invoke(self,context,event):
        log_operator_start("two_point_align",context)
        v = self._validate_exact_two_mesh(context,"two_point_align")
        if not v: return {"CANCELLED"}
        self.source,self.target=v
        log_object_pair("two_point_align",self.source,self.target,"invoke_before")
        self._before_source_snapshot=snapshot_object(self.source)
        self._before_target_snapshot=snapshot_object(self.target)
        overlay_engine.start(context,"two_point_align",self.source,self.target,"兩點對齊")
        overlay_engine.update(stage_label="來源第 1 點",points=[],flip_normal=False,snap_mode_label=_snap_mode_label("VERTEX"))
        self.source_points=[]; self.target_points=[]; self.stage="SOURCE_A"
        self._original_matrix=self.source.matrix_world.copy()
        self._preview_transform=None; self.snap_mode="VERTEX"
        self.init_snap_state(); self._sm=new_sm()
        context.window_manager.modal_handler_add(self)
        _set_header(context,f"兩點對齊｜來源: {self.source.name} 點第 1 點（左鍵）｜ESC 取消")
        self.report({"INFO"},f"兩點對齊開始：先點來源 {self.source.name} 的第 1 點")
        return {"RUNNING_MODAL"}

    def execute(self,context): return self.invoke(context,None)

    def _compute_two_point_transform(self,sa,sb,ta,tb):
        sv=sb-sa; tv=tb-ta
        if sv.length<1e-6 or tv.length<1e-6: raise ValueError("兩點距離太近，無法計算方向")
        rq=rotation_between_vectors(sv,tv); rm=rq.to_matrix().to_4x4()
        return Matrix.Translation(ta-(rm@sa))@rm

    def _expected(self): return self.source if self.stage.startswith("SOURCE") else self.target

    def _resolve_confirm(self,context,event):
        exp  = self._expected()
        hit  = _raycast_from_mouse(context,event,getattr(self,"snap_mode","VERTEX"))
        fr   = _dict_to_snap_result(hit,context,event) if hit and hit.get("object")==exp else None
        self.store_fresh(fr,self.stage,event)
        res,src = self.get_effective(self.stage,"ALL")
        if res is None or res.object!=exp:
            self.report({"WARNING"},"沒有點到物件表面"); return None,False
        is_s = src in ("sticky","last_valid")
        print(f"[SAP][CONFIRM] two_point stage={self.stage} src={src} type={res.snap_type}")
        return res.snap_location or res.location, is_s

    # stage labels
    _STAGE_MAP={"SOURCE_A":"來源第 1 點","SOURCE_B":"來源第 2 點","TARGET_A":"目標第 1 點","TARGET_B":"目標第 2 點預覽"}

    def modal(self,context,event):
        if event.type in {"MIDDLEMOUSE","WHEELUPMOUSE","WHEELDOWNMOUSE","TRACKPADPAN","TRACKPADZOOM","MOUSEROTATE","MOUSESMARTZOOM"}:
            return {"PASS_THROUGH"}
        if event.alt and event.type in {"LEFTMOUSE","MIDDLEMOUSE","RIGHTMOUSE"}:
            return {"PASS_THROUGH"}

        if event.value=="PRESS" and event.type in {"ONE","TWO","THREE","O"}:
            self.snap_mode={"ONE":"VERTEX","TWO":"EDGE","THREE":"FACE","O":"ORIGIN"}[event.type]
            overlay_engine.update(snap_mode_label=_snap_mode_label(self.snap_mode))
            self.report({"INFO"},f"吸附模式：{_snap_mode_label(self.snap_mode)}"); return {"RUNNING_MODAL"}
        if event.type=="TAB" and event.value=="PRESS":
            self.snap_mode=_next_snap_mode(self.snap_mode)
            overlay_engine.update(snap_mode_label=_snap_mode_label(self.snap_mode))
            self.report({"INFO"},f"吸附模式：{_snap_mode_label(self.snap_mode)}"); return {"RUNNING_MODAL"}

        if event.type=="ESC":
            log_operator_end("two_point_align","cancelled",stage=self.stage)
            overlay_engine.stop(context); return self._cancel(context,"兩點對齊已取消")
        if event.type=="SPACE" and event.value=="PRESS":
            log_operator_end("two_point_align","cancelled",stage=self.stage)
            overlay_engine.stop(context); return self._cancel(context,"兩點對齊已取消")

        if event.type=="MOUSEMOVE":
            exp  = self._expected()
            hit  = _raycast_from_mouse(context,event,getattr(self,"snap_mode","VERTEX"))
            if hit and hit.get("object")==exp:
                fr = _dict_to_snap_result(hit,context,event)
            elif exp is not None:
                # Cursor left expected object (hit other obj or miss) — find nearest candidate on it
                # This preserves intent: "I was heading toward bottom-left, don't jump back to top-left"
                fr = _nearest_candidate_on_object(context, event, exp, getattr(self,"snap_mode","VERTEX"))
            else:
                fr = None
            self.store_fresh(fr,self.stage,event)
            res,src = self.get_effective(self.stage,"ALL")
            is_s    = src in ("sticky","last_valid")
            sm      = self._sm

            if res and res.object==exp:
                sm.on_sticky() if is_s else (sm.on_live_snap() if res.is_non_ray else sm.on_hover())
                ploc   = res.snap_location or res.location
                ppts   = list(self.source_points)+list(self.target_points)+[ploc]
                _push_overlay(context,res,self._STAGE_MAP.get(self.stage,self.stage),
                              _snap_mode_label(self.snap_mode),sm,is_s,preview_points=ppts,operator=self)
                # TARGET_B preview transform
                if self.stage=="TARGET_B" and len(self.source_points)==2 and len(self.target_points)==1:
                    try:
                        t=self._compute_two_point_transform(self.source_points[0],self.source_points[1],self.target_points[0],ploc)
                        self._restore_source(); self._apply_preview_matrix(t)
                        context.view_layer.update(); overlay_engine.update_transform(self.source,self.target,t)
                        lk="🔒 預覽鎖定 " if is_s else ""
                        _set_header(context,f"兩點對齊｜{lk}目標第 2 點：左鍵確認｜ESC 取消")
                    except Exception: pass
                elif is_s:
                    _set_header(context,"兩點對齊｜🔒 已鎖定最後有效吸附點，左鍵可確認｜ESC 取消")
            else:
                sm.on_hover()
                _clear_overlay(context,stage_label=self._STAGE_MAP.get(self.stage,self.stage),
                               snap_mode_label=_snap_mode_label(self.snap_mode))
            return {"RUNNING_MODAL"}

        if event.type=="LEFTMOUSE" and event.value=="PRESS":
            loc,is_s=self._resolve_confirm(context,event)
            if loc is None: return {"RUNNING_MODAL"}

            if self.stage=="SOURCE_A":
                log_pick_point("two_point_align","SOURCE_A",self.source,loc)
                self.source_points.append(loc)
                overlay_engine.update(stage_label="來源第 2 點",points=self.source_points)
                self.stage="SOURCE_B"; self.confirm_snap(); self.advance_stage(); self._sm=new_sm()
                _set_header(context,f"兩點對齊｜來源: {self.source.name} 點第 2 點（左鍵）")
                self.report({"INFO"},"來源第 1 點已記錄，請點來源第 2 點"); return {"RUNNING_MODAL"}

            if self.stage=="SOURCE_B":
                log_pick_point("two_point_align","SOURCE_B",self.source,loc)
                self.source_points.append(loc)
                overlay_engine.update(stage_label="目標第 1 點",points=self.source_points)
                self.stage="TARGET_A"; self.confirm_snap(); self.advance_stage(); self._sm=new_sm()
                _set_header(context,f"兩點對齊｜目標: {self.target.name} 點第 1 點（左鍵）")
                self.report({"INFO"},"來源兩點完成，請點目標第 1 點"); return {"RUNNING_MODAL"}

            if self.stage=="TARGET_A":
                log_pick_point("two_point_align","TARGET_A",self.target,loc)
                self.target_points.append(loc)
                overlay_engine.update(stage_label="目標第 2 點",points=self.source_points+self.target_points)
                self.stage="TARGET_B"; self.confirm_snap(); self.advance_stage(); self._sm=new_sm()
                _set_header(context,f"兩點對齊｜目標: {self.target.name} 點第 2 點（移動滑鼠即時預覽，左鍵確認）")
                self.report({"INFO"},"目標第 1 點已記錄，移動滑鼠可看預覽，左鍵點目標第 2 點完成"); return {"RUNNING_MODAL"}

            if self.stage=="TARGET_B":
                log_pick_point("two_point_align","TARGET_B",self.target,loc)
                self.target_points.append(loc)
                try:
                    t=self._compute_two_point_transform(self.source_points[0],self.source_points[1],self.target_points[0],self.target_points[1])
                    self._restore_source(); self._apply_preview_matrix(t)
                    context.view_layer.update()
                    log_object_pair("two_point_align",self.source,self.target,"finish_after",source_points=self.source_points,target_points=self.target_points)
                    after_s=snapshot_object(self.source); after_t=snapshot_object(self.target)
                    log_transform_delta("two_point_align",self._before_source_snapshot,after_s,self._before_target_snapshot,after_t,source_points=self.source_points,target_points=self.target_points)
                    overlay_engine.update_transform(self.source,self.target,t)
                    overlay_engine.update(stage_label="完成",points=self.source_points+self.target_points)
                    log_operator_end("two_point_align","finished")
                    print(f"[SAP][兩點對齊] {self.source.name} → {self.target.name}")
                    overlay_engine.stop(context); return self._finish(context,"兩點對齊完成（v7.5.5）")
                except Exception as e:
                    log_operator_end("two_point_align","error",error=str(e))
                    overlay_engine.stop(context); return self._cancel(context,f"兩點對齊失敗：{e}")

        return {"RUNNING_MODAL"}


# ─── THREE-POINT ALIGN (bbox non-modal) ──────────────────────────────────────

class SMARTALIGNPRO_OT_three_point_align(Operator):
    bl_idname="smartalignpro.three_point_align"; bl_label="三點對齊"
    bl_description="使用來源三點與目標三點進行平面方向與位置對齊"
    bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        log_operator_start("three_point_align",context)
        settings=context.scene.smartalignpro_settings
        active=context.active_object
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if active is None or active.type!="MESH":
            self.report({"WARNING"},"請先選取一個目標 Mesh 物件作為 Active Object"); return {"CANCELLED"}
        if len(selected)!=2:
            self.report({"WARNING"},"請剛好選取兩個 Mesh 物件：先選來源，再選目標"); return {"CANCELLED"}
        source=next((o for o in selected if o!=active),None)
        if source is None:
            self.report({"WARNING"},"找不到來源物件"); return {"CANCELLED"}
        try:
            log_object_pair("three_point_align",source,active,"execute_before")
            three_point_align(source,active,settings.three_point_source_a,settings.three_point_source_b,settings.three_point_source_c,settings.three_point_target_a,settings.three_point_target_b,settings.three_point_target_c,settings)
            print(f"[SAP][三點對齊] {source.name} → {active.name}")
            log_operator_end("three_point_align","finished"); self.report({"INFO"},"三點對齊完成"); return {"FINISHED"}
        except Exception as e:
            log_operator_end("three_point_align","error",error=str(e)); self.report({"ERROR"},str(e)); return {"CANCELLED"}


# ─── THREE-POINT MODAL ───────────────────────────────────────────────────────

class SMARTALIGNPRO_OT_three_point_modal(Operator,_InteractiveAlignMixin,SnapSolverMixin):
    """三點對齊互動模式（v7.5.5 — 4-level sticky + triangle plane preview）"""
    bl_idname="smartalignpro.three_point_modal"; bl_label="三點對齊（互動模式）"
    bl_options={"REGISTER","UNDO","BLOCKING"}

    def invoke(self,context,event):
        log_operator_start("three_point_modal",context)
        v=self._validate_exact_two_mesh(context,"three_point_modal")
        if not v: return {"CANCELLED"}
        self.source,self.target=v
        log_object_pair("three_point_modal",self.source,self.target,"invoke_before")
        self._before_source_snapshot=snapshot_object(self.source)
        self._before_target_snapshot=snapshot_object(self.target)
        overlay_engine.start(context,"three_point_modal",self.source,self.target,"三點對齊")
        overlay_engine.update(stage_label="來源第 1 點",points=[],flip_normal=False,snap_mode_label=_snap_mode_label("VERTEX"))
        self.source_points=[]; self.target_points=[]; self.stage="SOURCE_1"
        self._original_matrix=self.source.matrix_world.copy()
        self._preview_transform=None; self.snap_mode="VERTEX"; self.flip_normal=False
        self.init_snap_state(); self._sm=new_sm()
        context.window_manager.modal_handler_add(self)
        _set_header(context,f"三點對齊｜來源: {self.source.name} 點第 1 點（左鍵）｜F 翻法線｜ESC 取消")
        self.report({"INFO"},f"三點對齊開始：先點來源 {self.source.name} 的第 1 點")
        return {"RUNNING_MODAL"}

    def execute(self,context): return self.invoke(context,None)

    def _expected(self): return self.source if self.stage.startswith("SOURCE") else self.target

    def _compute_three_point_transform(self,src_pts,tgt_pts,flip=False):
        sa,sb,sc=src_pts; ta,tb,tc=tgt_pts
        sx,sy,sn=get_plane_basis(sa,sb,sc); tx,ty,tn=get_plane_basis(ta,tb,tc)
        if flip: ty=-ty; tn=-tn
        return matrix_from_basis(ta,tx,ty,tn)@matrix_from_basis(sa,sx,sy,sn).inverted()

    def _resolve_confirm(self,context,event):
        exp=self._expected()
        hit=_raycast_from_mouse(context,event,getattr(self,"snap_mode","VERTEX"))
        fr=_dict_to_snap_result(hit,context,event) if hit and hit.get("object")==exp else None
        self.store_fresh(fr,self.stage,event)
        res,src=self.get_effective(self.stage,"ALL")
        if res is None or res.object!=exp:
            self.report({"WARNING"},"沒有點到物件表面"); return None,False
        is_s=src in ("sticky","last_valid")
        print(f"[SAP][CONFIRM] three_point stage={self.stage} src={src} type={res.snap_type}")
        return res.snap_location or res.location, is_s

    _STAGE_MAP={"SOURCE_1":"來源第 1 點","SOURCE_2":"來源第 2 點","SOURCE_3":"來源第 3 點","TARGET_1":"目標第 1 點","TARGET_2":"目標第 2 點","TARGET_3":"目標第 3 點預覽"}

    def modal(self,context,event):
        if event.type in {"MIDDLEMOUSE","WHEELUPMOUSE","WHEELDOWNMOUSE","TRACKPADPAN","TRACKPADZOOM","MOUSEROTATE","MOUSESMARTZOOM"}:
            return {"PASS_THROUGH"}
        if event.alt and event.type in {"LEFTMOUSE","MIDDLEMOUSE","RIGHTMOUSE"}:
            return {"PASS_THROUGH"}
        if event.type=="ESC":
            log_operator_end("three_point_modal","cancelled",stage=self.stage)
            overlay_engine.stop(context); return self._cancel(context,"三點對齊已取消")
        if event.type=="SPACE" and event.value=="PRESS":
            log_operator_end("three_point_modal","cancelled",stage=self.stage)
            overlay_engine.stop(context); return self._cancel(context,"三點對齊已取消")
        if event.type=="F" and event.value=="PRESS":
            self.flip_normal=not self.flip_normal
            overlay_engine.update(flip_normal=self.flip_normal)
            self.report({"INFO"},f"翻轉目標法線：{'開啟' if self.flip_normal else '關閉'}"); return {"RUNNING_MODAL"}

        if event.type=="MOUSEMOVE":
            exp=self._expected()
            hit=_raycast_from_mouse(context,event,getattr(self,"snap_mode","VERTEX"))
            if hit and hit.get("object")==exp:
                fr=_dict_to_snap_result(hit,context,event)
            elif exp is not None:
                # Cursor left expected object (hit other obj or miss) — preserve intent
                fr=_nearest_candidate_on_object(context,event,exp,getattr(self,"snap_mode","VERTEX"))
            else:
                fr=None
            self.store_fresh(fr,self.stage,event)
            res,src=self.get_effective(self.stage,"ALL")
            is_s=src in ("sticky","last_valid"); sm=self._sm

            if res and res.object==exp:
                sm.on_sticky() if is_s else (sm.on_live_snap() if res.is_non_ray else sm.on_hover())
                ploc=res.snap_location or res.location
                ppts=list(self.source_points)+list(self.target_points)+[ploc]
                _push_overlay(context,res,self._STAGE_MAP.get(self.stage,self.stage),
                              _snap_mode_label(self.snap_mode),sm,is_s,flip_normal=self.flip_normal,preview_points=ppts,operator=self)
                print(f"[SAP][3PT HOVER] stage={self.stage} src={src} type={res.snap_type}")

                if self.stage=="TARGET_3" and len(self.source_points)==3 and len(self.target_points)==2:
                    try:
                        t=self._compute_three_point_transform(self.source_points,self.target_points+[ploc],self.flip_normal)
                        self._restore_source(); self._apply_preview_matrix(t)
                        context.view_layer.update(); overlay_engine.update_transform(self.source,self.target,t)
                        # TASK 2: triangle plane + normal arrow
                        # NOTE: get_plane_basis already imported at module level — do NOT re-import here
                        try:
                            _, _, plane_n = get_plane_basis(
                                self.target_points[0],
                                self.target_points[1],
                                ploc,
                            )
                            plane_centroid = (self.target_points[0] + self.target_points[1] + ploc) / 3.0
                            overlay_engine.update(
                                plane_preview_points=self.target_points + [ploc],
                                plane_normal_origin=plane_centroid,
                                plane_normal_vec=plane_n,
                                plane_normal_scale=0.6,
                            )
                        except Exception:
                            pass
                        lk="🔒 預覽鎖定 " if is_s else ""
                        _set_header(context,f"三點對齊｜{lk}目標第 3 點：左鍵確認｜F 翻法線｜ESC 取消")
                    except Exception: pass
                elif is_s:
                    _set_header(context,"三點對齊｜🔒 已鎖定最後有效吸附點，左鍵可確認｜F 翻法線｜ESC 取消")
            else:
                sm.on_hover()
                _clear_overlay(context,stage_label=self._STAGE_MAP.get(self.stage,self.stage),snap_mode_label=_snap_mode_label(self.snap_mode))
            return {"RUNNING_MODAL"}

        if event.type=="LEFTMOUSE" and event.value=="PRESS":
            loc,is_s=self._resolve_confirm(context,event)
            if loc is None: return {"RUNNING_MODAL"}

            if self.stage.startswith("SOURCE"):
                log_pick_point("three_point_modal",self.stage,self.source,loc)
                self.source_points.append(loc); count=len(self.source_points)
                overlay_engine.update(stage_label=f"來源第 {min(count+1,3)} 點" if count<3 else "目標第 1 點",points=self.source_points,flip_normal=self.flip_normal)
                if count<3:
                    self.stage=f"SOURCE_{count+1}"
                    _set_header(context,f"三點對齊｜來源: {self.source.name} 點第 {count+1} 點（左鍵）")
                    self.report({"INFO"},f"來源第 {count} 點已記錄")
                else:
                    self.stage="TARGET_1"
                    _set_header(context,f"三點對齊｜目標: {self.target.name} 點第 1 點（左鍵）")
                    self.report({"INFO"},"來源三點完成，請開始點目標三點")
                self.confirm_snap(); self.advance_stage(); self._sm=new_sm(); return {"RUNNING_MODAL"}

            if self.stage.startswith("TARGET"):
                log_pick_point("three_point_modal",self.stage,self.target,loc)
                self.target_points.append(loc); count=len(self.target_points)
                overlay_engine.update(stage_label=f"目標第 {min(count+1,3)} 點" if count<3 else "完成",points=self.source_points+self.target_points,flip_normal=self.flip_normal)
                if count<3:
                    self.stage=f"TARGET_{count+1}"
                    msg="移動滑鼠可看預覽，左鍵確認" if count==2 else "請點下一個目標點"
                    _set_header(context,f"三點對齊｜目標: {self.target.name} 點第 {count+1} 點（{msg}）")
                    self.report({"INFO"},f"目標第 {count} 點已記錄")
                    self.confirm_snap(); self.advance_stage(); self._sm=new_sm(); return {"RUNNING_MODAL"}
                try:
                    t=self._compute_three_point_transform(self.source_points,self.target_points,self.flip_normal)
                    self._restore_source(); self._apply_preview_matrix(t)
                    settings=context.scene.smartalignpro_settings
                    if getattr(settings,"three_point_apply_offset",False) and getattr(settings,"collision_safe_mode",False):
                        _,_,tn=get_plane_basis(*self.target_points)
                        self.source.location+=tn.normalized()*getattr(settings,"small_offset",0.001)
                    context.view_layer.update()
                    print(f"[SAP][三點對齊互動版] {self.source.name} → {self.target.name}")
                    log_operator_end("three_point_modal","finished")
                    overlay_engine.stop(context); return self._finish(context,"三點對齊完成（v7.5.5）")
                except Exception as e:
                    log_operator_end("three_point_modal","error",error=str(e))
                    overlay_engine.stop(context); return self._cancel(context,f"三點對齊失敗：{e}")

        return {"RUNNING_MODAL"}


# ─── Remaining simple operators ───────────────────────────────────────────────

class SMARTALIGNPRO_OT_surface_normal_align(Operator):
    bl_idname="smartalignpro.surface_normal_align"; bl_label="表面法線對齊"
    bl_description="將物件對齊到目標表面法線"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        settings=context.scene.smartalignpro_settings; active=context.active_object
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if active is None or active.type!="MESH":
            self.report({"WARNING"},"請先選取一個目標 Mesh 物件作為 Active Object"); return {"CANCELLED"}
        sources=[o for o in selected if o!=active]
        if not sources:
            self.report({"WARNING"},"找不到來源物件"); return {"CANCELLED"}
        try:
            for s in sources: surface_normal_align_with_raycast(s,active,settings)
            self.report({"INFO"},f"表面法線對齊完成：{len(sources)} 個物件"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},str(e)); return {"CANCELLED"}

class SMARTALIGNPRO_OT_auto_contact_align(Operator):
    bl_idname="smartalignpro.auto_contact_align"; bl_label="接觸對齊"
    bl_description="智慧計算最佳接觸點並對齊"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        settings=context.scene.smartalignpro_settings; active=context.active_object
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if active is None or active.type!="MESH":
            self.report({"WARNING"},"請先選取一個目標 Mesh 物件作為 Active Object"); return {"CANCELLED"}
        sources=[o for o in selected if o!=active]
        if not sources:
            self.report({"WARNING"},"找不到來源物件"); return {"CANCELLED"}
        try:
            for s in sources: auto_contact_align(s,active,settings); print(f"[SAP][接觸對齊] {s.name} → {active.name}")
            self.report({"INFO"},f"接觸對齊完成：{len(sources)} 個物件"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},str(e)); return {"CANCELLED"}

class SMARTALIGNPRO_OT_align_to_ground(Operator):
    bl_idname="smartalignpro.align_to_ground"; bl_label="貼地對齊"
    bl_description="將選取的物件對齊到地面"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        settings=context.scene.smartalignpro_settings
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if not selected:
            self.report({"WARNING"},"請選取至少一個 Mesh 物件"); return {"CANCELLED"}
        try:
            r=align_to_ground(selected,settings)
            self.report({"INFO"},f"貼地對齊完成：{len(r)} 個物件" if r else "沒有找到地面"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},str(e)); return {"CANCELLED"}

class SMARTALIGNPRO_OT_align_to_surface(Operator):
    bl_idname="smartalignpro.align_to_surface"; bl_label="表面對齊"
    bl_description="將選取的物件對齊到表面"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        settings=context.scene.smartalignpro_settings
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if not selected:
            self.report({"WARNING"},"請選取至少一個 Mesh 物件"); return {"CANCELLED"}
        try:
            r=align_to_surface(selected,settings)
            self.report({"INFO"},f"表面對齊完成：{len(r)} 個物件" if r else "沒有找到表面"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},str(e)); return {"CANCELLED"}

class SMARTALIGNPRO_OT_smart_align(Operator):
    bl_idname="smartalignpro.smart_align"; bl_label="智能對齊"
    bl_description="根據物件類型自動選擇最佳對齊策略"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        settings=context.scene.smartalignpro_settings; active=context.active_object
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if active is None or active.type!="MESH":
            self.report({"WARNING"},"請先選取一個目標 Mesh 物件作為 Active Object"); return {"CANCELLED"}
        sources=[o for o in selected if o!=active]
        if not sources:
            self.report({"WARNING"},"找不到來源物件"); return {"CANCELLED"}
        si=get_alignment_strategy_suggestion(detect_object_type(active),settings.alignment_strategy)
        try:
            for s in sources:
                st=si["strategy"]
                if st=="TWO_POINT": two_point_align(s,active,"0","1","0","1")
                elif st=="THREE_POINT": three_point_align(s,active,"0","1","3","0","1","3",settings)
                elif st=="SURFACE_NORMAL": surface_normal_align_with_raycast(s,active,settings)
                elif st=="AUTO_CONTACT": auto_contact_align(s,active,settings)
            self.report({"INFO"},f"智能對齊完成：{len(sources)} 個物件"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},str(e)); return {"CANCELLED"}

class SMARTALIGNPRO_OT_smart_batch_align(Operator):
    bl_idname="smartalignpro.smart_batch_align"; bl_label="批量對齊"
    bl_description="使用指定策略批量對齊多個物件"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        settings=context.scene.smartalignpro_settings
        selected=[o for o in context.selected_objects if o.type=="MESH"]
        if len(selected)<2:
            self.report({"WARNING"},"請選取至少兩個 Mesh 物件"); return {"CANCELLED"}
        target=selected[0]; sources=selected[1:]
        try:
            for s in sources:
                st=settings.alignment_strategy
                if st=="TWO_POINT": two_point_align(s,target,"0","1","0","1")
                elif st=="THREE_POINT": three_point_align(s,target,"0","1","3","0","1","3",settings)
                elif st=="SURFACE_NORMAL": surface_normal_align_with_raycast(s,target,settings)
                elif st=="AUTO_CONTACT": auto_contact_align(s,target,settings)
            self.report({"INFO"},f"批量對齊完成：{len(sources)} 個物件"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},str(e)); return {"CANCELLED"}


# ─── Selector operators ───────────────────────────────────────────────────────

class SMARTALIGNPRO_OT_cad_directional_selector(Operator):
    bl_idname="smartalignpro.cad_directional_selector"; bl_label="CAD 模式 HUD 選擇器"
    bl_description="CAD 模式十字方向選單 - Alt+A（僅限 VIEW_3D / Object Mode）"
    bl_options={"REGISTER","UNDO","BLOCKING"}
    start_mouse_x:IntProperty(default=0); start_mouse_y:IntProperty(default=0)
    current_mode:StringProperty(default=""); current_direction:StringProperty(default="")
    threshold:IntProperty(default=40); hud_selector=None; last_direction=None

    @classmethod
    def poll(cls,context):
        # Item 3: VIEW_3D + OBJECT mode only
        return context.area and context.area.type=="VIEW_3D" and context.mode=="OBJECT"

    def invoke(self,context,event):
        print(f"[SAP][CAD] Alt+A invoke (VIEW_3D/OBJECT)")
        self.report({"INFO"},"CAD 選擇器已啟動")
        self.start_mouse_x=event.mouse_region_x; self.start_mouse_y=event.mouse_region_y
        try:
            from ..ui.hud_selector import hud_selector
            self.hud_selector=hud_selector
        except Exception as e:
            self.report({"ERROR"},f"HUD selector 導入失敗: {e}"); return {"CANCELLED"}
        try:
            self.hud_selector.start(context,self.start_mouse_x,self.start_mouse_y,mode_type="CAD")
        except Exception as e:
            self.report({"ERROR"},f"HUD selector 啟動失敗: {e}"); return {"CANCELLED"}
        self.current_mode=""; self.current_direction=""; self.last_direction=None
        # TASK 3: register selector mode HUD draw handler
        self._sel_hud_handle = None
        try:
            import bpy as _bpy
            self._sel_hud_handle = _bpy.types.SpaceView3D.draw_handler_add(
                self._draw_selector_hud, (context,), "WINDOW", "POST_PIXEL"
            )
        except Exception:
            pass
        context.window_manager.modal_handler_add(self)
        try: context.area.header_text_set(f"CAD 模式：{self.hud_selector.get_mode_name_chinese()}")
        except Exception: pass
        return {"RUNNING_MODAL"}

    def _draw_selector_hud(self, context):
        """TASK 3: draw selector mode + snap priority legend."""
        try:
            import blf, bpy as _bpy
            region = getattr(context, "region", None) or getattr(_bpy.context, "region", None)
            if not region: return
            x = region.width - 280
            y = region.height - 40
            lh = 18
            font_id = 0

            # Title
            blf.size(font_id, 14); blf.color(font_id, 1.0, 0.9, 0.3, 1.0)
            blf.position(font_id, x, y, 0); blf.draw(font_id, "CAD 選擇器模式"); y -= lh

            # Direction → mode
            dir_map = {"UP":"邊對齊","DOWN":"面對齊","LEFT":"CAD 吸附","RIGHT":"CAD 吸附","":"(移動選擇方向)"}
            cur_dir = self.current_direction or ""
            blf.size(font_id, 13); blf.color(font_id, 0.8, 0.95, 0.8, 1.0)
            blf.position(font_id, x, y, 0)
            blf.draw(font_id, f"  {cur_dir or '●'} → {dir_map.get(cur_dir,'?')}"); y -= lh

            # Snap priority legend
            blf.size(font_id, 12); blf.color(font_id, 0.7, 0.85, 1.0, 1.0)
            blf.position(font_id, x, y, 0)
            blf.draw(font_id, "吸附優先順序:"); y -= lh - 2
            priority_items = [
                ("頂點",    (0.2, 1.0, 0.4, 1.0)),
                ("邊中點",  (0.4, 0.9, 0.2, 1.0)),
                ("原點",    (0.8, 0.8, 0.2, 1.0)),
                ("邊",      (0.9, 0.6, 0.2, 1.0)),
                ("面中心",  (0.9, 0.4, 0.2, 1.0)),
                ("面",      (0.9, 0.3, 0.3, 1.0)),
            ]
            for label, col in priority_items:
                blf.size(font_id, 11); blf.color(font_id, *col)
                blf.position(font_id, x + 10, y, 0)
                blf.draw(font_id, f"▶ {label}"); y -= 15

            # Controls reminder
            blf.size(font_id, 11); blf.color(font_id, 0.7, 0.7, 0.7, 1.0)
            blf.position(font_id, x, y - 4, 0)
            blf.draw(font_id, "移動方向選功能 | 放開 A 執行 | ESC 取消")
        except Exception:
            pass

    def modal(self,context,event):
        if event.type=="ESC": return self._cancel_op(context)
        if event.type=="A" and event.value=="RELEASE": return self._execute(context)
        dx=event.mouse_region_x-self.start_mouse_x; dy=event.mouse_region_y-self.start_mouse_y
        dist=(dx**2+dy**2)**0.5
        if dist>self.threshold:
            from ..ui.hud_selector import determine_direction
            nd=determine_direction(dx,dy,self.last_direction,self.start_mouse_x,self.start_mouse_y)
            if nd and nd!=self.last_direction:
                self.last_direction=nd; self.current_direction=nd
                self.hud_selector.update_direction(nd)
                context.area.tag_redraw()
                context.area.header_text_set(f"CAD 模式：{self.hud_selector.get_mode_name_chinese()}")
        else:
            if self.current_direction!="":
                self.current_direction=""; self.last_direction=None
                if self.hud_selector: self.hud_selector.current_direction=""; self.hud_selector.current_mode=""
                context.area.tag_redraw(); context.area.header_text_set("CAD 模式：移回中心可取消")
        return {"RUNNING_MODAL"}

    def _remove_sel_hud(self):
        """Remove selector HUD draw handler."""
        import bpy as _bpy
        if getattr(self, "_sel_hud_handle", None):
            try:
                _bpy.types.SpaceView3D.draw_handler_remove(self._sel_hud_handle, "WINDOW")
            except Exception:
                pass
            self._sel_hud_handle = None

    def _cancel_op(self,context):
        self._remove_sel_hud()
        if self.hud_selector: self.hud_selector.stop(); self.hud_selector=None
        context.area.header_text_set(None); context.area.tag_redraw()
        self.report({"INFO"},"CAD 模式選擇器已取消"); return {"CANCELLED"}

    def _execute(self,context):
        self._remove_sel_hud()
        if self.hud_selector: self.hud_selector.stop(); self.hud_selector=None
        context.area.header_text_set(None); context.area.tag_redraw()
        try:
            if self.current_direction=="": self.report({"INFO"},"未選擇任何 CAD 功能"); return {"CANCELLED"}
            elif self.current_direction=="UP":   bpy.ops.smartalignpro.edge_align(); mn="邊對齊"
            elif self.current_direction=="DOWN":  bpy.ops.smartalignpro.face_align(); mn="面對齊"
            elif self.current_direction in ("LEFT","RIGHT"): bpy.ops.smartalignpro.cad_snap_modal("INVOKE_DEFAULT"); mn="CAD 吸附"
            else: self.report({"WARNING"},f"未知方向: {self.current_direction}"); return {"CANCELLED"}
            self.report({"INFO"},f"執行 {mn}"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},f"執行失敗: {e}"); return {"CANCELLED"}


class SMARTALIGNPRO_OT_directional_wheel_selector(Operator):
    bl_idname="smartalignpro.directional_wheel_selector"; bl_label="智慧對齊 HUD 選擇器"
    bl_description="十字方向選單 + 滾輪混合選擇器"; bl_options={"REGISTER","UNDO","BLOCKING"}
    ALIGNMENT_MODES={"TWO_POINT":"兩點對齊","THREE_POINT":"三點對齊","SURFACE_NORMAL":"表面法線對齊","CONTACT_ALIGN":"接觸對齊"}
    start_mouse_x:IntProperty(default=0); start_mouse_y:IntProperty(default=0)
    current_mode:StringProperty(default="TWO_POINT"); current_direction:StringProperty(default="")
    threshold:IntProperty(default=40); hud_selector=None; last_direction=None

    def invoke(self,context,event):
        self.start_mouse_x=event.mouse_region_x; self.start_mouse_y=event.mouse_region_y
        from ..ui.hud_selector import hud_selector
        self.hud_selector=hud_selector; self.hud_selector.start(context,self.start_mouse_x,self.start_mouse_y)
        self.current_mode="TWO_POINT"; self.current_direction=""; self.last_direction=None
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set(f"智慧對齊模式：{self.hud_selector.get_mode_name_chinese()}")
        return {"RUNNING_MODAL"}

    def modal(self,context,event):
        if event.type=="ESC": return self._cancel_op(context)
        if event.type=="Q" and event.value=="RELEASE": return self._execute(context)
        dx=event.mouse_region_x-self.start_mouse_x; dy=event.mouse_region_y-self.start_mouse_y
        dist=(dx**2+dy**2)**0.5
        if dist>self.threshold:
            from ..ui.hud_selector import determine_direction
            nd=determine_direction(dx,dy,self.last_direction,self.start_mouse_x,self.start_mouse_y)
            if nd and nd!=self.last_direction:
                self.last_direction=nd; self.hud_selector.update_direction(nd)
                self.current_mode=self.hud_selector.get_current_mode(); self.current_direction=nd
                context.area.tag_redraw(); context.area.header_text_set(f"智慧對齊模式：{self.hud_selector.get_mode_name_chinese()}")
        else:
            if self.current_direction!="":
                self.current_direction=""; self.last_direction=None; self.current_mode="TWO_POINT"
                if self.hud_selector: self.hud_selector.current_direction=""; self.hud_selector.current_mode="TWO_POINT"
                context.area.tag_redraw(); context.area.header_text_set("智慧對齊：移回中心可取消")
            if event.type=="WHEELUPMOUSE": self._cycle(True); context.area.header_text_set(f"智慧對齊模式：{self.hud_selector.get_mode_name_chinese()}")
            elif event.type=="WHEELDOWNMOUSE": self._cycle(False); context.area.header_text_set(f"智慧對齊模式：{self.hud_selector.get_mode_name_chinese()}")
        return {"RUNNING_MODAL"}

    def _cancel_op(self,context):
        if self.hud_selector: self.hud_selector.stop(); self.hud_selector=None
        context.area.header_text_set(None); context.area.tag_redraw()
        self.report({"INFO"},"智慧對齊選擇器已取消"); return {"CANCELLED"}

    def _execute(self,context):
        mn=self.ALIGNMENT_MODES.get(self.current_mode,self.current_mode)
        if self.hud_selector: self.hud_selector.stop(); self.hud_selector=None
        context.area.header_text_set(None); context.area.tag_redraw()
        if self.current_direction=="": self.report({"INFO"},"已取消"); return {"CANCELLED"}
        try:
            if self.current_mode=="TWO_POINT": bpy.ops.smartalignpro.two_point_align()
            elif self.current_mode=="THREE_POINT": bpy.ops.smartalignpro.three_point_modal()
            elif self.current_mode=="SURFACE_NORMAL": bpy.ops.smartalignpro.surface_normal_align()
            elif self.current_mode=="CONTACT_ALIGN": bpy.ops.smartalignpro.auto_contact_align()
            self.report({"INFO"},f"執行 {mn}"); return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},f"執行失敗: {e}"); return {"CANCELLED"}

    def _cycle(self,fwd):
        if self.hud_selector:
            from ..ui.hud_selector import cycle_direction
            cd=self.hud_selector.get_current_direction()
            nd="UP" if cd=="" else cycle_direction(cd,forward=fwd)
            self.last_direction=nd; self.hud_selector.update_direction(nd)
            self.current_mode=self.hud_selector.get_current_mode(); self.current_direction=nd
        else:
            ms=list(self.ALIGNMENT_MODES.keys()); i=ms.index(self.current_mode)
            self.current_mode=ms[(i+(1 if fwd else -1))%len(ms)]


# Advanced (Alt+Ctrl+Z) — kept verbatim from v7.5.2
MULTI_ALIGN_SUBMODES=[("ALIGN_TO_ACTIVE","對齊到 Active"),("DISTRIBUTE_EVEN","均勻分布"),("ARRANGE_LINE","排列成行"),("SORT_BY_AXIS","依軸排序")]
PIVOT_SUBMODES=[("ORIGIN_ALIGN","Origin 對齊"),("CURSOR_ALIGN","3D Cursor 對齊"),("LOC_ONLY","只移動位置"),("ROT_ONLY","只修改旋轉")]
VECTOR_SUBMODES=[("AXIS_X","X 軸約束"),("AXIS_Y","Y 軸約束"),("AXIS_Z","Z 軸約束"),("CUSTOM_VEC","自訂向量")]
PREVIEW_SUBMODES=[("PREVIEW","預覽對齊"),("APPLY","應用預覽"),("CLEAR","清除預覽")]
_ADVANCED_SUBMODES={"MULTI_OBJECT_ALIGN":MULTI_ALIGN_SUBMODES,"PIVOT_ALIGN":PIVOT_SUBMODES,"VECTOR_CONSTRAINT":VECTOR_SUBMODES,"PREVIEW_ALIGN":PREVIEW_SUBMODES}
_SUBMODE_OPS={
    "ALIGN_TO_ACTIVE":lambda:bpy.ops.smartalignpro.multi_object_align(alignment_mode="MULTIPLE_TO_TARGET"),
    "DISTRIBUTE_EVEN":lambda:bpy.ops.smartalignpro.multi_object_align(alignment_mode="ARRAY_ALIGNMENT"),
    "ARRANGE_LINE":lambda:bpy.ops.smartalignpro.multi_object_align(alignment_mode="CHAIN_ALIGNMENT"),
    "SORT_BY_AXIS":lambda:bpy.ops.smartalignpro.multi_object_align(alignment_mode="CIRCULAR_ALIGNMENT"),
    "ORIGIN_ALIGN":lambda:bpy.ops.smartalignpro.pivot_align(pivot_type="CENTER"),
    "CURSOR_ALIGN":lambda:bpy.ops.smartalignpro.pivot_align(pivot_type="VERTEX"),
    "LOC_ONLY":lambda:bpy.ops.smartalignpro.pivot_align(pivot_type="EDGE"),
    "ROT_ONLY":lambda:bpy.ops.smartalignpro.pivot_align(pivot_type="FACE"),
    "AXIS_X":lambda:bpy.ops.smartalignpro.vector_constraint_align(constraint_axis="X"),
    "AXIS_Y":lambda:bpy.ops.smartalignpro.vector_constraint_align(constraint_axis="Y"),
    "AXIS_Z":lambda:bpy.ops.smartalignpro.vector_constraint_align(constraint_axis="Z"),
    "CUSTOM_VEC":lambda:bpy.ops.smartalignpro.vector_constraint_align(constraint_type="VECTOR"),
    "PREVIEW":lambda:bpy.ops.smartalignpro.preview_align(),
    "APPLY":lambda:bpy.ops.smartalignpro.apply_preview(),
    "CLEAR":lambda:bpy.ops.smartalignpro.clear_preview(),
}

class SMARTALIGNPRO_OT_advanced_wheel_selector(Operator):
    bl_idname="smartalignpro.advanced_wheel_selector"; bl_label="進階工具 HUD 選擇器"
    bl_description="多物件/支點/向量/預覽 HUD 選單 + 滾輪子模式切換"; bl_options={"REGISTER","UNDO","BLOCKING"}
    start_mouse_x:IntProperty(default=0); start_mouse_y:IntProperty(default=0)
    current_mode:StringProperty(default="MULTI_OBJECT_ALIGN"); current_direction:StringProperty(default="")
    submode_index:IntProperty(default=0); threshold:IntProperty(default=40)
    hud_selector=None; last_direction=None
    def _submodes(self): return _ADVANCED_SUBMODES.get(self.current_mode,[])
    def _subkey(self):
        s=self._submodes(); return s[max(0,min(self.submode_index,len(s)-1))][0] if s else None
    def _sublabel(self):
        s=self._submodes(); return s[max(0,min(self.submode_index,len(s)-1))][1] if s else ""
    def _header(self,context):
        mn={"MULTI_OBJECT_ALIGN":"多物件對齊","PIVOT_ALIGN":"支點對齊","VECTOR_CONSTRAINT":"向量約束","PREVIEW_ALIGN":"預覽控制"}.get(self.current_mode,self.current_mode)
        sl=self._sublabel()
        context.area.header_text_set(f"進階工具：{mn}  ›  {sl}  [滾輪切換]" if sl else f"進階工具：{mn}")
    def invoke(self,context,event):
        self.start_mouse_x=event.mouse_region_x; self.start_mouse_y=event.mouse_region_y
        from ..ui.hud_selector import hud_selector
        self.hud_selector=hud_selector
        self.hud_selector.start(context,self.start_mouse_x,self.start_mouse_y,mode_type="ADVANCED")
        self.current_mode="MULTI_OBJECT_ALIGN"; self.current_direction=""; self.submode_index=0; self.last_direction=None
        context.window_manager.modal_handler_add(self); self._header(context); return {"RUNNING_MODAL"}
    def modal(self,context,event):
        if event.type=="ESC": return self._cancel(context)
        if event.type in {"Z","LEFT_CTRL","RIGHT_CTRL","LEFT_ALT","RIGHT_ALT"} and event.value=="RELEASE": return self._execute(context)
        dx=event.mouse_region_x-self.start_mouse_x; dy=event.mouse_region_y-self.start_mouse_y; dist=(dx**2+dy**2)**0.5
        if dist>self.threshold:
            from ..ui.hud_selector import determine_direction
            nd=determine_direction(dx,dy,self.last_direction,self.start_mouse_x,self.start_mouse_y)
            if nd and nd!=self.last_direction:
                self.last_direction=nd; self.current_direction=nd
                self.hud_selector.update_direction(nd); self.current_mode=self.hud_selector.get_current_mode()
                self.submode_index=0; context.area.tag_redraw(); self._header(context)
        else:
            if self.current_direction!="":
                self.current_direction=""; self.last_direction=None; self.current_mode="MULTI_OBJECT_ALIGN"; self.submode_index=0
                if self.hud_selector: self.hud_selector.current_direction=""; self.hud_selector.current_mode="MULTI_OBJECT_ALIGN"
                context.area.tag_redraw(); self._header(context)
            s=self._submodes()
            if event.type=="WHEELUPMOUSE" and s: self.submode_index=(self.submode_index-1)%len(s); self._header(context)
            elif event.type=="WHEELDOWNMOUSE" and s: self.submode_index=(self.submode_index+1)%len(s); self._header(context)
        return {"RUNNING_MODAL"}
    def _cancel(self,context):
        if self.hud_selector: self.hud_selector.stop(); self.hud_selector=None
        context.area.header_text_set(None); context.area.tag_redraw()
        self.report({"INFO"},"進階工具選擇器已取消"); return {"CANCELLED"}
    def _execute(self,context):
        if self.hud_selector: self.hud_selector.stop(); self.hud_selector=None
        context.area.header_text_set(None); context.area.tag_redraw()
        if self.current_direction=="": self.report({"INFO"},"已取消"); return {"CANCELLED"}
        key=self._subkey(); label=self._sublabel() or self.current_mode
        try:
            if key and key in _SUBMODE_OPS:
                _SUBMODE_OPS[key](); self.report({"INFO"},f"執行：{label}"); return {"FINISHED"}
            self.report({"WARNING"},f"尚未實作：{label}"); return {"CANCELLED"}
        except Exception as e:
            self.report({"ERROR"},f"執行失敗：{e}"); return {"CANCELLED"}
