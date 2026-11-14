#!/usr/bin/env bash
# Complete remaining Shard 01 case (path_text_top_n) and then execute Shard 02 for OTT-QA (GPT-OSS 20B).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ -f "$repo_root/.env" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    [[ "$line" =~ ^# ]] && continue
    [[ -z "$line" ]] && continue
    if [[ "$line" == *=* ]]; then
      var_name="${line%%=*}"
      var_val="${line#*=}"
      var_name="$(echo -n "$var_name" | tr -d ' ')"
      var_val="${var_val%\"}"
      var_val="${var_val#\"}"
      var_val="${var_val%\'}"
      var_val="${var_val#\'}"
      if [[ -z "${!var_name+x}" ]]; then
        export "$var_name"="$var_val"
      fi
    fi
  done < "$repo_root/.env"
fi

python_bin="$repo_root/.venv/bin/python"

echo "=========================================================================="
echo "BƯỚC 1: Hoàn tất Shard 01 cho OTT-QA (chạy nốt path_text_top_n còn thiếu)"
echo "=========================================================================="
METHODS="path_text_top_n" \
LLM_PROVIDER=openrouter \
OPENROUTER_MODEL=openai/gpt-oss-20b \
OPENROUTER_REASONING_ENABLED=true \
MAX_WORKERS=4 \
LLM_MAX_CONCURRENT_REQUESTS=4 \
bash "$repo_root/scripts/run_ottqa_shard01_100.sh"

echo ""
echo "=========================================================================="
echo "BƯỚC 2: Chạy tiếp Shard 02 cho OTT-QA (100 câu, 5 phương pháp, GPT-OSS 20B)"
echo "=========================================================================="
METHODS="online_unified_evidence_graph direct_llm odyssey graph_retrieval_no_path path_text_top_n" \
LLM_PROVIDER=openrouter \
OPENROUTER_MODEL=openai/gpt-oss-20b \
OPENROUTER_REASONING_ENABLED=true \
MAX_WORKERS=4 \
LLM_MAX_CONCURRENT_REQUESTS=4 \
INPUT="$repo_root/benchmarks/ottqa/ottqa-dev-odyssey-500-seed2027-shard02.json" \
RUN_TAG="ottqa-shard02-100-benchmark-20b" \
bash "$repo_root/scripts/run_ottqa_shard01_100.sh"

echo ""
echo "=========================================================================="
echo "TẤT CẢ CÁC RUN SHARD 01 VÀ SHARD 02 OTT-QA ĐÃ HOÀN TẤT!"
echo "=========================================================================="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$repo_root/data/results/ottqa-shard01-100-benchmark-20b"
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$repo_root/data/results/ottqa-shard02-100-benchmark-20b"
