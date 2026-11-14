#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-20b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)
export MAX_WORKERS=4
export LLM_MAX_CONCURRENT_REQUESTS=4
export OPENROUTER_MAX_CONCURRENT_REQUESTS=4

python_bin="$repo_root/.venv/bin/python"
output_dir="$repo_root/data/results/gpt-oss-20b-oueg-ablations-shard01"
log_dir="$output_dir/logs"
mkdir -p "$output_dir" "$log_dir"

input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard01.json"
model_label="openrouter__openai-gpt-oss-20b"
shard_label="shard01-of08"

common_args=(
  --dataset hybridqa
  --method online_unified_evidence_graph
  --input "$input"
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5
  --max-table-rows-for-kg 999999
  --max-context-chars 24000
  --max-output-tokens 1024
  --temperature 0
  --no-path-focused-prompt
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
  --max-workers 4
  --llm-max-concurrent-requests 4
  --quiet-records
  --resume
)

run_ablation() {
  local ablation="$1"
  shift
  local extra_args=("$@")
  local ablation_dir="$output_dir/$ablation"
  local output="$ablation_dir/hybridqa__${shard_label}__${model_label}__online_unified_evidence_graph__${ablation}.jsonl"
  local log="$log_dir/hybridqa__${shard_label}__${model_label}__online_unified_evidence_graph__${ablation}.log"

  mkdir -p "$ablation_dir"
  echo "[$(date --iso-8601=seconds)] >>> START ablation=$ablation"
  PYTHONUNBUFFERED=1 "$python_bin" -m src.run_baselines \
    --output "$output" \
    "${common_args[@]}" \
    "${extra_args[@]}" 2>&1 | tee "$log"
  echo "[$(date --iso-8601=seconds)] >>> DONE ablation=$ablation"
  
  # update benchmark summary
  "$python_bin" scripts/fast_benchmark_summary.py "$output_dir" || true
}

echo "=== Running remaining HybridQA Shard 01 Ablations ==="
run_ablation l1_only --no-adaptive-verification
run_ablation no_l2_new_evidence --no-focus-evidence-augmentation
run_ablation no_diagnostic_focus_resolution --no-diagnostic-focus-resolution
run_ablation no_prompt_compression --no-prompt-compression

echo "=== ALL ABLATIONS FINISHED ==="
"$python_bin" scripts/fast_benchmark_summary.py "$output_dir"
