#!/usr/bin/env bash
# Run the 5 main baselines on the 100-case OTT-QA Shard 01 benchmark with full L1/L2 OUEG configuration.
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

resolve_python() {
  local candidate resolved
  local candidates=()
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    candidates=("$PYTHON_BIN")
  else
    candidates=("$repo_root/.venv/bin/python" "python3")
  fi
  for candidate in "${candidates[@]}"; do
    if [[ "$candidate" == */* ]]; then
      resolved="$candidate"
    else
      resolved="$(command -v "$candidate" 2>/dev/null || true)"
    fi
    [[ -n "$resolved" && -x "$resolved" ]] || continue
    if "$resolved" -c "import src.run_baselines" >/dev/null 2>&1; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  echo "No usable Python interpreter found. Set PYTHON_BIN to an environment with project dependencies." >&2
  return 1
}

resolve_model_label() {
  "$python_bin" -c '
import re
from src.llm.client import get_provider
provider = get_provider()
name = getattr(provider, "name", "unknown-provider")
model = getattr(provider, "model", None) or "unknown-model"
label = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{name}__{model}").strip("-")
print(label or "unknown-provider__unknown-model")
'
}

python_bin="$(resolve_python)"
model_label="$(resolve_model_label)"
run_tag="${RUN_TAG:-ottqa-shard01-100-benchmark-20b}"
input="${INPUT:-$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard01.json}"
shard_label="${SHARD_LABEL:-}"
if [[ -z "$shard_label" ]]; then
  if [[ "$input" =~ shard([0-9]+) ]]; then
    shard_label="shard${BASH_REMATCH[1]}-100cases"
  else
    shard_label="shard01-100cases"
  fi
fi
result_root="${RESULT_ROOT:-$repo_root/data/results/$run_tag}"
log_root="${LOG_ROOT:-$repo_root/data/logs/$run_tag}"

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

mkdir -p "$result_root" "$log_root"
exec 9>"$result_root/.runner.lock"
if ! flock -n 9; then
  echo "Another runner already owns $result_root/.runner.lock" >&2
  exit 1
fi

echo "[$(date --iso-8601=seconds)] run_tag=$run_tag methods=${methods[*]} input=$input"
echo "model_label=$model_label"
echo "git_head=$(git rev-parse HEAD)"
max_workers="${MAX_WORKERS:-4}"
llm_max_concurrent_requests="${LLM_MAX_CONCURRENT_REQUESTS:-$max_workers}"

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
  echo "[$(date --iso-8601=seconds)] start method=$method model=$model_label output=$output"
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
    "${method_args[@]}" >> "$method_log" 2>&1
  echo "[$(date --iso-8601=seconds)] done method=$method"
done

echo "[$(date --iso-8601=seconds)] all requested runs completed: $result_root"
echo ""
echo "=== [KẾT QUẢ TỔNG HỢP BENCHMARK OTT-QA SHARD 01 (100 CÂU)] ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$result_root"
