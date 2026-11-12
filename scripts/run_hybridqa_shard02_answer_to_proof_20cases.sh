#!/usr/bin/env bash
# Answer-preserving no-path reader + selective proof attachment on HybridQA.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-oss-120b}"
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)

shard="02"
limit="20"
workers="${MAX_WORKERS:-2}"
run_tag="${RUN_TAG:-hybridqa-answer-to-proof-shard02-20-gpt-oss-120b-$(date -u +%Y%m%dT%H%M%SZ)}"
input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"
output_dir="$repo_root/data/results/$run_tag"
output="$output_dir/qeg_answer_to_proof.jsonl"
mkdir -p "$output_dir"
example_args=()
if [[ -n "${EXAMPLE_ID:-}" ]]; then
  example_args=(--example-id "$EXAMPLE_ID")
fi

echo "Running answer-preserving no-path + proof attachment"
echo "Model: $OPENROUTER_MODEL | cases: $limit | workers: $workers"
echo "Output: $output"

PYTHONUNBUFFERED=1 "$PYTHON" -m src.run_baselines \
  --dataset hybridqa \
  --method qeg_answer_to_proof \
  --input "$input" \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output "$output" \
  --resume \
  "${example_args[@]}" \
  --limit "$limit" \
  --top-k 5 --second-stage-k 3 \
  --max-context-chars 24000 --max-output-tokens 1024 --temperature 0 \
  --no-path-guidance --no-path-focused-prompt \
  --collision-passage-budget 12 --focus-passage-budget-per-candidate 2 \
  --focus-query-fallback-budget 2 --l2-existing-witness-budget 2 \
  --l2-max-edges-per-candidate 16 --l2-max-contexts-per-candidate 3 \
  --l2-context-snippet-chars 900 --l2-evidence-mode delta_only \
  --ambiguity-policy prompt --oueg-context-mode lossless \
  --max-workers "$workers" --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 120 --llm-sdk-retries 2 --quiet-records

"$PYTHON" "$repo_root/scripts/fast_benchmark_summary.py" "$output"
