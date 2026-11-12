#!/usr/bin/env bash
# Reproducible QEG soft-contract trial: answer first, then CITE_EVIDENCE.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f "$repo_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env"
  set +a
fi

input="${1:-$repo_root/benchmarks/hybridqa/hybridqa-dev-shard02-ambiguous20.json}"
output_dir="${OUTPUT_DIR:-$repo_root/data/results/qeg-soft-contract-ambiguous20-openrouter-gpt-oss-20b-$(date -u +%Y%m%dT%H%M%SZ)}"
baseline="${BASELINE:-$repo_root/data/results/qeg-ambiguous20-openrouter-gpt-oss-20b-20261104/no_path.jsonl}"
workers="${MAX_WORKERS:-2}"
model="${MODEL:-openai/gpt-oss-20b}"
python_bin="${PYTHON_BIN:-$repo_root/.venv/bin/python}"
[[ -x "$python_bin" ]] || python_bin="$(command -v python3)"

: "${OPENROUTER_API_KEY:?Set OPENROUTER_API_KEY or put it in .env}"
[[ -f "$input" ]] || { echo "Missing input: $input" >&2; exit 1; }
mkdir -p "$output_dir"

common_args=(
  --dataset hybridqa --input "$input" --output "$output_dir/qeg_soft_contract.jsonl"
  --method qeg_soft_contract
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5 --max-context-chars 24000 --max-table-rows-for-kg 999999
  --max-output-tokens 2048 --temperature 0
  --collision-passage-budget 12 --focus-passage-budget-per-candidate 2
  --focus-query-fallback-budget 2 --l2-existing-witness-budget 2
  --l2-max-edges-per-candidate 16 --l2-max-contexts-per-candidate 3
  --l2-context-snippet-chars 900 --l2-evidence-mode delta_only
  --ambiguity-policy prompt --oueg-context-mode lossless --no-path-guidance
  --max-workers "$workers" --llm-max-concurrent-requests "$workers"
  --write-completion-order --quiet-records
)
[[ "${RESUME:-false}" == "true" ]] && common_args+=(--resume)

env \
  LLM_PROVIDER=openrouter \
  OPENROUTER_MODEL="$model" \
  OPENROUTER_REASONING_ENABLED="${OPENROUTER_REASONING_ENABLED:-true}" \
  OPENROUTER_MAX_CONCURRENT_REQUESTS="$workers" \
  "$python_bin" -m src.run_baselines "${common_args[@]}"

report_args=(--input "$output_dir/qeg_soft_contract.jsonl" --output "$output_dir/qeg_grounding_report.json" --markdown "$output_dir/qeg_grounding_report.md")
[[ -f "$baseline" ]] && report_args+=(--baseline "$baseline")
"$python_bin" scripts/qeg_grounding_report.py "${report_args[@]}"
echo "QEG soft-contract trial complete: $output_dir"
