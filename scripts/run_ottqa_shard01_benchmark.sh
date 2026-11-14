#!/usr/bin/env bash
# Run the 5-method main benchmark on OTT-QA Shard 01 with GPT-OSS 20B.
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
echo "Starting OTT-QA Shard 01: Benchmark Suite (GPT-OSS 20B)"
echo "Date: $(date --iso-8601=seconds)"
echo "Model: $OPENROUTER_MODEL"
echo "Workers: $MAX_WORKERS"
echo "Methods: online_unified_evidence_graph, direct_llm, odyssey, graph_retrieval_no_path, path_text_top_n"
echo "=========================================================================="

RUN_TAG="gpt-oss-20b-shard01" bash scripts/run_ottqa_500.sh 01

echo ""
echo "=========================================================================="
echo "OTT-QA Shard 01 Benchmark run successfully completed!"
echo "Date: $(date --iso-8601=seconds)"
echo "=========================================================================="

