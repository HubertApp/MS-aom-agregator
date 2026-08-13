# run_worker.py
import asyncio

# Doit s'exécuter avant tout autre import applicatif (voir app/main.py).
from app.otel_setup import setup_otel
setup_otel()

from app.workers.callbacks.gtfs_callback import router
from faststream import FastStream
from faststream.rabbit import RabbitBroker
from app.core.config import secrets
# Ne pas afficher RABBITMQ_URL (peut contenir des identifiants).
broker = RabbitBroker(secrets.RABBITMQ_URL)
broker.include_router(router)

app = FastStream(broker)

if __name__ == "__main__":
    asyncio.run(app.run())