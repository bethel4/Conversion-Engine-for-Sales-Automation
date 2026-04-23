import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from agent.enrichment import briefs, competitor_gap, icp, phrasing


class TestBriefsPipeline(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

        os.environ["ENRICHMENT_CACHE_DB"] = str(self.tmp / "cache.db")

        # Minimal Crunchbase dataset for deterministic tests.
        self.cb_path = self.tmp / "crunchbase.json"
        self.cb_path.write_text(
            json.dumps(
                [
                    {
                        "id": "acme",
                        "name": "Acme",
                        "url": "https://www.crunchbase.com/organization/acme",
                        "website": "https://acme.example",
                        "country_code": "US",
                        "num_employees": "11-50",
                        "industries": json.dumps([{"value": "B2B SaaS"}]),
                        "builtwith_tech": json.dumps([{"name": "Kubernetes"}]),
                        "last_funding_date": "2026-03-09",
                        "last_funding_type": "Series B",
                        "last_funding_amount_usd": 14000000,
                    },
                    {
                        "id": "peer1",
                        "name": "BetterCo",
                        "url": "https://www.crunchbase.com/organization/betterco",
                        "website": "https://better.example",
                        "num_employees": "11-50",
                        "industries": json.dumps([{"value": "B2B SaaS"}, {"value": "Artificial Intelligence"}]),
                        "builtwith_tech": json.dumps([{"name": "TensorFlow"}]),
                    },
                    {
                        "id": "peer2",
                        "name": "ScaleCo",
                        "url": "https://www.crunchbase.com/organization/scaleco",
                        "website": "https://scale.example",
                        "num_employees": "11-50",
                        "industries": json.dumps([{"value": "B2B SaaS"}]),
                        "builtwith_tech": json.dumps([{"name": "Snowflake"}]),
                    },
                ]
            ),
            encoding="utf-8",
        )
        os.environ["CRUNCHBASE_ODM_PATH"] = str(self.cb_path)

        # Minimal layoffs dataset.
        self.layoffs_path = self.tmp / "layoffs.csv"
        self.layoffs_path.write_text(
            "Company,Location_HQ,Industry,Laid_Off_Count,Percentage,Date,Source,Country,Stage,Funds_Raised_USD\n"
            "Acme,SF Bay Area,Software,10,0.2,2026-04-01,https://example.com,United States,Series B,10\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        os.environ.pop("ENRICHMENT_CACHE_DB", None)
        os.environ.pop("CRUNCHBASE_ODM_PATH", None)

    def test_produce_hiring_signal_brief_and_write(self) -> None:
        today = date(2026, 4, 23)
        html = "<html><body><h3>Software Engineer</h3><h3>ML Engineer</h3></body></html>"
        brief = briefs.produce_hiring_signal_brief(
            "Acme",
            today=today,
            jobs_html=html,
            layoffs_dataset_path=self.layoffs_path,
        )
        self.assertIn("company", brief)
        self.assertIn("_confidence", brief["jobs"])
        self.assertIn("_confidence", brief["funding"])
        self.assertEqual(brief["funding"]["funded"], True)

        out = briefs.write_hiring_signal_brief_file(brief, out_dir=self.tmp / "briefs")
        self.assertTrue(out.exists())

    def test_competitor_gap_brief(self) -> None:
        today = date(2026, 4, 23)
        hiring = briefs.produce_hiring_signal_brief(
            "Acme",
            today=today,
            jobs_html="<html></html>",
            layoffs_dataset_path=self.layoffs_path,
        )
        gap = competitor_gap.produce_competitor_gap_brief("Acme", hiring_brief=hiring, today=today, peers_limit=5)
        self.assertIn("peers", gap)
        self.assertGreaterEqual(len(gap["peers"]), 1)

    def test_icp_classifier(self) -> None:
        brief = {
            "funding": {"funded": True, "confidence": "high", "round_type": "series_b"},
            "layoffs": {"had_layoff": False},
            "leadership_change": {"new_leader_detected": False},
            "ai_maturity": {"score": 1, "confidence": "low"},
            "jobs": {"engineering_roles": 7, "signal_strength": "medium"},
        }
        out = icp.classify_icp(brief)
        self.assertEqual(out["segment"], "segment_1")

        brief2 = dict(brief)
        brief2["layoffs"] = {"had_layoff": True, "confidence": "high"}
        out2 = icp.classify_icp(brief2)
        self.assertEqual(out2["segment"], "segment_2")

        brief3 = dict(brief)
        brief3["funding"] = {"funded": False}
        brief3["leadership_change"] = {"new_leader_detected": True, "confidence": "high"}
        out3 = icp.classify_icp(brief3)
        self.assertEqual(out3["segment"], "segment_3")

        brief4 = dict(brief)
        brief4["funding"] = {"funded": False}
        brief4["ai_maturity"] = {"score": 3, "confidence": "high"}
        out4 = icp.classify_icp(brief4)
        self.assertEqual(out4["segment"], "segment_4")

        out5 = icp.classify_icp({"funding": {"funded": False}, "ai_maturity": {"score": 0}})
        self.assertEqual(out5["segment"], "abstain")

    def test_phrase_and_audit(self) -> None:
        template = "your open engineering roles have grown {velocity}x — {engineering_roles} positions posted now"
        ev = {"velocity": 3.0, "engineering_roles": 9}
        self.assertIn("grown 3.0x", phrasing.phrase_with_confidence(template, ev, "high"))
        self.assertTrue(phrasing.phrase_with_confidence(template, ev, "medium").startswith("It looks like"))
        low = phrasing.phrase_with_confidence(template, ev, "low")
        self.assertTrue(low.endswith("?"))

        audit = phrasing.audit_overclaiming("You are growing aggressively at 3x.", "low")
        self.assertEqual(audit["ok"], False)


if __name__ == "__main__":
    unittest.main()
