"""RouteRescue AI - Complete System Orchestrator.

Starts all required processes in separate subprocesses:
1. FastAPI Backend API (`backend.main:app` on port 8000)
2. Streamlit Dashboard (`frontend/app.py` on port 8501)
3. Fetch.ai Agent Bureau (`agents.runner` on port 8010)

Handles clean shutdown on Ctrl+C.
"""

import sys
import subprocess
import time
import signal
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

if not VENV_PYTHON.exists():
    VENV_PYTHON = Path(sys.executable)


def main():
    print("=" * 65)
    print("      Starting RouteRescue AI Complete System Ecosystem")
    print("=" * 65)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Python:       {VENV_PYTHON}\n")

    processes = []
    
    try:
        # 1. FastAPI Backend
        print("[*] Launching FastAPI Backend on http://127.0.0.1:8000 ...")
        p_backend = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(PROJECT_ROOT)
        )
        processes.append(("FastAPI Backend", p_backend))
        time.sleep(2)

        # 2. Agent Bureau
        print("[*] Launching Multi-Agent Bureau on port 8010 ...")
        p_agents = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "agents.runner", "--mode", "bureau", "--port", "8010"],
            cwd=str(PROJECT_ROOT)
        )
        processes.append(("Agent Bureau", p_agents))
        time.sleep(2)

        # 3. Streamlit Frontend
        print("[*] Launching Streamlit Dashboard on http://localhost:8501 ...")
        p_frontend = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "streamlit", "run", "frontend/app.py", "--server.port", "8501", "--server.headless", "true"],
            cwd=str(PROJECT_ROOT)
        )
        processes.append(("Streamlit UI", p_frontend))

        print("\n" + "=" * 65)
        print("All RouteRescue AI services are running!")
        print("  - Backend API:       http://127.0.0.1:8000/docs")
        print("  - Streamlit UI:      http://localhost:8501")
        print("  - Agent Bureau:      port 8010")
        print("\nPress Ctrl+C to terminate all services safely.")
        print("=" * 65 + "\n")

        while True:
            time.sleep(1)
            for name, proc in processes:
                poll = proc.poll()
                if poll is not None:
                    print(f"[-] Warning: {name} exited unexpectedly with code {poll}!")

    except KeyboardInterrupt:
        print("\n[*] Shutting down all RouteRescue AI services...")
    finally:
        for name, proc in processes:
            if proc.poll() is None:
                print(f"  [+] Terminating {name}...")
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print("[+] All services stopped cleanly.")


if __name__ == "__main__":
    main()
