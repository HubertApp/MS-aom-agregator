from app.repositories.stop_repository import StopRepository

ARRETS = [
    {"stop_id": "N1:1", "name": "Gare Centrale", "network_id": "N1",
     "location": {"type": "Point", "coordinates": [2.25, 48.5]}},
    {"stop_id": "N1:2", "name": "Place du Marché", "network_id": "N1",
     "location": {"type": "Point", "coordinates": [3.5, 49.75]}},
    {"stop_id": "N2:1", "name": "Hôtel de Ville", "network_id": "N2",
     "location": {"type": "Point", "coordinates": [6.2, 49.1]}},
]


async def _repository(graphql_db):
    await graphql_db["stops"].insert_many([dict(arret) for arret in ARRETS])
    return StopRepository(graphql_db)


async def test_un_arret_existant_est_retrouve_par_son_identifiant(graphql_db):
    repository = await _repository(graphql_db)

    arret = await repository.get_by_id("N1:1")

    assert arret["name"] == "Gare Centrale"


async def test_un_identifiant_d_arret_inconnu_renvoie_none_sans_lever(graphql_db):
    repository = await _repository(graphql_db)

    assert await repository.get_by_id("N1:inconnu") is None


async def test_plusieurs_arrets_sont_recuperes_en_une_seule_requete(graphql_db):
    repository = await _repository(graphql_db)

    arrets = await repository.get_many_by_ids(["N1:1", "N2:1"])

    assert set(arrets) == {"N1:1", "N2:1"}


async def test_les_arrets_sont_indexes_par_identifiant_dans_le_resultat(graphql_db):
    repository = await _repository(graphql_db)

    arrets = await repository.get_many_by_ids(["N1:2"])

    assert arrets["N1:2"]["name"] == "Place du Marché"


async def test_un_arret_absent_du_lot_est_simplement_omis_du_resultat(graphql_db):
    repository = await _repository(graphql_db)

    arrets = await repository.get_many_by_ids(["N1:1", "N1:jamais-ingere"])

    assert set(arrets) == {"N1:1"}
