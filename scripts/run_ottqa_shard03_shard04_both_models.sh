#!/usr/bin/env bash
# Run OTT-QA Shard 03 and Shard 04 for both GPT-OSS 20B and GPT-OSS 120B (all 5 baselines).
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
max_workers="${MAX_WORKERS:-4}"
llm_max_concurrent_requests="${LLM_MAX_CONCURRENT_REQUESTS:-$max_workers}"

run_shards_for_model() {
  local model="$1"
  local tag="$2"
  local shards=("${@:3}")

  echo "=========================================================================="
  echo "BẮT ĐẦU CHẠY OTT-QA VỚI MODEL: $model"
  echo "Shards: ${shards[*]} | Tag: $tag | Workers: $max_workers"
  echo "Thời gian: $(date --iso-8601=seconds)"
  echo "=========================================================================="

  LLM_PROVIDER=openrouter \
  OPENROUTER_MODEL="$model" \
  OPENROUTER_REASONING_ENABLED=true \
  MAX_WORKERS="$max_workers" \
  LLM_MAX_CONCURRENT_REQUESTS="$llm_max_concurrent_requests" \
  RUN_TAG="$tag" \
  RESULT_ROOT="$repo_root/data/results/ottqa-500-seed2027/$tag" \
  LOG_ROOT="$repo_root/data/logs/ottqa-500-seed2027/$tag" \
  bash "$repo_root/scripts/run_ottqa_500.sh" "${shards[@]}"

  echo "=== [TỔNG HỢP CHO $tag] ==="
  "$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$repo_root/data/results/ottqa-500-seed2027/$tag" || true
}

echo "##########################################################################"
echo "TIẾN TRÌNH OTT-QA SHARD 03 & 04 (CẢ 2 MODEL: 20B VÀ 120B)"
echo "##########################################################################"

# BƯỚC 1: Chạy 20B cho Shard 03 và 04
run_shards_for_model "openai/gpt-oss-20b" "gpt-oss-20b-shard03-04" 03 04

# BƯỚC 2: Chạy 120B cho Shard 03 và 04
run_shards_for_model "openai/gpt-oss-120b" "gpt-oss-120b-shard03-04" 03 04

echo "##########################################################################"
echo "HOÀN TẤT TOÀN BỘ SHARD 03 & 04 CHO CẢ 2 MODEL!"
echo "Thời gian hoàn thành: $(date --iso-8601=seconds)"
echo "##########################################################################"
