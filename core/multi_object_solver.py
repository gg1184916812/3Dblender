"""
Smart Align Pro - 多物件求解系統
實現真正的 CAD 級多物件對齊求解
支持 A → B, A+B → C, Group → target 等模式
"""

import bpy
import math
from mathutils import Vector, Matrix
from .orientation_solver import orientation_solver
from ..utils.bbox_utils import get_bbox_center_world


class MultiObjectSolver:
    """多物件求解器核心類"""
    
    def __init__(self):
        self.alignment_modes = {
            'SINGLE_TO_TARGET': self.solve_single_to_target,
            'MULTIPLE_TO_TARGET': self.solve_multiple_to_target,
            'GROUP_TO_TARGET': self.solve_group_to_target,
            'CHAIN_ALIGNMENT': self.solve_chain_alignment,
            'CIRCULAR_ALIGNMENT': self.solve_circular_alignment,
            'ARRAY_ALIGNMENT': self.solve_array_alignment
        }
    
    def solve_alignment(self, source_objects, target_object, mode='MULTIPLE_TO_TARGET', 
                        alignment_type='TWO_POINT', from_points=None, to_points=None):
        """求解多物件對齊"""
        if mode not in self.alignment_modes:
            mode = 'MULTIPLE_TO_TARGET'
        
        return self.alignment_modes[mode](
            source_objects, target_object, alignment_type, from_points, to_points
        )
    
    def solve_single_to_target(self, source_objects, target_object, 
                              alignment_type, from_points, to_points):
        """求解單物件到目標對齊 (A → B)"""
        results = []
        
        for i, source_obj in enumerate(source_objects):
            try:
                if alignment_type == 'TWO_POINT' and from_points and to_points:
                    # 使用指定的點位
                    from_point = from_points[i] if i < len(from_points) else from_points[0]
                    to_point = to_points[i] if i < len(to_points) else to_points[0]
                    
                    result = orientation_solver.solve_two_point_orientation(
                        source_obj, target_object, from_point, to_point
                    )
                else:
                    # 使用默認中心點對齊
                    from_point = get_bbox_center_world(source_obj)
                    to_point = get_bbox_center_world(target_object)
                    
                    result = orientation_solver.solve_two_point_orientation(
                        source_obj, target_object, from_point, to_point
                    )
                
                result['source_object'] = source_obj
                result['target_object'] = target_object
                result['alignment_type'] = alignment_type
                results.append(result)
                
            except Exception as e:
                results.append({
                    'source_object': source_obj,
                    'target_object': target_object,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def solve_multiple_to_target(self, source_objects, target_object, 
                                alignment_type, from_points, to_points):
        """求解多物件到單目標對齊 (A+B → C)"""
        results = []
        
        # 計算整體變換
        if alignment_type == 'TWO_POINT' and from_points and to_points:
            # 使用第一個點位計算整體變換
            overall_result = orientation_solver.solve_two_point_orientation(
                source_objects[0], target_object, from_points[0], to_points[0]
            )
        else:
            # 使用中心點計算整體變換
            # 計算所有來源物件的整體中心
            overall_center = Vector((0, 0, 0))
            for obj in source_objects:
                overall_center += get_bbox_center_world(obj)
            overall_center /= len(source_objects)
            
            target_center = get_bbox_center_world(target_object)
            
            overall_result = orientation_solver.solve_two_point_orientation(
                source_objects[0], target_object, overall_center, target_center
            )
        
        # 應用整體變換到所有物件
        for source_obj in source_objects:
            try:
                # 計算相對變換
                original_matrix = source_obj.matrix_world.copy()
                
                # 應用變換
                if overall_result['success']:
                    if overall_result['translation']:
                        source_obj.matrix_world = overall_result['translation'] @ original_matrix
                    if overall_result['rotation']:
                        source_obj.matrix_world = overall_result['rotation'] @ source_obj.matrix_world
                
                result = {
                    'source_object': source_obj,
                    'target_object': target_object,
                    'success': overall_result['success'],
                    'translation': overall_result['translation'],
                    'rotation': overall_result['rotation'],
                    'alignment_type': alignment_type
                }
                results.append(result)
                
            except Exception as e:
                results.append({
                    'source_object': source_obj,
                    'target_object': target_object,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def solve_group_to_target(self, source_objects, target_object, 
                             alignment_type, from_points, to_points):
        """求解群組到目標對齊 (Group → target)"""
        # 創建臨時群組物件
        group_result = self._create_virtual_group(source_objects)
        
        if not group_result['success']:
            return [{
                'success': False,
                'error': group_result['error'],
                'source_objects': source_objects,
                'target_object': target_object
            }]
        
        virtual_group = group_result['virtual_group']
        
        try:
            # 對虛擬群組進行對齊
            if alignment_type == 'TWO_POINT' and from_points and to_points:
                group_result = orientation_solver.solve_two_point_orientation(
                    virtual_group, target_object, from_points[0], to_points[0]
                )
            else:
                group_center = get_bbox_center_world(virtual_group)
                target_center = get_bbox_center_world(target_object)
                
                group_result = orientation_solver.solve_two_point_orientation(
                    virtual_group, target_object, group_center, target_center
                )
            
            # 將變換應用到群組中的每個物件
            results = []
            for source_obj in source_objects:
                try:
                    original_matrix = source_obj.matrix_world.copy()
                    
                    # 計算相對於群組中心的變換
                    relative_pos = original_matrix.translation - virtual_group.matrix_world.translation
                    
                    # 應用群組變換
                    if group_result['success']:
                        if group_result['translation']:
                            new_translation = group_result['translation'].translation + relative_pos
                            source_obj.matrix_world.translation = new_translation
                        if group_result['rotation']:
                            source_obj.matrix_world = group_result['rotation'] @ source_obj.matrix_world
                    
                    results.append({
                        'source_object': source_obj,
                        'target_object': target_object,
                        'success': group_result['success'],
                        'alignment_type': alignment_type
                    })
                    
                except Exception as e:
                    results.append({
                        'source_object': source_obj,
                        'target_object': target_object,
                        'success': False,
                        'error': str(e)
                    })
            
            return results
            
        except Exception as e:
            return [{
                'success': False,
                'error': str(e),
                'source_objects': source_objects,
                'target_object': target_object
            }]
    
    def solve_chain_alignment(self, source_objects, target_object, 
                             alignment_type, from_points, to_points):
        """求解鏈式對齊 (A → B → C → ...)"""
        results = []
        
        # 按順序對齊每個物件到下一個物件
        for i in range(len(source_objects)):
            current_obj = source_objects[i]
            
            if i == len(source_objects) - 1:
                # 最後一個物件對齊到目標
                next_obj = target_object
            else:
                # 其他物件對齊到下一個物件
                next_obj = source_objects[i + 1]
            
            try:
                if alignment_type == 'TWO_POINT' and from_points and to_points:
                    from_point = from_points[i] if i < len(from_points) else from_points[0]
                    to_point = to_points[i] if i < len(to_points) else to_points[0]
                    
                    result = orientation_solver.solve_two_point_orientation(
                        current_obj, next_obj, from_point, to_point
                    )
                else:
                    from_point = get_bbox_center_world(current_obj)
                    to_point = get_bbox_center_world(next_obj)
                    
                    result = orientation_solver.solve_two_point_orientation(
                        current_obj, next_obj, from_point, to_point
                    )
                
                result['source_object'] = current_obj
                result['target_object'] = next_obj
                result['chain_index'] = i
                results.append(result)
                
            except Exception as e:
                results.append({
                    'source_object': current_obj,
                    'target_object': next_obj,
                    'success': False,
                    'error': str(e),
                    'chain_index': i
                })
        
        return results
    
    def solve_circular_alignment(self, source_objects, target_object, 
                                alignment_type, from_points, to_points):
        """求解圓形對齊 (圍繞目標圓形排列)"""
        results = []
        
        try:
            # 計算圓形排列參數
            target_center = get_bbox_center_world(target_object)
            radius = 2.0  # 默認半徑
            angle_step = 2 * math.pi / len(source_objects)
            
            for i, source_obj in enumerate(source_objects):
                try:
                    # 計算圓形位置
                    angle = i * angle_step
                    target_position = target_center + Vector((
                        radius * math.cos(angle),
                        radius * math.sin(angle),
                        0
                    ))
                    
                    # 計算變換
                    current_position = get_bbox_center_world(source_obj)
                    translation = Matrix.Translation(target_position - current_position)
                    
                    # 可選：面向中心
                    direction_to_center = (target_center - target_position).normalized()
                    if direction_to_center.length > 0.001:
                        # 計算面向中心的旋轉
                        forward = Vector((0, 1, 0))
                        rotation = self._calculate_look_rotation(forward, direction_to_center)
                        
                        result = {
                            'source_object': source_obj,
                            'target_object': target_object,
                            'success': True,
                            'translation': translation,
                            'rotation': rotation.to_matrix().to_4x4(),
                            'alignment_type': 'CIRCULAR',
                            'circular_index': i,
                            'target_position': target_position
                        }
                    else:
                        result = {
                            'source_object': source_obj,
                            'target_object': target_object,
                            'success': True,
                            'translation': translation,
                            'rotation': Matrix.Identity(4),
                            'alignment_type': 'CIRCULAR',
                            'circular_index': i,
                            'target_position': target_position
                        }
                    
                    results.append(result)
                    
                except Exception as e:
                    results.append({
                        'source_object': source_obj,
                        'target_object': target_object,
                        'success': False,
                        'error': str(e),
                        'alignment_type': 'CIRCULAR',
                        'circular_index': i
                    })
            
            return results
            
        except Exception as e:
            return [{
                'success': False,
                'error': str(e),
                'source_objects': source_objects,
                'target_object': target_object,
                'alignment_type': 'CIRCULAR'
            }]
    
    def solve_array_alignment(self, source_objects, target_object, 
                              alignment_type, from_points, to_points):
        """求解陣列對齊 (線性陣列排列)"""
        results = []
        
        try:
            # 計算陣列參數
            if len(source_objects) < 2:
                return [{
                    'success': False,
                    'error': "至少需要兩個物件進行陣列對齊",
                    'source_objects': source_objects,
                    'target_object': target_object
                }]
            
            # 計算陣列方向
            first_obj = source_objects[0]
            last_obj = source_objects[-1]
            
            first_pos = get_bbox_center_world(first_obj)
            last_pos = get_bbox_center_world(last_obj)
            
            array_direction = (last_pos - first_pos).normalized()
            spacing = (last_pos - first_pos).length / (len(source_objects) - 1)
            
            target_center = get_bbox_center_world(target_object)
            
            for i, source_obj in enumerate(source_objects):
                try:
                    # 計算陣列位置
                    target_position = target_center + array_direction * (i * spacing)
                    
                    # 計算變換
                    current_position = get_bbox_center_world(source_obj)
                    translation = Matrix.Translation(target_position - current_position)
                    
                    # 可選：對齊方向
                    if array_direction.length > 0.001:
                        forward = Vector((0, 1, 0))
                        rotation = self._calculate_look_rotation(forward, array_direction)
                        
                        result = {
                            'source_object': source_obj,
                            'target_object': target_object,
                            'success': True,
                            'translation': translation,
                            'rotation': rotation.to_matrix().to_4x4(),
                            'alignment_type': 'ARRAY',
                            'array_index': i,
                            'target_position': target_position
                        }
                    else:
                        result = {
                            'source_object': source_obj,
                            'target_object': target_object,
                            'success': True,
                            'translation': translation,
                            'rotation': Matrix.Identity(4),
                            'alignment_type': 'ARRAY',
                            'array_index': i,
                            'target_position': target_position
                        }
                    
                    results.append(result)
                    
                except Exception as e:
                    results.append({
                        'source_object': source_obj,
                        'target_object': target_object,
                        'success': False,
                        'error': str(e),
                        'alignment_type': 'ARRAY',
                        'array_index': i
                    })
            
            return results
            
        except Exception as e:
            return [{
                'success': False,
                'error': str(e),
                'source_objects': source_objects,
                'target_object': target_object,
                'alignment_type': 'ARRAY'
            }]
    
    def _create_virtual_group(self, objects):
        """創建虛擬群組物件"""
        try:
            # 計算群組邊界框
            min_point = Vector((float('inf'),) * 3)
            max_point = Vector((float('-inf'),) * 3)
            
            total_center = Vector((0, 0, 0))
            
            for obj in objects:
                bbox = obj.bound_box
                for corner in bbox:
                    world_corner = obj.matrix_world @ corner
                    min_point.x = min(min_point.x, world_corner.x)
                    min_point.y = min(min_point.y, world_corner.y)
                    min_point.z = min(min_point.z, world_corner.z)
                    max_point.x = max(max_point.x, world_corner.x)
                    max_point.y = max(max_point.y, world_corner.y)
                    max_point.z = max(max_point.z, world_corner.z)
                
                total_center += get_bbox_center_world(obj)
            
            group_center = total_center / len(objects)
            
            # 創建虛擬群組物件
            virtual_group = type('VirtualGroup', (), {})()
            virtual_group.matrix_world = Matrix.Translation(group_center)
            virtual_group.bound_box = [
                Vector((min_point.x - group_center.x, min_point.y - group_center.y, min_point.z - group_center.z)),
                Vector((max_point.x - group_center.x, min_point.y - group_center.y, min_point.z - group_center.z)),
                Vector((min_point.x - group_center.x, max_point.y - group_center.y, min_point.z - group_center.z)),
                Vector((max_point.x - group_center.x, max_point.y - group_center.y, min_point.z - group_center.z)),
                Vector((min_point.x - group_center.x, min_point.y - group_center.y, max_point.z - group_center.z)),
                Vector((max_point.x - group_center.x, min_point.y - group_center.y, max_point.z - group_center.z)),
                Vector((min_point.x - group_center.x, max_point.y - group_center.y, max_point.z - group_center.z)),
                Vector((max_point.x - group_center.x, max_point.y - group_center.y, max_point.z - group_center.z))
            ]
            
            return {
                'success': True,
                'virtual_group': virtual_group
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_look_rotation(self, forward, target_direction):
        """計算看向目標方向的旋轉"""
        from mathutils import Quaternion
        
        # 確保向量已歸一化
        forward = forward.normalized()
        target_direction = target_direction.normalized()
        
        # 計算旋轉軸和角度
        axis = forward.cross(target_direction)
        angle = math.acos(max(-1, min(1, forward.dot(target_direction))))
        
        if axis.length < 0.001:
            # 如果向量平行或反向
            if forward.dot(target_direction) > 0:
                return Quaternion((1, 0, 0, 0))  # 無旋轉
            else:
                return Quaternion((1, 0, 0, math.pi))  # 180度旋轉
        
        axis = axis.normalized()
        return Quaternion(axis, angle)


# 全局多物件求解器實例
multi_object_solver = MultiObjectSolver()
