from faststream.rabbit import RabbitBroker
from app.core.config import secrets, properties

broker = RabbitBroker(secrets.RABBITMQ_URL)
