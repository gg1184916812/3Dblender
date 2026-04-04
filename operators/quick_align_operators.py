"""
Smart Align Pro - 一鍵常用預設系統
快速對齊的商業級功能
"""

import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty
from mathutils import Vector, Matrix
from bpy_extras import view3d_utils
from typing import List, Dict, Any

from ..core.snap_engine import snap_engine
from ..core.preview_transform import preview, activate, apply_preview
from ..ui.overlays import overlay
from ..ui.hud_enhanced import hud


class SMARTALIGNPRO_OT_quick_align(Operator):
    """一鍵快速對齊 - 商業級功能"""
    bl_idname = "smartalignpro.quick_align"
    bl_label = "快速對齊"
    bl_description = "一鍵快速對齊到最近的面或邊"
    bl_options = {"REGISTER", "UNDO"}
    
    align_mode: EnumProperty(
        name="對齊模式",
        description="快速對齊的模式",
        items=[
            ("FACE_CENTER", "面中心", "對齊到最近的面中心"),
            ("EDGE_MIDPOINT", "邊中點", "對齊到最近的邊中點"),
            ("VERTEX", "頂點", "對齊到最近的頂點"),
            ("GROUND", "地面", "對齊到地面 (Z=0)"),
            ("NORMAL", "法線", "沿著法線方向對齊"),
        ],
        default="FACE_CENTER"
    )
    
    def execute(self, context):
        """執行快速對齊"""
        if not context.active_object:
            self.report({"WARNING"}, "請先選取一個物件")
            return {"CANCELLED"}
            
        
        try:
            obj = context.active_object
            original_location = obj.location.copy()
            
            if self.align_mode == "GROUND":
                # 對齊到地面
                obj.location.z = 0
                
            elif self.align_mode == "NORMAL":
                # 對齊到法線方向
                self._align_to_normal(context, obj)
                
            else:
                # 對齊到幾何特徵
                self._align_to_geometry(context, obj)
            
            # 顯示結果
            delta = obj.location - original_location
            self.report({"INFO"}, f"快速對齊完成：移動 {delta.length:.2f} 单位")
            
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"快速對齊失敗: {e}")
            return {"CANCELLED"}
    
    def _align_to_normal(self, context, obj):
        """對齊到法線方向"""
        # 獲取物件下方最近的點
        ray_start = obj.location + Vector((0, 0, 10))
        ray_direction = Vector((0, 0, -1))
        
        depsgraph = context.evaluated_depsgraph_get()
        hit, location, normal, _, _, _ = context.scene.ray_cast(depsgraph, ray_start, ray_direction)
        
        if hit and normal:
            # 計算對齊位置
            align_distance = 0.1  # 對齊距離
            obj.location = location + normal * align_distance
    
    def _align_to_geometry(self, context, obj):
        """對齊到幾何特徵"""
        # 使用吸附引擎找到最佳候選點
        region = context.region
        rv3d = context.space_data.region_3d
        
        if not region or not rv3d:
            return
            
        # 從物件中心向下 ray_cast
        center_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, obj.location)
        if center_2d:
            mouse_x, mouse_y = center_2d
            candidate = snap_engine.find_best_candidate(context, mouse_x, mouse_y)
            
            if candidate:
                # 根據模式對齊
                if self.align_mode == "FACE_CENTER" and candidate.snap_type == "FACE_CENTER":
                    obj.location = candidate.location
                elif self.align_mode == "EDGE_MIDPOINT" and candidate.snap_type == "MIDPOINT":
                    obj.location = candidate.location
                elif self.align_mode == "VERTEX" and candidate.snap_type == "VERTEX":
                    obj.location = candidate.location


