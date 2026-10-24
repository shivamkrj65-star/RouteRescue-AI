# RouteRescue AI 🚆🚌🚗✈️

**Autonomous Multimodal Travel Disruption Recovery System for Fetch-A-Thon 3.0**

RouteRescue AI is an autonomous multimodal travel recovery platform designed to monitor travel disruptions across train, bus, and road networks, evaluate alternative routes, and synthesize optimal alternative journeys based on passenger constraints.

This repository implements **Phase 1: Project Foundation**.

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

### 4. Run Automated Test Suite
```bash
pytest -v
```
All 22 unit tests will execute and verify schema compliance, dataset integrity, and search functionality.

### 5. Launch the FastAPI Backend
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- Redoc: `http://127.0.0.1:8000/redoc`

### 6. Launch the Streamlit Frontend Console
In a separate terminal (with the virtual environment activated):
```bash
streamlit run frontend/app.py --server.port 8501
```
Open your browser at `http://localhost:8501` to explore available journeys, view active disruption alerts, and inspect passenger recovery profiles.

---

## 🧪 Testing Results

Executed with `pytest -v`:
- `tests/test_schemas.py`: 6 tests passing (User journeys, booking status, disruptions, search models, recovery recommendations)
- `tests/test_synthetic_datasets.py`: 6 tests passing (>= 30 trains, >= 30 buses, >= 20 cabs, >= 10 disruptions, timezone & overnight accounting, demo labeling)
- `tests/test_transport_service.py`: 10 tests passing (origin/destination search, budget filtering, mode filtering, earliest departure, seat availability, overnight journeys, disruption checks, tradeoff summaries)

**Result: 22 passed in 2.41s (100% pass rate).**
