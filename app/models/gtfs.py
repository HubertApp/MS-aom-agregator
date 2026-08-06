
from typing import Annotated, Any, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationInfo


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str) and not v.strip():
        return None
    return v


def _blank_to_zero(v: Any) -> Any:
    if v is None or (isinstance(v, str) and not v.strip()):
        return 0.0
    return v


def _namespace(v: Any, info: ValidationInfo) -> Any:
    """
    Préfixe un identifiant GTFS par le network_id passé dans le contexte de
    validation, afin de le rendre unique à l'échelle de toutes les AOM agrégées.
    """
    if v is None:
        return None

    v = str(v).strip()
    if not v:
        return None

    network_id = (info.context or {}).get("network_id")
    return f"{network_id}:{v}" if network_id else v


def _namespace_agency(v: Any, info: ValidationInfo) -> Any:
    if v is None or (isinstance(v, str) and not v.strip()):
        v = "default"
    return _namespace(v, info)


# Identifiant obligatoire, namespacé (clé primaire d'une entité GTFS).
NamespacedId = Annotated[str, BeforeValidator(_namespace)]
OptionalNamespacedId = Annotated[Optional[str], BeforeValidator(_namespace)]
AgencyRef = Annotated[str, BeforeValidator(_namespace_agency)]

OptStr = Annotated[Optional[str], BeforeValidator(_blank_to_none)]
OptInt = Annotated[Optional[int], BeforeValidator(_blank_to_none)]
OptFloat = Annotated[Optional[float], BeforeValidator(_blank_to_none)]
Coordinate = Annotated[float, BeforeValidator(_blank_to_zero)]


class GTFSBase(BaseModel):

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        validate_default=True,
        str_strip_whitespace=True,
    )

class Agency(GTFSBase):
    agency_id: AgencyRef = Field(default="default", alias="agency_id")
    name: OptStr = Field(default=None, alias="agency_name")
    url: OptStr = Field(default=None, alias="agency_url")
    timezone: OptStr = Field(default=None, alias="agency_timezone")
    lang: OptStr = Field(default=None, alias="agency_lang")
    phone: OptStr = Field(default=None, alias="agency_phone")
    fare_url: OptStr = Field(default=None, alias="agency_fare_url")
    email: OptStr = Field(default=None, alias="agency_email")

class Stop(GTFSBase):
    stop_id: NamespacedId = Field(alias="stop_id")
    code: OptStr = Field(default=None, alias="stop_code")
    name: OptStr = Field(default=None, alias="stop_name")
    description: OptStr = Field(default=None, alias="stop_desc")
    lat: Coordinate = Field(default=0.0, alias="stop_lat")
    lon: Coordinate = Field(default=0.0, alias="stop_lon")
    zone_id: OptStr = Field(default=None, alias="zone_id")
    url: OptStr = Field(default=None, alias="stop_url")
    location_type: OptInt = Field(default=0, alias="location_type")
    parent_station: OptionalNamespacedId = Field(default=None, alias="parent_station")
    timezone: OptStr = Field(default=None, alias="stop_timezone")
    wheelchair_boarding: OptInt = Field(default=None, alias="wheelchair_boarding")
    platform_code: OptStr = Field(default=None, alias="platform_code")


class Route(GTFSBase):
    route_id: NamespacedId = Field(alias="route_id")
    agency_id: AgencyRef = Field(default="default", alias="agency_id")
    short_name: OptStr = Field(default=None, alias="route_short_name")
    long_name: OptStr = Field(default=None, alias="route_long_name")
    description: OptStr = Field(default=None, alias="route_desc")
    type: OptInt = Field(default=3, alias="route_type")
    url: OptStr = Field(default=None, alias="route_url")
    color: OptStr = Field(default=None, alias="route_color")
    text_color: OptStr = Field(default=None, alias="route_text_color")
    sort_order: OptInt = Field(default=None, alias="route_sort_order")


class Trip(GTFSBase):
    trip_id: NamespacedId = Field(alias="trip_id")
    route_id: NamespacedId = Field(alias="route_id")
    service_id: NamespacedId = Field(alias="service_id")
    headsign: OptStr = Field(default=None, alias="trip_headsign")
    short_name: OptStr = Field(default=None, alias="trip_short_name")
    direction_id: OptInt = Field(default=0, alias="direction_id")
    block_id: OptStr = Field(default=None, alias="block_id")
    shape_id: OptionalNamespacedId = Field(default=None, alias="shape_id")
    wheelchair_accessible: OptInt = Field(default=0, alias="wheelchair_accessible")
    bikes_allowed: OptInt = Field(default=0, alias="bikes_allowed")


class StopTime(GTFSBase):
    trip_id: NamespacedId = Field(alias="trip_id")
    stop_id: NamespacedId = Field(alias="stop_id")
    arrival_time: OptStr = Field(default=None, alias="arrival_time")
    departure_time: OptStr = Field(default=None, alias="departure_time")
    stop_sequence: OptInt = Field(default=0, alias="stop_sequence")
    stop_headsign: OptStr = Field(default=None, alias="stop_headsign")
    pickup_type: OptInt = Field(default=0, alias="pickup_type")
    drop_off_type: OptInt = Field(default=0, alias="drop_off_type")
    shape_dist_traveled: OptFloat = Field(default=None, alias="shape_dist_traveled")
    timepoint: OptInt = Field(default=None, alias="timepoint")

class Calendar(GTFSBase):
    service_id: NamespacedId = Field(alias="service_id")
    monday: OptInt = Field(default=0, alias="monday")
    tuesday: OptInt = Field(default=0, alias="tuesday")
    wednesday: OptInt = Field(default=0, alias="wednesday")
    thursday: OptInt = Field(default=0, alias="thursday")
    friday: OptInt = Field(default=0, alias="friday")
    saturday: OptInt = Field(default=0, alias="saturday")
    sunday: OptInt = Field(default=0, alias="sunday")
    start_date: OptStr = Field(default=None, alias="start_date")
    end_date: OptStr = Field(default=None, alias="end_date")

class CalendarDate(GTFSBase):
    service_id: NamespacedId = Field(alias="service_id")
    date: OptStr = Field(default=None, alias="date")
    # 1 = service ajouté ce jour-là, 2 = service retiré ce jour-là
    exception_type: OptInt = Field(default=None, alias="exception_type")

class Shape(GTFSBase):
    shape_id: NamespacedId = Field(alias="shape_id")
    pt_lat: Coordinate = Field(default=0.0, alias="shape_pt_lat")
    pt_lon: Coordinate = Field(default=0.0, alias="shape_pt_lon")
    pt_sequence: OptInt = Field(default=0, alias="shape_pt_sequence")
    shape_dist_traveled: OptFloat = Field(default=None, alias="shape_dist_traveled")

class Transfer(GTFSBase):
    from_stop_id: NamespacedId = Field(alias="from_stop_id")
    to_stop_id: NamespacedId = Field(alias="to_stop_id")
    transfer_type: OptInt = Field(default=0, alias="transfer_type")
    min_transfer_time: OptInt = Field(default=None, alias="min_transfer_time")


def to_seconds(value: Optional[str]) -> int:
    if not value:
        return 0
    try:
        hours, minutes, seconds = (int(part) for part in value.strip().split(":"))
    except ValueError:
        return 0
    return hours * 3600 + minutes * 60 + seconds
