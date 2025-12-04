"""
Configuration constants for Perplexity AI API.

This module contains all configurable constants used throughout the library.
Modify these values to customize behavior without changing core code.
"""

from typing import Dict

# API Configuration
API_BASE_URL = "https://www.perplexity.ai"
API_VERSION = "2.18"
API_TIMEOUT = 30

# Endpoints
ENDPOINT_AUTH_SESSION = f"{API_BASE_URL}/api/auth/session"
ENDPOINT_AUTH_SIGNIN = f"{API_BASE_URL}/api/auth/signin/email"
ENDPOINT_SSE_ASK = f"{API_BASE_URL}/rest/sse/perplexity_ask"
ENDPOINT_UPLOAD_URL = f"{API_BASE_URL}/rest/uploads/create_upload_url"
ENDPOINT_SOCKET_IO = f"{API_BASE_URL}/socket.io/"

# Emailnator Configuration
EMAILNATOR_BASE_URL = "https://www.emailnator.com"
EMAILNATOR_GENERATE_ENDPOINT = f"{EMAILNATOR_BASE_URL}/generate-email"
EMAILNATOR_MESSAGE_LIST_ENDPOINT = f"{EMAILNATOR_BASE_URL}/message-list"

# Account Limits
DEFAULT_COPILOT_QUERIES = 5
DEFAULT_FILE_UPLOADS = 10
ACCOUNT_TIMEOUT = 20  # seconds to wait for email

# Search Modes
SEARCH_MODES = ["auto", "pro", "reasoning", "deep research"]
SEARCH_SOURCES = ["web", "scholar", "social"]
SEARCH_LANGUAGES = ["en-US", "en-GB", "pt-BR", "es-ES", "fr-FR", "de-DE"]

# Model Mappings
MODEL_MAPPINGS: Dict[str, Dict[str, str]] = {
    "auto": {None: "turbo"},
    "pro": {
        None: "pplx_pro",
        "sonar": "experimental",
        "gpt-4.5": "gpt45",
        "gpt-4o": "gpt4o",
        "claude 3.7 sonnet": "claude2",
        "gemini 2.0 flash": "gemini2flash",
        "grok-2": "grok",
    },
    "reasoning": {
        None: "pplx_reasoning",
        "r1": "r1",
        "o3-mini": "o3mini",
        "claude 3.7 sonnet": "claude37sonnetthinking",
        "gpt5": "gpt5",
        "gpt5_thinking": "gpt5thinking",
    },
    "deep research": {None: "pplx_alpha"},
}

# Labs Models
LABS_MODELS = [
    "r1-1776",
    "sonar-pro",
    "sonar",
    "sonar-reasoning-pro",
    "sonar-reasoning",
]

# HTTP Headers Template
DEFAULT_HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",  # noqa: E501
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "dnt": "1",
    "priority": "u=0, i",
    "sec-ch-ua": '"Not;A=Brand";v="24", "Chromium";v="128"',
    "sec-ch-ua-arch": '"x86"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version": '"128.0.6613.120"',
    "sec-ch-ua-full-version-list": '"Not;A=Brand";v="24.0.0.0", "Chromium";v="128.0.6613.120"',  # noqa: E501
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"19.0.0"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",  # noqa: E501
}

# Emailnator Headers Template
EMAILNATOR_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "content-type": "application/json",
    "dnt": "1",
    "origin": EMAILNATOR_BASE_URL,
    "priority": "u=1, i",
    "referer": f"{EMAILNATOR_BASE_URL}/",
    "sec-ch-ua": '"Not;A=Brand";v="24", "Chromium";v="128"',
    "sec-ch-ua-arch": '"x86"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version": '"128.0.6613.120"',
    "sec-ch-ua-full-version-list": '"Not;A=Brand";v="24.0.0.0", "Chromium";v="128.0.6613.120"',  # noqa: E501
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"19.0.0"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",  # noqa: E501
    "x-requested-with": "XMLHttpRequest",
}

# Retry Configuration
RETRY_MAX_ATTEMPTS = 3
RETRY_BACKOFF_FACTOR = 2
RETRY_EXCEPTIONS = (ConnectionError, TimeoutError)

# Logging Configuration
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"
LOG_FILE = "perplexity.log"

# Rate Limiting
RATE_LIMIT_MIN_DELAY = 1.0  # seconds
RATE_LIMIT_MAX_DELAY = 3.0  # seconds
RATE_LIMIT_ENABLED = True

# Validation Patterns
EMAIL_SUBJECT_PATTERN = "Sign in to Perplexity"
SIGNIN_URL_PATTERN = (
    r'"(https://www\.perplexity\.ai/api/auth/callback/email\?callbackUrl=.*?)"'
)
