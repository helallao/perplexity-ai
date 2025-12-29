"""
fastmcp-based MCP server exposing Perplexity search and model listing tools.
Provides both stdio (console) and HTTP transports.
"""

import argparse
import os
from typing import Any, Dict, Iterable, List, Optional, Union

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.dependencies import get_http_headers

from .client import Client
from .config import LABS_MODELS, MODEL_MAPPINGS, SEARCH_LANGUAGES, SEARCH_MODES, SEARCH_SOURCES
from .exceptions import ValidationError
from .utils import sanitize_query, validate_file_data, validate_query_limits, validate_search_params

# API 密钥配置（从环境变量读取，默认为 sk-123456）
MCP_TOKEN = os.getenv("MCP_TOKEN", "sk-123456")


class AuthMiddleware(Middleware):
    """Bearer Token 认证中间件"""
    
    def __init__(self, token: str):
        self.token = token
    
    async def on_request(self, context: MiddlewareContext, call_next):
        """验证请求的 Authorization header"""
        headers = get_http_headers()
        if headers:  # HTTP 模式下才有 headers
            auth = headers.get("authorization") or headers.get("Authorization")
            if auth != f"Bearer {self.token}":
                raise PermissionError("Unauthorized: Invalid or missing Bearer token")
        return await call_next(context)


mcp = FastMCP("perplexity-mcp")

# 添加认证中间件
mcp.add_middleware(AuthMiddleware(MCP_TOKEN))
_client: Optional[Client] = None


def _get_client() -> Client:
    """Create a singleton Client instance."""
    global _client
    if _client is None:
        csrf_token = os.getenv("PPLX_NEXT_AUTH_CSRF_TOKEN")
        session_token = os.getenv("PPLX_SESSION_TOKEN")
        cookies = (
            {
                "next-auth.csrf-token": csrf_token,
                "__Secure-next-auth.session-token": session_token,
            }
            if csrf_token and session_token
            else {}
        )
        _client = Client(cookies)
    return _client


def _normalize_files(files: Optional[Union[Dict[str, Any], Iterable[str]]]) -> Dict[str, Any]:
    """
    Accept either a dict of filename->data or an iterable of file paths,
    and normalize to the dict format expected by Client.search.
    """
    if not files:
        return {}

    if isinstance(files, dict):
        normalized = files
    else:
        normalized = {}
        for path in files:
            filename = os.path.basename(path)
            with open(path, "rb") as fh:
                normalized[filename] = fh.read()

    validate_file_data(normalized)
    return normalized


def list_models_tool() -> Dict[str, Any]:
    """Return supported modes, model mappings, and Labs models."""
    return {
        "modes": SEARCH_MODES,
        "model_mappings": MODEL_MAPPINGS,
        "labs_models": LABS_MODELS,
    }


