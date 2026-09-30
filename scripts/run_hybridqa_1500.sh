#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

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
    if [[ -n "${PYTHON_BIN:-}" ]]; then
      echo "PYTHON_BIN cannot import src.run_baselines: $resolved" >&2
      return 1
    fi
    echo "Skipping unusable Python interpreter: $resolved" >&2
  done

  echo "No usable Python interpreter found. Set PYTHON_BIN to an environment with project dependencies." >&2
  return 1
}

resolve_model_label() {
  # Use the same factory as the benchmark to make the filename describe the
  # effective provider/model, without ever exposing credentials. Restrict the
  # label to portable filename characters because model IDs often contain `/`.
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
run_tag="${RUN_TAG:-run_$(date -u +%Y%m%dT%H%M%SZ)}"
input_prefix="${INPUT_PREFIX:-$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027}"
result_root="${RESULT_ROOT:-$repo_root/data/results/hybridqa-1500-seed2027/$run_tag}"
log_root="${LOG_ROOT:-$repo_root/data/logs/hybridqa-1500-seed2027/$run_tag}"

# Oracle evidence is a retrieval upper bound and numerical_ir targets arithmetic
# datasets, so the controlled HybridQA comparison uses these six methods.
default_methods=(
  graph_retrieval_no_path
  direct_llm
  flat_table_bm25
  online_kg_path_text
  path_consistency
  online_kg
)
if [[ -n "${METHODS:-}" ]]; then
  read -r -a methods <<< "$METHODS"
else
  methods=("${default_methods[@]}")
fi

if (( $# > 0 )); then
  shards=("$@")
else
  shards=(01 02 03 04 05 06 07 08)
fi

mkdir -p "$result_root" "$log_root"
exec 9>"$result_root/.runner.lock"
if ! flock -n 9; then
  echo "Another HybridQA runner already owns $result_root/.runner.lock" >&2
  exit 1
fi

echo "[$(date --iso-8601=seconds)] run_tag=$run_tag methods=${methods[*]} shards=${shards[*]}"
echo "model_label=$model_label"
echo "git_head=$(git rev-parse HEAD)"

for shard in "${shards[@]}"; do
  input="${input_prefix}-shard${shard}.json"
  if [[ ! -f "$input" ]]; then
    echo "Missing input shard: $input" >&2
    exit 1
  fi
  shard_label="shard${shard}-of08"
  for method in "${methods[@]}"; do
    method_dir="$result_root/$method"
    mkdir -p "$method_dir"
    output="$method_dir/${shard_label}__${model_label}__${method}.jsonl"
    method_log="$log_root/${shard_label}__${model_label}__${method}.log"
    echo "[$(date --iso-8601=seconds)] start method=$method shard=$shard model=$model_label output=$output"
    PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
      --dataset hybridqa \
      --method "$method" \
      --input "$input" \
      --tables-dir data/WikiTables-WithLinks/tables_tok \
      --passages-dir data/WikiTables-WithLinks/request_tok \
      --output "$output" \
      --top-k 5 \
      --second-stage-k 3 \
      --n-paths 5 \
      --max-replans 0 \
      --max-context-chars 24000 \
      --max-output-tokens 128 \
      --temperature 0 \
      --llm-timeout-seconds 120 \
      --llm-sdk-retries 2 \
      --fail-fast \
      --resume >> "$method_log" 2>&1
    echo "[$(date --iso-8601=seconds)] done method=$method shard=$shard"
  done
done

echo "[$(date --iso-8601=seconds)] all requested runs completed"
