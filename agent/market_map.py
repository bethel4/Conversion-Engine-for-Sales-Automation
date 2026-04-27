from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from agent.bench_gate import SKILL_ALIASES
from agent.enrichment.crunchbase import (
    is_recently_funded,
    load_crunchbase_dataset,
    normalize_company_name,
)
from agent.seed_assets import load_bench_counts


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET_PATH = REPO_ROOT / "data" / "raw" / "crunchbase" / "crunchbase-companies-information.csv"
DEFAULT_MANUAL_LABELS_PATH = REPO_ROOT / "data" / "processed" / "market_map" / "manual_labels.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "market_map"
DEFAULT_METHOD_PATH = REPO_ROOT / "method.md"
READINESS_LABELS = {0: "dormant", 1: "emerging", 2: "active", 3: "leading"}

STRONG_AI_KEYWORDS = (
    "artificial intelligence",
    "machine learning",
    "generative ai",
    "genai",
    "large language model",
    "llm",
    "computer vision",
    "deep learning",
    "neural network",
    "ai agent",
    "predictive analytics",
)
MEDIUM_AI_KEYWORDS = (
    "automation",
    "analytics",
    "data science",
    "data platform",
    "data pipeline",
    "intelligent",
    "recommendation",
    "forecasting",
    "natural language",
    "nlp",
    "mlops",
    "chatbot",
)
AI_INDUSTRY_KEYWORDS = (
    "artificial intelligence",
    "machine learning",
    "big data",
    "analytics",
    "data",
    "developer platform",
    "developer apis",
)

SECTOR_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Fintech", ("fintech", "financial", "payments", "banking", "insurance", "lending", "wealth", "risk")),
    ("Healthcare", ("health", "medical", "biotech", "pharma", "clinical")),
    ("Cybersecurity", ("security", "cybersecurity", "identity", "threat")),
    ("E-commerce", ("e-commerce", "ecommerce", "retail", "marketplace", "shopping")),
    ("MarTech", ("marketing", "advertising", "sales", "crm", "customer engagement")),
    ("DevTools", ("developer", "devops", "software", "api", "cloud", "infrastructure", "it services")),
    ("Telecom", ("telecommunications", "telecom", "wireless", "networking")),
    ("Manufacturing", ("manufacturing", "industrial", "robotics", "automotive", "hardware")),
    ("Education", ("education", "edtech", "learning", "training")),
    ("Logistics", ("logistics", "supply chain", "transport", "mobility", "fleet")),
    ("Real Estate", ("real estate", "property", "proptech", "construction")),
    ("Energy", ("energy", "climate", "solar", "battery", "utilities")),
    ("Media", ("media", "content", "gaming", "video", "music", "social media")),
]

SECTOR_SIGNAL_HINTS = {
    "Fintech": ("risk and data-platform pressure", "Lead with model-risk, underwriting, or analytics throughput."),
    "Healthcare": ("workflow automation and data quality", "Lead with regulated data workflows and delivery capacity."),
    "Cybersecurity": ("alert fatigue and platform scale", "Lead with detection engineering, data pipelines, and platform velocity."),
    "E-commerce": ("conversion, personalization, and data plumbing", "Lead with experimentation velocity and customer-data workflows."),
    "MarTech": ("revenue automation and segmentation", "Lead with campaign data quality and AI-assisted ops."),
    "DevTools": ("platform build-out and engineering leverage", "Lead with backend, data, and AI-platform staffing signals."),
    "Telecom": ("network ops and legacy data integration", "Lead with data engineering and platform modernization."),
    "Manufacturing": ("automation and operational analytics", "Lead with data pipelines, forecasting, and process visibility."),
    "Education": ("content automation and learner analytics", "Lead with personalization, content ops, and product analytics."),
    "Logistics": ("forecasting and operational coordination", "Lead with data platform, optimization, and dashboard delivery."),
    "Real Estate": ("workflow digitization and portfolio data", "Lead with operational reporting and internal tooling."),
    "Energy": ("asset monitoring and forecasting", "Lead with data engineering and predictive operations."),
    "Media": ("content operations and audience analytics", "Lead with recommendation, experimentation, and content workflows."),
    "Other": ("mixed operating signals", "Lead with the strongest public signal in the brief before expanding scope."),
}


