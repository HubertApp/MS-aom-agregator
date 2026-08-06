
import asyncio

from tests.conftest import (
    FakeRouteRepository,
    FakeShapeRepository,
    FakeStopRepository,
    FakeStopTimeRepository,
    FakeTripRepository,
)

from app.graphql.loaders.departures_loader import DeparturesKey, build_departures_loader
from app.graphql.loaders.route_loader import build_route_directions_loader, build_route_loader
from app.graphql.loaders.stop_loader import build_stop_loader

ARRETS = {
    "N1:1": {"stop_id": "N1:1", "name": "Gare Centrale", "network_id": "N1"},
    "N1:2": {"stop_id": "N1:2", "name": "Place du Marché", "network_id": "N1"},
    "N1:3": {"stop_id": "N1:3", "name": "Hôpital", "network_id": "N1"},
}

LIGNES = {
    "N1:R1": {"route_id": "N1:R1", "short_name": "1", "network_id": "N1"},
    "N1:R2": {"route_id": "N1:R2", "short_name": "2", "network_id": "N1"},
}


async def test_les_arrets_reviennent_dans_l_ordre_demande_et_non_celui_du_repository():
    loader = build_stop_loader(FakeStopRepository(documents=ARRETS))

    documents = await loader.load_many(["N1:3", "N1:1", "N1:2"])

    assert [document["stop_id"] for document in documents] == ["N1:3", "N1:1", "N1:2"]


async def test_un_arret_introuvable_donne_none_a_sa_place_sans_decaler_les_autres():
    loader = build_stop_loader(FakeStopRepository(documents=ARRETS))

    documents = await loader.load_many(["N1:1", "N1:inconnu", "N1:2"])

    assert [d["stop_id"] if d else None for d in documents] == ["N1:1", None, "N1:2"]


async def test_un_arret_demande_deux_fois_n_est_charge_qu_une_seule_fois():
    repository = FakeStopRepository(documents=ARRETS)
    loader = build_stop_loader(repository)

    await loader.load_many(["N1:1", "N1:2", "N1:1"])

    assert repository.batches == [["N1:1", "N1:2"]]

async def test_les_lignes_reviennent_dans_l_ordre_demande_et_non_celui_du_repository():
    loader = build_route_loader(FakeRouteRepository(documents=LIGNES))

    documents = await loader.load_many(["N1:R2", "N1:R1"])

    assert [document["route_id"] for document in documents] == ["N1:R2", "N1:R1"]


async def test_une_ligne_introuvable_donne_none_a_sa_place_sans_decaler_les_autres():
    loader = build_route_loader(FakeRouteRepository(documents=LIGNES))

    documents = await loader.load_many(["N1:R1", "N1:inconnue"])

    assert [d["route_id"] if d else None for d in documents] == ["N1:R1", None]


async def test_une_ligne_demandee_deux_fois_n_est_chargee_qu_une_seule_fois():
    repository = FakeRouteRepository(documents=LIGNES)
    loader = build_route_loader(repository)

    await loader.load_many(["N1:R1", "N1:R1"])

    assert repository.batches == [["N1:R1"]]

DEPARTS = {
    "N1:1": [{"trip_id": "N1:T1", "route_id": "N1:R1", "departure_time": "08:00:00"}],
    "N1:2": [{"trip_id": "N1:T2", "route_id": "N1:R1", "departure_time": "08:05:00"}],
}


async def test_deux_arrets_aux_memes_criteres_partagent_une_seule_requete():
    repository = FakeStopTimeRepository(departures_by_stop=DEPARTS)
    loader = build_departures_loader(repository)

    await loader.load_many([
        DeparturesKey("N1:1", after_seconds=0, limit=10),
        DeparturesKey("N1:2", after_seconds=0, limit=10),
    ])

    assert len(repository.departure_calls) == 1


async def test_les_arrets_aux_memes_criteres_sont_regroupes_dans_le_meme_appel():
    repository = FakeStopTimeRepository(departures_by_stop=DEPARTS)
    loader = build_departures_loader(repository)

    await loader.load_many([
        DeparturesKey("N1:1", after_seconds=0, limit=10),
        DeparturesKey("N1:2", after_seconds=0, limit=10),
    ])

    assert sorted(repository.departure_calls[0]["stop_ids"]) == ["N1:1", "N1:2"]


async def test_des_criteres_differents_donnent_des_requetes_distinctes():
    repository = FakeStopTimeRepository(departures_by_stop=DEPARTS)
    loader = build_departures_loader(repository)

    await loader.load_many([
        DeparturesKey("N1:1", after_seconds=0, limit=10),
        DeparturesKey("N1:1", after_seconds=0, limit=3),
    ])

    assert len(repository.departure_calls) == 2


