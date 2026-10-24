"""FastAPI Backend Client for Streamlit Dashboard in RouteRescue AI."""

import os
from typing import Any, Dict, List, Optional
import httpx

BACKEND_BASE_URL = os.getenv("ROUTERESCUE_BACKEND_URL", "http://127.0.0.1:8000")


class RouteRescueApiClient:
    """Client for communicating with the RouteRescue AI FastAPI backend."""

    def __init__(self, base_url: str = BACKEND_BASE_URL, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def check_health(self) -> Dict[str, Any]:
        """Checks if the FastAPI backend is online and healthy."""
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "offline", "error": str(e)}

    def list_locations(self) -> List[Dict[str, Any]]:
        """Retrieves all transit hub locations across Delhi, Jaipur, Chandigarh, Agra."""
        try:
            resp = httpx.get(f"{self.base_url}/api/v1/locations", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return []

    def list_user_journeys(self) -> List[Dict[str, Any]]:
        """Retrieves all active passenger journeys."""
        try:
            resp = httpx.get(f"{self.base_url}/api/v1/journeys", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return []

    def get_user_journey(self, journey_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves details of a specific passenger journey."""
        try:
            resp = httpx.get(f"{self.base_url}/api/v1/journeys/{journey_id}", timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def register_journey(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Registers a new user journey in the backend."""
        resp = httpx.post(f"{self.base_url}/api/v1/journeys", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def list_disruptions(
        self, city: Optional[str] = None, mode: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Lists active travel disruptions."""
        try:
            params = {}
            if city:
                params["city"] = city
            if mode and mode != "ALL":
                params["mode"] = mode
            resp = httpx.get(f"{self.base_url}/api/v1/disruptions", params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def inject_disruption(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Simulates a travel disruption (cancellation, delay, waitlist change)."""
        resp = httpx.post(f"{self.base_url}/api/v1/disruptions/inject", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Retrieves monitoring daemon configuration and active overrides count."""
        try:
            resp = httpx.get(f"{self.base_url}/api/v1/monitoring/status", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"active_overrides_count": 0, "overrides": {}, "error": str(e)}

    def get_monitoring_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves raw audit logs from the monitoring daemon."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/monitoring/logs",
                params={"limit": limit},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def get_agent_activity(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves real structured agent activity events."""
        try:
            resp = httpx.get(
                f"{self.base_url}/api/v1/agents/activity",
                params={"limit": limit},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return []

    def plan_recovery(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates multimodal recovery alternatives for a disrupted journey or route query."""
        resp = httpx.post(f"{self.base_url}/api/v1/recovery/plan", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def chat_recovery(
        self,
        message: str,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        max_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Interacts conversationally with ASI:One and the Recovery Planner."""
        payload: Dict[str, Any] = {"message": message}
        if origin:
            payload["origin"] = origin
        if destination:
            payload["destination"] = destination
        if max_budget is not None:
            payload["max_budget"] = max_budget

        resp = httpx.post(f"{self.base_url}/api/v1/recovery/chat", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def approve_booking(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Executes explicit user approval for a recovery travel alternative handoff."""
        resp = httpx.post(f"{self.base_url}/api/v1/bookings/approve", json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def reset_demo(self) -> Dict[str, Any]:
        """Resets the demonstration state, booking overrides, and seeded database."""
        resp = httpx.post(f"{self.base_url}/api/v1/demo/reset", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
