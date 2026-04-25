import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from agent.bench_gate import evaluate_capacity_request
from agent.calendar_handler import build_timezone_confirmation, needs_timezone_confirmation
from agent.enrichment import icp, phrasing
from agent.gap_guard import audit_gap_claim
from agent.thread_manager import ThreadManager
from agent.tone_checker import score_turns


class TestActIIIProbes(unittest.TestCase):
    def test_icp_layoff_dominates_recent_series_b(self) -> None:
        brief = {
            "funding": {
                "funded": True,
                "round_type": "series_b",
                "days_ago": 45,
                "confidence": "high",
            },
            "layoffs": {
                "had_layoff": True,
                "days_ago": 60,
                "percentage_cut": 0.20,
                "confidence": "high",
            },
            "leadership_change": {"new_leader_detected": False},
            "ai_maturity": {"score": 1, "confidence": "low"},
            "jobs": {"engineering_roles": 2, "signal_strength": "weak"},
        }

        result = icp.classify_icp(brief)

        self.assertEqual(result["segment"], "segment_2")
        self.assertGreater(result["scores"]["segment_2"], result["scores"]["segment_1"])

    def test_weak_job_signal_does_not_overclaim_growth(self) -> None:
        evidence = {"engineering_roles": 2, "signal_strength": "weak"}

        safe_text = phrasing.phrase_with_confidence(
            "you are aggressively scaling your engineering team",
            evidence,
            "low",
        )
        audit = phrasing.audit_overclaiming(safe_text, "low")
        violating_audit = phrasing.audit_overclaiming(
            "You're aggressively scaling your engineering team at 3x.",
            "low",
        )

        self.assertEqual(
            safe_text,
            "Are you finding it harder to hire engineering talent at the pace your roadmap needs?",
        )
        self.assertTrue(audit["ok"])
        self.assertFalse(violating_audit["ok"])
        self.assertIn("banned_word:aggressive", violating_audit["issues"])
        self.assertIn("multiplier_claim", violating_audit["issues"])

    def test_bench_gate_blocks_unsupported_stack_commitment(self) -> None:
        bench = {"python": 8, "data": 5, "ml": 3, "go": 0}

        result = evaluate_capacity_request("We need 5 Go engineers by next month.", bench)

        self.assertFalse(result["can_commit"])
        self.assertEqual(result["requested_skill"], "go")
        self.assertEqual(result["available_count"], 0)
        self.assertEqual(result["action"], "human_review")
        self.assertIn("delivery lead", result["response"].casefold())
        self.assertNotIn("we can provide", result["response"].casefold())

    def test_tone_stays_above_threshold_across_four_turns(self) -> None:
        turns = [
            "Makes sense. Most teams have heard a version of this before. The useful question is whether you need execution help this quarter or just more sourcing options?",
            "Fair question. Upwork can fill a seat. We focus on delivery-ready engineers and tighter follow-through once work starts. Is the gap speed, quality, or team ownership?",
            "That pushback is reasonable. Offshore only works when communication and delivery management are explicit. Where have past teams broken down for you: handoff, quality, or pace?",
            "If it helps, we can keep this concrete. Share the role profile and timeline, and we can tell you quickly whether it fits our bench or should stay with your internal team.",
        ]

        scores = score_turns(turns)

        self.assertEqual(len(scores), 4)
        self.assertTrue(all(item["score"] > 0.7 for item in scores), scores)

    def test_same_company_threads_do_not_leak_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "threads.db"
            os.environ["THREADS_DB_PATH"] = str(db_path)
            self.addCleanup(os.environ.pop, "THREADS_DB_PATH", None)

            manager = ThreadManager()
            manager.append_message(
                "acme:alice",
                role="user",
                content="We have a 5-person data team and need help with structure.",
                meta={"company": "Acme", "contact": "Alice", "role": "Co-founder"},
            )
            manager.append_message(
                "acme:bob",
                role="user",
                content="We are migrating infrastructure to AWS next quarter.",
                meta={"company": "Acme", "contact": "Bob", "role": "VP Engineering"},
            )

            alice_text = " ".join(message.content for message in manager.get_context("acme:alice"))
            bob_text = " ".join(message.content for message in manager.get_context("acme:bob"))

            self.assertIn("5-person data team", alice_text)
            self.assertNotIn("AWS migration", alice_text)
            self.assertIn("AWS", bob_text)
            self.assertNotIn("5-person data team", bob_text)

    def test_scheduling_edge_cases_require_timezone_confirmation(self) -> None:
        self.assertTrue(needs_timezone_confirmation("Monday morning works for me."))
        self.assertFalse(needs_timezone_confirmation("Monday morning works for me.", "Europe/Berlin"))

        eat_confirmation = build_timezone_confirmation(
            datetime(2026, 4, 30, 14, 0),
            "Africa/Addis_Ababa",
            "America/New_York",
        )
        dst_confirmation = build_timezone_confirmation(
            datetime(2026, 11, 2, 14, 0),
            "Europe/Berlin",
            "America/New_York",
        )

        self.assertIn("EAT (UTC+03:00)", eat_confirmation)
        self.assertIn("7am EDT (UTC-04:00)", eat_confirmation)
        self.assertIn("CET (UTC+01:00)", dst_confirmation)
        self.assertIn("8am EST (UTC-05:00)", dst_confirmation)

    def test_gap_guard_blocks_fabrication_when_brief_has_no_gap(self) -> None:
        brief = {"company": {"name": "Acme"}, "gaps": [], "peers": []}

        failing = audit_gap_claim(
            "Your top competitors are building dedicated AI teams while you fall behind.",
            brief,
        )
        passing = audit_gap_claim(
            "We looked at your sector peers — the picture on AI maturity is mixed. Worth a conversation to see where the real leverage is for you.",
            brief,
        )

        self.assertFalse(failing["ok"])
        self.assertIn("fabricated_gap_claim", failing["issues"])
        self.assertTrue(passing["ok"])

    def test_gap_guard_flags_condescending_real_gap_framing(self) -> None:
        brief = {
            "company": {"name": "Acme"},
            "gaps": [
                {
                    "gap": "ai_tech_stack",
                    "confidence": "high",
                    "evidence": {"sample_peers": ["BetterCo", "ScaleCo"]},
                }
            ],
        }

        failing = audit_gap_claim(
            "Your competitors BetterCo and ScaleCo are clearly ahead of you on AI.",
            brief,
        )
        passing = audit_gap_claim(
            "Some peers, including BetterCo and ScaleCo, show clearer AI platform footprints. Worth comparing where that matters for your roadmap.",
            brief,
        )

        self.assertFalse(failing["ok"])
        self.assertTrue(any(issue.startswith("condescending_gap_framing:") for issue in failing["issues"]))
        self.assertTrue(passing["ok"])


if __name__ == "__main__":
    unittest.main()
