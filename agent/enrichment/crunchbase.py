from __future__ import annotations

import argparse
import csv
import json
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


CRUNCHBASE_COMPAT_JSON_PATH = Path("data/crunchbase_odm_sample.json")


def normalize_company_name(name: str) -> str:
    """
    Normalization used for matching:
    - lowercase (casefold)
    - trim whitespace
    - remove common punctuation
    - collapse repeated whitespace
    """

    if not name:
        return ""

    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold().strip()
    text = text.replace("_", " ")
    text = re.sub(r"[^\w\s]", " ", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_firmographics_brief(
    crunchbase_record: dict[str, Any], days: int = 180, *, today: "date | None" = None
) -> dict[str, Any]:
    """
    Produces a compact, stable-shaped payload for downstream enrichment/classification:
      { crunchbase: {...}, firmographics: {...}, funding: {...} }
    """

    return {
        "crunchbase": {
            "id": crunchbase_record.get("id"),
            "name": _extract_company_name(crunchbase_record),
            "url": crunchbase_record.get("url"),
        },
        "firmographics": {
            "website": crunchbase_record.get("website"),
            "country_code": crunchbase_record.get("country_code")
            or crunchbase_record.get("country"),
            "num_employees": crunchbase_record.get("num_employees")
            or crunchbase_record.get("employee_count")
            or crunchbase_record.get("employees"),
            "industries": _extract_industries(crunchbase_record),
            "cb_rank": crunchbase_record.get("cb_rank"),
        },
        "funding": is_recently_funded(crunchbase_record, days=days, today=today),
    }


def is_recently_funded(
    crunchbase_record: dict[str, Any],
    days: int = 180,
    *,
    today: "date | None" = None,
) -> dict[str, Any]:
    """
    Returns funding recency signal:
      { funded, days_ago, amount_usd, round_type, confidence }

    Confidence buckets:
      - high: <60 days
      - medium: 60–119 days
      - low: 120–days days
    """

    from datetime import date

    if today is None:
        today = date.today()

    event = _extract_latest_funding_event(crunchbase_record)
    funded_on = _parse_date(event.get("date"))
    if funded_on is None:
        return {
            "funded": False,
            "days_ago": None,
            "amount_usd": _parse_usd_amount(event.get("amount_usd")),
            "round_type": event.get("round_type"),
            "confidence": None,
        }

    days_ago = (today - funded_on).days
    if days_ago < 0:
        # Bad/forward-dated data; treat as "just funded" rather than excluding.
        days_ago = 0

    funded = days_ago <= days
    confidence: str | None
    if not funded:
        confidence = None
    elif days_ago < 60:
        confidence = "high"
    elif days_ago < 120:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "funded": funded,
        "days_ago": days_ago,
        "amount_usd": _parse_usd_amount(event.get("amount_usd")),
        "round_type": event.get("round_type"),
        "confidence": confidence,
    }


def load_crunchbase_dataset(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Crunchbase dataset not found at: {dataset_path}")

    suffix = dataset_path.suffix.lower()
    if suffix in {".csv"}:
        with dataset_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]

    if suffix in {".json", ".jsonl", ".ndjson"}:
        raw = dataset_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        if suffix in {".jsonl", ".ndjson"} and not raw.startswith("["):
            records: list[dict[str, Any]] = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
            return records

        obj = json.loads(raw)
        if isinstance(obj, list):
            return obj  # type: ignore[return-value]
        if isinstance(obj, dict):
            for key in ("data", "records", "items", "results"):
                if isinstance(obj.get(key), list):
                    return obj[key]  # type: ignore[return-value]
            return [obj]  # type: ignore[list-item]

        raise ValueError(f"Unsupported JSON structure in {dataset_path}")

    raise ValueError(
        f"Unsupported Crunchbase dataset format: {dataset_path} (expected .csv, .json, .jsonl)"
    )


def build_name_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in records:
        name = _extract_company_name(record)
        if not name:
            continue
        key = normalize_company_name(name)
        if not key:
            continue
        index.setdefault(key, record)
    return index


