"""
Smart Align Pro - Enhanced Interactive Snap Modal
實現 CAD Transform 級別的滑鼠移動即時預覽變換
"""

import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, FloatProperty
from mathutils import Vector, Matrix, geometry
from typing import Optional, Dict, Any, List, Tuple
import time

from .modal_base import SmartAlignModalBase
from ..core.modal_kernel import AlignmentMode, ModalPoint
from ..core.topology_alignment import topology_alignment_system
from ..core.snap_priority_solver import get_snap_context, solve_snap_priority
from ..core.realtime_preview_engine import get_realtime_preview_engine, activate_realtime_preview, update_object_preview
from ..core.coordinate_space_solver import get_coordinate_space_solver, CoordinateSpaceType


class EnhancedInteractiveSnapModal(SmartAlignModalBase):
    """增強版交互式吸附 Modal - CAD Transform 級別的即時預覽"""
    
    bl_idname = "smartalignpro.enhanced_interactive_snap_modal"
    bl_label = "增強版交互式吸附"
    bl_description = "CAD Transform 級別的滑鼠移動即時預覽變換"
    
    # 對齊模式
    alignment_mode: EnumProperty(
        name="對齊模式",
        description="選擇對齊模式",
        items=[
            ("TWO_POINT", "兩點對齊", "使用兩點對齊"),
            ("THREE_POINT", "三點對齊", "使用三點對齊"),
            ("SURFACE_NORMAL", "表面法線", "使用表面法線對齊"),
            ("EDGE_TO_EDGE", "邊對邊", "邊緣到邊緣對齊"),
            ("FACE_TO_FACE", "面對面", "面到面對齊"),
        ],
        default="TWO_POINT",
    )
    
    # 預覽設置
    enable_realtime_preview: BoolProperty(
        name="啟用即時預覽",
        description="啟用滑鼠移動即時預覽",
        default=True,
    )
    
    preview_update_rate: FloatProperty(
        name="預覽更新率",
        description="預覽更新率 (FPS)",
        default=60.0,
        min=15.0,
        max=120.0,
        precision=1,
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.preview_engine = get_realtime_preview_engine()
        self.space_solver = get_coordinate_space_solver()
        self.last_preview_update = 0
        self.preview_active = False
        
        # 對齊數據
        self.source_points = []
        self.target_points = []
        self.current_transform = Matrix.Identity(4)
        
        # 即時預覽狀態
        self.mouse_position = Vector((0, 0, 0))
        self.last_mouse_position = Vector((0, 0, 0))
        self.is_dragging = False
        
    def _get_alignment_mode(self) -> AlignmentMode:
        """獲取對齊模式"""
        mode_map = {
            "TWO_POINT": AlignmentMode.TWO_POINT,
            "THREE_POINT": AlignmentMode.THREE_POINT,
            "SURFACE_NORMAL": AlignmentMode.SURFACE_NORMAL,
        }
        return mode_map.get(self.alignment_mode, AlignmentMode.TWO_POINT)
    
    def _initialize_specific_modal(self, context, event) -> bool:
        """初始化特定 Modal"""
        # 設置坐標空間求解器
        self.space_solver.set_context(context)
        
        # 啟動即時預覽引擎
        if self.enable_realtime_preview:
            activate_realtime_preview(context)
            self.preview_active = True
            
            # 添加預覽物件
            if context.active_object:
                self.preview_engine.add_preview_object(
                    context.active_object.name, 
                    context.active_object
                )
        
        return True
    
    def _handle_mouse_move(self, context, event):
        """處理滑鼠移動 - 即時預覽核心"""
        # 更新滑鼠位置
        self.mouse_position = Vector((event.mouse_region_x, event.mouse_region_y))
        
        # 檢查是否需要更新預覽
        current_time = time.time()
        update_interval = 1.0 / self.preview_update_rate
        
        if current_time - self.last_preview_update < update_interval:
            return {"RUNNING_MODAL"}
        
        self.last_preview_update = current_time
        
        # 尋找當前吸附點
        snap_point = self._find_snap_point(context, event)
        
        if snap_point:
            # 計算即時變換
            transform = self._calculate_realtime_transform(context, snap_point)
            
            if transform:
                self.current_transform = transform
                
                # 更新即時預覽
                if self.preview_active and context.active_object:
                    update_object_preview(
                        context.active_object.name, 
                        transform
                    )
                
                # 更新對齊預覽
                self._update_alignment_preview(context)
        
        return {"RUNNING_MODAL"}
    
    def _calculate_realtime_transform(self, context, snap_point) -> Optional[Matrix]:
        """計算即時變換 - 核心算法"""
        if not context.active_object:
            return None
        
        # 獲取當前 Modal 狀態
        status = self._modal_kernel.get_status_info()
        points = status["points"]
        
        if self.alignment_mode == "TWO_POINT":
            return self._calculate_two_point_realtime_transform(context, snap_point, points)
        elif self.alignment_mode == "THREE_POINT":
            return self._calculate_three_point_realtime_transform(context, snap_point, points)
        elif self.alignment_mode == "SURFACE_NORMAL":
            return self._calculate_surface_normal_realtime_transform(context, snap_point, points)
        elif self.alignment_mode == "EDGE_TO_EDGE":
            return self._calculate_edge_to_edge_realtime_transform(context, snap_point, points)
        elif self.alignment_mode == "FACE_TO_FACE":
            return self._calculate_face_to_face_realtime_transform(context, snap_point, points)
        
        return None
    
    def _calculate_two_point_realtime_transform(self, context, snap_point, points) -> Optional[Matrix]:
        """計算兩點對齊即時變換"""
        if "SOURCE_A" in points and "SOURCE_B" in points:
            source_a = points["SOURCE_A"]
            source_b = points["SOURCE_B"]
            
            # 計算來源向量
            source_vector = source_b - source_a
            source_length = source_vector.length
            
            if source_length < 0.0001:
                # 來源向量太短，使用簡單平移
                if "TARGET_A" in points:
                    target_a = points["TARGET_A"]
                    translation = snap_point.position - target_a
                    return Matrix.Translation(translation)
            else:
                # 根據當前狀態計算目標向量
                if "TARGET_A" in points:
                    target_a = points["TARGET_A"]
                    target_vector = snap_point.position - target_a
                    
                    # 計算變換矩陣
                    return self._calculate_two_point_transform_matrix(
                        source_a, source_b, target_a, snap_point.position
                    )
        
        return None
    
    def _calculate_three_point_realtime_transform(self, context, snap_point, points) -> Optional[Matrix]:
        """計算三點對齊即時變換"""
        if ("SOURCE_A" in points and "SOURCE_B" in points and "SOURCE_C" in points):
            source_a = points["SOURCE_A"]
            source_b = points["SOURCE_B"]
            source_c = points["SOURCE_C"]
            
            if "TARGET_A" in points and "TARGET_B" in points:
                target_a = points["TARGET_A"]
                target_b = points["TARGET_B"]
                
                # 使用當前滑鼠位置作為第三個目標點
                return self._calculate_three_point_transform_matrix(
                    source_a, source_b, source_c, 
                    target_a, target_b, snap_point.position
                )
        
        return None
    
    def _calculate_surface_normal_realtime_transform(self, context, snap_point, points) -> Optional[Matrix]:
        """計算表面法線即時變換"""
        if "SOURCE" in points:
            source_point = points["SOURCE"]
            
            # 計算法線對齊
            if snap_point.normal:
                # 計算旋轉使來源法線對齊到目標法線
                source_normal = source_point.normal if source_point.normal else Vector((0, 0, 1))
                target_normal = snap_point.normal
                
                # 計算旋轉軸和角度
                rotation_axis = source_normal.cross(target_normal)
                rotation_angle = source_normal.angle(target_normal)
                
                # 構建旋轉矩陣
                if rotation_angle > 0.0001:
                    rotation_matrix = Matrix.Rotation(rotation_angle, 4, rotation_axis)
                else:
                    rotation_matrix = Matrix.Identity(4)
                
                # 計算平移
                translation = snap_point.position - source_point.position
                
                # 構建完整變換矩陣
                transform = Matrix.Translation(translation) @ rotation_matrix
                
                return transform
        
        return None
    
    def _calculate_edge_to_edge_realtime_transform(self, context, snap_point, points) -> Optional[Matrix]:
        """計算邊對邊即時變換"""
        # 這是一個複雜的算法，需要找到兩條邊的最佳對齊
        # 暫時返回簡化版本
        return self._calculate_two_point_realtime_transform(context, snap_point, points)
    
    def _calculate_face_to_face_realtime_transform(self, context, snap_point, points) -> Optional[Matrix]:
        """計算面對面即時變換"""
        # 這是一個複雜的算法，需要找到兩個面的最佳對齊
        # 暫時返回簡化版本
        return self._calculate_three_point_realtime_transform(context, snap_point, points)
    
    def _calculate_two_point_transform_matrix(self, source_a, source_b, target_a, target_b) -> Matrix:
        """計算兩點對齊變換矩陣"""
        # 計算來源向量
        source_vector = source_b - source_a
        source_length = source_vector.length
        
        if source_length < 0.0001:
            # 來源向量太短，使用簡單平移
            translation = target_a - source_a
            return Matrix.Translation(translation)
        
        # 計算目標向量
        target_vector = target_b - target_a
        target_length = target_vector.length
        
        # 計算旋轉
        source_direction = source_vector.normalized()
        target_direction = target_vector.normalized()
        
        # 計算旋轉軸和角度
        rotation_axis = source_direction.cross(target_direction)
        rotation_angle = source_direction.angle(target_direction)
        
        # 構建旋轉矩陣
        if rotation_angle > 0.0001:
            rotation_matrix = Matrix.Rotation(rotation_angle, 4, rotation_axis)
        else:
            rotation_matrix = Matrix.Identity(4)
        
        # 計算縮放（如果需要）
        scale_matrix = Matrix.Identity(4)
        if self._modal_kernel.keep_scale and target_length > 0.0001:
            scale_factor = target_length / source_length
            scale_matrix = Matrix.Scale(scale_factor, 4)
        
        # 計算平移
        translation = target_a - source_a
        
        # 構建完整變換矩陣
        transform = Matrix.Translation(translation) @ rotation_matrix @ scale_matrix
        
        return transform
    
    def _calculate_three_point_transform_matrix(self, source_a, source_b, source_c, 
                                          target_a, target_b, target_c) -> Matrix:
        """計算三點對齊變換矩陣"""
        # 計算來源平面基座
        def get_plane_basis(p1, p2, p3):
            v1 = p2 - p1
            v2 = p3 - p1
            normal = v1.cross(v2).normalized()
            
            # 確保向量正交
            x_axis = v1.normalized()
            y_axis = normal.cross(x_axis).normalized()
            z_axis = normal
            
            return x_axis, y_axis, z_axis
        
        source_basis = get_plane_basis(source_a, source_b, source_c)
        target_basis = get_plane_basis(target_a, target_b, target_c)
        
        # 構建來源矩陣
        source_matrix = Matrix.Identity(4)
        source_matrix.translation = source_a
        source_matrix[0][0:3] = source_basis[0]
        source_matrix[1][0:3] = source_basis[1]
        source_matrix[2][0:3] = source_basis[2]
        
        # 構建目標矩陣
        target_matrix = Matrix.Identity(4)
        target_matrix.translation = target_a
        target_matrix[0][0:3] = target_basis[0]
        target_matrix[1][0:3] = target_basis[1]
        target_matrix[2][0:3] = target_basis[2]
        
        # 計算變換矩陣
        transform = target_matrix @ source_matrix.inverted()
        
        # 應用翻轉選項
        if self._modal_kernel.flip_normal:
            # 繞目標平面的 X 軸翻轉 180 度
            flip_matrix = Matrix.Rotation(3.14159, 4, target_basis[0])
            transform = flip_matrix @ transform
        
        return transform
    
    def _update_alignment_preview(self, context):
        """更新對齊預覽"""
        # 獲取當前狀態
        status = self._modal_kernel.get_status_info()
        points = status["points"]
        
        # 準備來源和目標點
        source_points = []
        target_points = []
        
        for point_type, point in points.items():
            if "SOURCE" in point_type:
                source_points.append(point)
            elif "TARGET" in point_type:
                target_points.append(point)
        
        # 更新對齊預覽
        self.preview_engine.update_alignment_preview(
            source_points, target_points, self.current_transform
        )
    
    def _execute_alignment(self, context):
        """執行對齊"""
        if context.active_object and self.current_transform != Matrix.Identity(4):
            # 保存當前狀態（用於撤銷）
            bpy.ops.ed.undo_push()
            
            # 應用變換
            context.active_object.matrix_world = self.current_transform @ context.active_object.matrix_world
            
            # 更新場景
            context.view_layer.update()
            
            self._report_status(context, f"即時對齊完成: {context.active_object.name}")
        
        return self._finish_modal(context, "FINISHED")
    
    def _finish_modal(self, context, result):
        """完成 Modal"""
        # 停用即時預覽
        if self.preview_active:
            self.preview_engine.deactivate(context)
            self.preview_active = False
        
        return super()._finish_modal(context, result)


# 註冊類別
CLASSES = [
    EnhancedInteractiveSnapModal,
]


def register():
    """註冊增強版交互式吸附操作器"""
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    """註銷增強版交互式吸附操作器"""
    for cls in CLASSES:
        bpy.utils.unregister_class(cls)
