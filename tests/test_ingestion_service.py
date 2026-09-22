
import math

import pytest

from app.services import ingestion_service as ingestion_module

pytestmark = pytest.mark.usefixtures("mock_db")

def arrets(network_id, identifiants=("1", "2"), nom="Arrêt"):
    return [
        {"stop_id": f"{network_id}:{i}", "name": f"{nom} {i}"} for i in identifiants
    ]


def routes(network_id, identifiants=("R1",)):
    return [{"route_id": f"{network_id}:{i}", "short_name": i} for i in identifiants]

class CollectionEspionnee:

    def __init__(self, collection, nom, journal, purge_en_echec=None, avant_purge=None):
        self._collection = collection
        self._nom = nom
        self._journal = journal
        self._purge_en_echec = purge_en_echec
        self._avant_purge = avant_purge

    def __getattr__(self, attribut):
        return getattr(self._collection, attribut)

    async def insert_many(self, documents, *args, **kwargs):
        self._journal.append(("insert_many", self._nom, len(documents)))
        return await self._collection.insert_many(documents, *args, **kwargs)

    async def delete_many(self, *args, **kwargs):
        self._journal.append(("delete_many", self._nom, None))
        if self._avant_purge is not None:
            await self._avant_purge(self._collection)
        if self._nom == self._purge_en_echec:
            raise RuntimeError("purge indisponible")
        return await self._collection.delete_many(*args, **kwargs)


class BaseEspionnee:
    def __init__(self, db, journal, purge_en_echec=None, avant_purge=None):
        self._db = db
        self._journal = journal
        self._purge_en_echec = purge_en_echec
        self._avant_purge = avant_purge

    def __getitem__(self, nom):
        return CollectionEspionnee(
            self._db[nom], nom, self._journal, self._purge_en_echec, self._avant_purge
        )


@pytest.fixture
def journal(service):
    appels = []
    service.db = BaseEspionnee(service.db, appels)
    return appels


class ParseurEspion:
    def __init__(self, resultat):
        self.resultat = resultat
        self.appels = []

    async def parse(self, directory_path, network_id):
        self.appels.append((directory_path, network_id))
        return self.resultat


@pytest.fixture
def installer_parseur(monkeypatch):
    def _installer(resultat):
        espion = ParseurEspion(resultat)
        monkeypatch.setattr(
            ingestion_module.ParserFactory,
            "get_parser",
            staticmethod(lambda format_type: espion),
        )
        return espion

    return _installer


async def documents_de(service, collection, network_id):
    return await service.db[collection].find({"network_id": network_id}).to_list(None)

async def test_l_ingestion_transmet_le_dossier_et_le_reseau_au_parseur(
    service, installer_parseur
):
    espion = installer_parseur({"stops": arrets("N1")})

    await service.ingest_datas("/flux/extrait", "GTFS", "N1")

    assert espion.appels == [("/flux/extrait", "N1")]


async def test_l_ingestion_ecrit_en_base_le_resultat_du_parseur(service, installer_parseur):
    installer_parseur({"stops": arrets("N1", ("1", "2", "3"))})

    await service.ingest_datas("/flux/extrait", "GTFS", "N1")

    assert await service.db["stops"].count_documents({"network_id": "N1"}) == 3


async def test_un_format_inconnu_remonte_une_erreur(service):
    with pytest.raises(ValueError):
        await service.ingest_datas("/flux/extrait", "NETEX", "N1")

async def test_chaque_document_insere_porte_le_reseau_ingere(service):
    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")

    documents = await documents_de(service, "stops", "N1")
    assert len(documents) == 2
    assert all(doc["network_id"] == "N1" for doc in documents)


async def test_chaque_document_insere_porte_un_identifiant_d_ingestion(service):
    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")

    documents = await documents_de(service, "stops", "N1")
    assert all(doc.get("_ingestion_id") for doc in documents)


async def test_toutes_les_collections_d_une_ingestion_partagent_le_meme_identifiant(service):
    await service._save_to_mongodb({"stops": arrets("N1"), "routes": routes("N1")}, "N1")

    inseres = await documents_de(service, "stops", "N1") + await documents_de(
        service, "routes", "N1"
    )
    assert len({doc["_ingestion_id"] for doc in inseres}) == 1


async def test_deux_ingestions_successives_ont_des_identifiants_differents(service):
    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")
    premier = (await documents_de(service, "stops", "N1"))[0]["_ingestion_id"]

    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")
    second = (await documents_de(service, "stops", "N1"))[0]["_ingestion_id"]

    assert premier != second

async def test_ingerer_un_second_reseau_laisse_le_premier_intact(service):
    await service._save_to_mongodb({"stops": arrets("metz")}, "metz")

    await service._save_to_mongodb({"stops": arrets("nancy")}, "nancy")

    documents_metz = await documents_de(service, "stops", "metz")
    assert {doc["stop_id"] for doc in documents_metz} == {"metz:1", "metz:2"}


async def test_reingerer_un_reseau_ne_touche_pas_les_autres_reseaux(service):
    await service._save_to_mongodb({"stops": arrets("metz")}, "metz")
    await service._save_to_mongodb({"stops": arrets("nancy")}, "nancy")
    avant = await documents_de(service, "stops", "nancy")

    await service._save_to_mongodb({"stops": arrets("metz", ("1", "2", "3"))}, "metz")

    apres = await documents_de(service, "stops", "nancy")
    assert apres == avant


async def test_reingerer_un_reseau_ne_cree_pas_de_doublons(service):
    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")

    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")

    documents = await documents_de(service, "stops", "N1")
    assert len(documents) == 2
    assert len({doc["stop_id"] for doc in documents}) == 2


