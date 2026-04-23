from __future__ import annotations

from typing import Any


def score_ai_maturity(signals: dict[str, Any]) -> dict[str, Any]:
    """
    Scores AI maturity 0–3 using multiple weak signals.

    Input signals (best-effort; missing keys treated as absent):
      - ai_ml_roles, engineering_roles
      - has_head_of_ai (bool)
      - github_ai_repos (int)
      - exec_llm_mentions (bool)
      - ai_product_on_site (bool)
      - ai_case_studies (bool)

    Returns:
      { score, confidence, evidence_count, justification, pitch_language_hint }
    """

    per_signal: dict[str, dict[str, Any]] = {}

    ai_roles = _as_int(signals.get("ai_ml_roles"))
    eng_roles = _as_int(signals.get("engineering_roles"))
    ratio = (ai_roles / eng_roles) if eng_roles and eng_roles > 0 else 0.0

    # 1) Hiring for AI/ML roles (high weight)
    points = 0.0
    if ai_roles >= 5 or ratio >= 0.35:
        points = 1.0
        weight = "high"
    elif ai_roles >= 2 or ratio >= 0.2:
        points = 0.5
        weight = "medium"
    elif ai_roles >= 1:
        points = 0.25
        weight = "low"
    else:
        weight = "none"
    per_signal["ai_hiring"] = {
        "points": points,
        "weight": weight,
        "evidence": {"ai_ml_roles": ai_roles, "engineering_roles": eng_roles, "ratio": round(ratio, 3)},
    }

    # 2) Leadership: Head of AI / ML (high)
    per_signal["ai_leadership"] = _bool_signal(
        bool(signals.get("has_head_of_ai")),
        points=1.0,
        weight="high",
        evidence={"has_head_of_ai": bool(signals.get("has_head_of_ai"))},
    )

    # 3) GitHub AI repos (medium)
    github_repos = _as_int(signals.get("github_ai_repos"))
    per_signal["github_ai_activity"] = _threshold_signal(
        github_repos,
        high=(5, 1.0),
        medium=(1, 0.5),
        low=(0, 0.0),
        evidence={"github_ai_repos": github_repos},
    )

    # 4) Exec mentions of LLM/AI (medium)
    per_signal["exec_mentions"] = _bool_signal(
        bool(signals.get("exec_llm_mentions")),
        points=0.5,
        weight="medium",
        evidence={"exec_llm_mentions": bool(signals.get("exec_llm_mentions"))},
    )

    # 5) AI product positioning on site (medium)
    per_signal["ai_product"] = _bool_signal(
        bool(signals.get("ai_product_on_site")),
        points=0.5,
        weight="medium",
        evidence={"ai_product_on_site": bool(signals.get("ai_product_on_site"))},
    )

    # 6) AI case studies / customers (low)
    per_signal["ai_case_studies"] = _bool_signal(
        bool(signals.get("ai_case_studies")),
        points=0.25,
        weight="low",
        evidence={"ai_case_studies": bool(signals.get("ai_case_studies"))},
    )

    raw = sum(v["points"] for v in per_signal.values())
    evidence_count = sum(1 for v in per_signal.values() if v["points"] > 0)

    score = _map_raw_to_score(raw)
    confidence = "high" if evidence_count >= 4 else "medium" if evidence_count >= 2 else "low"

    hint = (
        "assert"
        if confidence == "high"
        else "hedge"
        if confidence == "medium"
        else "ask"
    )

    return {
        "score": score,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "justification": {"raw_points": round(raw, 3), "per_signal": per_signal},
        "pitch_language_hint": hint,
    }


def _map_raw_to_score(raw: float) -> int:
    if raw >= 2.5:
        return 3
    if raw >= 1.5:
        return 2
    if raw >= 0.5:
        return 1
    return 0


def _as_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(value)
    except Exception:
        return 0


def _bool_signal(flag: bool, *, points: float, weight: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"points": points if flag else 0.0, "weight": weight if flag else "none", "evidence": evidence}


def _threshold_signal(
    value: int,
    *,
    high: tuple[int, float],
    medium: tuple[int, float],
    low: tuple[int, float],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if value >= high[0]:
        return {"points": high[1], "weight": "high", "evidence": evidence}
    if value >= medium[0]:
        return {"points": medium[1], "weight": "medium", "evidence": evidence}
    return {"points": low[1], "weight": "none", "evidence": evidence}

