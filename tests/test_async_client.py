"""Tests for perplexity_async.client.Client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from perplexity.config import ENDPOINT_AUTH_SESSION, SSE_ASK_HEADERS
from perplexity.exceptions import (
    AuthenticationError,
    FileUploadError,
    IncompleteResponseError,
    NetworkError,
    RateLimitError,
    ValidationError,
)
from perplexity_async.client import Client as AsyncClient


def make_sse_frames(answer: str = "OK") -> tuple[dict, list[bytes]]:
    """Build frames matching Perplexity's current combined end event."""
    message = {
        "blocks": [
            {
                "intended_usage": "ask_text",
                "markdown_block": {"answer": answer},
            }
        ]
    }
    frames = [
        f"event: message\r\ndata: {json.dumps(message)}".encode("utf-8"),
        b"event: end_of_stream\r\ndata: {}",
    ]
    expected = {**message, "answer": answer, "chunks": []}
    return expected, frames


def make_legacy_sse_frames(answer: str = "Legacy answer") -> tuple[dict, list[bytes]]:
    """Build frames using legacy nested text and FINAL step."""
    final_data = json.dumps({"answer": answer, "chunks": []})
    nested_text = json.dumps([{"step_type": "FINAL", "content": {"answer": final_data}}])
    message = {"text": nested_text}
    frames = [
        f"event: message\r\ndata: {json.dumps(message)}".encode("utf-8"),
        b"event: end_of_stream\r\ndata: {}",
    ]
    expected = {"text": json.loads(nested_text), "answer": answer, "chunks": []}
    return expected, frames


def make_async_response(frames: list[bytes], status_code: int = 200) -> MagicMock:
    """Build a mock response whose aiter_lines yields the specified frames."""
    response = MagicMock(status_code=status_code, ok=(200 <= status_code < 300))

    async def aiter_lines(*args, **kwargs):
        for frame in frames:
            yield frame

    response.aiter_lines = aiter_lines
    return response


@pytest.fixture
def mock_session():
    """Fixture providing a mocked requests.AsyncSession with successful handshake GET."""
    with patch("perplexity_async.client.requests.AsyncSession") as session_cls:
        session = MagicMock()
        session.headers = {}
        session.cookies = MagicMock()
        session.cookies.get_dict.return_value = {}
        session.get = AsyncMock(return_value=MagicMock(status_code=200, ok=True))
        session.post = AsyncMock()
        session_cls.return_value = session
        yield session


@pytest.mark.asyncio
async def test_async_client_init_unauthenticated(mock_session: MagicMock) -> None:
    """Client defaults for unauthenticated session."""
    cli = await AsyncClient()
    assert not cli.own
    assert cli.copilot == 0
    assert cli.file_upload == 0
    mock_session.get.assert_awaited_once_with(ENDPOINT_AUTH_SESSION)


@pytest.mark.asyncio
async def test_async_client_init_authenticated(mock_session: MagicMock) -> None:
    """Client defaults for authenticated session with cookies."""
    cli = await AsyncClient(cookies={"session_token": "valid_token"})
    assert cli.own
    assert cli.copilot == float("inf")
    assert cli.file_upload == float("inf")


@pytest.mark.asyncio
async def test_async_client_init_handshake_failure_tolerated(mock_session: MagicMock) -> None:
    """Handshake network errors during init are caught and logged without aborting."""
    mock_session.get.side_effect = RuntimeError("Handshake failed")
    cli = await AsyncClient()
    assert cli.session is mock_session


@pytest.mark.asyncio
async def test_async_client_search_validation_errors(mock_session: MagicMock) -> None:
    """Input validation enforces valid modes, sources, and account prerequisites."""
    cli = await AsyncClient()

    with pytest.raises(ValidationError, match="Invalid mode"):
        await cli.search("test", mode="non_existent")

    with pytest.raises(ValidationError, match="requires an account"):
        await cli.search("test", mode="pro", model="sonar")

    with pytest.raises(ValidationError, match="No remaining enhanced queries"):
        await cli.search("test", mode="pro")

    with pytest.raises(ValidationError, match="Invalid source"):
        await cli.search("test", sources=["invalid_source"])


@pytest.mark.asyncio
async def test_async_client_search_query_limits_enforced(mock_session: MagicMock) -> None:
    """Query limits raise ValidationError when upload quota is exhausted."""
    cli = await AsyncClient()
    cli.file_upload = 0

    with pytest.raises(ValidationError, match="Insufficient file uploads"):
        await cli.search("test", files={"doc.txt": b"content"})


