import json
import tempfile
import unittest
from pathlib import Path

from agent import market_map


class TestMarketMap(unittest.TestCase):
    def test_quick_ai_score_uses_keywords(self) -> None:
        record = {
            "about": "AI copilot for underwriting with machine learning and LLM workflows.",
            "full_description": "",
            "industries": json.dumps([{"value": "Financial Services"}, {"value": "Machine Learning"}]),
            "builtwith_tech": "[]",
        }

        scored = market_map.quick_ai_score(record)

        self.assertEqual(scored["score"], 3)
        self.assertIn("machine learning", scored["matched_keywords"])

    def test_analyze_market_map_builds_distribution_and_cells(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dataset_path = Path(tmp) / "sample.json"
            dataset_path.write_text(
                json.dumps(
                    [
                        {
                            "name": "AlphaAI",
                            "about": "Machine learning platform for fraud analytics.",
                            "full_description": "",
                            "industries": json.dumps([{"value": "Financial Services"}, {"value": "Machine Learning"}]),
                            "num_employees": "11-50",
                            "builtwith_tech": "[]",
                            "funding_rounds_list": json.dumps(
                                [{"announced_on": "2026-01-15", "money_raised": {"value_usd": 6000000}}]
                            ),
                        },
                        {
                            "name": "BetaAI",
                            "about": "Machine learning platform for fraud analytics.",
                            "full_description": "",
                            "industries": json.dumps([{"value": "Financial Services"}, {"value": "Machine Learning"}]),
                            "num_employees": "11-50",
                            "builtwith_tech": "[]",
                            "funding_rounds_list": json.dumps(
                                [{"announced_on": "2026-02-10", "money_raised": {"value_usd": 4000000}}]
                            ),
                        },
                        {
                            "name": "GammaAI",
                            "about": "Machine learning platform for fraud analytics.",
                            "full_description": "",
                            "industries": json.dumps([{"value": "Financial Services"}, {"value": "Machine Learning"}]),
                            "num_employees": "11-50",
                            "builtwith_tech": "[]",
                            "funding_rounds_list": json.dumps(
                                [{"announced_on": "2026-03-12", "money_raised": {"value_usd": 7000000}}]
                            ),
                        },
                        {
                            "name": "PlainOps",
                            "about": "Industrial services provider.",
                            "full_description": "",
                            "industries": json.dumps([{"value": "Manufacturing"}]),
                            "num_employees": "51-100",
                            "builtwith_tech": "[]",
                            "funding_rounds_list": "[]",
                        },
                    ]
                ),
                encoding="utf-8",
            )

            report = market_map.analyze_market_map(dataset_path=dataset_path, manual_labels_path=None)

        self.assertEqual(report["dataset_row_count"], 4)
        self.assertEqual(report["score_distribution"]["3"]["count"], 3)
        self.assertEqual(report["score_distribution"]["0"]["count"], 1)
        self.assertTrue(report["top_cells"])

    def test_validate_market_map_returns_macro_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            labels_path = Path(tmp) / "labels.json"
            labels_path.write_text(
                json.dumps(
                    [
                        {"company": "AlphaAI", "manual_score": 3, "notes": "Clear ML product."},
                        {"company": "PlainOps", "manual_score": 0, "notes": "No AI signal."},
                    ]
                ),
                encoding="utf-8",
            )
            scored_records = [
                {"company_name": "AlphaAI", "ai_readiness_score": 3, "matched_ai_keywords": ["machine learning"]},
                {"company_name": "PlainOps", "ai_readiness_score": 1, "matched_ai_keywords": ["analytics"]},
            ]

            report = market_map.validate_market_map(scored_records=scored_records, manual_labels_path=labels_path)

        self.assertEqual(report["sample_size"], 2)
        self.assertIn("macro_precision", report)
        self.assertIn("dormant", report["per_band"])
        self.assertEqual(report["per_band"]["leading"]["support"], 1)


if __name__ == "__main__":
    unittest.main()