async def test_un_arret_sans_aucun_depart_donne_une_liste_vide_a_sa_place():
    repository = FakeStopTimeRepository(departures_by_stop=DEPARTS)
    loader = build_departures_loader(repository)

    resultats = await loader.load_many([
        DeparturesKey("N1:1", after_seconds=0, limit=10),
        DeparturesKey("N1:desert", after_seconds=0, limit=10),
    ])

    assert resultats[1] == []


async def test_les_departs_reviennent_en_face_du_bon_arret():
    repository = FakeStopTimeRepository(departures_by_stop=DEPARTS)
    loader = build_departures_loader(repository)

    resultats = await loader.load_many([
        DeparturesKey("N1:2", after_seconds=0, limit=10),
        DeparturesKey("N1:1", after_seconds=0, limit=10),
    ])

    assert [depart[0]["trip_id"] for depart in resultats] == ["N1:T2", "N1:T1"]

COMPTES = {"N1:T-court": 5, "N1:T-long": 8, "N1:T-retour": 3}

DESSERTES = {
    "N1:T-court": ["N1:1", "N1:2"],
    "N1:T-long": ["N1:1", "N1:2", "N1:3"],
    "N1:T-retour": ["N1:3", "N1:1"],
}

TRACES = {
    "N1:SH-long": [[2.25, 48.5], [5.125, 46.0]],
    "N1:SH-retour": [[5.125, 46.0], [2.25, 48.5]],
}


def _trajet(trip_id, direction_id=0, shape_id=None, headsign="Centre"):
    trajet = {"trip_id": trip_id, "route_id": "N1:R1", "headsign": headsign}
    if direction_id is not None:
        trajet["direction_id"] = direction_id
    if shape_id is not None:
        trajet["shape_id"] = shape_id
    return trajet


def _loader(trips_by_route, comptes=None, dessertes=None, traces=None):
    return build_route_directions_loader(
        FakeTripRepository(trips_by_route=trips_by_route),
        FakeStopTimeRepository(
            counts_by_trip=comptes if comptes is not None else COMPTES,
            stops_by_trip=dessertes if dessertes is not None else DESSERTES,
        ),
        FakeShapeRepository(points_by_shape=traces if traces is not None else TRACES),
    )


LIGNE_COMPLETE = {
    "N1:R1": [
        _trajet("N1:T-court", direction_id=0, shape_id="N1:SH-court"),
        _trajet("N1:T-long", direction_id=0, shape_id="N1:SH-long"),
        _trajet("N1:T-retour", direction_id=1, shape_id="N1:SH-retour", headsign="Gare"),
    ]
}


async def test_le_trajet_desservant_le_plus_d_arrets_represente_sa_direction():
    loader = _loader(LIGNE_COMPLETE)

    directions = await loader.load("N1:R1")

    aller = next(d for d in directions if d["direction_id"] == 0)
    assert aller["trip_id"] == "N1:T-long"


async def test_l_election_du_representant_ne_depend_pas_de_l_ordre_de_lecture():
    inverse = {"N1:R1": list(reversed(LIGNE_COMPLETE["N1:R1"]))}
    loader = _loader(inverse)

    directions = await loader.load("N1:R1")

    aller = next(d for d in directions if d["direction_id"] == 0)
    assert aller["trip_id"] == "N1:T-long"


async def test_chaque_direction_n_apparait_qu_une_fois_dans_le_resultat():
    loader = _loader(LIGNE_COMPLETE)

    directions = await loader.load("N1:R1")

    assert [d["direction_id"] for d in directions] == [0, 1]


async def test_les_directions_sont_triees_par_identifiant_croissant():
    desordre = {
        "N1:R1": [
            _trajet("N1:T-retour", direction_id=1, headsign="Gare"),
            _trajet("N1:T-long", direction_id=0),
        ]
    }
    loader = _loader(desordre)

    directions = await loader.load("N1:R1")

    assert [d["direction_id"] for d in directions] == [0, 1]


async def test_un_trajet_sans_direction_est_confondu_avec_la_direction_zero():
    melange = {
        "N1:R1": [
            _trajet("N1:T-court", direction_id=0),
            _trajet("N1:T-long", direction_id=None),
        ]
    }
    loader = _loader(melange)

    directions = await loader.load("N1:R1")

    assert len(directions) == 1


async def test_le_trajet_sans_direction_concourt_pour_la_direction_zero():
    melange = {
        "N1:R1": [
            _trajet("N1:T-court", direction_id=0),
            _trajet("N1:T-long", direction_id=None),
        ]
    }
    loader = _loader(melange)

    directions = await loader.load("N1:R1")

    assert directions[0]["trip_id"] == "N1:T-long"

async def test_les_arrets_desservis_par_le_trajet_retenu_sont_rendus_dans_l_ordre():
    loader = _loader(LIGNE_COMPLETE)

    directions = await loader.load("N1:R1")

    assert directions[0]["stop_ids"] == ["N1:1", "N1:2", "N1:3"]


