import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from agent import hubspot_mcp


class TestHubSpotNoteFormatting(unittest.TestCase):
    def test_event_note_body_is_human_readable(self) -> None:
        body = hubspot_mcp._format_note_body(
            contact_id="12345",
            email="bethelyohannes4@gmail.com",
            event_type="enrichment_completed",
            occurred_at=datetime(2026, 4, 25, 8, 30, tzinfo=timezone.utc),
            body_json={
                "company_name": "Consolety",
                "thread_id": "thread_consolety_001",
                "firmographics": {"employees": "11-50"},
                "funding": {"round_type": "series_b"},
                "job_signals": {"engineering_roles": 5},
                "layoffs": {"had_layoff": False},
                "leadership": {"new_leader_detected": True},
                "ai_maturity": {"score": 3},
                "icp_classification": {"segment": "abstain"},
            },
        )

        self.assertIn("EVENT: enrichment_completed", body)
        self.assertIn("Contact ID: 12345", body)
        self.assertIn("Company: Consolety", body)
        self.assertIn("Email: bethelyohannes4@gmail.com", body)
        self.assertIn("Thread ID: thread_consolety_001", body)
        self.assertIn("Timestamp: 2026-04-25T08:30:00+00:00", body)
        self.assertIn("Firmographics:", body)
        self.assertIn("Funding:", body)
        self.assertIn("Job signals:", body)
        self.assertIn("Layoffs:", body)
        self.assertIn("Leadership:", body)
        self.assertIn("AI maturity:", body)
        self.assertIn("ICP classification:", body)
        self.assertIn("Data:", body)
        self.assertIn('"company_name": "Consolety"', body)

    def test_qualification_note_includes_summary_fields(self) -> None:
        body = hubspot_mcp._format_note_body(
            contact_id="12345",
            email="bethelyohannes4@gmail.com",
            event_type="qualification_complete",
            occurred_at=datetime(2026, 4, 25, 8, 30, tzinfo=timezone.utc),
            body_json={
                "segment": "abstain",
                "confidence": 0.15,
                "pitch_angle": "exploratory_generic",
            },
        )

        self.assertIn("EVENT: qualification_complete", body)
        self.assertIn("Segment: abstain", body)
        self.assertIn("Confidence: 0.15", body)
        self.assertIn("Pitch angle: exploratory_generic", body)


class TestHubSpotEnrichmentProperties(unittest.TestCase):
    def test_build_standard_contact_properties_maps_only_standard_fields(self) -> None:
        properties = hubspot_mcp.build_standard_contact_properties(
            email="lead@example.com",
            company_name="Stripe",
            firstname="Ada",
            lastname="Lovelace",
            lifecyclestage="salesqualifiedlead",
            hs_lead_status="OPEN",
        )

        self.assertEqual(properties["company"], "Stripe")
        self.assertEqual(properties["firstname"], "Ada")
        self.assertEqual(properties["lastname"], "Lovelace")
        self.assertEqual(properties["lifecyclestage"], "salesqualifiedlead")
        self.assertEqual(properties["hs_lead_status"], "OPEN")
        self.assertEqual(
            set(properties.keys()),
            {"email", "company", "firstname", "lastname", "lifecyclestage", "hs_lead_status"},
        )

    @patch("agent.hubspot_mcp._request")
    def test_write_enriched_contact_updates_standard_fields_only_when_optional_patch_fails(self, mock_request) -> None:
        def side_effect(method: str, path: str, *, json_body=None):
            if method == "POST" and path == "/crm/v3/objects/contacts/search":
                return {"results": [{"id": "123"}]}
            if method == "PATCH" and path == "/crm/v3/objects/contacts/123":
                if "tenacious_icp_segment" in json_body["properties"]:
                    raise RuntimeError("HubSpot MCP error 403: MISSING_SCOPES")
                return {"id": "123", "properties": json_body["properties"]}
            raise AssertionError(f"Unexpected request: {method} {path}")

        mock_request.side_effect = side_effect

        result = hubspot_mcp.write_enriched_contact(
            email="lead@example.com",
            phone="+15551234567",
            company_name="Stripe",
            icp_segment="segment_1",
            enrichment={
                "confidence": 0.91,
                "pitch_angle": "fresh_funding_scale_execution",
                "signals": {
                    "company": {"num_employees": "11-50", "industries": ["B2B SaaS"]},
                    "funding": {"round_type": "series_b", "amount_usd": 14000000, "days_ago": 45},
                    "jobs": {"engineering_roles": 8, "velocity_60d": 1.667, "_confidence": "high"},
                    "layoffs": {"had_layoff": False, "days_ago": None},
                    "leadership_change": {"new_leader_detected": False, "role": ""},
                    "ai_maturity": {"score": 2, "_confidence": "medium"},
                },
            },
        )

        self.assertEqual(result["id"], "123")
        patch_calls = [
            call for call in mock_request.call_args_list if call.args[0] == "PATCH"
        ]
        self.assertEqual(len(patch_calls), 2)
        updated_properties = patch_calls[0].kwargs["json_body"]["properties"]
        self.assertEqual(updated_properties["email"], "lead@example.com")
        self.assertEqual(updated_properties["company"], "Stripe")
        self.assertEqual(updated_properties["lifecyclestage"], "salesqualifiedlead")
        self.assertEqual(updated_properties["hs_lead_status"], "OPEN")
        self.assertFalse(
            any(
                call.args[1] == "/crm/v3/properties/contacts"
                for call in mock_request.call_args_list
            )
        )


if __name__ == "__main__":
    unittest.main()
