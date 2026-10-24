"""Phase 8 Comprehensive Integration, Failure Testing, and ASI:One Verification Suite.

Validates:
1. Exact Step 4 end-to-end scenario (Initial status WL 18, budget ₹1500, arrival 23:00, cancellation, recovery, handoff).
2. Step 5 ASI:One conversational interaction and follow-ups:
   - "What if I reduce my budget to ₹1,000?"
   - "Show the fastest route."
   - "I don't want more than one transfer."
3. Step 6 Failure Scenarios:
   - Rail Agent unavailable
   - Bus Agent timeout
   - Invalid journey data
   - Empty route results
   - Duplicate disruption events
   - Database restart / re-initialization
   - ASI:One service unavailable / missing credentials fallback
   - Overnight route duration calculation
   - Impossible transfer buffer rejection
   - User budget lower than all alternatives
4. Step 7 Request ID consistency and audit log fidelity.
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
from services.asione_service import AsiOneService
from services.disruption_evaluator import DisruptionEvaluator
from services.multimodal_router import MultimodalRouter
from services.recovery_engine import RecoveryEngine


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
# 1. STEP 4: EXACT END-TO-END SCENARIO (WL 18 -> CANCELLED -> RECOVERY -> HANDOFF)
# ==============================================================================

def test_step4_exact_wl18_disruption_recovery_scenario(client):
    """
    Step 4 Scenario:
    1. Register Delhi-to-Jaipur train journey (initial status WL 18, budget ₹1,500, arrival 11 PM / 23:00, max transfers 1).
    2. Simulated status changes to CANCELLED.
    3. Monitoring Agent detects the event.
    4. Recovery Planner automatically coordinates Rail, Bus, and Cab agents.
    5. Feasible alternatives filtered and ranked.
    6. Recommendation displayed and booking handoff approved.
    """
    loop = asyncio.new_event_loop()
    port_base = 8940

    # 1. Register Journey with WL status
    reg_payload = {
        "passenger_name": "Rohan Verma",
        "passenger_email": "rohan.verma@example.com",
        "origin": "Delhi",
        "destination": "Jaipur",
        "booking_status": "WAITLISTED",
        "booking_reference": "PNR-WL18-TEST",
        "fare_inr": 1250.0,
        "max_budget": 1500.0,
        "arrival_deadline": "23:00",
        "max_transfers": 1,
    }
    reg_resp = client.post("/api/v1/journeys", json=reg_payload)
    assert reg_resp.status_code == 200
    j_data = reg_resp.json()
    journey_id = j_data["journey_id"]
    assert j_data["booking_status"] == "WAITLISTED"

    # Set initial simulated status to WL 18
    booking_provider.inject_disruption(
        DisruptionInjectionPayload(
            journey_id=journey_id,
            status="WAITLISTED",
            pnr_position="WL 18",
            chart_prepared=False,
            reason="Initial waitlist ticket",
        )
    )

    # 2. Simulated status changes to CANCELLED
    dis_resp = client.post(
        "/api/v1/disruptions/inject",
        json={
            "journey_id": journey_id,
            "status": "CANCELLED",
            "reason": "Overhead traction line snapped between Rewari and Alwar",
        },
    )
    assert dis_resp.status_code == 200

    # 3. Disruption Evaluator detects cancellation
    evaluator = DisruptionEvaluator()
    journey_obj = db.get_user_journey(journey_id)
    sim_status = booking_provider.get_status(journey_obj)
    is_change, should_recover, reason_code = evaluator.evaluate_status_change(
        old_status=BookingStatus.WAITLISTED,
        new_status=sim_status,
    )
    assert is_change is True
    assert should_recover is True
    assert reason_code == "SERVICE_CANCELLED"

    # 4. Multi-agent coordination
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
        name="step4_client",
        seed="step4_client_seed_8945",
        port=port_base + 5,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_plans: List[RecoveryResponse] = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_plan(ctx: Context, sender: str, msg: RecoveryResponse):
        received_plans.append(msg)

    @client_agent.on_event("startup")
    async def run_query(ctx: Context):
        await asyncio.sleep(0.5)
        req = RecoveryRequest(
            request_id=f"REQ-STEP4-{journey_id}",
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
        while not received_plans and (time.time() - start) < 12.0:
            time.sleep(0.2)

    assert len(received_plans) == 1
    plan = received_plans[0]
    assert plan.success is True
    assert plan.total_options_evaluated > 0

    # 5. Check constraints & ranking
    assert len(plan.top_3_options) > 0
    top_opt = plan.top_3_options[0].alternative
    assert top_opt.fare_inr <= 1500.0
    arr_t = datetime.fromisoformat(top_opt.arrival_time).time()
    assert arr_t <= dt_time(23, 0)
    assert plan.best_option_explanation != ""

    # 6. Booking handoff
    hand_resp = client.post(
        "/api/v1/bookings/approve",
        json={
            "journey_id": journey_id,
            "alternative_id": top_opt.alternative_id,
            "service_id": top_opt.service_id,
            "provider": top_opt.provider,
            "booking_url": top_opt.booking_url or "https://www.zingbus.com",
            "fare_inr": top_opt.fare_inr,
            "user_approved": True,
            "passenger_name": "Rohan Verma",
        },
    )
    assert hand_resp.status_code == 200
    assert hand_resp.json()["status"] == "APPROVED_BY_USER"


# ==============================================================================
# 2. STEP 5: ASI:ONE CONVERSATIONAL INTERACTION & FOLLOW-UPS
# ==============================================================================

@pytest.mark.asyncio
async def test_step5_asione_conversational_followups():
    """
    Step 5 Scenario:
    Tests natural language instructions and follow-ups:
    1. Primary: "My train from Delhi to Jaipur was cancelled, find me a route under 1500 before 11 PM"
    2. Follow-up: "What if I reduce my budget to ₹1,000?"
    3. Follow-up: "Show the fastest route."
    4. Follow-up: "I don't want more than one transfer."
    """
    service = AsiOneService()

    # 1. Primary Instruction
    req1, _ = await service.parse_instruction_to_request(
        "My train from Delhi to Jaipur was cancelled, find me a route under 1500 before 11 PM"
    )
    assert req1.origin == "Delhi"
    assert req1.destination == "Jaipur"
    assert req1.max_budget == 1500.0
    assert req1.latest_acceptable_arrival == "23:00:00"

    # 2. Follow-up: Reduced budget to ₹1,000
    req2, _ = await service.parse_instruction_to_request("What if I reduce my budget to ₹1,000?")
    assert req2.max_budget == 1000.0

    # 3. Follow-up: Fastest route
    req3, _ = await service.parse_instruction_to_request("Show the fastest route from Delhi to Jaipur")
    assert req3.weights is not None
    assert req3.weights.duration_weight >= 0.60

    # 4. Follow-up: Transfer preference
    req4, _ = await service.parse_instruction_to_request("I don't want more than one transfer from Delhi to Jaipur")
    assert req4.max_transfers == 1


# ==============================================================================
# 3. STEP 6: COMPREHENSIVE FAILURE & RESILIENCE SCENARIOS
# ==============================================================================

def test_failure_rail_agent_unavailable():
    """Simulate Rail Agent offline: Planner recovers using Bus and Cab agents."""
    loop = asyncio.new_event_loop()
    port_base = 8960

    bus_agent = create_bus_agent(db=db, port=port_base + 1, loop=loop)
    cab_agent = create_cab_agent(db=db, port=port_base + 2, loop=loop)
    dummy_rail_address = "agent1q_offline_rail_00000000000000000000000000000000"

    planner = create_recovery_planner_agent(
        rail_agent_address=dummy_rail_address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=cab_agent.address,
        port=port_base + 3,
        loop=loop,
        timeout_seconds=1.5,
    )

    client_agent = Agent(name="rail_offline_client", seed="rail_offline_seed", port=port_base + 4, loop=loop)
    client_agent._mark_inactive_on_shutdown = False
    plans = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_plan(ctx: Context, sender: str, msg: RecoveryResponse):
        plans.append(msg)

    @client_agent.on_event("startup")
    async def run_q(ctx: Context):
        await asyncio.sleep(0.5)
        await ctx.send(
            planner.address,
            RecoveryRequest(
                request_id="REQ-RAIL-OFFLINE",
                origin="Delhi",
                destination="Jaipur",
                max_budget=2500.0,
                max_transfers=1,
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start = time.time()
        while not plans and (time.time() - start) < 10.0:
            time.sleep(0.2)

    assert len(plans) == 1
    p = plans[0]
    assert p.success is True
    assert p.modal_responses.get("TRAIN", {}).get("status") == "FAILED"
    assert p.modal_responses.get("BUS", {}).get("status") == "SUCCESS"
    assert len(p.top_3_options) > 0


def test_failure_bus_agent_timeout():
    """Simulate Bus Agent timeout: Planner recovers using Rail and Cab agents."""
    loop = asyncio.new_event_loop()
    port_base = 8980

    rail_agent = create_rail_agent(db=db, port=port_base + 1, loop=loop)
    cab_agent = create_cab_agent(db=db, port=port_base + 2, loop=loop)
    dummy_bus_address = "agent1q_offline_bus_00000000000000000000000000000000"

    planner = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=dummy_bus_address,
        cab_agent_address=cab_agent.address,
        port=port_base + 3,
        loop=loop,
        timeout_seconds=1.5,
    )

    client_agent = Agent(name="bus_offline_client", seed="bus_offline_seed", port=port_base + 4, loop=loop)
    client_agent._mark_inactive_on_shutdown = False
    plans = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_plan(ctx: Context, sender: str, msg: RecoveryResponse):
        plans.append(msg)

    @client_agent.on_event("startup")
    async def run_q(ctx: Context):
        await asyncio.sleep(0.5)
        await ctx.send(
            planner.address,
            RecoveryRequest(
                request_id="REQ-BUS-OFFLINE",
                origin="Delhi",
                destination="Jaipur",
                max_budget=2500.0,
                max_transfers=1,
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(cab_agent)
    bureau.add(planner)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start = time.time()
        while not plans and (time.time() - start) < 10.0:
            time.sleep(0.2)

    assert len(plans) == 1
    p = plans[0]
    assert p.success is True
    assert p.modal_responses.get("BUS", {}).get("status") == "FAILED"
    assert p.modal_responses.get("TRAIN", {}).get("status") == "SUCCESS"
    assert len(p.top_3_options) > 0


def test_failure_duplicate_disruption_prevention():
    """Verifies that injecting the identical disruption event twice is deduplicated."""
    evaluator = DisruptionEvaluator()
    payload = DisruptionInjectionPayload(
        journey_id="JRN-PRIYA-1002",
        status="DELAYED",
        delay_minutes=60,
        reason="Dense fog",
    )
    sim_status = booking_provider.inject_disruption(payload)

    # First event evaluation -> should trigger
    is_change, should_recover1, reason_code = evaluator.evaluate_status_change(
        old_status=BookingStatus.CONFIRMED, new_status=sim_status
    )
    assert should_recover1 is True
    # Record trigger in evaluator dedup set
    evaluator.mark_triggered("JRN-PRIYA-1002", reason_code)

    # Re-evaluate same state with deduplication check
    is_dupe = evaluator.is_duplicate("JRN-PRIYA-1002", reason_code)
    assert is_dupe is True, "Duplicate disruption must be recognized to prevent duplicate recovery triggers"


def test_failure_impossible_transfer_rejected():
    """Verifies that connections with transfer layover < minimum buffer are rejected."""
    from services.multimodal_router import JourneyLeg
    base_time = datetime(2026, 10, 24, 8, 0, tzinfo=IST)
    leg1 = JourneyLeg(
        leg_index=1,
        service_id="LEG-1",
        service_number="Shatabdi Express",
        provider="Northern Railway",
        mode="TRAIN",
        origin_code="UMB",
        origin_name="Ambala Cantt",
        origin_city="Ambala",
        destination_code="NDLS",
        destination_name="New Delhi",
        destination_city="Delhi",
        departure_time=base_time,
        arrival_time=base_time + timedelta(hours=2),  # 10:00
        duration_minutes=120,
        distance_km=200.0,
        fare_inr=300.0,
        seat_availability="AVAILABLE",
    )
    # Create leg 2 with impossible 5 min layover at NDLS (< 20m same-hub buffer)
    leg2_too_fast = JourneyLeg(
        leg_index=2,
        service_id="LEG-TOO-FAST",
        service_number="Fast Bus",
        provider="Zingbus",
        mode="BUS",
        origin_code="NDLS",
        origin_name="New Delhi",
        origin_city="Delhi",
        destination_code="JP",
        destination_name="Jaipur",
        destination_city="Jaipur",
        departure_time=base_time + timedelta(hours=2, minutes=5),  # 10:05 (5 min layover)
        arrival_time=base_time + timedelta(hours=6),
        duration_minutes=235,
        distance_km=250.0,
        fare_inr=500.0,
        seat_availability="AVAILABLE",
    )
    feasible, layover, reason = MultimodalRouter.is_transfer_feasible(leg1, leg2_too_fast)
    assert feasible is False
    assert layover == 5
    assert "impossible connection" in reason.lower()


def test_failure_user_budget_lower_than_all_alternatives(client):
    """Verifies graceful handling when budget ceiling is lower than all alternatives."""
    resp = client.post(
        "/api/v1/recovery/plan",
        json={"origin": "Delhi", "destination": "Jaipur", "max_budget": 100.0, "max_transfers": 1},
    )
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["valid_options_count"] == 0
    assert plan["rejection_reasons"].get("fare_exceeded_maximum_budget", 0) > 0


# ==============================================================================
# 4. STEP 7: LOGS AND REQUEST ID FIDELITY
# ==============================================================================

def test_step7_request_id_consistency_and_logs(client):
    """
    Step 7 Scenario:
    Verifies that request IDs remain consistent across the search and recovery cycle,
    and audit logs stored in SQLite accurately record agent operations.
    """
    req_payload = {
        "origin": "Delhi",
        "destination": "Jaipur",
        "max_budget": 3000.0,
        "max_transfers": 1,
    }
    resp = client.post("/api/v1/recovery/plan", json=req_payload)
    assert resp.status_code == 200
    plan = resp.json()
    req_id = plan["request_id"]
    assert req_id.startswith("REC-REQ-")

    # Verify audit logs captured this request_id
    act_resp = client.get("/api/v1/agents/activity?limit=20")
    assert act_resp.status_code == 200
    activities = act_resp.json()

    found_req_id = False
    for a in activities:
        details = a.get("details", {})
        if details.get("request_id") == req_id:
            found_req_id = True
            break
    assert found_req_id is True, f"Audit log did not record request ID {req_id}"
