"""Comprehensive tests for Phase 5: Intelligent Multimodal Route Optimization.

Verifies:
1. Cheapest route selection (prioritizing budget and affordability).
2. Fastest route selection (prioritizing rapid transit time).
3. Overnight journey handling (crossing midnight, duration accuracy).
4. Impossible connection rejection (enforcing minimum transfer buffers: 20m same-hub, 40m inter-terminal).
5. Insufficient budget enforcement (rejection when budget is lower than any available option).
6. No available alternatives handling (graceful fallback and constraint explanation).
7. Multimodal journey recovery via genuine uAgents multi-agent coordination.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta
import threading
import time
from typing import List

import pytest
from uagents import Agent, Bureau, Context

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.rail_agent import create_rail_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from config.settings import IST
from data.database import DatabaseManager
from schemas.agent_messages import (
    RecoveryRequest,
    RecoveryResponse,
    ScoringWeights,
    TransportSearchAlternative,
)
from services.multimodal_router import (
    JourneyLeg,
    MultimodalItinerary,
    MultimodalRouter,
    TransferPoint,
)
from services.recovery_engine import RecoveryEngine


@contextmanager
def running_bureau(bureau: Bureau, loop: asyncio.AbstractEventLoop):
    """Context manager to run a Bureau in a background daemon thread and cleanly shut it down."""
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
# 1. CHEAPEST ROUTE SELECTION
# ==============================================================================

def test_cheapest_route_selection():
    """Verify that when cost weight dominates, the router prioritizes the most economical alternative."""
    db = DatabaseManager()
    router = MultimodalRouter(db=db)

    # Search Delhi -> Jaipur with high cost sensitivity
    cost_weighted = ScoringWeights(
        cost_weight=0.8,
        duration_weight=0.1,
        reliability_weight=0.05,
        transfer_weight=0.05,
    )
    engine = RecoveryEngine(default_weights=cost_weighted, multimodal_router=router)

    request = RecoveryRequest(
        request_id="REQ-CHEAPEST-TEST",
        origin="Delhi",
        destination="Jaipur",
        weights=cost_weighted,
        max_transfers=1,
    )

    # Empty modal_results to trigger router route discovery
    response = engine.process_recovery(
        modal_results={},
        request=request,
        planner_address="test_planner",
    )

    assert response.success is True
    assert len(response.top_3_options) > 0

    best = response.top_3_options[0]
    # The best option should be an economical train or bus (< 600 INR)
    assert best.alternative.fare_inr <= 600.0
    assert best.score_breakdown["cost_score"] >= 80.0
    assert "cost-effective" in response.best_option_explanation.lower() or "fare" in response.best_option_explanation.lower()


# ==============================================================================
# 2. FASTEST ROUTE SELECTION
# ==============================================================================

def test_fastest_route_selection():
    """Verify that when duration weight dominates, the router selects the quickest transit option."""
    db = DatabaseManager()
    router = MultimodalRouter(db=db)

    speed_weighted = ScoringWeights(
        duration_weight=0.8,
        cost_weight=0.1,
        reliability_weight=0.05,
        transfer_weight=0.05,
    )
    engine = RecoveryEngine(default_weights=speed_weighted, multimodal_router=router)

    request = RecoveryRequest(
        request_id="REQ-FASTEST-TEST",
        origin="Delhi",
        destination="Jaipur",
        weights=speed_weighted,
        max_transfers=1,
    )

    response = engine.process_recovery(
        modal_results={},
        request=request,
        planner_address="test_planner",
    )

    assert response.success is True
    assert len(response.top_3_options) > 0

    best = response.top_3_options[0]
    # The quickest service between Delhi and Jaipur is Vande Bharat (~235 mins)
    assert best.alternative.duration_minutes <= 260
    assert best.score_breakdown["duration_score"] >= 80.0
    assert "rapid transit duration" in response.best_option_explanation.lower()


# ==============================================================================
# 3. OVERNIGHT JOURNEY HANDLING
# ==============================================================================

def test_overnight_journey_handling():
    """Verify overnight journeys crossing midnight are identified and calculate duration correctly."""
    db = DatabaseManager()
    router = MultimodalRouter(db=db)

    # Search Chandigarh -> Jaipur (known overnight corridor: TRN-14660, Zingbus sleeper)
    routes = router.find_routes(
        origin="Chandigarh",
        destination="Jaipur",
        max_transfers=0,
    )

    overnight_routes = [r for r in routes if r.is_overnight]
    assert len(overnight_routes) > 0

    sample = overnight_routes[0]
    assert sample.arrival_time.date() > sample.departure_time.date()

    # Verify duration matches actual difference
    expected_duration = int((sample.arrival_time - sample.departure_time).total_seconds() // 60)
    assert sample.total_duration_minutes == expected_duration
    assert sample.total_duration_minutes > 480  # > 8 hours for CDG -> JP overnight


# ==============================================================================
# 4. IMPOSSIBLE CONNECTION REJECTION
# ==============================================================================

def test_impossible_connection_rejection():
    """Verify strict rejection of impossible transfers: insufficient buffers or excessive layovers."""
    base_time = datetime.now(IST).replace(hour=8, minute=0, second=0, microsecond=0)

    # Leg 1: Arrives at NDLS at 10:00
    leg1 = JourneyLeg(
        leg_index=1,
        service_id="LEG-1",
        service_number="Express 1",
        provider="IRCTC",
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

    # Case A: Same hub, but layover is 10 min (< 20 min required buffer) -> REJECT
    leg2_same_hub_too_fast = JourneyLeg(
        leg_index=2,
        service_id="LEG-2A",
        service_number="Express 2A",
        provider="IRCTC",
        mode="TRAIN",
        origin_code="NDLS",
        origin_name="New Delhi",
        origin_city="Delhi",
        destination_code="JP",
        destination_name="Jaipur",
        destination_city="Jaipur",
        departure_time=base_time + timedelta(hours=2, minutes=10),  # 10:10 (10 min layover)
        arrival_time=base_time + timedelta(hours=6),
        duration_minutes=230,
        distance_km=300.0,
        fare_inr=500.0,
        seat_availability="AVAILABLE",
    )

    feasible, layover, reason = MultimodalRouter.is_transfer_feasible(leg1, leg2_same_hub_too_fast)
    assert feasible is False
    assert layover == 10
    assert "impossible connection" in reason.lower()

    # Case B: Inter-terminal (NDLS to DEL_ISBT in Delhi), layover is 25 min (< 40 min buffer) -> REJECT
    leg2_inter_terminal_too_fast = JourneyLeg(
        leg_index=2,
        service_id="LEG-2B",
        service_number="Volvo 2B",
        provider="Zingbus",
        mode="BUS",
        origin_code="DEL_ISBT",
        origin_name="Kashmere Gate ISBT",
        origin_city="Delhi",
        destination_code="JP",
        destination_name="Jaipur",
        destination_city="Jaipur",
        departure_time=base_time + timedelta(hours=2, minutes=25),  # 10:25 (25 min layover)
        arrival_time=base_time + timedelta(hours=7),
        duration_minutes=275,
        distance_km=280.0,
        fare_inr=600.0,
        seat_availability="AVAILABLE",
    )

    feasible, layover, reason = MultimodalRouter.is_transfer_feasible(leg1, leg2_inter_terminal_too_fast)
    assert feasible is False
    assert layover == 25
    assert "less than required inter_terminal buffer" in reason.lower()

    # Case C: Excessive layover (> 360 min) -> REJECT
    leg2_excessive = JourneyLeg(
        leg_index=2,
        service_id="LEG-2C",
        service_number="Express 2C",
        provider="IRCTC",
        mode="TRAIN",
        origin_code="NDLS",
        origin_name="New Delhi",
        origin_city="Delhi",
        destination_code="JP",
        destination_name="Jaipur",
        destination_city="Jaipur",
        departure_time=base_time + timedelta(hours=9),  # 17:00 (7 hours layover = 420 min)
        arrival_time=base_time + timedelta(hours=14),
        duration_minutes=300,
        distance_km=300.0,
        fare_inr=500.0,
        seat_availability="AVAILABLE",
    )

    feasible, layover, reason = MultimodalRouter.is_transfer_feasible(leg1, leg2_excessive)
    assert feasible is False
    assert "excessive layover" in reason.lower()

    # Case D: Valid same hub transfer (30 min layover >= 20 min) -> ACCEPT
    leg2_valid = JourneyLeg(
        leg_index=2,
        service_id="LEG-2D",
        service_number="Express 2D",
        provider="IRCTC",
        mode="TRAIN",
        origin_code="NDLS",
        origin_name="New Delhi",
        origin_city="Delhi",
        destination_code="JP",
        destination_name="Jaipur",
        destination_city="Jaipur",
        departure_time=base_time + timedelta(hours=2, minutes=30),  # 10:30 (30 min layover)
        arrival_time=base_time + timedelta(hours=6, minutes=30),
        duration_minutes=240,
        distance_km=300.0,
        fare_inr=500.0,
        seat_availability="AVAILABLE",
    )

    feasible, layover, reason = MultimodalRouter.is_transfer_feasible(leg1, leg2_valid)
    assert feasible is True
    assert layover == 30
    assert "feasible" in reason.lower()


# ==============================================================================
# 5. INSUFFICIENT BUDGET ENFORCEMENT
# ==============================================================================

def test_insufficient_budget_enforcement():
    """Verify that an unrealistically low budget strictly returns empty options and clear rejection reasons."""
    db = DatabaseManager()
    router = MultimodalRouter(db=db)
    engine = RecoveryEngine(multimodal_router=router)

    request = RecoveryRequest(
        request_id="REQ-LOW-BUDGET",
        origin="Delhi",
        destination="Jaipur",
        max_budget=50.0,  # Below any bus, train, or cab
        max_transfers=1,
    )

    response = engine.process_recovery(
        modal_results={},
        request=request,
        planner_address="test_planner",
    )

    assert response.success is True
    assert response.valid_options_count == 0
    assert len(response.top_3_options) == 0
    assert response.rejection_reasons.get("fare_exceeded_maximum_budget", 0) > 0
    assert "under inr 50" in response.best_option_explanation.lower()


# ==============================================================================
# 6. NO AVAILABLE ALTERNATIVES HANDLING
# ==============================================================================

def test_no_available_alternatives_graceful_handling():
    """Verify graceful error reporting when no routes can satisfy extreme or impossible constraints."""
    db = DatabaseManager()
    router = MultimodalRouter(db=db)
    engine = RecoveryEngine(multimodal_router=router)

    # Impossible deadline (departure >= 23:00, arrival <= 02:00 next day - only 3 hours for 300km)
    request = RecoveryRequest(
        request_id="REQ-NO-ALT",
        origin="Delhi",
        destination="Jaipur",
        earliest_departure="23:30:00",
        latest_acceptable_arrival="01:00:00",
        max_budget=2000.0,
        max_transfers=1,
    )

    response = engine.process_recovery(
        modal_results={},
        request=request,
        planner_address="test_planner",
    )

    assert response.success is True
    assert response.valid_options_count == 0
    assert len(response.top_3_options) == 0
    assert "could satisfy all user constraints" in response.best_option_explanation


# ==============================================================================
# 7. MULTIMODAL MULTI-AGENT RECOVERY COORDINATION TEST
# ==============================================================================

def test_multimodal_multi_agent_coordination():
    """Genuine uAgents multi-agent integration test verifying multimodal journey recovery:
    Client Agent -> Recovery Planner -> Rail, Bus, Cab Agents -> Recovery Planner -> Client Agent.
    """
    loop = asyncio.new_event_loop()

    # Initialize independent Bureau
    bureau = Bureau(port=8050, loop=loop)

    # Create modal agents with dedicated ports
    rail_agent = create_rail_agent(port=8051, loop=loop)
    bus_agent = create_bus_agent(port=8052, loop=loop)
    cab_agent = create_cab_agent(port=8053, loop=loop)

    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=cab_agent.address,
        port=8054,
        loop=loop,
        timeout_seconds=4.0,
    )

    client_agent = Agent(name="test_multimodal_client", seed="test_multimodal_client_seed", port=8055, loop=loop)
    client_agent._mark_inactive_on_shutdown = False
    client_agent._shutdown_timeout = 1.0

    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    received_response: List[RecoveryResponse] = []
    response_event = threading.Event()

    @client_agent.on_event("startup")
    async def request_multimodal_recovery(ctx: Context):
        req = RecoveryRequest(
            request_id="REQ-MULTI-COORDINATION",
            origin="Delhi",
            destination="Jaipur",
            max_budget=1500.0,
            max_transfers=1,
        )
        await ctx.send(planner_agent.address, req)

    @client_agent.on_message(model=RecoveryResponse)
    async def handle_recovery_response(ctx: Context, sender: str, msg: RecoveryResponse):
        received_response.append(msg)
        response_event.set()

    with running_bureau(bureau, loop):
        got_reply = response_event.wait(timeout=10.0)

    assert got_reply is True, "Client did not receive RecoveryResponse within timeout"
    assert len(received_response) == 1

    resp = received_response[0]
    assert resp.success is True
    assert resp.origin == "Delhi"
    assert resp.destination == "Jaipur"
    assert len(resp.top_3_options) > 0
    assert resp.valid_options_count > 0

    # Verify structured fields on recommended alternatives
    top_opt = resp.top_3_options[0].alternative
    assert top_opt.fare_inr <= 1500.0
    assert top_opt.transfers_count <= 1
    assert top_opt.journey_pattern != ""
    assert resp.best_option_explanation != ""
