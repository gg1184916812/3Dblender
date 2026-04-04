"""
Smart Align Pro - 多物件對齊操作器
實現真正的 CAD 級多物件對齊功能
"""

import bpy
from mathutils import Vector
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, BoolProperty, IntProperty, FloatProperty
from ..core.multi_object_solver import multi_object_solver
from ..core.orientation_solver import orientation_solver
from ..utils.icon_safe import safe_icon
from ..utils.debug_logger import log_operator_start, log_operator_end, log_object_pair, log_single_object_state

def _bbox_center_world(obj):
    """取得物件在世界座標的 bbox 中心（正確版）"""
    return sum((obj.matrix_world @ Vector(c) for c in obj.bound_box), Vector()) / 8


class SMARTALIGNPRO_OT_multi_object_align(Operator):
    """多物件對齊操作器"""
    bl_idname = "smartalignpro.multi_object_align"
    bl_label = "多物件對齊"
    bl_description = "CAD 級多物件對齊 (A+B → C, Group → target)"
    bl_options = {"REGISTER", "UNDO"}

    # 對齊模式
    alignment_mode: EnumProperty(
        name="對齊模式",
        description="多物件對齊模式",
        items=[
            ("SINGLE_TO_TARGET", "單物件到目標", "每個物件單獨對齊到目標"),
            ("MULTIPLE_TO_TARGET", "多物件到目標", "所有物件整體對齊到目標"),
            ("GROUP_TO_TARGET", "群組到目標", "將群組整體對齊到目標"),
            ("CHAIN_ALIGNMENT", "鏈式對齊", "A→B→C→... 鏈式對齊"),
            ("CIRCULAR_ALIGNMENT", "圓形排列", "圍繞目標圓形排列"),
            ("ARRAY_ALIGNMENT", "線性陣列", "線性陣列排列"),
        ],
        default="MULTIPLE_TO_TARGET",
    )
    
    # 對齊類型
    alignment_type: EnumProperty(
        name="對齊類型",
        description="對齊方式",
        items=[
            ("TWO_POINT", "兩點對齊", "使用兩點對齊"),
            ("THREE_POINT", "三點對齊", "使用三點對齊"),
            ("SURFACE_NORMAL", "表面法線", "表面法線對齊"),
            ("CENTER", "中心對齊", "中心點對齊"),
        ],
        default="CENTER",
    )
    
    # 陣列參數
    array_spacing: bpy.props.FloatProperty(
        name="陣列間距",
        description="陣列物件間的間距",
        default=2.0,
        min=0.1,
        max=10.0,
    )
    
    circular_radius: bpy.props.FloatProperty(
        name="圓形半徑",
        description="圓形排列的半徑",
        default=3.0,
        min=0.5,
        max=20.0,
    )
    
    def execute(self, context):
        """執行多物件對齊"""
        log_operator_start("multi_object_align", context, alignment_mode=self.alignment_mode, alignment_type=self.alignment_type)
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if len(selected) < 2:
            self.report({"WARNING"}, "請至少選取兩個 Mesh 物件")
            return {"CANCELLED"}
        
        # Active Object 作為目標（比 selected[-1] 穩定）
        target_object = context.active_object if context.active_object in selected else selected[-1]
        source_objects = [obj for obj in selected if obj != target_object]
        
        try:
            original_matrices = {obj.name: obj.matrix_world.copy() for obj in source_objects}
            for src in source_objects:
                log_object_pair("multi_object_align", src, target_object, "before_apply", alignment_mode=self.alignment_mode, alignment_type=self.alignment_type)

            results = multi_object_solver.solve_alignment(
                source_objects, target_object, 
                self.alignment_mode, self.alignment_type
            )

            def _matrix_changed(a, b, eps=1e-6):
                for i in range(4):
                    for j in range(4):
                        if abs(a[i][j] - b[i][j]) > eps:
                            return True
                return False

            success_count = 0
            for result in results:
                if result.get('success', False):
                    source_obj = result['source_object']
                    before = original_matrices.get(source_obj.name)
                    already_changed = before is not None and _matrix_changed(source_obj.matrix_world, before)

                    # 某些 solver 內部已直接套用矩陣；避免 operator 重複套用
                    if not already_changed:
                        if result.get('translation'):
                            source_obj.matrix_world = result['translation'] @ source_obj.matrix_world
                        if result.get('rotation'):
                            source_obj.matrix_world = result['rotation'] @ source_obj.matrix_world

                    log_object_pair("multi_object_align", source_obj, target_object, "after_apply", solver_result=result, already_changed=already_changed)
                    success_count += 1
                else:
                    print(f"[SmartAlignPro] 對齊失敗: {result.get('error', '未知錯誤')}")

            self.report({"INFO"}, f"多物件對齊完成：{success_count}/{len(source_objects)} 個物件")
            log_operator_end("multi_object_align", "finished", success_count=success_count, total=len(source_objects))
            return {"FINISHED"}

        except Exception as e:
            log_operator_end("multi_object_align", "error", error=str(e))
            self.report({"ERROR"}, f"多物件對齊失敗: {str(e)}")
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_pivot_align(Operator):
    """支點對齊操作器"""
    bl_idname = "smartalignpro.pivot_align"
    bl_label = "支點對齊"
    bl_description = "使用指定支點進行精確對齊"
    bl_options = {"REGISTER", "UNDO"}

    # 支點類型
    pivot_type: EnumProperty(
        name="支點類型",
        description="對齊支點類型",
        items=[
            ("VERTEX", "頂點支點", "使用頂點作為支點"),
            ("EDGE", "邊緣支點", "使用邊緣作為支點"),
            ("FACE", "面支點", "使用面作為支點"),
            ("CENTER", "中心支點", "使用物件中心作為支點"),
            ("CUSTOM", "自定義支點", "使用自定義位置作為支點"),
        ],
        default="CENTER",
    )
    
    # 支點索引
    pivot_index: IntProperty(
        name="支點索引",
        description="頂點/邊緣/面的索引",
        default=0,
        min=0,
    )
    
    # 自定義支點位置
    custom_pivot: bpy.props.FloatVectorProperty(
        name="自定義支點",
        description="自定義支點位置",
        default=(0.0, 0.0, 0.0),
    )
    
    def execute(self, context):
        """執行支點對齊"""
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if len(selected) != 2:
            self.report({"WARNING"}, "請選取剛好兩個 Mesh 物件")
            return {"CANCELLED"}
        
        source_obj, target_obj = selected
        log_object_pair("pivot_align", source_obj, target_obj, "before_apply", pivot_type=self.pivot_type, pivot_index=self.pivot_index)
        
        try:
            # 使用 orientation_solver 內建的 pivot_solver
            pivot_solver = orientation_solver.pivot_solver
            
            # 獲取來源物件支點
            if self.pivot_type == "VERTEX":
                source_pivot = pivot_solver.solve_vertex_pivot(source_obj, self.pivot_index)
            elif self.pivot_type == "EDGE":
                source_pivot = pivot_solver.solve_edge_pivot(source_obj, self.pivot_index)
            elif self.pivot_type == "FACE":
                source_pivot = pivot_solver.solve_face_pivot(source_obj, self.pivot_index)
            elif self.pivot_type == "CENTER":
                source_pivot = pivot_solver.solve_center_pivot(source_obj)
            elif self.pivot_type == "CUSTOM":
                source_pivot = pivot_solver.solve_custom_pivot(source_obj, Vector(self.custom_pivot))
            
            # 獲取目標物件支點
            target_pivot = pivot_solver.solve_center_pivot(target_obj)
            
            if not source_pivot['success'] or not target_pivot['success']:
                self.report({"ERROR"}, f"支點求解失敗: {source_pivot.get('error') or target_pivot.get('error')}")
                return {"CANCELLED"}
            
            # 執行支點對齊
            from_point = source_pivot['position']
            to_point = target_pivot['position']
            
            # 使用姿態求解器
            result = orientation_solver.solve_two_point_orientation(
                source_obj, target_obj, from_point, to_point
            )
            
            if result['success']:
                # 應用變換
                if result['translation']:
                    source_obj.matrix_world = result['translation'] @ source_obj.matrix_world
                if result['rotation']:
                    source_obj.matrix_world = result['rotation'] @ source_obj.matrix_world
                
                self.report({"INFO"}, f"支點對齊完成: {source_obj.name} → {target_obj.name}")
                log_object_pair("pivot_align", source_obj, target_obj, "after_apply", pivot_type=self.pivot_type, pivot_index=self.pivot_index, from_point=from_point, to_point=to_point)
                log_operator_end("pivot_align", "finished")
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, f"姿態求解失敗: {result.get('error')}")
                log_operator_end("pivot_align", "solver_failed", result=result)
                return {"CANCELLED"}
            
        except Exception as e:
            log_operator_end("pivot_align", "error", error=str(e))
            self.report({"ERROR"}, f"支點對齊失敗: {str(e)}")
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_vector_constraint_align(Operator):
    """向量約束對齊操作器"""
    bl_idname = "smartalignpro.vector_constraint_align"
    bl_label = "向量約束對齊"
    bl_description = "使用自定義向量約束進行對齊"
    bl_options = {"REGISTER", "UNDO"}

    # 約束類型
    constraint_type: EnumProperty(
        name="約束類型",
        description="向量約束類型",
        items=[
            ("AXIS", "軸向約束", "約束到指定軸向"),
            ("PLANE", "平面約束", "約束到指定平面"),
            ("VECTOR", "向量約束", "約束到自定義向量"),
            ("NORMAL", "法線約束", "約束到表面法線"),
            ("CAMERA", "相機約束", "約束到相機方向"),
        ],
        default="AXIS",
    )
    
    # 約束參數
    constraint_axis: EnumProperty(
        name="約束軸",
        description="約束軸向",
        items=[
            ("X", "X 軸", "約束到 X 軸"),
            ("Y", "Y 軸", "約束到 Y 軸"),
            ("Z", "Z 軸", "約束到 Z 軸"),
            ("-X", "-X 軸", "約束到 -X 軸"),
            ("-Y", "-Y 軸", "約束到 -Y 軸"),
            ("-Z", "-Z 軸", "約束到 -Z 軸"),
        ],
        default="X",
    )
    
    custom_vector: bpy.props.FloatVectorProperty(
        name="自定義向量",
        description="自定義約束向量",
        default=(1.0, 0.0, 0.0),
    )
    
    def execute(self, context):
        """執行向量約束對齊"""
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if len(selected) < 2:
            self.report({"WARNING"}, "請至少選取兩個 Mesh 物件")
            return {"CANCELLED"}
        
        target_obj = selected[-1]
        source_objs = selected[:-1]
        
        try:
            success_count = 0
            
            for source_obj in source_objs:
                # 設置約束
                constraint = None
                
                if self.constraint_type == "AXIS":
                    axis_vectors = {
                        "X": Vector((1, 0, 0)),
                        "Y": Vector((0, 1, 0)),
                        "Z": Vector((0, 0, 1)),
                        "-X": Vector((-1, 0, 0)),
                        "-Y": Vector((0, -1, 0)),
                        "-Z": Vector((0, 0, -1)),
                    }
                    constraint = {
                        'type': 'AXIS',
                        'axis': axis_vectors.get(self.constraint_axis, Vector((1, 0, 0)))
                    }
                
                elif self.constraint_type == "VECTOR":
                    constraint = {
                        'type': 'VECTOR',
                        'vector': Vector(self.custom_vector).normalized()
                    }
                
                elif self.constraint_type == "NORMAL":
                    # 使用目標物件表面法線
                    target_center = _bbox_center_world(target_obj)
                    ray_result = context.scene.ray_cast(
                        context.depsgraph,
                        target_center + Vector((0, 0, 10)),
                        Vector((0, 0, -1))
                    )
                    
                    if ray_result[0]:
                        constraint = {
                            'type': 'NORMAL',
                            'normal': ray_result[2]
                        }
                    else:
                        continue
                
                # 執行約束對齊
                if constraint:
                    # 計算對齊變換
                    from_point = _bbox_center_world(source_obj)
                    to_point = _bbox_center_world(target_obj)
                    
                    # 使用約束求解器
                    from ..core.orientation_solver import TranslationSolver
                    solver = TranslationSolver()
                    
                    transform = solver.solve_translation(
                        source_obj, from_point, to_point, constraint
                    )
                    
                    # 應用變換
                    source_obj.matrix_world = transform @ source_obj.matrix_world
                    log_object_pair("vector_constraint_align", source_obj, target_obj, "after_apply", constraint=constraint, transform=transform)
                    success_count += 1
            
            self.report({"INFO"}, f"向量約束對齊完成：{success_count}/{len(source_objs)} 個物件")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"向量約束對齊失敗: {str(e)}")
            return {"CANCELLED"}


