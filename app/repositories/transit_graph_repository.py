from datetime import date
from typing import Any, Dict, List

WEEKDAYS = [
    "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday",
]


class TransitGraphRepository:

    def __init__(self, db):
        self._stop_times = db["stop_times"]
        self._calendar = db["calendar"]
        self._calendar_dates = db["calendar_dates"]

    async def active_service_ids(self, network_id: str, day: date) -> List[str]:
        """Services reellement en circulation ce jour-la.

        Sans ce filtre, les courses du dimanche seraient comptees dans la
        frequence d'un mardi et toutes les attentes seraient sous-estimees.
        """
        stamp = day.strftime("%Y%m%d")
        weekday = WEEKDAYS[day.weekday()]

        cursor = self._calendar.find(
            {
                "network_id": network_id,
                weekday: 1,
                "start_date": {"$lte": stamp},
                "end_date": {"$gte": stamp},
            },
            {"service_id": 1},
        )
        service_ids = {document["service_id"] async for document in cursor}

        # calendar_dates.txt : 1 = service ajoute ce jour, 2 = service retire
        exceptions = self._calendar_dates.find(
            {"network_id": network_id, "date": stamp},
            {"service_id": 1, "exception_type": 1},
        )
        async for document in exceptions:
            if document.get("exception_type") == 1:
                service_ids.add(document["service_id"])
            elif document.get("exception_type") == 2:
                service_ids.discard(document["service_id"])

        return sorted(service_ids)

    async def list_trip_sequences(
        self,
        network_id: str,
        service_ids: List[str],
        window_start_s: int,
        window_end_s: int,
    ) -> List[Dict[str, Any]]:
        """Une course par document, avec la liste de ses passages."""
        pipeline = [
            {"$match": {
                "network_id": network_id,
                "service_id": {"$in": service_ids},
            }},
            {"$group": {
                "_id": "$trip_id",
                "route_id": {"$first": "$route_id"},
                "route_short_name": {"$first": "$route_short_name"},
                "direction_id": {"$first": "$direction_id"},
                "headsign": {"$first": "$headsign"},
                "first_departure": {"$min": "$departure_seconds"},
                "stops": {"$push": {
                    "stop_id": "$stop_id",
                    "t": "$departure_seconds",
                    "seq": "$stop_sequence",
                }},
            }},
            {"$match": {"first_departure": {
                "$gte": window_start_s,
                "$lt": window_end_s,
            }}},
        ]
        return [
            document
            async for document in self._stop_times.aggregate(pipeline)
        ]
