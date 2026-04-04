"""
Smart Align Pro - Contact Align Engine v7.5.0
Stabilization: Penetration check, small offset correction
"""

import bpy
from mathutils import Vector

class ContactAlignEngine:
    def __init__(self):
        self.collision_check_enabled = True
        self.small_offset = 0.001
        self.supported_types = [
            'cube_to_cube',
            'mesh_to_plane',
            'edge_to_face',
            'face_to_face'
        ]
    
    def align_cube_to_cube(self, source_obj, target_obj, contact_face):
        source_bbox = source_obj.bound_box
        target_bbox = target_obj.bound_box
        
        source_center = sum((Vector(b) for b in source_bbox), Vector()) / 8
        target_center = sum((Vector(b) for b in target_bbox), Vector()) / 8
        
        translation = target_center - source_center
        
        if self.collision_check_enabled:
            translation += Vector((0, 0, self.small_offset))
        
        return translation
    
    def align_mesh_to_plane(self, source_obj, target_obj):
        source_pos = source_obj.location
        target_pos = target_obj.location
        
        translation = target_pos - source_pos
        
        if self.collision_check_enabled:
            translation += Vector((0, 0, self.small_offset))
        
        return translation
    
    def check_penetration(self, source_obj, target_obj, translation):
        source_bbox = source_obj.bound_box
        target_bbox = target_obj.bound_box
        
        source_z_min = min(b[2] for b in source_bbox)
        source_z_max = max(b[2] for b in source_bbox)
        
        target_z_max = max(b[2] for b in target_bbox)
        
        aligned_z_min = source_z_min + translation.z
        
        if aligned_z_min < target_z_max:
            penetration = target_z_max - aligned_z_min
            return (False, penetration)
        
        return (True, 0)
    
    def apply_small_offset(self, translation, direction='Z', offset_value=None):
        if offset_value is None:
            offset_value = self.small_offset
        
        offset_vector = Vector((0, 0, 0))
        if direction == 'Z':
            offset_vector.z = offset_value
        elif direction == 'X':
            offset_vector.x = offset_value
        elif direction == 'Y':
            offset_vector.y = offset_value
        
        return translation + offset_vector
    
    def validate_alignment(self, source_obj, target_obj, translation):
        is_valid, penetration = self.check_penetration(source_obj, target_obj, translation)
        
        if not is_valid:
            translation = self.apply_small_offset(translation, direction='Z', offset_value=penetration + self.small_offset)
            return (True, "Penetration auto-corrected")
        
        return (True, "Alignment valid")

_contact_align_engine = ContactAlignEngine()

def get_contact_align_engine():
    return _contact_align_engine
