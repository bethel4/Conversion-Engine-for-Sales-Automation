from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import uvicorn


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
DEMO_DIR = REPO_ROOT / "data" / "demo"
PROSPECTS_PATH = DEMO_DIR / "prospects_demo.json"
HUBSPOT_STATE_PATH = DEMO_DIR / "hubspot_mock_state.json"
PROVIDER_LOG_PATH = DEMO_DIR / "provider_mock_log.jsonl"
SIGNALFORGE_BRIEF_PATH = DEMO_DIR / "hiring_signal_brief_signalforge_demo.json"


class DummyResponse:
    def __init__(
        self,
        *,
        ok: bool = True,
        status_code: int = 200,
        json_body: dict[str, Any] | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.ok = ok
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = text if text else json.dumps(self._json_body)
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        return self._json_body


def _ensure_demo_files() -> None:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    if not PROSPECTS_PATH.exists():
        PROSPECTS_PATH.write_text(
            json.dumps(
                [
                    {
                        "id": "consolety",
                        "prospect_name": "Bethel Yohannes",
                        "company": "Consolety",
                        "email": "bethelyohannes4@gmail.com",
                        "domain": "consolety.net",
                        "phone": "+251900000001",
                        "crunchbase_id": "consolety",
                        "thread_id": "thread_consolety_001",
                        "lifecycle_stage": "New",
                        "email_subject": "Quick signal review for Consolety",
                        "email_text": "Saw a few public signals around Consolety that may be worth a closer look. Open to a short exchange?",
                        "reply_text": "Yes — can you share what you found?",
                        "booking_id": "booking-consolety-001",
                        "use_playwright": False,
                        "peers_limit": 10,
                        "activity": [],
                    },
                    {
                        "id": "signalforge",
                        "prospect_name": "Aster Vale",
                        "company": "SignalForge",
                        "email": "aster@signalforge.example",
                        "domain": "signalforge.example",
                        "phone": "+251900000002",
                        "crunchbase_id": "signalforge",
                        "thread_id": "thread_signalforge_001",
                        "lifecycle_stage": "New",
                        "email_subject": "Capacity note for SignalForge",
                        "email_text": "We mapped your current hiring and platform signals. Worth a quick compare on execution bandwidth?",
                        "reply_text": "Yes, send me the details.",
                        "booking_id": "booking-signalforge-001",
                        "use_playwright": False,
                        "peers_limit": 10,
                        "activity": [],
                    },
                ],
                indent=2,
            ),
            encoding="utf-8",
        )
    if not HUBSPOT_STATE_PATH.exists():
        HUBSPOT_STATE_PATH.write_text(json.dumps({"contacts": {}, "notes": {}, "events": []}, indent=2), encoding="utf-8")
    PROVIDER_LOG_PATH.write_text("", encoding="utf-8")


def _load_hubspot_state() -> dict[str, Any]:
    return json.loads(HUBSPOT_STATE_PATH.read_text(encoding="utf-8"))


def _save_hubspot_state(state: dict[str, Any]) -> None:
    HUBSPOT_STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _append_provider_log(entry: dict[str, Any]) -> None:
    with PROVIDER_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _signalforge_brief() -> dict[str, Any]:
    return {
        "company": {
            "_confidence": "high",
            "name": "SignalForge",
            "crunchbase_id": "signalforge",
            "crunchbase_url": "https://www.crunchbase.com/organization/signalforge",
            "country_code": "US",
            "industries": ["Developer APIs", "Machine Learning", "Software"],
            "num_employees": "11-50",
            "website": "https://signalforge.example",
        },
        "funding": {
            "_confidence": "high",
            "funded": True,
            "days_ago": 32,
            "amount_usd": 12500000,
            "round_type": "series_b",
            "confidence": "high",
        },
        "jobs": {
            "_confidence": "high",
            "total_open_roles": 14,
            "engineering_roles": 8,
            "ai_ml_roles": 3,
            "velocity_60d": 1.75,
            "signal_strength": "strong",
            "source_url": "https://signalforge.example/careers",
        },
        "layoffs": {
            "_confidence": "high",
            "had_layoff": False,
            "days_ago": 0,
            "headcount_cut": 0,
            "percentage_cut": 0.0,
            "segment_implication": None,
            "confidence": "high",
        },
        "leadership_change": {
            "_confidence": "high",
            "new_leader_detected": True,
            "role": "cto",
            "name": "Mira Stone",
            "days_ago": 18,
            "confidence": "high",
            "source": "press-release",
        },
        "ai_maturity": {
            "_confidence": "high",
            "score": 3,
            "confidence": "high",
            "evidence_count": 5,
            "justification": {
                "raw_points": 3.25,
                "per_signal": {
                    "ai_hiring": {"points": 1.0, "weight": "high", "evidence": {"ai_ml_roles": 3, "engineering_roles": 8, "ratio": 0.375}},
                    "ai_leadership": {"points": 1.0, "weight": "high", "evidence": {"has_head_of_ai": True}},
                    "github_ai_activity": {"points": 0.5, "weight": "medium", "evidence": {"github_ai_repos": 2}},
                    "exec_mentions": {"points": 0.5, "weight": "medium", "evidence": {"exec_llm_mentions": True}},
                    "ai_product": {"points": 0.5, "weight": "medium", "evidence": {"ai_product_on_site": True}},
                    "ai_case_studies": {"points": 0.25, "weight": "low", "evidence": {"ai_case_studies": True}},
                },
            },
            "pitch_language_hint": "assert",
        },
        "tech_stack": {
            "_confidence": "high",
            "confidence": "high",
            "count": 7,
            "technologies": ["Python", "FastAPI", "Snowflake", "dbt", "Kubernetes", "OpenAI", "LangChain"],
        },
        "meta": {
            "generated_at": "2026-04-25",
            "inputs": {
                "domain": "signalforge.example",
                "days_funding": 180,
                "days_jobs_back": 60,
                "days_layoffs": 120,
                "days_leadership": 90,
            },
        },
    }


def _signalforge_enrichment_result() -> dict[str, Any]:
    brief = _signalforge_brief()
    SIGNALFORGE_BRIEF_PATH.write_text(json.dumps(brief, indent=2, sort_keys=True), encoding="utf-8")
    return {"brief": brief, "brief_path": str(SIGNALFORGE_BRIEF_PATH)}


def _signalforge_icp(_: dict[str, Any]) -> dict[str, Any]:
    return {
        "segment": "segment_1",
        "confidence": 0.93,
        "pitch_angle": "fresh_funding_scale_execution",
        "scores": {"segment_1": 0.93, "segment_2": 0.02, "segment_3": 0.4, "segment_4": 0.68},
        "reasoning": {"funding": {"funded": True}, "jobs": {"engineering_roles": 8}},
        "disqualifiers": {},
    }


def _patch_runtime() -> Any:
    os.environ.setdefault("LIVE_OUTBOUND", "true")
    os.environ.setdefault("EMAIL_PROVIDER", "resend")
    os.environ.setdefault("RESEND_API_KEY", "demo-resend-key")
    os.environ.setdefault("RESEND_FROM_EMAIL", "sales@tenacious.example")
    os.environ.setdefault("AFRICASTALKING_USERNAME", "sandbox")
    os.environ.setdefault("AFRICASTALKING_API_KEY", "demo-at-key")
    os.environ.setdefault("AFRICASTALKING_SENDER_ID", "TENACITY")
    os.environ.setdefault("CALCOM_BOOKING_LINK", "https://cal.com/tenacious/discovery")
    os.environ.setdefault("HUBSPOT_API_KEY", "demo-hubspot-key")
    os.environ["PROSPECTS_STORE_PATH"] = str(PROSPECTS_PATH)

    from agent import hubspot_mcp, main
    from agent.enrichment import competitor_gap as competitor_gap_module

    def fake_provider_post(url: str, *args: Any, **kwargs: Any) -> DummyResponse:
        payload = kwargs.get("json") or kwargs.get("data") or {}
        _append_provider_log({"url": url, "payload": payload})
        if "resend.com" in url or "mailersend.com" in url:
            return DummyResponse(json_body={"id": f"email_{len(PROVIDER_LOG_PATH.read_text(encoding='utf-8').splitlines())}"})
        if "africastalking" in url:
            return DummyResponse(json_body={"SMSMessageData": {"Recipients": [{"status": "Success"}]}})
        if "cal.com" in url:
            return DummyResponse(json_body={"status": "accepted", "booking_id": "booking_demo_001"})
        return DummyResponse(ok=False, status_code=500, text="Unsupported provider URL")

    def fake_hubspot_request(method: str, url: str, *, headers: dict[str, str] | None = None, json: dict[str, Any] | None = None, timeout: int = 20) -> DummyResponse:
        path = url.split("https://api.hubapi.com", 1)[-1]
        state = _load_hubspot_state()
        contacts: dict[str, Any] = state["contacts"]
        notes: dict[str, Any] = state["notes"]
        events: list[dict[str, Any]] = state["events"]
        events.append({"method": method, "path": path, "json": json})

        if method == "POST" and path == "/crm/v3/objects/contacts/search":
            filters = ((json or {}).get("filterGroups") or [{}])[0].get("filters") or [{}]
            prop = filters[0].get("propertyName")
            value = filters[0].get("value")
            matches = []
            for contact_id, contact in contacts.items():
                properties = contact.get("properties", {})
                if properties.get(prop) == value:
                    matches.append({"id": contact_id, "properties": properties})
            _save_hubspot_state(state)
            return DummyResponse(json_body={"results": matches[:1]})

        if method == "POST" and path == "/crm/v3/objects/contacts":
            contact_id = str(len(contacts) + 1)
            contacts[contact_id] = {"id": contact_id, "properties": dict((json or {}).get("properties") or {})}
            _save_hubspot_state(state)
            return DummyResponse(json_body={"id": contact_id, "properties": contacts[contact_id]["properties"]})

        if method == "PATCH" and path.startswith("/crm/v3/objects/contacts/"):
            contact_id = path.rsplit("/", 1)[-1]
            contact = contacts.setdefault(contact_id, {"id": contact_id, "properties": {}})
            contact["properties"].update(dict((json or {}).get("properties") or {}))
            _save_hubspot_state(state)
            return DummyResponse(json_body={"id": contact_id, "properties": contact["properties"]})

        if method == "POST" and path == "/crm/v3/objects/notes":
            note_id = str(len(notes) + 1)
            notes[note_id] = {"id": note_id, "properties": dict((json or {}).get("properties") or {}), "associations": []}
            _save_hubspot_state(state)
            return DummyResponse(json_body={"id": note_id})

        if method == "PUT" and "/crm/v4/objects/notes/" in path and "/associations/default/contacts/" in path:
            note_id = path.split("/crm/v4/objects/notes/")[1].split("/")[0]
            contact_id = path.rsplit("/", 1)[-1]
            note = notes.setdefault(note_id, {"id": note_id, "properties": {}, "associations": []})
            note["associations"].append(contact_id)
            _save_hubspot_state(state)
            return DummyResponse(json_body={})

        _save_hubspot_state(state)
        return DummyResponse(ok=False, status_code=404, text=f"Unhandled HubSpot path: {path}")

    real_run_hiring = main.run_hiring_signal_enrichment
    real_produce_brief = main.produce_hiring_signal_brief
    real_classify_icp = main.classify_icp
    real_competitor_gap = competitor_gap_module.produce_competitor_gap_brief

    def patched_run_hiring(company_name: str, **kwargs: Any) -> dict[str, Any]:
        if company_name.casefold() == "signalforge":
            return _signalforge_enrichment_result()
        return real_run_hiring(company_name, **kwargs)

    def patched_produce_brief(company_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if company_name.casefold() == "signalforge":
            return _signalforge_brief()
        return real_produce_brief(company_name, *args, **kwargs)

    def patched_classify_icp(brief: dict[str, Any]) -> dict[str, Any]:
        if brief.get("company", {}).get("name", "").casefold() == "signalforge":
            return _signalforge_icp(brief)
        return real_classify_icp(brief)

    def patched_competitor_gap(company_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        if company_name.casefold() == "signalforge":
            return {
                "company": {
                    "name": "SignalForge",
                    "crunchbase_url": "https://www.crunchbase.com/organization/signalforge",
                    "industries": ["Developer APIs", "Machine Learning"],
                    "num_employees": "11-50",
                },
                "prospect_percentile": 84,
                "peers": [
                    {
                        "name": "ForgePilot",
                        "url": "https://www.crunchbase.com/organization/forgepilot",
                        "num_employees": "11-50",
                        "industries": ["Developer APIs", "Machine Learning"],
                        "features": {"ai_tech_stack": True, "data_stack": True, "modern_cloud": True},
                        "ai_maturity": {"score": 3, "confidence": "high"},
                    }
                ],
                "gaps": [
                    {
                        "gap": "data_stack",
                        "confidence": "high",
                        "evidence": {"top_quartile_prevalence": 1.0, "sample_peers": ["ForgePilot"]},
                        "pitch_hook": "Top peers such as ForgePilot invest earlier in a modern data stack.",
                    }
                ],
                "meta": {
                    "generated_at": "2026-04-25",
                    "peer_count": 1,
                    "dataset_path": "synthetic-demo",
                    "method": "synthetic_demo",
                },
            }
        return real_competitor_gap(company_name, *args, **kwargs)

    main.requests.post = fake_provider_post
    main.run_hiring_signal_enrichment = patched_run_hiring
    main.produce_hiring_signal_brief = patched_produce_brief
    main.classify_icp = patched_classify_icp
    hubspot_mcp.requests.request = fake_hubspot_request
    competitor_gap_module.produce_competitor_gap_brief = patched_competitor_gap
    return main.app


def main() -> None:
    _ensure_demo_files()
    app = _patch_runtime()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
