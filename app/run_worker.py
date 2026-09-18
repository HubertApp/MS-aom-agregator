# run_worker.py

from app.core.otel_setup import setup_otel

setup_otel()

import asyncio
from app.workers.callbacks.gtfs_callback import router
from faststream import FastStream
from app.core.broker import broker
from app.core.topology import GTFS_INGESTION_RESULT

broker.include_router(router)

app = FastStream(broker)

@app.after_startup
async def declarer_topologie() -> None:
    await broker.declare_queue(GTFS_INGESTION_RESULT)

if __name__ == "__main__":
    asyncio.run(app.run())
