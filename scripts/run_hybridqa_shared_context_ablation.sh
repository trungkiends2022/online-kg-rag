#!/usr/bin/env bash
# Run the two shared-context ablations sequentially on GPT-OSS through OpenRouter.
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
  done
  echo "No usable Python interpreter found. Set PYTHON_BIN to an environment with project dependencies." >&2
  return 1
}

usage() {
  cat <<'EOF'
Usage: scripts/run_hybridqa_shared_context_ablation.sh [options]

Run Flat-RAG shared context and/or Path-Text top-N sequentially on one HybridQA shard.
The script selects OpenRouter GPT-OSS and writes self-describing JSONL, manifest,
summary, and log filenames. Credentials remain in .env; this script never prints them.

Options:
  -s, --shard <01..08>             Shard to run (default: 01).
  -m, --model <20b|120b|all|id>    GPT-OSS model(s), default: all.
  -b, --baseline <flat|path|both>  Baseline(s), default: both.
  -l, --limit <N>                  Run only the first N examples per baseline.
  -w, --workers <N>                Parallel examples and concurrent LLM calls (default: 4).
  -n, --n-paths <N>                Top-N paths for Path-Text (default: 5).
  --top-k <N>                      First-stage passage retrieval size (default: 5).
  --second-stage-k <N>             Deterministic retrieval expansion size (default: 3).
  --max-context-chars <N>          Prompt evidence budget (default: 24000).
  --max-output-tokens <N>          Completion budget (default: 1024).
  --output-dir <path>              Parent folder for outputs and logs.
  --tag <string>                   Default output folder tag if --output-dir is omitted.
  --no-resume                      Start new output files rather than resuming.
  -h, --help                       Show this help.

Model aliases:
  20b  -> openai/gpt-oss-20b
  120b -> openai/gpt-oss-120b
  all  -> run 20b, then 120b

Examples:
  # Full shard 01: Flat-RAG then Path-Text top-5, for both GPT-OSS models.
  bash scripts/run_hybridqa_shared_context_ablation.sh --shard 01

  # Smoke test top-3 Path-Text with GPT-OSS 120B and two concurrent requests.
  bash scripts/run_hybridqa_shared_context_ablation.sh \
    --shard 03 --model 120b --baseline path --n-paths 3 --limit 10 --workers 2

  # Flat-RAG only, with an explicit output folder.
  bash scripts/run_hybridqa_shared_context_ablation.sh \
    --model 20b --baseline flat --workers 4 --output-dir data/results/gpt_oss20b_flat_shard01
EOF
}

shard="01"
model_choice="all"
baseline_choice="both"
limit=""
workers=4
n_paths=5
top_k=5
second_stage_k=3
max_context_chars=24000
max_output_tokens=1024
run_tag="shared_context_ablation_$(date -u +%Y%m%dT%H%M%SZ)"
output_dir=""
resume=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--shard) shard="$2"; shift 2 ;;
    -m|--model) model_choice="$2"; shift 2 ;;
    -b|--baseline) baseline_choice="$2"; shift 2 ;;
    -l|--limit) limit="$2"; shift 2 ;;
    -w|--workers) workers="$2"; shift 2 ;;
    -n|--n-paths) n_paths="$2"; shift 2 ;;
    --top-k) top_k="$2"; shift 2 ;;
    --second-stage-k) second_stage_k="$2"; shift 2 ;;
    --max-context-chars) max_context_chars="$2"; shift 2 ;;
    --max-output-tokens) max_output_tokens="$2"; shift 2 ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    --tag) run_tag="$2"; shift 2 ;;
    --no-resume) resume=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$shard" =~ ^[0-9]+$ ]]; then
  printf -v shard "%02d" "$((10#$shard))"
fi
if [[ ! "$shard" =~ ^0[1-8]$ ]]; then
  echo "--shard must be between 01 and 08; received: $shard" >&2
  exit 2
