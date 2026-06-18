"""Project package."""

from .logging import configure_logging
from .settings import settings

# * This sets up logging outputs. Use `logger = logging.getLogger(__name__)` to log.
# * If writing a library, remove this configuration from here! Leave this here if this is an app.
configure_logging(configuration=settings.logging)

__all__: list[str] = []
