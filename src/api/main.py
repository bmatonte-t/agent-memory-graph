"""FastAPI application for Agent Memory Graph."""

import asyncio
import logging
import os
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable  # noqa: TC003
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter
from typing import Annotated, cast

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from src.agent import build_vertex_adapter_from_env
from src.agent.orchestrator import AgentOrchestrator
from src.db.spanner_client import SpannerClient
from src.mcp.service import MCPToolService
from src.memory.api import MemoryAPI
from src.memory.cognitive_weighting import CognitiveWeighting
from src.memory.mindmap_pipeline import MindMapPipeline, MindMapPipelineError
from src.models.agent import AgentOrchestrationRequest, AgentOrchestrationResponse
from src.models.mcp import MCPDiscoveryResponse, MCPInvokeRequest, MCPInvokeResponse
from src.models.mindmap import MindMapRequest, MindMapResponse
from src.models.schemas import (
    EndSessionRequest,
    EndSessionResponse,
    ErrorResponse,
    GraphExportResponse,
    HealthCheckResponse,
)
from src.observability.logging import structured_log
from src.observability.tracing import configure_tracer
from src.pipelines.bigquery_ingestion.ingest_orchestrator import BigQueryIngestJob
from src.project_base.logging import LoggingConfiguration
from src.project_base.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_DEFAULT_EMULATOR_PROJECT_ID = "test-project"
_DEFAULT_EMULATOR_INSTANCE_ID = "test-instance"
_DEFAULT_EMULATOR_DATABASE_ID = "test-database"
_HTTP_ERROR_STATUS_THRESHOLD = 400


def _initialize_spanner_from_environment() -> None:
    """Initialize the Spanner client from environment variables when available."""
    emulator_host = os.getenv("SPANNER_EMULATOR_HOST")

    project_id = os.getenv("GCP_PROJECT_ID")
    instance_id = os.getenv("SPANNER_INSTANCE_ID")
    database_id = os.getenv("SPANNER_DATABASE_ID")

    if emulator_host:
        project_id = project_id or _DEFAULT_EMULATOR_PROJECT_ID
        instance_id = instance_id or _DEFAULT_EMULATOR_INSTANCE_ID
        database_id = database_id or _DEFAULT_EMULATOR_DATABASE_ID

    if not all((project_id, instance_id, database_id)):
        logger.info("Spanner client not initialized at startup; missing configuration")
        return

    resolved_project_id = project_id
    resolved_instance_id = instance_id
    resolved_database_id = database_id

    if resolved_project_id is None or resolved_instance_id is None or resolved_database_id is None:
        logger.info("Spanner client not initialized at startup; missing configuration")
        return

    SpannerClient.initialize(
        project_id=resolved_project_id,
        instance_id=resolved_instance_id,
        database_id=resolved_database_id,
    )
    logger.info(
        "Spanner client initialized",
        extra={
            "spanner_project_id": project_id,
            "spanner_instance_id": instance_id,
            "spanner_database_id": database_id,
            "using_emulator": bool(emulator_host),
        },
    )


class DecayWeightsRequest(BaseModel):
    """Request payload for temporal decay endpoint."""

    decay_rate: float = Field(default=0.05, ge=0.0, le=1.0)


class PruneWeightsRequest(BaseModel):
    """Request payload for pruning endpoint."""

    threshold: float = Field(default=0.30, ge=0.0, le=1.0)


def _scheduler_request_metadata(request: Request) -> dict[str, str]:
    """Extract Cloud Scheduler metadata from HTTP headers.

    Args:
        request: FastAPI request object.

    Returns:
        dict[str, str]: Scheduler metadata for structured logs.
    """
    return {
        "job_id": request.headers.get("X-CloudScheduler-JobName", "manual-or-unknown"),
        "schedule_time": request.headers.get("X-CloudScheduler-ScheduleTime", "unknown"),
        "tenant_id": "global",
    }


class BigQueryIngestRequest(BaseModel):
    """Request payload for BigQuery ingestion orchestration."""

    project_id: str = Field(..., min_length=1)
    dataset_id: str = Field(..., min_length=1)
    table_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "project_id": "analytics-project",
                    "dataset_id": "customer_360",
                    "table_id": "support_tickets",
                    "tenant_id": "tenant_latam",
                }
            ]
        }
    }


class BigQueryIngestAcceptedResponse(BaseModel):
    """Response payload for accepted asynchronous BigQuery ingestion jobs."""

    status: str = Field(default="accepted")
    job_id: str
    tenant_id: str
    project_id: str
    dataset_id: str
    table_id: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "accepted",
                    "job_id": "ef3414f4-d7f6-4f78-9ef0-2bd6b9d4f13f",
                    "tenant_id": "tenant_latam",
                    "project_id": "analytics-project",
                    "dataset_id": "customer_360",
                    "table_id": "support_tickets",
                }
            ]
        }
    }


