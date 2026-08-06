from pydantic import BaseModel
from faststream.rabbit import RabbitRouter
from app.clients.gtfs_format import GTFSFormat
from app.services.ingestion_service import IngestionService

router = RabbitRouter()


class GTFSFileEvent(BaseModel):
    url: str
    network_id: str
    extract_to: str = "/tmp/gtfs_data"


@router.subscriber("gtfs.file.available")  # type: ignore
async def handle_gtfs_available(message: GTFSFileEvent):
    print(f"Démarrage du traitement pour : {message.url} (network_id={message.network_id})")

    file_client = GTFSFormat()
    await file_client.download(download_dir="./tmp_download", url=message.url)
    await file_client.extract(extract_dir=message.extract_to)

    ingestion_service = IngestionService()

    await ingestion_service.ingest_datas(
        directory_path=message.extract_to,
        format_type="GTFS",
        network_id=message.network_id,
    )

    await file_client.clean()
    await file_client.delete_all_files(message.extract_to)

    print("Traitement complet terminé avec succès")
