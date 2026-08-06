from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import secrets

client = AsyncIOMotorClient(secrets.DATABASE_URL)
db = client["aom_db"]