fi
for value_name in workers n_paths top_k max_context_chars max_output_tokens; do
  value="${!value_name}"
  if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "--${value_name//_/-} must be a positive integer; received: $value" >&2
    exit 2
  fi
done
if ! [[ "$second_stage_k" =~ ^[0-9]+$ ]]; then
  echo "--second-stage-k must be a non-negative integer; received: $second_stage_k" >&2
  exit 2
fi
if [[ -n "$limit" ]] && ! [[ "$limit" =~ ^[1-9][0-9]*$ ]]; then
  echo "--limit must be a positive integer; received: $limit" >&2
  exit 2
fi
if [[ "$baseline_choice" != "flat" && "$baseline_choice" != "path" && "$baseline_choice" != "both" ]]; then
  echo "--baseline must be flat, path, or both; received: $baseline_choice" >&2
  exit 2
fi

case "$model_choice" in
  20b) models=("openai/gpt-oss-20b") ;;
  120b) models=("openai/gpt-oss-120b") ;;
  all) models=("openai/gpt-oss-20b" "openai/gpt-oss-120b") ;;
  */*) models=("$model_choice") ;;
  *)
    echo "--model must be 20b, 120b, all, or an OpenRouter model ID; received: $model_choice" >&2
    exit 2
    ;;
esac

case "$baseline_choice" in
  flat) methods=("flat_rag_shared_context") ;;
  path) methods=("path_text_top_n") ;;
  both) methods=("flat_rag_shared_context" "path_text_top_n") ;;
esac

python_bin="$(resolve_python)"
input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"
[[ -f "$input" ]] || { echo "Missing input shard: $input" >&2; exit 1; }

output_dir="${output_dir:-$repo_root/data/results/hybridqa-1500-seed2027/$run_tag}"
log_dir="$output_dir/logs"
mkdir -p "$output_dir" "$log_dir"

echo "Output folder: $output_dir"
echo "Shard: shard${shard}-of08"
echo "Models: ${models[*]}"
echo "Baselines: ${methods[*]}"
echo "Workers: $workers | top-k: $top_k | second-stage-k: $second_stage_k | path top-N: $n_paths"

for model in "${models[@]}"; do
  model_label="openrouter__${model//\//-}"
  shard_label="shard${shard}-of08"
  for method in "${methods[@]}"; do
    method_dir="$output_dir/$method"
    mkdir -p "$method_dir"
    prefix="$method_dir/${shard_label}__${model_label}__${method}"
    output="${prefix}.jsonl"
    log="${log_dir}/${shard_label}__${model_label}__${method}.log"
    common_args=(
      --dataset hybridqa
      --method "$method"
      --input "$input"
      --tables-dir data/WikiTables-WithLinks/tables_tok
      --passages-dir data/WikiTables-WithLinks/request_tok
      --output "$output"
      --top-k "$top_k"
      --second-stage-k "$second_stage_k"
      --n-paths "$n_paths"
      --max-replans 0
      --max-context-chars "$max_context_chars"
      --max-output-tokens "$max_output_tokens"
      --temperature 0
      --max-workers "$workers"
      --llm-max-concurrent-requests "$workers"
      --llm-timeout-seconds 120
      --llm-sdk-retries 2
      --quiet-records
      --no-progress
    )
    [[ -n "$limit" ]] && common_args+=(--limit "$limit")
    [[ "$resume" == true ]] && common_args+=(--resume)

    echo "[$(date --iso-8601=seconds)] start $method with $model"
    env \
      LLM_PROVIDER=openrouter \
      OPENROUTER_MODEL="$model" \
      OPENROUTER_REASONING_ENABLED=true \
      PYTHONUNBUFFERED=1 \
      "$python_bin" -m src.run_baselines "${common_args[@]}" 2>&1 | tee "$log"
    echo "[$(date --iso-8601=seconds)] done: $output"
  done
done

echo "Completed. Logs: $log_dir"
