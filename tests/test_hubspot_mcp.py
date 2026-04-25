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
                "icp": {"segment": "abstain"},
            },
        )

        self.assertIn("EVENT: enrichment_completed", body)
        self.assertIn("Contact ID: 12345", body)
        self.assertIn("Company: Consolety", body)
        self.assertIn("Email: bethelyohannes4@gmail.com", body)
        self.assertIn("Thread ID: thread_consolety_001", body)
        self.assertIn("Timestamp: 2026-04-25T08:30:00+00:00", body)
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
    def test_build_enriched_contact_properties_maps_requested_fields(self) -> None:
        properties = hubspot_mcp.build_enriched_contact_properties(
            email="lead@example.com",
            phone="+15551234567",
            company_name="Stripe",
            icp_segment="segment_1",
            enrichment={
                "confidence": 0.91,
                "pitch_angle": "fresh_funding_scale_execution",
                "signals": {
                    "company": {
                        "num_employees": "11-50",
                        "industries": ["B2B SaaS", "Payments"],
                    },
                    "funding": {
                        "round_type": "series_b",
                        "amount_usd": 14000000,
                        "days_ago": 45,
                    },
                    "jobs": {
                        "engineering_roles": 8,
                        "velocity_60d": 1.667,
                        "_confidence": "high",
                    },
                    "layoffs": {
                        "had_layoff": False,
                        "days_ago": None,
                    },
                    "leadership_change": {
                        "new_leader_detected": True,
                        "role": "cto",
                    },
                    "ai_maturity": {
                        "score": 3,
                        "_confidence": "medium",
                    },
                },
            },
        )

        self.assertEqual(properties["company"], "Stripe")
        self.assertEqual(properties["tenacious_company_size"], "11-50")
        self.assertEqual(properties["tenacious_industry"], "B2B SaaS, Payments")
        self.assertEqual(properties["tenacious_funding_stage"], "series_b")
        self.assertEqual(properties["tenacious_funding_amount"], 14000000)
        self.assertEqual(properties["tenacious_funding_days_ago"], 45)
        self.assertEqual(properties["tenacious_engineering_roles"], 8)
        self.assertEqual(properties["tenacious_job_velocity_60d"], 1.667)
        self.assertEqual(properties["tenacious_job_signal_confidence"], "high")
        self.assertEqual(properties["tenacious_layoff_detected"], False)
        self.assertEqual(properties["tenacious_layoff_days_ago"], 0)
        self.assertEqual(properties["tenacious_leadership_change"], True)
        self.assertEqual(properties["tenacious_leadership_role"], "cto")
        self.assertEqual(properties["tenacious_ai_maturity_score"], 3)
        self.assertEqual(properties["tenacious_ai_maturity_confidence"], "medium")
        self.assertEqual(properties["tenacious_icp_segment"], "segment_1")
        self.assertEqual(properties["tenacious_icp_confidence"], 0.91)
        self.assertTrue(properties["tenacious_enrichment_timestamp"])

    @patch("agent.hubspot_mcp._request")
    def test_write_enriched_contact_creates_missing_properties_then_updates_contact(self, mock_request) -> None:
        def side_effect(method: str, path: str, *, json_body=None):
            if method == "GET" and path.startswith("/crm/v3/properties/contacts/"):
                raise RuntimeError("HubSpot MCP error 404: not found")
            if method == "POST" and path == "/crm/v3/objects/contacts/search":
                return {"results": [{"id": "123"}]}
            if method == "PATCH" and path == "/crm/v3/objects/contacts/123":
                return {"id": "123", "properties": json_body["properties"]}
            if method == "POST" and path == "/crm/v3/properties/contacts":
                return {"name": json_body["name"]}
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
        self.assertEqual(len(patch_calls), 1)
        updated_properties = patch_calls[0].kwargs["json_body"]["properties"]
        self.assertEqual(updated_properties["tenacious_icp_segment"], "segment_1")
        self.assertEqual(updated_properties["tenacious_engineering_roles"], 8)
        created_property_names = [
            call.kwargs["json_body"]["name"]
            for call in mock_request.call_args_list
            if call.args[0] == "POST" and call.args[1] == "/crm/v3/properties/contacts"
        ]
        self.assertIn("tenacious_company_size", created_property_names)
        self.assertIn("tenacious_enrichment_timestamp", created_property_names)


if __name__ == "__main__":
    unittest.main()
