import networkx as nx
from typing import List, Dict, Tuple, Optional
from models import (
    VenueLayout, BottleneckAlert, ReroutesuGgestion,
    VenueNode, NodeType
)

class ReroutingEngine:
    """
    Generates alternative routing suggestions to relieve bottlenecks.
    Uses k-shortest paths to find viable alternatives,
    then scores them by estimated time saving and capacity relief.
    """
    
    def __init__(self, layout: VenueLayout):
        self.layout = layout
        self.node_map = {node.id: node for node in layout.nodes}
        self.graph = self._build_graph()

    def _build_graph(self) -> nx.DiGraph:
        G = nx.DiGraph()
        for node in self.layout.nodes:
            G.add_node(
                node.id,
                name=node.name,
                node_type=node.node_type,
                capacity=node.capacity
            )
        for edge in self.layout.edges:
            G.add_edge(
                edge.from_node, edge.to_node,
                weight=edge.length / 1.4,       # base travel time seconds
                width=edge.width,
                edge_id=edge.id
            )
            if edge.is_bidirectional:
                G.add_edge(
                    edge.to_node, edge.from_node,
                    weight=edge.length / 1.4,
                    width=edge.width,
                    edge_id=edge.id
                )
        return G

    def _get_path_travel_time(
        self, 
        path: List[str], 
        congested_nodes: set
    ) -> float:
        """Calculate total travel time for a path, penalising congested nodes."""
        total = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if self.graph.has_edge(u, v):
                base_time = self.graph[u][v].get("weight", 10)
                penalty = 3.0 if v in congested_nodes else 1.0
                total += base_time * penalty
        return total

    def _path_avoids_nodes(self, path: List[str], avoid: set) -> bool:
        """Check if a path avoids given nodes (except start/end)."""
        for node in path[1:-1]:  # Allow start and end
            if node in avoid:
                return False
        return True

    def _get_entry_to_exit_flows(self) -> List[Tuple[str, str]]:
        """Get common entry→exit pairs to consider for rerouting."""
        entries = [
            n.id for n in self.layout.nodes 
            if n.node_type == NodeType.ENTRY
        ]
        exits = [
            n.id for n in self.layout.nodes 
            if n.node_type in [NodeType.EXIT, NodeType.EMERGENCY_EXIT]
        ]
        concessions = [
            n.id for n in self.layout.nodes 
            if n.node_type == NodeType.CONCESSION
        ]
        
        flows = []
        for entry in entries:
            for dest in exits + concessions:
                if entry != dest:
                    flows.append((entry, dest))
        return flows

    def generate_suggestions(
        self,
        bottlenecks: List[BottleneckAlert],
        occupancy_snapshot: Dict[str, int]
    ) -> List[ReroutesuGgestion]:
        """
        For each bottleneck, find alternative paths that bypass it.
        Returns list of rerouting suggestions.
        """
        if not bottlenecks:
            return []
        
        suggestions: List[ReroutesuGgestion] = []
        congested_nodes = {b.node_id for b in bottlenecks}
        critical_nodes = {
            b.node_id for b in bottlenecks 
            if b.severity in ["critical", "high"]
        }
        
        flows = self._get_entry_to_exit_flows()
        
        for source, target in flows:
            try:
                # Find original shortest path
                original_path = nx.shortest_path(
                    self.graph, source, target, weight="weight"
                )
            except nx.NetworkXNoPath:
                continue
            
            # Check if original path goes through a bottleneck
            path_bottlenecks = [
                n for n in original_path[1:-1] 
                if n in congested_nodes
            ]
            
            if not path_bottlenecks:
                continue  # No rerouting needed for this flow
            
            # Find alternative paths using k-shortest paths (k=5)
            best_alternative = None
            best_time_saving = -float("inf")
            
            try:
                # Temporarily penalise bottleneck nodes in graph
                original_weights = {}
                for bn in critical_nodes:
                    for pred in self.graph.predecessors(bn):
                        if self.graph.has_edge(pred, bn):
                            original_weights[(pred, bn)] = (
                                self.graph[pred][bn]["weight"]
                            )
                            self.graph[pred][bn]["weight"] *= 10
                
                alt_path = nx.shortest_path(
                    self.graph, source, target, weight="weight"
                )
                
                # Restore weights
                for (u, v), w in original_weights.items():
                    self.graph[u][v]["weight"] = w
                    
            except nx.NetworkXNoPath:
                for (u, v), w in original_weights.items():
                    self.graph[u][v]["weight"] = w
                continue
            
            # Calculate time savings
            original_time = self._get_path_travel_time(
                original_path, congested_nodes
            ) / 60  # convert to minutes
            
            alt_time = self._get_path_travel_time(
                alt_path, set()
            ) / 60
            
            time_saving = original_time - alt_time
            
            # Only suggest if alternative is meaningful
            if alt_path != original_path and len(alt_path) > 1:
                avoided = [
                    n for n in path_bottlenecks 
                    if n not in alt_path
                ]
                
                if avoided:
                    source_name = self.node_map.get(
                        source, VenueNode(
                            id=source, name=source,
                            node_type=NodeType.JUNCTION,
                            x=0, y=0, capacity=100
                        )
                    ).name
                    target_name = self.node_map.get(
                        target, VenueNode(
                            id=target, name=target,
                            node_type=NodeType.JUNCTION,
                            x=0, y=0, capacity=100
                        )
                    ).name
                    
                    suggestion = ReroutesuGgestion(
                        from_node=source,
                        to_node=target,
                        alternative_path=alt_path,
                        original_path=original_path,
                        time_saving_minutes=round(time_saving, 2),
                        reason=(
                            f"Route via {source_name}→{target_name} passes "
                            f"through {len(path_bottlenecks)} congested zone(s). "
                            f"Alternative avoids: "
                            f"{', '.join(self.node_map[n].name for n in avoided if n in self.node_map)}."
                        )
                    )
                    suggestions.append(suggestion)
        
        # Deduplicate and prioritise
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            key = (s.from_node, s.to_node)
            if key not in seen:
                seen.add(key)
                unique_suggestions.append(s)
        
        return unique_suggestions[:10]  # Return top 10