def _resolve_spanner_connection_settings() -> tuple[str, str, str]:
    """Resolve Spanner connection settings from runtime environment.

    Returns:
        tuple[str, str, str]: Spanner project, instance, and database identifiers.

    Raises:
        RuntimeError: If required variables are missing.
    """
    project_id = os.getenv("SPANNER_PROJECT_ID") or os.getenv("GCP_PROJECT_ID")
    instance_id = os.getenv("SPANNER_INSTANCE_ID")
    database_id = os.getenv("SPANNER_DATABASE_ID")

    if not project_id or not instance_id or not database_id:
        msg = (
            "Missing Spanner runtime settings. Required: SPANNER_INSTANCE_ID, "
            "SPANNER_DATABASE_ID, and SPANNER_PROJECT_ID or GCP_PROJECT_ID."
        )
        raise RuntimeError(msg)

    return project_id, instance_id, database_id


async def _execute_bigquery_ingestion_job(
    job_id: str,
    request: BigQueryIngestRequest,
) -> None:
    """Execute one BigQuery ingestion job in background.

    Args:
        job_id: Stable identifier for observability logs.
        request: Ingestion request payload.
    """
    logger.info(
        "bigquery_ingestion_job_started",
        extra={
            "job_id": job_id,
            "tenant_id": request.tenant_id,
            "project_id": request.project_id,
            "dataset_id": request.dataset_id,
            "table_id": request.table_id,
        },
    )
    try:
        spanner_project_id, spanner_instance_id, spanner_database_id = (
            _resolve_spanner_connection_settings()
        )
        ingest_job = BigQueryIngestJob(
            project_id=request.project_id,
            bigquery_dataset_id=request.dataset_id,
            spanner_project_id=spanner_project_id,
            spanner_instance_id=spanner_instance_id,
            spanner_database_id=spanner_database_id,
            tenant_id=request.tenant_id,
        )
        result = await asyncio.to_thread(ingest_job.ingest_table, request.table_id)
        logger.info(
            "bigquery_ingestion_job_completed",
            extra={
                "job_id": job_id,
                "tenant_id": request.tenant_id,
                "project_id": request.project_id,
                "dataset_id": request.dataset_id,
                "table_id": request.table_id,
                "nodes_written": result.get("nodes_written", 0),
                "edges_written": result.get("edges_written", 0),
                "relationships_inferred": result.get("relationships_inferred", 0),
            },
        )
    except Exception:
        logger.exception(
            "bigquery_ingestion_job_failed",
            extra={
                "job_id": job_id,
                "tenant_id": request.tenant_id,
                "project_id": request.project_id,
                "dataset_id": request.dataset_id,
                "table_id": request.table_id,
            },
        )


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Application lifespan handler for startup and shutdown events."""
    logger.info("Starting up Agent Memory Graph API")
    try:
        LoggingConfiguration().configure_logging(  # type: ignore[call-arg]
            configuration=settings.logging,
            cloud_logging=settings.cloud_logging if settings.cloud_logging.enabled else None,
        )
        configure_tracer(
            project_id=settings.cloud_trace.project_id if settings.cloud_trace.enabled else None,
        )
        _initialize_spanner_from_environment()
        yield
    finally:
        logger.info("Shutting down Agent Memory Graph API")
        try:
            SpannerClient.close()
        except Exception:
            logger.exception("Error during shutdown")


# Create FastAPI app
app = FastAPI(
    title="Agent Memory Graph API",
    description="GCP-native agent memory system with tripartite memory topology",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def api_request_logging_middleware(request: Request, call_next: object) -> Response:
    """Emit structured API request logs with normalized observability fields.

    Args:
        request: Incoming FastAPI request.
        call_next: Next middleware/handler callback.

    Returns:
        JSONResponse: Downstream HTTP response.
    """
    started = perf_counter()
    status_code = 500
    error_code = ""
    response: Response
    typed_call_next = cast("Callable[[Request], Awaitable[Response]]", call_next)

    try:
        response = await typed_call_next(request)
        status_code = int(response.status_code)
        if status_code >= _HTTP_ERROR_STATUS_THRESHOLD:
            error_code = f"HTTP_{status_code}"
    except Exception:
        error_code = "UNHANDLED_EXCEPTION"
        raise
    finally:
        latency_ms = round((perf_counter() - started) * 1000, 3)
        structured_log(
            logger,
            logging.INFO,
            "api_request_completed",
            {
                "tenant_id": request.query_params.get("tenant_id", ""),
                "tool_name": request.url.path,
                "latency_ms": latency_ms,
                "error_code": error_code,
                "http_method": request.method,
                "status_code": status_code,
            },
        )

    return response


_initialize_spanner_from_environment()

mindmap_pipeline = MindMapPipeline()
mcp_tool_service = MCPToolService(mindmap_pipeline=mindmap_pipeline)
agent_orchestrator = AgentOrchestrator(
    mcp_tool_service=mcp_tool_service,
    vertex_adapter=build_vertex_adapter_from_env(),
)


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Health check endpoint."""
    logger.info("Health check requested")
    return HealthCheckResponse(
        status="healthy",
        timestamp=datetime.now(UTC),
        database="initialized",
    )


