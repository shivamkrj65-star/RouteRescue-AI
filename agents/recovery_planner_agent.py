"""Recovery Planner Agent powered by Fetch.ai uAgents.

Coordinates multimodal recovery during travel disruptions:
1. Receives RecoveryRequest from users, coordinators, or disruption monitors.
2. Dispatches asynchronous TransportSearchQuery messages to Rail, Bus, and Cab agents.
3. Collects responses asynchronously and correlates them by request_id.
4. Handles agent response timeouts and offline agents gracefully.
5. Employs RecoveryEngine to enforce hard constraints and compute deterministic multi-criteria rankings.
6. Returns the top 3 recommended recovery alternatives and natural language rationale via RecoveryResponse.
"""

import asyncio
import time
from typing import Dict, Optional
from uagents import Agent, Context, Protocol
from uagents.crypto import Identity

from config.settings import settings
from schemas.agent_messages import (
    RecoveryRequest,
    RecoveryResponse,
    TransportSearchQuery,
    TransportSearchResult,
)
from services.recovery_engine import RecoveryEngine


def get_default_agent_address(seed: str) -> str:
    """Derive deterministic cryptographic address for an agent seed."""
    return Identity.from_seed(seed, 0).address


def create_recovery_planner_agent(
    rail_agent_address: Optional[str] = None,
    bus_agent_address: Optional[str] = None,
    cab_agent_address: Optional[str] = None,
    port: Optional[int] = None,
    endpoint: Optional[str] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
    timeout_seconds: Optional[float] = None,
    engine: Optional[RecoveryEngine] = None,
) -> Agent:
    """Factory creating an independent Recovery Planner Agent instance."""
    agent_port = port or settings.planner_agent.port
    agent_endpoint = endpoint or settings.planner_agent.endpoint
    default_timeout = timeout_seconds or settings.agent_message_timeout_seconds
    recovery_engine = engine or RecoveryEngine()

    rail_address = rail_agent_address or get_default_agent_address(settings.rail_agent.seed)
    bus_address = bus_agent_address or get_default_agent_address(settings.bus_agent.seed)
    cab_address = cab_agent_address or get_default_agent_address(settings.cab_agent.seed)

    planner_agent = Agent(
        name=settings.planner_agent.name,
        seed=settings.planner_agent.seed,
        port=agent_port,
        endpoint=[agent_endpoint] if agent_endpoint else None,
        loop=loop,
    )

    # Disable remote Almanac ping delays on shutdown for fast, clean teardown in tests
    planner_agent._mark_inactive_on_shutdown = False
    planner_agent._shutdown_timeout = 1.0

    # In-memory tracking of active recovery requests
    pending_requests: Dict[str, dict] = {}

    planner_protocol = Protocol(name="RecoveryPlannerProtocol", version="1.0.0")

    async def _await_and_respond(ctx: Context, req_id: str, agent_address: str):
        """Background coroutine that gathers modal responses with timeout, ranks, and replies."""
        state = pending_requests.get(req_id)
        if not state:
            return

        timeout_sec = state["timeout_sec"]
        try:
            await asyncio.wait_for(state["event"].wait(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            ctx.logger.warning(
                f"[PLANNER] Timeout waiting for modal agents for {req_id} after {timeout_sec}s. "
                f"Proceeding with {len(state['received'])}/3 modal responses."
            )

        duration_ms = (time.time() - state["start_time"]) * 1000.0
        modal_results: Dict[str, TransportSearchResult] = state["received"]

        # If any modal agent timed out or was offline, record synthetic timeout entry
        expected_modes = [("TRAIN", rail_address), ("BUS", bus_address), ("CAB", cab_address)]
        for mode, addr in expected_modes:
            if mode not in modal_results:
                modal_results[mode] = TransportSearchResult(
                    request_id=f"{req_id}#{mode}",
                    agent_name=f"{mode.lower()}_search_agent",
                    agent_address=addr or "unknown",
                    mode=mode,
                    success=False,
                    total_found=0,
                    results=[],
                    error_message=f"Agent response timed out after {timeout_sec}s or agent offline",
                )

        # Process hard constraint filtering, multi-criteria scoring, and top 3 ranking
        recovery_response = recovery_engine.process_recovery(
            modal_results=modal_results,
            request=state["request"],
            planner_address=agent_address,
            execution_time_ms=round(duration_ms, 2),
        )

        requester = state["requester"]
        ctx.logger.info(
            f"[PLANNER] Sending RecoveryResponse for {req_id} to {requester} "
            f"({len(recovery_response.top_3_options)} top options, valid: {recovery_response.valid_options_count})"
        )
        await ctx.send(requester, recovery_response)
        pending_requests.pop(req_id, None)

    @planner_protocol.on_message(model=RecoveryRequest, replies={RecoveryResponse})
    async def handle_recovery_request(ctx: Context, sender: str, msg: RecoveryRequest):
        agent_name = getattr(ctx.agent, "name", "recovery_planner_agent") if hasattr(ctx, "agent") else "recovery_planner_agent"
        agent_address = getattr(ctx.agent, "address", "") if hasattr(ctx, "agent") else ""

        ctx.logger.info(
            f"[PLANNER] Agent [{agent_name}] received RecoveryRequest {msg.request_id} from {sender} "
            f"for {msg.origin} -> {msg.destination} (Budget: INR {msg.max_budget})"
        )

        req_id = msg.request_id
        state = {
            "request": msg,
            "requester": sender,
            "received": {},
            "event": asyncio.Event(),
            "start_time": time.time(),
            "timeout_sec": default_timeout,
        }
        pending_requests[req_id] = state

        # Dispatch search queries to Rail, Bus, and Cab agents via genuine uAgents messaging
        modal_queries = [
            (rail_address, "TRAIN"),
            (bus_address, "BUS"),
            (cab_address, "CAB"),
        ]
        for target_address, mode in modal_queries:
            if target_address:
                query = TransportSearchQuery(
                    request_id=f"{req_id}#{mode}",
                    origin=msg.origin,
                    destination=msg.destination,
                    travel_date=msg.journey_date,
                    earliest_departure=msg.earliest_departure,
                )
                await ctx.send(target_address, query)
                ctx.logger.info(f"[PLANNER] Dispatched {mode} search query to {target_address}")

        # Spawn asynchronous collector task
        asyncio.create_task(_await_and_respond(ctx, req_id, agent_address))

    @planner_protocol.on_message(model=TransportSearchResult)
    async def handle_modal_result(ctx: Context, sender: str, msg: TransportSearchResult):
        req_id = msg.request_id.split("#")[0]
        state = pending_requests.get(req_id)
        if not state:
            ctx.logger.warning(f"[PLANNER] Received unexpected or late result for {msg.request_id} from {sender}")
            return

        mode = msg.mode or "UNKNOWN"
        state["received"][mode] = msg
        ctx.logger.info(
            f"[PLANNER] Collected {mode} result for {req_id} ({msg.total_found} alternatives) from {sender}"
        )

        # Once all 3 modal agents have responded, wake up collector immediately
        if len(state["received"]) >= 3:
            state["event"].set()

    planner_agent.include(planner_protocol)
    return planner_agent
