
from tests.conftest import FakeLoader, FakeStopRepository, build_fake_context

from app.graphql import context as context_module
from app.graphql.schema import schema

ARRET = {"stop_id": "N1:1", "name": "Gare Centrale", "network_id": "N1"}

PASSAGE = {
    "trip_id": "N1:T1",
    "stop_sequence": 1,
    "arrival_time": "25:30:00",
    "departure_time": "25:31:00",
    "route_id": "N1:R1",
    "route_short_name": "1",
    "network_id": "N1",
}

LIGNES = [
    {"route_id": f"N1:R{numero}", "short_name": str(numero), "network_id": "N1"}
    for numero in range(1, 6)
]


async def test_le_service_se_declare_en_ligne():
    resultat = await schema.execute("query { status }", context_value={})

    assert resultat.data == {"status": "Online"}


async def test_un_arret_inconnu_renvoie_null_sans_erreur_graphql():
    resultat = await schema.execute(
        'query { stop(id: "N1:inconnu") { name } }',
        context_value=build_fake_context(),
    )

    assert resultat.errors is None and resultat.data == {"stop": None}


async def test_les_champs_arrivent_au_front_en_camel_case():
    contexte = build_fake_context(
        stop_loader=FakeLoader(results={"N1:1": ARRET}),
        departures_loader=FakeLoader(default=[PASSAGE]),
    )

    resultat = await schema.execute(
        'query { stop(id: "N1:1") { id departures { departureTime route { shortName } } } }',
        context_value=contexte,
    )

    assert resultat.data["stop"]["departures"] == [
        {"departureTime": "25:31:00", "route": {"shortName": "1"}}
    ]


async def test_une_borne_de_validation_violee_remonte_dans_les_erreurs_graphql():
    resultat = await schema.execute(
        "query { stopsNearby(lat: 48.5, lon: 2.25, radiusMeters: 50000) { id } }",
        context_value=build_fake_context(),
    )

    assert resultat.errors and "radiusMeters" in str(resultat.errors[0])


async def test_une_borne_violee_annule_les_donnees_du_champ_concerne():
    resultat = await schema.execute(
        "query { stopsNearby(lat: 48.5, lon: 2.25, radiusMeters: 50000) { id } }",
        context_value=build_fake_context(),
    )

    assert resultat.data is None


async def test_le_catalogue_de_lignes_fonctionne_avec_le_vrai_contexte(mock_graphql_db):
    await mock_graphql_db["routes"].insert_many([dict(ligne) for ligne in LIGNES])
    contexte = await context_module.get_context()

    resultat = await schema.execute(
        "query { routes(page: 1, pageSize: 2) { totalCount totalPages items { id } } }",
        context_value=contexte,
    )

    assert resultat.errors is None
    assert resultat.data["routes"] == {
        "totalCount": 5,
        "totalPages": 3,
        "items": [{"id": "N1:R1"}, {"id": "N1:R2"}],
    }


async def test_la_recherche_par_nom_est_exposee_au_front_en_camel_case():
    contexte = build_fake_context(
        stop_repository=FakeStopRepository(matching=[ARRET]),
    )

    resultat = await schema.execute(
        'query { searchStops(query: "gare", first: 5, networkId: "N1") { id name } }',
        context_value=contexte,
    )

    assert resultat.errors is None
    assert resultat.data == {"searchStops": [{"id": "N1:1", "name": "Gare Centrale"}]}


async def test_la_recherche_par_nom_se_contente_de_la_saisie():
    contexte = build_fake_context(stop_repository=FakeStopRepository(matching=[ARRET]))

    resultat = await schema.execute(
        'query { searchStops(query: "gare") { name } }',
        context_value=contexte,
    )

    assert resultat.errors is None
    assert contexte["stop_repository"].search_calls == [
        {"query": "gare", "limit": 20, "network_id": None}
    ]
