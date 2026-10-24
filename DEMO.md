# RouteRescue AI — Official Hackathon Demonstration Script (3–5 Minutes)

**Event:** Fetch-A-Thon 3.0 (Innovation Lab Track)  
**Project:** RouteRescue AI — Autonomous Multimodal Travel Disruption Recovery System  
**Target Duration:** 3 to 5 Minutes  
**Presenters:** Project Architect / AI Multi-Agent Engineer  

---

## 🎯 Demonstration Setup & Checklist

Before starting the presentation:
1. Ensure services are running:
   ```powershell
   .\.venv\Scripts\python.exe scripts/start_all.py
   ```
2. Open the following browser tabs:
   - **Streamlit Dashboard:** `http://localhost:8501`
   - **FastAPI OpenAPI Docs:** `http://127.0.0.1:8000/docs`
   - **Agentverse Explorer / Mailbox:** `https://agentverse.ai`
3. Have a terminal ready to show the live execution script:
   ```powershell
   .\.venv\Scripts\python.exe scripts/run_demo.py
   ```

---

## ⏱️ Minute-by-Minute Presentation Script

### Part 1: The Problem & Pitch (0:00 – 0:45)

> **Speaker:**  
> *"Good morning judges and fellow builders. Every single day across high-density transit corridors, millions of travelers face sudden travel disruption—train derailments, seasonal fog cancellations, or waitlist tickets dropped after chart preparation.*  
>  
> *When your train is abruptly cancelled, you're stranded. You're opening IRCTC, switching to RedBus, checking Uber, doing mental math under extreme panic to reach your meeting before 11 PM without spending a fortune.*  
>  
> *Traditional chatbots can only regurgitate canned text when prompted. What passengers actually need is **an autonomous multi-agent system that monitors their journey in the background, detects disruptions proactively, negotiates with independent transport search agents, and synthesizes a feasible multimodal recovery route**.*  
>  
> *This is **RouteRescue AI**, powered by Fetch.ai uAgents, Agentverse, and ASI:One."*

---

### Part 2: Agentverse & The Multi-Agent Ecosystem (0:45 – 1:30)

> **Speaker:**  
> *"Let's look under the hood. RouteRescue AI is not a monolithic application. It is a decentralized bureau of five specialized Fetch.ai autonomous agents, each with its own cryptographic address and uAgents protocol.*  
>  
> *(Show `Agent Activity` tab on Dashboard or Agentverse console)*  
>  
> *1. **The Rail Search Agent** indexes Shatabdi, Rajdhani, and Vande Bharat services.*  
> *2. **The Bus Search Agent** monitors Zingbus, NueGo Electric, and RSRTC Volvo fleets.*  
> *3. **The Cab & Road Agent** calculates intercity highway routes like Uber Intercity and Savaari.*  
> *4. **The Disruption Monitor Agent** is an autonomous sentinel continuously polling booking statuses.*  
> *5. **The Recovery Planner Agent** orchestrates the entire workflow. Registered on **Agentverse** with public address `agent1q00zd0...`, it communicates via the **Agent Chat Protocol (ACP)** so any external user or agent in the ecosystem can discover its services."*

---

### Part 3: Autonomous Disruption Handling in Action (1:30 – 2:30)

