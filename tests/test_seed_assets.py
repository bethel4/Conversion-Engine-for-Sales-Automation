import unittest

from agent.bench_gate import evaluate_capacity_request
from agent.seed_assets import canonical_seed_files, load_bench_counts, load_icp_rules, load_style_guide_rules
from agent.tone_checker import score_tone

try:
    from agent.main import classify_reply_intent
except Exception:  # pragma: no cover
    classify_reply_intent = None


class TestSeedAssets(unittest.TestCase):
    def test_canonical_seed_files_exist(self) -> None:
        for logical_name, path in canonical_seed_files().items():
            self.assertTrue(path.exists(), f"{logical_name} -> {path} is missing")

    def test_icp_rules_load_from_seed_definition(self) -> None:
        rules = load_icp_rules()
        self.assertEqual(rules["segment_1"]["funding_window_days"], 180)
        self.assertEqual(rules["segment_1"]["headcount_min"], 15)
        self.assertEqual(rules["segment_1"]["headcount_max"], 80)
        self.assertEqual(rules["segment_4"]["min_ai_maturity"], 2)

    def test_style_guide_rules_load_from_seed(self) -> None:
        rules = load_style_guide_rules()
        self.assertIn("direct", rules["markers"])
        self.assertEqual(rules["max_cold_email_words"], 120)
        self.assertEqual(rules["max_subject_chars"], 60)

    def test_bench_gate_defaults_to_seed_bench_summary(self) -> None:
        counts = load_bench_counts()
        self.assertEqual(counts["go"], 3)

        result = evaluate_capacity_request("We need 4 Go engineers this month.")
        self.assertFalse(result["can_commit"])
        self.assertEqual(result["available_count"], 3)

    def test_tone_checker_uses_style_guide_jargon_rules(self) -> None:
        scored = score_tone(
            "We have bench capacity and world-class engineers ready to deploy for your roadmap?"
        )
        self.assertFalse(scored["ok"])
        self.assertIn("prospect_jargon:bench", scored["issues"])
        self.assertIn("cliche:world-class", scored["issues"])

    def test_reply_intent_classifier_stays_rule_based(self) -> None:
        if classify_reply_intent is None:
            self.skipTest("agent.main unavailable in this environment")
        scored = classify_reply_intent("Interested, can you send pricing and a case study?")
        self.assertEqual(scored["label"], "interested")
        self.assertNotIn("OpenRouter", scored["reason"])


if __name__ == "__main__":
    unittest.main()
