#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import uuid
from collections import deque
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


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == value[-1]) and value[0] in {"'", '"'}):
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        env[key] = _strip_quotes(value)
    return env


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


@dataclass(frozen=True)
class SubprocessResult:
    cmd: list[str]
    returncode: int
    output_tail: str


class SubprocessError(RuntimeError):
    def __init__(self, *, cmd: list[str], returncode: int, output_tail: str):
        super().__init__(f"Command failed (exit {returncode}): {' '.join(cmd)}")
        self.cmd = cmd
        self.returncode = returncode
        self.output_tail = output_tail


def _run_subprocess(cmd: list[str], cwd: Path, env: dict[str, str]) -> SubprocessResult:
    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Command not found: {cmd[0]}. Is it installed and on PATH?"
        ) from exc

    tail = deque(maxlen=400)
    assert process.stdout is not None
    for line in process.stdout:
        sys.stdout.write(line)
        tail.append(line.rstrip("\n"))
    process.wait()

    output_tail = "\n".join(tail)
    if process.returncode != 0:
        raise SubprocessError(cmd=cmd, returncode=process.returncode, output_tail=output_tail)
    return SubprocessResult(cmd=cmd, returncode=process.returncode, output_tail=output_tail)


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


def _tau2_command_prefix(tau2_repo: Path) -> list[str]:
    uv_bin = shutil.which("uv")
    if uv_bin:
        return [uv_bin, "run", "tau2"]

    local_tau2 = tau2_repo / ".venv" / "bin" / "tau2"
    if local_tau2.exists():
        return [str(local_tau2)]

    tau2_bin = shutil.which("tau2")
    if tau2_bin:
        return [tau2_bin]

    return ["uv", "run", "tau2"]


def _maybe_convert_results_to_dir(tau2_repo: Path, run_dir: Path, env: dict[str, str]) -> None:
    cmd = _tau2_command_prefix(tau2_repo) + ["convert-results", str(run_dir), "--to", "dir", "--no-backup"]
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


def _langfuse_client_if_configured(*, require: bool) -> Any:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")
    environment = os.getenv("LANGFUSE_TRACING_ENVIRONMENT") or "development"

    if not public_key or not secret_key:
        if require:
            raise RuntimeError(
                "Langfuse credentials missing. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY."
            )
        return None
    try:
        from langfuse import Langfuse  # type: ignore
    except Exception:
        if require:
            raise RuntimeError("Langfuse SDK not installed. `pip install langfuse`.")
        return None
    try:
        return Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
            environment=environment,
        )
    except Exception as exc:
        if require:
            raise RuntimeError(f"Failed to initialize Langfuse client: {exc}") from exc
        return None


def _as_langfuse_metadata(value: dict[str, Any]) -> dict[str, str]:
    # Metadata values are most useful as short strings and are commonly capped.
    out: dict[str, str] = {}
    for k, v in value.items():
        if v is None:
            continue
        s = str(v)
        out[k] = s[:200]
    return out


def _truncate_for_langfuse(value: Any, *, max_depth: int = 4, max_list: int = 30, max_str: int = 800) -> Any:
    if max_depth <= 0:
        return "<truncated>"
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_str else (value[:max_str] + "…")
    if isinstance(value, list):
        truncated = [_truncate_for_langfuse(v, max_depth=max_depth - 1, max_list=max_list, max_str=max_str) for v in value[:max_list]]
        if len(value) > max_list:
            truncated.append(f"<truncated {len(value) - max_list} items>")
        return truncated
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in list(value.items())[:200]:
            out[str(k)] = _truncate_for_langfuse(v, max_depth=max_depth - 1, max_list=max_list, max_str=max_str)
        if len(value) > 200:
            out["<truncated_keys>"] = len(value) - 200
        return out
    return _truncate_for_langfuse(str(value), max_depth=max_depth, max_list=max_list, max_str=max_str)


