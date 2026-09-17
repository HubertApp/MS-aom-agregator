from faststream.rabbit import Channel, RabbitBroker, ExchangeType, RabbitExchange
from app.core.config import secrets

broker = RabbitBroker(
    secrets.RABBITMQ_URL,
    default_channel=Channel(on_return_raises=True),
)
gtfs_events_exchange = RabbitExchange(
    "gtfs.events",
    type=ExchangeType.TOPIC,
    durable=True,
)
