Agrégateur de données de transport statiques. Le service ingère les archives GTFS des réseaux enregistrés par MS-Admin, les normalise dans une base commune à toutes les AOM, et les expose au front via un subgraph GraphQL orienté carte.

| | |
|---|---|
| Langage | Python 3.13 (`.python-version`) |
| API | GraphQL fédéré (Apollo Federation 2.0) |
| Port hôte | 8002 (80 dans le conteneur) |
| Base | MongoDB (`aom_db`) |
| Broker | RabbitMQ |
| Processus | 2 (API + worker) |

## Ce que fait le service

Deux responsabilités distinctes, servies par deux processus qui partagent la même image et la même base.

**Il ingère.** Le worker consomme `gtfs.file.available`, télécharge l'archive ZIP, la décompresse, valide chaque ligne des fichiers `.txt` contre un modèle pydantic, écrit le résultat dans MongoDB, puis publie un accusé sur `gtfs.ingestion.result`. Un flux réel représente quelques centaines de milliers de documents — sur le jeu de test : 78 lignes, 1 675 arrêts, 27 746 trajets, 661 688 horaires de passage, 104 952 points de tracé.

**Il sert.** L'API expose les arrêts à proximité d'un point, les prochains départs, les lignes et leurs tracés. C'est la source de données de la carte du front. Toutes les lectures passent par des DataLoaders, aucune n'écrit.

Les deux processus sont indépendants : l'API répond même si le worker est arrêté, elle sert simplement les données de la dernière ingestion réussie.

## Architecture

Une seule image, lancée deux fois. **Le worker n'est pas optionnel** : sans lui, aucune donnée n'entre jamais en base et l'API renvoie des collections vides.

```mermaid
flowchart LR
    ADM["MS-Admin<br/>API"]
    WRK["Worker aom-agregator<br/>FastStream"]
    NET["transport.data.gouv.fr<br/>archive ZIP"]
    DB[("MongoDB aom_db<br/>9 collections")]
    API["API aom-agregator<br/>uvicorn, port 80"]
    GW["Apollo Router<br/>port 4000"]

    ADM -- "gtfs.file.available<br/>network_id, url, format" --> WRK
    WRK -- "GET" --> NET
    WRK --> DB
    WRK -- "gtfs.ingestion.result<br/>network_id, status, error" --> ADM
    DB --> API
    API --> GW
```

La topologie des queues est déclarée dans `app/core/topology.py`, un fichier **dupliqué à l'identique dans MS-Admin**. Une déclaration AMQP étant idempotente tant que les paramètres concordent, chaque service déclare tout ce qu'il touche — ce qu'il consomme comme ce qu'il produit — et l'ordre de démarrage n'a plus d'importance. En contrepartie, toute divergence entre les deux copies provoque un `PRECONDITION_FAILED` au démarrage : les modifier ensemble est une obligation, pas une préférence.

Le service est un **subgraph Apollo Federation 2.0**, atteint par le router à l'adresse `http://service-aom-agregator:80/graphql`. Il *étend* le type `TransitNetwork` défini par MS-Admin, via la clé `externalId` : un arrêt ou une ligne expose son réseau sans que ce dépôt ne stocke la moindre métadonnée de réseau.

## Modèle de données

Neuf collections dans `aom_db`, une par fichier GTFS : `agencies`, `routes`, `stops`, `trips`, `stop_times`, `calendar`, `calendar_dates`, `shapes`, `transfers`. Aucun ODM, des dictionnaires bruts écrits par `model_dump()`.

### Les identifiants sont préfixés par le réseau

C'est le choix structurant du service. Toutes les AOM partagent les mêmes collections, or rien ne garantit qu'un `route_id` soit unique entre deux flux — `"1"` est un identifiant de ligne extrêmement répandu. Chaque identifiant GTFS est donc préfixé à la validation par le `network_id` de l'ingestion en cours :

```
route_id "R1" du réseau 63b4c3d2  ->  "63b4c3d2:R1"
```

Le préfixage est porté par les types annotés `NamespacedId` / `OptionalNamespacedId` de `app/models/gtfs.py`, appliqués aussi bien aux clés primaires qu'aux références (`parent_station`, `shape_id`, `trip_id`...), afin que les jointures restent cohérentes. Le `network_id` circule via le contexte de validation pydantic, pas par un argument : `model_validate(row, context={"network_id": ...})`.

Conséquence pratique : **tout identifiant renvoyé par l'API est préfixé**, et une requête sur un `stop_id` brut issu d'un GTFS ne trouvera rien.

### Les horaires sont dénormalisés dans les passages

