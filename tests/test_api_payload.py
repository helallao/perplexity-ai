import json

import httpx
import pytest

from app.main import app


class StubClient:
    def __init__(self, cookies):
        self.cookies = cookies

    def search(self, **_kwargs):
        return {"debug": {"cookies": self.cookies}}


def stub_sync_client(cookies):
    return StubClient(cookies)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_cookies_override_env(monkeypatch):
    monkeypatch.setenv("PPLX_COOKIES_JSON", json.dumps({"a": "env"}))
    monkeypatch.setattr("app.main.get_sync_client", stub_sync_client)
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
