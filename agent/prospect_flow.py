from __future__ import annotations

from typing import Any


def build_thread_id(company_name: str | None) -> str | None:
    if not isinstance(company_name, str) or not company_name.strip():
        return None
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in company_name.strip())
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_")
    if not slug:
        return None
    return f"thread_{slug}_001"


def build_event_context(
    *,
    prospect_email: str | None,
    identity: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    identity = identity or {}
    company_name = identity.get("company_name")
    thread_id = identity.get("thread_id") or build_thread_id(company_name)
    out: dict[str, Any] = {}

    if isinstance(company_name, str) and company_name.strip():
        out["company_name"] = company_name.strip()
    if isinstance(prospect_email, str) and prospect_email.strip():
        out["prospect_email"] = prospect_email.strip()
    if isinstance(thread_id, str) and thread_id.strip():
        out["thread_id"] = thread_id.strip()
    if isinstance(extra, dict):
        out.update(extra)
    return out


def build_booking_link_followup_text(segment: str, booking_link: str) -> str:
    safe_segment = (segment or "").strip().casefold()
    if safe_segment == "abstain":
        return (
            "Thanks — based on the public signals we found, it may be worth a short discovery call. "
            f"You can book time here: {booking_link}"
        )
    return (
        "Thanks for the reply. Based on the public signals we found, it may be worth a short discovery call. "
        f"You can book time here: {booking_link}"
    )
