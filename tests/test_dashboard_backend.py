"""Tests for Phase 7 FastAPI Backend Endpoints supporting the Streamlit Dashboard."""

import pytest
from fastapi.testclient import TestClient

from backend.main import app, db, booking_provider
from schemas.common import BookingStatus
from schemas.disruption import DisruptionInjectionPayload


@pytest.fixture
def client():
    """Provides a FastAPI test client."""
    return TestClient(app)


def test_backend_health_check(client):
    """Verifies that the /health endpoint reports online status and demonstration labels."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert data["is_demo_mode"] is True
    assert "Delhi" in data["corridor"]


def test_journey_registration_endpoint(client):
    """Verifies that a passenger journey can be registered via POST /api/v1/journeys."""
    payload = {
        "passenger_name": "Kavita Rao",
        "passenger_email": "kavita.rao@example.com",
        "origin": "Delhi",
        "destination": "Jaipur",
        "booking_status": "CONFIRMED",
        "max_budget": 3500.0,
        "arrival_deadline": "14:00",
        "max_transfers": 1,
    }
    resp = client.post("/api/v1/journeys", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["passenger_name"] == "Kavita Rao"
    assert data["journey_id"].startswith("JRN-KAVITA")
    assert data["booking_reference"].startswith("PNR-")
    assert data["booked_service"]["origin"]["city"] == "Delhi"

    # Verify persistent retrieval
    get_resp = client.get(f"/api/v1/journeys/{data['journey_id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["journey_id"] == data["journey_id"]


def test_recovery_plan_endpoint(client):
    """Verifies direct recovery planning via POST /api/v1/recovery/plan."""
    payload = {
        "origin": "Delhi",
        "destination": "Jaipur",
        "max_budget": 4000.0,
        "max_transfers": 1,
    }
    resp = client.post("/api/v1/recovery/plan", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["origin"] == "Delhi"
    assert data["destination"] == "Jaipur"
    assert len(data["top_3_options"]) > 0
    assert "best_option_explanation" in data
    assert len(data["best_option_explanation"]) > 0


def test_agent_activity_endpoint(client):
    """Verifies structured agent activity retrieval via GET /api/v1/agents/activity."""
    # First inject a disruption to ensure activity exists
    client.post(
        "/api/v1/disruptions/inject",
        json={
            "journey_id": "JRN-ROHAN-9901",
            "status": "CANCELLED",
            "reason": "Test engine failure",
        },
    )

    resp = client.get("/api/v1/agents/activity?limit=20")
    assert resp.status_code == 200
    activities = resp.json()
    assert isinstance(activities, list)
    assert len(activities) > 0

    first = activities[0]
    assert "log_id" in first
    assert "timestamp" in first
    assert "agent_name" in first
    assert "action" in first
    assert "details" in first
    assert "event_type" in first


def test_booking_approval_requires_user_consent(client):
    """Verifies that booking handoff strictly rejects requests without explicit user consent."""
    payload = {
        "journey_id": "JRN-ROHAN-9901",
        "alternative_id": "ALT-TEST-001",
        "service_id": "BUS-ZB-101",
        "provider": "Zingbus",
        "booking_url": "https://www.zingbus.com",
        "fare_inr": 650.0,
        "user_approved": False,  # Missing user consent!
        "passenger_name": "Rohan Sharma",
    }
    resp = client.post("/api/v1/bookings/approve", json=payload)
    assert resp.status_code == 400
    assert "User approval required" in resp.json()["detail"]


def test_booking_approval_success_handoff(client):
    """Verifies successful booking approval when user authorization is explicitly granted."""
    payload = {
        "journey_id": "JRN-ROHAN-9901",
        "alternative_id": "ALT-TEST-001",
        "service_id": "BUS-ZB-101",
        "provider": "Zingbus",
        "booking_url": "https://www.zingbus.com/booking/test",
        "fare_inr": 650.0,
        "user_approved": True,  # User explicitly checked the approval box
        "passenger_name": "Rohan Sharma",
    }
    resp = client.post("/api/v1/bookings/approve", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["status"] == "APPROVED_BY_USER"
    assert "Zingbus" in data["message"]
    assert "DEMONSTRATION HANDOFF" in data["disclaimer"]
    assert data["booking_url"] == "https://www.zingbus.com/booking/test"

    # Verify journey was updated to CONFIRMED
    j_resp = client.get("/api/v1/journeys/JRN-ROHAN-9901")
    assert j_resp.status_code == 200
    assert j_resp.json()["booking_status"] == BookingStatus.CONFIRMED.value


def test_demo_reset_endpoint(client):
    """Verifies demonstration state reset restores baseline data and clears overrides."""
    # First set an override
    booking_provider.set_status("PNR-TEST-OVERRIDE", BookingStatus.CANCELLED)
    assert len(booking_provider.list_all_statuses()) > 0

    # Call reset
    resp = client.post("/api/v1/demo/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "reset to initial baseline" in data["message"]

    # Overrides should be cleared
    assert len(booking_provider.list_all_statuses()) == 0

    # Baseline journey Rohan Sharma should exist
    j_resp = client.get("/api/v1/journeys/JRN-ROHAN-9901")
    assert j_resp.status_code == 200
    assert j_resp.json()["passenger_name"] == "Rohan Sharma"


def test_end_to_end_dashboard_scenario(client):
    """
    End-to-End Success Criteria Test:
    1. Register a new passenger journey.
    2. Simulate a travel disruption on that journey.
    3. Observe that agent activity log captures both registration and disruption.
    4. Request recovery recommendations and verify ranked options.
    5. Approve booking handoff with explicit user authorization.
    """
    # 1. Register Journey
    reg_payload = {
        "passenger_name": "Devika Sen",
        "passenger_email": "devika.sen@example.com",
        "origin": "Delhi",
        "destination": "Jaipur",
        "booking_status": "CONFIRMED",
        "max_budget": 3000.0,
        "arrival_deadline": "17:00",
        "max_transfers": 1,
    }
    reg_resp = client.post("/api/v1/journeys", json=reg_payload)
    assert reg_resp.status_code == 200
    journey = reg_resp.json()
    journey_id = journey["journey_id"]
    assert journey["passenger_name"] == "Devika Sen"

    # 2. Simulate Disruption
    dis_payload = {
        "journey_id": journey_id,
        "status": "CANCELLED",
        "reason": "Sudden locomotive breakdown near Alwar",
    }
    dis_resp = client.post("/api/v1/disruptions/inject", json=dis_payload)
    assert dis_resp.status_code == 200
    assert dis_resp.json()["success"] is True

    # Check journey status updated
    j_check = client.get(f"/api/v1/journeys/{journey_id}")
    assert j_check.status_code == 200
    assert j_check.json()["booking_status"] == BookingStatus.CANCELLED.value

    # 3. Observe Agent Activity Log
    act_resp = client.get("/api/v1/agents/activity?limit=30")
    assert act_resp.status_code == 200
    activities = act_resp.json()
    event_types = [a["event_type"] for a in activities]
    assert "JOURNEY_REGISTERED" in event_types
    assert "DISRUPTION_INJECTED_VIA_API" in event_types

    # 4. Request Recovery Plan
    rec_payload = {
        "journey_id": journey_id,
        "origin": "Delhi",
        "destination": "Jaipur",
        "max_budget": 3500.0,
        "max_transfers": 1,
    }
    rec_resp = client.post("/api/v1/recovery/plan", json=rec_payload)
    assert rec_resp.status_code == 200
    plan = rec_resp.json()
    assert plan["success"] is True
    assert len(plan["top_3_options"]) > 0
    top_option = plan["top_3_options"][0]["alternative"]

    # 5. User-Authorized Booking Handoff
    handoff_payload = {
        "journey_id": journey_id,
        "alternative_id": top_option["alternative_id"],
        "service_id": top_option["service_id"],
        "provider": top_option["provider"],
        "booking_url": top_option.get("booking_url") or "https://www.zingbus.com",
        "fare_inr": top_option["fare_inr"],
        "user_approved": True,
        "passenger_name": "Devika Sen",
    }
    hand_resp = client.post("/api/v1/bookings/approve", json=handoff_payload)
    assert hand_resp.status_code == 200
    assert hand_resp.json()["status"] == "APPROVED_BY_USER"

    # Confirm journey was updated back to CONFIRMED
    final_j = client.get(f"/api/v1/journeys/{journey_id}").json()
    assert final_j["booking_status"] == BookingStatus.CONFIRMED.value
