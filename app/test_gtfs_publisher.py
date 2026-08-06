import asyncio
from faststream.rabbit import RabbitBroker

from app.core.config import secrets


async def run_test():
    async with RabbitBroker(secrets.RABBITMQ_URL) as broker:
        payload = {
            "url": "https://www.data.gouv.fr/api/1/datasets/r/92af6161-1b1a-4e0b-8f60-d97f213d993a",
            "network_id": "test-network",
            "extract_to": "./tmp_download"
        }

        print("Envoi du faux message à RabbitMQ...")
        await broker.publish(
            payload,
            queue="gtfs.file.available"
        )
        print("Message envoyé avec succès")


if __name__ == "__main__":
    asyncio.run(run_test())
