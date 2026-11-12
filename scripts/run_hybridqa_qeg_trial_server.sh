#!/usr/bin/env bash
# Compare QEG with full OUEG and the stronger no-path L1 control on HybridQA.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f "$repo_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env"
  set +a
fi

usage() {
  cat <<'EOF'
Usage: bash scripts/run_hybridqa_qeg_trial_server.sh [options]

Runs QEG, the no-path OUEG control, and optionally the original full OUEG on
identical HybridQA shards. QEG answers are accepted only with visible KG-edge
evidence paths. The script writes a grounding report and paired McNemar EM test.

  --base-url URL       OpenAI-compatible local server (default: localhost:8000/v1)
  --model NAME         Model deployed on the server (default: openai/gpt-oss-20b)
  --api-key KEY        Server API key (default: EMPTY)
  --workers N          Concurrent samples (default: 4)
  --shards "06 07 08"  Evaluation shards (default: all 500 examples)
  --limit N            Cap each shard for a smoke trial
  --methods "qeg_soft_contract qeg no_path full"
                       Configurations to run (default: "qeg no_path")
  --output-dir PATH    Output directory
  --no-resume          Do not resume existing JSONL files
  -h, --help           Show this help
EOF
}

base_url="${SERVER_BASE_URL:-${COMPAT_BASE_URL:-http://localhost:8000/v1}}"
model="${COMPAT_MODEL:-openai/gpt-oss-20b}"
api_key="${COMPAT_API_KEY:-EMPTY}"
workers="${MAX_WORKERS:-4}"
shards=(06 07 08)
methods=(qeg_soft_contract no_path)
limit=""
output_dir=""
resume=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url) base_url="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --api-key) api_key="$2"; shift 2 ;;
    --workers) workers="$2"; shift 2 ;;
    --shards) read -r -a shards <<< "$2"; shift 2 ;;
    --methods) read -r -a methods <<< "$2"; shift 2 ;;
    --limit) limit="$2"; shift 2 ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    --no-resume) resume=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
else
  python_bin="$(command -v python3)"
fi

run_tag="qeg-hybridqa-$(date -u +%Y%m%dT%H%M%SZ)"
output_dir="${output_dir:-$repo_root/data/results/$run_tag}"
mkdir -p "$output_dir"

common_args=(
  --dataset hybridqa
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5
  --max-context-chars 24000
  --max-table-rows-for-kg 999999
  --max-output-tokens 2048
  --temperature 0
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
[[ -n "$limit" ]] && common_args+=(--limit "$limit")
[[ "$resume" == true ]] && common_args+=(--resume)

qeg_files=()
baseline_files=()
for method in "${methods[@]}"; do
  case "$method" in
    qeg) cli_method=qeg; extra_args=() ;;
    qeg_soft_contract) cli_method=qeg_soft_contract; extra_args=() ;;
    no_path) cli_method=online_unified_evidence_graph; extra_args=(--no-path-guidance) ;;
    full) cli_method=online_unified_evidence_graph; extra_args=() ;;
    *) echo "Unknown QEG trial method: $method" >&2; exit 2 ;;
  esac
  for shard in "${shards[@]}"; do
    printf -v shard_fmt "%02d" "$((10#$shard))"
    input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard_fmt}.json"
    [[ -f "$input" ]] || { echo "Missing input: $input" >&2; exit 1; }
    output="$output_dir/${method}__hybridqa_shard${shard_fmt}.jsonl"
    echo "Running $method on shard $shard_fmt -> $output"
    env \
      LLM_PROVIDER=openai_compatible \
      COMPAT_BASE_URL="$base_url" \
      COMPAT_MODEL="$model" \
      COMPAT_API_KEY="$api_key" \
      COMPAT_REASONING_ENABLED="${COMPAT_REASONING_ENABLED:-true}" \
      MAX_WORKERS="$workers" \
      LLM_MAX_CONCURRENT_REQUESTS="$workers" \
      "$python_bin" -m src.run_baselines \
        --input "$input" --output "$output" --method "$cli_method" \
        "${common_args[@]}" "${extra_args[@]}"
    [[ "$method" == qeg || "$method" == qeg_soft_contract ]] && qeg_files+=("$output")
    [[ "$method" == no_path ]] && baseline_files+=("$output")
  done
done

if ((${#qeg_files[@]})); then
  report_args=(--input "${qeg_files[@]}" --output "$output_dir/qeg_grounding_report.json" --markdown "$output_dir/qeg_grounding_report.md")
  if ((${#baseline_files[@]})); then
    report_args+=(--baseline "${baseline_files[@]}")
  fi
  "$python_bin" scripts/qeg_grounding_report.py "${report_args[@]}"
fi

echo "QEG trial complete: $output_dir"
