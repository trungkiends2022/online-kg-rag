#!/usr/bin/env bash
# Run 10 cases of HybridQA and 10 cases of OTT-QA with Qwen 122B (OUEG)
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
export LLM_PROVIDER="${LLM_PROVIDER:-openrouter}"

if [[ "$LLM_PROVIDER" == "openai_compatible" ]]; then
  export COMPAT_MODEL="${COMPAT_MODEL:-Qwen/Qwen3.5-122B-A10B}"
  export COMPAT_BASE_URL="${COMPAT_BASE_URL:-http://localhost:8000/v1}"
  export COMPAT_API_KEY="${COMPAT_API_KEY:-EMPTY}"
  export COMPAT_REASONING_ENABLED="${COMPAT_REASONING_ENABLED:-true}"
else
  export OPENROUTER_MODEL="${OPENROUTER_MODEL:-qwen/qwen3.5-122b-a10b}"
  export OPENROUTER_REASONING_ENABLED="${OPENROUTER_REASONING_ENABLED:-true}"
fi

workers=2
limit=10
tag="qwen3.5-122b-10cases"

output_dir="$repo_root/data/results/$tag"
mkdir -p "$output_dir"

echo "=========================================================================="
echo "Starting 10-case test with $OPENROUTER_MODEL"
echo "Tag: $tag | Workers: $workers | Limit: $limit"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="

# 1. HybridQA (10 cases)
echo ""
echo "=== [1/2] Running HybridQA Shard 01 (10 cases) ==="
hybridqa_input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard01.json"
hybridqa_output="$output_dir/hybridqa_shard01_oueg_10cases.jsonl"

PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
  --dataset hybridqa \
  --method online_unified_evidence_graph \
  --input "$hybridqa_input" \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output "$hybridqa_output" \
  --limit "$limit" \
  --top-k 5 \
  --second-stage-k 3 \
  --n-paths 5 \
  --max-replans 0 \
  --max-context-chars 24000 \
  --max-output-tokens 2048 \
  --temperature 0 \
  --max-workers "$workers" \
  --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 180 \
  --llm-sdk-retries 2 \
  --quiet-records \
  --max-table-rows-for-kg 999999 \
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
  --resume

echo "=== HybridQA 10 cases finished! ==="

# 2. OTT-QA (10 cases)
echo ""
echo "=== [2/2] Running OTT-QA Shard 01 (10 cases) ==="
ottqa_input="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard01.json"
ottqa_output="$output_dir/ottqa_shard01_oueg_10cases.jsonl"

PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
  --dataset ottqa \
  --method online_unified_evidence_graph \
  --input "$ottqa_input" \
  --tables-dir data/OTT-QA/data/traindev_tables_tok \
  --passages-dir data/OTT-QA/data/traindev_request_tok \
  --output "$ottqa_output" \
  --limit "$limit" \
  --top-k 5 \
  --second-stage-k 3 \
  --n-paths 5 \
  --max-replans 0 \
  --max-context-chars 24000 \
  --max-output-tokens 2048 \
  --temperature 0 \
  --max-workers "$workers" \
  --llm-max-concurrent-requests "$workers" \
  --llm-timeout-seconds 180 \
  --llm-sdk-retries 2 \
  --quiet-records \
  --max-table-rows-for-kg 999999 \
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
  --resume

echo "=== OTT-QA 10 cases finished! ==="

echo ""
echo "=========================================================================="
echo "=== Summary Results ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$output_dir" || true
echo "Completed at: $(date --iso-8601=seconds)"
echo "=========================================================================="

