from app.repositories.route_repository import RouteRepository

LIGNES = [
    {"route_id": "N1:C", "short_name": "2", "long_name": "Ligne 2", "network_id": "N1"},
    {"route_id": "N1:B", "short_name": "1", "long_name": "Ligne 1 bis", "network_id": "N1"},
    {"route_id": "N1:A", "short_name": "1", "long_name": "Ligne 1", "network_id": "N1"},
    {"route_id": "N1:D", "short_name": "3", "long_name": "Ligne 3", "network_id": "N1"},
    {"route_id": "N2:A", "short_name": "1", "long_name": "Ligne 1 de Metz", "network_id": "N2"},
]

ORDRE_ATTENDU = ["N1:A", "N1:B", "N2:A", "N1:C", "N1:D"]


async def _repository(graphql_db):
    await graphql_db["routes"].insert_many([dict(ligne) for ligne in LIGNES])
    return RouteRepository(graphql_db)


def _identifiants(documents):
    return [document["route_id"] for document in documents]


async def test_les_lignes_de_meme_nom_court_sont_departagees_par_leur_identifiant(graphql_db):
    repository = await _repository(graphql_db)

    documents, _ = await repository.list_paginated(page=1, page_size=100)

    assert _identifiants(documents) == ORDRE_ATTENDU


async def test_l_ordre_de_pagination_est_reproductible_d_une_execution_a_l_autre(graphql_db):
    repository = await _repository(graphql_db)

    executions = [_identifiants((await repository.list_paginated(page=1, page_size=100))[0])
                  for _ in range(3)]

    assert executions == [ORDRE_ATTENDU] * 3

async def test_la_deuxieme_page_reprend_la_ou_la_premiere_s_arrete(graphql_db):
    repository = await _repository(graphql_db)

    documents, _ = await repository.list_paginated(page=2, page_size=2)

    assert _identifiants(documents) == ORDRE_ATTENDU[2:4]


async def test_la_derniere_page_incomplete_ne_renvoie_que_ce_qui_reste(graphql_db):
    repository = await _repository(graphql_db)

    documents, _ = await repository.list_paginated(page=3, page_size=2)

    assert _identifiants(documents) == ORDRE_ATTENDU[4:]


async def test_une_page_au_dela_du_dernier_document_est_vide_sans_lever(graphql_db):
    repository = await _repository(graphql_db)

    documents, _ = await repository.list_paginated(page=99, page_size=2)

    assert documents == []


async def test_le_total_compte_toutes_les_lignes_et_pas_seulement_la_page(graphql_db):
    repository = await _repository(graphql_db)

    _, total_count = await repository.list_paginated(page=1, page_size=2)

    assert total_count == len(LIGNES)

async def test_le_filtre_par_reseau_ne_renvoie_que_les_lignes_du_reseau_demande(graphql_db):
    repository = await _repository(graphql_db)

    documents, _ = await repository.list_paginated(page=1, page_size=100, network_id="N2")

    assert _identifiants(documents) == ["N2:A"]


async def test_le_total_est_lui_aussi_filtre_par_reseau(graphql_db):

    repository = await _repository(graphql_db)

    _, total_count = await repository.list_paginated(page=1, page_size=100, network_id="N2")

    assert total_count == 1


async def test_plusieurs_lignes_sont_recuperees_en_une_seule_requete(graphql_db):
    repository = await _repository(graphql_db)

    lignes = await repository.get_many_by_ids(["N1:A", "N1:D"])

    assert set(lignes) == {"N1:A", "N1:D"}


async def test_une_ligne_absente_du_lot_est_simplement_omise_du_resultat(graphql_db):
    repository = await _repository(graphql_db)

    lignes = await repository.get_many_by_ids(["N1:A", "N1:jamais-ingeree"])

    assert set(lignes) == {"N1:A"}
