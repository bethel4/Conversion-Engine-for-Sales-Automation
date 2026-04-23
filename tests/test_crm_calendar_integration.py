import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from agent.main import app, set_calendar_event_handler


class TestCrmCalendarIntegration(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        set_calendar_event_handler(lambda event: None)

    def tearDown(self) -> None:
        set_calendar_event_handler(lambda event: None)

    @patch("agent.main.write_enriched_contact")
    @patch("agent.main.classify_icp")
    @patch("agent.main.produce_hiring_signal_brief")
    def test_crm_enrichment_writes_icp_and_signals(
        self,
        mock_brief: Mock,
        mock_icp: Mock,
        mock_write: Mock,
    ) -> None:
        mock_brief.return_value = {
            "funding": {"funded": True, "confidence": "high"},
            "jobs": {"engineering_roles": 5},
            "layoffs": {"had_layoff": False},
            "leadership_change": {"new_leader_detected": False},
            "ai_maturity": {"score": 1},
            "tech_stack": {"technologies": ["HubSpot"]},
            "meta": {"generated_at": "2026-04-23"},
        }
        mock_icp.return_value = {
            "segment": "segment_1",
            "confidence": 0.91,
            "pitch_angle": "fresh_funding_scale_execution",
            "scores": {"segment_1": 0.91},
            "reasoning": {"funding": {"funded": True}},
            "disqualifiers": {},
        }
        mock_write.return_value = {"id": "contact_123"}

        result = self.client.post(
            "/crm/prospects/enrich",
            json={
                "email": "lead@example.com",
                "company_name": "Stripe",
                "phone": "+15551234567",
            },
        )

        self.assertEqual(result.status_code, 200)
        call = mock_write.call_args.kwargs
        self.assertEqual(call["email"], "lead@example.com")
        self.assertEqual(call["icp_segment"], "segment_1")
        self.assertIn("signals", call["enrichment"])
        self.assertIn("meta", call["enrichment"])

    @patch.dict("os.environ", {"CALCOM_API_KEY": "cal-key"}, clear=False)
    @patch("agent.main.requests.post")
    def test_calendar_booking_is_callable(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"booking": {"id": 42}}
        mock_post.return_value = response

        result = self.client.post(
            "/calendar/book",
            json={
                "name": "Bethel",
                "email": "lead@example.com",
                "start": "2026-04-24T10:00:00Z",
                "event_type_id": 123,
                "time_zone": "Africa/Addis_Ababa",
                "title": "Demo call",
                "company_name": "Stripe",
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["provider"], "cal.com")
        mock_post.assert_called_once()

    @patch("agent.main.write_booking_update")
    def test_calendar_webhook_updates_same_prospect(self, mock_update: Mock) -> None:
        observed = []
        set_calendar_event_handler(observed.append)
        mock_update.return_value = {"id": "contact_123"}

        result = self.client.post(
            "/calendar/webhook",
            json={
                "triggerEvent": "BOOKING_CREATED",
                "booking": {
                    "id": "booking_123",
                    "status": "confirmed",
                    "startTime": "2026-04-24T10:00:00Z",
                    "title": "Demo call",
                    "attendee": {"email": "lead@example.com"},
                },
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].email, "lead@example.com")
        update_call = mock_update.call_args.kwargs
        self.assertEqual(update_call["email"], "lead@example.com")
        self.assertEqual(update_call["booking_id"], "booking_123")


if __name__ == "__main__":
    unittest.main()
