#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent.enrichment.phrasing import audit_overclaiming, phrase_with_confidence
from agent.gap_guard import audit_gap_claim
from agent.tone_checker import score_tone


DEFAULT_OUTPUT_DIR = Path("eval")
DEFAULT_COST_PER_MILLION_TOKENS = 0.10
DEFAULT_TONE_THRESHOLD = 0.7


@dataclass(frozen=True)
class VariantSpec:
    name: str
    include_confidence_phrasing: bool
    include_audit: bool
    include_tone_check: bool
    description: str


VARIANTS = (
    VariantSpec(
        name="method",
        include_confidence_phrasing=True,
        include_audit=True,
        include_tone_check=True,
        description="confidence-aware phrasing + overclaim audit + tone repair",
    ),
    VariantSpec(
        name="ablation_no_audit",
        include_confidence_phrasing=True,
        include_audit=False,
        include_tone_check=True,
        description="confidence-aware phrasing + tone repair only",
    ),
    VariantSpec(
        name="ablation_no_confidence",
        include_confidence_phrasing=False,
        include_audit=False,
        include_tone_check=True,
        description="tone repair only; no confidence-aware phrasing or audit",
    ),
    VariantSpec(
        name="day1_baseline",
        include_confidence_phrasing=False,
        include_audit=False,
        include_tone_check=False,
        description="raw baseline phrasing without safety repair",
    ),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".jsonl":
        tasks = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and isinstance(parsed.get("tasks"), list):
            tasks = parsed["tasks"]
        elif isinstance(parsed, list):
            tasks = parsed
        else:
            raise RuntimeError(f"Unsupported held-out task format in {path}")
    if not isinstance(tasks, list) or not tasks:
        raise RuntimeError(f"No tasks found in {path}")
    normalized: list[dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise RuntimeError(f"Task {idx} in {path} is not a JSON object")
        task_id = str(task.get("task_id") or f"task_{idx:03d}")
        checks = task.get("checks") if isinstance(task.get("checks"), dict) else {}
        normalized.append(
            {
                "task_id": task_id,
                "claim_template": task.get("claim_template") or task.get("template") or "",
                "baseline_text": task.get("baseline_text"),
                "evidence": task.get("evidence") if isinstance(task.get("evidence"), dict) else {},
                "confidence": str(task.get("confidence") or "none"),
                "checks": checks,
                "competitor_gap_brief": (
                    task.get("competitor_gap_brief")
                    if isinstance(task.get("competitor_gap_brief"), dict)
                    else None
                ),
            }
        )
    return normalized


def _format_template_high(claim_template: str | dict[str, str], evidence: dict[str, Any]) -> str:
    if isinstance(claim_template, dict):
        template = (
            claim_template.get("baseline")
            or claim_template.get("high")
            or claim_template.get("medium")
            or claim_template.get("low")
            or claim_template.get("none")
            or ""
        )
        try:
            return template.format(**evidence)
        except Exception:
            return template
    try:
        return str(claim_template).format(**evidence)
    except Exception:
        return str(claim_template)


def _estimate_tokens(task: dict[str, Any], output_text: str) -> int:
    payload = json.dumps(
        {
            "claim_template": task.get("claim_template"),
            "evidence": task.get("evidence"),
            "confidence": task.get("confidence"),
            "checks": task.get("checks"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return max(1, math.ceil((len(payload) + len(output_text)) / 4))


def _infer_mode(text: str) -> str:
    stripped = (text or "").strip()
    lowered = stripped.casefold()
    if not stripped:
        return "empty"
    if lowered.startswith("it looks like "):
        return "hedge"
    if "?" in stripped:
        if lowered.startswith("what ") or lowered.startswith("how "):
            return "open"
        return "ask"
    return "assert"


def _repair_for_tone(task: dict[str, Any], text: str) -> str:
    evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
    confidence = str(task.get("confidence") or "none")
    repaired = phrase_with_confidence(task.get("claim_template") or "", evidence, confidence)
    if repaired.strip() != text.strip():
        return repaired
    if confidence.casefold() in {"low", "none"}:
        return phrase_with_confidence(task.get("claim_template") or "", evidence, "none")
    return repaired if "?" in repaired else repaired.rstrip(".") + "?"


def _apply_variant(task: dict[str, Any], variant: VariantSpec) -> tuple[str, dict[str, Any]]:
    evidence = task.get("evidence") if isinstance(task.get("evidence"), dict) else {}
    confidence = str(task.get("confidence") or "none")
    baseline_text = task.get("baseline_text")

    if isinstance(baseline_text, str) and baseline_text.strip():
        raw_baseline = baseline_text.strip()
    else:
        raw_baseline = _format_template_high(task.get("claim_template") or "", evidence).strip()

    if variant.include_confidence_phrasing:
        text = phrase_with_confidence(task.get("claim_template") or "", evidence, confidence).strip()
    else:
        text = raw_baseline

    audit_result = audit_overclaiming(text, confidence)
    if variant.include_audit and not audit_result["ok"]:
        text = phrase_with_confidence(task.get("claim_template") or "", evidence, "none").strip()
        audit_result = audit_overclaiming(text, confidence)

    tone_result = score_tone(text)
    min_tone = float(task.get("checks", {}).get("min_tone_score", DEFAULT_TONE_THRESHOLD))
    if variant.include_tone_check and tone_result["score"] < min_tone:
        text = _repair_for_tone(task, text).strip()
        tone_result = score_tone(text)

    gap_result = audit_gap_claim(text, task.get("competitor_gap_brief"))
    diagnostics = {
        "mode": _infer_mode(text),
        "audit": audit_result,
        "tone": tone_result,
        "gap_audit": gap_result,
    }
    return text, diagnostics


def _score_output(task: dict[str, Any], text: str, diagnostics: dict[str, Any]) -> tuple[bool, list[str]]:
    checks = task.get("checks") if isinstance(task.get("checks"), dict) else {}
    failures: list[str] = []

    expected_mode = checks.get("mode")
    if expected_mode and diagnostics["mode"] != expected_mode:
        failures.append(f"mode:{diagnostics['mode']}!=expected:{expected_mode}")

    question_required = checks.get("question_required")
    if question_required is True and "?" not in text:
        failures.append("missing_question")

    audit_ok = checks.get("audit_ok")
    if audit_ok is not None and bool(diagnostics["audit"]["ok"]) != bool(audit_ok):
        failures.append("audit_mismatch")

    gap_ok = checks.get("gap_audit_ok")
    if gap_ok is not None and bool(diagnostics["gap_audit"]["ok"]) != bool(gap_ok):
        failures.append("gap_audit_mismatch")

    min_tone_score = checks.get("min_tone_score")
    if min_tone_score is not None and float(diagnostics["tone"]["score"]) < float(min_tone_score):
        failures.append(f"tone_below:{min_tone_score}")

    for needle in checks.get("required_substrings", []):
        if str(needle).casefold() not in text.casefold():
            failures.append(f"missing:{needle}")

    for needle in checks.get("forbidden_substrings", []):
        if str(needle).casefold() in text.casefold():
            failures.append(f"forbidden:{needle}")

    return (len(failures) == 0), failures


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    values_sorted = sorted(values)
    if len(values_sorted) == 1:
        return values_sorted[0]
    k = (len(values_sorted) - 1) * (pct / 100.0)
    lower = int(math.floor(k))
    upper = int(math.ceil(k))
    if lower == upper:
        return values_sorted[lower]
    weight = k - lower
    return values_sorted[lower] * (1.0 - weight) + values_sorted[upper] * weight


def _wilson_ci_95(passed: int, total: int) -> list[float] | None:
    if total <= 0:
        return None
    z = 1.959963984540054
    phat = passed / total
    denom = 1.0 + (z * z) / total
    center = (phat + (z * z) / (2.0 * total)) / denom
    margin = (
        z
        * ((phat * (1.0 - phat) + (z * z) / (4.0 * total)) / total) ** 0.5
        / denom
    )
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _trial_pass_rates(rows: list[dict[str, Any]], n_trials: int) -> list[float]:
    scores: list[float] = []
    for trial in range(1, n_trials + 1):
        trial_rows = [row for row in rows if int(row["trial"]) == trial]
        if not trial_rows:
            scores.append(0.0)
            continue
        passed = sum(1 for row in trial_rows if row["passed"])
        scores.append(passed / len(trial_rows))
    return scores


def _exact_paired_permutation_test(trial_scores_a: list[float], trial_scores_b: list[float]) -> dict[str, Any]:
    if len(trial_scores_a) != len(trial_scores_b):
        raise RuntimeError("Paired statistical test requires equal trial counts")
    diffs = [a - b for a, b in zip(trial_scores_a, trial_scores_b)]
    observed = statistics.mean(diffs) if diffs else 0.0
    n = len(diffs)
    if n == 0:
        return {"delta": 0.0, "p_value": 1.0, "method": "exact_paired_permutation", "n_trials": 0}

    values = []
    for mask in range(1 << n):
        flipped = []
        for idx, diff in enumerate(diffs):
            flipped.append(diff if ((mask >> idx) & 1) == 0 else -diff)
        values.append(statistics.mean(flipped))
    p_value = sum(1 for value in values if value >= observed - 1e-12) / len(values)
    return {
        "delta": observed,
        "p_value": p_value,
        "method": "exact_paired_permutation",
        "n_trials": n,
        "trial_deltas": diffs,
    }


def _run_variant(
    *,
    tasks: list[dict[str, Any]],
    variant: VariantSpec,
    n_trials: int,
    cost_per_million_tokens: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trial in range(1, n_trials + 1):
        for task in tasks:
            started = time.perf_counter()
            text, diagnostics = _apply_variant(task, variant)
            passed, failures = _score_output(task, text, diagnostics)
            latency_ms = (time.perf_counter() - started) * 1000.0
            tokens = _estimate_tokens(task, text)
            cost_usd = tokens * (cost_per_million_tokens / 1_000_000.0)
            rows.append(
                {
                    "task_id": task["task_id"],
                    "trial": trial,
                    "condition": variant.name,
                    "timestamp": _utc_now_iso(),
                    "passed": passed,
                    "latency_ms": round(latency_ms, 3),
                    "tokens": tokens,
                    "cost_usd": cost_usd,
                    "confidence": task["confidence"],
                    "output_text": text,
                    "diagnostics": diagnostics,
                    "failures": failures,
                }
            )

    trial_scores = _trial_pass_rates(rows, n_trials)
    latencies = [float(row["latency_ms"]) for row in rows]
    costs = [float(row["cost_usd"]) for row in rows]
    passed_n = sum(1 for row in rows if row["passed"])
    summary = {
        "condition": variant.name,
        "description": variant.description,
        "n_tasks": len(tasks),
        "n_trials": n_trials,
        "pass_at_1": statistics.mean(trial_scores) if trial_scores else 0.0,
        "trial_pass_rates": trial_scores,
        "ci_95": _wilson_ci_95(passed_n, len(rows)),
        "cost_per_task_usd": statistics.mean(costs) if costs else 0.0,
        "p95_latency_ms": _percentile(latencies, 95) or 0.0,
    }
    return rows, summary


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _render_method_md(
    *,
    tasks_file: Path,
    output_dir: Path,
    n_tasks: int,
    n_trials: int,
    summaries: dict[str, dict[str, Any]],
    stats: dict[str, Any],
) -> str:
    lines = [
        "# Act IV Method",
        "",
        "## Primary mechanism",
        "- Full method: `phrase_with_confidence` -> `audit_overclaiming` hard repair -> `score_tone` repair.",
        "- Ablation B: confidence-aware phrasing + tone repair, but no overclaim audit.",
        "- Ablation C: tone repair only, with no confidence-aware phrasing and no overclaim audit.",
        "- Day 1 baseline: raw baseline phrasing with no repair layer.",
        "",
        "## Held-out protocol",
        f"- Tasks file: `{tasks_file}`",
        f"- Output directory: `{output_dir}`",
        f"- Held-out tasks: `{n_tasks}`",
        f"- Trials per condition: `{n_trials}`",
        f"- Total task runs: `{n_tasks * n_trials * len(VARIANTS)}`",
        "",
        "## Statistical test",
        "- We compare trial-level pass@1 scores between the full method and the Day 1 baseline.",
        "- Test: exact paired permutation test over the trial pass-rate vector.",
        "- Alternative hypothesis: Delta A = pass@1(method) - pass@1(day1_baseline) > 0.",
        "",
        "```python",
        "trial_deltas = [a - b for a, b in zip(method_trial_pass_rates, baseline_trial_pass_rates)]",
        "observed = sum(trial_deltas) / len(trial_deltas)",
        "p_value = sum(",
        "    1",
        "    for mask in range(1 << len(trial_deltas))",
        "    if sum(",
        "        diff if ((mask >> idx) & 1) == 0 else -diff",
        "        for idx, diff in enumerate(trial_deltas)",
        "    ) / len(trial_deltas) >= observed",
        ") / (1 << len(trial_deltas))",
        "```",
        "",
        f"- Observed Delta A: `{stats['method_vs_day1']['delta']:.4f}`",
        f"- One-sided p-value: `{stats['method_vs_day1']['p_value']:.6f}`",
        "",
        "## Results snapshot",
    ]
    for name in ("method", "ablation_no_audit", "ablation_no_confidence", "day1_baseline"):
        summary = summaries[name]
        lines.append(
            f"- `{name}`: pass@1={summary['pass_at_1']:.4f}, "
            f"95% CI={summary['ci_95']}, cost/task=${summary['cost_per_task_usd']:.6f}, "
            f"p95 latency={summary['p95_latency_ms']:.3f} ms"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Act IV ablations on a held-out slice.")
    parser.add_argument("--tasks-file", type=Path, required=True, help="Held-out tasks file (.json or .jsonl).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for Act IV outputs.")
    parser.add_argument("--n-trials", type=int, default=5, help="Trials per condition.")
    parser.add_argument(
        "--cost-per-million-tokens",
        type=float,
        default=DEFAULT_COST_PER_MILLION_TOKENS,
        help="Token cost assumption used for estimated cost-per-task.",
    )
    args = parser.parse_args(argv)

    tasks_file = args.tasks_file.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    tasks = _load_tasks(tasks_file)

    all_rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        rows, summary = _run_variant(
            tasks=tasks,
            variant=variant,
            n_trials=args.n_trials,
            cost_per_million_tokens=args.cost_per_million_tokens,
        )
        all_rows.extend(rows)
        summaries[variant.name] = summary

    stats = {
        "method_vs_day1": _exact_paired_permutation_test(
            summaries["method"]["trial_pass_rates"],
            summaries["day1_baseline"]["trial_pass_rates"],
        ),
        "method_vs_ablation_no_audit": _exact_paired_permutation_test(
            summaries["method"]["trial_pass_rates"],
            summaries["ablation_no_audit"]["trial_pass_rates"],
        ),
        "method_vs_ablation_no_confidence": _exact_paired_permutation_test(
            summaries["method"]["trial_pass_rates"],
            summaries["ablation_no_confidence"]["trial_pass_rates"],
        ),
    }

    results = {
        "generated_at": _utc_now_iso(),
        "tasks_file": str(tasks_file),
        "n_tasks": len(tasks),
        "n_trials": args.n_trials,
        "conditions": summaries,
        "statistical_tests": stats,
    }
    _write_json(output_dir / "ablation_results.json", results)
    _write_jsonl(output_dir / "held_out_traces.jsonl", all_rows)
    (output_dir / "method.md").write_text(
        _render_method_md(
            tasks_file=tasks_file,
            output_dir=output_dir,
            n_tasks=len(tasks),
            n_trials=args.n_trials,
            summaries=summaries,
            stats=stats,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
