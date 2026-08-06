from typing import Any, Dict, List

from strawberry.dataloader import DataLoader

from app.repositories.stop_time_repository import StopTimeRepository


def build_stop_routes_loader(repository: StopTimeRepository) -> DataLoader:
    async def load(stop_ids: List[str]) -> List[List[Dict[str, Any]]]:
        grouped = await repository.list_distinct_routes_for_stops(list(stop_ids))
        return [grouped.get(stop_id, []) for stop_id in stop_ids]

    return DataLoader(load_fn=load)