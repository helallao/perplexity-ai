"""Utility tests with console-like output for user visibility."""

import json
import time

import pytest

from perplexity.exceptions import ValidationError
from perplexity.utils import (
    parse_nested_json_response,
    rate_limit,
    retry_with_backoff,
    sanitize_query,
    validate_file_data,
    validate_query_limits,
    validate_search_params,
)


def test_sanitize_query_trims_and_validates() -> None:
    print("console.log -> testing sanitize_query behavior")
    assert sanitize_query("  hello world  ") == "hello world"
    with pytest.raises(ValidationError):
        sanitize_query("")
    with pytest.raises(ValidationError, match="must be string"):
        sanitize_query(123)  # type: ignore
    with pytest.raises(ValidationError, match="too long"):
        sanitize_query("a" * 10001)


def test_validate_search_params_requires_own_account() -> None:
    print("console.log -> validating search params requirements")
    validate_search_params("auto", None, ["web"], own_account=False)
    with pytest.raises(ValidationError):
        validate_search_params("pro", "sonar", ["web"], own_account=False)


def test_validate_search_params_sources_type_and_values() -> None:
    print("console.log -> testing sources validation")
    with pytest.raises(ValidationError, match="must be a list or tuple"):
        validate_search_params("auto", None, "web", own_account=False)  # type: ignore

    with pytest.raises(ValidationError, match="Invalid sources"):
        validate_search_params("auto", None, ["invalid_source"], own_account=False)

    with pytest.raises(ValidationError, match="At least one source"):
        validate_search_params("auto", None, [], own_account=False)


def test_validate_search_params_invalid_mode() -> None:
    print("console.log -> testing invalid search mode")
    with pytest.raises(ValidationError, match="Invalid mode"):
        validate_search_params("invalid_mode", None, ["web"], own_account=False)


def test_validate_search_params_invalid_model() -> None:
    print("console.log -> testing invalid model for mode")
    with pytest.raises(ValidationError, match="Invalid model"):
        validate_search_params("pro", "non_existent_model", ["web"], own_account=True)


def test_validate_query_limits() -> None:
    print("console.log -> testing query and file limit validation")
    validate_query_limits(copilot_remaining=5, file_upload_remaining=10, mode="pro", files_count=2)
    validate_query_limits(copilot_remaining=0, file_upload_remaining=10, mode="auto", files_count=0)

    with pytest.raises(ValidationError, match="No remaining enhanced queries"):
        validate_query_limits(copilot_remaining=0, file_upload_remaining=10, mode="pro", files_count=0)

    with pytest.raises(ValidationError, match="Insufficient file uploads"):
        validate_query_limits(copilot_remaining=5, file_upload_remaining=1, mode="pro", files_count=2)


def test_validate_file_data() -> None:
    print("console.log -> testing file data validation")
    validate_file_data({"test.txt": b"content", "doc.md": "text"})

    with pytest.raises(ValidationError, match="must be a dictionary"):
        validate_file_data(["not", "a", "dict"])  # type: ignore

    with pytest.raises(ValidationError, match="Filename must be string"):
        validate_file_data({123: b"content"})  # type: ignore

    with pytest.raises(ValidationError, match="Filename cannot be empty"):
        validate_file_data({"   ": b"content"})

    with pytest.raises(ValidationError, match="File data must be bytes or string"):
        validate_file_data({"test.txt": 12345})  # type: ignore


def test_retry_with_backoff_eventually_succeeds(monkeypatch) -> None:
    print("console.log -> exercising retry_with_backoff decorator")
    sleep_calls = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    attempts = {"count": 0}

    @retry_with_backoff(max_attempts=3, backoff_factor=0.0)
    def flaky_call() -> str:
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise RuntimeError("temporary failure")
        return "ok"

    assert flaky_call() == "ok"
    assert attempts["count"] == 2
    assert len(sleep_calls) == 1


def test_retry_with_backoff_fails_after_max_attempts(monkeypatch) -> None:
    print("console.log -> testing retry_with_backoff failure limit")
    monkeypatch.setattr(time, "sleep", lambda x: None)

    @retry_with_backoff(max_attempts=2, backoff_factor=0.0)
    def always_fails():
        raise ValueError("persistent failure")

    with pytest.raises(ValueError, match="persistent failure"):
        always_fails()


def test_rate_limit(monkeypatch) -> None:
    print("console.log -> testing rate_limit decorator")
    sleep_calls = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    @rate_limit(min_delay=0.1, max_delay=0.2)
    def quick_call():
        return "done"

    quick_call()
    quick_call()
    assert len(sleep_calls) >= 1


def test_parse_nested_json_response() -> None:
    print("console.log -> testing parse_nested_json_response")
    # Case 1: non-dict input
    assert parse_nested_json_response(None) is None  # type: ignore

    # Case 2: standard nested JSON with FINAL step
    nested_text = json.dumps([
        {"step_type": "SEARCH", "content": {}},
        {"step_type": "FINAL", "content": {"answer": json.dumps({"answer": "42", "chunks": ["chunk1"]})}},
    ])
    resp = {"text": nested_text}
    parsed = parse_nested_json_response(resp)
    assert parsed["answer"] == "42"
    assert parsed["chunks"] == ["chunk1"]

    # Case 3: invalid json in text field
    invalid_resp = {"text": "not valid json"}
    parsed_inv = parse_nested_json_response(invalid_resp)
    assert parsed_inv["text"] == "not valid json"

