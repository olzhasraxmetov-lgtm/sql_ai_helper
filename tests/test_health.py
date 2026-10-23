from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from sql_helper.config import Settings
from sql_helper.presentation.api.app import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(Settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
