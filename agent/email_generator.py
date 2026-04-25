from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.enrichment.phrasing import phrase_with_confidence
from agent.seed_assets import CASE_STUDIES_PATH, REPO_ROOT, SALES_DECK_NOTES_PATH, STYLE_GUIDE_PATH


EMAIL_SEQUENCES_DIR = REPO_ROOT / "data" / "processed" / "seed" / "email_sequences"
COLD_SEQUENCE_PATH = EMAIL_SEQUENCES_DIR / "cold.md"


def generate_outreach_email(
    *,
    company_name: str,
    prospect_name: str | None,
    qualification: dict[str, Any] | None,
    hiring_brief: dict[str, Any] | None,
    competitor_gap_brief: dict[str, Any] | None,
) -> dict[str, Any]:
    qualification = qualification or {}
    hiring_brief = hiring_brief or {}
    competitor_gap_brief = competitor_gap_brief or {}

    first_name = _first_name(prospect_name)
    segment = str(qualification.get("segment") or "abstain")
    confidence = float(qualification.get("confidence") or 0.0)
    pitch_angle = str(qualification.get("pitch_angle") or "exploratory_generic")

    seed_presence = {
        "style_guide": STYLE_GUIDE_PATH.exists(),
        "email_sequences": COLD_SEQUENCE_PATH.exists(),
        "case_studies": CASE_STUDIES_PATH.exists(),
        "sales_deck_notes": SALES_DECK_NOTES_PATH.exists(),
    }

    signal_facts = _signal_facts(hiring_brief, competitor_gap_brief)
    fallback = segment == "abstain" or confidence < 0.6
    subject = _build_subject(segment=segment, company_name=company_name, signal_facts=signal_facts, fallback=fallback)
    body = _build_body(
        first_name=first_name,
        company_name=company_name,
        segment=segment,
        confidence=confidence,
        pitch_angle=pitch_angle,
        signal_facts=signal_facts,
        fallback=fallback,
    )

    source = {
        "used_enrichment_data": bool(hiring_brief),
        "used_icp_segment": segment != "abstain",
        "used_ai_maturity_score": isinstance(hiring_brief.get("ai_maturity"), dict),
        "used_competitor_gap_brief": bool(competitor_gap_brief),
        "used_style_guide": seed_presence["style_guide"],
        "used_email_sequences": seed_presence["email_sequences"],
        "used_case_studies": seed_presence["case_studies"],
        "signals_used": signal_facts["signals_used"],
        "seed_files_loaded": {
            "style_guide.md": str(STYLE_GUIDE_PATH) if seed_presence["style_guide"] else None,
            "email_sequences/cold.md": str(COLD_SEQUENCE_PATH) if seed_presence["email_sequences"] else None,
            "case_studies.md": str(CASE_STUDIES_PATH) if seed_presence["case_studies"] else None,
            "sales_deck_notes.md": str(SALES_DECK_NOTES_PATH) if seed_presence["sales_deck_notes"] else None,
        },
        "fallback_reason": "low_icp_confidence" if fallback else None,
        "pitch_language_hint": hiring_brief.get("ai_maturity", {}).get("pitch_language_hint"),
        "generation_mode": "fallback_generic" if fallback else "signal_grounded",
    }

    return {
        "subject": subject,
        "text": body,
        "source": source,
        "warning": "This is a generic fallback email because ICP confidence is low." if fallback else None,
    }


def _first_name(prospect_name: str | None) -> str:
    if not isinstance(prospect_name, str) or not prospect_name.strip():
        return "there"
    return prospect_name.strip().split()[0]


