import gradio as gr
import requests
import json
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
import os

# ── Configuration ─────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Colour scheme ─────────────────────────────────────────────────────────────
SEVERITY_COLOURS = {
    "critical": "#FF0000",
    "high":     "#FF6600",
    "medium":   "#FFB300",
    "low":      "#4CAF50",
    "normal":   "#2196F3"
}

NODE_TYPE_COLOURS = {
    "entry":          "#4CAF50",
    "exit":           "#2196F3",
    "emergency_exit": "#FF5722",
    "concession":     "#FF9800",
    "walkway":        "#9E9E9E",
    "junction":       "#9C27B0"
}

NODE_TYPE_SYMBOLS = {
    "entry":          "triangle-up",
    "exit":           "triangle-down",
    "emergency_exit": "star",
    "concession":     "square",
    "walkway":        "circle",
    "junction":       "diamond"
}


# ── Helper Functions ──────────────────────────────────────────────────────────

def fetch_venue_layout(venue_type: str) -> Dict:
    """Fetch venue layout from backend."""
    try:
        endpoint = (
            f"{BACKEND_URL}/venue/stadium" 
            if venue_type == "Stadium" 
            else f"{BACKEND_URL}/venue/festival"
        )
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def run_simulation_request(
    venue_type: str,
    crowd_size: int,
    event_duration: int,
    arrival_pattern: str,
    time_step: int
) -> Dict:
    """Send simulation request to backend."""
    layout = fetch_venue_layout(venue_type)
    if "error" in layout:
        return {"error": layout["error"]}
    
    payload = {
        "crowd_size": crowd_size,
        "event_duration_minutes": event_duration,
        "arrival_pattern": arrival_pattern.lower(),
        "venue_layout": layout,
        "time_step_seconds": time_step
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/simulate",
            json=payload,
            timeout=120  # Simulation can take time
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": "Simulation timed out. Try reducing crowd size or duration."}
    except Exception as e:
        return {"error": str(e)}


def build_venue_map(
    layout: Dict,
    bottlenecks: List[Dict] = None,
    suggestions: List[Dict] = None,
    occupancy_snapshot: Dict[str, int] = None
) -> go.Figure:
    """
    Build an interactive Plotly venue map showing:
    - Nodes coloured by type and congestion level
    - Edges as walkways
    - Bottleneck highlights
    - Rerouting arrows
    """
    nodes = layout.get("nodes", [])
    edges = layout.get("edges", [])
    
    # Index nodes
    node_map = {n["id"]: n for n in nodes}
    
    # Bottleneck lookup
    bn_map = {}
    if bottlenecks:
        for bn in bottlenecks:
            bn_map[bn["node_id"]] = bn
    
    # Alternative path edges from suggestions
    alt_edges = set()
    original_edges = set()
    if suggestions:
        for s in suggestions:
            path = s.get("alternative_path", [])
            for i in range(len(path) - 1):
                alt_edges.add((path[i], path[i+1]))
            orig = s.get("original_path", [])
            for i in range(len(orig) - 1):
                original_edges.add((orig[i], orig[i+1]))
    
    fig = go.Figure()
    
    # ── Draw edges ────────────────────────────────────────────────────
    for edge in edges:
        fn = node_map.get(edge["from_node"])
        tn = node_map.get(edge["to_node"])
        if not fn or not tn:
            continue
        
        is_alt = (edge["from_node"], edge["to_node"]) in alt_edges
        is_orig_congested = (
            (edge["from_node"], edge["to_node"]) in original_edges and
            (edge["from_node"] in bn_map or edge["to_node"] in bn_map)
        )
        
        if is_alt:
            color, width, dash = "#00C853", 4, "solid"
        elif is_orig_congested:
            color, width, dash = "#FF1744", 3, "dash"
        else:
            color, width, dash = "#B0BEC5", 2, "solid"
        
        fig.add_trace(go.Scatter(
            x=[fn["x"], tn["x"], None],
            y=[fn["y"], tn["y"], None],
            mode="lines",
            line=dict(color=color, width=width, dash=dash),
            hoverinfo="skip",
            showlegend=False,
            name=""
        ))
        
        # Arrow for direction on alt routes
        if is_alt:
            mid_x = (fn["x"] + tn["x"]) / 2
            mid_y = (fn["y"] + tn["y"]) / 2
            dx = tn["x"] - fn["x"]
            dy = tn["y"] - fn["y"]
            fig.add_annotation(
                x=mid_x + dx * 0.1,
                y=mid_y + dy * 0.1,
                ax=mid_x - dx * 0.1,
                ay=mid_y - dy * 0.1,
                xref="x", yref="y",
                axref="x", ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.5,
                arrowcolor="#00C853",
                arrowwidth=2
            )
    
    # ── Draw nodes ────────────────────────────────────────────────────
    # Group by type for legend
    type_groups: Dict[str, List] = {}
    
    for node in nodes:
        ntype = node["node_type"]
        bn = bn_map.get(node["id"])
        occ = (occupancy_snapshot or {}).get(node["id"], 0)
        capacity = node["capacity"]
        occ_pct = (occ / max(capacity, 1)) * 100
        
        # Determine colour based on congestion
        if bn:
            colour = SEVERITY_COLOURS[bn["severity"]]
            size = 20 if bn["severity"] == "critical" else 16
        else:
            colour = NODE_TYPE_COLOURS.get(ntype, "#9E9E9E")
            size = 12
        
        hover_text = (
            f"<b>{node['name']}</b><br>"
            f"Type: {ntype.replace('_', ' ').title()}<br>"
            f"Capacity: {capacity}<br>"
            f"Occupancy: {occ} ({occ_pct:.1f}%)"
        )
        if bn:
            hover_text += (
                f"<br><b>⚠️ {bn['severity'].upper()} BOTTLENECK</b>"
                f"<br>Wait: ~{bn['estimated_wait_minutes']} min"
            )
        
        if ntype not in type_groups:
            type_groups[ntype] = {
                "x": [], "y": [], "text": [], "hovertext": [],
                "colours": [], "sizes": [],
                "symbol": NODE_TYPE_SYMBOLS.get(ntype, "circle")
            }
        
        type_groups[ntype]["x"].append(node["x"])
        type_groups[ntype]["y"].append(node["y"])
        type_groups[ntype]["text"].append(node["name"])
        type_groups[ntype]["hovertext"].append(hover_text)
        type_groups[ntype]["colours"].append(colour)
        type_groups[ntype]["sizes"].append(size)
    
    for ntype, data in type_groups.items():
        fig.add_trace(go.Scatter(
            x=data["x"],
            y=data["y"],
            mode="markers+text",
            marker=dict(
                size=data["sizes"],
                color=data["colours"],
                symbol=data["symbol"],
                line=dict(color="white", width=1.5)
            ),
            text=[n.split()[-1] for n in data["text"]],
            textposition="top center",
            textfont=dict(size=9, color="#37474F"),
            hovertext=data["hovertext"],
            hoverinfo="text",
            name=ntype.replace("_", " ").title(),
            legendgroup=ntype
        ))
    
    # ── Legend annotations ────────────────────────────────────────────
    if bottlenecks:
        for severity in ["critical", "high", "medium", "low"]:
            count = sum(1 for b in bottlenecks if b["severity"] == severity)
            if count > 0:
                fig.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode="markers",
                    marker=dict(
                        size=12, 
                        color=SEVERITY_COLOURS[severity],
                        symbol="circle"
                    ),
                    name=f"⚠ {severity.title()} ({count})",
                    showlegend=True
                ))
    
    fig.update_layout(
        title=dict(
            text=f"🏟️ {layout.get('venue_name', 'Venue')} — Crowd Flow Map",
            font=dict(size=18, color="#1A237E"),
            x=0.5
        ),
        xaxis=dict(
            range=[-5, 105], 
            showgrid=True, 
            gridcolor="#ECEFF1",
            zeroline=False,
            tickvals=[]
        ),
        yaxis=dict(
            range=[-5, 105], 
            showgrid=True, 
            gridcolor="#ECEFF1",
            zeroline=False,
            scaleanchor="x",
            scaleratio=1,
            tickvals=[]
        ),
        plot_bgcolor="#F8F9FA",
        paper_bgcolor="white",
        height=600,
        legend=dict(
            orientation="v",
            x=1.02, y=1,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="#CFD8DC",
            borderwidth=1,
            font=dict(size=11)
        ),
        margin=dict(l=20, r=180, t=60, b=20),
        hovermode="closest"
    )
    
    return fig


