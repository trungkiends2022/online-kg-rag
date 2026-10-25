#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-120b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)

shard="01"
limit="30"
workers=2
input="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard${shard}.json"
output="$repo_root/data/results/ottqa-500-seed2027/oueg-shard${shard}-30.jsonl"
mkdir -p "$(dirname "$output")"

echo "=== Running OUEG Focus Recovery on OTT-QA (limit 30) ==="
echo "Model: $OPENROUTER_MODEL"
echo "Input: $input"
echo "Output: $output"

PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset ottqa \
  --method online_unified_evidence_graph \
  --input "$input" \
  --tables-dir data/OTT-QA/data/traindev_tables_tok \
  --passages-dir data/OTT-QA/data/traindev_request_tok \
  --output "$output" \
  --limit "$limit" \
  --top-k 5 \
  --second-stage-k 3 \
  --max-context-chars 24000 \
  --max-output-tokens 1024 \
  --temperature 0 \
  --no-path-focused-prompt \
  --prompt-path-budget 8 \
  --collision-passage-budget 12 \
  --focus-passage-budget-per-candidate 2 \
  --focus-query-fallback-budget 2 \
  --l2-existing-witness-budget 2 \
  --l2-max-edges-per-candidate 16 \
  --l2-max-contexts-per-candidate 3 \
  --l2-context-snippet-chars 900 \
  --l2-evidence-mode delta_only \
  --ambiguity-policy prompt \
  --oueg-context-mode lossless \
  --n-paths 5 \
  --max-replans 0 \
  --max-workers "$workers" \
  --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 120 \
  --llm-sdk-retries 2 \
  --quiet-records

echo "=== OTT-QA 30 cases run completed! ==="

