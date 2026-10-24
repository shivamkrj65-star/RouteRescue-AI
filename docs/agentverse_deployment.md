# RouteRescue AI — Agentverse & ASI:One Registration and Deployment Guide

This guide describes the complete procedure for deploying, registering, and exposing the **RouteRescue AI Recovery Planner Agent** on **Fetch.ai Agentverse** and integrating with **ASI:One** for conversational travel recovery.

---

## 🏗️ Architecture Overview

RouteRescue AI supports two standard Fetch.ai Agentverse integration patterns:

1. **Local Agent with Agentverse Mailbox (Recommended for Hybrid / On-Premise deployments):**
   - The multi-agent system runs locally on your machine or private server.
   - It establishes a persistent, secure WebSocket/HTTP mailbox connection with Agentverse.
   - No open public inbound ports or static IPs are required.
   - Users on Agentverse Explorer or ASI:One can discover and chat with the local agent.

2. **Hosted Agent on Agentverse (Cloud Deployment):**
   - The agent script is deployed directly into an Agentverse cloud container.
   - The agent runs 24/7 in Fetch.ai's hosted serverless infrastructure.

```
+-----------------------------------------------------------------------------------------------------------------+
|                                              Fetch.ai Ecosystem                                                 |
|                                                                                                                 |
|   +-----------------------+              +------------------------+              +--------------------------+   |
|   |   ASI:One Chat UI     |              |   Agentverse Explorer  |              |    Agentverse Mailbox    |   |
|   |  (Conversational LLM) | <----------> |     & Almanac Directory| <----------> | (https://agentverse.ai)  |   |
|   +-----------------------+              +------------------------+              +--------------------------+   |
|                                                                                               |                 |
|                                         Agent Chat Protocol (v1.0.0)                          |                 |
|                                          (ChatMessage, TextContent)                           |                 |
|                                                                                               v                 |
|                                                                                  +--------------------------+   |
|                                                                                  |  Recovery Planner Agent  |   |
|                                                                                  | (recovery_planner_agent) |   |
|                                                                                  +--------------------------+   |
|                                                                                               |                 |
|                                                                                               | uAgents Msg     |
|                                                                                               v                 |
|                                                                                  +--------------------------+   |
|                                                                                  |  Modal Transport Agents  |   |
|                                                                                  |     (Rail, Bus, Cab)     |   |
|                                                                                  +--------------------------+   |
+-----------------------------------------------------------------------------------------------------------------+
```

---

## 🔑 Prerequisites & Environment Variables

Create or update your `.env` file with your credentials:

```bash
# Agentverse Credentials
AGENTVERSE_API_KEY=your_agentverse_api_key_here
AGENTVERSE_MAILBOX=true
AGENTVERSE_URL=https://agentverse.ai

# ASI:One Conversational LLM API (Optional: fallback NLP parser used if not configured)
ASI1_API_KEY=your_asi1_api_key_here
ASI1_BASE_URL=https://api.asi1.ai/v1
ASI1_MODEL=asi1-mini
```

> **Note on Fallback Resilience:** If `ASI1_API_KEY` is not set or if the external API experiences downtime, RouteRescue AI automatically degrades to its built-in deterministic rule-based NLP extractor and template generator. The recovery planning workflow remains 100% operational.

---

## 📋 Step-by-Step Registration Workflow

