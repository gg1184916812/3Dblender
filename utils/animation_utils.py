"""
Smart Align Pro - 動畫工具模組
包含動畫相關的輔助函數
"""

import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, IntProperty, FloatProperty, EnumProperty


class AnimationData:
    """動畫數據管理類"""
    
    def __init__(self):
        self.keyframes = {}
        self.timeline_handlers = []
    
    def save_keyframe_state(self, obj, frame):
        """保存關鍵幀狀態"""
        state = {
            "frame": frame,
            "location": obj.location.copy(),
            "rotation": obj.rotation_euler.copy(),
            "scale": obj.scale.copy(),
            "matrix_world": obj.matrix_world.copy()
        }
        
        if obj.name not in self.keyframes:
            self.keyframes[obj.name] = []
        
        self.keyframes[obj.name].append(state)
        return state
    
    def get_keyframe_state(self, obj_name, frame):
        """獲取關鍵幀狀態"""
        if obj_name not in self.keyframes:
            return None
        
        for state in self.keyframes[obj_name]:
            if state["frame"] == frame:
                return state
        
        return None
    
    def clear_keyframes(self, obj_name=None):
        """清除關鍵幀數據"""
        if obj_name:
            self.keyframes.pop(obj_name, None)
        else:
            self.keyframes.clear()


# 全局動畫數據實例
animation_data = AnimationData()


class SMARTALIGNPRO_OT_timeline_align(Operator):
    """時間軸對齊操作器"""
    bl_idname = "smartalignpro.timeline_align"
    bl_label = "時間軸對齊"
    bl_description = "在時間軸上創建對齊動畫"
    bl_options = {"REGISTER", "UNDO"}

    start_frame: IntProperty(
        name="開始幀",
        description="動畫開始幀",
        default=1,
        min=0
    )
    
    end_frame: IntProperty(
        name="結束幀",
        description="動畫結束幀",
        default=25,
        min=1
    )
    
    interpolation: bpy.props.EnumProperty(
        name="插值模式",
        description="關鍵幀插值模式",
        items=[
            ("LINEAR", "線性", "線性插值"),
            ("BEZIER", "貝茲", "貝茲插值"),
            ("CONSTANT", "常數", "常數插值"),
        ],
        default="LINEAR"
    )

    def execute(self, context):
        active = context.active_object
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not active or active.type != "MESH":
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
            # 保存當前幀
            original_frame = context.scene.frame_current
            
            # 設置開始幀
            context.scene.frame_set(self.start_frame)
            
            # 為每個來源物件創建動畫
            for source in sources:
                # 在開始幀插入關鍵幀（原始位置）
                source.keyframe_insert(data_path="location", frame=self.start_frame)
                source.keyframe_insert(data_path="rotation_euler", frame=self.start_frame)
                source.keyframe_insert(data_path="scale", frame=self.start_frame)
                
                # 設置插值模式
                if self.interpolation != "LINEAR":
                    fcurves = source.animation_data.action.fcurves
                    for fcurve in fcurves:
                        for keyframe in fcurve.keyframe_points:
                            keyframe.interpolation = self.interpolation
            
            # 執行對齊
            from ..core.alignment import two_point_align
            settings = context.scene.smartalignpro_settings
            
            for source in sources:
                two_point_align(source, active, "0", "1", "0", "1")
            
            # 設置結束幀
            context.scene.frame_set(self.end_frame)
            
            # 在結束幀插入關鍵幀（對齊後位置）
            for source in sources:
                source.keyframe_insert(data_path="location", frame=self.end_frame)
                source.keyframe_insert(data_path="rotation_euler", frame=self.end_frame)
                source.keyframe_insert(data_path="scale", frame=self.end_frame)
                
                # 設置插值模式
                if self.interpolation != "LINEAR":
                    fcurves = source.animation_data.action.fcurves
                    for fcurve in fcurves:
                        for keyframe in fcurve.keyframe_points:
                            keyframe.interpolation = self.interpolation
            
            # 恢復原始幀
            context.scene.frame_set(original_frame)
            
            self.report({"INFO"}, f"時間軸對齊完成：{len(sources)} 個物件 ({self.start_frame}-{self.end_frame}幀)")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_bake_animation(Operator):
    """烘焙動畫操作器"""
    bl_idname = "smartalignpro.bake_animation"
    bl_label = "烘焙動畫"
    bl_description = "烘焙對齊動畫到關鍵幀"
    bl_options = {"REGISTER", "UNDO"}

    step: IntProperty(
        name="烘焙步長",
        description="關鍵幀間隔",
        default=1,
        min=1,
        max=10
    )

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not selected:
            self.report({"WARNING"}, "請選取至少一個 Mesh 物件")
            return {"CANCELLED"}
        
        try:
            # 獲取動畫範圍
            scene = context.scene
            start_frame = scene.frame_start
            end_frame = scene.frame_end
            
            baked_objects = 0
            
            for obj in selected:
                if not obj.animation_data or not obj.animation_data.action:
                    continue
                
                # 清除現有關鍵幀
                obj.animation_data_clear()
                
                # 重新烘焙
                current_frame = scene.frame_current
                
                for frame in range(start_frame, end_frame + 1, self.step):
                    scene.frame_set(frame)
                    
                    # 插入關鍵幀
                    obj.keyframe_insert(data_path="location", frame=frame)
                    obj.keyframe_insert(data_path="rotation_euler", frame=frame)
                    obj.keyframe_insert(data_path="scale", frame=frame)
                
                baked_objects += 1
            
            # 恢復原始幀
            scene.frame_set(current_frame)
            
            self.report({"INFO"}, f"動畫烘焙完成：{baked_objects} 個物件")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


