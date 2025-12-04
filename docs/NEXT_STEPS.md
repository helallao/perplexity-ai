    Search with Perplexity AI.
    
    Args:
        query: Search query text
        mode: Search mode ('auto', 'pro', 'reasoning', 'deep research')
        model: Specific model to use (depends on mode)
        sources: List of sources (['web', 'scholar', 'social'])
        files: Files to upload {filename: content}
        stream: Enable streaming responses
        language: ISO 639 language code
        follow_up: Previous query for context
        incognito: Enable incognito mode
        
    Returns:
        Response dictionary with 'answer' key, or generator if stream=True
        
    Raises:
        # Next Steps Guide

        This guide outlines the steps remaining to refactor the legacy modules so they align with the new infrastructure (configuration, logging, exceptions, and utilities).

        ## Objectives

        1. Integrate the new infrastructure modules (`config`, `logger`, `exceptions`, `utils`).
    # Next Steps Guide

    This guide captures the remaining refactor work required to bring the legacy clients (sync and async) in line with the new infrastructure modules (`config`, `logger`, `exceptions`, and `utils`).

    ## Objectives

    1. Reuse the shared infrastructure everywhere (no hardcoded constants or print statements).
    2. Add complete type hints and Google-style docstrings to every public function.
    3. Replace generic `Exception` handling with the typed hierarchy from `perplexity.exceptions`.
    4. Provide deterministic cleanup via context managers for clients that own network resources.
    5. Extend automated tests to cover client behaviors once the refactor is complete.

    ## Phase 1 – Synchronous Client

    ### 1.1 Update `perplexity/client.py`

    - Import configuration, logger, utilities, and exceptions instead of duplicating values.
    - Replace every literal endpoint, header, or limit with entries from `config.py`.
    - Wrap outbound calls with `@retry_with_backoff` and `@rate_limit`.
    - Validate queries, sources, and file uploads using `validate_search_params`, `validate_query_limits`, and `validate_file_data`.
    - Raise typed errors such as `ValidationError`, `AuthenticationError`, `RateLimitError`, `ResponseParseError`, and `NetworkError`.
    - Add full type hints to the class and methods (including streaming generators).
    - Write docstrings that describe arguments, return values, and raised exceptions.
    - Emit structured logs via `logger.info()`/`logger.error()` instead of `print()`.

    ### 1.2 Update `perplexity/emailnator.py`

    - Load URL templates, timeouts, and retry values from `config.py`.
    - Replace console output with structured logging.
    - Validate cookie/token input and raise the appropriate exception (`AuthenticationError`, `ValidationError`, or `SessionExpiredError`).
    - Add docstrings and type hints for public helpers (e.g., account creation, cookie refresh).

    ### 1.3 Update `perplexity/driver.py`

    - Centralize browser paths, user agents, and wait times in `config.py`.
    - Create a dedicated exception (e.g., `DriverError`) for automation failures.
    - Ensure the driver shuts down cleanly by implementing context manager support.
    - Log navigation steps, screenshot captures, and failures.

    ### 1.4 Update `perplexity/labs.py`

    - Apply the same improvements to the Labs/WebSocket client.
    - Guarantee cleanup of WebSocket sessions by using context managers or explicit `close()` calls.
    - Translate low-level errors into the custom exception hierarchy.

    ## Phase 2 – Async Client

    - Mirror every change from Phase 1 in `perplexity_async/client.py`, `perplexity_async/emailnator.py`, and `perplexity_async/labs.py`.
    - Provide async-safe retry and rate-limit decorators (accepting async callables).
    - Use `async with aiohttp.ClientSession()` and ensure sessions are closed predictably.
    - Add tests with `pytest-asyncio` covering success paths, streaming, and error translation.

    ## Phase 3 – Integration Tests

    - Extend `tests/` with mocked HTTP sessions for sync and async clients.
    - Cover: successful searches, validation errors, streaming chunk parsing, rate-limit handling, and retry logic.
    - Example skeleton:

    ```python
    @patch("perplexity.client.requests.Session")
    def test_search_basic(mock_session):
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "text": '{"steps":[{"FINAL":{"answer":"{\"answer\":\"Test\"}"}}]}'
        }
        mock_session.return_value.post.return_value = mock_resp

        client = Client()
        result = client.search("test query")

        assert result["answer"] == "Test"
    ```

    ## Phase 4 – Context Managers

    - Implement `__enter__`/`__exit__` for sync clients and `__aenter__`/`__aexit__` for async clients.
    - Ensure HTTP sessions, browser drivers, and WebSocket connections close even if errors occur.

    ## Phase 5 – Documentation and Examples

    - Update README usage examples after the refactor.
    - Add docstrings to every public symbol and run `pydocstyle`.
    - Expand the `examples/` directory if new workflows are introduced (e.g., context manager usage).

    ## Supporting Tooling

    - `mypy perplexity/ perplexity_async/ --strict`
    - `pytest tests/ --cov=perplexity --cov-report=term-missing`
    - `black`, `isort`, `flake8`, `pylint`, and `bandit`
    - `pydocstyle` for docstring validation
    - `sphinx-build -b html docs/ docs/_build/` when publishing reference docs

    ## Refactor Checklist

    - [ ] Replace literals with configuration references
    - [ ] Remove all `print()` statements (use the logger)
    - [ ] Apply retry and rate-limit decorators everywhere requests are made
    - [ ] Enforce validation helpers before network calls
    - [ ] Raise custom exceptions instead of generic ones
    - [ ] Provide complete type hints and docstrings
    - [ ] Implement context managers for clients that own resources
    - [ ] Add sync and async integration tests
    - [ ] Update README, CHANGELOG, and examples after the refactor

    ## Prioritization

    1. **High priority** – Refactor `perplexity/client.py`, share infrastructure across async modules, update documentation.
    2. **Medium priority** – Integration tests, async-specific helpers, response caching.
    3. **Low priority** – CLI tooling, Sphinx site, performance profiling.

    ## Working Tips

    1. Refactor one module at a time and keep commits focused.
    2. Run the pytest suite and `verify_implementation.py` after each major change.
    3. Update the changelog as soon as a refactor slice lands.
    4. Use pull requests for review even if you are the sole maintainer to keep a documented history.

    ---

    **Last updated**: January 2025
