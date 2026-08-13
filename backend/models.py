from pydantic import BaseModel
from typing import List, Dict, Optional, Tuple
from enum import Enum

class NodeType(str, Enum):
    ENTRY = "entry"
    EXIT = "exit"
    CONCESSION = "concession"
    WALKWAY = "walkway"
    EMERGENCY_EXIT = "emergency_exit"
    JUNCTION = "junction"

class VenueNode(BaseModel):
    id: str
    name: str
    node_type: NodeType
    x: float                        # position on layout grid (0-100)
    y: float
    capacity: int                   # max people this node can hold safely
    current_occupancy: int = 0
    is_blocked: bool = False

class VenueEdge(BaseModel):
    id: str
    from_node: str
    to_node: str
    width: float                    # metres wide (affects flow rate)
    length: float                   # metres long
    is_bidirectional: bool = True
    current_flow: int = 0           # people per minute currently

class VenueLayout(BaseModel):
    venue_name: str
    nodes: List[VenueNode]
    edges: List[VenueEdge]
    total_capacity: int

class SimulationConfig(BaseModel):
    crowd_size: int
    event_duration_minutes: int
    arrival_pattern: str = "uniform"   # uniform, rush, staggered
    venue_layout: VenueLayout
    time_step_seconds: int = 30

class BottleneckAlert(BaseModel):
    node_id: str
    node_name: str
    severity: str                   # low, medium, high, critical
    occupancy_percent: float
    estimated_wait_minutes: float
    timestamp_seconds: int

class ReroutesuGgestion(BaseModel):
    from_node: str
    to_node: str
    alternative_path: List[str]
    original_path: List[str]
    time_saving_minutes: float
    reason: str

class SimulationResult(BaseModel):
    simulation_id: str
    total_time_seconds: int
    bottlenecks: List[BottleneckAlert]
    reroute_suggestions: List[ReroutesuGgestion]
    node_occupancy_timeline: Dict[str, List[int]]
    edge_flow_timeline: Dict[str, List[int]]
    ai_safety_report: str
    risk_score: float               # 0-100
    peak_congestion_time: int
