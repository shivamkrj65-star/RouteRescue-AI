# RouteRescue AI 🚆🚌🚗✈️

**Autonomous Multimodal Travel Recovery System for Fetch-A-Thon 3.0**

RouteRescue AI is an autonomous, decentralized multi-agent system built on the **Fetch.ai uAgents Framework**, **Agentverse**, and **ASI:One**. When travel disruptions strike—such as cancelled trains, grounded flights, or blocked highways—RouteRescue AI detects the incidents in real-time, coordinates modal search agents across rail, bus/coach, and road/cab providers, and synthesizes optimal alternative multimodal journeys tailored to user budget, deadlines, and transfer limits.

---

## 🏛️ System Architecture

```
                        +----------------------------+
                        |          User UI           |
                        |   (Streamlit Console)      |
                        +--------------+-------------+
                                       |
                                       v
                        +----------------------------+
                        |      FastAPI Backend       |
                        |  (REST API & Webhooks)     |
                        +--------------+-------------+
                                       |
        ===============================+================================
        Fetch.ai uAgents Multi-Agent Bureau / Decentralized Mesh Network
        ===============================+================================
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
       +-----------------------+              +-------------------------+
       |  Disruption Monitor   |              |    Recovery Planner     |
       |         Agent         |              |          Agent          |
       +-----------+-----------+              +------------+------------+
                   |                                       |
                   | (DisruptionAlertMessage)              | (ModalSearchRequest)
                   +-------------------------------------->|
                                                           |
                      +-------------------+----------------+-------------------+
                      |                   |                                    |
                      v                   v                                    v
           +--------------------+ +--------------------+             +--------------------+
           |  Rail Search Agent | |  Bus Search Agent  |             |  Cab & Road Agent  |
           |  (Avanti, LNER,    | | (National Express, |             | (Uber, Cabs, Road  |
           |   TransPennine)    | |  Megabus, FlixBus) |             |  Highway Transfer) |
           +--------------------+ +--------------------+             +--------------------+
                      |                   |                                    |
                      +-------------------+------------------------------------+
                                          | (ModalSearchResponse)
                                          v
                              +------------------------+
                              | Multimodal Optimizer   |
                              | (NetworkX Graph Engine)|
                              +------------------------+
                                          |
                                          v
                              +------------------------+
                              | Human-in-the-Loop Gate |
                              | (User Approval Engine) |
                              +------------------------+
```

---

## 🤖 Required Agents

1. **Disruption Monitor Agent**: Continuously polls and streams train, flight, and road incidents, broadcasting alerts to the Recovery Planner.
2. **Rail Search Agent**: Discovers available alternative train departures and interconnecting railway corridors.
3. **Bus Search Agent**: Identifies intercity coach and regional bus alternatives.
4. **Cab & Road Agent**: Computes dynamic road alternatives, intra-city transit transfers (e.g., station-to-coach station), and emergency highway connections.
5. **Recovery Planner Agent**: Orchestrates the multi-agent consensus, queries the NetworkX Multimodal Optimizer, and generates ranked recovery plans.

---

## 🔒 Key Design Guarantees

1. **Authenticity Tagging (`DataVerificationStatus`)**:
   - `VERIFIED_LIVE`: Authenticated live partner data.
   - `SIMULATED_ESTIMATE`: Synthetic travel data and estimated rates clearly labeled.
   - Live availability and prices are **never fabricated**.
2. **Human-In-The-Loop Approval (`BookingApprovalStatus`)**:
   - All recovery itineraries require explicit user approval (`APPROVED_BY_USER`) before any booking instructions or reservation executions can proceed.
3. **Strict Typed Message Protocols**:
   - Every message derives directly from `uagents.Model` for Fetch.ai compatibility.

---

## 📁 Repository Structure

```
Route Rescue AI/
├── pyproject.toml              # Project metadata and dependencies
├── requirements.txt            # Pinned requirements
├── README.md                   # System documentation
├── data/
│   └── routerescue.db          # SQLite database (schedules, disruptions, audit logs)
├── src/
│   └── routerescue/
│       ├── __init__.py
│       ├── config.py           # System settings, agent ports & seed phrases
│       ├── schemas/            # Fetch.ai uAgents Pydantic-compatible schemas
│       │   ├── __init__.py
│       │   ├── common.py       # Enums (modes, severities, verification, approval)
│       │   ├── disruption.py   # DisruptionEvent schema
│       │   ├── travel.py       # Location, TravelSegment, Journey, PassengerProfile
│       │   └── messages.py     # Agent-to-agent message payloads
│       ├── data/               # Realistic synthetic datasets & persistence
│       │   ├── __init__.py
│       │   ├── database.py     # SQLite DatabaseManager with audit logging
│       │   ├── synthetic_corridors.py # Core UK hubs & disruption scenarios
│       │   └── seed_data.py    # Timetable generator & database seeder
│       ├── optimizer/          # [Phase 2] Multimodal NetworkX route solver
│       ├── agents/             # [Phase 3] Fetch.ai uAgents implementation
│       ├── api/                # [Phase 4] FastAPI REST endpoints
│       └── ui/                 # [Phase 4] Streamlit interactive operations console
└── tests/
    ├── conftest.py             # Test fixtures and isolated temp DBs
    ├── test_schemas.py         # Schema compliance & verification tests
    ├── test_database.py        # SQLite queries, constraints, and audit tests
    └── test_synthetic_data.py  # Corridor integrity & timetable generation tests
```

---

## 🚀 Development Phases

- **Phase 1 (Completed ✅)**: Project foundation, shared schemas (`uagents.Model`), realistic synthetic datasets across UK corridors (3,300+ segments, 13 hubs, 3 benchmark disruptions), SQLite audit layer, and test suite (15/15 passing).
- **Phase 2 (Next)**: NetworkX Multimodal Route Recovery Optimizer considering budget limits, arrival deadlines, transfer penalties, and layover buffers.
- **Phase 3**: Five autonomous Fetch.ai uAgents with agent-to-agent messaging protocol and local `Bureau` execution.
- **Phase 4**: FastAPI backend and Streamlit interactive travel recovery dashboard.
- **Phase 5**: Agentverse & ASI:One integration with full end-to-end integration tests.

---

## 🧪 Running Tests

```bash
# Activate virtual environment
.\.venv\Scripts\activate

# Run test suite
pytest
```
