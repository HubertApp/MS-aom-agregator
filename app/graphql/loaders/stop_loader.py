from typing import Dict, List, Optional

from strawberry.dataloader import DataLoader

from app.repositories.stop_repository import StopRepository


def build_stop_loader(repository: StopRepository) -> DataLoader:
    async def load(stop_ids: List[str]) -> List[Optional[Dict]]:
        found = await repository.get_many_by_ids(list(stop_ids))
        return [found.get(stop_id) for stop_id in stop_ids]

    return DataLoader(load_fn=load)