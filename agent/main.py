import json
import os
from urllib.parse import parse_qs
from typing import Any, Callable, Literal, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.enrichment.briefs import produce_hiring_signal_brief
from agent.enrichment.pipeline import run_hiring_signal_enrichment
from agent.enrichment.icp import classify_icp
from agent.hubspot_mcp import (
    log_event,
    set_lifecycle_stage,
    write_booking_update,
    write_enriched_contact,
)

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
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
AFRICASTALKING_SMS_API_URL = "https://api.africastalking.com/version1/messaging"
CALCOM_API_URL = "https://api.cal.com/v1/bookings"
EmailEventType = Literal["reply", "bounce"]
SMSEventType = Literal["reply"]
CalendarEventType = Literal["booking_confirmed"]


def _hubspot_api_key() -> str:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY is not set")
    return api_key


def _calcom_api_key() -> str:
    api_key = os.getenv("CALCOM_API_KEY")
    if not api_key:
        raise RuntimeError("CALCOM_API_KEY is not set")
    return api_key


def _calcom_api_url() -> str:
    return os.getenv("CALCOM_API_URL", CALCOM_API_URL)


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
    start_time: Optional[str] = None
    title: Optional[str] = None
    raw_payload: dict[str, Any]


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
    if not payload.text and not payload.html:
        raise RuntimeError("Email payload must include text or html content")

    headers = {
        "Authorization": f"Bearer {_resend_api_key()}",
        "Content-Type": "application/json",
    }
    data = {
        "from": payload.from_email or _resend_from_email(),
        "to": payload.to,
        "subject": payload.subject,
        "text": payload.text,
        "html": payload.html,
        "reply_to": payload.reply_to,
        "tags": payload.tags,
    }

    try:
        response = requests.post(RESEND_API_URL, json=data, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"Resend send failed: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"Resend error {response.status_code}: {response.text}")

    return response.json()


def send_sms_to_warm_lead(payload: SMSSendRequest) -> dict[str, Any]:
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
            "funding": brief["funding"],
            "jobs": brief["jobs"],
            "layoffs": brief["layoffs"],
            "leadership_change": brief["leadership_change"],
            "ai_maturity": brief["ai_maturity"],
            "tech_stack": brief["tech_stack"],
        },
        "meta": brief["meta"],
    }
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
            },
        )
    except Exception as exc:  # pragma: no cover
        print("IDENTITY CACHE ERROR:", str(exc))
    try:
        log_event(
            email=payload.email,
            phone=payload.phone,
            event_type="enrichment_completed",
            data={"company_name": payload.company_name, "icp": icp, "brief_meta": brief.get("meta")},
        )
        log_event(
            email=payload.email,
            phone=payload.phone,
            event_type="qualified",
            data={"segment": icp["segment"], "confidence": icp["confidence"], "pitch_angle": icp["pitch_angle"]},
        )
    except Exception as exc:  # pragma: no cover
        print("HUBSPOT EVENT LOGGING ERROR (enrichment/qualified):", str(exc))
    return {"hubspot": hubspot, "enrichment": enrichment}


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


def _parse_email_event(payload: dict[str, Any]) -> EmailEvent:
    event_type = payload.get("type") or payload.get("event")
    if not isinstance(event_type, str):
        raise ValueError("Webhook payload is missing event type")

    normalized_type = event_type.lower()
    data = _extract_webhook_payload(payload)

    if "reply" in normalized_type or "received" in normalized_type:
        message_id = data.get("email_id") or data.get("id") or data.get("message_id")
        sender = data.get("from") or data.get("sender")
        recipients = data.get("to") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        if not message_id or not sender:
            raise ValueError("Reply webhook payload is missing message id or sender")
        return EmailEvent(
            event_type="reply",
            message_id=str(message_id),
            sender=str(sender),
            subject=data.get("subject"),
            text=data.get("text") or data.get("text_body"),
            html=data.get("html") or data.get("html_body"),
            to=[str(item) for item in recipients],
            raw_payload=payload,
        )

    if "bounce" in normalized_type:
        message_id = data.get("email_id") or data.get("id") or data.get("message_id")
        sender = data.get("from") or data.get("recipient")
        if not message_id or not sender:
            raise ValueError("Bounce webhook payload is missing message id or recipient")
        recipients = data.get("to") or data.get("recipient") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        return EmailEvent(
            event_type="bounce",
            message_id=str(message_id),
            sender=str(sender),
            subject=data.get("subject"),
            text=data.get("reason"),
            to=[str(item) for item in recipients],
            raw_payload=payload,
        )

    raise ValueError(f"Unsupported email webhook event type: {event_type}")


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


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {"raw": (await request.body()).decode("utf-8", errors="replace")}

    print("WEBHOOK RECEIVED:", data)

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
        for recipient in payload.to:
            try:
                log_event(
                    email=recipient,
                    event_type="email_sent",
                    data={
                        "provider": "resend",
                        "message_id": result.get("id"),
                        "subject": payload.subject,
                        "tags": payload.tags,
                    },
                )
            except Exception as exc:  # pragma: no cover
                print("HUBSPOT EVENT LOGGING ERROR (email_sent):", str(exc))
        return {"status": "sent", "provider": "resend", "result": result}
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


