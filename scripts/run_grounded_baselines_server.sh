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
  --shards "01 02..."              Specific shard(s) to run (e.g. "01" or "01 02").
  --workers <N>                    Example/request concurrency (default: 4).
  --run-tag <name>                 Result tag prefix (default: grounded-baselines-v1).
  --with-ablations                 Run both main benchmarks and 7-component ablations.
  --ablations-only                 Run only the 7-component ablations (HybridQA 500).
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
selected_shards=()
dry_run=false
with_ablations=false
ablations_only=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset) dataset_selector="$2"; shift 2 ;;
    --model) model_selector="$2"; shift 2 ;;
    --shards) read -r -a selected_shards <<< "$2"; shift 2 ;;
    --workers) workers="$2"; shift 2 ;;
    --run-tag) run_tag_prefix="$2"; shift 2 ;;
    --with-ablations) with_ablations=true; shift ;;
    --ablations-only) ablations_only=true; with_ablations=true; shift ;;
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
    bash "$script" "${selected_shards[@]}"
  )
  printf '\n[%s] %s / GPT-OSS-%s\n' "$(date --iso-8601=seconds)" "$dataset" "$scale"
  if [[ "$dry_run" == true ]]; then
    printf '  '; printf '%q ' "${command[@]}"; printf '\n'
  else
    "${command[@]}"
  fi
}

run_ablation_suite() {
  local scale="$1" model tag out_dir
  case "$scale" in
    20b) model="openai/gpt-oss-20b" ;;
    120b) model="openai/gpt-oss-120b" ;;
  esac
  tag="${run_tag_prefix}-ablations-gpt-oss-${scale}"
  out_dir="data/results/$tag"
  local extra_ablation_args=()
  if (( ${#selected_shards[@]} == 1 )); then
    extra_ablation_args+=(--shard "${selected_shards[0]}")
  fi
  local command=(env
    "LLM_PROVIDER=openrouter"
    "OPENROUTER_MODEL=$model"
    "OPENROUTER_REASONING_ENABLED=${OPENROUTER_REASONING_ENABLED:-true}"
    bash "scripts/run_hybridqa_500_oueg_component_ablations.sh"
    --workers "$workers"
    --output-dir "$out_dir"
    "${extra_ablation_args[@]}"
  )
  printf '\n[%s] hybridqa-ablations / GPT-OSS-%s\n' "$(date --iso-8601=seconds)" "$scale"
  if [[ "$dry_run" == true ]]; then
    printf '  '; printf '%q ' "${command[@]}"; printf '\n'
  else
    "${command[@]}"
  fi
}

if [[ "$ablations_only" == false ]]; then
  for scale in "${models[@]}"; do
    for dataset in "${datasets[@]}"; do
      run_suite "$scale" "$dataset"
    done
  done
fi

if [[ "$with_ablations" == true ]]; then
  for scale in "${models[@]}"; do
    run_ablation_suite "$scale"
  done
fi

echo ""
echo "=========================================================================="
echo "Completed requested grounded-baseline suites."
echo "=========================================================================="

if [[ "$dry_run" == false ]]; then
  if [[ "$ablations_only" == false ]]; then
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
  if [[ "$with_ablations" == true ]]; then
    for scale in "${models[@]}"; do
      ablation_dir="data/results/${run_tag_prefix}-ablations-gpt-oss-${scale}"
      if [[ -d "$ablation_dir" ]]; then
        echo ""
        echo ">>> Summary: [HybridQA Ablations / GPT-OSS-$scale] ($ablation_dir)"
        python3 scripts/fast_benchmark_summary.py "$ablation_dir" || true
      fi
    done
  fi
fi
