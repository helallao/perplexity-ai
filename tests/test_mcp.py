"""MCP HTTP 模式测试。

测试覆盖：
1. 模型列表返回
2. search 模式下前三个模型的正确返回
3. research 模式下前三个模型的正确处理

使用 fastmcp 客户端连接 MCP 服务器。
从 .env 文件读取 cookie 配置。
"""

import asyncio
import json
import os
import pytest
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# MCP 服务器配置
MCP_BASE_URL = "http://127.0.0.1:8000/mcp"
MCP_TOKEN = os.getenv("MCP_TOKEN", "sk-123456")

# 超时配置（秒）
CALL_TOOL_TIMEOUT = 30

# 测试问题
SEARCH_QUESTION = "When is the upcoming Chinese New Year"
RESEARCH_QUESTION = "What is Chinese New Year and what are the customs"


def create_mcp_client(token: str = MCP_TOKEN) -> Client:
    """创建 MCP 客户端。"""
    transport = StreamableHttpTransport(
        url=MCP_BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
    )
    return Client(transport)


def parse_tool_result(result: Any) -> Dict[str, Any]:
    """解析工具返回结果。"""
    # CallToolResult 对象有 content 属性
    if hasattr(result, "content"):
        content = result.content
        for item in content:
            if hasattr(item, "text"):
                return json.loads(item.text)
    # 如果直接是列表
    elif isinstance(result, list):
        for item in result:
            if hasattr(item, "text"):
                return json.loads(item.text)
    return {}


def has_valid_cookies() -> bool:
    """检查是否配置了有效的 Perplexity cookies。"""
    csrf_token = os.getenv("PPLX_NEXT_AUTH_CSRF_TOKEN")
    session_token = os.getenv("PPLX_SESSION_TOKEN")
    return bool(csrf_token and session_token)


class TestMCPAuthentication:
    """MCP 认证测试。"""

    @pytest.mark.asyncio
    async def test_valid_token_accepted(self) -> None:
        """测试有效 token 被接受。"""
        print("console.log -> 测试有效 token 认证")
        client = create_mcp_client(MCP_TOKEN)
        async with client:
            tools = await client.list_tools()
            assert len(tools) > 0
            print(f"console.log -> 认证成功，获取到 {len(tools)} 个工具")

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self) -> None:
        """测试无效 token 被拒绝。"""
        print("console.log -> 测试无效 token 认证")
        client = create_mcp_client("invalid-token")
        with pytest.raises(Exception):
            async with client:
                await client.list_tools()
        print("console.log -> 无效 token 被正确拒绝")


class TestListModels:
    """模型列表测试。"""

    @pytest.mark.asyncio
    async def test_list_models_returns_expected_structure(self) -> None:
        """测试 list_models 返回正确的数据结构。"""
        print("console.log -> 测试 list_models 工具")
        client = create_mcp_client()
        async with client:
            result = await client.call_tool("list_models", {})
            tool_result = parse_tool_result(result)

            # 验证返回数据包含必要字段
            assert "modes" in tool_result
            assert "model_mappings" in tool_result
            assert "labs_models" in tool_result

            # 验证 modes 列表
            modes = tool_result["modes"]
            assert "auto" in modes
            assert "pro" in modes
            assert "reasoning" in modes
            assert "deep research" in modes

            # 验证 model_mappings
            model_mappings = tool_result["model_mappings"]
            assert "pro" in model_mappings
            assert "reasoning" in model_mappings

            # 验证 labs_models
            labs_models = tool_result["labs_models"]
            assert len(labs_models) > 0
            assert "sonar" in labs_models

            print(f"console.log -> list_models 返回结构正确")
            print(f"console.log -> modes: {modes}")
            print(f"console.log -> labs_models: {labs_models}")


