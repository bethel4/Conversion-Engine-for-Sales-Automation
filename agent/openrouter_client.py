from __future__ import annotations

import json
import os
from typing import Any

import requests


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def is_enabled() -> bool:
    return bool((os.getenv("OPENROUTER_API_KEY") or "").strip())


def configured_model() -> str | None:
    model = (os.getenv("OPENROUTER_MODEL") or "").strip()
    return model or None


def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    api_key = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    model = configured_model()
    if not model:
        raise RuntimeError("OPENROUTER_MODEL is not set")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    site_url = (os.getenv("OPENROUTER_HTTP_REFERER") or "").strip()
    app_name = (os.getenv("OPENROUTER_APP_NAME") or "").strip()
    if site_url:
        headers["HTTP-Referer"] = site_url
    if app_name:
        headers["X-Title"] = app_name

    payload = {
        "model": model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        response = requests.post(OPENROUTER_API_URL, headers=headers, json=payload, timeout=45)
    except requests.RequestException as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

    if not response.ok:
        raise RuntimeError(f"OpenRouter error {response.status_code}: {response.text}")

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("OpenRouter returned non-JSON response") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"OpenRouter response missing content: {data}") from exc

    if not isinstance(content, str):
        raise RuntimeError("OpenRouter returned non-string content")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenRouter returned invalid JSON content: {content}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("OpenRouter JSON content must be an object")
    return parsed