> **Speaker:**  
> *(Navigate to `Demo Controls` tab on Streamlit UI, or run `scripts/run_demo.py`)*  
>  
> *"Let's watch a real end-to-end scenario. Meet Priya Sharma. Priya has a waitlisted ticket (WL 18) on the Swarna Jayanti Rajdhani from Delhi to Jaipur. She has a strict maximum budget of ₹1,500 and must arrive before 11 PM tonight.*  
>  
> *Watch what happens when Northern Railway abruptly cancels her train. (Click 'Simulate Train Cancellation' or trigger via API).*  
>  
> *Notice that Priya didn't have to check her phone. The **Disruption Monitor Agent** detected the status change to `CANCELLED` within seconds. It checked its deduplication cache to prevent duplicate alerts, and dispatched a `RecoveryRequest` to the **Recovery Planner Agent**.*  
>  
> *(Switch to `Agent Activity` page)*  
>  
> *Look at the live log stream! The Planner immediately dispatched parallel `TransportSearchQuery` messages to the Rail, Bus, and Cab agents. All three agents replied asynchronously with genuine uAgents messages containing verified alternatives correlated by a unique `request_id`.*  
>  
> *The routing engine evaluated all candidate connections. An Uber Intercity cab was rejected because it cost ₹3,600—violating Priya's ₹1,500 budget. Late overnight trains were rejected for violating her 11 PM deadline.*  
>  
> *(Switch to `Recovery Results` page)*  
>  
> *Here is the winning recommendation: **NueGo Electric - Green Eco Express**. Departure at 14:00, arrival at 19:15—well before her deadline—at a total fare of just **₹520**, earning a top composite score of 83.6 out of 100!"*

---

### Part 4: ASI:One Conversational Reasoning & User Preference Changes (2:30 – 3:30)

> **Speaker:**  
> *(Click the 'ASI:One Conversational Assistant' tab on the Dashboard)*  
>  
> *"What if Priya wants to talk to the system naturally? We've integrated **ASI:One** with full Agent Chat Protocol (ACP) support.*  
>  
> *Let's ask: **'What if I reduce my budget to ₹1,000?'**  
>  
> *(Click Send)*  
>  
> *ASI:One uses natural language understanding to extract the updated ₹1,000 budget ceiling, dispatches an ACP message to the Recovery Planner, and immediately re-evaluates the corridor. It confirms that the NueGo Electric bus and Pooja Superfast train still satisfy her new budget, explaining why each option qualifies.*  
>  
> *Let's ask: **'Show the fastest route.'**  
>  
> *Instantly, ASI:One dynamically updates the multi-criteria optimization weights—shifting duration weight to 70%—and re-ranks the alternatives to highlight the fastest journey under 5 hours.*  
>  
> *Most importantly: **ASI:One never invents fictitious trains or ticket prices**. Every single response is strictly grounded in the actual deterministic alternatives returned by the multi-agent bureau."*

---

### Part 5: Secure Booking Handoff & Real-World Impact (3:30 – 4:30)

> **Speaker:**  
> *(Click 'Proceed to Booking Handoff')*  
>  
> *"Now comes the most critical aspect: **safety and consent**.  
> In travel systems, an AI agent must never automatically charge a credit card without explicit user approval.  
>  
> *RouteRescue AI enforces a mandatory confirmation checkpoint. Priya reviews the selected alternative, checks the authorization box, and clicks 'Authorize Booking Handoff'.  
>  
> *The system securely hands off the booking to the verified operator portal (e.g. RedBus or IRCTC) with pre-populated parameters.  
>  
> *To summarize what you've seen today:*  
> *1. **Autonomous background monitoring** using Fetch.ai uAgents.*  
> *2. **Parallel multi-agent dispatch** across separate Rail, Bus, and Cab agents.*  
> *3. **Intelligent constraint-based routing** rejecting budget-busting and impossible connections.*  
> *4. **Agentverse discovery and ACP conversational interaction** with ASI:One.*  
> *5. **100% test-verified local execution** with zero mockups.*  
>  
> *RouteRescue AI proves how decentralized autonomous agents can solve real-world logistical nightmares for millions of passengers. Thank you!"*

---

## 🛠️ Demonstration Commands Cheat-Sheet

| Action | Command | Expected Result |
|:---|:---|:---|
| **Full System Health Check** | `python scripts/health_check.py` | Prints `PASSED` across all 6 core components |
| **Run E2E Demo via CLI** | `python scripts/run_demo.py` | Executes Priya Sharma's full disruption, recovery, and ASI:One follow-up in terminal |
| **Reset Demonstration Data** | `curl -X POST http://127.0.0.1:8000/api/v1/demo/reset` | Resets all disruptions and restores seeded baseline database |
| **Run Complete Test Suite** | `pytest -v` | Executes all 75 tests with 100% pass rate |
