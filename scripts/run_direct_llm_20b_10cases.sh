#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-20b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)

workers=2

echo "=== 1/2: Direct LLM (gpt-oss-20b) on OTT-QA (10 cases) ==="
PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset ottqa \
  --method direct_llm \
  --input benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard01.json \
  --tables-dir data/OTT-QA/data/traindev_tables_tok \
  --passages-dir data/OTT-QA/data/traindev_request_tok \
  --output data/results/ottqa-500-seed2027/direct_llm-gpt-oss-20b-shard01-10.jsonl \
  --limit 10 \
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

echo "=== 2/2: Direct LLM (gpt-oss-20b) on HybridQA (10 cases) ==="
PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset hybridqa \
  --method direct_llm \
  --input benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard02.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-1500-seed2027/direct_llm-gpt-oss-20b-shard02-10.jsonl \
  --limit 10 \
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

echo "=== Completed both 10-case runs with gpt-oss-20b! ==="