async def test_la_destination_du_trajet_retenu_est_reprise_par_la_direction():
    loader = _loader(LIGNE_COMPLETE)

    directions = await loader.load("N1:R1")

    assert directions[1]["headsign"] == "Gare"


async def test_le_trace_du_trajet_retenu_est_rendu_avec_la_direction():
    loader = _loader(LIGNE_COMPLETE)

    directions = await loader.load("N1:R1")

    assert directions[0]["coordinates"] == TRACES["N1:SH-long"]


async def test_un_trajet_sans_trace_donne_une_direction_sans_coordonnees():
    sans_trace = {"N1:R1": [_trajet("N1:T-long", direction_id=0)]}
    loader = _loader(sans_trace)

    directions = await loader.load("N1:R1")

    assert directions[0]["coordinates"] == []


async def test_un_trace_inconnu_du_repository_donne_une_direction_sans_coordonnees():
    trace_fantome = {"N1:R1": [_trajet("N1:T-long", direction_id=0, shape_id="N1:SH-fantome")]}
    loader = _loader(trace_fantome)

    directions = await loader.load("N1:R1")

    assert directions[0]["coordinates"] == []


async def test_une_ligne_dont_aucun_trajet_n_est_connu_donne_une_liste_vide():
    loader = _loader({})

    assert await loader.load("N1:R1") == []


async def test_une_ligne_sans_trajet_donne_une_liste_vide_meme_si_une_autre_en_a():
    loader = _loader(LIGNE_COMPLETE)

    resultats = await loader.load_many(["N1:R1", "N1:R-vide"])

    assert resultats[1] == []


async def test_le_trace_n_est_pas_demande_quand_aucun_trajet_retenu_n_en_a():
    sans_trace = {"N1:R1": [_trajet("N1:T-long", direction_id=0)]}
    repository = FakeShapeRepository(points_by_shape=TRACES)
    loader = build_route_directions_loader(
        FakeTripRepository(trips_by_route=sans_trace),
        FakeStopTimeRepository(counts_by_trip=COMPTES, stops_by_trip=DESSERTES),
        repository,
    )

    await loader.load("N1:R1")

    assert repository.calls == []


DEUX_LIGNES = {
    "N1:R1": [_trajet("N1:T-long", direction_id=0, shape_id="N1:SH-long")],
    "N1:R2": [{"trip_id": "N1:T-retour", "route_id": "N1:R2", "direction_id": 0,
               "headsign": "Gare", "shape_id": "N1:SH-retour"}],
}


async def test_deux_lignes_ne_declenchent_qu_une_seule_requete_de_trajets():
    trip_repository = FakeTripRepository(trips_by_route=DEUX_LIGNES)
    loader = build_route_directions_loader(
        trip_repository,
        FakeStopTimeRepository(counts_by_trip=COMPTES, stops_by_trip=DESSERTES),
        FakeShapeRepository(points_by_shape=TRACES),
    )

    await asyncio.gather(loader.load("N1:R1"), loader.load("N1:R2"))

    assert trip_repository.calls == [["N1:R1", "N1:R2"]]


async def test_deux_lignes_ne_declenchent_qu_un_seul_comptage_d_arrets():
    stop_time_repository = FakeStopTimeRepository(
        counts_by_trip=COMPTES, stops_by_trip=DESSERTES
    )
    loader = build_route_directions_loader(
        FakeTripRepository(trips_by_route=DEUX_LIGNES),
        stop_time_repository,
        FakeShapeRepository(points_by_shape=TRACES),
    )

    await asyncio.gather(loader.load("N1:R1"), loader.load("N1:R2"))

    assert len(stop_time_repository.count_calls) == 1


async def test_deux_lignes_ne_declenchent_qu_une_seule_requete_de_traces():
    shape_repository = FakeShapeRepository(points_by_shape=TRACES)
    loader = build_route_directions_loader(
        FakeTripRepository(trips_by_route=DEUX_LIGNES),
        FakeStopTimeRepository(counts_by_trip=COMPTES, stops_by_trip=DESSERTES),
        shape_repository,
    )

    await asyncio.gather(loader.load("N1:R1"), loader.load("N1:R2"))

    assert shape_repository.calls == [["N1:SH-long", "N1:SH-retour"]]


async def test_les_directions_reviennent_en_face_de_la_bonne_ligne():
    loader = build_route_directions_loader(
        FakeTripRepository(trips_by_route=DEUX_LIGNES),
        FakeStopTimeRepository(counts_by_trip=COMPTES, stops_by_trip=DESSERTES),
        FakeShapeRepository(points_by_shape=TRACES),
    )

    resultats = await loader.load_many(["N1:R2", "N1:R1"])

    assert [directions[0]["trip_id"] for directions in resultats] == [
        "N1:T-retour", "N1:T-long",
    ]
