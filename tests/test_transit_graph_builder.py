from app.services.transit_graph_builder import build_transit_graph


def _stop(stop_id, lon, lat):
    return {"stop_id": stop_id, "location": {"type": "Point", "coordinates": [lon, lat]}}


def test_construit_les_aretes_de_trajet_et_de_montee():
    trip_sequences = [
        {
            "_id": "metz:trip1", "route_id": "metz:C1", "route_short_name": "C1",
            "direction_id": 0, "headsign": "Hopital",
            "stops": [
                {"stop_id": "metz:gare", "t": 28_920, "seq": 1},    # 08:02
                {"stop_id": "metz:mairie", "t": 29_220, "seq": 2},  # 08:07
            ],
        },
        {
            "_id": "metz:trip2", "route_id": "metz:C1", "route_short_name": "C1",
            "direction_id": 0, "headsign": "Hopital",
            "stops": [
                {"stop_id": "metz:gare", "t": 29_400, "seq": 1},
                {"stop_id": "metz:mairie", "t": 29_760, "seq": 2},
            ],
        },
    ]
    stops = {
        "metz:gare": _stop("metz:gare", 6.1757, 49.1193),
        "metz:mairie": _stop("metz:mairie", 6.1780, 49.1160),
    }

    graph = build_transit_graph(trip_sequences, stops, window_seconds=7200)

    edges = {edge["edge_id"]: edge for edge in graph["edges"]}
    ride = edges["ride:metz:C1|0|metz:gare->metz:mairie"]
    assert ride["weight"] == 330.0          # moyenne de 300 s et 360 s
    assert ride["layer"] == 2
    assert ride["transit_line_id"] == "metz:C1"

    # 2 courses en 7200 s => intervalle 3600 s => attente 1800 s, plafonnee
    board = edges["board:metz:C1|0|metz:gare"]
    assert board["weight"] == 1800.0 + 30.0
    assert board["source_id"] == "gtfs:stop:metz:gare"
    assert board["target_id"] == "gtfs:ride:metz:C1|0|metz:gare"


def test_ignore_les_passages_sans_horaire():
    trip_sequences = [{
        "_id": "t", "route_id": "r", "direction_id": 0,
        "stops": [
            {"stop_id": "a", "t": 0, "seq": 1},
            {"stop_id": "b", "t": 0, "seq": 2},
        ],
    }]
    stops = {"a": _stop("a", 6.0, 49.0), "b": _stop("b", 6.1, 49.1)}

    graph = build_transit_graph(trip_sequences, stops, window_seconds=3600)

    assert graph["edges"] == []
