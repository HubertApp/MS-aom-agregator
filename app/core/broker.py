from faststream.rabbit import Channel, RabbitBroker

from app.core.config import secrets

# FastStream publie déjà avec mandatory=True, mais aio-pika est configuré avec
# on_return_raises=False : un message non routable est renvoyé par RabbitMQ puis
# avalé, et le publish réussit. on_return_raises=True le transforme en
# DeliveryError, donc en échec visible plutôt qu'en perte silencieuse.
broker = RabbitBroker(
    secrets.RABBITMQ_URL,
    default_channel=Channel(on_return_raises=True),
)
