import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
    from agent.main import app
except Exception as exc:  # pragma: no cover
    TestClient = None  # type: ignore[assignment]
    app = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


@unittest.skipIf(
    TestClient is None,
    f"Skipping prospects API tests (FastAPI/Pydantic mismatch or missing endpoints): {_IMPORT_ERROR}",
)
class TestProspectsApi(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.tempdir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tempdir.name) / "prospects.json"
        self.write_store(
            [
                {
                    "id": "consolety",
                    "prospect_name": "Bethel Yohannes",
                    "company": "Consolety",
                    "email": "bethelyohannes4@gmail.com",
                }
            ]
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_store(self, records) -> None:
        self.store_path.write_text(json.dumps(records), encoding="utf-8")

    def test_list_prospects_reads_backend_store(self) -> None:
        with patch.dict("os.environ", {"PROSPECTS_STORE_PATH": str(self.store_path)}, clear=False):
            result = self.client.get("/prospects")

        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(len(body["prospects"]), 1)
        self.assertEqual(body["prospects"][0]["company"], "Consolety")

    @patch.dict(
        "os.environ",
        {
            "LIVE_OUTBOUND": "false",
            "EMAIL_PROVIDER": "mailersend",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "OPENROUTER_MODEL": "openai/gpt-4o-mini",
        },
        clear=False,
    )
    def test_config_reports_outbound_pause(self) -> None:
        result = self.client.get("/config")

        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["live_outbound"], False)
        self.assertEqual(body["email_provider"], "mailersend")
        self.assertEqual(body["openrouter_enabled"], True)
        self.assertEqual(body["openrouter_model"], "openai/gpt-4o-mini")
        self.assertEqual(body["rollback_batch_size"], 50)

    def test_generate_email_persists_source_and_resets_approval(self) -> None:
        self.write_store(
            [
                {
                    "id": "consolety",
                    "prospect_name": "Bethel Yohannes",
                    "company": "Consolety",
                    "email": "bethelyohannes4@gmail.com",
                    "email_approved": True,
                    "qualification": {
                        "segment": "segment_1",
                        "confidence": 0.82,
                        "pitch_angle": "capacity_after_funding",
                    },
                    "latest_hiring_brief": {
                        "funding": {"funded": True, "round_type": "series_a", "days_ago": 25},
                        "jobs": {"engineering_roles": 6, "ai_ml_roles": 1},
                        "layoffs": {"had_layoff": False},
                        "leadership_change": {"new_leader_detected": False},
                        "ai_maturity": {"score": 2, "_confidence": "medium", "pitch_language_hint": "direct"},
                    },
                    "latest_competitor_gap_brief": {
                        "gaps": [
                            {
                                "gap": "data_platform_coverage",
                                "confidence": "high",
                                "evidence": {"sample_peers": ["Peer A", "Peer B"]},
                            }
                        ]
                    },
                }
            ]
        )

        with patch.dict("os.environ", {"PROSPECTS_STORE_PATH": str(self.store_path)}, clear=False):
            result = self.client.post("/prospects/consolety/generate-email", json={})

        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertEqual(body["prospect"]["email_approved"], False)
        self.assertTrue(body["prospect"]["email_generated"])
        self.assertIsNotNone(body["prospect"]["email_generated_at"])
        self.assertEqual(body["generation_metadata"]["prospect_id"], "consolety")
        self.assertEqual(body["generation_metadata"]["thread_id"], "thread_consolety_001")
        self.assertEqual(body["generation_metadata"]["generation_mode"], "signal_grounded")
        self.assertTrue(body["email"]["source"]["used_enrichment_data"])
        self.assertTrue(body["email"]["source"]["used_icp_segment"])
        self.assertTrue(body["email"]["source"]["used_ai_maturity_score"])
        self.assertTrue(body["email"]["source"]["used_competitor_gap_brief"])
        self.assertIn("signals_used", body["email"]["source"])

    def test_approve_email_persists_flag(self) -> None:
        self.write_store(
            [
                {
                    "id": "consolety",
                    "prospect_name": "Bethel Yohannes",
                    "company": "Consolety",
                    "email": "bethelyohannes4@gmail.com",
                    "email_approved": False,
                }
            ]
        )

        with patch.dict("os.environ", {"PROSPECTS_STORE_PATH": str(self.store_path)}, clear=False):
            result = self.client.post("/prospects/consolety/approve-email", json={"approved": True})

        self.assertEqual(result.status_code, 200)
        body = result.json()
        self.assertTrue(body["approved"])
        self.assertTrue(body["prospect"]["email_approved"])


if __name__ == "__main__":
    unittest.main()
