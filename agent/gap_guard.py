from __future__ import annotations

import re
from typing import Any


FABRICATION_PATTERNS = (
    r"\bcompetitors?\b.*\bahead\b",
    r"\btop peers?\b.*\bwhile you\b",
    r"\bfall(ing)? behind\b",
    r"\byou(?:'re| are) not\b",
    r"\bbetterco\b",
    r"\bscaleco\b",
)

CONDESCENDING_TERMS = (
    "clearly ahead",
    "behind your competitors",
    "falling behind",
    "while you are not",
    "while you're not",
    "you lag",
    "you are behind",
)


def audit_gap_claim(email_text: str, competitor_gap_brief: dict[str, Any] | None) -> dict[str, Any]:
    """
    Returns {ok, issues[]} for competitor-gap grounding and tone.
    """

    text = (email_text or "").strip()
    lowered = text.casefold()
    brief = competitor_gap_brief or {}
    gaps = brief.get("gaps") if isinstance(brief.get("gaps"), list) else []
    issues: list[str] = []

    if not gaps:
        for pattern in FABRICATION_PATTERNS:
            if re.search(pattern, lowered):
                issues.append("fabricated_gap_claim")
                break

    for term in CONDESCENDING_TERMS:
        if term in lowered:
            issues.append(f"condescending_gap_framing:{term}")

    return {"ok": len(issues) == 0, "issues": issues}
