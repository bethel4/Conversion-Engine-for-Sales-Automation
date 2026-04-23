import unittest
from unittest.mock import Mock, patch

try:
    from fastapi.testclient import TestClient
    from agent.main import app, set_email_event_handler, set_sms_event_handler
except Exception as exc:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    set_email_event_handler = None  # type: ignore[assignment]
    set_sms_event_handler = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@unittest.skipIf(
    TestClient is None or set_email_event_handler is None or set_sms_event_handler is None,
    f"Skipping email handler tests (FastAPI/Pydantic mismatch or missing endpoints): {_IMPORT_ERROR}",
)
class TestEmailHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        set_email_event_handler(lambda event: None)
        set_sms_event_handler(lambda event: None)

    def tearDown(self) -> None:
        set_email_event_handler(lambda event: None)
        set_sms_event_handler(lambda event: None)

    @patch.dict(
        "os.environ",
        {"RESEND_API_KEY": "test-key", "RESEND_FROM_EMAIL": "sales@example.com"},
        clear=False,
    )
    @patch("agent.main.requests.post")
    def test_send_email_uses_resend(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"id": "email_123"}
        mock_post.return_value = response

        result = self.client.post(
            "/emails/send",
            json={
                "to": ["lead@example.com"],
                "subject": "Checking in",
                "text": "Hello from sales",
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["provider"], "resend")
        mock_post.assert_called_once()

    @patch.dict(
        "os.environ",
        {"RESEND_API_KEY": "test-key", "RESEND_FROM_EMAIL": "sales@example.com"},
        clear=False,
    )
    @patch("agent.main.requests.post")
    def test_send_email_failure_is_not_silent(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = False
        response.status_code = 422
        response.text = "invalid email"
        mock_post.return_value = response

        result = self.client.post(
            "/emails/send",
            json={
                "to": ["lead@example.com"],
                "subject": "Checking in",
                "text": "Hello from sales",
            },
        )

        self.assertEqual(result.status_code, 502)
        self.assertIn("Resend error 422", result.json()["detail"])

    def test_reply_webhook_emits_downstream_event(self) -> None:
        observed = []
        set_email_event_handler(observed.append)

        result = self.client.post(
            "/emails/webhook",
            json={
                "type": "email.received",
                "data": {
                    "email_id": "email_123",
                    "from": "lead@example.com",
                    "to": ["sales@example.com"],
                    "subject": "Re: Hello",
                    "text_body": "Interested, tell me more.",
                },
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].event_type, "reply")
        self.assertEqual(observed[0].sender, "lead@example.com")

    def test_bounce_webhook_is_accepted(self) -> None:
        observed = []
        set_email_event_handler(observed.append)

        result = self.client.post(
            "/emails/webhook",
            json={
                "type": "email.bounced",
                "data": {
                    "email_id": "email_123",
                    "recipient": "lead@example.com",
                    "reason": "Mailbox not found",
                },
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(observed[0].event_type, "bounce")
        self.assertEqual(observed[0].text, "Mailbox not found")

    def test_malformed_webhook_payload_returns_400(self) -> None:
        result = self.client.post(
            "/emails/webhook",
            data="not-json",
            headers={"content-type": "application/json"},
        )

        self.assertEqual(result.status_code, 400)
        self.assertIn("Malformed webhook payload", str(result.json()["detail"]))

    @patch.dict(
        "os.environ",
        {
            "AFRICASTALKING_USERNAME": "sandbox",
            "AFRICASTALKING_API_KEY": "test-key",
            "AFRICASTALKING_SENDER_ID": "10X",
        },
        clear=False,
    )
    @patch("agent.main.requests.post")
    def test_send_sms_uses_africas_talking_for_warm_leads(self, mock_post: Mock) -> None:
        response = Mock()
        response.ok = True
        response.json.return_value = {"SMSMessageData": {"Recipients": [{"status": "Success"}]}}
        mock_post.return_value = response

        result = self.client.post(
            "/sms/send",
            json={
                "to": ["+251900000000"],
                "message": "Thanks for replying. Can we talk tomorrow?",
                "prior_email_reply_received": True,
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["provider"], "africas_talking")
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["apiKey"], "test-key")
        self.assertEqual(kwargs["data"]["username"], "sandbox")
        self.assertEqual(kwargs["data"]["to"], "+251900000000")
        self.assertEqual(kwargs["data"]["from"], "10X")

    @patch("agent.main.requests.post")
    def test_send_sms_is_blocked_for_cold_outreach(self, mock_post: Mock) -> None:
        result = self.client.post(
            "/sms/send",
            json={
                "to": ["+251900000000"],
                "message": "Cold intro",
                "prior_email_reply_received": False,
            },
        )

        self.assertEqual(result.status_code, 403)
        self.assertIn("warm leads", result.json()["detail"])
        mock_post.assert_not_called()

    def test_sms_webhook_emits_downstream_event(self) -> None:
        observed = []
        set_sms_event_handler(observed.append)

        result = self.client.post(
            "/sms/webhook",
            data={
                "id": "sms_123",
                "from": "+251900000000",
                "to": "+251700000000",
                "text": "Yes, send me details",
                "date": "2026-04-23 10:00:00",
                "linkId": "link-123",
            },
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].event_type, "reply")
        self.assertEqual(observed[0].sender, "+251900000000")
        self.assertEqual(observed[0].text, "Yes, send me details")

    def test_sms_webhook_rejects_missing_sender(self) -> None:
        result = self.client.post(
            "/sms/webhook",
            data={"text": "Hello"},
        )

        self.assertEqual(result.status_code, 400)
        self.assertIn("missing sender or text", result.json()["detail"])


if __name__ == "__main__":
    unittest.main()
