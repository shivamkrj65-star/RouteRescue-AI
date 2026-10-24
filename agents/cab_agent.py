"""Cab & Road Search Agent powered by Fetch.ai uAgents.

Autonomously receives TransportSearchQuery messages, evaluates road and cab options
against synthetic datasets via CabRoadSearchService, and replies with structured
TransportSearchResult messages containing ranked taxi, rideshare, and road connections.
"""

import asyncio
from typing import Optional
from uagents import Agent, Context, Protocol

from config.settings import settings
from data.database import DatabaseManager
from schemas.agent_messages import TransportSearchQuery, TransportSearchResult
from services.modal_search import CabRoadSearchService


def create_cab_agent(
    db: Optional[DatabaseManager] = None,
    port: Optional[int] = None,
    endpoint: Optional[str] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Agent:
    """Factory creating an independent Cab & Road Search Agent instance."""
    agent_port = port or settings.cab_agent.port
    agent_endpoint = endpoint or settings.cab_agent.endpoint

    cab_agent = Agent(
        name=settings.cab_agent.name,
        seed=settings.cab_agent.seed,
        port=agent_port,
        endpoint=[agent_endpoint] if agent_endpoint else None,
        loop=loop,
    )

    cab_service = CabRoadSearchService(db=db)
    cab_protocol = Protocol(name="CabRoadSearchProtocol", version="1.0.0")

    @cab_protocol.on_message(model=TransportSearchQuery, replies={TransportSearchResult})
    async def handle_search_query(ctx: Context, sender: str, msg: TransportSearchQuery):
        agent_name = getattr(ctx.agent, "name", "cab_road_search_agent") if hasattr(ctx, "agent") else "cab_road_search_agent"
        agent_address = getattr(ctx.agent, "address", "") if hasattr(ctx, "agent") else ""

        ctx.logger.info(
            f"[CAB] Agent [{agent_name}] received search query {msg.request_id} from {sender} "
            f"for {msg.origin} -> {msg.destination} (Budget: INR {msg.max_budget_inr})"
        )

        try:
            # Query synthetic road datasets via separated modal search service
            result = cab_service.search_cabs(
                query=msg,
                agent_name=agent_name,
                agent_address=agent_address,
            )

            ctx.logger.info(
                f"[CAB] Agent successfully found {result.total_found} road alternatives "
                f"in {result.execution_time_ms} ms. Replying to {sender}."
            )
            await ctx.send(sender, result)

        except Exception as exc:
            ctx.logger.error(f"[CAB] Error in Cab & Road Search Agent: {exc}")
            err_result = TransportSearchResult(
                request_id=msg.request_id,
                agent_name=agent_name,
                agent_address=agent_address,
                mode="CAB",
                success=False,
                total_found=0,
                results=[],
                error_message=f"Cab Search Agent internal error: {str(exc)}",
            )
            await ctx.send(sender, err_result)

    cab_agent.include(cab_protocol)
    cab_agent._mark_inactive_on_shutdown = False
    cab_agent._shutdown_timeout = 1.0
    return cab_agent


if __name__ == "__main__":
    agent = create_cab_agent()
    print(f"Starting Cab & Road Search Agent at {agent.address} on port {settings.cab_agent.port}...")
    agent.run()
