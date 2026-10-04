"""Offline acceptance tests for the MCP-only durable research journal."""

import asyncio
import json
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from perplexity.exceptions import IncompleteResponseError
from perplexity.research_jobs import (
    ResearchCapacityError,
    ResearchConflictError,
    ResearchJobManager,
    ResearchJournalError,
    ResearchStoreInUseError,
    _acquire_store_lock,
    _release_store_lock,
)


@pytest.fixture(autouse=True)
def _skip_posix_journal_tests_on_windows(request: pytest.FixtureRequest) -> None:
    if (
        os.name == "nt"
        and request.node.name != "test_windows_journal_fails_closed_without_touching_store"
    ):
        pytest.skip("the private research journal is intentionally unavailable on Windows")


def completed(answer: str):
    def run(query, observe):
        observe({"backend_uuid": f"backend-{query}", "secret": "ignored"})
        return {"answer": answer}

    return run


@pytest.mark.asyncio
async def test_cancelled_mcp_waiter_does_not_cancel_research_and_result_persists(
    tmp_path: Path,
) -> None:
    release = threading.Event()
    calls = []

    def delayed(query, observe):
        calls.append(query)
        observe({"response_id": "observed-id"})
        assert release.wait(2)
        return {"answer": "exact final answer"}

    db = tmp_path / "private" / "jobs.sqlite3"
    manager = ResearchJobManager(str(db), delayed)
    started = manager.start("delayed research", idempotency_key="request-1")
    assert started["id"]
    assert started["delivery_state"] in {"queued", "running"}

    # FastMCP dispatches synchronous tools through worker threads. Cancelling that
    # request-side waiter must not cancel the manager-owned worker.
    wait_started = threading.Event()

    def wait_for_job():
        wait_started.set()
        return manager.wait(started["id"])

    waiter = asyncio.create_task(asyncio.to_thread(wait_for_job))
    while not wait_started.is_set():
        await asyncio.sleep(0)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter

    # Retrying a start after its MCP response disappeared must not resubmit it.
    retried = manager.start("delayed research", idempotency_key="request-1")
    assert retried["id"] == started["id"]
    with pytest.raises(ResearchConflictError):
        manager.start("different research", idempotency_key="request-1")

    release.set()
    finished = manager.wait(started["id"], timeout=2)
    assert finished["delivery_state"] == "completed"
    assert finished["provider_state"] == "unknown"
    assert finished["provider_ids"] == {"response_id": "observed-id"}
    assert finished["result"] == "exact final answer"
    assert calls == ["delayed research"]
    manager.close()

    reopened = ResearchJobManager(str(db), completed("must not run"))
    assert reopened.get(started["id"])["result"] == "exact final answer"
    assert oct(os.stat(db).st_mode & 0o777) == "0o600"
    assert oct(os.stat(db.parent).st_mode & 0o777) == "0o700"
    reopened.close()


def test_query_status_search_and_cursor_pagination(tmp_path: Path) -> None:
    manager = ResearchJobManager(str(tmp_path / "jobs.sqlite3"), completed("done"))
    ids = []
    for query in ["alpha one", "beta", "alpha two"]:
        job = manager.start(query)
        ids.append(job["id"])
        manager.wait(job["id"], timeout=2)

    first = manager.list(query="alpha", status="completed", limit=1)
    assert len(first["records"]) == 1
    assert first["next_cursor"]
    second = manager.list(query="alpha", status="completed", limit=1, cursor=first["next_cursor"])
    assert len(second["records"]) == 1
    assert second["records"][0]["id"] != first["records"][0]["id"]
    assert "result" not in first["records"][0]
    with pytest.raises(ValueError):
        manager.list(limit=101)
    with pytest.raises(ValueError):
        manager.list(cursor="not-a-cursor")
    manager.close()


