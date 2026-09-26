#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Determine Python binary
if [[ -n "${PYTHON_BIN:-}" && -x "$PYTHON_BIN" ]]; then
  python_bin="$PYTHON_BIN"
elif [[ -x "$repo_root/.venv/bin/python" ]]; then
  python_bin="$repo_root/.venv/bin/python"
else
  python_bin="$(command -v python3)"
fi

# Default configuration
SHARD="01"
METHOD="online_kg_path_text"
WORKERS=4
MAX_WORKERS_ALLOWED=8
COMPARE_DIRECT=true
LIMIT=""
RESUME=true
QUIET_RECORDS=true
RUN_TAG="${RUN_TAG:-run_$(date +%Y%m%d_%H%M%S)}"
RESULT_DIR="${RESULT_DIR:-$repo_root/data/results/hybridqa-1500-seed2027/$RUN_TAG}"

usage() {
  cat << EOF
Usage: $(basename "$0") [options]

Chạy benchmark HybridQA theo từng shard, hiển thị tiến độ bằng tqdm,
ghi log EM, ACC, số lần gọi LLM, thời gian chạy và so sánh với direct_llm.

Options:
  -s, --shard <01..08|all>   Shard cần chạy (mặc định: 01). Có thể là 01, 02, ..., 08 hoặc all.
  -w, --workers <1..8>       Số luồng chạy song song (mặc định: 4, tối đa: 8).
  -m, --method <name>        Phương pháp đánh giá (mặc định: online_kg_path_text).
                             Các lựa chọn: online_kg_path_text, online_kg, flat_table_bm25,
                             graph_retrieval_no_path, path_consistency, direct_llm.
  --no-compare-direct        Chỉ chạy phương pháp đã chọn, không chạy direct_llm để so sánh.
  -l, --limit <N>            Chỉ chạy N mẫu đầu tiên trong shard (rất tiện để test nhanh).
  --no-resume                Ghi đè kết quả, không chạy tiếp từ kết quả cũ.
  --verbose-records          In toàn bộ JSON từng mẫu ra stdout (thay vì chỉ hiện tqdm).
  --tag <string>             Đặt tag định danh lần chạy (mặc định: run_YYYYMMDD_HHMMSS).
  --output-dir <path>        Thư mục lưu kết quả (mặc định: data/results/hybridqa-1500-seed2027/<tag>).
  -h, --help                 Hiển thị hướng dẫn này.

Ví dụ:
  # Chạy shard 01 với 4 luồng, so sánh online_kg_path_text với direct_llm:
  $(basename "$0") --shard 01 --workers 4

  # Chạy test nhanh 5 câu đầu của shard 02 với 8 luồng song song:
  $(basename "$0") --shard 02 --workers 8 --limit 5

  # Chạy phương pháp online_kg full pipeline trên shard 01 với 8 luồng:
  $(basename "$0") --shard 01 --workers 8 --method online_kg
EOF
  exit 0
}

# Parse CLI arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--shard)
      SHARD="$2"
      shift 2
      ;;
    -w|--workers)
      WORKERS="$2"
      shift 2
      ;;
    -m|--method)
      METHOD="$2"
      shift 2
      ;;
    --no-compare-direct)
      COMPARE_DIRECT=false
      shift
      ;;
    -l|--limit)
      LIMIT="$2"
      shift 2
      ;;
    --no-resume)
      RESUME=false
      shift
      ;;
    --verbose-records)
      QUIET_RECORDS=false
      shift
      ;;
    --tag)
      RUN_TAG="$2"
      RESULT_DIR="$repo_root/data/results/hybridqa-1500-seed2027/$RUN_TAG"
      shift 2
      ;;
    --output-dir)
      RESULT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ || "$1" == "all" ]]; then
        SHARD="$1"
        shift
      else
        echo "Lỗi: Tham số không hợp lệ '$1'" >&2
        usage
      fi
      ;;
  esac
done

# Validate workers
if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || (( WORKERS < 1 )); then
  echo "Lỗi: Số luồng --workers phải là số nguyên dương từ 1 đến $MAX_WORKERS_ALLOWED." >&2
  exit 1
fi
if (( WORKERS > MAX_WORKERS_ALLOWED )); then
  echo "Cảnh báo: Số luồng yêu cầu ($WORKERS) vượt quá giới hạn tối đa ($MAX_WORKERS_ALLOWED). Tự động điều chỉnh về $MAX_WORKERS_ALLOWED luồng." >&2
  WORKERS=$MAX_WORKERS_ALLOWED
fi

# Resolve shards
if [[ "$SHARD" == "all" ]]; then
  shards=(01 02 03 04 05 06 07 08)
else
  # Format shard with 2 digits (e.g. 1 -> 01)
  printf -v padded_shard "%02d" "$((10#$SHARD))" 2>/dev/null || padded_shard="$SHARD"
  shards=("$padded_shard")
fi

# Methods to run
methods=("$METHOD")
if [ "$COMPARE_DIRECT" = true ] && [ "$METHOD" != "direct_llm" ]; then
  methods+=("direct_llm")
fi

mkdir -p "$RESULT_DIR"

