"""Smart Align Pro - 統一對齊求解器引擎"""
from typing import Optional, Dict, Any
from enum import Enum
import logging
from .candidate_types import Candidate, CandidateCollection, CandidateType

logger = logging.getLogger("SmartAlignPro.UnifiedSolver")

class AlignmentIntent(Enum):
    POINT_TO_POINT = "point_to_point"
    EDGE_TO_EDGE = "edge_to_edge"
    FACE_TO_FACE = "face_to_face"
    NORMAL_ALIGN = "normal_align"
    THREE_POINT_MATCH = "three_point_match"
    OUTSIDE_CONTACT = "outside_contact"
    INSIDE_ALIGN = "inside_align"
    CENTER_ALIGN = "center_align"
    AXIS_ONLY_MOVE = "axis_only_move"

class AxisMask(Enum):
    X_ONLY = (1, 0, 0)
    Y_ONLY = (0, 1, 0)
    Z_ONLY = (0, 0, 1)
    XY_PLANE = (1, 1, 0)
    YZ_PLANE = (0, 1, 1)
    XZ_PLANE = (1, 0, 1)
    FREE = (1, 1, 1)

class AlignmentSolution:
    def __init__(self):
        self.translation = (0, 0, 0)
        self.rotation = (0, 0, 0)
        self.scale = (1, 1, 1)
        self.intent = None
        self.source_candidate = None
        self.target_candidate = None
        self.is_valid = False
        self.error_message = ""
        self.debug_log = {}
    
    def apply_axis_mask(self, mask):
        if isinstance(self.translation, tuple):
            t = list(self.translation)
        else:
            t = [self.translation.x, self.translation.y, self.translation.z]
        mask_tuple = mask.value
        t[0] *= mask_tuple[0]
        t[1] *= mask_tuple[1]
        t[2] *= mask_tuple[2]
        self.translation = tuple(t)

class UnifiedSolverEngine:
    def __init__(self):
        self.current_intent = None
        self.current_solution = None
        self.debug_mode = False
    
    def solve(self, intent, source_data, target_data, options=None):
        solution = AlignmentSolution()
        solution.intent = intent
        if options is None:
            options = {}
        try:
            if intent == AlignmentIntent.POINT_TO_POINT:
                self._solve_point_to_point(solution, source_data, target_data, options)
            elif intent == AlignmentIntent.AXIS_ONLY_MOVE:
                self._solve_axis_only_move(solution, source_data, target_data, options)
            else:
                solution.error_message = f"Unknown intent: {intent}"
                solution.is_valid = False
            if "axis_mask" in options and solution.is_valid:
                mask = options["axis_mask"]
                if isinstance(mask, AxisMask):
                    solution.apply_axis_mask(mask)
            self.current_solution = solution
            return solution
        except Exception as e:
            solution.is_valid = False
            solution.error_message = str(e)
            if self.debug_mode:
                import traceback
                logger.error(f"Solver error: {traceback.format_exc()}")
            return solution
    
    def _solve_point_to_point(self, solution, source_data, target_data, options):
        source_pos = source_data.get("position")
        target_pos = target_data.get("position")
        if source_pos is None or target_pos is None:
            solution.error_message = "Missing source or target position"
            solution.is_valid = False
            return
        if isinstance(source_pos, tuple):
            solution.translation = tuple(t - s for s, t in zip(source_pos, target_pos))
        else:
            solution.translation = target_pos - source_pos
        solution.is_valid = True
        solution.debug_log["method"] = "two_point_simple"
    
    def _solve_axis_only_move(self, solution, source_data, target_data, options):
        source_pos = source_data.get("position")
        target_pos = target_data.get("position")
        if source_pos is None or target_pos is None:
            solution.error_message = "Missing source or target position"
            solution.is_valid = False
            return
        if isinstance(source_pos, tuple):
            solution.translation = tuple(t - s for s, t in zip(source_pos, target_pos))
        else:
            solution.translation = target_pos - source_pos
        solution.rotation = (0, 0, 0)
        solution.is_valid = True
        solution.debug_log["method"] = "axis_only_move"

_unified_solver = UnifiedSolverEngine()

def get_unified_solver():
    return _unified_solver