@app.post("/api/v1/mindmap/execute", response_model=MindMapResponse)
async def execute_mindmap(request: MindMapRequest) -> MindMapResponse:
    """Execute Phase 2 MindMap pipeline.

    Args:
        request (MindMapRequest): Pipeline execution request.

    Returns:
        MindMapResponse: Grounded response with traceability envelope.

    Raises:
        HTTPException: Raised when validation fails.
    """
    try:
        return await mindmap_pipeline.execute(query=request.query, session_id=request.session_id)
    except MindMapPipelineError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.code}:{exc}") from exc


@app.post("/api/v1/mcp/invoke", response_model=MCPInvokeResponse)
async def invoke_mcp_tool(request: MCPInvokeRequest) -> MCPInvokeResponse:
    """Invoke one MCP tool through a stable HTTP contract."""
    return await mcp_tool_service.invoke(request)


@app.get("/.well-known/mcp")
async def mcp_discovery(
    version: Annotated[str | None, Query()] = None,
) -> MCPDiscoveryResponse:
    """Expose versioned MCP discovery manifest for client auto-configuration."""
    try:
        return mcp_tool_service.get_discovery_manifest(requested_version=version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/agent/respond", response_model=AgentOrchestrationResponse)
async def agent_respond(request: AgentOrchestrationRequest) -> AgentOrchestrationResponse:
    """Execute one prompt -> tool-chain -> response orchestration cycle."""
    return await agent_orchestrator.respond(request)


@app.post("/api/v1/session/end", response_model=EndSessionResponse)
async def end_session(request: EndSessionRequest) -> EndSessionResponse:
    """Close a session and execute session knowledge extraction protocol."""
    return await MemoryAPI.end_session(
        tenant_id=request.tenant_id,
        session_id=request.session_id,
        end_reason=request.end_reason,
        domain_hint=request.domain_hint,
        window_size=request.window_size,
    )


@app.post("/internal/decay-weights")
async def decay_weights(
    request: DecayWeightsRequest,
    http_request: Request,
) -> dict[str, float | int | str]:
    """Run temporal decay for semantic and context memory tiers."""
    scheduler_metadata = _scheduler_request_metadata(http_request)
    logger.info(
        "Starting scheduler decay run",
        extra={
            **scheduler_metadata,
            "operation": "decay_weights",
            "decay_rate": request.decay_rate,
        },
    )

    try:
        updated_nodes = await CognitiveWeighting.decay_weights_temporal(
            decay_rate=request.decay_rate
        )
    except ValueError as exc:
        logger.warning(
            "Scheduler decay run rejected due to invalid payload",
            extra={
                **scheduler_metadata,
                "operation": "decay_weights",
                "result": "invalid_payload",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception(
            "Scheduler decay run failed",
            extra={
                **scheduler_metadata,
                "operation": "decay_weights",
                "result": "failure",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "Scheduler decay run completed",
        extra={
            **scheduler_metadata,
            "operation": "decay_weights",
            "result": "success",
            "updated_nodes": updated_nodes,
        },
    )

    return {
        "status": "ok",
        "operation": "decay_weights",
        "decay_rate": request.decay_rate,
        "updated_nodes": updated_nodes,
    }


@app.post("/internal/prune-weights")
async def prune_weights(
    request: PruneWeightsRequest,
    http_request: Request,
) -> dict[str, float | int | str]:
    """Run weight-based pruning for low-cognitive-weight nodes."""
    scheduler_metadata = _scheduler_request_metadata(http_request)
    logger.info(
        "Starting scheduler pruning run",
        extra={
            **scheduler_metadata,
            "operation": "prune_weights",
            "threshold": request.threshold,
        },
    )

    try:
        updated_nodes = await CognitiveWeighting.prune_weights_below_threshold(
            threshold=request.threshold
        )
    except ValueError as exc:
        logger.warning(
            "Scheduler pruning run rejected due to invalid payload",
            extra={
                **scheduler_metadata,
                "operation": "prune_weights",
                "result": "invalid_payload",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception(
            "Scheduler pruning run failed",
            extra={
                **scheduler_metadata,
                "operation": "prune_weights",
                "result": "failure",
                "error": str(exc),
            },
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    logger.info(
        "Scheduler pruning run completed",
        extra={
            **scheduler_metadata,
            "operation": "prune_weights",
            "result": "success",
            "updated_nodes": updated_nodes,
        },
    )

    return {
        "status": "ok",
        "operation": "prune_weights",
        "threshold": request.threshold,
        "updated_nodes": updated_nodes,
    }


@app.post(
    "/internal/ingest/bigquery",
    response_model=BigQueryIngestAcceptedResponse,
    status_code=202,
)
async def ingest_bigquery_table(
    request: BigQueryIngestRequest,
    background_tasks: BackgroundTasks,
) -> BigQueryIngestAcceptedResponse:
    """Trigger asynchronous BigQuery table ingestion orchestration.

    Args:
        request: BigQuery ingestion request payload.
        background_tasks: FastAPI background task scheduler.

    Returns:
        BigQueryIngestAcceptedResponse: Accepted job envelope.
    """
    job_id = str(uuid.uuid4())
    background_tasks.add_task(_execute_bigquery_ingestion_job, job_id, request)
    return BigQueryIngestAcceptedResponse(
        job_id=job_id,
        tenant_id=request.tenant_id,
        project_id=request.project_id,
        dataset_id=request.dataset_id,
        table_id=request.table_id,
    )


@app.get("/api/v1/graph/export", response_model=GraphExportResponse)
async def export_graph_snapshot(
    tenant_id: str,
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
) -> GraphExportResponse:
    """Export a tenant graph snapshot in JSON-LD format.

    Args:
        tenant_id: Tenant identifier for graph scoping.
        limit: Maximum number of nodes and edges returned.

    Returns:
        GraphExportResponse: JSON-LD graph export envelope.
    """
    return await MemoryAPI.export_graph_snapshot(tenant_id=tenant_id, limit=limit)


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Create a stable error envelope for API responses.

    Args:
        status_code: HTTP status code to return.
        code: Stable machine-readable error code.
        message: Client-safe error message.

    Returns:
        JSONResponse: Serialized error response payload.
    """
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=message,
            code=code,
            timestamp=datetime.now(UTC),
        ).model_dump(mode="json"),
    )


def _format_request_validation_error(exc: RequestValidationError) -> str:
    """Build a client-safe validation message without leaking internals.

    Args:
        exc: Validation exception from request parsing.

    Returns:
        str: Sanitized message with field guidance only.
    """
    body_fields: set[str] = set()

    minimum_body_location_depth = 2

    for error in exc.errors():
        location = error.get("loc", ())
        if len(location) >= minimum_body_location_depth and location[0] == "body":
            field_name = str(location[-1])
            if field_name:
                body_fields.add(field_name)

    if body_fields:
        ordered_fields = ", ".join(sorted(body_fields))
        return f"Invalid request payload. Check fields: {ordered_fields}."

    return "Invalid request payload."


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    """Global fallback exception handler for unhandled errors."""
    logger.exception("Unhandled exception")
    return _error_response(
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected internal error occurred.",
    )


@app.exception_handler(ValueError)
async def validation_exception_handler(_request: Request, exc: ValueError) -> JSONResponse:
    """Map domain validation errors to stable 400 responses."""
    logger.warning("Validation error: %s", exc)
    return _error_response(
        status_code=400,
        code="VALIDATION_ERROR",
        message=str(exc),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Map request schema validation errors to stable 422 responses."""
    client_message = _format_request_validation_error(exc)
    logger.warning(
        "Request validation error",
        extra={
            "error_count": len(exc.errors()),
            "fields": sorted(
                {
                    str(error.get("loc", ())[-1])
                    for error in exc.errors()
                    if error.get("loc") and error.get("loc", ())[0] == "body"
                }
            ),
        },
    )
    return _error_response(
        status_code=422,
        code="REQUEST_VALIDATION_ERROR",
        message=client_message,
    )


@app.exception_handler(PermissionError)
async def permission_exception_handler(_request: Request, exc: PermissionError) -> JSONResponse:
    """Map permission failures to stable 403 responses without leaking internals."""
    logger.warning("Permission error: %s", exc)
    return _error_response(
        status_code=403,
        code="FORBIDDEN",
        message="The requested operation is not permitted.",
    )


@app.exception_handler(RuntimeError)
async def runtime_exception_handler(_request: Request, exc: RuntimeError) -> JSONResponse:
    """Map runtime errors to stable 500 responses without leaking internals."""
    logger.error("Runtime error: %s", exc)
    return _error_response(
        status_code=500,
        code="RUNTIME_ERROR",
        message="An internal error occurred.",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)  # noqa: S104
