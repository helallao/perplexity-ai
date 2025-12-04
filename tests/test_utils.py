"""Utility tests with console-like output for user visibility."""

import time

import pytest

from perplexity.exceptions import ValidationError
from perplexity.utils import (
    retry_with_backoff,
    sanitize_query,
    validate_search_params,
)


def test_sanitize_query_trims_and_validates() -> None:
    print("console.log -> testing sanitize_query behavior")
    assert sanitize_query("  hello world  ") == "hello world"
    with pytest.raises(ValidationError):
        sanitize_query("")


def test_validate_search_params_requires_own_account() -> None:
    print("console.log -> validating search params requirements")
    validate_search_params("auto", None, ["web"], own_account=False)
    with pytest.raises(ValidationError):
        validate_search_params("pro", "sonar", ["web"], own_account=False)


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
