# run_worker.py
import asyncio
from app.workers.callbacks.gtfs_callback import router
from faststream import FastStream
from app.core.broker import broker

broker.include_router(router)

app = FastStream(broker)

if __name__ == "__main__":
    asyncio.run(app.run())
