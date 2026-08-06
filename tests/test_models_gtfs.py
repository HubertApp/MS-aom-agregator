
import pytest
from pydantic import ValidationError

from app.models.gtfs import (
    Agency,
    Calendar,
    CalendarDate,
    Route,
    Shape,
    Stop,
    StopTime,
    Transfer,
    Trip,
)

RESEAU = {"network_id": "N1"}


def test_l_identifiant_d_arret_est_prefixe_par_le_reseau():
    arret = Stop.model_validate({"stop_id": "1"}, context=RESEAU)

    assert arret.stop_id == "N1:1"


@pytest.mark.parametrize("contexte", [None, {}], ids=["contexte_absent", "contexte_vide"])
def test_sans_reseau_dans_le_contexte_l_identifiant_reste_brut(contexte):
    arret = Stop.model_validate({"stop_id": "1"}, context=contexte)

    assert arret.stop_id == "1"


def test_deux_reseaux_produisent_deux_identifiants_distincts():
    metz = Stop.model_validate({"stop_id": "1"}, context={"network_id": "metz"})
    nancy = Stop.model_validate({"stop_id": "1"}, context={"network_id": "nancy"})

    assert metz.stop_id != nancy.stop_id


def test_la_station_parente_d_un_arret_est_namespacee():
    arret = Stop.model_validate({"stop_id": "2", "parent_station": "1"}, context=RESEAU)

    assert arret.parent_station == "N1:1"


def test_le_trace_d_un_trajet_est_namespace():
    trajet = Trip.model_validate(
        {"trip_id": "T1", "route_id": "R1", "service_id": "S1", "shape_id": "SH1"},
        context=RESEAU,
    )

    assert trajet.shape_id == "N1:SH1"


@pytest.mark.parametrize(
    "colonnes",
    [{"shape_id": ""}, {}],
    ids=["colonne_vide", "colonne_absente"],
)
def test_un_trajet_sans_trace_a_un_shape_id_nul(colonnes):
    trajet = Trip.model_validate(
        {"trip_id": "T1", "route_id": "R1", "service_id": "S1", **colonnes},
        context=RESEAU,
    )

    assert trajet.shape_id is None


def test_les_deux_arrets_d_une_correspondance_sont_namespaces():
    correspondance = Transfer.model_validate(
        {"from_stop_id": "1", "to_stop_id": "2"}, context=RESEAU
    )

    assert (correspondance.from_stop_id, correspondance.to_stop_id) == ("N1:1", "N1:2")


def test_les_references_du_passage_a_l_arret_sont_namespacees():
    passage = StopTime.model_validate({"trip_id": "T1", "stop_id": "1"}, context=RESEAU)

    assert (passage.trip_id, passage.stop_id) == ("N1:T1", "N1:1")


def test_l_identifiant_de_trace_est_namespace_sur_le_point_de_trace():
    point = Shape.model_validate({"shape_id": "SH1"}, context=RESEAU)

    assert point.shape_id == "N1:SH1"

@pytest.mark.parametrize(
    "colonnes",
    [{}, {"agency_id": ""}],
    ids=["colonne_absente", "colonne_vide"],
)
def test_une_agence_sans_identifiant_retombe_sur_un_default_namespace(colonnes):
    agence = Agency.model_validate({"agency_name": "Réseau", **colonnes}, context=RESEAU)

    assert agence.agency_id == "N1:default"


def test_une_route_sans_agence_pointe_vers_l_agence_par_defaut_du_meme_reseau():
    agence = Agency.model_validate({"agency_name": "Réseau"}, context=RESEAU)
    route = Route.model_validate({"route_id": "R1"}, context=RESEAU)

    assert route.agency_id == agence.agency_id


def test_le_default_d_agence_differe_d_un_reseau_a_l_autre():
    metz = Agency.model_validate({}, context={"network_id": "metz"})
    nancy = Agency.model_validate({}, context={"network_id": "nancy"})

    assert metz.agency_id != nancy.agency_id

def test_une_chaine_vide_sur_un_entier_optionnel_devient_nulle():
    arret = Stop.model_validate({"stop_id": "1", "wheelchair_boarding": ""}, context=RESEAU)

    assert arret.wheelchair_boarding is None


def test_une_chaine_vide_sur_un_flottant_optionnel_devient_nulle():
    passage = StopTime.model_validate(
        {"trip_id": "T1", "stop_id": "1", "shape_dist_traveled": ""}, context=RESEAU
    )

    assert passage.shape_dist_traveled is None


