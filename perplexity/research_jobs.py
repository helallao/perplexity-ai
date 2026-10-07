"""Durable, bounded local journal for MCP-launched deep research.

The journal records work performed by this server. It deliberately does not model
Perplexity account history or claim that observed provider identifiers are recovery
handles.
"""

import base64
import binascii
from collections import deque
import hashlib
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from curl_cffi.requests.exceptions import RequestException

from .exceptions import AuthenticationError, IncompleteResponseError, RateLimitError
from .utils import has_usable_final_response

DELIVERY_STATES = {"queued", "running", "completed", "failed", "interrupted"}
ACTIVE_STATES = {"queued", "running"}
_IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_PROVIDER_ID_FIELDS = {
    "backend_uuid",
    "frontend_context_uuid",
    "frontend_uuid",
    "response_id",
    "thread_url_slug",
}

JOURNAL_SUPPORTED = os.name != "nt"
JOURNAL_SUPPORT_MESSAGE = (
    "the private research journal is unavailable on Windows because owner-only "
    "file ACLs cannot be established with the Python standard library"
)

_msvcrt: Any = None
_fcntl: Any = None
if os.name == "nt":  # pragma: no cover - selected on Windows CI
    import msvcrt as windows_locking

    _msvcrt = windows_locking
else:  # pragma: no cover - platform selection itself is trivial
    import fcntl as posix_locking

    _fcntl = posix_locking


class ResearchJournalError(RuntimeError):
    """Base exception for local research journal operations."""


class ResearchCapacityError(ResearchJournalError):
    """Raised when the bounded active-job capacity is full."""


class ResearchConflictError(ResearchJournalError):
    """Raised when an idempotency key is reused for a different request."""


class ResearchNotFoundError(ResearchJournalError):
    """Raised when a local research ID is not present in this journal."""


