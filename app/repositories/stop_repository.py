from typing import Any, Dict, List, Optional


class StopRepository:

    def __init__(self, db):
        self._collection = db["stops"]

    async def get_by_id(self, stop_id: str) -> Optional[Dict[str, Any]]:
        return await self._collection.find_one({"stop_id": stop_id})

    async def get_many_by_ids(self, stop_ids: List[str]) -> Dict[str, Dict[str, Any]]:

        cursor = self._collection.find({"stop_id": {"$in": stop_ids}})
        return {document["stop_id"]: document async for document in cursor}

    async def find_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
        limit: int,
        network_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        geo_near: Dict[str, Any] = {
            "near": {"type": "Point", "coordinates": [longitude, latitude]},
            "distanceField": "distance_meters",
            "maxDistance": radius_meters,
            "spherical": True,
        }
        if network_id:
            # Filtre appliqué pendant le parcours de l'index géospatial, et non
            # après : c'est bien plus efficace qu'un $match en aval.
            geo_near["query"] = {"network_id": network_id}

        pipeline = [{"$geoNear": geo_near}, {"$limit": limit}]

        return [document async for document in self._collection.aggregate(pipeline)]
