"""RouteRescue AI - Modern Streamlit Multi-Agent Recovery Dashboard.

Fetch-A-Thon 3.0 Multimodal Travel Recovery Platform.
Connects directly to the FastAPI backend (http://127.0.0.1:8000).
"""

from datetime import date, datetime, time
import json
import streamlit as st

from frontend.api_client import RouteRescueApiClient

# Configure Page
st.set_page_config(
    page_title="RouteRescue AI - Autonomous Travel Recovery",
    page_icon="🚆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize API Client
api_client = RouteRescueApiClient()

# Initialize Session State
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "📊 Dashboard"
if "handoff_alternative" not in st.session_state:
    st.session_state["handoff_alternative"] = None
if "selected_recovery_journey" not in st.session_state:
    st.session_state["selected_recovery_journey"] = None
if "last_recovery_plan" not in st.session_state:
    st.session_state["last_recovery_plan"] = None


# -----------------------------------------------------------------------------
# Sidebar Navigation & Backend Status
# -----------------------------------------------------------------------------

st.sidebar.title("🚆 RouteRescue AI")
st.sidebar.caption("Autonomous Multimodal Travel Recovery | Fetch-A-Thon 3.0")

# Check backend health
health = api_client.check_health()
if health.get("status") == "online":
    st.sidebar.success(f"🟢 Backend Online (v{health.get('version', '1.0')})")
else:
    st.sidebar.error("🔴 Backend Offline (Start `uvicorn backend.main:app` on port 8000)")

# Navigation Menu
pages = [
    "📊 Dashboard",
    "📝 Journey Registration",
    "🤖 Agent Activity",
    "🧭 Recovery Results",
    "🎛️ Demo Controls",
    "🎟️ Booking Handoff",
]

# Allow programmatically updating page via session state
if "page_selector" not in st.session_state or st.session_state["page_selector"] not in pages:
    st.session_state["page_selector"] = st.session_state["selected_page"]

page = st.sidebar.radio(
    "Navigation",
    options=pages,
    index=pages.index(st.session_state["page_selector"]),
    key="nav_radio",
)
st.session_state["selected_page"] = page
st.session_state["page_selector"] = page

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ Quick Demonstration Actions")

if st.sidebar.button("🔄 Reset Demo to Baseline", use_container_width=True):
    with st.spinner("Resetting database and status overrides..."):
        res = api_client.reset_demo()
        st.session_state["handoff_alternative"] = None
        st.session_state["selected_recovery_journey"] = None
        st.session_state["last_recovery_plan"] = None
        st.sidebar.success("Demonstration reset to baseline!")
        st.rerun()

st.sidebar.caption(
    "⚠️ **Demonstration Notice**: All schedules, journeys, and alerts are realistic synthetic demonstration data. "
    "No actual payments or booking reservations are finalized without user authorization."
)


# -----------------------------------------------------------------------------
# PAGE 1: DASHBOARD
# -----------------------------------------------------------------------------
if page == "📊 Dashboard":
    st.title("📊 System Dashboard & Monitored Journeys")
    st.caption("Real-time monitoring of passenger bookings, disruptions, and autonomous recovery status.")

    # Fetch Data
    journeys = api_client.list_user_journeys()
    disruptions = api_client.list_disruptions()
    mon_status = api_client.get_monitoring_status()

    # Metric Row
    total_journeys = len(journeys)
    disrupted_count = sum(
        1 for j in journeys if j.get("booking_status") in ("CANCELLED_BY_DISRUPTION", "DELAYED", "WAITLISTED", "DROPPED_CHART_PREPARED")
    )
    confirmed_count = sum(1 for j in journeys if j.get("booking_status") == "CONFIRMED")
    active_alerts_count = len(disruptions)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Journeys", total_journeys)
    m2.metric("Disrupted / At-Risk", disrupted_count, delta=f"{disrupted_count} requiring recovery", delta_color="inverse")
    m3.metric("Confirmed & On-Track", confirmed_count)
    m4.metric("Active Travel Alerts", active_alerts_count)

    st.markdown("---")

    # Layout: Journeys Table & Disruptions Feed
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("👤 Monitored Passenger Journeys")
        
        status_filter = st.selectbox(
            "Filter by Booking Status",
            options=["ALL", "CANCELLED_BY_DISRUPTION", "DELAYED", "WAITLISTED", "CONFIRMED", "RAC"],
            index=0,
        )

        filtered_journeys = [
            j for j in journeys if status_filter == "ALL" or j.get("booking_status") == status_filter
        ]

        if not filtered_journeys:
            st.info("No journeys found matching the selected filter.")
        else:
            for j in filtered_journeys:
                status = j.get("booking_status", "UNKNOWN")
                svc = j.get("booked_service", {})
                orig = svc.get("origin", {}).get("name", "Unknown Origin")
                dest = svc.get("destination", {}).get("name", "Unknown Dest")
                orig_city = svc.get("origin", {}).get("city", "")
                dest_city = svc.get("destination", {}).get("city", "")

                status_color = "green" if status == "CONFIRMED" else "red" if "CANCELLED" in status else "orange"

                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 2])
                    with c1:
                        st.markdown(f"**{j.get('passenger_name')}** (`{j.get('journey_id')}`)")
                        st.caption(f"PNR: `{j.get('booking_reference')}` | Email: {j.get('passenger_email')}")
                        st.markdown(f"📍 **{orig}** ➔ **{dest}**")
                    with c2:
                        st.markdown(f"**{svc.get('mode', 'TRAIN')}**: {svc.get('service_number', '')}")
                        st.caption(f"Operator: {svc.get('provider', '')}")
                        st.markdown(f"Status: :{status_color}[**{status}**]")
                    with c3:
                        st.metric("Fare", f"₹{j.get('booked_fare_inr', 0):,.0f}")
                        if status != "CONFIRMED":
                            if st.button("Recover Journey 🚀", key=f"rec_btn_{j.get('journey_id')}", use_container_width=True):
                                st.session_state["selected_recovery_journey"] = j
                                st.session_state["page_selector"] = "🧭 Recovery Results"
                                st.rerun()

    with col_right:
        st.subheader("🚨 Corridor Travel Alerts")
        if not disruptions:
            st.info("No active corridor travel alerts.")
        else:
            for d in disruptions:
                with st.container(border=True):
                    st.markdown(f"**⚠️ {d.get('headline')}**")
                    st.write(d.get("description"))
                    st.caption(
                        f"Route: {d.get('affected_origin')} ➔ {d.get('affected_destination')} | "
                        f"Mode: {d.get('mode')} | Severity: `{d.get('severity')}`"
                    )

        st.subheader("⚙️ Monitoring Daemon")
        with st.container(border=True):
            st.write(f"**Polling Frequency**: Every `{mon_status.get('poll_interval_seconds', 60)}`s (Demo: `{mon_status.get('demo_poll_interval_seconds', 5)}`s)")
            st.write(f"**Delay Threshold**: `{mon_status.get('qualifying_delay_threshold_minutes', 60)}` minutes")
            st.write(f"**Active Status Overrides**: `{mon_status.get('active_overrides_count', 0)}`")
            st.caption("Autonomous DisruptionMonitorAgent actively checks SQLite journey statuses.")