@pytest.mark.asyncio
async def test_async_client_search_copilot_decrement(mock_session: MagicMock) -> None:
    """Finite copilot quota decrements by one on pro search."""
    cli = await AsyncClient()
    cli.own = True
    cli.copilot = 5

    _, frames = make_sse_frames("OK")
    mock_session.post.return_value = make_async_response(frames)

    await cli.search("test", mode="pro")
    assert cli.copilot == 4


@pytest.mark.asyncio
async def test_async_client_search_success_blocks_format(mock_session: MagicMock) -> None:
    """Non-streaming search parses modern blocks response and sets top-level answer."""
    expected, frames = make_sse_frames("Deep learning answer")
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    result = await cli.search("What is deep learning?")

    assert isinstance(result, dict)
    assert result["answer"] == "Deep learning answer"
    assert result["blocks"] == expected["blocks"]


@pytest.mark.asyncio
async def test_async_client_strict_completion_and_provider_timeout(
    mock_session: MagicMock,
) -> None:
    partial = {"answer": "partial", "response_id": "diagnostic-only"}
    frames = [f"data: {json.dumps(partial)}".encode("utf-8")]
    mock_session.post.return_value = make_async_response(frames)
    observed = []
    cli = await AsyncClient()

    assert (await cli.search("test"))["answer"] == "partial"
    with pytest.raises(IncompleteResponseError, match="before terminal"):
        await cli.search(
            "test",
            require_complete=True,
            provider_timeout=321,
            event_callback=observed.append,
        )

    assert observed[-1]["response_id"] == "diagnostic-only"
    assert mock_session.post.call_args.kwargs["timeout"] == 321


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_timeout", [0, -1, float("nan"), float("inf"), True])
async def test_async_client_rejects_invalid_provider_timeout(
    mock_session: MagicMock, provider_timeout
) -> None:
    cli = await AsyncClient()
    with pytest.raises(ValueError, match="finite number greater than zero"):
        await cli.search("test", provider_timeout=provider_timeout)


@pytest.mark.asyncio
async def test_async_client_search_success_legacy_text_format(mock_session: MagicMock) -> None:
    """Non-streaming search parses legacy nested JSON string within text property."""
    expected, frames = make_legacy_sse_frames("Legacy answer text")
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    result = await cli.search("Legacy query")

    assert isinstance(result, dict)
    assert result["answer"] == "Legacy answer text"
    assert result["text"] == expected["text"]


@pytest.mark.asyncio
async def test_async_client_search_streaming_chunks(mock_session: MagicMock) -> None:
    """Streaming search yields parsed responses chunk by chunk until end_of_stream."""
    chunk1 = {"blocks": [{"intended_usage": "ask_text", "markdown_block": {"answer": "Part 1"}}]}
    chunk2 = {"blocks": [{"intended_usage": "ask_text", "markdown_block": {"answer": "Part 2"}}]}
    frames = [
        f"data: {json.dumps(chunk1)}\r\n\r\n".encode("utf-8"),
        f"data: {json.dumps(chunk2)}\r\n\r\n".encode("utf-8"),
        b"event: end_of_stream\r\ndata: {}",
    ]
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    stream = await cli.search("Stream query", stream=True)
    yielded = [item async for item in stream]

    assert len(yielded) == 2
    assert yielded[0]["answer"] == "Part 1"
    assert yielded[1]["answer"] == "Part 2"


@pytest.mark.asyncio
async def test_async_client_search_empty_response(mock_session: MagicMock) -> None:
    """Abrupt end_of_stream with no prior data returns empty dict."""
    frames = [b"event: end_of_stream\r\ndata: {}"]
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    result = await cli.search("Empty test")
    assert result == {}


@pytest.mark.asyncio
async def test_async_client_search_malformed_chunk_skipped(mock_session: MagicMock) -> None:
    """Corrupted JSON chunks in SSE stream are skipped without aborting stream."""
    valid_payload = {
        "blocks": [{"intended_usage": "ask_text", "markdown_block": {"answer": "Recovered"}}]
    }
    frames = [
        b"data: {invalid json content\r\n\r\n",
        f"data: {json.dumps(valid_payload)}\r\n\r\n".encode("utf-8"),
        b"event: end_of_stream\r\ndata: {}",
    ]
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    result = await cli.search("Malformed chunk test")
    assert result.get("answer") == "Recovered"


