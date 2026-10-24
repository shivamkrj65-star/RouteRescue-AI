"""FastAPI backend application for RouteRescue AI."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config.settings import IST, settings
from data.database import DatabaseManager
from data.seed_data import seed_database
from schemas.agent_messages import RecoveryRequest, RecoveryResponse
from schemas.common import BookingStatus, TransportMode
from schemas.disruption import DisruptionEvent, DisruptionInjectionPayload
from schemas.search import TransportSearchRequest, TransportSearchResponse
from schemas.travel import Location, TransportService, UserJourney
from services.asione_service import AsiOneService
from services.booking_provider import SimulatedBookingProvider
from services.recovery_engine import RecoveryEngine
from services.transport_service import TransportDataService

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Autonomous Multimodal Travel Disruption Recovery Platform (Fetch-A-Thon 3.0)",
)

# Enable CORS for local Streamlit & frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseManager()
transport_service = TransportDataService(db=db)
booking_provider = SimulatedBookingProvider()
recovery_engine = RecoveryEngine()
asione_service = AsiOneService()


class RecoveryChatPayload(BaseModel):
    message: str = Field(description="Conversational travel query or disruption statement")
    origin: Optional[str] = Field(default=None, description="Optional explicit origin override")
    destination: Optional[str] = Field(default=None, description="Optional explicit destination override")
    max_budget: Optional[float] = Field(default=None, description="Optional explicit budget ceiling override")


class JourneyRegistrationPayload(BaseModel):
    passenger_name: str = Field(description="Passenger full name")
    passenger_email: Optional[str] = Field(default="passenger@example.com", description="Contact email")
    service_id: Optional[str] = Field(default=None, description="Booked service ID (e.g. TRN-12015)")
    origin: str = Field(description="Origin city or transit hub code")
    destination: str = Field(description="Destination city or transit hub code")
    journey_date: Optional[str] = Field(default=None, description="Date of travel (YYYY-MM-DD)")
    booking_reference: Optional[str] = Field(default=None, description="PNR or booking reference")
    booking_status: BookingStatus = Field(default=BookingStatus.CONFIRMED, description="Booking status")
    fare_inr: Optional[float] = Field(default=None, description="Fare in INR")
    max_budget: Optional[float] = Field(default=5000.0, description="Budget ceiling in INR")
    arrival_deadline: Optional[str] = Field(default=None, description="Arrival deadline (HH:MM or ISO timestamp)")
    max_transfers: Optional[int] = Field(default=2, description="Max transfers allowed")


class RecoveryPlanPayload(BaseModel):
    journey_id: Optional[str] = Field(default=None, description="Optional disrupted journey ID")
    origin: str = Field(description="Origin city or transit hub code")
    destination: str = Field(description="Destination city or transit hub code")
    journey_date: Optional[str] = Field(default=None, description="Travel date YYYY-MM-DD")
    earliest_departure: Optional[str] = Field(default=None, description="Earliest allowed departure (HH:MM or ISO timestamp)")
    latest_arrival: Optional[str] = Field(default=None, description="Latest acceptable arrival deadline (HH:MM or ISO timestamp)")
    max_budget: Optional[float] = Field(default=5000.0, description="Budget ceiling in INR")
    max_transfers: int = Field(default=2, description="Maximum transfers permitted (0 for direct only)")


class BookingApprovalPayload(BaseModel):
    journey_id: Optional[str] = Field(default=None, description="Disrupted journey ID if applicable")
    alternative_id: str = Field(description="Selected recovery alternative ID")
    service_id: str = Field(description="Selected transport service ID")
    provider: str = Field(description="Selected operator name")
    booking_url: Optional[str] = Field(default=None, description="Official provider checkout/booking URL")
    fare_inr: float = Field(description="Total booking fare in INR")
    user_approved: bool = Field(description="Explicit user confirmation checkbox")
    passenger_name: Optional[str] = Field(default=None, description="Passenger name")


@app.post("/api/v1/recovery/chat", tags=["ASI:One & Recovery Planner"])
async def recovery_chat(payload: RecoveryChatPayload):
    """
    Conversational travel recovery endpoint powered by ASI:One.
    1. Converts conversational text into a structured RecoveryRequest.
    2. Overrides fields if explicitly provided.
    3. Invokes the core RecoveryEngine (multimodal routing, constraint validation, scoring).
    4. Synthesizes an empathetic, grounded response strictly based on actual options.
    """
    # 1. Parse natural language instruction
    req, used_llm = await asione_service.parse_instruction_to_request(payload.message)

    # 2. Apply explicit overrides if supplied
    if payload.origin:
        req.origin = payload.origin
    if payload.destination:
        req.destination = payload.destination
    if payload.max_budget is not None:
        req.max_budget = payload.max_budget

    # 3. Execute recovery planning workflow
    recovery_resp = recovery_engine.process_recovery(
        modal_results={},
        request=req,
        planner_address="http://127.0.0.1:8004/submit",
    )

    # 4. Generate grounded natural-language response
    conversational_reply, reply_used_llm = await asione_service.generate_grounded_response(
        request=req,
        response=recovery_resp,
        user_message=payload.message,
    )

    return {
        "success": True,
        "query": payload.message,
        "parsed_request": req.dict() if hasattr(req, "dict") else req.model_dump(),
        "recovery_response": recovery_resp.dict() if hasattr(recovery_resp, "dict") else recovery_resp.model_dump(),
        "conversational_reply": conversational_reply,
        "used_llm": used_llm or reply_used_llm,
        "provider": "ASI:One (asi1-mini)" if (used_llm or reply_used_llm) else "RouteRescue NLP Engine (Deterministic Fallback)",
    }


@app.get("/", tags=["System"])
def root():
    """Root endpoint welcoming users and directing to interactive documentation."""
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "status": "online",
        "docs_url": "http://127.0.0.1:8000/docs",
        "health_check": "http://127.0.0.1:8000/health",
        "streamlit_dashboard": "http://localhost:8501",
        "message": "RouteRescue AI Backend is running. Visit /docs for interactive Swagger API UI.",
    }


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint confirming system status and synthetic demonstration mode."""
    return {
        "status": "online",
        "app_name": settings.app_name,
        "version": settings.version,
        "is_demo_mode": settings.is_demo_mode,
        "corridor": settings.corridor_region,
        "data_label": settings.synthetic_label,
    }


