"""Application SLI metrics using OpenTelemetry Metrics API.

Provides lightweight metric instruments for the three operational SLIs:
- Request throughput (counters per operation and tier)
- Latency histograms (per operation)
- Error rates (counter of failed operations)

Cloud Monitoring export is available when `opentelemetry-exporter-gcp-monitoring`
is installed and a project_id is provided. Falls back to no-op without configuration.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from logging import getLogger
from typing import TYPE_CHECKING

from opentelemetry.metrics import Counter, Histogram, Meter, get_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)

if TYPE_CHECKING:
    from opentelemetry.sdk.metrics.export import MetricReader

try:
    CloudMonitoringMetricsExporter = import_module(
        "opentelemetry.exporter.cloud_monitoring"
    ).CloudMonitoringMetricsExporter
except ImportError:
    CloudMonitoringMetricsExporter = None

logger = getLogger(__name__)

_METER_NAME = "agent-memory-graph"


def configure_metrics(
    project_id: str | None = None,
    *,
    export_to_console: bool = False,
) -> MeterProvider:
    """Configure the global metrics provider for Cloud Monitoring export.

    Args:
        project_id: GCP project identifier for Cloud Monitoring export. When
            provided and `opentelemetry-exporter-gcp-monitoring` is installed,
            enables Cloud Monitoring export.
        export_to_console: When `True`, exports metrics to stdout (useful for
            local debugging). Mutually exclusive with Cloud Monitoring export.

    Returns:
        MeterProvider: The configured provider set as the global metrics provider.
    """
    readers: list[MetricReader] = []

    if export_to_console:
        readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))
        logger.info("metrics configured exporter=console")
    elif project_id:
        if CloudMonitoringMetricsExporter is not None:
            exporter = CloudMonitoringMetricsExporter(project_id=project_id)
            readers.append(PeriodicExportingMetricReader(exporter))
            logger.info("metrics configured cloud_monitoring project=%s", project_id)
        else:
            logger.warning(
                "Cloud Monitoring exporter unavailable. "
                "Install opentelemetry-exporter-gcp-monitoring to enable export."
            )
    else:
        logger.debug("metrics configured no_op (no project_id provided)")

    provider = MeterProvider(metric_readers=readers)
    from opentelemetry import metrics  # noqa: PLC0415

    metrics.set_meter_provider(provider)
    return provider


@lru_cache(maxsize=1)
def _get_meter() -> Meter:
    """Return the application meter (cached singleton).

    Returns:
        Meter: Active meter for the application.
    """
    return get_meter_provider().get_meter(_METER_NAME)


def orchestrator_request_counter() -> Counter:
    """Return the agent orchestration request counter.

    Returns:
        Counter: Tracks agent orchestration requests by mode and grounded status.
    """
    return _get_meter().create_counter(
        "agent.orchestrator.requests",
        unit="1",
        description="Number of agent orchestration requests",
    )


def mcp_tool_invocation_counter() -> Counter:
    """Return the MCP tool invocation counter.

    Returns:
        Counter: Tracks tool invocations by tool_name and success status.
    """
    return _get_meter().create_counter(
        "mcp.tool.invocations",
        unit="1",
        description="Number of MCP tool invocations",
    )


def mcp_tool_error_counter() -> Counter:
    """Return the MCP tool error counter.

    Returns:
        Counter: Tracks failed tool invocations by tool_name and error_code.
    """
    return _get_meter().create_counter(
        "mcp.tool.errors",
        unit="1",
        description="Number of failed MCP tool invocations",
    )


def pipeline_execution_histogram() -> Histogram:
    """Return the MindMap pipeline execution latency histogram.

    Returns:
        Histogram: Records pipeline execution latency in milliseconds.
    """
    return _get_meter().create_histogram(
        "mindmap.pipeline.execution_ms",
        unit="ms",
        description="MindMap pipeline execution latency in milliseconds",
    )


def pipeline_fact_counter() -> Counter:
    """Return the MindMap pipeline serialized fact counter.

    Returns:
        Counter: Tracks the number of facts serialized per pipeline execution.
    """
    return _get_meter().create_counter(
        "mindmap.pipeline.facts",
        unit="1",
        description="Number of serialized facts produced by MindMap pipeline executions",
    )


def emit_counter(name: str, *, labels: dict[str, str]) -> None:
    """Emit a single-unit increment on a named counter with the given labels.

    This is a convenience wrapper around the OTel Counter API that creates (or
    looks up) the counter instrument and records a value of 1.

    Args:
        name: Metric name (e.g. ``"authorization.denied"``).
        labels: Attribute dictionary forwarded as OTel metric attributes.
    """
    _get_meter().create_counter(name, unit="1").add(1, labels)


def record_authorization_denial(tenant_id: str, resource_type: str) -> None:
    """Emit a metric for every authorization DENIED decision.

    Args:
        tenant_id: Tenant identifier for the denied request.
        resource_type: Resource type that was denied (e.g. label or memory tier).
    """
    emit_counter(
        "authorization.denied",
        labels={"tenant_id": tenant_id, "resource_type": resource_type},
    )


def record_high_severity_contradiction(tenant_id: str, node_id: str) -> None:
    """Emit metric when HIGH severity contradiction is detected during synthesis.

    Args:
        tenant_id: Tenant identifier for the affected pipeline execution.
        node_id: Node identifier associated with the contradiction.
    """
    emit_counter(
        "memory.contradiction.high",
        labels={"tenant_id": tenant_id, "node_id": node_id},
    )