def _extract_clean_result(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract only the final answer from the search response."""
    result = {}
    
    # 只提取最终答案
    if "answer" in response:
        result["answer"] = response["answer"]
    
    return result


def _run_query(
    query: str,
    mode: str,
    model: Optional[str] = None,
    sources: Optional[List[str]] = None,
    language: str = "en-US",
    incognito: bool = False,
    files: Optional[Union[Dict[str, Any], Iterable[str]]] = None,
) -> Dict[str, Any]:
    """Execute a Perplexity query (non-streaming) and return the final response."""
    client = _get_client()
    try:
        clean_query = sanitize_query(query)
        chosen_sources = sources or ["web"]

        if language not in SEARCH_LANGUAGES:
            raise ValidationError(
                f"Invalid language '{language}'. Choose from: {', '.join(SEARCH_LANGUAGES)}"
            )

        validate_search_params(mode, model, chosen_sources, own_account=client.own)
        normalized_files = _normalize_files(files)
        validate_query_limits(client.copilot, client.file_upload, mode, len(normalized_files))

        response = client.search(
            clean_query,
            mode=mode,
            model=model,
            sources=chosen_sources,
            files=normalized_files,
            stream=False,
            language=language,
            incognito=incognito,
        )
        
        # 只返回精简的最终结果
        clean_result = _extract_clean_result(response)
        return {"status": "ok", "data": clean_result}
    except Exception as exc:  # fastmcp will surface this to the client
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "message": str(exc),
        }


@mcp.tool
def list_models() -> Dict[str, Any]:
    """
    获取 Perplexity 支持的所有搜索模式和模型列表
    
    当你需要了解可用的模型选项时调用此工具。
    
    Returns:
        包含 modes (搜索模式)、model_mappings (模型映射) 和 labs_models (实验模型) 的字典
    """
    return list_models_tool()


@mcp.tool
def search(
    query: str,
    mode: str = "pro",
    model: Optional[str] = None,
    sources: Optional[List[str]] = None,
    language: str = "en-US",
    incognito: bool = False,
    files: Optional[Union[Dict[str, Any], Iterable[str]]] = None,
) -> Dict[str, Any]:
    """
    Perplexity 快速搜索 - 用于获取实时网络信息和简单问题解答

    ⚡ 特点: 速度快，适合需要实时信息的简单查询

    Args:
        query: 搜索问题 (清晰、具体的问题效果更好)
        mode: 搜索模式
            - 'auto': 快速模式，使用 turbo 模型，不消耗额度
            - 'pro': 专业模式，更准确的结果 (默认)
        model: 指定模型 (仅 pro 模式生效)
            - None: 使用默认模型 (推荐)
            - 'sonar': Perplexity 自研模型
            - 'gpt-5.2': OpenAI 最新模型
            - 'claude-4.5-sonnet': Anthropic Claude
            - 'grok-4.1': xAI Grok
        sources: 搜索来源列表
            - 'web': 网页搜索 (默认)
            - 'scholar': 学术论文
            - 'social': 社交媒体
        language: 响应语言代码 (默认 'en-US'，中文用 'zh-CN')
        incognito: 隐身模式，不保存搜索历史
        files: 上传文件 (用于分析文档内容)

    Returns:
        {"status": "ok", "data": {"answer": "搜索结果..."}}
        或 {"status": "error", "error_type": "...", "message": "..."}
    """
    # 限制 search 只能使用 auto 或 pro 模式
    if mode not in ["auto", "pro"]:
        mode = "pro"
    return _run_query(query, mode, model, sources, language, incognito, files)


@mcp.tool
def research(
    query: str,
    mode: str = "reasoning",
    model: Optional[str] = "gemini-3.0-pro",
    sources: Optional[List[str]] = None,
    language: str = "en-US",
    incognito: bool = False,
    files: Optional[Union[Dict[str, Any], Iterable[str]]] = None,
) -> Dict[str, Any]:
    """
    Perplexity 深度研究 - 用于复杂问题分析和深度调研

    🧠 特点: 使用推理模型，会进行多步思考，结果更全面准确，但耗时较长

    Args:
        query: 研究问题 (问题越具体，研究结果越有针对性)
        mode: 研究模式
            - 'reasoning': 推理模式，多步思考分析 (默认)
            - 'deep research': 深度研究，最全面但最耗时
        model: 指定推理模型 (仅 reasoning 模式生效)
            - 'gemini-3.0-pro': Google Gemini Pro (默认，推荐)
            - 'gpt-5.2-thinking': OpenAI 思考模型
            - 'claude-4.5-sonnet-thinking': Claude 推理模型
            - 'kimi-k2-thinking': Moonshot Kimi
            - 'grok-4.1-reasoning': xAI Grok 推理
        sources: 搜索来源列表
            - 'web': 网页搜索 (默认)
            - 'scholar': 学术论文 (学术研究推荐)
            - 'social': 社交媒体
        language: 响应语言代码 (默认 'en-US'，中文用 'zh-CN')
        incognito: 隐身模式，不保存搜索历史
        files: 上传文件 (用于分析文档内容)

    Returns:
        {"status": "ok", "data": {"answer": "研究结果..."}}
        或 {"status": "error", "error_type": "...", "message": "..."}
    """
    # 限制 research 只能使用 reasoning 或 deep research 模式
    if mode not in ["reasoning", "deep research"]:
        mode = "reasoning"
    return _run_query(query, mode, model, sources, language, incognito, files)


def run_server(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8000,
) -> None:
    """Start the MCP server with the requested transport."""
    if transport == "http":
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Perplexity MCP server (fastmcp).")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport to use for MCP server.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host (when transport=http).")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (when transport=http).")
    args = parser.parse_args()
    run_server(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