echo "================================================================================"
echo "                HYBRIDQA 1500 BENCHMARK RUNNER"
echo "================================================================================"
echo "Python:          $python_bin"
echo "Shards:          ${shards[*]}"
echo "Methods:         ${methods[*]}"
echo "Song song:       $WORKERS luồng (tối đa cho phép: $MAX_WORKERS_ALLOWED)"
echo "Output thư mục:  $RESULT_DIR"
if [ -n "$LIMIT" ]; then
  echo "Giới hạn mẫu:    $LIMIT mẫu / shard"
fi
echo "================================================================================"

for s in "${shards[@]}"; do
  shard_input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${s}.json"
  if [[ ! -f "$shard_input" ]]; then
    echo "Lỗi: Không tìm thấy file shard: $shard_input" >&2
    exit 1
  fi

  echo ""
  echo ">>> [SHARD $s] Bắt đầu đánh giá..."

  for m in "${methods[@]}"; do
    m_dir="$RESULT_DIR/$m"
    mkdir -p "$m_dir"
    out_file="$m_dir/shard${s}.jsonl"

    cmd=(
      "$python_bin" -m src.run_baselines
      --dataset hybridqa
      --method "$m"
      --input "$shard_input"
      --tables-dir data/WikiTables-WithLinks/tables_tok
      --passages-dir data/WikiTables-WithLinks/request_tok
      --output "$out_file"
      --top-k 5
      --second-stage-k 3
      --n-paths 3
      --max-replans 0
      --max-context-chars 24000
      --max-output-tokens 512
      --temperature 0
      --max-workers "$WORKERS"
      --llm-max-concurrent-requests "$WORKERS"
      --force-progress
    )

    if [ "$RESUME" = true ]; then
      cmd+=(--resume)
    fi
    if [ "$QUIET_RECORDS" = true ]; then
      cmd+=(--quiet-records)
    fi
    if [ -n "$LIMIT" ]; then
      cmd+=(--limit "$LIMIT")
    fi

    echo "--- Chạy phương pháp: $m (Luồng: $WORKERS) ---"
    PYTHONUNBUFFERED=1 "${cmd[@]}"
    echo "--- Hoàn thành: $m (Đã lưu: $out_file) ---"
  done

  # Print comparison table for this shard if direct_llm was run
  if [ "$COMPARE_DIRECT" = true ] && [ "$METHOD" != "direct_llm" ]; then
    echo ""
    echo "=== [KẾT QUẢ SO SÁNH SHARD $s] ==="
    "$python_bin" -c "
import json
from pathlib import Path

shard = '$s'
res_dir = Path('$RESULT_DIR')
target_m = '$METHOD'
methods = [target_m, 'direct_llm']

print(f'| {\"Chỉ số (Metric)\":<30} | {target_m:<22} | {\"direct_llm\":<15} |')
print(f'|{\":-\":-<32}|{\":-\":-<24}|{\":-\":-<17}|')

data = {}
for m in methods:
    p = res_dir / m / f'shard{shard}.jsonl.summary.json'
    if p.exists():
        data[m] = json.loads(p.read_text(encoding='utf-8'))
    else:
        data[m] = {}

def fmt_pct(val):
    return f'{val:.2f}%' if val is not None else 'N/A'

def fmt_num(val, dec=1):
    return f'{val:.{dec}f}' if val is not None else 'N/A'

def fmt_ms(val):
    if val is None:
        return 'N/A'
    return f'{val/1000:.1f}s' if val >= 1000 else f'{val:.0f}ms'

row1 = ('Số mẫu đánh giá (Evaluated)', f\"{data[target_m].get('num_examples', 'N/A')}\", f\"{data['direct_llm'].get('num_examples', 'N/A')}\")
row2 = ('Exact Match (EM)', fmt_pct(data[target_m].get('exact_match_percent')), fmt_pct(data['direct_llm'].get('exact_match_percent')))
row3 = ('Semantic Exact Match (ACC)', fmt_pct(data[target_m].get('semantic_exact_match_percent')), fmt_pct(data['direct_llm'].get('semantic_exact_match_percent')))
row4 = ('Token F1 Score', fmt_pct(data[target_m].get('f1_percent')), fmt_pct(data['direct_llm'].get('f1_percent')))
row5 = ('Tổng số LLM calls', fmt_num(data[target_m].get('total_llm_calls'), 0), fmt_num(data['direct_llm'].get('total_llm_calls'), 0))
row6 = ('TB số LLM calls / mẫu', fmt_num(data[target_m].get('mean_llm_calls'), 2), fmt_num(data['direct_llm'].get('mean_llm_calls'), 2))
row7 = ('TB thời gian chạy / mẫu', fmt_ms(data[target_m].get('mean_wall_time_ms')), fmt_ms(data['direct_llm'].get('mean_wall_time_ms')))
row8 = ('Tổng thời gian chạy', fmt_ms(data[target_m].get('total_wall_time_ms')), fmt_ms(data['direct_llm'].get('total_wall_time_ms')))

for label, v1, v2 in [row1, row2, row3, row4, row5, row6, row7, row8]:
    print(f'| {label:<30} | {v1:<22} | {v2:<15} |')
"
  fi
done

echo ""
echo "================================================================================"
echo "Hoàn thành toàn bộ benchmark! Kết quả đã được lưu tại: $RESULT_DIR"
echo "================================================================================"
