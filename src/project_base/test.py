"""Template smoke-check script for local developer setup.

Remove this file when you start a new project from this template.
"""

import logging
from datetime import UTC, datetime

from src.project_base.src import a

logger = logging.getLogger(__name__)


def current_timestamp() -> datetime:
    """Return a timezone-aware UTC timestamp for smoke checks.

    Returns:
        datetime: Current UTC timestamp.
    """
    return datetime.now(UTC)


def main() -> None:
    """Run template smoke checks without introducing lint/type failures."""
    a()
    logger.info("Template smoke-check timestamp: %s", current_timestamp().isoformat())


if __name__ == "__main__":
    main()
