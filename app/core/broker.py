from faststream.rabbit import RabbitBroker
from app.core.config import secrets

broker = RabbitBroker(secrets.RABBITMQ_URL)