@pytest.mark.parametrize(
    "failure, expected_state, expected_code",
    [
        (IncompleteResponseError("partial secret"), "interrupted", "incomplete_delivery"),
        (TimeoutError("cookie=secret"), "interrupted", "provider_timeout"),
        (ConnectionError("transport secret"), "interrupted", "provider_transport"),
        (RuntimeError("authorization: secret"), "failed", "provider_error"),
    ],
)
def test_transport_failure_never_succeeds_or_leaks_credentials(
    tmp_path: Path, failure: BaseException, expected_state: str, expected_code: str
) -> None:
    def fail(query, observe):
        raise failure

    manager = ResearchJobManager(str(tmp_path / f"{expected_code}.sqlite3"), fail)
    job = manager.start("research")
    result = manager.wait(job["id"], timeout=2)
    assert result["delivery_state"] == expected_state
    assert result["provider_state"] == "unknown"
    assert result["result"] is None
    assert result["error"]["code"] == expected_code
    assert "secret" not in result["error"]["message"]
    manager.close()


def test_bounded_capacity_and_shutdown_interrupt_without_reexecution(tmp_path: Path) -> None:
    release = threading.Event()
    calls = []

    def blocked(query, observe):
        calls.append(query)
        release.wait(2)
        return {"answer": query}

    db = tmp_path / "jobs.sqlite3"
    manager = ResearchJobManager(str(db), blocked, max_queue=1)
    first = manager.start("first")
    while manager.get(first["id"])["delivery_state"] == "queued":
        threading.Event().wait(0.01)
    second = manager.start("second")
    with pytest.raises(ResearchCapacityError):
        manager.start("third")

    manager.close(wait_timeout=0)
    release.set()
    reopened = ResearchJobManager(str(db), completed("must not rerun"))
    assert reopened.get(first["id"])["delivery_state"] == "interrupted"
    assert reopened.get(second["id"])["delivery_state"] == "interrupted"
    assert calls == ["first"]
    reopened.close()


def test_queue_rejection_does_not_create_false_idempotent_acceptance(tmp_path: Path) -> None:
    release = threading.Event()
    calls = []

    def blocked(query, observe):
        calls.append(query)
        release.wait(2)
        return {"answer": query}

    manager = ResearchJobManager(str(tmp_path / "jobs.sqlite3"), blocked, max_queue=1)
    first = manager.start("first")
    while manager.get(first["id"])["delivery_state"] == "queued":
        threading.Event().wait(0.01)
    second = manager.start("second")

    with pytest.raises(ResearchCapacityError):
        manager.start("retry later", idempotency_key="capacity-key")
    with pytest.raises(ResearchCapacityError):
        manager.start("retry later", idempotency_key="capacity-key")

    release.set()
    manager.wait(first["id"], timeout=2)
    manager.wait(second["id"], timeout=2)
    accepted = manager.start("retry later", idempotency_key="capacity-key")
    manager.wait(accepted["id"], timeout=2)
    assert calls == ["first", "second", "retry later"]
    manager.close()


def test_restart_marks_stale_active_and_store_has_single_owner(tmp_path: Path) -> None:
    db = tmp_path / "jobs.sqlite3"
    manager = ResearchJobManager(str(db), completed("done"))
    job = manager.start("record")
    manager.wait(job["id"], timeout=2)
    with pytest.raises(ResearchStoreInUseError):
        ResearchJobManager(str(db), completed("other"))
    manager.close()

    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE research_jobs SET delivery_state = 'running', result = NULL WHERE id = ?",
            (job["id"],),
        )
    calls = []

    def forbidden(query, observe):
        calls.append(query)
        return {"answer": "rerun"}

    reopened = ResearchJobManager(str(db), forbidden)
    recovered = reopened.get(job["id"])
    assert recovered["delivery_state"] == "interrupted"
    assert recovered["provider_state"] == "unknown"
    assert recovered["error"]["code"] == "server_restart"
    assert calls == []
    reopened.close()


