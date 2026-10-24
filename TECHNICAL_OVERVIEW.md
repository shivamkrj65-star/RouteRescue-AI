# RouteRescue AI — Technical Architecture & Deep Dive Overview

**Fetch-A-Thon 3.0: Technical Architecture Documentation**

---

## 1. Why a Multi-Agent Architecture Was Selected

Traditional travel systems are built around monolithic search queries: a single server contacts multiple APIs sequentially, aggregates them in memory, and returns results. This architecture breaks down in real-world disruption recovery:

1. **Heterogeneous Modalities:** Railways, intercity buses, and highway cab networks operate on fundamentally different schedules, APIs, availability models, and disruption dynamics. Treating them as independent domain agents allows each modal search agent to maintain its own domain-specific indexing, filtering, and heuristics.
2. **Asynchronous Parallelism:** Instead of blocking while querying slow transportation APIs sequentially, the Recovery Planner broadcasts requests simultaneously to independent agents and collects responses asynchronously using correlation IDs.
3. **Decoupled Autonomy:** The **Disruption Monitor Agent** is a continuously running sentinel. It doesn't need to know how route optimization works; it only needs to observe bookings, evaluate status changes against business rules, and notify the **Recovery Planner Agent** when a recovery event triggers.
4. **Resilience & Fault Isolation:** If the Rail Search Agent experiences an outage or timeout, the Recovery Planner does not crash. It gracefully handles the offline agent and continues ranking viable bus and road alternatives.

---

## 2. Why Fetch.ai uAgents Was Used

Fetch.ai's **uAgents** framework was selected because it provides native primitives for decentralized, autonomous multi-agent systems:

- **Cryptographic Identities:** Every agent has its own unique private key, public key, and Bech32 address (e.g. `agent1qtufey...`). Message authenticity is cryptographically guaranteed.
- **Protocol-Driven Messaging:** Communication is defined using explicit typed `Protocol` models and `@protocol.on_message` handlers. This ensures strict schema validation at the network boundary.
- **Built-in Schedulers:** Agents use `@agent.on_interval` handlers for periodic tasks (such as background booking status monitoring) without requiring external chron daemons.
- **Asynchronous Message Routing:** Supports true non-blocking message exchanges, timeouts, and correlation tokens between agents operating in separate processes or threads.
- **Native Bureau Runtime:** Supports hosting multiple agents locally on a single Bureau port (`port 8010`) while preserving isolated agent contexts, event loops, and mailboxes.

---

## 3. Why Agentverse Integration Matters

**Agentverse** bridges RouteRescue AI from a local prototype to a discoverable, interoperable node in the global agent ecosystem:

1. **Mailbox Infrastructure:** Allows agents deployed on private workstations or behind NAT firewalls to receive incoming messages reliably from other agents without exposing public IP ports.
2. **Global Agent Discovery:** By publishing agent manifests and protocol schemas to Agentverse, other autonomous agents (e.g., corporate travel agents, hotel booking agents, or calendar assistants) can autonomously discover RouteRescue AI and request travel disruption recovery on behalf of their users.
3. **Managed Cloud Deployment:** Enables zero-infrastructure migration where agent code can be hosted and executed directly on Agentverse cloud workers.

---

## 4. Why ASI:One Is a Meaningful Part of the Workflow

Rather than using a generic chatbot, **ASI:One** is deeply integrated into the operational recovery pipeline:

1. **Conversational Intent Extraction:** Passengers in distress express requirements naturally (*"My train was cancelled, I need to get to Jaipur before 11 PM, but I can't spend more than ₹1,500"*). ASI:One extracts structured entities: `origin="Delhi"`, `destination="Jaipur"`, `latest_arrival="23:00"`, `max_budget=1500.0`.
2. **Context-Aware Follow-ups:** Handles conversational refinement (*"What if I reduce my budget to ₹1,000?"* or *"Show the fastest route"*) and dynamically recalibrates constraint parameters.
3. **Grounded Fact Synthesis:** ASI:One never hallucinates schedules. It takes the deterministic mathematical output from the routing engine and translates it into an empathetic, clear, grounded explanation.
4. **Deterministic Fallback Engine:** To guarantee zero downtime, RouteRescue AI includes an automated regex-based NLP engine. If the ASI:One API key is unavailable or experiences latency, the local parser immediately takes over without user impact.

---

## 5. How Route Optimization Works

The multimodal routing engine in RouteRescue AI combines time-dependent constraint filtering with multi-criteria optimization:

### Step 1: Candidate Generation
The engine ingests all alternatives returned by the Rail, Bus, and Cab agents, including direct services and multimodal connection legs (e.g. Cab from Gurugram to Delhi Station + Express Train to Jaipur).

