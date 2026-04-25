from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from agent.seed_assets import load_icp_rules


def classify_icp(
    hiring_brief: dict[str, Any],
    *,
    threshold: float = 0.60,
) -> dict[str, Any]:
    """
    Lightweight ICP classifier with abstention.

    Segments:
      - segment_1: recently funded (Series A/B)
      - segment_2: restructuring / layoffs
      - segment_3: leadership change (CTO/VP Eng)
      - segment_4: AI capability gap (requires ai_maturity.score >= 2)
    """

    funding = hiring_brief.get("funding", {}) if isinstance(hiring_brief.get("funding"), dict) else {}
    jobs = hiring_brief.get("jobs", {}) if isinstance(hiring_brief.get("jobs"), dict) else {}
    layoffs = hiring_brief.get("layoffs", {}) if isinstance(hiring_brief.get("layoffs"), dict) else {}
    leadership = (
        hiring_brief.get("leadership_change", {})
        if isinstance(hiring_brief.get("leadership_change"), dict)
        else {}
    )
    ai = hiring_brief.get("ai_maturity", {}) if isinstance(hiring_brief.get("ai_maturity"), dict) else {}
    company = hiring_brief.get("company", {}) if isinstance(hiring_brief.get("company"), dict) else {}
    rules = load_icp_rules()

    disqualifiers: dict[str, Any] = {}

    s1, s1_blocked = _score_segment_1(funding, layoffs, jobs, company, rules["segment_1"])
    if s1_blocked:
        disqualifiers["segment_1"] = s1_blocked
    s2, s2_blocked = _score_segment_2(layoffs, jobs, company, rules["segment_2"])
    if s2_blocked:
        disqualifiers["segment_2"] = s2_blocked
    s3, s3_blocked = _score_segment_3(leadership, company, rules["segment_3"])
    if s3_blocked:
        disqualifiers["segment_3"] = s3_blocked
    s4, s4_blocked = _score_segment_4(ai, rules["segment_4"])
    if s4_blocked:
        disqualifiers["segment_4"] = "ai_maturity_below_2"

    scores = {
        "segment_1": s1,
        "segment_2": s2,
        "segment_3": s3,
        "segment_4": s4,
    }
    best_segment = max(scores, key=scores.get)
    best_score = scores[best_segment]

    segment = best_segment if best_score >= threshold else "abstain"
    pitch_angle = _pitch_angle(segment)

    reasoning = {
        "funding": _summarize_signal(funding, keys=("funded", "days_ago", "round_type", "confidence")),
        "jobs": _summarize_signal(jobs, keys=("engineering_roles", "ai_ml_roles", "velocity_60d", "signal_strength")),
        "layoffs": _summarize_signal(layoffs, keys=("had_layoff", "days_ago", "percentage_cut", "confidence")),
        "leadership_change": _summarize_signal(leadership, keys=("new_leader_detected", "role", "days_ago", "confidence")),
        "ai_maturity": _summarize_signal(ai, keys=("score", "confidence", "evidence_count")),
    }

    return {
        "segment": segment,
        "confidence": round(float(best_score), 3),
        "scores": {k: round(float(v), 3) for k, v in scores.items()},
        "pitch_angle": pitch_angle,
        "reasoning": reasoning,
        "disqualifiers": disqualifiers,
    }


