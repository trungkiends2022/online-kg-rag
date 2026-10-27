#!/usr/bin/env bash
# Run 20 cases of OTT-QA Shard 02 with Direct LLM (gpt-oss-20b)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-20b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)

shard="02"
limit="20"
workers="${MAX_WORKERS:-4}"
input="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard${shard}.json"
output="$repo_root/data/results/ottqa-500-seed2027/direct_llm-gpt-oss-20b-shard${shard}-${limit}.jsonl"
mkdir -p "$(dirname "$output")"

echo "=========================================================================="
echo "Running Direct LLM on OTT-QA Shard $shard (limit $limit)"
echo "Date: $(date --iso-8601=seconds)"
echo "Model: $OPENROUTER_MODEL"
echo "Workers: $workers"
echo "Input: $input"
echo "Output: $output"
echo "=========================================================================="

PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset ottqa \
  --method direct_llm \
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
  --max-workers "$workers" \
  --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 120 \
  --llm-sdk-retries 2 \
  --quiet-records

echo ""
echo "=========================================================================="
echo "OTT-QA Shard $shard Direct LLM 20 cases completed!"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="

# Summarize and compare head-to-head with OUEG
oueg_file="$repo_root/data/results/ottqa-500-seed2027/oueg-gpt-oss-20b-shard${shard}-${limit}.jsonl"
if [[ -f "$oueg_file" ]]; then
  echo "=== Head-to-Head Comparison: OUEG vs Direct LLM ==="
  "$PYTHON" "$repo_root/scripts/fast_benchmark_summary.py" --compare "$oueg_file" "$output"
else
  "$PYTHON" "$repo_root/scripts/fast_benchmark_summary.py" "$output"
fi

