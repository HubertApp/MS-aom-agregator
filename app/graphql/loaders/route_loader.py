from typing import Any, Dict, List, Optional

from strawberry.dataloader import DataLoader

from app.repositories.route_repository import RouteRepository
from app.repositories.shape_repository import ShapeRepository
from app.repositories.stop_time_repository import StopTimeRepository
from app.repositories.trip_repository import TripRepository


def build_route_loader(repository: RouteRepository) -> DataLoader:

    async def load(route_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
        found = await repository.get_many_by_ids(list(route_ids))
        return [found.get(route_id) for route_id in route_ids]

    return DataLoader(load_fn=load)


def build_route_directions_loader(
    trip_repository: TripRepository,
    stop_time_repository: StopTimeRepository,
    shape_repository: ShapeRepository,
) -> DataLoader:

    async def load(route_ids: List[str]) -> List[List[Dict[str, Any]]]:
        trips_by_route = await trip_repository.list_by_route_ids(list(route_ids))

        every_trip_id = [
            trip["trip_id"]
            for trips in trips_by_route.values()
            for trip in trips
        ]
        if not every_trip_id:
            return [[] for _ in route_ids]

        stop_counts = await stop_time_repository.count_by_trips(every_trip_id)

        representatives: Dict[str, Dict[int, Dict[str, Any]]] = {}
        for route_id, trips in trips_by_route.items():
            by_direction: Dict[int, Dict[str, Any]] = {}
            for trip in trips:
                direction_id = trip.get("direction_id") or 0
                current = by_direction.get(direction_id)
                if current is None or stop_counts.get(trip["trip_id"], 0) > stop_counts.get(current["trip_id"], 0):
                    by_direction[direction_id] = trip
            representatives[route_id] = by_direction

        chosen_trips = [
            trip
            for by_direction in representatives.values()
            for trip in by_direction.values()
        ]

        # arrêt et tracés des seuls trajets retenus
        stop_times_by_trip = await stop_time_repository.list_for_trips(
            [trip["trip_id"] for trip in chosen_trips]
        )
        shape_ids = [trip["shape_id"] for trip in chosen_trips if trip.get("shape_id")]
        points_by_shape = await shape_repository.list_points_for_shapes(shape_ids) if shape_ids else {}

        results: List[List[Dict[str, Any]]] = []
        for route_id in route_ids:
            directions = []
            for direction_id in sorted(representatives.get(route_id, {})):
                trip = representatives[route_id][direction_id]
                directions.append({
                    "direction_id": direction_id,
                    "headsign": trip.get("headsign"),
                    "trip_id": trip["trip_id"],
                    "stop_ids": [
                        stop_time["stop_id"]
                        for stop_time in stop_times_by_trip.get(trip["trip_id"], [])
                    ],
                    "coordinates": points_by_shape.get(trip.get("shape_id"), []),
                })
            results.append(directions)

        return results

    return DataLoader(load_fn=load)
