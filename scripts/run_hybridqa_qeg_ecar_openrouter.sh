#!/usr/bin/env bash
# Compare the no-path reader with the no-extra-call QEG-ECAR executor.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f "$repo_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env"
  set +a
fi

input="${1:-$repo_root/benchmarks/hybridqa/hybridqa-dev-shard02-stratified10x10-seed20261104.json}"
output_dir="${OUTPUT_DIR:-$repo_root/data/results/qeg-ecar-openrouter-gpt-oss-20b-$(date -u +%Y%m%dT%H%M%SZ)}"
workers="${MAX_WORKERS:-2}"
model="${MODEL:-openai/gpt-oss-20b}"
python_bin="${PYTHON_BIN:-$repo_root/.venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$(command -v python3)"

: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY or put it in .env}"
[[ -f "$input" ]] || { echo "Missing input: $input" >&2; exit 1; }
mkdir -p "$output_dir"

common_args=(
  --dataset hybridqa --input "$input"
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5 --max-context-chars 24000 --max-table-rows-for-kg 999999
  --max-output-tokens 2048 --temperature 0
  --collision-passage-budget 12 --focus-passage-budget-per-candidate 2
  --focus-query-fallback-budget 2 --l2-existing-witness-budget 2
  --l2-max-edges-per-candidate 16 --l2-max-contexts-per-candidate 3
  --l2-context-snippet-chars 900 --l2-evidence-mode delta_only
  --ambiguity-policy prompt --oueg-context-mode lossless
  --max-workers "$workers" --llm-max-concurrent-requests "$workers"
  --write-completion-order --quiet-records
)
[[ "${RESUME:-false}" == "true" ]] && common_args+=(--resume)

run() {
  env LLM_PROVIDER=openrouter OPENROUTER_MODEL="$model" \
    OPENROUTER_REASONING_ENABLED="${OPENROUTER_REASONING_ENABLED:-true}" \
    OPENROUTER_MAX_CONCURRENT_REQUESTS="$workers" \
    "$python_bin" -m src.run_baselines "$@"
}

run --output "$output_dir/no_path.jsonl" --method online_unified_evidence_graph \
  "${common_args[@]}" --no-path-guidance
run --output "$output_dir/qeg_ecar.jsonl" --method qeg_ecar \
  "${common_args[@]}" --no-path-guidance

"$python_bin" scripts/qeg_stratified_report.py \
  --qeg "$output_dir/qeg_ecar.jsonl" --baseline "$output_dir/no_path.jsonl" \
  --selection "${input}.selection.json" --output "$output_dir/ecar_stratified_report.json" \
  --markdown "$output_dir/ecar_stratified_report.md" --candidate-label ECAR

echo "QEG-ECAR trial complete: $output_dir"
