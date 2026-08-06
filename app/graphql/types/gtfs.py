
import math
from typing import Any, Dict, List, Optional

import strawberry

from app.graphql.loaders.departures_loader import DeparturesKey
from app.models.gtfs import to_seconds

MAX_FIRST = 100
MAX_PAGE_SIZE = 100
MAX_RADIUS_METERS = 5_000


@strawberry.type
class GeoJSONPoint:
    type: str = "Point"
    coordinates: List[float] = strawberry.field(default_factory=list)

    # GeoJSON stocke [longitude, latitude], dans cet ordre contre-intuitif.
    # On expose latitude/longitude explicitement pour que le front n'ait pas à
    # s'en souvenir.
    @strawberry.field
    def latitude(self) -> Optional[float]:
        return self.coordinates[1] if len(self.coordinates) == 2 else None

    @strawberry.field
    def longitude(self) -> Optional[float]:
        return self.coordinates[0] if len(self.coordinates) == 2 else None


@strawberry.type
class GeoJSONLineString:

    type: str = "LineString"
    coordinates: List[List[float]] = strawberry.field(default_factory=list)


@strawberry.federation.type(keys=["id"], extend=True)
class TransitNetwork:
    id: strawberry.ID = strawberry.federation.field(external=True)


@strawberry.type
class RouteDirection:
    direction_id: int
    headsign: Optional[str]
    stops: List["Stop"]
    geometry: Optional[GeoJSONLineString]


@strawberry.type
class Route:
    id: strawberry.ID
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    type: Optional[int] = None
    color: Optional[str] = None
    text_color: Optional[str] = None
    network_id: strawberry.Private[str] = ""

    @classmethod
    def from_document(cls, document: Dict[str, Any]) -> "Route":
        return cls(
            id=strawberry.ID(document["route_id"]),
            short_name=document.get("short_name"),
            long_name=document.get("long_name"),
            type=document.get("type"),
            color=document.get("color"),
            text_color=document.get("text_color"),
            network_id=document.get("network_id", ""),
        )

    @strawberry.field
    def network(self) -> TransitNetwork:
        return TransitNetwork(id=strawberry.ID(self.network_id))

    @strawberry.field
    async def directions(self, info: strawberry.Info) -> List[RouteDirection]:

        raw_directions = await info.context["route_directions_loader"].load(str(self.id))
        if not raw_directions:
            return []

        # Les arrêts passent par le DataLoader des arrêts : ceux partagés entre
        # deux directions (ou deux lignes) ne sont chargés qu'une seule fois.
        stop_loader = info.context["stop_loader"]

        directions: List[RouteDirection] = []
        for raw in raw_directions:
            documents = await stop_loader.load_many(raw["stop_ids"]) if raw["stop_ids"] else []
            coordinates = raw.get("coordinates") or []
            directions.append(RouteDirection(
                direction_id=raw["direction_id"],
                headsign=raw.get("headsign"),
                stops=[Stop.from_document(d) for d in documents if d],
                geometry=GeoJSONLineString(coordinates=coordinates) if coordinates else None,
            ))
        return directions


@strawberry.type
class PaginatedRoutes:
    items: List[Route]
    total_count: int
    page: int
    page_size: int

    @strawberry.field
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return math.ceil(self.total_count / self.page_size)


@strawberry.type
class Departure:
    trip_id: strawberry.ID
    stop_sequence: Optional[int]
    arrival_time: Optional[str]
    departure_time: Optional[str]
    headsign: Optional[str]
    route: Optional[Route]

    @classmethod
    def from_document(cls, document: Dict[str, Any]) -> "Departure":
        return cls(
            trip_id=strawberry.ID(document["trip_id"]),
            stop_sequence=document.get("stop_sequence"),
            arrival_time=document.get("arrival_time"),
            departure_time=document.get("departure_time"),
            headsign=document.get("headsign"),
            route=Route(
                id=strawberry.ID(document["route_id"]),
                short_name=document.get("route_short_name"),
                long_name=document.get("route_long_name"),
                type=document.get("route_type"),
                color=document.get("route_color"),
                text_color=document.get("route_text_color"),
                network_id=document.get("network_id", ""),
            ) if document.get("route_id") else None,
        )


@strawberry.type
class Stop:
    id: strawberry.ID
    name: Optional[str]
    location: Optional[GeoJSONPoint]
    network_id: strawberry.Private[str]
    distance_meters: Optional[float] = None

    @classmethod
    def from_document(
        cls,
        document: Dict[str, Any],
        distance_meters: Optional[float] = None,
    ) -> "Stop":
        coordinates = (document.get("location") or {}).get("coordinates") or []
        return cls(
            id=strawberry.ID(document["stop_id"]),
            name=document.get("name"),
            location=GeoJSONPoint(coordinates=coordinates) if coordinates else None,
            network_id=document.get("network_id", ""),
            distance_meters=distance_meters if distance_meters is not None else document.get("distance_meters"),
        )

    @strawberry.field
    def network(self) -> TransitNetwork:
        return TransitNetwork(id=strawberry.ID(self.network_id))

    @strawberry.field
    async def departures(
        self,
        info: strawberry.Info,
        first: int = 10,
        after: Optional[str] = None,
    ) -> List[Departure]:

        if first < 1 or first > MAX_FIRST:
            raise ValueError(f"'first' doit être compris entre 1 et {MAX_FIRST}.")

        key = DeparturesKey(
            stop_id=str(self.id),
            after_seconds=to_seconds(after),
            limit=first,
        )
        documents = await info.context["departures_loader"].load(key)
        return [Departure.from_document(document) for document in documents]

    @strawberry.field
    async def routes(self, info: strawberry.Info) -> List[Route]:
        documents = await info.context["stop_routes_loader"].load(str(self.id))
        return [
            Route(
                id=strawberry.ID(document["route_id"]),
                short_name=document.get("route_short_name"),
                long_name=document.get("route_long_name"),
                type=document.get("route_type"),
                color=document.get("route_color"),
                text_color=document.get("route_text_color"),
                network_id=document.get("network_id", ""),
            )
            for document in documents
        ]