def test_windows_lock_adapter_uses_nonblocking_one_byte_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from perplexity import research_jobs

    calls = []
    fake_msvcrt = SimpleNamespace(
        LK_NBLCK=2,
        LK_UNLCK=3,
        locking=lambda fd, mode, size: calls.append((fd, mode, size)),
    )
    monkeypatch.setattr(research_jobs, "_msvcrt", fake_msvcrt)
    monkeypatch.setattr(research_jobs, "_fcntl", None)

    path = tmp_path / "windows.lock"
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        _acquire_store_lock(fd)
        _release_store_lock(fd)
    finally:
        os.close(fd)

    assert calls == [(fd, fake_msvcrt.LK_NBLCK, 1), (fd, fake_msvcrt.LK_UNLCK, 1)]
    assert path.stat().st_size == 1


def test_windows_journal_fails_closed_without_touching_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from perplexity import research_jobs

    db = tmp_path / "private" / "jobs.sqlite3"
    monkeypatch.setattr(research_jobs, "JOURNAL_SUPPORTED", False)

    with pytest.raises(ResearchJournalError, match="unavailable on Windows"):
        ResearchJobManager(str(db), completed("must not run"))

    assert not db.parent.exists()


def test_existing_parent_permissions_are_not_changed_and_init_failure_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    operator_parent = tmp_path / "operator-managed"
    operator_parent.mkdir(mode=0o755)
    os.chmod(operator_parent, 0o755)
    db = operator_parent / "jobs.sqlite3"

    with monkeypatch.context() as scoped:
        scoped.setattr(
            ResearchJobManager,
            "_create_schema",
            lambda self: (_ for _ in ()).throw(RuntimeError("schema failure")),
        )
        with pytest.raises(RuntimeError, match="schema failure"):
            ResearchJobManager(str(db), completed("unused"))

    assert oct(operator_parent.stat().st_mode & 0o777) == "0o755"
    # A second manager can acquire the same path, proving the failed initializer
    # closed its SQLite connection and released/closed its file lock.
    manager = ResearchJobManager(str(db), completed("done"))
    manager.close()


def test_worker_start_failure_releases_store_for_immediate_reacquire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "jobs.sqlite3"

    with monkeypatch.context() as scoped:
        scoped.setattr(
            threading.Thread,
            "start",
            lambda self: (_ for _ in ()).throw(RuntimeError("thread start failed")),
        )
        with pytest.raises(RuntimeError, match="thread start failed"):
            ResearchJobManager(str(db), completed("unused"))

    manager = ResearchJobManager(str(db), completed("done"))
    manager.close()


def test_close_wakes_waiter_and_closed_reads_fail_explicitly(tmp_path: Path) -> None:
    release = threading.Event()

    def blocked(query, observe):
        release.wait(2)
        return {"answer": "late"}

    manager = ResearchJobManager(str(tmp_path / "jobs.sqlite3"), blocked)
    job = manager.start("closing")
    waiter_result = []

    def wait_for_close():
        try:
            manager.wait(job["id"])
        except Exception as exc:
            waiter_result.append(exc)

    waiter = threading.Thread(target=wait_for_close)
    waiter.start()
    manager.close(wait_timeout=0)
    waiter.join(timeout=1)
    assert not waiter.is_alive()
    assert len(waiter_result) == 1
    assert isinstance(waiter_result[0], ResearchJournalError)
    with pytest.raises(ResearchJournalError, match="closed"):
        manager.get(job["id"])
    with pytest.raises(ResearchJournalError, match="closed"):
        manager.list()
    release.set()


def test_mcp_tools_use_authenticated_server_manager_and_survive_lost_start_response(
    tmp_path: Path,
) -> None:
    from perplexity import mcp as mcp_module

    manager = ResearchJobManager(str(tmp_path / "jobs.sqlite3"), completed("tool result"))
    anonymous = MagicMock(own=False)
    with patch.object(mcp_module, "research_manager", None):
        with pytest.raises(PermissionError):
            mcp_module._get_research_manager(anonymous)

    with patch.object(mcp_module, "research_manager", manager):
        lost = mcp_module.perplexity_research_start("tool query", "tool-request")
        # Retrying after an MCP response was lost deduplicates rather than resubmits.
        retried = mcp_module.perplexity_research_start("tool query", "tool-request")
        assert retried["id"] == lost["id"]
        manager.wait(lost["id"], timeout=2)
        assert mcp_module.perplexity_research_get(lost["id"])["result"] == "tool result"
        assert mcp_module.perplexity_research_list(query="tool")["records"][0]["id"] == lost["id"]
    manager.close()


