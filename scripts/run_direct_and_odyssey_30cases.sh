#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-120b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)

shard="02"
limit="30"
workers=2
input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"

echo "=== 1/2: Running Direct LLM (limit 30) ==="
PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset hybridqa \
  --method direct_llm \
  --input "$input" \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-1500-seed2027/direct_llm-shard02-30.jsonl \
  --limit "$limit" \
  --top-k 5 \
  --second-stage-k 3 \
  --max-context-chars 24000 \
  --max-output-tokens 1024 \
  --temperature 0 \
  --max-workers "$workers" \
  --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 120 \
  --llm-sdk-retries 2 \
  --quiet-records

echo "=== 2/2: Running Odyssey (limit 30) ==="
PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset hybridqa \
  --method odyssey \
  --input "$input" \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-1500-seed2027/odyssey-shard02-30.jsonl \
  --limit "$limit" \
  --top-k 5 \
  --second-stage-k 3 \
  --max-context-chars 24000 \
  --max-output-tokens 1024 \
  --temperature 0 \
  --max-workers "$workers" \
  --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 120 \
  --llm-sdk-retries 2 \
  --quiet-records

echo "=== Both Baselines Completed! ==="

