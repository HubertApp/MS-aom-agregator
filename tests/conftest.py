from __future__ import annotations

import itertools
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.graphql import context as context_module
from app.services import ingestion_service as ingestion_module


FLUX_DE_REFERENCE: Dict[str, str] = {
    "agency.txt": (
        "agency_id,agency_name,agency_url,agency_timezone\n"
        "AG1,Réseau de test,https://example.org,Europe/Paris\n"
    ),
    "stops.txt": (
        "stop_id,stop_name,stop_lat,stop_lon,parent_station,location_type,wheelchair_boarding\n"
        "1,Gare Centrale,48.5,2.25,,1,1\n"
        "2,Place du Marché,49.75,3.5,1,0,2\n"
    ),
    "routes.txt": (
        "route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "R1,AG1,1,Ligne 1 - Centre,0\n"
    ),
    "trips.txt": (
        "trip_id,route_id,service_id,trip_headsign,direction_id,shape_id,block_id,wheelchair_accessible\n"
        "T1,R1,S1,Centre-ville,0,SH1,BLK-01,2\n"
    ),
    "stop_times.txt": (
        "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "T1,25:30:00,25:31:00,1,1\n"
        "T1,25:45:00,25:46:00,2,2\n"
    ),
    "calendar.txt": (
        "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "S1,1,1,1,1,1,0,0,20250101,20251231\n"
    ),
    "calendar_dates.txt": (
        "service_id,date,exception_type\n"
        "S1,20250501,2\n"
    ),
    "shapes.txt": (
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
        "SH1,48.5,2.25,1\n"
    ),
    "transfers.txt": (
        "from_stop_id,to_stop_id,transfer_type,min_transfer_time\n"
        "1,2,2,300\n"
    ),
}

# Quatre lignes d'arrêts dont deux sont volontairement invalides :
#  - ligne 3 : stop_id vide            -> rejetée (pas de clé primaire)
#  - ligne 5 : location_type non entier -> rejetée
# La ligne 4 (coordonnées vides) est en revanche parfaitement valide : les
# coordonnées manquantes retombent sur 0.0. Une colonne surnuméraire est
# présente partout pour vérifier qu'elle est ignorée sans erreur.
STOPS_AVEC_ERREURS = (
    "stop_id,stop_name,stop_lat,stop_lon,location_type,colonne_inconnue\n"
    "1,Arrêt valide,48.5,2.25,0,valeur ignorée\n"
    ",Arrêt sans identifiant,48.6,2.30,0,valeur ignorée\n"
    "3,Arrêt sans coordonnées,,,0,valeur ignorée\n"
    "4,Arrêt au type invalide,48.7,2.40,pas-un-entier,valeur ignorée\n"
)

@pytest.fixture
def ecrire_flux_gtfs(tmp_path: Path) -> Callable[..., Path]:

    compteur = itertools.count()

    def _ecrire(fichiers: Dict[str, str], encoding: str = "utf-8") -> Path:
        dossier = tmp_path / f"flux_{next(compteur)}"
        dossier.mkdir()
        for nom, contenu in fichiers.items():
            (dossier / nom).write_text(contenu, encoding=encoding)
        return dossier

    return _ecrire


@pytest.fixture
def gtfs_feed(ecrire_flux_gtfs: Callable[..., Path]) -> Path:
    return ecrire_flux_gtfs(FLUX_DE_REFERENCE)


@pytest.fixture
def gtfs_feed_with_errors(ecrire_flux_gtfs: Callable[..., Path]) -> Path:
    return ecrire_flux_gtfs({**FLUX_DE_REFERENCE, "stops.txt": STOPS_AVEC_ERREURS})


@pytest.fixture
def mock_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingestion_module.secrets, "DATABASE_URL", "mongodb://localhost:27017")
    monkeypatch.setattr(ingestion_module, "AsyncIOMotorClient", AsyncMongoMockClient)


@pytest.fixture
def service(mock_db: None) -> ingestion_module.IngestionService:
    return ingestion_module.IngestionService()


@pytest.fixture
def graphql_db():
    return AsyncMongoMockClient()["aom_db"]


@pytest.fixture
def mock_graphql_db(monkeypatch: pytest.MonkeyPatch):
    fake_db = AsyncMongoMockClient()["aom_db"]
    monkeypatch.setattr(context_module, "db", fake_db)
    return fake_db

class FakeLoader:
    """Double de `DataLoader` : renvoie une valeur préparée et retient les clés reçues."""

    def __init__(self, results: Optional[Dict[Any, Any]] = None, default: Any = None):
        self._results = dict(results or {})
        self._default = default
        self.calls: List[Any] = []

    async def load(self, key: Any) -> Any:
        self.calls.append(key)
        return self._results.get(key, self._default)

    async def load_many(self, keys: List[Any]) -> List[Any]:
        return [await self.load(key) for key in keys]


