"""
Smart Align Pro - 兩點對齊 Modal
使用統一對齊框架
"""

import bpy
from mathutils import Vector, Matrix
from typing import List, Dict, Any, Tuple

from ..core.unified_modal_base import SmartAlignModalBase
from ..core.modal_kernel import AlignmentMode


class SMARTALIGNPRO_OT_modal_two_point_align(SmartAlignModalBase):
    """兩點對齊 Modal - 統一框架版本"""
    
    bl_idname = "smartalignpro.modal_two_point_align"
    bl_label = "兩點對齊 (Modal)"
    bl_description = "CAD 級兩點對齊，支援即時預覽"
    bl_options = {"REGISTER", "UNDO", "BLOCKING"}
    
    def _get_alignment_mode(self) -> AlignmentMode:
        """返回對齊模式"""
        return AlignmentMode.TWO_POINT
        
    def _get_required_points(self) -> Dict[str, int]:
        """返回所需點位數量"""
        return {"source": 2, "target": 2}
        
    def _solve_alignment(self, source_points: List[Vector], target_points: List[Vector]) -> Dict[str, Any]:
        """
        v7.4: 求解兩點對齊 - 使用統一 constraint 系統
        
        流程：
        1. 建立 runtime context
        2. 求解平移和旋轉
        3. 應用統一 constraint
        """
        if len(source_points) < 2 or len(target_points) < 2:
            return {"success": False, "error": "點位不足"}
            
        try:
            # Step 1: 建立兩點對齊 runtime
            runtime = self._build_two_point_runtime(source_points, target_points)
            
            # Step 2: 求解平移
            translation = self._solve_two_point_translation(runtime)
            
            # Step 3: 求解旋轉
            rotation = self._solve_two_point_rotation(runtime)
            
            # Step 4: 應用統一 constraint
            translation, rotation = self._apply_two_point_constraint(translation, rotation, runtime)
            
            return {
                "success": True,
                "translation": translation,
                "rotation": rotation,
                "source_points": source_points,
                "target_points": target_points,
                "runtime": runtime,
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _build_two_point_runtime(self, source_points: List[Vector], target_points: List[Vector]) -> Dict[str, Any]:
        """
        v7.4: 建立兩點對齊運行時上下文
        """
        source_vec = source_points[1] - source_points[0]
        target_vec = target_points[1] - target_points[0]
        
        return {
            "source_points": source_points,
            "target_points": target_points,
            "source_vec": source_vec,
            "target_vec": target_vec,
            "source_origin": source_points[0],
            "target_origin": target_points[0],
            "constraint_mode": self.constraint_mode,
            "axis_lock_state": self._get_current_axis_lock_state(),
        }
    
    def _solve_two_point_translation(self, runtime: Dict[str, Any]) -> Matrix:
        """
        v7.4: 求解兩點對齊平移
        """
        source_origin = runtime["source_origin"]
        target_origin = runtime["target_origin"]
        constraint_mode = runtime["constraint_mode"]
        
        # 預設：完整平移
        delta = target_origin - source_origin
        
        # 如果處於 ROTATE_ONLY 模式，不平移
        if constraint_mode == "ROTATE_ONLY":
            return Matrix.Identity(4)
        
        return Matrix.Translation(delta)
    
    def _solve_two_point_rotation(self, runtime: Dict[str, Any]) -> Matrix:
        """
        v7.4: 求解兩點對齊旋轉
        """
        source_vec = runtime["source_vec"]
        target_vec = runtime["target_vec"]
        constraint_mode = runtime["constraint_mode"]
        
        # 如果處於 TRANSLATE_ONLY 模式，不旋轉
        if constraint_mode == "TRANSLATE_ONLY":
            return Matrix.Identity(4)
        
        # 計算旋轉
        from mathutils import Quaternion
        rotation = Quaternion(source_vec.rotation_difference(target_vec)).to_matrix().to_4x4()
        
        return rotation
    
    def _apply_two_point_constraint(self, translation: Matrix, rotation: Matrix, runtime: Dict[str, Any]) -> Tuple[Matrix, Matrix]:
        """
        v7.4: 應用統一 constraint 系統
        
        使用 AxisLockingSystem 的統一接口，而不是自己處理 X/Y/Z
        """
        constraint_mode = runtime["constraint_mode"]
        
        # NONE: 無約束
        if constraint_mode == "NONE":
            return translation, rotation
            
        # TRANSLATE_ONLY: 僅平移（已在 solve 階段處理）
        if constraint_mode == "TRANSLATE_ONLY":
            return translation, Matrix.Identity(4)
            
        # ROTATE_ONLY: 僅旋轉（已在 solve 階段處理）
        if constraint_mode == "ROTATE_ONLY":
            return Matrix.Identity(4), rotation
        
        # 軸鎖定：使用統一 AxisLockingSystem
        if constraint_mode.startswith("AXIS_LOCK_"):
            try:
                from ..core.axis_locking_system import get_axis_locking_system, AxisConstraintKind
                
                axis_system = get_axis_locking_system()
                axis_name = constraint_mode.split("_")[-1]  # X, Y, Z
                
                # 設置軸鎖定
                axis_system.set_axis_lock_by_name(axis_name)
                
                # 應用 constraint 到平移
                delta = translation.translation
                constrained_delta = axis_system.apply_axis_constraint_to_delta(delta)
                
                translation = Matrix.Translation(constrained_delta)
                rotation = Matrix.Identity(4)
                
            except Exception as e:
                print(f"[TwoPointAlign] Axis lock failed: {e}")
                # Fallback: 使用舊的 X/Y/Z 邏輯
                axis = constraint_mode.split("_")[-1].lower()
                axis_index = {"x": 0, "y": 1, "z": 2}[axis]
                
                delta = runtime["target_origin"] - runtime["source_origin"]
                constrained_delta = Vector((0, 0, 0))
                constrained_delta[axis_index] = delta[axis_index]
                translation = Matrix.Translation(constrained_delta)
                rotation = Matrix.Identity(4)
        
        return translation, rotation
    
    def _get_current_axis_lock_state(self):
        """獲取當前軸鎖定狀態"""
        if self.constraint_mode.startswith("AXIS_LOCK_"):
            return self.constraint_mode
        return None


# 註冊類別
classes = [
    SMARTALIGNPRO_OT_modal_two_point_align,
]
