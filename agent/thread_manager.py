from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ThreadMessage:
    thread_id: str
    role: str
    content: str
    created_at: str
    meta: dict[str, Any] | None = None


class ThreadManager:
    """
    Act III (Probe category: Multi-thread leakage)

    Stores conversation context keyed by `thread_id` and *only* retrieves context
    for the requested thread. This prevents cross-thread contamination when the
    agent is handling multiple prospects concurrently.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else default_threads_db_path()
        self._init_db()

    def append_message(
        self,
        thread_id: str,
        *,
        role: str,
        content: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if not thread_id or not thread_id.strip():
            raise ValueError("thread_id is required")
        if not role or not role.strip():
            raise ValueError("role is required")

        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO thread_messages (thread_id, role, content, created_at, meta_json) VALUES (?,?,?,?,?)",
                (thread_id, role, content, created_at, _json_dumps(meta)),
            )
            conn.commit()

    def get_context(self, thread_id: str, *, limit: int = 20) -> list[ThreadMessage]:
        if not thread_id or not thread_id.strip():
            raise ValueError("thread_id is required")

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT thread_id, role, content, created_at, meta_json
                FROM thread_messages
                WHERE thread_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (thread_id, limit),
            ).fetchall()

        # Return oldest -> newest
        out: list[ThreadMessage] = []
        for t_id, role, content, created_at, meta_json in reversed(rows):
            out.append(
                ThreadMessage(
                    thread_id=t_id,
                    role=role,
                    content=content,
                    created_at=created_at,
                    meta=_json_loads(meta_json),
                )
            )
        return out

    def clear_thread(self, thread_id: str) -> None:
        if not thread_id or not thread_id.strip():
            raise ValueError("thread_id is required")
        with self._connect() as conn:
            conn.execute("DELETE FROM thread_messages WHERE thread_id = ?", (thread_id,))
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS thread_messages (
                  thread_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  meta_json TEXT,
                  rowid INTEGER PRIMARY KEY AUTOINCREMENT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_thread_messages_thread_created ON thread_messages(thread_id, created_at)"
            )
            conn.commit()


def default_threads_db_path() -> Path:
    override = os.getenv("THREADS_DB_PATH")
    if override:
        return Path(override).expanduser()
    return _repo_root() / "data" / "threads.db"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    try:
        import json

        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return None


def _json_loads(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        import json

        obj = json.loads(value)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None

