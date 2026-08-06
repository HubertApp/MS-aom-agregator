from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.core.config import properties
from app.graphql.context import get_context
from app.graphql.schema import schema
from app.run_worker import broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connexion du serveur RabbitMQ")
    await broker.connect()
    yield
    await broker.disconnect()
    print("Deconnexion du serveur RabbitMQ")


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graphql_app = GraphQLRouter(schema, context_getter=get_context)
app.include_router(graphql_app, prefix=properties.GRAPHQL_PREFIX)