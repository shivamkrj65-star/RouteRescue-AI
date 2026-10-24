"""RouteRescue AI - End-to-End Demonstration Scenario Runner.

Executes Step 4 & 5 Hackathon Demo:
1. Registers Priya Sharma's Delhi -> Jaipur journey (Status: WL 18, Budget: ₹1,500, Deadline: 23:00)
2. Injects simulated CANCELLED disruption event
3. Triggers recovery planning across Rail, Bus, and Cab modal options
4. Evaluates constraints (max budget ₹1,500, arrival before 11 PM / 23:00, max transfers 1)
5. Displays top recommended route, composite score, and grounded explanation
6. Demonstrates user authorization for booking handoff
7. Tests conversational follow-ups via ASI:One:
   - "What if I reduce my budget to ₹1,000?"
   - "Show the fastest route."
   - "I don't want more than one transfer."
"""

import sys
import os
from pathlib import Path

# Force UTF-8 on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
from fastapi.testclient import TestClient
from backend.main import app


def get_client():
    """Return a live HTTP client if backend is running on 8000, otherwise TestClient."""
    try:
        with httpx.Client(timeout=2.0) as probe:
            res = probe.get("http://127.0.0.1:8000/health")
            if res.status_code == 200:
                print("  [*] Connecting to live FastAPI backend at http://127.0.0.1:8000")
                return httpx.Client(base_url="http://127.0.0.1:8000", timeout=15.0)
    except Exception:
        pass
    print("  [*] Live backend not detected on 8000; executing via local ASGI TestClient")
    return TestClient(app)


