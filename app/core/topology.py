"""Topologie RabbitMQ partagée entre MS-Admin et MS-aom-agregator.

Ce fichier est dupliqué à l'identique dans les deux dépôts.

Une déclaration de queue AMQP est idempotente tant que les paramètres
concordent : chaque service déclare donc tout ce qu'il touche, producteur
comme consommateur, et l'ordre de démarrage n'a plus aucune importance.

En contrepartie, toute divergence de paramètres entre les deux copies provoque
un PRECONDITION_FAILED (406) au démarrage. Les deux copies doivent donc être
modifiées ensemble, et le broker vidé de la queue concernée avant déploiement.
"""

from faststream.rabbit import RabbitQueue

# MS-Admin -> MS-aom-agregator : demande d'ingestion d'un flux GTFS.
GTFS_FILE_AVAILABLE = RabbitQueue("gtfs.file.available", durable=True)

# MS-aom-agregator -> MS-Admin : résultat de l'ingestion.
GTFS_INGESTION_RESULT = RabbitQueue("gtfs.ingestion.result", durable=True)