def test_une_chaine_vide_sur_un_texte_optionnel_devient_nulle():
    arret = Stop.model_validate({"stop_id": "1", "stop_desc": ""}, context=RESEAU)

    assert arret.description is None


def test_des_coordonnees_vides_valent_zero():
    arret = Stop.model_validate(
        {"stop_id": "1", "stop_lat": "", "stop_lon": ""}, context=RESEAU
    )

    assert (arret.lat, arret.lon) == (0.0, 0.0)


def test_les_espaces_autour_des_valeurs_sont_supprimes():
    arret = Stop.model_validate({"stop_id": "1", "stop_name": "  Gare Centrale  "}, context=RESEAU)

    assert arret.name == "Gare Centrale"


def test_une_colonne_non_modelisee_est_ignoree_sans_erreur():
    arret = Stop.model_validate(
        {"stop_id": "1", "colonne_maison_du_producteur": "peu importe"}, context=RESEAU
    )

    assert arret.stop_id == "N1:1"

def test_un_horaire_apres_minuit_est_conserve_tel_quel():
    passage = StopTime.model_validate(
        {"trip_id": "T1", "stop_id": "1", "arrival_time": "25:30:00"}, context=RESEAU
    )

    assert passage.arrival_time == "25:30:00"


def test_les_dates_de_validite_restent_des_chaines():
    calendrier = Calendar.model_validate(
        {"service_id": "S1", "start_date": "20250101"}, context=RESEAU
    )

    assert calendrier.start_date == "20250101"


def test_la_date_d_exception_reste_une_chaine():
    exception = CalendarDate.model_validate(
        {"service_id": "S1", "date": "20250501", "exception_type": "2"}, context=RESEAU
    )

    assert (exception.date, exception.exception_type) == ("20250501", 2)


def test_un_block_id_textuel_est_accepte():
    trajet = Trip.model_validate(
        {"trip_id": "T1", "route_id": "R1", "service_id": "S1", "block_id": "BLK-01"},
        context=RESEAU,
    )

    assert trajet.block_id == "BLK-01"


def test_le_temps_minimal_de_correspondance_devient_un_entier_de_secondes():
    correspondance = Transfer.model_validate(
        {"from_stop_id": "1", "to_stop_id": "2", "min_transfer_time": "300"}, context=RESEAU
    )

    assert correspondance.min_transfer_time == 300


def test_l_accessibilite_en_fauteuil_reste_un_entier():
    trajet = Trip.model_validate(
        {"trip_id": "T1", "route_id": "R1", "service_id": "S1", "wheelchair_accessible": "2"},
        context=RESEAU,
    )

    assert trajet.wheelchair_accessible == 2


def test_le_type_de_route_devient_un_entier():
    route = Route.model_validate({"route_id": "R1", "route_type": "0"}, context=RESEAU)

    assert route.type == 0

@pytest.mark.parametrize(
    "ligne",
    [{}, {"stop_id": ""}, {"stop_id": "   "}],
    ids=["absent", "vide", "espaces"],
)
def test_un_arret_sans_identifiant_est_rejete(ligne):
    with pytest.raises(ValidationError):
        Stop.model_validate(ligne, context=RESEAU)


@pytest.mark.parametrize(
    "manquant",
    ["trip_id", "route_id", "service_id"],
)
def test_un_trajet_ampute_d_un_identifiant_obligatoire_est_rejete(manquant):
    ligne = {"trip_id": "T1", "route_id": "R1", "service_id": "S1"}
    ligne[manquant] = ""

    with pytest.raises(ValidationError):
        Trip.model_validate(ligne, context=RESEAU)


def test_une_route_sans_identifiant_est_rejetee():
    with pytest.raises(ValidationError):
        Route.model_validate({"route_short_name": "1"}, context=RESEAU)


def test_un_calendrier_sans_service_est_rejete():
    with pytest.raises(ValidationError):
        Calendar.model_validate({"monday": "1"}, context=RESEAU)


def test_une_correspondance_sans_arret_de_depart_est_rejetee():
    with pytest.raises(ValidationError):
        Transfer.model_validate({"to_stop_id": "2"}, context=RESEAU)

def test_la_serialisation_utilise_les_noms_de_champs_python_et_non_les_alias_gtfs():
    arret = Stop.model_validate(
        {"stop_id": "1", "stop_name": "Gare", "stop_desc": "Quai A", "stop_lat": "48.5"},
        context=RESEAU,
    )

    document = arret.model_dump()

    assert {"name", "description", "lat"} <= set(document)
    assert {"stop_name", "stop_desc", "stop_lat"}.isdisjoint(document)
