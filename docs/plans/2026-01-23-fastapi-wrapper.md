# FastAPI Wrapper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Xây dựng FastAPI service bọc Perplexity client (sync + async), hỗ trợ SSE streaming, upload file, và deploy dễ trên Rancher.

**Architecture:** Core async dùng `perplexity_async.Client`; endpoint sync chạy bằng threadpool. API nhận JSON hoặc multipart, cookies ưu tiên từ request và fallback env. Streaming dùng SSE.

**Tech Stack:** FastAPI, Uvicorn, Pydantic, python-multipart, pytest

---

### Task 1: Thêm scaffold FastAPI + /health

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Test: `tests/test_api_health.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_health_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_health.py::test_health_ok -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'` or 404

**Step 3: Write minimal implementation**

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_health.py::test_health_ok -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/__init__.py app/main.py tests/test_api_health.py
git commit -m "feat: add fastapi app with health endpoint"
```

---

### Task 2: Thêm model payload + parse cookies (env + override)

**Files:**
- Create: `app/schemas.py`
- Create: `app/utils.py`
- Modify: `app/main.py`
- Test: `tests/test_api_payload.py`

**Step 1: Write the failing test**

```python
import json
import os
from fastapi.testclient import TestClient
from app.main import app


def test_cookies_override_env(monkeypatch):
    monkeypatch.setenv("PPLX_COOKIES_JSON", json.dumps({"a": "env"}))
    client = TestClient(app)

    resp = client.post("/search", json={
        "query": "hi",
        "cookies": {"a": "req"}
    })
    assert resp.status_code == 200
    assert resp.json()["debug"]["cookies"] == {"a": "req"}
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_payload.py::test_cookies_override_env -v`
Expected: FAIL (endpoint not implemented)

**Step 3: Write minimal implementation**

```python
# app/utils.py
import json
import os


def parse_cookies(raw_cookies):
    env_raw = os.getenv("PPLX_COOKIES_JSON")
    if raw_cookies is None:
        raw_cookies = env_raw
    if raw_cookies is None:
        return {}
    if isinstance(raw_cookies, dict):
        return raw_cookies
    return json.loads(raw_cookies)
```

```python
# app/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SearchPayload(BaseModel):
    query: str
    mode: str = "auto"
    model: Optional[str] = None
    sources: List[str] = Field(default_factory=lambda: ["web"])
    language: str = "en-US"
    incognito: bool = False
    follow_up: Optional[Dict[str, Any]] = None
    cookies: Optional[Dict[str, Any]] = None
```

```python
# app/main.py (tạm trả debug)
from fastapi import FastAPI
from app.schemas import SearchPayload
from app.utils import parse_cookies

app = FastAPI()

@app.post("/search")
async def search(payload: SearchPayload):
    cookies = parse_cookies(payload.cookies)
    return {"debug": {"cookies": cookies}}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_payload.py::test_cookies_override_env -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/schemas.py app/utils.py app/main.py tests/test_api_payload.py
git commit -m "feat: add payload schema and cookie parsing"
```

---

### Task 3: Endpoint sync/async thực thi search + multipart files

**Files:**
- Create: `app/clients.py`
- Modify: `app/main.py`
- Test: `tests/test_api_search.py`

**Step 1: Write the failing test**

```python
import json
from fastapi.testclient import TestClient
from app.main import app


class StubSync:
    def __init__(self):
        self.called = None

    def search(self, **kwargs):
        self.called = kwargs
        return {"answer": "ok"}


class StubAsync:
    async def search(self, **kwargs):
        return {"answer": "ok"}


async def stub_async_client(_cookies):
    return StubAsync()


def stub_sync_client(_cookies):
    return StubSync()


