from typing import List, Optional

import strawberry

from app.graphql.resolvers.routes import resolve_route, resolve_routes
from app.graphql.resolvers.stops import resolve_stop, resolve_stops_nearby
from app.graphql.resolvers.system import resolve_status
from app.graphql.resolvers.transit_graph import resolve_transit_graph
from app.graphql.types.gtfs import PaginatedRoutes, Route, Stop
from app.graphql.types.transit_graph import TransitGraph


@strawberry.type
class Query:
    stops_nearby: List[Stop] = strawberry.field(resolver=resolve_stops_nearby)
    stop: Optional[Stop] = strawberry.field(resolver=resolve_stop)
    routes: PaginatedRoutes = strawberry.field(resolver=resolve_routes)
    route: Optional[Route] = strawberry.field(resolver=resolve_route)
    status: str = strawberry.field(resolver=resolve_status)
    transit_graph: TransitGraph = strawberry.field(resolver=resolve_transit_graph)

schema = strawberry.federation.Schema(query=Query, federation_version="2.0")
