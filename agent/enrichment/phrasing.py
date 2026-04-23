from __future__ import annotations

import argparse
import json
import re
from typing import Any


BANNED_LOW_CONFIDENCE = (
    "aggressive",
    "rapidly",
    "exploding",
    "surging",
    "tripling",
    "skyrocketing",
    "massive growth",
)

MULTIPLIER_PATTERNS = (
    r"\b\d+(\.\d+)?x\b",
    r"\b\d+(\.\d+)?\s*×\b",
    r"\btripled\b",
    r"\bdoubled\b",
)


def phrase_with_confidence(
    claim_template: str | dict[str, str],
    evidence: dict[str, Any] | None,
    confidence_level: str,
) -> str:
    """
    Generates language matched to evidence confidence:
      - high: assert
      - medium: hedge with observable fact
      - low: ask instead of assert
      - none: open question

    `claim_template` can be:
      - str: formatted with evidence via `str.format(**evidence)`
      - dict: keys high/medium/low/none -> explicit templates
    """

    evidence = evidence or {}
    level = (confidence_level or "none").casefold()
    if isinstance(claim_template, dict):
        template = (
            claim_template.get(level)
            or claim_template.get("none")
            or next(iter(claim_template.values()), "")
        )
        return _safe_format(template, evidence)

    formatted = _safe_format(claim_template, evidence)

    if level == "high":
        return formatted
    if level == "medium":
        return _hedge(formatted)
    if level == "low":
        return _ask_from_evidence(evidence) or _ask(formatted)
    return _open_question_from_evidence(evidence) or _open_question()


def audit_overclaiming(email_text: str, confidence_level: str) -> dict[str, Any]:
    """
    Returns {ok, issues[]} for tone safety.
    """

    text = (email_text or "")
    level = (confidence_level or "none").casefold()
    issues: list[str] = []

    if level in {"low", "none"}:
        t = text.casefold()
        for w in BANNED_LOW_CONFIDENCE:
            if w in t:
                issues.append(f"banned_word:{w}")
        for pat in MULTIPLIER_PATTERNS:
            if re.search(pat, t):
                issues.append("multiplier_claim")
                break

    return {"ok": len(issues) == 0, "issues": issues}


def _safe_format(template: str, evidence: dict[str, Any]) -> str:
    try:
        return template.format(**evidence)
    except Exception:
        return template


def _hedge(sentence: str) -> str:
    s = sentence.strip()
    if not s:
        return ""
    if s[0].islower():
        s = s[0].upper() + s[1:]
    return f"It looks like {s[0].lower() + s[1:]}" if not s.casefold().startswith("it looks like") else s


def _ask(sentence: str) -> str:
    s = sentence.strip().rstrip(".")
    if not s:
        return "Are you finding it hard to hire at the pace you need?"
    # Convert assertion-ish sentence into a question.
    return f"Are you finding it hard to {s[0].lower() + s[1:]}?"


def _open_question() -> str:
    return "What does your current engineering capacity situation look like?"


def _ask_from_evidence(evidence: dict[str, Any]) -> str | None:
    eng = evidence.get("engineering_roles")
    if isinstance(eng, int) and eng >= 2:
        return "Are you finding it harder to hire engineering talent at the pace your roadmap needs?"
    return None


def _open_question_from_evidence(evidence: dict[str, Any]) -> str | None:
    if "engineering_roles" in evidence:
        return "How are you thinking about engineering capacity right now?"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Confidence-aware phrasing helper")
    parser.add_argument("--template", required=True, help="Claim template (Python format string)")
    parser.add_argument("--confidence", default="none", help="high|medium|low|none")
    parser.add_argument("--evidence-json", default="{}", help="Evidence JSON dict for formatting")
    args = parser.parse_args(argv)

    evidence = json.loads(args.evidence_json)
    text = phrase_with_confidence(args.template, evidence, args.confidence)
    audit = audit_overclaiming(text, args.confidence)
    print(json.dumps({"text": text, "audit": audit}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
