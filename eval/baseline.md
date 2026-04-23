# τ²-Bench Baseline (dev slice)

This repo runs τ²-Bench via the external CLI (no tau2 internals imported) and logs:

- `eval/trace_log.jsonl` (one line per task × trial)
- `eval/score_log.json` (appended run summaries)

## Prereqs

- Python 3.11+ recommended
- `uv` installed
- A local checkout of `tau2-bench` (this repo assumes `../tau2-bench`)
- LLM provider API key(s) in env (e.g. `OPENROUTER_API_KEY`)

Optional (Langfuse):

- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
- `LANGFUSE_BASE_URL` (e.g. US cloud)
- `LANGFUSE_TRACING_ENVIRONMENT=development`

## Run: 1-task smoke test (retail)

```bash
python eval/run_baseline.py \
  --tau2-repo ../tau2-bench \
  --partition retail \
  --smoke-save-to smoke_retail \
  --save-to baseline_retail_dev \
  --n-tasks 30 \
  --n-trials 5
```

Notes:

- `eval/run_baseline.py` loads `.env` by default; override with `--env-file`.
- If Langfuse is configured, each task-trial gets a `tau2_retail` trace and the trace id is written to `eval/trace_log.jsonl`.

## “Overnight” run tips

- Use a unique `--save-to` per run so you can resume/debug easily.
- Keep `--max-concurrency` conservative to avoid rate limits.

Example:

```bash
python eval/run_baseline.py \
  --tau2-repo ../tau2-bench \
  --partition retail \
  --task-split-name dev \
  --agent-llm openrouter/qwen/qwen3-30b-a3b \
  --user-llm openrouter/qwen/qwen3-30b-a3b \
  --n-tasks 30 \
  --n-trials 5 \
  --max-concurrency 3 \
  --save-to retail_dev_30x5_$(date +%Y%m%d_%H%M%S)
```

## Outputs

- `eval/trace_log.jsonl` schema:
  - `{task_id, trial, model, partition, passed, latency_ms, tokens, trace_id, timestamp}`
- `eval/score_log.json` schema (appended list):
  - `{partition, model, n_tasks, n_trials, pass_at_1, ci_95, cost_per_run_usd, p50_latency_ms, p95_latency_ms, run_at, ...}`

