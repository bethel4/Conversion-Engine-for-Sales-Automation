import json
import tempfile
import unittest
from pathlib import Path

from agent.enrichment.crunchbase import ensure_compat_json_dataset
from agent.outreach.confidence_phraser import audit_overclaiming
from agent.qualification.icp_classifier import classify_icp
from eval.tau2_harness import run_eval


class TestCompatModules(unittest.TestCase):
    def test_icp_compat_wrapper(self) -> None:
        brief = {
            "funding": {"funded": True, "round_type": "series_b", "days_ago": 45, "amount_usd": 14000000},
            "layoffs": {"had_layoff": False},
            "company": {"employee_count": 45},
            "jobs": {"engineering_roles": 7, "signal_strength": "medium"},
            "ai_maturity": {"score": 1, "confidence": "medium"},
        }
        result = classify_icp(brief)
        self.assertEqual(result["segment"], "segment_1")
        self.assertIn("primary_signal", result)
        self.assertIsNone(result["abstain_reason"])

    def test_overclaiming_compat_wrapper(self) -> None:
        result = audit_overclaiming("you are aggressively hiring", "low")
        self.assertFalse(result["ok"])

    def test_tau2_harness_writes_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            score_log = Path(tmp) / "score_log.json"
            trace_log = Path(tmp) / "trace_log.jsonl"

            import eval.tau2_harness as harness

            harness.SCORE_LOG = score_log
            harness.TRACE_LOG = trace_log
            result = run_eval(
                [{"id": "task_1", "passed": True, "tokens_used": 100}, {"id": "task_2", "passed": False, "tokens_used": 150}],
                model="qwen/qwen3-30b-a3b",
                n_trials=2,
            )

            self.assertTrue(score_log.exists())
            self.assertTrue(trace_log.exists())
            self.assertGreaterEqual(result["pass_at_1"], 0.0)
            self.assertLessEqual(result["pass_at_1"], 1.0)

    def test_ensure_compat_json_dataset(self) -> None:
        path = ensure_compat_json_dataset()
        self.assertTrue(path.exists())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, list)


if __name__ == "__main__":
    unittest.main()
