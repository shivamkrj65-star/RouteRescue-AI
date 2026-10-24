# RouteRescue AI - Hackathon Demonstration & Execution Guide 🚆🚌🚗

**Fetch-A-Thon 3.0: Autonomous Multimodal Travel Disruption Recovery System**

RouteRescue AI is an autonomous, multi-agent travel recovery platform built on **Fetch.ai uAgents**, **ASI:One**, **FastAPI**, **Streamlit**, and **SQLite**. It continuously monitors active passenger bookings, detects cancellations and severe delays, coordinates between independent rail, bus, and road search agents, evaluates multimodal route permutations using time-dependent network algorithms, and provides explainable, budget-compliant recovery recommendations with explicit user-authorized booking handoffs.

---

## 📋 Table of Contents
1. [Prerequisites & Installation](#1-prerequisites--installation)
2. [Environment Variables Configuration](#2-environment-variables-configuration)
3. [Commands to Launch Application Services](#3-commands-to-launch-application-services)
4. [3-Minute Live Demonstration Script](#4-3-minute-live-demonstration-script)
5. [Expected Outputs & Verification](#5-expected-outputs--verification)
6. [Troubleshooting & Diagnostics](#6-troubleshooting--diagnostics)

---

## 1. Prerequisites & Installation

### System Requirements
- Python 3.10 to 3.13
- Operating System: Windows, macOS, or Linux
- Virtual environment tool (`venv`)
- Network: Localhost access for ports `8000` (FastAPI), `8010` (uAgents Bureau), and `8501` (Streamlit)

### Step-by-Step Setup
```bash
# 1. Clone the repository and navigate to the project directory
git clone https://github.com/your-username/RouteRescue-AI.git
cd "Route Rescue AI"

# 2. Create and activate a Python virtual environment
# Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS:
python3 -m venv .venv
source .venv/bin/activate

# 3. Upgrade pip and install all core dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 2. Required & Optional Environment Variables

Create a `.env` file in the project root (or set environment variables in your active shell):

```ini
# Application Environment
APP_ENV=development
LOG_LEVEL=INFO

# Transit Network & Database
DATABASE_PATH=data/routerescue.db

# API & Streamlit Ports
API_HOST=127.0.0.1
API_PORT=8000
STREAMLIT_PORT=8501

# Monitoring Daemon Configuration
MONITOR_POLL_INTERVAL_SECONDS=60.0
MONITOR_DEMO_POLL_INTERVAL_SECONDS=1.0
QUALIFYING_DELAY_THRESHOLD_MINUTES=45

# ----------------------------------------------------------------------
# External AI & Agentverse Integrations (Optional)
# Core multi-agent routing operates with 100% uptime using deterministic fallbacks if omitted
# ----------------------------------------------------------------------

# ASI:One Conversational Engine (https://asi1.ai)
ASI1_API_KEY=your_asi1_api_key_here
ASI1_BASE_URL=https://api.asi1.ai/v1
ASI1_MODEL=asi1-mini

# Fetch.ai Agentverse Mailbox & Registration (https://agentverse.ai)
AGENTVERSE_API_KEY=your_agentverse_api_key_here
AGENTVERSE_MAILBOX=false
AGENTVERSE_URL=https://agentverse.ai
```

> **Note on Zero-Downtime Resilience**: If `ASI1_API_KEY` is not provided, RouteRescue AI automatically activates its deterministic NLP and rule-based parser fallback. All search, routing, and recovery functions remain 100% operational.

---

## 3. Commands to Launch Application Services

Running RouteRescue AI involves three primary services:

### Option A: Standard Multi-Terminal Launch (Recommended for Demo)

#### Terminal 1 — Start the FastAPI Backend
```bash
# Windows:
.\.venv\Scripts\uvicorn.exe backend.main:app --host 127.0.0.1 --port 8000 --reload

# Linux / macOS:
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
*API docs available at: `http://127.0.0.1:8000/docs`*

#### Terminal 2 — Start the uAgents Autonomous Bureau
```bash
# Windows:
.\.venv\Scripts\python.exe -m agents.runner

# Linux / macOS:
python -m agents.runner
```
*Spins up all 5 agents (Rail, Bus, Cab, Recovery Planner, Disruption Monitor) on port 8010.*

#### Terminal 3 — Start the Streamlit Dashboard
```bash
# Windows:
.\.venv\Scripts\streamlit.exe run frontend/app.py --server.port 8501

# Linux / macOS:
streamlit run frontend/app.py --server.port 8501
```
*Dashboard opens in browser at: `http://localhost:8501`*

---

### Option B: Quick Verification via Pytest
To run the automated integration test suite across all agents and backend endpoints:
```bash
pytest -v
```

---

## 4. 3-Minute Live Demonstration Script

Follow this step-by-step walkthrough for an impactful 3-minute hackathon demo presentation.

### ⏱️ Minute 0:00 – 0:45: Introduction & System Dashboard
1. Open the Streamlit dashboard at `http://localhost:8501`.
2. **Key Talking Points**:
   - *"RouteRescue AI is an autonomous multimodal travel recovery system built on the Fetch.ai uAgents framework."*
   - *"Our demonstration network covers 15 transit hubs across the northern corridor (Delhi, Jaipur, Chandigarh, Agra) with 90+ synthetic scheduled services."*
3. Point out the top metrics cards: **Active Journeys**, **Disrupted / At-Risk Count**, and **Active Travel Alerts**.
4. Show the **Monitored Passenger Journeys** table displaying passengers with statuses: `CONFIRMED`, `WAITLISTED`, `RAC`, and `CANCELLED`.

---

### ⏱️ Minute 0:45 – 1:30: Journey Registration & Disruption Simulation
1. Click **📝 Journey Registration** on the sidebar.
2. Fill out a passenger journey:
   - **Passenger Full Name**: `Arjun Singhania`
   - **Origin City**: `Delhi`
   - **Destination City**: `Jaipur`
   - **Maximum Budget Ceiling**: `1500` INR
   - **Arrival Deadline**: `23:00` (11 PM)
   - **Transfer Preferences**: `Max 1 Transfer`
3. Click **Register & Activate Autonomous Monitoring 🚀**.
   - Note the generated Journey ID (e.g., `JRN-ARJUN-...`) and confirmation message.
4. Click **🎛️ Demo Controls** in the sidebar.
5. In **Custom Disruption Injection**:
   - Select `Arjun Singhania`'s journey.
   - Set status to `CANCELLED`.
   - Reason: `"Severe overhead traction breakdown near Rewari Junction"`.
   - Click **Inject Disruption into Provider ⚡**.
   - Show that the booking provider immediately records the cancellation.

---

### ⏱️ Minute 1:30 – 2:15: Multi-Agent Execution & Explainable Recovery
1. Click **🤖 Agent Activity** in the sidebar.
2. **Key Talking Points**:
   - *"Notice this is not hardcoded mockup data. This is a real-time audit log from SQLite capturing genuine uAgents messaging."*
   - Highlight:
     - `PassengerGateway ➔ Registered new journey`
     - `DisruptionSimulator ➔ Simulated CANCELLED on journey`
     - `RecoveryPlannerAgent ➔ Dispatched multimodal search queries to Rail, Bus, and Cab agents`
     - `ModalSearchAgents ➔ Collected verified travel alternatives`
     - `RecoveryPlannerAgent ➔ Evaluated options and generated composite score rankings`
   - Expand the JSON message details to show the request IDs, timestamps, and payload structure.
3. Click **🧭 Recovery Results** in the sidebar.
4. Click **🚀 Calculate Multimodal Recovery Alternatives**.
5. **Key Talking Points**:
   - Point out **Total Evaluated** vs **Valid Feasible Options** vs **Constraint Violations**.
   - Review **Recommended Option #1**: Show the provider (e.g. *NueGo Electric* or *Zingbus*), departure time, arrival time, total fare (strictly under the ₹1,500 budget), and transfer details.
   - Read the **Grounded Planner Explanation**: Highlight that the explanation specifically articulates why this option won based on speed, affordability, seat availability, and transfer simplicity.

---

### ⏱️ Minute 2:15 – 3:00: Booking Handoff, Safety Guardrail & ASI:One
1. On the recommended option, click **Select for Booking Handoff 🎟️**.
2. The UI smoothly transitions to **🎟️ Booking Handoff**.
3. **Key Talking Points**:
   - *"An autonomous travel agent must respect user safety and financial boundaries."*
   - Show the official provider redirect URL (IRCTC, Zingbus, NueGo).
   - Point out that the **Confirm & Record Recovery Booking** button is **disabled** until the user checks the explicit authorization checkbox.
4. Check the box: `[x] I explicitly authorize RouteRescue AI to confirm this recovery option on my behalf.`
5. Click **Confirm & Record Recovery Booking ✅**.
   - Balloons trigger, booking is approved, status updates to `CONFIRMED`, and a timestamped audit record is written.
6. Optional extra: Switch to **🧭 Recovery Results ➔ ASI:One Conversational Assistant** and show natural-language travel querying.

---

## 5. Expected Outputs & Verification

| Action | API Endpoint Called | Expected Result / Status Transition |
| :--- | :--- | :--- |
| **Health Check** | `GET /health` | Status `online`, version `0.1.0`, `is_demo_mode: True` |
| **List Journeys** | `GET /api/v1/journeys` | Returns 5+ baseline seeded passenger journeys |
| **Register Journey** | `POST /api/v1/journeys` | Returns `UserJourney` with `JRN-` ID, `PNR-` reference, status `CONFIRMED` |
| **Inject Disruption** | `POST /api/v1/disruptions/inject` | Status updates to `CANCELLED` / `DELAYED`; SQLite log recorded |
| **Autonomous Recovery** | `POST /api/v1/recovery/plan` | Returns `top_3_options`, `valid_options_count`, `best_option_explanation` |
| **Agent Activity Logs** | `GET /api/v1/agents/activity` | Returns list of structured events with `agent_name`, `action`, `details` |
| **Booking Approval** | `POST /api/v1/bookings/approve` | Rejects with 400 if `user_approved: False`; returns `APPROVED_BY_USER` if True |
| **Demo Reset** | `POST /api/v1/demo/reset` | Overrides cleared, seeded journeys restored, `DEMO_RESET` logged |

---

## 6. Troubleshooting & Diagnostics

### Issue: Port 8000 or 8010 Already in Use
**Symptom**: `OSError: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)`
**Resolution**:
```bash
# Check what process is listening on the port (Windows):
netstat -ano | findstr :8000
# Terminate the process by PID:
taskkill /F /PID <PID>
```

### Issue: Deprecation Warning on Python 3.13 (`There is no current event loop`)
**Symptom**: `DeprecationWarning: There is no current event loop` from `uagents/agent.py`
**Resolution**: This is a non-fatal warning originating within `uagents` compatibility with Python 3.13's asyncio policy. All agent threads and async message exchanges execute normally.

### Issue: Streamlit Shows "Backend Offline"
**Symptom**: Red banner in Streamlit sidebar: `Backend Offline`.
**Resolution**:
1. Verify the FastAPI backend is running on `127.0.0.1:8000` via `curl http://127.0.0.1:8000/health`.
2. Ensure no firewall or proxy is blocking local loopback calls.

### Issue: Resetting the Demonstration Environment
If test journeys accumulate or you want to restart the demo from a clean baseline:
1. In the Streamlit sidebar, click **🔄 Reset Demo to Baseline**.
2. Or send a POST request:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/demo/reset
   ```
All in-memory overrides are wiped and SQLite is re-seeded to its pristine state.
