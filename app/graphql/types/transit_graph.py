from typing import List, Optional

import strawberry


@strawberry.input
class BoundingBoxInput:
    north: float
    south: float
    east: float
    west: float


@strawberry.type
class TransitNode:
    id: strawberry.ID
    lat: float
    lon: float
    is_transit_stop: bool


@strawberry.type
class TransitEdge:
    edge_id: strawberry.ID
    source_id: str
    target_id: str
    weight: float          # SECONDES
    length: float          # METRES
    layer: int
    transit_line_id: Optional[str] = None
    name: Optional[str] = None


@strawberry.type
class TransitGraph:
    network_id: str
    hour_bucket: int       # heure de reference, sert de cle de cache au consommateur
    nodes: List[TransitNode]
    edges: List[TransitEdge]
