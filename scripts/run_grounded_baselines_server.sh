#!/usr/bin/env bash
# Launch the finalized zero-shot grounded QA comparison on a server.
# It runs methods sequentially to respect provider rate limits and writes a
# separate manifest-backed result tree for every dataset/model combination.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage: bash scripts/run_grounded_baselines_server.sh [options]

Run the five finalized baselines, sequentially:
  online_unified_evidence_graph direct_llm odyssey
  graph_retrieval_no_path path_text_top_n

Options:
  --dataset <hybridqa|ottqa|both>  Dataset suite to run (default: both).
  --model <20b|120b|both>          GPT-OSS model scale (default: both).
  --workers <N>                    Example/request concurrency (default: 4).
  --run-tag <name>                 Result tag prefix (default: grounded-baselines-v1).
  --dry-run                        Print exact launches without calling a model.
  -h, --help                       Show this help.

Requirements: source .env (or otherwise export OPENROUTER_API_KEY) before
launching. Existing result files may resume only when their manifest matches.
EOF
}

dataset_selector="both"
model_selector="both"
workers="${MAX_WORKERS:-4}"
run_tag_prefix="${RUN_TAG_PREFIX:-grounded-baselines-v1}"
dry_run=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset) dataset_selector="$2"; shift 2 ;;
    --model) model_selector="$2"; shift 2 ;;
    --workers) workers="$2"; shift 2 ;;
    --run-tag) run_tag_prefix="$2"; shift 2 ;;
    --dry-run) dry_run=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$dataset_selector" in hybridqa|ottqa|both) ;; *) echo "--dataset must be hybridqa, ottqa, or both" >&2; exit 2 ;; esac
case "$model_selector" in 20b|120b|both) ;; *) echo "--model must be 20b, 120b, or both" >&2; exit 2 ;; esac
[[ "$workers" =~ ^[1-9][0-9]*$ ]] || { echo "--workers must be a positive integer" >&2; exit 2; }

if [[ "$dry_run" == false && -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is not set. Run: set -a; source .env; set +a" >&2
  exit 2
fi

methods="online_unified_evidence_graph direct_llm odyssey graph_retrieval_no_path path_text_top_n"
if [[ "$model_selector" == "both" ]]; then models=(20b 120b); else models=("$model_selector"); fi
if [[ "$dataset_selector" == "both" ]]; then datasets=(hybridqa ottqa); else datasets=("$dataset_selector"); fi

run_suite() {
  local scale="$1" dataset="$2" model script tag
  case "$scale" in
    20b) model="openai/gpt-oss-20b" ;;
    120b) model="openai/gpt-oss-120b" ;;
  esac
  case "$dataset" in
    hybridqa) script="scripts/run_hybridqa_1500.sh" ;;
    ottqa) script="scripts/run_ottqa_500.sh" ;;
  esac
  tag="${run_tag_prefix}-gpt-oss-${scale}"
  local command=(env
    "LLM_PROVIDER=openrouter"
    "OPENROUTER_MODEL=$model"
    "OPENROUTER_REASONING_ENABLED=${OPENROUTER_REASONING_ENABLED:-true}"
    "MAX_WORKERS=$workers"
    "LLM_MAX_CONCURRENT_REQUESTS=$workers"
    "METHODS=$methods"
    "RUN_TAG=$tag"
    bash "$script"
  )
  printf '\n[%s] %s / GPT-OSS-%s\n' "$(date --iso-8601=seconds)" "$dataset" "$scale"
  if [[ "$dry_run" == true ]]; then
    printf '  '; printf '%q ' "${command[@]}"; printf '\n'
  else
    "${command[@]}"
  fi
}

for scale in "${models[@]}"; do
  for dataset in "${datasets[@]}"; do
    run_suite "$scale" "$dataset"
  done
done

echo ""
echo "=========================================================================="
echo "Completed requested grounded-baseline suites."
echo "=========================================================================="

if [[ "$dry_run" == false ]]; then
  for scale in "${models[@]}"; do
    for dataset in "${datasets[@]}"; do
      tag="${run_tag_prefix}-gpt-oss-${scale}"
      case "$dataset" in
        hybridqa) res_dir="data/results/hybridqa-1500-seed2027/$tag" ;;
        ottqa) res_dir="data/results/ottqa-500-seed2027/$tag" ;;
      esac
      if [[ -d "$res_dir" ]]; then
        echo ""
        echo ">>> Summary: [$dataset / GPT-OSS-$scale] ($res_dir)"
        python3 scripts/fast_benchmark_summary.py "$res_dir" || true
      fi
    done
  done
fi
