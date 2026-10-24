"""Comprehensive tests for Phase 6: ASI:One and Agentverse Integration.

Verifies:
1. Deterministic NLP extraction of travel parameters (origin, destination, budget, deadline).
2. ASI:One structured parsing with mocked LLM completions.
3. Graceful fallback to deterministic parsing when ASI:One is offline or credentials missing.
4. Grounded conversational response generation (enforcing strict anti-hallucination rules).
5. Grounded fallback when zero options meet user constraints.
6. Genuine uAgents Agent Chat Protocol messaging exchange:
   Client Agent -> ChatMessage -> RecoveryPlannerAgent -> ChatAcknowledgement + ChatMessage -> Client Agent.
7. FastAPI conversational chat endpoint POST /api/v1/recovery/chat.
8. Live integration test with ASI:One (active when ASI1_API_KEY is configured).
"""

import asyncio
from contextlib import contextmanager
import json
import os
import threading
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from uagents import Agent, Bureau, Context
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
)

from agents.bus_agent import create_bus_agent
from agents.cab_agent import create_cab_agent
from agents.rail_agent import create_rail_agent
from agents.recovery_planner_agent import create_recovery_planner_agent
from backend.main import app
from config.settings import settings
from schemas.agent_messages import (
    RankedAlternative,
    RecoveryRequest,
    RecoveryResponse,
    TransportSearchAlternative,
)
from services.asione_service import AsiOneService
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
# 1. DETERMINISTIC RULE-BASED NLP PARSER TESTS
# ==============================================================================

def test_deterministic_rule_based_parser_delhi_to_jaipur():
    """Verify deterministic extractor correctly parses complex user instruction without LLM."""
    service = AsiOneService()
    text = (
        "My train 12015 from Delhi to Jaipur was cancelled! "
        "I need to reach Jaipur before 18:00 with a budget under 1500 INR."
    )

    req = service.parse_with_deterministic_rules(text)

    assert req.origin == "Delhi"
    assert req.destination == "Jaipur"
    assert req.max_budget == 1500.0
    assert req.latest_acceptable_arrival == "18:00:00"
    assert req.max_transfers == 1


def test_deterministic_rule_based_parser_chandigarh_to_agra():
    """Verify extraction of departure time and non-stop transfers."""
    service = AsiOneService()
    text = "I am stuck in Chandigarh, need to go to Agra after 07:00 AM, max 2500 rupees, direct only."

    req = service.parse_with_deterministic_rules(text)

    assert req.origin == "Chandigarh"
    assert req.destination == "Agra"
    assert req.max_budget == 2500.0
    assert req.earliest_departure == "07:00:00"
    assert req.max_transfers == 0


# ==============================================================================
# 2. ASI:ONE MOCKED STRUCTURED PARSER TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_asione_structured_parser_mocked():
    """Verify ASI:One structured completion returns validated RecoveryRequest."""
    service = AsiOneService(api_key="mock_asi1_key")

    mock_llm_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "origin": "Delhi",
                            "destination": "Jaipur",
                            "earliest_departure": "06:00:00",
                            "latest_acceptable_arrival": "17:30:00",
                            "max_budget": 1200.0,
                            "max_transfers": 1,
                        }
                    )
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_llm_json
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        req, used_llm = await service.parse_instruction_to_request(
            "Find me an alternative route from Delhi to Jaipur before 5:30 PM under 1200"
        )

        assert used_llm is True
        assert req.origin == "Delhi"
        assert req.destination == "Jaipur"
        assert req.max_budget == 1200.0
        assert req.latest_acceptable_arrival == "17:30:00"
        assert mock_post.called


@pytest.mark.asyncio
async def test_asione_api_failure_graceful_fallback():
    """Verify that when ASI:One throws an error or times out, it gracefully falls back to deterministic NLP."""
    service = AsiOneService(api_key="mock_asi1_key")

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectError("Failed to connect to api.asi1.ai")

        req, used_llm = await service.parse_instruction_to_request(
            "From Delhi to Jaipur under 1500 before 18:00"
        )

        # Should fall back cleanly without raising
        assert used_llm is False
        assert req.origin == "Delhi"
        assert req.destination == "Jaipur"
        assert req.max_budget == 1500.0
        assert req.latest_acceptable_arrival == "18:00:00"


