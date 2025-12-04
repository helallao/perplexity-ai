"""
Custom exceptions for Perplexity AI library.

This module defines all custom exceptions used throughout the library
for better error handling and debugging.
"""


class PerplexityError(Exception):
    """Base exception for all Perplexity AI errors."""

    pass


class AuthenticationError(PerplexityError):
    """Raised when authentication fails."""

    pass


class RateLimitError(PerplexityError):
    """Raised when rate limit is exceeded."""

    pass


class NetworkError(PerplexityError):
    """Raised when network request fails."""

    pass


class InvalidModeError(PerplexityError):
    """Raised when an invalid search mode is provided."""

    pass


class InvalidModelError(PerplexityError):
    """Raised when an invalid model is provided for a mode."""

    pass


class InvalidSourceError(PerplexityError):
    """Raised when an invalid source is provided."""

    pass


class QueryLimitExceededError(PerplexityError):
    """Raised when query limit is exceeded."""

    pass


class FileUploadError(PerplexityError):
    """Raised when file upload fails."""

    pass


class EmailnatorError(PerplexityError):
    """Raised when Emailnator service fails."""

    pass


class AccountCreationError(PerplexityError):
    """Raised when account creation fails."""

    pass


class ParsingError(PerplexityError):
    """Raised when response parsing fails."""

    pass


class ValidationError(PerplexityError):
    """Raised when input validation fails."""

    pass
