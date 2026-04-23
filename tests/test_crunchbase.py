import json
import os
import tempfile
import unittest
from pathlib import Path

from agent.enrichment import crunchbase


class TestCrunchbaseLookup(unittest.TestCase):
    def setUp(self) -> None:
        crunchbase._clear_caches()

    def _write_json_dataset(self, records: list[dict]) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / "crunchbase_sample.json"
        path.write_text(json.dumps(records), encoding="utf-8")
        return path

    def test_exact_match(self) -> None:
        dataset_path = self._write_json_dataset(
            [{"name": "Stripe", "url": "https://www.crunchbase.com/organization/stripe"}]
        )
        os.environ["CRUNCHBASE_ODM_PATH"] = str(dataset_path)
        crunchbase._clear_caches()

        record = crunchbase.lookup_company("Stripe")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["name"], "Stripe")

    def test_case_insensitive_match(self) -> None:
        dataset_path = self._write_json_dataset([{"name": "Stripe", "id": "stripe"}])
        os.environ["CRUNCHBASE_ODM_PATH"] = str(dataset_path)
        crunchbase._clear_caches()

        record = crunchbase.lookup_company("  sTRiPe  ")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["id"], "stripe")

    def test_unknown_company(self) -> None:
        dataset_path = self._write_json_dataset([{"name": "Stripe"}])
        os.environ["CRUNCHBASE_ODM_PATH"] = str(dataset_path)
        crunchbase._clear_caches()

        self.assertIsNone(crunchbase.lookup_company("Definitely Not A Real Company"))

    def test_is_recently_funded_confidence_buckets(self) -> None:
        from datetime import date, timedelta

        today = date(2026, 4, 23)
        record_high = {
            "funding_rounds_list": json.dumps(
                [
                    {
                        "announced_on": (today - timedelta(days=45)).isoformat(),
                        "title": "Series B - ExampleCo",
                    }
                ]
            )
        }
        record_low = {
            "funding_rounds_list": json.dumps(
                [
                    {
                        "announced_on": (today - timedelta(days=150)).isoformat(),
                        "title": "Venture Round - ExampleCo",
                    }
                ]
            )
        }

        signal_high = crunchbase.is_recently_funded(record_high, today=today)
        self.assertEqual(signal_high["funded"], True)
        self.assertEqual(signal_high["days_ago"], 45)
        self.assertEqual(signal_high["confidence"], "high")
        self.assertEqual(signal_high["round_type"], "series_b")

        signal_low = crunchbase.is_recently_funded(record_low, today=today)
        self.assertEqual(signal_low["funded"], True)
        self.assertEqual(signal_low["days_ago"], 150)
        self.assertEqual(signal_low["confidence"], "low")
        self.assertEqual(signal_low["round_type"], "venture_round")

    def test_build_firmographics_brief_shape(self) -> None:
        from datetime import date

        record = {
            "id": "stripe",
            "name": "Stripe",
            "url": "https://www.crunchbase.com/organization/stripe",
            "website": "https://stripe.com",
            "country_code": "US",
            "num_employees": "8000",
            "industries": json.dumps([{"value": "Fintech"}, {"value": "Payments"}]),
            "cb_rank": "12",
            "last_funding_date": "2026-03-09",
            "last_funding_type": "Series B",
            "last_funding_amount_usd": "14000000",
        }

        brief = crunchbase.build_firmographics_brief(record, today=date(2026, 4, 23))
        self.assertEqual(brief["crunchbase"]["id"], "stripe")
        self.assertEqual(brief["crunchbase"]["name"], "Stripe")
        self.assertEqual(brief["firmographics"]["country_code"], "US")
        self.assertEqual(brief["firmographics"]["industries"], ["Fintech", "Payments"])
        self.assertEqual(brief["funding"]["funded"], True)
        self.assertEqual(brief["funding"]["confidence"], "high")
        self.assertEqual(brief["funding"]["round_type"], "series_b")
        self.assertEqual(brief["funding"]["amount_usd"], 14000000)


if __name__ == "__main__":
    unittest.main()
