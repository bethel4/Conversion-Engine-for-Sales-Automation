from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PROSPECTS_PATH = Path("data/prospects.json")


def _store_path() -> Path:
    raw = os.getenv("PROSPECTS_STORE_PATH")
    if raw and raw.strip():
        return Path(raw.strip())
    return DEFAULT_PROSPECTS_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_records(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    records: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            records.append(item)
    return records


def load_prospects() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    try:
        return _normalize_records(json.loads(raw))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Prospect store is not valid JSON: {path}") from exc


def save_prospects(prospects: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prospects, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_prospect(prospect: dict[str, Any]) -> dict[str, Any]:
    prospects = load_prospects()
    prospect_id = str(prospect.get("id") or "").strip()
    email = str(prospect.get("email") or "").strip()
    if not prospect_id:
        raise ValueError("Prospect id is required")
    if not email:
        raise ValueError("Prospect email is required")

    for existing in prospects:
        if _matches(existing, prospect_id=prospect_id):
            raise ValueError(f"Prospect with id '{prospect_id}' already exists")
        if _matches(existing, email=email):
            raise ValueError(f"Prospect with email '{email}' already exists")

    record = dict(prospect)
    record.setdefault("activity", [])
    record.setdefault("lifecycle_stage", "New")
    record.setdefault("last_activity", _utc_now())
    prospects.append(record)
    save_prospects(prospects)
    return record


def _matches(prospect: dict[str, Any], *, prospect_id: str | None = None, email: str | None = None) -> bool:
    if prospect_id and str(prospect.get("id") or "").strip() == prospect_id:
        return True
    if email and str(prospect.get("email") or "").strip().casefold() == email.casefold():
        return True
    return False


def get_prospect(*, prospect_id: str | None = None, email: str | None = None) -> dict[str, Any] | None:
    for prospect in load_prospects():
        if _matches(prospect, prospect_id=prospect_id, email=email):
            return prospect
    return None


def update_prospect(
    *,
    prospect_id: str | None = None,
    email: str | None = None,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    prospects = load_prospects()
    for index, prospect in enumerate(prospects):
        if not _matches(prospect, prospect_id=prospect_id, email=email):
            continue
        merged = dict(prospect)
        merged.update(patch)
        merged["last_activity"] = patch.get("last_activity") or _utc_now()
        prospects[index] = merged
        save_prospects(prospects)
        return merged
    return None


def append_activity(
    *,
    prospect_id: str | None = None,
    email: str | None = None,
    activity: dict[str, Any],
) -> dict[str, Any] | None:
    prospects = load_prospects()
    for index, prospect in enumerate(prospects):
        if not _matches(prospect, prospect_id=prospect_id, email=email):
            continue
        merged = dict(prospect)
        current = merged.get("activity")
        events = current if isinstance(current, list) else []
        events = [item for item in events if isinstance(item, dict)]
        event = dict(activity)
        event.setdefault("timestamp", _utc_now())
        events.append(event)
        merged["activity"] = events[-25:]
        merged["last_activity"] = event["timestamp"]
        prospects[index] = merged
        save_prospects(prospects)
        return merged
    return None