async def test_un_arret_disparu_du_nouveau_flux_disparait_de_la_base(service):
    await service._save_to_mongodb({"stops": arrets("N1", ("1", "2", "3"))}, "N1")

    await service._save_to_mongodb({"stops": arrets("N1", ("1", "2"))}, "N1")

    documents = await documents_de(service, "stops", "N1")
    assert {doc["stop_id"] for doc in documents} == {"N1:1", "N1:2"}


async def test_reingerer_un_flux_modifie_met_a_jour_les_valeurs_en_base(service):
    await service._save_to_mongodb({"stops": arrets("N1", ("1",), nom="Ancien nom")}, "N1")

    await service._save_to_mongodb({"stops": arrets("N1", ("1",), nom="Nouveau nom")}, "N1")

    documents = await documents_de(service, "stops", "N1")
    assert [doc["name"] for doc in documents] == ["Nouveau nom 1"]

async def test_une_collection_vide_ne_declenche_aucune_ecriture(service, journal):
    await service._save_to_mongodb({"stops": arrets("N1"), "shapes": []}, "N1")

    assert [appel for appel in journal if appel[1] == "shapes"] == []


async def test_une_collection_absente_du_nouveau_flux_conserve_ses_documents(service):
    # Délibéré : un fichier absent ou un parsing raté ne doit pas vider la base.
    await service._save_to_mongodb(
        {"stops": arrets("N1"), "shapes": [{"shape_id": "N1:SH1"}]}, "N1"
    )

    await service._save_to_mongodb({"stops": arrets("N1"), "shapes": []}, "N1")

    assert await service.db["shapes"].count_documents({"network_id": "N1"}) == 1

async def test_les_insertions_precedent_toutes_les_suppressions(service, journal):
    await service._save_to_mongodb({"stops": arrets("N1"), "routes": routes("N1")}, "N1")
    journal.clear()

    await service._save_to_mongodb({"stops": arrets("N1"), "routes": routes("N1")}, "N1")

    operations = [appel[0] for appel in journal]
    derniere_insertion = len(operations) - 1 - operations[::-1].index("insert_many")
    premiere_suppression = operations.index("delete_many")
    assert derniere_insertion < premiere_suppression


async def test_le_reseau_reste_lisible_pendant_toute_la_reingestion(service):
    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")

    presents_au_debut_de_la_purge = []

    async def _observer(collection):
        presents_au_debut_de_la_purge.append(
            await collection.count_documents({"network_id": "N1"})
        )

    service.db = BaseEspionnee(service.db, [], avant_purge=_observer)

    await service._save_to_mongodb({"stops": arrets("N1")}, "N1")

    # Les deux versions coexistent le temps de la bascule : 2 anciens + 2 nouveaux.
    assert presents_au_debut_de_la_purge == [4]

async def test_tous_les_documents_sont_inseres_malgre_le_decoupage_en_lots(
    service, monkeypatch
):
    monkeypatch.setattr(service, "BATCH_SIZE", 3)

    await service._save_to_mongodb({"stops": arrets("N1", tuple(str(i) for i in range(7)))}, "N1")

    assert await service.db["stops"].count_documents({"network_id": "N1"}) == 7


async def test_le_nombre_de_lots_suit_la_taille_configuree(service, monkeypatch, journal):
    monkeypatch.setattr(service, "BATCH_SIZE", 3)

    await service._save_to_mongodb({"stops": arrets("N1", tuple(str(i) for i in range(7)))}, "N1")

    insertions = [appel for appel in journal if appel[0] == "insert_many"]
    assert len(insertions) == math.ceil(7 / 3)

@pytest.fixture
def collections_indexees(service, monkeypatch):
    appels = []

    async def _enregistrer(collection_name):
        appels.append(collection_name)

    monkeypatch.setattr(service, "_ensure_indexes", _enregistrer)
    return appels


async def test_les_index_sont_crees_pour_chaque_collection_ecrite(service, collections_indexees):
    await service._save_to_mongodb({"stops": arrets("N1"), "routes": routes("N1")}, "N1")

    assert collections_indexees == ["stops", "routes"]


async def test_aucun_index_n_est_cree_pour_une_collection_ignoree(service, collections_indexees):
    await service._save_to_mongodb({"stops": arrets("N1"), "shapes": []}, "N1")

    assert "shapes" not in collections_indexees


@pytest.mark.parametrize(
    "collection", ["stops", "stop_times", "trips", "routes", "calendar_dates"]
)
async def test_la_creation_des_index_ne_leve_pas_d_exception(service, collection):
    await service._ensure_indexes(collection)

async def test_l_echec_de_purge_d_une_collection_n_empeche_pas_les_suivantes(service):
    await service._save_to_mongodb({"stops": arrets("N1"), "routes": routes("N1")}, "N1")

    appels = []
    service.db = BaseEspionnee(service.db, appels, purge_en_echec="stops")
    await service._save_to_mongodb(
        {"stops": arrets("N1"), "routes": routes("N1", ("R2",))}, "N1"
    )

    routes_en_base = await documents_de(service, "routes", "N1")
    assert {doc["route_id"] for doc in routes_en_base} == {"N1:R2"}


async def _index_de(service, collection):
    await service._ensure_indexes(collection)
    information = await service.db[collection].index_information()
    return {tuple(champ for champ, _ in index["key"]) for index in information.values()}


async def test_les_arrets_sont_indexes_sur_le_nom_normalise(service):
    assert ("name_normalized",) in await _index_de(service, "stops")


async def test_les_arrets_sont_indexes_par_reseau_puis_nom_normalise(service):
    assert ("network_id", "name_normalized") in await _index_de(service, "stops")
