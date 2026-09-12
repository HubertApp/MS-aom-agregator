from faststream.rabbit import ExchangeType, RabbitBroker, RabbitExchange
from app.core.config import secrets

broker = RabbitBroker(secrets.RABBITMQ_URL)

gtfs_events_exchange = RabbitExchange(
    "gtfs.events",
    type=ExchangeType.TOPIC,
    durable=True,
)