@app.get("/api/v1/locations", response_model=List[Location], tags=["Transit Network"])
def get_locations():
    """Returns all registered transit hub locations in Delhi, Jaipur, Chandigarh, Agra."""
    return db.list_all_locations()


@app.post("/api/v1/search", response_model=TransportSearchResponse, tags=["Transport Search"])
def search_transport(request: TransportSearchRequest):
    """
    Multimodal transport search endpoint.
    Filters by origin, destination, time of day, travel date, budget cap, mode, and seat availability.
    """
    return transport_service.search_transport(request)


@app.get("/api/v1/disruptions", response_model=List[DisruptionEvent], tags=["Disruptions"])
def get_disruptions(
    mode: Optional[TransportMode] = Query(default=None, description="Filter by transport mode"),
    city: Optional[str] = Query(default=None, description="Filter by station or city"),
):
    """Returns all active travel disruption incidents."""
    return transport_service.list_active_disruptions(station_or_city=city, mode=mode)


@app.get("/api/v1/services/{service_id}", response_model=TransportService, tags=["Transit Network"])
def get_service_details(service_id: str):
    """Retrieves full specifications for a transport service."""
    service = transport_service.get_service_details(service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found.")
    return service


@app.get("/api/v1/journeys/{journey_id}", response_model=UserJourney, tags=["User Journeys"])
def get_user_journey(journey_id: str):
    """Retrieves a passenger's booked journey by journey_id."""
    journey = db.get_user_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail=f"User journey '{journey_id}' not found.")
    return journey


@app.get("/api/v1/journeys", response_model=List[UserJourney], tags=["User Journeys"])
def list_user_journeys():
    """Lists all active and monitored passenger journeys."""
    return db.list_all_user_journeys()


@app.post("/api/v1/disruptions/inject", tags=["Disruptions & Monitoring"])
def inject_disruption(payload: DisruptionInjectionPayload):
    """
    Injects a demonstration disruption into the simulated booking provider.
    Can cancel, delay, waitlist, or drop a passenger journey after charting.
    """
    journey = db.get_user_journey(payload.journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail=f"Journey '{payload.journey_id}' not found.")

    sim_status = booking_provider.inject_disruption(payload)
    db.update_journey_status(payload.journey_id, sim_status.status)
    db.log_monitoring_event(
        event_type="DISRUPTION_INJECTED_VIA_API",
        details={
            "journey_id": payload.journey_id,
            "status": payload.status,
            "delay_minutes": payload.delay_minutes,
            "pnr_position": payload.pnr_position,
            "chart_prepared": payload.chart_prepared,
            "reason": payload.reason,
        },
    )

    return {
        "success": True,
        "message": f"Disruption injected for journey {payload.journey_id}: {payload.status}",
        "simulated_status": sim_status.model_dump(),
    }


@app.get("/api/v1/monitoring/logs", tags=["Disruptions & Monitoring"])
def get_monitoring_logs(limit: int = Query(default=50, ge=1, le=200)):
    """Retrieves recent audit logs of automated monitoring actions and disruption recovery."""
    return db.get_monitoring_logs(limit=limit)


