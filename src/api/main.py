"""FastAPI application for Agent Memory Graph."""

import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.db.spanner_client import SpannerClient
from src.models.schemas import ErrorResponse, HealthCheckResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Agent Memory Graph API",
    description="GCP-native agent memory system with tripartite memory topology",
    version="0.1.0",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database connections on startup."""
    logger.info("Starting up Agent Memory Graph API")
    try:
        # Initialize Spanner client (in production, use real credentials)
        # For now, this will be called explicitly when needed
        pass
    except Exception as e:
        logger.error(f"Failed to initialize Spanner client: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Close database connections on shutdown."""
    logger.info("Shutting down Agent Memory Graph API")
    try:
        SpannerClient.close()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": "initialized",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=str(exc),
            code="INTERNAL_ERROR",
            timestamp=datetime.utcnow(),
        ).dict(),
    )


# Import and include routers (will be created in Phase 1C)
# from src.api.routes import memory_router
# app.include_router(memory_router.router, prefix="/api/v1/memory", tags=["memory"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
