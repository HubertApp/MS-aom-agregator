from typing import List, Optional

import strawberry

from app.core.text import normalize_for_search
from app.graphql.types.gtfs import MAX_FIRST, MAX_RADIUS_METERS, MIN_QUERY_LENGTH, Stop


async def resolve_stop(info: strawberry.Info, id: strawberry.ID) -> Optional[Stop]:
    document = await info.context["stop_loader"].load(str(id))
    return Stop.from_document(document) if document else None


async def resolve_stops_nearby(
    info: strawberry.Info,
    lat: float,
    lon: float,
    radius_meters: int = 500,
    first: int = 20,
    network_id: Optional[strawberry.ID] = None,
) -> List[Stop]:

    if first < 1 or first > MAX_FIRST:
        raise ValueError(f"'first' doit être compris entre 1 et {MAX_FIRST}.")
    if radius_meters < 1 or radius_meters > MAX_RADIUS_METERS:
        raise ValueError(f"'radiusMeters' doit être compris entre 1 et {MAX_RADIUS_METERS}.")
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise ValueError("Coordonnées invalides : latitude dans [-90, 90], longitude dans [-180, 180].")

    documents = await info.context["stop_repository"].find_nearby(
        latitude=lat,
        longitude=lon,
        radius_meters=radius_meters,
        limit=first,
        network_id=str(network_id) if network_id else None,
    )
    return [Stop.from_document(document) for document in documents]


async def resolve_search_stops(
    info: strawberry.Info,
    query: str,
    first: int = 20,
    network_id: Optional[strawberry.ID] = None,
) -> List[Stop]:

    if first < 1 or first > MAX_FIRST:
        raise ValueError(f"'first' doit être compris entre 1 et {MAX_FIRST}.")
    if len(normalize_for_search(query)) < MIN_QUERY_LENGTH:
        raise ValueError(
            f"'query' doit comporter au moins {MIN_QUERY_LENGTH} caractères "
            "alphanumériques (les accents, espaces et ponctuations sont ignorés)."
        )

    documents = await info.context["stop_repository"].search_by_name(
        query=query,
        limit=first,
        network_id=str(network_id) if network_id else None,
    )
    return [Stop.from_document(document) for document in documents]
