from __future__ import annotations

import re
from typing import Any

CONFIDENCE_THRESHOLD = 0.60


def classify_icp(brief: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_brief(brief)
    funding = normalized.get("funding", {}) if isinstance(normalized.get("funding"), dict) else {}
    layoffs = normalized.get("layoffs", {}) if isinstance(normalized.get("layoffs"), dict) else {}
    leadership = normalized.get("leadership_change", {}) if isinstance(normalized.get("leadership_change"), dict) else {}
    ai = normalized.get("ai_maturity", {}) if isinstance(normalized.get("ai_maturity"), dict) else {}
    company = normalized.get("company", {}) if isinstance(normalized.get("company"), dict) else {}
    jobs = normalized.get("jobs", {}) if isinstance(normalized.get("jobs"), dict) else {}

    emp = int(company.get("employee_count") or company.get("num_employees_numeric") or 0)

    scores: dict[str, float] = {}

    s1 = 0.0
    if funding.get("funded") and str(funding.get("round_type") or "") in {"series_a", "series_b", "seed"}:
        s1 += 0.5
        if int(funding.get("days_ago") or 999) < 90:
            s1 += 0.3
        if 15 <= emp <= 80:
            s1 += 0.2
        if layoffs.get("had_layoff"):
            s1 -= 0.4
    scores["segment_1"] = round(s1, 2)

    s2 = 0.0
    if 200 <= emp <= 2000:
        s2 += 0.4
    if layoffs.get("had_layoff") and int(layoffs.get("days_ago") or 999) < 120:
        s2 += 0.5
    elif funding.get("funded") is False and emp > 200:
        s2 += 0.1
    scores["segment_2"] = round(s2, 2)

    s3 = 0.0
    if leadership.get("new_leader_detected"):
        s3 += 0.7
        if int(leadership.get("days_ago") or 999) < 60:
            s3 += 0.2
        elif int(leadership.get("days_ago") or 999) < 90:
            s3 += 0.1
    scores["segment_3"] = round(s3, 2)

    s4 = 0.0
    ai_score = int(ai.get("score") or 0)
    if ai_score >= 2:
        s4 += 0.5
        if ai_score == 3:
            s4 += 0.3
        if int(jobs.get("ai_ml_roles") or 0) >= 3:
            s4 += 0.2
    scores["segment_4"] = round(s4, 2)

    best_segment = max(scores, key=scores.get)
    best_confidence = scores[best_segment]
    if best_confidence < CONFIDENCE_THRESHOLD:
        return {
            "segment": "abstain",
            "confidence": best_confidence,
            "scores": scores,
            "pitch_angle": "exploratory: what engineering challenges are you prioritizing?",
            "reasoning": f"Highest segment score {best_confidence} below threshold {CONFIDENCE_THRESHOLD}",
            "abstain_reason": "Insufficient signal for confident segment classification",
        }

    return {
        "segment": best_segment,
        "confidence": best_confidence,
        "scores": scores,
        "primary_signal": _primary_signal(normalized, best_segment),
        "disqualifiers": _disqualifiers(normalized, best_segment),
        "pitch_angle": _pitch_angle(normalized, best_segment),
        "reasoning": _build_reasoning(normalized, scores),
        "abstain_reason": None,
    }


def _normalize_brief(brief: dict[str, Any]) -> dict[str, Any]:
    out = dict(brief)
    company = dict(brief.get("company", {})) if isinstance(brief.get("company"), dict) else {}
    numeric_count = _employee_count(company.get("employee_count") or company.get("num_employees"))
    if "num_employees" not in company and "employee_count" in company:
        value = company.get("employee_count")
        company["num_employees"] = value if isinstance(value, str) else str(value)
    company["num_employees_numeric"] = numeric_count
    if "employee_count" not in company:
        company["employee_count"] = numeric_count
    out["company"] = company
    return out


def _employee_count(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = [int(part) for part in re.findall(r"\d+", value)]
        if not digits:
            return 0
        if len(digits) == 1:
            return digits[0]
        return round(sum(digits[:2]) / 2)
    return 0


def _primary_signal(brief: dict[str, Any], segment: str) -> str:
    if segment == "segment_1":
        f = brief.get("funding", {})
        round_type = str(f.get("round_type") or "?").replace("series_", "series_")
        return f"{round_type}_funded_{f.get('days_ago', '?')}_days_ago"
    if segment == "segment_2":
        return f"layoff_{brief.get('layoffs', {}).get('days_ago', '?')}_days_ago"
    if segment == "segment_3":
        lead = brief.get("leadership_change", {})
        return f"new_leader_{lead.get('role', 'cto')}_{lead.get('days_ago', '?')}_days_ago"
    if segment == "segment_4":
        return f"ai_maturity_score_{brief.get('ai_maturity', {}).get('score', '?')}"
    return "unknown"


def _disqualifiers(brief: dict[str, Any], segment: str) -> list[str]:
    out: list[str] = []
    if segment == "segment_1" and brief.get("layoffs", {}).get("had_layoff"):
        out.append("post-layoff company — use segment_2 pitch instead")
    if segment == "segment_4" and int(brief.get("ai_maturity", {}).get("score") or 0) < 2:
        out.append("ai_maturity < 2 — do not pitch capability gap")
    return out


def _pitch_angle(brief: dict[str, Any], segment: str) -> str:
    funding = brief.get("funding", {})
    ai = brief.get("ai_maturity", {})
    return {
        "segment_1": f"scale engineering output faster than recruiting allows — {funding.get('round_type', 'recent')} funding creates the window",
        "segment_2": "replace higher-cost roles with offshore equivalents without cutting delivery capacity",
        "segment_3": "new leadership window: reassess offshore mix and vendor strategy early",
        "segment_4": f"specialized {ai.get('pitch_language_hint', 'AI capability')} without full-time hiring risk",
    }.get(segment, "exploratory_generic")


def _build_reasoning(brief: dict[str, Any], scores: dict[str, Any]) -> str:
    parts: list[str] = []
    funding = brief.get("funding", {})
    if funding.get("funded"):
        amount = float(funding.get("amount_usd") or 0)
        parts.append(f"Closed ${amount / 1e6:.1f}M {funding.get('round_type', '')} {funding.get('days_ago', '?')} days ago.")
    jobs = brief.get("jobs", {})
    if int(jobs.get("engineering_roles") or 0) > 0:
        parts.append(f"{jobs.get('engineering_roles')} open engineering roles ({jobs.get('signal_strength', '?')} velocity).")
    ai = brief.get("ai_maturity", {})
    parts.append(f"AI maturity: {ai.get('score', 0)}/3 ({ai.get('confidence', '?')} confidence).")
    parts.append(f"All segment scores: {scores}")
    return " ".join(parts)
