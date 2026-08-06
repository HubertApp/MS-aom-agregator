# MS-aom-agregator

Microservice d'agrégation des données GTFS (arrêts, lignes, horaires) de
plusieurs autorités organisatrices de mobilité (AOM) dans une base commune,
exposées via une API GraphQL en lecture seule.

## Stack

- Python 3.12+, FastAPI
- Strawberry GraphQL (fédération)
- MongoDB (Motor, driver async)
- RabbitMQ (FastStream) pour la réception des flux GTFS à ingérer
- uv pour la gestion des dépendances

## Fonctionnement

1. MS-Admin publie un message `gtfs.file.available` sur RabbitMQ.
2. Le worker (`app/workers`) consomme le message et déclenche l'ingestion.
3. Le fichier GTFS est parsé et enregistré en base, avec dénormalisation des
   champs utiles (nom de ligne, couleur...) directement dans `stop_times`.
4. L'API GraphQL lit ces données pour servir arrêts, lignes et horaires.

## Architecture

- `app/services` : ingestion et parsing des flux GTFS
- `app/workers` : consommateur RabbitMQ
- `app/repositories` : accès brut à MongoDB
- `app/graphql` : schéma, types, resolvers, dataloaders (API en lecture seule)
- `app/models` : modèles Pydantic de validation GTFS

## Configuration

Créer un fichier `.env` à la racine avec les bonnes valeurs
RABBITMQ_URL=amqp://user:password@localhost:5672
DATABASE_URL=mongodb://mongouser:mongopassword@localhost:27017/?authSource=admin

Remplacer les valeurs exemple ci-dessus par les vraies. Ce qui change est l'user le password et l'adresse.


## Lancement

docker compose up -d


Démarre RabbitMQ, MongoDB, l'API et le worker d'ingestion.

- API GraphQL : http://localhost:8002/graphql

## Tests

uv run pytest


Base MongoDB simulée (`mongomock-motor`) : aucune dépendance à une base réelle.