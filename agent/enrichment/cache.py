from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def cache_db_path() -> Path:
    override = os.getenv("ENRICHMENT_CACHE_DB")
    if override:
        return Path(override).expanduser()
    return _repo_root() / "data" / "cache.db"


def get_cache(source: str, key: str, *, max_age_seconds: int = 24 * 3600) -> Any | None:
    _init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT value_json, cached_at FROM cache WHERE source=? AND key=?",
            (source, key),
        ).fetchone()
    if row is None:
        return None

    value_json, cached_at = row
    try:
        cached_dt = datetime.fromisoformat(cached_at)
    except Exception:
        return None

    age_seconds = (datetime.now(timezone.utc) - cached_dt).total_seconds()
    if age_seconds > max_age_seconds:
        return None

    try:
        return json.loads(value_json)
    except Exception:
        return None


def set_cache(source: str, key: str, value: Any) -> None:
    _init_db()
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO cache (source, key, value_json, cached_at) VALUES (?,?,?,?)",
            (source, key, payload, now),
        )
        conn.commit()


def list_cache(source: str, key_prefix: str) -> list[dict[str, Any]]:
    """
    Returns rows for keys like "{key_prefix}%":
      [{key, value, cached_at}, ...]
    """

    _init_db()
    like = f"{key_prefix}%"
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, value_json, cached_at FROM cache WHERE source=? AND key LIKE ?",
            (source, like),
        ).fetchall()

    out: list[dict[str, Any]] = []
    for key, value_json, cached_at in rows:
        try:
            value = json.loads(value_json)
        except Exception:
            value = None
        out.append({"key": key, "value": value, "cached_at": cached_at})
    return out


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _connect() -> sqlite3.Connection:
    path = cache_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
              source TEXT NOT NULL,
              key TEXT NOT NULL,
              value_json TEXT NOT NULL,
              cached_at TEXT NOT NULL,
              PRIMARY KEY (source, key)
            )
            """
        )
        conn.commit()

