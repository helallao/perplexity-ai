from fastapi import FastAPI

from app.schemas import SearchPayload
from app.utils import parse_cookies

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/search")
async def search(payload: SearchPayload):
    cookies = parse_cookies(payload.cookies)
    return {"debug": {"cookies": cookies}}
