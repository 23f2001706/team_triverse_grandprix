import uuid
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import json

from models import (
    SimulationConfig, SimulationResult, VenueLayout,
    VenueNode, VenueEdge, NodeType
)
from simulation import CrowdSimulator
from bottleneck import BottleneckDetector
from rerouting import ReroutingEngine
from ai_advisor import AIAdvisor

app = FastAPI(
    title="Crowd Flow Optimiser API",
    description="Real-time crowd simulation and bottleneck detection",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise AI advisor (token from env)
HF_TOKEN = os.getenv("HF_TOKEN", None)
ai_advisor = AIAdvisor(hf_token=HF_TOKEN)

# Cache recent simulation results
simulation_cache: Dict[str, SimulationResult] = {}


def get_default_stadium_layout() -> VenueLayout:
    """Returns a pre-built stadium venue layout for demo purposes."""
    nodes = [
        # Entry gates
        VenueNode(id="gate_north", name="North Entry Gate", 
                  node_type=NodeType.ENTRY, x=50, y=5, capacity=200),
        VenueNode(id="gate_south", name="South Entry Gate", 
                  node_type=NodeType.ENTRY, x=50, y=95, capacity=200),
        VenueNode(id="gate_east", name="East Entry Gate", 
                  node_type=NodeType.ENTRY, x=95, y=50, capacity=150),
        VenueNode(id="gate_west", name="West Entry Gate", 
                  node_type=NodeType.ENTRY, x=5, y=50, capacity=150),
        
        # Main concourses / junctions
        VenueNode(id="concourse_north", name="North Concourse", 
                  node_type=NodeType.JUNCTION, x=50, y=20, capacity=500),
        VenueNode(id="concourse_south", name="South Concourse", 
                  node_type=NodeType.JUNCTION, x=50, y=80, capacity=500),
        VenueNode(id="concourse_east", name="East Concourse", 
                  node_type=NodeType.JUNCTION, x=80, y=50, capacity=400),
        VenueNode(id="concourse_west", name="West Concourse", 
                  node_type=NodeType.JUNCTION, x=20, y=50, capacity=400),
        VenueNode(id="central_plaza", name="Central Plaza", 
                  node_type=NodeType.JUNCTION, x=50, y=50, capacity=800),
        
        # Concession stands
        VenueNode(id="food_north", name="Food Court North", 
                  node_type=NodeType.CONCESSION, x=35, y=25, capacity=150),
        VenueNode(id="food_south", name="Food Court South", 
                  node_type=NodeType.CONCESSION, x=65, y=75, capacity=150),
        VenueNode(id="bar_east", name="East Bar", 
                  node_type=NodeType.CONCESSION, x=75, y=35, capacity=100),
        VenueNode(id="bar_west", name="West Bar", 
                  node_type=NodeType.CONCESSION, x=25, y=65, capacity=100),
        
        # Exits
        VenueNode(id="exit_main", name="Main Exit", 
                  node_type=NodeType.EXIT, x=50, y=2, capacity=300),
        VenueNode(id="exit_south", name="South Exit", 
                  node_type=NodeType.EXIT, x=50, y=98, capacity=250),
        
        # Emergency exits
        VenueNode(id="emg_exit_ne", name="Emergency Exit NE", 
                  node_type=NodeType.EMERGENCY_EXIT, x=90, y=10, capacity=200),
        VenueNode(id="emg_exit_sw", name="Emergency Exit SW", 
                  node_type=NodeType.EMERGENCY_EXIT, x=10, y=90, capacity=200),
    ]
    
    edges = [
        # Gate connections
        VenueEdge(id="e1", from_node="gate_north", to_node="concourse_north",
                  width=8, length=20),
        VenueEdge(id="e2", from_node="gate_south", to_node="concourse_south",
                  width=8, length=20),
        VenueEdge(id="e3", from_node="gate_east", to_node="concourse_east",
                  width=6, length=20),
        VenueEdge(id="e4", from_node="gate_west", to_node="concourse_west",
                  width=6, length=20),
        
        # Concourse connections
        VenueEdge(id="e5", from_node="concourse_north", to_node="central_plaza",
                  width=10, length=30),
        VenueEdge(id="e6", from_node="concourse_south", to_node="central_plaza",
                  width=10, length=30),
        VenueEdge(id="e7", from_node="concourse_east", to_node="central_plaza",
                  width=8, length=35),
        VenueEdge(id="e8", from_node="concourse_west", to_node="central_plaza",
                  width=8, length=35),
        
        # Cross connections
        VenueEdge(id="e9", from_node="concourse_north", to_node="concourse_east",
                  width=5, length=40),
        VenueEdge(id="e10", from_node="concourse_north", to_node="concourse_west",
                  width=5, length=40),
        VenueEdge(id="e11", from_node="concourse_south", to_node="concourse_east",
                  width=5, length=40),
        VenueEdge(id="e12", from_node="concourse_south", to_node="concourse_west",
                  width=5, length=40),
        
        # Food/bar connections
        VenueEdge(id="e13", from_node="concourse_north", to_node="food_north",
                  width=4, length=15),
        VenueEdge(id="e14", from_node="concourse_south", to_node="food_south",
                  width=4, length=15),
        VenueEdge(id="e15", from_node="concourse_east", to_node="bar_east",
                  width=3, length=15),
        VenueEdge(id="e16", from_node="concourse_west", to_node="bar_west",
                  width=3, length=15),
        
        # Exit connections
        VenueEdge(id="e17", from_node="concourse_north", to_node="exit_main",
                  width=12, length=15),
        VenueEdge(id="e18", from_node="concourse_south", to_node="exit_south",
                  width=10, length=15),
        
        # Emergency exit connections
        VenueEdge(id="e19", from_node="concourse_east", to_node="emg_exit_ne",
                  width=6, length=25, is_bidirectional=False),
        VenueEdge(id="e20", from_node="concourse_west", to_node="emg_exit_sw",
                  width=6, length=25, is_bidirectional=False),
        VenueEdge(id="e21", from_node="central_plaza", to_node="exit_main",
                  width=8, length=45),
        VenueEdge(id="e22", from_node="central_plaza", to_node="exit_south",
                  width=8, length=45),
    ]
    
    return VenueLayout(
        venue_name="Stadium Demo",
        nodes=nodes,
        edges=edges,
        total_capacity=sum(n.capacity for n in nodes)
    )


def get_festival_layout() -> VenueLayout:
    """Festival ground layout with multiple stages."""
    nodes = [
        VenueNode(id="main_entrance", name="Main Entrance", 
                  node_type=NodeType.ENTRY, x=50, y=2, capacity=300),
        VenueNode(id="side_entrance_l", name="Left Side Entrance", 
                  node_type=NodeType.ENTRY, x=5, y=30, capacity=150),
        VenueNode(id="side_entrance_r", name="Right Side Entrance", 
                  node_type=NodeType.ENTRY, x=95, y=30, capacity=150),
        
        VenueNode(id="main_stage_area", name="Main Stage Area", 
                  node_type=NodeType.JUNCTION, x=50, y=40, capacity=2000),
        VenueNode(id="stage_b", name="Stage B Area", 
                  node_type=NodeType.JUNCTION, x=20, y=65, capacity=800),
        VenueNode(id="stage_c", name="Stage C Area", 
                  node_type=NodeType.JUNCTION, x=80, y=65, capacity=800),
        
        VenueNode(id="food_village", name="Food Village", 
                  node_type=NodeType.CONCESSION, x=50, y=70, capacity=400),
        VenueNode(id="bar_left", name="Bar Left", 
                  node_type=NodeType.CONCESSION, x=15, y=50, capacity=200),
        VenueNode(id="bar_right", name="Bar Right", 
                  node_type=NodeType.CONCESSION, x=85, y=50, capacity=200),
        
        VenueNode(id="main_exit", name="Main Exit", 
                  node_type=NodeType.EXIT, x=50, y=98, capacity=400),
        VenueNode(id="emg_left", name="Emergency Left", 
                  node_type=NodeType.EMERGENCY_EXIT, x=2, y=80, capacity=300),
        VenueNode(id="emg_right", name="Emergency Right", 
                  node_type=NodeType.EMERGENCY_EXIT, x=98, y=80, capacity=300),
    ]
    
    edges = [
        VenueEdge(id="f1", from_node="main_entrance", 
                  to_node="main_stage_area", width=15, length=40),
        VenueEdge(id="f2", from_node="side_entrance_l", 
                  to_node="stage_b", width=8, length=35),
        VenueEdge(id="f3", from_node="side_entrance_r", 
                  to_node="stage_c", width=8, length=35),
        VenueEdge(id="f4", from_node="main_stage_area", 
                  to_node="stage_b", width=10, length=40),
        VenueEdge(id="f5", from_node="main_stage_area", 
                  to_node="stage_c", width=10, length=40),
        VenueEdge(id="f6", from_node="main_stage_area", 
                  to_node="food_village", width=12, length=30),
        VenueEdge(id="f7", from_node="stage_b", 
                  to_node="bar_left", width=5, length=20),
        VenueEdge(id="f8", from_node="stage_c", 
                  to_node="bar_right", width=5, length=20),
        VenueEdge(id="f9", from_node="food_village", 
                  to_node="main_exit", width=15, length=30),
        VenueEdge(id="f10", from_node="stage_b", 
                  to_node="emg_left", width=8, length=20, is_bidirectional=False),
        VenueEdge(id="f11", from_node="stage_c", 
                  to_node="emg_right", width=8, length=20, is_bidirectional=False),
        VenueEdge(id="f12", from_node="main_stage_area", 
                  to_node="main_exit", width=10, length=60),
    ]
    
    return VenueLayout(
        venue_name="Festival Grounds",
        nodes=nodes,
        edges=edges,
        total_capacity=sum(n.capacity for n in nodes)
    )


@app.get("/")
def root():
    return {
        "message": "Crowd Flow Optimiser API",
        "version": "1.0.0",
        "endpoints": ["/simulate", "/venue/stadium", 
                      "/venue/festival", "/results/{id}"]
    }


@app.get("/venue/stadium")
def get_stadium_layout():
    """Return the default stadium venue layout."""
    layout = get_default_stadium_layout()
    return layout.dict()


@app.get("/venue/festival")
def get_festival_layout_endpoint():
    """Return the festival grounds layout."""
    layout = get_festival_layout()
    return layout.dict()


@app.post("/simulate")
def run_simulation(config: SimulationConfig) -> Dict[str, Any]:
    """
    Run crowd flow simulation with given configuration.
    Returns simulation ID and full results.
    """
    sim_id = str(uuid.uuid4())[:8]
    
    try:
        # ── 1. Run crowd simulation ──────────────────────────────────
        print(f"\n[{sim_id}] Starting simulation...")
        simulator = CrowdSimulator(config)
        occupancy_timeline, flow_timeline, peak_data = simulator.run()
        
        # ── 2. Detect bottlenecks ────────────────────────────────────
        print(f"[{sim_id}] Detecting bottlenecks...")
        detector = BottleneckDetector(
            config.venue_layout, 
            config.time_step_seconds
        )
        bottlenecks = detector.detect(occupancy_timeline, flow_timeline)
        risk_score = detector.compute_risk_score(bottlenecks)
        
        # ── 3. Generate rerouting suggestions ────────────────────────
        print(f"[{sim_id}] Computing rerouting suggestions...")
        rerouter = ReroutingEngine(config.venue_layout)
        suggestions = rerouter.generate_suggestions(
            bottlenecks, 
            peak_data.get("max_occupancies", {})
        )
        
        # ── 4. AI safety report ──────────────────────────────────────
        print(f"[{sim_id}] Generating AI safety report...")
        ai_report = ai_advisor.generate_safety_report(
            venue_name=config.venue_layout.venue_name,
            crowd_size=config.crowd_size,
            bottlenecks=bottlenecks,
            suggestions=suggestions,
            risk_score=risk_score,
            peak_time_seconds=peak_data.get("peak_step", 0),
            time_step_seconds=config.time_step_seconds
        )
        
        # ── 5. Package results ───────────────────────────────────────
        result = SimulationResult(
            simulation_id=sim_id,
            total_time_seconds=(
                config.event_duration_minutes * 60
            ),
            bottlenecks=bottlenecks,
            reroute_suggestions=suggestions,
            node_occupancy_timeline=occupancy_timeline,
            edge_flow_timeline=flow_timeline,
            ai_safety_report=ai_report,
            risk_score=risk_score,
            peak_congestion_time=peak_data.get("peak_step", 0)
        )
        
        # Cache result
        simulation_cache[sim_id] = result
        print(f"[{sim_id}] Simulation complete. "
              f"Risk score: {risk_score}, "
              f"Bottlenecks: {len(bottlenecks)}, "
              f"Reroutes: {len(suggestions)}")
        
        return result.dict()
        
    except Exception as e:
        print(f"[{sim_id}] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/{simulation_id}")
def get_results(simulation_id: str):
    """Retrieve cached simulation results by ID."""
    if simulation_id not in simulation_cache:
        raise HTTPException(
            status_code=404, 
            detail=f"Simulation {simulation_id} not found"
        )
    return simulation_cache[simulation_id].dict()


@app.get("/health")
def health_check():
    return {"status": "healthy", "model": AIAdvisor.MODEL_ID}
