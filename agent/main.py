import os
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Conversion Engine Agent")


def _hubspot_api_key() -> str:
    api_key = os.getenv("HUBSPOT_API_KEY")
    if not api_key:
        raise RuntimeError("HUBSPOT_API_KEY is not set")
    return api_key


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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/contacts")
def create_contact_route(payload: ContactIn):
    try:
        return create_contact(payload.email, payload.phone)
    except RuntimeError as exc:
        message = str(exc)
        status_code = 500 if "HUBSPOT_API_KEY is not set" in message else 502
        raise HTTPException(status_code=status_code, detail=message) from exc
