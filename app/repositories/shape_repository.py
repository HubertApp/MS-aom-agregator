from collections import defaultdict
from typing import Dict, List

from pymongo import ASCENDING


class ShapeRepository:

    def __init__(self, db):
        self._collection = db["shapes"]

    async def list_points_for_shapes(self, shape_ids: List[str]) -> Dict[str, List[List[float]]]:

        cursor = self._collection.find(
            {"shape_id": {"$in": shape_ids}},
            {"shape_id": 1, "pt_lat": 1, "pt_lon": 1, "pt_sequence": 1},
        ).sort([("shape_id", ASCENDING), ("pt_sequence", ASCENDING)])

        grouped: Dict[str, List[List[float]]] = defaultdict(list)
        async for document in cursor:
            grouped[document["shape_id"]].append([
                document.get("pt_lon") or 0.0,
                document.get("pt_lat") or 0.0,
            ])
        return grouped
