"""
Smart Align Pro - Unified Preview Engine
統一預覽引擎 - 致命差距③修復

所有 modal operator 共用同一套 preview 管線：
PreviewEngine.update() → draw() → clear() → commit() → cancel()
"""

import bpy
import gpu
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
from typing import Optional, Dict, Any, List, Callable


class PreviewState:
    """預覽狀態封裝"""
    def __init__(self):
        self.original_matrix: Optional[Matrix] = None
        self.preview_matrix: Optional[Matrix] = None
        self.is_dirty: bool = False
        self.draw_handler = None
        self.shader = None
        self.batch = None
        self.hud_lines: List[str] = []


class UnifiedPreviewEngine:
    """統一預覽引擎 - 單一 realtime engine 實現
    
    致命差距③修復：
    - 取代分散的 interactive_preview.py, hover_preview_system.py, realtime_preview_engine.py
    - 統一管線：update → draw → clear → commit → cancel
    - 所有 modal 共用，確保手感一致
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._state = PreviewState()
        self._draw_callback = None
        self._handlers = {}
        
        # 著色器快取
        self._shader = None
        self._batch = None
        
    def _get_shader(self):
        """獲取 3D 著色器 (惰性初始化)"""
        if self._shader is None:
            import gpu
            self._shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        return self._shader
        
    def update(self, context, active_obj: bpy.types.Object, 
               preview_matrix: Matrix, hud_lines: List[str] = None):
        """更新預覽狀態
        
        Args:
            context: Blender context
            active_obj: 當前操作物件
            preview_matrix: 預覽變換矩陣
            hud_lines: HUD 顯示文字列表
        """
        if active_obj is None:
            return
            
        # 儲存原始狀態 (首次)
        if self._state.original_matrix is None:
            self._state.original_matrix = active_obj.matrix_world.copy()
            
        # 更新預覽矩陣
        self._state.preview_matrix = preview_matrix.copy()
        self._state.is_dirty = True
        
        # 更新 HUD
        if hud_lines:
            self._state.hud_lines = hud_lines
            
        # 應用預覽變換
        active_obj.matrix_world = preview_matrix
        
        # 標記重繪
        if context.area:
            context.area.tag_redraw()
            
    def draw(self):
        """繪製預覽視覺回饋 - 3D 視圖回呼"""
        import blf
        import bgl
        
        if not self._state.hud_lines:
            return
            
        # 繪製 HUD 文字
        font_id = 0
        blf.size(font_id, 14)
        
        y_offset = 100
        for line in self._state.hud_lines:
            blf.position(font_id, 20, y_offset, 0)
            blf.draw(font_id, line)
            y_offset -= 20
            
    def register_draw(self, context):
        """註冊繪製回呼"""
        if self._draw_callback is None:
            self._draw_callback = bpy.types.SpaceView3D.draw_handler_add(
                self.draw, (), 'WINDOW', 'POST_PIXEL'
            )
            
    def unregister_draw(self):
        """註銷繪製回呼"""
        if self._draw_callback is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._draw_callback, 'WINDOW')
            self._draw_callback = None
            
    def clear(self, context, active_obj: Optional[bpy.types.Object] = None):
        """清除預覽 - 恢復原始狀態但不提交
        
        這是 cancel 或 ESC 時的清理
        """
        if active_obj and self._state.original_matrix:
            active_obj.matrix_world = self._state.original_matrix.copy()
            
        self._state.preview_matrix = None
        self._state.is_dirty = False
        
        if context.area:
            context.area.tag_redraw()
            
    def commit(self, context, active_obj: Optional[bpy.types.Object] = None):
        """提交預覽 - 確認變更
        
        這是 Enter/Space 確認時的提交
        """
        # 當前 matrix 已經是預覽狀態，只需要標記場景更新
        if active_obj:
            active_obj.update_tag()
            
        # 清除預覽狀態
        self._state.original_matrix = None
        self._state.preview_matrix = None
        self._state.is_dirty = False
        
        if context.area:
            context.area.tag_redraw()
            
    def cancel(self, context, active_obj: Optional[bpy.types.Object] = None):
        """取消預覽 - 完全撤銷
        
        ESC 取消 modal 時呼叫
        """
        self.clear(context, active_obj)
        self.unregister_draw()
        
    def get_hud_lines(self, operator) -> List[str]:
        """生成標準 HUD 文字"""
        lines = []
        
        # 模式資訊
        if hasattr(operator, 'mode_level'):
            mode_str = "簡單" if operator.mode_level.name == "SIMPLE" else "進階"
            lines.append(f"【{mode_str}模式】Tab切換")
            
        # 當前階段
        if hasattr(operator, 'workflow_stage'):
            stage_name = operator.workflow_stage.name
            if hasattr(operator, '_stage_labels'):
                stage_label = operator._stage_labels.get(stage_name, stage_name)
                lines.append(stage_label)
                
        # 軸鎖定
        if hasattr(operator, 'axis_lock'):
            if operator.axis_lock.current_lock.is_active:
                lines.append(f"軸鎖定: {operator.axis_lock.current_lock.lock_type.name}")
                
        # 快捷鍵提示
        lines.append("Enter確認 | ESC取消 | Tab切換模式")
        
        return lines
        
    def is_active(self) -> bool:
        """檢查是否有活躍的預覽"""
        return self._state.preview_matrix is not None


# 全局統一預覽引擎實例
_preview_engine: Optional[UnifiedPreviewEngine] = None


def get_preview_engine() -> UnifiedPreviewEngine:
    """獲取全局統一預覽引擎"""
    global _preview_engine
    if _preview_engine is None:
        _preview_engine = UnifiedPreviewEngine()
    return _preview_engine


def reset_preview_engine():
    """重置全局統一預覽引擎"""
    global _preview_engine
    if _preview_engine:
        _preview_engine.unregister_draw()
    _preview_engine = None


# ============================================================================
# v7.4 新增：Preview Transform 計算與 Commit 整合
# ============================================================================

class PreviewTransformResult:
    """
    預覽變換結果 - v7.4: 作為 commit 的單一真相來源
    
    這個類別確保 preview matrix 就是 commit matrix，不再重新計算
    """
    
    def __init__(self, matrix: Matrix, original: Matrix, 
                 domain=None, candidate=None, solver_name: str = ""):
        self.matrix = matrix.copy()
        self.original = original.copy()
        self.domain = domain
        self.candidate = candidate
        self.solver_name = solver_name
        self._applied = False
        
    def apply(self):
        """
        套用變換 - 這就是 commit，不再重新計算
        
        v7.4 核心原則：preview = commit
        """
        if self._applied:
            print("[PreviewTransform] Already applied, skipping")
            return True
            
        try:
            # 如果有 candidate，獲取 source object
            if self.candidate and 'source_obj' in self.candidate:
                obj = self.candidate['source_obj']
            else:
                # 從當前上下文獲取
                import bpy
                obj = bpy.context.active_object
                
            if obj is None:
                print("[PreviewTransform] No object to apply")
                return False
                
            # 直接套用預覽矩陣
            obj.matrix_world = self.matrix
            self._applied = True
            
            print(f"[PreviewTransform] Applied {self.solver_name} transform")
            return True
            
        except Exception as e:
            print(f"[PreviewTransform] Apply failed: {e}")
            return False
            
    def apply_to_object(self, obj: bpy.types.Object):
        """套用到指定物件"""
        if obj and self.matrix:
            obj.matrix_world = self.matrix
            self._applied = True
            return True
        return False
        
    def revert(self):
        """還原到原始狀態"""
        try:
            if self.candidate and 'source_obj' in self.candidate:
                obj = self.candidate['source_obj']
            else:
                import bpy
                obj = bpy.context.active_object
                
            if obj and self.original:
                obj.matrix_world = self.original
                self._applied = False
                return True
        except Exception as e:
            print(f"[PreviewTransform] Revert failed: {e}")
            
        return False


def compute_preview_transform(solver: Callable,
                              domain=None,
                              candidate: Dict[str, Any] = None) -> Optional[PreviewTransformResult]:
    """
    計算預覽變換 - v7.4: 讓 preview = commit
    
    這個函數計算的結果將直接用於 commit，不再重新計算
    
    Args:
        solver: solver 函數
        domain: ConstraintDomain 實例
        candidate: 候選點資訊
        
    Returns:
        PreviewTransformResult: 包含預覽矩陣的結果物件
    """
    import bpy
    
    if solver is None:
        print("[compute_preview_transform] No solver provided")
        return None
        
    # 獲取當前物件和原始矩陣
    obj = bpy.context.active_object
    if obj is None:
        print("[compute_preview_transform] No active object")
        return None
        
    original_matrix = obj.matrix_world.copy()
    
    try:
        # 執行 solver 計算變換
        # solver 可能回傳矩陣或字典
        result = solver()
        
        if result is None:
            print("[compute_preview_transform] Solver returned None")
            return None
            
        # 解析 solver 結果
        if isinstance(result, Matrix):
            transform_matrix = result
        elif isinstance(result, dict):
            # 如果回傳字典，提取矩陣
            if 'matrix' in result:
                transform_matrix = result['matrix']
            elif 'translation' in result and 'rotation' in result:
                # 組合平移和旋轉
                transform_matrix = result['translation'] @ result['rotation']
            elif 'transform' in result:
                transform_matrix = result['transform']
            else:
                print(f"[compute_preview_transform] Unknown result format: {result.keys()}")
                return None
        else:
            print(f"[compute_preview_transform] Unknown result type: {type(result)}")
            return None
            
        # 應用約束域限制
        if domain is not None and hasattr(domain, 'is_active') and domain.is_active:
            # 使用 coordinate_space_solver 應用約束
            try:
                from .coordinate_space_solver import apply_domain_constraint_to_transform
                transform_matrix = apply_domain_constraint_to_transform(
                    transform_matrix, domain, original_matrix
                )
            except Exception as e:
                print(f"[compute_preview_transform] Domain constraint failed: {e}")
        
        # 創建結果物件
        # v7.4: 這個結果將直接用於 commit
        preview_result = PreviewTransformResult(
            matrix=transform_matrix,
            original=original_matrix,
            domain=domain,
            candidate=candidate,
            solver_name=getattr(solver, '__name__', str(solver))
        )
        
        return preview_result
        
    except Exception as e:
        print(f"[compute_preview_transform] Computation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# 快捷函數：直接獲取預覽結果並套用
def preview_and_commit(solver: Callable,
                       domain=None,
                       candidate: Dict[str, Any] = None) -> bool:
    """
    計算預覽並立即套用 - 簡化流程
    
    Args:
        solver: solver 函數
        domain: ConstraintDomain 實例
        candidate: 候選點資訊
        
    Returns:
        bool: 是否成功
    """
    result = compute_preview_transform(solver, domain, candidate)
    if result:
        return result.apply()
    return False
