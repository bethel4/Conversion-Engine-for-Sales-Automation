from __future__ import annotations

import argparse
import json
import re
from datetime import date
from typing import Any

from .cache import get_cache, set_cache
from .crunchbase import normalize_company_name


LEADERSHIP_ROLES = (
    "cto",
    "chief technology officer",
    "vp engineering",
    "vice president engineering",
    "head of engineering",
    "chief architect",
    "vp of engineering",
)


def detect_leadership_change(
    company_name: str,
    *,
    days: int = 90,
    today: date | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Best-effort local detector over provided sources.

    sources: [{"text": "...", "date": "YYYY-MM-DD", "source": "url-or-name"}, ...]
    Returns:
      { new_leader_detected, role, name, days_ago, confidence, source }
    """

    if today is None:
        today = date.today()

    key = normalize_company_name(company_name)
    if not key:
        return _empty()

    cache_key = f"{key}:{days}:{today.isoformat()}"
    cached = get_cache("leadership_change", cache_key, max_age_seconds=24 * 3600)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    if not sources:
        result = _empty()
        set_cache("leadership_change", cache_key, result)
        return result

    best: dict[str, Any] | None = None
    for item in sources:
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        role = _find_role(text)
        if role is None:
            continue
        published = _parse_date(item.get("date"))
        if published is None:
            continue
        days_ago = (today - published).days
        if days_ago < 0:
            days_ago = 0
        if days_ago > days:
            continue
        name = _extract_name(text)
        confidence = _confidence(text)
        source = item.get("source")
        if not isinstance(source, str):
            source = None
        candidate = {
            "new_leader_detected": True,
            "role": role,
            "name": name,
            "days_ago": days_ago,
            "confidence": confidence,
            "source": source,
        }
        if best is None or candidate["days_ago"] < best["days_ago"]:
            best = candidate

    result = best or _empty()
    set_cache("leadership_change", cache_key, result)
    return result


def _empty() -> dict[str, Any]:
    return {
        "new_leader_detected": False,
        "role": None,
        "name": None,
        "days_ago": None,
        "confidence": None,
        "source": None,
    }


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def _find_role(text: str) -> str | None:
    t = text.casefold()
    for role in LEADERSHIP_ROLES:
        if role in t:
            return role.replace(" ", "_")
    return None


def _extract_name(text: str) -> str | None:
    # Very small heuristic: "appoints Sarah Chen as CTO" / "names Sarah Chen CTO"
    patterns = [
        r"appoints\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+as\s+(?:a\s+)?(?:cto|chief technology officer|vp of engineering|vp engineering|head of engineering|chief architect)",
        r"names\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:as\s+)?(?:cto|chief technology officer|vp of engineering|vp engineering|head of engineering|chief architect)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+joins\s+as\s+(?:a\s+)?(?:cto|chief technology officer|vp of engineering|vp engineering|head of engineering|chief architect)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _confidence(text: str) -> str:
    t = text.casefold()
    strong = ("appoint", "named", "joins as", "promoted", "effective")
    if any(k in t for k in strong):
        return "high"
    return "medium"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Leadership-change signal (local sources)")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--days", type=int, default=90, help="Lookback window")
    parser.add_argument(
        "--sources-json",
        help='JSON list of sources, e.g. \'[{"text":"...","date":"2026-03-01","source":"..."}]\'',
    )
    args = parser.parse_args(argv)

    sources = json.loads(args.sources_json) if args.sources_json else None
    result = detect_leadership_change(args.company, days=args.days, sources=sources)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
