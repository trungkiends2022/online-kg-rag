#!/usr/bin/env bash
# Run remaining 100 cases of Shard 01 for both 20B and 120B, then combine into full 200 cases.
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
remaining_input="$repo_root/benchmarks/hybridqa/hybridqa-dev-shard01-remaining100cases.json"

echo "=========================================================================="
echo "BƯỚC 1: Đã hoàn tất 100 câu còn lại cho 20B (bỏ qua rerun)"
echo "=========================================================================="
# Step 1 was already 100% completed:
# LLM_PROVIDER=openrouter OPENROUTER_MODEL=openai/gpt-oss-20b INPUT="$remaining_input" RUN_TAG="hybridqa-shard01-remaining100-20b" bash "$repo_root/scripts/run_hybridqa_shard01_100.sh"

echo "=========================================================================="
echo "BƯỚC 2: Chạy các baseline còn lại cho OPENAI/GPT-OSS-120B"
echo "=========================================================================="
LLM_PROVIDER=openrouter \
OPENROUTER_MODEL=openai/gpt-oss-120b \
OPENROUTER_REASONING_ENABLED=true \
INPUT="$remaining_input" \
RUN_TAG="hybridqa-shard01-remaining100-120b" \
METHODS="odyssey graph_retrieval_no_path path_text_top_n" \
bash "$repo_root/scripts/run_hybridqa_shard01_100.sh"

echo "=========================================================================="
echo "BƯỚC 3: Tổng hợp toàn bộ 200 câu Shard 01 (100 câu đầu + 100 câu sau)"
echo "=========================================================================="
"$python_bin" -c '
import json, os, shutil
from pathlib import Path

repo_root = Path(".").resolve()
methods = [
    "online_unified_evidence_graph",
    "direct_llm",
    "odyssey",
    "graph_retrieval_no_path",
    "path_text_top_n"
]

for scale, m_label, run_first, run_rem in [
    ("20b", "openrouter__openai-gpt-oss-20b", "hybridqa-shard01-100-benchmark", "hybridqa-shard01-remaining100-20b"),
    ("120b", "openrouter__openai-gpt-oss-120b", "hybridqa-shard01-100-benchmark-120b", "hybridqa-shard01-remaining100-120b"),
]:
    full_dir = repo_root / f"data/results/hybridqa-shard01-full200-{scale}"
    full_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n--- Đang tổng hợp 200 câu cho {scale.upper()} tại {full_dir} ---")
    
    for method in methods:
        m_dir = full_dir / method
        m_dir.mkdir(parents=True, exist_ok=True)
        out_jsonl = m_dir / f"shard01-full200__{m_label}__{method}.jsonl"
        
        file_part1 = repo_root / f"data/results/{run_first}/{method}/shard01-100cases__{m_label}__{method}.jsonl"
        file_part2 = repo_root / f"data/results/{run_rem}/{method}/shard01-100cases__{m_label}__{method}.jsonl"
        
        records = []
        seen_ids = set()
        for fpath in [file_part1, file_part2]:
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip().replace("\x00", "")
                        if not line: continue
                        r = json.loads(line)
                        qid = r.get("id") or r.get("question_id")
                        if qid not in seen_ids:
                            records.append(r)
                            seen_ids.add(qid)
        
        with open(out_jsonl, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"  [{method}] Ghi {len(records)}/200 records -> {out_jsonl.name}")

print("\nHoàn tất gộp records. Đang chạy fast_benchmark_summary trên cả 2 bộ 200 câu...")
'

echo ""
echo "=== [BÁO CÁO TỔNG HỢP SHARD 01 FULL 200 CÂU - GPT-OSS 20B] ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$repo_root/data/results/hybridqa-shard01-full200-20b"

echo ""
echo "=== [BÁO CÁO TỔNG HỢP SHARD 01 FULL 200 CÂU - GPT-OSS 120B] ==="
"$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$repo_root/data/results/hybridqa-shard01-full200-120b"
