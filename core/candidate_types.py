"""Smart Align Pro - 統一候選點數據結構"""
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum

class CandidateType(Enum):
    POINT = "point"
    VERTEX = "vertex"
    EDGE_CENTER = "edge_center"
    EDGE_MIDPOINT = "edge_midpoint"
    FACE_CENTER = "face_center"
    FACE_NORMAL = "face_normal"
    BBOX_CORNER = "bbox_corner"
    BBOX_FACE_CENTER = "bbox_face_center"
    BBOX_EDGE_CENTER = "bbox_edge_center"
    OBJECT_CENTER = "object_center"
    PROJECTED_CONTACT = "projected_contact"
    SURFACE_CONTACT = "surface_contact"
    CUSTOM = "custom"

class CandidatePriority(Enum):
    CRITICAL = 10
    HIGH = 5
    NORMAL = 3
    LOW = 1
    IGNORE = 0

@dataclass
class Candidate:
    type: CandidateType
    priority: CandidatePriority = CandidatePriority.NORMAL
    unique_id: str = ""
    world_position: Any = field(default_factory=lambda: (0, 0, 0))
    local_position: Optional[Any] = None
    normal: Any = field(default_factory=lambda: (0, 0, 1))
    tangent: Optional[Any] = None
    bitangent: Optional[Any] = None
    source_object: Optional[Any] = None
    source_data_index: int = -1
    available_for_modes: List[str] = field(default_factory=list)
    is_valid: bool = True
    label: str = ""
    display_color: Tuple[float, float, float, float] = (1.0, 1.0, 0.0, 1.0)
    display_size: float = 8.0
    distance_to_mouse: float = float('inf')
    proximity_score: float = 0.0
    relevance_score: float = 0.0
    combined_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.unique_id:
            self.unique_id = self._generate_id()
    
    def _generate_id(self) -> str:
        obj_name = self.source_object.name if self.source_object else "unknown"
        return f"{obj_name}_{self.type.value}_{self.source_data_index}_{id(self)}"
    
    def copy(self):
        import copy
        return copy.deepcopy(self)
    
    def set_display(self, color, size=8.0):
        self.display_color = color
        self.display_size = size
        return self
    
    def calculate_score(self, mouse_dist, relevance=1.0):
        self.distance_to_mouse = mouse_dist
        self.relevance_score = relevance
        self.proximity_score = max(0, 1.0 - (mouse_dist / 100.0))
        self.combined_score = (self.proximity_score * 0.6 + (self.priority.value / 10.0) * 0.2 + self.relevance_score * 0.2)
        return self.combined_score

@dataclass
class CandidateCollection:
    candidates: List[Candidate] = field(default_factory=list)
    current_index: int = -1
    
    def add(self, candidate):
        if candidate.is_valid:
            self.candidates.append(candidate)
    
    def clear(self):
        self.candidates.clear()
        self.current_index = -1
    
    def sort_by_score(self):
        self.candidates.sort(key=lambda c: c.combined_score, reverse=True)
        if len(self.candidates) > 0:
            self.current_index = 0
    
    def cycle_next(self):
        if not self.candidates:
            return None
        self.current_index = (self.current_index + 1) % len(self.candidates)
        return self.get_current()
    
    def cycle_prev(self):
        if not self.candidates:
            return None
        self.current_index = (self.current_index - 1) % len(self.candidates)
        return self.get_current()
    
    def get_current(self):
        if 0 <= self.current_index < len(self.candidates):
            return self.candidates[self.current_index]
        return None
    
    def get_best(self):
        if not self.candidates:
            return None
        return max(self.candidates, key=lambda c: c.combined_score)
    
    def count_by_type(self, candidate_type):
        return sum(1 for c in self.candidates if c.type == candidate_type)
    
    def __len__(self):
        return len(self.candidates)