@app.post("/calendar/book")
def create_booking_route(payload: CalcomBookingRequest):
    try:
        result = create_calcom_booking(payload)
        try:
            log_event(
                email=payload.email,
                event_type="call_booked",
                data={
                    "provider": "cal.com",
                    "booking": result,
                    "company_name": payload.company_name,
                },
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


@app.post("/emails/webhook")
async def email_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as exc:
        raw = (await request.body()).decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=400,
            detail={"error": "Malformed webhook payload", "raw": raw},
        ) from exc

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Malformed webhook payload")

    try:
        event = _parse_email_event(payload)
        emit_email_event(event)
        try:
            if event.event_type == "reply":
                log_event(
                    email=event.sender,
                    event_type="email_reply_received",
                    data={
                        "message_id": event.message_id,
                        "subject": event.subject,
                        "text": event.text,
                    },
                )
                # Best-effort: qualify on reply by using cached identity from earlier enrichment.
                try:
                    from agent.enrichment.cache import get_cache

                    identity = get_cache(
                        "prospect_identity",
                        event.sender.casefold(),
                        max_age_seconds=365 * 24 * 3600,
                    )
                except Exception:
                    identity = None

                if isinstance(identity, dict) and identity.get("company_name"):
                    try:
                        enrich_and_write_contact(
                            ProspectEnrichmentRequest(
                                email=identity.get("email") or event.sender,
                                company_name=str(identity["company_name"]),
                                phone=identity.get("phone"),
                                domain=identity.get("domain"),
                                leadership_sources=identity.get("leadership_sources") or [],
                            )
                        )
                    except Exception as exc:  # pragma: no cover
                        print("AUTO-QUALIFICATION ERROR:", str(exc))

                # Optional: if you set a static booking link, send it after qualification.
                booking_link = os.getenv("CALCOM_BOOKING_LINK")
                if booking_link and isinstance(booking_link, str) and booking_link.strip():
                    try:
                        followup = send_email(
                            EmailSendRequest(
                                to=[event.sender],
                                subject="Quick booking link",
                                text=(
                                    "Thanks — if it’s helpful, here’s a direct booking link for a short call:\n"
                                    f"{booking_link.strip()}\n"
                                ),
                            )
                        )
                        log_event(
                            email=event.sender,
                            event_type="followup_booking_link_sent",
                            data={"booking_link": booking_link.strip(), "message_id": followup.get("id")},
                        )
                    except Exception as exc:  # pragma: no cover
                        print("FOLLOWUP BOOKING LINK ERROR:", str(exc))
            elif event.event_type == "bounce":
                log_event(
                    email=event.sender,
                    event_type="email_bounce_received",
                    data={"message_id": event.message_id, "reason": event.text},
                )
        except Exception as exc:  # pragma: no cover
            print("HUBSPOT EVENT LOGGING ERROR (email_webhook):", str(exc))
        return {
            "status": "accepted",
            "event_type": event.event_type,
            "message_id": event.message_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email event handling failed: {exc}") from exc


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
        emit_calendar_event(event)
        hubspot = write_booking_update(
            email=event.email,
            booking_id=event.booking_id,
            booking_status=event.booking_status,
            booking_start_time=event.start_time,
            booking_title=event.title,
        )
        try:
            if event.booking_status == "completed":
                log_event(
                    email=event.email,
                    event_type="call_completed",
                    data={"booking_id": event.booking_id, "title": event.title},
                )
                set_lifecycle_stage(
                    email=event.email,
                    stage=os.getenv("HUBSPOT_STAGE_CALL_COMPLETED", "customer"),
                )
            else:
                log_event(
                    email=event.email,
                    event_type="call_booked",
                    data={"booking_id": event.booking_id, "title": event.title},
                )
                set_lifecycle_stage(
                    email=event.email,
                    stage=os.getenv("HUBSPOT_STAGE_CALL_BOOKED", "appointmentscheduled"),
                )
        except Exception as exc:  # pragma: no cover
            print("HUBSPOT EVENT LOGGING ERROR (calendar_webhook):", str(exc))
        return {
            "status": "accepted",
            "event_type": event.event_type,
            "booking_id": event.booking_id,
            "hubspot": hubspot,
        }
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
        status_code = 500 if "HUBSPOT_API_KEY is not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