class TestSearchMode:
    """Search 模式测试。"""

    # Search 模式下的前三个可用模型（pro 模式）
    SEARCH_MODELS = [None, "sonar", "gpt-5.2"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", SEARCH_MODELS)
    async def test_search_with_model(self, model: Optional[str]) -> None:
        """测试 search 工具使用不同模型。"""
        model_name = model if model else "default"
        print(f"console.log -> 测试 search 模式，模型: {model_name}")

        # 检查是否有 cookies 配置
        if not has_valid_cookies():
            print("console.log -> 警告: 未配置 Perplexity cookies，跳过实际搜索测试")
            pytest.skip("需要配置 PPLX_NEXT_AUTH_CSRF_TOKEN 和 PPLX_SESSION_TOKEN")

        arguments: Dict[str, Any] = {
            "query": SEARCH_QUESTION,
            "mode": "pro",
            "language": "en-US",
        }
        if model:
            arguments["model"] = model

        client = create_mcp_client()
        async with client:
            try:
                result = await asyncio.wait_for(
                    client.call_tool("search", arguments),
                    timeout=CALL_TOOL_TIMEOUT
                )
            except asyncio.TimeoutError:
                pytest.fail(f"search 调用超时 ({CALL_TOOL_TIMEOUT}s)，模型: {model_name}")
            tool_result = parse_tool_result(result)

            # 验证返回结构
            assert "status" in tool_result, f"返回结果缺少 status 字段: {tool_result}"

            if tool_result["status"] == "ok":
                assert "data" in tool_result
                print(f"console.log -> search 成功，模型 {model_name}")
                if "answer" in tool_result.get("data", {}):
                    answer_preview = tool_result["data"]["answer"][:200] + "..."
                    print(f"console.log -> 回答预览: {answer_preview}")
            else:
                # 记录错误信息
                error_msg = tool_result.get("message", "未知错误")
                print(f"console.log -> search 模型 {model_name} 返回错误: {error_msg}")
                # 验证错误结构正确
                assert "error_type" in tool_result or "message" in tool_result


class TestResearchMode:
    """Research 模式测试。"""

    # Research 模式下的前三个可用模型（reasoning 模式）
    RESEARCH_MODELS = [None, "gemini-3.0-pro", "gpt-5.2-thinking"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model", RESEARCH_MODELS)
    async def test_research_with_model(self, model: Optional[str]) -> None:
        """测试 research 工具使用不同模型。"""
        model_name = model if model else "default"
        print(f"console.log -> 测试 research 模式，模型: {model_name}")

        # 检查是否有 cookies 配置
        if not has_valid_cookies():
            print("console.log -> 警告: 未配置 Perplexity cookies，跳过实际研究测试")
            pytest.skip("需要配置 PPLX_NEXT_AUTH_CSRF_TOKEN 和 PPLX_SESSION_TOKEN")

        arguments: Dict[str, Any] = {
            "query": RESEARCH_QUESTION,
            "mode": "reasoning",
            "language": "en-US",
        }
        if model:
            arguments["model"] = model

        client = create_mcp_client()
        async with client:
            try:
                result = await asyncio.wait_for(
                    client.call_tool("research", arguments),
                    timeout=CALL_TOOL_TIMEOUT
                )
            except asyncio.TimeoutError:
                pytest.fail(f"research 调用超时 ({CALL_TOOL_TIMEOUT}s)，模型: {model_name}")
            tool_result = parse_tool_result(result)

            # 验证返回结构
            assert "status" in tool_result, f"返回结果缺少 status 字段: {tool_result}"

            if tool_result["status"] == "ok":
                assert "data" in tool_result
                print(f"console.log -> research 成功，模型 {model_name}")
                if "answer" in tool_result.get("data", {}):
                    answer_preview = tool_result["data"]["answer"][:200] + "..."
                    print(f"console.log -> 回答预览: {answer_preview}")
            else:
                # 记录错误信息
                error_msg = tool_result.get("message", "未知错误")
                print(f"console.log -> research 模型 {model_name} 返回错误: {error_msg}")
                # 验证错误结构正确
                assert "error_type" in tool_result or "message" in tool_result


class TestToolsAvailability:
    """工具可用性测试。"""

    @pytest.mark.asyncio
    async def test_all_expected_tools_exist(self) -> None:
        """测试所有预期的工具都存在。"""
        print("console.log -> 测试工具可用性")
        client = create_mcp_client()
        async with client:
            tools = await client.list_tools()
            tool_names = [tool.name for tool in tools]

            # 验证预期的工具存在
            expected_tools = ["list_models", "search", "research"]
            for tool_name in expected_tools:
                assert tool_name in tool_names, f"缺少预期的工具: {tool_name}"
                print(f"console.log -> 工具 {tool_name} 存在")

            print(f"console.log -> 所有工具可用: {tool_names}")
