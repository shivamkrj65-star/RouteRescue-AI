"""Realistic synthetic transit corridors, locations, and disruption scenarios.

Covers major UK multimodal corridors:
London (Euston, King's Cross, Heathrow, Victoria Coach)
Birmingham (New Street, Airport, Coach Station)
Manchester (Piccadilly, Airport, Coach Station)
Leeds, Liverpool, and Edinburgh.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from routerescue.schemas.common import (
    DataVerificationStatus,
    DisruptionSeverity,
    DisruptionType,
    TransportMode,
)
from routerescue.schemas.disruption import DisruptionEvent
from routerescue.schemas.travel import Location

# Standard Core Hub Locations
LOCATIONS: Dict[str, Location] = {
    # London
    "EUS": Location(
        code="EUS",
        name="London Euston",
        city="London",
        latitude=51.5281,
        longitude=-0.1336,
        location_type="station",
    ),
    "KGX": Location(
        code="KGX",
        name="London King's Cross",
        city="London",
        latitude=51.5308,
        longitude=-0.1238,
        location_type="station",
    ),
    "VIC": Location(
        code="VIC",
        name="London Victoria Coach Station",
        city="London",
        latitude=51.4925,
        longitude=-0.1478,
        location_type="coach_station",
    ),
    "LHR": Location(
        code="LHR",
        name="London Heathrow Airport",
        city="London",
        latitude=51.4700,
        longitude=-0.4543,
        location_type="airport",
    ),
    # Birmingham
    "BHM": Location(
        code="BHM",
        name="Birmingham New Street",
        city="Birmingham",
        latitude=52.4778,
        longitude=-1.8986,
        location_type="station",
    ),
    "BCS": Location(
        code="BCS",
        name="Birmingham Digbeth Coach Station",
        city="Birmingham",
        latitude=52.4754,
        longitude=-1.8890,
        location_type="coach_station",
    ),
    "BHX": Location(
        code="BHX",
        name="Birmingham Airport",
        city="Birmingham",
        latitude=52.4539,
        longitude=-1.7480,
        location_type="airport",
    ),
    # Manchester
    "MAN": Location(
        code="MAN",
        name="Manchester Piccadilly",
        city="Manchester",
        latitude=53.4774,
        longitude=-2.2309,
        location_type="station",
    ),
    "MCS": Location(
        code="MCS",
        name="Manchester Central Coach Station",
        city="Manchester",
        latitude=53.4789,
        longitude=-2.2383,
        location_type="coach_station",
    ),
    "MAN_AIR": Location(
        code="MAN_AIR",
        name="Manchester Airport",
        city="Manchester",
        latitude=53.3653,
        longitude=-2.2728,
        location_type="airport",
    ),
    # Supporting Hubs (North & Midlands)
    "LDS": Location(
        code="LDS",
        name="Leeds City Station",
        city="Leeds",
        latitude=53.7954,
        longitude=-1.5478,
        location_type="station",
    ),
    "LIV": Location(
        code="LIV",
        name="Liverpool Lime Street",
        city="Liverpool",
        latitude=53.4076,
        longitude=-2.9779,
        location_type="station",
    ),
    "EDB": Location(
        code="EDB",
        name="Edinburgh Waverley",
        city="Edinburgh",
        latitude=55.9520,
        longitude=-3.1899,
        location_type="station",
    ),
}


def get_default_disruption_scenarios(base_time: datetime | None = None) -> List[DisruptionEvent]:
    """Generates benchmark disruption scenarios for testing and demonstration."""
    if base_time is None:
        base_time = datetime.now(timezone.utc)

    return [
        DisruptionEvent(
            event_id="DISR-RAIL-001",
            mode=TransportMode.TRAIN,
            disruption_type=DisruptionType.CANCELLATION,
            severity=DisruptionSeverity.CRITICAL,
            source_reference="NR-INCIDENT-9921",
            operator="Avanti West Coast",
            affected_origin="EUS",
            affected_destination="MAN",
            affected_stations=["EUS", "MKC", "RUG", "COV", "BHM", "SOT", "MAN"],
            delay_minutes=0,
            is_cancelled=True,
            description="Emergency overhead electric wire damage near Rugby. All direct West Coast Main Line trains between London Euston and Manchester Piccadilly are suspended.",
            verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
            reported_at=base_time - timedelta(minutes=15),
            valid_until=base_time + timedelta(hours=6),
        ),
        DisruptionEvent(
            event_id="DISR-AIR-002",
            mode=TransportMode.FLIGHT,
            disruption_type=DisruptionType.AIRPORT_ATC,
            severity=DisruptionSeverity.HIGH,
            source_reference="NATS-FLOW-401",
            operator="British Airways",
            affected_origin="LHR",
            affected_destination="MAN_AIR",
            affected_stations=["LHR", "MAN_AIR"],
            delay_minutes=150,
            is_cancelled=False,
            description="UK NATS Air Traffic Control ground delay program in effect due to London terminal airspace software failure. Domestic shuttle flights delayed over 2.5 hours.",
            verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
            reported_at=base_time - timedelta(minutes=30),
            valid_until=base_time + timedelta(hours=4),
        ),
        DisruptionEvent(
            event_id="DISR-ROAD-003",
            mode=TransportMode.CAB,
            disruption_type=DisruptionType.ROAD_ACCIDENT,
            severity=DisruptionSeverity.MEDIUM,
            source_reference="HE-TRAFFIC-1044",
            operator="National Highways",
            affected_origin="BHM",
            affected_destination="MAN",
            affected_stations=["BHM", "MAN"],
            delay_minutes=45,
            is_cancelled=False,
            description="M6 Northbound lanes 2 and 3 closed between J16 and J17 following multi-vehicle collision. Road travel times increased by 45 minutes.",
            verification_status=DataVerificationStatus.SIMULATED_ESTIMATE,
            reported_at=base_time - timedelta(minutes=10),
            valid_until=base_time + timedelta(hours=2),
        ),
    ]
