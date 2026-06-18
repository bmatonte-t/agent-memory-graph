"""FastAPI application for Agent Memory Graph."""

import logging
from collections.abc import AsyncGenerator  # noqa: TC003
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


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
        # Initialize Spanner client lazily when needed.
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


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            code="INTERNAL_ERROR",
            timestamp=datetime.now(UTC),
        ).model_dump(mode="json"),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)  # noqa: S104
