from __future__ import annotations

from typing import Any

from agent.seed_assets import load_style_guide_rules


APOLOGETIC_TERMS = ("sorry", "apologize", "apologies")
DEFENSIVE_TERMS = ("actually", "frankly", "to be honest", "obviously")
GENERIC_CONSULTING_TERMS = (
    "leverage",
    "best-in-class",
    "synergy",
    "digital transformation",
    "end-to-end",
)


def score_tone(text: str) -> dict[str, Any]:
    """
    Lightweight voice check backed by the Tenacious style guide seed file.
    Higher scores favor concise, direct, grounded, professional language.
    """

    rules = load_style_guide_rules()
    raw = (text or "").strip()
    lowered = raw.casefold()
    issues: list[str] = []
    score = 1.0

    for term in APOLOGETIC_TERMS:
        if term in lowered:
            score -= 0.12
            issues.append(f"apologetic:{term}")

    for term in DEFENSIVE_TERMS:
        if term in lowered:
            score -= 0.08
            issues.append(f"defensive:{term}")

    for term in GENERIC_CONSULTING_TERMS:
        if term in lowered:
            score -= 0.1
            issues.append(f"generic:{term}")

    word_count = len(raw.split())
    max_words = int(rules.get("max_cold_email_words", 120))
    if word_count > max_words:
        score -= 0.2
        issues.append("over_explaining")
    elif word_count > 55:
        score -= 0.1
        issues.append("slightly_long")

    if "?" not in raw:
        score -= 0.05
        issues.append("no_question")

    for jargon in rules.get("disallowed_jargon", ()):
        if jargon in lowered:
            score -= 0.16
            issues.append(f"prospect_jargon:{jargon}")

    for cliche in rules.get("disallowed_cliches", ()):
        if cliche in lowered:
            score -= 0.16
            issues.append(f"cliche:{cliche}")

    for phrase in rules.get("reengagement_banned", ()):
        if phrase in lowered:
            score -= 0.08
            issues.append(f"reengagement_tone:{phrase}")

    if not any(token in lowered for token in ("team", "engineer", "delivery", "roadmap", "hire")):
        score -= 0.05
        issues.append("low_specificity")

    score = max(0.0, min(1.0, round(score, 3)))
    return {"score": score, "ok": score >= 0.7, "issues": issues}


def score_turns(turns: list[str]) -> list[dict[str, Any]]:
    return [{"turn": idx + 1, **score_tone(text)} for idx, text in enumerate(turns)]
