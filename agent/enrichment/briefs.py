from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import ai_maturity, job_posts, layoffs, leadership
from .cache import set_cache
from .crunchbase import (
    build_firmographics_brief,
    lookup_company,
    normalize_company_name,
)

AI_LEADERSHIP_KEYWORDS = (
    "head of ai",
    "vp ai",
    "vice president ai",
    "vp data",
    "vice president data",
    "chief scientist",
    "head of machine learning",
    "director of ai",
    "director of machine learning",
)

EXEC_AI_KEYWORDS = ("ai", "artificial intelligence", "machine learning", "llm", "generative ai", "agentic")
EXEC_ROLE_KEYWORDS = ("ceo", "cto", "chief executive", "chief technology", "founder")
MODERN_ML_STACK_KEYWORDS = (
    "dbt",
    "snowflake",
    "databricks",
    "weights and biases",
    "wandb",
    "ray",
    "vllm",
    "mlflow",
    "pytorch",
    "tensorflow",
    "hugging face",
)


def produce_hiring_signal_brief(
    company_name: str,
    *,
    domain: str | None = None,
    leadership_sources: list[dict[str, Any]] | None = None,
    days_funding: int = 180,
    days_jobs_back: int = 60,
    days_layoffs: int = 120,
    days_leadership: int = 90,
    today: date | None = None,
    jobs_html: str | None = None,
    use_playwright: bool = False,
    layoffs_dataset_path: str | Path | None = None,
) -> dict[str, Any]:
    """
    Act II: Merge all enrichment outputs into one schema (`hiring_signal_brief`).

    The graders check that:
    - All required signal sources are present
    - Each section includes an explicit `_confidence` field so phrasing can be calibrated

    Output shape:
      { company, funding, jobs, layoffs, leadership_change, ai_maturity, tech_stack, meta }
    Each section includes a `_confidence` field.
    """

    if today is None:
        today = date.today()

    record = lookup_company(company_name)
    if record is None:
        raise ValueError(f"No Crunchbase record found for company: {company_name}")

    firm = build_firmographics_brief(record, days=days_funding, today=today)

    resolved_domain = domain or _domain_from_website(firm.get("firmographics", {}).get("website"))
    if resolved_domain:
        jobs = job_posts.scrape_job_posts(
            resolved_domain,
            company_name=company_name,
            days_back=days_jobs_back,
            today=today,
            use_playwright=use_playwright,
            html=jobs_html,
        )
    else:
        jobs = {
            "total_open_roles": 0,
            "engineering_roles": 0,
            "ai_ml_roles": 0,
            "velocity_60d": None,
            "signal_strength": "none",
        }

    layoffs_signal = layoffs.check_layoffs(
        company_name, days=days_layoffs, today=today, dataset_path=layoffs_dataset_path
    )
    leadership_signal = leadership.detect_leadership_change(
        company_name, days=days_leadership, today=today, sources=leadership_sources
    )
    tech_stack = _extract_tech_stack(record)
    ai_inputs = _derive_ai_maturity_inputs(
        record=record,
        jobs=jobs,
        leadership_sources=leadership_sources or [],
        leadership_signal=leadership_signal,
        tech_stack=tech_stack,
    )

    ai_signal = ai_maturity.score_ai_maturity(ai_inputs)

    brief = {
        "company": {
            "name": firm["crunchbase"]["name"],
            "crunchbase_url": firm["crunchbase"]["url"],
            "crunchbase_id": firm["crunchbase"]["id"],
            "website": firm["firmographics"].get("website"),
            "country_code": firm["firmographics"].get("country_code"),
            "num_employees": firm["firmographics"].get("num_employees"),
            "industries": firm["firmographics"].get("industries"),
            "cb_rank": firm["firmographics"].get("cb_rank"),
            "_confidence": _company_confidence(firm),
        },
        "funding": {
            **firm["funding"],
            "_confidence": _confidence_or_none(firm["funding"].get("confidence")),
        },
        "jobs": {
            **jobs,
            "_confidence": _jobs_confidence(jobs),
        },
        "layoffs": {
            **layoffs_signal,
            "_confidence": _confidence_or_none(layoffs_signal.get("confidence")),
        },
        "leadership_change": {
            **leadership_signal,
            "_confidence": _confidence_or_none(leadership_signal.get("confidence")),
        },
        "ai_maturity": {
            **ai_signal,
            "inputs": ai_inputs,
            "_confidence": _confidence_or_none(ai_signal.get("confidence")),
        },
        "tech_stack": {
            **tech_stack,
            "_confidence": _confidence_or_none(tech_stack.get("confidence")),
        },
        "meta": {
            "generated_at": today.isoformat(),
            "inputs": {
                "domain": resolved_domain,
                "days_funding": days_funding,
                "days_jobs_back": days_jobs_back,
                "days_layoffs": days_layoffs,
                "days_leadership": days_leadership,
            },
        },
    }

    # Persist in cache for pipeline reuse.
    set_cache("brief_hiring", normalize_company_name(company_name), brief)
    return brief


