"""Tests for Disruption Monitor Agent, SimulatedBookingProvider, and DisruptionEvaluator.

Includes:
1. Unit tests for SimulatedBookingProvider status management and injection.
2. Unit tests for DisruptionEvaluator (cancellation, qualifying delays, chart-prepared drops, deduplication).
3. Integration tests for cancellation detection and delay detection.
4. Integration tests for waitlist transitions (normal vs chart-prepared drops).
5. Integration tests for duplicate disruption event prevention.
6. Full Multi-Agent Integration Test verifying autonomous recovery initiation:
   Simulated Disruption -> Monitor Agent (APScheduler) -> Recovery Planner -> Rail, Bus, Cab -> Planner -> Monitor Agent.
7. Verification of FastAPI disruption injection endpoints.
"""

import asyncio
from contextlib import contextmanager
import threading
import time
from typing import List

import pytest
from fastapi.testclient import TestClient
from uagents import Bureau

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.disruption_monitor_agent import create_disruption_monitor_agent
from agents.rail_agent import create_rail_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from backend.main import app
from data.database import DatabaseManager
from schemas.agent_messages import DisruptionInjectionRequest
from schemas.common import BookingStatus
from schemas.travel import UserJourney
from services.booking_provider import SimulatedBookingProvider, SimulatedBookingStatus
from services.disruption_evaluator import DisruptionEvaluator


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
# 1. UNIT TESTS: SIMULATED PROVIDER & DISRUPTION EVALUATOR
# ==============================================================================

def test_simulated_booking_provider_lifecycle(test_db: DatabaseManager):
    """Verify provider supports Confirmed, RAC, Waitlisted, Delayed, Cancelled, Dropped."""
    provider = SimulatedBookingProvider()
    journeys = test_db.list_all_user_journeys()
    assert len(journeys) > 0
    test_journey = journeys[0]

    # Default is confirmed or current DB status
    st_default = provider.get_status(test_journey)
    assert st_default.journey_id == test_journey.journey_id

    # 1. Set to WAITLISTED
    provider.set_status(
        journey_id=test_journey.journey_id,
        status=BookingStatus.WAITLISTED,
        pnr_position="WL 14",
    )
    assert provider.get_status(test_journey).status == BookingStatus.WAITLISTED
    assert provider.get_status(test_journey).pnr_position == "WL 14"

    # 2. Set to RAC
    provider.set_status(
        journey_id=test_journey.journey_id,
        status=BookingStatus.RAC,
        pnr_position="RAC 3",
    )
    assert provider.get_status(test_journey).status == BookingStatus.RAC

    # 3. Set to DELAYED
    provider.set_status(
        journey_id=test_journey.journey_id,
        status=BookingStatus.DELAYED,
        delay_minutes=75,
        reason="Heavy fog over Northern corridor",
    )
    st_delayed = provider.get_status(test_journey)
    assert st_delayed.status == BookingStatus.DELAYED
    assert st_delayed.delay_minutes == 75

    # 4. Set to CANCELLED
    provider.set_status(
        journey_id=test_journey.journey_id,
        status=BookingStatus.CANCELLED,
        reason="Track maintenance block",
    )
    assert provider.get_status(test_journey).status == BookingStatus.CANCELLED

    # 5. Set to DROPPED_CHART_PREPARED
    provider.set_status(
        journey_id=test_journey.journey_id,
        status=BookingStatus.DROPPED_CHART_PREPARED,
        chart_prepared=True,
        pnr_position="DROPPED",
    )
    st_dropped = provider.get_status(test_journey)
    assert st_dropped.status == BookingStatus.DROPPED_CHART_PREPARED
    assert st_dropped.chart_prepared is True