class FakeStopRepository:

    def __init__(
        self,
        documents: Optional[Dict[str, Dict[str, Any]]] = None,
        nearby: Optional[List[Dict[str, Any]]] = None,
        matching: Optional[List[Dict[str, Any]]] = None,
    ):
        self._documents = dict(documents or {})
        self._nearby = list(nearby or [])
        self._matching = list(matching or [])
        self.batches: List[List[str]] = []
        self.calls: List[Dict[str, Any]] = []
        self.search_calls: List[Dict[str, Any]] = []

    async def get_many_by_ids(self, stop_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        self.batches.append(list(stop_ids))
        return {
            stop_id: document
            for stop_id, document in self._documents.items()
            if stop_id in stop_ids
        }

    async def find_nearby(self, **arguments: Any) -> List[Dict[str, Any]]:
        self.calls.append(arguments)
        return list(self._nearby)

    async def search_by_name(self, **arguments: Any) -> List[Dict[str, Any]]:
        self.search_calls.append(arguments)
        return list(self._matching)


class FakeRouteRepository:

    def __init__(
        self,
        documents: Optional[Dict[str, Dict[str, Any]]] = None,
        paginated: Optional[List[Dict[str, Any]]] = None,
        total_count: int = 0,
    ):
        self._documents = dict(documents or {})
        self._paginated = list(paginated or [])
        self._total_count = total_count
        self.batches: List[List[str]] = []
        self.calls: List[Dict[str, Any]] = []

    async def get_many_by_ids(self, route_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        self.batches.append(list(route_ids))
        return {
            route_id: document
            for route_id, document in self._documents.items()
            if route_id in route_ids
        }

    async def list_paginated(self, **arguments: Any):
        self.calls.append(arguments)
        return list(self._paginated), self._total_count


class FakeTripRepository:

    def __init__(self, trips_by_route: Optional[Dict[str, List[Dict[str, Any]]]] = None):
        self._trips_by_route = dict(trips_by_route or {})
        self.calls: List[List[str]] = []

    async def list_by_route_ids(self, route_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        self.calls.append(list(route_ids))
        # Comme le vrai repository : une ligne sans trajet est absente du résultat.
        return {
            route_id: self._trips_by_route[route_id]
            for route_id in route_ids
            if route_id in self._trips_by_route
        }


class FakeStopTimeRepository:

    def __init__(
        self,
        counts_by_trip: Optional[Dict[str, int]] = None,
        stops_by_trip: Optional[Dict[str, List[str]]] = None,
        departures_by_stop: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ):
        self._counts_by_trip = dict(counts_by_trip or {})
        self._stops_by_trip = dict(stops_by_trip or {})
        self._departures_by_stop = dict(departures_by_stop or {})
        self.count_calls: List[List[str]] = []
        self.list_calls: List[List[str]] = []
        self.departure_calls: List[Dict[str, Any]] = []

    async def count_by_trips(self, trip_ids: List[str]) -> Dict[str, int]:
        self.count_calls.append(list(trip_ids))
        return {
            trip_id: self._counts_by_trip[trip_id]
            for trip_id in trip_ids
            if trip_id in self._counts_by_trip
        }

    async def list_for_trips(self, trip_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        self.list_calls.append(list(trip_ids))
        return {
            trip_id: [{"trip_id": trip_id, "stop_id": stop_id, "stop_sequence": rang}
                      for rang, stop_id in enumerate(self._stops_by_trip[trip_id], start=1)]
            for trip_id in trip_ids
            if trip_id in self._stops_by_trip
        }

    async def list_departures_for_stops(
        self,
        stop_ids: List[str],
        after_seconds: int,
        limit: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        self.departure_calls.append(
            {"stop_ids": list(stop_ids), "after_seconds": after_seconds, "limit": limit}
        )
        return {
            stop_id: self._departures_by_stop[stop_id]
            for stop_id in stop_ids
            if stop_id in self._departures_by_stop
        }


class FakeShapeRepository:

    def __init__(self, points_by_shape: Optional[Dict[str, List[List[float]]]] = None):
        self._points_by_shape = dict(points_by_shape or {})
        self.calls: List[List[str]] = []

    async def list_points_for_shapes(self, shape_ids: List[str]) -> Dict[str, List[List[float]]]:
        self.calls.append(list(shape_ids))
        return {
            shape_id: self._points_by_shape[shape_id]
            for shape_id in shape_ids
            if shape_id in self._points_by_shape
        }


def build_fake_context(**overrides: Any) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "stop_loader": FakeLoader(),
        "departures_loader": FakeLoader(default=[]),
        "route_loader": FakeLoader(),
        "route_directions_loader": FakeLoader(default=[]),
        "stop_routes_loader": FakeLoader(default=[]),
        "stop_repository": FakeStopRepository(),
        "route_repository": FakeRouteRepository(),
    }
    context.update(overrides)
    return context


def fake_info(**overrides: Any) -> SimpleNamespace:
    return SimpleNamespace(context=build_fake_context(**overrides))
