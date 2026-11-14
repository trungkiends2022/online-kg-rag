#!/usr/bin/env bash
# Reproducible HybridQA benchmark suite for controlled architecture comparison
# and causal OUEG ablations. Every output receives a run manifest from
# src.run_baselines, so runs with incompatible settings cannot be resumed.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage: bash scripts/run_hybridqa_oueg_benchmark_suite.sh [options]

Run a controlled HybridQA comparison and/or in-family OUEG ablations. All
methods use the same input IDs, top-k=5, second-stage-k=3, 24k-char context
cap, temperature 0, output budget 1024, and model inherited from .env.

Options:
  -s, --shard <01..08>      Input shard (default: 02).
  -l, --limit <N>           Limit each method to the first N examples.
  -w, --workers <N>         Parallel examples / LLM requests (default: 2).
  --track <name>            controlled, ablation, or all (default: all).
  --include-odyssey         Add ODYSSEY as an external-cost comparator.
  --path-focused            Use the focused path reader view for OUEG.
                            Default retains the complete compact OUEG in L1.
  --output-dir <path>       Parent directory for JSONL outputs and logs.
  --resume                  Resume compatible incomplete JSONLs.
  -h, --help                Show this help.

Controlled methods:
  direct_llm, flat_rag_shared_context, graph_retrieval_no_path,
  path_text_top_n (strict path-only), oueg_l1_only, oueg_full.

The optional ODYSSEY run is intentionally marked external-cost: it has a
different multi-call control flow, so it must not be reported as call-budget
matched with the controlled rows.

Examples:
  # Smoke-test all rows of the suite on 30 cases.
  OPENROUTER_API_KEY=... bash scripts/run_hybridqa_oueg_benchmark_suite.sh \
    --shard 02 --limit 30 --output-dir data/results/hybridqa_suite_smoke

  # Full controlled table, then OUEG ablations, on one 200-case shard.
  bash scripts/run_hybridqa_oueg_benchmark_suite.sh --shard 02 \
    --output-dir data/results/hybridqa_suite_shard02 --resume
EOF
}

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
    if "$resolved" -c 'import src.run_baselines' >/dev/null 2>&1; then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  echo "No usable Python interpreter found. Set PYTHON_BIN to the project environment." >&2
  return 1
}

resolve_model_label() {
  "$python_bin" -c '
import re
from src.llm.client import get_provider
provider = get_provider()
name = getattr(provider, "name", "unknown-provider")
model = getattr(provider, "model", None) or "unknown-model"
print(re.sub(r"[^A-Za-z0-9._-]+", "-", f"{name}__{model}").strip("-") or "unknown")
'
}