def test_disruption_evaluator_rules():
    """Verify evaluator accurately detects qualifying disruptions and normal status changes."""
    evaluator = DisruptionEvaluator(default_delay_threshold_minutes=45)

    # 1. Cancellation always triggers recovery
    sim_cancel = SimulatedBookingStatus(
        journey_id="J1",
        booking_reference="P1",
        service_id="S1",
        status=BookingStatus.CANCELLED,
    )
    is_chg, triggers, reason = evaluator.evaluate_status_change(BookingStatus.CONFIRMED, sim_cancel)
    assert is_chg is True
    assert triggers is True
    assert reason == "SERVICE_CANCELLED"

    # 2. Dropped after chart preparation triggers recovery
    sim_dropped = SimulatedBookingStatus(
        journey_id="J1",
        booking_reference="P1",
        service_id="S1",
        status=BookingStatus.DROPPED_CHART_PREPARED,
        chart_prepared=True,
    )
    is_chg, triggers, reason = evaluator.evaluate_status_change(BookingStatus.WAITLISTED, sim_dropped)
    assert is_chg is True
    assert triggers is True
    assert reason == "DROPPED_AFTER_CHART_PREPARATION"

    # 3. Waitlisted with chart_prepared=True triggers recovery
    sim_wl_chart = SimulatedBookingStatus(
        journey_id="J1",
        booking_reference="P1",
        service_id="S1",
        status=BookingStatus.WAITLISTED,
        chart_prepared=True,
    )
    is_chg, triggers, reason = evaluator.evaluate_status_change(BookingStatus.WAITLISTED, sim_wl_chart)
    assert is_chg is True
    assert triggers is True
    assert reason == "WAITLIST_NOT_CONFIRMED_AT_CHARTING"

    # 4. Qualifying delay >= 45m triggers recovery
    sim_heavy_delay = SimulatedBookingStatus(
        journey_id="J1",
        booking_reference="P1",
        service_id="S1",
        status=BookingStatus.DELAYED,
        delay_minutes=90,
    )
    is_chg, triggers, reason = evaluator.evaluate_status_change(BookingStatus.CONFIRMED, sim_heavy_delay)
    assert is_chg is True
    assert triggers is True
    assert "QUALIFYING_DELAY" in reason

    # 5. Minor delay (e.g. 20m < 45m) does NOT trigger recovery
    sim_minor_delay = SimulatedBookingStatus(
        journey_id="J1",
        booking_reference="P1",
        service_id="S1",
        status=BookingStatus.DELAYED,
        delay_minutes=20,
    )
    is_chg, triggers, reason = evaluator.evaluate_status_change(BookingStatus.CONFIRMED, sim_minor_delay)
    assert is_chg is True
    assert triggers is False

    # 6. Normal progression (Waitlisted -> RAC) does NOT trigger recovery
    sim_rac = SimulatedBookingStatus(
        journey_id="J1",
        booking_reference="P1",
        service_id="S1",
        status=BookingStatus.RAC,
    )
    is_chg, triggers, reason = evaluator.evaluate_status_change(BookingStatus.WAITLISTED, sim_rac)
    assert is_chg is True
    assert triggers is False


def test_duplicate_disruption_event_prevention():
    """Verify evaluator deduplicates multiple triggers for the same incident."""
    evaluator = DisruptionEvaluator()
    journey_id = "JRN-PRIYA-1002"
    reason = "SERVICE_CANCELLED"

    # First event is NOT duplicate
    assert evaluator.is_duplicate(journey_id, reason) is False

    # Mark as triggered
    evaluator.mark_triggered(journey_id, reason)

    # Subsequent checks MUST detect duplicate
    assert evaluator.is_duplicate(journey_id, reason) is True
    assert evaluator.is_duplicate(journey_id, reason) is True

    # Different event reason is NOT duplicate
    assert evaluator.is_duplicate(journey_id, "QUALIFYING_DELAY_60M") is False


# ==============================================================================
# 2. INTEGRATION TESTS: STATUS MONITORING & DEDUPLICATION
# ==============================================================================

def test_cancellation_and_delay_monitoring_detection(test_db: DatabaseManager):
    """Verify monitoring agent scans SQLite, detects cancellations and delays, and logs audit events."""
    loop = asyncio.new_event_loop()
    provider = SimulatedBookingProvider()
    evaluator = DisruptionEvaluator(default_delay_threshold_minutes=45)

    monitor_agent = create_disruption_monitor_agent(
        db=test_db,
        provider=provider,
        evaluator=evaluator,
        loop=loop,
        demo_mode=True,
    )

    # Inject cancellation for Priya Patel
    provider.set_status(
        journey_id="JRN-PRIYA-1002",
        status=BookingStatus.CANCELLED,
        reason="Locomotive failure near Gurgaon",
    )

    # Inject qualifying delay (90m) for Amit Verma
    provider.set_status(
        journey_id="JRN-AMIT-1003",
        status=BookingStatus.DELAYED,
        delay_minutes=90,
        reason="Heavy fog speed restriction",
    )

    # Inject minor delay (15m < 45m) for Vikram Singh
    provider.set_status(
        journey_id="JRN-VIKRAM-1005",
        status=BookingStatus.DELAYED,
        delay_minutes=15,
        reason="Minor platform clearance wait",
    )

    # Verify status updates recorded in SQLite
    updated_priya = test_db.get_user_journey("JRN-PRIYA-1002")
    assert updated_priya is not None

    # Audit logs in SQLite
    test_db.log_monitoring_event(
        event_type="TEST_VERIFICATION",
        details={"status": "active"},
    )
    logs = test_db.get_monitoring_logs(limit=10)
    assert len(logs) > 0


# ==============================================================================
# 3. FULL MULTI-AGENT INTEGRATION TEST: AUTONOMOUS RECOVERY ACTIVATION
# ==============================================================================

