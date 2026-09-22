from app.core.text import normalize_for_search


def test_les_accents_sont_retires_du_nom_normalise():
    assert normalize_for_search("Place du Marché") == "placedumarche"


def test_la_casse_est_ignoree_par_la_normalisation():
    assert normalize_for_search("GARE CENTRALE") == normalize_for_search("gare centrale")


def test_les_espaces_sont_retires_du_nom_normalise():
    assert normalize_for_search("Gare   Centrale") == "garecentrale"


def test_la_ponctuation_est_retiree_du_nom_normalise():
    assert normalize_for_search("Saint-Lazare (quai n°2)") == "saintlazarequain2"


def test_les_chiffres_sont_conserves_dans_le_nom_normalise():
    assert normalize_for_search("Quai 14") == "quai14"


def test_un_nom_absent_est_normalise_en_chaine_vide():
    assert normalize_for_search(None) == ""
