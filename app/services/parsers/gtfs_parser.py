# app/services/parsers/gtfs_parser.py
import asyncio
import csv
import os
from typing import Any, Dict, List, Type

from pydantic import ValidationError

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
)
from app.services.parsers.i_parser import IParser


class GTFSParser(IParser):
    """
    Parseur GTFS : lit les fichiers .txt dézippés et les convertit en documents
    prêts à être insérés en base.

    Toute la validation et la normalisation (typage, valeurs par défaut,
    préfixage des identifiants par le network_id) est déléguée aux modèles
    Pydantic de app/models/gtfs.py. Comme ces modèles déclarent les noms de
    colonnes GTFS en alias, chaque ligne brute de `csv.DictReader` leur est
    passée telle quelle.
    """

    # Association fichier GTFS -> (nom de la collection Mongo, modèle Pydantic).
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
        result["stops"] = [self._to_geojson(stop) for stop in result.get("stops", [])]

        print(
            "✅ [GTFSParser] Fin du parsing ! "
            + ", ".join(f"{len(docs)} {name}" for name, docs in result.items())
        )
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
            for line_number, row in enumerate(reader, start=2): # start 2 pour ignorer l'entete
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
