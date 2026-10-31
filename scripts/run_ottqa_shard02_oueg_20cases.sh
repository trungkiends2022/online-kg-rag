#!/usr/bin/env bash
# Run 20 cases of OTT-QA Shard 02 with full OUEG (L1 full graph + L2 diagnostic delta recovery)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-oss-20b}"
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)

shard="02"
limit="20"
workers="${MAX_WORKERS:-4}"
input="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard${shard}.json"
output="$repo_root/data/results/ottqa-500-seed2027/oueg-gpt-oss-20b-shard${shard}-${limit}.jsonl"
mkdir -p "$(dirname "$output")"

echo "=========================================================================="
echo "Running OUEG L1, L2 Full on OTT-QA Shard $shard (limit $limit)"
echo "Date: $(date --iso-8601=seconds)"
echo "Model: $OPENROUTER_MODEL"
echo "Workers: $workers"
echo "Input: $input"
echo "Output: $output"
echo "=========================================================================="

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

echo ""
echo "=========================================================================="
echo "OTT-QA Shard $shard 20 cases completed!"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="

# Summarize results ultra-fast
"$PYTHON" "$repo_root/scripts/fast_benchmark_summary.py" "$output"

