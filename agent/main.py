import json
import os
from typing import Any, Callable, Literal, Optional

import requests
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

app = FastAPI(title="Conversion Engine Agent")

RESEND_API_URL = "https://api.resend.com/emails"
AFRICASTALKING_SMS_API_URL = "https://api.africastalking.com/version1/messaging"
EmailEventType = Literal["reply", "bounce"]
SMSEventType = Literal["reply"]


def _hubspot_api_key() -> str:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY is not set")
    return api_key


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
    url = "https://api.hubapi.com/crm/v3/objects/contacts"

    headers = {
        "Authorization": f"Bearer {_hubspot_api_key()}",
        "Content-Type": "application/json"
    }

    data = {
        "properties": {
            "email": email,
            "phone": phone
        }
    }

    try:
        response = requests.post(url, json=data, headers=headers, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"HubSpot request failed: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"HubSpot error {response.status_code}: {response.text}")

    return response.json()


class ContactIn(BaseModel):
    email: str = Field(..., min_length=3)
    phone: Optional[str] = None


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


EmailEventHandler = Callable[[EmailEvent], None]
SMSEventHandler = Callable[[SMSEvent], None]


def _default_email_event_handler(event: EmailEvent) -> None:
    # Default behavior is explicit and observable until a downstream handler is attached.
    print("EMAIL EVENT:", event.model_dump())


def _default_sms_event_handler(event: SMSEvent) -> None:
    # Default behavior is explicit and observable until a downstream handler is attached.
    print("SMS EVENT:", event.model_dump())


email_event_handler: EmailEventHandler = _default_email_event_handler
sms_event_handler: SMSEventHandler = _default_sms_event_handler


def set_email_event_handler(handler: EmailEventHandler) -> None:
    # Downstream systems can register their own callback without changing the webhook route.
    global email_event_handler
    email_event_handler = handler


def set_sms_event_handler(handler: SMSEventHandler) -> None:
    # Downstream systems can register their own callback without changing the webhook route.
    global sms_event_handler
    sms_event_handler = handler


def emit_email_event(event: EmailEvent) -> None:
    email_event_handler(event)


def emit_sms_event(event: SMSEvent) -> None:
    sms_event_handler(event)


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


async def _read_sms_webhook_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        payload = await request.json()
        if not isinstance(payload, dict):
            raise ValueError("Malformed SMS webhook payload")
        return payload

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        payload: dict[str, Any] = {}
        for key, value in form.multi_items():
            payload[key] = str(value)
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
        return {"status": "sent", "provider": "resend", "result": send_email(payload)}
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc


@app.post("/sms/send")
def send_sms_route(payload: SMSSendRequest):
    try:
        result = send_sms_to_warm_lead(payload)
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
        return {
            "status": "accepted",
            "event_type": event.event_type,
            "message_id": event.message_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Email event handling failed: {exc}") from exc


@app.post("/sms/webhook")
async def sms_webhook(request: Request):
    try:
        payload = await _read_sms_webhook_payload(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        event = _parse_sms_event(payload)
        emit_sms_event(event)
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
