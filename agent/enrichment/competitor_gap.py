from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from . import ai_maturity
from .cache import set_cache
from .crunchbase import load_crunchbase_dataset, normalize_company_name
from .briefs import _parse_jsonish as _parse_jsonish_briefs  # reuse helper
from .briefs import produce_hiring_signal_brief, write_hiring_signal_brief_file


AI_TECH_KEYWORDS = (
    "tensorflow",
    "pytorch",
    "hugging face",
    "openai",
    "vertex ai",
    "sagemaker",
    "bedrock",
    "mlflow",
    "kubeflow",
    "langchain",
    "llamaindex",
    "databricks",
)

DATA_TECH_KEYWORDS = ("snowflake", "bigquery", "redshift", "databricks", "dbt", "kafka")
MODERN_CLOUD_KEYWORDS = ("kubernetes", "docker", "aws", "gcp", "google cloud", "azure", "cloudflare")


def produce_competitor_gap_brief(
    company_name: str,
    *,
    hiring_brief: dict[str, Any] | None = None,
    peers_limit: int = 10,
    today: date | None = None,
) -> dict[str, Any]:
    """
    Produces competitor gap brief from local Crunchbase dataset (no paid APIs).

    Output:
      { company, prospect_percentile, peers, gaps, meta }
    """

    if today is None:
        today = date.today()

    if hiring_brief is None:
        hiring_brief = produce_hiring_signal_brief(company_name, today=today)

    dataset_path = _resolve_dataset_path()
    records = load_crunchbase_dataset(dataset_path)

    target = _find_record(records, company_name)
    if target is None:
        raise ValueError(f"No Crunchbase record for company: {company_name}")

    peers = _find_peers(records, target, limit=peers_limit)
    peer_summaries = []
    peer_scores = []
    for peer in peers:
        summary = _summarize_company(peer)
        score = _score_peer_ai(peer)
        peer_summaries.append({**summary, "ai_maturity": score})
        peer_scores.append(score["score"])

    prospect_score = hiring_brief.get("ai_maturity", {}).get("score")
    if not isinstance(prospect_score, int):
        prospect_score = _score_peer_ai(target)["score"]

    percentile = _percentile(prospect_score, peer_scores)
    gaps = _derive_gaps(target, peer_summaries)

    brief = {
        "company": {
            "name": hiring_brief.get("company", {}).get("name") or company_name,
            "crunchbase_url": hiring_brief.get("company", {}).get("crunchbase_url"),
            "industries": hiring_brief.get("company", {}).get("industries"),
            "num_employees": hiring_brief.get("company", {}).get("num_employees"),
        },
        "prospect_percentile": percentile,
        "peers": peer_summaries,
        "gaps": gaps,
        "meta": {
            "generated_at": today.isoformat(),
            "peer_count": len(peer_summaries),
            "dataset_path": str(dataset_path),
            "method": "heuristic_local",
        },
    }

    set_cache("brief_competitor_gap", normalize_company_name(company_name), brief)
    return brief


