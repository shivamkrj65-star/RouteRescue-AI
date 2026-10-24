"""RouteRescue AI - System Health Check Script.

Verifies:
1. Database connectivity and schema integrity
2. FastAPI backend availability
3. Streamlit dashboard availability
4. Synthetic transport datasets
5. Fetch.ai Agent identities & uAgents address verification
6. ASI:One / LLM configuration status
"""

import sys
import os
from pathlib import Path

# Force UTF-8 on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from config.settings import settings
from data.database import DatabaseManager
from data.synthetic_network import DEMO_LOCATIONS
from agents.rail_agent import create_rail_agent
from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from agents.disruption_monitor_agent import create_disruption_monitor_agent


def check_database() -> bool:
    print("[*] Checking Database...")
    try:
        db = DatabaseManager(settings.db_path)
        journeys = db.list_all_user_journeys()
        disruptions = db.get_active_disruptions()
        logs = db.get_monitoring_logs(limit=5)
        print(f"  [+] Database OK ({settings.db_path})")
        print(f"      Total journeys: {len(journeys)}, Active disruptions: {len(disruptions)}, Monitoring logs: {len(logs)}")
        return True
    except Exception as e:
        print(f"  [-] Database FAILED: {e}")
        return False


def check_datasets() -> bool:
    print("[*] Checking Synthetic Datasets...")
    try:
        db = DatabaseManager(settings.db_path)
        all_services = db.get_all_services()
        train_count = sum(1 for s in all_services if s.mode.value == "TRAIN")
        bus_count = sum(1 for s in all_services if s.mode.value == "BUS")
        cab_count = sum(1 for s in all_services if s.mode.value == "CAB")
        print(f"  [+] Synthetic Datasets OK ({len(all_services)} total services loaded in DB)")
        print(f"      Trains: {train_count}, Buses: {bus_count}, Cabs: {cab_count}")
        print(f"      Transit Hubs: {len(DEMO_LOCATIONS)}")
        return True
    except Exception as e:
        print(f"  [-] Datasets FAILED: {e}")
        return False


def check_agents() -> bool:
    print("[*] Checking Agent Identities & uAgents Addresses...")
    try:
        rail_agent = create_rail_agent()
        bus_agent = create_bus_agent()
        cab_agent = create_cab_agent()
        planner_agent = create_recovery_planner_agent()
        monitor_agent = create_disruption_monitor_agent()

        agents = [
            ("Rail Search Agent", rail_agent.address),
            ("Bus Search Agent", bus_agent.address),
            ("Cab Search Agent", cab_agent.address),
            ("Recovery Planner", planner_agent.address),
            ("Disruption Monitor", monitor_agent.address),
        ]
        for name, addr in agents:
            print(f"  [+] {name:25} -> {addr}")
        return True
    except Exception as e:
        print(f"  [-] Agent check FAILED: {e}")
        return False


def check_backend_api() -> bool:
    print(f"[*] Checking FastAPI Backend API (http://{settings.api_host}:{settings.api_port})...")
    url = f"http://{settings.api_host}:{settings.api_port}/health"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                print(f"  [+] Backend API OK: status={data.get('status')}, version={data.get('version', '0.1.0')}")
                return True
            else:
                print(f"  [-] Backend returned HTTP {resp.status_code}: {resp.text}")
                return False
    except httpx.ConnectError:
        print(f"  [?] Backend is not running on {url} (Start with: python scripts/start_all.py)")
        return False
    except Exception as e:
        print(f"  [-] Backend check FAILED: {e}")
        return False


def check_streamlit_dashboard() -> bool:
    print("[*] Checking Streamlit Dashboard (http://localhost:8501)...")
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get("http://localhost:8501")
            if resp.status_code == 200:
                print(f"  [+] Streamlit UI OK: HTTP 200")
                return True
            else:
                print(f"  [-] Streamlit returned HTTP {resp.status_code}")
                return False
    except httpx.ConnectError:
        print("  [?] Streamlit is not running on http://localhost:8501 (Start with: python scripts/start_all.py)")
        return False
    except Exception as e:
        print(f"  [-] Streamlit check FAILED: {e}")
        return False


def check_asione_config() -> bool:
    print("[*] Checking ASI:One / LLM Configuration...")
    key = settings.asione_api_key
    if key and not key.startswith("test_") and not key.startswith("demo_"):
        print(f"  [+] ASI:One API Key configured: {key[:8]}... (Live API enabled: model={settings.asione_model})")
    else:
        print(f"  [i] ASI:One API Key: Offline/Deterministic Mode Active (Ready for zero-latency local demo)")
    return True


def main():
    print("=" * 65)
    print("        RouteRescue AI - System Health Check")
    print("=" * 65)
    
    results = {
        "Database": check_database(),
        "Datasets": check_datasets(),
        "Agents": check_agents(),
        "ASI:One": check_asione_config(),
        "Backend API": check_backend_api(),
        "Dashboard UI": check_streamlit_dashboard(),
    }
    
    print("\n" + "=" * 65)
    print("                   Summary")
    print("=" * 65)
    all_ok = True
    for component, passed in results.items():
        status = "PASSED" if passed else "ATTENTION NEEDED"
        if not passed:
            all_ok = False
        print(f"  {component:20}: {status}")
    print("=" * 65)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