def _score_segment_1(
    funding: dict[str, Any],
    layoffs: dict[str, Any],
    jobs: dict[str, Any],
    company: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[float, str | None]:
    if funding.get("funded") is not True:
        return 0.05, "not_recently_funded"

    funding_days = funding.get("days_ago")
    if isinstance(funding_days, int) and funding_days > int(rules.get("funding_window_days", 180)):
        return 0.1, "funding_outside_window"

    round_type = (funding.get("round_type") or "").casefold()
    if round_type and not any(k in round_type for k in ("series a", "series b", "series_a", "series_b")):
        # Unknown round type; keep but lower.
        round_factor = 0.4
    else:
        round_factor = 1.0

    conf = funding.get("confidence")
    base = {"high": 0.9, "medium": 0.7, "low": 0.55}.get(conf, 0.5)

    employee_count = _employee_count(company.get("num_employees"))
    min_headcount = int(rules.get("headcount_min", 15))
    max_headcount = int(rules.get("headcount_max", 80))
    if employee_count is not None and not (min_headcount <= employee_count <= max_headcount):
        base -= 0.2

    min_engineering_roles = int(rules.get("min_engineering_roles", 5))
    engineering_roles = jobs.get("engineering_roles")
    if isinstance(engineering_roles, int) and engineering_roles < min_engineering_roles:
        base -= 0.1

    # Layoffs disqualifier/penalty sourced from the ICP seed doc.
    layoff_window = int(rules.get("layoff_override_days", 90))
    layoff_pct = float(rules.get("layoff_override_pct", 0.15))
    if (
        layoffs.get("had_layoff") is True
        and isinstance(layoffs.get("days_ago"), int)
        and layoffs["days_ago"] <= layoff_window
        and float(layoffs.get("percentage_cut") or 0.0) > layoff_pct
    ):
        return 0.0, "recent_major_layoff"
    if layoffs.get("had_layoff") is True:
        return max(0.0, base - 0.4) * round_factor, None

    return max(0.0, base * round_factor), None


def _score_segment_2(
    layoffs: dict[str, Any],
    jobs: dict[str, Any],
    company: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[float, str | None]:
    if layoffs.get("had_layoff") is not True:
        return 0.15, "no_layoff_signal"
    layoff_days = layoffs.get("days_ago")
    if isinstance(layoff_days, int) and layoff_days > int(rules.get("layoff_window_days", 120)):
        return 0.2, "layoff_outside_window"
    if float(layoffs.get("percentage_cut") or 0.0) > float(rules.get("max_layoff_pct", 0.4)):
        return 0.1, "layoff_too_deep"
    engineering_roles = jobs.get("engineering_roles")
    min_engineering_roles = int(rules.get("min_engineering_roles", 3))
    if isinstance(engineering_roles, int) and engineering_roles < min_engineering_roles:
        conf = layoffs.get("confidence")
        base = {"high": 0.75, "medium": 0.65, "low": 0.6}.get(conf, 0.65)
        return base, "post_layoff_hiring_frozen"
    conf = layoffs.get("confidence")
    score = {"high": 0.95, "medium": 0.8, "low": 0.6}.get(conf, 0.75)
    employee_count = _employee_count(company.get("num_employees"))
    if employee_count is not None:
        min_headcount = int(rules.get("min_headcount", 200))
        max_headcount = int(rules.get("max_headcount", 2000))
        if not (min_headcount <= employee_count <= max_headcount):
            score -= 0.2
    return max(0.0, score), None


def _score_segment_3(
    leadership: dict[str, Any],
    company: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[float, str | None]:
    if leadership.get("new_leader_detected") is not True:
        return 0.1, "no_leadership_change"
    if isinstance(leadership.get("days_ago"), int) and leadership["days_ago"] > int(
        rules.get("leadership_window_days", 90)
    ):
        return 0.2, "leadership_change_outside_window"
    role = (leadership.get("role") or "").casefold()
    if role and role not in {"cto", "vp engineering", "vp_eng", "vp of engineering"}:
        return 0.3, "non_qualifying_leader_role"
    conf = leadership.get("confidence")
    score = {"high": 0.9, "medium": 0.75, "low": 0.6}.get(conf, 0.7)
    employee_count = _employee_count(company.get("num_employees"))
    if employee_count is not None:
        min_headcount = int(rules.get("headcount_min", 50))
        max_headcount = int(rules.get("headcount_max", 500))
        if not (min_headcount <= employee_count <= max_headcount):
            score -= 0.15
    return max(0.0, score), None


def _score_segment_4(ai: dict[str, Any], rules: dict[str, Any]) -> tuple[float, bool]:
    score = ai.get("score")
    if not isinstance(score, int):
        score = 0
    if score < int(rules.get("min_ai_maturity", 2)):
        return 0.0, True

    conf = ai.get("confidence")
    conf_factor = {"high": 1.0, "medium": 0.85, "low": 0.7}.get(conf, 0.8)

    # Score 2 -> 0.7, score 3 -> 0.85
    base = 0.7 + (0.15 * max(0, min(1, score - 2)))
    return base * conf_factor, False


def _pitch_angle(segment: str) -> str:
    return {
        "segment_1": "fresh_funding_scale_execution",
        "segment_2": "cost_pressure_do_more_with_less",
        "segment_3": "new_leader_vendor_strategy_window",
        "segment_4": "ai_capability_gap_platform_enablement",
        "abstain": "exploratory_generic",
    }.get(segment, "exploratory_generic")


def _summarize_signal(signal: dict[str, Any], *, keys: tuple[str, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in keys:
        if k in signal:
            out[k] = signal.get(k)
    return out


def _employee_count(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    digits = [int(item) for item in re.findall(r"\d+", value)]
    if not digits:
        return None
    matches = digits
    if len(matches) == 1:
        return matches[0]
    return round(sum(matches[:2]) / 2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify ICP segment from hiring_signal_brief.json")
    parser.add_argument("--brief", required=True, help="Path to hiring_signal_brief JSON")
    parser.add_argument("--threshold", type=float, default=0.60, help="Abstention threshold")
    args = parser.parse_args(argv)

    brief = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    result = classify_icp(brief, threshold=args.threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
