import json
import tempfile
import unittest
from pathlib import Path

from eval.run_ablations import main as run_ablations_main


class TestAblationRunner(unittest.TestCase):
    def test_runner_writes_expected_outputs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tasks_file = repo_root / "eval" / "sample_held_out_tasks.json"

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            exit_code = run_ablations_main(
                [
                    "--tasks-file",
                    str(tasks_file),
                    "--output-dir",
                    str(output_dir),
                    "--n-trials",
                    "2",
                ]
            )

            self.assertEqual(exit_code, 0)

            results = json.loads((output_dir / "ablation_results.json").read_text(encoding="utf-8"))
            traces = (output_dir / "held_out_traces.jsonl").read_text(encoding="utf-8").splitlines()
            method_md = (output_dir / "method.md").read_text(encoding="utf-8")

            self.assertEqual(results["n_tasks"], 3)
            self.assertEqual(results["n_trials"], 2)
            self.assertEqual(len(traces), 24)
            self.assertIn("method", results["conditions"])
            self.assertIn("ablation_no_audit", results["conditions"])
            self.assertIn("ablation_no_confidence", results["conditions"])
            self.assertIn("day1_baseline", results["conditions"])
            self.assertIn("method_vs_day1", results["statistical_tests"])
            self.assertIn("Primary mechanism", method_md)

            method_pass = results["conditions"]["method"]["pass_at_1"]
            baseline_pass = results["conditions"]["day1_baseline"]["pass_at_1"]
            self.assertGreater(method_pass, baseline_pass)


if __name__ == "__main__":
    unittest.main()
