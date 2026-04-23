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
EmailEventType = Literal["reply", "bounce"]


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


EmailEventHandler = Callable[[EmailEvent], None]


def _default_email_event_handler(event: EmailEvent) -> None:
    # Default behavior is explicit and observable until a downstream handler is attached.
    print("EMAIL EVENT:", event.model_dump())


email_event_handler: EmailEventHandler = _default_email_event_handler


def set_email_event_handler(handler: EmailEventHandler) -> None:
    # Downstream systems can register their own callback without changing the webhook route.
    global email_event_handler
    email_event_handler = handler


def emit_email_event(event: EmailEvent) -> None:
    email_event_handler(event)


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


@app.post("/contacts")
def create_contact_route(payload: ContactIn):
    try:
        return create_contact(payload.email, payload.phone)
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "HUBSPOT_API_KEY is not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
