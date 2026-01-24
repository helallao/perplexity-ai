from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SearchPayload(BaseModel):
    query: str
    mode: str = "auto"
    model: Optional[str] = None
    sources: List[str] = Field(default_factory=lambda: ["web"])
    language: str = "en-US"
    incognito: bool = False
    follow_up: Optional[Dict[str, Any]] = None
    cookies: Optional[Dict[str, Any]] = None
