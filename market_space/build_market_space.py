from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from agent.market_map import analyze_market_map


def build_market_space(crunchbase_data: list[dict[str, Any]], llm_client: Any | None = None) -> dict[str, Any]:
    report = analyze_market_map_from_records(crunchbase_data)
    out_dir = Path("market_space")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "market_space.csv"
    rows = report["cells"]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [
            "sector",
            "size_band",
            "ai_readiness_band",
            "cell_population",
            "avg_funding_12m_usd",
            "avg_hiring_velocity",
            "bench_match_score",
            "combined_score",
        ])
        writer.writeheader()
        writer.writerows(rows)
    return {"cells": len(rows), "top_cell": rows[0] if rows else None}


def analyze_market_map_from_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    tmp = Path("market_space/.tmp_records.json")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(records), encoding="utf-8")
    report = analyze_market_map(dataset_path=tmp, manual_labels_path=None)
    rows = []
    for cell in report.get("market_space", []):
        rows.append(
            {
                "sector": cell["sector"],
                "size_band": _size_band(cell["size_band"]),
                "ai_readiness_band": cell["ai_readiness_label"],
                "cell_population": cell["company_count"],
                "avg_funding_12m_usd": int(cell["avg_funding_usd_12m"]),
                "avg_hiring_velocity": "medium",
                "bench_match_score": round(cell["avg_bench_match_score"], 2),
                "combined_score": round(cell["combined_score"], 3),
            }
        )
    rows.sort(key=lambda row: row["combined_score"], reverse=True)
    return {"cells": rows}


def _size_band(value: str) -> str:
    if value.startswith("micro"):
        return "micro"
    if value.startswith("small"):
        return "small"
    if value.startswith("growth") or value.startswith("mid-market"):
        return "mid"
    if value.startswith("enterprise"):
        return "large"
    return "unknown"