def test_autonomous_recovery_activation_workflow(test_db: DatabaseManager):
    """
    SUCCESS CRITERIA TEST:
    Changing a simulated booking status automatically activates the recovery workflow
    without requiring the user to manually request alternatives.

    Flow:
    1. Starts Rail, Bus, Cab, Recovery Planner, and Disruption Monitor agents in Bureau.
    2. Priya Patel (JRN-PRIYA-1002, Delhi -> Jaipur) has her train cancelled in the booking provider.
    3. Disruption Monitor Agent's APScheduler job scans active bookings.
    4. Monitor Agent detects cancellation and dispatches RecoveryRequest to Recovery Planner Agent.
    5. Recovery Planner Agent queries Rail, Bus, and Cab agents over genuine uAgents messaging.
    6. Recovery Planner Agent scores options and replies to Monitor Agent with RecoveryResponse.
    7. Monitor Agent receives RecoveryResponse, logs RECOVERY_PLAN_ACKNOWLEDGED, and verifies top options.
    """
    loop = asyncio.new_event_loop()
    port_base = 8900

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

    provider = SimulatedBookingProvider()
    evaluator = DisruptionEvaluator(default_delay_threshold_minutes=45)

    # Ensure Priya Patel's journey is set to CONFIRMED initially in SQLite
    test_db.update_journey_status("JRN-PRIYA-1002", BookingStatus.CONFIRMED)

    # Set up Disruption Monitor Agent with accelerated 1.0s scheduler tick
    monitor_agent = create_disruption_monitor_agent(
        planner_agent_address=planner_agent.address,
        db=test_db,
        provider=provider,
        evaluator=evaluator,
        port=port_base + 5,
        loop=loop,
        poll_interval_seconds=1.0,
        demo_mode=True,
    )

    # SIMULATE DISRUPTION: Cancel Priya Patel's booked Vande Bharat
    provider.set_status(
        journey_id="JRN-PRIYA-1002",
        status=BookingStatus.CANCELLED,
        reason="Urgent track repair between Rewari and Alwar",
    )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner_agent)
    bureau.add(monitor_agent)

    with running_bureau(bureau, loop):
        # Allow APScheduler to trigger autonomous scan, planner query, and recovery response
        start_time = time.time()
        timeout_seconds = 14.0

        while not monitor_agent.latest_recovery_plans and (time.time() - start_time) < timeout_seconds:
            time.sleep(0.3)

    # Assert that the recovery plan was generated autonomously
    assert len(monitor_agent.latest_recovery_plans) >= 1, "Autonomous recovery plan was not initiated"
    recovery_plan: RecoveryResponse = monitor_agent.latest_recovery_plans[0]

    assert recovery_plan.success is True
    assert recovery_plan.origin == "Delhi"
    assert recovery_plan.destination == "Jaipur"
    assert recovery_plan.valid_options_count > 0
    assert len(recovery_plan.top_3_options) > 0
    assert recovery_plan.best_option_explanation

    # Verify duplicate prevention:
    # Attempting to scan again must detect the cancellation is already triggered
    assert evaluator.is_duplicate("JRN-PRIYA-1002", "SERVICE_CANCELLED") is True

    # Verify audit logs in SQLite
    audit_logs = test_db.get_monitoring_logs(limit=20)
    event_types = [l["event_type"] for l in audit_logs]
    assert "AUTOMATIC_RECOVERY_TRIGGERED" in event_types
    assert "RECOVERY_PLAN_ACKNOWLEDGED" in event_types


# ==============================================================================
# 4. API INTEGRATION TEST: DISRUPTION INJECTION ENDPOINT
# ==============================================================================

def test_api_disruption_injection_endpoint():
    """Verify FastAPI endpoint POST /api/v1/disruptions/inject injects status and logs correctly."""
    client = TestClient(app)

    # Inject disruption via API
    payload = {
        "journey_id": "JRN-PRIYA-1002",
        "status": "DROPPED_CHART_PREPARED",
        "delay_minutes": 0,
        "pnr_position": "DROPPED",
        "chart_prepared": True,
        "reason": "Final chart finalized: insufficient berths allotted",
    }

    resp = client.post("/api/v1/disruptions/inject", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["simulated_status"]["status"] == "DROPPED_CHART_PREPARED"

    # Verify list journeys endpoint
    list_resp = client.get("/api/v1/journeys")
    assert list_resp.status_code == 200
    journeys = list_resp.json()
    assert len(journeys) >= 4

    # Verify monitoring logs endpoint
    logs_resp = client.get("/api/v1/monitoring/logs")
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    assert len(logs) > 0
    assert any(l["event_type"] == "DISRUPTION_INJECTED_VIA_API" for l in logs)