# -----------------------------------------------------------------------------
# PAGE 2: JOURNEY REGISTRATION
# -----------------------------------------------------------------------------
elif page == "📝 Journey Registration":
    st.title("📝 Register New Journey")
    st.caption("Submit a passenger journey for autonomous monitoring and recovery coordination.")

    locations = api_client.list_locations()
    city_names = sorted(list(set([loc["city"] for loc in locations]))) if locations else ["Delhi", "Jaipur", "Chandigarh", "Agra"]

    with st.form("journey_registration_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Passenger Information")
            p_name = st.text_input("Passenger Full Name", value="Aarav Mehta")
            p_email = st.text_input("Contact Email", value="aarav.mehta@example.com")
            pnr = st.text_input("Booking Reference / PNR (Optional)", placeholder="Leave blank to auto-generate")
            init_status = st.selectbox("Initial Booking Status", options=["CONFIRMED", "WAITLISTED", "RAC"], index=0)

        with col2:
            st.subheader("Journey & Transit Corridor")
            orig = st.selectbox("Origin City", options=city_names, index=0)
            dest_candidates = [c for c in city_names if c != orig]
            dest = st.selectbox("Destination City", options=dest_candidates, index=0)
            j_date = st.date_input("Travel Date", value=date.today())
            fare = st.number_input("Fare Paid (INR)", min_value=100.0, max_value=20000.0, value=1250.0, step=50.0)

        st.markdown("---")
        st.subheader("Autonomous Recovery Constraints")
        rc1, rc2, rc3 = st.columns(3)
        with rc1:
            max_budget = st.number_input("Maximum Budget Ceiling (INR)", min_value=500.0, max_value=25000.0, value=3500.0, step=100.0)
        with rc2:
            arrival_deadline = st.text_input("Arrival Deadline (e.g. 15:30 or 21:00)", value="18:00")
        with rc3:
            max_transfers = st.selectbox("Transfer Preferences", options=[0, 1, 2], format_func=lambda x: f"{x} Transfers ({'Direct only' if x == 0 else 'Multimodal allowed' if x > 0 else ''})", index=1)

        submitted = st.form_submit_button("Register & Activate Autonomous Monitoring 🚀", use_container_width=True)

        if submitted:
            if not p_name.strip():
                st.error("Please enter passenger name.")
            else:
                payload = {
                    "passenger_name": p_name.strip(),
                    "passenger_email": p_email.strip(),
                    "origin": orig,
                    "destination": dest,
                    "journey_date": str(j_date),
                    "booking_reference": pnr.strip() if pnr.strip() else None,
                    "booking_status": init_status,
                    "fare_inr": fare,
                    "max_budget": max_budget,
                    "arrival_deadline": arrival_deadline.strip() if arrival_deadline.strip() else None,
                    "max_transfers": max_transfers,
                }
                with st.spinner("Registering journey with backend gateway..."):
                    try:
                        registered = api_client.register_journey(payload)
                        st.success(f"🎉 Journey `{registered.get('journey_id')}` registered successfully!")
                        st.json(registered)
                        st.info("DisruptionMonitorAgent has started tracking this booking reference.")
                    except Exception as e:
                        st.error(f"Failed to register journey: {e}")


