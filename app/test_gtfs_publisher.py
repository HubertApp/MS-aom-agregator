import asyncio

from app.core.broker import broker
from app.core.topology import GTFS_FILE_AVAILABLE


async def run_test():
    async with broker:
        # Déclaration explicite : ce script est le point d'entrée de `make seed`,
        # il peut donc tourner avant que le worker n'ait déclaré la queue.
        await broker.declare_queue(GTFS_FILE_AVAILABLE)

        payload = {
            "url": "https://www.data.gouv.fr/api/1/datasets/r/92af6161-1b1a-4e0b-8f60-d97f213d993a",
            "network_id": "test-network",
            "format": "GTFS",
            "extract_to": "./tmp_download",
        }

        print("Envoi du faux message à RabbitMQ...")
        await broker.publish(payload, queue=GTFS_FILE_AVAILABLE, persist=True)
        print("Message envoyé avec succès")


if __name__ == "__main__":
    asyncio.run(run_test())