def analyze_market_map(
    *,
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    manual_labels_path: str | Path | None = DEFAULT_MANUAL_LABELS_PATH,
) -> dict[str, Any]:
    records = load_crunchbase_dataset(dataset_path)
    bench_counts = load_bench_counts()
    as_of_date = _dataset_as_of(records)
    scored_records = [_score_record(record, bench_counts=bench_counts, as_of_date=as_of_date) for record in records]

    score_distribution = Counter(item["ai_readiness_score"] for item in scored_records)
    sector_summary = _build_sector_summary(scored_records)
    market_space = _build_market_space(scored_records)
    top_cells = _rank_top_cells(scored_records)

    report: dict[str, Any] = {
        "dataset_path": str(Path(dataset_path)),
        "dataset_row_count": len(records),
        "as_of_date": as_of_date.isoformat(),
        "score_distribution": {
            str(score): {
                "label": READINESS_LABELS[score],
                "count": score_distribution.get(score, 0),
                "share": round(score_distribution.get(score, 0) / len(records), 4) if records else 0.0,
            }
            for score in range(4)
        },
        "sector_summary": sector_summary,
        "market_space": market_space,
        "top_cells": top_cells,
    }

    if manual_labels_path and Path(manual_labels_path).exists():
        report["validation"] = validate_market_map(
            scored_records=scored_records,
            manual_labels_path=manual_labels_path,
        )

    return report


def quick_ai_score(record: dict[str, Any]) -> dict[str, Any]:
    text = _record_text(record)
    industries = _extract_industries(record)
    industry_text = " ".join(industries)

    strong_hits = [keyword for keyword in STRONG_AI_KEYWORDS if keyword in text or keyword in industry_text]
    medium_hits = [keyword for keyword in MEDIUM_AI_KEYWORDS if keyword in text or keyword in industry_text]
    industry_hits = [keyword for keyword in AI_INDUSTRY_KEYWORDS if keyword in industry_text]

    if len(strong_hits) >= 2 or (strong_hits and (medium_hits or industry_hits)):
        score = 3
    elif len(strong_hits) >= 1 or len(medium_hits) >= 2 or len(industry_hits) >= 2:
        score = 2
    elif medium_hits or industry_hits:
        score = 1
    else:
        score = 0

    matched = sorted(set(strong_hits + medium_hits + industry_hits))
    return {
        "score": score,
        "label": READINESS_LABELS[score],
        "matched_keywords": matched,
    }


def validate_market_map(
    *,
    scored_records: list[dict[str, Any]],
    manual_labels_path: str | Path,
) -> dict[str, Any]:
    labels = json.loads(Path(manual_labels_path).read_text(encoding="utf-8"))
    if not isinstance(labels, list):
        raise ValueError("Manual labels file must contain a list")

    record_index = {normalize_company_name(item["company_name"]): item for item in scored_records}
    confusion = [[0 for _ in range(4)] for _ in range(4)]
    evaluated: list[dict[str, Any]] = []

    for entry in labels:
        if not isinstance(entry, dict):
            continue
        company = str(entry.get("company") or "")
        manual_score = int(entry.get("manual_score"))
        if manual_score not in READINESS_LABELS:
            raise ValueError(f"Unsupported manual score for {company}: {manual_score}")
        record = record_index.get(normalize_company_name(company))
        if record is None:
            raise ValueError(f"Manual label company not found in dataset: {company}")
        predicted = int(record["ai_readiness_score"])
        confusion[manual_score][predicted] += 1
        evaluated.append(
            {
                "company": company,
                "manual_score": manual_score,
                "manual_label": READINESS_LABELS[manual_score],
                "predicted_score": predicted,
                "predicted_label": READINESS_LABELS[predicted],
                "notes": entry.get("notes"),
                "matched_keywords": record.get("matched_ai_keywords", []),
            }
        )

    per_band: dict[str, Any] = {}
    precision_values: list[float] = []
    recall_values: list[float] = []
    for score, label in READINESS_LABELS.items():
        tp = confusion[score][score]
        fp = sum(confusion[row][score] for row in range(4) if row != score)
        fn = sum(confusion[score][col] for col in range(4) if col != score)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        precision_values.append(precision)
        recall_values.append(recall)
        per_band[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "support": sum(confusion[score]),
        }

    sample_size = len(evaluated)
    exact_matches = sum(confusion[i][i] for i in range(4))
    accuracy = exact_matches / sample_size if sample_size else 0.0
    ci_low, ci_high = _wilson_interval(exact_matches, sample_size)

    return {
        "sample_size": sample_size,
        "macro_precision": round(mean(precision_values), 3) if precision_values else 0.0,
        "macro_recall": round(mean(recall_values), 3) if recall_values else 0.0,
        "exact_match_accuracy": round(accuracy, 3),
        "accuracy_95_ci": [round(ci_low, 3), round(ci_high, 3)],
        "per_band": per_band,
        "confusion_matrix": confusion,
        "evaluated_companies": evaluated,
        "known_false_positive_modes": [
            "Marketing copy that says AI or analytics without clear evidence of an actual AI product or team.",
            "Services firms that mention automation capabilities but do not show sustained AI-readiness signals.",
        ],
        "known_false_negative_modes": [
            "Stealth or services-heavy companies with sparse public descriptions and no explicit AI vocabulary.",
            "Domain-specific data platforms that look operationally advanced but avoid AI terminology in public copy.",
        ],
    }


