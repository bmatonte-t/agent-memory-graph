"""Structured logging helpers for Google Cloud Logging compatibility.

Provides a small utility so all layers emit log records with consistent
`extra` dictionaries that Cloud Logging can ingest as structured JSON labels
rather than needing to parse the message string.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from logging import Logger


def structured_log(
    log: Logger,
    level: int,
    event: str,
    fields: dict[str, Any],
) -> None:
    """Emit a structured log record compatible with Google Cloud Logging.

    The log message is kept as a compact JSON string for readability in
    non-Cloud environments. The same `fields` dict is also passed as `extra`
    so that Cloud Logging structured sinks can index individual labels.

    Args:
        log: Logger instance for the calling module.
        level: Logging level constant (e.g., `logging.INFO`).
        event: Event identifier string used as the primary message key.
        fields: Key-value pairs to include both in the JSON message and as
            structured labels in Cloud Logging.
    """
    message = f"{event} {json.dumps(fields, default=str)}"
    log.log(level, message, extra={**fields, "event": event})
