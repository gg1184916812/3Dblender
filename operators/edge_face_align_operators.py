"""
Smart Align Pro - Edge / Face / Orientation 對齊操作器
新增真正工程級入口：
- Edge → Edge 對齊
- Face → Face 對齊
- 複製旋轉 / 位置 / 縮放
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty
from mathutils import Vector, Matrix


AXIS_EPSILON = 1e-8


def _selected_mesh_edit_objects(context):
    return [obj for obj in context.selected_objects if obj and obj.type == "MESH"]



def _validate_two_mesh_objects(context, operator_name):
    """驗證兩個 Mesh 物件。Edit Mode 用選取面，Object Mode 用自動最大面。"""
    active = context.active_object

    if context.mode == "EDIT_MESH":
        # Edit Mode：原有邏輯，用 BMesh 選取面
        selected = _selected_mesh_edit_objects(context)
        if len(selected) != 2:
            raise RuntimeError(f"{operator_name} 需要剛好選取 2 個 Mesh 物件")
        if active is None or active.type != "MESH":
            raise RuntimeError("Active Object 必須是目標 Mesh")
        source = next((obj for obj in selected if obj != active), None)
        if source is None:
            raise RuntimeError("找不到來源物件，請先選來源，再將目標設成 Active Object")
        return source, active
    else:
        # Object Mode：用 selected_objects
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if len(selected) < 2:
            raise RuntimeError(f"{operator_name} 至少需要 2 個選取的 Mesh 物件")
        if active is None or active.type != "MESH":
            raise RuntimeError("Active Object 必須是目標 Mesh")
        source = next((obj for obj in selected if obj != active), None)
        if source is None:
            raise RuntimeError("找不到來源物件")
        return source, active



def _selected_edges_world(obj):
    bm = bmesh.from_edit_mesh(obj.data)
    edges = [e for e in bm.edges if e.select]
    if len(edges) != 1:
        raise RuntimeError(f"物件「{obj.name}」必須剛好選取 1 條邊")

    e = edges[0]
    p0 = obj.matrix_world @ e.verts[0].co.copy()
    p1 = obj.matrix_world @ e.verts[1].co.copy()

    normal = Vector((0.0, 0.0, 0.0))
    if len(e.link_faces) > 0:
        for f in e.link_faces:
            normal += obj.matrix_world.to_3x3() @ f.normal
        if normal.length > AXIS_EPSILON:
            normal.normalize()
    return {
        "edge": e,
        "p0": p0,
        "p1": p1,
        "mid": (p0 + p1) * 0.5,
        "dir": (p1 - p0).normalized(),
        "normal": normal if normal.length > AXIS_EPSILON else None,
    }



def _selected_face_world(obj):
    """取得物件的對齊面資訊。
    Edit Mode：用使用者選取的那個面。
    Object Mode：自動取面積最大的面（最有代表性）。
    """
    import bpy
    import bmesh as _bmesh

    if bpy.context.mode == "EDIT_MESH":
        # Edit Mode 原有邏輯
        bm = _bmesh.from_edit_mesh(obj.data)
        faces = [f for f in bm.faces if f.select]
        if len(faces) != 1:
            raise RuntimeError(f"物件「{obj.name}」必須剛好選取 1 個面（目前選了 {len(faces)} 個）")
        f_data = faces[0]
        verts_world = [obj.matrix_world @ v.co.copy() for v in f_data.verts]
        normal = (obj.matrix_world.to_3x3() @ f_data.normal).normalized()
    else:
        # Object Mode：取面積最大的面
        bm = _bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        if not bm.faces:
            bm.free()
            raise RuntimeError(f"物件「{obj.name}」沒有任何面")
        f_data = max(bm.faces, key=lambda f: f.calc_area())
        verts_world = [obj.matrix_world @ v.co.copy() for v in f_data.verts]
        normal = (obj.matrix_world.to_3x3() @ f_data.normal).normalized()
        bm.free()

    center = sum(verts_world, Vector((0.0, 0.0, 0.0))) / len(verts_world)

    primary = None
    longest = -1.0
    loop_count = len(verts_world)
    for i in range(loop_count):
        a = verts_world[i]
        b = verts_world[(i + 1) % loop_count]
        edge_vec = b - a
        length = edge_vec.length
        if length > longest and length > AXIS_EPSILON:
            longest = length
            primary = edge_vec.normalized()

    if primary is None:
        raise RuntimeError(f"物件「{obj.name}」的面無法建立主方向")

    secondary = normal.cross(primary)
    if secondary.length <= AXIS_EPSILON:
        raise RuntimeError(f"物件「{obj.name}」的面法線與主方向異常")
    secondary.normalize()

    primary = secondary.cross(normal)
    primary.normalize()

    return {
        "face": f_data,
        "center": center,
        "normal": normal,
        "primary": primary,
        "secondary": secondary,
    }



def _make_basis(origin, x_axis, y_axis, z_axis):
    return Matrix((
        (x_axis.x, y_axis.x, z_axis.x, origin.x),
        (x_axis.y, y_axis.y, z_axis.y, origin.y),
        (x_axis.z, y_axis.z, z_axis.z, origin.z),
        (0.0, 0.0, 0.0, 1.0),
    ))



def _apply_matrix_to_object(source_obj, transform):
    source_obj.matrix_world = transform @ source_obj.matrix_world


"""
Smart Align Pro - Edge / Face / Orientation 對齊操作器
新增真正工程級入口：
- Edge → Edge 對齊
- Face → Face 對齊
- 複製旋轉 / 位置 / 縮放
"""

import bpy
import bmesh
from bpy.types import Operator
from bpy.props import BoolProperty, EnumProperty
from mathutils import Vector, Matrix
from ..core.solver_manager import solve_alignment


AXIS_EPSILON = 1e-8


class SMARTALIGNPRO_OT_edge_align_quick(Operator):
    """快速邊對齊（基於邊界框）"""
    bl_idname = "smartalignpro.edge_align_quick"
    bl_label = "快速邊對齊"
    bl_description = "基於邊界框的快速邊對齊"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print(f"[SmartAlignPro][OPERATOR] edge_align_quick executed")
        
        # 獲取選中的物件
        selected = context.selected_objects
        active = context.active_object
        
        if len(selected) < 2 or not active:
            self.report({"WARNING"}, "需要選擇至少 2 個物件，其中一個為活動物件")
            return {"CANCELLED"}
        
        # 設置來源和目標
        # Active Object = 目標（不動），非Active = 來源（移動）
        target_obj = active if active in selected else selected[0]
        source_obj = next((obj for obj in selected if obj != target_obj), None)
        
        if not target_obj:
            self.report({"WARNING"}, "找不到目標物件")
            return {"CANCELLED"}
        
        print(f"[SmartAlignPro][OPERATOR] Quick edge align: {source_obj.name} → {target_obj.name}")
        
        # 使用 solver manager 執行邊對齊
        result = solve_alignment("EDGE_ALIGN", source_obj, target_obj, mode="CAD")
        
        if result.get('success', True):
            self.report({"INFO"}, f"快速邊對齊完成：{source_obj.name} → {target_obj.name}")
        else:
            self.report({"ERROR"}, f"邊對齊失敗：{result.get('error', '未知錯誤')}")
            return {"CANCELLED"}
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_edge_align_cad(Operator):
    """CAD 模式邊對齊（支援互動式選取）"""
    bl_idname = "smartalignpro.edge_align_cad"
    bl_label = "CAD 邊對齊"
    bl_description = "CAD 模式的邊對齊，支援精確邊選取"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print(f"[SmartAlignPro][OPERATOR] edge_align_cad executed")
        
        # 獲取選中的物件
        selected = context.selected_objects
        active = context.active_object
        
        if len(selected) < 2 or not active:
            self.report({"WARNING"}, "需要選擇至少 2 個物件，其中一個為活動物件")
            return {"CANCELLED"}
        
        # 設置來源和目標
        # Active Object = 目標（不動），非Active = 來源（移動）
        target_obj = active if active in selected else selected[0]
        source_obj = next((obj for obj in selected if obj != target_obj), None)
        
        if not target_obj:
            self.report({"WARNING"}, "找不到目標物件")
            return {"CANCELLED"}
        
        print(f"[SmartAlignPro][OPERATOR] CAD edge align: {source_obj.name} → {target_obj.name}")
        
        # 使用 solver manager 執行 CAD 邊對齊
        settings = context.scene.smartalignpro_settings
        result = solve_alignment("EDGE_ALIGN", source_obj, target_obj, mode="CAD", settings=settings)
        
        if result.get('success', True):
            self.report({"INFO"}, f"CAD 邊對齊完成：{source_obj.name} → {target_obj.name}")
        else:
            self.report({"ERROR"}, f"CAD 邊對齊失敗：{result.get('error', '未知錯誤')}")
            return {"CANCELLED"}
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_face_align_quick(Operator):
    """快速面對齊（基於邊界框）"""
    bl_idname = "smartalignpro.face_align_quick"
    bl_label = "快速面對齊"
    bl_description = "基於邊界框的快速面對齊"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print(f"[SmartAlignPro][OPERATOR] face_align_quick executed")
        
        # 獲取選中的物件
        selected = context.selected_objects
        active = context.active_object
        
        if len(selected) < 2 or not active:
            self.report({"WARNING"}, "需要選擇至少 2 個物件，其中一個為活動物件")
            return {"CANCELLED"}
        
        # 設置來源和目標
        # Active Object = 目標（不動），非Active = 來源（移動）
        target_obj = active if active in selected else selected[0]
        source_obj = next((obj for obj in selected if obj != target_obj), None)
        
        if not target_obj:
            self.report({"WARNING"}, "找不到目標物件")
            return {"CANCELLED"}
        
        print(f"[SmartAlignPro][OPERATOR] Quick face align: {source_obj.name} → {target_obj.name}")
        
        # 使用 solver manager 執行面對齊
        result = solve_alignment("FACE_ALIGN", source_obj, target_obj, mode="CAD")
        
        if result.get('success', True):
            self.report({"INFO"}, f"快速面對齊完成：{source_obj.name} → {target_obj.name}")
        else:
            self.report({"ERROR"}, f"面對齊失敗：{result.get('error', '未知錯誤')}")
            return {"CANCELLED"}
        
        return {"FINISHED"}


class SMARTALIGNPRO_OT_face_align_cad(Operator):
    """CAD 模式面對齊（支援互動式選取）"""
    bl_idname = "smartalignpro.face_align_cad"
    bl_label = "CAD 面對齊"
    bl_description = "CAD 模式的面對齊，支援精確面選取"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print(f"[SmartAlignPro][OPERATOR] face_align_cad executed")
        
        # 獲取選中的物件
        selected = context.selected_objects
        active = context.active_object
        
        if len(selected) < 2 or not active:
            self.report({"WARNING"}, "需要選擇至少 2 個物件，其中一個為活動物件")
            return {"CANCELLED"}
        
        # 設置來源和目標
        # Active Object = 目標（不動），非Active = 來源（移動）
        target_obj = active if active in selected else selected[0]
        source_obj = next((obj for obj in selected if obj != target_obj), None)
        
        if not target_obj:
            self.report({"WARNING"}, "找不到目標物件")
            return {"CANCELLED"}
        
        print(f"[SmartAlignPro][OPERATOR] CAD face align: {source_obj.name} → {target_obj.name}")
        
        # 使用 solver manager 執行 CAD 面對齊
        settings = context.scene.smartalignpro_settings
        result = solve_alignment("FACE_ALIGN", source_obj, target_obj, mode="CAD", settings=settings)
        
        if result.get('success', True):
            self.report({"INFO"}, f"CAD 面對齊完成：{source_obj.name} → {target_obj.name}")
        else:
            self.report({"ERROR"}, f"CAD 面對齊失敗：{result.get('error', '未知錯誤')}")
            return {"CANCELLED"}
        
        return {"FINISHED"}
    bl_description = "在多物件編輯模式下，來源 1 條邊對齊到目標 1 條邊"
    bl_options = {"REGISTER", "UNDO"}

    flip_target_direction: bpy.props.BoolProperty(
        name="反轉目標方向",
        description="若方向顛倒，可啟用以反轉目標邊方向",
        default=False,
    )

    align_normals: bpy.props.BoolProperty(
        name="盡量對齊相鄰面法線",
        description="若兩條邊都有相鄰面，會再嘗試補正繞邊軸旋轉",
        default=True,
    )

    def execute(self, context):
        try:
            source_obj, target_obj = _validate_two_mesh_objects(context, "邊對邊對齊")
            src = _selected_edges_world(source_obj)
            tgt = _selected_edges_world(target_obj)

            target_dir = tgt["dir"].copy()
            if self.flip_target_direction:
                target_dir.negate()

            rot_main = src["dir"].rotation_difference(target_dir).to_matrix().to_4x4()

            src_mid_after_main = rot_main @ src["mid"]
            transform = Matrix.Translation(tgt["mid"] - src_mid_after_main) @ rot_main

            if self.align_normals and src["normal"] is not None and tgt["normal"] is not None:
                src_normal_after_main = (rot_main.to_3x3() @ src["normal"]).normalized()
                projected_src = (src_normal_after_main - src_normal_after_main.dot(target_dir) * target_dir)
                projected_tgt = (tgt["normal"] - tgt["normal"].dot(target_dir) * target_dir)
                if projected_src.length > AXIS_EPSILON and projected_tgt.length > AXIS_EPSILON:
                    projected_src.normalize()
                    projected_tgt.normalize()
                    angle = projected_src.angle(projected_tgt, 0.0)
                    cross = projected_src.cross(projected_tgt)
                    if cross.dot(target_dir) < 0.0:
                        angle = -angle
                    rot_twist = Matrix.Rotation(angle, 4, target_dir)
                    src_mid_after_twist = (Matrix.Translation(tgt["mid"]) @ rot_twist @ Matrix.Translation(-tgt["mid"]) @ transform) @ src["mid"]
                    fix_translation = Matrix.Translation(tgt["mid"] - src_mid_after_twist)
                    transform = fix_translation @ Matrix.Translation(tgt["mid"]) @ rot_twist @ Matrix.Translation(-tgt["mid"]) @ transform

            bpy.ops.object.mode_set(mode="OBJECT")
            _apply_matrix_to_object(source_obj, transform)
            bpy.ops.object.mode_set(mode="EDIT")

            self.report({"INFO"}, f"邊對邊對齊完成：{source_obj.name} → {target_obj.name}")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_face_align(Operator):
    """以來源選取面對齊到目標選取面"""
    bl_idname = "smartalignpro.face_align"
    bl_label = "面對面對齊"
    bl_description = "在多物件編輯模式下，來源 1 個面對齊到目標 1 個面"
    bl_options = {"REGISTER", "UNDO"}

    flip_target_normal: bpy.props.BoolProperty(
        name="反轉目標法線",
        description="若方向相反，可反轉目標面法線",
        default=False,
    )

    def execute(self, context):
        try:
            source_obj, target_obj = _validate_two_mesh_objects(context, "面對面對齊")
            src = _selected_face_world(source_obj)
            tgt = _selected_face_world(target_obj)

            target_normal = tgt["normal"].copy()
            target_secondary = tgt["secondary"].copy()
            if self.flip_target_normal:
                target_normal.negate()
                target_secondary.negate()

            src_basis = _make_basis(src["center"], src["primary"], src["secondary"], src["normal"])
            tgt_basis = _make_basis(tgt["center"], tgt["primary"], target_secondary, target_normal)
            transform = tgt_basis @ src_basis.inverted()

            was_edit = (context.mode == "EDIT_MESH")
            if was_edit:
                bpy.ops.object.mode_set(mode="OBJECT")
            _apply_matrix_to_object(source_obj, transform)
            if was_edit:
                bpy.ops.object.mode_set(mode="EDIT")

            mode_hint = "（Edit Mode 精確面選取）" if was_edit else "（Object Mode 自動最大面）"
            self.report({"INFO"}, f"面對面對齊完成：{source_obj.name} → {target_obj.name} {mode_hint}")
            return {"FINISHED"}

        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_copy_rotation_only(Operator):
    """僅複製旋轉"""
    bl_idname = "smartalignpro.copy_rotation_only"
    bl_label = "只複製旋轉"
    bl_description = "將來源物件旋轉複製成目標物件旋轉"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.active_object
        selected = _selected_mesh_edit_objects(context) if context.mode == "EDIT_MESH" else [obj for obj in context.selected_objects if obj.type == "MESH"]

        if active is None or active.type != "MESH":
            self.report({"WARNING"}, "請先選取目標 Mesh 作為 Active Object")
            return {"CANCELLED"}

        sources = [obj for obj in selected if obj != active]
        if not sources:
            self.report({"WARNING"}, "至少需要 1 個來源物件")
            return {"CANCELLED"}

        for source in sources:
            source.rotation_mode = active.rotation_mode
            source.rotation_euler = active.rotation_euler.copy()
            if hasattr(source, "rotation_quaternion") and active.rotation_mode == "QUATERNION":
                source.rotation_quaternion = active.rotation_quaternion.copy()

        self.report({"INFO"}, f"已複製旋轉到 {len(sources)} 個來源物件")
        return {"FINISHED"}


class SMARTALIGNPRO_OT_copy_location_only(Operator):
    """僅複製位置"""
    bl_idname = "smartalignpro.copy_location_only"
    bl_label = "只複製位置"
    bl_description = "將來源物件位置複製成目標物件位置"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]

        if active is None or active.type != "MESH":
            self.report({"WARNING"}, "請先選取目標 Mesh 作為 Active Object")
            return {"CANCELLED"}

        sources = [obj for obj in selected if obj != active]
        if not sources:
            self.report({"WARNING"}, "至少需要 1 個來源物件")
            return {"CANCELLED"}

        for source in sources:
            source.location = active.location.copy()

        self.report({"INFO"}, f"已複製位置到 {len(sources)} 個來源物件")
        return {"FINISHED"}


class SMARTALIGNPRO_OT_copy_scale_only(Operator):
    """僅複製縮放"""
    bl_idname = "smartalignpro.copy_scale_only"
    bl_label = "只複製縮放"
    bl_description = "將來源物件縮放複製成目標物件縮放"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]

        if active is None or active.type != "MESH":
            self.report({"WARNING"}, "請先選取目標 Mesh 作為 Active Object")
            return {"CANCELLED"}

        sources = [obj for obj in selected if obj != active]
        if not sources:
            self.report({"WARNING"}, "至少需要 1 個來源物件")
            return {"CANCELLED"}

        for source in sources:
            source.scale = active.scale.copy()

        self.report({"INFO"}, f"已複製縮放到 {len(sources)} 個來源物件")
        return {"FINISHED"}


class SMARTALIGNPRO_OT_edge_align(Operator):
    """邊對齊（統一入口，自動選擇 Quick 或 CAD 模式）"""
    bl_idname = "smartalignpro.edge_align"
    bl_label = "邊對齊"
    bl_description = "邊對齊（依設定自動選擇 Quick 或 CAD 模式）"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        print(f"[SmartAlignPro][OPERATOR] edge_align (unified) executed")

        selected = context.selected_objects
        active = context.active_object

        if len(selected) < 2 or not active:
            self.report({"WARNING"}, "需要選擇至少 2 個物件，其中一個為活動物件")
            return {"CANCELLED"}

        # Active Object = 目標（不動），非Active = 來源（移動）
        target_obj = active if active in selected else selected[0]
        source_obj = next((obj for obj in selected if obj != target_obj), None)

        if not target_obj:
            self.report({"WARNING"}, "找不到目標物件")
            return {"CANCELLED"}

        print(f"[SmartAlignPro][OPERATOR] Edge align (unified): {source_obj.name} → {target_obj.name}")

        result = solve_alignment("EDGE_ALIGN", source_obj, target_obj, mode="CAD")

        if result.get('success', True):
            self.report({"INFO"}, f"邊對齊完成：{source_obj.name} → {target_obj.name}")
        else:
            self.report({"ERROR"}, f"邊對齊失敗：{result.get('error', '未知錯誤')}")
            return {"CANCELLED"}

        return {"FINISHED"}
