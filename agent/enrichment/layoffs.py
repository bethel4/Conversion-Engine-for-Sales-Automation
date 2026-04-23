from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
from typing import Any

from .cache import get_cache, set_cache
from .crunchbase import normalize_company_name


def load_layoffs_dataset(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"layoffs.fyi dataset not found at: {dataset_path}")

    with dataset_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def check_layoffs(
    company_name: str,
    days: int = 120,
    *,
    dataset_path: str | Path | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """
    Returns:
      { had_layoff, days_ago, headcount_cut, percentage_cut, confidence, segment_implication }
    """

    if today is None:
        today = date.today()

    normalized = _normalize_for_layoffs(company_name)
    if not normalized:
        return _empty()

    cache_key = f"{normalized}:{days}:{today.isoformat()}"
    cached = get_cache("layoffs_check", cache_key, max_age_seconds=24 * 3600)
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    if dataset_path is None:
        dataset_path = _default_dataset_path()

    events = _find_events(dataset_path, normalized)
    if not events:
        result = _empty()
        set_cache("layoffs_check", cache_key, result)
        return result

    latest = max(events, key=lambda e: e.get("Date") or "")
    event_date = _parse_date(latest.get("Date"))
    if event_date is None:
        result = _empty()
        set_cache("layoffs_check", cache_key, result)
        return result

    days_ago = (today - event_date).days
    headcount_cut = _parse_int(latest.get("Laid_Off_Count"))
    percentage_cut = _parse_float(latest.get("Percentage"))

    had_layoff = days_ago <= days
    confidence = None
    if had_layoff:
        confidence = "high" if percentage_cut is not None or headcount_cut is not None else "medium"
    else:
        # Found a layoff, but stale for the ICP.
        confidence = "low"

    result = {
        "had_layoff": had_layoff,
        "days_ago": days_ago,
        "headcount_cut": headcount_cut,
        "percentage_cut": percentage_cut,
        "confidence": confidence,
        "segment_implication": "segment_2" if had_layoff else None,
    }
    set_cache("layoffs_check", cache_key, result)
    return result


def _empty() -> dict[str, Any]:
    return {
        "had_layoff": False,
        "days_ago": None,
        "headcount_cut": None,
        "percentage_cut": None,
        "confidence": None,
        "segment_implication": None,
    }


def _default_dataset_path() -> Path:
    return _repo_root() / "data" / "raw" / "layoffs" / "layoffs.csv"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_for_layoffs(name: str) -> str:
    base = normalize_company_name(name)
    if not base:
        return ""

    tokens = base.split()
    if tokens and tokens[-1] in {
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "ltd",
        "limited",
        "llc",
        "plc",
        "gmbh",
        "sarl",
        "sa",
        "ag",
    }:
        tokens = tokens[:-1]
    return " ".join(tokens)


def _find_events(dataset_path: str | Path, normalized_company: str) -> list[dict[str, Any]]:
    records = load_layoffs_dataset(dataset_path)
    out: list[dict[str, Any]] = []
    for row in records:
        comp = row.get("Company")
        if not isinstance(comp, str):
            continue
        if _normalize_for_layoffs(comp) == normalized_company:
            out.append(row)
    return out


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


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local layoffs.fyi lookup")
    parser.add_argument("--name", required=True, help="Company name to check")
    parser.add_argument("--days", type=int, default=120, help="Lookback window in days")
    parser.add_argument("--dataset-path", help="Optional override CSV path")
    args = parser.parse_args(argv)

    result = check_layoffs(
        args.name,
        days=args.days,
        dataset_path=args.dataset_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