@pytest.mark.asyncio
async def test_async_client_search_follow_up_payload(mock_session: MagicMock) -> None:
    """Follow-up context passes previous backend uuid and merges attachments."""
    _, frames = make_sse_frames("Follow up response")
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    follow_up = {
        "backend_uuid": "prev-backend-uuid-42",
        "attachments": ["https://storage.example.com/file1.pdf"],
    }
    await cli.search("Next question", follow_up=follow_up)

    posted_json = mock_session.post.call_args.kwargs["json"]
    assert posted_json["params"]["last_backend_uuid"] == "prev-backend-uuid-42"
    assert "https://storage.example.com/file1.pdf" in posted_json["params"]["attachments"]


@pytest.mark.asyncio
async def test_async_client_search_passes_sse_headers(mock_session: MagicMock) -> None:
    """SSE_ASK_HEADERS are passed with search requests to match browser fetch."""
    _, frames = make_sse_frames("Header check")
    mock_session.post.return_value = make_async_response(frames)

    cli = await AsyncClient()
    await cli.search("Hello world")

    headers = mock_session.post.call_args.kwargs.get("headers")
    assert headers == SSE_ASK_HEADERS


@pytest.mark.asyncio
async def test_async_client_search_http_status_errors(mock_session: MagicMock) -> None:
    """HTTP error status codes map to specific typed Perplexity exceptions."""
    cli = await AsyncClient()

    # 429 RateLimitError
    mock_session.post.return_value = MagicMock(status_code=429)
    with pytest.raises(RateLimitError):
        await cli.search("test")

    # 401 AuthenticationError
    mock_session.post.return_value = MagicMock(status_code=401)
    with pytest.raises(AuthenticationError):
        await cli.search("test")

    # 403 AuthenticationError
    mock_session.post.return_value = MagicMock(status_code=403)
    with pytest.raises(AuthenticationError):
        await cli.search("test")

    # 500 NetworkError
    mock_session.post.return_value = MagicMock(status_code=500)
    with pytest.raises(NetworkError):
        await cli.search("test")


@pytest.mark.asyncio
async def test_async_client_file_upload_success(mock_session: MagicMock) -> None:
    """File upload flow posts to upload URL, uploads to S3, and includes in attachments."""
    cli = await AsyncClient()
    cli.file_upload = 5

    upload_info_resp = MagicMock(status_code=200, ok=True)
    upload_info_resp.json.return_value = {
        "fields": {"AWSAccessKeyId": "key123"},
        "s3_bucket_url": "https://s3.amazonaws.com/uploads",
        "s3_object_url": "https://s3.amazonaws.com/uploads/sample.txt",
    }
    s3_resp = MagicMock(status_code=200, ok=True)

    _, frames = make_sse_frames("Upload analyzed")
    sse_resp = make_async_response(frames)

    mock_session.post.side_effect = [upload_info_resp, s3_resp, sse_resp]

    result = await cli.search("Analyze document", files={"sample.txt": b"Sample file content"})

    assert result.get("answer") == "Upload analyzed"
    assert cli.file_upload == 4

    search_payload = mock_session.post.call_args_list[-1].kwargs["json"]
    assert "https://s3.amazonaws.com/uploads/sample.txt" in search_payload["params"]["attachments"]


@pytest.mark.asyncio
async def test_async_client_file_upload_url_failure(mock_session: MagicMock) -> None:
    """FileUploadError is raised when pre-signed upload URL request fails."""
    cli = await AsyncClient()
    cli.file_upload = 5

    fail_resp = MagicMock(status_code=500, ok=False)
    mock_session.post.return_value = fail_resp

    with pytest.raises(FileUploadError, match="Failed to get upload URL: 500"):
        await cli.search("Analyze document", files={"sample.txt": b"content"})


@pytest.mark.asyncio
async def test_async_client_file_upload_s3_failure(mock_session: MagicMock) -> None:
    """FileUploadError is raised when S3 multipart upload fails."""
    cli = await AsyncClient()
    cli.file_upload = 5

    upload_info_resp = MagicMock(status_code=200, ok=True)
    upload_info_resp.json.return_value = {
        "fields": {},
        "s3_bucket_url": "https://s3.amazonaws.com/uploads",
        "s3_object_url": "https://s3.amazonaws.com/uploads/sample.txt",
    }
    s3_fail_resp = MagicMock(status_code=403, ok=False)

    mock_session.post.side_effect = [upload_info_resp, s3_fail_resp]

    with pytest.raises(FileUploadError, match="File upload to storage failed: 403"):
        await cli.search("Analyze document", files={"sample.txt": b"content"})
