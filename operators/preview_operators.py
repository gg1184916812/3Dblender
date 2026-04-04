"""
Smart Align Pro - 預覽系統操作器模組
包含預覽相關的操作器和處理函數
"""

import bpy
import blf
from bpy.types import Operator
from mathutils import Matrix, Vector
from ..core.alignment import (
    two_point_align, three_point_align, surface_normal_align_with_raycast,
    auto_contact_align
)
from ..utils.debug_logger import log_operator_start, log_operator_end, log_object_pair, log_single_object_state

preview_data = {}
preview_handlers = []

class PreviewData:
    def __init__(self, obj_name, original_matrix, preview_matrix, strategy="UNDEFINED"):
        self.obj_name = obj_name
        self.original_matrix = original_matrix
        self.preview_matrix = preview_matrix
        self.material_overrides = {}
        self.strategy = strategy

def _matrices_different(a: Matrix, b: Matrix, eps: float = 1e-6):
    for i in range(4):
        for j in range(4):
            if abs(a[i][j] - b[i][j]) > eps:
                return True
    return False

def clear_all_previews_internal(context):
    global preview_data, preview_handlers
    for obj_name, data in list(preview_data.items()):
        obj = bpy.data.objects.get(obj_name)
        if obj:
            obj.matrix_world = data.original_matrix.copy()
            if getattr(obj.data, "materials", None) is not None:
                obj.data.materials.clear()
                for mat in data.material_overrides:
                    obj.data.materials.append(mat)
            obj.show_transparent = False
            obj.show_wire = False
    preview_data.clear()
    for handler in preview_handlers:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
        except Exception:
            pass
    preview_handlers.clear()
    if hasattr(context.scene.smartalignpro_settings, 'preview_mode'):
        context.scene.smartalignpro_settings.preview_mode = False

class SMARTALIGNPRO_OT_preview_align(Operator):
    bl_idname = "smartalignpro.preview_align"
    bl_label = "預覽對齊"
    bl_description = "建立可見的預覽對齊結果"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    def execute(self, context):
        log_operator_start("preview_align", context)
        settings = context.scene.smartalignpro_settings
        clear_all_previews_internal(context)

        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if active is None or active.type != "MESH":
            self.report({"WARNING"}, "請先選取一個目標 Mesh 物件作為 Active Object")
            return {"CANCELLED"}
        if len(selected) < 2:
            self.report({"WARNING"}, "請至少選取兩個 Mesh 物件")
            return {"CANCELLED"}

        sources = [obj for obj in selected if obj != active]
        if not sources:
            self.report({"WARNING"}, "找不到來源物件")
            return {"CANCELLED"}

        try:
            for source in sources:
                log_object_pair("preview_align", source, active, "before_preview", alignment_strategy=getattr(settings, "alignment_strategy", "AUTO_CONTACT"))
                original_matrix = source.matrix_world.copy()
                strategy = getattr(settings, "alignment_strategy", "AUTO_CONTACT") or "AUTO_CONTACT"

                # compute a preview transform using configured strategy; fallback to contact preview
                if strategy == "TWO_POINT":
                    two_point_align(source, active,
                                    settings.two_point_source_a, settings.two_point_source_b,
                                    settings.two_point_target_a, settings.two_point_target_b)
                elif strategy == "THREE_POINT":
                    three_point_align(source, active,
                                      settings.three_point_source_a, settings.three_point_source_b, settings.three_point_source_c,
                                      settings.three_point_target_a, settings.three_point_target_b, settings.three_point_target_c,
                                      settings)
                elif strategy == "SURFACE_NORMAL":
                    surface_normal_align_with_raycast(source, active, settings)
                else:
                    strategy = "AUTO_CONTACT"
                    auto_contact_align(source, active, settings)

                preview_matrix = source.matrix_world.copy()

                # fallback if strategy produced no visible change
                if not _matrices_different(original_matrix, preview_matrix):
                    strategy = "CENTER_OFFSET_FALLBACK"
                    offset = active.matrix_world.translation - source.matrix_world.translation
                    preview_matrix = Matrix.Translation(offset) @ source.matrix_world

                source.matrix_world = original_matrix.copy()
                preview_data[source.name] = PreviewData(source.name, original_matrix, preview_matrix, strategy=strategy)
                log_single_object_state("preview_align", "preview_matrix_captured", source, preview_matrix=preview_matrix)
                print(f"[SmartAlignPro][PREVIEW DEBUG] captured preview matrix for {source.name} | original={tuple(round(v,4) for v in original_matrix.translation)} | preview={tuple(round(v,4) for v in preview_matrix.translation)} | strategy={strategy}")

                self.apply_preview_material(source)
                source.matrix_world = preview_matrix.copy()
                print(f"[SmartAlignPro][PREVIEW DEBUG] visible preview active for {source.name} | location={tuple(round(v,4) for v in source.matrix_world.translation)}")

            settings.preview_mode = True
            self.add_preview_handlers(context)
            self.report({"INFO"}, f"預覽創建完成：{len(sources)} 個物件")
            log_operator_end("preview_align", "finished", preview_count=len(sources))
            context.window_manager.modal_handler_add(self)
            return {"RUNNING_MODAL"}
        except Exception as e:
            clear_all_previews_internal(context)
            log_operator_end("preview_align", "error", error=str(e))
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

    def modal(self, context, event):
        try:
            if event.type == "ESC" and event.value == "PRESS":
                print("[SmartAlignPro][PREVIEW DEBUG] ESC -> clear")
                clear_all_previews_internal(context)
                self.report({"INFO"}, "已取消預覽")
                return {"CANCELLED"}
            if event.type == "SPACE" and event.value == "PRESS":
                clear_all_previews_internal(context)
                self.report({"INFO"}, "已取消預覽")
                return {"CANCELLED"}
            if event.alt and event.type == "LEFTMOUSE" and event.value == "PRESS":
                print("[SmartAlignPro][PREVIEW DEBUG] ALT+LMB -> APPLY PREVIEW")
                return bpy.ops.smartalignpro.apply_preview()
            if event.alt and event.type == "RIGHTMOUSE" and event.value == "PRESS":
                print("[SmartAlignPro][PREVIEW DEBUG] ALT+RMB -> CLEAR PREVIEW")
                clear_all_previews_internal(context)
                self.report({"INFO"}, "已清除預覽")
                return {"CANCELLED"}
            return {"RUNNING_MODAL"}
        except Exception as e:
            print(f"[SmartAlignPro][PREVIEW DEBUG] modal exception: {e}")
            self.report({"ERROR"}, f"預覽 modal 錯誤: {e}")
            clear_all_previews_internal(context)
            return {"CANCELLED"}

    def apply_preview_material(self, obj):
        if obj.name not in preview_data:
            return
        preview_mat = bpy.data.materials.new(name="SmartAlignPreview")
        preview_mat.use_nodes = True
        preview_mat.node_tree.nodes.clear()
        output_node = preview_mat.node_tree.nodes.new(type="ShaderNodeOutputMaterial")
        principled_bsdf = preview_mat.node_tree.nodes.new(type="ShaderNodeBsdfPrincipled")
        principled_bsdf.inputs["Base Color"].default_value = (0.2, 0.5, 1.0, 0.8)
        principled_bsdf.inputs["Alpha"].default_value = 0.35
        principled_bsdf.inputs["Roughness"].default_value = 0.2
        preview_mat.blend_method = 'BLEND'
        preview_mat.node_tree.links.new(principled_bsdf.outputs["BSDF"], output_node.inputs["Surface"])
        preview_data[obj.name].material_overrides = obj.data.materials[:]
        obj.data.materials.clear()
        obj.data.materials.append(preview_mat)
        obj.show_transparent = True
        obj.show_wire = True

    def add_preview_handlers(self, context):
        handler = bpy.types.SpaceView3D.draw_handler_add(
            self.draw_preview_info, (context,), 'WINDOW', 'POST_PIXEL'
        )
        preview_handlers.append(handler)

    def draw_preview_info(self, context):
        if not preview_data:
            return
        try:
            blf.size(0, 12)
        except TypeError:
            blf.size(0, 12, 72)
        blf.position(0, 10, 10, 0)
        blf.draw(0, f"預覽模式 - {len(preview_data)} 個物件")
        strategy = next(iter(preview_data.values())).strategy if preview_data else "UNDEFINED"
        blf.position(0, 10, 25, 0)
        blf.draw(0, f"策略: {strategy}")
        blf.position(0, 10, 40, 0)
        blf.draw(0, "Alt+左鍵套用 | Alt+右鍵/ESC 取消")