def lookup_company(name: str) -> dict[str, Any] | None:
    normalized = normalize_company_name(name)
    if not normalized:
        return None
    dataset_path = _resolve_dataset_path()
    cache_key = f"{Path(dataset_path).name}:{normalized}"
    try:
        from .cache import get_cache, set_cache
    except Exception:  # pragma: no cover
        get_cache = None  # type: ignore[assignment]
        set_cache = None  # type: ignore[assignment]

    if get_cache is not None:
        cached = get_cache("crunchbase_lookup", cache_key, max_age_seconds=7 * 24 * 3600)
        if isinstance(cached, dict) and cached.get("__not_found__") is True:
            return None
        if isinstance(cached, dict):
            return _with_compat_fields(cached)  # type: ignore[return-value]

    record = _lookup_by_normalized_name(normalized, dataset_path)
    if record is not None:
        record = _with_compat_fields(record)
    if set_cache is not None:
        if record is None:
            set_cache("crunchbase_lookup", cache_key, {"__not_found__": True})
        else:
            set_cache("crunchbase_lookup", cache_key, record)
    return record


def search_companies(query: str = "", *, limit: int = 20) -> list[dict[str, Any]]:
    dataset_path = _resolve_dataset_path()
    records = load_crunchbase_dataset(dataset_path)
    normalized_query = normalize_company_name(query)

    matches: list[dict[str, Any]] = []
    for record in records:
        name = _extract_company_name(record)
        if not name:
            continue
        normalized_name = normalize_company_name(name)
        if normalized_query and normalized_query not in normalized_name:
            continue
        enriched = _with_compat_fields(record)
        matches.append(
            {
                "name": name,
                "id": enriched.get("id"),
                "domain": _domain_from_record(enriched),
                "country": enriched.get("country"),
                "employee_count": enriched.get("employee_count"),
                "industries": enriched.get("categories") or [],
                "description": enriched.get("description"),
            }
        )
        if len(matches) >= limit:
            break
    return matches


