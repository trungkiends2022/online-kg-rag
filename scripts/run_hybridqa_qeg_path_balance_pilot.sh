#!/usr/bin/env bash
# Pilot the unranked multi-path QEG branch against cached follow-up no-path IDs.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-oss-20b}"
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)
export OPENROUTER_MIN_REQUEST_INTERVAL_SECONDS="${OPENROUTER_MIN_REQUEST_INTERVAL_SECONDS:-6}"

input="$repo_root/benchmarks/hybridqa/hybridqa-dev-shard02-after-stratified20-next50.json"
run_tag="${RUN_TAG:-hybridqa-qeg-path-balance-pilot20-gpt-oss-20b-$(date -u +%Y%m%dT%H%M%SZ)}"
output_dir="$repo_root/data/results/$run_tag"
output="$output_dir/qeg_path_balance.jsonl"
workers="${MAX_WORKERS:-2}"
mkdir -p "$output_dir"

echo "QEG-PathBalance pilot | model: $OPENROUTER_MODEL | output: $output"
PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset hybridqa --method qeg_path_balance --input "$input" \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output "$output" --limit 20 --resume \
  --top-k 5 --second-stage-k 3 --max-table-rows-for-kg 999999 \
  --max-context-chars 24000 --max-output-tokens 1024 --temperature 0 \
  --no-path-focused-prompt --collision-passage-budget 12 \
  --focus-passage-budget-per-candidate 2 --focus-query-fallback-budget 2 \
  --l2-existing-witness-budget 2 --l2-max-edges-per-candidate 16 \
  --l2-max-contexts-per-candidate 3 --l2-context-snippet-chars 900 \
  --l2-evidence-mode delta_only --ambiguity-policy prompt --oueg-context-mode lossless \
  --max-workers "$workers" --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 120 --llm-sdk-retries 2 --quiet-records

"$PYTHON" scripts/fast_benchmark_summary.py "$output"
