from app.repositories.shape_repository import ShapeRepository
from app.repositories.stop_time_repository import StopTimeRepository
from app.repositories.trip_repository import TripRepository

TRAJETS = [
    {"trip_id": "N1:T1", "route_id": "N1:R1", "direction_id": 0,
     "headsign": "Centre-ville", "shape_id": "N1:SH1", "service_id": "N1:S1"},
    {"trip_id": "N1:T2", "route_id": "N1:R1", "direction_id": 1,
     "headsign": "Gare", "shape_id": "N1:SH2", "service_id": "N1:S1"},
    {"trip_id": "N1:T3", "route_id": "N1:R2", "direction_id": 0,
     "headsign": "Hôpital", "shape_id": "N1:SH3", "service_id": "N1:S2"},
]

POINTS = [
    {"shape_id": "N1:SH1", "pt_lat": 48.5, "pt_lon": 2.25, "pt_sequence": 3},
    {"shape_id": "N1:SH1", "pt_lat": 44.75, "pt_lon": 7.5, "pt_sequence": 1},
    {"shape_id": "N1:SH1", "pt_lat": 46.0, "pt_lon": 5.125, "pt_sequence": 2},
]

PASSAGES = [
    {"trip_id": "N1:T1", "stop_id": "N1:3", "stop_sequence": 3, "departure_seconds": 300,
     "departure_time": "00:05:00", "route_id": "N1:R1", "route_short_name": "1"},
    {"trip_id": "N1:T1", "stop_id": "N1:1", "stop_sequence": 1, "departure_seconds": 100,
     "departure_time": "00:01:40", "route_id": "N1:R1", "route_short_name": "1"},
    {"trip_id": "N1:T1", "stop_id": "N1:2", "stop_sequence": 2, "departure_seconds": 200,
     "departure_time": "00:03:20", "route_id": "N1:R1", "route_short_name": "1"},
    {"trip_id": "N1:T2", "stop_id": "N1:1", "stop_sequence": 1, "departure_seconds": 50,
     "departure_time": "00:00:50", "route_id": "N1:R1", "route_short_name": "1"},
]


async def _trajets(graphql_db):
    await graphql_db["trips"].insert_many([dict(trajet) for trajet in TRAJETS])
    return TripRepository(graphql_db)


async def _traces(graphql_db):
    await graphql_db["shapes"].insert_many([dict(point) for point in POINTS])
    return ShapeRepository(graphql_db)


async def _passages(graphql_db):
    await graphql_db["stop_times"].insert_many([dict(passage) for passage in PASSAGES])
    return StopTimeRepository(graphql_db)

async def test_les_trajets_de_plusieurs_lignes_sont_regroupes_par_ligne(graphql_db):
    repository = await _trajets(graphql_db)

    groupes = await repository.list_by_route_ids(["N1:R1", "N1:R2"])

    assert {ligne: [t["trip_id"] for t in trajets] for ligne, trajets in groupes.items()} == {
        "N1:R1": ["N1:T1", "N1:T2"],
        "N1:R2": ["N1:T3"],
    }


async def test_un_champ_liste_dans_la_projection_ressort_bien_du_trajet(graphql_db):
    repository = await _trajets(graphql_db)

    groupes = await repository.list_by_route_ids(["N1:R1"])

    assert groupes["N1:R1"][0]["headsign"] == "Centre-ville"


async def test_un_champ_absent_de_la_projection_n_est_pas_remonte(graphql_db):
    repository = await _trajets(graphql_db)

    groupes = await repository.list_by_route_ids(["N1:R1"])

    assert "service_id" not in groupes["N1:R1"][0]


async def test_une_ligne_sans_aucun_trajet_est_absente_du_resultat(graphql_db):
    repository = await _trajets(graphql_db)

    groupes = await repository.list_by_route_ids(["N1:R1", "N1:sans-trajet"])

    assert "N1:sans-trajet" not in groupes


