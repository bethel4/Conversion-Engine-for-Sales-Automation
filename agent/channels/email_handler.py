from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from agent.config import STAFF_SINK_EMAIL, is_live_outbound
from agent.crm.hubspot_mcp import log_event


def _load_runtime() -> tuple[Any, Any, Any]:
    from agent.main import EmailSendRequest, classify_reply_intent, send_email

    return EmailSendRequest, classify_reply_intent, send_email


def send_outreach_email(prospect: dict[str, Any], email: dict[str, Any]) -> dict[str, Any]:
    to_address = prospect["email"] if is_live_outbound() else STAFF_SINK_EMAIL
    sent_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if is_live_outbound():
        EmailSendRequest, _, send_email = _load_runtime()
        payload = EmailSendRequest(
            to=[to_address],
            subject=email["subject"],
            text=email.get("body_text"),
            html=email.get("body_html"),
            tags=[
                {"name": "variant", "value": str(email.get("variant", "unknown"))},
                {"name": "prospect_id", "value": str(prospect.get("hubspot_id", ""))},
                {"name": "draft", "value": "true"},
            ],
        )
        result = send_email(payload)
        message_id = str(result.get("id") or result.get("message_id") or "")
    else:
        result = {"id": f"sink_{int(datetime.now(timezone.utc).timestamp())}"}
        message_id = str(result["id"])

    response = {
        "sent": True,
        "message_id": message_id,
        "to": to_address,
        "sent_at": sent_at,
        "variant": email.get("variant"),
        "logged_to_hubspot": False,
    }
    try:
        if prospect.get("email") or prospect.get("hubspot_id"):
            log_event(
                email=prospect.get("email"),
                event_type="email_sent",
                data={
                    "message_id": message_id,
                    "subject": email["subject"],
                    "variant": email.get("variant"),
                    "brief_ref": email.get("brief_ref"),
                    "sent_at": sent_at,
                },
            )
            response["logged_to_hubspot"] = True
    except Exception as exc:
        response["hubspot_error"] = str(exc)
    return response


def handle_reply_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    _, classify_reply_intent, _ = _load_runtime()
    body = str(payload.get("text") or payload.get("body") or "")
    from_email = ""
    raw_from = payload.get("from")
    if isinstance(raw_from, dict):
        from_email = str(raw_from.get("email") or "")
    elif isinstance(raw_from, str):
        from_email = raw_from

    intent = classify_reply_intent(body)
    next_action = {
        "interested": "qualify",
        "asks_for_info": "qualify",
        "not_interested": "nurture",
        "unclear": "nurture",
    }.get(intent["label"], "nurture")
    return {
        "prospect_id": payload.get("prospect_id") or payload.get("hubspot_id"),
        "reply_received": True,
        "next_action": next_action,
        "logged": bool(from_email or body),
    }