### Step 1: Create an Agentverse Account
1. Navigate to [https://agentverse.ai](https://agentverse.ai).
2. Sign in using your Web3 wallet (Fetch Station, Keplr) or Google/GitHub credentials.

### Step 2: Generate an Agentverse API Key
1. Go to your **Profile** (top right) $\rightarrow$ **API Keys**.
2. Click **+ New API Key**.
3. Name your key (e.g. `routerescue-planner-key`).
4. Copy the generated key and assign it to `AGENTVERSE_API_KEY` in your `.env` file.

### Step 3: Register Local Agent with Agentverse Mailbox
1. In the Agentverse dashboard, go to **Local Agents** $\rightarrow$ **+ New Agent**.
2. Select **Connect Local Agent**.
3. Give your agent a name: `RouteRescue Recovery Planner`.
4. Copy the generated mailbox address or leave `AGENTVERSE_MAILBOX=true` in your `.env` to automatically establish the mailbox.

### Step 4: Configure Agent Profile & Discovery Manifest
When creating `recovery_planner_agent`, the agent initializes with the following profile:
- **Name:** `recovery_planner_agent`
- **Handle:** `@routerescue_planner`
- **Description:** `RouteRescue AI Autonomous Multimodal Travel Recovery Planner. Coordinates rail, bus, and road search agents to recover disrupted journeys in Northern India.`
- **Protocols Published:**
  - `RecoveryPlannerProtocol` (v1.0.0) — Structured agent-to-agent recovery messages.
  - `chat_protocol_spec` (`AgentChatProtocol`) — Agent Chat Protocol for ASI:One and human conversation.

### Step 5: Configure Starter Prompts for ASI:One
The Recovery Planner is pre-configured with starter prompts that appear as quick-action buttons on Agentverse Explorer and ASI:One:
1. *"My train 12015 from Delhi to Jaipur was cancelled. Find me recovery options under Rs. 1500 before 6 PM."*
2. *"Find the fastest route from Chandigarh to Jaipur tonight."*
3. *"I'm stuck in Delhi, need to reach Agra by 11 AM under 1000 INR."*

### Step 6: Start the Agent System
Run the unified multi-agent bureau:
```bash
python -m agents.runner
```
The Recovery Planner Agent will output:
```text
INFO: [recovery_planner_agent]: Connecting to Agentverse Mailbox...
INFO: [recovery_planner_agent]: Mailbox connected successfully.
INFO: [recovery_planner_agent]: Published manifest for RecoveryPlannerProtocol & AgentChatProtocol.
```

---

## 💬 Conversational Interaction via ASI:One

When a passenger or operator submits a natural language message through the Agentverse Chat interface or ASI:One:

1. **Chat Message Delivery:** A `ChatMessage` envelope containing `TextContent` is received by `handle_chat_message`.
2. **Immediate Acknowledgment:** The agent immediately replies with a `ChatAcknowledgement` confirming receipt.
3. **Intent Extraction:** `AsiOneService` parses the conversational text, extracting the origin, destination, arrival deadline, and budget cap.
4. **Autonomous Recovery Workflow:** The planner dispatches parallel queries to `rail_search_agent`, `bus_search_agent`, and `cab_road_search_agent`, queries `MultimodalRouter` for multi-leg connections, and ranks candidates using multi-criteria deterministic utility scoring.
5. **Grounded Response Generation:** `AsiOneService` converts the verified alternatives into an empathetic natural-language reply grounded strictly in the returned data.
6. **Delivery:** The formatted response is transmitted back to the user's chat session as a `ChatMessage`.

---

## 🛡️ Anti-Hallucination & Integrity Principles

1. **Zero Fabrication Guarantee:**
   - The agent will **never** invent fictitious train numbers, bus operators, prices, seat counts, or departure times.
   - If no route meets the passenger's constraints, the agent truthfully reports that zero options were found and details the exact constraints that caused rejections (e.g. `fare_exceeded_maximum_budget: 12`).
2. **Explicit User Approval:**
   - No ticket purchase, cab reservation, or payment is executed without explicit passenger confirmation.
3. **Demonstration Dataset Labeling:**
   - Every generated recovery plan is labeled: `DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)`.

---

## 🧪 Testing and Verification

Run the automated test suite for Phase 6:
```bash
# Run local mock tests (verifies parsing, fallback, grounding, ChatMessage exchange)
pytest -v tests/test_asione_agentverse.py

# Run live ASI:One test (only runs when ASI1_API_KEY is configured in .env)
pytest -v tests/test_asione_agentverse.py -k "test_live_asione_api_integration"
```