async def test_le_resultat_des_trajets_est_un_defaultdict_qui_cree_la_cle_a_la_lecture(graphql_db):
    repository = await _trajets(graphql_db)

    groupes = await repository.list_by_route_ids(["N1:R1"])

    assert groupes["N1:sans-trajet"] == []

async def test_les_points_d_un_trace_sont_ordonnes_par_rang(graphql_db):
    repository = await _traces(graphql_db)

    traces = await repository.list_points_for_shapes(["N1:SH1"])

    assert traces["N1:SH1"] == [[7.5, 44.75], [5.125, 46.0], [2.25, 48.5]]


async def test_les_points_d_un_trace_sont_en_longitude_puis_latitude(graphql_db):
    repository = await _traces(graphql_db)

    traces = await repository.list_points_for_shapes(["N1:SH1"])

    assert traces["N1:SH1"][0] == [7.5, 44.75]


async def test_un_trace_inconnu_est_absent_du_resultat_sans_lever(graphql_db):
    repository = await _traces(graphql_db)

    traces = await repository.list_points_for_shapes(["N1:SH1", "N1:trace-fantome"])

    assert "N1:trace-fantome" not in traces


async def test_le_nombre_d_arrets_est_compte_pour_chaque_trajet_demande(graphql_db):
    repository = await _passages(graphql_db)

    comptes = await repository.count_by_trips(["N1:T1", "N1:T2"])

    assert comptes == {"N1:T1": 3, "N1:T2": 1}


async def test_un_trajet_sans_passage_est_absent_du_comptage(graphql_db):
    repository = await _passages(graphql_db)

    comptes = await repository.count_by_trips(["N1:T1", "N1:T-vide"])

    assert "N1:T-vide" not in comptes


async def test_les_arrets_d_un_trajet_sont_ordonnes_par_rang_de_desserte(graphql_db):
    repository = await _passages(graphql_db)

    dessertes = await repository.list_for_trips(["N1:T1"])

    assert [p["stop_id"] for p in dessertes["N1:T1"]] == ["N1:1", "N1:2", "N1:3"]


async def test_les_dessertes_de_plusieurs_trajets_sont_regroupees_par_trajet(graphql_db):
    repository = await _passages(graphql_db)

    dessertes = await repository.list_for_trips(["N1:T1", "N1:T2"])

    assert {trajet: len(passages) for trajet, passages in dessertes.items()} == {
        "N1:T1": 3, "N1:T2": 1,
    }

async def test_les_departs_anterieurs_a_l_heure_demandee_sont_ecartes(graphql_db):
    repository = await _passages(graphql_db)

    departs = await repository.list_departures_for_stops(["N1:1"], after_seconds=100, limit=10)

    assert [d["trip_id"] for d in departs["N1:1"]] == ["N1:T1"]


async def test_les_departs_d_un_arret_sont_rendus_du_plus_proche_au_plus_lointain(graphql_db):
    repository = await _passages(graphql_db)

    departs = await repository.list_departures_for_stops(["N1:1"], after_seconds=0, limit=10)

    assert [d["departure_seconds"] for d in departs["N1:1"]] == [50, 100]


async def test_seuls_les_premiers_departs_demandes_sont_rendus(graphql_db):
    repository = await _passages(graphql_db)

    departs = await repository.list_departures_for_stops(["N1:1"], after_seconds=0, limit=1)

    assert [d["trip_id"] for d in departs["N1:1"]] == ["N1:T2"]


async def test_les_departs_de_plusieurs_arrets_sont_recuperes_en_une_seule_requete(graphql_db):
    repository = await _passages(graphql_db)

    departs = await repository.list_departures_for_stops(
        ["N1:1", "N1:2", "N1:3"], after_seconds=0, limit=10
    )

    assert {arret: len(passages) for arret, passages in departs.items()} == {
        "N1:1": 2, "N1:2": 1, "N1:3": 1,
    }


