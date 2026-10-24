# RouteRescue AI 🚆🚌🚗✈️

**Autonomous Multimodal Travel Disruption Recovery System for Fetch-A-Thon 3.0**

RouteRescue AI is an autonomous multimodal travel recovery platform designed to monitor travel disruptions across train, bus, and road networks, evaluate alternative routes, and synthesize optimal alternative journeys based on passenger constraints.

This repository implements **Phase 1: Project Foundation**, **Phase 2: Independent Transport Agents**, and **Phase 3: Recovery Planner Agent**.

---

## 🧭 Phase 3: Recovery Planner Multi-Agent Coordination

RouteRescue AI coordinates autonomous recovery using a dedicated **Recovery Planner Agent** that interacts directly with the modal search agents:

1. **Recovery Planner Agent** (`recovery_planner_agent`):
   - Cryptographic Address: `agent1q00zd0l68j6n3f450fhdtacxakj9ne7qlajl5nq6ldrsmadqx2r6x9gnfj9`
   - Protocol: `RecoveryPlannerProtocol` (v1.0.0)
   - Function: Receives `RecoveryRequest` messages, dispatches parallel `TransportSearchQuery` messages to Rail, Bus, and Cab agents, correlates responses asynchronously, handles offline timeouts, enforces hard user constraints, scores alternatives via deterministic multi-criteria utility functions, and replies with the top 3 ranked options and natural-language selection rationale.

2. **Deterministic Recovery Engine** (`services/recovery_engine.py`):
   - **Hard Constraint Enforcement:** Rejects alternatives departing before `earliest_departure`, arriving after `latest_acceptable_arrival`, exceeding `max_budget`, having sold-out seats, or exceeding `max_transfers`.
   - **Multi-Criteria Scoring Function:**
     $$S = w_{\text{time}} \cdot S_{\text{time}} + w_{\text{cost}} \cdot S_{\text{cost}} + w_{\text{reliability}} \cdot S_{\text{reliability}} + w_{\text{transfers}} \cdot S_{\text{transfers}}$$
     - $S_{\text{time}}$: Normalized travel duration efficiency (faster transit gets higher score).
     - $S_{\text{cost}}$: Cost economy normalized against budget ceiling (lower fare scores higher).
     - $S_{\text{reliability}}$: Confidence weighting based on seat availability (`AVAILABLE`: 100, `FEW_SEATS`: 85, `ON_DEMAND`: 90, `RAC`: 50, `WAITLISTED`: 25).
     - $S_{\text{transfers}}$: Direct route bonus (0 transfers: 100, 1 transfer: 70).
   - **Explainable Recommendation Rationale:** Generates human-readable explanations detailing why Option #1 scored highest, its key operational strengths, and trade-off contrasts with Option #2 and Option #3.

```
+----------------------------------------------------------------------------------------------------+
|                                      Fetch.ai Multi-Agent Bureau                                   |
|                                                                                                    |
|    +-----------------------+                         +-----------------------------+               |
|    |                       |    RecoveryRequest      |                             |               |
|    |                       | ----------------------> |                             |               |
|    |                       | <---------------------- |                             |               |
|    |                       |    RecoveryResponse     |                             |               |
|    |  Passenger / Client   |                         |   Recovery Planner Agent    |               |
|    |         Agent         |                         |  (RecoveryPlannerProtocol)  |               |
|    |                       |                         |                             |               |
|    +-----------------------+                         +-----------------------------+               |
|                                                                 |   ^   |                          |
|                                            TransportSearchQuery |   |   | TransportSearchResult    |
|                                                                 v   |   v                          |
|                                          +---------------------------------------------+           |
|                                          |                                             |           |
|                               +--------------------+ +-------------------+ +---------------------+ |
|                               | Rail Search Agent  | | Bus Search Agent  | | Cab & Road Agent    | |
|                               | (RailSearchProto)  | | (BusSearchProto)  | | (CabRoadProto)      | |
|                               +--------------------+ +-------------------+ +---------------------+ |
|                                          |                     |                     |             |
|                                          +---------------------+---------------------+             |
|                                                                |                                   |
|                                                                v                                   |
|                                                  SQLite Transport Network DB                       |
+----------------------------------------------------------------------------------------------------+
```

---

## 🤖 Phase 2: Autonomous Transport Agents Architecture

RouteRescue AI deploys three autonomous search agents built with the **Fetch.ai uAgents** framework:

1. **Rail Search Agent** (`rail_search_agent`):
   - Cryptographic Address: `agent1q2r3529s3309a9w0cwhd8zfqv5952l4g2u8j6t6075908d0yq8c9x5p6v69`
   - Protocol: `RailSearchProtocol` (v1.0.0)
   - Function: Autonomously receives `TransportSearchQuery` messages, executes train searches against synthetic datasets, and replies with structured `TransportSearchResult` messages containing ranked train alternatives.