# -----------------------------------------------------------------------------
# PAGE 3: AGENT ACTIVITY
# -----------------------------------------------------------------------------
elif page == "🤖 Agent Activity":
    st.title("🤖 Multi-Agent Execution & Audit Log")
    st.caption("Live timeline of uAgents inter-agent messaging, search dispatches, disruption triggers, and ranking decisions.")

    col_btn, col_filter = st.columns([1, 3])
    with col_btn:
        if st.button("🔄 Refresh Logs", use_container_width=True):
            st.rerun()
    with col_filter:
        agent_filter = st.selectbox(
            "Filter by Agent",
            options=["ALL", "RecoveryPlannerAgent", "DisruptionMonitorAgent", "ModalSearchAgents", "PassengerGateway", "BookingHandoffAgent", "DisruptionSimulator", "SystemSupervisor"],
            index=0,
        )

    activity_logs = api_client.get_agent_activity(limit=100)

    filtered_logs = [
        log for log in activity_logs
        if agent_filter == "ALL" or log.get("agent_name") == agent_filter
    ]

    if not filtered_logs:
        st.info("No agent activity found matching the selected filter. Trigger a disruption or register a journey to generate agent logs.")
    else:
        st.write(f"Showing **{len(filtered_logs)}** verified multi-agent operations:")
        for log in filtered_logs:
            agent = log.get("agent_name", "UnknownAgent")
            action = log.get("action", "")
            event_type = log.get("event_type", "")
            ts = log.get("timestamp", "")
            details = log.get("details", {})

            badge_color = "blue"
            if "Monitor" in agent or "Disruption" in agent:
                badge_color = "red"
            elif "Planner" in agent:
                badge_color = "violet"
            elif "Booking" in agent:
                badge_color = "green"

            with st.container(border=True):
                r1, r2 = st.columns([3, 1])
                with r1:
                    st.markdown(f":{badge_color}[**{agent}**] ➔ **{action}**")
                    st.caption(f"Event: `{event_type}` | Timestamp: `{ts}`")
                with r2:
                    st.markdown(f"Log ID: `#{log.get('log_id')}`")

                with st.expander("🔍 View Message Payload & Correlation Details"):
                    st.json(details)


