# 🏟️ Crowd Flow Optimiser
### Built by Team Triverse

---

## 👥 Team Triverse

| Member | Role | HuggingFace Profile |
|--------|------|-------------------|
| Member 1 | Simulation Engine & Backend | [@member1](https://huggingface.co/member1) |
| Member 2 | Frontend & Visualisation | [@member2](https://huggingface.co/member2) |
| Member 3 | AI Integration & Safety Reports | [@member3](https://huggingface.co/member3) |

> **Note:** Replace the names and HuggingFace profile links above
> with each team member's actual details.
> Every member must have their own HuggingFace account.

---

## 📌 Project Overview

Large venues — stadiums, railway stations, festivals — often see
people bunch up at entry gates, food counters, or exits without
warning. When that happens without anyone noticing in time, it can
turn into a real safety risk.

**Crowd Flow Optimiser** solves this by:
- Simulating how crowds move through a venue layout
- Automatically detecting where and when bottlenecks form
- Suggesting real-time rerouting to guide people away from danger
- Generating AI-powered safety advisories for venue staff

---

## 🤗 HuggingFace Hub Integration

| Component | HuggingFace Resource |
|-----------|---------------------|
| AI Safety Reports | [`mistralai/Mistral-7B-Instruct-v0.3`](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3) |
| Inference Method | `huggingface_hub.InferenceClient` |
| Fallback | Rule-based report if API unavailable |

> Every team member has their own individual HuggingFace account
> as required by competition rules.

---

## 🏗️ Architecture

```
[Gradio Frontend :7860]
        ↕  REST API calls
[FastAPI Backend :8000]
        ↕
[CrowdSimulator] → [BottleneckDetector] → [ReroutingEngine]
                                                ↕
                                   [AIAdvisor → HuggingFace Hub]
                                   [Mistral-7B-Instruct-v0.3]
```

---

## 📁 Project Structure

```
crowd_flow_optimiser/
├── backend/
│   ├── main.py           # FastAPI server & venue layouts
│   ├── simulation.py     # Agent-based crowd simulation engine
│   ├── bottleneck.py     # Bottleneck detection & severity scoring
│   ├── rerouting.py      # Alternative path generation
│   ├── ai_advisor.py     # HuggingFace Mistral-7B integration
│   └── models.py         # Pydantic data models
├── frontend/
│   └── app.py            # Gradio UI with Plotly visualisations
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup & Installation

### Step 1 — Clone the repository
```bash
git clone https://github.com/your-org/crowd-flow-optimiser.git
cd crowd-flow-optimiser
```

### Step 2 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Set your HuggingFace token

Get your token from: https://huggingface.co/settings/tokens

```bash
# Linux / macOS
export HF_TOKEN="hf_your_token_here"

# Windows (Command Prompt)
set HF_TOKEN=hf_your_token_here

# Windows (PowerShell)
$env:HF_TOKEN="hf_your_token_here"
```

> Each team member should use their **own** HuggingFace token.

### Step 4 — Start the backend
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Step 5 — Start the frontend (open a new terminal)
```bash
cd frontend
export BACKEND_URL="http://localhost:8000"
python app.py
```

### Step 6 — Open your browser
```
http://localhost:7860
```

---

## 🚀 Quick Start (using shell scripts)

```bash
# Terminal 1 — Backend
chmod +x run_backend.sh
./run_backend.sh

# Terminal 2 — Frontend
chmod +x run_frontend.sh
./run_frontend.sh
```

---

## 🎮 How to Use

```
1. Select Venue Type     →  Stadium or Festival layout
2. Set Crowd Size        →  100 to 5000 people
3. Set Event Duration    →  30 to 300 minutes
4. Pick Arrival Pattern  →  Uniform / Rush / Staggered
5. Click Preview Venue   →  See the venue map before running
6. Click Run Simulation  →  Full simulation starts (~30-60 sec)
7. View Results          →  Map · Timeline · Heatmap · AI Report
```

---

## 🔬 How the Simulation Works

| Step | What Happens |
|------|-------------|
| **1. Graph Model** | Venue nodes (gates, concessions, exits) connected by walkway edges |
| **2. Agent Spawning** | People appear at entry gates following the chosen arrival pattern |
| **3. Pathfinding** | Each agent uses Dijkstra's algorithm with live congestion penalties |
| **4. Congestion** | High occupancy slows movement, creating realistic crowd spillback |
| **5. Bottleneck Detection** | Persistent high occupancy flagged across 4 severity levels |
| **6. Rerouting** | Alternative paths found by temporarily penalising congested nodes |
| **7. AI Report** | Mistral-7B summarises findings into actionable safety advice |

---

## 📊 Severity Levels

| Level | Occupancy Threshold | Colour | Action Required |
|-------|-------------------|--------|----------------|
| 🟢 Low | > 60% capacity | Green | Monitor |
| 🟡 Medium | > 75% capacity | Yellow | Prepare staff |
| 🟠 High | > 88% capacity | Orange | Deploy staff now |
| 🔴 Critical | > 95% capacity | Red | Immediate intervention |

---

## 🗺️ Venue Layouts

### Stadium Layout
```
         [North Gate]
              |
    [Food Court North]
              |
[West Gate]--[North Concourse]--[East Gate]
    |              |                 |
[West        [Central Plaza]    [East
Concourse]        |            Concourse]
    |         [South           |
[Bar West]  Concourse]      [Bar East]
              |
    [Food Court South]
              |
         [South Gate]
```

### Festival Layout
```
         [Main Entrance]
              |
        [Main Stage Area]
         /            \
   [Stage B]        [Stage C]
      |          |      |
  [Bar Left] [Food   [Bar Right]
             Village]
                |
           [Main Exit]
```

---

## 🛠️ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | API info |
| `GET` | `/venue/stadium` | Stadium layout JSON |
| `GET` | `/venue/festival` | Festival layout JSON |
| `POST` | `/simulate` | Run crowd simulation |
| `GET` | `/results/{id}` | Fetch cached results |
| `GET` | `/health` | Health check |

### Example simulation request:
```json
POST /simulate
{
  "crowd_size": 2000,
  "event_duration_minutes": 90,
  "arrival_pattern": "rush",
  "time_step_seconds": 30,
  "venue_layout": { ... }
}
```

---

## 🧪 Test Scenarios

| Scenario | Venue | Crowd | Duration | Pattern | Expected |
|----------|-------|-------|----------|---------|----------|
| Normal event | Stadium | 500 | 120 min | Uniform | Low risk |
| Concert rush | Stadium | 2000 | 90 min | Rush | High risk at North Gate |
| Festival peak | Festival | 3000 | 180 min | Staggered | Medium risk |
| Emergency drill | Festival | 1000 | 60 min | Rush | Critical at Main Stage |

---

## ⚠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| Backend not starting | Check port 8000 is free: `lsof -i :8000` |
| Frontend can't reach backend | Check `BACKEND_URL` env variable is set |
| AI report shows fallback | Check `HF_TOKEN` is valid and not expired |
| Simulation times out | Reduce crowd size or increase time step |
| No bottlenecks detected | Increase crowd size or use Rush arrival pattern |

---

## 📦 Dependencies

```
Backend:   FastAPI · Uvicorn · NetworkX · NumPy · Pydantic
Frontend:  Gradio · Plotly · Pandas
AI:        huggingface-hub · transformers
```

---

## 📄 Licence

MIT Licence — built for the hackathon by **Team Triverse**.

---

## 🏆 Competition Checklist

- [x] Frontend (Gradio) + Backend (FastAPI) — not notebook-only
- [x] HuggingFace Hub model used (`mistralai/Mistral-7B-Instruct-v0.3`)
- [x] Balanced difficulty — custom simulation + AI, not a single API call
- [x] Every team member has an individual HuggingFace account
- [x] Real-time bottleneck detection and rerouting
- [x] Interactive visual frontend with venue map, heatmap, charts

---

*Built with ❤️ by **Team Triverse***
