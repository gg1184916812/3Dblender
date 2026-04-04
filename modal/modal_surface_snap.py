"""
Smart Align Pro - 表面吸附 Modal 系統
CAD Transform 等級的互動體驗
"""

import bpy
from bpy.types import Operator
from mathutils import Vector, Matrix
from ..core.align_engine import align_engine
from ..core.math_utils import ray_cast_to_surface, project_point_to_plane
from ..keymap_manager import log_hotkey_trigger, log_hotkey_cancel


class SMARTALIGNPRO_OT_modal_surface_snap(Operator):
    """表面吸附 Modal 操作器 - CAD Transform 等級"""
    bl_idname = "smartalignpro.modal_surface_snap"
    bl_label = "表面吸附 (Modal)"
    bl_description = "CAD 級表面吸附，支援即時預覽"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}

    # Modal 狀態
    stage: bpy.props.EnumProperty(
        name="階段",
        items=[
            ("SELECT_SOURCE", "選擇來源物件", "選擇要吸附的物件"),
            ("SELECT_TARGET", "選擇目標表面", "選擇目標表面"),
            ("ADJUST_NORMAL", "調整法線", "調整法線對齊"),
            ("CONFIRM", "確認對齊", "確認並執行對齊"),
        ],
        default="SELECT_SOURCE",
    )
    
    # 吸附設置
    snap_mode: bpy.props.EnumProperty(
        name="吸附模式",
        items=[
            ("VERTEX", "頂點", "吸附到頂點"),
            ("EDGE", "邊緣", "吸附到邊緣"),
            ("FACE", "面", "吸附到面"),
            ("NORMAL", "法線", "沿法線吸附"),
        ],
        default="FACE",
    )
    
    # 對齊軸
    align_axis: bpy.props.EnumProperty(
        name="對齊軸",
        items=[
            ("AUTO", "自動", "自動選擇最佳軸"),
            ("X", "X 軸", "對齊到 X 軸"),
            ("Y", "Y 軸", "對齊到 Y 軸"),
            ("Z", "Z 軸", "對齊到 Z 軸"),
            ("-X", "-X 軸", "對齊到 -X 軸"),
            ("-Y", "-Y 軸", "對齊到 -Y 軸"),
            ("-Z", "-Z 軸", "對齊到 -Z 軸"),
        ],
        default="AUTO",
    )
    
    # 預覽設置
    show_preview: bpy.props.BoolProperty(default=True)
    preview_active: bpy.props.BoolProperty(default=False)
    
    # 吸附結果
    snap_point: bpy.props.FloatVectorProperty(size=3)
    snap_normal: bpy.props.FloatVectorProperty(size=3)
    snap_object: bpy.props.StringProperty()

    def invoke(self, context, event):
        """啟動 Modal 模式"""
        log_hotkey_trigger("modal_surface_snap")
        
        # 檢查選擇狀態
        selected = [obj for obj in context.selected_objects if obj.type == "MESH"]
        
        if len(selected) < 1:
            log_hotkey_cancel("modal_surface_snap", "no objects selected")
            self.report({"WARNING"}, "請至少選取一個 Mesh 物件")
            return {"CANCELLED"}
        
        # 初始化狀態
        self.stage = "SELECT_SOURCE"
        self.source_objects = selected.copy()
        self.target_object = None
        
        # 重置吸附結果
        self.snap_point = (0, 0, 0)
        self.snap_normal = (0, 0, 1)
        self.snap_object = ""
        
        # 預覽系統
        self.preview_active = False
        self.original_transforms = {}
        
        # 保存原始變換
        for obj in self.source_objects:
            self.original_transforms[obj.name] = {
                'matrix': obj.matrix_world.copy(),
                'location': obj.location.copy(),
                'rotation': obj.rotation_euler.copy(),
                'scale': obj.scale.copy()
            }
        
        # 添加 Modal 處理器
        context.window_manager.modal_handler_add(self)
        
        # 顯示提示
        self._show_help()
        
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        """處理 Modal 事件"""
        context.area.tag_redraw()
        
        # ESC 取消
        if event.type == "ESC":
            self._restore_original_transforms()
            self.report({"INFO"}, "表面吸附已取消")
            return {"CANCELLED"}
        
        # Enter 確認
        if event.type == "RET" and event.value == "PRESS":
            if self.stage == "CONFIRM":
                return self._execute_alignment(context)
            else:
                self._next_stage()
        
        # Tab 切換吸附模式
        if event.type == "TAB" and event.value == "PRESS":
            self._cycle_snap_mode()
        
        # A 鍵切換對齊軸
        if event.type == "A" and event.value == "PRESS":
            self._cycle_align_axis()
        
        # 滑鼠左鍵選擇/吸附
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if self.stage == "SELECT_SOURCE":
                self._confirm_source_selection(context)
            elif self.stage == "SELECT_TARGET":
                self._snap_to_surface(context, event)
        
        # 右鍵返回上一階段
        if event.type == "RIGHTMOUSE" and event.value == "PRESS":
            self._previous_stage()
        
        # 空格鍵切換預覽
        if event.type == "SPACE" and event.value == "PRESS":
            self.show_preview = not self.show_preview
            if not self.show_preview:
                self._restore_original_transforms()
        
        # 滑鼠移動更新預覽
        if event.type == "MOUSEMOVE" and self.show_preview:
            self._update_preview(context, event)
        
        return {"RUNNING_MODAL"}

    def _confirm_source_selection(self, context):
        """確認來源物件選擇"""
        if not self.source_objects:
            self.report({"WARNING"}, "沒有選擇來源物件")
            return
        
        self.stage = "SELECT_TARGET"
        self.report({"INFO"}, f"已選擇 {len(self.source_objects)} 個來源物件，請選擇目標表面")
        self._show_help()

    def _snap_to_surface(self, context, event):
        """吸附到表面"""
        # 獲取滑鼠射線
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        view_vector = context.space_data.region_3d.view_matrix.inverted().to_3x3() @ Vector((0, 0, -1))
        origin = context.space_data.region_3d.view_matrix.inverted().translation
        
        # 執行射線檢測
        result, location, normal, face_index, obj, matrix = context.scene.ray_cast(
            context.depsgraph, origin, view_vector
        )
        
        if result:
            self.snap_point = location
            self.snap_normal = normal
            self.snap_object = obj.name
            self.target_object = obj
            
            self.report({"INFO"}, f"已吸附到 {obj.name} 表面")
            self._next_stage()
        else:
            self.report({"WARNING"}, "無法吸附到表面")

    def _next_stage(self):
        """進入下一階段"""
        if self.stage == "SELECT_SOURCE":
            self.stage = "SELECT_TARGET"
        elif self.stage == "SELECT_TARGET":
            self.stage = "ADJUST_NORMAL"
            self.report({"INFO"}, "調整法線對齊設置")
        elif self.stage == "ADJUST_NORMAL":
            self.stage = "CONFIRM"
            self.report({"INFO"}, "按 Enter 確認對齊")
        
        self._show_help()

    def _previous_stage(self):
        """返回上一階段"""
        if self.stage == "SELECT_TARGET":
            self.stage = "SELECT_SOURCE"
        elif self.stage == "ADJUST_NORMAL":
            self.stage = "SELECT_TARGET"
        elif self.stage == "CONFIRM":
            self.stage = "ADJUST_NORMAL"
        
        self._show_help()

    def _cycle_snap_mode(self):
        """循環切換吸附模式"""
        modes = ["VERTEX", "EDGE", "FACE", "NORMAL"]
        current_index = modes.index(self.snap_mode)
        self.snap_mode = modes[(current_index + 1) % len(modes)]
        
        mode_names = {
            "VERTEX": "頂點",
            "EDGE": "邊緣",
            "FACE": "面",
            "NORMAL": "法線"
        }
        
        self.report({"INFO"}, f"吸附模式: {mode_names[self.snap_mode]}")

    def _cycle_align_axis(self):
        """循環切換對齊軸"""
        axes = ["AUTO", "X", "Y", "Z", "-X", "-Y", "-Z"]
        current_index = axes.index(self.align_axis)
        self.align_axis = axes[(current_index + 1) % len(axes)]
        
        self.report({"INFO"}, f"對齊軸: {self.align_axis}")

    def _update_preview(self, context, event):
        """更新即時預覽"""
        if self.stage not in ["ADJUST_NORMAL", "CONFIRM"]:
            return
        
        if not self.target_object:
            return
        
        try:
            # 恢復原始變換
            self._restore_original_transforms()
            
            # 執行預覽對齊
            for source_obj in self.source_objects:
                self._align_to_surface(source_obj)
            
            self.preview_active = True
            
        except Exception as e:
            print(f"[ModalSurfaceSnap] 預覽更新失敗: {e}")

    def _align_to_surface(self, source_obj):
        """對齊物件到表面"""
        # 計算對齊軸
        if self.align_axis == "AUTO":
            # 自動選擇最佳軸
            align_axis = self.snap_normal
        else:
            axis_map = {
                "X": Vector((1, 0, 0)),
                "Y": Vector((0, 1, 0)),
                "Z": Vector((0, 0, 1)),
                "-X": Vector((-1, 0, 0)),
                "-Y": Vector((0, -1, 0)),
                "-Z": Vector((0, 0, -1))
            }
            align_axis = axis_map.get(self.align_axis, Vector((0, 0, 1)))
        
        # 執行表面法線對齊
        class TempSettings:
            def __init__(self):
                self.normal_align_axis = "Z"
                self.normal_align_move_to_hit = True
        
        settings = TempSettings()
        settings.normal_align_axis = self.align_axis
        
        align_engine.align_surface_normal(source_obj, self.target_object, settings)
        
        # 移動到吸附點
        if self.snap_mode == "FACE":
            # 計算物件底部中心到吸附點的偏移
            obj_bottom = source_obj.matrix_world.translation - Vector((0, 0, source_obj.dimensions.z / 2))
            offset = self.snap_point - obj_bottom
            source_obj.location += offset

    def _restore_original_transforms(self):
        """恢復原始變換"""
        for obj_name, transform_data in self.original_transforms.items():
            obj = bpy.data.objects.get(obj_name)
            if obj:
                obj.matrix_world = transform_data['matrix']
        
        self.preview_active = False

    def _execute_alignment(self, context):
        """執行最終對齊"""
        if not self.target_object:
            self.report({"WARNING"}, "沒有選擇目標表面")
            return {"CANCELLED"}
        
        try:
            # 確保使用最新變換
            if not self.preview_active:
                for source_obj in self.source_objects:
                    self._align_to_surface(source_obj)
            
            self.report({"INFO"}, f"表面吸附完成：{len(self.source_objects)} 個物件")
            return {"FINISHED"}
            
        except Exception as e:
            self._restore_original_transforms()
            self.report({"ERROR"}, f"對齊失敗: {str(e)}")
            return {"CANCELLED"}

    def _show_help(self):
        """顯示幫助信息"""
        help_texts = {
            "SELECT_SOURCE": "來源物件選擇 - 左鍵確認 | 空格:預覽 | 右鍵:返回",
            "SELECT_TARGET": "目標表面選擇 - 左鍵吸附 | Tab:模式 | 空格:預覽",
            "ADJUST_NORMAL": "法線調整 - A:對齊軸 | Tab:模式 | Enter:確認",
            "CONFIRM": "確認對齊 - Enter:執行 | A:對齊軸 | Tab:模式 | 右鍵:返回"
        }
        
        self.report({"INFO"}, help_texts.get(self.stage, ""))

    def draw(self, context):
        """繪製 HUD 顯示"""
        # 這裡可以添加 3D 視圖覆蓋繪製
        pass
