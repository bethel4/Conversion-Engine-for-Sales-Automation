import unittest

from agent.prospect_flow import build_booking_link_followup_text, build_event_context, build_thread_id


class TestProspectFlowHelpers(unittest.TestCase):
    def test_build_thread_id_is_stable(self) -> None:
        self.assertEqual(build_thread_id("Consolety"), "thread_consolety_001")
        self.assertEqual(build_thread_id("Acme Corp"), "thread_acme_corp_001")

    def test_build_event_context_carries_company_email_and_thread(self) -> None:
        identity = {"company_name": "Consolety", "thread_id": "thread_consolety_001"}
        context = build_event_context(
            prospect_email="bethelyohannes4@gmail.com",
            identity=identity,
            extra={"message_id": "msg_123"},
        )

        self.assertEqual(context["company_name"], "Consolety")
        self.assertEqual(context["prospect_email"], "bethelyohannes4@gmail.com")
        self.assertEqual(context["thread_id"], "thread_consolety_001")
        self.assertEqual(context["message_id"], "msg_123")

    def test_booking_link_followup_text_is_safe_for_abstain(self) -> None:
        text = build_booking_link_followup_text(
            "abstain",
            "https://cal.com/example/discovery",
        )

        self.assertIn("based on the public signals we found", text)
        self.assertIn("https://cal.com/example/discovery", text)
        self.assertNotIn("aggressively", text.casefold())


if __name__ == "__main__":
    unittest.main()
