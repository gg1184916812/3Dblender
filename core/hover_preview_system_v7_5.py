"""
Smart Align Pro - Hover Preview System v7.5.0
Stability update: Anti-jitter, stable highlight, clear color distinction
"""

import bpy
from mathutils import Vector

class HoverPreviewSystem:
    def __init__(self):
        self.current_candidate = None
        self.last_candidate = None
        self.candidate_stick_time = 0
        self.stick_threshold_ms = 150
        self.candidates = []
        self.preview_objects = []
        
        self.COLOR_SOURCE = (1.0, 0.2, 0.2, 0.8)
        self.COLOR_TARGET = (0.2, 0.8, 0.2, 0.8)
        self.COLOR_CANDIDATE = (1.0, 1.0, 0.2, 0.6)
        self.COLOR_HOVER = (0.2, 0.2, 1.0, 0.9)
    
    def update_candidates(self, new_candidates, mouse_dist_threshold=50):
        if not new_candidates:
            self.candidates = []
            return
        
        for candidate in new_candidates:
            dist = candidate.get('distance', float('inf'))
            proximity = max(0, 1.0 - (dist / 100.0))
            priority = candidate.get('priority', 1.0)
            candidate['score'] = proximity * 0.7 + priority * 0.3
        
        new_candidates.sort(key=lambda c: c['score'], reverse=True)
        
        if self.current_candidate and len(new_candidates) > 0:
            current_score = self.current_candidate.get('score', 0)
            best_score = new_candidates[0].get('score', 0)
            
            if best_score < current_score * 1.15:
                new_candidates.insert(0, self.current_candidate)
        
        self.candidates = new_candidates
        if len(new_candidates) > 0:
            self.current_candidate = new_candidates[0]
    
    def get_preview_color_for_candidate(self, candidate_type):
        if candidate_type == "source":
            return self.COLOR_SOURCE
        elif candidate_type == "target":
            return self.COLOR_TARGET
        elif candidate_type == "hover":
            return self.COLOR_HOVER
        else:
            return self.COLOR_CANDIDATE
    
    def render_preview(self, source_point, target_point, highlight_candidate=None):
        preview_info = {
            'source': {'pos': source_point, 'color': self.COLOR_SOURCE, 'size': 10},
            'target': {'pos': target_point, 'color': self.COLOR_TARGET, 'size': 10},
            'highlight': {
                'pos': highlight_candidate,
                'color': self.COLOR_HOVER,
                'size': 8
            } if highlight_candidate else None
        }
        return preview_info
    
    def check_preview_consistency(self, preview_result, actual_result):
        if not preview_result or not actual_result:
            return False
        
        preview_pos = preview_result.get('pos')
        actual_pos = actual_result.get('pos')
        
        if preview_pos and actual_pos:
            diff = (preview_pos - actual_pos).length
            return diff < 0.001
        
        return True

_hover_preview_system = HoverPreviewSystem()

def get_hover_preview_system():
    return _hover_preview_system
