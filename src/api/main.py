"""FastAPI application for Agent Memory Graph."""

import logging
import os
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.agent import build_vertex_adapter_from_env
from src.agent.orchestrator import AgentOrchestrator
from src.db.spanner_client import SpannerClient
from src.mcp.service import MCPToolService
from src.memory.cognitive_weighting import CognitiveWeighting
from src.memory.mindmap_pipeline import MindMapPipeline, MindMapPipelineError
from src.models.agent import AgentOrchestrationRequest, AgentOrchestrationResponse
from src.models.mcp import MCPInvokeRequest, MCPInvokeResponse
from src.models.mindmap import MindMapRequest, MindMapResponse
from src.models.schemas import ErrorResponse, HealthCheckResponse
from src.observability.tracing import configure_tracer
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


@app.post("/api/v1/agent/respond", response_model=AgentOrchestrationResponse)
async def agent_respond(request: AgentOrchestrationRequest) -> AgentOrchestrationResponse:
    """Execute one prompt -> tool-chain -> response orchestration cycle."""
    return await agent_orchestrator.respond(request)


@app.post("/internal/decay-weights")
async def decay_weights(request: DecayWeightsRequest) -> dict[str, float | int | str]:
    """Run temporal decay for semantic and context memory tiers."""
    try:
        updated_nodes = await CognitiveWeighting.decay_weights_temporal(
            decay_rate=request.decay_rate
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "ok",
        "operation": "decay_weights",
        "decay_rate": request.decay_rate,
        "updated_nodes": updated_nodes,
    }


@app.post("/internal/prune-weights")
async def prune_weights(request: PruneWeightsRequest) -> dict[str, float | int | str]:
    """Run weight-based pruning for low-cognitive-weight nodes."""
    try:
        updated_nodes = await CognitiveWeighting.prune_weights_below_threshold(
            threshold=request.threshold
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "status": "ok",
        "operation": "prune_weights",
        "threshold": request.threshold,
        "updated_nodes": updated_nodes,
    }


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
