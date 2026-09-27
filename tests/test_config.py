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


def test_enterprise_pro_models_available() -> None:
    print("console.log -> checking enterprise/pro account model availability")
    pro_models = config.MODEL_MAPPINGS["pro"]
    # Enterprise pro accounts should be able to use gpt5 (non-reasoning GPT-5)
    assert "gpt5" in pro_models, "'gpt5' must be a valid model for pro mode (issue #68)"

    reasoning_models = config.MODEL_MAPPINGS["reasoning"]
    # o3 is a valid reasoning model separate from o3-mini
    assert "o3" in reasoning_models, "'o3' must be a valid model for reasoning mode"
    assert "o3-mini" in reasoning_models

    # grok-4.1 uses a dot, not a hyphen (README fix)
    assert "grok-4.1" in pro_models
    assert "grok-4-1" not in pro_models
