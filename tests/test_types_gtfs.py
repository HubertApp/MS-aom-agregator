import pytest
import strawberry

from tests.conftest import FakeLoader, fake_info

from app.graphql.loaders.departures_loader import DeparturesKey
from app.graphql.types.gtfs import (
    MAX_FIRST,
    Departure,
    GeoJSONPoint,
    PaginatedRoutes,
    Route,
    Stop,
)

ARRET = {
    "stop_id": "N1:1",
    "name": "Gare Centrale",
    "network_id": "N1",
    "location": {"type": "Point", "coordinates": [2.25, 48.5]},
}

LIGNE = {
    "route_id": "N1:R1",
    "short_name": "1",
    "long_name": "Ligne 1 - Centre",
    "type": 0,
    "color": "FF0000",
    "text_color": "FFFFFF",
    "network_id": "N1",
}

PASSAGE = {
    "trip_id": "N1:T1",
    "stop_sequence": 2,
    "arrival_time": "25:30:00",
    "departure_time": "25:31:00",
    "headsign": "Centre-ville",
    "route_id": "N1:R1",
    "route_short_name": "1",
    "route_long_name": "Ligne 1 - Centre",
    "route_type": 0,
    "route_color": "FF0000",
    "route_text_color": "FFFFFF",
    "network_id": "N1",
}


def _arret(**surcharges):
    return Stop.from_document({**ARRET, **surcharges})


def test_la_latitude_est_lue_en_seconde_position_du_point():
    assert GeoJSONPoint(coordinates=[2.25, 48.5]).latitude() == 48.5


def test_la_longitude_est_lue_en_premiere_position_du_point():
    assert GeoJSONPoint(coordinates=[2.25, 48.5]).longitude() == 2.25


def test_un_point_sans_coordonnees_n_a_pas_de_latitude():
    assert GeoJSONPoint(coordinates=[]).latitude() is None


def test_un_point_sans_coordonnees_n_a_pas_de_longitude():
    assert GeoJSONPoint(coordinates=[]).longitude() is None


def test_un_arret_expose_la_position_du_document():
    assert _arret().location.coordinates == [2.25, 48.5]


def test_un_arret_sans_position_dans_le_document_n_a_pas_de_position():
    assert Stop.from_document({"stop_id": "N1:1"}).location is None


def test_un_arret_dont_la_position_est_vide_n_a_pas_de_position():
    assert _arret(location={"type": "Point", "coordinates": []}).location is None


def test_un_arret_reprend_le_reseau_du_document():
    assert _arret().network().id == "N1"


def test_un_arret_sans_reseau_dans_le_document_a_un_reseau_vide():
    assert Stop.from_document({"stop_id": "N1:1"}).network_id == ""


def test_la_distance_passee_en_parametre_prime_sur_celle_du_document():
    arret = Stop.from_document({**ARRET, "distance_meters": 900.0}, distance_meters=12.5)

    assert arret.distance_meters == 12.5


def test_la_distance_du_document_sert_quand_aucune_n_est_passee():
    arret = Stop.from_document({**ARRET, "distance_meters": 900.0})

    assert arret.distance_meters == 900.0

def test_une_ligne_reprend_son_nom_court_du_document():
    assert Route.from_document(LIGNE).short_name == "1"


def test_une_ligne_reprend_ses_couleurs_du_document():
    ligne = Route.from_document(LIGNE)

    assert (ligne.color, ligne.text_color) == ("FF0000", "FFFFFF")


def test_une_ligne_reduite_a_son_identifiant_ne_leve_pas():
    ligne = Route.from_document({"route_id": "N1:R1"})

    assert (ligne.id, ligne.short_name, ligne.long_name) == ("N1:R1", None, None)


def test_une_ligne_expose_le_reseau_federe_correspondant():
    assert Route.from_document(LIGNE).network().id == "N1"

def test_un_passage_reprend_ses_horaires_du_document():
    passage = Departure.from_document(PASSAGE)

    assert (passage.arrival_time, passage.departure_time) == ("25:30:00", "25:31:00")


def test_un_passage_conserve_les_horaires_au_dela_de_minuit_tels_quels():
    assert Departure.from_document(PASSAGE).departure_time == "25:31:00"


def test_un_passage_reconstitue_sa_ligne_depuis_les_champs_denormalises():
    ligne = Departure.from_document(PASSAGE).route

    assert (ligne.id, ligne.short_name, ligne.color) == ("N1:R1", "1", "FF0000")


