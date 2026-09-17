from __future__ import annotations

from typing import Any, Dict, List

import pytest
from faststream.rabbit import TestRabbitBroker

# L'import de run_worker câble le router sur le broker partagé : les tests
# vérifient donc aussi que le worker et le publisher utilisent le même broker.
from app.run_worker import broker as worker_broker
from app.core.topology import GTFS_FILE_AVAILABLE, GTFS_INGESTION_RESULT
from app.workers.callbacks import gtfs_callback


class FakeGTFSFormat:
    """Double de `GTFSFormat` : trace les appels et peut échouer à la demande."""

    instances: List["FakeGTFSFormat"] = []

    def __init__(self, download_error: Exception | None = None):
        self.download_error = download_error
        self.calls: List[str] = []
        FakeGTFSFormat.instances.append(self)

    async def download(self, download_dir: str = None, url: str = None) -> None:
        self.calls.append("download")
        if self.download_error:
            raise self.download_error

    async def extract(self, extract_dir: str = None, get_dir: str = None) -> None:
        self.calls.append("extract")

    async def clean(self) -> None:
        self.calls.append("clean")

    async def delete_all_files(self, dir_to_clean: str = None) -> None:
        self.calls.append("delete_all_files")


class FakeIngestionService:
    """Double d'`IngestionService` : retient le format reçu."""

    appels: List[Dict[str, Any]] = []

    async def ingest_datas(self, directory_path: str, format_type: str, network_id: str):
        FakeIngestionService.appels.append(
            {"directory_path": directory_path, "format_type": format_type, "network_id": network_id}
        )


@pytest.fixture(autouse=True)
def reinitialiser_doubles():
    FakeGTFSFormat.instances.clear()
    FakeIngestionService.appels.clear()
    gtfs_callback.result_publisher.mock.reset_mock()
    yield


@pytest.fixture
def client_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(gtfs_callback, "GTFSFormat", lambda: FakeGTFSFormat())
    monkeypatch.setattr(gtfs_callback, "IngestionService", FakeIngestionService)


@pytest.fixture
def client_en_echec(monkeypatch: pytest.MonkeyPatch):
    erreur = RuntimeError("404 Not Found")
    monkeypatch.setattr(gtfs_callback, "GTFSFormat", lambda: FakeGTFSFormat(download_error=erreur))
    monkeypatch.setattr(gtfs_callback, "IngestionService", FakeIngestionService)
    return erreur


MESSAGE = {
    "url": "https://example.org/gtfs.zip",
    "network_id": "63b4c3d2",
    "extract_to": "./tmp_test_extract",
}


# Le mock du publisher n'est instrumenté que le temps du contexte
# `TestRabbitBroker` : toutes les assertions doivent y rester.


async def test_succes_publie_un_statut_ok(client_ok):
    async with TestRabbitBroker(worker_broker) as br:
        await br.publish(MESSAGE, queue="gtfs.file.available")

        gtfs_callback.result_publisher.mock.assert_called_once_with(
            {"network_id": "63b4c3d2", "status": "ok", "error": None}
        )


async def test_format_par_defaut_gtfs(client_ok):
    async with TestRabbitBroker(worker_broker) as br:
        await br.publish(MESSAGE, queue="gtfs.file.available")

    assert FakeIngestionService.appels[0]["format_type"] == "GTFS"


async def test_format_du_message_est_transmis(client_ok):
    async with TestRabbitBroker(worker_broker) as br:
        await br.publish({**MESSAGE, "format": "NETEX"}, queue="gtfs.file.available")

    assert FakeIngestionService.appels[0]["format_type"] == "NETEX"


async def test_echec_publie_un_statut_error_puis_remonte(client_en_echec):
    async with TestRabbitBroker(worker_broker) as br:
        with pytest.raises(RuntimeError):
            await br.publish(MESSAGE, queue="gtfs.file.available")

        gtfs_callback.result_publisher.mock.assert_called_once_with(
            {"network_id": "63b4c3d2", "status": "error", "error": "404 Not Found"}
        )


async def test_format_inconnu_est_rejete(monkeypatch: pytest.MonkeyPatch):
    # Ici l'IngestionService réel est utilisé : c'est la ParserFactory qui doit refuser.
    monkeypatch.setattr(gtfs_callback, "GTFSFormat", lambda: FakeGTFSFormat())

    async with TestRabbitBroker(worker_broker) as br:
        with pytest.raises(ValueError):
            await br.publish({**MESSAGE, "format": "INCONNU"}, queue="gtfs.file.available")

        (payload,), _ = gtfs_callback.result_publisher.mock.call_args
        assert payload["status"] == "error"
        assert "INCONNU" in payload["error"]


async def test_nettoyage_effectue_meme_en_cas_d_echec(client_en_echec):
    async with TestRabbitBroker(worker_broker) as br:
        with pytest.raises(RuntimeError):
            await br.publish(MESSAGE, queue="gtfs.file.available")

    assert FakeGTFSFormat.instances[0].calls == ["download", "clean", "delete_all_files"]


# La topologie est dupliquée à l'identique dans MS-Admin : toute divergence de
# ces paramètres provoquerait un PRECONDITION_FAILED au démarrage. Ce test force
# une modification consciente, à répercuter dans les deux dépôts.
@pytest.mark.parametrize("queue", [GTFS_FILE_AVAILABLE, GTFS_INGESTION_RESULT])
def test_parametres_de_declaration_des_queues(queue):
    assert queue.durable is True
    assert queue.exclusive is False
    assert queue.auto_delete is False
    assert queue.arguments == {"x-queue-type": "classic"}
