import json

import httpx
import pytest

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


class StubAsync:
    async def search(self, **kwargs):
        async def gen():
            yield {"answer": "a"}
            yield {"answer": "b"}

        return gen() if kwargs.get("stream") else {"answer": "ok"}


async def stub_async_client(_cookies):
    return StubAsync()


@pytest.mark.anyio
async def test_search_async(monkeypatch):
    monkeypatch.setattr("app.main.get_async_client", stub_async_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/search_async", json={"query": "hi"})
    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"


@pytest.mark.anyio
async def test_stream_sse(monkeypatch):
    monkeypatch.setattr("app.main.get_async_client", stub_async_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("POST", "/search/stream", json={"query": "hi"}) as resp:
            assert resp.status_code == 200
            body = b"".join([chunk async for chunk in resp.aiter_bytes()]).decode()
    assert "data: {" in body