Chaque document de `stop_times` recopie les champs de son trajet et de sa ligne (`headsign`, `route_id`, `route_short_name`, `route_color`...) et porte un `departure_seconds` calculé. Le chemin le plus sollicité de l'API — les prochains départs d'un arrêt — devient une lecture d'une seule collection au lieu d'une double jointure. La donnée GTFS étant figée entre deux ingestions, la duplication ne peut pas se désynchroniser.

`departure_seconds` existe parce que **GTFS autorise les heures au-delà de 24 h** : un départ à `25:31:00` appartient au service de la veille et doit se trier après `23:59:00`, ce qu'un tri lexicographique sur la chaîne ne donne pas. `to_seconds()` convertit sans borne supérieure.

### L'échange de version est en deux phases

`IngestionService` insère les nouveaux documents avec un `_ingestion_id` tiré au hasard, puis supprime tout ce qui porte le même `network_id` et un `_ingestion_id` différent. La base n'est jamais vide entre les deux : une lecture concurrente voit l'ancienne version, puis la nouvelle.

Un fichier absent ou vide **ne déclenche aucune purge** : la collection est laissée en l'état plutôt que vidée par accident. C'est délibéré — mieux vaut une version périmée qu'un trou.

Les index sont créés à chaque ingestion par `_ensure_indexes`, l'opération étant idempotente : `network_id` partout, `2dsphere` sur `stops.location`, et des index composés sur `stop_times` pour les deux accès chauds (`stop_id + departure_seconds`, `trip_id + stop_sequence`).

## Surface GraphQL

| Opération | Rôle | Garde-fous |
|---|---|---|
| `stopsNearby(lat, lon, radiusMeters, first, networkId)` | Arrêts autour d'un point, triés par distance | rayon ≤ 5 000 m, `first` ≤ 100, coordonnées validées |
| `stop(id)` | Un arrêt par identifiant préfixé | — |
| `routes(networkId, page, pageSize)` | Lignes paginées | `pageSize` ≤ 100 |
| `route(id)` | Une ligne par identifiant préfixé | — |
| `status` | Sonde de vie, renvoie `"Online"` | — |

Les champs imbriqués font le gros du travail : `Stop.departures`, `Stop.routes`, `Route.directions`. Tous passent par un DataLoader construit par requête dans `get_context()`, ce qui regroupe les accès et évite le N+1 quand le front demande cent arrêts et leurs lignes.

`Route.directions` mérite une mention. GTFS ne décrit pas une « direction » : il décrit des milliers de trajets. Le loader choisit, pour chaque `direction_id`, **le trajet qui dessert le plus d'arrêts** comme représentant, et n'en charge que les arrêts et le tracé. C'est une heuristique, pas une vérité du format : une ligne dont la variante la plus longue est un service exceptionnel affichera cette variante.

`stopsNearby` filtre le réseau **à l'intérieur** de l'étape `$geoNear`, pas dans un `$match` en aval : le filtre est appliqué pendant le parcours de l'index géospatial.

Les positions sortent en GeoJSON, qui stocke `[longitude, latitude]` dans cet ordre contre-intuitif. Le type `GeoJSONPoint` expose en plus `latitude` et `longitude` explicitement, pour que le front n'ait pas à s'en souvenir.

## Contrats de message

### Entrant : `gtfs.file.available`

Consommé par le **worker**. Émis par MS-Admin à la création d'un réseau et à chaque relance.

```json
{
  "network_id": "63b4c3d2d7857ab0c49dde9a",
  "url": "https://transport.data.gouv.fr/resources/83710/download",
  "format": "GTFS",
  "extract_to": "/tmp/gtfs_data"
}
```

`format` est transmis tel quel à `ParserFactory`, qui ne connaît que `GTFS` et lève un `ValueError` explicite sur tout le reste — c'est ce qui rend le refus lisible dans le message d'erreur retourné. `extract_to` est optionnel et vaut `/tmp/gtfs_data` par défaut ; MS-Admin ne l'envoie pas.

### Sortant : `gtfs.ingestion.result`

Publié dans **tous les cas**, succès comme échec. Message persistant, queue durable.

```json
{
  "network_id": "63b4c3d2d7857ab0c49dde9a",
  "status": "ok",
  "error": null
}
```

`status` vaut strictement `ok` ou `error` ; le consommateur MS-Admin le valide par pydantic et rejette toute autre valeur. En cas d'échec, `error` porte le message de l'exception et **l'exception est relancée** après publication : FastStream applique alors sa politique par défaut, `REJECT_ON_ERROR`, qui rejette le message sans remise en file. Pas de boucle de redelivery, et la trace complète part dans les logs.

Le nettoyage des fichiers temporaires est dans un `finally` et ne peut pas masquer le résultat : une erreur de nettoyage est journalisée, jamais propagée.

## Stack