### Step 2: Hard Constraint Elimination (Zero Tolerance)
A candidate journey is strictly rejected if:
- $\text{Total Fare} > \text{Maximum Budget Ceiling}$
- $\text{Arrival Time} > \text{Latest Acceptable Deadline}$
- $\text{Departure Time} < \text{Earliest Departure Threshold}$
- $\text{Transfers} > \text{Maximum Permitted Transfers}$
- $\text{Transfer Buffer} < 30 \text{ minutes}$ (eliminates impossible tight connections)
- $\text{Seat Status} == \text{SOLD\_OUT}$

### Step 3: Multi-Criteria Composite Scoring
Feasible candidates are scored on a normalized scale $[0, 100]$:

$$S(j) = 100 \times \left( w_{\text{cost}} \cdot S_{\text{cost}} + w_{\text{dur}} \cdot S_{\text{dur}} + w_{\text{rel}} \cdot S_{\text{rel}} + w_{\text{dir}} \cdot S_{\text{dir}} \right)$$

- **Economy ($S_{\text{cost}}$):** Linear savings normalized against the user's budget ceiling.
- **Speed ($S_{\text{dur}}$):** Transit duration normalized between the fastest and slowest feasible options.
- **Reliability ($S_{\text{rel}}$):** Historical punctuality score of the operator (e.g. 0.94 for Rajdhani, 0.88 for NueGo).
- **Directness ($S_{\text{dir}}$):** Penalizes transfers (1.0 for direct, 0.7 for 1 transfer, 0.4 for $\ge 2$).

The top 3 scoring journeys are returned, and a natural-language justification is generated for the highest-ranked alternative.

---

## 6. How Monitoring Triggers Recovery

The **Disruption Monitor Agent** acts as an autonomous background sentinel:

1. **State Polling:** Periodically reads all active journeys from SQLite (`routerescue.db`) using APScheduler.
2. **Status Evaluation:** Queries the `SimulatedBookingProvider` to check current PNR state (Confirmed, Waitlisted, RAC, Delayed, Cancelled, Dropped).
3. **Disruption Heuristics:**
   - Any status change to `CANCELLED` triggers immediate recovery.
   - Any delay exceeding the qualifying threshold (default: 45 minutes) triggers recovery.
   - Any waitlist ticket dropped after chart preparation triggers recovery.
4. **Deduplication:** A cached set of `(journey_id, reason_code)` prevents duplicate recovery requests for the same disruption incident.
5. **Autonomous Dispatch:** Constructs a `RecoveryRequest` and sends it directly to the Recovery Planner Agent's address via uAgents messaging.

---

## 7. Division of Responsibilities: AI vs. Deterministic

To ensure mathematical precision, safety, and reliability, RouteRescue AI maintains a strict division of labor:

| Capability | Module | Type | Why This Approach Was Chosen |
|:---|:---|:---:|:---|
| **Conversational Understanding** | ASI:One / LiteLLM | **AI / LLM** | Handles natural language variance, colloquial phrasing, and conversational follow-ups. |
| **Response Tone & Empathy** | ASI:One | **AI / LLM** | Explains complex transit tradeoffs in friendly, accessible human language. |
| **Constraint Validation** | `RecoveryEngine` | **Deterministic** | Budget ceilings, deadlines, and buffer times cannot tolerate hallucinations. |
| **Route Scoring & Ranking** | `RecoveryEngine` | **Deterministic** | Mathematical formula ensures transparent, reproducible, and verifiable recommendations. |
| **Connection Feasibility** | `MultimodalRouter` | **Deterministic** | Station coordinates and 30-minute layover rules require exact mathematical checks. |
| **Disruption Detection** | `DisruptionEvaluator` | **Deterministic** | Status change thresholds (>45 min, cancellations) follow strict business logic. |
| **Booking Handoff** | Gateway Controller | **Deterministic** | Absolute safety: requires explicit user checkbox authorization before handoff. |

---

## 8. What Data Is Simulated (Demonstration Boundaries)

For the purposes of Fetch-A-Thon 3.0 evaluation, RouteRescue AI operates on realistic, high-fidelity synthetic data:

- **Corridor Coverage:** Northern India golden triangle (Delhi, Jaipur, Chandigarh, Agra, Gurugram, Noida, Mathura, Ambala).
- **Transit Services:** 90 curated transit connections across 15 transit hubs (33 Trains, 34 Buses, 23 Cabs).
- **Booking Provider:** `SimulatedBookingProvider` models real IRCTC PNR lifecycle states (`CONFIRMED`, `WL 18`, `RAC 4`, `CANCELLED`, `DROPPED_AFTER_CHARTING`).
- **Simulated Labeling:** All synthetic records are explicitly tagged with `DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)` to distinguish them from live production data.
