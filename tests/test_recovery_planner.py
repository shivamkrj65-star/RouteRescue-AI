"""Tests for Recovery Planner Agent and RecoveryEngine.

Includes:
1. Unit tests for deterministic constraint validation, scoring, ranking, and explanation generation.
2. Full multi-agent uAgents integration tests verifying genuine messaging:
   Client Agent -> Recovery Planner Agent -> Rail, Bus, Cab Agents -> Recovery Planner Agent -> Client Agent.
3. Constraint rejection over multi-agent messaging (budget, arrival deadlines).
4. Offline / unavailable agent timeout resilience.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, time as dt_time
import threading
import time
from typing import List

import pytest
from uagents import Agent, Bureau, Context

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.rail_agent import create_rail_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from data.database import DatabaseManager
from schemas.agent_messages import (
    RankedAlternative,
    RecoveryRequest,
    RecoveryResponse,
    ScoringWeights,
    TransportSearchAlternative,
    TransportSearchResult,
)
from services.recovery_engine import RecoveryEngine


@contextmanager
def running_bureau(bureau: Bureau, loop: asyncio.AbstractEventLoop):
    """Context manager to run a Bureau in an isolated thread and shut it down cleanly."""
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


# ==============================================================================
# 1. UNIT TESTS: RECOVERY ENGINE DETERMINISTIC LOGIC
# ==============================================================================

def test_recovery_engine_constraint_validation():
    """Verify RecoveryEngine enforces hard constraints: budget, arrival, departure, seat availability."""
    engine = RecoveryEngine()

    alternatives = [
        # Option 1: Valid affordable train
        TransportSearchAlternative(
            alternative_id="ALT-1",
            rank=1,
            service_id="TRN-01",
            service_number="12015 Ajmer Shatabdi",
            provider="Northern Railway",
            mode="TRAIN",
            origin_code="NDLS",
            origin_name="New Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T06:10:00+05:30",
            arrival_time="2026-10-24T10:40:00+05:30",
            duration_minutes=270,
            distance_km=308.0,
            fare_inr=950.0,
            seat_availability="AVAILABLE",
            tradeoffs="Fast transit",
        ),
        # Option 2: Over-budget cab
        TransportSearchAlternative(
            alternative_id="ALT-2",
            rank=2,
            service_id="CAB-01",
            service_number="Uber Intercity Sedan",
            provider="Uber India",
            mode="CAB",
            origin_code="NDLS",
            origin_name="New Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T07:00:00+05:30",
            arrival_time="2026-10-24T11:45:00+05:30",
            duration_minutes=285,
            distance_km=280.0,
            fare_inr=4200.0,
            seat_availability="ON_DEMAND",
            tradeoffs="Private door-to-point",
        ),
        # Option 3: Too late arrival bus
        TransportSearchAlternative(
            alternative_id="ALT-3",
            rank=3,
            service_id="BUS-01",
            service_number="RSRTC Night Express",
            provider="RSRTC",
            mode="BUS",
            origin_code="DEL_ISBT",
            origin_name="Kashmere Gate",
            destination_code="JAI_BUS",
            destination_name="Sindhi Camp",
            departure_time="2026-10-24T18:00:00+05:30",
            arrival_time="2026-10-24T23:30:00+05:30",
            duration_minutes=330,
            distance_km=280.0,
            fare_inr=450.0,
            seat_availability="AVAILABLE",
            tradeoffs="Night arrival",
        ),
        # Option 4: Sold out train
        TransportSearchAlternative(
            alternative_id="ALT-4",
            rank=4,
            service_id="TRN-02",
            service_number="20978 Vande Bharat",
            provider="Northern Railway",
            mode="TRAIN",
            origin_code="NDLS",
            origin_name="New Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T06:40:00+05:30",
            arrival_time="2026-10-24T10:35:00+05:30",
            duration_minutes=235,
            distance_km=308.0,
            fare_inr=1250.0,
            seat_availability="SOLD_OUT",
            tradeoffs="Sold out",
        ),
        # Option 5: Too early departure train
        TransportSearchAlternative(
            alternative_id="ALT-5",
            rank=5,
            service_id="TRN-03",
            service_number="12414 Jammu Mail",
            provider="Northern Railway",
            mode="TRAIN",
            origin_code="DLI",
            origin_name="Old Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T04:15:00+05:30",
            arrival_time="2026-10-24T09:50:00+05:30",
            duration_minutes=335,
            distance_km=308.0,
            fare_inr=320.0,
            seat_availability="AVAILABLE",
            tradeoffs="Early morning",
        ),
    ]

    # Test request: Budget <= 1500, Earliest Departure >= 06:00:00, Latest Arrival <= 18:00:00
    request = RecoveryRequest(
        request_id="REQ-TEST-VALIDATION",
        origin="Delhi",
        destination="Jaipur",
        earliest_departure="06:00:00",
        latest_acceptable_arrival="18:00:00",
        max_budget=1500.0,
    )

    valid, rejections = engine.validate_and_filter(alternatives, request)

    # ALT-1 is the only valid alternative:
    # ALT-2 fails budget (> 1500)
    # ALT-3 fails arrival (> 18:00)
    # ALT-4 fails seat availability (SOLD_OUT)
    # ALT-5 fails departure (< 06:00)
    assert len(valid) == 1
    assert valid[0].alternative_id == "ALT-1"
    assert rejections["fare_exceeded_maximum_budget"] == 1
    assert rejections["arrived_after_latest_deadline"] == 1
    assert rejections["seats_sold_out"] == 1
    assert rejections["departed_before_earliest_allowed"] == 1


def test_recovery_engine_scoring_and_ranking():
    """Verify deterministic ranking and configurable scoring weights."""
    engine = RecoveryEngine()

    candidates = [
        # Option A: Fastest, medium price (Train)
        TransportSearchAlternative(
            alternative_id="ALT-FAST",
            rank=1,
            service_id="TRN-VB",
            service_number="20978 Vande Bharat",
            provider="Northern Railway",
            mode="TRAIN",
            origin_code="NDLS",
            origin_name="New Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T06:40:00+05:30",
            arrival_time="2026-10-24T10:35:00+05:30",
            duration_minutes=235,
            distance_km=308.0,
            fare_inr=1150.0,
            seat_availability="AVAILABLE",
            tradeoffs="Fastest executive rail",
        ),
        # Option B: Cheapest, slower (Bus)
        TransportSearchAlternative(
            alternative_id="ALT-CHEAP",
            rank=2,
            service_id="BUS-ZB",
            service_number="Zingbus Electric AC",
            provider="Zingbus",
            mode="BUS",
            origin_code="DEL_ISBT",
            origin_name="Kashmere Gate",
            destination_code="JAI_BUS",
            destination_name="Sindhi Camp",
            departure_time="2026-10-24T07:00:00+05:30",
            arrival_time="2026-10-24T12:00:00+05:30",
            duration_minutes=300,
            distance_km=280.0,
            fare_inr=520.0,
            seat_availability="AVAILABLE",
            tradeoffs="Budget electric coach",
        ),
        # Option C: Moderate speed, higher price (Cab)
        TransportSearchAlternative(
            alternative_id="ALT-CAB",
            rank=3,
            service_id="CAB-EV",
            service_number="BluSmart EV Sedan",
            provider="BluSmart",
            mode="CAB",
            origin_code="NDLS",
            origin_name="New Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T07:15:00+05:30",
            arrival_time="2026-10-24T12:00:00+05:30",
            duration_minutes=285,
            distance_km=280.0,
            fare_inr=3200.0,
            seat_availability="ON_DEMAND",
            tradeoffs="Doorstep private transport",
        ),
    ]

    # Test 1: Standard balanced weights (default: 40% time, 30% cost, 20% rel, 10% trf)
    req_balanced = RecoveryRequest(
        request_id="REQ-BALANCED",
        origin="Delhi",
        destination="Jaipur",
        max_budget=4000.0,
    )
    ranked_balanced = engine.score_and_rank(candidates, req_balanced)
    assert len(ranked_balanced) == 3
    assert ranked_balanced[0].rank == 1
    assert ranked_balanced[1].rank == 2
    assert ranked_balanced[2].rank == 3
    # In balanced evaluation, Vande Bharat achieves highest composite score
    assert ranked_balanced[0].alternative.alternative_id == "ALT-FAST"
    assert ranked_balanced[0].composite_score >= ranked_balanced[1].composite_score

    # Test 2: Custom pure cost priority (0.10 time, 0.70 cost, 0.10 rel, 0.10 trf)
    req_cost_priority = RecoveryRequest(
        request_id="REQ-COST-FIRST",
        origin="Delhi",
        destination="Jaipur",
        max_budget=4000.0,
        weights=ScoringWeights(duration_weight=0.10, cost_weight=0.70, reliability_weight=0.10, transfer_weight=0.10),
    )
    ranked_cost = engine.score_and_rank(candidates, req_cost_priority)
    # Under cost-dominated weighting, the Zingbus (INR 520) must rank #1
    assert ranked_cost[0].alternative.alternative_id == "ALT-CHEAP"
    assert ranked_cost[0].composite_score > ranked_cost[1].composite_score


def test_recovery_engine_explanation_generation():
    """Verify natural language explanation explains #1 choice clearly and contrasts alternatives."""
    engine = RecoveryEngine()

    candidates = [
        TransportSearchAlternative(
            alternative_id="ALT-1",
            rank=1,
            service_id="TRN-VB",
            service_number="20978 Vande Bharat",
            provider="Northern Railway",
            mode="TRAIN",
            origin_code="NDLS",
            origin_name="New Delhi",
            destination_code="JP",
            destination_name="Jaipur",
            departure_time="2026-10-24T06:40:00+05:30",
            arrival_time="2026-10-24T10:35:00+05:30",
            duration_minutes=235,
            distance_km=308.0,
            fare_inr=1150.0,
            seat_availability="AVAILABLE",
            tradeoffs="Fastest transit",
        ),
        TransportSearchAlternative(
            alternative_id="ALT-2",
            rank=2,
            service_id="BUS-ZB",
            service_number="Zingbus Electric AC",
            provider="Zingbus",
            mode="BUS",
            origin_code="DEL_ISBT",
            origin_name="Kashmere Gate",
            destination_code="JAI_BUS",
            destination_name="Sindhi Camp",
            departure_time="2026-10-24T07:00:00+05:30",
            arrival_time="2026-10-24T12:00:00+05:30",
            duration_minutes=300,
            distance_km=280.0,
            fare_inr=520.0,
            seat_availability="AVAILABLE",
            tradeoffs="Cheapest",
        ),
    ]

    req = RecoveryRequest(request_id="REQ-EXP", origin="Delhi", destination="Jaipur", max_budget=2000.0)
    ranked = engine.score_and_rank(candidates, req)
    explanation = engine.generate_best_option_explanation(ranked, req, {}, len(candidates))

    assert "Option #1 (TRAIN: Northern Railway - 20978 Vande Bharat)" in explanation
    assert "was selected as the highest-ranked recovery journey" in explanation
    assert "Option #2 (BUS - Zingbus)" in explanation


