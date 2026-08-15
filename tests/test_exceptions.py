"""Tests for custom exceptions."""

from perplexity.exceptions import (
    AccountCreationError,
    AuthenticationError,
    EmailnatorError,
    FileUploadError,
    InvalidModeError,
    InvalidModelError,
    InvalidSourceError,
    NetworkError,
    ParsingError,
    PerplexityError,
    QueryLimitExceededError,
    RateLimitError,
    ValidationError,
)


def test_exception_hierarchy() -> None:
    exceptions = [
        AccountCreationError,
        AuthenticationError,
        EmailnatorError,
        FileUploadError,
        InvalidModeError,
        InvalidModelError,
        InvalidSourceError,
        NetworkError,
        ParsingError,
        QueryLimitExceededError,
        RateLimitError,
        ValidationError,
    ]

    for exc in exceptions:
        assert issubclass(exc, PerplexityError)
        instance = exc("test message")
        assert str(instance) == "test message"
