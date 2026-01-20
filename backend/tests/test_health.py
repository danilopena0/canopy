"""Basic health check tests."""

import pytest
from litestar.testing import AsyncTestClient

from src.app import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncTestClient(app=app) as client:
        yield client


async def test_health_endpoint(client):
    """Test the health check endpoint returns 200."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
