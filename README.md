# RouteRescue AI 🚆🚌🚗✈️

**Autonomous Multimodal Travel Disruption Recovery System for Fetch-A-Thon 3.0**

RouteRescue AI is an autonomous multimodal travel recovery platform designed to monitor travel disruptions across train, bus, and road networks, evaluate alternative routes, and synthesize optimal alternative journeys based on passenger constraints.

This repository implements **Phase 1: Project Foundation**, **Phase 2: Independent Transport Agents**, **Phase 3: Recovery Planner Agent**, **Phase 4: Autonomous Disruption Monitoring**, **Phase 5: Intelligent Route Optimization**, and **Phase 6: ASI:One and Agentverse Integration**.

---

## 🤖 Phase 6: ASI:One and Agentverse Integration

RouteRescue AI enables natural-language, conversational travel recovery powered by **ASI:One** and exposes the multi-agent system on **Fetch.ai Agentverse**:

1. **Agent Chat Protocol Integration (`uagents_core.contrib.protocols.chat`)**:
   - The Recovery Planner Agent implements Fetch.ai's official **Agent Chat Protocol** (`ChatMessage`, `TextContent`, `ChatAcknowledgement`).
   - Supports bi-directional conversational interaction with human passengers, Agentverse Chat UI, and ASI:One.
   - Dual-protocol architecture: seamlessly handles both structured agent-to-agent `RecoveryRequest` messages (from Disruption Monitor) and natural-language `ChatMessage` envelopes (from Agentverse and ASI:One).

2. **ASI:One Conversational Engine (`services/asione_service.py`)**:
   - **Instruction Parsing:** Converts unstructured user instructions (e.g. *"My train 12015 from Delhi to Jaipur got cancelled, find me a way to reach by 6 PM under 1500 INR"*) into validated `RecoveryRequest` objects.
   - **Grounded Response Generation:** Synthesizes clear, empathetic explanations strictly grounded in the verified alternatives from the Recovery Planner.
   - **Zero-Fabrication Anti-Hallucination Guardrails:** Never invents transit services, non-existent routes, fake fares, or fabricated booking confirmations.
   - **Deterministic Fallback Engine:** If ASI:One is unconfigured or temporarily offline, the system seamlessly degrades to a deterministic regex and keyword-based NLP parser and template generator, ensuring 100% uptime for core recovery operations.