def build_occupancy_chart(
    occupancy_timeline: Dict[str, List[int]],
    node_map: Dict[str, Dict],
    time_step_seconds: int,
    bottleneck_node_ids: List[str]
) -> go.Figure:
    """Line chart of occupancy over time for bottleneck nodes."""
    
    fig = go.Figure()
    
    # Only show bottleneck nodes + top 5 by max occupancy
    nodes_to_show = set(bottleneck_node_ids)
    
    # Add top occupied nodes
    max_occs = {
        nid: max(series) if series else 0 
        for nid, series in occupancy_timeline.items()
    }
    top_nodes = sorted(max_occs, key=max_occs.get, reverse=True)[:5]
    nodes_to_show.update(top_nodes)
    
    for node_id in nodes_to_show:
        series = occupancy_timeline.get(node_id, [])
        if not series:
            continue
        
        node_info = node_map.get(node_id, {})
        name = node_info.get("name", node_id)
        capacity = node_info.get("capacity", 1)
        
        times = [
            i * time_step_seconds / 60 
            for i in range(len(series))
        ]
        
        is_bn = node_id in bottleneck_node_ids
        
        fig.add_trace(go.Scatter(
            x=times,
            y=series,
            mode="lines",
            name=name,
            line=dict(
                width=3 if is_bn else 1.5,
                dash="solid" if is_bn else "dot"
            ),
            hovertemplate=(
                f"<b>{name}</b><br>"
                "Time: %{x:.1f} min<br>"
                "Occupancy: %{y}<br>"
                f"Capacity: {capacity}<extra></extra>"
            )
        ))
        
        # Capacity line
        if is_bn:
            fig.add_hline(
                y=capacity,
                line_dash="dash",
                line_color="red",
                opacity=0.4,
                annotation_text=f"{name} capacity",
                annotation_position="right"
            )
    
    fig.update_layout(
        title="📈 Occupancy Over Time",
        xaxis_title="Time (minutes)",
        yaxis_title="People Count",
        height=380,
        plot_bgcolor="#F8F9FA",
        paper_bgcolor="white",
        legend=dict(
            orientation="h",
            y=-0.2
        ),
        hovermode="x unified"
    )
    
    return fig


