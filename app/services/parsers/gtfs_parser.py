import asyncio
import csv
import os
from typing import Any, Dict, List, Type

from pydantic import ValidationError

from app.core.text import normalize_for_search
from app.models.gtfs import (
    Agency,
    Calendar,
    CalendarDate,
    GTFSBase,
    Route,
    Shape,
    Stop,
    StopTime,
    Transfer,
    Trip,
    to_seconds,
)
from app.services.parsers.i_parser import IParser


class GTFSParser(IParser):

    FILE_MAPPING: List[tuple] = [
        ("agency.txt", "agencies", Agency),
        ("routes.txt", "routes", Route),
        ("stops.txt", "stops", Stop),
        ("trips.txt", "trips", Trip),
        ("stop_times.txt", "stop_times", StopTime),
        ("calendar.txt", "calendar", Calendar),
        ("calendar_dates.txt", "calendar_dates", CalendarDate),
        ("shapes.txt", "shapes", Shape),
        ("transfers.txt", "transfers", Transfer),
    ]

    MAX_LOGGED_ERRORS = 10

    async def parse(self, directory_path: str, network_id: str) -> Dict[str, List[Dict[str, Any]]]:
        print(f"[GTFSParser] Démarrage de l'analyse dans : {directory_path} (network_id={network_id})")

        result: Dict[str, List[Dict[str, Any]]] = {}

        for file_name, collection_name, model in self.FILE_MAPPING:
            file_path = os.path.join(directory_path, file_name)
            documents = await asyncio.to_thread(self._read_file, file_path, model, network_id)
            result[collection_name] = documents

        result["stops"] = [
            self._with_normalized_name(self._to_geojson(stop))
            for stop in result.get("stops", [])
        ]
        self._denormalize_stop_times(result)

        print("[GTFSParser] Fin du parsing ! "+ ", ".join(f"{len(docs)} {name}" for name, docs in result.items()))
        return result

    def _read_file(
        self,
        file_path: str,
        model: Type[GTFSBase],
        network_id: str,
    ) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            print(f"{os.path.basename(file_path)} absent du flux, ignoré.")
            return []

        documents: List[Dict[str, Any]] = []
        errors = 0

        with open(file_path, mode="r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for line_number, row in enumerate(reader, start=2):  # start 2 pour ignorer l'entete
                try:
                    validated = model.model_validate(row, context={"network_id": network_id})
                except ValidationError as exc:
                    errors += 1
                    if errors <= self.MAX_LOGGED_ERRORS:
                        print(
                            f"{os.path.basename(file_path)} ligne {line_number} ignorée : "
                            f"{exc.error_count()} erreur(s) de validation "
                            f"({'; '.join(e['msg'] for e in exc.errors()[:3])})"
                        )
                    continue
                documents.append(validated.model_dump())

        if errors:
            print(
                f"{os.path.basename(file_path)} : {errors} ligne(s) ignorée(s) "
                f"sur {errors + len(documents)}."
            )
        print(f"{os.path.basename(file_path)} : {len(documents)} enregistrement(s).")

        return documents

    @staticmethod
    def _to_geojson(stop: Dict[str, Any]) -> Dict[str, Any]:
        """Remplace les champs lat/lon d'un arrêt par un point GeoJSON."""
        lat = stop.pop("lat", 0.0) or 0.0
        lon = stop.pop("lon", 0.0) or 0.0
        stop["location"] = {"type": "Point", "coordinates": [lon, lat]}
        return stop

    @staticmethod
    def _with_normalized_name(stop: Dict[str, Any]) -> Dict[str, Any]:
        """Ajoute à un arrêt la forme comparable de son nom, celle qu'interroge `searchStops`."""
        stop["name_normalized"] = normalize_for_search(stop.get("name"))
        return stop

    def _denormalize_stop_times(self, result: Dict[str, List[Dict[str, Any]]]) -> None:
        """
        Recopie dans chaque stop_time les informations de son trajet et de sa
        ligne. La donnée GTFS étant figée entre deux ingestions, cette
        duplication est sans risque de désynchronisation, et elle supprime une
        double jointure sur le chemin le plus sollicité de l'API.
        """
        trips_by_id = {trip["trip_id"]: trip for trip in result.get("trips", [])}
        routes_by_id = {route["route_id"]: route for route in result.get("routes", [])}

        for stop_time in result.get("stop_times", []):
            trip = trips_by_id.get(stop_time["trip_id"])
            route = routes_by_id.get(trip["route_id"]) if trip else None

            if trip:
                stop_time["headsign"] = trip.get("headsign")
                stop_time["direction_id"] = trip.get("direction_id")
                stop_time["service_id"] = trip.get("service_id")

            if route:
                stop_time["route_id"] = route["route_id"]
                stop_time["route_short_name"] = route.get("short_name")
                stop_time["route_long_name"] = route.get("long_name")
                stop_time["route_type"] = route.get("type")
                stop_time["route_color"] = route.get("color")
                stop_time["route_text_color"] = route.get("text_color")

            stop_time["departure_seconds"] = to_seconds(stop_time.get("departure_time"))