| Brique | Choix | À savoir |
|---|---|---|
| Web | FastAPI + uvicorn | Le broker est connecté dans le `lifespan` |
| GraphQL | Strawberry, fédération 2.0 | `federation_version` épinglé à `"2.0"` |
| Base | MongoDB via motor | Async, aucun ODM, dictionnaires bruts |
| Messagerie | FastStream 0.6.5 + RabbitMQ | `ack_policy` par défaut : `REJECT_ON_ERROR` |
| Validation | pydantic v2 | `BeforeValidator` pour le préfixage et les champs vides |
| HTTP sortant | httpx | Téléchargement en flux, par blocs de 8 Kio |
| Dépendances | uv + `uv.lock` | Le venv est hors du projet, dans `/opt/venv` |
| Lint | ruff | Exécuté en CI |
| Tests | pytest + mongomock-motor | 227 tests, MongoDB simulé en mémoire |

La décompression et la lecture CSV passent par `asyncio.to_thread` : ce sont les deux seules opérations bloquantes du worker, et les sortir de la boucle évite de figer la connexion au broker pendant une minute.

### Deux fichiers de configuration, deux rôles

`app/core/config.py` déclare deux classes qui lisent deux fichiers différents.

| Classe | Fichier | Contenu |
|---|---|---|
| `Secrets` | `.env`, non versionné | `DATABASE_URL`, `RABBITMQ_URL` |
| `Properties` | `application.properties`, versionné | `APP_NAME`, `LOG_LEVEL`, `GRAPHQL_PREFIX` |

Les variables d'environnement priment sur les deux, et le compose fournit déjà `DATABASE_URL` et `RABBITMQ_URL`. **Aucun `.env` n'est donc nécessaire pour démarrer en conteneur** — contrairement à MS-Admin, le `Dockerfile` d'ici ne copie pas ce fichier et un clone neuf se lance tel quel.

Pour exécuter l'API ou le worker **hors Docker**, en revanche, il faut écrire un `.env` à la racine, les valeurs par défaut du code ne pointant sur rien d'utilisable. Les ports sont ceux publiés par les composes :

```
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
DATABASE_URL=mongodb://mongouser:mongopassword@localhost:27002/?authSource=admin
```

`authSource=admin` est nécessaire dès que l'URL comporte un chemin de base : sans lui, pymongo tente de s'authentifier contre cette base plutôt que contre `admin`, et échoue sur un `Authentication failed` peu bavard.

## Démarrer depuis un clone neuf

1. Créer le réseau Docker partagé, s'il n'existe pas. Il est déclaré `external` par tous les composes du monorepo.

   ```bash
   docker network create hubert-network
   ```

2. Démarrer RabbitMQ, qui vit dans le compose de la racine du monorepo et non ici.

   ```bash
   docker compose -f ../../docker-compose.yml up -d rabbitmq
   ```

3. Lancer les deux conteneurs du service, plus sa base — `mongodb-aom-agregator`, `service-aom-agregator`, `ms-aom-agregator-worker`.

   ```bash
   docker compose up -d
   ```

4. Vérifier que le worker écoute. La ligne attendue nomme la queue.

   ```bash
   docker logs ms-aom-agregator-worker | grep "waiting for messages"
   ```

5. Déclencher une ingestion de démonstration. Compter environ une minute : le flux de test fait plus de 600 000 horaires de passage.

   ```bash
   docker compose exec -T aom-agregator-api python -m app.test_gtfs_publisher
   ```

   Depuis la racine du monorepo, `make seed` fait exactement la même chose.

6. Interroger le subgraph en direct, sans passer par la gateway. GraphiQL est servi sur `http://localhost:8002/graphql`.

   ```bash
   curl -s -X POST http://localhost:8002/graphql -H 'Content-Type: application/json' -d '{"query":"{ routes(pageSize:5){ totalCount items { id shortName longName } } }"}'
   ```

   Un `totalCount` à zéro signifie que l'ingestion n'a pas eu lieu ou a échoué : relire les logs du worker avant de chercher ailleurs.

### Après toute modification du schéma

Le router Apollo valide chaque requête contre `gateway/supergraph.graphql`, un fichier statique chargé au démarrage. Il n'introspecte rien à l'exécution. Ajouter un champ ici le rend disponible sur le port 8002 mais **invisible depuis la gateway** tant que le supergraph n'est pas recomposé. Le symptôme est un `GRAPHQL_VALIDATION_FAILED` côté front alors que tout fonctionne en direct.

```bash
make supergraph   # depuis la racine du monorepo
```

La recomposition introspecte tous les subgraphs et échoue si un seul manque à l'appel : ils doivent tous être démarrés.

### Tests

La suite tourne hors ligne, MongoDB étant simulé en mémoire par `mongomock-motor`. Ni conteneur ni broker nécessaires.

```bash
uv run pytest -q
```