def build_heatmap(
    occupancy_timeline: Dict[str, List[int]],
    node_map: Dict[str, Dict],
    time_step_seconds: int
) -> go.Figure:
    """Heatmap of occupancy % across all nodes over time."""
    
    nodes = list(occupancy_timeline.keys())
    node_names = [node_map.get(n, {}).get("name", n) for n in nodes]
    capacities = [
        max(node_map.get(n, {}).get("capacity", 1), 1) for n in nodes
    ]
    
    # Compute occupancy %
    max_steps = max((len(s) for s in occupancy_timeline.values()), default=1)
    matrix = []
    
    for i, node_id in enumerate(nodes):
        series = occupancy_timeline[node_id]
        pct_series = [
            min(100, (occ / capacities[i]) * 100) 
            for occ in series
        ]
        # Pad if needed
        pct_series += [0] * (max_steps - len(pct_series))
        matrix.append(pct_series)
    
    # Downsample time axis if too many steps
    step = max(1, max_steps // 50)
    time_labels = [
        f"{i * time_step_seconds * step / 60:.0f}m" 
        for i in range(max_steps // step)
    ]
    matrix_ds = [row[::step] for row in matrix]
    
    fig = go.Figure(data=go.Heatmap(
        z=matrix_ds,
        x=time_labels,
        y=node_names,
        colorscale=[
            [0.0, "#E8F5E9"],
            [0.4, "#FFF176"],
            [0.6, "#FFB300"],
            [0.8, "#FF5722"],
            [1.0, "#B71C1C"]
        ],
        zmin=0,
        zmax=100,
        colorbar=dict(
            title="Occupancy %",
            tickvals=[0, 25, 50, 75, 100],
            ticktext=["0%", "25%", "50%", "75%", "100%+"]
        ),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Time: %{x}<br>"
            "Occupancy: %{z:.1f}%<extra></extra>"
        )
    ))
    
    fig.update_layout(
        title="🌡️ Congestion Heatmap (All Zones Over Time)",
        xaxis_title="Time",
        yaxis_title="Zone",
        height=400,
        plot_bgcolor="#F8F9FA",
        paper_bgcolor="white",
        xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
        yaxis=dict(tickfont=dict(size=10))
    )
    
    return fig


def build_risk_gauge(risk_score: float) -> go.Figure:
    """Semi-circular gauge for overall risk score."""
    
    if risk_score < 30:
        colour = "#4CAF50"
        label = "LOW RISK"
    elif risk_score < 60:
        colour = "#FF9800"
        label = "MODERATE RISK"
    elif risk_score < 80:
        colour = "#FF5722"
        label = "HIGH RISK"
    else:
        colour = "#B71C1C"
        label = "CRITICAL RISK"
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=risk_score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"Overall Risk Score<br><span style='font-size:0.9em;color:{colour}'>{label}</span>"},
        delta={"reference": 50},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1},
            "bar": {"color": colour},
            "steps": [
                {"range": [0, 30],  "color": "#E8F5E9"},
                {"range": [30, 60], "color": "#FFF8E1"},
                {"range": [60, 80], "color": "#FBE9E7"},
                {"range": [80, 100],"color": "#FFEBEE"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 80
            }
        }
    ))
    
    fig.update_layout(
        height=280,
        paper_bgcolor="white",
        font=dict(size=14)
    )
    return fig


