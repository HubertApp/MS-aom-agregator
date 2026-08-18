from app.core.database import db
from app.graphql.loaders.departures_loader import build_departures_loader
from app.graphql.loaders.route_loader import build_route_directions_loader, build_route_loader
from app.graphql.loaders.stop_loader import build_stop_loader
from app.repositories.route_repository import RouteRepository
from app.repositories.shape_repository import ShapeRepository
from app.repositories.stop_repository import StopRepository
from app.repositories.stop_time_repository import StopTimeRepository
from app.repositories.transit_graph_repository import TransitGraphRepository
from app.repositories.trip_repository import TripRepository
from app.graphql.loaders.stop_routes_loader import build_stop_routes_loader

async def get_context():
    stop_repository = StopRepository(db)
    stop_time_repository = StopTimeRepository(db)
    route_repository = RouteRepository(db)
    trip_repository = TripRepository(db)
    shape_repository = ShapeRepository(db)
    transit_graph_repository = TransitGraphRepository(db)

    return {
        "stop_repository": stop_repository,
        "stop_time_repository": stop_time_repository,
        "route_repository": route_repository,
        "trip_repository": trip_repository,
        "shape_repository": shape_repository,
        "transit_graph_repository": transit_graph_repository,
        "stop_routes_loader": build_stop_routes_loader(stop_time_repository),
        "stop_loader": build_stop_loader(stop_repository),
        "departures_loader": build_departures_loader(stop_time_repository),
        "route_loader": build_route_loader(route_repository),
        "route_directions_loader": build_route_directions_loader(
            trip_repository,
            stop_time_repository,
            shape_repository,
        ),
    }