class SMARTALIGNPRO_OT_clear_animation(Operator):
    """清除動畫操作器"""
    bl_idname = "smartalignpro.clear_animation"
    bl_label = "清除動畫"
    bl_description = "清除選取物件的動畫"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if not selected:
            self.report({"WARNING"}, "請選取至少一個 Mesh 物件")
            return {"CANCELLED"}
        
        try:
            cleared_objects = 0
            
            for obj in selected:
                if obj.animation_data:
                    obj.animation_data_clear()
                    cleared_objects += 1
            
            self.report({"INFO"}, f"動畫清除完成：{cleared_objects} 個物件")
            return {"FINISHED"}
            
        except Exception as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}


def save_keyframe_state(obj, frame):
    """保存關鍵幀狀態（兼容函數）"""
    return animation_data.save_keyframe_state(obj, frame)


def create_timeline_alignment(context, obj, target_frames, alignment_type="POSITION"):
    """創建時間軸對齊（兼容函數）"""
    scene = context.scene
    original_frame = scene.frame_current
    
    try:
        for frame in target_frames:
            scene.frame_set(frame)
            
            # 保存當前狀態
            animation_data.save_keyframe_state(obj, frame)
            
            # 插入關鍵幀
            if alignment_type == "POSITION":
                obj.keyframe_insert(data_path="location", frame=frame)
            elif alignment_type == "ROTATION":
                obj.keyframe_insert(data_path="rotation_euler", frame=frame)
            elif alignment_type == "SCALE":
                obj.keyframe_insert(data_path="scale", frame=frame)
            else:  # ALL
                obj.keyframe_insert(data_path="location", frame=frame)
                obj.keyframe_insert(data_path="rotation_euler", frame=frame)
                obj.keyframe_insert(data_path="scale", frame=frame)
        
        return True
        
    finally:
        scene.frame_set(original_frame)


def remove_timeline_handlers():
    """移除時間軸處理器"""
    for handler in animation_data.timeline_handlers:
        try:
            bpy.app.handlers.frame_change_post.remove(handler)
        except:
            pass
    animation_data.timeline_handlers.clear()


def add_timeline_handler(callback):
    """添加時間軸處理器"""
    handler = bpy.app.handlers.frame_change_post.append(callback)
    animation_data.timeline_handlers.append(handler)
    return handler


def get_animation_summary(obj):
    """獲取動畫摘要"""
    if not obj.animation_data or not obj.animation_data.action:
        return {"has_animation": False}
    
    action = obj.animation_data.action
    fcurves = action.fcurves
    
    summary = {
        "has_animation": True,
        "fcurve_count": len(fcurves),
        "keyframe_count": 0,
        "frame_range": [float('inf'), float('-inf')],
        "animated_properties": []
    }
    
    for fcurve in fcurves:
        summary["animated_properties"].append(fcurve.data_path)
        summary["keyframe_count"] += len(fcurve.keyframe_points)
        
        for keyframe in fcurve.keyframe_points:
            summary["frame_range"][0] = min(summary["frame_range"][0], keyframe.co.x)
            summary["frame_range"][1] = max(summary["frame_range"][1], keyframe.co.x)
    
    # 修正無限值
    if summary["frame_range"][0] == float('inf'):
        summary["frame_range"][0] = 0
    if summary["frame_range"][1] == float('-inf'):
        summary["frame_range"][1] = 0
    
    return summary
