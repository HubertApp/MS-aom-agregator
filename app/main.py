from contextlib import asynccontextmanager

from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from app.core.config import properties
#from app.graphql.schema import schema
from fastapi.middleware.cors import CORSMiddleware

from app.run_worker import broker

#graphql_app = GraphQLRouter(
 #   schema
#)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connexion du serveur RabbitMQ")
    await broker.connect()
    yield
    await broker.disconnect()
    print("Deconnexion du serveur RabbitMQ")
app = FastAPI()
#app.include_router(graphql_app, prefix=properties.GRAPHQL_PREFIX)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)