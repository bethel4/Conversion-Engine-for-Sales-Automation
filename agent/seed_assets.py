from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SEED_ROOT = REPO_ROOT / "data" / "processed" / "seed"

ICP_DEFINITION_PATH = SEED_ROOT / "icp_definition.md"
STYLE_GUIDE_PATH = SEED_ROOT / "style_guide.md"
BENCH_SUMMARY_PATH = SEED_ROOT / "bench_summary.json"
PRICING_SHEET_PATH = SEED_ROOT / "pricing_sheet.md"
CASE_STUDIES_PATH = SEED_ROOT / "case_studies.md"
SALES_DECK_NOTES_PATH = SEED_ROOT / "sales_deck_notes.md"


def canonical_seed_files() -> dict[str, Path]:
    return {
        "icp.md": ICP_DEFINITION_PATH,
        "icp_definition.md": ICP_DEFINITION_PATH,
        "style_guide.md": STYLE_GUIDE_PATH,
        "bench_summary.json": BENCH_SUMMARY_PATH,
        "pricing_sheet.md": PRICING_SHEET_PATH,
        "case_studies.md": CASE_STUDIES_PATH,
        "sales_deck_notes.md": SALES_DECK_NOTES_PATH,
    }


@lru_cache(maxsize=1)
def load_icp_rules() -> dict[str, Any]:
    text = ICP_DEFINITION_PATH.read_text(encoding="utf-8")
    return {
        "segment_1": {
            "funding_window_days": _extract_number(
                text,
                r"Closed a Series A or Series B round in the last \*\*(\d+)\s+days\*\*",
                default=180,
            ),
            "headcount_min": _extract_number(
                text,
                r"Headcount \*\*(\d+)[–-](\d+)\*\* per LinkedIn or Crunchbase",
                default=15,
            ),
            "headcount_max": _extract_number(
                text,
                r"Headcount \*\*(\d+)[–-](\d+)\*\* per LinkedIn or Crunchbase",
                default=80,
                group=2,
            ),
            "min_engineering_roles": _extract_number_word(
                text,
                r"At least \*\*([A-Za-z0-9]+)\s+open engineering roles\*\*",
                default=5,
            ),
            "layoff_override_days": _extract_number(
                text,
                r"Layoff event in the last \*\*(\d+)\s+days\*\* of more than \*\*15%",
                default=90,
            ),
            "layoff_override_pct": _extract_percent(
                text,
                r"Layoff event in the last \*\*\d+\s+days\*\* of more than \*\*(\d+)%",
                default=0.15,
            ),
        },
        "segment_2": {
            "layoff_window_days": _extract_number(
                text,
                r"Layoff event in the last \*\*(\d+)\s+days\*\* per layoffs\.fyi",
                default=120,
            ),
            "min_headcount": _extract_number(text, r"headcount \*\*(\d+)[–-](\d[\d,]*)\*\*\.", default=200, group=1),
            "max_headcount": _extract_number(
                text,
                r"headcount \*\*(\d+)[–-](\d[\d,]*)\*\*\.",
                default=2000,
                group=2,
            ),
            "min_engineering_roles": 3,
            "max_layoff_pct": _extract_percent(text, r"Layoff percentage above \*\*(\d+)%\*\*", default=0.4),
        },
        "segment_3": {
            "leadership_window_days": _extract_number(
                text,
                r"appointed in the last \*\*(\d+)\s+days\*\* per Crunchbase People",
                default=90,
            ),
            "headcount_min": _extract_number(text, r"Headcount \*\*(50)[–-](\d+)\*\*", default=50),
            "headcount_max": _extract_number(
                text,
                r"Headcount \*\*(50)[–-](\d+)\*\*",
                default=500,
                group=2,
            ),
        },
        "segment_4": {
            "min_ai_maturity": _extract_number(text, r"AI-readiness score\s+(\d+)\s+or above", default=2),
        },
        "classification_priority": [
            "segment_2",
            "segment_3",
            "segment_4",
            "segment_1",
            "abstain",
        ],
    }


@lru_cache(maxsize=1)
def load_style_guide_rules() -> dict[str, Any]:
    text = STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    markers = re.findall(r"### \d+\.\s+([A-Za-z-]+)", text)
    return {
        "markers": [marker.strip().casefold().replace("-", "_") for marker in markers],
        "max_cold_email_words": _extract_number(text, r"Max\s+(\d+)\s+words"),
        "max_subject_chars": _extract_number(text, r"Subject line under\s+(\d+)"),
        "disallowed_subject_starts": ("quick", "just", "hey"),
        "required_subject_starts": ("request", "follow-up", "context", "question"),
        "disallowed_jargon": ("bench",),
        "disallowed_cliches": (
            "top talent",
            "world-class",
            "a-players",
            "rockstar",
            "ninja",
        ),
        "reengagement_banned": ("following up again", "circling back"),
    }


@lru_cache(maxsize=1)
def load_bench_summary() -> dict[str, Any]:
    return json.loads(BENCH_SUMMARY_PATH.read_text(encoding="utf-8"))


def load_bench_counts() -> dict[str, int]:
    data = load_bench_summary()
    stacks = data.get("stacks", {}) if isinstance(data, dict) else {}
    counts: dict[str, int] = {}
    for stack, payload in stacks.items():
        if isinstance(stack, str) and isinstance(payload, dict):
            counts[stack] = int(payload.get("available_engineers", 0) or 0)
    return counts


def _extract_number(text: str, pattern: str, default: int = 0, group: int = 1) -> int:
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return default
    return int(match.group(group).replace(",", ""))


def _extract_percent(text: str, pattern: str, default: float = 0.0) -> float:
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return default
    return int(match.group(1)) / 100.0


def _extract_number_word(text: str, pattern: str, default: int = 0) -> int:
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return default
    token = match.group(1).casefold()
    if token.isdigit():
        return int(token)
    return {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }.get(token, default)