shard="02"
limit=""
workers=2
track="all"
include_odyssey=false
path_focused=false
output_dir=""
resume=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--shard) shard="$2"; shift 2 ;;
    -l|--limit) limit="$2"; shift 2 ;;
    -w|--workers) workers="$2"; shift 2 ;;
    --track) track="$2"; shift 2 ;;
    --include-odyssey) include_odyssey=true; shift ;;
    --path-focused) path_focused=true; shift ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    --resume) resume=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$shard" =~ ^[0-9]+$ ]]; then printf -v shard "%02d" "$((10#$shard))"; fi
[[ "$shard" =~ ^0[1-8]$ ]] || { echo "--shard must be 01..08" >&2; exit 2; }
[[ "$workers" =~ ^[1-9][0-9]*$ ]] || { echo "--workers must be positive" >&2; exit 2; }
[[ -z "$limit" || "$limit" =~ ^[1-9][0-9]*$ ]] || { echo "--limit must be positive" >&2; exit 2; }
[[ "$track" == controlled || "$track" == ablation || "$track" == all ]] || { echo "--track must be controlled, ablation, or all" >&2; exit 2; }

python_bin="$(resolve_python)"
: "${LLM_PROVIDER:=openrouter}"
: "${OPENROUTER_MODEL:=openai/gpt-oss-120b}"
: "${OPENROUTER_REASONING_ENABLED:=true}"
export LLM_PROVIDER OPENROUTER_MODEL OPENROUTER_REASONING_ENABLED
model_label="$(resolve_model_label)"

input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"
[[ -f "$input" ]] || { echo "Missing input shard: $input" >&2; exit 1; }
output_dir="${output_dir:-$repo_root/data/results/hybridqa_oueg_benchmark_suite_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$output_dir/logs"

common_args=(
  --dataset hybridqa --input "$input"
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5 --second-stage-k 3
  --max-context-chars 24000 --max-output-tokens 1024 --temperature 0
  --n-paths 5
  --focus-passage-budget-per-candidate 2 --focus-query-fallback-budget 2
  --l2-existing-witness-budget 2 --l2-max-edges-per-candidate 16
  --l2-max-contexts-per-candidate 3 --l2-context-snippet-chars 900
  --l2-evidence-mode delta_only
  --max-workers "$workers" --llm-max-concurrent-requests "$workers"
  --llm-timeout-seconds 120 --llm-sdk-retries 2 --quiet-records
)
[[ -n "$limit" ]] && common_args+=(--limit "$limit")
[[ "$resume" == true ]] && common_args+=(--resume)

run_method() {
  local section="$1" label="$2" method="$3"
  shift 3
  local output="$output_dir/$section/hybridqa__shard${shard}__${model_label}__${label}.jsonl"
  local log="$output_dir/logs/hybridqa__shard${shard}__${model_label}__${label}.log"
  mkdir -p "$(dirname "$output")"
  echo "[$(date --iso-8601=seconds)] start section=$section label=$label method=$method"
  PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
    --method "$method" --output "$output" "${common_args[@]}" "$@" 2>&1 | tee "$log"
  echo "[$(date --iso-8601=seconds)] done label=$label"
}

# The full implementation retains a complete compact L1 graph by default,
# matching the focus-augmentation runner. Path-focused mode is opt-in for
# studying prompt-order/path-salience effects.
oueg_view_args=()
[[ "$path_focused" == true ]] && oueg_view_args+=(--path-focused-prompt)

echo "Output folder: $output_dir"
echo "Model: ${LLM_PROVIDER}/${OPENROUTER_MODEL}; shard=$shard; track=$track; workers=$workers"

if [[ "$track" == controlled || "$track" == all ]]; then
  run_method controlled direct_llm direct_llm
  run_method controlled flat_rag_shared_context flat_rag_shared_context
  run_method controlled graph_retrieval_no_path graph_retrieval_no_path
  run_method controlled strict_path_text_top_n path_text_top_n --strict-path-text-top-n
  run_method controlled oueg_l1_only online_unified_evidence_graph "${oueg_view_args[@]}" --no-adaptive-verification
  run_method controlled oueg_full online_unified_evidence_graph "${oueg_view_args[@]}"
  if [[ "$include_odyssey" == true ]]; then
    run_method external_cost odyssey odyssey --odyssey-max-hops 3 --odyssey-semantic-threshold 0.8
  fi
fi

if [[ "$track" == ablation || "$track" == all ]]; then
  run_method ablation no_l2_new_evidence online_unified_evidence_graph "${oueg_view_args[@]}" --no-focus-evidence-augmentation
  run_method ablation no_diagnostic_focus_resolution online_unified_evidence_graph "${oueg_view_args[@]}" --no-diagnostic-focus-resolution
  run_method ablation no_path_guidance online_unified_evidence_graph "${oueg_view_args[@]}" --no-path-guidance
  run_method ablation no_hyperlink_expansion online_unified_evidence_graph "${oueg_view_args[@]}" --no-hyperlink-expansion
fi

echo "Completed. Each JSONL has a manifest and a sibling summary JSON. Results: $output_dir"
