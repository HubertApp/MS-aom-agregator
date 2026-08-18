from datetime import datetime, timezone
from typing import Any, Dict, Optional

import strawberry

from app.graphql.types.transit_graph import (
    BoundingBoxInput,
    TransitEdge,
    TransitGraph,
    TransitNode,
)
from app.services.transit_graph_builder import build_transit_graph

WINDOW_HALF_WIDTH_S = 3_600      # fenetre de +/- 1 h autour de l'heure demandee


def _inside(document: Dict[str, Any], bbox: BoundingBoxInput) -> bool:
    coordinates = (document.get("location") or {}).get("coordinates") or []
    if len(coordinates) != 2:
        return False
    lon, lat = coordinates
    return bbox.south <= lat <= bbox.north and bbox.west <= lon <= bbox.east


async def resolve_transit_graph(
    info: strawberry.Info,
    network_id: strawberry.ID,
    departure_time: datetime,
    bbox: Optional[BoundingBoxInput] = None,
) -> TransitGraph:
    repository = info.context["transit_graph_repository"]
    stop_repository = info.context["stop_repository"]

    moment = (
        departure_time.astimezone(timezone.utc)
        if departure_time.tzinfo
        else departure_time
    )
    hour_bucket = moment.hour
    window_start = max(0, hour_bucket * 3600 - WINDOW_HALF_WIDTH_S)
    window_end = hour_bucket * 3600 + WINDOW_HALF_WIDTH_S

    empty = TransitGraph(
        network_id=str(network_id), hour_bucket=hour_bucket, nodes=[], edges=[]
    )

    service_ids = await repository.active_service_ids(str(network_id), moment.date())
    if not service_ids:
        return empty

    trip_sequences = await repository.list_trip_sequences(
        network_id=str(network_id),
        service_ids=service_ids,
        window_start_s=window_start,
        window_end_s=window_end,
    )
    if not trip_sequences:
        return empty

    stop_ids = {
        passage["stop_id"]
        for trip in trip_sequences
        for passage in (trip.get("stops") or [])
    }
    stops_by_id = await stop_repository.get_many_by_ids(sorted(stop_ids))

    if bbox:
        stops_by_id = {
            stop_id: document
            for stop_id, document in stops_by_id.items()
            if _inside(document, bbox)
        }

    graph = build_transit_graph(
        trip_sequences=trip_sequences,
        stops_by_id=stops_by_id,
        window_seconds=window_end - window_start,
    )

    return TransitGraph(
        network_id=str(network_id),
        hour_bucket=hour_bucket,
        nodes=[
            TransitNode(
                id=strawberry.ID(node["id"]),
                lat=node["lat"],
                lon=node["lon"],
                is_transit_stop=node["is_transit_stop"],
            )
            for node in graph["nodes"]
        ],
        edges=[
            TransitEdge(
                edge_id=strawberry.ID(edge["edge_id"]),
                source_id=edge["source_id"],
                target_id=edge["target_id"],
                weight=edge["weight"],
                length=edge["length"],
                layer=edge["layer"],
                transit_line_id=edge["transit_line_id"],
                name=edge["name"],
            )
            for edge in graph["edges"]
        ],
    )
