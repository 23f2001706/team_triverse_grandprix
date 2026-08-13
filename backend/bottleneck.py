from typing import List, Dict, Tuple
from models import (
    VenueLayout, BottleneckAlert, VenueNode, NodeType
)

class BottleneckDetector:
    """
    Analyses occupancy timelines to identify bottlenecks.
    Uses threshold-based severity scoring and persistence checking
    (a bottleneck is only flagged if congestion persists, 
    not just a single spike).
    """
    
    # Occupancy thresholds as fraction of capacity
    THRESHOLDS = {
        "low":      0.60,
        "medium":   0.75,
        "high":     0.88,
        "critical": 0.95
    }
    
    # Minimum consecutive steps to flag as bottleneck
    PERSISTENCE_STEPS = 3
    
    def __init__(self, layout: VenueLayout, time_step_seconds: int = 30):
        self.layout = layout
        self.time_step_seconds = time_step_seconds
        self.node_map = {node.id: node for node in layout.nodes}

    def _get_severity(self, occupancy_ratio: float) -> str:
        if occupancy_ratio >= self.THRESHOLDS["critical"]:
            return "critical"
        elif occupancy_ratio >= self.THRESHOLDS["high"]:
            return "high"
        elif occupancy_ratio >= self.THRESHOLDS["medium"]:
            return "medium"
        elif occupancy_ratio >= self.THRESHOLDS["low"]:
            return "low"
        return "none"

    def _estimate_wait_time(
        self, 
        node: VenueNode, 
        occupancy: int,
        incoming_flow: int
    ) -> float:
        """
        Little's Law approximation: W = L / λ
        W = average wait time
        L = average number in queue (occupancy above comfortable level)
        λ = arrival rate (incoming_flow)
        """
        excess = max(0, occupancy - int(node.capacity * 0.7))
        flow = max(1, incoming_flow)
        wait_minutes = (excess / flow) * (self.time_step_seconds / 60)
        return round(wait_minutes, 2)

    def detect(
        self,
        occupancy_timeline: Dict[str, List[int]],
        flow_timeline: Dict[str, List[int]]
    ) -> List[BottleneckAlert]:
        """
        Scan timeline for bottleneck events.
        Returns list of BottleneckAlert ordered by severity and time.
        """
        alerts: List[BottleneckAlert] = []
        seen_alerts = set()  # Avoid duplicate alerts for same node
        
        for node_id, occupancy_series in occupancy_timeline.items():
            node = self.node_map.get(node_id)
            if not node:
                continue
            
            consecutive_congestion = 0
            max_severity = "none"
            max_occupancy = 0
            max_step = 0
            
            for step, occupancy in enumerate(occupancy_series):
                ratio = occupancy / max(node.capacity, 1)
                severity = self._get_severity(ratio)
                
                if severity != "none":
                    consecutive_congestion += 1
                    if occupancy > max_occupancy:
                        max_occupancy = occupancy
                        max_step = step
                    
                    # Track worst severity
                    severity_rank = ["none", "low", "medium", "high", "critical"]
                    if (severity_rank.index(severity) > 
                            severity_rank.index(max_severity)):
                        max_severity = severity
                    
                    # Flag if persistent enough
                    if (consecutive_congestion >= self.PERSISTENCE_STEPS and 
                            node_id not in seen_alerts):
                        
                        # Estimate incoming flow to that node
                        incoming_flow = max_occupancy // max(max_step, 1)
                        wait_mins = self._estimate_wait_time(
                            node, max_occupancy, incoming_flow
                        )
                        
                        alert = BottleneckAlert(
                            node_id=node_id,
                            node_name=node.name,
                            severity=max_severity,
                            occupancy_percent=round(
                                (max_occupancy / node.capacity) * 100, 1
                            ),
                            estimated_wait_minutes=wait_mins,
                            timestamp_seconds=max_step * self.time_step_seconds
                        )
                        alerts.append(alert)
                        seen_alerts.add(node_id)
                else:
                    consecutive_congestion = 0
        
        # Sort: critical first, then by occupancy %
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: (
            severity_order.get(a.severity, 4),
            -a.occupancy_percent
        ))
        
        return alerts

    def compute_risk_score(self, alerts: List[BottleneckAlert]) -> float:
        """
        Overall venue risk score 0-100.
        Weighted by severity and number of bottlenecks.
        """
        if not alerts:
            return 0.0
        
        severity_weights = {
            "critical": 40,
            "high": 20,
            "medium": 8,
            "low": 2
        }
        
        raw_score = sum(
            severity_weights.get(a.severity, 0) for a in alerts
        )
        
        # Cap at 100
        return min(100.0, round(raw_score, 1))from typing import List, Dict, Tuple
