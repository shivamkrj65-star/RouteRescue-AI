"""Multi-agent runner and bureau orchestrator for Phase 2 transport search agents."""

from typing import List, Optional
from uagents import Agent, Bureau

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.rail_agent import create_rail_agent
from data.database import DatabaseManager


def create_transport_bureau(
    db: Optional[DatabaseManager] = None,
    agents: Optional[List[Agent]] = None,
    port: int = 8000,
    endpoint: Optional[str] = None,
) -> Bureau:
    """Creates a unified Fetch.ai Bureau hosting all three independent transport search agents."""
    bureau = Bureau(port=port, endpoint=endpoint)

    if agents is None:
        rail = create_rail_agent(db=db)
        bus = create_bus_agent(db=db)
        cab = create_cab_agent(db=db)
        agents = [rail, bus, cab]

    for ag in agents:
        bureau.add(ag)

    return bureau


if __name__ == "__main__":
    print("Starting RouteRescue AI Transport Search Agents Bureau...")
    bureau = create_transport_bureau()
    bureau.run()
