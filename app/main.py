from contextlib import asynccontextmanager

# Doit s'exécuter avant tout autre import applicatif : instrumente les
# imports suivants (httpx, logging...) dès qu'ils sont chargés.
from app.otel_setup import setup_otel, instrument_fastapi
setup_otel()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.core.config import properties
from app.graphql.context import get_context
from app.graphql.schema import schema
from app.core.broker import broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connexion du serveur RabbitMQ")
    await broker.connect()
    yield
    await broker.disconnect()
    print("Deconnexion du serveur RabbitMQ")


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