"""Streamlit Interactive Disruption Recovery Console for RouteRescue AI."""

import streamlit as st
from datetime import datetime, date, time
from config.settings import IST, settings
from data.database import DatabaseManager
from schemas.common import TransportMode
from services.asione_service import AsiOneService
from services.recovery_engine import RecoveryEngine
from services.transport_service import TransportDataService

st.set_page_config(
    page_title="RouteRescue AI - Travel Recovery",
    page_icon="🚆",
    layout="wide",
)

st.title("🚆 RouteRescue AI")
st.caption(f"Autonomous Multimodal Travel Disruption Recovery System | Demonstration Region: {settings.corridor_region}")

st.info(
    "⚠️ **Demonstration Mode Notice**: All train schedules, bus routes, highway connections, and disruption alerts "
    "are realistic synthetic records generated for Fetch-A-Thon 3.0. Live bookings are not executed without user approval."
)

db = DatabaseManager()
transport_service = TransportDataService(db=db)

# Sidebar
st.sidebar.header("🔍 Journey Search & Recovery")
locations = db.list_all_locations()
location_names = sorted(list(set([loc.city for loc in locations])))

col1, col2 = st.sidebar.columns(2)
with col1:
    origin_city = st.selectbox("Origin", options=location_names, index=0)
with col2:
    dest_candidates = [c for c in location_names if c != origin_city]
    destination_city = st.selectbox("Destination", options=dest_candidates, index=0)

budget = st.sidebar.number_input("Max Budget (INR)", min_value=100.0, max_value=10000.0, value=2500.0, step=100.0)
mode_choice = st.sidebar.selectbox("Filter Mode", options=["ALL", "TRAIN", "BUS", "CAB"])
selected_mode = None if mode_choice == "ALL" else TransportMode(mode_choice)
available_only = st.sidebar.checkbox("Available Seats Only", value=True)

search_clicked = st.sidebar.button("Search Alternative Journeys", use_container_width=True)

# Main Dashboard Tabs
tab_search, tab_disruptions, tab_passenger, tab_assistant = st.tabs([
    "🛣️ Available Journeys",
    "🚨 Active Disruptions",
    "👤 Passenger Recovery Monitor",
    "🤖 ASI:One Travel Assistant",
])

with tab_search:
    st.subheader(f"Search Results: {origin_city} ➔ {destination_city}")
    response = transport_service.search_by_params(
        origin=origin_city,
        destination=destination_city,
        max_budget_inr=budget,
        mode=selected_mode,
        require_available_seats=available_only,
    )

    if response.total_found == 0:
        st.warning(f"No direct connections found matching criteria between {origin_city} and {destination_city}. Try adjusting your budget or mode filter.")
    else:
        st.success(f"Found {response.total_found} alternative service options:")
        for alt in response.results:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
                with c1:
                    st.markdown(f"### #{alt.rank} {alt.service.mode.value}")
                    st.write(f"**Provider:** {alt.service.provider}")
                    st.caption(f"ID: `{alt.service.service_id}`")
                with c2:
                    st.write(f"**Route:** {alt.service.origin.name} ➔ {alt.service.destination.name}")
                    overnight_badge = " 🌙 *Overnight*" if alt.is_overnight else ""
                    st.write(f"**Timing:** {alt.departure_time.strftime('%H:%M')} – {alt.arrival_time.strftime('%H:%M')}{overnight_badge}")
                    st.caption(f"Duration: {alt.duration_minutes // 60}h {alt.duration_minutes % 60}m | Distance: {alt.service.distance_km:.0f} km")
                with c3:
                    st.metric("Estimated Fare", f"₹{alt.total_fare_inr:.0f}")
                    st.write(f"**Status:** `{alt.availability_status.value}`")
                with c4:
                    st.caption(f"💡 *{alt.tradeoffs}*")
                    if alt.booking_url:
                        st.link_button("View Details", alt.booking_url, use_container_width=True)

with tab_disruptions:
    st.subheader("Simulated Travel Disruption Monitor (Active Corridors)")
    disruptions = transport_service.list_active_disruptions()
    for d in disruptions:
        with st.container(border=True):
            col_d1, col_d2 = st.columns([3, 1])
            with col_d1:
                st.markdown(f"#### ⚠️ {d.headline}")
                st.write(d.description)
                st.caption(f"Corridor: **{d.affected_origin} ➔ {d.affected_destination}** | Operator: {d.operator} | Ref: `{d.source_reference}`")
            with col_d2:
                st.error(f"Severity: {d.severity.value}")
                if d.is_cancelled:
                    st.badge("SERVICE CANCELLED")
                else:
                    st.warning(f"Delay: +{d.delay_minutes} mins")

with tab_passenger:
    st.subheader("Demonstration Disrupted Passenger Profile")
    journey = db.get_user_journey("JRN-ROHAN-9901")
    if journey:
        st.write(f"**Passenger:** {journey.passenger_name} ({journey.passenger_email})")
        st.write(f"**Booked Train:** {journey.booked_service.service_number} ({journey.booked_service.origin.name} ➔ {journey.booked_service.destination.name})")
        st.error(f"**Status:** {journey.booking_status.value} (Track Maintenance near Alwar)")
        st.write(f"**PNR Reference:** `{journey.booking_reference}` | **Paid Fare:** ₹{journey.booked_fare_inr:.0f}")

with tab_assistant:
    st.subheader("🤖 ASI:One Conversational Disruption Recovery")
    st.caption("Ask questions naturally: report a cancelled service, request recovery alternatives, or set custom budget/arrival limits.")

    asione_svc = AsiOneService()
    recovery_eng = RecoveryEngine()

    status_badge = "🟢 Live (ASI:One Configured)" if asione_svc.is_configured else "🟡 Local NLP Fallback (Deterministic Mode)"
    st.caption(f"Provider Status: **{status_badge}** | Model: `{asione_svc.model}`")

    # Example starter prompts
    st.markdown("**Quick Prompts:**")
    prompt_cols = st.columns(3)
    p1 = "My train 12015 from Delhi to Jaipur was cancelled. Find me options under 1500 INR before 6 PM."
    p2 = "Find the fastest route from Chandigarh to Jaipur tonight."
    p3 = "I'm stuck in Delhi, need to reach Agra by 11 AM under 1000 INR."

    selected_prompt = None
    if prompt_cols[0].button("⚠️ Delhi ➔ Jaipur (Cancelled)", use_container_width=True):
        selected_prompt = p1
    if prompt_cols[1].button("⚡ Chandigarh ➔ Jaipur (Fastest)", use_container_width=True):
        selected_prompt = p2
    if prompt_cols[2].button("⏱️ Delhi ➔ Agra (Under 1000)", use_container_width=True):
        selected_prompt = p3

    user_query = st.chat_input("Describe your travel disruption or travel need...")
    active_input = selected_prompt or user_query

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for item in st.session_state["chat_history"]:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])

    if active_input:
        with st.chat_message("user"):
            st.markdown(active_input)
        st.session_state["chat_history"].append({"role": "user", "content": active_input})

        with st.chat_message("assistant"):
            with st.spinner("Analyzing disruption & synthesizing multimodal recovery..."):
                # Run parse
                req = asione_svc.parse_with_deterministic_rules(active_input)
                rec_resp = recovery_eng.process_recovery(
                    modal_results={},
                    request=req,
                    planner_address="recovery_planner_agent",
                )
                reply = asione_svc.generate_deterministic_explanation(req, rec_resp)
                st.markdown(reply)
                st.session_state["chat_history"].append({"role": "assistant", "content": reply})
