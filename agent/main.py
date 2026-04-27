import json
import os
from datetime import datetime, timezone
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import parse_qs
from typing import Any, Callable, Literal, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.enrichment.briefs import produce_hiring_signal_brief
from agent.enrichment.crunchbase import search_companies
from agent.enrichment.pipeline import run_hiring_signal_enrichment
from agent.enrichment.icp import classify_icp
from agent.email_generator import generate_outreach_email
from agent.hubspot_mcp import (
    log_event,
    set_lifecycle_stage,
    write_booking_update,
    write_enriched_contact,
)
from agent.openrouter_client import configured_model as openrouter_model, is_enabled as openrouter_enabled
from agent.outbound_policy import live_outbound_config, require_live_outbound
from agent.prospect_store import append_activity, create_prospect, get_prospect, load_prospects, update_prospect
from agent.prospect_flow import build_booking_link_followup_text, build_event_context, build_thread_id

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    # Be robust to starting `uvicorn` from any working directory.
    # Prefer a repo-root `.env` next to the `agent/` folder if present.
    repo_root_env = Path(__file__).resolve().parents[1] / ".env"
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(cwd_env)
    elif repo_root_env.exists():
        load_dotenv(repo_root_env)
    else:
        load_dotenv()

app = FastAPI(title="Conversion Engine Agent")

# Local UI/dev convenience (Next.js dev server, etc.).
# If you deploy behind a gateway, set `CORS_ALLOW_ORIGINS` explicitly.
_cors_origins_raw = os.getenv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

