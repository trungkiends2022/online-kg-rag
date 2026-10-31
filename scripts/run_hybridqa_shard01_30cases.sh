#!/usr/bin/env bash
# Run 30 cases of HybridQA Shard 01 with the full OUEG configuration.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-120b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)
export MAX_WORKERS=4
export LLM_MAX_CONCURRENT_REQUESTS=4

python_bin="$repo_root/.venv/bin/python"
input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard01.json"
output="$repo_root/data/results/hybridqa-1500-seed2027/oueg-l1full-l2delta-shard01-30.jsonl"
mkdir -p "$(dirname "$output")"

echo "=========================================================================="
echo "Starting HybridQA Shard 01 (30 cases) - Full OUEG Configuration"
echo "Date: $(date --iso-8601=seconds)"
echo "Model: $OPENROUTER_MODEL"
echo "Workers: $MAX_WORKERS"
echo "Input: $input"
echo "Output: $output"
echo "=========================================================================="

PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
  --dataset hybridqa \
  --method online_unified_evidence_graph \
  --input "$input" \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output "$output" \
  --limit 30 \
  --top-k 5 \
  --second-stage-k 3 \
  --max-table-rows-for-kg 999999 \
  --max-context-chars 24000 \
  --max-output-tokens 1024 \
  --temperature 0 \
  --no-path-focused-prompt \
  --prompt-path-budget 8 \
  --collision-passage-budget 12 \
  --focus-passage-budget-per-candidate 2 \
  --l2-evidence-mode delta_only \
  --ambiguity-policy prompt \
  --oueg-context-mode lossless \
  --n-paths 5 \
  --max-replans 0 \
  --max-workers "$MAX_WORKERS" \
  --llm-max-concurrent-requests "$LLM_MAX_CONCURRENT_REQUESTS" \
  --llm-timeout-seconds 120 \
  --llm-sdk-retries 2 \
  --quiet-records

echo ""
echo "=========================================================================="
echo "HybridQA Shard 01 (30 cases) run completed!"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="
