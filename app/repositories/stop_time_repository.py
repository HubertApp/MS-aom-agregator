from collections import defaultdict
from typing import Any, Dict, List

from pymongo import ASCENDING


class StopTimeRepository:

    def __init__(self, db):
        self._collection = db["stop_times"]

    async def list_departures_for_stops(
        self,
        stop_ids: List[str],
        after_seconds: int,
        limit: int,
    ) -> Dict[str, List[Dict[str, Any]]]:

        pipeline = [
            {"$match": {
                "stop_id": {"$in": stop_ids},
                "departure_seconds": {"$gte": after_seconds},
            }},
            {"$sort": {"departure_seconds": ASCENDING}},
            {"$group": {"_id": "$stop_id", "departures": {"$push": "$$ROOT"}}},
            # $slice après $group : on ne garde que les premiers départs de chaque arrêt sans rapatrier toute la journée
            {"$project": {"departures": {"$slice": ["$departures", limit]}}},
        ]

        grouped: Dict[str, List[Dict[str, Any]]] = {}
        async for document in self._collection.aggregate(pipeline):
            grouped[document["_id"]] = document["departures"]
        return grouped

    async def count_by_trips(self, trip_ids: List[str]) -> Dict[str, int]:
        pipeline = [
            {"$match": {"trip_id": {"$in": trip_ids}}},
            {"$group": {"_id": "$trip_id", "count": {"$sum": 1}}},
        ]
        return {
            document["_id"]: document["count"]
            async for document in self._collection.aggregate(pipeline)
        }

    async def list_for_trips(self, trip_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:

        cursor = self._collection.find(
            {"trip_id": {"$in": trip_ids}},
            {"trip_id": 1, "stop_id": 1, "stop_sequence": 1},
        ).sort([("trip_id", ASCENDING), ("stop_sequence", ASCENDING)])

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        async for document in cursor:
            grouped[document["trip_id"]].append(document)
        return grouped

    async def list_distinct_routes_for_stops(
            self,
            stop_ids: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Lignes desservant chaque arrêt demandé, sans doublon, déduites de
        l'ENSEMBLE des passages
        on ne rapatrie qu'une ligne par (arrêt, route_id), jamais un passage entier,
        donc le volume reste faible même sur un arrêt à fort trafic
        """
        pipeline = [
            {"$match": {
                "stop_id": {"$in": stop_ids},
                "route_id": {"$exists": True},
            }},
            {"$group": {
                "_id": {"stop_id": "$stop_id", "route_id": "$route_id"},
                "route_short_name": {"$first": "$route_short_name"},
                "route_long_name": {"$first": "$route_long_name"},
                "route_type": {"$first": "$route_type"},
                "route_color": {"$first": "$route_color"},
                "route_text_color": {"$first": "$route_text_color"},
                "network_id": {"$first": "$network_id"},
            }},
        ]

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        async for document in self._collection.aggregate(pipeline):
            grouped[document["_id"]["stop_id"]].append({
                "route_id": document["_id"]["route_id"],
                "route_short_name": document.get("route_short_name"),
                "route_long_name": document.get("route_long_name"),
                "route_type": document.get("route_type"),
                "route_color": document.get("route_color"),
                "route_text_color": document.get("route_text_color"),
                "network_id": document.get("network_id"),
            })
        return grouped