def _extract_company_name(record: dict[str, Any]) -> str | None:
    for key in ("name", "company_name", "organization_name", "company"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _with_compat_fields(record: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    funding = _extract_latest_funding_event(record)
    industries = _extract_industries(record) or []
    enriched.setdefault("domain", record.get("website") or record.get("domain"))
    enriched.setdefault("country", record.get("country_code") or record.get("country"))
    enriched.setdefault("employee_count", _coerce_employee_count(record.get("num_employees") or record.get("employee_count")))
    enriched.setdefault("categories", industries)
    enriched.setdefault("description", record.get("full_description") or record.get("about"))
    enriched.setdefault("linkedin_url", _extract_linkedin_url(record))
    enriched.setdefault("founded_year", _extract_founded_year(record))
    enriched.setdefault("last_funding_date", funding.get("date"))
    enriched.setdefault("last_funding_type", funding.get("round_type"))
    enriched.setdefault("last_funding_amount_usd", _parse_usd_amount(funding.get("amount_usd")))
    enriched.setdefault("_source", "crunchbase_odm")
    enriched.setdefault("_confidence", 1.0)
    return enriched


def _extract_industries(record: dict[str, Any]) -> list[str] | None:
    value = record.get("industries") or record.get("categories") or record.get("category")
    parsed = _parse_jsonish(value)
    if isinstance(parsed, list):
        out: list[str] = []
        for item in parsed:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                v = item.get("value") or item.get("name") or item.get("category")
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
        return out or None
    if isinstance(value, str) and value.strip() and value.strip().lower() != "null":
        return [value.strip()]
    return None


def _extract_linkedin_url(record: dict[str, Any]) -> str | None:
    parsed = _parse_jsonish(record.get("social_media_links"))
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, str) and "linkedin.com" in item:
                return item
    return None


def _extract_founded_year(record: dict[str, Any]) -> int | None:
    raw = record.get("founded_date")
    if not isinstance(raw, str) or len(raw) < 4:
        return None
    try:
        return int(raw[:4])
    except ValueError:
        return None


def _coerce_employee_count(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    matches = [int(item) for item in re.findall(r"\d+", value)]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    return round(sum(matches[:2]) / 2)


def _extract_latest_funding_event(record: dict[str, Any]) -> dict[str, Any]:
    """
    Returns best-effort normalized fields:
      { date, amount_usd, round_type }
    """

    direct_date = _first_str(
        record,
        (
            "last_funding_date",
            "last_funding_at",
            "last_funding_on",
            "last_funding_round_date",
        ),
    )
    direct_round = _first_str(
        record,
        ("last_funding_type", "last_funding_round_type", "last_funding_round"),
    )
    direct_amount = record.get("last_funding_amount_usd") or record.get(
        "last_funding_amount"
    )
    if direct_date:
        return {
            "date": direct_date,
            "amount_usd": direct_amount,
            "round_type": _normalize_round_type(direct_round) if direct_round else None,
        }

    # BrightData sample stores JSON-encoded lists in CSV columns.
    event_lists: list[list[dict[str, Any]]] = []
    for key in ("funding_rounds_list", "funding_rounds", "funds_raised", "funds_list"):
        parsed = _parse_jsonish(record.get(key))
        if isinstance(parsed, list):
            event_lists.append([x for x in parsed if isinstance(x, dict)])
        elif isinstance(parsed, dict):
            values = list(parsed.values())
            events = [x for x in values if isinstance(x, dict)]
            if events:
                event_lists.append(events)

    events = [e for sub in event_lists for e in sub]
    best: dict[str, Any] | None = None
    best_date = None
    for event in events:
        date_str = _first_str(event, ("announced_on", "date", "closed_on", "funded_on"))
        parsed_date = _parse_date(date_str)
        if parsed_date is None:
            continue
        if best_date is None or parsed_date > best_date:
            best_date = parsed_date
            best = event

    if best is None:
        return {"date": None, "amount_usd": None, "round_type": None}

    date_str = _first_str(best, ("announced_on", "date", "closed_on", "funded_on"))
    amount_usd = best.get("money_raised_usd") or best.get("raised_amount_usd") or best.get(
        "amount_usd"
    )
    round_type = (
        _first_str(best, ("investment_type", "round_type", "funding_type", "series"))
        or _round_type_from_title(_first_str(best, ("title", "name")))
    )
    return {
        "date": date_str,
        "amount_usd": amount_usd,
        "round_type": _normalize_round_type(round_type) if round_type else None,
    }


def _first_str(obj: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = obj.get(key)
        if isinstance(value, str) and value.strip() and value.strip().lower() != "null":
            return value.strip()
    return None


def _round_type_from_title(title: str | None) -> str | None:
    if not title:
        return None
    # Example: "Venture Round - Styloosh" -> "Venture Round"
    return title.split(" - ", 1)[0].strip() if " - " in title else title.strip()


def _normalize_round_type(round_type: str | None) -> str | None:
    if not round_type:
        return None
    text = round_type.casefold().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", "_", text).strip("_")
    return text or None


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw or raw.lower() == "null":
        return None
    if raw[0] not in "[{":
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _parse_date(value: Any) -> "date | None":
    from datetime import date, datetime

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text or text.lower() == "null":
        return None

    # Common: "2024-07-03 00:00:00.000" or ISO-like timestamps.
    text = text.replace("Z", "")
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)

    try:
        return date.fromisoformat(text[:10])
    except Exception:
        pass

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _parse_usd_amount(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() == "null":
        return None
    text = text.replace(",", "")
    text = re.sub(r"[^0-9.\\-]", "", text)
    if not text:
        return None
    try:
        num = float(text)
        return int(num) if num.is_integer() else num
    except Exception:
        return None


def _repo_root() -> Path:
    # agent/enrichment/crunchbase.py -> repo root is two parents up from agent/
    return Path(__file__).resolve().parents[2]


def ensure_compat_json_dataset(target_path: str | Path | None = None) -> Path:
    """
    Materialize the legacy `data/crunchbase_odm_sample.json` dataset from the local CSV/JSON
    sample when that compatibility file is absent.
    """

    target = Path(target_path) if target_path is not None else _repo_root() / CRUNCHBASE_COMPAT_JSON_PATH
    if target.exists():
        return target

    source = Path(_resolve_dataset_path())
    records = load_crunchbase_dataset(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _resolve_dataset_path() -> str:
    """
    Finds a local Crunchbase ODM sample.

    Search order:
    1) $CRUNCHBASE_ODM_PATH (explicit override)
    2) data/raw/crunchbase/ (known filenames then any .csv/.json/.jsonl)

    If not found, the loader path is created at data/raw/crunchbase/ and a
    FileNotFoundError is raised with instructions.
    """

    env_path = os.getenv("CRUNCHBASE_ODM_PATH")
    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.exists():
            return str(candidate.resolve())

    dataset_dir = _repo_root() / "data" / "raw" / "crunchbase"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    preferred = [
        dataset_dir / "crunchbase-companies-information.csv",
        dataset_dir / "crunchbase-odm-sample.csv",
        dataset_dir / "crunchbase-odm-sample.json",
        dataset_dir / "odm_sample.csv",
        dataset_dir / "odm_sample.json",
    ]
    for path in preferred:
        if path.exists():
            return str(path.resolve())

    candidates: list[Path] = []
    for suffix in (".csv", ".json", ".jsonl", ".ndjson"):
        candidates.extend(sorted(dataset_dir.glob(f"*{suffix}")))
    if candidates:
        return str(candidates[0].resolve())

    raise FileNotFoundError(
        "Crunchbase ODM sample not found. "
        "Download the 1001-record sample dataset and place it under "
        f"{dataset_dir} (or set $CRUNCHBASE_ODM_PATH to point to it)."
    )


@lru_cache(maxsize=4)
def _get_index(dataset_path: str) -> dict[str, dict[str, Any]]:
    records = load_crunchbase_dataset(dataset_path)
    return build_name_index(records)


@lru_cache(maxsize=4096)
def _lookup_by_normalized_name(
    normalized_name: str, dataset_path: str
) -> dict[str, Any] | None:
    index = _get_index(dataset_path)
    return index.get(normalized_name)


def _clear_caches() -> None:
    _get_index.cache_clear()
    _lookup_by_normalized_name.cache_clear()


def _default_out_path(company_name: str) -> Path:
    safe = normalize_company_name(company_name).replace(" ", "_") or "company"
    return _repo_root() / "data" / "processed" / "crunchbase" / f"{safe}.json"


def _resolve_out_path(out_arg: str, company_name: str) -> Path:
    requested = Path(out_arg)
    default_file = _default_out_path(company_name).name

    if requested.exists() and requested.is_dir():
        return requested / default_file

    # If user typed a trailing slash, treat as a directory even if it doesn't exist yet.
    if out_arg.endswith(("/", os.sep)):
        return requested / default_file

    # If they provided an explicit filename, respect it.
    if requested.suffix.lower() in {".json"}:
        return requested

    # Otherwise assume it's a directory path.
    return requested / default_file


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _domain_from_record(record: dict[str, Any]) -> str | None:
    website = record.get("website") or record.get("domain")
    if not isinstance(website, str) or not website.strip():
        return None
    value = re.sub(r"^https?://", "", website.strip())
    return value.split("/", 1)[0] or None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local Crunchbase ODM lookup")
    parser.add_argument("--name", required=True, help="Company name to look up")
    parser.add_argument(
        "--dataset-path",
        help="Optional override path (also supports $CRUNCHBASE_ODM_PATH)",
    )
    parser.add_argument(
        "--brief",
        action="store_true",
        help="Emit a compact firmographics+funding payload instead of the full record",
    )
    parser.add_argument(
        "--out",
        help="Write output JSON to this file (or directory). Default: data/processed/crunchbase/<company>.json",
    )
    args = parser.parse_args(argv)

    if args.dataset_path:
        os.environ["CRUNCHBASE_ODM_PATH"] = args.dataset_path
        _clear_caches()

    record = lookup_company(args.name)
    if record is None:
        payload: Any = None
        if args.out:
            _write_json(_resolve_out_path(args.out, args.name), payload)
        else:
            print("null")
        return 1

    payload = build_firmographics_brief(record) if args.brief else record
    if args.out:
        _write_json(_resolve_out_path(args.out, args.name), payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
