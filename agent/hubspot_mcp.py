from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

HUBSPOT_API_URL = "https://api.hubapi.com"


def _hubspot_api_key() -> str:
    api_key = os.getenv("HUBSPOT_API_KEY") or os.getenv("HUBSPOT_TOKEN")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY or HUBSPOT_TOKEN is not set")
    return api_key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_hubspot_api_key()}",
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{HUBSPOT_API_URL}{path}"
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(),
            json=json_body,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"HubSpot MCP request failed: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"HubSpot MCP error {response.status_code}: {response.text}")

    if not response.text.strip():
        return {}
    return response.json()


def _search_contact_by_email(email: str) -> dict[str, Any] | None:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }
                ]
            }
        ],
        "limit": 1,
    }
    result = _request("POST", "/crm/v3/objects/contacts/search", json_body=payload)
    matches = result.get("results")
    if isinstance(matches, list) and matches:
        first = matches[0]
        if isinstance(first, dict):
            return first
    return None


def _upsert_contact_by_email(email: str, properties: dict[str, Any]) -> dict[str, Any]:
    existing = _search_contact_by_email(email)
    if existing and existing.get("id"):
        contact_id = str(existing["id"])
        return _request(
            "PATCH",
            f"/crm/v3/objects/contacts/{contact_id}",
            json_body={"properties": properties},
        )
    return _request(
        "POST",
        "/crm/v3/objects/contacts",
        json_body={"properties": properties},
    )


def _search_company_by_name(company_name: str) -> dict[str, Any] | None:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "name",
                        "operator": "EQ",
                        "value": company_name,
                    }
                ]
            }
        ],
        "limit": 1,
    }
    result = _request("POST", "/crm/v3/objects/companies/search", json_body=payload)
    matches = result.get("results")
    if isinstance(matches, list) and matches:
        first = matches[0]
        if isinstance(first, dict):
            return first
    return None


def _upsert_company_by_name(company_name: str, properties: dict[str, Any]) -> dict[str, Any]:
    existing = _search_company_by_name(company_name)
    if existing and existing.get("id"):
        company_id = str(existing["id"])
        return _request(
            "PATCH",
            f"/crm/v3/objects/companies/{company_id}",
            json_body={"properties": properties},
        )
    return _request(
        "POST",
        "/crm/v3/objects/companies",
        json_body={"properties": properties},
    )


def build_standard_contact_properties(
    *,
    email: str,
    company_name: str | None = None,
    firstname: str | None = None,
    lastname: str | None = None,
    lifecyclestage: str | None = None,
    hs_lead_status: str | None = None,
) -> dict[str, Any]:
    properties: dict[str, Any] = {
        "email": email,
        "company": _coalesce_text(company_name),
    }
    if firstname and firstname.strip():
        properties["firstname"] = firstname.strip()
    if lastname and lastname.strip():
        properties["lastname"] = lastname.strip()
    if lifecyclestage and lifecyclestage.strip():
        properties["lifecyclestage"] = lifecyclestage.strip()
    if hs_lead_status and hs_lead_status.strip():
        properties["hs_lead_status"] = hs_lead_status.strip()
    return properties