# -----------------------------------------------------------------------------
# PAGE 4: RECOVERY RESULTS
# -----------------------------------------------------------------------------
elif page == "🧭 Recovery Results":
    st.title("🧭 Intelligent Recovery Recommendations")
    st.caption("Multimodal route optimization, constraint validation, and deterministic utility ranking.")

    # Check if a journey was pre-selected from Dashboard
    preselected = st.session_state.get("selected_recovery_journey")
    locations = api_client.list_locations()
    city_names = sorted(list(set([loc["city"] for loc in locations]))) if locations else ["Delhi", "Jaipur", "Chandigarh", "Agra"]

    # Tabs for Structured vs Conversational
    tab_structured, tab_conversational = st.tabs(["⚡ Structured Recovery Planner", "💬 ASI:One Conversational Assistant"])

    with tab_structured:
        with st.container(border=True):
            st.subheader("Travel Recovery Request Parameters")
            c1, c2, c3 = st.columns(3)
            with c1:
                default_orig_idx = 0
                if preselected:
                    orig_cand = preselected.get("booked_service", {}).get("origin", {}).get("city")
                    if orig_cand in city_names:
                        default_orig_idx = city_names.index(orig_cand)
                rec_orig = st.selectbox("Origin", options=city_names, index=default_orig_idx, key="rec_orig_sel")
            with c2:
                dest_cand = [c for c in city_names if c != rec_orig]
                default_dest_idx = 0
                if preselected:
                    d_cand = preselected.get("booked_service", {}).get("destination", {}).get("city")
                    if d_cand in dest_cand:
                        default_dest_idx = dest_cand.index(d_cand)
                rec_dest = st.selectbox("Destination", options=dest_cand, index=default_dest_idx, key="rec_dest_sel")
            with c3:
                rec_budget = st.number_input("Max Budget (INR)", min_value=500.0, max_value=20000.0, value=4500.0, step=100.0)

            c4, c5 = st.columns(2)
            with c4:
                rec_deadline = st.text_input("Arrival Deadline (Optional, e.g. 15:30)", value="18:30")
            with c5:
                rec_transfers = st.selectbox("Max Transfers Allowed", options=[0, 1, 2], index=1)

            run_clicked = st.button("🚀 Calculate Multimodal Recovery Alternatives", use_container_width=True)

        if run_clicked or (preselected and st.session_state.get("last_recovery_plan") is None):
            payload = {
                "origin": rec_orig,
                "destination": rec_dest,
                "max_budget": rec_budget,
                "latest_arrival": rec_deadline if rec_deadline.strip() else None,
                "max_transfers": rec_transfers,
            }
            if preselected:
                payload["journey_id"] = preselected.get("journey_id")

            with st.spinner("Recovery Planner coordinating with Rail, Bus, and Cab agents..."):
                try:
                    plan = api_client.plan_recovery(payload)
                    st.session_state["last_recovery_plan"] = plan
                except Exception as e:
                    st.error(f"Recovery planning failed: {e}")

        # Render Plan if available
        plan = st.session_state.get("last_recovery_plan")
        if plan:
            st.markdown("---")
            m1, m2, m3 = st.columns(3)
            m1.metric("Evaluated Alternatives", plan.get("total_options_evaluated", 0))
            m2.metric("Valid Feasible Options", plan.get("valid_options_count", 0))
            m3.metric("Constraint Violations", plan.get("rejected_options_count", 0))

            top_options = plan.get("top_3_options", [])
            if not top_options:
                st.warning("No feasible recovery alternatives found that satisfy all constraints (budget ceiling, arrival deadline, transfer limits).")
            else:
                st.subheader("🏆 Recommended Recovery Alternative (Option #1)")
                best_opt = top_options[0]
                best_alt = best_opt.get("alternative", {})
                
                with st.container(border=True):
                    b1, b2, b3 = st.columns([3, 2, 2])
                    with b1:
                        st.markdown(f"### #{best_opt.get('rank')} {best_alt.get('mode')} — {best_alt.get('provider')}")
                        st.markdown(f"**Route**: {best_alt.get('origin_name')} ➔ {best_alt.get('destination_name')}")
                        if best_alt.get("transfers_count", 0) > 0 and best_alt.get("legs_summary"):
                            st.info(f"**Multimodal Itinerary**: {best_alt.get('legs_summary')}")
                    with b2:
                        dep = best_alt.get("departure_time", "")[:16].replace("T", " ")
                        arr = best_alt.get("arrival_time", "")[:16].replace("T", " ")
                        st.write(f"**Departure**: `{dep}`")
                        st.write(f"**Arrival**: `{arr}`")
                        st.caption(f"Duration: {best_alt.get('duration_minutes', 0) // 60}h {best_alt.get('duration_minutes', 0) % 60}m | Pattern: `{best_alt.get('journey_pattern', 'DIRECT')}`")
                    with b3:
                        st.metric("Total Fare", f"₹{best_alt.get('fare_inr', 0):,.0f}")
                        st.write(f"Composite Score: **{best_opt.get('composite_score', 0):.1f}/100**")
                        if st.button("Select for Booking Handoff 🎟️", key="btn_select_best", use_container_width=True):
                            st.session_state["handoff_alternative"] = best_alt
                            st.session_state["page_selector"] = "🎟️ Booking Handoff"
                            st.rerun()

                st.markdown("#### 💡 Grounded Planner Explanation")
                st.success(plan.get("best_option_explanation", "Selected based on optimal balance of speed, cost, and reliability."))

                if len(top_options) > 1:
                    st.subheader("🥈 Backup Recovery Alternatives")
                    alt_cols = st.columns(len(top_options) - 1)
                    for idx, opt in enumerate(top_options[1:]):
                        alt_data = opt.get("alternative", {})
                        with alt_cols[idx]:
                            with st.container(border=True):
                                st.markdown(f"#### #{opt.get('rank')} {alt_data.get('mode')} ({alt_data.get('provider')})")
                                st.write(f"**Timing**: {alt_data.get('departure_time', '')[11:16]} ➔ {alt_data.get('arrival_time', '')[11:16]}")
                                st.write(f"**Fare**: ₹{alt_data.get('fare_inr', 0):,.0f} | Duration: {alt_data.get('duration_minutes', 0)}m")
                                st.caption(f"Tradeoffs: *{alt_data.get('tradeoffs', '')}*")
                                if st.button(f"Select Option #{opt.get('rank')}", key=f"btn_alt_{idx}", use_container_width=True):
                                    st.session_state["handoff_alternative"] = alt_data
                                    st.session_state["page_selector"] = "🎟️ Booking Handoff"
                                    st.rerun()

    with tab_conversational:
        st.subheader("Conversational Travel Recovery via ASI:One")
        st.caption("Interact conversationally with our multi-agent recovery system. Powered by ASI:One.")

        user_query = st.text_area(
            "Describe your travel disruption or requirements:",
            value="My train from Delhi to Jaipur TRN-12015 was cancelled. I have a meeting in Jaipur at 3 PM and a budget of 3000 rupees. Find me the best alternative.",
            height=100,
        )

        if st.button("Ask ASI:One Recovery Assistant 💬", use_container_width=True):
            with st.spinner("ASI:One interpreting query and invoking Recovery Planner..."):
                try:
                    chat_resp = api_client.chat_recovery(message=user_query)
                    st.markdown("### 💬 Assistant Response")
                    st.info(chat_resp.get("conversational_reply", "No response returned."))
                    st.caption(f"Provider: {chat_resp.get('provider')}")

                    resp_data = chat_resp.get("recovery_response", {})
                    top_opts = resp_data.get("top_3_options", [])
                    if top_opts:
                        st.markdown("#### Structured Travel Options Grounded in Response:")
                        for opt in top_opts:
                            alt = opt.get("alternative", {})
                            with st.container(border=True):
                                c1, c2, c3 = st.columns([3, 2, 2])
                                with c1:
                                    st.markdown(f"**#{opt.get('rank')} {alt.get('mode')} — {alt.get('provider')}**")
                                    st.caption(f"{alt.get('origin_name')} ➔ {alt.get('destination_name')}")
                                with c2:
                                    st.write(f"Timing: {alt.get('departure_time', '')[11:16]} - {alt.get('arrival_time', '')[11:16]}")
                                    st.write(f"Fare: ₹{alt.get('fare_inr', 0):,.0f}")
                                with c3:
                                    if st.button(f"Select #{opt.get('rank')}", key=f"btn_chat_sel_{opt.get('rank')}", use_container_width=True):
                                        st.session_state["handoff_alternative"] = alt
                                        st.session_state["page_selector"] = "🎟️ Booking Handoff"
                                        st.rerun()
                except Exception as e:
                    st.error(f"ASI:One chat query failed: {e}")


