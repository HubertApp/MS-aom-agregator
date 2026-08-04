"""
Fixtures partagées de la campagne de tests d'ingestion.

Les flux GTFS de test sont écrits à la volée dans `tmp_path` plutôt que commités :
on teste de la logique, pas de la volumétrie, donc chaque fichier tient en deux
ou trois lignes.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Callable, Dict

import pytest
from mongomock_motor import AsyncMongoMockClient

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


# --------------------------------------------------------------------------- #
# MongoDB simulé
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ingestion_module.secrets, "DATABASE_URL", "mongodb://localhost:27017")
    monkeypatch.setattr(ingestion_module, "AsyncIOMotorClient", AsyncMongoMockClient)


@pytest.fixture
def service(mock_db: None) -> ingestion_module.IngestionService:
    return ingestion_module.IngestionService()
