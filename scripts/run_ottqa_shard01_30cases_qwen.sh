#!/usr/bin/env bash
# Run 30 cases of OTT-QA Shard 01 with Qwen 30B / 32B via OpenRouter
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f "$repo_root/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue
    if [[ "$line" == *=* ]]; then
      var_name="${line%%=*}"
      var_val="${line#*=}"
      var_name="$(echo -n "$var_name" | tr -d ' ')"
      var_val="${var_val%\"}"
      var_val="${var_val#\"}"
      var_val="${var_val%\'}"
      var_val="${var_val#\'}"
      if [[ -z "${!var_name+x}" ]]; then
        export "$var_name"="$var_val"
      fi
    fi
  done < "$repo_root/.env"
fi

python_bin="$repo_root/.venv/bin/python"
export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-qwen/qwen3-30b-a3b-instruct-2507}"
export OPENROUTER_REASONING_ENABLED="${OPENROUTER_REASONING_ENABLED:-true}"
max_workers="${MAX_WORKERS:-4}"
llm_max_concurrent_requests="${LLM_MAX_CONCURRENT_REQUESTS:-$max_workers}"

shard="01"
limit="${LIMIT:-30}"
tag="${RUN_TAG:-qwen30b-shard01-30cases}"
output_dir="$repo_root/data/results/ottqa-500-seed2027/$tag"
log_dir="$repo_root/data/logs/ottqa-500-seed2027/$tag"
mkdir -p "$output_dir" "$log_dir"

input="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard${shard}.json"

default_methods=(online_unified_evidence_graph direct_llm odyssey)
if [[ -n "${METHODS:-}" ]]; then
  read -r -a methods <<< "$METHODS"
else
  methods=("${default_methods[@]}")
fi

echo "=========================================================================="
echo "Running OTT-QA Shard 01 (Limit: $limit) with $OPENROUTER_MODEL"
echo "Methods: ${methods[*]}"
echo "Output: $output_dir"
echo "Workers: $max_workers"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="

for method in "${methods[@]}"; do
  echo "[$(date --iso-8601=seconds)] Starting method: $method"
  output_file="$output_dir/${method}.jsonl"
  log_file="$log_dir/${method}.log"

  method_args=()
  [[ "$method" == "path_text_top_n" ]] && method_args+=(--strict-path-text-top-n)
  if [[ "$method" == "online_unified_evidence_graph" ]]; then
    method_args+=(
      --max-table-rows-for-kg 999999
      --no-path-focused-prompt
      --prompt-path-budget 8
      --collision-passage-budget 12
      --focus-passage-budget-per-candidate 2
      --focus-query-fallback-budget 2
      --l2-existing-witness-budget 2
      --l2-max-edges-per-candidate 16
      --l2-max-contexts-per-candidate 3
      --l2-context-snippet-chars 900
      --l2-evidence-mode delta_only
      --ambiguity-policy prompt
      --oueg-context-mode lossless
    )
  fi

  PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
    --dataset ottqa \
    --method "$method" \
    --input "$input" \
    --tables-dir data/OTT-QA/data/traindev_tables_tok \
    --passages-dir data/OTT-QA/data/traindev_request_tok \
    --output "$output_file" \
    --limit "$limit" \
    --top-k 5 \
    --second-stage-k 3 \
    --n-paths 5 \
    --max-replans 0 \
    --max-context-chars 24000 \
    --max-output-tokens 2048 \
    --temperature 0 \
    --max-workers "$max_workers" \
    --llm-max-concurrent-requests "$llm_max_concurrent_requests" \
    --llm-timeout-seconds 180 \
    --llm-sdk-retries 2 \
    --quiet-records \
    --resume \
    "${method_args[@]}" 2>&1 | tee "$log_file"

  echo "[$(date --iso-8601=seconds)] Finished method: $method"
done

echo "=========================================================================="
echo "=== Summary Results ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$output_dir" || true
echo "Completed at: $(date --iso-8601=seconds)"
echo "=========================================================================="

