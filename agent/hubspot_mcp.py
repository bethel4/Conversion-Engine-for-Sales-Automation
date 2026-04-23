from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

HUBSPOT_API_URL = "https://api.hubapi.com"


def _hubspot_api_key() -> str:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY is not set")
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


def build_enriched_contact_properties(
    *,
    email: str,
    phone: str | None = None,
    company_name: str | None = None,
    icp_segment: str,
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "email": email,
        "phone": phone,
        "company": company_name,
        "icp_segment": icp_segment,
        "pitch_angle": enrichment.get("pitch_angle"),
        "signal_enrichment_json": json.dumps(enrichment, separators=(",", ":"), sort_keys=True),
        "enrichment_timestamp": timestamp,
    }


def write_enriched_contact(
    *,
    email: str,
    phone: str | None = None,
    company_name: str | None = None,
    icp_segment: str,
    enrichment: dict[str, Any],
) -> dict[str, Any]:
    properties = build_enriched_contact_properties(
        email=email,
        phone=phone,
        company_name=company_name,
        icp_segment=icp_segment,
        enrichment=enrichment,
    )
    return _upsert_contact_by_email(email, properties)


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
