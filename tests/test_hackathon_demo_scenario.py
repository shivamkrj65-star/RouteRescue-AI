"""Final QA Integration & Demonstration Verification Suite for RouteRescue AI.

Covers:
1. Exact Hackathon Scenario:
   - Delhi -> Jaipur passenger journey.
   - ₹1,500 budget and arrival before 11 PM (23:00).
   - Simulated cancellation detected by monitoring.
   - Real uAgents messaging: Planner -> Rail, Bus, Cab agents -> Planner.
   - Constraint validation and deterministic ranking.
   - Top route selection and user booking handoff.
2. Resilience when one modal agent is unavailable/offline.
3. Invalid inputs and unfeasible constraints (zero alternatives fallback).
4. Demo reset functionality and baseline synchronization.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, time as dt_time, timedelta
import threading
import time
from typing import List

import pytest
from fastapi.testclient import TestClient
from uagents import Agent, Bureau, Context

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.rail_agent import create_rail_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from backend.main import app, booking_provider, db
from config.settings import IST
from schemas.agent_messages import (
    RecoveryRequest,
    RecoveryResponse,
    TransportSearchAlternative,
)
from schemas.common import BookingStatus
from schemas.disruption import DisruptionInjectionPayload
from services.disruption_evaluator import DisruptionEvaluator


@contextmanager
def running_bureau(bureau: Bureau, loop: asyncio.AbstractEventLoop):
    """Context manager to run an isolated uAgents Bureau in a daemon thread."""
    def runner():
        asyncio.set_event_loop(loop)
        bureau.run()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    try:
        yield
    finally:
        def stop():
            for task in asyncio.all_tasks(loop):
                task.cancel()
        if not loop.is_closed():
            loop.call_soon_threadsafe(stop)
        thread.join(timeout=2.0)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


# ==============================================================================
# TEST 1: EXACT HACKATHON DEMONSTRATION SCENARIO (MULTI-AGENT)
# ==============================================================================

def test_exact_hackathon_demonstration_scenario(client):
    """
    Executes the exact hackathon scenario:
    1. Register simulated Delhi-to-Jaipur train journey (₹1,500 budget, arrival before 11 PM / 23:00).
    2. Simulated cancellation injected & detected.
    3. Multi-agent uAgents communication: Planner Agent queries Rail, Bus, and Cab agents.
    4. Dataset-backed options returned by transport agents.
    5. Planner filters hard constraints (Budget <= 1500, Arrival <= 23:00) and ranks routes.
    6. Verify dashboard backend receives plan with explanation.
    7. User approves booking handoff.
    """
    loop = asyncio.new_event_loop()
    port_base = 8900

    # 1. Register User Journey via Backend API
    reg_payload = {
        "passenger_name": "Arjun Singhania",
        "passenger_email": "arjun.singhania@example.com",
        "origin": "Delhi",
        "destination": "Jaipur",
        "booking_status": "CONFIRMED",
        "max_budget": 1500.0,
        "arrival_deadline": "23:00",
        "max_transfers": 1,
    }
    reg_resp = client.post("/api/v1/journeys", json=reg_payload)
    assert reg_resp.status_code == 200
    journey_data = reg_resp.json()
    journey_id = journey_data["journey_id"]
    pnr = journey_data["booking_reference"]
    assert journey_data["passenger_name"] == "Arjun Singhania"

    # 2. Simulate Cancellation
    dis_payload = {
        "journey_id": journey_id,
        "status": "CANCELLED",
        "reason": "Signal failure and track maintenance on Delhi-Jaipur line",
    }
    dis_resp = client.post("/api/v1/disruptions/inject", json=dis_payload)
    assert dis_resp.status_code == 200

    # Verify status changed in SQLite and evaluator triggers recovery
    evaluator = DisruptionEvaluator()
    journey_obj = db.get_user_journey(journey_id)
    assert journey_obj is not None
    sim_status = booking_provider.get_status(journey_obj)
    assert sim_status is not None
    assert sim_status.status == BookingStatus.CANCELLED
    is_change, should_recover, reason_code = evaluator.evaluate_status_change(
        old_status=BookingStatus.CONFIRMED, new_status=sim_status
    )
    assert is_change is True
    assert should_recover is True
    assert reason_code == "SERVICE_CANCELLED"

    # 3. Spin up genuine multi-agent uAgents Bureau
    rail_agent = create_rail_agent(db=db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=db, port=port_base + 2, loop=loop)
    cab_agent = create_cab_agent(db=db, port=port_base + 3, loop=loop)

    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=cab_agent.address,
        port=port_base + 4,
        loop=loop,
        timeout_seconds=3.0,
    )

    client_agent = Agent(
        name="hackathon_demo_client",
        seed="hackathon_demo_seed_8905",
        port=port_base + 5,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_recovery: List[RecoveryResponse] = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_recovery(ctx: Context, sender: str, msg: RecoveryResponse):
        received_recovery.append(msg)

    @client_agent.on_event("startup")
    async def dispatch_request(ctx: Context):
        await asyncio.sleep(0.5)
        # User constraint: budget ₹1,500, arrive before 11 PM (23:00)
        req = RecoveryRequest(
            request_id=f"HACKATHON-DEMO-{journey_id}",
            origin="Delhi",
            destination="Jaipur",
            max_budget=1500.0,
            latest_acceptable_arrival="23:00",
            max_transfers=1,
            user_id=journey_id,
        )
        await ctx.send(planner_agent.address, req)

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start = time.time()
        while not received_recovery and (time.time() - start) < 12.0:
            time.sleep(0.2)

    # 4. Verify multi-agent coordination results
    assert len(received_recovery) == 1, "Expected recovery plan from multi-agent coordination"
    plan = received_recovery[0]

    assert plan.success is True
    assert plan.origin == "Delhi"
    assert plan.destination == "Jaipur"
    assert plan.total_options_evaluated > 0

    # 5. Verify hard constraints strictly enforced
    assert len(plan.top_3_options) > 0, "Expected at least 1 feasible recovery option within ₹1,500 budget"
    for option in plan.top_3_options:
        alt = option.alternative
        assert alt.fare_inr <= 1500.0, f"Option {alt.service_number} exceeds ₹1,500 budget: {alt.fare_inr}"
        arr_time = datetime.fromisoformat(alt.arrival_time).time()
        assert arr_time <= dt_time(23, 0), f"Option {alt.service_number} arrives after 23:00: {arr_time}"

    # 6. Verify explanation is present and grounded
    assert plan.best_option_explanation != ""
    assert len(plan.best_option_explanation) > 20
    top_recommended = plan.top_3_options[0].alternative

    # 7. Execute Booking Handoff
    handoff_payload = {
        "journey_id": journey_id,
        "alternative_id": top_recommended.alternative_id,
        "service_id": top_recommended.service_id,
        "provider": top_recommended.provider,
        "booking_url": top_recommended.booking_url or "https://www.zingbus.com",
        "fare_inr": top_recommended.fare_inr,
        "user_approved": True,
        "passenger_name": "Arjun Singhania",
    }
    hand_resp = client.post("/api/v1/bookings/approve", json=handoff_payload)
    assert hand_resp.status_code == 200
    hand_data = hand_resp.json()
    assert hand_data["status"] == "APPROVED_BY_USER"
    assert "DEMONSTRATION HANDOFF" in hand_data["disclaimer"]

    # Verify journey record confirmed in database
    final_j = client.get(f"/api/v1/journeys/{journey_id}").json()
    assert final_j["booking_status"] == BookingStatus.CONFIRMED.value


# ==============================================================================
# TEST 2: RECOVERY RESILIENCE WITH UNAVAILABLE / OFFLINE MODAL AGENT
# ==============================================================================

def test_recovery_resilience_when_transport_agent_offline(client):
    """
    Verifies that when one modal agent (e.g. Cab agent) is offline or unreachable,
    the Recovery Planner gracefully completes recovery using the remaining agents.
    """
    loop = asyncio.new_event_loop()
    port_base = 8920

    rail_agent = create_rail_agent(db=db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=db, port=port_base + 2, loop=loop)
    # Intentionally provide a non-existent agent address for cab
    offline_cab_address = "agent1q_offline_cab_address_0000000000000000000000000000000"

    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=offline_cab_address,
        port=port_base + 3,
        loop=loop,
        timeout_seconds=1.5,
    )

    client_agent = Agent(
        name="test_offline_client",
        seed="test_offline_seed_8924",
        port=port_base + 4,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_recovery: List[RecoveryResponse] = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_recovery(ctx: Context, sender: str, msg: RecoveryResponse):
        received_recovery.append(msg)

    @client_agent.on_event("startup")
    async def dispatch_request(ctx: Context):
        await asyncio.sleep(0.5)
        req = RecoveryRequest(
            request_id="REQ-OFFLINE-TEST",
            origin="Delhi",
            destination="Jaipur",
            max_budget=2000.0,
            latest_acceptable_arrival="23:30",
            max_transfers=1,
        )
        await ctx.send(planner_agent.address, req)

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start = time.time()
        while not received_recovery and (time.time() - start) < 10.0:
            time.sleep(0.2)

    assert len(received_recovery) == 1, "Recovery planner must respond even if one agent is offline"
    resp = received_recovery[0]
    assert resp.success is True
    # Cab should be recorded as failed or timeout
    assert resp.modal_responses.get("CAB", {}).get("status") == "FAILED"
    # Train and Bus should succeed
    assert resp.modal_responses.get("TRAIN", {}).get("status") == "SUCCESS"
    assert resp.modal_responses.get("BUS", {}).get("status") == "SUCCESS"
    # Feasible alternatives still found from remaining agents
    assert len(resp.top_3_options) > 0


# ==============================================================================
# TEST 3: INVALID INPUTS & MISSING TRANSPORT ALTERNATIVES
# ==============================================================================

def test_invalid_inputs_and_missing_alternatives(client):
    """
    Verifies graceful handling of:
    1. Impossible budget ceiling (e.g. ₹50 when minimum fare is ₹450).
    2. Non-existent transit corridor.
    3. Missing user approval in booking handoff.
    """
    # 1. Impossible Budget
    resp_budget = client.post(
        "/api/v1/recovery/plan",
        json={
            "origin": "Delhi",
            "destination": "Jaipur",
            "max_budget": 50.0,  # Below any transit option
            "max_transfers": 1,
        },
    )
    assert resp_budget.status_code == 200
    plan_budget = resp_budget.json()
    assert plan_budget["valid_options_count"] == 0
    assert len(plan_budget["top_3_options"]) == 0
    assert "rejection_reasons" in plan_budget
    assert plan_budget["rejection_reasons"].get("fare_exceeded_maximum_budget", 0) > 0
    assert "No travel alternatives from Delhi to Jaipur" in plan_budget["best_option_explanation"]

    # 2. Non-existent Corridor
    resp_nowhere = client.post(
        "/api/v1/recovery/plan",
        json={
            "origin": "NowhereLand",
            "destination": "Atlantis",
            "max_budget": 5000.0,
            "max_transfers": 1,
        },
    )
    assert resp_nowhere.status_code == 200
    plan_nowhere = resp_nowhere.json()
    assert plan_nowhere["total_options_evaluated"] == 0
    assert len(plan_nowhere["top_3_options"]) == 0

    # 3. Missing user approval
    resp_unapproved = client.post(
        "/api/v1/bookings/approve",
        json={
            "alternative_id": "ALT-TEST",
            "service_id": "TRN-12004",
            "provider": "Indian Railways",
            "fare_inr": 800.0,
            "user_approved": False,
        },
    )
    assert resp_unapproved.status_code == 400
    assert "User approval required" in resp_unapproved.json()["detail"]


# ==============================================================================
# TEST 4: DEMO RESET FUNCTIONALITY
# ==============================================================================

def test_demo_reset_restores_baseline_data(client):
    """
    Verifies that calling the demonstration reset endpoint:
    1. Clears in-memory booking provider overrides.
    2. Restores seeded database records.
    3. Logs a DEMO_RESET event in SQLite audit log.
    """
    # 1. Inject multiple disruptions
    client.post(
        "/api/v1/disruptions/inject",
        json={"journey_id": "JRN-ROHAN-9901", "status": "CANCELLED", "reason": "Test disruption 1"},
    )
    client.post(
        "/api/v1/disruptions/inject",
        json={"journey_id": "JRN-PRIYA-1002", "status": "DELAYED", "delay_minutes": 180, "reason": "Test disruption 2"},
    )
    assert len(booking_provider.list_all_statuses()) >= 2

    # 2. Call reset
    reset_resp = client.post("/api/v1/demo/reset")
    assert reset_resp.status_code == 200
    assert reset_resp.json()["success"] is True

    # 3. Verify overrides cleared
    assert len(booking_provider.list_all_statuses()) == 0

    # 4. Verify audit log contains DEMO_RESET
    act_resp = client.get("/api/v1/agents/activity?limit=10")
    assert act_resp.status_code == 200
    logs = act_resp.json()
    event_types = [l["event_type"] for l in logs]
    assert "DEMO_RESET" in event_types
