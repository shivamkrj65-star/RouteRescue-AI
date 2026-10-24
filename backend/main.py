"""FastAPI backend application for RouteRescue AI."""

from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from data.database import DatabaseManager
from schemas.common import TransportMode
from schemas.disruption import DisruptionEvent
from schemas.search import TransportSearchRequest, TransportSearchResponse
from schemas.travel import Location, TransportService, UserJourney
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
