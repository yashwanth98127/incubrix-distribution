from app.connectors.base import Connector
from app.connectors.discourse import DiscourseConnector
from app.connectors.lemmy import LemmyConnector
from app.connectors.devto import DevtoConnector
from app.connectors.ghost import GhostConnector
from app.connectors.webhook import WebhookConnector
from app.connectors.assisted import AssistedConnector

REGISTRY: dict[str, Connector] = {
    "discourse": DiscourseConnector(),
    "lemmy": LemmyConnector(),
    "devto": DevtoConnector(),
    "ghost": GhostConnector(),
    "webhook": WebhookConnector(),
    "assisted": AssistedConnector(),
}


def get_connector(key: str) -> Connector:
    from app.core.errors import IncuBrixError
    c = REGISTRY.get(key)
    if not c:
        raise IncuBrixError("NOT_FOUND", f"no connector registered for key '{key}'")
    return c
