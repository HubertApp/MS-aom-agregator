import uuid
from typing import Any, Dict, List

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, GEOSPHERE

from app.core.config import secrets
from app.services.parsers.factory import ParserFactory


class IngestionService:
    BATCH_SIZE = 5_000

    def __init__(self):
        self.client = AsyncIOMotorClient(secrets.DATABASE_URL)
        self.db = self.client["aom_db"]

    async def ingest_datas(self, directory_path: str, format_type: str, network_id: str):
        parser = ParserFactory.get_parser(format_type)
        standardized_data = await parser.parse(directory_path, network_id)
        await self._save_to_mongodb(standardized_data, network_id)
        print("[IngestionService] Ingestion terminée avec succès !")

    async def _save_to_mongodb(self, data: Dict[str, List[Dict[str, Any]]], network_id: str):
        ingestion_id = uuid.uuid4().hex

        print(f"[Ingestion {ingestion_id[:8]}] Phase 1 : écriture des nouveaux documents (réseau {network_id})...")

        written_collections = []

        for collection_name, documents in data.items():
            if not documents:
                # Un fichier absent ou vide ne doit pas entraîner la suppression des données existantes : on préfère conserver la version précédente plutôt que de vider la collection par accident
                print(f"{collection_name} : aucune donnée, collection laissée en l'état.")
                continue

            collection = self.db[collection_name]

            for document in documents:
                document["network_id"] = network_id
                document["_ingestion_id"] = ingestion_id

            for start in range(0, len(documents), self.BATCH_SIZE):
                await collection.insert_many(documents[start:start + self.BATCH_SIZE])

            await self._ensure_indexes(collection_name)
            written_collections.append(collection_name)
            print(f"{len(documents)} document(s) insérés dans {collection_name}.")

        print(f"[Ingestion {ingestion_id[:8]}] Phase 2 : purge de la version précédente du réseau...")

        for collection_name in written_collections:
            try:
                result = await self.db[collection_name].delete_many(
                    {"network_id": network_id, "_ingestion_id": {"$ne": ingestion_id}}
                )
                print(f"{collection_name} : {result.deleted_count} ancien(s) document(s) supprimé(s).")
            except Exception as e:
                print(f"Erreur lors de la purge de {collection_name} : {e}")

    async def _ensure_indexes(self, collection_name: str):

        collection = self.db[collection_name]

        await collection.create_index([("network_id", ASCENDING)])

        if collection_name == "stops":
            await collection.create_index([("location", GEOSPHERE)])
            await collection.create_index([("stop_id", ASCENDING)])
        elif collection_name == "stop_times":
            await collection.create_index([("stop_id", ASCENDING), ("departure_seconds", ASCENDING)])
            await collection.create_index([("trip_id", ASCENDING), ("stop_sequence", ASCENDING)])
            await collection.create_index([("network_id", ASCENDING), ("service_id", ASCENDING)])
        elif collection_name == "trips":
            await collection.create_index([("route_id", ASCENDING)])
            await collection.create_index([("service_id", ASCENDING)])
        elif collection_name == "routes":
            await collection.create_index([("route_id", ASCENDING)])
        elif collection_name == "shapes":
            await collection.create_index([("shape_id", ASCENDING), ("pt_sequence", ASCENDING)])
