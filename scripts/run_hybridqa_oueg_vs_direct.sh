#!/usr/bin/env bash
# Run exactly one HybridQA shard with OUEG and Direct LLM into one review folder.
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
Usage: scripts/run_hybridqa_oueg_vs_direct.sh [options]

Run one HybridQA shard with online_unified_evidence_graph (OUEG) and direct_llm.
All raw outputs, summaries, logs, and joined review reports are put in one folder.

Options:
  -s, --shard <01..08>      Shard to run (default: 02).
  -l, --limit <N>           Evaluate only the first N examples of the shard.
  -w, --workers <N>         Parallel examples / max concurrent LLM requests (default: 4).
  --max-output-tokens <N>   Max generated tokens per answer (default: 1024).
  --output-dir <path>       One folder for this comparison run.
  --tag <string>            Default output folder tag if --output-dir is omitted.
  --no-resume               Do not pass --resume to the benchmark runner.
  -h, --help                Show this help.

Examples:
  bash scripts/run_hybridqa_oueg_vs_direct.sh --shard 02 --limit 100
  bash scripts/run_hybridqa_oueg_vs_direct.sh --shard 01 --output-dir data/results/review_shard01
EOF
}

shard="02"
limit=""
workers=4
max_output_tokens=1024
run_tag="oueg_vs_direct_$(date -u +%Y%m%dT%H%M%SZ)"
output_dir=""
resume=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--shard) shard="$2"; shift 2 ;;
    -l|--limit) limit="$2"; shift 2 ;;
    -w|--workers) workers="$2"; shift 2 ;;
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
if ! [[ "$workers" =~ ^[1-9][0-9]*$ ]]; then
  echo "--workers must be a positive integer; received: $workers" >&2
  exit 2
fi
if [[ -n "$limit" ]] && ! [[ "$limit" =~ ^[1-9][0-9]*$ ]]; then
  echo "--limit must be a positive integer; received: $limit" >&2
  exit 2
fi
if ! [[ "$max_output_tokens" =~ ^[1-9][0-9]*$ ]]; then
  echo "--max-output-tokens must be a positive integer; received: $max_output_tokens" >&2
  exit 2
fi

python_bin="$(resolve_python)"
input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json"
[[ -f "$input" ]] || { echo "Missing input shard: $input" >&2; exit 1; }

output_dir="${output_dir:-$repo_root/data/results/hybridqa-1500-seed2027/$run_tag}"
mkdir -p "$output_dir"

prefix="$output_dir/hybridqa_shard${shard}"
oueg_output="${prefix}_OUEG.jsonl"
direct_output="${prefix}_directLLM.jsonl"
markdown_report="${prefix}_comparison.md"
csv_report="${prefix}_comparison.csv"

common_args=(
  --dataset hybridqa
  --input "$input"
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5
  --second-stage-k 3
  --n-paths 5
  --max-replans 0
  --max-context-chars 24000
  --max-output-tokens "$max_output_tokens"
  --temperature 0
  --max-workers "$workers"
  --llm-max-concurrent-requests "$workers"
  --llm-timeout-seconds 120
  --llm-sdk-retries 2
  --quiet-records
)
[[ -n "$limit" ]] && common_args+=(--limit "$limit")
[[ "$resume" == true ]] && common_args+=(--resume)

echo "Output folder: $output_dir"
echo "[1/3] OUEG -> $(basename "$oueg_output")"
PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
  --method online_unified_evidence_graph \
  --output "$oueg_output" \
  "${common_args[@]}" 2>&1 | tee "${prefix}_OUEG.log"

echo "[2/3] Direct LLM -> $(basename "$direct_output")"
PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
  --method direct_llm \
  --output "$direct_output" \
  "${common_args[@]}" 2>&1 | tee "${prefix}_directLLM.log"

echo "[3/3] Joining results and deriving ambiguity from OUEG"
"$python_bin" scripts/compare_oueg_direct.py \
  --oueg "$oueg_output" \
  --direct "$direct_output" \
  --markdown "$markdown_report" \
  --csv "$csv_report"

echo "Done. Review: $csv_report"