def test_lazy_manager_creation_is_singleton_under_concurrency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from perplexity import mcp as mcp_module

    monkeypatch.setenv("PERPLEXITY_RESEARCH_DB", str(tmp_path / "lazy.sqlite3"))
    cli = MagicMock(own=True)
    results = []
    failures = []
    start = threading.Barrier(8)

    def create():
        try:
            start.wait()
            results.append(mcp_module._get_research_manager(cli))
        except Exception as exc:
            failures.append(exc)

    with patch.object(mcp_module, "research_manager", None):
        threads = [threading.Thread(target=create) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        assert not failures
        assert len(results) == 8
        assert len({id(manager) for manager in results}) == 1
        results[0].close()
        mcp_module.research_manager = None


@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "0", "-1", "3601"])
def test_provider_timeout_configuration_is_finite_positive_and_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    from perplexity import mcp as mcp_module

    monkeypatch.setenv("PERPLEXITY_RESEARCH_DB", str(tmp_path / f"{value}.sqlite3"))
    monkeypatch.setenv("PERPLEXITY_RESEARCH_PROVIDER_TIMEOUT", value)
    with patch.object(mcp_module, "research_manager", None):
        with pytest.raises(ValueError, match="between 30 and 3600"):
            mcp_module._get_research_manager(MagicMock(own=True))


def test_invalid_queue_configuration_is_not_silently_coerced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from perplexity import mcp as mcp_module

    monkeypatch.setenv("PERPLEXITY_RESEARCH_DB", str(tmp_path / "queue.sqlite3"))
    monkeypatch.setenv("PERPLEXITY_RESEARCH_MAX_QUEUE", "1.5")
    with patch.object(mcp_module, "research_manager", None):
        with pytest.raises(ValueError, match="must be an integer"):
            mcp_module._get_research_manager(MagicMock(own=True))


def test_mcp_tool_registration_is_auth_gated() -> None:
    from perplexity import mcp as mcp_module

    class FakeServer:
        def __init__(self):
            self.names = []

        def tool(self, name=None):
            def register(function):
                self.names.append(name or function.__name__)
                return function

            return register

    anonymous = FakeServer()
    mcp_module._register_tools(anonymous, authenticated=False)
    assert anonymous.names == ["perplexity_ask"]

    authenticated = FakeServer()
    mcp_module._register_tools(authenticated, authenticated=True)
    assert authenticated.names == [
        "perplexity_ask",
        "perplexity_research",
        "perplexity_research_start",
        "perplexity_research_list",
        "perplexity_research_get",
        "perplexity_reason",
        "perplexity_search",
    ]

    authenticated_without_journal = FakeServer()
    mcp_module._register_tools(
        authenticated_without_journal,
        authenticated=True,
        journal_supported=False,
    )
    assert authenticated_without_journal.names == [
        "perplexity_ask",
        "perplexity_reason",
        "perplexity_search",
    ]


@pytest.mark.asyncio
async def test_answer_waiters_do_not_starve_list_or_get_on_small_executor(
    tmp_path: Path,
) -> None:
    from perplexity import mcp as mcp_module

    release = threading.Event()

    def blocked(query, observe):
        assert release.wait(3)
        return {"answer": query}

    manager = ResearchJobManager(str(tmp_path / "saturation.sqlite3"), blocked)
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=5))
    waiters = []

    try:
        with patch.object(mcp_module, "research_manager", manager):
            waiters = [
                asyncio.create_task(mcp_module._perplexity_research_mcp(f"query-{index}"))
                for index in range(5)
            ]
            for _ in range(100):
                if len(manager.list(limit=20)["records"]) == 5:
                    break
                await asyncio.sleep(0.01)
            assert len(manager.list(limit=20)["records"]) == 5

            page = await asyncio.wait_for(
                mcp_module._perplexity_research_list_mcp(limit=20),
                timeout=0.2,
            )
            record = await asyncio.wait_for(
                mcp_module._perplexity_research_get_mcp(page["records"][0]["id"]),
                timeout=0.2,
            )
            assert record["delivery_state"] in {"queued", "running"}
    finally:
        for waiter in waiters:
            waiter.cancel()
        await asyncio.gather(*waiters, return_exceptions=True)
        release.set()
        manager.close()