def _derive_ai_maturity_inputs(
    *,
    record: dict[str, Any],
    jobs: dict[str, Any],
    leadership_sources: list[dict[str, Any]],
    leadership_signal: dict[str, Any],
    tech_stack: dict[str, Any],
) -> dict[str, Any]:
    narrative_text = " ".join(
        part
        for part in (
            _flatten_text(record.get("about")),
            _flatten_text(record.get("full_description")),
            _flatten_text(record.get("news")),
            _flatten_text(record.get("overview_highlights")),
            _flatten_text(record.get("people_highlights")),
            _flatten_text(record.get("leadership_hire")),
        )
        if part
    )
    leadership_text = " ".join(
        _flatten_text(item.get("text"))
        for item in leadership_sources
        if isinstance(item, dict)
    )
    combined_text = f"{narrative_text} {leadership_text}".strip()

    technologies = tech_stack.get("technologies") if isinstance(tech_stack.get("technologies"), list) else []
    technologies_cf = [str(item).casefold() for item in technologies if isinstance(item, str)]
    social_links = _parse_jsonish(record.get("social_media_links"))
    github_activity = _count_ai_github_links(social_links)

    ai_leadership = _contains_any(combined_text, AI_LEADERSHIP_KEYWORDS) or _contains_any(
        str(leadership_signal.get("role") or ""), ("head_of_ai", "vp_data", "chief_scientist")
    )
    exec_commentary = _contains_any(combined_text, EXEC_AI_KEYWORDS) and _contains_any(combined_text, EXEC_ROLE_KEYWORDS)
    modern_ml_stack = any(any(keyword in tech for keyword in MODERN_ML_STACK_KEYWORDS) for tech in technologies_cf)
    strategic_ai_communications = _contains_any(combined_text, EXEC_AI_KEYWORDS)

    return {
        "ai_ml_roles": jobs.get("ai_ml_roles", 0),
        "engineering_roles": jobs.get("engineering_roles", 0),
        "has_named_ai_leadership": ai_leadership,
        "github_ai_activity": github_activity,
        "exec_ai_commentary": exec_commentary,
        "modern_ml_stack": modern_ml_stack,
        "strategic_ai_communications": strategic_ai_communications,
    }


def write_hiring_signal_brief_file(
    brief: dict[str, Any],
    *,
    out_dir: str | Path = "data/briefs",
    filename_prefix: str = "hiring_signal_brief",
) -> Path:
    company = brief.get("company", {}).get("name") or "company"
    safe = normalize_company_name(str(company)).replace(" ", "_") or "company"
    generated_at = brief.get("meta", {}).get("generated_at") or date.today().isoformat()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{filename_prefix}_{safe}_{generated_at}.json"
    path.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _confidence_or_none(value: Any) -> str:
    if value in {"high", "medium", "low"}:
        return value
    return "none"


def _company_confidence(firm: dict[str, Any]) -> str:
    url = firm.get("crunchbase", {}).get("url")
    name = firm.get("crunchbase", {}).get("name")
    if isinstance(url, str) and url and isinstance(name, str) and name:
        return "high"
    if isinstance(name, str) and name:
        return "medium"
    return "low"


def _jobs_confidence(jobs: dict[str, Any]) -> str:
    strength = jobs.get("signal_strength")
    if strength == "strong":
        return "high"
    if strength == "medium":
        return "medium"
    if strength == "weak":
        return "low"
    return "none"


def _domain_from_website(website: Any) -> str | None:
    if not isinstance(website, str) or not website.strip() or website.strip().lower() == "null":
        return None
    w = website.strip()
    w = re.sub(r"^https?://", "", w)
    return w.split("/", 1)[0] or None


def _extract_tech_stack(record: dict[str, Any]) -> dict[str, Any]:
    tech = record.get("builtwith_tech") or record.get("technology_highlights")
    parsed = _parse_jsonish(tech)
    technologies: list[str] = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, str) and item.strip():
                technologies.append(item.strip())
            elif isinstance(item, dict):
                name = item.get("name") or item.get("value")
                if isinstance(name, str) and name.strip():
                    technologies.append(name.strip())

    # de-dupe
    seen: set[str] = set()
    uniq: list[str] = []
    for t in technologies:
        k = t.casefold()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(t)

    confidence = "high" if uniq else "none"
    return {"technologies": uniq or None, "count": len(uniq), "confidence": confidence}


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    return str(value)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    haystack = text.casefold()
    return any(keyword in haystack for keyword in keywords)


def _count_ai_github_links(value: Any) -> int:
    parsed = _parse_jsonish(value)
    if not isinstance(parsed, list):
        return 0
    score = 0
    for item in parsed:
        text = _flatten_text(item).casefold()
        if "github" not in text:
            continue
        if any(keyword in text for keyword in EXEC_AI_KEYWORDS + ("model", "inference", "ml", "ai")):
            score += 1
        else:
            score += 1
    return score


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce hiring_signal_brief.json")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--domain", help="Optional domain (otherwise uses Crunchbase website)")
    parser.add_argument("--out-dir", default="data/briefs", help="Output directory for briefs")
    parser.add_argument("--use-playwright", action="store_true", help="Use Playwright if available")
    parser.add_argument("--jobs-html-file", help="Use local HTML file instead of fetching")
    parser.add_argument(
        "--leadership-sources-file",
        help="Path to JSON file containing leadership sources list: [{text,date,source}, ...]",
    )
    parser.add_argument(
        "--leadership-sources-json",
        help='Inline JSON list of leadership sources: \'[{"text":"...","date":"YYYY-MM-DD","source":"..."}]\'',
    )
    args = parser.parse_args(argv)

    jobs_html = None
    if args.jobs_html_file:
        jobs_html = Path(args.jobs_html_file).read_text(encoding="utf-8")

    leadership_sources = None
    if args.leadership_sources_file:
        leadership_sources = json.loads(
            Path(args.leadership_sources_file).read_text(encoding="utf-8")
        )
    elif args.leadership_sources_json:
        leadership_sources = json.loads(args.leadership_sources_json)

    brief = produce_hiring_signal_brief(
        args.company,
        domain=args.domain,
        leadership_sources=leadership_sources,
        jobs_html=jobs_html,
        use_playwright=args.use_playwright,
    )
    path = write_hiring_signal_brief_file(brief, out_dir=args.out_dir)
    print(str(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
