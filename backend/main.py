"""FastAPI backend application for RouteRescue AI."""

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from data.database import DatabaseManager
from schemas.common import BookingStatus, TransportMode
from schemas.disruption import DisruptionEvent, DisruptionInjectionPayload
from schemas.search import TransportSearchRequest, TransportSearchResponse
from schemas.travel import Location, TransportService, UserJourney
from services.booking_provider import SimulatedBookingProvider
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