def _structured_result(result):
    structured = getattr(result, "structured_content", None)
    if structured is None:
        structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    return json.loads(result.content[0].text)


def _expected_mcp_server_shutdown(exc: BaseException) -> bool:
    nested = getattr(exc, "exceptions", None)
    if nested is not None:
        return bool(nested) and all(_expected_mcp_server_shutdown(item) for item in nested)
    return isinstance(exc, asyncio.CancelledError) or exc.__class__.__name__ in {
        "BrokenResourceError",
        "ClosedResourceError",
        "EndOfStream",
    }


@pytest.mark.asyncio
async def test_real_mcp_cancellation_keeps_job_and_list_get_remain_responsive(
    tmp_path: Path,
) -> None:
    """Exercise cancellation through a real MCP ClientSession and server loop."""
    import anyio
    from mcp import ClientSession
    from perplexity import mcp as mcp_module

    try:
        from mcp.server.mcpserver import MCPServer as Server

        lowlevel_attribute = "_lowlevel_server"
    except ImportError:
        from mcp.server.fastmcp import FastMCP as Server

        lowlevel_attribute = "_mcp_server"

    release = threading.Event()
    provider_started = threading.Event()
    calls = []

    def delayed(query, observe):
        calls.append(query)
        provider_started.set()
        assert release.wait(3)
        return {"answer": "MCP final answer"}

    manager = ResearchJobManager(str(tmp_path / "mcp.sqlite3"), delayed)
    server = Server("offline-research-test")
    mcp_module._register_tools(server, authenticated=True)
    lowlevel_server = getattr(server, lowlevel_attribute)

    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream(16)
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream(16)
    server_task = asyncio.create_task(
        lowlevel_server.run(
            client_to_server_receive,
            server_to_client_send,
            lowlevel_server.create_initialization_options(),
            raise_exceptions=True,
        )
    )

    try:
        with patch.object(mcp_module, "research_manager", manager):
            async with ClientSession(server_to_client_receive, client_to_server_send) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "perplexity_research" in {tool.name for tool in tools.tools}

                blocking_call = asyncio.create_task(
                    session.call_tool("perplexity_research", {"query": "MCP delayed"})
                )
                while not provider_started.is_set():
                    await asyncio.sleep(0)

                # The long answer-only waiter must not block other MCP calls.
                page_result = await asyncio.wait_for(
                    session.call_tool("perplexity_research_list", {"limit": 20}),
                    timeout=1,
                )
                page = _structured_result(page_result)
                research_id = page["records"][0]["id"]
                running_result = await asyncio.wait_for(
                    session.call_tool("perplexity_research_get", {"research_id": research_id}),
                    timeout=1,
                )
                assert _structured_result(running_result)["delivery_state"] == "running"

                blocking_call.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await blocking_call

                release.set()
                for _ in range(100):
                    completed_result = await session.call_tool(
                        "perplexity_research_get", {"research_id": research_id}
                    )
                    completed_payload = _structured_result(completed_result)
                    if completed_payload["delivery_state"] == "completed":
                        break
                    await asyncio.sleep(0.01)
                assert completed_payload["result"] == "MCP final answer"
                assert calls == ["MCP delayed"]
    finally:
        release.set()
        manager.close()
        if not server_task.done():
            server_task.cancel()
        try:
            await server_task
        except BaseException as exc:
            if not _expected_mcp_server_shutdown(exc):
                raise
        await client_to_server_send.aclose()
        await client_to_server_receive.aclose()
        await server_to_client_send.aclose()
        await server_to_client_receive.aclose()
