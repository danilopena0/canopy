"""Litestar application setup."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from litestar import Litestar, get
from litestar.config.cors import CORSConfig
from litestar.logging import LoggingConfig
from litestar.openapi import OpenAPIConfig
from litestar.openapi.spec import Contact

from .config import get_settings
from .db import close_database, get_database
from .models import HealthResponse
from .routes import (
    ApplicationController,
    DocumentController,
    JobController,
    ProfileController,
    SearchController,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncIterator[None]:
    """Application lifespan context manager.

    Handles database initialization on startup and cleanup on shutdown.
    """
    settings = get_settings()
    logger.info(f"Starting Canopy with database: {settings.database_path}")

    # Initialize database
    await get_database()
    logger.info("Database initialized")

    yield

    # Cleanup
    await close_database()
    logger.info("Database connection closed")


@get("/api/health")
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", database="connected")


# CORS configuration for frontend development
cors_config = CORSConfig(
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# OpenAPI documentation configuration
openapi_config = OpenAPIConfig(
    title="Canopy API",
    version="0.1.0",
    description="Job search and application assistant API",
    contact=Contact(name="Canopy"),
)

# Logging configuration
logging_config = LoggingConfig(
    root={"level": get_settings().log_level, "handlers": ["console"]},
    formatters={
        "standard": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    },
    log_exceptions="always",
)

# Create the Litestar application
app = Litestar(
    route_handlers=[
        health_check,
        JobController,
        SearchController,
        ApplicationController,
        ProfileController,
        DocumentController,
    ],
    lifespan=[lifespan],
    cors_config=cors_config,
    openapi_config=openapi_config,
    logging_config=logging_config,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
