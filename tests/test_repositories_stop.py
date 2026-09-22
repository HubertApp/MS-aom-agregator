from app.repositories.stop_repository import StopRepository

# `name_normalized` est posé à l'ingestion : on le reproduit ici pour que le
# jeu de test reflète ce que contient réellement la collection.
ARRETS = [
    {"stop_id": "N1:1", "name": "Gare Centrale", "name_normalized": "garecentrale",
     "network_id": "N1", "location": {"type": "Point", "coordinates": [2.25, 48.5]}},
    {"stop_id": "N1:2", "name": "Place du Marché", "name_normalized": "placedumarche",
     "network_id": "N1", "location": {"type": "Point", "coordinates": [3.5, 49.75]}},
    {"stop_id": "N2:1", "name": "Hôtel de Ville", "name_normalized": "hoteldeville",
     "network_id": "N2", "location": {"type": "Point", "coordinates": [6.2, 49.1]}},
    {"stop_id": "N2:2", "name": "Gare du Nord", "name_normalized": "garedunord",
     "network_id": "N2", "location": {"type": "Point", "coordinates": [2.35, 48.88]}},
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


async def _noms_trouves(repository, query, **options):
    return [arret["name"] for arret in await repository.search_by_name(query, **options)]


async def test_la_recherche_ignore_les_accents_absents_de_la_saisie(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "marche", limit=10) == ["Place du Marché"]


async def test_la_recherche_ignore_la_casse_de_la_saisie(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "CENTRALE", limit=10) == ["Gare Centrale"]


async def test_la_recherche_ignore_les_espaces_de_la_saisie(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "hotel de ville", limit=10) == ["Hôtel de Ville"]


async def test_la_recherche_trouve_un_fragment_au_milieu_du_nom(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "du", limit=10) == ["Gare du Nord", "Place du Marché"]


async def test_les_resultats_sont_ordonnes_par_nom_normalise(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "gare", limit=10) == ["Gare Centrale", "Gare du Nord"]


async def test_la_recherche_peut_etre_restreinte_a_un_seul_reseau(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "gare", limit=10, network_id="N2") == ["Gare du Nord"]


async def test_la_recherche_ne_renvoie_pas_plus_d_arrets_que_la_limite(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "gare", limit=1) == ["Gare Centrale"]


async def test_une_saisie_sans_correspondance_renvoie_une_liste_vide(graphql_db):
    repository = await _repository(graphql_db)

    assert await _noms_trouves(repository, "aeroport", limit=10) == []


async def test_une_saisie_sans_aucun_caractere_utile_ne_renvoie_aucun_arret(graphql_db):
    repository = await _repository(graphql_db)

    # Sans ce garde-fou, la saisie « .* » deviendrait une regex vide qui
    # remonterait toute la collection.
    assert await _noms_trouves(repository, ".*", limit=10) == []