# ==============================================================================
# 3. GROUNDED CONVERSATIONAL EXPLANATION TESTS
# ==============================================================================

def test_grounded_response_deterministic_synthesis():
    """Verify deterministic response generator adheres strictly to anti-hallucination rules."""
    service = AsiOneService()

    req = RecoveryRequest(
        request_id="REQ-TEST",
        origin="Delhi",
        destination="Jaipur",
        max_budget=1500.0,
    )

    alt = TransportSearchAlternative(
        alternative_id="ALT-01",
        rank=1,
        service_id="TRN-12015",
        service_number="12015 Ajmer Shatabdi",
        provider="Northern Railway",
        mode="TRAIN",
        origin_code="NDLS",
        origin_name="New Delhi",
        destination_code="JP",
        destination_name="Jaipur Junction",
        departure_time="2026-10-24T06:10:00+05:30",
        arrival_time="2026-10-24T10:40:00+05:30",
        duration_minutes=270,
        distance_km=308.0,
        fare_inr=950.0,
        seat_availability="AVAILABLE",
        transfers_count=0,
        journey_pattern="DIRECT_TRAIN",
        has_estimated_costs=False,
        tradeoffs="Fast transit, guaranteed seat",
    )

    ranked_alt = RankedAlternative(
        rank=1,
        composite_score=94.5,
        score_breakdown={"duration_score": 90.0, "cost_score": 95.0},
        alternative=alt,
        selection_reason="Optimal recovery option with low fare and fast transit.",
    )

    rec_resp = RecoveryResponse(
        request_id="REQ-TEST",
        planner_address="test_planner",
        success=True,
        origin="Delhi",
        destination="Jaipur",
        total_options_evaluated=8,
        valid_options_count=4,
        rejected_options_count=4,
        top_3_options=[ranked_alt],
        best_option_explanation="12015 Ajmer Shatabdi was selected as top recommendation.",
    )

    explanation = service.generate_deterministic_explanation(req, rec_resp)

    # Must mention verified service number, provider, times, fare
    assert "12015 Ajmer Shatabdi" in explanation
    assert "Northern Railway" in explanation
    assert "INR 950" in explanation
    assert "06:10" in explanation
    assert "10:40" in explanation
    assert "Demonstration dataset for Fetch-A-Thon 3.0" in explanation
    assert "explicit approval" in explanation.lower()


def test_grounded_response_zero_options_explanation():
    """Verify explanation when 0 options meet constraints truthfully details rejection reasons."""
    service = AsiOneService()

    req = RecoveryRequest(
        request_id="REQ-EMPTY",
        origin="Delhi",
        destination="Jaipur",
        max_budget=100.0,
    )

    rec_resp = RecoveryResponse(
        request_id="REQ-EMPTY",
        planner_address="test_planner",
        success=True,
        origin="Delhi",
        destination="Jaipur",
        total_options_evaluated=10,
        valid_options_count=0,
        rejected_options_count=10,
        rejection_reasons={"fare_exceeded_maximum_budget": 10},
        top_3_options=[],
        best_option_explanation="No travel alternatives under INR 100 could satisfy all user constraints.",
    )

    explanation = service.generate_deterministic_explanation(req, rec_resp)

    assert "no travel options could satisfy all your constraints" in explanation
    assert "fare exceeded maximum budget" in explanation
    assert "RouteRescue AI demonstration network" in explanation


# ==============================================================================
# 4. AGENT CHAT PROTOCOL MESSAGING TEST (GENUINE UAGENTS EXCHANGE)
# ==============================================================================

