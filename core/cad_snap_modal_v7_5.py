"""
Smart Align Pro - CAD Snap Modal v7.5.0
Feel optimization: Direction hysteresis, confirm delay, visual feedback
"""

import bpy
from mathutils import Vector
import time

class CADSnapModal:
    def __init__(self):
        self.current_direction = None
        self.last_direction = None
        self.direction_confirm_time = 0
        self.direction_confirm_threshold_ms = 60
        
        self.hysteresis_threshold = 1.2
        self.deadzone_radius = 50
        
        self.DIRECTIONS = {
            'LEFT': (-1, 0),
            'RIGHT': (1, 0),
            'UP': (0, 1),
            'DOWN': (0, -1),
            'CENTER': (0, 0),
        }
        
        self.direction_colors = {
            'LEFT': (1.0, 0.0, 0.0, 1.0),
            'RIGHT': (0.0, 1.0, 0.0, 1.0),
            'UP': (0.0, 0.0, 1.0, 1.0),
            'DOWN': (1.0, 1.0, 0.0, 1.0),
            'CENTER': (0.5, 0.5, 0.5, 0.5),
        }
    
    def detect_direction(self, mouse_delta):
        dx, dy = mouse_delta
        dist = (dx**2 + dy**2) ** 0.5
        
        if dist < self.deadzone_radius:
            return ('CENTER', False)
        
        if abs(dx) > abs(dy):
            direction = 'RIGHT' if dx > 0 else 'LEFT'
        else:
            direction = 'UP' if dy > 0 else 'DOWN'
        
        return (direction, True)
    
    def apply_hysteresis(self, new_direction, is_confident):
        if not is_confident:
            return self.current_direction
        
        if self.current_direction is None:
            return new_direction
        
        if new_direction == self.current_direction:
            return new_direction
        
        return self.current_direction
    
    def apply_confirm_delay(self, direction):
        current_time = time.time() * 1000
        
        if direction != self.last_direction:
            self.direction_confirm_time = current_time
            self.last_direction = direction
            return False
        
        elapsed = current_time - self.direction_confirm_time
        if elapsed >= self.direction_confirm_threshold_ms:
            return True
        
        return False
    
    def get_direction_visual_feedback(self, direction):
        if direction == 'CENTER':
            return {
                'color': self.direction_colors['CENTER'],
                'text': 'CANCEL',
                'size': 24,
                'opacity': 0.3
            }
        else:
            return {
                'color': self.direction_colors.get(direction, (1, 1, 1, 1)),
                'text': direction,
                'size': 32,
                'opacity': 0.9
            }
    
    def differentiate_left_right(self, direction, action):
        if direction == 'LEFT':
            return {'axis': 'X', 'direction': -1, 'target': 'align_to_left'}
        elif direction == 'RIGHT':
            return {'axis': 'X', 'direction': 1, 'target': 'align_to_right'}
        elif direction == 'UP':
            return {'axis': 'Z', 'direction': 1, 'target': 'align_to_up'}
        elif direction == 'DOWN':
            return {'axis': 'Z', 'direction': -1, 'target': 'align_to_down'}
        
        return None

_cad_snap_modal = CADSnapModal()

def get_cad_snap_modal():
    return _cad_snap_modal