# ==============================================================================
# 2. MULTI-AGENT INTEGRATION TESTS: GENUINE uAGENTS MESSAGING
# ==============================================================================

def test_full_recovery_planner_multi_agent_coordination(test_db: DatabaseManager):
    """
    Full 5-agent uAgents integration test:
    - Starts Rail Agent, Bus Agent, Cab Agent, Recovery Planner Agent, and Client Agent in a Bureau.
    - Client sends RecoveryRequest to Recovery Planner Agent.
    - Planner sends TransportSearchQuery to Rail, Bus, and Cab agents asynchronously.
    - Modal agents respond to Planner with TransportSearchResult.
    - Planner correlates, validates constraints, ranks, synthesizes explanation, and replies with RecoveryResponse.
    - Client receives and asserts valid top 3 alternatives and rationale.
    """
    loop = asyncio.new_event_loop()
    port_base = 8600

    rail_agent = create_rail_agent(db=test_db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=test_db, port=port_base + 2, loop=loop)
    cab_agent = create_cab_agent(db=test_db, port=port_base + 3, loop=loop)

    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=cab_agent.address,
        port=port_base + 4,
        loop=loop,
    )

    client_agent = Agent(
        name="test_passenger_client",
        seed="test_passenger_seed_8605",
        port=port_base + 5,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_response: List[RecoveryResponse] = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_recovery_response(ctx: Context, sender: str, msg: RecoveryResponse):
        received_response.append(msg)

    @client_agent.on_event("startup")
    async def dispatch_recovery_request(ctx: Context):
        await ctx.send(
            planner_agent.address,
            RecoveryRequest(
                request_id="REQ-RECOVERY-FULL-01",
                origin="Delhi",
                destination="Jaipur",
                max_budget=2500.0,
                earliest_departure="06:00:00",
                latest_acceptable_arrival="22:00:00",
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start_time = time.time()
        while not received_response and (time.time() - start_time) < 12.0:
            time.sleep(0.2)

    assert len(received_response) == 1, "Client did not receive RecoveryResponse within timeout"
    resp = received_response[0]

    # Verify Response Metadata
    assert resp.request_id == "REQ-RECOVERY-FULL-01"
    assert resp.success is True
    assert resp.origin == "Delhi"
    assert resp.destination == "Jaipur"
    assert resp.planner_address == planner_agent.address
    assert resp.total_options_evaluated > 0
    assert resp.valid_options_count > 0

    # Verify All 3 Modal Agents Responded Successfully
    assert "TRAIN" in resp.modal_responses
    assert "BUS" in resp.modal_responses
    assert "CAB" in resp.modal_responses
    assert resp.modal_responses["TRAIN"]["status"] == "SUCCESS"
    assert resp.modal_responses["BUS"]["status"] == "SUCCESS"
    assert resp.modal_responses["CAB"]["status"] == "SUCCESS"

    # Verify Top 3 Ranked Recovery Options
    assert len(resp.top_3_options) == 3
    assert resp.top_3_options[0].rank == 1
    assert resp.top_3_options[1].rank == 2
    assert resp.top_3_options[2].rank == 3
    assert resp.top_3_options[0].composite_score >= resp.top_3_options[1].composite_score
    assert resp.top_3_options[1].composite_score >= resp.top_3_options[2].composite_score

    # Verify Hard Constraints on Recommended Options
    for option in resp.top_3_options:
        alt = option.alternative
        assert alt.fare_inr <= 2500.0
        assert alt.seat_availability != "SOLD_OUT"
        assert alt.departure_time
        assert alt.arrival_time
        assert option.composite_score > 0
        assert option.selection_reason

    # Verify Natural Language Explanation
    assert resp.best_option_explanation
    assert resp.top_3_options[0].alternative.provider in resp.best_option_explanation
    assert "Option #1" in resp.best_option_explanation


def test_recovery_planner_strict_constraint_filtering(test_db: DatabaseManager):
    """Verify Recovery Planner rejects options violating tight user constraints over uAgents messaging."""
    loop = asyncio.new_event_loop()
    port_base = 8700

    rail_agent = create_rail_agent(db=test_db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=test_db, port=port_base + 2, loop=loop)
    cab_agent = create_cab_agent(db=test_db, port=port_base + 3, loop=loop)

    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=cab_agent.address,
        port=port_base + 4,
        loop=loop,
    )

    client_agent = Agent(
        name="test_strict_client",
        seed="test_strict_seed_8705",
        port=port_base + 5,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_response: List[RecoveryResponse] = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_recovery_response(ctx: Context, sender: str, msg: RecoveryResponse):
        received_response.append(msg)

    @client_agent.on_event("startup")
    async def dispatch_strict_recovery(ctx: Context):
        # Strict constraints: Budget <= INR 600, Latest Arrival <= 14:00:00
        await ctx.send(
            planner_agent.address,
            RecoveryRequest(
                request_id="REQ-RECOVERY-STRICT-02",
                origin="Delhi",
                destination="Jaipur",
                max_budget=600.0,
                earliest_departure="05:00:00",
                latest_acceptable_arrival="14:00:00",
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start_time = time.time()
        while not received_response and (time.time() - start_time) < 12.0:
            time.sleep(0.2)

    assert len(received_response) == 1
    resp = received_response[0]

    assert resp.success is True
    assert resp.rejected_options_count > 0
    # Every returned alternative must strictly respect the INR 600 ceiling
    for option in resp.top_3_options:
        assert option.alternative.fare_inr <= 600.0


def test_recovery_planner_offline_agent_resilience(test_db: DatabaseManager):
    """Verify Recovery Planner gracefully handles an unresponsive/offline modal agent with timeouts."""
    loop = asyncio.new_event_loop()
    port_base = 8800

    rail_agent = create_rail_agent(db=test_db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=test_db, port=port_base + 2, loop=loop)
    # Intentionally point cab agent to a dummy non-existent address
    dummy_offline_cab_address = "agent1qdummyoffline0000000000000000000000000000000000000000000"

    # Set timeout to 1.5s for fast test execution
    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=dummy_offline_cab_address,
        port=port_base + 3,
        loop=loop,
        timeout_seconds=1.5,
    )

    client_agent = Agent(
        name="test_resilience_client",
        seed="test_resilience_seed_8804",
        port=port_base + 4,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_response: List[RecoveryResponse] = []

    @client_agent.on_message(model=RecoveryResponse)
    async def on_recovery_response(ctx: Context, sender: str, msg: RecoveryResponse):
        received_response.append(msg)

    @client_agent.on_event("startup")
    async def dispatch_request(ctx: Context):
        await ctx.send(
            planner_agent.address,
            RecoveryRequest(
                request_id="REQ-RECOVERY-TIMEOUT-03",
                origin="Delhi",
                destination="Jaipur",
                max_budget=1500.0,
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start_time = time.time()
        while not received_response and (time.time() - start_time) < 10.0:
            time.sleep(0.2)

    assert len(received_response) == 1
    resp = received_response[0]

    # Verify the planner handled the offline cab agent without crashing
    assert resp.success is True
    assert "CAB" in resp.modal_responses
    assert resp.modal_responses["CAB"]["status"] == "FAILED"
    assert "timed out" in resp.modal_responses["CAB"]["error_message"].lower()

    # Verify that Rail and Bus results were still combined and ranked
    assert resp.modal_responses["TRAIN"]["status"] == "SUCCESS"
    assert resp.modal_responses["BUS"]["status"] == "SUCCESS"
    assert len(resp.top_3_options) > 0
    assert resp.best_option_explanation