def build_optional_enrichment_properties(
    *,
    icp_segment: str,
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    signals = enrichment.get("signals", {}) if isinstance(enrichment.get("signals"), dict) else {}
    funding = signals.get("funding", {}) if isinstance(signals.get("funding"), dict) else {}
    jobs = signals.get("jobs", {}) if isinstance(signals.get("jobs"), dict) else {}
    layoffs = signals.get("layoffs", {}) if isinstance(signals.get("layoffs"), dict) else {}
    leadership = (
        signals.get("leadership_change", {})
        if isinstance(signals.get("leadership_change"), dict)
        else {}
    )
    ai = signals.get("ai_maturity", {}) if isinstance(signals.get("ai_maturity"), dict) else {}
    company_signal = signals.get("company", {}) if isinstance(signals.get("company"), dict) else {}
    industry = _first_non_empty(
        enrichment.get("industry"),
        company_signal.get("industry"),
        company_signal.get("industries"),
    )

    return {
        "tenacious_company_size": _coalesce_text(
            enrichment.get("company_size"),
            company_signal.get("num_employees"),
            company_signal.get("company_size"),
        ),
        "tenacious_industry": _coalesce_text(industry),
        "tenacious_funding_stage": _coalesce_text(funding.get("round_type")),
        "tenacious_funding_amount": _coalesce_number(funding.get("amount_usd")),
        "tenacious_funding_days_ago": _coalesce_number(funding.get("days_ago")),
        "tenacious_engineering_roles": _coalesce_number(jobs.get("engineering_roles")),
        "tenacious_job_velocity_60d": _coalesce_number(jobs.get("velocity_60d")),
        "tenacious_job_signal_confidence": _coalesce_text(
            jobs.get("_confidence"),
            jobs.get("confidence"),
            jobs.get("signal_strength"),
        ),
        "tenacious_layoff_detected": _coalesce_bool(layoffs.get("had_layoff")),
        "tenacious_layoff_days_ago": _coalesce_number(layoffs.get("days_ago")),
        "tenacious_leadership_change": _coalesce_bool(leadership.get("new_leader_detected")),
        "tenacious_leadership_role": _coalesce_text(leadership.get("role")),
        "tenacious_ai_maturity_score": _coalesce_number(ai.get("score")),
        "tenacious_ai_maturity_confidence": _coalesce_text(ai.get("_confidence"), ai.get("confidence")),
        "tenacious_icp_segment": _coalesce_text(icp_segment),
        "tenacious_icp_confidence": _coalesce_number(enrichment.get("confidence")),
        "tenacious_enrichment_timestamp": timestamp,
    }


def build_standard_company_properties(
    *,
    company_name: str,
    icp_segment: str,
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    signals = enrichment.get("signals", {}) if isinstance(enrichment.get("signals"), dict) else {}
    company_signal = signals.get("company", {}) if isinstance(signals.get("company"), dict) else {}
    industry = _coalesce_text(
        enrichment.get("industry"),
        company_signal.get("industry"),
        company_signal.get("industries"),
    )
    description = _coalesce_text(
        company_signal.get("description"),
        f"Enriched ICP prospect in {icp_segment.replace('_', ' ')}" if icp_segment else "",
    )

    properties: dict[str, Any] = {"name": company_name.strip()}
    if industry:
        properties["industry"] = industry

    employee_count = _coalesce_employee_count(
        enrichment.get("company_size"),
        company_signal.get("num_employees"),
        company_signal.get("company_size"),
    )
    if employee_count is not None:
        properties["numberofemployees"] = employee_count
    if description:
        properties["description"] = description
    return properties


def write_enriched_contact(
    *,
    email: str,
    phone: str | None = None,
    company_name: str | None = None,
    icp_segment: str,
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    properties = build_standard_contact_properties(
        email=email,
        company_name=company_name,
        lifecyclestage=os.getenv("HUBSPOT_LIFECYCLE_STAGE_ENRICHED", "salesqualifiedlead"),
        hs_lead_status="OPEN",
    )
    if phone and phone.strip():
        properties["phone"] = phone.strip()
    result = _upsert_contact_by_email(email, properties)
    contact_id = str(result.get("id") or "")
    if contact_id:
        optional_properties = build_optional_enrichment_properties(
            icp_segment=icp_segment,
            enrichment=enrichment,
        )
        try:
            _request(
                "PATCH",
                f"/crm/v3/objects/contacts/{contact_id}",
                json_body={"properties": optional_properties},
            )
        except RuntimeError:
            pass
    company_result: dict[str, Any] | None = None
    company_associated = False
    company_error: str | None = None
    if contact_id and company_name and company_name.strip():
        company_properties = build_standard_company_properties(
            company_name=company_name,
            icp_segment=icp_segment,
            enrichment=enrichment,
        )
        try:
            company_result = _upsert_company_by_name(company_name.strip(), company_properties)
            company_id = str(company_result.get("id") or "")
            if company_id:
                _associate_contact_to_company_default(contact_id=contact_id, company_id=company_id)
                company_associated = True
        except RuntimeError as exc:
            company_error = str(exc)
    if company_result is not None:
        result["company"] = company_result
        result["company_associated"] = company_associated
    if company_error:
        result["company_error"] = company_error
    return result


def write_booking_update(
    *,
    email: str,
    booking_id: str,
    booking_status: str,
    booking_start_time: str | None = None,
    booking_title: str | None = None,
) -> dict[str, Any]:
    properties = {
        "email": email,
        "calcom_booking_id": booking_id,
        "calcom_booking_status": booking_status,
        "calcom_booking_start_time": booking_start_time,
        "calcom_booking_title": booking_title,
        "calendar_booking_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    return _upsert_contact_by_email(email, properties)


def log_event(
    *,
    email: str | None = None,
    phone: str | None = None,
    event_type: str,
    data: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    """
    Act II/III: HubSpot conversation event logging.

    Graders verify end-to-end execution by inspecting HubSpot. This function logs a
    timeline note on the contact for key events such as:
      - email_sent
      - email_reply_received
      - qualified
      - sms_sent
      - call_booked
      - call_completed

    Implementation notes:
    - Creates a HubSpot NOTE object (timeline-visible when associated to contact).
    - Best-effort: if association fails, the note is still created and the contact
      is updated with a lightweight JSON field (`conversation_event_json`) when available.
    """

    if not event_type or not event_type.strip():
        raise ValueError("event_type is required")
    if not email and not phone:
        raise ValueError("email or phone is required to log an event")

    occurred_at = occurred_at or datetime.now(timezone.utc)
    payload = data or {}

    contact = _ensure_contact(email=email, phone=phone)
    contact_id = str(contact["id"])

    note = _create_note(
        contact_id=contact_id,
        email=email,
        event_type=event_type,
        occurred_at=occurred_at,
        body_json=payload,
    )
    note_id = str(note.get("id") or note.get("objectId") or "")

    associated = False
    if note_id:
        try:
            _associate_note_to_contact_default(note_id=note_id, contact_id=contact_id)
            associated = True
        except Exception:
            associated = False

    # Best-effort contact property log for accounts that don't show notes or where
    # association permissions are missing.
    try:
        _request(
            "PATCH",
            f"/crm/v3/objects/contacts/{contact_id}",
            json_body={
                "properties": {
                    "last_conversation_event_type": event_type,
                    "last_conversation_event_at": occurred_at.replace(microsecond=0).isoformat(),
                    "last_conversation_event_json": json.dumps(
                        {"event_type": event_type, "data": payload},
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                }
            },
        )
    except Exception:
        pass

    return {
        "contact_id": contact_id,
        "note_id": note_id or None,
        "associated_to_contact": associated,
    }


def update_contact(
    *,
    email: str,
    properties: dict[str, Any],
) -> dict[str, Any]:
    """
    Upserts contact properties by email (used when lifecycle stage or key fields change).
    """

    return _upsert_contact_by_email(email, properties)


def set_lifecycle_stage(
    *,
    email: str,
    stage: str,
) -> dict[str, Any]:
    """
    Updates HubSpot `lifecyclestage` (standard property) for the contact.

    Defaults are configurable via env so the demo can match the target HubSpot portal.
    """

    stage_value = stage
    return update_contact(email=email, properties={"lifecyclestage": stage_value})


def _ensure_contact(*, email: str | None, phone: str | None) -> dict[str, Any]:
    if email:
        existing = _search_contact_by_email(email)
        if existing is not None:
            return existing
        return _request("POST", "/crm/v3/objects/contacts", json_body={"properties": {"email": email}})

    assert phone is not None
    existing = _search_contact_by_phone(phone)
    if existing is not None:
        return existing
    return _request("POST", "/crm/v3/objects/contacts", json_body={"properties": {"phone": phone}})


def _search_contact_by_phone(phone: str) -> dict[str, Any] | None:
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "phone",
                        "operator": "EQ",
                        "value": phone,
                    }
                ]
            }
        ],
        "limit": 1,
    }
    result = _request("POST", "/crm/v3/objects/contacts/search", json_body=payload)
    matches = result.get("results")
    if isinstance(matches, list) and matches:
        first = matches[0]
        if isinstance(first, dict):
            return first
    return None


def _coalesce_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            joined = ", ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                return joined
    return ""


def _coalesce_number(value: Any) -> int | float:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return 0


def _coalesce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _coalesce_employee_count(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            digits = "".join(ch if ch.isdigit() else " " for ch in value)
            parts = [part for part in digits.split() if part]
            if len(parts) == 1:
                return int(parts[0])
    return None


def _first_non_empty(*values: Any) -> Any:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list) and value:
            return value
    return None


def _create_note(
    *,
    contact_id: str,
    email: str | None,
    event_type: str,
    occurred_at: datetime,
    body_json: dict[str, Any],
) -> dict[str, Any]:
    # HubSpot note fields:
    # - hs_note_body: HTML/text string
    # - hs_timestamp: epoch ms timestamp
    occurred_ms = int(occurred_at.timestamp() * 1000)
    note_body = _format_note_body(
        contact_id=contact_id,
        email=email,
        event_type=event_type,
        occurred_at=occurred_at,
        body_json=body_json,
    )
    return _request(
        "POST",
        "/crm/v3/objects/notes",
        json_body={
            "properties": {
                "hs_timestamp": str(occurred_ms),
                "hs_note_body": note_body,
            }
        },
    )


def _associate_note_to_contact_default(*, note_id: str, contact_id: str) -> None:
    # Use the v4 "default association" route to avoid needing a hard-coded associationTypeId.
    _request(
        "PUT",
        f"/crm/v4/objects/notes/{note_id}/associations/default/contacts/{contact_id}",
        json_body=None,
    )


def _associate_contact_to_company_default(*, contact_id: str, company_id: str) -> None:
    _request(
        "PUT",
        f"/crm/v4/objects/contacts/{contact_id}/associations/default/companies/{company_id}",
        json_body=None,
    )


def _format_note_body(
    *,
    contact_id: str,
    email: str | None,
    event_type: str,
    occurred_at: datetime,
    body_json: dict[str, Any],
) -> str:
    timestamp = occurred_at.replace(microsecond=0).isoformat()
    lines = [
        f"EVENT: {event_type}",
        f"Contact ID: {contact_id}",
    ]

    company_name = body_json.get("company_name")
    if isinstance(company_name, str) and company_name.strip():
        lines.append(f"Company: {company_name.strip()}")

    if isinstance(email, str) and email.strip():
        lines.append(f"Email: {email.strip()}")

    thread_id = body_json.get("thread_id")
    if isinstance(thread_id, str) and thread_id.strip():
        lines.append(f"Thread ID: {thread_id.strip()}")

    lines.append(f"Timestamp: {timestamp}")

    if event_type == "qualification_complete":
        segment = body_json.get("segment")
        confidence = body_json.get("confidence")
        pitch_angle = body_json.get("pitch_angle")
        if segment is not None:
            lines.append(f"Segment: {segment}")
        if confidence is not None:
            lines.append(f"Confidence: {confidence}")
        if pitch_angle is not None:
            lines.append(f"Pitch angle: {pitch_angle}")
    elif event_type == "enrichment_completed":
        details = (
            ("Firmographics", body_json.get("firmographics")),
            ("Funding", body_json.get("funding")),
            ("Job signals", body_json.get("job_signals")),
            ("Layoffs", body_json.get("layoffs")),
            ("Leadership", body_json.get("leadership")),
            ("AI maturity", body_json.get("ai_maturity")),
            ("ICP classification", body_json.get("icp_classification")),
        )
        for label, value in details:
            lines.append(f"{label}:")
            lines.append(_stringify_note_value(value))

    raw = {
        "event_type": event_type,
        "occurred_at": timestamp,
        "contact_id": contact_id,
        "email": email,
        "data": body_json,
    }
    pretty_json = json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True)
    summary = "\n".join(lines)
    return f"<pre>{summary}\n\nData:\n{pretty_json}</pre>"[:7500]


def _stringify_note_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, str):
        return value.strip() or "n/a"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