def format_bottleneck_table(bottlenecks: List[Dict]) -> pd.DataFrame:
    """Format bottlenecks as a displayable DataFrame."""
    if not bottlenecks:
        return pd.DataFrame({"Message": ["No bottlenecks detected ✅"]})
    
    rows = []
    severity_emoji = {
        "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"
    }
    
    for bn in bottlenecks:
        rows.append({
            "Severity": f"{severity_emoji.get(bn['severity'], '⚪')} {bn['severity'].upper()}",
            "Zone": bn["node_name"],
            "Occupancy": f"{bn['occupancy_percent']:.1f}%",
            "Est. Wait": f"{bn['estimated_wait_minutes']} min",
            "Alert Time": f"{bn['timestamp_seconds'] // 60} min {bn['timestamp_seconds'] % 60}s"
        })
    
    return pd.DataFrame(rows)


def format_reroute_table(suggestions: List[Dict], node_map: Dict) -> pd.DataFrame:
    """Format rerouting suggestions as a DataFrame."""
    if not suggestions:
        return pd.DataFrame({"Message": ["No rerouting needed ✅"]})
    
    rows = []
    for s in suggestions:
        from_name = node_map.get(s["from_node"], {}).get("name", s["from_node"])
        to_name = node_map.get(s["to_node"], {}).get("name", s["to_node"])
        alt_path = " → ".join(
            node_map.get(n, {}).get("name", n) 
            for n in s["alternative_path"]
        )
        
        rows.append({
            "From": from_name,
            "To": to_name,
            "Alternative Route": alt_path[:80] + ("..." if len(alt_path) > 80 else ""),
            "Time Saving": f"{s['time_saving_minutes']:.1f} min",
            "Reason": s["reason"][:100] + ("..." if len(s["reason"]) > 100 else "")
        })
    
    return pd.DataFrame(rows)


# ── Main Gradio App ───────────────────────────────────────────────────────────

def run_full_simulation(
    venue_type: str,
    crowd_size: int,
    event_duration: int,
    arrival_pattern: str,
    time_step: int,
    progress=gr.Progress()
) -> Tuple:
    """
    Master function called when user clicks 'Run Simulation'.
    Returns all outputs for Gradio components.
    """
    progress(0, desc="Fetching venue layout...")
    
    layout_data = fetch_venue_layout(venue_type)
    if "error" in layout_data:
        error_msg = f"❌ Error fetching layout: {layout_data['error']}"
        empty_fig = go.Figure()
        empty_df = pd.DataFrame({"Error": [error_msg]})
        return (empty_fig, empty_fig, empty_fig, empty_fig, 
                empty_df, empty_df, error_msg, "")
    
    # Build initial map (no simulation data yet)
    node_map = {n["id"]: n for n in layout_data.get("nodes", [])}
    
    progress(0.1, desc="Running crowd simulation (this may take 30-60 seconds)...")
    
    result = run_simulation_request(
        venue_type=venue_type,
        crowd_size=int(crowd_size),
        event_duration=int(event_duration),
        arrival_pattern=arrival_pattern,
        time_step=int(time_step)
    )
    
    if "error" in result:
        error_msg = f"❌ Simulation error: {result['error']}"
        empty_fig = go.Figure()
        empty_df = pd.DataFrame({"Error": [error_msg]})
        return (empty_fig, empty_fig, empty_fig, empty_fig,
                empty_df, empty_df, error_msg, "")
    
    progress(0.7, desc="Building visualisations...")
    
    # Extract data
    bottlenecks = result.get("bottlenecks", [])
    suggestions = result.get("reroute_suggestions", [])
    risk_score = result.get("risk_score", 0)
    occupancy_timeline = result.get("node_occupancy_timeline", {})
    ai_report = result.get("ai_safety_report", "No report generated.")
    sim_id = result.get("simulation_id", "N/A")
    peak_step = result.get("peak_congestion_time", 0)
    peak_minute = (peak_step * time_step) // 60
    
    # Peak occupancy snapshot
    peak_snapshot = {}
    for node_id, series in occupancy_timeline.items():
        if series and peak_step < len(series):
            peak_snapshot[node_id] = series[peak_step]
    
    # Build figures
    venue_map = build_venue_map(
        layout_data, bottlenecks, suggestions, peak_snapshot
    )
    
    bn_node_ids = [b["node_id"] for b in bottlenecks]
    occupancy_chart = build_occupancy_chart(
        occupancy_timeline, node_map, time_step, bn_node_ids
    )
    
    heatmap = build_heatmap(occupancy_timeline, node_map, time_step)
    risk_gauge = build_risk_gauge(risk_score)
    
    # Tables
    bn_df = format_bottleneck_table(bottlenecks)
    reroute_df = format_reroute_table(suggestions, node_map)
    
    # Summary text
    summary = (
        f"✅ **Simulation Complete** | ID: `{sim_id}`\n\n"
        f"- **Risk Score:** {risk_score}/100\n"
        f"- **Bottlenecks Found:** {len(bottlenecks)}\n"
        f"- **Rerouting Suggestions:** {len(suggestions)}\n"
        f"- **Peak Congestion At:** {peak_minute} minutes into event\n"
        f"- **Crowd Size:** {crowd_size:,} people | "
        f"**Duration:** {event_duration} min | "
        f"**Pattern:** {arrival_pattern}"
    )
    
    progress(1.0, desc="Done!")
    
    return (
        venue_map,
        occupancy_chart,
        heatmap,
        risk_gauge,
        bn_df,
        reroute_df,
        ai_report,
        summary
    )


