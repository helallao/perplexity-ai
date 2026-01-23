# Thiết kế FastAPI wrapper cho Perplexity client

**Mục tiêu:** Cung cấp service HTTP đơn giản để gọi Perplexity sync/async, hỗ trợ streaming SSE, upload file và deploy dễ dàng trên Rancher.

## Kiến trúc
- Core là `perplexity_async.Client` (async), endpoint sync chạy qua threadpool để tương thích hệ thống cũ.
- FastAPI app nằm trong `app/` với các endpoint:
  - `GET /health`
  - `POST /search` (sync wrapper)
  - `POST /search_async` (async)
  - `POST /search/stream` (SSE)
- Tránh Playwright/driver; chỉ dùng HTTP client có sẵn.

## API & Payload
- Hỗ trợ **JSON** và **multipart/form-data**.
  - JSON: gửi trực tiếp body.
  - Multipart: field `payload` chứa JSON string + nhiều file `files`.
- Payload chung:
  - `query` (bắt buộc)
  - `mode`, `model`, `sources`, `language`, `incognito`
  - `follow_up` (dict)
  - `cookies` (dict hoặc JSON string, override env)
- Files chuyển thành dict `{filename: bytes}` theo API hiện tại.

## Streaming
- SSE (`text/event-stream`).
- Mỗi chunk: `data: {json}\n\n`.
- Nếu lỗi khi stream, emit `event: error` với JSON `{error: ...}` rồi đóng stream.

## Cookies
- Mặc định đọc từ `PPLX_COOKIES_JSON`.
- Nếu request có `cookies`, dùng request (override env).
- Không log cookie giá trị.

## Lỗi & Log
- 400 nếu thiếu/không hợp lệ payload.
- 422 cho lỗi validation.
- 500 cho lỗi runtime ngoài dự kiến.
- Log metadata (endpoint, mode, thời gian) và trace khi exception.

## Container & Rancher
- Dockerfile dùng `python:3.11-slim`, chạy `uvicorn app.main:app`.
- Khuyến nghị cấu hình env qua Kubernetes Secret.

## Testing
- Test parse payload JSON/multipart, override cookies, streaming SSE.
- Mock client để tránh gọi Perplexity thật.
