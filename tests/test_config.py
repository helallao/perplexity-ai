"""Smoke tests for perplexity.config with console-style output."""

from perplexity import config


def test_api_endpoints_structure() -> None:
    print("console.log -> validating API endpoints and versions")
    assert config.API_BASE_URL.startswith("https://")
    assert config.API_VERSION.count(".") >= 1
    assert config.ENDPOINT_SSE_ASK.startswith(config.API_BASE_URL)
    assert config.EMAILNATOR_BASE_URL in config.EMAILNATOR_GENERATE_ENDPOINT


def test_search_modes_and_models() -> None:
    print("console.log -> checking search modes and model mappings")
    assert set(config.SEARCH_MODES) >= {"auto", "pro", "reasoning"}
    pro_models = config.MODEL_MAPPINGS["pro"]
    assert None in pro_models
    assert "sonar" in pro_models
    assert "deep research" in config.MODEL_MAPPINGS