@app.get("/api/v1/monitoring/status", tags=["Disruptions & Monitoring"])
def get_monitoring_status():
    """Returns the current state of simulated booking status overrides and monitoring settings."""
    return {
        "active_overrides_count": len(booking_provider.list_all_statuses()),
        "overrides": {k: v.model_dump() for k, v in booking_provider.list_all_statuses().items()},
        "poll_interval_seconds": settings.monitor_poll_interval_seconds,
        "demo_poll_interval_seconds": settings.monitor_demo_poll_interval_seconds,
        "qualifying_delay_threshold_minutes": settings.qualifying_delay_threshold_minutes,
    }


@app.post("/api/v1/journeys", response_model=UserJourney, tags=["User Journeys"])
def register_user_journey(payload: JourneyRegistrationPayload):
    """
    Registers a new passenger journey subjected to autonomous disruption monitoring.
    Links to a transport service in the corridor network.
    """
    booked_svc: Optional[TransportService] = None
    if payload.service_id:
        booked_svc = transport_service.get_service_details(payload.service_id)
        if not booked_svc:
            raise HTTPException(status_code=404, detail=f"Service '{payload.service_id}' not found.")
    else:
        orig_codes = transport_service.resolve_location_codes(payload.origin)
        dest_codes = transport_service.resolve_location_codes(payload.destination)
        matching = db.query_services(origin_codes=orig_codes, destination_codes=dest_codes)
        if matching:
            booked_svc = matching[0]
        else:
            all_services = db.get_all_services()
            if not all_services:
                raise HTTPException(status_code=400, detail="No transport services available.")
            booked_svc = all_services[0]

    name_clean = "".join(c for c in payload.passenger_name if c.isalnum()).upper()[:8] or "PASSENGER"
    journey_id = f"JRN-{name_clean}-{uuid.uuid4().hex[:6].upper()}"
    pnr = payload.booking_reference or f"PNR-{uuid.uuid4().hex[:8].upper()}"
    fare = payload.fare_inr if payload.fare_inr is not None else booked_svc.fare_inr

    user_journey = UserJourney(
        journey_id=journey_id,
        passenger_name=payload.passenger_name,
        passenger_email=payload.passenger_email or "passenger@example.com",
        booked_service=booked_svc,
        booking_status=payload.booking_status,
        booking_reference=pnr,
        booked_fare_inr=fare,
        created_at=datetime.now(IST),
        is_synthetic=True,
    )
    db.save_user_journey(user_journey)

    db.log_monitoring_event(
        event_type="JOURNEY_REGISTERED",
        details={
            "journey_id": journey_id,
            "passenger_name": payload.passenger_name,
            "origin": booked_svc.origin.name,
            "destination": booked_svc.destination.name,
            "service_id": booked_svc.service_id,
            "provider": booked_svc.provider,
            "booking_reference": pnr,
            "status": payload.booking_status.value,
            "max_budget": payload.max_budget,
            "arrival_deadline": payload.arrival_deadline,
            "max_transfers": payload.max_transfers,
        },
    )

    return user_journey


@app.post("/api/v1/recovery/plan", tags=["Recovery Planner"])
def plan_recovery(payload: RecoveryPlanPayload):
    """
    Executes multimodal recovery planning: constraint validation, scoring, and ranking.
    """
    req_id = f"REC-REQ-{uuid.uuid4().hex[:8].upper()}"
    recovery_req = RecoveryRequest(
        request_id=req_id,
        origin=payload.origin,
        destination=payload.destination,
        journey_date=payload.journey_date,
        earliest_departure=payload.earliest_departure,
        latest_acceptable_arrival=payload.latest_arrival,
        max_budget=payload.max_budget,
        max_transfers=payload.max_transfers,
        user_id=payload.journey_id,
    )

    db.log_monitoring_event(
        event_type="SEARCH_DISPATCHED",
        details={
            "request_id": req_id,
            "origin": payload.origin,
            "destination": payload.destination,
            "max_budget": payload.max_budget,
            "max_transfers": payload.max_transfers,
            "dispatched_to": ["rail_search_agent", "bus_search_agent", "cab_road_search_agent"],
        },
    )

    recovery_resp = recovery_engine.process_recovery(
        modal_results={},
        request=recovery_req,
        planner_address="agent1q_recovery_planner_agentverse",
    )

    top_option_desc = (
        f"{recovery_resp.top_3_options[0].alternative.mode} - {recovery_resp.top_3_options[0].alternative.service_number}"
        if recovery_resp.top_3_options
        else "NONE"
    )
    db.log_monitoring_event(
        event_type="RECOVERY_PLAN_GENERATED",
        details={
            "request_id": req_id,
            "total_evaluated": recovery_resp.total_options_evaluated,
            "valid_options_count": recovery_resp.valid_options_count,
            "rejected_options_count": recovery_resp.rejected_options_count,
            "top_recommended_option": top_option_desc,
            "best_option_score": recovery_resp.top_3_options[0].composite_score if recovery_resp.top_3_options else 0.0,
        },
    )

    return recovery_resp.model_dump()


