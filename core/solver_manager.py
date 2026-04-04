"""
Smart Align Pro - Solver Manager
統一調用所有求解器
"""

import bpy
from mathutils import Vector
from .two_point_solver import (
    solve_two_point_transform, 
    solve_two_point_directional,
    solve_two_point_cad_picking,
    solve_two_point_bbox_align
)
from .three_point_solver import (
    solve_three_point_transform,
    solve_three_point_rigid_transform,
    solve_three_point_cad_picking
)
from .edge_solver import (
    solve_edge_to_edge_contact,
    solve_edge_align_cad_picking
)
from .face_solver import (
    solve_face_to_face_contact,
    solve_face_align_cad_picking
)


class SolverManager:
    """統一求解器管理器"""
    
    @staticmethod
    def solve_two_point(source_obj, target_obj, mode="CAD", source_point_key=None, target_point_key=None):
        """
        統一的兩點對齊接口
        
        Args:
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            mode (str): 模式 ("CAD", "BBOX", "DIRECTIONAL")
            source_point_key (str): 來源點位鍵值
            target_point_key (str): 目標點位鍵值
            
        Returns:
            dict: 求解結果
        """
        print(f"[SmartAlignPro][SOLVER MANAGER] Two-point align: {mode}")
        print(f"[SmartAlignPro][SOLVER MANAGER] Source: {source_obj.name} → Target: {target_obj.name}")
        
        if mode == "CAD":
            return solve_two_point_cad_picking(source_obj, target_obj)
        elif mode == "BBOX" and source_point_key and target_point_key:
            return solve_two_point_bbox_align(source_obj, target_obj, source_point_key, target_point_key)
        else:
            # 預設 CAD 模式
            return solve_two_point_cad_picking(source_obj, target_obj)
    
    @staticmethod
    def solve_three_point(source_obj, target_obj, mode="CAD", source_keys=None, target_keys=None, settings=None):
        """
        統一的三點對齊接口
        
        Args:
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            mode (str): 模式 ("CAD", "RIGID")
            source_keys (list): 來源點位鍵值列表
            target_keys (list): 目標點位鍵值列表
            settings: 設置物件
            
        Returns:
            dict: 求解結果
        """
        print(f"[SmartAlignPro][SOLVER MANAGER] Three-point align: {mode}")
        print(f"[SmartAlignPro][SOLVER MANAGER] Source: {source_obj.name} → Target: {target_obj.name}")
        
        if mode == "CAD":
            return solve_three_point_cad_picking(source_obj, target_obj, settings)
        elif mode == "RIGID" and source_keys and target_keys:
            return solve_three_point_rigid_transform(source_obj, target_obj, source_keys, target_keys, settings)
        else:
            # 預設 CAD 模式
            return solve_three_point_cad_picking(source_obj, target_obj, settings)
    
    @staticmethod
    def solve_edge_align(source_obj, target_obj, mode="CAD", source_edge_key=None, target_edge_key=None, settings=None):
        """
        統一的邊對齊接口
        
        Args:
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            mode (str): 模式 ("CAD", "CONTACT")
            source_edge_key (tuple): 來源邊鍵值
            target_edge_key (tuple): 目標邊鍵值
            settings: 設置物件
            
        Returns:
            dict: 求解結果
        """
        print(f"[SmartAlignPro][SOLVER MANAGER] Edge align: {mode}")
        print(f"[SmartAlignPro][SOLVER MANAGER] Source: {source_obj.name} → Target: {target_obj.name}")
        
        if mode == "CAD":
            return solve_edge_align_cad_picking(source_obj, target_obj, settings)
        elif mode == "CONTACT" and source_edge_key and target_edge_key:
            return solve_edge_to_edge_contact(source_obj, target_obj, source_edge_key, target_edge_key, settings)
        else:
            # 預設 CAD 模式
            return solve_edge_align_cad_picking(source_obj, target_obj, settings)
    
    @staticmethod
    def solve_face_align(source_obj, target_obj, mode="CAD", source_face_key=None, target_face_key=None, settings=None):
        """
        統一的面對齊接口
        
        Args:
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            mode (str): 模式 ("CAD", "CONTACT")
            source_face_key (str): 來源面鍵值
            target_face_key (str): 目標面鍵值
            settings: 設置物件
            
        Returns:
            dict: 求解結果
        """
        print(f"[SmartAlignPro][SOLVER MANAGER] Face align: {mode}")
        print(f"[SmartAlignPro][SOLVER MANAGER] Source: {source_obj.name} → Target: {target_obj.name}")
        
        if mode == "CAD":
            return solve_face_align_cad_picking(source_obj, target_obj, settings)
        elif mode == "CONTACT" and source_face_key and target_face_key:
            return solve_face_to_face_contact(source_obj, target_obj, source_face_key, target_face_key, settings)
        else:
            # 預設 CAD 模式
            return solve_face_align_cad_picking(source_obj, target_obj, settings)
    
    @staticmethod
    def solve_surface_normal(source_obj, target_obj, settings):
        """
        表面法線對齊（使用現有實現）
        
        Args:
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            settings: 設置物件
            
        Returns:
            dict: 求解結果
        """
        # 使用現有的 surface_normal_align_with_raycast 實現
        from .alignment import surface_normal_align_with_raycast
        
        try:
            result = surface_normal_align_with_raycast(source_obj, target_obj, settings)
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def solve_auto_contact(source_obj, target_obj, settings):
        """
        自動接觸對齊（使用現有實現）
        
        Args:
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            settings: 設置物件
            
        Returns:
            dict: 求解結果
        """
        print(f"[SmartAlignPro][SOLVER MANAGER] Auto contact align")
        print(f"[SmartAlignPro][SOLVER MANAGER] Source: {source_obj.name} → Target: {target_obj.name}")
        
        # 使用現有的 auto_contact_align 實現
        from .alignment import auto_contact_align
        
        try:
            result = auto_contact_align(source_obj, target_obj, settings)
            print(f"[SmartAlignPro][SOLVER MANAGER] Auto contact align completed")
            return {'success': True, 'result': result}
        except Exception as e:
            print(f"[SmartAlignPro][SOLVER MANAGER] Auto contact align failed: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def execute_alignment(alignment_type, source_obj, target_obj, **kwargs):
        """
        統一執行對齊操作
        
        Args:
            alignment_type (str): 對齊類型
            source_obj (bpy.types.Object): 來源物件
            target_obj (bpy.types.Object): 目標物件
            **kwargs: 其他參數
            
        Returns:
            dict: 執行結果
        """
        print(f"[SmartAlignPro][SOLVER] Starting alignment execution")
        print(f"[SmartAlignPro][SOLVER] Alignment type: {alignment_type}")
        print(f"[SmartAlignPro][SOLVER] Source object: {source_obj.name}")
        print(f"[SmartAlignPro][SOLVER] Target object: {target_obj.name}")
        print(f"[SmartAlignPro][SOLVER] Source location: {source_obj.location}")
        print(f"[SmartAlignPro][SOLVER] Target location: {target_obj.location}")
        print(f"[SmartAlignPro][SOLVER] Source rotation: {source_obj.rotation_euler}")
        print(f"[SmartAlignPro][SOLVER] Target rotation: {target_obj.rotation_euler}")
        
        try:
            result = None
            
            if alignment_type == "TWO_POINT":
                result = SolverManager.solve_two_point(source_obj, target_obj, **kwargs)
            elif alignment_type == "THREE_POINT":
                result = SolverManager.solve_three_point(source_obj, target_obj, **kwargs)
            elif alignment_type == "EDGE_ALIGN":
                result = SolverManager.solve_edge_align(source_obj, target_obj, **kwargs)
            elif alignment_type == "FACE_ALIGN":
                result = SolverManager.solve_face_align(source_obj, target_obj, **kwargs)
            elif alignment_type == "SURFACE_NORMAL":
                result = SolverManager.solve_surface_normal(source_obj, target_obj, **kwargs)
            elif alignment_type == "AUTO_CONTACT":
                result = SolverManager.solve_auto_contact(source_obj, target_obj, **kwargs)
            else:
                raise ValueError(f"Unknown alignment type: {alignment_type}")
            
            # 輸出結果信息
            if result and result.get('success', True):
                print(f"[SmartAlignPro][SOLVER] Alignment completed successfully")
                if 'transform_matrix' in result:
                    transform = result['transform_matrix']
                    print(f"[SmartAlignPro][SOLVER] Transform matrix applied: {transform}")
                    print(f"[SmartAlignPro][SOLVER] Transform determinant: {transform.determinant()}")
                
                if 'rotation' in result:
                    rotation = result['rotation']
                    print(f"[SmartAlignPro][SOLVER] Rotation applied: {rotation}")
                
                if 'translation' in result:
                    translation = result['translation']
                    print(f"[SmartAlignPro][SOLVER] Translation applied: {translation}")
                
                # 輸出最終物件狀態
                print(f"[SmartAlignPro][SOLVER] Final source location: {source_obj.location}")
                print(f"[SmartAlignPro][SOLVER] Final source rotation: {source_obj.rotation_euler}")
            else:
                print(f"[SmartAlignPro][SOLVER] Alignment failed: {result.get('error', 'Unknown error')}")
                
            return result
                
        except Exception as e:
            print(f"[SmartAlignPro][SOLVER] Alignment execution failed: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}


# 全局求解器管理器實例
solver_manager = SolverManager()


def solve_alignment(alignment_type, source_obj, target_obj, **kwargs):
    """
    便捷函數：執行對齊求解
    
    Args:
        alignment_type (str): 對齊類型
        source_obj (bpy.types.Object): 來源物件
        target_obj (bpy.types.Object): 目標物件
        **kwargs: 其他參數
        
    Returns:
        dict: 求解結果
    """
    return solver_manager.execute_alignment(alignment_type, source_obj, target_obj, **kwargs)
