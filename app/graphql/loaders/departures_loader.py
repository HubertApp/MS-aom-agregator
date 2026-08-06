from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

from strawberry.dataloader import DataLoader

from app.repositories.stop_time_repository import StopTimeRepository


@dataclass(frozen=True)
class DeparturesKey:
    stop_id: str
    after_seconds: int
    limit: int


def build_departures_loader(repository: StopTimeRepository) -> DataLoader:
    async def load(keys: List[DeparturesKey]) -> List[List[Dict]]:
        by_parameters = defaultdict(list)
        for key in keys:
            by_parameters[(key.after_seconds, key.limit)].append(key.stop_id)

        results: Dict[DeparturesKey, List[Dict]] = {}
        for (after_seconds, limit), stop_ids in by_parameters.items():
            grouped = await repository.list_departures_for_stops(stop_ids, after_seconds, limit)
            for stop_id in stop_ids:
                results[DeparturesKey(stop_id, after_seconds, limit)] = grouped.get(stop_id, [])

        return [results.get(key, []) for key in keys]

    return DataLoader(load_fn=load)