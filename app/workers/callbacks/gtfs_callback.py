from datetime import datetime, timezone

from pydantic import BaseModel
from faststream.rabbit import RabbitRouter
from app.clients.gtfs_format import GTFSFormat
from app.core.topology import GTFS_FILE_AVAILABLE, GTFS_INGESTION_RESULT
from app.services.ingestion_service import IngestionService

router = RabbitRouter()

# Fil de retour vers MS-Admin : sans lui, un réseau resterait indéfiniment en
# PENDING_AGGREGATION. persist=True car un résultat perdu au redémarrage du
# broker laisserait le réseau dans le même état bloqué.
result_publisher = router.publisher(GTFS_INGESTION_RESULT, persist=True)


class GTFSFileEvent(BaseModel):
    url: str
    network_id: str
    format: str = "GTFS"
    extract_to: str = "/tmp/gtfs_data"


@router.subscriber(GTFS_FILE_AVAILABLE)  # type: ignore
async def handle_gtfs_available(message: GTFSFileEvent):
    print(
        f"Démarrage du traitement pour : {message.url} "
        f"(network_id={message.network_id}, format={message.format})"
    )

    file_client = GTFSFormat()

    try:
        await file_client.download(download_dir="./tmp_download", url=message.url)
        await file_client.extract(extract_dir=message.extract_to)

        ingestion_service = IngestionService()

        await ingestion_service.ingest_datas(
            directory_path=message.extract_to,
            format_type=message.format,
            network_id=message.network_id,
        )

        print("Traitement complet terminé avec succès")

        await result_publisher.publish({
            "network_id": message.network_id,
            "status": "ok",
            "error": None,
        })

    except Exception as e:
        print(f"Échec du traitement pour le réseau {message.network_id} : {e}")

        try:
            await result_publisher.publish({
                "network_id": message.network_id,
                "status": "error",
                "error": str(e),
            })
        except Exception as publish_error:
            print(f"Impossible de publier le résultat en erreur : {publish_error}")
        raise

    finally:
        await _nettoyer(file_client, message.extract_to)


async def _nettoyer(file_client: GTFSFormat, extract_to: str) -> None:
    """Nettoie les fichiers temporaires sans jamais masquer le résultat du traitement."""
    try:
        await file_client.clean()
        await file_client.delete_all_files(extract_to)
    except Exception as e:
        print(f"Erreur lors du nettoyage des fichiers temporaires : {e}")