def _signal_facts(hiring_brief: dict[str, Any], competitor_gap_brief: dict[str, Any]) -> dict[str, Any]:
    funding = hiring_brief.get("funding", {}) if isinstance(hiring_brief.get("funding"), dict) else {}
    jobs = hiring_brief.get("jobs", {}) if isinstance(hiring_brief.get("jobs"), dict) else {}
    layoffs = hiring_brief.get("layoffs", {}) if isinstance(hiring_brief.get("layoffs"), dict) else {}
    leadership = hiring_brief.get("leadership_change", {}) if isinstance(hiring_brief.get("leadership_change"), dict) else {}
    ai = hiring_brief.get("ai_maturity", {}) if isinstance(hiring_brief.get("ai_maturity"), dict) else {}
    gaps = competitor_gap_brief.get("gaps") if isinstance(competitor_gap_brief.get("gaps"), list) else []

    signals_used: list[str] = []
    if funding.get("funded"):
        signals_used.append("funding")
    if jobs.get("engineering_roles") or jobs.get("ai_ml_roles"):
        signals_used.append("hiring")
    if layoffs.get("had_layoff"):
        signals_used.append("layoffs")
    if leadership.get("new_leader_detected"):
        signals_used.append("leadership change")
    if ai.get("score", 0) > 0:
        signals_used.append("AI maturity")

    primary_signal = None
    if funding.get("funded"):
        round_type = str(funding.get("round_type") or "funding").replace("_", " ")
        primary_signal = f"You closed a {round_type} round {funding.get('days_ago')} days ago."
    elif layoffs.get("had_layoff"):
        primary_signal = f"You had a public layoff event {layoffs.get('days_ago')} days ago."
    elif leadership.get("new_leader_detected"):
        primary_signal = f"You brought in a new {leadership.get('role') or 'leader'} {leadership.get('days_ago')} days ago."
    elif jobs.get("engineering_roles"):
        primary_signal = (
            f"We found {jobs.get('engineering_roles')} engineering roles open"
            f"{' including ' + str(jobs.get('ai_ml_roles')) + ' AI/ML roles' if jobs.get('ai_ml_roles') else ''}."
        )
    else:
        primary_signal = "We reviewed the public engineering and operating signals around your team."

    bottleneck = _bottleneck_line(funding=funding, jobs=jobs, layoffs=layoffs, leadership=leadership, ai=ai)
    service_line = _service_line(ai=ai, gaps=gaps)
    gap_line = None
    if gaps:
        first_gap = gaps[0]
        sample_peers = ", ".join(first_gap.get("evidence", {}).get("sample_peers", [])[:2])
        gap_line = (
            f"One peer-pattern we noticed: {str(first_gap.get('gap') or '').replace('_', ' ')}"
            + (f" shows up in peers like {sample_peers}." if sample_peers else ".")
        )

    return {
        "signals_used": signals_used,
        "primary_signal": primary_signal,
        "bottleneck": bottleneck,
        "service_line": service_line,
        "gap_line": gap_line,
        "ai_confidence": str(ai.get("_confidence") or ai.get("confidence") or "none"),
    }


def _build_subject(*, segment: str, company_name: str, signal_facts: dict[str, Any], fallback: bool) -> str:
    if fallback:
        return f"Question: engineering capacity at {company_name}"
    if segment == "segment_1":
        return f"Context: {company_name}'s recent funding"
    if segment == "segment_2":
        return f"Context: {company_name}'s restructuring window"
    if segment == "segment_3":
        return f"Question: leadership change at {company_name}"
    if segment == "segment_4":
        return f"Question: AI capability build at {company_name}"
    return f"Question: engineering capacity at {company_name}"


def _build_body(
    *,
    first_name: str,
    company_name: str,
    segment: str,
    confidence: float,
    pitch_angle: str,
    signal_facts: dict[str, Any],
    fallback: bool,
) -> str:
    signal_line = signal_facts["primary_signal"]
    if fallback:
        signal_line = phrase_with_confidence(
            "you are aggressively scaling your engineering team",
            {"engineering_roles": 0},
            "low",
        )

    lines = [
        f"{first_name},",
        "",
        signal_line,
        signal_facts["bottleneck"],
    ]
    if signal_facts.get("gap_line"):
        lines.append(signal_facts["gap_line"])
    lines.extend(
        [
            signal_facts["service_line"],
            "Worth 15 minutes next week to compare notes?",
            "",
            "Marcus",
            "Research Partner",
            "Tenacious Intelligence Corporation",
            "gettenacious.com",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


def _bottleneck_line(
    *,
    funding: dict[str, Any],
    jobs: dict[str, Any],
    layoffs: dict[str, Any],
    leadership: dict[str, Any],
    ai: dict[str, Any],
) -> str:
    if funding.get("funded"):
        return "Teams in that post-funding window usually hit an execution-capacity bottleneck before they hit a budget bottleneck."
    if layoffs.get("had_layoff"):
        return "After a restructure, the pressure is usually to keep delivery moving with a smaller team rather than add process overhead."
    if leadership.get("new_leader_detected"):
        return "The first quarter after a leadership change is usually when delivery model and vendor mix get reviewed."
    if ai.get("score", 0) >= 2:
        return "Companies showing this level of AI-readiness usually need delivery capacity around platform work, not generic staff augmentation."
    if jobs.get("engineering_roles", 0) >= 5:
        return "At that hiring pace, the bottleneck is usually recruiting throughput and delivery continuity."
    return "The useful question is whether your current engineering capacity matches the roadmap you need to ship."


def _service_line(*, ai: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    if ai.get("score", 0) >= 2:
        return "We plug in delivery-ready engineers across backend, data, and AI-adjacent platform work without turning the first call into a staffing pitch."
    if gaps:
        return "We usually help teams close that kind of delivery gap with a focused squad rather than a broad outsourcing program."
    return "We run delivery-ready engineering squads for teams that need execution help without expanding internal hiring cycles."