def _langfuse_log_task_run(
    *,
    langfuse: Any,
    run_id: str,
    record: TaskTrialRecord,
    save_to: str,
    tau2_cmd: list[str],
    sim_raw: dict[str, Any],
) -> Optional[str]:
    if langfuse is None:
        return None

    # One Langfuse trace per task+trial. Use a deterministic trace id for stability.
    try:
        trace_id = langfuse.create_trace_id(
            seed=f"{run_id}:{record.partition}:{record.model}:{save_to}:{record.task_id}:{record.trial}"
        )
    except Exception:
        trace_id = None

    trace_context = {"trace_id": trace_id} if isinstance(trace_id, str) else None
    try:
        with langfuse.start_as_current_observation(
            as_type="span",
            name="tau2_retail",
            trace_context=trace_context,
            input={
                "tau2_cmd": tau2_cmd,
                "task_id": record.task_id,
                "trial": record.trial,
                "model": record.model,
                "partition": record.partition,
                "save_to": save_to,
                "raw_summary": _truncate_for_langfuse(sim_raw),
            },
            metadata=_as_langfuse_metadata(
                {
                    "task_id": record.task_id,
                    "trial": record.trial,
                    "model": record.model,
                    "partition": record.partition,
                    "save_to": save_to,
                }
            ),
        ) as span:
            actual_trace_id = getattr(span, "trace_id", None) or trace_id
            status_message = (
                "passed"
                if record.passed is True
                else ("failed" if record.passed is False else "unknown")
            )
            span.update(
                output={
                    "passed": record.passed,
                    "latency_ms": record.latency_ms,
                    "tokens": record.tokens,
                    "cost_usd": record.cost_usd,
                },
                level="ERROR" if record.passed is False else "DEFAULT",
                status_message=status_message,
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


def _langfuse_log_subprocess_error(
    *,
    langfuse: Any,
    run_id: str,
    model: str,
    partition: str,
    save_to: str,
    tau2_cmd: list[str],
    error: str,
    output_tail: str,
) -> None:
    if langfuse is None:
        return
    try:
        trace_id = langfuse.create_trace_id(seed=f"{run_id}:cli_error:{partition}:{model}:{save_to}")
    except Exception:
        trace_id = None
    trace_context = {"trace_id": trace_id} if isinstance(trace_id, str) else None
    try:
        with langfuse.start_as_current_observation(
            as_type="span",
            name="tau2_retail",
            trace_context=trace_context,
            input={
                "tau2_cmd": tau2_cmd,
                "model": model,
                "partition": partition,
                "save_to": save_to,
            },
            metadata=_as_langfuse_metadata(
                {"task_id": "tau2_cli", "trial": 0, "model": model, "partition": partition, "save_to": save_to}
            ),
        ) as span:
            span.update(
                output={"subprocess_error": error, "output_tail": output_tail},
                level="ERROR",
                status_message="subprocess_failed",
            )
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
    cmd = _build_tau2_run_cmd(
        tau2_repo,
        domain=domain,
        agent_llm=agent_llm,
        user_llm=user_llm,
        task_split_name=task_split_name,
        num_tasks=num_tasks,
        num_trials=num_trials,
        max_concurrency=max_concurrency,
        save_to=save_to,
        log_level=log_level,
    )
    _run_subprocess(cmd, cwd=tau2_repo, env=env)

    run_dir = _tau2_data_dir(tau2_repo, env) / "simulations" / save_to
    results_path = run_dir / "results.json"
    if not results_path.exists():
        raise RuntimeError(
            f"tau2 completed but no results found at {results_path}. "
            "Check `TAU2_DATA_DIR` and `--save-to`."
        )
    return run_dir


def _build_tau2_run_cmd(
    tau2_repo: Path,
    *,
    domain: str,
    agent_llm: str,
    user_llm: str,
    task_split_name: str,
    num_tasks: int,
    num_trials: int,
    max_concurrency: int,
    save_to: str,
    log_level: str,
) -> list[str]:
    return _tau2_command_prefix(tau2_repo) + [
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


def _records_from_simulations(
    *,
    simulations: list[dict[str, Any]],
    model: str,
    partition: str,
    save_to: str,
    tau2_cmd: list[str],
    run_id: str,
    langfuse: Any,
) -> list[TaskTrialRecord]:
    extracted: list[tuple[str, int, dict[str, Any], Optional[bool], Optional[float], Optional[int], str, Optional[float]]] = []
    fallback_timestamp = _utc_now_iso()
    for sim in simulations:
        task_id = _extract_task_id(sim) or "unknown"
        trial = _extract_trial(sim) or 0
        passed = _extract_passed(sim)
        latency_ms = _extract_latency_ms(sim)
        tokens = _extract_tokens(sim)
        timestamp = _extract_timestamp(sim) or fallback_timestamp
        cost_usd = _extract_cost_usd(sim)
        extracted.append((task_id, trial, sim, passed, latency_ms, tokens, timestamp, cost_usd))

    # Assign trials for any simulation records that don't carry an explicit trial index.
    by_task: dict[str, list[tuple[str, int, dict[str, Any], Optional[bool], Optional[float], Optional[int], str, Optional[float]]]] = {}
    for item in extracted:
        by_task.setdefault(item[0], []).append(item)

    records: list[TaskTrialRecord] = []
    for task_id, items in by_task.items():
        for idx, (task_id, trial, sim_raw, passed, latency_ms, tokens, timestamp, cost_usd) in enumerate(
            items, start=1
        ):
            resolved_trial = trial if trial > 0 else idx
            record = TaskTrialRecord(
                task_id=task_id,
                trial=resolved_trial,
                model=model,
                partition=partition,
                passed=passed,
                latency_ms=latency_ms,
                tokens=tokens,
                trace_id=uuid.uuid4().hex,
                timestamp=timestamp,
                cost_usd=cost_usd,
            )
            langfuse_trace_id = _langfuse_log_task_run(
                langfuse=langfuse,
                run_id=run_id,
                record=record,
                save_to=save_to,
                tau2_cmd=tau2_cmd,
                sim_raw=sim_raw,
            )
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

    return records


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
    if sys.version_info < (3, 10):
        raise RuntimeError("This script requires Python 3.10+")
    if sys.version_info < (3, 11):
        print("Warning: Python 3.11+ is recommended.", file=sys.stderr)

    parser = argparse.ArgumentParser(description="Run a tau2 baseline via subprocess (uv).")
    parser.add_argument("--tau2-repo", type=Path, required=True, help="Path to a local tau2-bench repo checkout.")
    parser.add_argument("--output-dir", type=Path, default=Path("eval"), help="Directory to write logs to.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional dotenv file to load (default: .env).",
    )
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

    env = dict(os.environ)
    env_file = args.env_file.expanduser().resolve()
    env.update(_load_env_file(env_file))

    # Ensure the local process environment sees the dotenv values too.
    for k, v in env.items():
        os.environ.setdefault(k, v)

    _ensure_llm_api_key_present()

    if args.tau2_data_dir is not None:
        env["TAU2_DATA_DIR"] = str(args.tau2_data_dir.expanduser().resolve())

    run_id = uuid.uuid4().hex
    langfuse = _langfuse_client_if_configured(require=args.require_langfuse)

    try:
        if args.smoke_first:
            smoke_cmd = _build_tau2_run_cmd(
                tau2_repo,
                domain=args.partition,
                agent_llm=args.agent_llm,
                user_llm=args.user_llm,
                task_split_name=args.task_split_name,
                num_tasks=1,
                num_trials=1,
                max_concurrency=1,
                save_to=args.smoke_save_to,
                log_level=args.log_level,
            )
            try:
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
            except SubprocessError as exc:
                _langfuse_log_subprocess_error(
                    langfuse=langfuse,
                    run_id=run_id,
                    model=args.agent_llm,
                    partition=args.partition,
                    save_to=args.smoke_save_to,
                    tau2_cmd=smoke_cmd,
                    error=str(exc),
                    output_tail=exc.output_tail,
                )
                raise

            smoke_sims = _load_simulations(smoke_dir)
            smoke_records = _records_from_simulations(
                simulations=smoke_sims,
                model=args.agent_llm,
                partition=args.partition,
                save_to=args.smoke_save_to,
                tau2_cmd=smoke_cmd,
                run_id=run_id,
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

        baseline_cmd = _build_tau2_run_cmd(
            tau2_repo,
            domain=args.partition,
            agent_llm=args.agent_llm,
            user_llm=args.user_llm,
            task_split_name=args.task_split_name,
            num_tasks=args.n_tasks,
            num_trials=args.n_trials,
            max_concurrency=args.max_concurrency,
            save_to=args.save_to,
            log_level=args.log_level,
        )

        try:
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
        except SubprocessError as exc:
            _langfuse_log_subprocess_error(
                langfuse=langfuse,
                run_id=run_id,
                model=args.agent_llm,
                partition=args.partition,
                save_to=args.save_to,
                tau2_cmd=baseline_cmd,
                error=str(exc),
                output_tail=exc.output_tail,
            )
            _append_score_log(
                args.output_dir / "score_log.json",
                {
                    "partition": args.partition,
                    "model": args.agent_llm,
                    "n_tasks": args.n_tasks,
                    "n_trials": args.n_trials,
                    "pass_at_1": None,
                    "ci_95": None,
                    "cost_per_run_usd": None,
                    "p50_latency_ms": None,
                    "p95_latency_ms": None,
                    "run_at": _utc_now_iso(),
                    "error": str(exc),
                },
            )
            raise

        sims = _load_simulations(run_dir)
        records = _records_from_simulations(
            simulations=sims,
            model=args.agent_llm,
            partition=args.partition,
            save_to=args.save_to,
            tau2_cmd=baseline_cmd,
            run_id=run_id,
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
    except SubprocessError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        _langfuse_flush(langfuse)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
