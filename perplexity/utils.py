"""
Utility functions for Perplexity AI library.

This module provides helper functions for retry logic, validation,
and other common operations.
"""

import random
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

from .config import (
    MODEL_MAPPINGS,
    RATE_LIMIT_MAX_DELAY,
    RATE_LIMIT_MIN_DELAY,
    RETRY_BACKOFF_FACTOR,
    RETRY_MAX_ATTEMPTS,
    SEARCH_MODES,
    SEARCH_SOURCES,
)
from .exceptions import ValidationError
from .logger import get_logger

logger = get_logger("utils")


def retry_with_backoff(
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    backoff_factor: float = RETRY_BACKOFF_FACTOR,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable:
    """
    Decorator that retries a function with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for wait time between retries
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback function called on each retry

    Returns:
        Decorated function with retry logic

    Example:
        >>> @retry_with_backoff(max_attempts=3)
        ... def fetch_data():
        ...     return api.get("/data")
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts: {e}")
                        raise

                    wait_time = backoff_factor**attempt + random.uniform(0, 1)
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {wait_time:.2f}s..."
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(wait_time)

            raise Exception(f"Failed after {max_attempts} attempts")

        return wrapper

    return decorator


def rate_limit(
    min_delay: float = RATE_LIMIT_MIN_DELAY,
    max_delay: float = RATE_LIMIT_MAX_DELAY,
) -> Callable:
    """
    Decorator that rate limits function calls with random delay.

    Args:
        min_delay: Minimum delay in seconds
        max_delay: Maximum delay in seconds

    Returns:
        Decorated function with rate limiting

    Example:
        >>> @rate_limit(min_delay=1.0, max_delay=3.0)
        ... def make_request():
        ...     return api.get("/endpoint")
    """

    def decorator(func: Callable) -> Callable:
        last_call = [0.0]  # Mutable container to store across calls

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = random.uniform(min_delay, max_delay)
            elapsed = time.time() - last_call[0]

            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"Rate limiting: waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)

            last_call[0] = time.time()
            return func(*args, **kwargs)

        return wrapper

    return decorator


def validate_search_params(
    mode: str, model: Optional[str], sources: list, own_account: bool = False
) -> None:
    """
    Validate search parameters.

    Args:
        mode: Search mode
        model: Model name (optional)
        sources: List of sources
        own_account: Whether using own account

    Raises:
        ValidationError: If parameters are invalid

    Example:
        >>> validate_search_params("pro", "gpt-4.5", ["web"], True)
    """
    # Validate mode
    if mode not in SEARCH_MODES:
        raise ValidationError(f"Invalid mode '{mode}'. Must be one of: {', '.join(SEARCH_MODES)}")

    # Validate model
    if model is not None:
        valid_models = list(MODEL_MAPPINGS.get(mode, {}).keys())
        if model not in valid_models:
            raise ValidationError(
                f"Invalid model '{model}' for mode '{mode}'. "
                f"Valid models: {', '.join(str(m) for m in valid_models)}"
            )

    # Check if model requires own account
    if model is not None and not own_account:
        raise ValidationError(
            "Model selection requires an account with cookies. "
            "Initialize Client with cookies parameter."
        )

    # Validate sources
    invalid_sources = [s for s in sources if s not in SEARCH_SOURCES]
    if invalid_sources:
        raise ValidationError(
            f"Invalid sources: {', '.join(invalid_sources)}. "
            f"Valid sources: {', '.join(SEARCH_SOURCES)}"
        )

    if not sources:
        raise ValidationError("At least one source must be specified")


def validate_query_limits(
    copilot_remaining: int,
    file_upload_remaining: int,
    mode: str,
    files_count: int,
) -> None:
    """
    Validate query and file upload limits.

    Args:
        copilot_remaining: Remaining copilot queries
        file_upload_remaining: Remaining file uploads
        mode: Search mode
        files_count: Number of files to upload

    Raises:
        ValidationError: If limits are exceeded

    Example:
        >>> validate_query_limits(5, 10, "pro", 2)
    """
    # Check copilot queries
    if mode in ["pro", "reasoning", "deep research"] and copilot_remaining <= 0:
        raise ValidationError(
            f"No remaining enhanced queries for mode '{mode}'. "
            f"Create a new account or use mode='auto'."
        )

    # Check file uploads
    if files_count > 0 and file_upload_remaining < files_count:
        raise ValidationError(
            f"Insufficient file uploads. Requested: {files_count}, "
            f"Available: {file_upload_remaining}"
        )


def validate_file_data(files: dict) -> None:
    """
    Validate file data dictionary.

    Args:
        files: Dictionary with filenames as keys and file data as values

    Raises:
        ValidationError: If file data is invalid

    Example:
        >>> validate_file_data({"doc.pdf": b"..."})
    """
    if not isinstance(files, dict):
        raise ValidationError("Files must be a dictionary")

    for filename, data in files.items():
        if not isinstance(filename, str):
            raise ValidationError(f"Filename must be string, got {type(filename)}")

        if not filename.strip():
            raise ValidationError("Filename cannot be empty")

        if not isinstance(data, (bytes, str)):
            raise ValidationError(f"File data must be bytes or string, got {type(data)}")


def sanitize_query(query: str) -> str:
    """
    Sanitize and validate query string.

    Args:
        query: Query string

    Returns:
        Sanitized query string

    Raises:
        ValidationError: If query is invalid

    Example:
        >>> sanitize_query("  What is AI?  ")
        'What is AI?'
    """
    if not isinstance(query, str):
        raise ValidationError(f"Query must be string, got {type(query)}")

    query = query.strip()

    if not query:
        raise ValidationError("Query cannot be empty")

    if len(query) > 10000:
        raise ValidationError("Query is too long (max 10000 characters)")

    return query


def parse_nested_json_response(content_json: dict) -> dict:
    """
    Parse nested JSON response from Perplexity API.

    Extracts answer and chunks from the nested 'text' field structure:
    text (JSON string) -> list of steps -> FINAL step -> answer (JSON string)

    Args:
        content_json: Response JSON from API

    Returns:
        Enriched response with extracted answer and chunks

    Example:
        >>> response = parse_nested_json_response(api_response)
        >>> print(response['answer'])
    """
    import json

    if "text" in content_json and content_json["text"]:
        try:
            text_parsed = json.loads(content_json["text"])

            if isinstance(text_parsed, list):
                for step in text_parsed:
                    if step.get("step_type") == "FINAL":
                        final_content = step.get("content", {})

                        if "answer" in final_content:
                            try:
                                answer_data = json.loads(final_content["answer"])
                                content_json["answer"] = answer_data.get("answer", "")
                                content_json["chunks"] = answer_data.get("chunks", [])
                            except (json.JSONDecodeError, TypeError):
                                pass
                        break

            content_json["text"] = text_parsed
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

    return content_json