def preview_venue(venue_type: str) -> go.Figure:
    """Show venue layout before simulation."""
    layout_data = fetch_venue_layout(venue_type)
    if "error" in layout_data:
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error loading venue: {layout_data['error']}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16, color="red")
        )
        return fig
    return build_venue_map(layout_data)


# ── Gradio Interface ──────────────────────────────────────────────────────────

with gr.Blocks(
    title="🏟️ Crowd Flow Optimiser",
    theme=gr.themes.Soft(
        primary_hue="blue",
        secondary_hue="orange"
    ),
    css="""
        .risk-critical { background: #ffebee; border-left: 4px solid #f44336; }
        .risk-high     { background: #fff3e0; border-left: 4px solid #ff9800; }
        .header-box { 
            background: linear-gradient(135deg, #1a237e, #283593);
            color: white; padding: 20px; border-radius: 10px;
            margin-bottom: 15px;
        }
        .metric-box {
            background: #f5f5f5; border-radius: 8px;
            padding: 15px; text-align: center;
        }
    """
) as demo:
    
    # ── Header ─────────────────────────────────────────────────────────
    gr.HTML("""
        <div style="background: linear-gradient(135deg, #1a237e, #1565C0);
                    color: white; padding: 25px; border-radius: 12px;
                    margin-bottom: 20px; text-align: center;">
            <h1 style="margin:0; font-size: 2.2em;">
                🏟️ Crowd Flow Optimiser
            </h1>
            <p style="margin: 8px 0 0 0; font-size: 1.1em; opacity: 0.9;">
                Simulate crowd movement · Detect bottlenecks · Generate safe rerouting
            </p>
            <p style="margin: 5px 0 0 0; font-size: 0.85em; opacity: 0.7;">
                Powered by Agent-Based Simulation + Mistral-7B on HuggingFace Hub
            </p>
        </div>
    """)
    
    # ── Controls ───────────────────────────────────────────────────────
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### ⚙️ Simulation Settings")
            
            venue_selector = gr.Dropdown(
                choices=["Stadium", "Festival"],
                value="Stadium",
                label="🏟️ Venue Type",
                info="Choose pre-built venue layout"
            )
            
            crowd_size_slider = gr.Slider(
                minimum=100,
                maximum=5000,
                value=1500,
                step=100,
                label="👥 Total Crowd Size",
                info="Number of people attending"
            )
            
            duration_slider = gr.Slider(
                minimum=30,
                maximum=300,
                value=90,
                step=15,
                label="⏱️ Event Duration (minutes)"
            )
            
            arrival_pattern = gr.Radio(
                choices=["Uniform", "Rush", "Staggered"],
                value="Uniform",
                label="📊 Arrival Pattern",
                info=(
                    "Uniform: spread evenly | "
                    "Rush: most arrive early | "
                    "Staggered: waves"
                )
            )
            
            time_step = gr.Slider(
                minimum=10,
                maximum=60,
                value=30,
                step=10,
                label="⏲️ Simulation Time Step (seconds)",
                info="Smaller = more accurate but slower"
            )
            
            with gr.Row():
                preview_btn = gr.Button("👁️ Preview Venue", variant="secondary")
                run_btn = gr.Button(
                    "▶️ Run Simulation", 
                    variant="primary",
                    size="lg"
                )
            
            gr.Markdown("""
            ---
            **How it works:**
            1. Choose your venue and crowd settings
            2. Click **Preview Venue** to see the layout
            3. Click **Run Simulation** to start
            4. View bottlenecks, heatmaps and AI safety report
            
            **Legend:**
            - 🟢 Entry Gates
            - 🔵 Exits  
            - ⭐ Emergency Exits
            - 🟠 Concessions
            - 🟣 Junctions
            - 🔴 Critical bottleneck
            - 🟠 High bottleneck
            - 🟡 Medium bottleneck
            - 🟢 Low / Safe zone
            - **Green lines** = suggested alternate routes
            - **Red dashed** = congested original routes
            """)
        
        # ── Main Visualisation Area ─────────────────────────────────
        with gr.Column(scale=3):
            summary_text = gr.Markdown(
                "Configure settings and click **Run Simulation** to begin."
            )
            
            with gr.Tabs():
                with gr.TabItem("🗺️ Venue Map"):
                    venue_map_plot = gr.Plot(label="Venue Map")
                
                with gr.TabItem("📈 Occupancy Over Time"):
                    occupancy_plot = gr.Plot(label="Occupancy Timeline")
                
                with gr.TabItem("🌡️ Congestion Heatmap"):
                    heatmap_plot = gr.Plot(label="Heatmap")
                
                with gr.TabItem("🎯 Risk Gauge"):
                    risk_gauge_plot = gr.Plot(label="Risk Score")
    
    # ── Tables ─────────────────────────────────────────────────────────
    gr.Markdown("---")
    with gr.Row():
        with gr.Column():
            gr.Markdown("### ⚠️ Bottleneck Alerts")
            bottleneck_table = gr.Dataframe(
                label="Detected Bottlenecks",
                wrap=True,
                interactive=False
            )
        
        with gr.Column():
            gr.Markdown("### 🔀 Rerouting Suggestions")
            reroute_table = gr.Dataframe(
                label="Alternative Routes",
                wrap=True,
                interactive=False
            )
    
    # ── AI Safety Report ───────────────────────────────────────────────
    gr.Markdown("---")
    gr.Markdown("### 🤖 AI Safety Advisory Report")
    gr.Markdown(
        "*Generated by Mistral-7B-Instruct via HuggingFace Hub — "
        "provides actionable recommendations based on simulation results*"
    )
    ai_report_output = gr.Markdown(
        value="*AI report will appear here after simulation runs...*"
    )
    
    # ── Examples ───────────────────────────────────────────────────────
    gr.Markdown("---")
    gr.Markdown("### 🎪 Quick Examples")
    gr.Examples(
        examples=[
            ["Stadium", 2000, 90,  "Rush",      30],
            ["Stadium", 500,  120, "Uniform",   30],
            ["Festival", 3000, 180, "Staggered", 30],
            ["Festival", 1000, 60,  "Rush",      20],
        ],
        inputs=[
            venue_selector, crowd_size_slider, 
            duration_slider, arrival_pattern, time_step
        ],
        label="Try these scenarios"
    )
    
    # ── Event Handlers ─────────────────────────────────────────────────
    
    preview_btn.click(
        fn=preview_venue,
        inputs=[venue_selector],
        outputs=[venue_map_plot]
    )
    
    run_btn.click(
        fn=run_full_simulation,
        inputs=[
            venue_selector,
            crowd_size_slider,
            duration_slider,
            arrival_pattern,
            time_step
        ],
        outputs=[
            venue_map_plot,
            occupancy_plot,
            heatmap_plot,
            risk_gauge_plot,
            bottleneck_table,
            reroute_table,
            ai_report_output,
            summary_text
        ]
    )
    
    # Auto-preview on venue change
    venue_selector.change(
        fn=preview_venue,
        inputs=[venue_selector],
        outputs=[venue_map_plot]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