RESEND_API_URL = "https://api.resend.com/emails"
RESEND_RECEIVING_API_URL = "https://api.resend.com/emails/receiving"
MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"
AFRICASTALKING_SMS_API_URL = "https://api.africastalking.com/version1/messaging"
CALCOM_API_URL = "https://api.cal.com/v1/bookings"
EmailEventType = Literal["reply", "bounce", "delivery"]
SMSEventType = Literal["reply"]
CalendarEventType = Literal["booking_confirmed"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _hubspot_api_key() -> str:
    api_key = os.getenv("HUBSPOT_API_KEY") or os.getenv("HUBSPOT_TOKEN")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY or HUBSPOT_TOKEN is not set")
    return api_key


def _calcom_api_key() -> str:
    api_key = os.getenv("CALCOM_API_KEY")
    if not api_key:
        raise RuntimeError("CALCOM_API_KEY is not set")
    return api_key


def _calcom_api_url() -> str:
    return os.getenv("CALCOM_API_URL", CALCOM_API_URL)


def _fetch_calcom_booking(booking_id: str) -> dict[str, Any] | None:
    """Fetch detailed booking information from Cal.com API"""
    try:
        headers = {
            "Authorization": f"Bearer {_calcom_api_key()}",
            "Content-Type": "application/json",
        }
        # Try to get booking details - this may need adjustment based on Cal.com API
        url = f"{_calcom_api_url()}/{booking_id}"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except requests.RequestException:
        return None


def _calcom_booking_link() -> str:
    booking_link = os.getenv("CALCOM_BOOKING_LINK")
    if not booking_link or not booking_link.strip():
        raise RuntimeError("CALCOM_BOOKING_LINK is not set")
    return booking_link.strip()


def _mailersend_api_key() -> str:
    api_key = os.getenv("MAILERSEND_API_KEY")
    if not api_key:
        raise RuntimeError("MAILERSEND_API_KEY is not set")
    return api_key


def _mailersend_from_email() -> str:
    from_email = os.getenv("MAILERSEND_FROM_EMAIL")
    if not from_email:
        raise RuntimeError("MAILERSEND_FROM_EMAIL is not set")
    return from_email


def _mailersend_from_name() -> str:
    return (os.getenv("MAILERSEND_FROM_NAME") or "Tenacious").strip() or "Tenacious"


def _mailersend_inbound_address() -> str:
    inbound_address = os.getenv("MAILERSEND_INBOUND_ADDRESS")
    if not inbound_address or not inbound_address.strip():
        raise RuntimeError("MAILERSEND_INBOUND_ADDRESS is not set")
    return inbound_address.strip()


def _resend_api_key() -> str:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set")
    return api_key


def _resend_from_email() -> str:
    from_email = os.getenv("RESEND_FROM_EMAIL")
    if not from_email:
        raise RuntimeError("RESEND_FROM_EMAIL is not set")
    return from_email


def _resend_from_name() -> str:
    return (os.getenv("RESEND_FROM_NAME") or "Tenacious").strip() or "Tenacious"


def _email_provider() -> str:
    return (os.getenv("EMAIL_PROVIDER") or "resend").strip().lower()


def _africas_talking_username() -> str:
    username = os.getenv("AFRICASTALKING_USERNAME")
    if not username:
        raise RuntimeError("AFRICASTALKING_USERNAME is not set")
    return username


def _africas_talking_api_key() -> str:
    api_key = os.getenv("AFRICASTALKING_API_KEY")
    if not api_key:
        raise RuntimeError("AFRICASTALKING_API_KEY is not set")
    return api_key


def _africas_talking_sender_id() -> Optional[str]:
    return os.getenv("AFRICASTALKING_SENDER_ID")


def _africas_talking_sms_api_url() -> str:
    return os.getenv("AFRICASTALKING_SMS_API_URL", AFRICASTALKING_SMS_API_URL)


def create_contact(email: str, phone: Optional[str] = None):
    enrichment = {
        "segment": "unclassified",
        "confidence": 0.0,
        "pitch_angle": "exploratory_generic",
        "reasoning": {},
    }
    return write_enriched_contact(
        email=email,
        phone=phone,
        company_name=None,
        icp_segment="unclassified",
        enrichment=enrichment,
    )


class ContactIn(BaseModel):
    email: str = Field(..., min_length=3)
    phone: Optional[str] = None


class ProspectEnrichmentRequest(BaseModel):
    email: str = Field(..., min_length=3)
    company_name: str = Field(..., min_length=1)
    phone: Optional[str] = None
    domain: Optional[str] = None
    leadership_sources: list[dict[str, Any]] = Field(default_factory=list)


class ProspectCreateRequest(BaseModel):
    company: str = Field(..., min_length=1)
    prospect_name: str = Field(..., min_length=1)
    email: Optional[str] = None
    domain: Optional[str] = None
    phone: Optional[str] = None
    use_playwright: bool = False
    peers_limit: int = Field(10, ge=1, le=25)


class HiringBriefRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    domain: Optional[str] = None
    use_playwright: bool = False
    out_dir: str = "data/briefs"
    leadership_sources: list[dict[str, Any]] = Field(default_factory=list)


class CompetitorGapRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    hiring_brief: Optional[dict[str, Any]] = None
    peers_limit: int = Field(10, ge=1, le=25)
    out_dir: str = "data/briefs"


class ProspectEnrichActionRequest(BaseModel):
    domain: Optional[str] = None
    use_playwright: bool = False
    peers_limit: int = Field(10, ge=1, le=25)
    leadership_sources: list[dict[str, Any]] = Field(default_factory=list)


class EmailSendRequest(BaseModel):
    to: list[str] = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    text: Optional[str] = None
    html: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    tags: list[dict[str, str]] = Field(default_factory=list)


class EmailEvent(BaseModel):
    event_type: EmailEventType
    message_id: str
    sender: str
    subject: Optional[str] = None
    text: Optional[str] = None
    html: Optional[str] = None
    to: list[str] = Field(default_factory=list)
    received_at: Optional[str] = None
    provider_event_type: Optional[str] = None
    raw_payload: dict[str, Any]


class SMSSendRequest(BaseModel):
    to: list[str] = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    prior_email_reply_received: bool = Field(
        ...,
        description="SMS is a warm-lead channel and can only be used after a prior email reply.",
    )
    sender_id: Optional[str] = None


class SMSEvent(BaseModel):
    event_type: SMSEventType
    message_id: str
    sender: str
    recipient: Optional[str] = None
    text: str
    link_id: Optional[str] = None
    received_at: Optional[str] = None
    raw_payload: dict[str, Any]


class CalcomBookingRequest(BaseModel):
    name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    start: str = Field(..., min_length=1)
    event_type_id: int
    time_zone: str = Field(..., min_length=1)
    title: Optional[str] = None
    notes: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    language: str = "en"


class CalendarEvent(BaseModel):
    event_type: CalendarEventType
    booking_id: str
    email: str
    booking_status: str
    attendee_name: Optional[str] = None
    start_time: Optional[str] = None
    title: Optional[str] = None
    raw_payload: dict[str, Any]


class ManualReplyRequest(BaseModel):
    message_id: Optional[str] = None
    subject: Optional[str] = None
    text: Optional[str] = None


class SendBookingLinkRequest(BaseModel):
    subject: Optional[str] = None


class SyncBookingRequest(BaseModel):
    booking_id: str = Field(..., min_length=1)
    booking_status: str = Field("confirmed", min_length=1)
    start_time: Optional[str] = None
    title: Optional[str] = None
    attendee_name: Optional[str] = None
    attendee_email: Optional[str] = None
    timezone: Optional[str] = None


class GenerateEmailRequest(BaseModel):
    approval_reset: bool = True


class ApproveEmailRequest(BaseModel):
    approved: bool = True


EmailEventHandler = Callable[[EmailEvent], None]
SMSEventHandler = Callable[[SMSEvent], None]
CalendarEventHandler = Callable[[CalendarEvent], None]


def _default_email_event_handler(event: EmailEvent) -> None:
    # Default behavior is explicit and observable until a downstream handler is attached.
    print("EMAIL EVENT:", event.model_dump())


def _default_sms_event_handler(event: SMSEvent) -> None:
    # Default behavior is explicit and observable until a downstream handler is attached.
    print("SMS EVENT:", event.model_dump())


def _default_calendar_event_handler(event: CalendarEvent) -> None:
    # Default behavior is explicit and observable until a downstream handler is attached.
    print("CALENDAR EVENT:", event.model_dump())


email_event_handler: EmailEventHandler = _default_email_event_handler
sms_event_handler: SMSEventHandler = _default_sms_event_handler
calendar_event_handler: CalendarEventHandler = _default_calendar_event_handler


def set_email_event_handler(handler: EmailEventHandler) -> None:
    # Downstream systems can register their own callback without changing the webhook route.
    global email_event_handler
    email_event_handler = handler


def set_sms_event_handler(handler: SMSEventHandler) -> None:
    # Downstream systems can register their own callback without changing the webhook route.
    global sms_event_handler
    sms_event_handler = handler


def set_calendar_event_handler(handler: CalendarEventHandler) -> None:
    # Downstream systems can register their own callback without changing the webhook route.
    global calendar_event_handler
    calendar_event_handler = handler


def emit_email_event(event: EmailEvent) -> None:
    email_event_handler(event)


def emit_sms_event(event: SMSEvent) -> None:
    sms_event_handler(event)


def emit_calendar_event(event: CalendarEvent) -> None:
    calendar_event_handler(event)


def send_email(payload: EmailSendRequest) -> dict[str, Any]:
    require_live_outbound("email_send")
    if not payload.text and not payload.html:
        raise RuntimeError("Email payload must include text or html content")
    provider = _email_provider()
    if provider == "mailersend":
        return _send_email_via_mailersend(payload)
    if provider == "resend":
        return _send_email_via_resend(payload)
    raise RuntimeError(f"Unsupported EMAIL_PROVIDER: {provider}")


def _send_email_via_resend(payload: EmailSendRequest) -> dict[str, Any]:
    try:
        headers = {
            "Authorization": f"Bearer {_resend_api_key()}",
            "Content-Type": "application/json",
        }
        data: dict[str, Any] = {
            "from": f"{_resend_from_name()} <{payload.from_email or _resend_from_email()}>",
            "to": payload.to,
            "subject": payload.subject,
            "text": payload.text,
            "html": payload.html,
        }
        if payload.reply_to:
            data["reply_to"] = payload.reply_to
        if payload.tags:
            data["tags"] = payload.tags
        response = requests.post(RESEND_API_URL, json=data, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"Resend send failed: {exc}") from exc
    if not response.ok:
        raise RuntimeError(f"Resend error {response.status_code}: {response.text}")
    try:
        result = response.json()
    except ValueError:
        result = {}
    return result if isinstance(result, dict) else {}


def _send_email_via_mailersend(payload: EmailSendRequest) -> dict[str, Any]:
    try:
        recipients = []
        for email in payload.to:
            prospect = get_prospect(email=email) or {}
            recipient: dict[str, Any] = {"email": email}
            prospect_name = prospect.get("prospect_name")
            if isinstance(prospect_name, str) and prospect_name.strip():
                recipient["name"] = prospect_name.strip()
            recipients.append(recipient)
        headers = {
            "Authorization": f"Bearer {_mailersend_api_key()}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        data = {
            "from": {
                "email": payload.from_email or _mailersend_from_email(),
                "name": _mailersend_from_name(),
            },
            "to": recipients,
            "subject": payload.subject,
            "text": payload.text,
            "html": payload.html,
            "reply_to": [{"email": payload.reply_to or _mailersend_inbound_address()}],
        }
        response = requests.post(MAILERSEND_API_URL, json=data, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"MailerSend send failed: {exc}") from exc
    if not response.ok:
        raise RuntimeError(f"MailerSend error {response.status_code}: {response.text}")
    try:
        result = response.json()
    except ValueError:
        result = {}
    if not isinstance(result, dict):
        result = {}
    result.setdefault("id", response.headers.get("x-message-id") or response.headers.get("X-Message-Id"))
    return result


def _response_provider_name() -> str:
    return _email_provider()


def send_sms_to_warm_lead(payload: SMSSendRequest) -> dict[str, Any]:
    require_live_outbound("sms_send")
    # SMS is intentionally gated behind a prior email reply so it is never used for cold outreach.
    if not payload.prior_email_reply_received:
        raise PermissionError("SMS is only allowed for warm leads after a prior email reply")

    headers = {
        "Accept": "application/json",
        "apiKey": _africas_talking_api_key(),
    }
    data = {
        "username": _africas_talking_username(),
        "to": ",".join(payload.to),
        "message": payload.message,
    }
    sender_id = payload.sender_id or _africas_talking_sender_id()
    if sender_id:
        data["from"] = sender_id

    try:
        response = requests.post(
            _africas_talking_sms_api_url(),
            data=data,
            headers=headers,
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Africa's Talking send failed: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"Africa's Talking error {response.status_code}: {response.text}")

    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def enrich_and_write_contact(payload: ProspectEnrichmentRequest) -> dict[str, Any]:
    leadership_sources = payload.leadership_sources or None
    brief = produce_hiring_signal_brief(
        payload.company_name,
        domain=payload.domain,
        leadership_sources=leadership_sources,
    )
    icp = classify_icp(brief)
    enrichment = {
        "segment": icp["segment"],
        "confidence": icp["confidence"],
        "pitch_angle": icp["pitch_angle"],
        "scores": icp["scores"],
        "reasoning": icp["reasoning"],
        "disqualifiers": icp["disqualifiers"],
        "signals": {
            "company": brief["company"],
            "funding": brief["funding"],
            "jobs": brief["jobs"],
            "layoffs": brief["layoffs"],
            "leadership_change": brief["leadership_change"],
            "ai_maturity": brief["ai_maturity"],
            "tech_stack": brief["tech_stack"],
        },
        "meta": brief["meta"],
    }
    thread_id = build_thread_id(payload.company_name)
    hubspot = write_enriched_contact(
        email=payload.email,
        phone=payload.phone,
        company_name=payload.company_name,
        icp_segment=icp["segment"],
        enrichment=enrichment,
    )
    try:
        # Thread/prospect identity cache so a later reply webhook can be linked back to company_name.
        from agent.enrichment.cache import set_cache

        set_cache(
            "prospect_identity",
            payload.email.casefold(),
            {
                "email": payload.email,
                "phone": payload.phone,
                "company_name": payload.company_name,
                "domain": payload.domain,
                "leadership_sources": payload.leadership_sources,
                "thread_id": thread_id,
            },
        )
    except Exception as exc:  # pragma: no cover
        print("IDENTITY CACHE ERROR:", str(exc))
    note_result = None
    try:
        note_result = log_event(
            email=payload.email,
            phone=payload.phone,
            event_type="enrichment_completed",
            data={
                "company_name": payload.company_name,
                "email": payload.email,
                "thread_id": thread_id,
                "enrichment_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "firmographics": brief.get("company"),
                "funding": brief.get("funding"),
                "job_signals": brief.get("jobs"),
                "layoffs": brief.get("layoffs"),
                "leadership": brief.get("leadership_change"),
                "ai_maturity": brief.get("ai_maturity"),
                "icp_classification": {
                    "segment": icp["segment"],
                    "confidence": icp["confidence"],
                    "pitch_angle": icp["pitch_angle"],
                    "scores": icp["scores"],
                    "reasoning": icp["reasoning"],
                    "disqualifiers": icp["disqualifiers"],
                },
            },
        )
    except Exception as exc:  # pragma: no cover
        print("HUBSPOT EVENT LOGGING ERROR (enrichment_completed):", str(exc))
        raise RuntimeError(f"HubSpot enrichment note creation failed: {exc}") from exc
    try:
        log_event(
            email=payload.email,
            phone=payload.phone,
            event_type="qualification_complete",
            data=build_event_context(
                prospect_email=payload.email,
                identity={"company_name": payload.company_name, "thread_id": thread_id},
                extra={
                    "segment": icp["segment"],
                    "confidence": icp["confidence"],
                    "pitch_angle": icp["pitch_angle"],
                },
            ),
        )
    except Exception as exc:  # pragma: no cover
        print("HUBSPOT EVENT LOGGING ERROR (qualification_complete):", str(exc))
    return {"hubspot": hubspot, "enrichment": enrichment, "thread_id": thread_id, "note": note_result}


def _store_enrichment_result(
    *,
    prospect_id: str,
    prospect: dict[str, Any],
    hiring: dict[str, Any],
    competitor_gap: dict[str, Any],
    crm: dict[str, Any],
) -> dict[str, Any] | None:
    enrichment = crm.get("enrichment") if isinstance(crm, dict) else {}
    patch = {
        "domain": prospect.get("domain"),
        "thread_id": crm.get("thread_id") or prospect.get("thread_id"),
        "hubspot": crm.get("hubspot"),
        "qualification": {
            "segment": enrichment.get("segment"),
            "confidence": enrichment.get("confidence"),
            "pitch_angle": enrichment.get("pitch_angle"),
        }
        if isinstance(enrichment, dict)
        else None,
        "latest_hiring_brief": hiring.get("brief"),
        "latest_hiring_brief_path": hiring.get("brief_path"),
        "latest_competitor_gap_brief": competitor_gap.get("brief"),
        "latest_competitor_gap_brief_path": competitor_gap.get("brief_path"),
        "lifecycle_stage": "Qualified",
    }
    updated = update_prospect(prospect_id=prospect_id, patch=patch)
    append_activity(
        prospect_id=prospect_id,
        activity={
            "type": "enrichment_completed",
            "title": "Enrichment completed",
            "description": "Hiring signal brief, competitor gap brief, and CRM enrichment were updated.",
        },
    )
    return updated


def _lookup_identity(email: str) -> dict[str, Any] | None:
    try:
        from agent.enrichment.cache import get_cache

        identity = get_cache(
            "prospect_identity",
            email.casefold(),
            max_age_seconds=365 * 24 * 3600,
        )
    except Exception:
        identity = None
    return identity if isinstance(identity, dict) else None


def classify_reply_intent(text: str) -> dict[str, Any]:
    normalized = (text or "").strip().casefold()
    if not normalized:
        return {"label": "unclear", "confidence": 0.3, "reason": "empty reply body"}

    not_interested_markers = ("not interested", "stop", "unsubscribe", "remove me", "no thanks", "don't contact", "do not contact")
    interested_markers = ("interested", "sounds good", "let's talk", "lets talk", "book", "call", "meeting", "demo", "chat")
    info_markers = ("send", "share", "brief", "details", "more info", "more information", "pricing", "case study", "deck")

    if any(marker in normalized for marker in not_interested_markers):
        return {"label": "not_interested", "confidence": 0.95, "reason": "explicit negative intent marker"}
    if any(marker in normalized for marker in interested_markers):
        return {"label": "interested", "confidence": 0.85, "reason": "positive meeting or interest marker"}
    if any(marker in normalized for marker in info_markers) or "?" in normalized:
        return {"label": "asks_for_info", "confidence": 0.75, "reason": "information request marker"}
    return {"label": "unclear", "confidence": 0.45, "reason": "no strong intent marker detected"}


def build_reply_next_action(
    *,
    intent: dict[str, Any],
    event: EmailEvent,
    identity: dict[str, Any] | None,
    qualification_result: dict[str, Any] | None,
) -> dict[str, Any]:
    label = str(intent.get("label") or "unclear")
    company_name = str((identity or {}).get("company_name") or "")
    qualification = qualification_result.get("enrichment") if isinstance(qualification_result, dict) else {}
    segment = qualification.get("segment") if isinstance(qualification, dict) else None

    if label == "interested":
        return {
            "type": "booking_link",
            "status": "recommended",
            "reason": "Prospect signaled active interest.",
            "draft": build_booking_link_followup_text(str(segment or "abstain"), _calcom_booking_link()) if os.getenv("CALCOM_BOOKING_LINK") else None,
        }
    if label == "asks_for_info":
        return {
            "type": "brief_response",
            "status": "recommended",
            "reason": "Prospect asked for more context.",
            "draft": (
                f"Thanks for the reply. We pulled the brief based on public signals around {company_name or 'your team'} "
                "and can send the key findings before we book time."
            ),
        }
    if label == "not_interested":
        return {
            "type": "close_lost",
            "status": "applied",
            "reason": "Prospect explicitly declined.",
            "draft": None,
        }
    return {
        "type": "manual_review",
        "status": "required",
        "reason": "Intent is unclear and needs human review.",
        "draft": None,
    }


def _process_reply_event(event: EmailEvent) -> dict[str, Any]:
    emit_email_event(event)
    identity = _lookup_identity(event.sender)
    reply_context = build_event_context(
        prospect_email=event.sender,
        identity=identity,
        extra={
            "message_id": event.message_id,
            "subject": event.subject,
            "text": event.text,
        },
    )
    try:
        log_event(
            email=event.sender,
            event_type="email_reply_received",
            data=reply_context,
        )
    except Exception as exc:  # pragma: no cover
        print("HUBSPOT EVENT LOGGING ERROR (email_reply_received):", str(exc))

    qualification_result: dict[str, Any] | None = None
    if identity and identity.get("company_name"):
        qualification_result = enrich_and_write_contact(
            ProspectEnrichmentRequest(
                email=identity.get("email") or event.sender,
                company_name=str(identity["company_name"]),
                phone=identity.get("phone"),
                domain=identity.get("domain"),
                leadership_sources=identity.get("leadership_sources") or [],
            )
        )
    intent = classify_reply_intent(event.text or event.html or "")
    next_action = build_reply_next_action(intent=intent, event=event, identity=identity, qualification_result=qualification_result)

    updated = update_prospect(
        email=event.sender,
        patch={
            "last_reply_message_id": event.message_id,
            "last_reply_subject": event.subject,
            "last_reply_text": event.text,
            "last_reply_html": event.html,
            "last_reply_to": event.to,
            "last_reply_received_at": event.received_at,
            "last_reply_source": "webhook",
            "reply_intent": intent["label"],
            "reply_intent_confidence": intent["confidence"],
            "reply_intent_reason": intent["reason"],
            "reply_next_action": next_action,
            "lifecycle_stage": "Reply received",
        },
    )
    if intent["label"] == "not_interested":
        try:
            set_lifecycle_stage(
                email=event.sender,
                stage=os.getenv("HUBSPOT_STAGE_CLOSED_LOST", "other"),
            )
        except Exception as exc:  # pragma: no cover
            print("HUBSPOT LIFECYCLE ERROR (closed_lost):", str(exc))
        update_prospect(
            email=event.sender,
            patch={"lifecycle_stage": "Closed lost"},
        )
    if qualification_result:
        enrichment = qualification_result.get("enrichment")
        if isinstance(enrichment, dict):
            update_prospect(
                email=event.sender,
                patch={
                    "qualification": {
                        "segment": enrichment.get("segment"),
                        "confidence": enrichment.get("confidence"),
                        "pitch_angle": enrichment.get("pitch_angle"),
                    },
                    "hubspot": qualification_result.get("hubspot"),
                    "thread_id": qualification_result.get("thread_id") or (updated or {}).get("thread_id"),
                },
            )
    append_activity(
        email=event.sender,
        activity={
            "type": "email_reply_received",
            "title": "Reply processed",
            "description": event.text or event.html or "Inbound reply received.",
        },
    )
    return {
        "status": "accepted",
        "event_type": event.event_type,
        "message_id": event.message_id,
        "reply_intent": intent,
        "next_action": next_action,
        "qualification": qualification_result.get("enrichment") if isinstance(qualification_result, dict) else None,
    }


def _send_booking_link(*, email: str, subject: str | None = None) -> dict[str, Any]:
    booking_link = _calcom_booking_link()
    prospect = get_prospect(email=email) or {}
    qualification = prospect.get("qualification") if isinstance(prospect.get("qualification"), dict) else {}
    segment = str(qualification.get("segment") or "abstain")
    result = send_email(
        EmailSendRequest(
            to=[email],
            subject=subject or "Book time with Tenacious",
            text=build_booking_link_followup_text(segment, booking_link),
        )
    )
    identity = _lookup_identity(email)
    try:
        log_event(
            email=email,
            event_type="booking_link_sent",
            data=build_event_context(
                prospect_email=email,
                identity=identity,
                extra={
                    "calcom_booking_link": booking_link,
                    "message_id": result.get("id"),
                    "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                },
            ),
        )
    except Exception as exc:  # pragma: no cover
        print("HUBSPOT EVENT LOGGING ERROR (booking_link_sent):", str(exc))
    update_prospect(
        email=email,
        patch={
            "booking_link_sent_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "booking_link": booking_link,
            "lifecycle_stage": "Booking link sent",
            "last_message_id": result.get("id"),
        },
    )
    append_activity(
        email=email,
        activity={
            "type": "booking_link_sent",
            "title": "Booking link sent",
            "description": f"Cal.com booking link sent via {_response_provider_name()}.",
        },
    )
    return {"provider": _response_provider_name(), "result": result, "booking_link": booking_link}


def _process_calendar_event(event: CalendarEvent) -> dict[str, Any]:
    emit_calendar_event(event)
    hubspot = write_booking_update(
        email=event.email,
        booking_id=event.booking_id,
        booking_status=event.booking_status,
        booking_start_time=event.start_time,
        booking_title=event.title,
    )
    identity = _lookup_identity(event.email)
    try:
        if event.booking_status == "completed":
            log_event(
                email=event.email,
                event_type="call_completed",
                data=build_event_context(
                    prospect_email=event.email,
                    identity=identity,
                    extra={"booking_id": event.booking_id, "title": event.title},
                ),
            )
            set_lifecycle_stage(
                email=event.email,
                stage=os.getenv("HUBSPOT_STAGE_CALL_COMPLETED", "customer"),
            )
            lifecycle_stage = "Call completed"
        else:
            log_event(
                email=event.email,
                event_type="call_booked",
                data=build_event_context(
                    prospect_email=event.email,
                    identity=identity,
                    extra={"booking_id": event.booking_id, "title": event.title},
                ),
            )
            set_lifecycle_stage(
                email=event.email,
                stage=os.getenv("HUBSPOT_STAGE_CALL_BOOKED", "appointmentscheduled"),
            )
            lifecycle_stage = "Discovery booked"
    except Exception as exc:  # pragma: no cover
        print("HUBSPOT EVENT LOGGING ERROR (calendar_webhook):", str(exc))
        lifecycle_stage = "Discovery booked"
    update_prospect(
        email=event.email,
        patch={
            "booking_id": event.booking_id,
            "booking_status": event.booking_status,
            "booking_start_time": event.start_time,
            "booking_title": event.title,
            "hubspot": hubspot,
            "lifecycle_stage": lifecycle_stage,
        },
    )
    append_activity(
        email=event.email,
        activity={
            "type": "call_booked" if event.booking_status != "completed" else "call_completed",
            "title": "Booking synced" if event.booking_status != "completed" else "Call completed",
            "description": event.title or event.booking_id,
        },
    )
    return {
        "status": "accepted",
        "event_type": event.event_type,
        "booking_id": event.booking_id,
        "hubspot": hubspot,
    }


def create_calcom_booking(payload: CalcomBookingRequest) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {_calcom_api_key()}",
        "Content-Type": "application/json",
    }
    data = {
        "eventTypeId": payload.event_type_id,
        "start": payload.start,
        "responses": {
            "name": payload.name,
            "email": payload.email,
            "notes": payload.notes,
        },
        "timeZone": payload.time_zone,
        "language": payload.language,
        "title": payload.title,
        "metadata": {
            "phone": payload.phone,
            "company_name": payload.company_name,
        },
    }

    try:
        response = requests.post(_calcom_api_url(), json=data, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"Cal.com booking failed: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"Cal.com error {response.status_code}: {response.text}")

    return response.json()


def _extract_webhook_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Providers often wrap the event body inside `data`; fall back to the root object.
    data = payload.get("data")
    if isinstance(data, dict):
        return data
    return payload


def _extract_email_address(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("email") or value.get("raw") or value.get("address")
    if not isinstance(value, str):
        return None
    _, address = parseaddr(value)
    normalized = (address or value).strip()
    return normalized or None


def _extract_email_addresses(values: Any) -> list[str]:
    if isinstance(values, dict):
        nested = values.get("data")
        if isinstance(nested, list):
            values = nested
        else:
            values = values.get("to") or values.get("cc") or values.get("bcc") or []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        email = _extract_email_address(item)
        if email:
            out.append(email)
    return out


def _normalize_email_body(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _resend_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_resend_api_key()}",
        "Content-Type": "application/json",
    }


def _retrieve_resend_received_email(email_id: str) -> dict[str, Any]:
    try:
        response = requests.get(
            f"{RESEND_RECEIVING_API_URL}/{email_id}",
            headers=_resend_headers(),
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Resend receiving fetch failed: {exc}") from exc
    if not response.ok:
        raise RuntimeError(f"Resend receiving error {response.status_code}: {response.text}")
    try:
        result = response.json()
    except ValueError:
        result = {}
    if not isinstance(result, dict):
        return {}
    data = result.get("data")
    if isinstance(data, dict):
        return data
    return result


def _resolve_resend_reply_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("type") or payload.get("event") or "").lower()
    data = _extract_webhook_payload(payload)
    if event_type != "email.received":
        return data

    has_body = bool(_normalize_email_body(data.get("text")) or _normalize_email_body(data.get("text_body")) or _normalize_email_body(data.get("html")) or _normalize_email_body(data.get("html_body")))
    email_id = data.get("email_id") or data.get("id")
    if has_body or not email_id:
        return data

    received = _retrieve_resend_received_email(str(email_id))
    merged = dict(data)
    merged.update(received)
    merged.setdefault("email_id", email_id)
    return merged


def _parse_email_event(payload: dict[str, Any]) -> EmailEvent:
    event_type = payload.get("type") or payload.get("event")
    if not isinstance(event_type, str):
        raise ValueError("Webhook payload is missing event type")

    normalized_type = event_type.lower()
    data = _resolve_resend_reply_payload(payload) if normalized_type == "email.received" else _extract_webhook_payload(payload)

    if "reply" in normalized_type or "received" in normalized_type or "inbound" in normalized_type:
        message_id = data.get("message_id") or data.get("email_id") or data.get("id")
        sender = _extract_email_address(data.get("from") or data.get("sender"))
        recipients = _extract_email_addresses(data.get("to") or data.get("recipients"))
        if isinstance(data.get("recipients"), dict):
            recipients = recipients or _extract_email_addresses(data["recipients"].get("to"))
        if not message_id or not sender:
            raise ValueError("Reply webhook payload is missing message id or sender")
        return EmailEvent(
            event_type="reply",
            message_id=str(message_id),
            sender=str(sender),
            subject=data.get("subject"),
            text=_normalize_email_body(data.get("text") or data.get("text_body")),
            html=_normalize_email_body(data.get("html") or data.get("html_body")),
            to=[str(item) for item in recipients],
            received_at=str(data.get("created_at") or payload.get("created_at")) if (data.get("created_at") or payload.get("created_at")) else None,
            provider_event_type=normalized_type,
            raw_payload=payload,
        )

    if normalized_type in {"email.sent", "email.delivered", "email.delivery_delayed", "email.failed"}:
        message_id = data.get("email_id") or data.get("id") or data.get("message_id")
        sender = _extract_email_address(data.get("from")) or "provider"
        recipients = _extract_email_addresses(data.get("to") or data.get("recipient"))
        if not message_id:
            raise ValueError("Delivery webhook payload is missing message id")
        return EmailEvent(
            event_type="delivery",
            message_id=str(message_id),
            sender=sender,
            subject=data.get("subject"),
            to=recipients,
            received_at=str(data.get("created_at") or payload.get("created_at")) if (data.get("created_at") or payload.get("created_at")) else None,
            provider_event_type=normalized_type,
            raw_payload=payload,
        )

    if "bounce" in normalized_type:
        message_id = data.get("email_id") or data.get("id") or data.get("message_id")
        sender = _extract_email_address(data.get("from") or data.get("recipient")) or str(data.get("recipient") or "")
        if not message_id or not sender:
            raise ValueError("Bounce webhook payload is missing message id or recipient")
        recipients = _extract_email_addresses(data.get("to") or data.get("recipient"))
        return EmailEvent(
            event_type="bounce",
            message_id=str(message_id),
            sender=str(sender),
            subject=data.get("subject"),
            text=data.get("reason"),
            to=[str(item) for item in recipients],
            received_at=str(data.get("created_at") or payload.get("created_at")) if (data.get("created_at") or payload.get("created_at")) else None,
            provider_event_type=normalized_type,
            raw_payload=payload,
        )

    raise ValueError(f"Unsupported email webhook event type: {event_type}")


async def _read_json_payload(request: Request, malformed_message: str) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raw = (await request.body()).decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=400,
            detail={"error": malformed_message, "raw": raw},
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=malformed_message)
    return payload


def _parse_sms_event(payload: dict[str, Any]) -> SMSEvent:
    sender = payload.get("from") or payload.get("sender")
    text = payload.get("text") or payload.get("message")
    message_id = payload.get("id") or payload.get("messageId") or payload.get("message_id")
    if not sender or not text:
        raise ValueError("SMS webhook payload is missing sender or text")
    if not message_id:
        message_id = f"{sender}:{text}"

    return SMSEvent(
        event_type="reply",
        message_id=str(message_id),
        sender=str(sender),
        recipient=str(payload["to"]) if payload.get("to") else None,
        text=str(text),
        link_id=str(payload["linkId"]) if payload.get("linkId") else None,
        received_at=str(payload["date"]) if payload.get("date") else None,
        raw_payload=payload,
    )


def _parse_calendar_event(payload: dict[str, Any]) -> CalendarEvent:
    event_type = str(payload.get("triggerEvent") or payload.get("type") or payload.get("event") or "")
    normalized = event_type.lower()
    data = _extract_webhook_payload(payload)
    booking = data.get("booking") if isinstance(data.get("booking"), dict) else data
    attendee = booking.get("attendee") if isinstance(booking.get("attendee"), dict) else {}
    email = attendee.get("email") or booking.get("email")
    attendee_name = attendee.get("name") or booking.get("name")
    booking_id = booking.get("id") or booking.get("uid") or payload.get("bookingId")
    start_time = booking.get("startTime") or booking.get("start")
    title = booking.get("title")
    status = str(booking.get("status") or "confirmed").lower()

    if "booking" not in normalized and "meeting" not in normalized:
        raise ValueError(f"Unsupported calendar webhook event type: {event_type or 'unknown'}")
    if status not in {"accepted", "confirmed", "completed"}:
        raise ValueError(f"Unsupported calendar booking status: {status}")
    if not email or not booking_id:
        raise ValueError("Calendar webhook payload is missing attendee email or booking id")

    return CalendarEvent(
        event_type="booking_confirmed",
        booking_id=str(booking_id),
        email=str(email),
        booking_status=status,
        attendee_name=str(attendee_name) if attendee_name else None,
        start_time=str(start_time) if start_time else None,
        title=str(title) if title else None,
        raw_payload=payload,
    )


async def _read_sms_webhook_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Malformed SMS webhook payload")
        return payload

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        raw = (await request.body()).decode("utf-8", errors="replace")
        parsed = parse_qs(raw, keep_blank_values=True)
        payload = {key: values[-1] for key, values in parsed.items()}
        return payload

    raw = (await request.body()).decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError("Malformed SMS webhook payload") from None
    if not isinstance(payload, dict):
        raise ValueError("Malformed SMS webhook payload")
    return payload


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config():
    return {
        "status": "ok",
        "agent_api_url": None,
        "email_provider": _response_provider_name(),
        "openrouter_enabled": openrouter_enabled(),
        "openrouter_model": openrouter_model(),
        **live_outbound_config(),
    }


@app.get("/prospects")
def list_prospects_route():
    return {"prospects": load_prospects()}


@app.get("/companies")
def list_companies_route(q: str = "", limit: int = 20):
    safe_limit = max(1, min(limit, 50))
    return {"companies": search_companies(q, limit=safe_limit)}


@app.post("/prospects")
def create_prospect_route(payload: ProspectCreateRequest):
    company = payload.company.strip()
    prospect_name = payload.prospect_name.strip()
    domain = payload.domain.strip() if isinstance(payload.domain, str) and payload.domain.strip() else None
    prospect_id = company.casefold().replace(".", "").replace("&", "and")
    prospect_id = "".join(ch if ch.isalnum() else "_" for ch in prospect_id)
    prospect_id = "_".join(part for part in prospect_id.split("_") if part) or "prospect"
    email = payload.email.strip() if isinstance(payload.email, str) and payload.email.strip() else _synthetic_email(company, prospect_id)
    phone = payload.phone.strip() if isinstance(payload.phone, str) and payload.phone.strip() else _synthetic_phone(prospect_id)

    record = {
        "id": prospect_id,
        "prospect_name": prospect_name,
        "company": company,
        "email": email,
        "domain": domain,
        "phone": phone,
        "thread_id": build_thread_id(company),
        "lifecycle_stage": "New",
        "email_subject": f"Quick signal review for {company}",
        "email_text": f"Saw a few public signals around {company} that may be worth a closer look. Open to a short exchange?",
        "use_playwright": bool(payload.use_playwright),
        "peers_limit": int(payload.peers_limit),
        "activity": [],
    }
    try:
        created = create_prospect(record)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "created", "prospect": created}


def _synthetic_email(company: str, prospect_id: str) -> str:
    domain_slug = "".join(ch for ch in company.casefold() if ch.isalnum()) or prospect_id
    return f"{prospect_id}@{domain_slug}.example.com"


def _synthetic_phone(prospect_id: str) -> str:
    digits = "".join(str((ord(ch) % 10)) for ch in prospect_id)[:9].ljust(9, "0")
    return f"+2519{digits}"


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {"raw": (await request.body()).decode("utf-8", errors="replace")}

    print("WEBHOOK RECEIVED:", data)

    event_type = data.get("type") or data.get("event")
    if isinstance(event_type, str):
        normalized = event_type.lower()
        if normalized.startswith("email.") or "inbound" in normalized or "reply" in normalized:
            return await _handle_email_webhook_payload(data)

    email = data.get("email")
    phone = data.get("from") or data.get("phone")

    if not email:
        return {"status": "ignored", "reason": "no email provided"}

    try:
        result = create_contact(email=email, phone=phone)
        print("HUBSPOT RESULT:", result)
        return {"status": "created", "hubspot": result}
    except Exception as e:
        print("HUBSPOT ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emails/send")
def send_email_route(payload: EmailSendRequest):
    try:
        result = send_email(payload)
        message_id = result.get("id")
        for recipient in payload.to:
            try:
                identity = _lookup_identity(recipient)
                log_event(
                    email=recipient,
                    event_type="email_sent",
                    data=build_event_context(
                        prospect_email=recipient,
                        identity=identity,
                        extra={
                            "provider": _response_provider_name(),
                            "message_id": message_id,
                            "subject": payload.subject,
                            "tags": payload.tags,
                        },
                    ),
                )
            except Exception as exc:  # pragma: no cover
                print("HUBSPOT EVENT LOGGING ERROR (email_sent):", str(exc))
            update_prospect(
                email=recipient,
                patch={
                    "last_message_id": message_id,
                    "email_subject": payload.subject,
                    "email_text": payload.text,
                    "lifecycle_stage": "Outreach sent",
                },
            )
            append_activity(
                email=recipient,
                activity={
                    "type": "email_sent",
                    "title": "Outreach sent",
                    "description": payload.subject,
                },
            )
        return {"status": "sent", "provider": _response_provider_name(), "message_id": message_id, "result": result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/crm/prospects/enrich")
def enrich_prospect_route(payload: ProspectEnrichmentRequest):
    try:
        return enrich_and_write_contact(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/enrichment/hiring-brief")
def generate_hiring_brief_route(payload: HiringBriefRequest):
    """
    Central Act II merger endpoint:
    returns the merged brief schema + writes hiring_signal_brief_<company>_<date>.json.
    """

    try:
        leadership_sources = payload.leadership_sources or None
        result = run_hiring_signal_enrichment(
            payload.company_name,
            domain=payload.domain,
            leadership_sources=leadership_sources,
            out_dir=payload.out_dir,
            use_playwright=payload.use_playwright,
        )
        return {"status": "ok", **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/enrichment/competitor-gap")
def generate_competitor_gap_route(payload: CompetitorGapRequest):
    """
    Produces competitor_gap_brief_<company>_<date>.json (local-only; no paid APIs).
    """

    try:
        from agent.enrichment.competitor_gap import (
            produce_competitor_gap_brief,
            write_competitor_gap_brief_file,
        )

        brief = produce_competitor_gap_brief(
            payload.company_name,
            hiring_brief=payload.hiring_brief,
            peers_limit=payload.peers_limit,
        )
        path = write_competitor_gap_brief_file(brief, out_dir=payload.out_dir)
        return {"status": "ok", "brief": brief, "brief_path": str(path)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/prospects/{prospect_id}/enrich")
def enrich_prospect_product_route(prospect_id: str, payload: ProspectEnrichActionRequest | None = None):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    request = payload or ProspectEnrichActionRequest()
    leadership_sources = request.leadership_sources or prospect.get("leadership_sources") or None
    domain = request.domain if request.domain is not None else prospect.get("domain")
    use_playwright = request.use_playwright if payload is not None else bool(prospect.get("use_playwright"))
    peers_limit = request.peers_limit if payload is not None else int(prospect.get("peers_limit") or 10)
    try:
        hiring = run_hiring_signal_enrichment(
            prospect["company"],
            domain=domain,
            leadership_sources=leadership_sources,
            out_dir="data/briefs",
            use_playwright=use_playwright,
        )
        from agent.enrichment.competitor_gap import (
            produce_competitor_gap_brief,
            write_competitor_gap_brief_file,
        )

        competitor_gap_brief = produce_competitor_gap_brief(
            prospect["company"],
            hiring_brief=hiring["brief"],
            peers_limit=peers_limit,
        )
        competitor_gap = {
            "brief": competitor_gap_brief,
            "brief_path": str(write_competitor_gap_brief_file(competitor_gap_brief, out_dir="data/briefs")),
        }
        crm = enrich_and_write_contact(
            ProspectEnrichmentRequest(
                email=prospect["email"],
                company_name=prospect["company"],
                phone=prospect.get("phone"),
                domain=domain,
                leadership_sources=request.leadership_sources or prospect.get("leadership_sources") or [],
            )
        )
        update_prospect(
            prospect_id=prospect_id,
            patch={
                "domain": domain,
                "use_playwright": use_playwright,
                "peers_limit": peers_limit,
            },
        )
        updated = _store_enrichment_result(
            prospect_id=prospect_id,
            prospect=prospect,
            hiring=hiring,
            competitor_gap=competitor_gap,
            crm=crm,
        )
        return {"status": "ok", "prospect": updated, "hiring": hiring, "competitor_gap": competitor_gap, "crm": crm}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/prospects/{prospect_id}/send-outreach")
def send_outreach_route(prospect_id: str, payload: EmailSendRequest | None = None):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    request = payload or EmailSendRequest(
        to=[str(prospect["email"])],
        subject=str(prospect.get("email_subject") or f"Quick signal review for {prospect['company']}"),
        text=str(prospect.get("email_text") or ""),
    )
    if request.to != [prospect["email"]]:
        request = EmailSendRequest(
            to=[str(prospect["email"])],
            subject=request.subject,
            text=request.text,
            html=request.html,
            from_email=request.from_email,
            reply_to=request.reply_to,
            tags=request.tags,
        )
    return send_email_route(request)


@app.post("/prospects/{prospect_id}/generate-email")
def generate_email_route(prospect_id: str, payload: GenerateEmailRequest | None = None):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    hiring_brief = prospect.get("latest_hiring_brief") if isinstance(prospect.get("latest_hiring_brief"), dict) else None
    competitor_gap_brief = (
        prospect.get("latest_competitor_gap_brief") if isinstance(prospect.get("latest_competitor_gap_brief"), dict) else None
    )
    qualification = prospect.get("qualification") if isinstance(prospect.get("qualification"), dict) else None

    if not hiring_brief or not competitor_gap_brief or not qualification:
        raise HTTPException(
            status_code=400,
            detail="Generate Email requires enrichment and ICP classification first.",
        )

    generated = generate_outreach_email(
        company_name=str(prospect["company"]),
        prospect_name=str(prospect.get("prospect_name") or ""),
        qualification=qualification,
        hiring_brief=hiring_brief,
        competitor_gap_brief=competitor_gap_brief,
    )
    request = payload or GenerateEmailRequest()
    generation_metadata = {
        "generated_at": _utc_now(),
        "prospect_id": prospect_id,
        "thread_id": str(prospect.get("thread_id") or build_thread_id(str(prospect["company"]))),
        "icp_segment": str(qualification.get("segment") or "abstain"),
        "icp_confidence": float(qualification.get("confidence") or 0.0),
        "signals_used": list(generated.get("source", {}).get("signals_used") or []),
        "generation_mode": str(generated.get("source", {}).get("generation_mode") or "fallback_generic"),
    }
    patch = {
        "email_subject": generated["subject"],
        "email_text": generated["text"],
        "email_source": generated["source"],
        "email_warning": generated.get("warning"),
        "email_generated": True,
        "email_generated_at": generation_metadata["generated_at"],
        "email_generation_metadata": generation_metadata,
    }
    if request.approval_reset:
        patch["email_approved"] = False
    updated = update_prospect(prospect_id=prospect_id, patch=patch)
    append_activity(
        prospect_id=prospect_id,
        activity={
            "type": "email_generated",
            "title": "Email generated",
            "description": generated["subject"],
        },
    )
    return {"status": "ok", "email": generated, "generation_metadata": generation_metadata, "prospect": updated}


@app.post("/prospects/{prospect_id}/approve-email")
def approve_email_route(prospect_id: str, payload: ApproveEmailRequest | None = None):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    request = payload or ApproveEmailRequest()
    approved = bool(request.approved)
    updated = update_prospect(
        prospect_id=prospect_id,
        patch={"email_approved": approved},
    )
    append_activity(
        prospect_id=prospect_id,
        activity={
            "type": "email_approved",
            "title": "Email approved" if approved else "Email approval reset",
            "description": "Outbound content approved for send." if approved else "Email requires approval before send.",
        },
    )
    return {"status": "ok", "approved": approved, "prospect": updated}


@app.post("/prospects/{prospect_id}/process-reply")
def process_reply_route(prospect_id: str, payload: ManualReplyRequest):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    reply_text = payload.text or prospect.get("last_reply_text")
    if not isinstance(reply_text, str) or not reply_text.strip():
        raise HTTPException(status_code=400, detail="Reply text is required unless a webhook reply is already stored for this prospect.")
    event = EmailEvent(
        event_type="reply",
        message_id=payload.message_id or str(prospect.get("last_reply_message_id") or prospect.get("last_message_id") or f"reply_{prospect_id}"),
        sender=str(prospect["email"]),
        subject=payload.subject or str(prospect.get("last_reply_subject") or prospect.get("email_subject") or ""),
        text=reply_text.strip(),
        html=str(prospect.get("last_reply_html")) if prospect.get("last_reply_html") else None,
        to=[str(item) for item in prospect.get("last_reply_to") or [] if isinstance(item, str)],
        received_at=str(prospect.get("last_reply_received_at")) if prospect.get("last_reply_received_at") else None,
        provider_event_type="manual.process_reply" if payload.text else "stored.webhook_reply",
        raw_payload={"source": "manual_process_reply" if payload.text else "stored_webhook_reply"},
    )
    try:
        return _process_reply_event(event)
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/prospects/{prospect_id}/send-booking-link")
def send_booking_link_route(prospect_id: str, payload: SendBookingLinkRequest | None = None):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    try:
        result = _send_booking_link(email=str(prospect["email"]), subject=payload.subject if payload else None)
        return {"status": "sent", **result}
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/prospects/{prospect_id}/sync-booking")
def sync_booking_route(prospect_id: str, payload: SyncBookingRequest):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    
    # Fetch detailed booking information from Cal.com
    calcom_booking = _fetch_calcom_booking(payload.booking_id)
    
    # Create booking artifact with all required details
    booking_artifact = {
        "status": payload.booking_status.lower(),
        "event_type": payload.title or f"Discovery call with Tenacious delivery lead",
        "attendee_name": payload.attendee_name or str(prospect.get("prospect_name") or ""),
        "attendee_email": payload.attendee_email or str(prospect["email"]),
        "start_time": payload.start_time,
        "timezone": payload.timezone or "UTC",
        "calcom_booking_id": payload.booking_id,
        "calcom_uid": calcom_booking.get("uid") if calcom_booking else None,
        "synced_at": _utc_now(),
        "raw_calcom_data": calcom_booking,
    }
    
    # Store booking artifact in prospect record
    updated_prospect = update_prospect(
        prospect_id=prospect_id,
        patch={
            "booking_artifact": booking_artifact,
            "booking_status": payload.booking_status.lower(),
            "booking_start_time": payload.start_time,
            "booking_title": payload.title,
        }
    )
    
    event = CalendarEvent(
        event_type="booking_confirmed",
        booking_id=payload.booking_id,
        email=str(prospect["email"]),
        booking_status=payload.booking_status.lower(),
        attendee_name=booking_artifact["attendee_name"],
        start_time=payload.start_time,
        title=payload.title or f"{prospect['company']} discovery call",
        raw_payload={"source": "manual_sync_booking", "booking_artifact": booking_artifact},
    )
    
    try:
        result = _process_calendar_event(event)
        # Include booking artifact in response
        result["booking_artifact"] = booking_artifact
        return result
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/prospects/{prospect_id}/refresh-crm")
def refresh_crm_route(prospect_id: str):
    prospect = get_prospect(prospect_id=prospect_id)
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")
    payload = ProspectEnrichmentRequest(
        email=str(prospect["email"]),
        company_name=str(prospect["company"]),
        phone=prospect.get("phone"),
        domain=prospect.get("domain"),
        leadership_sources=prospect.get("leadership_sources") or [],
    )
    try:
        crm = enrich_and_write_contact(payload)
        enrichment = crm.get("enrichment") if isinstance(crm, dict) else {}
        updated = update_prospect(
            prospect_id=prospect_id,
            patch={
                "hubspot": crm.get("hubspot"),
                "thread_id": crm.get("thread_id") or prospect.get("thread_id"),
                "qualification": {
                    "segment": enrichment.get("segment"),
                    "confidence": enrichment.get("confidence"),
                    "pitch_angle": enrichment.get("pitch_angle"),
                }
                if isinstance(enrichment, dict)
                else prospect.get("qualification"),
                "lifecycle_stage": "Qualified" if enrichment else prospect.get("lifecycle_stage"),
            },
        )
        return {"status": "ok", "prospect": updated, "crm": crm}
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/calendar/book")
def create_booking_route(payload: CalcomBookingRequest):
    try:
        result = create_calcom_booking(payload)
        try:
            try:
                from agent.enrichment.cache import get_cache

                identity = get_cache(
                    "prospect_identity",
                    payload.email.casefold(),
                    max_age_seconds=365 * 24 * 3600,
                )
            except Exception:
                identity = None
            log_event(
                email=payload.email,
                event_type="call_booked",
                data=build_event_context(
                    prospect_email=payload.email,
                    identity=identity if isinstance(identity, dict) else {"company_name": payload.company_name},
                    extra={
                        "provider": "cal.com",
                        "booking": result,
                        "booking_id": _extract_booking_id(result),
                        "event_type": "Discovery Call with Tenacious Delivery Lead",
                        "attendee_name": payload.name,
                        "attendee_email": payload.email,
                        "scheduled_start_time": payload.start,
                        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    },
                ),
            )
            set_lifecycle_stage(
                email=payload.email,
                stage=os.getenv("HUBSPOT_STAGE_CALL_BOOKED", "appointmentscheduled"),
            )
        except Exception as exc:  # pragma: no cover
            print("HUBSPOT EVENT LOGGING ERROR (call_booked):", str(exc))
        return {"status": "booked", "provider": "cal.com", "result": result}
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/sms/send")
def send_sms_route(payload: SMSSendRequest):
    try:
        result = send_sms_to_warm_lead(payload)
        for recipient in payload.to:
            try:
                log_event(
                    phone=recipient,
                    event_type="sms_sent",
                    data={
                        "provider": "africas_talking",
                        "message": payload.message,
                        "result": result,
                    },
                )
            except Exception as exc:  # pragma: no cover
                print("HUBSPOT EVENT LOGGING ERROR (sms_sent):", str(exc))
        return {"status": "sent", "provider": "africas_talking", "result": result}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


async def _handle_email_webhook_payload(payload: dict[str, Any]):
    try:
        event = _parse_email_event(payload)
        if event.event_type == "reply":
            return _process_reply_event(event)
        elif event.event_type == "delivery":
            recipients = [recipient for recipient in event.to if recipient]
            for recipient in recipients:
                update_prospect(
                    email=recipient,
                    patch={
                        "last_delivery_event": event.provider_event_type,
                        "last_delivery_message_id": event.message_id,
                        "last_delivery_at": event.received_at,
                    },
                )
                append_activity(
                    email=recipient,
                    activity={
                        "type": str(event.provider_event_type or "email_delivery"),
                        "title": str(event.provider_event_type or "Email delivery").replace("email.", "Email ").replace("_", " ").title(),
                        "description": event.subject or event.message_id,
                    },
                )
            return {
                "status": "accepted",
                "event_type": event.provider_event_type or event.event_type,
                "message_id": event.message_id,
                "delivery_recipients": recipients,
            }
        elif event.event_type == "bounce":
            emit_email_event(event)
            try:
                log_event(
                    email=event.sender,
                    event_type="email_bounce_received",
                    data={"message_id": event.message_id, "reason": event.text},
                )
            except Exception as exc:  # pragma: no cover
                print("HUBSPOT EVENT LOGGING ERROR (email_bounce_received):", str(exc))
        return {
            "status": "accepted",
            "event_type": event.event_type,
            "message_id": event.message_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email event handling failed: {exc}") from exc


@app.post("/emails/webhook")
async def email_webhook(request: Request):
    payload = await _read_json_payload(request, "Malformed webhook payload")
    return await _handle_email_webhook_payload(payload)


@app.post("/emails/webhook/mailersend")
async def mailersend_email_webhook(request: Request):
    payload = await _read_json_payload(request, "Malformed MailerSend webhook payload")
    return await _handle_email_webhook_payload(payload)


@app.post("/calendar/webhook")
async def calendar_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        raw = (await request.body()).decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=400,
            detail={"error": "Malformed calendar webhook payload", "raw": raw},
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Malformed calendar webhook payload")

    try:
        event = _parse_calendar_event(payload)
        return _process_calendar_event(event)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Calendar event handling failed: {exc}") from exc


@app.post("/sms/webhook")
async def sms_webhook(request: Request):
    try:
        payload = await _read_sms_webhook_payload(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        event = _parse_sms_event(payload)
        emit_sms_event(event)
        try:
            log_event(
                phone=event.sender,
                event_type="sms_reply_received",
                data={"message_id": event.message_id, "text": event.text},
            )
        except Exception as exc:  # pragma: no cover
            print("HUBSPOT EVENT LOGGING ERROR (sms_webhook):", str(exc))
        return {
            "status": "accepted",
            "event_type": event.event_type,
            "message_id": event.message_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"SMS event handling failed: {exc}") from exc


@app.post("/contacts")
def create_contact_route(payload: ContactIn):
    try:
        return create_contact(payload.email, payload.phone)
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "HUBSPOT_API_KEY or HUBSPOT_TOKEN is not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
