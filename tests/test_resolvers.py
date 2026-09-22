import pytest

from tests.conftest import FakeRouteRepository, FakeStopRepository, FakeLoader, fake_info

from app.graphql.resolvers.routes import resolve_route, resolve_routes
from app.graphql.resolvers.stops import resolve_search_stops, resolve_stop, resolve_stops_nearby
from app.graphql.types.gtfs import MAX_FIRST, MAX_PAGE_SIZE, MAX_RADIUS_METERS

ARRET = {"stop_id": "N1:1", "name": "Gare Centrale", "network_id": "N1"}
LIGNE = {"route_id": "N1:R1", "short_name": "1", "network_id": "N1"}

ARRETS_PROCHES = [
    {**ARRET, "distance_meters": 42.0},
    {"stop_id": "N1:2", "name": "Place du Marché", "network_id": "N1", "distance_meters": 120.0},
]


def _contexte_arrets_proches():
    return fake_info(stop_repository=FakeStopRepository(nearby=ARRETS_PROCHES))


async def test_un_arret_existant_est_renvoye_par_son_identifiant():
    info = fake_info(stop_loader=FakeLoader(results={"N1:1": ARRET}))

    arret = await resolve_stop(info, "N1:1")

    assert arret.name == "Gare Centrale"


async def test_un_identifiant_d_arret_inconnu_renvoie_none_sans_lever():
    assert await resolve_stop(fake_info(), "N1:inconnu") is None


async def test_la_recherche_de_proximite_accepte_un_seul_arret_demande():
    arrets = await resolve_stops_nearby(_contexte_arrets_proches(), lat=48.5, lon=2.25, first=1)

    assert len(arrets) == len(ARRETS_PROCHES)


async def test_la_recherche_de_proximite_accepte_exactement_la_limite_d_arrets():
    arrets = await resolve_stops_nearby(
        _contexte_arrets_proches(), lat=48.5, lon=2.25, first=MAX_FIRST
    )

    assert len(arrets) == len(ARRETS_PROCHES)


async def test_la_recherche_de_proximite_refuse_de_ne_demander_aucun_arret():
    with pytest.raises(ValueError, match="first"):
        await resolve_stops_nearby(fake_info(), lat=48.5, lon=2.25, first=0)


async def test_la_recherche_de_proximite_refuse_de_depasser_la_limite_d_arrets():
    with pytest.raises(ValueError, match="first"):
        await resolve_stops_nearby(fake_info(), lat=48.5, lon=2.25, first=MAX_FIRST + 1)

async def test_la_recherche_de_proximite_accepte_un_rayon_d_un_metre():
    arrets = await resolve_stops_nearby(
        _contexte_arrets_proches(), lat=48.5, lon=2.25, radius_meters=1
    )

    assert len(arrets) == len(ARRETS_PROCHES)


async def test_la_recherche_de_proximite_accepte_exactement_le_rayon_maximal():
    arrets = await resolve_stops_nearby(
        _contexte_arrets_proches(), lat=48.5, lon=2.25, radius_meters=MAX_RADIUS_METERS
    )

    assert len(arrets) == len(ARRETS_PROCHES)


async def test_la_recherche_de_proximite_refuse_un_rayon_nul():
    with pytest.raises(ValueError, match="radiusMeters"):
        await resolve_stops_nearby(fake_info(), lat=48.5, lon=2.25, radius_meters=0)


async def test_la_recherche_de_proximite_refuse_un_rayon_au_dela_du_maximum():
    with pytest.raises(ValueError, match="radiusMeters"):
        await resolve_stops_nearby(
            fake_info(), lat=48.5, lon=2.25, radius_meters=MAX_RADIUS_METERS + 1
        )

@pytest.mark.parametrize("lat", [-90, 90])
async def test_la_recherche_de_proximite_accepte_les_poles(lat):
    arrets = await resolve_stops_nearby(_contexte_arrets_proches(), lat=lat, lon=2.25)

    assert len(arrets) == len(ARRETS_PROCHES)


@pytest.mark.parametrize("lon", [-180, 180])
async def test_la_recherche_de_proximite_accepte_l_antimeridien(lon):
    arrets = await resolve_stops_nearby(_contexte_arrets_proches(), lat=48.5, lon=lon)

    assert len(arrets) == len(ARRETS_PROCHES)


@pytest.mark.parametrize("lat", [-90.1, 90.1])
async def test_la_recherche_de_proximite_refuse_une_latitude_hors_plage(lat):
    with pytest.raises(ValueError, match="latitude"):
        await resolve_stops_nearby(fake_info(), lat=lat, lon=2.25)


@pytest.mark.parametrize("lon", [-180.1, 180.1])
async def test_la_recherche_de_proximite_refuse_une_longitude_hors_plage(lon):
    with pytest.raises(ValueError, match="longitude"):
        await resolve_stops_nearby(fake_info(), lat=48.5, lon=lon)

async def test_la_recherche_de_proximite_transmet_le_rayon_et_la_limite_au_repository():
    repository = FakeStopRepository(nearby=ARRETS_PROCHES)
    info = fake_info(stop_repository=repository)

    await resolve_stops_nearby(info, lat=48.5, lon=2.25, radius_meters=300, first=5)

    assert repository.calls[0] == {
        "latitude": 48.5, "longitude": 2.25,
        "radius_meters": 300, "limit": 5, "network_id": None,
    }