def test_un_passage_sans_ligne_dans_le_document_n_a_pas_de_ligne():
    document = {champ: valeur for champ, valeur in PASSAGE.items() if champ != "route_id"}

    assert Departure.from_document(document).route is None



def _pagination(total_count, page_size):
    return PaginatedRoutes(items=[], total_count=total_count, page=1, page_size=page_size)


def test_le_nombre_de_pages_arrondit_la_derniere_page_incomplete_au_dessus():
    assert _pagination(total_count=7, page_size=2).total_pages() == 4


def test_le_nombre_de_pages_est_exact_quand_le_total_tombe_juste():
    assert _pagination(total_count=8, page_size=2).total_pages() == 4


def test_un_catalogue_vide_ne_compte_aucune_page():
    assert _pagination(total_count=0, page_size=25).total_pages() == 0


def test_une_taille_de_page_nulle_ne_provoque_pas_de_division_par_zero():
    assert _pagination(total_count=7, page_size=0).total_pages() == 0


async def test_l_heure_de_depart_demandee_est_convertie_en_secondes():
    loader = FakeLoader(default=[])
    info = fake_info(departures_loader=loader)

    await _arret().departures(info, after="25:30:00")

    assert loader.calls == [DeparturesKey(stop_id="N1:1", after_seconds=91800, limit=10)]


async def test_l_absence_d_heure_de_depart_demande_les_passages_depuis_minuit():
    loader = FakeLoader(default=[])
    info = fake_info(departures_loader=loader)

    await _arret().departures(info)

    assert loader.calls[0].after_seconds == 0


async def test_le_nombre_de_passages_demande_est_repercute_dans_la_cle():
    loader = FakeLoader(default=[])
    info = fake_info(departures_loader=loader)

    await _arret().departures(info, first=25)

    assert loader.calls[0].limit == 25


async def test_les_documents_de_passage_sont_convertis_en_objets_departure():
    loader = FakeLoader(default=[PASSAGE])
    info = fake_info(departures_loader=loader)

    passages = await _arret().departures(info)

    assert [passage.trip_id for passage in passages] == ["N1:T1"]


async def test_demander_zero_passage_est_refuse():
    with pytest.raises(ValueError, match="first"):
        await _arret().departures(fake_info(), first=0)


async def test_demander_plus_de_passages_que_la_limite_est_refuse():
    with pytest.raises(ValueError, match="first"):
        await _arret().departures(fake_info(), first=MAX_FIRST + 1)


async def test_demander_un_seul_passage_est_accepte():
    assert await _arret().departures(fake_info(), first=1) == []


async def test_demander_exactement_la_limite_de_passages_est_accepte():
    assert await _arret().departures(fake_info(), first=MAX_FIRST) == []


LIGNES_DE_L_ARRET = [
    {
        "route_id": "N1:R1",
        "route_short_name": "1",
        "route_long_name": "Ligne 1 - Centre",
        "route_type": 0,
        "route_color": "FF0000",
        "route_text_color": "FFFFFF",
        "network_id": "N1",
    },
    {
        "route_id": "N1:R2",
        "route_short_name": "2",
        "route_long_name": "Ligne 2 - Nord",
        "route_type": 3,
        "route_color": "0000FF",
        "route_text_color": "FFFFFF",
        "network_id": "N1",
    },
]


async def test_les_lignes_desservant_un_arret_viennent_du_loader_dedie():
    departures = FakeLoader(default=[])
    info = fake_info(
        departures_loader=departures,
        stop_routes_loader=FakeLoader(default=LIGNES_DE_L_ARRET),
    )

    lignes = await _arret().routes(info)

    assert len(lignes) == 2
    assert departures.calls == []


async def test_les_lignes_desservant_un_arret_sont_converties_avec_leurs_champs():
    info = fake_info(stop_routes_loader=FakeLoader(default=LIGNES_DE_L_ARRET))

    lignes = await _arret().routes(info)

    premiere = next(ligne for ligne in lignes if ligne.id == "N1:R1")
    assert premiere.short_name == "1"
    assert premiere.long_name == "Ligne 1 - Centre"
    assert premiere.type == 0
    assert premiere.color == "FF0000"
    assert premiere.text_color == "FFFFFF"


async def test_un_arret_sans_aucune_ligne_associee_ne_dessert_rien():
    assert await _arret().routes(fake_info()) == []


async def test_la_cle_transmise_au_loader_est_l_identifiant_de_l_arret_seul():
    loader = FakeLoader(default=[])
    info = fake_info(stop_routes_loader=loader)

    await _arret().routes(info)

    assert loader.calls == ["N1:1"]