# -----------------------------------------------------------------------------
# PAGE 5: DEMO CONTROLS
# -----------------------------------------------------------------------------
elif page == "🎛️ Demo Controls":
    st.title("🎛️ Disruption Simulation & Demonstration Controls")
    st.caption("Inject travel disruptions into the active booking provider to trigger autonomous multi-agent recovery.")

    journeys = api_client.list_user_journeys()
    journey_ids = [j.get("journey_id") for j in journeys]

    st.subheader("⚡ Quick Demonstration Scenarios (One-Click)")
    sc1, sc2, sc3 = st.columns(3)

    with sc1:
        with st.container(border=True):
            st.markdown("#### 💥 Train Cancellation")
            st.write("**Target**: Rohan Sharma (`JRN-ROHAN-9901`)")
            st.caption("Route: Delhi ➔ Jaipur | TRN-12015 Shatabdi")
            if st.button("Trigger Cancellation", use_container_width=True):
                with st.spinner("Injecting cancellation disruption..."):
                    api_client.inject_disruption({
                        "journey_id": "JRN-ROHAN-9901",
                        "status": "CANCELLED",
                        "reason": "Overhead traction wire snap at Rewari junction",
                    })
                    st.success("Disruption injected! Autonomous recovery triggered.")
                    st.session_state["selected_recovery_journey"] = next((j for j in journeys if j.get("journey_id") == "JRN-ROHAN-9901"), None)
                    st.session_state["page_selector"] = "🧭 Recovery Results"
                    st.rerun()

    with sc2:
        with st.container(border=True):
            st.markdown("#### ⏱️ Severe Train Delay")
            st.write("**Target**: Priya Patel (`JRN-PRIYA-1002`)")
            st.caption("Route: Delhi ➔ Jaipur | TRN-20978 Vande Bharat")
            if st.button("Trigger 120m Delay", use_container_width=True):
                with st.spinner("Injecting 120m delay..."):
                    api_client.inject_disruption({
                        "journey_id": "JRN-PRIYA-1002",
                        "status": "DELAYED",
                        "delay_minutes": 120,
                        "reason": "Signalling interlocking glitch at Gurgaon",
                    })
                    st.success("120-minute qualifying delay injected!")
                    st.session_state["selected_recovery_journey"] = next((j for j in journeys if j.get("journey_id") == "JRN-PRIYA-1002"), None)
                    st.session_state["page_selector"] = "🧭 Recovery Results"
                    st.rerun()

    with sc3:
        with st.container(border=True):
            st.markdown("#### 📉 Waitlist Dropped Post-Chart")
            st.write("**Target**: Neha Gupta (`JRN-NEHA-1004`)")
            st.caption("Route: Delhi ➔ Chandigarh | TRN-12004")
            if st.button("Trigger Chart Drop", use_container_width=True):
                with st.spinner("Injecting charting drop..."):
                    api_client.inject_disruption({
                        "journey_id": "JRN-NEHA-1004",
                        "status": "DROPPED_CHART_PREPARED",
                        "chart_prepared": True,
                        "pnr_position": "DROPPED",
                        "reason": "WL ticket not confirmed upon final chart release",
                    })
                    st.success("Dropped waitlist injected!")
                    st.session_state["selected_recovery_journey"] = next((j for j in journeys if j.get("journey_id") == "JRN-NEHA-1004"), None)
                    st.session_state["page_selector"] = "🧭 Recovery Results"
                    st.rerun()

    st.markdown("---")
    st.subheader("🛠️ Custom Disruption Injection")

    with st.form("custom_disruption_form"):
        col1, col2 = st.columns(2)
        with col1:
            target_journey = st.selectbox("Select Target Journey", options=journey_ids, index=0 if journey_ids else None)
            dis_status = st.selectbox("Injected Status", options=["CANCELLED", "DELAYED", "WAITLISTED", "DROPPED_CHART_PREPARED", "CONFIRMED"])
            reason = st.text_input("Operational Disruption Reason", value="Dense fog causing speed restriction and cancellation")

        with col2:
            delay_mins = st.slider("Delay Duration (Minutes)", min_value=0, max_value=360, value=90, step=15)
            pnr_pos = st.text_input("PNR Position (for Waitlist / RAC)", value="WL 5")
            chart_prep = st.checkbox("Reservation Chart Finalized", value=False)

        inject_btn = st.form_submit_button("Inject Disruption into Provider ⚡", use_container_width=True)

        if inject_btn:
            if not target_journey:
                st.error("No journey selected.")
            else:
                payload = {
                    "journey_id": target_journey,
                    "status": dis_status,
                    "delay_minutes": delay_mins,
                    "reason": reason,
                    "pnr_position": pnr_pos,
                    "chart_prepared": chart_prep,
                }
                try:
                    res = api_client.inject_disruption(payload)
                    st.success(f"Disruption injected: {res.get('message')}")
                    st.session_state["selected_recovery_journey"] = next((j for j in journeys if j.get("journey_id") == target_journey), None)
                except Exception as e:
                    st.error(f"Failed to inject disruption: {e}")