def test_agent_chat_protocol_message_exchange():
    """Genuine uAgents multi-agent integration test verifying conversational Agent Chat Protocol:
    Client Agent -> ChatMessage -> RecoveryPlannerAgent -> ChatAcknowledgement + ChatMessage -> Client Agent.
    """
    loop = asyncio.new_event_loop()
    bureau = Bureau(port=8060, loop=loop)

    rail_agent = create_rail_agent(port=8061, loop=loop)
    bus_agent = create_bus_agent(port=8062, loop=loop)
    cab_agent = create_cab_agent(port=8063, loop=loop)

    planner_agent = create_recovery_planner_agent(
        rail_agent_address=rail_agent.address,
        bus_agent_address=bus_agent.address,
        cab_agent_address=cab_agent.address,
        port=8064,
        loop=loop,
        timeout_seconds=4.0,
    )

    client_agent = Agent(name="test_chat_client", seed="test_chat_client_seed_v1", port=8065, loop=loop)
    client_agent._mark_inactive_on_shutdown = False
    client_agent._shutdown_timeout = 1.0

    bureau.add(rail_agent)
    bureau.add(bus_agent)
    bureau.add(cab_agent)
    bureau.add(planner_agent)
    bureau.add(client_agent)

    received_acks: List[ChatAcknowledgement] = []
    received_chat_messages: List[ChatMessage] = []
    completion_event = threading.Event()

    @client_agent.on_event("startup")
    async def send_chat_recovery_inquiry(ctx: Context):
        msg = ChatMessage(
            content=[
                TextContent(
                    type="text",
                    text="My train from Delhi to Jaipur got cancelled. Find me recovery options under 1500 INR before 18:00.",
                )
            ]
        )
        await ctx.send(planner_agent.address, msg)

    @client_agent.on_message(model=ChatAcknowledgement)
    async def handle_acknowledgement(ctx: Context, sender: str, msg: ChatAcknowledgement):
        received_acks.append(msg)

    @client_agent.on_message(model=ChatMessage)
    async def handle_chat_reply(ctx: Context, sender: str, msg: ChatMessage):
        received_chat_messages.append(msg)
        completion_event.set()

    with running_bureau(bureau, loop):
        got_reply = completion_event.wait(timeout=12.0)

    assert got_reply is True, "Client did not receive conversational ChatMessage reply from RecoveryPlanner"
    assert len(received_acks) >= 1
    assert len(received_chat_messages) == 1

    reply = received_chat_messages[0]
    reply_text = reply.text()

    # Verify conversational grounding and content
    assert "Delhi" in reply_text
    assert "Jaipur" in reply_text
    assert "Option 1" in reply_text or "Option #1" in reply_text
    assert "Demonstration dataset" in reply_text


# ==============================================================================
# 5. FASTAPI CONVERSATIONAL RECOVERY ENDPOINT TEST
# ==============================================================================

def test_fastapi_conversational_recovery_endpoint():
    """Verify POST /api/v1/recovery/chat processes natural-language instructions."""
    client = TestClient(app)

    payload = {
        "message": "My morning train from Delhi to Jaipur was cancelled! Need options under 1500 INR before 6 PM.",
    }

    response = client.post("/api/v1/recovery/chat", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["parsed_request"]["origin"] == "Delhi"
    assert data["parsed_request"]["destination"] == "Jaipur"
    assert data["parsed_request"]["max_budget"] == 1500.0
    assert len(data["recovery_response"]["top_3_options"]) > 0
    assert "conversational_reply" in data
    assert "Option 1" in data["conversational_reply"]


# ==============================================================================
# 6. LIVE ASI:ONE API INTEGRATION TEST (CONDITIONAL)
# ==============================================================================

@pytest.mark.skipif(
    not os.getenv("ASI1_API_KEY") or os.getenv("ASI1_API_KEY") == "your_asi1_api_key_here",
    reason="ASI1_API_KEY not configured in environment (live test skipped in local CI)",
)
@pytest.mark.asyncio
async def test_live_asione_api_integration():
    """Live integration test against official ASI:One endpoint (runs when valid ASI1_API_KEY is supplied)."""
    service = AsiOneService()
    assert service.is_configured is True

    user_query = "Find me a recovery option from Delhi to Agra arriving before 12:00 with budget 800 INR."
    req, used_llm = await service.parse_instruction_to_request(user_query)

    assert used_llm is True
    assert req.origin == "Delhi"
    assert req.destination == "Agra"
    assert req.max_budget == 800.0
