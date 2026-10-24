"""Bus Search Agent powered by Fetch.ai uAgents.

Autonomously receives TransportSearchQuery messages, executes bus searches
against synthetic datasets via BusSearchService, and replies with structured
TransportSearchResult messages containing ranked coach and bus alternatives.
"""

import asyncio
from typing import Optional
from uagents import Agent, Context, Protocol

from config.settings import settings
from data.database import DatabaseManager
from schemas.agent_messages import TransportSearchQuery, TransportSearchResult
from services.modal_search import BusSearchService


def create_bus_agent(
    db: Optional[DatabaseManager] = None,
    port: Optional[int] = None,
    endpoint: Optional[str] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Agent:
    """Factory creating an independent Bus Search Agent instance."""
    agent_port = port or settings.bus_agent.port
    agent_endpoint = endpoint or settings.bus_agent.endpoint

    bus_agent = Agent(
        name=settings.bus_agent.name,
        seed=settings.bus_agent.seed,
        port=agent_port,
        endpoint=[agent_endpoint] if agent_endpoint else None,
        loop=loop,
    )

    bus_service = BusSearchService(db=db)
    bus_protocol = Protocol(name="BusSearchProtocol", version="1.0.0")

    @bus_protocol.on_message(model=TransportSearchQuery, replies={TransportSearchResult})
    async def handle_search_query(ctx: Context, sender: str, msg: TransportSearchQuery):
        agent_name = getattr(ctx.agent, "name", "bus_search_agent") if hasattr(ctx, "agent") else "bus_search_agent"
        agent_address = getattr(ctx.agent, "address", "") if hasattr(ctx, "agent") else ""

        ctx.logger.info(
            f"[BUS] Agent [{agent_name}] received search query {msg.request_id} from {sender} "
            f"for {msg.origin} -> {msg.destination} (Budget: INR {msg.max_budget_inr})"
        )

        try:
            # Query synthetic datasets via separated modal search service
            result = bus_service.search_bus(
                query=msg,
                agent_name=agent_name,
                agent_address=agent_address,
            )

            ctx.logger.info(
                f"[BUS] Agent successfully found {result.total_found} bus alternatives "
                f"in {result.execution_time_ms} ms. Replying to {sender}."
            )
            await ctx.send(sender, result)

        except Exception as exc:
            ctx.logger.error(f"[BUS] Error in Bus Search Agent: {exc}")
            err_result = TransportSearchResult(
                request_id=msg.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="BUS",
                success=False,
                total_found=0,
                results=[],
                error_message=f"Bus Search Agent internal error: {str(exc)}",
            )
            await ctx.send(sender, err_result)

    bus_agent.include(bus_protocol)
    bus_agent._mark_inactive_on_shutdown = False
    bus_agent._shutdown_timeout = 1.0
    return bus_agent


if __name__ == "__main__":
    agent = create_bus_agent()
    print(f"Starting Bus Search Agent at {agent.address} on port {settings.bus_agent.port}...")
    agent.run()
