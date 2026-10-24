"""Realistic demonstration transit network for Delhi, Jaipur, Chandigarh, Agra, and nearby hubs.

Contains:
- Core geographic locations (Rail, Bus, Airport, Taxi hubs)
- 32 Alternative train services (Shatabdi, Vande Bharat, Rajdhani, Superfast, Overnight)
- 32 Intercity bus services (Zingbus, IntrCity, NueGo Electric, RSRTC Volvo)
- 21 Cab and road connections (Uber Intercity, BluSmart, Savaari, Highway Outstation)
- 10 Realistic simulated disruption scenarios
"""

from datetime import datetime, time, timedelta
from typing import Dict, List, Optional

from config.settings import IST
from schemas.common import (
    DisruptionSeverity,
    DisruptionType,
    SeatAvailabilityStatus,
    TransportMode,
)
from schemas.disruption import DisruptionEvent
from schemas.travel import Location, TransportService

# -----------------------------------------------------------------------------
# 1. Demonstration Transit Hubs & Locations
# -----------------------------------------------------------------------------

DEMO_LOCATIONS: Dict[str, Location] = {
    # Delhi & NCR
    "NDLS": Location(
        code="NDLS",
        name="New Delhi Railway Station",
        city="Delhi",
        state="Delhi",
        latitude=28.6415,
        longitude=77.2194,
        location_type="railway_station",
    ),
    "NZM": Location(
        code="NZM",
        name="Hazrat Nizamuddin Railway Station",
        city="Delhi",
        state="Delhi",
        latitude=28.5888,
        longitude=77.2536,
        location_type="railway_station",
    ),
    "DEL_ISBT": Location(
        code="DEL_ISBT",
        name="Maharana Pratap Inter-State Bus Terminus (Kashmere Gate)",
        city="Delhi",
        state="Delhi",
        latitude=28.6678,
        longitude=77.2291,
        location_type="bus_stand",
    ),
    "DEL_AIR": Location(
        code="DEL_AIR",
        name="Indira Gandhi International Airport (Terminal 3)",
        city="Delhi",
        state="Delhi",
        latitude=28.5562,
        longitude=77.1000,
        location_type="airport",
    ),
    "GGN": Location(
        code="GGN",
        name="Gurugram IFFCO Chowk Transit Hub",
        city="Gurugram",
        state="Haryana",
        latitude=28.4720,
        longitude=77.0725,
        location_type="taxi_stand",
    ),
    "NOI": Location(
        code="NOI",
        name="Noida Botanical Garden Terminal",
        city="Noida",
        state="Uttar Pradesh",
        latitude=28.5645,
        longitude=77.3340,
        location_type="bus_stand",
    ),

    # Jaipur
    "JP": Location(
        code="JP",
        name="Jaipur Junction Railway Station",
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9200,
        longitude=75.7878,
        location_type="railway_station",
    ),
    "JAI_BUS": Location(
        code="JAI_BUS",
        name="Sindhi Camp Central Bus Stand",
        city="Jaipur",
        state="Rajasthan",
        latitude=26.9239,
        longitude=75.8016,
        location_type="bus_stand",
    ),
    "JAI_AIR": Location(
        code="JAI_AIR",
        name="Jaipur International Airport (Sanganer)",
        city="Jaipur",
        state="Rajasthan",
        latitude=26.8289,
        longitude=75.8056,
        location_type="airport",
    ),

    # Chandigarh
    "CDG": Location(
        code="CDG",
        name="Chandigarh Junction Railway Station",
        city="Chandigarh",
        state="Chandigarh",
        latitude=30.7046,
        longitude=76.8277,
        location_type="railway_station",
    ),
    "CDG_BUS": Location(
        code="CDG_BUS",
        name="ISBT Sector 43 Bus Terminal",
        city="Chandigarh",
        state="Chandigarh",
        latitude=30.7200,
        longitude=76.7450,
        location_type="bus_stand",
    ),
    "UMB": Location(
        code="UMB",
        name="Ambala Cantt Junction",
        city="Ambala",
        state="Haryana",
        latitude=30.3606,
        longitude=76.8294,
        location_type="railway_station",
    ),

    # Agra
    "AGC": Location(
        code="AGC",
        name="Agra Cantt Railway Station",
        city="Agra",
        state="Uttar Pradesh",
        latitude=27.1587,
        longitude=77.9908,
        location_type="railway_station",
    ),
    "AGR_BUS": Location(
        code="AGR_BUS",
        name="Idgah Intercity Bus Stand",
        city="Agra",
        state="Uttar Pradesh",
        latitude=27.1630,
        longitude=77.9890,
        location_type="bus_stand",
    ),
    "MTJ": Location(
        code="MTJ",
        name="Mathura Junction",
        city="Mathura",
        state="Uttar Pradesh",
        latitude=27.4924,
        longitude=77.6737,
        location_type="railway_station",
    ),
}


