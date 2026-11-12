#!/usr/bin/env bash
# Paired follow-up: Direct LLM, no-path OUEG, then answer-preserving QEG-ECAR.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

PYTHON="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-oss-20b}"
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)
# User traffic budget is 10 requests/minute. This is process-global in the
# client, so model calls remain paced even while KG construction overlaps.
export OPENROUTER_MIN_REQUEST_INTERVAL_SECONDS="${OPENROUTER_MIN_REQUEST_INTERVAL_SECONDS:-6}"

input="$repo_root/benchmarks/hybridqa/hybridqa-dev-shard02-after-stratified20-next50.json"
run_tag="${RUN_TAG:-hybridqa-followup50-answer-to-proof-gpt-oss-20b-$(date -u +%Y%m%dT%H%M%SZ)}"
output_dir="$repo_root/data/results/$run_tag"
workers="${MAX_WORKERS:-2}"
mkdir -p "$output_dir"
exec 9>"$output_dir/.runner.lock"
flock -n 9 || { echo "Another runner owns $output_dir" >&2; exit 1; }

common=(
  --dataset hybridqa --input "$input"
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --limit 50 --top-k 5 --second-stage-k 3
  --max-context-chars 24000 --max-table-rows-for-kg 999999
  --max-output-tokens 1024 --temperature 0
  --collision-passage-budget 12 --focus-passage-budget-per-candidate 2
  --focus-query-fallback-budget 2 --l2-existing-witness-budget 2
  --l2-max-edges-per-candidate 16 --l2-max-contexts-per-candidate 3
  --l2-context-snippet-chars 900 --l2-evidence-mode delta_only
  --ambiguity-policy prompt --oueg-context-mode lossless
  --max-workers "$workers" --llm-max-concurrent-requests "$workers"
  --llm-timeout-seconds 120 --llm-sdk-retries 2 --quiet-records --resume
)

echo "Follow-up 50 | model: $OPENROUTER_MODEL | output: $output_dir"
"$PYTHON" -m src.run_baselines --method direct_llm \
  --output "$output_dir/direct_llm.jsonl" "${common[@]}"
"$PYTHON" -m src.run_baselines --method online_unified_evidence_graph \
  --no-path-guidance --no-path-focused-prompt \
  --output "$output_dir/no_path.jsonl" "${common[@]}"

# This pass never changes `answer`: it validates whether a cached no-path
# answer maps to deterministic evidence in the same retrieved graph.
"$PYTHON" scripts/replay_ecar.py \
  --input "$output_dir/no_path.jsonl" \
  --output "$output_dir/qeg_ecar_answer_to_proof.jsonl" \
  --preserve-answer

"$PYTHON" scripts/fast_benchmark_summary.py \
  "$output_dir/direct_llm.jsonl" "$output_dir/no_path.jsonl" \
  "$output_dir/qeg_ecar_answer_to_proof.jsonl"
"$PYTHON" scripts/fast_benchmark_summary.py --compare \
  "$output_dir/direct_llm.jsonl" "$output_dir/no_path.jsonl"