# -----------------------------------------------------------------------------
# PAGE 6: BOOKING HANDOFF
# -----------------------------------------------------------------------------
elif page == "🎟️ Booking Handoff":
    st.title("🎟️ Booking Handoff & Authorization")
    st.caption("Secure transition to transport provider with explicit user consent and safety guardrails.")

    handoff_alt = st.session_state.get("handoff_alternative")

    if not handoff_alt:
        st.warning("No recovery alternative currently selected for booking handoff.")
        st.info("Navigate to 🧭 **Recovery Results** and click 'Select for Booking Handoff' on any recommended option.")
    else:
        st.subheader("Selected Travel Alternative")
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.markdown(f"### {handoff_alt.get('mode')} — {handoff_alt.get('provider')}")
                st.write(f"**Route**: {handoff_alt.get('origin_name')} ➔ {handoff_alt.get('destination_name')}")
                st.caption(f"Service ID: `{handoff_alt.get('service_id')}` | Pattern: `{handoff_alt.get('journey_pattern', 'DIRECT')}`")
            with c2:
                st.write(f"**Departure**: `{handoff_alt.get('departure_time', '')[:16].replace('T', ' ')}`")
                st.write(f"**Arrival**: `{handoff_alt.get('arrival_time', '')[:16].replace('T', ' ')}`")
                st.caption(f"Seat Availability: `{handoff_alt.get('seat_availability')}`")
            with c3:
                st.metric("Total Fare", f"₹{handoff_alt.get('fare_inr', 0):,.0f}")
                if handoff_alt.get("has_estimated_costs"):
                    st.caption("⚠️ Includes estimated on-demand road legs")

        st.markdown("---")
        st.subheader("Official Provider Booking Redirect")
        booking_url = handoff_alt.get("booking_url") or "https://www.irctc.co.in"
        st.write(f"Provider Portal: `{booking_url}`")
        st.link_button("🌐 Open Provider Portal in New Tab", booking_url, use_container_width=True)

        st.markdown("---")
        st.subheader("Explicit User Authorization")
        st.warning(
            "⚠️ **Autonomous Safety Guardrail**: RouteRescue AI strictly requires explicit user approval before "
            "updating journey records or dispatching booking confirmations. No real money is ever debited."
        )

        user_approved = st.checkbox(
            "I explicitly authorize RouteRescue AI to confirm this recovery option on my behalf.",
            value=False,
            key="user_consent_checkbox",
        )

        orig_journey = st.session_state.get("selected_recovery_journey")
        j_id = orig_journey.get("journey_id") if orig_journey else None

        if st.button("Confirm & Record Recovery Booking ✅", disabled=not user_approved, use_container_width=True):
            payload = {
                "journey_id": j_id,
                "alternative_id": handoff_alt.get("alternative_id", "ALT-SELECTED"),
                "service_id": handoff_alt.get("service_id", "UNKNOWN"),
                "provider": handoff_alt.get("provider", "Transit Provider"),
                "booking_url": booking_url,
                "fare_inr": handoff_alt.get("fare_inr", 0.0),
                "user_approved": True,
                "passenger_name": orig_journey.get("passenger_name") if orig_journey else "Passenger",
            }
            with st.spinner("Recording user authorization and updating journey state..."):
                try:
                    approval_res = api_client.approve_booking(payload)
                    st.success("🎉 Booking Handoff Approved and Recorded!")
                    st.json(approval_res)
                    st.balloons()
                except Exception as e:
                    st.error(f"Booking approval failed: {e}")
