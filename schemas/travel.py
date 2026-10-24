"""Location, transport service, and user journey schemas."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

from config.settings import IST
from schemas.common import BookingStatus, SeatAvailabilityStatus, TransportMode


class Location(BaseModel):
    """Transit node or city location representation."""
    code: str = Field(description="Unique code e.g. NDLS, JP, CDG, AGC")
    name: str = Field(description="Full station or terminal name")
    city: str = Field(description="City e.g. Delhi, Jaipur, Chandigarh, Agra")
    state: str = Field(default="India", description="State or territory")
    latitude: float = Field(description="Latitude coordinate")
    longitude: float = Field(description="Longitude coordinate")
    location_type: str = Field(default="railway_station", description="Type: railway_station, bus_stand, airport, taxi_stand")


class TransportService(BaseModel):
    """An individual transport service (train, bus, cab, flight)."""
    service_id: str = Field(description="Unique service identifier e.g. TRN-12004")
    mode: TransportMode = Field(description="Transport mode e.g. TRAIN, BUS, CAB")
    provider: str = Field(description="Service operating company e.g. Indian Railways, Zingbus, Uber")
    service_number: str = Field(description="Official train number or bus route e.g. 12004 Shatabdi Express")
    origin: Location = Field(description="Service departure location")
    destination: Location = Field(description="Service arrival location")
    departure_time: datetime = Field(description="Timezone-aware departure timestamp")
    arrival_time: datetime = Field(description="Timezone-aware arrival timestamp")
    duration_minutes: int = Field(ge=0, description="Scheduled duration in minutes")
    distance_km: float = Field(ge=0.0, description="Transit distance in kilometers")
    fare_inr: float = Field(ge=0.0, description="Estimated fare in Indian Rupees (INR)")
    seat_availability: SeatAvailabilityStatus = Field(
        default=SeatAvailabilityStatus.AVAILABLE,
        description="Current seat booking availability",
    )
    available_seats_count: Optional[int] = Field(
        default=None,
        description="Exact count of remaining seats if applicable",
    )
    booking_url: Optional[str] = Field(
        default=None,
        description="Direct official booking or provider link",
    )
    is_overnight: bool = Field(
        default=False,
        description="True if journey crosses midnight into the next day",
    )
    is_synthetic: bool = Field(
        default=True,
        description="Indicator that this record is demonstration data",
    )
    data_label: str = Field(
        default="DEMONSTRATION SYNTHETIC DATASET (Fetch-A-Thon 3.0)",
        description="Explicit demonstration label to satisfy data integrity guidelines",
    )


class UserJourney(BaseModel):
    """A passenger's booked or tracked journey subjected to monitoring."""
    journey_id: str = Field(description="Unique passenger trip identifier")
    passenger_name: str = Field(description="Passenger display name")
    passenger_email: str = Field(default="passenger@example.com", description="Contact email")
    booked_service: TransportService = Field(description="The underlying booked transport service")
    booking_status: BookingStatus = Field(
        default=BookingStatus.CONFIRMED,
        description="Current booking status",
    )
    booking_reference: str = Field(description="PNR number or booking confirmation code")
    booked_fare_inr: float = Field(ge=0.0, description="Total fare paid")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(IST),
        description="Timestamp when journey was booked",
    )
    is_synthetic: bool = Field(default=True)
