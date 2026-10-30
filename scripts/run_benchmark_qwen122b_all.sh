#!/usr/bin/env bash
# ==============================================================================
# Script Benchmark Toàn diện với Qwen 122B (Qwen 3.5 122B) trên HybridQA & OTT-QA
# Hỗ trợ cả 2 chế độ:
#   1. OpenRouter API: LLM_PROVIDER=openrouter (OPENROUTER_MODEL="qwen/qwen3.5-122b-a10b")
#   2. Local Server (vLLM / SGLang / Ollama): LLM_PROVIDER=openai_compatible (COMPAT_BASE_URL="http://localhost:8000/v1")
# ==============================================================================

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# 1. Tự động load file .env nếu có (không ghi đè biến môi trường đã export từ shell)
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

# 2. Xác định Python interpreter
resolve_python() {
  local candidate resolved
  local candidates=()
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    candidates=("$PYTHON_BIN")
  else
    candidates=("$repo_root/.venv/bin/python" "python3")
  fi
  for candidate in "${candidates[@]}"; do
    if [[ "$candidate" == */* ]]; then resolved="$candidate"; else resolved="$(command -v "$candidate" 2>/dev/null || true)"; fi
    [[ -n "$resolved" && -x "$resolved" ]] || continue
    if "$resolved" -c "import src.run_baselines" >/dev/null 2>&1; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  echo "Không tìm thấy môi trường Python phù hợp. Hãy đặt PYTHON_BIN=<path_to_python>." >&2
  return 1
}

python_bin="$(resolve_python)"

# 3. Cấu hình Model & Provider cho Qwen 122B
# Mặc định dùng openrouter, nếu bạn chạy vLLM local thì set: LLM_PROVIDER=openai_compatible
export LLM_PROVIDER="${LLM_PROVIDER:-openrouter}"

if [[ "$LLM_PROVIDER" == "openai_compatible" ]]; then
  export COMPAT_MODEL="${COMPAT_MODEL:-Qwen/Qwen3.5-122B-A10B}"
  export COMPAT_BASE_URL="${COMPAT_BASE_URL:-http://localhost:8000/v1}"
  export COMPAT_API_KEY="${COMPAT_API_KEY:-EMPTY}"
else
  export OPENROUTER_MODEL="${OPENROUTER_MODEL:-qwen/qwen3.5-122b-a10b}"
  export OPENROUTER_REASONING_ENABLED="${OPENROUTER_REASONING_ENABLED:-true}"
fi

# 4. Xác định Model Label
model_label="$($python_bin -c 'import re; from src.llm.client import get_provider; p=get_provider(); name=getattr(p, "name", "unknown-provider"); model=getattr(p, "model", None) or "unknown-model"; print(re.sub(r"[^A-Za-z0-9._-]+", "-", name + "__" + model).strip("-") or "unknown-provider__unknown-model")')"

# 5. Cấu hình Tham số Chạy
max_workers="${MAX_WORKERS:-4}"
llm_max_concurrent_requests="${LLM_MAX_CONCURRENT_REQUESTS:-$max_workers}"
run_tag="${RUN_TAG:-qwen122b-$(date -u +%Y%m%d)}"

# Tập datasets cần chạy (hybridqa, ottqa, hoặc cả hai)
target_datasets="${DATASETS:-hybridqa ottqa}"

# Cấu hình Shard (mặc định Shard 01 cho HybridQA, Shard 01 cho OTT-QA hoặc tuỳ chỉnh từ biến môi trường)
hybridqa_shards=(${HYBRIDQA_SHARDS:-01})
ottqa_shards=(${OTTQA_SHARDS:-01 02 03 04 05})

# Phương pháp đánh giá (đủ cả 5 baseline tiêu chuẩn)
default_methods=(online_unified_evidence_graph direct_llm odyssey graph_retrieval_no_path path_text_top_n)
if [[ -n "${METHODS:-}" ]]; then
  read -r -a methods <<< "$METHODS"
else
  methods=("${default_methods[@]}")
fi

echo "=========================================================================="
echo "KHỞI ĐỘNG BENCHMARK TOÀN DIỆN VỚI QWEN 122B"
echo "Thời gian: $(date --iso-8601=seconds)"
echo "Python: $python_bin"
echo "Provider: $LLM_PROVIDER"
echo "Model Label: $model_label"
echo "Workers: $max_workers | Concurrent LLM Calls: $llm_max_concurrent_requests"
echo "Datasets: $target_datasets"
echo "Methods: ${methods[*]}"
echo "=========================================================================="

# ------------------------------------------------------------------------------
# HÀM CHẠY CHO HYBRIDQA
# ------------------------------------------------------------------------------
run_hybridqa() {
  local result_root="$repo_root/data/results/qwen122b-benchmark/hybridqa"
  local log_root="$repo_root/data/logs/qwen122b-benchmark/hybridqa"
  local input_prefix="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027"

  mkdir -p "$result_root" "$log_root"

  echo ""
  echo ">>> [HYBRIDQA] BẮT ĐẦU CHẠY SHARDS: ${hybridqa_shards[*]}"
  for shard in "${hybridqa_shards[@]}"; do
    local input="${input_prefix}-shard${shard}.json"
    if [[ ! -f "$input" ]]; then
      echo "LỖI: Không tìm thấy input HybridQA: $input" >&2
      continue
    fi
    local shard_label="shard${shard}-of08"

    for method in "${methods[@]}"; do
      local method_args=()
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

      local method_dir="$result_root/$method"
      mkdir -p "$method_dir"
      local output="$method_dir/${shard_label}__${model_label}__${method}.jsonl"
      local log="$log_root/${shard_label}__${model_label}__${method}.log"

      echo "[$(date --iso-8601=seconds)] [HybridQA] Start method=$method shard=$shard"
      PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
        --dataset hybridqa \
        --method "$method" \
        --input "$input" \
        --tables-dir data/WikiTables-WithLinks/tables_tok \
        --passages-dir data/WikiTables-WithLinks/request_tok \
        --output "$output" \
        --top-k 5 --second-stage-k 3 --n-paths 5 --max-replans 0 \
        --max-context-chars 24000 --max-output-tokens 2048 --temperature 0 \
        --max-workers "$max_workers" --llm-max-concurrent-requests "$llm_max_concurrent_requests" \
        --llm-timeout-seconds 180 --llm-sdk-retries 2 --fail-fast --quiet-records --resume \
        "${method_args[@]}" >> "$log" 2>&1
      echo "[$(date --iso-8601=seconds)] [HybridQA] Done method=$method shard=$shard"
    done
  done

  echo ""
  echo "=== [TỔNG HỢP KẾT QUẢ BENCHMARK HYBRIDQA] ==="
  "$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$result_root" || true
}

# ------------------------------------------------------------------------------
# HÀM CHẠY CHO OTT-QA
# ------------------------------------------------------------------------------
run_ottqa() {
  local result_root="$repo_root/data/results/qwen122b-benchmark/ottqa"
  local log_root="$repo_root/data/logs/qwen122b-benchmark/ottqa"
  local input_prefix="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027"

  mkdir -p "$result_root" "$log_root"

  echo ""
  echo ">>> [OTT-QA] BẮT ĐẦU CHẠY SHARDS: ${ottqa_shards[*]}"
  for shard in "${ottqa_shards[@]}"; do
    local input="${input_prefix}-shard${shard}.json"
    if [[ ! -f "$input" ]]; then
      echo "LỖI: Không tìm thấy input OTT-QA: $input" >&2
      continue
    fi

    local shard_label
    if (( 10#$shard <= 5 )); then
      shard_label="shard${shard}-of05"
    else
      shard_label="shard${shard}-of10"
    fi

    for method in "${methods[@]}"; do
      local method_args=()
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

      local method_dir="$result_root/$method"
      mkdir -p "$method_dir"
      local output="$method_dir/${shard_label}__${model_label}__${method}.jsonl"
      local log="$log_root/${shard_label}__${model_label}__${method}.log"

      echo "[$(date --iso-8601=seconds)] [OTT-QA] Start method=$method shard=$shard"
      PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
        --dataset ottqa \
        --method "$method" \
        --input "$input" \
        --tables-dir data/OTT-QA/data/traindev_tables_tok \
        --passages-dir data/OTT-QA/data/traindev_request_tok \
        --output "$output" \
        --top-k 5 --second-stage-k 3 --n-paths 5 --max-replans 0 \
        --max-context-chars 24000 --max-output-tokens 2048 --temperature 0 \
        --max-workers "$max_workers" --llm-max-concurrent-requests "$llm_max_concurrent_requests" \
        --llm-timeout-seconds 180 --llm-sdk-retries 2 --fail-fast --quiet-records --resume \
        "${method_args[@]}" >> "$log" 2>&1
      echo "[$(date --iso-8601=seconds)] [OTT-QA] Done method=$method shard=$shard"
    done
  done

  echo ""
  echo "=== [TỔNG HỢP KẾT QUẢ BENCHMARK OTT-QA] ==="
  "$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$result_root" || true
}

# ------------------------------------------------------------------------------
# ĐIỀU PHỐI CHẠY THEO TARGET_DATASETS
# ------------------------------------------------------------------------------
for dataset in $target_datasets; do
  case "$dataset" in
    hybridqa)
      run_hybridqa
      ;;
    ottqa)
      run_ottqa
      ;;
    *)
      echo "Bỏ qua dataset không hợp lệ: $dataset (chỉ hỗ trợ: hybridqa, ottqa)"
      ;;
  esac
done

echo ""
echo "=========================================================================="
echo "HOÀN TẤT TOÀN BỘ BENCHMARK QWEN 122B CHO CẢ 2 DATASET!"
echo "Thời gian kết thúc: $(date --iso-8601=seconds)"
echo "Kết quả HybridQA lưu tại: $repo_root/data/results/qwen122b-benchmark/hybridqa"
echo "Kết quả OTT-QA lưu tại:   $repo_root/data/results/qwen122b-benchmark/ottqa"
echo "=========================================================================="

