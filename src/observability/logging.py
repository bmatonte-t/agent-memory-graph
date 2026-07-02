"""Structured logging helpers for Google Cloud Logging compatibility.

Provides a small utility so all layers emit log records with consistent
`extra` dictionaries that Cloud Logging can ingest as structured JSON labels
rather than needing to parse the message string.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from opentelemetry import trace

if TYPE_CHECKING:
    from logging import Logger


_REQUIRED_LOG_FIELDS = {
    "trace_id": "",
    "tenant_id": "",
    "tool_name": "",
    "latency_ms": 0.0,
    "error_code": "",
}


def _resolve_trace_id() -> str:
    """Resolve current trace id from active span context.

    Returns:
        str: Hex-encoded trace id, or empty string when no active span exists.
    """
    context = trace.get_current_span().get_span_context()
    if context.trace_id == 0:
        return ""
    return f"{context.trace_id:032x}"


def _build_structured_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized structured payload with required observability keys.

    Args:
        fields: Caller-provided structured fields.

    Returns:
        dict[str, Any]: Normalized fields with required keys.
    """
    payload = {**_REQUIRED_LOG_FIELDS}
    payload.update(fields)
    if not payload.get("trace_id"):
        payload["trace_id"] = _resolve_trace_id()
    return payload


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
    normalized_fields = _build_structured_fields(fields)
    message = f"{event} {json.dumps(normalized_fields, default=str)}"
    log.log(level, message, extra={**normalized_fields, "event": event})
