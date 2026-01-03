"""FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger

from app.config import get_settings
from app.dependencies import close_redis_pool, get_redis
from app.models.responses import HealthResponse


def setup_logging() -> None:
    """Configure structured JSON logging."""
    settings = get_settings()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if settings.log_format == "json":
        # JSON format for production
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "time", "levelname": "level"},
        )
    else:
        # Text format for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level)

    # Reduce noise from uvicorn access logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    logger = logging.getLogger(__name__)
    settings = get_settings()

    # Startup
    setup_logging()
    logger.info(
        "Starting tee-sniper-api",
        extra={
            "host": settings.api_host,
            "port": settings.api_port,
            "debug": settings.debug,
        },
    )

    yield

    # Shutdown
    logger.info("Shutting down tee-sniper-api")
    await close_redis_pool()
    logger.info("Redis connection pool closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Tee Sniper API",
        description="API for golf course tee time booking",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health check endpoint
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Health check",
        description="Returns the health status of the service",
    )
    async def health_check() -> HealthResponse:
        logger = logging.getLogger(__name__)
        redis_healthy = False

        try:
            redis = await get_redis()
            await redis.ping()
            redis_healthy = True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")

        return HealthResponse(
            status="healthy" if redis_healthy else "degraded",
            timestamp=datetime.now(timezone.utc),
            redis_connected=redis_healthy,
        )

    return app


# Create app instance
app = create_app()