async def test_la_recherche_de_proximite_restreint_au_reseau_demande():
    repository = FakeStopRepository(nearby=ARRETS_PROCHES)
    info = fake_info(stop_repository=repository)

    await resolve_stops_nearby(info, lat=48.5, lon=2.25, network_id="N1")

    assert repository.calls[0]["network_id"] == "N1"


async def test_la_recherche_de_proximite_conserve_la_distance_calculee_par_mongo():
    arrets = await resolve_stops_nearby(_contexte_arrets_proches(), lat=48.5, lon=2.25)

    assert [arret.distance_meters for arret in arrets] == [42.0, 120.0]

async def test_une_ligne_existante_est_renvoyee_par_son_identifiant():
    info = fake_info(route_loader=FakeLoader(results={"N1:R1": LIGNE}))

    ligne = await resolve_route(info, "N1:R1")

    assert ligne.short_name == "1"


async def test_un_identifiant_de_ligne_inconnu_renvoie_none_sans_lever():
    assert await resolve_route(fake_info(), "N1:inconnue") is None

def _contexte_lignes():
    return fake_info(route_repository=FakeRouteRepository(paginated=[LIGNE], total_count=7))


async def test_le_catalogue_de_lignes_refuse_une_page_inferieure_a_un():
    with pytest.raises(ValueError, match="page"):
        await resolve_routes(fake_info(), page=0)


async def test_le_catalogue_de_lignes_refuse_une_taille_de_page_nulle():
    with pytest.raises(ValueError, match="pageSize"):
        await resolve_routes(fake_info(), page_size=0)


async def test_le_catalogue_de_lignes_refuse_une_taille_de_page_au_dela_du_maximum():
    with pytest.raises(ValueError, match="pageSize"):
        await resolve_routes(fake_info(), page_size=MAX_PAGE_SIZE + 1)


async def test_le_catalogue_de_lignes_accepte_exactement_la_taille_de_page_maximale():
    catalogue = await resolve_routes(_contexte_lignes(), page_size=MAX_PAGE_SIZE)

    assert catalogue.page_size == MAX_PAGE_SIZE


async def test_le_catalogue_de_lignes_transmet_la_pagination_au_repository():
    info = _contexte_lignes()

    await resolve_routes(info, page=3, page_size=10)

    assert info.context["route_repository"].calls[0] == {
        "page": 3, "page_size": 10, "network_id": None,
    }


async def test_le_catalogue_de_lignes_transmet_le_reseau_en_texte_au_repository():
    info = _contexte_lignes()

    await resolve_routes(info, network_id="N1")

    assert info.context["route_repository"].calls[0]["network_id"] == "N1"


async def test_le_catalogue_de_lignes_reporte_le_total_renvoye_par_le_repository():
    catalogue = await resolve_routes(_contexte_lignes())

    assert catalogue.total_count == 7


async def test_le_catalogue_de_lignes_convertit_les_documents_en_objets_ligne():
    catalogue = await resolve_routes(_contexte_lignes())

    assert [ligne.id for ligne in catalogue.items] == ["N1:R1"]


ARRETS_TROUVES = [
    {"stop_id": "N1:1", "name": "Gare Centrale", "network_id": "N1"},
    {"stop_id": "N2:2", "name": "Gare du Nord", "network_id": "N2"},
]


def _contexte_recherche():
    return fake_info(stop_repository=FakeStopRepository(matching=ARRETS_TROUVES))


async def test_la_recherche_par_nom_retourne_les_arrets_correspondants():
    arrets = await resolve_search_stops(_contexte_recherche(), query="gare")

    assert [arret.name for arret in arrets] == ["Gare Centrale", "Gare du Nord"]


async def test_la_recherche_par_nom_transmet_la_saisie_et_la_limite_au_repository():
    info = _contexte_recherche()

    await resolve_search_stops(info, query="gare", first=5, network_id="N1")

    assert info.context["stop_repository"].search_calls == [
        {"query": "gare", "limit": 5, "network_id": "N1"}
    ]


async def test_la_recherche_par_nom_sans_reseau_n_applique_aucun_filtre():
    info = _contexte_recherche()

    await resolve_search_stops(info, query="gare")

    assert info.context["stop_repository"].search_calls[0]["network_id"] is None


async def test_la_recherche_par_nom_refuse_de_ne_demander_aucun_arret():
    with pytest.raises(ValueError, match="first"):
        await resolve_search_stops(fake_info(), query="gare", first=0)


async def test_la_recherche_par_nom_refuse_de_depasser_la_limite_d_arrets():
    with pytest.raises(ValueError, match="first"):
        await resolve_search_stops(fake_info(), query="gare", first=MAX_FIRST + 1)


async def test_la_recherche_par_nom_refuse_une_saisie_trop_courte():
    with pytest.raises(ValueError, match="query"):
        await resolve_search_stops(fake_info(), query="g")


async def test_la_recherche_par_nom_refuse_une_saisie_reduite_a_de_la_ponctuation():
    # « -- » ne laisse aucun caractère après normalisation : la refuser évite
    # de faire balayer toute la collection à MongoDB.
    with pytest.raises(ValueError, match="query"):
        await resolve_search_stops(fake_info(), query="--")
