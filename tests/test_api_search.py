import json

import httpx
import pytest

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


class StubSync:
    def __init__(self):
        self.called = None

    def search(self, **kwargs):
        self.called = kwargs
        return {"answer": "ok"}


def stub_sync_client(_cookies):
    return StubSync()


@pytest.mark.anyio
async def test_search_multipart_files(monkeypatch):
    monkeypatch.setattr("app.main.get_sync_client", stub_sync_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/search",
            files=[
                ("payload", (None, json.dumps({"query": "hi"}), "application/json")),
                ("files", ("a.txt", b"hello", "text/plain")),
            ],
        )

    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"