def _infer_agent_metadata(event_type: str, details: Dict[str, Any]) -> Tuple[str, str]:
    """Infers agent name and readable action label from audit event."""
    if event_type in ("DISRUPTION_DETECTED", "STATUS_CHECK"):
        return "DisruptionMonitorAgent", f"Detected disruption event for {details.get('journey_id', 'journey')}"
    elif event_type == "DISRUPTION_INJECTED_VIA_API":
        return "DisruptionSimulator", f"Simulated {details.get('status', 'disruption')} on journey {details.get('journey_id', '')}"
    elif event_type == "SEARCH_DISPATCHED":
        return "RecoveryPlannerAgent", f"Dispatched multimodal search queries for {details.get('origin', '')} -> {details.get('destination', '')}"
    elif event_type == "SEARCH_RESULTS_COLLECTED":
        return "ModalSearchAgents", "Collected transport options from Rail, Bus, and Cab agents"
    elif event_type == "RECOVERY_PLAN_GENERATED":
        return "RecoveryPlannerAgent", f"Evaluated {details.get('total_evaluated', 0)} options | Recommended: {details.get('top_recommended_option', 'N/A')}"
    elif event_type == "JOURNEY_REGISTERED":
        return "PassengerGateway", f"Registered new journey {details.get('journey_id', '')} for {details.get('passenger_name', '')}"
    elif event_type == "BOOKING_APPROVED_BY_USER":
        return "BookingHandoffAgent", f"User authorized booking handoff for {details.get('provider', 'provider')} ({details.get('service_id', '')})"
    elif event_type in ("DEMO_RESET", "DATABASE_SEEDED"):
        return "SystemSupervisor", "Demonstration baseline dataset reset and synchronized"
    return "RouteRescueAgent", f"Processed system event: {event_type}"


@app.get("/api/v1/agents/activity", tags=["Agent Activity"])
def get_agent_activity(limit: int = Query(default=50, ge=1, le=200)):
    """
    Returns real agent messaging, search dispatches, disruption triggers,
    and recovery decisions extracted from the persistent SQLite audit log.
    """
    raw_logs = db.get_monitoring_logs(limit=limit)
    activity_items = []
    for item in raw_logs:
        agent_name, action_desc = _infer_agent_metadata(item["event_type"], item["details"])
        activity_items.append({
            "log_id": item["log_id"],
            "timestamp": item["timestamp"],
            "event_type": item["event_type"],
            "agent_name": agent_name,
            "action": action_desc,
            "details": item["details"],
        })
    return activity_items


@app.post("/api/v1/bookings/approve", tags=["Booking Handoff"])
def approve_booking(payload: BookingApprovalPayload):
    """
    Simulates user-authorized booking handoff.
    Requires explicit user approval before marking status and providing checkout URLs.
    No live funds are ever debited.
    """
    if not payload.user_approved:
        raise HTTPException(
            status_code=400,
            detail="User approval required. Please confirm your authorization checkbox to proceed.",
        )

    if payload.journey_id:
        db.update_journey_status(payload.journey_id, BookingStatus.CONFIRMED)

    db.log_monitoring_event(
        event_type="BOOKING_APPROVED_BY_USER",
        details={
            "journey_id": payload.journey_id,
            "alternative_id": payload.alternative_id,
            "service_id": payload.service_id,
            "provider": payload.provider,
            "fare_inr": payload.fare_inr,
            "booking_url": payload.booking_url,
            "passenger_name": payload.passenger_name,
            "user_approved": True,
        },
    )

    return {
        "success": True,
        "status": "APPROVED_BY_USER",
        "message": f"Recovery journey via {payload.provider} approved by user.",
        "booking_url": payload.booking_url or "https://www.irctc.co.in",
        "fare_inr": payload.fare_inr,
        "disclaimer": "DEMONSTRATION HANDOFF: Provider link opened with explicit user approval. Synthetic demonstration mode (Fetch-A-Thon 3.0); no payment debited.",
    }


@app.post("/api/v1/demo/reset", tags=["Demo Controls"])
def reset_demo():
    """
    Resets the demonstration to its initial baseline:
    1. Clears in-memory booking status overrides.
    2. Re-seeds demonstration database (locations, services, baseline journeys, disruptions).
    3. Logs DEMO_RESET event.
    """
    booking_provider.reset_all()
    seed_database(db)
    db.log_monitoring_event(
        event_type="DEMO_RESET",
        details={"status": "Demonstration reset to baseline initial state"},
    )
    return {
        "success": True,
        "message": "Demonstration environment and booking provider reset to initial baseline state.",
    }
