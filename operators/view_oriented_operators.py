"""
Smart Align Pro - 視圖導向對齊系統
根據當前視角自動判斷對齊方向
"""

import bpy
from bpy.types import Operator, Panel
from bpy.props import EnumProperty, BoolProperty
from mathutils import Vector, Matrix
from typing import List, Dict, Any, Tuple
import math

from ..core.snap_engine import snap_engine
from ..core.preview_transform import preview, activate, apply_preview
from ..core.view_axis_solver import ViewAxisSolver, get_view_basis, get_view_direction_vectors
from ..ui.overlays import overlay
from ..ui.hud_enhanced import hud


class ViewOrientedAligner:
    """視圖導向對齊器 - v7.4: 使用 ViewAxisSolver"""
    
    def __init__(self, *args, **kwargs):
        self.view_basis = None
        self.context = None
        
    def update_view_vectors(self, context):
        """更新視角向量 - v7.4: 使用 ViewAxisSolver"""
        try:
            self.context = context
            self.view_basis = get_view_basis(context)
            return self.view_basis is not None
        except Exception:
            return False
        
    def get_dominant_axis(self) -> str:
        """獲取主要軸向 - 保留舊 API 相容性"""
        if not self.view_basis:
            return "NONE"
        
        view_dir = self.view_basis.get('view_forward', Vector((0, 0, -1)))
        abs_x = abs(view_dir.x)
        abs_y = abs(view_dir.y)
        abs_z = abs(view_dir.z)
        max_val = max(abs_x, abs_y, abs_z)
        
        if max_val == abs_x:
            return "X_POSITIVE" if view_dir.x > 0 else "X_NEGATIVE"
        elif max_val == abs_y:
            return "Y_POSITIVE" if view_dir.y > 0 else "Y_NEGATIVE"
        else:
            return "Z_POSITIVE" if view_dir.z > 0 else "Z_NEGATIVE"
    
    def get_view_plane(self) -> str:
        """獲取視角平面 - 保留舊 API 相容性"""
        if not self.view_basis:
            return "NONE"
            
        dominant = self.get_dominant_axis()
        if dominant in ["X_POSITIVE", "X_NEGATIVE"]:
            return "YZ_PLANE"
        elif dominant in ["Y_POSITIVE", "Y_NEGATIVE"]:
            return "XZ_PLANE"
        elif dominant in ["Z_POSITIVE", "Z_NEGATIVE"]:
            return "XY_PLANE"
        return "NONE"
    
    def get_alignment_directions(self) -> Dict[str, Vector]:
        """
        獲取對齊方向 - v7.4: 使用 ViewAxisSolver
        
        這是超越 CAD Transform 的殺手功能：
        - 左 = 畫面左 (不是世界 X-)
        - 右 = 畫面右
        - 上 = 畫面上
        - 下 = 畫面下
        """
        if not self.view_basis:
            return {}
        
        # v7.4: 統一調用 ViewAxisSolver
        if not self.context:
            return {}
        directions = get_view_direction_vectors(self.context)
        
        # 轉換為舊格式
        return {
            "UP": directions.get('UP', Vector((0, 1, 0))),
            "DOWN": directions.get('DOWN', Vector((0, -1, 0))),
            "LEFT": directions.get('LEFT', Vector((-1, 0, 0))),
            "RIGHT": directions.get('RIGHT', Vector((1, 0, 0))),
            "FORWARD": directions.get('DEPTH_FORWARD', Vector((0, 0, 1))),
            "BACKWARD": directions.get('DEPTH_BACK', Vector((0, 0, -1))),
            "CENTER": Vector((0, 0, 0))
        }


# 全局視圖導向對齊器
view_oriented_aligner = ViewOrientedAligner()