2. **Bus Search Agent** (`bus_search_agent`):
   - Cryptographic Address: `agent1qv3l4q397s4e48k29p6qg9y867zfcgpx8z2d2df26c5j6vd2whn9xwq5mcu`
   - Protocol: `BusSearchProtocol` (v1.0.0)
   - Function: Evaluates intercity bus routes across operators (electric AC, sleeper, Volvo, state roadways), evaluating availability and luggage allowances.
3. **Cab & Road Search Agent** (`cab_road_search_agent`):
   - Cryptographic Address: `agent1qw82a2cfhsk88339p857gsw4h65z2cr2f6f58p83g6dqwqj3whu5xej5msr`
   - Protocol: `CabRoadSearchProtocol` (v1.0.0)
   - Function: Evaluates point-to-point road travel, expressway transfers, and on-demand cab connections.

```
+-----------------------------------------------------------------------------------------+
|                                    Fetch.ai Bureau                                      |
|                                                                                         |
|   +-----------------------+   TransportSearchQuery    +-----------------------------+   |
|   |                       | ------------------------> |      Rail Search Agent      |   |
|   |                       | <------------------------ |     (RailSearchProtocol)    |   |
|   |                       |   TransportSearchResult   +-----------------------------+   |
|   |                       |                                                             |
|   |  Coordinator / Client |   TransportSearchQuery    +-----------------------------+   |
|   |         Agent         | ------------------------> |       Bus Search Agent      |   |
|   |                       | <------------------------ |     (BusSearchProtocol)     |   |
|   |                       |   TransportSearchResult   +-----------------------------+   |
|   |                       |                                                             |
|   |                       |   TransportSearchQuery    +-----------------------------+   |
|   |                       | ------------------------> |   Cab & Road Search Agent   |   |
|   |                       | <------------------------ |   (CabRoadSearchProtocol)   |   |
|   +-----------------------+   TransportSearchResult   +-----------------------------+   |
+-----------------------------------------------------------------------------------------+
```

### Key Agent Engineering Highlights:
- **Clean Decoupling:** Modal search logic (`services/modal_search.py`) is completely separated from communication protocol code (`agents/*.py`).
- **Cryptographic Identities & Addresses:** Each agent has deterministic Ed25519 cryptographic keypairs generated from seeds.
- **Asynchronous uAgents Messaging:** True agent-to-agent message passing using `ctx.send(...)` and typed Pydantic models.
- **Request ID Correlation:** All message schemas include `request_id` to correlate asynchronous queries across distributed agents.
- **Resilience & Timeouts:** Handles empty results, impossible budget caps, and network timeouts cleanly.

---

## 🏛️ Project Architecture & Directory Layout

The project follows a clean, modular structure:

```
Route Rescue AI/
├── config/                     # Configuration and environment settings
│   ├── __init__.py
│   └── settings.py             # Settings (IST timezone, SQLite path, API ports)
├── schemas/                    # Shared Pydantic data models
│   ├── __init__.py
│   ├── common.py               # Enums (TransportMode, BookingStatus, SeatAvailability)
│   ├── travel.py               # Location, TransportService, UserJourney
│   ├── disruption.py           # DisruptionEvent schema
│   └── search.py               # Search requests, alternatives, recovery recommendations
├── data/                       # Synthetic datasets & SQLite persistence
│   ├── __init__.py
│   ├── synthetic_network.py    # Delhi, Jaipur, Chandigarh, Agra corridor network
│   ├── database.py             # Thread-safe SQLite DatabaseManager
│   └── seed_data.py            # Dataset seeder
│   └── routerescue.db          # SQLite database
├── services/                   # Business logic and transport search engine
│   ├── __init__.py
│   └── transport_service.py    # TransportDataService (multimodal filtering & tradeoffs)
├── backend/                    # FastAPI REST API
│   ├── __init__.py
│   └── main.py                 # Endpoints (/health, /search, /disruptions, /journeys)
├── frontend/                   # Streamlit Interactive Console
│   ├── __init__.py
│   └── app.py                  # Live dashboard & recovery view
├── agents/                     # [Phase 3] Fetch.ai uAgents multi-agent system
│   ├── __init__.py
│   └── README.md               # Agent specifications and uAgents protocol plan
├── tests/                      # Automated test suite
│   ├── conftest.py             # Pytest fixtures and isolated temporary databases
│   ├── test_schemas.py         # Schema validation & serialization tests
│   ├── test_synthetic_datasets.py # Dataset integrity, counts & overnight checks
│   └── test_transport_service.py  # Transport search & filtering tests
├── .env.example                # Example environment variables
├── requirements.txt            # Dependency specification
├── pyproject.toml              # Build & test configuration
└── README.md                   # Documentation
```

---