class SMARTALIGNPRO_PT_multi_object_panel(Panel):
    """多物件對齊面板"""
    bl_label = "多物件對齊"
    bl_idname = "SMARTALIGNPRO_PT_multi_object_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "對齊"
    bl_parent_id = "SMARTALIGNPRO_PT_main_panel"

    def draw(self, context):
        print("[SmartAlignPro][UI DRAW] multi_object_panel draw start")
        
        layout = self.layout
        
        # 多物件對齊
        box = layout.box()
        box.label(text="多物件對齊", icon=safe_icon("GROUP_VERTEX"))
        
        col = box.column(align=True)
        col.operator("smartalignpro.multi_object_align", text="多物件對齊", icon=safe_icon("MOD_ARRAY"))
        
        # 對齊模式
        box.prop(context.scene.smartalignpro_settings, "multi_object_alignment_mode")
        box.prop(context.scene.smartalignpro_settings, "multi_object_alignment_type")
        
        # 根據模式顯示特定參數
        if context.scene.smartalignpro_settings.multi_object_alignment_mode == "ARRAY_ALIGNMENT":
            box.prop(context.scene.smartalignpro_settings, "array_spacing")
        elif context.scene.smartalignpro_settings.multi_object_alignment_mode == "CIRCULAR_ALIGNMENT":
            box.prop(context.scene.smartalignpro_settings, "circular_radius")
        
        # 支點對齊
        pivot_box = layout.box()
        pivot_box.label(text="支點對齊", icon=safe_icon("SNAP_VERTEX"))
        
        pivot_col = pivot_box.column(align=True)
        pivot_col.operator("smartalignpro.pivot_align", text="支點對齊", icon=safe_icon("EMPTY_AXIS"))
        
        pivot_box.prop(context.scene.smartalignpro_settings, "pivot_type")
        
        # 根據支點類型顯示參數
        if context.scene.smartalignpro_settings.pivot_type in ["VERTEX", "EDGE", "FACE"]:
            pivot_box.prop(context.scene.smartalignpro_settings, "pivot_index")
        elif context.scene.smartalignpro_settings.pivot_type == "CUSTOM":
            pivot_box.prop(context.scene.smartalignpro_settings, "custom_pivot")
        
        # 向量約束
        constraint_box = layout.box()
        constraint_box.label(text="向量約束", icon=safe_icon("CONSTRAINT"))
        
        constraint_col = constraint_box.column(align=True)
        constraint_col.operator("smartalignpro.vector_constraint_align", text="向量約束對齊", icon=safe_icon("CON_TRACKTO"))
        
        constraint_box.prop(context.scene.smartalignpro_settings, "vector_constraint_type")
        
        # 根據約束類型顯示參數
        if context.scene.smartalignpro_settings.vector_constraint_type == "AXIS":
            constraint_box.prop(context.scene.smartalignpro_settings, "vector_constraint_axis")
        elif context.scene.smartalignpro_settings.vector_constraint_type == "VECTOR":
            constraint_box.prop(context.scene.smartalignpro_settings, "custom_constraint_vector")
