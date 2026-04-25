from __future__ import annotations

from typing import Any


def score_ai_maturity(signals: dict[str, Any]) -> dict[str, Any]:
    """
    Act II: Score AI maturity (0–3) with per-signal justification.

    This output is used to:
    - Gate Segment 4 entirely (score must be >= 2)
    - Control phrasing (assert vs hedge vs ask) based on confidence

    Scoring uses 6 signals with weights (high/medium/low). Points are summed then mapped
    to a 0–3 integer score. A full `justification.per_signal` is returned so the composer
    can cite evidence without overclaiming.

    Input signals (best-effort; missing keys treated as absent):
      - ai_ml_roles, engineering_roles
      - has_named_ai_leadership (bool)
      - github_ai_activity (int)
      - exec_ai_commentary (bool)
      - modern_ml_stack (bool)
      - strategic_ai_communications (bool)

    Returns:
      { score, confidence, evidence_count, justification, pitch_language_hint }
    """

    per_signal: dict[str, dict[str, Any]] = {}

    ai_roles = _as_int(signals.get("ai_ml_roles"))
    eng_roles = _as_int(signals.get("engineering_roles"))
    ratio = (ai_roles / eng_roles) if eng_roles and eng_roles > 0 else 0.0

    # 1) AI-adjacent open roles (high weight)
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
    per_signal["ai_adjacent_open_roles"] = {
        "points": points,
        "weight": weight,
        "evidence": {"ai_ml_roles": ai_roles, "engineering_roles": eng_roles, "ratio": round(ratio, 3)},
    }

    # 2) Named AI/ML leadership (high)
    leadership_flag = bool(signals.get("has_named_ai_leadership", signals.get("has_head_of_ai")))
    per_signal["named_ai_ml_leadership"] = _bool_signal(
        leadership_flag,
        points=1.0,
        weight="high",
        evidence={"has_named_ai_leadership": leadership_flag},
    )

    # 3) Public GitHub org activity (medium)
    github_activity = _as_int(signals.get("github_ai_activity", signals.get("github_ai_repos")))
    per_signal["public_github_org_activity"] = _threshold_signal(
        github_activity,
        high=(5, 1.0),
        medium=(1, 0.5),
        low=(0, 0.0),
        evidence={"github_ai_activity": github_activity},
    )

    # 4) Executive commentary (medium)
    exec_commentary_flag = bool(signals.get("exec_ai_commentary", signals.get("exec_llm_mentions")))
    per_signal["executive_commentary"] = _bool_signal(
        exec_commentary_flag,
        points=0.5,
        weight="medium",
        evidence={"exec_ai_commentary": exec_commentary_flag},
    )

    # 5) Modern data / ML stack (low)
    modern_stack_flag = bool(signals.get("modern_ml_stack", signals.get("ai_product_on_site")))
    per_signal["modern_data_ml_stack"] = _bool_signal(
        modern_stack_flag,
        points=0.5,
        weight="low",
        evidence={"modern_ml_stack": modern_stack_flag},
    )

    # 6) Strategic communications (low)
    strategic_flag = bool(signals.get("strategic_ai_communications", signals.get("ai_case_studies")))
    per_signal["strategic_communications"] = _bool_signal(
        strategic_flag,
        points=0.25,
        weight="low",
        evidence={"strategic_ai_communications": strategic_flag},
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