class SMARTALIGNPRO_OT_surface_align(Operator):
    """表面對齊 - 商業級功能"""
    bl_idname = "smartalignpro.surface_align"
    bl_label = "表面對齊"
    bl_description = "將物件對齊到表面，保持法線方向"
    bl_options = {"REGISTER", "UNDO"}
    
    offset_distance: bpy.props.FloatProperty(
        name="偏移距離",
        description="對齊後與表面的距離",
        default=0.0,
        min=-1.0,
        max=1.0,
        step=0.01
    )
    
    def execute(self, context):
        """執行表面對齊"""
        if not context.active_object:
            self.report({"WARNING"}, "請先選取一個物件")
            return {"CANCELLED"}
            
        
        try:
            obj = context.active_object
            
            # 從物件位置向下 ray_cast
            ray_start = obj.location + Vector((0, 0, 10))
            ray_direction = Vector((0, 0, -1))
            
            depsgraph = context.evaluated_depsgraph_get()
            hit, location, normal, _, _, _ = context.scene.ray_cast(depsgraph, ray_start, ray_direction)
            
            if not hit:
                self.report({"WARNING"}, "找不到下方的表面")
                return {"CANCELLED"}
            
            # 計算對齊位置
            align_location = location + normal * self.offset_distance
            
            # 計算對齊旋轉
            up_vector = Vector((0, 0, 1))
            rotation_axis = up_vector.cross(normal)
            rotation_angle = up_vector.angle(normal)
            
            if rotation_axis.length > 0.001:
                from mathutils import Quaternion
                rotation = Quaternion(rotation_axis.normalized(), rotation_angle)
                obj.rotation_mode = 'QUATERNION'
                obj.rotation_quaternion = rotation @ obj.rotation_quaternion
            
            # 應用位置
            obj.location = align_location
            
            self.report({"INFO"}, f"表面對齊完成：法線 ({normal.x:.2f}, {normal.y:.2f}, {normal.z:.2f})")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"表面對齊失敗: {e}")
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_preset_align(Operator):
    """預設對齊 - 商業級功能"""
    bl_idname = "smartalignpro.preset_align"
    bl_label = "預設對齊"
    bl_description = "使用預設配置進行對齊"
    bl_options = {"REGISTER", "UNDO"}
    
    preset_type: EnumProperty(
        name="預設類型",
        description="預設對齊類型",
        items=[
            ("BOTTOM_CENTER", "底部中心", "將物件底部中心對齊到世界中心"),
            ("TOP_CENTER", "頂部中心", "將物件頂部中心對齊到世界中心"),
            ("FRONT_CENTER", "前面中心", "將物件前面中心對齊到世界中心"),
            ("SIDE_CENTER", "側面中心", "將物件側面中心對齊到世界中心"),
            ("GRID_SNAP", "網格對齊", "將物件對齊到最近的網格點"),
            ("ORIGIN_ALIGN", "原點對齊", "將物件原點對齊到世界原點"),
        ],
        default="BOTTOM_CENTER"
    )
    
    def execute(self, context):
        """執行預設對齊"""
        if not context.active_object:
            self.report({"WARNING"}, "請先選取一個物件")
            return {"CANCELLED"}
            
        
        try:
            obj = context.active_object
            original_location = obj.location.copy()
            
            if self.preset_type == "BOTTOM_CENTER":
                self._align_bottom_center(obj)
            elif self.preset_type == "TOP_CENTER":
                self._align_top_center(obj)
            elif self.preset_type == "FRONT_CENTER":
                self._align_front_center(obj)
            elif self.preset_type == "SIDE_CENTER":
                self._align_side_center(obj)
            elif self.preset_type == "GRID_SNAP":
                self._align_grid_snap(obj)
            elif self.preset_type == "ORIGIN_ALIGN":
                self._align_origin(obj)
            
            # 顯示結果
            delta = obj.location - original_location
            self.report({"INFO"}, f"預設對齊完成：移動 {delta.length:.2f} 单位")
            
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"預設對齊失敗: {e}")
            return {"CANCELLED"}
    
    def _align_bottom_center(self, obj):
        """對齊底部中心"""
        # 獲取物件的 bounding box
        bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        
        # 找到最低點
        min_z = min(corner.z for corner in bbox_corners)
        
        # 將底部中心對齊到世界中心
        obj.location.z = -min_z
        obj.location.x = 0
        obj.location.y = 0
    
    def _align_top_center(self, obj):
        """對齊頂部中心"""
        bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        
        # 找到最高點
        max_z = max(corner.z for corner in bbox_corners)
        
        # 將頂部中心對齊到世界中心
        obj.location.z = -max_z
        obj.location.x = 0
        obj.location.y = 0
    
    def _align_front_center(self, obj):
        """對齊前面中心"""
        bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        
        # 找到最前面的點
        max_y = max(corner.y for corner in bbox_corners)
        
        # 將前面中心對齊到世界中心
        obj.location.y = -max_y
        obj.location.x = 0
        obj.location.z = 0
    
    def _align_side_center(self, obj):
        """對齊側面中心"""
        bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        
        # 找到最右側的點
        max_x = max(corner.x for corner in bbox_corners)
        
        # 將側面中心對齊到世界中心
        obj.location.x = -max_x
        obj.location.y = 0
        obj.location.z = 0
    
    def _align_grid_snap(self, obj):
        """對齊到網格"""
        grid_size = 1.0  # 網格大小
        
        # 對齊到最近的網格點
        obj.location.x = round(obj.location.x / grid_size) * grid_size
        obj.location.y = round(obj.location.y / grid_size) * grid_size
        obj.location.z = round(obj.location.z / grid_size) * grid_size
    
    def _align_origin(self, obj):
        """對齊原點"""
        obj.location = Vector((0, 0, 0))


class SMARTALIGNPRO_PT_quick_align_panel(Panel):
    """快速對齊面板"""
    bl_label = "快速對齊"
    bl_idname = "SMARTALIGNPRO_PT_quick_align_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Smart Align Pro"
    
    def draw(self, context):
        layout = self.layout
        
        # 快速對齊
        box = layout.box()
        box.label(text="快速對齊", icon="MOD_ALIGN")
        
        col = box.column(align=True)
        col.operator("smartalignpro.quick_align", text="面中心對齊").align_mode = "FACE_CENTER"
        col.operator("smartalignpro.quick_align", text="邊中點對齊").align_mode = "EDGE_MIDPOINT"
        col.operator("smartalignpro.quick_align", text="頂點對齊").align_mode = "VERTEX"
        col.operator("smartalignpro.quick_align", text="地面對齊").align_mode = "GROUND"
        
        # 表面對齊
        box = layout.box()
        box.label(text="表面對齊", icon="MOD_NORMALEDIT")
        
        col = box.column(align=True)
        op = col.operator("smartalignpro.surface_align", text="表面對齊")
        if hasattr(context.scene, "smartalignpro_settings"):
            op.offset_distance = context.scene.smartalignpro_settings.offset_distance
            col.prop(context.scene.smartalignpro_settings, "offset_distance", text="偏移距離")
        
        # 預設對齊
        box = layout.box()
        box.label(text="預設對齊", icon="SETTINGS")
        
        col = box.column(align=True)
        col.operator("smartalignpro.preset_align", text="底部中心").preset_type = "BOTTOM_CENTER"
        col.operator("smartalignpro.preset_align", text="頂部中心").preset_type = "TOP_CENTER"
        col.operator("smartalignpro.preset_align", text="前面中心").preset_type = "FRONT_CENTER"
        col.operator("smartalignpro.preset_align", text="側面中心").preset_type = "SIDE_CENTER"
        col.operator("smartalignpro.preset_align", text="網格對齊").preset_type = "GRID_SNAP"
        col.operator("smartalignpro.preset_align", text="原點對齊").preset_type = "ORIGIN_ALIGN"
