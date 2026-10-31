#!/usr/bin/env bash
# Benchmark the full-OUEG L1 + diagnostic-triggered L2 augmentation branch.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage: bash scripts/run_hybridqa_oueg_focus_augmentation.sh [options]

Runs OUEG with a complete compact graph in L1.  L2 is called only after a
non-answer diagnostic; candidate-linked text augmentation is enabled for
missing_link / insufficient_evidence and is balanced per focus candidate.

Required environment:
  OPENROUTER_API_KEY

Optional environment (defaults shown):
  PYTHON_BIN=.venv/bin/python (falls back to python3)
  LLM_PROVIDER=openrouter
  OPENROUTER_MODEL=openai/gpt-oss-120b
  OPENROUTER_REASONING_ENABLED=true

Options:
  -s, --shard <01..08>      HybridQA 1,500-case shard (default: 02)
  -l, --limit <N>           Process the first N uncompleted examples
  -w, --workers <N>         Parallel examples / concurrent LLM calls (default: 2)
  --output <path>           JSONL output path
  --resume                  Resume from an existing output JSONL
  --no-collision-expansion  Disable the existing pre-L1 collision expansion
  --l2-complete-re-read     Diagnostic ablation: send complete OUEG to L2
  -h, --help                Show this help

Example:
  OPENROUTER_API_KEY=... bash scripts/run_hybridqa_oueg_focus_augmentation.sh \
    --shard 02 --limit 100
EOF
}

shard="02"
limit=""
workers=2
output=""
input_override=""
path_focused=false
resume=false
collision_expansion=true
l2_evidence_mode="delta_only"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--shard) shard="$2"; shift 2 ;;
    -l|--limit) limit="$2"; shift 2 ;;
    -w|--workers) workers="$2"; shift 2 ;;
    -i|--input) input_override="$2"; shift 2 ;;
    --output) output="$2"; shift 2 ;;
    --compressed|--path-focused) path_focused=true; shift ;;
    --resume) resume=true; shift ;;
    --no-collision-expansion) collision_expansion=false; shift ;;
    --l2-complete-re-read) l2_evidence_mode="complete_re_read"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ "$shard" =~ ^[0-9]+$ ]]; then
  printf -v shard "%02d" "$((10#$shard))"
fi
[[ "$shard" =~ ^0[1-8]$ ]] || { echo "--shard must be 01..08" >&2; exit 2; }
[[ "$workers" =~ ^[1-9][0-9]*$ ]] || { echo "--workers must be positive" >&2; exit 2; }
[[ -z "$limit" || "$limit" =~ ^[1-9][0-9]*$ ]] || { echo "--limit must be positive" >&2; exit 2; }

python_bin="${PYTHON_BIN:-}"
if [[ -z "$python_bin" ]]; then
  if [[ -x "$repo_root/.venv/bin/python" ]]; then
    python_bin="$repo_root/.venv/bin/python"
  else
    python_bin="python3"
  fi
fi
"$python_bin" -c 'import src.run_baselines' >/dev/null 2>&1 || {
  echo "PYTHON_BIN cannot import src.run_baselines: $python_bin" >&2
  exit 1
}

: "${LLM_PROVIDER:=openrouter}"
: "${OPENROUTER_MODEL:=openai/gpt-oss-120b}"
: "${OPENROUTER_REASONING_ENABLED:=true}"
export LLM_PROVIDER OPENROUTER_MODEL OPENROUTER_REASONING_ENABLED

input="${input_override:-$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard}.json}"
[[ -f "$input" ]] || { echo "Missing input file: $input" >&2; exit 1; }

output="${output:-$repo_root/data/results/hybridqa-1500-seed2027/oueg-focus-augmentation-shard${shard}.jsonl}"
mkdir -p "$(dirname "$output")"

args=(
  --dataset hybridqa
  --method online_unified_evidence_graph
  --input "$input"
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --output "$output"
  --top-k 5
  --second-stage-k 3
  --max-context-chars 24000
  --max-output-tokens 1024
  --temperature 0
  --focus-passage-budget-per-candidate 2
  --focus-query-fallback-budget 2
  --l2-existing-witness-budget 2
  --l2-max-edges-per-candidate 16
  --l2-max-contexts-per-candidate 3
  --l2-context-snippet-chars 900
  --l2-evidence-mode "$l2_evidence_mode"
  --max-workers "$workers"
  --llm-max-concurrent-requests "$workers"
  --llm-timeout-seconds 120
  --llm-sdk-retries 2
  --quiet-records
)
[[ "$path_focused" == true ]] && args+=(--path-focused-prompt)
[[ -n "$limit" ]] && args+=(--limit "$limit")
[[ "$resume" == true ]] && args+=(--resume)
[[ "$collision_expansion" == true ]] || args+=(--no-collision-evidence-expansion)

echo "OUEG focus-augmentation benchmark"
echo "model=${LLM_PROVIDER}/${OPENROUTER_MODEL} shard=${shard} workers=${workers}"
echo "output=${output}"
PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines "${args[@]}"
