import json

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from app.clients import get_async_client, get_sync_client
from app.schemas import SearchPayload
from app.utils import parse_cookies

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/search")
async def search(request: Request):
    payload = await parse_payload(request)
    cookies = parse_cookies(payload.cookies)
    files = await collect_files(request)

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


@app.post("/search_async")
async def search_async(request: Request):
    payload = await parse_payload(request)
    cookies = parse_cookies(payload.cookies)
    files = await collect_files(request)

    client = await get_async_client(cookies)
    return await client.search(
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


@app.post("/search/stream")
async def search_stream(request: Request):
    payload = await parse_payload(request)
    cookies = parse_cookies(payload.cookies)
    files = await collect_files(request)

    client = await get_async_client(cookies)

    async def event_gen():
        try:
            async for chunk in await client.search(
                query=payload.query,
                mode=payload.mode,
                model=payload.model,
                sources=payload.sources,
                files=files,
                stream=True,
                language=payload.language,
                follow_up=payload.follow_up,
                incognito=payload.incognito,
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


async def parse_payload(request: Request) -> SearchPayload:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        data = await request.json()
        return SearchPayload(**data)

    form = await request.form()
    payload_raw = form.get("payload")
    data = {} if payload_raw is None else json.loads(payload_raw)
    return SearchPayload(**data)


async def collect_files(request: Request) -> dict:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("application/json"):
        return {}

    form = await request.form()
    files = {}
    for item in form.getlist("files"):
        content = await item.read()
        files[item.filename] = content
    return files
