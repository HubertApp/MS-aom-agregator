import asyncio
from faststream.rabbit import RabbitBroker

from app.core.config import secrets


async def run_test():
    # On se connecte au même RabbitMQ que le worker
    async with RabbitBroker(secrets.RABBITMQ_URL) as broker:
        # Le payload qui correspond exactement à ton modèle Pydantic GtfsFileEvent
        payload = {
            # ⚠️ Remplace ceci par une vraie URL pointant vers un fichier ZIP GTFS
            # (Prends un petit réseau pour que le test soit rapide !)
            "url": "https://www.data.gouv.fr/api/1/datasets/r/92af6161-1b1a-4e0b-8f60-d97f213d993a",

            # On extrait dans un dossier local pour que tu puisses vérifier visuellement
            "extract_to": "./tmp_download"
        }

        print("🚀 Envoi du faux message à RabbitMQ...")
        await broker.publish(
            payload,
            queue="gtfs.file.available"
        )
        print("✅ Message envoyé avec succès !")


if __name__ == "__main__":
    asyncio.run(run_test())