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

    def test_write_market_map_bundle_emits_expected_files(self) -> None:
        report = {
            "dataset_path": "sample.csv",
            "dataset_row_count": 2,
            "as_of_date": "2026-04-26",
            "market_space": [
                {
                    "sector": "Fintech",
                    "size_band": "small (11-50)",
                    "ai_readiness_score": 2,
                    "ai_readiness_label": "active",
                    "company_count": 4,
                    "funded_last_12m_count": 2,
                    "avg_funding_usd_12m": 8200000,
                    "avg_bench_match_score": 0.72,
                    "combined_score": 0.648,
                    "lead_signal": "recent funding plus AI-readiness",
                }
            ],
            "top_cells": [
                {
                    "sector": "Fintech",
                    "size_band": "small (11-50)",
                    "ai_readiness_score": 2,
                    "ai_readiness_label": "active",
                    "company_count": 4,
                    "funded_last_12m_count": 2,
                    "avg_funding_usd_12m": 8200000,
                    "avg_bench_match_score": 0.72,
                    "combined_score": 0.648,
                    "lead_signal": "recent funding plus AI-readiness",
                    "narrative": "Sample narrative",
                    "outbound_recommendation": "Sample recommendation",
                }
            ],
            "validation": {
                "sample_size": 30,
                "macro_precision": 0.7,
                "macro_recall": 0.68,
                "exact_match_accuracy": 0.73,
                "accuracy_95_ci": [0.55, 0.86],
                "per_band": {
                    "dormant": {"precision": 0.8, "recall": 0.9, "support": 10},
                    "emerging": {"precision": 0.6, "recall": 0.5, "support": 5},
                    "active": {"precision": 0.7, "recall": 0.6, "support": 8},
                    "leading": {"precision": 0.75, "recall": 0.7, "support": 7},
                },
                "known_false_positive_modes": ["fp example"],
                "known_false_negative_modes": ["fn example"],
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            method_path = Path(tmp) / "method.md"
            method_path.write_text("# Existing Method\n", encoding="utf-8")
            report_json = market_map.write_market_map_report(report, out_dir=tmp)
            market_space_csv = market_map.write_market_space_csv(report, out_dir=tmp)
            top_cells_md = market_map.write_top_cells_markdown(report, out_dir=tmp)
            written_method = market_map.write_method_markdown(report, target_path=method_path)
            csv_text = market_space_csv.read_text(encoding="utf-8")
            top_cells_text = top_cells_md.read_text(encoding="utf-8")
            method_text = written_method.read_text(encoding="utf-8")

        self.assertEqual(report_json.name, "market_map_report.json")
        self.assertEqual(market_space_csv.name, "market_space.csv")
        self.assertEqual(top_cells_md.name, "top_cells.md")
        self.assertIn("sector,size_band,ai_readiness,companies,avg_funding,bench_match", csv_text)
        self.assertIn("Fintech", csv_text)
        self.assertIn("# Top Cells", top_cells_text)
        self.assertIn("Sample recommendation", top_cells_text)
        self.assertIn("# Existing Method", method_text)
        self.assertIn("## Market Map Validation Snapshot", method_text)
        self.assertIn("Macro precision: 0.7", method_text)


if __name__ == "__main__":
    unittest.main()
