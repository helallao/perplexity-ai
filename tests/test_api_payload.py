import json

import httpx
import pytest

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_cookies_override_env(monkeypatch):
    monkeypatch.setenv("PPLX_COOKIES_JSON", json.dumps({"a": "env"}))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/search",
            json={
                "query": "hi",
                "cookies": {"a": "req"},
            },
        )
    assert resp.status_code == 200
    assert resp.json()["debug"]["cookies"] == {"a": "req"}