def write_market_map_report(report: dict[str, Any], *, out_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    target = out_path / "market_map_report.json"
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return target


def write_market_space_csv(report: dict[str, Any], *, out_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    target = out_path / "market_space.csv"
    fieldnames = [
        "sector",
        "size_band",
        "ai_readiness",
        "companies",
        "avg_funding",
        "bench_match",
        "funded_last_12m",
        "combined_score",
        "lead_signal",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for cell in report.get("market_space", []):
            writer.writerow(
                {
                    "sector": cell["sector"],
                    "size_band": cell["size_band"],
                    "ai_readiness": f"{cell['ai_readiness_label']} ({cell['ai_readiness_score']})",
                    "companies": cell["company_count"],
                    "avg_funding": _format_usd(cell["avg_funding_usd_12m"]),
                    "bench_match": f"{cell['avg_bench_match_score']:.2f}",
                    "funded_last_12m": cell["funded_last_12m_count"],
                    "combined_score": f"{cell['combined_score']:.3f}",
                    "lead_signal": cell["lead_signal"],
                }
            )
    return target


def write_top_cells_markdown(report: dict[str, Any], *, out_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    target = out_path / "top_cells.md"
    lines = [
        "# Top Cells",
        "",
        f"As of {report.get('as_of_date')}, the strongest outbound cells in the Crunchbase batch are:",
        "",
    ]
    for idx, cell in enumerate(report.get("top_cells", []), start=1):
        lines.extend(
            [
                f"## {idx}. {cell['sector']} | {cell['size_band']} | {cell['ai_readiness_label']} ({cell['ai_readiness_score']})",
                "",
                f"- Companies: {cell['company_count']}",
                f"- Avg funding: {_format_usd(cell['avg_funding_usd_12m'])}",
                f"- Bench match: {cell['avg_bench_match_score']:.2f}",
                f"- Funded last 12 months: {cell['funded_last_12m_count']}",
                f"- Why it is attractive: {cell['narrative']}",
                f"- Outbound recommendation: {cell['outbound_recommendation']}",
                "",
            ]
        )
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return target


def write_method_markdown(report: dict[str, Any], *, target_path: str | Path = DEFAULT_METHOD_PATH) -> Path:
    target = Path(target_path)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    section = _render_market_map_method_section(report)
    start_marker = "<!-- market-map:start -->"
    end_marker = "<!-- market-map:end -->"
    block = f"{start_marker}\n{section}\n{end_marker}\n"

    if start_marker in existing and end_marker in existing:
        prefix, rest = existing.split(start_marker, 1)
        _, suffix = rest.split(end_marker, 1)
        updated = prefix.rstrip() + "\n\n" + block + suffix.lstrip("\n")
    else:
        updated = existing.rstrip() + ("\n\n" if existing.strip() else "") + block

    target.write_text(updated, encoding="utf-8")
    return target


def write_market_map_bundle(report: dict[str, Any], *, out_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, Path]:
    return {
        "report_json": write_market_map_report(report, out_dir=out_dir),
        "market_space_csv": write_market_space_csv(report, out_dir=out_dir),
        "top_cells_md": write_top_cells_markdown(report, out_dir=out_dir),
        "method_md": write_method_markdown(report),
    }


def _score_record(record: dict[str, Any], *, bench_counts: dict[str, int], as_of_date: date) -> dict[str, Any]:
    score = quick_ai_score(record)
    funding = is_recently_funded(record, days=365, today=as_of_date)
    sector = _extract_sector(record)
    size_band = _size_band(record.get("num_employees"))
    bench_match = _bench_match_score(record, bench_counts=bench_counts)
    return {
        "company_name": record.get("name") or record.get("company_name") or "Unknown",
        "sector": sector,
        "size_band": size_band,
        "ai_readiness_score": score["score"],
        "ai_readiness_label": score["label"],
        "matched_ai_keywords": score["matched_keywords"],
        "funded_last_12m": bool(funding.get("funded")),
        "funding_amount_usd_12m": int(funding.get("amount_usd") or 0) if funding.get("funded") else 0,
        "bench_match_score": round(bench_match["score"], 3),
        "bench_match_stacks": bench_match["matched_stacks"],
        "lead_signal": _lead_signal(score=score["score"], funded=bool(funding.get("funded")), sector=sector),
    }


def _build_sector_summary(scored_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scored_records:
        grouped[item["sector"]].append(item)

    summary = []
    for sector, items in grouped.items():
        if len(items) < 5:
            continue
        ai_ready = [item for item in items if item["ai_readiness_score"] >= 2]
        summary.append(
            {
                "sector": sector,
                "company_count": len(items),
                "ai_ready_count": len(ai_ready),
                "ai_ready_share": round(len(ai_ready) / len(items), 4) if items else 0.0,
                "avg_bench_match_score": round(mean(item["bench_match_score"] for item in items), 3) if items else 0.0,
            }
        )

    return sorted(summary, key=lambda item: (-item["ai_ready_share"], -item["company_count"], item["sector"]))[:12]


def _build_market_space(scored_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for item in scored_records:
        if item["size_band"] == "unknown":
            continue
        grouped[(item["sector"], item["size_band"], item["ai_readiness_score"])].append(item)

    rows = []
    for (sector, size_band, readiness_score), items in grouped.items():
        population = len(items)
        avg_funding = mean(item["funding_amount_usd_12m"] for item in items) if items else 0.0
        avg_bench_match = mean(item["bench_match_score"] for item in items) if items else 0.0
        funded_count = sum(1 for item in items if item["funded_last_12m"])
        combined_score = min(population / 20, 1.0) * 0.3 + min(avg_funding / 10_000_000, 1.0) * 0.3 + avg_bench_match * 0.4
        lead_signal = Counter(item["lead_signal"] for item in items).most_common(1)[0][0]
        rows.append(
            {
                "sector": sector,
                "size_band": size_band,
                "ai_readiness_score": readiness_score,
                "ai_readiness_label": READINESS_LABELS[readiness_score],
                "company_count": population,
                "funded_last_12m_count": funded_count,
                "avg_funding_usd_12m": round(avg_funding, 2),
                "avg_bench_match_score": round(avg_bench_match, 3),
                "combined_score": round(combined_score, 3),
                "lead_signal": lead_signal,
            }
        )

    return sorted(
        rows,
        key=lambda item: (-item["combined_score"], -item["company_count"], item["sector"], item["size_band"], item["ai_readiness_score"]),
    )


def _rank_top_cells(scored_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for cell in _build_market_space(scored_records):
        if cell["ai_readiness_score"] <= 0:
            continue
        if cell["company_count"] < 3:
            continue
        narrative = _cell_narrative(
            sector=cell["sector"],
            size_band=cell["size_band"],
            readiness_label=cell["ai_readiness_label"],
            population=cell["company_count"],
            funded_count=cell["funded_last_12m_count"],
            avg_funding=cell["avg_funding_usd_12m"],
            avg_bench_match=cell["avg_bench_match_score"],
            lead_signal=cell["lead_signal"],
        )
        ranked.append(
            {
                **cell,
                "narrative": narrative,
                "outbound_recommendation": _outbound_recommendation(
                    sector=cell["sector"],
                    size_band=cell["size_band"],
                    readiness_label=cell["ai_readiness_label"],
                    lead_signal=cell["lead_signal"],
                ),
            }
        )

    return sorted(ranked, key=lambda item: (-item["combined_score"], -item["company_count"], item["sector"]))[:5]


def _cell_narrative(
    *,
    sector: str,
    size_band: str,
    readiness_label: str,
    population: int,
    funded_count: int,
    avg_funding: float,
    avg_bench_match: float,
    lead_signal: str,
) -> str:
    why_buy, lead_hint = SECTOR_SIGNAL_HINTS.get(sector, SECTOR_SIGNAL_HINTS["Other"])
    return (
        f"{sector} companies in the {size_band} band with {readiness_label} AI-readiness form a cell of {population} accounts. "
        f"{funded_count} were funded in the last 12 months and average recent funding is ${avg_funding:,.0f}. "
        f"Bench match averages {avg_bench_match:.0%}, so Tenacious can credibly sell into this cell around {why_buy}; "
        f"lead signal: {lead_signal}. {lead_hint}"
    )


def _outbound_recommendation(*, sector: str, size_band: str, readiness_label: str, lead_signal: str) -> str:
    _, lead_hint = SECTOR_SIGNAL_HINTS.get(sector, SECTOR_SIGNAL_HINTS["Other"])
    return (
        f"Prioritize {size_band} accounts in {sector} with {readiness_label} readiness. "
        f"Open with {lead_signal}, then pivot to Tenacious capacity proof and a concrete delivery wedge. {lead_hint}"
    )


def _bench_match_score(record: dict[str, Any], *, bench_counts: dict[str, int]) -> dict[str, Any]:
    text = _record_text(record)
    matched_stacks = []
    for stack, aliases in SKILL_ALIASES.items():
        if any(alias in text for alias in aliases):
            matched_stacks.append(stack)

    industries = _extract_industries(record)
    industry_text = " ".join(industries)
    if not matched_stacks and ("analytics" in industry_text or "data" in industry_text):
        matched_stacks.extend(["python", "data"])
    if not matched_stacks and ("software" in industry_text or "developer" in industry_text):
        matched_stacks.extend(["python", "frontend"])
    if not matched_stacks and ("ai" in industry_text or "machine learning" in industry_text):
        matched_stacks.extend(["ml", "python"])

    matched_stacks = sorted(set(stack for stack in matched_stacks if stack in bench_counts))
    capacity = sum(bench_counts.get(stack, 0) for stack in matched_stacks)
    score = min(capacity / 24.0, 1.0)
    return {"score": score, "matched_stacks": matched_stacks}


def _extract_sector(record: dict[str, Any]) -> str:
    text = _record_text(record)
    industries = _extract_industries(record)
    combined = " ".join(industries) + " " + text
    for sector, keywords in SECTOR_RULES:
        if any(keyword in combined for keyword in keywords):
            return sector
    if industries:
        return industries[0].title()
    return "Other"


def _size_band(value: Any) -> str:
    text = str(value or "").strip()
    mapping = {
        "1-10": "micro (1-10)",
        "11-50": "small (11-50)",
        "51-100": "growth (51-100)",
        "101-250": "growth (101-250)",
        "251-500": "mid-market (251-500)",
        "501-1000": "mid-market (501-1000)",
        "1001-5000": "enterprise (1001-5000)",
        "5001-10000": "enterprise (5001-10000)",
        "10001+": "enterprise (10001+)",
    }
    return mapping.get(text, "unknown")


def _lead_signal(*, score: int, funded: bool, sector: str) -> str:
    if funded and score >= 2:
        return "recent funding plus AI-readiness"
    if score >= 2:
        return "AI-readiness signals"
    if funded:
        return "recent funding"
    if sector in SECTOR_SIGNAL_HINTS:
        return SECTOR_SIGNAL_HINTS[sector][0]
    return "broad operational signal"


def _extract_industries(record: dict[str, Any]) -> list[str]:
    raw = _parse_jsonish(record.get("industries"))
    if isinstance(raw, list):
        values = []
        for item in raw:
            if isinstance(item, dict):
                value = item.get("value") or item.get("name")
                if isinstance(value, str) and value.strip():
                    values.append(value.strip().casefold())
            elif isinstance(item, str) and item.strip():
                values.append(item.strip().casefold())
        return values
    if isinstance(raw, str) and raw.strip():
        return [raw.strip().casefold()]
    return []


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower() == "null":
        return None
    if text.startswith("[") or text.startswith("{"):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _record_text(record: dict[str, Any]) -> str:
    parts = [
        str(record.get("about") or ""),
        str(record.get("full_description") or ""),
        " ".join(_extract_industries(record)),
        _builtwith_text(record),
    ]
    return " ".join(part.casefold() for part in parts if part).strip()


def _builtwith_text(record: dict[str, Any]) -> str:
    parsed = _parse_jsonish(record.get("builtwith_tech"))
    if not isinstance(parsed, list):
        return ""
    out = []
    for item in parsed:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                out.append(name.strip())
    return " ".join(out)


def _dataset_as_of(records: list[dict[str, Any]]) -> date:
    timestamps = []
    for record in records:
        raw = str(record.get("timestamp") or "").strip()
        if not raw:
            continue
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                timestamps.append(datetime.strptime(raw, fmt).date())
                break
            except ValueError:
                continue
    return max(timestamps) if timestamps else date.today()


def _wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    phat = successes / total
    denominator = 1 + z * z / total
    center = phat + z * z / (2 * total)
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total)
    return max(0.0, (center - margin) / denominator), min(1.0, (center + margin) / denominator)


def _format_usd(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def _render_market_map_method_section(report: dict[str, Any]) -> str:
    validation = report.get("validation") if isinstance(report.get("validation"), dict) else None
    lines = [
        "## Market Map Validation Snapshot",
        "",
        "This section is generated from `agent.market_map` and summarizes the batch market-space scoring outputs.",
        "",
        "### Dataset",
        "",
        f"- Source: `{report.get('dataset_path')}`",
        f"- Companies scored: {report.get('dataset_row_count')}",
        f"- Dataset as of: {report.get('as_of_date')}",
        "",
        "### Scoring Logic",
        "",
        "- AI readiness is scored from 0 to 3 using keyword and industry evidence from company descriptions, industries, and named technologies.",
        "- Sector is assigned with deterministic keyword rules over industries and company text.",
        "- Size band is derived from Crunchbase employee ranges.",
        "- Recent funding uses the last 12 months of disclosed rounds.",
        "- Bench match estimates how well the company stack aligns with Tenacious bench supply.",
        "",
        "### Cell Ranking",
        "",
        "- Cells are grouped by `sector + size_band + ai_readiness`.",
        "- Cells with fewer than 3 companies are dropped from priority ranking.",
        "- Combined score weights population, average recent funding, and bench match.",
        "",
    ]
    if validation:
        lines.extend(
            [
                "### Validation",
                "",
                f"- Manual label sample size: {validation.get('sample_size')}",
                f"- Macro precision: {validation.get('macro_precision')}",
                f"- Macro recall: {validation.get('macro_recall')}",
                f"- Exact-match accuracy: {validation.get('exact_match_accuracy')}",
                f"- 95% CI for accuracy: {validation.get('accuracy_95_ci')}",
                "",
                "#### Per-Band Metrics",
                "",
                "| Band | Precision | Recall | Support |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        per_band = validation.get("per_band", {})
        for band in ("dormant", "emerging", "active", "leading"):
            metrics = per_band.get(band, {})
            lines.append(
                f"| {band} | {metrics.get('precision', 0.0)} | {metrics.get('recall', 0.0)} | {metrics.get('support', 0)} |"
            )
        lines.extend(["", "#### Known False Positives", ""])
        for item in validation.get("known_false_positive_modes", []):
            lines.append(f"- {item}")
        lines.extend(["", "#### Known False Negatives", ""])
        for item in validation.get("known_false_negative_modes", []):
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a lightweight market map from the Crunchbase sample")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH), help="Crunchbase CSV/JSON dataset path")
    parser.add_argument("--manual-labels", default=str(DEFAULT_MANUAL_LABELS_PATH), help="Optional manual labels JSON path")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUTPUT_DIR), help="Output directory for report JSON")
    args = parser.parse_args(argv)

    labels_path: str | Path | None = args.manual_labels
    if isinstance(labels_path, str) and not labels_path.strip():
        labels_path = None

    report = analyze_market_map(dataset_path=args.dataset, manual_labels_path=labels_path)
    paths = write_market_map_bundle(report, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "dataset_row_count": report["dataset_row_count"],
                "report_json": str(paths["report_json"]),
                "market_space_csv": str(paths["market_space_csv"]),
                "top_cells_md": str(paths["top_cells_md"]),
                "method_md": str(paths["method_md"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
