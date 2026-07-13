# app/services/parsers/gtfs_parser.py
import asyncio
import csv
import os
from typing import List, Dict, Any

from app.graphql.types.gtfs_data import GTFSData
from app.services.parsers.i_parser import IParser


class GTFSParser(IParser):
    """
    Parseur GTFS : lit les fichiers .txt dézippés et les convertit en modèle standardisé.
    """

    async def parse(self, directory_path: str):
        print(f"🔍 [GTFSParser] Démarrage de l'analyse dans : {directory_path}")
        raw_agencies = await asyncio.to_thread(self._read_and_map_agencies, os.path.join(directory_path, "agency.txt"))
        raw_routes = await asyncio.to_thread(self._read_and_map_routes, os.path.join(directory_path, "routes.txt"))
        raw_stops = await asyncio.to_thread(self._read_and_map_stops, os.path.join(directory_path, "stops.txt"))
        raw_trips = await asyncio.to_thread(self._read_and_map_trips, os.path.join(directory_path, "trips.txt"))
        raw_stop_times = await asyncio.to_thread(self._read_and_map_stop_times,
                                                 os.path.join(directory_path, "stop_times.txt"))
        raw_calendar = await asyncio.to_thread(self._read_and_map_calendar,
                                               os.path.join(directory_path, "calendar.txt"))
        raw_calendar_dates = await asyncio.to_thread(self._read_and_map_calendar_dates,"calendar_dates.txt")
        print(
            f"✅ [GTFSParser] Fin du parsing ! "
            f"({len(raw_agencies)} agences, {len(raw_routes)} lignes, {len(raw_stops)} arrêts, "
            f"{len(raw_trips)} trips, {len(raw_stop_times)} horaires, "
            f"{len(raw_calendar)} calendriers, {len(raw_calendar_dates)} dates d'exception)"
        )
        return GTFSData(
            agencies= raw_agencies,
            routes =raw_routes,
            stops=raw_stops,
            stop_times= raw_stop_times,
            calendar= raw_calendar,
            calendar_dates= raw_calendar_dates,
            trips= raw_trips
        )

    def _read_and_map_agencies(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mapped_data.append({
                    "id": row.get("agency_id", "default"),
                    "name": row.get("agency_name"),
                    "url": row.get("agency_url"),
                    "timezone": row.get("agency_timezone")
                })
        return mapped_data

    def _read_and_map_stops(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lat = float(row["stop_lat"]) if row.get("stop_lat") else 0.0
                lon = float(row["stop_lon"]) if row.get("stop_lon") else 0.0

                mapped_data.append({
                    "stop_id": row.get("stop_id"),
                    "name": row.get("stop_name"),
                    "location": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    }
                })
        return mapped_data

    def _read_and_map_routes(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mapped_data.append({
                    "route_id": row.get("route_id"),
                    "short_name": row.get("route_short_name"),
                    "long_name": row.get("route_long_name"),
                    "type": int(row["route_type"]) if row.get("route_type") else 3
                })
        return mapped_data

    def _read_and_map_trips(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mapped_data.append({
                    "trip_id": row.get("trip_id"),
                    "route_id": row.get("route_id"),
                    "service_id": row.get("service_id"),
                    "headsign": row.get("trip_headsign"),
                    "direction_id": int(row["direction_id"]) if row.get("direction_id") and row[
                        "direction_id"].isdigit() else 0,
                    "shape_id": row.get("shape_id")
                })
        return mapped_data

    def _read_and_map_stop_times(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                seq = int(row["stop_sequence"]) if row.get("stop_sequence") and row["stop_sequence"].isdigit() else 0

                mapped_data.append({
                    "trip_id": row.get("trip_id"),
                    "arrival_time": row.get("arrival_time"),
                    "departure_time": row.get("departure_time"),
                    "stop_id": row.get("stop_id"),
                    "stop_sequence": seq
                })
        return mapped_data

    def _read_and_map_calendar(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                mapped_data.append({
                    "service_id": row.get("service_id"),
                    "monday": int(row.get("monday", 0)),
                    "tuesday": int(row.get("tuesday", 0)),
                    "wednesday": int(row.get("wednesday", 0)),
                    "thursday": int(row.get("thursday", 0)),
                    "friday": int(row.get("friday", 0)),
                    "saturday": int(row.get("saturday", 0)),
                    "sunday": int(row.get("sunday", 0)),
                    "start_date": row.get("start_date"),
                    "end_date": row.get("end_date")
                })
        return mapped_data

    def _read_and_map_calendar_dates(self, file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []

        mapped_data = []
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                exception_type = int(row["exception_type"]) if row.get("exception_type") and row[
                    "exception_type"].isdigit() else 0

                mapped_data.append({
                    "service_id": row.get("service_id"),
                    "date": row.get("date"),  # Format YYYYMMDD
                    "exception_type": exception_type
                })
        return mapped_data
