"""Cloud Trace integration using OpenTelemetry SDK.

Provides a lightweight tracer abstraction that works with:
- Google Cloud Trace (when opentelemetry-exporter-gcp-trace is installed and project_id is set)
- Any custom SpanExporter (useful for tests with InMemorySpanExporter)
- No-op mode when neither is configured (local development default)
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Span, StatusCode

logger = logging.getLogger(__name__)

_TRACER_NAME = "agent-memory-graph"


def configure_tracer(
    project_id: str | None = None,
    *,
    span_exporter: SpanExporter | None = None,
    _allow_reset: bool = False,
) -> TracerProvider:
    """Configure the global tracer provider for Cloud Trace export.

    Configures tracing with the following precedence:
    1. Custom `span_exporter` when provided (used in tests).
    2. Cloud Trace exporter when `project_id` is set and the GCP exporter is installed.
    3. No-op tracer (default for local development).

    Args:
        project_id: GCP project identifier for Cloud Trace. When provided and
            `opentelemetry-exporter-gcp-trace` is installed, enables Cloud Trace export.
        span_exporter: Optional custom exporter. Takes precedence over `project_id`.
            Pass an `InMemorySpanExporter` instance in tests to capture spans.
        _allow_reset: Internal flag that permits re-configuring the global provider.
            Only use in test fixtures to reset between isolated test sessions.

    Returns:
        TracerProvider: The configured provider set as the global trace provider.
    """
    if _allow_reset:
        # Reset OTel global state to allow provider replacement in tests.
        trace._TRACER_PROVIDER = None  # noqa: SLF001

    provider = TracerProvider()

    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
        logger.info("tracer configured exporter=%s", type(span_exporter).__name__)
    elif project_id:
        try:
            from opentelemetry.exporter.cloud_trace import (  # type: ignore[import-not-found]
                CloudTraceSpanExporter,
            )

            exporter = CloudTraceSpanExporter(project_id=project_id)
            provider.add_span_processor(SimpleSpanProcessor(exporter))
            logger.info("tracer configured cloud_trace project=%s", project_id)
        except ImportError:
            logger.warning(
                "Cloud Trace exporter unavailable. "
                "Install opentelemetry-exporter-gcp-trace to enable export."
            )
    else:
        logger.debug("tracer configured no_op (no project_id provided)")

    trace.set_tracer_provider(provider)
    return provider


def get_tracer() -> trace.Tracer:
    """Return the configured application tracer.

    Returns:
        trace.Tracer: Active tracer for the application.
    """
    return trace.get_tracer(_TRACER_NAME)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, str | int | float | bool] | None = None,
) -> Generator[Span, None, None]:
    """Context manager that creates and manages a trace span.

    Sets ERROR status and records exceptions automatically when the body raises.

    Args:
        name: Span name describing the operation (e.g. "orchestrator.respond").
        attributes: Optional key-value span attributes for request context.
            Use string values for identifiers (tenant_id, session_id, request_id).

    Yields:
        Span: Active span. Call `span.set_attribute()` to add runtime attributes.

    Raises:
        Exception: Re-raises any exception after recording it on the span.
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as exc:
            span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            raise
