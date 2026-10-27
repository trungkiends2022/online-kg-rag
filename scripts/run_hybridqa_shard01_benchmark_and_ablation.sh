#!/usr/bin/env bash
# Run both the 5-method main benchmark and the 7-component ablation on HybridQA Shard 01.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export LLM_PROVIDER=openrouter
export OPENROUTER_MODEL=openai/gpt-oss-20b
export OPENROUTER_REASONING_ENABLED=true
export OPENROUTER_API_KEY=$(grep -oP '(?<=OPENROUTER_API_KEY=)[^\s]+' .env)
export MAX_WORKERS=4
export LLM_MAX_CONCURRENT_REQUESTS=4

echo "=========================================================================="
echo "Starting HybridQA Shard 01: Benchmark & Ablation Suite (GPT-OSS 20B)"
echo "Date: $(date --iso-8601=seconds)"
echo "Model: $OPENROUTER_MODEL"
echo "Workers: $MAX_WORKERS"
echo "=========================================================================="

echo ""
echo ">>> STEP 1/2: Main Benchmark on Shard 01 (5 methods x 200 examples)"
echo "    Methods: online_unified_evidence_graph, direct_llm, odyssey, graph_retrieval_no_path, path_text_top_n"
RUN_TAG="gpt-oss-20b-grounded-shard01" bash scripts/run_hybridqa_1500.sh 01

echo ""
echo ">>> STEP 2/2: OUEG Component Ablations on Shard 01 (7 ablations x 200 examples)"
echo "    Configurations: full, no_record_nodes, no_path_guidance, l1_only, no_l2_new_evidence, no_diagnostic_focus_resolution, no_prompt_compression"
bash scripts/run_hybridqa_500_oueg_component_ablations.sh \
  --shard 01 \
  --workers "$MAX_WORKERS" \
  --tag "gpt-oss-20b-oueg-ablations-shard01"

echo ""
echo "=========================================================================="
echo "All HybridQA Shard 01 Benchmark & Ablation runs successfully completed!"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="

