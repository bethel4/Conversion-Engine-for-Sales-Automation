#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class TaskTrialRecord:
    task_id: str
    trial: int
    model: str
    partition: str
    passed: Optional[bool]
    latency_ms: Optional[float]
    tokens: Optional[int]
    trace_id: str
    timestamp: str
    cost_usd: Optional[float] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RuntimeError(f"Missing result file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return int(value)
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 0:
            return False
        if value == 1:
            return True
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0"}:
            return False
    return None


def _get_nested(obj: Any, path: Iterable[str]) -> Any:
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return None
        if key not in cur:
            return None
        cur = cur[key]
    return cur


def _first_present(obj: dict[str, Any], paths: list[tuple[str, ...]]) -> Any:
    for p in paths:
        v = _get_nested(obj, p)
        if v is not None:
            return v
    return None


def _extract_task_id(sim: dict[str, Any]) -> Optional[str]:
    candidates = [
        ("task_id",),
        ("taskId",),
        ("task", "id"),
        ("task", "task_id"),
        ("task", "taskId"),
    ]
    value = _first_present(sim, candidates)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_trial(sim: dict[str, Any]) -> Optional[int]:
    candidates = [
        ("trial",),
        ("trial_index",),
        ("trialIndex",),
        ("trial_num",),
        ("trialNum",),
    ]
    return _safe_int(_first_present(sim, candidates))


def _extract_passed(sim: dict[str, Any]) -> Optional[bool]:
    candidates = [
        ("passed",),
        ("pass",),
        ("success",),
        ("succeeded",),
        ("solved",),
        ("evaluation", "passed"),
        ("evaluation", "success"),
        ("eval", "passed"),
        ("eval", "success"),
        ("result", "passed"),
        ("result", "success"),
    ]
    direct = _safe_bool(_first_present(sim, candidates))
    if direct is not None:
        return direct

    reward_candidates = [
        ("reward",),
        ("total_reward",),
        ("totalReward",),
        ("evaluation", "reward"),
        ("evaluation", "total_reward"),
    ]
    reward = _safe_float(_first_present(sim, reward_candidates))
    if reward is not None:
        if reward == 0:
            return False
        if reward == 1:
            return True
    return None


def _extract_latency_ms(sim: dict[str, Any]) -> Optional[float]:
    candidates_ms = [
        ("latency_ms",),
        ("latencyMs",),
        ("duration_ms",),
        ("durationMs",),
        ("wall_time_ms",),
        ("wallTimeMs",),
    ]
    val = _safe_float(_first_present(sim, candidates_ms))
    if val is not None:
        return val

    candidates_s = [
        ("latency_s",),
        ("latencySeconds",),
        ("duration_s",),
        ("durationSeconds",),
        ("wall_time_s",),
        ("wallTimeSeconds",),
    ]
    val_s = _safe_float(_first_present(sim, candidates_s))
    if val_s is not None:
        return val_s * 1000.0

    return None


def _extract_tokens(sim: dict[str, Any]) -> Optional[int]:
    direct_candidates = [
        ("tokens",),
        ("total_tokens",),
        ("totalTokens",),
        ("usage", "total_tokens"),
        ("usage", "totalTokens"),
    ]
    direct = _safe_int(_first_present(sim, direct_candidates))
    if direct is not None:
        return direct

    usage_candidates = [
        ("usage",),
        ("llm_usage",),
        ("llmUsage",),
        ("token_usage",),
        ("tokenUsage",),
    ]
    usage = _first_present(sim, usage_candidates)
    if isinstance(usage, dict):
        total = _safe_int(usage.get("total_tokens") or usage.get("totalTokens"))
        if total is not None:
            return total
        prompt = _safe_int(usage.get("prompt_tokens") or usage.get("promptTokens")) or 0
        completion = _safe_int(usage.get("completion_tokens") or usage.get("completionTokens")) or 0
        if prompt or completion:
            return prompt + completion

    return None


def _extract_timestamp(sim: dict[str, Any]) -> Optional[str]:
    candidates = [
        ("timestamp",),
        ("created_at",),
        ("createdAt",),
        ("started_at",),
        ("startedAt",),
        ("run_at",),
        ("runAt",),
    ]
    value = _first_present(sim, candidates)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _extract_cost_usd(sim: dict[str, Any]) -> Optional[float]:
    candidates = [
        ("cost_usd",),
        ("costUsd",),
        ("cost",),
        ("usage", "cost_usd"),
        ("usage", "costUsd"),
    ]
    cost = _safe_float(_first_present(sim, candidates))
    if cost is None:
        return None
    if cost < 0:
        return None
    return cost


def _run_subprocess(cmd: list[str], cwd: Path, env: dict[str, str]) -> None:
    try:
        subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            check=True,
            text=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Command not found: {cmd[0]}. Is it installed and on PATH?"
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed (exit {exc.returncode}): {' '.join(cmd)}") from exc


def _tau2_data_dir(tau2_repo: Path, env: dict[str, str]) -> Path:
    data_dir = env.get("TAU2_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    return tau2_repo / "data"


def _ensure_llm_api_key_present() -> None:
    # tau2 uses LiteLLM under the hood; exact key depends on provider/model.
    # We fail early if *no* common provider key is present.
    common_keys = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "XAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "MISTRAL_API_KEY",
        "COHERE_API_KEY",
        "DEEPSEEK_API_KEY",
        "TOGETHER_API_KEY",
    ]
    if any(os.getenv(k) for k in common_keys):
        return
    raise RuntimeError(
        "No LLM provider API key found in environment. "
        f"Set one of: {', '.join(common_keys)}"
    )


def _maybe_convert_results_to_dir(tau2_repo: Path, run_dir: Path, env: dict[str, str]) -> None:
    cmd = ["uv", "run", "tau2", "convert-results", str(run_dir), "--to", "dir", "--no-backup"]
    _run_subprocess(cmd, cwd=tau2_repo, env=env)


_SIM_FILENAME_RE = re.compile(r"^sim_(\d+)\.json$")


def _sim_sort_key(path: Path) -> tuple[int, str]:
    m = _SIM_FILENAME_RE.match(path.name)
    if m:
        return (int(m.group(1)), path.name)
    return (10**9, path.name)


def _load_simulations(run_dir: Path) -> list[dict[str, Any]]:
    sims_dir = run_dir / "simulations"
    if sims_dir.is_dir():
        sim_paths = sorted(sims_dir.glob("*.json"), key=_sim_sort_key)
        sims: list[dict[str, Any]] = []
        for p in sim_paths:
            obj = _read_json(p)
            if isinstance(obj, dict):
                sims.append(obj)
        if sims:
            return sims

    results_path = run_dir / "results.json"
    results = _read_json(results_path)
    if isinstance(results, dict) and isinstance(results.get("simulations"), list):
        sims: list[dict[str, Any]] = []
        for item in results["simulations"]:
            if isinstance(item, dict):
                sims.append(item)
        if sims:
            return sims

    raise RuntimeError(
        f"Could not find simulation data under {run_dir}. "
        "Expected `simulations/*.json` (dir format) or `results.json` with a `simulations` list."
    )


def _assign_trials_if_missing(records: list[TaskTrialRecord]) -> list[TaskTrialRecord]:
    # If trial is missing from the raw results, fall back to ordering per task.
    by_task: dict[str, list[TaskTrialRecord]] = {}
    for r in records:
        by_task.setdefault(r.task_id, []).append(r)

    updated: list[TaskTrialRecord] = []
    for task_id, items in by_task.items():
        # Preserve input order (already sorted by sim_*.json index).
        for idx, r in enumerate(items, start=1):
            if r.trial > 0:
                updated.append(r)
            else:
                updated.append(
                    TaskTrialRecord(
                        task_id=r.task_id,
                        trial=idx,
                        model=r.model,
                        partition=r.partition,
                        passed=r.passed,
                        latency_ms=r.latency_ms,
                        tokens=r.tokens,
                        trace_id=r.trace_id,
                        timestamp=r.timestamp,
                        cost_usd=r.cost_usd,
                    )
                )
    return updated


def _wilson_ci_95(passed: int, total: int) -> Optional[tuple[float, float]]:
    if total <= 0:
        return None
    # Wilson score interval for 95% CI.
    z = 1.959963984540054  # scipy.stats.norm.ppf(0.975)
    phat = passed / total
    denom = 1.0 + (z * z) / total
    center = (phat + (z * z) / (2.0 * total)) / denom
    margin = (
        z
        * ((phat * (1.0 - phat) + (z * z) / (4.0 * total)) / total) ** 0.5
        / denom
    )
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return (lo, hi)


def _percentile(values: list[float], pct: float) -> Optional[float]:
    if not values:
        return None
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _append_score_log(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []
    else:
        existing = []

    if not isinstance(existing, list):
        existing = [existing]
    existing.append(entry)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _langfuse_client_if_configured() -> Any:
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import get_client  # type: ignore
    except Exception:
        return None
    try:
        return get_client()
    except Exception:
        return None


def _langfuse_log_task_run(langfuse: Any, record: TaskTrialRecord) -> Optional[str]:
    if langfuse is None:
        return None

    # Create a deterministic Langfuse trace id so re-runs can correlate if desired.
    try:
        trace_id = langfuse.create_trace_id(
            seed=f"{record.partition}:{record.model}:{record.task_id}:{record.trial}"
        )
    except Exception:
        trace_id = None

    trace_context = {"trace_id": trace_id} if isinstance(trace_id, str) else None
    try:
        with langfuse.start_as_current_observation(
            as_type="span",
            name="tau2.task_run",
            trace_context=trace_context,
        ) as span:
            actual_trace_id = getattr(span, "trace_id", None) or trace_id
            span.update(
                metadata={"task_id": record.task_id, "model": record.model, "trial": record.trial},
                output={
                    "passed": record.passed,
                    "latency_ms": record.latency_ms,
                    "tokens": record.tokens,
                    "cost_usd": record.cost_usd,
                },
            )
    except Exception:
        # Langfuse must never break the benchmark run.
        return None
    return actual_trace_id if isinstance(actual_trace_id, str) and actual_trace_id else None


def _langfuse_flush(langfuse: Any) -> None:
    if langfuse is None:
        return
    try:
        langfuse.flush()
    except Exception:
        return


def run_tau2_eval(
    *,
    tau2_repo: Path,
    domain: str,
    agent_llm: str,
    user_llm: str,
    num_tasks: int,
    num_trials: int,
    save_to: str,
    task_split_name: str,
    max_concurrency: int,
    log_level: str,
    env: dict[str, str],
) -> Path:
    cmd = [
        "uv",
        "run",
        "tau2",
        "run",
        "--domain",
        domain,
        "--agent-llm",
        agent_llm,
        "--user-llm",
        user_llm,
        "--task-split-name",
        task_split_name,
        "--num-tasks",
        str(num_tasks),
        "--num-trials",
        str(num_trials),
        "--max-concurrency",
        str(max_concurrency),
        "--save-to",
        save_to,
        "--log-level",
        log_level,
        "--auto-resume",
    ]

    _run_subprocess(cmd, cwd=tau2_repo, env=env)

    run_dir = _tau2_data_dir(tau2_repo, env) / "simulations" / save_to
    results_path = run_dir / "results.json"
    if not results_path.exists():
        raise RuntimeError(
            f"tau2 completed but no results found at {results_path}. "
            "Check `TAU2_DATA_DIR` and `--save-to`."
        )
    return run_dir


def _records_from_simulations(
    *,
    simulations: list[dict[str, Any]],
    model: str,
    partition: str,
    langfuse: Any,
) -> list[TaskTrialRecord]:
    records: list[TaskTrialRecord] = []
    fallback_timestamp = _utc_now_iso()
    for sim in simulations:
        task_id = _extract_task_id(sim) or "unknown"
        trial = _extract_trial(sim) or 0
        passed = _extract_passed(sim)
        latency_ms = _extract_latency_ms(sim)
        tokens = _extract_tokens(sim)
        timestamp = _extract_timestamp(sim) or fallback_timestamp
        cost_usd = _extract_cost_usd(sim)

        record = TaskTrialRecord(
            task_id=task_id,
            trial=trial,
            model=model,
            partition=partition,
            passed=passed,
            latency_ms=latency_ms,
            tokens=tokens,
            trace_id=uuid.uuid4().hex,
            timestamp=timestamp,
            cost_usd=cost_usd,
        )
        langfuse_trace_id = _langfuse_log_task_run(langfuse, record)
        if isinstance(langfuse_trace_id, str) and langfuse_trace_id:
            record = TaskTrialRecord(
                task_id=record.task_id,
                trial=record.trial,
                model=record.model,
                partition=record.partition,
                passed=record.passed,
                latency_ms=record.latency_ms,
                tokens=record.tokens,
                trace_id=langfuse_trace_id,
                timestamp=record.timestamp,
                cost_usd=record.cost_usd,
            )
        records.append(record)
    return _assign_trials_if_missing(records)


def _write_logs(
    *,
    output_dir: Path,
    records: list[TaskTrialRecord],
    model: str,
    partition: str,
    n_tasks: int,
    n_trials: int,
) -> None:
    trace_rows: list[dict[str, Any]] = []
    for r in records:
        trace_rows.append(
            {
                "task_id": r.task_id,
                "trial": r.trial,
                "model": r.model,
                "partition": r.partition,
                "passed": r.passed,
                "latency_ms": r.latency_ms,
                "tokens": r.tokens,
                "trace_id": r.trace_id,
                "timestamp": r.timestamp,
            }
        )
    _append_jsonl(output_dir / "trace_log.jsonl", trace_rows)

    trial1 = [r for r in records if r.trial == 1 and r.passed is not None]
    pass_at_1: Optional[float]
    ci_95: Optional[list[float]]
    if trial1:
        passed_n = sum(1 for r in trial1 if r.passed)
        total_n = len(trial1)
        pass_at_1 = passed_n / total_n
        ci = _wilson_ci_95(passed_n, total_n)
        ci_95 = [ci[0], ci[1]] if ci else None
    else:
        pass_at_1 = None
        ci_95 = None

    latencies = [r.latency_ms for r in records if isinstance(r.latency_ms, (int, float))]
    p50_latency_ms = _percentile([float(x) for x in latencies], 50) if latencies else None
    p95_latency_ms = _percentile([float(x) for x in latencies], 95) if latencies else None

    costs = [r.cost_usd for r in records if isinstance(r.cost_usd, (int, float))]
    cost_per_run_usd = (statistics.mean([float(c) for c in costs]) if costs else None)

    score_entry = {
        "partition": partition,
        "model": model,
        "n_tasks": n_tasks,
        "n_trials": n_trials,
        "pass_at_1": pass_at_1,
        "ci_95": ci_95,
        "cost_per_run_usd": cost_per_run_usd,
        "p50_latency_ms": p50_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "run_at": _utc_now_iso(),
    }
    _append_score_log(output_dir / "score_log.json", score_entry)


def main(argv: Optional[list[str]] = None) -> int:
    if sys.version_info < (3, 11):
        raise RuntimeError("This script requires Python 3.11+")

    parser = argparse.ArgumentParser(description="Run a tau2 baseline via subprocess (uv).")
    parser.add_argument("--tau2-repo", type=Path, required=True, help="Path to a local tau2-bench repo checkout.")
    parser.add_argument("--output-dir", type=Path, default=Path("eval"), help="Directory to write logs to.")
    parser.add_argument("--partition", default="retail", help="tau2 domain/partition to run (default: retail).")
    parser.add_argument("--agent-llm", default="gpt-4.1", help="Agent LLM identifier for tau2.")
    parser.add_argument("--user-llm", default="gpt-4.1", help="User simulator LLM identifier for tau2.")
    parser.add_argument("--task-split-name", default="base", help="Task split name (default: base).")
    parser.add_argument("--max-concurrency", type=int, default=3, help="Max concurrent simulations.")
    parser.add_argument("--log-level", default="ERROR", help="tau2 log level.")
    parser.add_argument("--save-to", default="baseline_retail", help="tau2 save directory name under data/simulations/.")
    parser.add_argument("--n-tasks", type=int, default=30, help="Number of tasks for the baseline run.")
    parser.add_argument("--n-trials", type=int, default=5, help="Number of trials for the baseline run.")
    parser.add_argument(
        "--smoke-first",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Run a 1-task smoke test before the baseline run.",
    )
    parser.add_argument("--smoke-save-to", default="smoke_retail", help="save-to name for smoke test.")
    parser.add_argument("--tau2-data-dir", type=Path, default=None, help="Override TAU2_DATA_DIR for the tau2 run.")
    parser.add_argument(
        "--require-langfuse",
        action="store_true",
        help="Fail if Langfuse credentials or SDK are not available.",
    )

    args = parser.parse_args(argv)
    tau2_repo = args.tau2_repo.expanduser().resolve()
    if not tau2_repo.exists():
        raise RuntimeError(f"--tau2-repo does not exist: {tau2_repo}")

    _ensure_llm_api_key_present()

    env = dict(os.environ)
    if args.tau2_data_dir is not None:
        env["TAU2_DATA_DIR"] = str(args.tau2_data_dir.expanduser().resolve())

    langfuse = _langfuse_client_if_configured()
    if args.require_langfuse and langfuse is None:
        raise RuntimeError(
            "Langfuse not configured. Set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY "
            "and ensure `langfuse` is installed."
        )

    if args.smoke_first:
        smoke_dir = run_tau2_eval(
            tau2_repo=tau2_repo,
            domain=args.partition,
            agent_llm=args.agent_llm,
            user_llm=args.user_llm,
            num_tasks=1,
            num_trials=1,
            save_to=args.smoke_save_to,
            task_split_name=args.task_split_name,
            max_concurrency=1,
            log_level=args.log_level,
            env=env,
        )
        _maybe_convert_results_to_dir(tau2_repo, smoke_dir, env)
        smoke_sims = _load_simulations(smoke_dir)
        smoke_records = _records_from_simulations(
            simulations=smoke_sims,
            model=args.agent_llm,
            partition=args.partition,
            langfuse=langfuse,
        )
        _write_logs(
            output_dir=args.output_dir,
            records=smoke_records,
            model=args.agent_llm,
            partition=args.partition,
            n_tasks=1,
            n_trials=1,
        )

    run_dir = run_tau2_eval(
        tau2_repo=tau2_repo,
        domain=args.partition,
        agent_llm=args.agent_llm,
        user_llm=args.user_llm,
        num_tasks=args.n_tasks,
        num_trials=args.n_trials,
        save_to=args.save_to,
        task_split_name=args.task_split_name,
        max_concurrency=args.max_concurrency,
        log_level=args.log_level,
        env=env,
    )

    _maybe_convert_results_to_dir(tau2_repo, run_dir, env)
    sims = _load_simulations(run_dir)
    records = _records_from_simulations(
        simulations=sims,
        model=args.agent_llm,
        partition=args.partition,
        langfuse=langfuse,
    )
    _write_logs(
        output_dir=args.output_dir,
        records=records,
        model=args.agent_llm,
        partition=args.partition,
        n_tasks=args.n_tasks,
        n_trials=args.n_trials,
    )

    _langfuse_flush(langfuse)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