async def test_un_arret_sans_aucun_depart_est_absent_du_resultat(graphql_db):
    repository = await _passages(graphql_db)

    departs = await repository.list_departures_for_stops(
        ["N1:1", "N1:desert"], after_seconds=0, limit=10
    )

    assert "N1:desert" not in departs


async def test_les_departs_conservent_les_champs_denormalises_de_la_ligne(graphql_db):
    repository = await _passages(graphql_db)

    departs = await repository.list_departures_for_stops(["N1:1"], after_seconds=0, limit=1)

    assert departs["N1:1"][0]["route_short_name"] == "1"

PASSAGES_LIGNES = [
    {"stop_id": "N1:1", "route_id": "N1:R1", "route_short_name": "1",
     "route_long_name": "Ligne 1 - Centre", "route_type": 0,
     "route_color": "FF0000", "route_text_color": "FFFFFF", "network_id": "N1"},
    {"stop_id": "N1:1", "route_id": "N1:R1", "route_short_name": "1",
     "route_long_name": "Ligne 1 - Centre", "route_type": 0,
     "route_color": "FF0000", "route_text_color": "FFFFFF", "network_id": "N1"},
    {"stop_id": "N1:1", "route_id": "N1:R2", "route_short_name": "2",
     "route_long_name": "Ligne 2 - Nord", "route_type": 3,
     "route_color": "0000FF", "route_text_color": "FFFFFF", "network_id": "N1"},
    {"stop_id": "N1:1"},  # passage sans route_id : ligne non retrouvée à l'ingestion
    {"stop_id": "N1:2", "route_id": "N1:R3", "route_short_name": "3",
     "route_long_name": "Ligne 3 - Sud", "route_type": 3,
     "route_color": "00FF00", "route_text_color": "000000", "network_id": "N1"},
]


async def _passages_lignes(graphql_db):
    await graphql_db["stop_times"].insert_many([dict(passage) for passage in PASSAGES_LIGNES])
    return StopTimeRepository(graphql_db)


async def test_les_lignes_d_un_arret_sont_dedupliquees(graphql_db):
    repository = await _passages_lignes(graphql_db)

    lignes = await repository.list_distinct_routes_for_stops(["N1:1"])

    assert {ligne["route_id"] for ligne in lignes["N1:1"]} == {"N1:R1", "N1:R2"}
    assert len(lignes["N1:1"]) == 2


async def test_un_passage_sans_route_id_n_ajoute_aucune_ligne(graphql_db):
    repository = await _passages_lignes(graphql_db)

    lignes = await repository.list_distinct_routes_for_stops(["N1:1"])

    assert None not in {ligne["route_id"] for ligne in lignes["N1:1"]}


async def test_les_lignes_conservent_leurs_champs_denormalises(graphql_db):
    repository = await _passages_lignes(graphql_db)

    lignes = await repository.list_distinct_routes_for_stops(["N1:1"])

    ligne_1 = next(ligne for ligne in lignes["N1:1"] if ligne["route_id"] == "N1:R1")
    assert ligne_1["route_short_name"] == "1"
    assert ligne_1["route_long_name"] == "Ligne 1 - Centre"
    assert ligne_1["route_type"] == 0
    assert ligne_1["route_color"] == "FF0000"
    assert ligne_1["route_text_color"] == "FFFFFF"
    assert ligne_1["network_id"] == "N1"


async def test_les_lignes_de_plusieurs_arrets_sont_recuperees_en_une_seule_requete(graphql_db):
    repository = await _passages_lignes(graphql_db)

    lignes = await repository.list_distinct_routes_for_stops(["N1:1", "N1:2"])

    assert {ligne["route_id"] for ligne in lignes["N1:2"]} == {"N1:R3"}


async def test_un_arret_sans_aucune_ligne_est_absent_du_resultat(graphql_db):
    repository = await _passages_lignes(graphql_db)

    lignes = await repository.list_distinct_routes_for_stops(["N1:1", "N1:desert"])

    assert "N1:desert" not in lignes