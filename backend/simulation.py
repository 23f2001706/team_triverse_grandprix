import numpy as np
import networkx as nx
from typing import Dict, List, Tuple
import random
from models import (
    VenueLayout, SimulationConfig, VenueNode, 
    VenueEdge, NodeType
)

class CrowdSimulator:
    """
    Agent-based crowd flow simulator using a graph network.
    Each node has a capacity, each edge has a flow rate limit.
    People move through the network following shortest paths,
    with congestion slowing movement and causing spillback.
    """

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.layout = config.venue_layout
        self.graph = self._build_graph()
        
        # State tracking
        self.node_occupancy: Dict[str, int] = {
            node.id: 0 for node in self.layout.nodes
        }
        self.edge_flow: Dict[str, int] = {
            edge.id: 0 for edge in self.layout.edges
        }
        
        # Timeline recording
        self.occupancy_timeline: Dict[str, List[int]] = {
            node.id: [] for node in self.layout.nodes
        }
        self.flow_timeline: Dict[str, List[int]] = {
            edge.id: [] for edge in self.layout.edges
        }
        
        # Agent tracking: {agent_id: (current_node, destination, path)}
        self.agents: Dict[int, Dict] = {}
        self.agent_counter = 0
        self.completed_agents = 0
        
        # Node lookup
        self.node_map: Dict[str, VenueNode] = {
            node.id: node for node in self.layout.nodes
        }
        self.edge_map: Dict[str, VenueEdge] = {
            edge.id: edge for edge in self.layout.edges
        }

    def _build_graph(self) -> nx.DiGraph:
        """Build a directed graph from venue layout."""
        G = nx.DiGraph()
        
        for node in self.layout.nodes:
            G.add_node(
                node.id,
                node_type=node.node_type,
                capacity=node.capacity,
                x=node.x,
                y=node.y,
                name=node.name
            )
        
        for edge in self.layout.edges:
            # Weight = travel time in seconds (length / walking_speed)
            # Walking speed ~1.4 m/s, slowed by width constraints
            base_travel_time = edge.length / 1.4
            G.add_edge(
                edge.from_node,
                edge.to_node,
                weight=base_travel_time,
                width=edge.width,
                length=edge.length,
                edge_id=edge.id,
                capacity=int(edge.width * 80)  # ~80 people per metre width per min
            )
            if edge.is_bidirectional:
                G.add_edge(
                    edge.to_node,
                    edge.from_node,
                    weight=base_travel_time,
                    width=edge.width,
                    length=edge.length,
                    edge_id=edge.id,
                    capacity=int(edge.width * 80)
                )
        return G

    def _get_entry_nodes(self) -> List[str]:
        return [n.id for n in self.layout.nodes if n.node_type == NodeType.ENTRY]

    def _get_exit_nodes(self) -> List[str]:
        return [
            n.id for n in self.layout.nodes 
            if n.node_type in [NodeType.EXIT, NodeType.EMERGENCY_EXIT]
        ]

    def _get_concession_nodes(self) -> List[str]:
        return [n.id for n in self.layout.nodes if n.node_type == NodeType.CONCESSION]

    def _compute_congestion_weight(self, node_id: str) -> float:
        """
        Returns a congestion multiplier for edge weights near a node.
        Higher occupancy → slower movement → higher effective weight.
        """
        node = self.node_map[node_id]
        occ = self.node_occupancy.get(node_id, 0)
        ratio = occ / max(node.capacity, 1)
        
        if ratio < 0.5:
            return 1.0
        elif ratio < 0.7:
            return 1.5
        elif ratio < 0.85:
            return 2.5
        elif ratio < 0.95:
            return 5.0
        else:
            return 10.0  # Near jam conditions

    def _find_best_path(self, source: str, target: str) -> List[str]:
        """Find shortest path considering current congestion."""
        try:
            # Temporarily adjust weights based on congestion
            for u, v, data in self.graph.edges(data=True):
                congestion_u = self._compute_congestion_weight(u)
                congestion_v = self._compute_congestion_weight(v)
                data['dynamic_weight'] = (
                    data['weight'] * max(congestion_u, congestion_v)
                )
            
            path = nx.shortest_path(
                self.graph, source, target, weight='dynamic_weight'
            )
            return path
        except nx.NetworkXNoPath:
            return []

    def _spawn_agents(self, time_step: int, total_steps: int) -> int:
        """Spawn agents at entry nodes based on arrival pattern."""
        entry_nodes = self._get_entry_nodes()
        if not entry_nodes:
            return 0
        
        crowd_size = self.config.crowd_size
        
        if self.config.arrival_pattern == "uniform":
            # Spread evenly across first 60% of event
            arrival_window = int(total_steps * 0.6)
            agents_per_step = crowd_size / max(arrival_window, 1)
            if time_step > arrival_window:
                return 0
            spawned = int(agents_per_step)
            
        elif self.config.arrival_pattern == "rush":
            # 70% arrive in first 20% of event
            rush_window = int(total_steps * 0.2)
            if time_step < rush_window:
                spawned = int((crowd_size * 0.7) / rush_window)
            elif time_step < total_steps * 0.6:
                spawned = int((crowd_size * 0.3) / (total_steps * 0.4))
            else:
                return 0
                
        elif self.config.arrival_pattern == "staggered":
            # Waves every 20% of event
            wave_size = crowd_size // 5
            wave_length = total_steps // 5
            if time_step % wave_length < wave_length * 0.3:
                spawned = int(wave_size / (wave_length * 0.3))
            else:
                return 0
        else:
            spawned = 0

        # Create agents with random entry points and destinations
        exit_nodes = self._get_exit_nodes()
        concession_nodes = self._get_concession_nodes()
        
        for _ in range(spawned):
            entry = random.choice(entry_nodes)
            
            # 60% go to concessions first, 40% go straight to exits/interior
            if concession_nodes and random.random() < 0.6:
                target = random.choice(concession_nodes)
            elif exit_nodes:
                target = random.choice(exit_nodes)
            else:
                continue
            
            path = self._find_best_path(entry, target)
            if not path:
                continue
            
            agent_id = self.agent_counter
            self.agent_counter += 1
            self.agents[agent_id] = {
                "current_node": entry,
                "path": path,
                "path_index": 0,
                "steps_in_current_node": 0,
                "wait_time": 0
            }
            
            # Add to node occupancy
            if self.node_occupancy[entry] < self.node_map[entry].capacity * 1.2:
                self.node_occupancy[entry] = min(
                    self.node_occupancy[entry] + 1,
                    self.node_map[entry].capacity + 10
                )
        
        return spawned

    def _move_agents(self):
        """Advance all agents one time step along their paths."""
        agents_to_remove = []
        
        for agent_id, agent in self.agents.items():
            current = agent["current_node"]
            path = agent["path"]
            idx = agent["path_index"]
            
            # Check if agent reached destination
            if idx >= len(path) - 1:
                # Agent completed journey
                self.node_occupancy[current] = max(
                    0, self.node_occupancy[current] - 1
                )
                self.completed_agents += 1
                agents_to_remove.append(agent_id)
                continue
            
            next_node = path[idx + 1]
            
            # Check congestion at next node
            next_cap = self.node_map[next_node].capacity
            next_occ = self.node_occupancy.get(next_node, 0)
            congestion_ratio = next_occ / max(next_cap, 1)
            
            # Probability of moving depends on congestion
            move_prob = max(0.1, 1.0 - congestion_ratio * 0.8)
            
            if random.random() < move_prob:
                # Move to next node
                self.node_occupancy[current] = max(
                    0, self.node_occupancy[current] - 1
                )
                self.node_occupancy[next_node] = min(
                    self.node_occupancy.get(next_node, 0) + 1,
                    next_cap + 20  # Allow slight overflow to model real danger
                )
                agent["path_index"] += 1
                agent["current_node"] = next_node
                agent["steps_in_current_node"] = 0
                
                # Update edge flow
                if self.graph.has_edge(current, next_node):
                    edge_data = self.graph[current][next_node]
                    eid = edge_data.get("edge_id", f"{current}-{next_node}")
                    if eid in self.edge_flow:
                        self.edge_flow[eid] = min(
                            self.edge_flow[eid] + 1,
                            edge_data.get("capacity", 100)
                        )
            else:
                agent["steps_in_current_node"] += 1
                agent["wait_time"] += 1
        
        # Remove completed agents
        for aid in agents_to_remove:
            del self.agents[aid]
        
        # Decay edge flows slightly (people keep moving out)
        for eid in self.edge_flow:
            self.edge_flow[eid] = max(0, int(self.edge_flow[eid] * 0.85))

    def _record_state(self):
        """Record current state to timelines."""
        for node_id in self.node_occupancy:
            self.occupancy_timeline[node_id].append(
                self.node_occupancy[node_id]
            )
        for edge_id in self.edge_flow:
            self.flow_timeline[edge_id].append(self.edge_flow[edge_id])

    def run(self) -> Tuple[Dict, Dict, Dict]:
        """
        Run the full simulation.
        Returns: occupancy_timeline, flow_timeline, peak_data
        """
        total_steps = (
            self.config.event_duration_minutes * 60 
            // self.config.time_step_seconds
        )
        
        peak_data = {
            "max_occupancies": {},
            "peak_step": 0,
            "peak_total_crowd": 0
        }
        
        print(f"Running simulation: {total_steps} steps, "
              f"{self.config.crowd_size} people")
        
        for step in range(total_steps):
            # Spawn new arrivals
            self._spawn_agents(step, total_steps)
            
            # Move existing agents
            self._move_agents()
            
            # Record state
            self._record_state()
            
            # Track peak
            total_crowd = sum(self.node_occupancy.values())
            if total_crowd > peak_data["peak_total_crowd"]:
                peak_data["peak_total_crowd"] = total_crowd
                peak_data["peak_step"] = step
                peak_data["max_occupancies"] = dict(self.node_occupancy)
            
            # Progress every 10%
            if step % max(1, total_steps // 10) == 0:
                print(f"  Step {step}/{total_steps} | "
                      f"Active agents: {len(self.agents)} | "
                      f"Completed: {self.completed_agents}")
        
        return (
            self.occupancy_timeline, 
            self.flow_timeline, 
            peak_data
        )
