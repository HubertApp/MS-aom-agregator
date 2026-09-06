# run_worker.py
import asyncio
from faststream import FastStream

from app.core.broker import broker
from app.core.topology import GTFS_INGESTION_RESULT
from app.workers.callbacks.gtfs_callback import router

# Le broker partagé (app/core/broker.py) est le seul point de connexion :
# le publisher déclaré sur le router doit être exposé par ce broker-là.
broker.include_router(router)

app = FastStream(broker)


@app.after_startup
async def declarer_topologie() -> None:
    """Déclare la queue de résultat, que le publisher ne déclare pas lui-même.

    Un publisher FastStream ne déclare que son exchange. Sans cette ligne, un
    résultat publié avant le premier démarrage du worker MS-Admin partirait
    dans le vide (ou, avec on_return_raises, échouerait bruyamment).
    """
    await broker.declare_queue(GTFS_INGESTION_RESULT)


if __name__ == "__main__":
    asyncio.run(app.run())