def test_search_multipart_files(monkeypatch):
    monkeypatch.setattr("app.clients.get_sync_client", stub_sync_client)

    client = TestClient(app)
    resp = client.post(
        "/search",
        files={
            "payload": (None, json.dumps({"query": "hi"}), "application/json"),
            "files": ("a.txt", b"hello", "text/plain"),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "ok"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_search.py::test_search_multipart_files -v`
Expected: FAIL (no multipart handling/client)

**Step 3: Write minimal implementation**

```python
# app/clients.py
import perplexity
import perplexity_async


def get_sync_client(cookies):
    return perplexity.Client(cookies)


async def get_async_client(cookies):
    return await perplexity_async.Client(cookies)
```

```python
# app/main.py (thêm parse multipart + gọi client)
from fastapi import FastAPI, Request
from app.schemas import SearchPayload
from app.utils import parse_cookies
from app.clients import get_sync_client

app = FastAPI()

async def parse_payload(request: Request) -> SearchPayload:
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        return SearchPayload(**data)
    form = await request.form()
    payload_raw = form.get("payload")
    data = {} if payload_raw is None else json.loads(payload_raw)
    return SearchPayload(**data)

@app.post("/search")
async def search(request: Request):
    payload = await parse_payload(request)
    cookies = parse_cookies(payload.cookies)

    files = {}
    form = await request.form()
    for item in form.getlist("files"):
        content = await item.read()
        files[item.filename] = content

    client = get_sync_client(cookies)
    return client.search(
        query=payload.query,
        mode=payload.mode,
        model=payload.model,
        sources=payload.sources,
        files=files,
        stream=False,
        language=payload.language,
        follow_up=payload.follow_up,
        incognito=payload.incognito,
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_search.py::test_search_multipart_files -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/clients.py app/main.py tests/test_api_search.py
git commit -m "feat: add sync search endpoint with multipart"
```

---

### Task 4: Thêm async endpoint + SSE streaming

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api_stream.py`

**Step 1: Write the failing test**

```python
import json
from fastapi.testclient import TestClient
from app.main import app


class StubAsync:
    async def search(self, **kwargs):
        async def gen():
            yield {"answer": "a"}
            yield {"answer": "b"}
        return gen() if kwargs.get("stream") else {"answer": "ok"}


async def stub_async_client(_cookies):
    return StubAsync()


def test_stream_sse(monkeypatch):
    monkeypatch.setattr("app.clients.get_async_client", stub_async_client)

    client = TestClient(app)
    with client.stream("POST", "/search/stream", json={"query": "hi"}) as resp:
        assert resp.status_code == 200
        body = "".join([chunk.decode() for chunk in resp.iter_bytes()])
    assert "data: {" in body
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_stream.py::test_stream_sse -v`
Expected: FAIL (no /search/stream)

**Step 3: Write minimal implementation**

```python
from fastapi.responses import StreamingResponse
from app.clients import get_async_client

@app.post("/search_async")
async def search_async(request: Request):
    payload = await parse_payload(request)
    cookies = parse_cookies(payload.cookies)
    files = await collect_files(request)
    client = await get_async_client(cookies)
    return await client.search(..., stream=False)

@app.post("/search/stream")
async def search_stream(request: Request):
    payload = await parse_payload(request)
    cookies = parse_cookies(payload.cookies)
    files = await collect_files(request)
    client = await get_async_client(cookies)

    async def event_gen():
        try:
            async for chunk in await client.search(..., stream=True):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_stream.py::test_stream_sse -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/main.py tests/test_api_stream.py
git commit -m "feat: add async search and sse streaming"
```

---

### Task 5: Thêm dependencies + Dockerfile + tài liệu

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `Dockerfile`
- Create: `.dockerignore`
- Modify: `README.md`

**Step 1: Update dependencies**

Add to `pyproject.toml` dependencies:
- `fastapi>=0.109`
- `uvicorn>=0.27`
- `python-multipart>=0.0.9`

Add to `requirements.txt` same packages.

**Step 2: Add Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 3: Add .dockerignore**

```
.git
.worktrees
__pycache__
*.pyc
tests
images
perplexity.log
```

**Step 4: Update README**

Add section “FastAPI Service” with:
- Run local: `uvicorn app.main:app --reload`
- Env: `PPLX_COOKIES_JSON`
- Sample curl for `/search` and `/search/stream`

**Step 5: Commit**

```bash
git add pyproject.toml requirements.txt Dockerfile .dockerignore README.md
git commit -m "chore: add fastapi deps and docker support"
```
