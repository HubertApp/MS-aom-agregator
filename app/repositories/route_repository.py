from typing import Any, Dict, List, Optional, Tuple

from pymongo import ASCENDING


class RouteRepository:

    def __init__(self, db):
        self._collection = db["routes"]

    async def get_many_by_ids(self, route_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        cursor = self._collection.find({"route_id": {"$in": route_ids}})
        return {document["route_id"]: document async for document in cursor}

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        network_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:

        query: Dict[str, Any] = {}
        if network_id:
            query["network_id"] = network_id

        total_count = await self._collection.count_documents(query)

        cursor = (
            self._collection.find(query)
            .sort([("short_name", ASCENDING), ("route_id", ASCENDING)])
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        return [document async for document in cursor], total_count
