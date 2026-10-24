"""Integration tests for Fetch.ai uAgents Phase 2 transport search agents.

Tests:
1. Agent identity, cryptographic address generation, and protocol registration.
2. Separation of modal search logic from messaging code.
3. Actual uAgents agent-to-agent message transmission (Request-Response lifecycle).
4. Request ID correlation across multi-agent queries.
5. Filter application (origin, destination, departure time, budget) by autonomous agents.
6. Error handling, timeout handling, and edge case resilience.
"""

import asyncio
from contextlib import contextmanager
import threading
import time
from datetime import datetime, time as dt_time
import pytest
from uagents import Agent, Bureau, Context

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.rail_agent import create_rail_agent
from config.settings import settings
from data.database import DatabaseManager
from schemas.agent_messages import (
    TransportSearchAlternative,
    TransportSearchQuery,
    TransportSearchResult,
)
from services.modal_search import (
    BusSearchService,
    CabRoadSearchService,
    RailSearchService,
)


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


def test_agent_identities_and_addresses(test_db: DatabaseManager):
    """Verify each agent has its own unique name, cryptographic address, and protocols."""
    rail_agent = create_rail_agent(db=test_db)
    bus_agent = create_bus_agent(db=test_db)
    cab_agent = create_cab_agent(db=test_db)

    # Names
    assert rail_agent.name == settings.rail_agent.name
    assert bus_agent.name == settings.bus_agent.name
    assert cab_agent.name == settings.cab_agent.name

    # Bech32 Agent Addresses
    assert rail_agent.address.startswith("agent1")
    assert bus_agent.address.startswith("agent1")
    assert cab_agent.address.startswith("agent1")

    # Distinct addresses
    addresses = {rail_agent.address, bus_agent.address, cab_agent.address}
    assert len(addresses) == 3, "Each agent must possess a unique cryptographic address"


def test_separated_modal_search_services(test_db: DatabaseManager):
    """Verify that modal search services execute cleanly independent of the network layer."""
    rail_svc = RailSearchService(db=test_db)
    bus_svc = BusSearchService(db=test_db)
    cab_svc = CabRoadSearchService(db=test_db)

    # Rail Search
    rail_query = TransportSearchQuery(
        request_id="REQ-TEST-RAIL-01",
        origin="Delhi",
        destination="Jaipur",
        max_budget_inr=1000.0,
    )
    rail_res = rail_svc.search_rail(rail_query, agent_name="test_rail", agent_address="test_addr")
    assert rail_res.success is True
    assert rail_res.mode == "TRAIN"
    assert rail_res.total_found > 0
    for opt in rail_res.results:
        assert opt.fare_inr <= 1000.0
        assert opt.mode == "TRAIN"
        assert "train" in opt.tradeoffs.lower() or "express" in opt.tradeoffs.lower() or "sleeper" in opt.tradeoffs.lower()

    # Bus Search
    bus_query = TransportSearchQuery(
        request_id="REQ-TEST-BUS-01",
        origin="Delhi",
        destination="Jaipur",
        max_budget_inr=600.0,
    )
    bus_res = bus_svc.search_bus(bus_query, agent_name="test_bus", agent_address="test_addr")
    assert bus_res.success is True
    assert bus_res.mode == "BUS"
    assert bus_res.total_found > 0
    for opt in bus_res.results:
        assert opt.fare_inr <= 600.0
        assert opt.mode == "BUS"

    # Cab Search
    cab_query = TransportSearchQuery(
        request_id="REQ-TEST-CAB-01",
        origin="Delhi",
        destination="Agra",
        max_budget_inr=5000.0,
    )
    cab_res = cab_svc.search_cabs(cab_query, agent_name="test_cab", agent_address="test_addr")
    assert cab_res.success is True
    assert cab_res.mode == "CAB"
    assert cab_res.total_found > 0
    for opt in cab_res.results:
        assert opt.fare_inr <= 5000.0
        assert opt.mode == "CAB"


