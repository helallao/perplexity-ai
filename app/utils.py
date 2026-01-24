import json
import os


def parse_cookies(raw_cookies):
    env_raw = os.getenv("PPLX_COOKIES_JSON")
    if raw_cookies is None:
        raw_cookies = env_raw
    if raw_cookies is None:
        return {}
    if isinstance(raw_cookies, dict):
        return raw_cookies
    return json.loads(raw_cookies)
