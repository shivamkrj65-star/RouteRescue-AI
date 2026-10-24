"""Disruption Monitor Agent powered by Fetch.ai uAgents.

Autonomous agent monitoring active passenger journeys in SQLite:
1. Queries SimulatedBookingProvider for live status updates (Confirmed, RAC, Waitlisted, Delayed, Cancelled, Dropped).
2. Periodically scans active bookings using APScheduler (accelerated in demo mode).
3. Detects meaningful operational status changes via DisruptionEvaluator.
4. Automatically triggers the Recovery Planner Agent when a cancellation, qualifying delay, or chart-prepared drop occurs.
5. Deduplicates recovery triggers to prevent redundant recovery workflows for the same disruption.
6. Records all status transitions and automated recovery actions to SQLite audit logs.
"""

import asyncio
import time
from typing import List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from uagents import Agent, Context, Protocol
from uagents.crypto import Identity

from config.settings import settings
from data.database import DatabaseManager
from schemas.agent_messages import (
    DisruptionInjectionRequest,
    RecoveryRequest,
    RecoveryResponse,
)
from schemas.common import BookingStatus
from services.booking_provider import SimulatedBookingProvider, SimulatedBookingStatus
from services.disruption_evaluator import DisruptionEvaluator


def get_default_agent_address(seed: str) -> str:
    """Derive deterministic cryptographic address for an agent seed."""
    return Identity.from_seed(seed, 0).address