def write_competitor_gap_brief_file(
    brief: dict[str, Any],
    *,
    out_dir: str | Path = "data/briefs",
    filename_prefix: str = "competitor_gap_brief",
) -> Path:
    company = brief.get("company", {}).get("name") or "company"
    safe = normalize_company_name(str(company)).replace(" ", "_") or "company"
    generated_at = brief.get("meta", {}).get("generated_at") or date.today().isoformat()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{filename_prefix}_{safe}_{generated_at}.json"
    path.write_text(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _resolve_dataset_path() -> Path:
    # Use the same default location as crunchbase lookup.
    from .crunchbase import _resolve_dataset_path as _resolve  # type: ignore

    return Path(_resolve())


def _find_record(records: list[dict[str, Any]], company_name: str) -> dict[str, Any] | None:
    target = normalize_company_name(company_name)
    for r in records:
        name = r.get("name")
        if isinstance(name, str) and normalize_company_name(name) == target:
            return r
    return None


def _extract_industries(record: dict[str, Any]) -> set[str]:
    value = record.get("industries")
    parsed = _parse_jsonish_briefs(value)
    out: set[str] = set()
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                v = item.get("value") or item.get("name")
                if isinstance(v, str) and v.strip():
                    out.add(v.strip())
            elif isinstance(item, str) and item.strip():
                out.add(item.strip())
    return out


def _employee_bucket(record: dict[str, Any]) -> str | None:
    value = record.get("num_employees")
    if not isinstance(value, str) or not value.strip() or value.strip().lower() == "null":
        return None
    return value.strip()


def _find_peers(
    records: list[dict[str, Any]],
    target: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    target_ind = _extract_industries(target)
    target_bucket = _employee_bucket(target)
    target_name = normalize_company_name(str(target.get("name") or ""))

    candidates: list[tuple[int, dict[str, Any]]] = []
    for r in records:
        name = normalize_company_name(str(r.get("name") or ""))
        if not name or name == target_name:
            continue
        bucket = _employee_bucket(r)
        if target_bucket and bucket and bucket != target_bucket:
            continue
        ind = _extract_industries(r)
        overlap = len(target_ind.intersection(ind))
        if overlap <= 0:
            continue
        candidates.append((overlap, r))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in candidates[:limit]]


def _summarize_company(record: dict[str, Any]) -> dict[str, Any]:
    features = _compute_features(record)
    return {
        "name": record.get("name"),
        "url": record.get("url"),
        "num_employees": record.get("num_employees"),
        "industries": sorted(_extract_industries(record)) or None,
        "features": features,
    }


def _extract_tech_names(record: dict[str, Any]) -> set[str]:
    tech = record.get("builtwith_tech") or record.get("technology_highlights")
    parsed = _parse_jsonish_briefs(tech)
    out: set[str] = set()
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                name = item.get("name") or item.get("value")
                if isinstance(name, str) and name.strip():
                    out.add(name.strip())
            elif isinstance(item, str) and item.strip():
                out.add(item.strip())
    return out


def _score_peer_ai(record: dict[str, Any]) -> dict[str, Any]:
    industries = {s.casefold() for s in _extract_industries(record)}
    tech = {s.casefold() for s in _extract_tech_names(record)}

    has_ai_industry = any(
        k in " ".join(sorted(industries))
        for k in ("artificial intelligence", "machine learning", "generative ai", "llm", "ai")
    )
    has_ai_tech = any(any(k in t for t in tech) for k in AI_TECH_KEYWORDS)
    has_modern_stack = any(any(k in t for t in tech) for k in DATA_TECH_KEYWORDS + AI_TECH_KEYWORDS)

    signals = {
        "ai_ml_roles": 0,
        "engineering_roles": 0,
        "has_named_ai_leadership": False,
        "github_ai_activity": 0,
        "exec_ai_commentary": bool(has_ai_industry),
        "modern_ml_stack": bool(has_modern_stack),
        "strategic_ai_communications": bool(has_ai_industry and has_ai_tech),
    }
    return ai_maturity.score_ai_maturity(signals)


def _percentile(prospect_score: int, peer_scores: list[int]) -> int:
    if not peer_scores:
        return 50
    below = sum(1 for s in peer_scores if s < prospect_score)
    return int(round(100 * below / max(1, len(peer_scores))))


def _derive_gaps(target: dict[str, Any], peers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_tech = {t.casefold() for t in _extract_tech_names(target)}
    target_ind = {i.casefold() for i in _extract_industries(target)}

    features = [
        ("ai_tech_stack", AI_TECH_KEYWORDS),
        ("data_stack", DATA_TECH_KEYWORDS),
        ("modern_cloud", MODERN_CLOUD_KEYWORDS),
    ]

    # Identify top quartile peers by ai_maturity.score
    scores = sorted([p.get("ai_maturity", {}).get("score", 0) for p in peers if isinstance(p, dict)])
    if not scores:
        return []
    q3 = scores[int(0.75 * (len(scores) - 1))]

    top = [p for p in peers if (p.get("ai_maturity", {}).get("score", 0) >= q3)]

    gaps: list[dict[str, Any]] = []
    for name, keywords in features:
        top_has = 0
        for p in top:
            feats = p.get("features") if isinstance(p, dict) else None
            if isinstance(feats, dict) and feats.get(name) is True:
                top_has += 1

        prevalence = top_has / max(1, len(top))
        target_has = any(any(k in t for t in target_tech) for k in keywords) or any(
            k in " ".join(sorted(target_ind)) for k in keywords
        )
        if target_has or prevalence < 0.6:
            continue

        confidence = "high" if prevalence >= 0.8 else "medium"
        sample_peers = [p.get("name") for p in top[:3] if isinstance(p.get("name"), str)]
        gaps.append(
            {
                "gap": name,
                "confidence": confidence,
                "evidence": {
                    "top_quartile_prevalence": round(prevalence, 2),
                    "sample_peers": sample_peers,
                },
                "pitch_hook": _pitch_hook(name, sample_peers),
            }
        )

    return gaps[:3]


def _compute_features(record: dict[str, Any]) -> dict[str, bool]:
    tech = {s.casefold() for s in _extract_tech_names(record)}
    ind = {s.casefold() for s in _extract_industries(record)}
    ind_text = " ".join(sorted(ind))

    def has_any(keywords: tuple[str, ...]) -> bool:
        return any(any(k in t for t in tech) for k in keywords) or any(k in ind_text for k in keywords)

    return {
        "ai_tech_stack": has_any(AI_TECH_KEYWORDS),
        "data_stack": has_any(DATA_TECH_KEYWORDS),
        "modern_cloud": has_any(MODERN_CLOUD_KEYWORDS),
    }


def _pitch_hook(gap: str, sample_peers: list[str]) -> str:
    peers = ", ".join(sample_peers) if sample_peers else "peers at your stage"
    if gap == "ai_tech_stack":
        return f"Several top peers ({peers}) show clear AI platform footprints — worth comparing what that looks like in practice."
    if gap == "data_stack":
        return f"Top peers ({peers}) tend to invest earlier in a modern data stack — that often unlocks faster AI iteration later."
    if gap == "modern_cloud":
        return f"Top peers ({peers}) often standardize on modern cloud primitives — it’s a common enabler for reliable delivery velocity."
    return "Peers in your cohort show a repeatable practice that may be worth benchmarking."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce competitor_gap_brief.json")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--out-dir", default="data/briefs", help="Output directory for briefs")
    parser.add_argument("--peers", type=int, default=10, help="Max peers")
    args = parser.parse_args(argv)

    hiring = produce_hiring_signal_brief(args.company)
    hiring_path = write_hiring_signal_brief_file(hiring, out_dir=args.out_dir)
    brief = produce_competitor_gap_brief(args.company, hiring_brief=hiring, peers_limit=args.peers)
    path = write_competitor_gap_brief_file(brief, out_dir=args.out_dir)

    print(json.dumps({"hiring_brief": str(hiring_path), "competitor_gap_brief": str(path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