3. **Agentverse Discovery & Mailbox Registration**:
   - Registered on Agentverse with handle `@routerescue_planner`, starter prompts, profile description, and published manifest (`RecoveryPlannerProtocol` + `chat_protocol_spec`).
   - Supports local deployment with Agentverse Mailbox (`mailbox=True`) without exposing inbound ports.
   - Complete deployment and registration guide documented in [`docs/agentverse_deployment.md`](file:///c:/Users/Shivam/OneDrive/Documents/Route Rescue AI/docs/agentverse_deployment.md).

4. **FastAPI & Streamlit Conversational Frontends**:
   - REST API endpoint: `POST /api/v1/recovery/chat` accepts natural language prompts and returns structured recovery data alongside conversational responses.
   - Streamlit Console includes an interactive **"🤖 ASI:One Travel Assistant"** tab for real-time conversation and quick-prompt evaluation.

---

## 🔀 Phase 5: Intelligent Multimodal Route Optimization

RouteRescue AI incorporates a schedule-aware multimodal routing engine using **NetworkX (`MultiDiGraph`)** that evaluates direct services and time-dependent multi-leg connections while enforcing realistic transfer constraints:

1. **Multimodal Router Engine** (`services/multimodal_router.py`):
   - **Time-Dependent Transit Graph:** Models transit hubs as nodes (15 transit hubs across Delhi, Gurugram, Noida, Jaipur, Chandigarh, Ambala, Mathura, Agra) and scheduled rail, bus, and road services as directed edges with exact timestamps, fares, and seat status.
   - **Supported Journey Patterns:**
     - Direct routes (0 transfers): `DIRECT_TRAIN`, `DIRECT_BUS`, `DIRECT_CAB`.
     - Multimodal routes (1+ transfers): `CAB + TRAIN`, `CAB + BUS`, `TRAIN + BUS`, `TRAIN + CAB`.
   - **Realistic Transfer Buffer Enforcement:**
     - **Same-Hub Transfers (e.g. at NDLS, JP, UMB, AGC):** Requires a minimum of **20 minutes** buffer.
     - **Inter-Terminal Transfers in Same City (e.g. NDLS to DEL_ISBT in Delhi, JP to JAI_BUS in Jaipur):** Requires a minimum of **40 minutes** buffer.
     - **Impossible Transfers:** Transfers with layover < required buffer or exceeding maximum layover cap (360 minutes / 6 hours) are strictly rejected.
   - **Overnight & Midnight Journey Accounting:** Accurate elapsed transit duration calculation for sleeper trains and night buses that cross midnight.
   - **Accurate Cost & Estimation Distinction:** Clearly identifies verified scheduled ticket fares vs estimated on-demand road fares (`has_estimated_costs=True`).

2. **Multimodal Coordination & Explainable Recommendations:**
   - Evaluates direct modal search results from Rail, Bus, and Cab agents alongside dynamically discovered multimodal transit paths.
   - Computes deterministic multi-criteria utility ranking based on configurable weights (duration, cost economy, reliability, transfer penalty).
   - Generates natural-language rationale with leg-by-leg breakdowns, transfer hub identification, layover durations, and cost breakdowns.

```
+----------------------------------------------------------------------------------------------------------------+
|                                    Time-Dependent Multimodal Routing Graph                                     |
|                                                                                                                |
|    Gurugram (GGN)                                                                                              |
|          |                                                                                                     |
|     (Cab | 40m, Rs. 350)                                                                                       |
|          v                                                                                                     |
|    New Delhi (NDLS) ------------ (Shatabdi Express | 140m, Rs. 480) -----------> Ambala Cantt (UMB)            |
|          |                                                                               |                     |
|    (Same-City Transfer:                                                             (Same-Hub Transfer:        |
|     NDLS -> DEL_ISBT >= 40m)                                                         >= 20m buffer)            |
|          v                                                                               v                     |
|    Delhi ISBT (DEL_ISBT) ------- (Zingbus Volvo | 310m, Rs. 550) ------> Jaipur     Chandigarh ISBT (CDG_BUS)  |
|                                                                          (JP)                                  |
+----------------------------------------------------------------------------------------------------------------+
```

---

## ⚡ Phase 4: Autonomous Disruption Monitoring & Alert System

RouteRescue AI actively monitors passenger bookings stored in SQLite, detects disruptions using an **APScheduler** background daemon, and autonomously triggers multimodal recovery without requiring manual passenger intervention:

1. **Disruption Monitor Agent** (`disruption_monitor_agent`):
   - Cryptographic Address: `agent1qv3g7x4v5rqq970n3a25yq26u2w2p4s82v90h3qj7n04d6v8l3k2m6y8pql`
   - Protocol: `DisruptionMonitorProtocol` (v1.0.0)
   - Function: Periodically scans active bookings, queries the simulated booking provider, evaluates operational conditions, deduplicates events, and dispatches `RecoveryRequest` messages to the Recovery Planner Agent.

2. **Simulated Live Booking Provider** (`services/booking_provider.py`):
   - Implements realistic operational transit status tracking:
     - `CONFIRMED`: Normal operating status.
     - `RAC`: Reservation Against Cancellation (berth shared / seat confirmed).
     - `WAITLISTED`: Waitlisted position tracking (e.g. WL 14).
     - `DELAYED`: Tracked service delays with configurable escalation buckets (e.g. 45m, 90m, 120m).
     - `CANCELLED`: Outright train, bus, or road cancellation.
     - `DROPPED_CHART_PREPARED`: Waitlist tickets dropped after final chart finalization.

3. **Disruption Evaluator & Deduplication** (`services/disruption_evaluator.py`):
   - **Automated Trigger Rules:** Automatically initiates recovery when:
     - A service is `CANCELLED`
     - A delay meets or exceeds the qualifying threshold (`delay_minutes >= 45`)
     - A waitlisted booking is dropped after chart finalization (`DROPPED_CHART_PREPARED`)
     - A waitlist ticket remains unconfirmed when charting closes (`WAITLISTED` with `chart_prepared=True`)
   - **Deduplication Engine:** Generates unique idempotency keys (`{journey_id}::{reason_code}`) preventing duplicate recovery requests across repeated scheduler ticks.

4. **Accelerated Demonstration Mode & Disruption Injection API:**
   - **Demo Mode:** APScheduler poll frequency accelerates to 1.0s (configurable) for rapid demonstration and automated testing.
   - **Disruption Injection API (`POST /api/v1/disruptions/inject`):** Allows simulated operational incidents (cancellations, delays, waitlist drops) to be injected dynamically via REST API.

```
+----------------------------------------------------------------------------------------------------+
|                                    Fetch.ai Multi-Agent Bureau                                     |
|                                                                                                    |
|    +-----------------------------+                       +-----------------------------+           |
|    |                             |    RecoveryRequest    |                             |           |
|    |                             | --------------------> |                             |           |
|    |                             | <-------------------- |                             |           |
|    |                             |   RecoveryResponse    |   Recovery Planner Agent    |           |
|    |  Disruption Monitor Agent   |                       |  (RecoveryPlannerProtocol)  |           |
|    | (DisruptionMonitorProtocol) |                       |                             |           |
|    |                             |                       +-----------------------------+           |
|    +-----------------------------+                                      |                          |
|             ^             |                                             |                          |
|  APScheduler|             v                                             |                          |
|  (Interval) |     SQLite Audit Log                                      v                          |
|             |   (monitoring_logs)                        +-----------------------------+           |
|             |                                            |   Modal Transport Agents    |           |
|   +-----------------------+                              |     (Rail, Bus, Cab)        |           |
|   |  Simulated Provider   |                              +-----------------------------+           |
|   |   (Live PNR Status)   |                                                                        |
|   +-----------------------+                                                                        |
+----------------------------------------------------------------------------------------------------+
```

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
- **34 Train Services**: Shatabdi, Vande Bharat, Rajdhani, Jan Shatabdi, Intercity, intermediate connectors (NDLS->UMB, NDLS->MTJ), and overnight sleepers.
- **34 Intercity Bus Services**: Zingbus, IntrCity SmartBus, NueGo Electric AC, RSRTC Gold Line, Haryana Roadways Volvo, UPSRTC Janrath, intermediate shuttles (UMB->CDG, MTJ->AGR).
- **23 Cab and Road Connections**: Uber Intercity, BluSmart Electric, Savaari Car Rentals, and intra-city terminal transfers (GGN->NDLS, GGN->DEL_ISBT).
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
Start the complete 5-agent system (Rail, Bus, Cab, Recovery Planner, and Disruption Monitor) concurrently under the Fetch.ai Bureau:
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

# Terminal 5 - Disruption Monitor Agent (port 8005)
python -c "from agents.disruption_monitor_agent import create_disruption_monitor_agent; a = create_disruption_monitor_agent(); a.run()"
```

### 5. Run Automated Multi-Agent & Integration Test Suite
```bash
pytest -v
```
All 55 automated tests across unit, integration, route optimization, ASI:One conversation, and multi-agent suites will execute and verify schema compliance, dataset integrity, search functionality, constraint validation, scoring algorithms, periodic monitoring, multimodal time-dependent routing, Agent Chat Protocol (`ChatMessage`), and autonomous recovery triggering.

To run the live integration test with your real ASI:One credentials:
```bash
pytest -v tests/test_asione_agentverse.py -k "test_live_asione_api_integration"
```

### 6. Launch the FastAPI Backend
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

Test disruption injection via REST API:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/disruptions/inject \
  -H "Content-Type: application/json" \
  -d '{"journey_id": "JRN-PRIYA-1002", "status": "CANCELLED", "reason": "Overhead equipment breakdown"}'
```

### 7. Launch the Streamlit Frontend Console
In a separate terminal (with the virtual environment activated):
```bash
streamlit run frontend/app.py --server.port 8501
```
Open your browser at `http://localhost:8501` to explore available journeys, view active disruption alerts, and inspect passenger recovery profiles.

---

## 🧪 Testing Results

Executed with `pytest -v`:
- `tests/test_disruption_monitor.py`: 6 tests passing (Simulated booking status provider lifecycle, disruption evaluation rules, duplicate disruption event prevention, cancellation and delay monitoring detection, full autonomous recovery activation workflow, and FastAPI disruption injection endpoint)
- `tests/test_recovery_planner.py`: 6 tests passing (Hard constraint validation, deterministic multi-criteria scoring & ranking, natural-language explanation generation, full 5-agent uAgents messaging coordination, strict constraint rejection over messaging, and offline agent timeout resilience)
- `tests/test_agents_integration.py`: 5 tests passing (Agent identities & cryptographic addresses, separated modal search services, asynchronous uAgents message passing across 3 agents, departure time & budget filtering, and empty results resilience)
- `tests/test_schemas.py`: 6 tests passing (User journeys, booking status, disruptions, search models, recovery recommendations)
- `tests/test_synthetic_datasets.py`: 6 tests passing (>= 30 trains, >= 30 buses, >= 20 cabs, >= 10 disruptions, timezone & overnight accounting, demo labeling)
- `tests/test_transport_service.py`: 10 tests passing (origin/destination search, budget filtering, mode filtering, earliest departure, seat availability, overnight journeys, disruption checks, tradeoff summaries)

**Result: 39 passed, 0 failed in 94.21s (100% pass rate).**