class SMARTALIGNPRO_OT_apply_preview(Operator):
    bl_idname = "smartalignpro.apply_preview"
    bl_label = "應用預覽"
    bl_description = "應用預覽的對齊結果"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if not preview_data:
            self.report({"WARNING"}, "沒有預覽可以應用")
            return {"CANCELLED"}
        try:
            applied_count = 0
            for obj_name, data in list(preview_data.items()):
                obj = bpy.data.objects.get(obj_name)
                if obj:
                    obj.matrix_world = data.preview_matrix.copy()
                    obj.data.materials.clear()
                    for mat in data.material_overrides:
                        obj.data.materials.append(mat)
                    obj.show_transparent = False
                    obj.show_wire = False
                    applied_count += 1
            preview_data.clear()
            for handler in preview_handlers:
                try:
                    bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
                except Exception:
                    pass
            preview_handlers.clear()
            context.scene.smartalignpro_settings.preview_mode = False
            self.report({"INFO"}, f"預覽應用完成：{applied_count} 個物件")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

class SMARTALIGNPRO_OT_clear_preview(Operator):
    bl_idname = "smartalignpro.clear_preview"
    bl_label = "清除預覽"
    bl_description = "清除所有預覽"

    def execute(self, context):
        clear_all_previews_internal(context)
        self.report({"INFO"}, "預覽已清除")
        return {"FINISHED"}

classes = (
    SMARTALIGNPRO_OT_preview_align,
    SMARTALIGNPRO_OT_apply_preview,
    SMARTALIGNPRO_OT_clear_preview,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    clear_all_previews_internal(bpy.context)
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


# 相容舊版清理 API
def remove_preview_handlers():
    try:
        ctx = bpy.context
    except Exception:
        ctx = None
    if ctx is not None:
        clear_all_previews_internal(ctx)
    else:
        global preview_data, preview_handlers
        preview_data.clear()
        for handler in preview_handlers:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
            except Exception:
                pass
        preview_handlers.clear()


def remove_preview_data():
    remove_preview_handlers()
