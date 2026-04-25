import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from agent.enrichment import ai_maturity, cache, job_posts, leadership, layoffs


class TestSignals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        os.environ["ENRICHMENT_CACHE_DB"] = str(Path(self._tmp.name) / "cache.db")

    def tearDown(self) -> None:
        os.environ.pop("ENRICHMENT_CACHE_DB", None)

    def test_sqlite_cache_roundtrip(self) -> None:
        cache.set_cache("unit", "k1", {"ok": True})
        value = cache.get_cache("unit", "k1", max_age_seconds=3600)
        self.assertEqual(value, {"ok": True})
        self.assertIsNone(cache.get_cache("unit", "k1", max_age_seconds=-1))

    def test_check_layoffs_recent(self) -> None:
        csv_path = Path(self._tmp.name) / "layoffs.csv"
        csv_path.write_text(
            "Company,Location_HQ,Industry,Laid_Off_Count,Percentage,Date,Source,Country,Stage,Funds_Raised_USD\n"
            "TechCo,SF Bay Area,Software,180,0.18,2026-03-09,https://example.com,United States,Series B,48\n",
            encoding="utf-8",
        )
        result = layoffs.check_layoffs(
            "TechCo Inc.",
            days=120,
            dataset_path=csv_path,
            today=date(2026, 4, 23),
        )
        self.assertEqual(result["had_layoff"], True)
        self.assertEqual(result["days_ago"], 45)
        self.assertEqual(result["headcount_cut"], 180)
        self.assertAlmostEqual(result["percentage_cut"], 0.18)
        self.assertEqual(result["segment_implication"], "segment_2")

    def test_check_layoffs_unknown(self) -> None:
        csv_path = Path(self._tmp.name) / "layoffs.csv"
        csv_path.write_text(
            "Company,Location_HQ,Industry,Laid_Off_Count,Percentage,Date,Source,Country,Stage,Funds_Raised_USD\n"
            "TechCo,SF Bay Area,Software,180,0.18,2026-03-09,https://example.com,United States,Series B,48\n",
            encoding="utf-8",
        )
        result = layoffs.check_layoffs(
            "NopeCo", dataset_path=csv_path, today=date(2026, 4, 23)
        )
        self.assertEqual(result["had_layoff"], False)
        self.assertIsNone(result["days_ago"])

    def test_job_posts_classification_and_velocity(self) -> None:
        today = date(2026, 4, 23)
        key = "acme"
        # Seed a snapshot exactly 60 days back with 3 eng roles.
        past = today - timedelta(days=60)
        cache.set_cache(
            "job_posts_snapshot",
            f"{key}:{past.isoformat()}",
            {"engineering_roles": 3, "total_open_roles": 3, "ai_ml_roles": 0},
        )

        html = """
        <html><body>
          <h3>Software Engineer</h3>
          <h3>Machine Learning Engineer</h3>
          <h3>Account Executive</h3>
        </body></html>
        """
        result = job_posts.scrape_job_posts(
            "acme.example",
            company_name="Acme",
            today=today,
            html=html,
        )
        self.assertEqual(result["engineering_roles"], 2)
        self.assertEqual(result["ai_ml_roles"], 1)
        self.assertEqual(result["signal_strength"], "weak")
        self.assertEqual(result["velocity_60d"], -1)
        self.assertEqual(result["open_roles_60_days_ago"], 3)
        self.assertTrue(result["robots_policy"]["public_page_only"])
        self.assertIsNotNone(result["checked_at"])

    def test_detect_leadership_change(self) -> None:
        sources = [
            {
                "text": "TechCo appoints Sarah Chen as CTO, effective March 1st.",
                "date": "2026-03-01",
                "source": "press-release",
            }
        ]
        result = leadership.detect_leadership_change(
            "TechCo", sources=sources, today=date(2026, 4, 23)
        )
        self.assertEqual(result["new_leader_detected"], True)
        self.assertEqual(result["role"], "cto")
        self.assertEqual(result["name"], "Sarah Chen")
        self.assertEqual(result["days_ago"], 53)

    def test_score_ai_maturity(self) -> None:
        scored = ai_maturity.score_ai_maturity(
            {
                "ai_ml_roles": 5,
                "engineering_roles": 12,
                "has_named_ai_leadership": True,
                "github_ai_activity": 0,
                "exec_ai_commentary": True,
                "modern_ml_stack": True,
            }
        )
        self.assertEqual(scored["score"], 3)
        self.assertEqual(scored["confidence"], "high")
        self.assertEqual(scored["pitch_language_hint"], "assert")


if __name__ == "__main__":
    unittest.main()