# -----------------------------------------------------------------------------
# 2. Generator for Synthetic Train Services (>= 30 Services)
# -----------------------------------------------------------------------------

def get_synthetic_train_services(base_date: Optional[datetime] = None) -> List[TransportService]:
    """
    Returns 32 realistic train services connecting Delhi, Jaipur, Chandigarh, and Agra.
    Includes express trains, Shatabdis, Vande Bharats, and overnight sleepers.
    """
    if base_date is None:
        base_date = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)

    train_specs = [
        # (ID, Number, Name, Origin, Dest, DepHour, DepMin, DurMin, DistKm, Fare, Seats, Status, IsOvernight)
        # Delhi <-> Jaipur
        ("TRN-12015", "12015", "Ajmer Shatabdi Express", "NDLS", "JP", 6, 10, 280, 308.0, 940.0, 48, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-20978", "20978", "Ajmer Vande Bharat Express", "NDLS", "JP", 6, 20, 235, 308.0, 1250.0, 32, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12958", "12958", "Swarna Jayanti Rajdhani", "NDLS", "JP", 19, 55, 270, 308.0, 1420.0, 18, SeatAvailabilityStatus.FEW_SEATS, False),
        ("TRN-14321", "14321", "Bareilly-Bhuj Express", "NDLS", "JP", 11, 40, 320, 308.0, 385.0, 0, SeatAvailabilityStatus.WAITLISTED, False),
        ("TRN-12414", "12414", "Pooja Superfast Express", "NDLS", "JP", 22, 10, 310, 308.0, 420.0, 65, SeatAvailabilityStatus.AVAILABLE, True),
        ("TRN-12413", "12413", "Pooja Superfast Express", "JP", "NDLS", 23, 15, 315, 308.0, 420.0, 52, SeatAvailabilityStatus.AVAILABLE, True),
        ("TRN-12016", "12016", "New Delhi Shatabdi Express", "JP", "NDLS", 17, 40, 280, 308.0, 940.0, 25, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-20977", "20977", "Delhi Vande Bharat Express", "JP", "NDLS", 18, 45, 235, 308.0, 1250.0, 14, SeatAvailabilityStatus.FEW_SEATS, False),
        ("TRN-12957", "12957", "New Delhi Rajdhani Express", "JP", "NDLS", 2, 45, 265, 308.0, 1420.0, 20, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-22996", "22996", "Mandore Superfast Express", "JP", "NDLS", 1, 20, 290, 308.0, 410.0, 12, SeatAvailabilityStatus.RAC, False),

        # Delhi <-> Chandigarh
        ("TRN-12011", "12011", "Kalka Shatabdi Express", "NDLS", "CDG", 7, 40, 205, 244.0, 830.0, 60, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12005", "12005", "Kalka Shatabdi (Evening)", "NDLS", "CDG", 17, 15, 205, 244.0, 830.0, 44, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-22447", "22447", "Vande Bharat Express", "NDLS", "CDG", 5, 50, 180, 244.0, 1150.0, 35, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12057", "12057", "Jan Shatabdi Express", "NDLS", "CDG", 14, 35, 245, 244.0, 420.0, 80, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-14095", "14095", "Himalayan Queen", "NDLS", "CDG", 5, 35, 280, 244.0, 310.0, 22, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12012", "12012", "New Delhi Shatabdi Express", "CDG", "NDLS", 18, 20, 205, 244.0, 830.0, 50, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12006", "12006", "New Delhi Shatabdi (Morning)", "CDG", "NDLS", 6, 50, 205, 244.0, 830.0, 42, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-22448", "22448", "New Delhi Vande Bharat", "CDG", "NDLS", 15, 15, 180, 244.0, 1150.0, 18, SeatAvailabilityStatus.FEW_SEATS, False),
        ("TRN-12058", "12058", "Jan Shatabdi Express", "CDG", "NDLS", 7, 45, 245, 244.0, 420.0, 75, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12412", "12412", "Chandigarh Intercity Express", "CDG", "NDLS", 17, 0, 270, 244.0, 330.0, 10, SeatAvailabilityStatus.RAC, False),

        # Delhi <-> Agra
        ("TRN-12050", "12050", "Gatimaan Superfast Express", "NZM", "AGC", 8, 10, 100, 188.0, 750.0, 90, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12002", "12002", "Bhopal Shatabdi Express", "NDLS", "AGC", 6, 0, 115, 195.0, 680.0, 72, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-22436", "22436", "Vande Bharat Express", "NDLS", "AGC", 6, 0, 105, 195.0, 980.0, 40, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12280", "12280", "Taj Express", "NDLS", "AGC", 7, 5, 175, 195.0, 290.0, 110, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12418", "12418", "Prayagraj Express (Overnight)", "NDLS", "AGC", 22, 10, 160, 195.0, 480.0, 38, SeatAvailabilityStatus.AVAILABLE, True),
        ("TRN-12049", "12049", "Gatimaan Express", "AGC", "NZM", 17, 45, 100, 188.0, 750.0, 85, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12001", "12001", "Bhopal Shatabdi", "AGC", "NDLS", 21, 15, 120, 195.0, 680.0, 58, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12279", "12279", "Taj Express", "AGC", "NDLS", 18, 20, 175, 195.0, 290.0, 95, SeatAvailabilityStatus.AVAILABLE, False),

        # Jaipur <-> Agra & Chandigarh <-> Jaipur Connectors
        ("TRN-12988", "12988", "Ajmer-Sealdah Express", "JP", "AGC", 14, 40, 270, 241.0, 380.0, 45, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-12987", "12987", "Sealdah-Ajmer Express", "AGC", "JP", 8, 15, 275, 241.0, 380.0, 50, SeatAvailabilityStatus.AVAILABLE, False),
        ("TRN-14660", "14660", "Chandigarh-Barmer Express (Overnight)", "CDG", "JP", 21, 45, 545, 520.0, 620.0, 30, SeatAvailabilityStatus.AVAILABLE, True),
        ("TRN-14659", "14659", "Barmer-Chandigarh Express (Overnight)", "JP", "CDG", 23, 10, 540, 520.0, 620.0, 28, SeatAvailabilityStatus.AVAILABLE, True),
    ]

    services: List[TransportService] = []
    for spec in train_specs:
        (
            s_id,
            num,
            name,
            orig_c,
            dest_c,
            dep_h,
            dep_m,
            dur_m,
            dist,
            fare,
            seats,
            status,
            is_overnight,
        ) = spec

        dep_dt = base_date.replace(hour=dep_h, minute=dep_m)
        arr_dt = dep_dt + timedelta(minutes=dur_m)
        calculated_overnight = arr_dt.date() > dep_dt.date()

        services.append(
            TransportService(
                service_id=s_id,
                mode=TransportMode.TRAIN,
                provider="Indian Railways / IRCTC",
                service_number=f"{num} {name}",
                origin=DEMO_LOCATIONS[orig_c],
                destination=DEMO_LOCATIONS[dest_c],
                departure_time=dep_dt,
                arrival_time=arr_dt,
                duration_minutes=dur_m,
                distance_km=dist,
                fare_inr=fare,
                seat_availability=status,
                available_seats_count=seats,
                booking_url=f"https://www.irctc.co.in/nget/booking?trainNo={num}",
                is_overnight=calculated_overnight,
            )
        )

    return services


# -----------------------------------------------------------------------------
# 3. Generator for Synthetic Intercity Bus Services (>= 30 Services)
# -----------------------------------------------------------------------------

def get_synthetic_bus_services(base_date: Optional[datetime] = None) -> List[TransportService]:
    """
    Returns 32 realistic intercity bus services across Delhi, Jaipur, Chandigarh, and Agra.
    Includes Volvo 9600s, NueGo Electric AC, and overnight sleeper coaches.
    """
    if base_date is None:
        base_date = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)

    bus_specs = [
        # (ID, Provider, RouteName, Origin, Dest, DepHour, DepMin, DurMin, DistKm, Fare, Seats, Status, IsOvernight)
        # Delhi <-> Jaipur
        ("BUS-ZB-101", "Zingbus Electric", "Premium AC Seater (Volvo 9600)", "DEL_ISBT", "JAI_BUS", 6, 0, 310, 290.0, 550.0, 24, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-102", "Zingbus", "AC Sleeper 2+1", "DEL_ISBT", "JAI_BUS", 8, 30, 330, 290.0, 720.0, 18, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-INT-201", "IntrCity SmartBus", "Smart AC Seater Express", "DEL_ISBT", "JAI_BUS", 11, 0, 320, 290.0, 580.0, 30, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-NUE-301", "NueGo Electric", "Green Eco Express", "DEL_ISBT", "JAI_BUS", 14, 0, 315, 290.0, 520.0, 35, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-RSR-401", "RSRTC Volvo", "Rajasthan Gold Line", "DEL_ISBT", "JAI_BUS", 16, 30, 330, 290.0, 650.0, 20, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-103", "Zingbus Overnight", "Luxury Multi-Axle Sleeper", "DEL_ISBT", "JAI_BUS", 23, 0, 330, 290.0, 850.0, 12, SeatAvailabilityStatus.AVAILABLE, True),
        ("BUS-INT-202", "IntrCity SmartBus", "Overnight Smart Sleeper", "DEL_ISBT", "JAI_BUS", 23, 45, 345, 290.0, 890.0, 8, SeatAvailabilityStatus.FEW_SEATS, True),
        ("BUS-ZB-104", "Zingbus", "AC Seater Return", "JAI_BUS", "DEL_ISBT", 7, 0, 315, 290.0, 550.0, 28, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-NUE-302", "NueGo Electric", "Green Eco Return", "JAI_BUS", "DEL_ISBT", 12, 30, 315, 290.0, 520.0, 32, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-RSR-402", "RSRTC Volvo", "Rajasthan Gold Return", "JAI_BUS", "DEL_ISBT", 17, 0, 330, 290.0, 650.0, 22, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-105", "Zingbus Overnight", "Overnight Multi-Axle Sleeper", "JAI_BUS", "DEL_ISBT", 23, 15, 330, 290.0, 850.0, 15, SeatAvailabilityStatus.AVAILABLE, True),

        # Delhi <-> Chandigarh
        ("BUS-HR-501", "Haryana Roadways Volvo", "Super Luxury AC Express", "DEL_ISBT", "CDG_BUS", 6, 30, 270, 250.0, 680.0, 25, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-106", "Zingbus", "Premium AC Volvo", "DEL_ISBT", "CDG_BUS", 9, 0, 260, 250.0, 590.0, 30, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-INT-203", "IntrCity SmartBus", "Smart Lounge Express", "DEL_ISBT", "CDG_BUS", 12, 30, 265, 250.0, 620.0, 22, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-NUE-303", "NueGo Electric", "Green Electric Highway", "DEL_ISBT", "CDG_BUS", 15, 0, 270, 250.0, 540.0, 36, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-107", "Zingbus Overnight", "Luxury AC Sleeper", "DEL_ISBT", "CDG_BUS", 23, 30, 280, 250.0, 780.0, 14, SeatAvailabilityStatus.AVAILABLE, True),
        ("BUS-HR-502", "Haryana Roadways Volvo", "Super Luxury Return", "CDG_BUS", "DEL_ISBT", 7, 15, 270, 250.0, 680.0, 26, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-108", "Zingbus", "Premium AC Return", "CDG_BUS", "DEL_ISBT", 10, 0, 260, 250.0, 590.0, 28, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-INT-204", "IntrCity SmartBus", "Smart Lounge Return", "CDG_BUS", "DEL_ISBT", 14, 0, 265, 250.0, 620.0, 20, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-109", "Zingbus Overnight", "Overnight Sleeper Return", "CDG_BUS", "DEL_ISBT", 23, 15, 280, 250.0, 780.0, 16, SeatAvailabilityStatus.AVAILABLE, True),

        # Delhi <-> Agra
        ("BUS-UP-601", "UPSRTC Janrath", "Express AC Service", "DEL_ISBT", "AGR_BUS", 6, 45, 210, 210.0, 380.0, 38, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-110", "Zingbus", "Yamuna Expressway Volvo", "DEL_ISBT", "AGR_BUS", 8, 30, 195, 210.0, 480.0, 25, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-INT-205", "IntrCity SmartBus", "Taj Express SmartBus", "DEL_ISBT", "AGR_BUS", 11, 15, 195, 210.0, 510.0, 22, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-111", "Zingbus", "Afternoon Express", "DEL_ISBT", "AGR_BUS", 15, 30, 200, 210.0, 480.0, 30, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-UP-602", "UPSRTC Janrath", "Evening Janrath", "DEL_ISBT", "AGR_BUS", 19, 0, 210, 210.0, 380.0, 35, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-112", "Zingbus", "Morning Taj Return", "AGR_BUS", "DEL_ISBT", 7, 30, 195, 210.0, 480.0, 26, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-UP-603", "UPSRTC Janrath", "Day Express Return", "AGR_BUS", "DEL_ISBT", 11, 0, 210, 210.0, 380.0, 40, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-INT-206", "IntrCity SmartBus", "Smart Lounge Return", "AGR_BUS", "DEL_ISBT", 16, 0, 195, 210.0, 510.0, 24, SeatAvailabilityStatus.AVAILABLE, False),

        # Jaipur <-> Agra & Chandigarh <-> Jaipur
        ("BUS-RSR-403", "RSRTC Express", "Jaipur-Agra Goldline", "JAI_BUS", "AGR_BUS", 6, 15, 330, 240.0, 460.0, 30, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-UP-604", "UPSRTC Express", "Agra-Jaipur Connector", "AGR_BUS", "JAI_BUS", 14, 0, 330, 240.0, 460.0, 28, SeatAvailabilityStatus.AVAILABLE, False),
        ("BUS-ZB-113", "Zingbus Overnight", "Chandigarh-Jaipur Sleeper", "CDG_BUS", "JAI_BUS", 21, 30, 570, 510.0, 1150.0, 14, SeatAvailabilityStatus.AVAILABLE, True),
        ("BUS-ZB-114", "Zingbus Overnight", "Jaipur-Chandigarh Sleeper", "JAI_BUS", "CDG_BUS", 21, 45, 570, 510.0, 1150.0, 12, SeatAvailabilityStatus.AVAILABLE, True),
    ]

    services: List[TransportService] = []
    for spec in bus_specs:
        (
            s_id,
            prov,
            r_name,
            orig_c,
            dest_c,
            dep_h,
            dep_m,
            dur_m,
            dist,
            fare,
            seats,
            status,
            is_overnight,
        ) = spec

        dep_dt = base_date.replace(hour=dep_h, minute=dep_m)
        arr_dt = dep_dt + timedelta(minutes=dur_m)
        calculated_overnight = arr_dt.date() > dep_dt.date()

        services.append(
            TransportService(
                service_id=s_id,
                mode=TransportMode.BUS,
                provider=prov,
                service_number=r_name,
                origin=DEMO_LOCATIONS[orig_c],
                destination=DEMO_LOCATIONS[dest_c],
                departure_time=dep_dt,
                arrival_time=arr_dt,
                duration_minutes=dur_m,
                distance_km=dist,
                fare_inr=fare,
                seat_availability=status,
                available_seats_count=seats,
                booking_url=f"https://www.redbus.in/bus-tickets?route={s_id}",
                is_overnight=calculated_overnight,
            )
        )

    return services


# -----------------------------------------------------------------------------
# 4. Generator for Synthetic Cab & Road Connections (>= 20 Services)
# -----------------------------------------------------------------------------

def get_synthetic_cab_services(base_date: Optional[datetime] = None) -> List[TransportService]:
    """
    Returns 21 on-demand and scheduled highway cab connections across the corridor.
    Includes Uber Intercity, BluSmart, Savaari, and inter-terminal transfers.
    """
    if base_date is None:
        base_date = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)

    cab_specs = [
        # (ID, Provider, ServiceName, Origin, Dest, DepHour, DepMin, DurMin, DistKm, Fare, Seats, Status)
        # Highway Outstations
        ("CAB-UBR-01", "Uber Intercity", "Sedan (Dzire / Etios)", "NDLS", "JP", 7, 0, 260, 280.0, 3450.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-UBR-02", "Uber Intercity SUV", "Innova Crysta Highway", "NDLS", "JP", 10, 30, 250, 280.0, 5200.0, 6, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-BLU-03", "BluSmart Intercity", "All-Electric Highway EV", "GGN", "JP", 8, 0, 230, 255.0, 3100.0, 4, SeatAvailabilityStatus.AVAILABLE),
        ("CAB-SAV-04", "Savaari Car Rentals", "Dedicated Chauffeur Sedan", "JP", "NDLS", 14, 0, 260, 280.0, 3600.0, 4, SeatAvailabilityStatus.AVAILABLE),
        ("CAB-UBR-05", "Uber Intercity", "Direct GT Road Sedan", "NDLS", "CDG", 6, 30, 230, 245.0, 3200.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-UBR-06", "Uber Intercity SUV", "Innova Highway Cruiser", "NDLS", "CDG", 11, 0, 220, 245.0, 4850.0, 6, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-SAV-07", "Savaari Car Rentals", "One-Way Highway Cab", "CDG", "NDLS", 16, 0, 230, 245.0, 3350.0, 4, SeatAvailabilityStatus.AVAILABLE),
        ("CAB-BLU-08", "BluSmart Intercity", "Express EV Taj Corridor", "NOI", "AGC", 7, 30, 160, 185.0, 2650.0, 4, SeatAvailabilityStatus.AVAILABLE),
        ("CAB-UBR-09", "Uber Intercity", "Yamuna Expressway Sedan", "NDLS", "AGC", 9, 0, 180, 205.0, 2850.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-UBR-10", "Uber Intercity SUV", "Yamuna Expressway Innova", "NDLS", "AGC", 13, 0, 170, 205.0, 4400.0, 6, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-SAV-11", "Savaari Car Rentals", "Taj Express Return", "AGC", "NDLS", 17, 30, 180, 205.0, 2900.0, 4, SeatAvailabilityStatus.AVAILABLE),

        # Airport & Inter-Hub Connectors
        ("CAB-AIR-12", "Mega Cabs Airport", "Delhi IGI to Agra Express", "DEL_AIR", "AGC", 8, 30, 185, 215.0, 3100.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-AIR-13", "Uber Intercity", "Delhi IGI to Jaipur Express", "DEL_AIR", "JP", 10, 0, 245, 270.0, 3600.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-HUB-14", "BluSmart City", "New Delhi Station to Kashmere Gate", "NDLS", "DEL_ISBT", 7, 15, 25, 8.5, 220.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-HUB-15", "BluSmart City", "Nizamuddin to New Delhi Station", "NZM", "NDLS", 8, 45, 30, 9.8, 250.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-HUB-16", "City Taxis Jaipur", "Sindhi Camp Bus to Railway Station", "JAI_BUS", "JP", 9, 0, 15, 2.8, 120.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-HUB-17", "Chandigarh Radio Cabs", "ISBT 43 to Chandigarh Railway Station", "CDG_BUS", "CDG", 11, 30, 20, 8.2, 190.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-HUB-18", "Agra Tourist Cabs", "Idgah Bus Stand to Agra Cantt", "AGR_BUS", "AGC", 12, 0, 12, 3.1, 130.0, 4, SeatAvailabilityStatus.ON_DEMAND),

        # Cross-Corridor Road Links
        ("CAB-INT-19", "Savaari Car Rentals", "Jaipur to Agra Direct Highway Cab", "JP", "AGC", 8, 0, 260, 240.0, 3400.0, 4, SeatAvailabilityStatus.AVAILABLE),
        ("CAB-INT-20", "Uber Intercity", "Agra to Jaipur Highway Sedan", "AGC", "JP", 14, 30, 260, 240.0, 3400.0, 4, SeatAvailabilityStatus.ON_DEMAND),
        ("CAB-INT-21", "Savaari Car Rentals", "Ambala Cantt to Chandigarh Fast Cab", "UMB", "CDG", 9, 15, 50, 48.0, 850.0, 4, SeatAvailabilityStatus.AVAILABLE),
    ]

    services: List[TransportService] = []
    for spec in cab_specs:
        s_id, prov, name, orig_c, dest_c, dep_h, dep_m, dur_m, dist, fare, seats, status = spec
        dep_dt = base_date.replace(hour=dep_h, minute=dep_m)
        arr_dt = dep_dt + timedelta(minutes=dur_m)
        calculated_overnight = arr_dt.date() > dep_dt.date()

        services.append(
            TransportService(
                service_id=s_id,
                mode=TransportMode.CAB,
                provider=prov,
                service_number=name,
                origin=DEMO_LOCATIONS[orig_c],
                destination=DEMO_LOCATIONS[dest_c],
                departure_time=dep_dt,
                arrival_time=arr_dt,
                duration_minutes=dur_m,
                distance_km=dist,
                fare_inr=fare,
                seat_availability=status,
                available_seats_count=seats,
                booking_url=f"https://m.uber.com/looking?service={s_id}",
                is_overnight=calculated_overnight,
            )
        )

    return services


# -----------------------------------------------------------------------------
# 5. Generator for Simulated Disruption Scenarios (10 Scenarios)
# -----------------------------------------------------------------------------

def get_simulated_disruptions(base_time: Optional[datetime] = None) -> List[DisruptionEvent]:
    """
    Returns 10 simulated disruption events across Delhi, Jaipur, Chandigarh, and Agra corridors.
    Includes fog delays, derailments, signal failures, expressway jams, and ATC congestion.
    """
    if base_time is None:
        base_time = datetime.now(IST)

    return [
        DisruptionEvent(
            event_id="DISR-FOG-001",
            mode=TransportMode.TRAIN,
            disruption_type=DisruptionType.FOG_DELAY,
            severity=DisruptionSeverity.CRITICAL,
            source_reference="NR-FOG-2026-101",
            operator="Northern Railway",
            affected_origin="NDLS",
            affected_destination="AGC",
            affected_stations=["NDLS", "NZM", "MTJ", "AGC"],
            delay_minutes=180,
            is_cancelled=False,
            headline="Dense Winter Fog Halts Express Trains on Delhi-Agra Corridor",
            description="Visibility dropped below 50 meters between Mathura and Agra Cantt. Speed restrictions of 30 km/h enforced, delaying all morning Shatabdi and express trains by 3+ hours.",
            reported_at=base_time - timedelta(minutes=45),
            valid_until=base_time + timedelta(hours=6),
        ),
        DisruptionEvent(
            event_id="DISR-OHE-002",
            mode=TransportMode.TRAIN,
            disruption_type=DisruptionType.LOCOMOTIVE_FAILURE,
            severity=DisruptionSeverity.HIGH,
            source_reference="NR-OHE-992",
            operator="Northern Railway (Ambala Division)",
            affected_origin="NDLS",
            affected_destination="CDG",
            affected_stations=["NDLS", "UMB", "CDG"],
            delay_minutes=120,
            is_cancelled=False,
            headline="Overhead Electric Cable Snap near Ambala Cantt",
            description="High-voltage overhead traction equipment failure between Kurukshetra and Ambala Cantt. Delhi-Chandigarh track power disrupted. Diesel rescue engine in transit.",
            reported_at=base_time - timedelta(minutes=30),
            valid_until=base_time + timedelta(hours=3),
        ),
        DisruptionEvent(
            event_id="DISR-CNCL-003",
            mode=TransportMode.TRAIN,
            disruption_type=DisruptionType.TRACK_MAINTENANCE,
            severity=DisruptionSeverity.CRITICAL,
            source_reference="NWR-BLOCK-401",
            operator="North Western Railway",
            affected_origin="NDLS",
            affected_destination="JP",
            affected_stations=["NDLS", "RE", "AWR", "JP"],
            delay_minutes=0,
            is_cancelled=True,
            headline="Emergency Track Settlement Cancels Ajmer Shatabdi (12015)",
            description="Emergency ballast packing and track realignment work near Alwar Junction. Train 12015 Ajmer Shatabdi cancelled for today. Passengers advised to seek road or bus alternatives.",
            reported_at=base_time - timedelta(minutes=90),
            valid_until=base_time + timedelta(hours=8),
        ),
        DisruptionEvent(
            event_id="DISR-EXP-004",
            mode=TransportMode.ROAD,
            disruption_type=DisruptionType.HIGHWAY_CONGESTION,
            severity=DisruptionSeverity.HIGH,
            source_reference="YEIDA-TRAFFIC-882",
            operator="Yamuna Expressway Authority",
            affected_origin="DEL_ISBT",
            affected_destination="AGR_BUS",
            affected_stations=["DEL_ISBT", "NOI", "AGR_BUS"],
            delay_minutes=75,
            is_cancelled=False,
            headline="Yamuna Expressway Multi-Vehicle Congestion at Toll Plaza Jewar",
            description="Heavy freight truck breakdown causing 12 km gridlock approaching Jewar interchange. Intercity bus travel times between Delhi and Agra extended by 75 minutes.",
            reported_at=base_time - timedelta(minutes=20),
            valid_until=base_time + timedelta(hours=2),
        ),
        DisruptionEvent(
            event_id="DISR-NH44-005",
            mode=TransportMode.ROAD,
            disruption_type=DisruptionType.ROAD_ACCIDENT,
            severity=DisruptionSeverity.MEDIUM,
            source_reference="NHAI-TRAF-110",
            operator="National Highways Authority of India",
            affected_origin="DEL_ISBT",
            affected_destination="CDG_BUS",
            affected_stations=["DEL_ISBT", "UMB", "CDG_BUS"],
            delay_minutes=45,
            is_cancelled=False,
            headline="NH44 GT Road Lane Diversion near Karnal",
            description="Culvert maintenance and container rollover near Karnal bypass. Northbound traffic routed through single service lane. Add 45 minutes to highway bus and cab itineraries.",
            reported_at=base_time - timedelta(minutes=15),
            valid_until=base_time + timedelta(hours=3),
        ),
        DisruptionEvent(
            event_id="DISR-ATC-006",
            mode=TransportMode.FLIGHT,
            disruption_type=DisruptionType.AIRPORT_ATC,
            severity=DisruptionSeverity.HIGH,
            source_reference="AAI-DEL-ATC-55",
            operator="Airports Authority of India",
            affected_origin="DEL_AIR",
            affected_destination="JAI_AIR",
            affected_stations=["DEL_AIR", "JAI_AIR"],
            delay_minutes=110,
            is_cancelled=False,
            headline="Delhi Airport ATC Ground Delay Program in Effect",
            description="Runway 29R closed for urgent rubber removal and sensor maintenance. Departure release delays affecting short-haul domestic shuttles to Jaipur and Chandigarh.",
            reported_at=base_time - timedelta(minutes=60),
            valid_until=base_time + timedelta(hours=4),
        ),
        DisruptionEvent(
            event_id="DISR-SIG-007",
            mode=TransportMode.TRAIN,
            disruption_type=DisruptionType.SIGNAL_FAILURE,
            severity=DisruptionSeverity.MEDIUM,
            source_reference="NCR-SIG-221",
            operator="North Central Railway",
            affected_origin="NZM",
            affected_destination="AGC",
            affected_stations=["NZM", "MTJ", "AGC"],
            delay_minutes=60,
            is_cancelled=False,
            headline="Electronic Interlocking Signal Failure at Mathura Jn",
            description="Point detection failure on line 4 at Mathura Junction. Route relay interlocking operating in manual paper authority mode, creating 60 minute bunching of trains.",
            reported_at=base_time - timedelta(minutes=25),
            valid_until=base_time + timedelta(hours=2),
        ),
        DisruptionEvent(
            event_id="DISR-BUS-008",
            mode=TransportMode.BUS,
            disruption_type=DisruptionType.WEATHER,
            severity=DisruptionSeverity.HIGH,
            source_reference="RSRTC-DISPATCH-901",
            operator="RSRTC & Private Coach Consortium",
            affected_origin="JAI_BUS",
            affected_destination="AGR_BUS",
            affected_stations=["JAI_BUS", "AGR_BUS"],
            delay_minutes=90,
            is_cancelled=False,
            headline="Severe Dust Storm & Visibility Drop on Bharatpur-Agra Highway",
            description="Sudden western disturbance dust storm across eastern Rajasthan and western UP. Intercity buses operating with hazard lights at reduced speeds.",
            reported_at=base_time - timedelta(minutes=35),
            valid_until=base_time + timedelta(hours=3),
        ),
        DisruptionEvent(
            event_id="DISR-STRIKE-009",
            mode=TransportMode.CAB,
            disruption_type=DisruptionType.STRIKE,
            severity=DisruptionSeverity.MEDIUM,
            source_reference="DEL-CAB-UNION-04",
            operator="Delhi-NCR App Cab Drivers Welfare Union",
            affected_origin="NDLS",
            affected_destination="DEL_ISBT",
            affected_stations=["NDLS", "DEL_ISBT", "GGN"],
            delay_minutes=30,
            is_cancelled=False,
            headline="Intermittent App-Cab Surge and Availability Shortage at New Delhi Station",
            description="Local driver union protest over platform commission rates. On-demand cab wait times increased to 30+ minutes at NDLS Paharganj and Ajmeri Gate sides.",
            reported_at=base_time - timedelta(minutes=40),
            valid_until=base_time + timedelta(hours=4),
        ),
        DisruptionEvent(
            event_id="DISR-DERAIL-010",
            mode=TransportMode.TRAIN,
            disruption_type=DisruptionType.LOCOMOTIVE_FAILURE,
            severity=DisruptionSeverity.CRITICAL,
            source_reference="NWR-INC-781",
            operator="North Western Railway",
            affected_origin="JP",
            affected_destination="NDLS",
            affected_stations=["JP", "AWR", "NDLS"],
            delay_minutes=240,
            is_cancelled=False,
            headline="Freight Wagon Axle Lock at Bandikui Blocks Jaipur-Delhi Line",
            description="Goods train wagon axle lock between Bandikui and Dausa blocked the UP mainline. Traffic operating on single line reversible system with delays exceeding 4 hours.",
            reported_at=base_time - timedelta(minutes=50),
            valid_until=base_time + timedelta(hours=5),
        ),
    ]
