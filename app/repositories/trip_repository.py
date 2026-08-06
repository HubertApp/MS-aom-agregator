from collections import defaultdict
from typing import Any, Dict, List


class TripRepository:

    def __init__(self, db):
        self._collection = db["trips"]

    async def list_by_route_ids(self, route_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        projection = {
            "trip_id": 1,
            "route_id": 1,
            "direction_id": 1,
            "headsign": 1,
            "shape_id": 1,
        }
        cursor = self._collection.find({"route_id": {"$in": route_ids}}, projection)

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        async for document in cursor:
            grouped[document["route_id"]].append(document)
        return grouped