class SMARTALIGNPRO_OT_view_oriented_align(Operator):
    """視圖導向對齊 - 商業級功能"""
    bl_idname = "smartalignpro.view_oriented_align"
    bl_label = "視圖導向對齊"
    bl_description = "根據當前視角進行智能對齊"
    bl_options = {"REGISTER", "UNDO"}
    
    align_direction: EnumProperty(
        name="對齊方向",
        description="相對於視角的對齊方向",
        items=[
            ("UP", "向上", "向視角上方對齊"),
            ("DOWN", "向下", "向視角下方對齊"),
            ("LEFT", "向左", "向視角左方對齊"),
            ("RIGHT", "向右", "向視角右方對齊"),
            ("CENTER", "中心", "向視角中心對齊"),
            ("AUTO", "自動", "自動判斷最佳對齊方向"),
        ],
        default="AUTO"
    )
    
    align_distance: bpy.props.FloatProperty(
        name="對齊距離",
        description="對齊的距離",
        default=0.0,
        min=-10.0,
        max=10.0,
        step=0.1
    )
    
    def execute(self, context):
        """執行視圖導向對齊"""
        if not context.active_object:
            self.report({"WARNING"}, "請先選取一個物件")
            return {"CANCELLED"}
            
        
        try:
            # 更新視角向量
            if not view_oriented_aligner.update_view_vectors(context):
                self.report({"WARNING"}, "無法獲取視角信息")
                return {"CANCELLED"}
            
            obj = context.active_object
            original_location = obj.location.copy()
            
            # 獲取對齊方向
            if self.align_direction == "AUTO":
                direction = self._get_auto_direction(context, obj)
            else:
                directions = view_oriented_aligner.get_alignment_directions()
                direction = directions.get(self.align_direction, Vector((0, 0, 0)))
            
            if direction.length == 0:
                self.report({"WARNING"}, "無法確定對齊方向")
                return {"CANCELLED"}
            
            # 計算對齊位置
            if self.align_direction == "CENTER":
                target_location = Vector((0, 0, 0))
            else:
                # 將物件投影到對齊方向
                projected_distance = obj.location.dot(direction)
                target_location = direction * (projected_distance + self.align_distance)
            
            # 應用對齊
            obj.location = target_location
            
            # 顯示結果
            delta = obj.location - original_location
            dominant_axis = view_oriented_aligner.get_dominant_axis()
            view_plane = view_oriented_aligner.get_view_plane()
            
            self.report({"INFO"}, f"視圖導向對齊完成：{dominant_axis} | {view_plane} | 移動 {delta.length:.2f} 单位")
            
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, f"視圖導向對齊失敗: {e}")
            return {"CANCELLED"}
    
    def _get_auto_direction(self, context, obj) -> Vector:
        """自動判斷最佳對齊方向"""
        directions = view_oriented_aligner.get_alignment_directions()

        # 回傳真正的方向向量，而不是位置差，避免 AUTO 模式計算錯亂
        min_distance = float('inf')
        best_direction = Vector((0, 0, 0))

        for direction_name, direction in directions.items():
            if direction_name == "CENTER":
                continue

            projected_distance = obj.location.dot(direction.normalized())
            target_location = direction.normalized() * projected_distance
            distance = (obj.location - target_location).length

            if distance < min_distance:
                min_distance = distance
                best_direction = direction.normalized()

        return best_direction