def create_disruption_monitor_agent(
    planner_agent_address: Optional[str] = None,
    db: Optional[DatabaseManager] = None,
    provider: Optional[SimulatedBookingProvider] = None,
    evaluator: Optional[DisruptionEvaluator] = None,
    port: Optional[int] = None,
    endpoint: Optional[str] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
    poll_interval_seconds: Optional[float] = None,
    delay_threshold_minutes: Optional[int] = None,
    demo_mode: bool = True,
) -> Agent:
    """Factory creating an autonomous Disruption Monitor Agent instance."""
    agent_port = port or settings.monitor_agent.port
    agent_endpoint = endpoint or settings.monitor_agent.endpoint
    database = db or DatabaseManager()
    booking_provider = provider or SimulatedBookingProvider()
    threshold = delay_threshold_minutes or settings.qualifying_delay_threshold_minutes
    disruption_evaluator = evaluator or DisruptionEvaluator(default_delay_threshold_minutes=threshold)

    planner_address = planner_agent_address or get_default_agent_address(settings.planner_agent.seed)

    # Use accelerated demo polling interval if demo_mode is True
    interval_sec = poll_interval_seconds or (
        settings.monitor_demo_poll_interval_seconds if demo_mode else settings.monitor_poll_interval_seconds
    )

    monitor_agent = Agent(
        name=settings.monitor_agent.name,
        seed=settings.monitor_agent.seed,
        port=agent_port,
        endpoint=[agent_endpoint] if agent_endpoint else None,
        loop=loop,
    )

    monitor_agent._mark_inactive_on_shutdown = False
    monitor_agent._shutdown_timeout = 1.0

    # APScheduler running on the agent's asyncio event loop
    scheduler = AsyncIOScheduler(event_loop=loop)
    active_ctx: List[Optional[Context]] = [None]
    latest_recovery_plans: List[RecoveryResponse] = []

    monitor_protocol = Protocol(name="DisruptionMonitorProtocol", version="1.0.0")

    async def scan_and_evaluate_journeys(ctx: Context) -> int:
        """Scan active passenger journeys and trigger automated recovery for qualifying disruptions."""
        agent_name = getattr(ctx.agent, "name", "disruption_monitor_agent") if hasattr(ctx, "agent") else "disruption_monitor_agent"
        journeys = database.list_all_user_journeys()
        triggered_count = 0

        for journey in journeys:
            current_sim: SimulatedBookingStatus = booking_provider.get_status(journey)
            old_status: BookingStatus = journey.booking_status

            is_meaningful, triggers_recovery, reason = disruption_evaluator.evaluate_status_change(
                old_status=old_status,
                new_status=current_sim,
                delay_threshold_minutes=threshold,
            )

            if is_meaningful:
                old_val = old_status.value if hasattr(old_status, "value") else str(old_status)
                new_val = current_sim.status.value if hasattr(current_sim.status, "value") else str(current_sim.status)

                # Update SQLite database
                database.update_journey_status(journey.journey_id, new_val)
                database.log_monitoring_event(
                    event_type="BOOKING_STATUS_CHANGED",
                    details={
                        "journey_id": journey.journey_id,
                        "passenger": journey.passenger_name,
                        "old_status": old_val,
                        "new_status": new_val,
                        "pnr_position": current_sim.pnr_position,
                        "delay_minutes": current_sim.delay_minutes,
                        "reason": current_sim.reason,
                        "evaluation_code": reason,
                    },
                )
                ctx.logger.info(
                    f"[MONITOR] Status change on {journey.journey_id} ({journey.passenger_name}): "
                    f"{old_val} -> {new_val} [{reason}]"
                )

            if triggers_recovery:
                # Requirement 6: Prevent duplicate recovery requests for the same disruption event
                if disruption_evaluator.is_duplicate(journey.journey_id, reason):
                    ctx.logger.info(
                        f"[MONITOR] Suppressing duplicate recovery trigger for {journey.journey_id} ({reason})"
                    )
                    database.log_monitoring_event(
                        event_type="DUPLICATE_TRIGGER_SUPPRESSED",
                        details={
                            "journey_id": journey.journey_id,
                            "reason": reason,
                        },
                    )
                    continue

                # Mark as triggered in deduplication ledger
                disruption_evaluator.mark_triggered(journey.journey_id, reason)

                # Requirement 5 & 10: Automatically trigger the Recovery Planner via uAgents messaging
                req_id = f"REC-AUTO-{journey.journey_id}-{int(time.time() * 1000)}"
                budget_ceiling = round(journey.booked_fare_inr * 1.5, 2)

                recovery_query = RecoveryRequest(
                    request_id=req_id,
                    origin=journey.booked_service.origin.city,
                    destination=journey.booked_service.destination.city,
                    journey_date=journey.booked_service.departure_time.date().isoformat(),
                    earliest_departure=journey.booked_service.departure_time.time().isoformat(),
                    latest_acceptable_arrival=None,
                    max_budget=budget_ceiling,
                    max_transfers=1,
                    user_id=journey.passenger_email,
                    disrupted_service_id=journey.booked_service.service_id,
                )

                ctx.logger.info(
                    f"[MONITOR] Automatically triggering Recovery Planner for {journey.journey_id} "
                    f"via uAgents messaging to {planner_address} (Reason: {reason})"
                )

                await ctx.send(planner_address, recovery_query)
                triggered_count += 1

                database.log_monitoring_event(
                    event_type="AUTOMATIC_RECOVERY_TRIGGERED",
                    details={
                        "journey_id": journey.journey_id,
                        "passenger": journey.passenger_name,
                        "request_id": req_id,
                        "trigger_reason": reason,
                        "disrupted_service": journey.booked_service.service_id,
                        "planner_address": planner_address,
                        "max_budget": budget_ceiling,
                    },
                )

        return triggered_count

    @monitor_agent.on_event("startup")
    async def on_startup(ctx: Context):
        active_ctx[0] = ctx
        ctx.logger.info(
            f"[MONITOR] Disruption Monitor Agent active. Initializing APScheduler "
            f"(Interval: {interval_sec}s, Demo mode: {demo_mode}, Delay threshold: {threshold}m)"
        )

        async def scheduled_tick():
            if active_ctx[0]:
                await scan_and_evaluate_journeys(active_ctx[0])

        scheduler.add_job(scheduled_tick, "interval", seconds=interval_sec, id="monitor_scan_job")
        scheduler.start()

    @monitor_agent.on_event("shutdown")
    async def on_shutdown(ctx: Context):
        ctx.logger.info("[MONITOR] Shutting down Disruption Monitor Agent scheduler...")
        if scheduler.running:
            scheduler.shutdown(wait=False)

    @monitor_protocol.on_message(model=RecoveryResponse)
    async def on_recovery_response(ctx: Context, sender: str, msg: RecoveryResponse):
        """Receives recovery plan synthesized by Recovery Planner Agent."""
        ctx.logger.info(
            f"[MONITOR] Received RecoveryResponse from {sender} for {msg.request_id}: "
            f"{len(msg.top_3_options)} recovery options found (Valid: {msg.valid_options_count})"
        )
        latest_recovery_plans.append(msg)

        database.log_monitoring_event(
            event_type="RECOVERY_PLAN_ACKNOWLEDGED",
            details={
                "request_id": msg.request_id,
                "planner_address": sender,
                "top_options_count": len(msg.top_3_options),
                "best_option_explanation": msg.best_option_explanation,
            },
        )

    @monitor_protocol.on_message(model=DisruptionInjectionRequest)
    async def on_disruption_injection(ctx: Context, sender: str, msg: DisruptionInjectionRequest):
        """Allows injecting demonstration disruptions via uAgents messaging."""
        ctx.logger.info(
            f"[MONITOR] Received DisruptionInjectionRequest from {sender} for journey {msg.journey_id}: "
            f"new status={msg.status}, delay={msg.delay_minutes}m, reason='{msg.reason}'"
        )
        booking_provider.inject_disruption(msg)
        # Immediately trigger evaluation tick
        await scan_and_evaluate_journeys(ctx)

    monitor_agent.include(monitor_protocol)

    # Attach helper references for testing and API integration
    monitor_agent.provider = booking_provider
    monitor_agent.evaluator = disruption_evaluator
    monitor_agent.scheduler = scheduler
    monitor_agent.scan_now = lambda: scan_and_evaluate_journeys(active_ctx[0]) if active_ctx[0] else None
    monitor_agent.latest_recovery_plans = latest_recovery_plans

    return monitor_agent