def test_uagents_actual_message_exchange(test_db: DatabaseManager):
    """
    Integration test verifying actual uAgents agent-to-agent messaging:
    - Starts Rail Search Agent, Bus Search Agent, and Cab & Road Agent in a Bureau.
    - Test Client Agent sends TransportSearchQuery to each agent.
    - Verifies asynchronous reception, request ID correlation, and structured results.
    """
    loop = asyncio.new_event_loop()
    port_base = 8200
    rail_agent = create_rail_agent(db=test_db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=test_db, port=port_base + 2, loop=loop)
    cab_agent = create_cab_agent(db=test_db, port=port_base + 3, loop=loop)

    client_agent = Agent(
        name="test_client_coordinator",
        seed="test_coordinator_seed_8204",
        port=port_base + 4,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received_results = {}
    expected_requests = {
        "REQ-RAIL-INTEG-01": "TRAIN",
        "REQ-BUS-INTEG-02": "BUS",
        "REQ-CAB-INTEG-03": "CAB",
    }

    @client_agent.on_message(model=TransportSearchResult)
    async def on_search_result(ctx: Context, sender: str, msg: TransportSearchResult):
        received_results[msg.request_id] = msg

    @client_agent.on_event("startup")
    async def dispatch_queries(ctx: Context):
        # Query Rail Agent
        await ctx.send(
            rail_agent.address,
            TransportSearchQuery(
                request_id="REQ-RAIL-INTEG-01",
                origin="Delhi",
                destination="Jaipur",
                max_budget_inr=1500.0,
            ),
        )
        # Query Bus Agent
        await ctx.send(
            bus_agent.address,
            TransportSearchQuery(
                request_id="REQ-BUS-INTEG-02",
                origin="Delhi",
                destination="Jaipur",
                max_budget_inr=800.0,
            ),
        )
        # Query Cab Agent
        await ctx.send(
            cab_agent.address,
            TransportSearchQuery(
                request_id="REQ-CAB-INTEG-03",
                origin="Delhi",
                destination="Jaipur",
                max_budget_inr=6000.0,
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        # Poll with timeout for all 3 agents to respond via messaging
        timeout_seconds = 10.0
        start_time = time.time()

        while len(received_results) < len(expected_requests) and (time.time() - start_time) < timeout_seconds:
            time.sleep(0.2)

    # Assertions on received messages
    assert len(received_results) == 3, f"Expected 3 responses, received {len(received_results)} within timeout"

    # Verify Rail Agent Response
    rail_resp: TransportSearchResult = received_results["REQ-RAIL-INTEG-01"]
    assert rail_resp.request_id == "REQ-RAIL-INTEG-01"
    assert rail_resp.mode == "TRAIN"
    assert rail_resp.success is True
    assert rail_resp.agent_address == rail_agent.address
    assert rail_resp.total_found > 0
    assert len(rail_resp.results) == rail_resp.total_found

    # Verify Bus Agent Response
    bus_resp: TransportSearchResult = received_results["REQ-BUS-INTEG-02"]
    assert bus_resp.request_id == "REQ-BUS-INTEG-02"
    assert bus_resp.mode == "BUS"
    assert bus_resp.success is True
    assert bus_resp.agent_address == bus_agent.address
    assert bus_resp.total_found > 0

    # Verify Cab Agent Response
    cab_resp: TransportSearchResult = received_results["REQ-CAB-INTEG-03"]
    assert cab_resp.request_id == "REQ-CAB-INTEG-03"
    assert cab_resp.mode == "CAB"
    assert cab_resp.success is True
    assert cab_resp.agent_address == cab_agent.address
    assert cab_resp.total_found > 0

    # Verify Journey Timestamps and Availability
    for r in rail_resp.results + bus_resp.results + cab_resp.results:
        assert r.departure_time
        assert r.arrival_time
        assert r.fare_inr > 0
        assert r.seat_availability in ["AVAILABLE", "FEW_SEATS", "ON_DEMAND", "RAC", "WAITLISTED", "SOLD_OUT"]
        assert r.tradeoffs


def test_uagents_departure_time_and_budget_filters(test_db: DatabaseManager):
    """Test agents respect earliest departure time and budget limits via messaging."""
    loop = asyncio.new_event_loop()
    port_base = 8300
    rail_agent = create_rail_agent(db=test_db, port=port_base + 1, loop=loop)
    bus_agent = create_bus_agent(db=test_db, port=port_base + 2, loop=loop)

    client_agent = Agent(
        name="test_filter_client",
        seed="test_filter_seed_8303",
        port=port_base + 3,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received = {}

    @client_agent.on_message(model=TransportSearchResult)
    async def on_result(ctx: Context, sender: str, msg: TransportSearchResult):
        received[msg.request_id] = msg

    @client_agent.on_event("startup")
    async def send_queries(ctx: Context):
        # Query trains departing >= 17:00
        await ctx.send(
            rail_agent.address,
            TransportSearchQuery(
                request_id="REQ-FILTER-TIME",
                origin="Delhi",
                destination="Jaipur",
                earliest_departure="17:00:00",
            ),
        )
        # Query bus with tight budget limit of INR 550
        await ctx.send(
            bus_agent.address,
            TransportSearchQuery(
                request_id="REQ-FILTER-BUDGET",
                origin="Delhi",
                destination="Jaipur",
                max_budget_inr=550.0,
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start_time = time.time()
        while len(received) < 2 and (time.time() - start_time) < 10.0:
            time.sleep(0.2)

    assert len(received) == 2

    # Verify time filter on Rail
    rail_resp = received["REQ-FILTER-TIME"]
    assert rail_resp.total_found > 0
    for alt in rail_resp.results:
        dep_time = datetime.fromisoformat(alt.departure_time).time()
        assert dep_time >= dt_time(17, 0), f"Train departure {dep_time} was earlier than 17:00"

    # Verify budget filter on Bus
    bus_resp = received["REQ-FILTER-BUDGET"]
    assert bus_resp.total_found > 0
    for alt in bus_resp.results:
        assert alt.fare_inr <= 550.0, f"Bus fare {alt.fare_inr} exceeded budget 550.0"


def test_uagents_empty_results_resilience(test_db: DatabaseManager):
    """Test agents return clean empty results when no routes match extreme criteria."""
    loop = asyncio.new_event_loop()
    port_base = 8400
    rail_agent = create_rail_agent(db=test_db, port=port_base + 1, loop=loop)
    client_agent = Agent(
        name="test_empty_client",
        seed="test_empty_seed_8402",
        port=port_base + 2,
        loop=loop,
    )
    client_agent._mark_inactive_on_shutdown = False

    received = []

    @client_agent.on_message(model=TransportSearchResult)
    async def on_result(ctx: Context, sender: str, msg: TransportSearchResult):
        received.append(msg)

    @client_agent.on_event("startup")
    async def send_impossible_query(ctx: Context):
        # Budget cap of INR 50 for Delhi to Jaipur (impossible)
        await ctx.send(
            rail_agent.address,
            TransportSearchQuery(
                request_id="REQ-EMPTY-50",
                origin="Delhi",
                destination="Jaipur",
                max_budget_inr=50.0,
            ),
        )

    bureau = Bureau(port=port_base, loop=loop, shutdown_timeout=1)
    bureau.add(rail_agent)
    bureau.add(client_agent)

    with running_bureau(bureau, loop):
        start_time = time.time()
        while not received and (time.time() - start_time) < 10.0:
            time.sleep(0.2)

    assert len(received) == 1
    resp = received[0]
    assert resp.request_id == "REQ-EMPTY-50"
    assert resp.success is True
    assert resp.total_found == 0
    assert len(resp.results) == 0