from models import (
    VenueLayout, BottleneckAlert, VenueNode, NodeType
)

class BottleneckDetector:
    """
    Analyses occupancy timelines to identify bottlenecks.
    Uses threshold-based severity scoring and persistence checking
    (a bottleneck is only flagged if congestion persists, 
    not just a single spike).
    """
    
    # Occupancy thresholds as fraction of capacity
    THRESHOLDS = {
        "low":      0.60,
        "medium":   0.75,
        "high":     0.88,
        "critical": 0.95
    }
    
    # Minimum consecutive steps to flag as bottleneck
    PERSISTENCE_STEPS = 3
    
    def __init__(self, layout: VenueLayout, time_step_seconds: int = 30):
        self.layout = layout
        self.time_step_seconds = time_step_seconds
        self.node_map = {node.id: node for node in layout.nodes}

    def _get_severity(self, occupancy_ratio: float) -> str:
        if occupancy_ratio >= self.THRESHOLDS["critical"]:
            return "critical"
        elif occupancy_ratio >= self.THRESHOLDS["high"]:
            return "high"
        elif occupancy_ratio >= self.THRESHOLDS["medium"]:
            return "medium"
        elif occupancy_ratio >= self.THRESHOLDS["low"]:
            return "low"
        return "none"

    def _estimate_wait_time(
        self, 
        node: VenueNode, 
        occupancy: int,
        incoming_flow: int
    ) -> float:
        """
        Little's Law approximation: W = L / λ
        W = average wait time
        L = average number in queue (occupancy above comfortable level)
        λ = arrival rate (incoming_flow)
        """
        excess = max(0, occupancy - int(node.capacity * 0.7))
        flow = max(1, incoming_flow)
        wait_minutes = (excess / flow) * (self.time_step_seconds / 60)
        return round(wait_minutes, 2)

    def detect(
        self,
        occupancy_timeline: Dict[str, List[int]],
        flow_timeline: Dict[str, List[int]]
    ) -> List[BottleneckAlert]:
        """
        Scan timeline for bottleneck events.
        Returns list of BottleneckAlert ordered by severity and time.
        """
        alerts: List[BottleneckAlert] = []
        seen_alerts = set()  # Avoid duplicate alerts for same node
        
        for node_id, occupancy_series in occupancy_timeline.items():
            node = self.node_map.get(node_id)
            if not node:
                continue
            
            consecutive_congestion = 0
            max_severity = "none"
            max_occupancy = 0
            max_step = 0
            
            for step, occupancy in enumerate(occupancy_series):
                ratio = occupancy / max(node.capacity, 1)
                severity = self._get_severity(ratio)
                
                if severity != "none":
                    consecutive_congestion += 1
                    if occupancy > max_occupancy:
                        max_occupancy = occupancy
                        max_step = step
                    
                    # Track worst severity
                    severity_rank = ["none", "low", "medium", "high", "critical"]
                    if (severity_rank.index(severity) > 
                            severity_rank.index(max_severity)):
                        max_severity = severity
                    
                    # Flag if persistent enough
                    if (consecutive_congestion >= self.PERSISTENCE_STEPS and 
                            node_id not in seen_alerts):
                        
                        # Estimate incoming flow to that node
                        incoming_flow = max_occupancy // max(max_step, 1)
                        wait_mins = self._estimate_wait_time(
                            node, max_occupancy, incoming_flow
                        )
                        
                        alert = BottleneckAlert(
                            node_id=node_id,
                            node_name=node.name,
                            severity=max_severity,
                            occupancy_percent=round(
                                (max_occupancy / node.capacity) * 100, 1
                            ),
                            estimated_wait_minutes=wait_mins,
                            timestamp_seconds=max_step * self.time_step_seconds
                        )
                        alerts.append(alert)
                        seen_alerts.add(node_id)
                else:
                    consecutive_congestion = 0
        
        # Sort: critical first, then by occupancy %
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts.sort(key=lambda a: (
            severity_order.get(a.severity, 4),
            -a.occupancy_percent
        ))
        
        return alerts

    def compute_risk_score(self, alerts: List[BottleneckAlert]) -> float:
        """
        Overall venue risk score 0-100.
        Weighted by severity and number of bottlenecks.
        """
        if not alerts:
            return 0.0
        
        severity_weights = {
            "critical": 40,
            "high": 20,
            "medium": 8,
            "low": 2
        }
        
        raw_score = sum(
            severity_weights.get(a.severity, 0) for a in alerts
        )
        
        # Cap at 100
        return min(100.0, round(raw_score, 1))
