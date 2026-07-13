import dataclasses
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import GEOSPHERE, ASCENDING

from app.core.config import secrets
from app.services.parsers.factory import ParserFactory


class IngestionService:

    def __init__(self):
        self.client = AsyncIOMotorClient(secrets.DATABASE_URL)
        self.db = self.client["aom_database"]

    async def ingest_datas(self, directory_path: str, format_type: str):
        parser = ParserFactory.get_parser(format_type)
        standardized_data = await parser.parse(directory_path)
        await self._save_to_mongodb_blue_green(standardized_data)
        print("🎉 [IngestionService] Ingestion Blue/Green terminée avec succès !")

    async def _save_to_mongodb_blue_green(self, data):
        timestamp = int(datetime.now().timestamp())

        if isinstance(data, dict):
            collections_mapping = data
        elif dataclasses.is_dataclass(data):
            collections_mapping = dataclasses.asdict(data)
        elif hasattr(data, "model_dump"):
            collections_mapping = data.model_dump(exclude_none=True, exclude_unset=True)
        else:
            raise TypeError("Le format de données passé à l'ingestion n'est pas supporté.")

        print("🟢 [Blue/Green] Phase 1 : Écriture dans les collections temporaires...")

        for base_name, dataset in collections_mapping.items():
            if not dataset:
                continue

            temp_collection_name = f"{base_name}_temp_{timestamp}"
            temp_collection = self.db[temp_collection_name]

            await temp_collection.insert_many(dataset)

            if base_name == "stops":
                await temp_collection.create_index([("location", GEOSPHERE)])
            elif base_name == "stop_times":
                await temp_collection.create_index([("stop_id", ASCENDING), ("departure_time", ASCENDING)])
            elif base_name == "trips":
                await temp_collection.create_index([("route_id", ASCENDING)])

            print(f"   ✓ {len(dataset)} documents insérés dans {temp_collection_name} (avec index).")

        print("🔵 [Blue/Green] Phase 2 : Bascule atomique (Renommage)...")
        for base_name, dataset in collections_mapping.items():
            if not dataset:
                continue

            temp_collection_name = f"{base_name}_temp_{timestamp}"

            source_ns = f"aom_database.{temp_collection_name}"
            target_ns = f"aom_database.{base_name}"

            try:
                await self.client.admin.command(
                    'renameCollection', source_ns,
                    to=target_ns,
                    dropTarget=True
                )
                print(f"   🔄 Bascule réussie : {temp_collection_name} -> {base_name}")
            except Exception as e:
                print(f"   ❌ Erreur lors de la bascule de {base_name} : {e}")