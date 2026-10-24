"""Multi-agent runner and bureau orchestrator for RouteRescue AI agents."""

from typing import List, Optional
from uagents import Agent, Bureau

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.disruption_monitor_agent import create_disruption_monitor_agent
from agents.rail_agent import create_rail_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from data.database import DatabaseManager


def create_transport_bureau(
    db: Optional[DatabaseManager] = None,
    agents: Optional[List[Agent]] = None,
    port: int = 8000,
    endpoint: Optional[str] = None,
    include_planner: bool = True,
    include_monitor: bool = True,
) -> Bureau:
    """Creates a unified Fetch.ai Bureau hosting the transport search agents, Recovery Planner, and Disruption Monitor."""
    bureau = Bureau(port=port, endpoint=endpoint)

    if agents is None:
        rail = create_rail_agent(db=db)
        bus = create_bus_agent(db=db)
        cab = create_cab_agent(db=db)
        agent_list = [rail, bus, cab]

        planner = None
        if include_planner:
            planner = create_recovery_planner_agent(
                rail_agent_address=rail.address,
                bus_agent_address=bus.address,
                cab_agent_address=cab.address,
            )
            agent_list.append(planner)

        if include_monitor and planner:
            monitor = create_disruption_monitor_agent(
                planner_agent_address=planner.address,
                db=db,
            )
            agent_list.append(monitor)

        agents = agent_list

    for ag in agents:
        bureau.add(ag)

    return bureau


if __name__ == "__main__":
    print("Starting RouteRescue AI Full Autonomous Multi-Agent Bureau (Rail, Bus, Cab, Recovery Planner, Disruption Monitor)...")
    bureau = create_transport_bureau()
    bureau.run()
