"""Traduit des sequences de passages GTFS en noeuds et aretes de graphe."""

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

BOARDING_PENALTY_S = 30.0     # temps de montee dans le vehicule
ALIGHTING_COST_S = 5.0        # descente : quasi gratuit, mais non nul
MAX_WAIT_S = 1_800.0          # plafond d'attente : au-dela, la ligne n'est pas utile

LAYER_TRANSIT = 2
LAYER_CONNECTION = 3


def stop_node_id(stop_id: str) -> str:
    return f"gtfs:stop:{stop_id}"


def ride_node_id(route_id: str, direction_id: int, stop_id: str) -> str:
    return f"gtfs:ride:{route_id}|{direction_id}|{stop_id}"


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius_m = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_transit_graph(
    trip_sequences: Iterable[Dict[str, Any]],
    stops_by_id: Dict[str, Dict[str, Any]],
    window_seconds: int,
) -> Dict[str, List[Dict[str, Any]]]:
    """Construit la couche transit.

    Args:
        trip_sequences: un document par course, tel que renvoye par
            TransitGraphRepository.list_trip_sequences
        stops_by_id: documents `stops` indexes par stop_id (pour les coordonnees)
        window_seconds: largeur de la fenetre horaire, sert au calcul de frequence

    Returns:
        {"nodes": [...], "edges": [...]} en dictionnaires bruts.
    """
    ride_durations: Dict[Tuple[str, int, str, str], List[float]] = defaultdict(list)
    trips_per_line: Dict[Tuple[str, int], set] = defaultdict(set)
    line_labels: Dict[Tuple[str, int], str] = {}

    for trip in trip_sequences:
        route_id = trip.get("route_id")
        if not route_id:
            continue

        direction_id = int(trip.get("direction_id") or 0)
        line = (route_id, direction_id)
        trips_per_line[line].add(trip["_id"])

        if line not in line_labels:
            short_name = trip.get("route_short_name") or route_id
            headsign = trip.get("headsign")
            line_labels[line] = (
                f"Ligne {short_name} vers {headsign}" if headsign
                else f"Ligne {short_name}"
            )

        # Le tri se fait ici, pas dans Mongo : voir la note de l'etape 1b.
        passages = sorted(trip.get("stops") or [], key=lambda p: p.get("seq") or 0)

        for current, following in zip(passages, passages[1:]):
            duration = (following.get("t") or 0) - (current.get("t") or 0)
            if duration <= 0:
                # horaire absent, ou passage apres minuit mal encode : on ignore
                continue
            key = (route_id, direction_id, current["stop_id"], following["stop_id"])
            ride_durations[key].append(duration)

    # Frequence : n courses dans une fenetre de N secondes => un passage toutes les
    # N/n secondes. L'attente moyenne d'un voyageur qui arrive au hasard est la
    # moitie de cet intervalle.
    headway_by_line = {
        line: window_seconds / len(trip_ids)
        for line, trip_ids in trips_per_line.items()
        if trip_ids
    }

    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []
    boarding_points: set = set()
    alighting_points: set = set()

    def register_stop(stop_id: str) -> Optional[Dict[str, Any]]:
        document = stops_by_id.get(stop_id)
        if not document:
            return None
        coordinates = (document.get("location") or {}).get("coordinates") or []
        if len(coordinates) != 2:
            return None
        node_id = stop_node_id(stop_id)
        nodes.setdefault(node_id, {
            "id": node_id,
            "lon": float(coordinates[0]),
            "lat": float(coordinates[1]),
            "is_transit_stop": True,
        })
        return nodes[node_id]

    def register_ride(route_id: str, direction_id: int, stop_id: str):
        anchor = register_stop(stop_id)
        if anchor is None:
            return None
        node_id = ride_node_id(route_id, direction_id, stop_id)
        nodes.setdefault(node_id, {
            "id": node_id,
            "lon": anchor["lon"],
            "lat": anchor["lat"],
            "is_transit_stop": True,
        })
        return nodes[node_id]

    # --- Aretes de trajet (a bord du vehicule) ---
    for (route_id, direction_id, from_stop, to_stop), durations in ride_durations.items():
        source = register_ride(route_id, direction_id, from_stop)
        target = register_ride(route_id, direction_id, to_stop)
        if source is None or target is None:
            continue

        edges.append({
            "edge_id": f"ride:{route_id}|{direction_id}|{from_stop}->{to_stop}",
            "source_id": source["id"],
            "target_id": target["id"],
            "weight": sum(durations) / len(durations),
            "length": haversine_m(
                source["lon"], source["lat"], target["lon"], target["lat"]
            ),
            "layer": LAYER_TRANSIT,
            "transit_line_id": route_id,
            "name": line_labels.get((route_id, direction_id)),
        })
        boarding_points.add((route_id, direction_id, from_stop))
        alighting_points.add((route_id, direction_id, to_stop))

    # --- Aretes de montee : c'est ici que le temps entre dans le graphe ---
    for route_id, direction_id, stop_id in boarding_points:
        headway = headway_by_line.get((route_id, direction_id), MAX_WAIT_S * 2)
        wait = min(MAX_WAIT_S, headway / 2)
        edges.append({
            "edge_id": f"board:{route_id}|{direction_id}|{stop_id}",
            "source_id": stop_node_id(stop_id),
            "target_id": ride_node_id(route_id, direction_id, stop_id),
            "weight": wait + BOARDING_PENALTY_S,
            "length": 0.0,
            "layer": LAYER_CONNECTION,
            "transit_line_id": route_id,
            "name": line_labels.get((route_id, direction_id)),
        })

    # --- Aretes de descente ---
    for route_id, direction_id, stop_id in alighting_points:
        edges.append({
            "edge_id": f"alight:{route_id}|{direction_id}|{stop_id}",
            "source_id": ride_node_id(route_id, direction_id, stop_id),
            "target_id": stop_node_id(stop_id),
            "weight": ALIGHTING_COST_S,
            "length": 0.0,
            "layer": LAYER_CONNECTION,
            "transit_line_id": route_id,
            "name": "Descente",
        })

    return {"nodes": list(nodes.values()), "edges": edges}
