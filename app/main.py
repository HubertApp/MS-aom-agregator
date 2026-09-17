from app.core.otel_setup import setup_otel, instrument_fastapi
setup_otel()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.core.config import properties
from app.graphql.context import get_context
from app.graphql.schema import schema
from app.core.broker import broker
import logging
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Connexion au serveur RabbitMQ")
    await broker.connect()
    yield
    await broker.disconnect()
    logger.info("Déconnexion du serveur RabbitMQ")

app = FastAPI(lifespan=lifespan)
instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix=properties.GRAPHQL_PREFIX)

instrument_fastapi(app)