## 🗺️ Demonstration Transport Network

The demonstration network is centered around the Northern India Golden Transit Triangle:
- **Delhi & NCR**: New Delhi Railway Station (`NDLS`), Hazrat Nizamuddin (`NZM`), Kashmere Gate ISBT (`DEL_ISBT`), Indira Gandhi International Airport (`DEL_AIR`), Gurugram (`GGN`), Noida (`NOI`).
- **Jaipur**: Jaipur Junction (`JP`), Sindhi Camp Bus Stand (`JAI_BUS`), Jaipur Airport (`JAI_AIR`).
- **Chandigarh**: Chandigarh Junction (`CDG`), ISBT Sector 43 (`CDG_BUS`), Ambala Cantt (`UMB`).
- **Agra**: Agra Cantt (`AGC`), Idgah Bus Terminal (`AGR_BUS`), Mathura Junction (`MTJ`).

### Synthetic Dataset Guarantees:
- **32 Train Services**: Shatabdi, Vande Bharat, Rajdhani, Jan Shatabdi, Intercity, and overnight sleepers.
- **32 Intercity Bus Services**: Zingbus, IntrCity SmartBus, NueGo Electric AC, RSRTC Gold Line, Haryana Roadways Volvo, UPSRTC Janrath.
- **21 Cab and Road Connections**: Uber Intercity, BluSmart Electric, Savaari Car Rentals, and intra-city terminal transfers.
- **10 Simulated Disruption Scenarios**: Winter fog delays, track maintenance cancellations, overhead equipment failure, Yamuna Expressway gridlock, and airport ATC delay programs.
- **Data Integrity**: Every record includes exact departure/arrival times (with timezone awareness in `Asia/Kolkata` IST), distance, fare in INR, seat availability, provider name, direct booking URL, overnight flags, and explicit demonstration labels.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11, 3.12, or 3.13
- Git

### 2. Setup Virtual Environment
```bash
# Clone or navigate to the repository
cd "Route Rescue AI"

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Seed Synthetic Database
Populates the SQLite database (`data/routerescue.db`) with the demonstration transport network:
```bash
python -m data.seed_data
```

### 4. Run the Autonomous Multi-Agent System
Start the complete multi-agent system (Rail, Bus, Cab, and Recovery Planner) concurrently under the Fetch.ai Bureau:
```bash
python -m agents.runner
```
Or run each agent independently in its own process:
```bash
# Terminal 1 - Rail Agent (port 8001)
python -c "from agents.rail_agent import create_rail_agent; a = create_rail_agent(); a.run()"

# Terminal 2 - Bus Agent (port 8002)
python -c "from agents.bus_agent import create_bus_agent; a = create_bus_agent(); a.run()"

# Terminal 3 - Cab & Road Agent (port 8003)
python -c "from agents.cab_agent import create_cab_agent; a = create_cab_agent(); a.run()"

# Terminal 4 - Recovery Planner Agent (port 8004)
python -c "from agents.recovery_planner_agent import create_recovery_planner_agent; a = create_recovery_planner_agent(); a.run()"
```

### 5. Run Automated Multi-Agent & Integration Test Suite
```bash
pytest -v
```
All 33 automated tests across unit and multi-agent integration suites will execute and verify schema compliance, dataset integrity, search functionality, constraint validation, scoring algorithms, and asynchronous agent-to-agent messaging.

### 6. Launch the FastAPI Backend
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

### 7. Launch the Streamlit Frontend Console
In a separate terminal (with the virtual environment activated):
```bash
streamlit run frontend/app.py --server.port 8501
```
Open your browser at `http://localhost:8501` to explore available journeys, view active disruption alerts, and inspect passenger recovery profiles.

---

## 🧪 Testing Results

Executed with `pytest -v`:
- `tests/test_recovery_planner.py`: 6 tests passing (Hard constraint validation, deterministic multi-criteria scoring & ranking, natural-language explanation generation, full 5-agent uAgents messaging coordination, strict constraint rejection over messaging, and offline agent timeout resilience)
- `tests/test_agents_integration.py`: 5 tests passing (Agent identities & cryptographic addresses, separated modal search services, asynchronous uAgents message passing across 3 agents, departure time & budget filtering, and empty results resilience)
- `tests/test_schemas.py`: 6 tests passing (User journeys, booking status, disruptions, search models, recovery recommendations)
- `tests/test_synthetic_datasets.py`: 6 tests passing (>= 30 trains, >= 30 buses, >= 20 cabs, >= 10 disruptions, timezone & overnight accounting, demo labeling)
- `tests/test_transport_service.py`: 10 tests passing (origin/destination search, budget filtering, mode filtering, earliest departure, seat availability, overnight journeys, disruption checks, tradeoff summaries)

**Result: 33 passed, 0 failed in 94.21s (100% pass rate).**
