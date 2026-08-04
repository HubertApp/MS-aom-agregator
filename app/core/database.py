from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import secrets

client = AsyncIOMotorClient(secrets.DATABASE_URL)
db = client.admin_db
registred_transit_network = db.registered_transit_network