#!/usr/bin/env bash
# ==============================================================================
# Run 100 cases of OTT-QA Shard 01 with Qwen 122B (Reasoning Enabled by default)
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

# Tự động ưu tiên giá trị đã cấu hình trong .env hoặc biến môi trường truyền vào
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

max_workers="${MAX_WORKERS:-4}"
llm_max_concurrent_requests="${LLM_MAX_CONCURRENT_REQUESTS:-$max_workers}"

run_tag="${RUN_TAG:-ottqa-shard01-100cases-qwen122b-reasoning}"
input="${INPUT:-$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard01.json}"
shard_label="shard01-100cases"

result_root="$repo_root/data/results/$run_tag"
log_root="$repo_root/data/logs/$run_tag"
mkdir -p "$result_root" "$log_root"

# Mặc định chạy OUEG và Direct LLM, hoặc tuỳ chọn qua METHODS
default_methods=(
  online_unified_evidence_graph
  direct_llm
)
if [[ -n "${METHODS:-}" ]]; then
  read -r -a methods <<< "$METHODS"
else
  methods=("${default_methods[@]}")
fi

model_label="$($python_bin -c '
import re
from src.llm.client import get_provider
provider = get_provider()
name = getattr(provider, "name", "unknown-provider")
model = getattr(provider, "model", None) or "unknown-model"
label = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{name}__{model}").strip("-")
print(label or "unknown-provider__unknown-model")
')"

echo "=========================================================================="
echo "CHẠY 100 CÂU OTT-QA SHARD 01 VỚI QWEN 122B"
echo "Model: $OPENROUTER_MODEL (Reasoning: $OPENROUTER_REASONING_ENABLED)"
echo "Methods: ${methods[*]}"
echo "Workers: $max_workers | Output: $result_root"
echo "Thời gian bắt đầu: $(date --iso-8601=seconds)"
echo "=========================================================================="

for method in "${methods[@]}"; do
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

  method_dir="$result_root/$method"
  mkdir -p "$method_dir"
  output="$method_dir/${shard_label}__${model_label}__${method}.jsonl"
  method_log="$log_root/${shard_label}__${model_label}__${method}.log"

  echo "[$(date --iso-8601=seconds)] >>> Bắt đầu method=$method"
  PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
    --dataset ottqa \
    --method "$method" \
    --input "$input" \
    --tables-dir data/OTT-QA/data/traindev_tables_tok \
    --passages-dir data/OTT-QA/data/traindev_request_tok \
    --output "$output" \
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
    --fail-fast \
    --quiet-records \
    --resume \
    "${method_args[@]}" 2>&1 | tee "$method_log"

  echo "[$(date --iso-8601=seconds)] >>> Hoàn thành method=$method"
done

echo ""
echo "=========================================================================="
echo "=== [KẾT QUẢ TỔNG HỢP 100 CÂU OTT-QA SHARD 01] ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$result_root" || true
echo "Thời gian kết thúc: $(date --iso-8601=seconds)"
echo "=========================================================================="

