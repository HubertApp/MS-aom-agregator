

from tests.conftest import FLUX_DE_REFERENCE

from app.services.parsers.factory import ParserFactory
from app.services.parsers.gtfs_parser import GTFSParser

COLLECTIONS_ATTENDUES = {collection for _, collection, _ in GTFSParser.FILE_MAPPING}


def _arret(documents, identifiant):
    return next(doc for doc in documents if doc["stop_id"] == identifiant)


def test_la_fabrique_retourne_un_parseur_gtfs_quel_que_soit_la_casse():
    assert isinstance(ParserFactory.get_parser("gtfs"), GTFSParser)


async def test_le_parsing_retourne_toutes_les_collections_du_mapping(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "N1")

    assert set(resultat) == COLLECTIONS_ATTENDUES


async def test_un_flux_reduit_retourne_quand_meme_toutes_les_collections(ecrire_flux_gtfs):
    flux = ecrire_flux_gtfs({"agency.txt": FLUX_DE_REFERENCE["agency.txt"]})

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert set(resultat) == COLLECTIONS_ATTENDUES


async def test_un_fichier_facultatif_absent_donne_une_collection_vide(ecrire_flux_gtfs):
    flux = ecrire_flux_gtfs({k: v for k, v in FLUX_DE_REFERENCE.items() if k != "shapes.txt"})

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert resultat["shapes"] == []
    assert len(resultat["stops"]) == 2


async def test_un_fichier_limite_a_son_entete_donne_une_collection_vide(ecrire_flux_gtfs):
    flux = ecrire_flux_gtfs(
        {**FLUX_DE_REFERENCE, "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n"}
    )

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert resultat["stops"] == []

async def test_une_ligne_invalide_est_ecartee_sans_perdre_les_lignes_valides(
    gtfs_feed_with_errors,
):
    resultat = await GTFSParser().parse(str(gtfs_feed_with_errors), "N1")

    assert {doc["stop_id"] for doc in resultat["stops"]} == {"N1:1", "N1:3"}


async def test_un_fichier_entierement_invalide_donne_une_collection_vide(ecrire_flux_gtfs):
    flux = ecrire_flux_gtfs(
        {
            **FLUX_DE_REFERENCE,
            "stops.txt": (
                "stop_id,stop_name,stop_lat,stop_lon\n"
                ",Sans identifiant,48.5,2.25\n"
                ",Sans identifiant non plus,49.0,3.0\n"
            ),
        }
    )

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert resultat["stops"] == []


async def test_toutes_les_lignes_invalides_sont_ecartees_meme_au_dela_du_plafond_de_log(
    ecrire_flux_gtfs,
):
    invalides = "".join(f",Arrêt anonyme {i},48.5,2.25\n" for i in range(50))
    flux = ecrire_flux_gtfs(
        {
            **FLUX_DE_REFERENCE,
            "stops.txt": (
                "stop_id,stop_name,stop_lat,stop_lon\n"
                "1,Gare Centrale,48.5,2.25\n"
                "2,Place du Marché,49.75,3.5\n" + invalides
            ),
        }
    )

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert len(resultat["stops"]) == 2


async def test_le_plafond_de_log_limite_le_nombre_de_lignes_detaillees(
    ecrire_flux_gtfs, capsys
):
    invalides = "".join(f",Arrêt anonyme {i},48.5,2.25\n" for i in range(50))
    flux = ecrire_flux_gtfs(
        {**FLUX_DE_REFERENCE, "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n" + invalides}
    )

    await GTFSParser().parse(str(flux), "N1")

    detaillees = capsys.readouterr().out.count(" ignorée : ")
    assert detaillees == GTFSParser.MAX_LOGGED_ERRORS

async def test_les_coordonnees_geojson_sont_en_longitude_puis_latitude(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "N1")

    gare = _arret(resultat["stops"], "N1:1")
    assert gare["location"] == {"type": "Point", "coordinates": [2.25, 48.5]}


async def test_les_champs_lat_et_lon_disparaissent_apres_construction_du_point(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "N1")

    gare = _arret(resultat["stops"], "N1:1")
    assert "lat" not in gare and "lon" not in gare


async def test_un_arret_sans_coordonnees_est_place_a_l_origine(gtfs_feed_with_errors):
    resultat = await GTFSParser().parse(str(gtfs_feed_with_errors), "N1")

    sans_coordonnees = _arret(resultat["stops"], "N1:3")
    assert sans_coordonnees["location"]["coordinates"] == [0.0, 0.0]

async def test_un_fichier_encode_en_utf8_avec_bom_est_lu_correctement(ecrire_flux_gtfs):
    flux = ecrire_flux_gtfs(FLUX_DE_REFERENCE, encoding="utf-8-sig")

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert resultat["agencies"][0]["agency_id"] == "N1:AG1"


async def test_les_dates_d_exception_sont_lues_depuis_le_dossier_du_flux(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "N1")

    assert len(resultat["calendar_dates"]) == 1
    assert resultat["calendar_dates"][0]["service_id"] == "N1:S1"


async def test_le_reseau_est_propage_jusqu_aux_documents_produits(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "reseau-de-metz")

    assert all(doc["stop_id"].startswith("reseau-de-metz:") for doc in resultat["stops"])


async def test_les_references_croisees_sont_namespacees_de_maniere_coherente(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "N1")

    assert resultat["trips"][0]["route_id"] == resultat["routes"][0]["route_id"]
    assert resultat["stop_times"][0]["trip_id"] == resultat["trips"][0]["trip_id"]


async def test_chaque_arret_porte_la_forme_normalisee_de_son_nom(gtfs_feed):
    resultat = await GTFSParser().parse(str(gtfs_feed), "N1")

    marche = _arret(resultat["stops"], "N1:2")
    assert marche["name_normalized"] == "placedumarche"


async def test_un_arret_sans_nom_porte_une_forme_normalisee_vide(ecrire_flux_gtfs):
    flux = ecrire_flux_gtfs({
        **FLUX_DE_REFERENCE,
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n1,,48.5,2.25\n",
    })

    resultat = await GTFSParser().parse(str(flux), "N1")

    assert _arret(resultat["stops"], "N1:1")["name_normalized"] == ""
