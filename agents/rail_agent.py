"""Rail Search Agent powered by Fetch.ai uAgents.

Autonomously receives TransportSearchQuery messages, executes rail searches
against synthetic datasets via RailSearchService, and replies with structured
TransportSearchResult messages containing ranked train alternatives.
"""

import asyncio
from typing import Optional
from uagents import Agent, Context, Protocol

from config.settings import settings
from data.database import DatabaseManager
from schemas.agent_messages import TransportSearchQuery, TransportSearchResult
from services.modal_search import RailSearchService


def create_rail_agent(
    db: Optional[DatabaseManager] = None,
    port: Optional[int] = None,
    endpoint: Optional[str] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Agent:
    """Factory creating an independent Rail Search Agent instance."""
    agent_port = port or settings.rail_agent.port
    agent_endpoint = endpoint or settings.rail_agent.endpoint

    rail_agent = Agent(
        name=settings.rail_agent.name,
        seed=settings.rail_agent.seed,
        port=agent_port,
        endpoint=[agent_endpoint] if agent_endpoint else None,
        loop=loop,
    )

    rail_service = RailSearchService(db=db)
    rail_protocol = Protocol(name="RailSearchProtocol", version="1.0.0")

    @rail_protocol.on_message(model=TransportSearchQuery, replies={TransportSearchResult})
    async def handle_search_query(ctx: Context, sender: str, msg: TransportSearchQuery):
        agent_name = getattr(ctx.agent, "name", "rail_search_agent") if hasattr(ctx, "agent") else "rail_search_agent"
        agent_address = getattr(ctx.agent, "address", "") if hasattr(ctx, "agent") else ""

        ctx.logger.info(
            f"[RAIL] Agent [{agent_name}] received search query {msg.request_id} from {sender} "
            f"for {msg.origin} -> {msg.destination} (Budget: INR {msg.max_budget_inr})"
        )

        try:
            # Query the synthetic dataset using the separated modal search engine
            result = rail_service.search_rail(
                query=msg,
                agent_name=agent_name,
                agent_address=agent_address,
            )

            ctx.logger.info(
                f"[RAIL] Agent successfully found {result.total_found} train alternatives "
                f"in {result.execution_time_ms} ms. Replying to {sender}."
            )
            await ctx.send(sender, result)

        except Exception as exc:
            ctx.logger.error(f"[RAIL] Error in Rail Search Agent: {exc}")
            err_result = TransportSearchResult(
                request_id=msg.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="TRAIN",
                success=False,
                total_found=0,
                results=[],
                error_message=f"Rail Search Agent internal error: {str(exc)}",
            )
            await ctx.send(sender, err_result)

    rail_agent.include(rail_protocol)
    rail_agent._mark_inactive_on_shutdown = False
    rail_agent._shutdown_timeout = 1.0
    return rail_agent


if __name__ == "__main__":
    agent = create_rail_agent()
    print(f"Starting Rail Search Agent at {agent.address} on port {settings.rail_agent.port}...")
    agent.run()
