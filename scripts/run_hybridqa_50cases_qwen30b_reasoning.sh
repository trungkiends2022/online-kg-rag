#!/usr/bin/env bash
# ==============================================================================
# Run 50 cases of HybridQA Shard 01 with Qwen 30B Reasoning for ALL 5 BASELINES
# ==============================================================================
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f "$repo_root/.env" ]]; then
  set -a
  source "$repo_root/.env"
  set +a
fi

python_bin="$repo_root/.venv/bin/python"

export LLM_PROVIDER=openrouter
# Model Qwen 30B có native reasoning CoT
export OPENROUTER_MODEL="qwen/qwen3-vl-30b-a3b-thinking"
export OPENROUTER_REASONING_ENABLED=true

workers="${MAX_WORKERS:-2}"
limit="${LIMIT:-50}"
shard="01"
tag="hybridqa-shard01-50cases-qwen30b-reasoning"

output_dir="$repo_root/data/results/$tag"
log_dir="$repo_root/data/logs/$tag"
mkdir -p "$output_dir" "$log_dir"

input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"

# Danh sách đầy đủ cả 5 baseline tiêu chuẩn
default_methods=(
  online_unified_evidence_graph
  direct_llm
  odyssey
  graph_retrieval_no_path
  path_text_top_n
)
if [[ -n "${METHODS:-}" ]]; then
  read -r -a methods <<< "$METHODS"
else
  methods=("${default_methods[@]}")
fi

echo "=========================================================================="
echo "CHẠY 50 CÂU HYBRIDQA SHARD 01 VỚI QWEN 30B REASONING (FULL 5 BASELINES)"
echo "Model: $OPENROUTER_MODEL"
echo "Reasoning: $OPENROUTER_REASONING_ENABLED"
echo "Workers: $workers | Limit: $limit"
echo "Methods: ${methods[*]}"
echo "Input: $input"
echo "Output Root: $output_dir"
echo "Thời gian bắt đầu: $(date --iso-8601=seconds)"
echo "=========================================================================="

for method in "${methods[@]}"; do
  echo ""
  echo "--------------------------------------------------------------------------"
  echo "[$(date --iso-8601=seconds)] >>> BẮT ĐẦU METHOD: $method"
  echo "--------------------------------------------------------------------------"

  method_output="$output_dir/hybridqa_shard01_${limit}cases_${method}.jsonl"
  method_log="$log_dir/hybridqa_shard01_${limit}cases_${method}.log"

  method_args=()
  if [[ "$method" == "path_text_top_n" ]]; then
    method_args+=(--strict-path-text-top-n)
  fi
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
    --dataset hybridqa \
    --method "$method" \
    --input "$input" \
    --tables-dir data/WikiTables-WithLinks/tables_tok \
    --passages-dir data/WikiTables-WithLinks/request_tok \
    --output "$method_output" \
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
    --resume \
    "${method_args[@]}" 2>&1 | tee "$method_log"

  echo "[$(date --iso-8601=seconds)] >>> HOÀN THÀNH METHOD: $method"
done

echo ""
echo "=========================================================================="
echo "=== [KẾT QUẢ TỔNG HỢP SO SÁNH 5 BASELINE TRÊN 50 CÂU HYBRIDQA] ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$output_dir" || true
echo "Thời gian kết thúc: $(date --iso-8601=seconds)"
echo "=========================================================================="