class SMARTALIGNPRO_OT_view_snap(Operator):
    """視圖吸附 - 商業級功能"""
    bl_idname = "smartalignpro.view_snap"
    bl_label = "視圖吸附"
    bl_description = "根據視角進行智能吸附"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}
    
    def invoke(self, context, event):
        """啟動視圖吸附"""
        
        # 更新視角向量
        if not view_oriented_aligner.update_view_vectors(context):
            self.report({"WARNING"}, "無法獲取視角信息")
            return {"CANCELLED"}
        
        # 啟動視覺系統
        activate(context.active_object, context.selected_objects)
        overlay.register()
        
        # 啟動 HUD
        hud.start("VIEW_SNAP")
        hud.update(mode="SELECT_TARGET")
        
        # 添加 modal 處理器
        context.window_manager.modal_handler_add(self)
        
        self.report({"INFO"}, "視圖吸附模式：左鍵確認，ESC 取消")
        return {"RUNNING_MODAL"}
    
    def modal(self, context, event):
        """處理 modal 事件"""
        context.area.tag_redraw()
        
        # ESC 取消
        if event.type == "ESC":
            return self._cancel_operation(context)
        
        # Enter 執行對齊
        if event.type == "RET" and event.value == "PRESS":
            return self._execute_alignment(context)
        
        # 滑鼠移動
        if event.type == "MOUSEMOVE":
            return self._handle_mouse_move(context, event)
        
        # 左鍵確認
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            return self._handle_click(context, event)
        
        return {"RUNNING_MODAL"}
    
    def _handle_mouse_move(self, context, event):
        """處理滑鼠移動"""
        # 使用吸附引擎找到候選點
        candidate = snap_engine.find_best_candidate(context, event.mouse_region_x, event.mouse_region_y)
        
        if candidate:
            # 更新 overlay
            overlay.update_hover_candidate(candidate)
            
            # 計算視圖導向的對齊位置
            aligned_location = self._get_view_aligned_location(candidate.location)
            
            # 更新預覽
            from ..core.preview_transform import update_transform
            translation = aligned_location - context.active_object.location
            update_transform(translation=translation)
            
            # 更新 HUD
            hud.update(snap_info=f"{candidate.snap_type} ({candidate.screen_distance:.1f}px)")
        else:
            overlay.clear_hover_candidate()
        
        return {"RUNNING_MODAL"}
    
    def _handle_click(self, context, event):
        """處理點擊"""
        candidate = snap_engine.find_best_candidate(context, event.mouse_region_x, event.mouse_region_y)
        
        if candidate:
            # 執行對齊
            return self._execute_alignment(context)
        
        return {"RUNNING_MODAL"}
    
    def _execute_alignment(self, context):
        """執行對齊"""
        try:
            apply_preview()
            
            # 清理視覺系統
            overlay.unregister()
            hud.stop()
            
            self.report({"INFO"}, "視圖吸附完成")
            return {"FINISHED"}
            
        except Exception as e:
            from ..core.preview_transform import cancel_preview
            cancel_preview()
            self.report({"ERROR"}, f"視圖吸附失敗: {e}")
            return {"CANCELLED"}
    
    def _cancel_operation(self, context):
        """取消操作"""
        from ..core.preview_transform import cancel_preview
        cancel_preview()
        
        overlay.unregister()
        hud.stop()
        
        self.report({"INFO"}, "視圖吸附已取消")
        return {"CANCELLED"}
    
    def _get_view_aligned_location(self, location: Vector) -> Vector:
        """獲取視圖導向的對齊位置"""
        directions = view_oriented_aligner.get_alignment_directions()
        
        # 找到最近的對齊方向
        min_distance = float('inf')
        best_location = location
        
        for direction_name, direction in directions.items():
            if direction_name == "CENTER":
                target_location = Vector((0, 0, 0))
            else:
                # 投影到方向
                projected_distance = location.dot(direction)
                target_location = direction * projected_distance
            
            distance = (location - target_location).length
            
            if distance < min_distance:
                min_distance = distance
                best_location = target_location
        
        return best_location


class SMARTALIGNPRO_PT_view_oriented_panel(Panel):
    """視圖導向對齊面板"""
    bl_label = "視圖導向對齊"
    bl_idname = "SMARTALIGNPRO_PT_view_oriented_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Smart Align Pro"
    
    def draw(self, context):
        layout = self.layout
        
        # 視圖導向對齊
        box = layout.box()
        box.label(text="視圖導向對齊", icon="VIEW_ORTHO")
        
        col = box.column(align=True)
        col.operator("smartalignpro.view_oriented_align", text="向上對齊").align_direction = "UP"
        col.operator("smartalignpro.view_oriented_align", text="向下對齊").align_direction = "DOWN"
        col.operator("smartalignpro.view_oriented_align", text="向左對齊").align_direction = "LEFT"
        col.operator("smartalignpro.view_oriented_align", text="向右對齊").align_direction = "RIGHT"
        col.operator("smartalignpro.view_oriented_align", text="中心對齊").align_direction = "CENTER"
        col.operator("smartalignpro.view_oriented_align", text="自動對齊").align_direction = "AUTO"
        
        # 視圖吸附
        box = layout.box()
        box.label(text="視圖吸附", icon="SNAP_GRID")
        
        col = box.column(align=True)
        col.operator("smartalignpro.view_snap", text="啟動視圖吸附")
        
        # 顯示當前視角信息
        if view_oriented_aligner.update_view_vectors(context):
            dominant_axis = view_oriented_aligner.get_dominant_axis()
            view_plane = view_oriented_aligner.get_view_plane()
            
            col.separator()
            col.label(text=f"主要軸向: {dominant_axis}")
            col.label(text=f"視角平面: {view_plane}")
