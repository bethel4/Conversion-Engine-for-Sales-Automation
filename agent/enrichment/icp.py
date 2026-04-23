from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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

    disqualifiers: dict[str, Any] = {}

    s1 = _score_segment_1(funding, layoffs)
    s2 = _score_segment_2(layoffs)
    s3 = _score_segment_3(leadership)
    s4, s4_blocked = _score_segment_4(ai)
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


def _score_segment_1(funding: dict[str, Any], layoffs: dict[str, Any]) -> float:
    if funding.get("funded") is not True:
        return 0.05

    round_type = (funding.get("round_type") or "").casefold()
    if round_type and not any(k in round_type for k in ("series_a", "series_b", "venture", "seed", "series")):
        # Unknown round type; keep but lower.
        round_factor = 0.85
    else:
        round_factor = 1.0

    conf = funding.get("confidence")
    base = {"high": 0.9, "medium": 0.7, "low": 0.55}.get(conf, 0.5)

    # Layoffs disqualifier/penalty
    if layoffs.get("had_layoff") is True:
        return max(0.0, base - 0.4) * round_factor

    return base * round_factor


def _score_segment_2(layoffs: dict[str, Any]) -> float:
    if layoffs.get("had_layoff") is not True:
        return 0.15
    conf = layoffs.get("confidence")
    return {"high": 0.95, "medium": 0.8, "low": 0.6}.get(conf, 0.75)


def _score_segment_3(leadership: dict[str, Any]) -> float:
    if leadership.get("new_leader_detected") is not True:
        return 0.1
    conf = leadership.get("confidence")
    return {"high": 0.9, "medium": 0.75, "low": 0.6}.get(conf, 0.7)


def _score_segment_4(ai: dict[str, Any]) -> tuple[float, bool]:
    score = ai.get("score")
    if not isinstance(score, int):
        score = 0
    if score < 2:
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
