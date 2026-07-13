import strawberry
from typing import List, Optional
from dataclasses import field

@strawberry.type
class Agency:
    id: str
    name: Optional[str] = None
    url: Optional[str] = None
    timezone: Optional[str] = None

@strawberry.type
class GeoJSONPoint:
    type: str = "Point"
    coordinates: List[float] = field(default_factory=list)

@strawberry.type
class Stop:
    stop_id: str
    name: Optional[str] = None
    location: Optional[GeoJSONPoint] = None

@strawberry.type
class Route:
    route_id: str
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    type: int = 3

@strawberry.type
class Trip:
    trip_id: str
    route_id: str
    service_id: str
    headsign: Optional[str] = None
    direction_id: int = 0
    shape_id: Optional[str] = None

@strawberry.type
class StopTime:
    trip_id: str
    arrival_time: Optional[str] = None
    departure_time: Optional[str] = None
    stop_id: str
    stop_sequence: int

@strawberry.type
class Calendar:
    service_id: str
    monday: int
    tuesday: int
    wednesday: int
    thursday: int
    friday: int
    saturday: int
    sunday: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None

@strawberry.type
class CalendarDate:
    service_id: str
    date: str
    exception_type: int

@strawberry.type
class GTFSData:
    agencies: List[Agency] = field(default_factory=list)
    routes: List[Route] = field(default_factory=list)
    stops: List[Stop] = field(default_factory=list)
    trips: List[Trip] = field(default_factory=list)
    stop_times: List[StopTime] = field(default_factory=list)
    calendar: List[Calendar] = field(default_factory=list)
    calendar_dates: List[CalendarDate] = field(default_factory=list)