class ResearchStoreInUseError(ResearchJournalError):
    """Raised when another manager already owns the same local store."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_query(query: str) -> str:
    if not isinstance(query, str):
        raise ValueError("query must be a string")
    normalized = query.strip()
    if not normalized:
        raise ValueError("query cannot be empty")
    if len(normalized) > 10000:
        raise ValueError("query is too long (max 10000 characters)")
    return normalized


def _validate_research_id(research_id: str) -> str:
    try:
        return str(UUID(research_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("research_id must be a UUID") from exc


def _encode_cursor(created_at: str, research_id: str) -> str:
    raw = json.dumps([created_at, research_id], separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> Tuple[str, str]:
    if not isinstance(cursor, str) or not cursor or len(cursor) > 256:
        raise ValueError("cursor is invalid")
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        created_at, research_id = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return str(created_at), _validate_research_id(research_id)
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
        raise ValueError("cursor is invalid") from exc


def extract_provider_ids(payload: Any) -> Dict[str, str]:
    """Extract only known identifier-shaped fields observed in provider SSE data."""
    found: Dict[str, str] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in _PROVIDER_ID_FIELDS and isinstance(child, str) and child:
                    found[key] = child[:256]
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return found


def _sanitized_failure(exc: BaseException) -> Tuple[str, str]:
    if isinstance(exc, AuthenticationError):
        return "authentication_error", "Provider authentication failed"
    if isinstance(exc, RateLimitError):
        return "rate_limited", "Provider rate limit reached"
    if isinstance(exc, IncompleteResponseError):
        return "incomplete_delivery", "Provider stream ended before verified final delivery"
    if isinstance(exc, (TimeoutError,)) or "timeout" in exc.__class__.__name__.lower():
        return "provider_timeout", "Provider request timed out before verified final delivery"
    if isinstance(exc, (ConnectionError, RequestException)):
        return "provider_transport", "Provider transport ended before verified final delivery"
    return "provider_error", "Provider request failed before verified final delivery"


def _acquire_store_lock(fd: int) -> None:
    """Acquire a non-blocking one-byte lock using the host stdlib primitive."""
    if _msvcrt is not None:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
        return
    assert _fcntl is not None
    _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)


def _release_store_lock(fd: int) -> None:
    """Release a lock acquired by :func:`_acquire_store_lock`."""
    if _msvcrt is not None:
        os.lseek(fd, 0, os.SEEK_SET)
        _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
        return
    assert _fcntl is not None
    _fcntl.flock(fd, _fcntl.LOCK_UN)


def _ensure_private_parent(parent: Path) -> None:
    """Create missing store directories privately without chmodding existing ones."""
    missing = []
    current = parent
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not current.is_dir():
        raise NotADirectoryError(f"research journal parent is not a directory: {current}")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise
        else:
            os.chmod(directory, 0o700)


class ResearchJobManager:
    """Own one SQLite journal and execute jobs through one bounded worker."""

    def __init__(
        self,
        db_path: str,
        runner: Callable[[str, Callable[[Dict[str, Any]], None]], Any],
        *,
        owner_scope: str = "authenticated-server",
        max_queue: int = 8,
    ) -> None:
        if max_queue < 1 or max_queue > 100:
            raise ValueError("max_queue must be between 1 and 100")
        if not JOURNAL_SUPPORTED:
            raise ResearchJournalError(JOURNAL_SUPPORT_MESSAGE)
        self.db_path = Path(db_path).expanduser().resolve()
        self.runner = runner
        self.owner_scope = owner_scope
        self.max_queue = max_queue
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._closed = False
        self._pending: "deque[str]" = deque()

        _ensure_private_parent(self.db_path.parent)
        lock_path = self.db_path.with_suffix(self.db_path.suffix + ".lock")
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        os.chmod(lock_path, 0o600)
        try:
            _acquire_store_lock(lock_fd)
        except OSError as exc:
            os.close(lock_fd)
            raise ResearchStoreInUseError(
                "research journal is already owned by another server"
            ) from exc

        db: Optional[sqlite3.Connection] = None
        try:
            db = sqlite3.connect(str(self.db_path), check_same_thread=False)
            os.chmod(self.db_path, 0o600)
            db.row_factory = sqlite3.Row
            self._lock_fd = lock_fd
            self._db = db
            self._db.execute("PRAGMA journal_mode=DELETE")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._create_schema()
            self._interrupt_stale_jobs()
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="perplexity-research-worker",
                daemon=True,
            )
            self._worker.start()
        except Exception:
            if db is not None:
                db.close()
            _release_store_lock(lock_fd)
            os.close(lock_fd)
            raise

    def _create_schema(self) -> None:
        with self._db:
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS research_jobs (
                    id TEXT PRIMARY KEY,
                    owner_scope TEXT NOT NULL,
                    query TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    idempotency_key TEXT,
                    delivery_state TEXT NOT NULL,
                    provider_state TEXT NOT NULL DEFAULT 'unknown',
                    provider_ids TEXT NOT NULL DEFAULT '{}',
                    result TEXT,
                    error_code TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    UNIQUE(owner_scope, idempotency_key)
                )
                """)
            self._db.execute(
                "CREATE INDEX IF NOT EXISTS research_jobs_list_idx "
                "ON research_jobs(owner_scope, created_at DESC, id DESC)"
            )

    def _interrupt_stale_jobs(self) -> None:
        now = _now()
        with self._db:
            self._db.execute(
                """
                UPDATE research_jobs
                SET delivery_state = 'interrupted', provider_state = 'unknown',
                    error_code = 'server_restart',
                    error_message = 'Server restarted before verified final delivery',
                    finished_at = ?
                WHERE owner_scope = ? AND delivery_state IN ('queued', 'running')
                """,
                (now, self.owner_scope),
            )

    def start(self, query: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        normalized = _validate_query(query)
        if idempotency_key is not None and not _IDEMPOTENCY_PATTERN.fullmatch(idempotency_key):
            raise ValueError(
                "idempotency_key must be 1-128 letters, numbers, dots, colons, "
                "underscores, or hyphens"
            )
        request_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        research_id = str(uuid4())
        created_at = _now()

        with self._condition:
            if self._closed:
                raise ResearchJournalError("research journal is closed")
            self._db.execute("BEGIN IMMEDIATE")
            try:
                if idempotency_key is not None:
                    existing = self._db.execute(
                        """
                        SELECT * FROM research_jobs
                        WHERE owner_scope = ? AND idempotency_key = ?
                        """,
                        (self.owner_scope, idempotency_key),
                    ).fetchone()
                    if existing is not None:
                        self._db.commit()
                        if existing["request_hash"] != request_hash:
                            raise ResearchConflictError(
                                "idempotency key was already used for a different research query"
                            )
                        return self._row_to_public(existing, include_result=True)

                if len(self._pending) >= self.max_queue:
                    self._db.rollback()
                    raise ResearchCapacityError("research queue is at capacity")

                self._db.execute(
                    """
                    INSERT INTO research_jobs (
                        id, owner_scope, query, request_hash, idempotency_key,
                        delivery_state, created_at
                    ) VALUES (?, ?, ?, ?, ?, 'queued', ?)
                    """,
                    (
                        research_id,
                        self.owner_scope,
                        normalized,
                        request_hash,
                        idempotency_key,
                        created_at,
                    ),
                )
                self._db.commit()
            except Exception:
                if self._db.in_transaction:
                    self._db.rollback()
                raise

            # The durable row is committed before the worker can observe this ID.
            # Admission and deque mutation share the manager condition, so no
            # queue.Full race can strand an accepted durable row.
            self._pending.append(research_id)
            self._condition.notify_all()
            return self.get(research_id)

    def get(self, research_id: str) -> Dict[str, Any]:
        normalized_id = _validate_research_id(research_id)
        with self._lock:
            if self._closed:
                raise ResearchJournalError("research journal is closed")
            row = self._db.execute(
                "SELECT * FROM research_jobs WHERE id = ? AND owner_scope = ?",
                (normalized_id, self.owner_scope),
            ).fetchone()
            if row is None:
                raise ResearchNotFoundError("local research record was not found")
            return self._row_to_public(row, include_result=True)

    def list(
        self,
        *,
        query: Optional[str] = None,
        status: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if query is not None:
            if not isinstance(query, str):
                raise ValueError("query filter must be a string")
            query = query.strip()
            if len(query) > 500:
                raise ValueError("query filter is too long (max 500 characters)")
        if status is not None and status not in DELIVERY_STATES:
            raise ValueError("status is invalid")

        clauses = ["owner_scope = ?"]
        params: List[Any] = [self.owner_scope]
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            clauses.append("query LIKE ? ESCAPE '\\' COLLATE NOCASE")
            params.append(f"%{escaped}%")
        if status:
            clauses.append("delivery_state = ?")
            params.append(status)
        if cursor:
            created_at, research_id = _decode_cursor(cursor)
            clauses.append("(created_at < ? OR (created_at = ? AND id < ?))")
            params.extend([created_at, created_at, research_id])

        sql = (
            "SELECT * FROM research_jobs WHERE "
            + " AND ".join(clauses)
            + " ORDER BY created_at DESC, id DESC LIMIT ?"
        )
        params.append(limit + 1)
        with self._lock:
            if self._closed:
                raise ResearchJournalError("research journal is closed")
            rows = self._db.execute(sql, params).fetchall()
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor(last["created_at"], last["id"])
        return {
            "records": [self._row_to_public(row, include_result=False) for row in page_rows],
            "next_cursor": next_cursor,
        }

    def wait(self, research_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
        normalized_id = _validate_research_id(research_id)
        with self._condition:
            finished = self._condition.wait_for(
                lambda: self._closed
                or self.get(normalized_id)["delivery_state"] not in ACTIVE_STATES,
                timeout=timeout,
            )
            if not finished:
                raise TimeoutError("local wait timed out; research continues independently")
            if self._closed:
                raise ResearchJournalError("research journal closed while waiting")
            return self.get(normalized_id)

    def close(self, wait_timeout: float = 1.0) -> None:
        with self._condition:
            if self._closed:
                return
            with self._db:
                self._db.execute(
                    """
                    UPDATE research_jobs
                    SET delivery_state = 'interrupted', provider_state = 'unknown',
                        error_code = 'server_shutdown',
                        error_message = 'Server stopped before verified final delivery',
                        finished_at = ?
                    WHERE owner_scope = ? AND delivery_state IN ('queued', 'running')
                    """,
                    (_now(), self.owner_scope),
                )
            self._closed = True
            self._pending.clear()
            self._condition.notify_all()

        self._worker.join(timeout=max(0.0, wait_timeout))
        with self._lock:
            self._db.close()
            _release_store_lock(self._lock_fd)
            os.close(self._lock_fd)

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._closed or bool(self._pending))
                if self._closed:
                    return
                research_id = self._pending.popleft()
                started_at = _now()
                with self._db:
                    updated = self._db.execute(
                        """
                        UPDATE research_jobs SET delivery_state = 'running', started_at = ?
                        WHERE id = ? AND owner_scope = ? AND delivery_state = 'queued'
                        """,
                        (started_at, research_id, self.owner_scope),
                    ).rowcount
                if not updated:
                    continue
                row = self._db.execute(
                    "SELECT query FROM research_jobs WHERE id = ?", (research_id,)
                ).fetchone()
                query = row["query"]
                self._condition.notify_all()

            def observe(payload: Dict[str, Any]) -> None:
                provider_ids = extract_provider_ids(payload)
                if provider_ids:
                    self._merge_provider_ids(research_id, provider_ids)

            try:
                response = self.runner(query, observe)
                if not has_usable_final_response(response):
                    raise IncompleteResponseError(
                        "verified terminal response did not contain an answer"
                    )
                result = str(response["answer"])
            except Exception as exc:
                code, message = _sanitized_failure(exc)
                self._finish_failure(research_id, code, message)
            else:
                self._finish_success(research_id, result)

    def _merge_provider_ids(self, research_id: str, provider_ids: Dict[str, str]) -> None:
        with self._lock:
            if self._closed:
                return
            row = self._db.execute(
                "SELECT provider_ids FROM research_jobs WHERE id = ?", (research_id,)
            ).fetchone()
            if row is None:
                return
            current = json.loads(row["provider_ids"])
            current.update(provider_ids)
            with self._db:
                self._db.execute(
                    "UPDATE research_jobs SET provider_ids = ? WHERE id = ?",
                    (json.dumps(current, sort_keys=True), research_id),
                )

    def _finish_success(self, research_id: str, result: str) -> None:
        with self._condition:
            if self._closed:
                return
            with self._db:
                self._db.execute(
                    """
                    UPDATE research_jobs SET delivery_state = 'completed', result = ?,
                        error_code = NULL, error_message = NULL, finished_at = ?
                    WHERE id = ? AND delivery_state = 'running'
                    """,
                    (result, _now(), research_id),
                )
            self._condition.notify_all()

    def _finish_failure(self, research_id: str, code: str, message: str) -> None:
        with self._condition:
            if self._closed:
                return
            delivery_state = (
                "interrupted"
                if code
                in {
                    "incomplete_delivery",
                    "provider_timeout",
                    "provider_transport",
                }
                else "failed"
            )
            with self._db:
                self._db.execute(
                    """
                    UPDATE research_jobs SET delivery_state = ?, provider_state = 'unknown',
                        error_code = ?, error_message = ?, finished_at = ?
                    WHERE id = ? AND delivery_state = 'running'
                    """,
                    (delivery_state, code, message, _now(), research_id),
                )
            self._condition.notify_all()

    @staticmethod
    def _row_to_public(row: sqlite3.Row, *, include_result: bool) -> Dict[str, Any]:
        result = {
            "id": row["id"],
            "query": row["query"],
            "delivery_state": row["delivery_state"],
            "provider_state": row["provider_state"],
            "provider_ids": json.loads(row["provider_ids"]),
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "error": (
                {"code": row["error_code"], "message": row["error_message"]}
                if row["error_code"]
                else None
            ),
        }
        if include_result:
            result["result"] = row["result"]
        return result
