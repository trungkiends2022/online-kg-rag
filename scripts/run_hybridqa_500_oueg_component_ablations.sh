#!/usr/bin/env bash
# Run causal OUEG component ablations over a selected HybridQA shard. By default
# it uses shards 06, 07, and 08 (200 + 200 + 100 = 500 records per ablation).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Auto-load .env configuration if present (without overwriting existing env vars)
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

usage() {
  cat <<'EOF'
Usage: scripts/run_hybridqa_500_oueg_component_ablations.sh [options]

Run the OUEG full control plus six causal ablations on HybridQA. By default this
runs shards 06, 07, and 08 (500 records per configuration); use --shard for a
single shard. Provider,
model, API key, base URL, and timeout are inherited from .env exactly as in the
OUEG/Direct runner.

Options:
  -s, --shard <01..08>      Run one shard instead of the default 06, 07, and 08.
  -w, --workers <N>         Parallel examples and concurrent LLM requests (default: 4).
  --output-dir <path>       Parent folder for results and logs.
  --tag <string>            Default output-folder tag if --output-dir is omitted.
  --no-resume               Do not pass --resume; use only with a new output folder.
  -h, --help                Show this help.

Configurations and their causal role:
  full                             complete OUEG control
  no_record_nodes                  tests row-binding record centroids
  no_path_guidance                 tests non-filtering traversal guidance
  l1_only                          tests the value of adaptive L2 verification
  no_l2_new_evidence               tests targeted new evidence versus re-reading
  no_diagnostic_focus_resolution   tests grounding diagnostics to exact row values
  no_prompt_compression            tests lossless compact serialization; report coverage/tokens too

Each log name contains: benchmark, shard, provider/model, method, and ablation.

Example:
  bash scripts/run_hybridqa_500_oueg_component_ablations.sh \
    --workers 64 \
    --output-dir data/results/hybridqa_500_oueg_component_ablations

  # Run the full control and ablations on shard 03 only.
  bash scripts/run_hybridqa_500_oueg_component_ablations.sh \
    --shard 03 --workers 64 \
    --output-dir data/results/hybridqa_shard03_oueg_component_ablations
EOF
}

workers=4
single_shard=""
run_tag="oueg_component_ablations_500_$(date -u +%Y%m%dT%H%M%SZ)"
output_dir=""
resume=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--shard) single_shard="$2"; shift 2 ;;
    -w|--workers) workers="$2"; shift 2 ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    --tag) run_tag="$2"; shift 2 ;;
    --no-resume) resume=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if ! [[ "$workers" =~ ^[1-9][0-9]*$ ]]; then
  echo "--workers must be a positive integer; received: $workers" >&2
  exit 2
fi
if [[ -n "$single_shard" ]]; then
  if [[ "$single_shard" =~ ^[0-9]+$ ]]; then
    printf -v single_shard "%02d" "$((10#$single_shard))"
  fi
  if [[ ! "$single_shard" =~ ^0[1-8]$ ]]; then
    echo "--shard must be between 01 and 08; received: $single_shard" >&2
    exit 2
  fi
fi

python_bin="$(resolve_python)"
model_label="$(resolve_model_label)"
output_dir="${output_dir:-$repo_root/data/results/$run_tag}"
log_dir="$output_dir/logs"
mkdir -p "$output_dir" "$log_dir"

if [[ -n "$single_shard" ]]; then
  shards=("$single_shard")
else
  shards=(06 07 08)
fi
common_args=(
  --dataset hybridqa
  --method online_unified_evidence_graph
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5
  --max-context-chars 24000
  --max-table-rows-for-kg 999999
  --no-path-focused-prompt
  --max-output-tokens 2048
  --temperature 0
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
  --max-workers "$workers"
  --llm-max-concurrent-requests "$workers"
  --quiet-records
)
[[ "$resume" == true ]] && common_args+=(--resume)

run_ablation() {
  local ablation="$1"
  shift
  local extra_args=("$@")
  local shard shard_label input ablation_dir output log

  ablation_dir="$output_dir/$ablation"
  mkdir -p "$ablation_dir"

  for shard in "${shards[@]}"; do
    shard_label="shard${shard}-of08"
    input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"
    [[ -f "$input" ]] || { echo "Missing input shard: $input" >&2; return 1; }

    output="$ablation_dir/hybridqa__${shard_label}__${model_label}__online_unified_evidence_graph__${ablation}.jsonl"
    log="$log_dir/hybridqa__${shard_label}__${model_label}__online_unified_evidence_graph__${ablation}.log"

    echo "[$(date --iso-8601=seconds)] start ablation=$ablation shard=$shard model=$model_label"
    PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
      --input "$input" \
      --output "$output" \
      "${common_args[@]}" \
      "${extra_args[@]}" 2>&1 | tee "$log"
    echo "[$(date --iso-8601=seconds)] done ablation=$ablation shard=$shard"
  done
}

echo "Output folder: $output_dir"
echo "Model from .env: $model_label"
echo "Shards: ${shards[*]} (500 records per ablation)"
echo "Workers: $workers"

run_ablation full
run_ablation no_record_nodes --no-record-nodes
run_ablation no_path_guidance --no-path-guidance
run_ablation l1_only --no-adaptive-verification
run_ablation no_l2_new_evidence --no-focus-evidence-augmentation
run_ablation no_diagnostic_focus_resolution --no-diagnostic-focus-resolution
run_ablation no_prompt_compression --no-prompt-compression

echo "Completed. Results: $output_dir"
echo "Logs: $log_dir"

echo ""
echo "=== [KẾT QUẢ TỔNG HỢP ABLATION] ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$output_dir"