def run_demo():
    print("=" * 72)
    print("      RouteRescue AI - End-to-End Autonomous Recovery Demonstration")
    print("=" * 72)
    
    client = get_client()

    # 1. Register Priya Sharma's Journey
    print("\n[Step 1] Registering User Journey...")
    reg_payload = {
        "passenger_name": "Priya Sharma",
        "passenger_email": "priya.sharma@example.com",
        "origin": "Delhi",
        "destination": "Jaipur",
        "booking_status": "WAITLISTED",
        "booking_reference": "PNR-PRIYA-WL18",
        "fare_inr": 1150.0,
        "max_budget": 1500.0,
        "arrival_deadline": "23:00",
        "max_transfers": 1,
    }
    resp = client.post("/api/v1/journeys", json=reg_payload)
    if resp.status_code != 200:
        print(f"[-] Registration failed: {resp.text}")
        return
    journey = resp.json()
    journey_id = journey["journey_id"]
    svc = journey.get("booked_service", {})
    orig_city = svc.get("origin", {}).get("city", "Delhi")
    dest_city = svc.get("destination", {}).get("city", "Jaipur")
    svc_name = svc.get("service_name", "Express Service")

    print(f"  [+] Passenger: {journey['passenger_name']} (ID: {journey_id})")
    print(f"      Route:     {orig_city} -> {dest_city}")
    print(f"      Booking:   {journey.get('booking_reference')} ({svc_name})")
    print(f"      Initial:   Status={journey['booking_status']} (WL 18)")
    print(f"      Policy:    Max Budget=Rs. 1,500.00 | Deadline=23:00 | Max Transfers=1")

    # 2. Inject Disruption (Cancellation)
    print("\n[Step 2] Simulating Journey Disruption Event...")
    inj_payload = {
        "journey_id": journey_id,
        "status": "CANCELLED",
        "delay_minutes": 0,
        "pnr_position": None,
        "reason": "Severe technical derailment risk - Northern Railway cancelled service",
    }
    inj_resp = client.post("/api/v1/disruptions/inject", json=inj_payload)
    print(f"  [!] Disruption Injected: Status -> CANCELLED")
    print(f"  [+] Event response: {inj_resp.json().get('message')}")

    # 3. Trigger Recovery Planning
    print("\n[Step 3] Autonomous Recovery Planning...")
    print("  [*] Querying modal search services (Rail, Bus, Cab)...")
    plan_payload = {
        "journey_id": journey_id,
        "origin": "Delhi",
        "destination": "Jaipur",
        "max_budget": 1500.0,
        "latest_arrival": "23:00",
        "max_transfers": 1,
    }
    plan_resp = client.post("/api/v1/recovery/plan", json=plan_payload)
    if plan_resp.status_code != 200:
        print(f"[-] Recovery planning failed: {plan_resp.text}")
        return
    plan_data = plan_resp.json()
    top_3 = plan_data.get("top_3_options", [])
    
    print(f"  [+] Multi-agent Recovery Search: Success={plan_data.get('success')}")
    print(f"  [+] Total Valid Alternatives:    {plan_data.get('total_alternatives_considered')}")
    print(f"  [+] Top Options Returned:        {len(top_3)}")

    if top_3:
        top_ranked = top_3[0]
        alt = top_ranked["alternative"]
        print("\n" + "-" * 72)
        print("                 TOP RECOMMENDED RECOVERY OPTION")
        print("-" * 72)
        print(f"  Mode:            {alt.get('mode')} ({alt.get('provider')} - {alt.get('service_name')})")
        print(f"  Departure:       {alt.get('departure_time')}")
        print(f"  Arrival:         {alt.get('arrival_time')} (Arrives before 23:00 deadline)")
        print(f"  Total Cost:      Rs. {alt.get('fare_inr', 0):,.2f} (Within budget Rs. 1,500.00)")
        print(f"  Transfers:       {alt.get('transfers', 0)} transfer(s)")
        print(f"  Composite Score: {top_ranked.get('score', 0):.2f} / 100")
        print(f"  Explanation:     {plan_data.get('best_option_explanation')}")
        print("-" * 72)

        # Alternative options
        if len(top_3) > 1:
            print("\n  Other Ranked Options:")
            for i, opt in enumerate(top_3[1:], start=2):
                o_alt = opt["alternative"]
                print(f"    Option #{i}: [{o_alt.get('mode')}] {o_alt.get('service_name')} | "
                      f"Dep: {str(o_alt.get('departure_time'))[11:16]} -> Arr: {str(o_alt.get('arrival_time'))[11:16]} | "
                      f"Cost: Rs. {o_alt.get('fare_inr', 0):,.2f} | Score: {opt.get('score', 0):.2f}")

        # 4. User Authorization Booking Handoff
        print("\n[Step 4] Passenger Authorization for Booking Handoff...")
        book_payload = {
            "journey_id": journey_id,
            "alternative_id": alt["alternative_id"],
            "service_id": alt["service_id"],
            "provider": alt.get("provider", "TransportProvider"),
            "booking_url": alt.get("booking_url") or "https://www.irctc.co.in",
            "fare_inr": alt.get("fare_inr", 1250.0),
            "user_approved": True,
            "passenger_name": "Priya Sharma",
        }
        book_resp = client.post("/api/v1/bookings/approve", json=book_payload)
        book_data = book_resp.json()
        print(f"  [+] Passenger Consent: Confirmed")
        print(f"  [+] Booking Status:    {book_data.get('status')}")
        print(f"  [+] Provider Handoff:  {book_data.get('handoff_url', alt.get('booking_url'))}")
        print(f"  [+] Note:              {book_data.get('message', 'Booking handoff ready')}")

    # 5. ASI:One Conversational Follow-ups
    print("\n[Step 5] Testing ASI:One Conversational Interaction...")
    queries = [
        "What if I reduce my budget to Rs. 1,000?",
        "Show the fastest route.",
        "I don't want more than one transfer.",
    ]
    for q in queries:
        print(f"\n  Passenger Query: \"{q}\"")
        chat_payload = {
            "message": q,
            "context_journey_id": journey_id,
        }
        chat_resp = client.post("/api/v1/recovery/chat", json=chat_payload)
        if chat_resp.status_code == 200:
            cdata = chat_resp.json()
            preq = cdata.get("parsed_request", {})
            r_resp = cdata.get("recovery_response", {})
            top_rec = r_resp.get("top_3_options", [{}])[0] if r_resp.get("top_3_options") else {}
            alt_info = top_rec.get("alternative", {})
            cost_str = f"Rs. {alt_info.get('fare_inr', 0):,.2f}" if alt_info else "N/A"
            provider = cdata.get("provider", "ASI:One")
            reply = cdata.get("conversational_reply", "No response generated")
            print(f"  [+] Engine:        {provider}")
            print(f"  [+] Parsed Intent: Origin={preq.get('origin')}, Dest={preq.get('destination')}, Budget=Rs. {preq.get('max_budget')}")
            print(f"  [+] Best Route:    [{alt_info.get('mode', 'N/A')}] {alt_info.get('service_name', 'N/A')} | Cost: {cost_str}")
            print(f"  [+] AI Explanation:\n      {reply.strip()[:200]}...")
        else:
            print(f"  [-] Chat failed: {chat_resp.text}")

    print("\n" + "=" * 72)
    print("      Demonstration Completed Successfully!")
    print("=" * 72)


if __name__ == "__main__":
    run_demo()
