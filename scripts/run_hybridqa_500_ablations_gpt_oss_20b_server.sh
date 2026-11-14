#!/usr/bin/env bash
# ==============================================================================
# Script chạy 7 cấu hình Causal Component Ablation cho OUEG (QEG-RAG)
# trên 500 mẫu HybridQA (Shards 06, 07, 08) với GPT-OSS 20B trên Local/Server
#
# QUAN TRỌNG: Script này sử dụng trực tiếp server nội bộ (vLLM / Ollama / SGLang /
# OpenAI-compatible server), TUYỆT ĐỐI KHÔNG DÙNG OpenRouter.
# ==============================================================================

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# 1. Tự động nạp .env nếu có (không ghi đè biến đã export ngoài shell)
if [[ -f "$repo_root/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$repo_root/.env"
  set +a
fi

# 2. Thiết lập cố định LLM Provider là openai_compatible (server nội bộ)
export LLM_PROVIDER="openai_compatible"
# Đảm bảo gỡ bỏ hoàn toàn biến OPENROUTER để tránh nhầm lẫn
unset OPENROUTER_MODEL 2>/dev/null || true

# 3. Giá trị mặc định (Ưu tiên mô hình GPT-OSS 20B theo yêu cầu bài toán)
DEFAULT_BASE_URL="${SERVER_BASE_URL:-${COMPAT_BASE_URL:-http://localhost:8000/v1}}"
# Nếu COMPAT_MODEL trong .env là llama3.1 thì chuyển về openai/gpt-oss-20b theo yêu cầu
if [[ "${COMPAT_MODEL:-}" == "llama3.1" || -z "${COMPAT_MODEL:-}" ]]; then
  DEFAULT_MODEL="openai/gpt-oss-20b"
else
  DEFAULT_MODEL="$COMPAT_MODEL"
fi
DEFAULT_API_KEY="${COMPAT_API_KEY:-EMPTY}"
DEFAULT_REASONING="${COMPAT_REASONING_ENABLED:-true}"
DEFAULT_WORKERS="${MAX_WORKERS:-4}"
DEFAULT_SHARDS=(06 07 08) # 200 + 200 + 100 = 500 records

# 7 cấu hình ablation chuẩn
ALL_ABLATIONS=(
  full
  no_record_nodes
  no_path_guidance
  l1_only
  no_l2_new_evidence
  no_diagnostic_focus_resolution
  no_prompt_compression
)

base_url="$DEFAULT_BASE_URL"
model="$DEFAULT_MODEL"
api_key="$DEFAULT_API_KEY"
reasoning_enabled="$DEFAULT_REASONING"
workers="$DEFAULT_WORKERS"
shards=("${DEFAULT_SHARDS[@]}")
selected_ablations=("${ALL_ABLATIONS[@]}")
limit=""
output_dir=""
run_tag="hybridqa-500-ablations-gpt-oss-20b-server-$(date -u +%Y%m%dT%H%M%SZ)"
resume=true
dry_run=false
check_server=true

usage() {
  cat <<'EOF'
Cách dùng:
  bash scripts/run_hybridqa_500_ablations_gpt_oss_20b_server.sh [TÙY CHỌN]

Mô tả:
  Chạy đầy đủ 7 cấu hình Causal Component Ablations trên 500 mẫu HybridQA
  (shards 06, 07, 08) sử dụng mô hình GPT-OSS 20B triển khai trên Server nội bộ
  (vLLM / SGLang / Ollama / OpenAI-compatible endpoint). Không phụ thuộc OpenRouter.

Tùy chọn kết nối & Model:
  --base-url <url>         URL endpoint của Server (mặc định: http://localhost:8000/v1)
  --model <name>           Tên định danh model trên server (mặc định: openai/gpt-oss-20b)
  --api-key <key>          API key nếu server yêu cầu (mặc định: EMPTY)
  --no-reasoning           Tắt reasoning CoT payload (mặc định: bật CoT reasoning)
  --skip-server-check      Bỏ qua bước kiểm tra kết nối tới Server endpoint

Tùy chọn Benchmark:
  -w, --workers <N>        Số worker đồng thời / concurrent requests (mặc định: 4)
  --shards "06 07 08"      Danh sách shards muốn chạy (mặc định: "06 07 08" = 500 mẫu)
  --ablations "cfg1 cfg2"  Chỉ chạy các ablation được chỉ định (mặc định: đủ 7 cấu hình)
  -l, --limit <N>          Giới hạn N mẫu trên mỗi shard (dùng để test nhanh)
  --output-dir <path>      Thư mục lưu kết quả (mặc định: data/results/<run_tag>)
  --tag <name>             Tên tag để đặt tên thư mục kết quả
  --no-resume              Chạy lại từ đầu, không bỏ qua các câu đã xử lý
  --dry-run                Chỉ in các lệnh thực thi mà không gọi mô hình thực tế
  -h, --help               Hiển thị hướng dẫn này

7 Cấu hình Causal Ablation:
  1. full                             OUEG hoàn chỉnh (Control)
  2. no_record_nodes                  Bỏ record centroid row nodes (--no-record-nodes)
  3. no_path_guidance                 Bỏ dẫn đường đồ thị (--no-path-guidance)
  4. l1_only                          Chỉ dùng L1, bỏ L2 adaptive verification (--no-adaptive-verification)
  5. no_l2_new_evidence               L2 không nạp thêm context mới (--no-focus-evidence-augmentation)
  6. no_diagnostic_focus_resolution   Bỏ phân giải diagnostic focus (--no-diagnostic-focus-resolution)
  7. no_prompt_compression            Bỏ nén prompt compact lossless (--no-prompt-compression)

Ví dụ:
  # Chạy đầy đủ 500 mẫu với 4 workers trên server local:
  bash scripts/run_hybridqa_500_ablations_gpt_oss_20b_server.sh

  # Chạy với vLLM trên cổng 8000:
  bash scripts/run_hybridqa_500_ablations_gpt_oss_20b_server.sh \
    --base-url http://localhost:8000/v1 \
    --model openai/gpt-oss-20b \
    --workers 8

  # Test nhanh 5 câu trên shard 06:
  bash scripts/run_hybridqa_500_ablations_gpt_oss_20b_server.sh \
    --shards "06" --limit 5 --ablations "full no_record_nodes"
EOF
}

# 4. Phân tích tham số dòng lệnh
while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url) base_url="$2"; shift 2 ;;
    --model) model="$2"; shift 2 ;;
    --api-key) api_key="$2"; shift 2 ;;
    --no-reasoning) reasoning_enabled="false"; shift ;;
    --skip-server-check) check_server=false; shift ;;
    -w|--workers) workers="$2"; shift 2 ;;
    --shards) read -r -a shards <<< "$2"; shift 2 ;;
    --ablations) read -r -a selected_ablations <<< "$2"; shift 2 ;;
    -l|--limit) limit="$2"; shift 2 ;;
    --output-dir) output_dir="$2"; shift 2 ;;
    --tag) run_tag="$2"; shift 2 ;;
    --no-resume) resume=false; shift ;;
    --dry-run) dry_run=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Tùy chọn không hợp lệ: $1" >&2; usage >&2; exit 2 ;;
  esac
done

# 5. Kiểm tra tính hợp lệ của tham số
if ! [[ "$workers" =~ ^[1-9][0-9]*$ ]]; then
  echo "Lỗi: --workers phải là số nguyên dương; nhận được: $workers" >&2
  exit 2
fi
if [[ -n "$limit" ]] && ! [[ "$limit" =~ ^[1-9][0-9]*$ ]]; then
  echo "Lỗi: --limit phải là số nguyên dương; nhận được: $limit" >&2
  exit 2
fi

# 6. Thiết lập các biến môi trường cho OpenAI-compatible provider
export COMPAT_BASE_URL="$base_url"
export COMPAT_MODEL="$model"
export COMPAT_API_KEY="$api_key"
export COMPAT_REASONING_ENABLED="$reasoning_enabled"
export MAX_WORKERS="$workers"
export LLM_MAX_CONCURRENT_REQUESTS="$workers"

# 7. Tìm Python interpreter có sẵn môi trường
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

  echo "Không tìm thấy môi trường Python phù hợp chứa src.run_baselines. Hãy đặt PYTHON_BIN." >&2
  return 1
}

python_bin="$(resolve_python)"

# 8. Xác định model label chuẩn hoá cho tên file kết quả
resolve_model_label() {
  "$python_bin" -c '
import re
from src.llm.client import get_provider

provider = get_provider()
name = getattr(provider, "name", "openai_compatible")
model_val = getattr(provider, "model", None) or "gpt-oss-20b"
label = re.sub(r"[^A-Za-z0-9._-]+", "-", f"{name}__{model_val}").strip("-")
print(label or "openai_compatible__gpt-oss-20b")
'
}

model_label="$(resolve_model_label)"
output_dir="${output_dir:-$repo_root/data/results/$run_tag}"
log_dir="$repo_root/data/logs/$run_tag"
mkdir -p "$output_dir" "$log_dir"

# 9. Kiểm tra kết nối và tự động nhận diện Server endpoint nếu cần
if [[ "$dry_run" == false && "$check_server" == true ]]; then
  echo ">>> Kiểm tra kết nối tới Server endpoint: $base_url"
  check_server_fn() {
    local target_url="$1"
    "$python_bin" -c '
import sys
from openai import OpenAI
try:
    client = OpenAI(base_url="'"$target_url"'", api_key="'"$api_key"'", timeout=3.0)
    models = client.models.list()
    model_ids = [m.id for m in getattr(models, "data", [])]
    print("SUCCESS:" + ",".join(model_ids[:5]))
except Exception as e:
    print("ERROR:" + str(e))
' 2>/dev/null || true
  }

  check_output="$(check_server_fn "$base_url")"
  if [[ "$check_output" == SUCCESS:* ]]; then
    available_models="${check_output#SUCCESS:}"
    echo "  [OK] Kết nối thành công tới Server ($base_url)!"
    echo "  Các model tìm thấy: ${available_models:-N/A}"
  else
    # Thử fallback kiểm tra cổng 8000 nếu base_url mặc định đang là 11434 nhưng không thông
    fallback_candidates=("http://localhost:8000/v1" "http://localhost:11434/v1" "http://127.0.0.1:8000/v1")
    found_fallback=""
    for cand in "${fallback_candidates[@]}"; do
      if [[ "$cand" != "$base_url" ]]; then
        cand_output="$(check_server_fn "$cand")"
        if [[ "$cand_output" == SUCCESS:* ]]; then
          found_fallback="$cand"
          available_models="${cand_output#SUCCESS:}"
          echo "  [TỰ ĐỘNG CHUYỂN] Phát hiện server đang hoạt động tại: $cand"
          echo "  Các model tìm thấy: ${available_models:-N/A}"
          base_url="$cand"
          export COMPAT_BASE_URL="$base_url"
          break
        fi
      fi
    done

    if [[ -z "$found_fallback" ]]; then
      echo "  [LƯU Ý] Không kết nối được API models tại $base_url: ${check_output#ERROR:}"
      echo "  Tiến trình vẫn tiếp tục chạy với endpoint $base_url. (Dùng cờ --base-url <url> nếu cổng khác)."
    fi
  fi
fi

# 10. Danh sách cờ đặc thù cho từng ablation
get_ablation_flags() {
  local cfg="$1"
  case "$cfg" in
    full) echo "" ;;
    no_record_nodes) echo "--no-record-nodes" ;;
    no_path_guidance) echo "--no-path-guidance" ;;
    l1_only) echo "--no-adaptive-verification" ;;
    no_l2_new_evidence) echo "--no-focus-evidence-augmentation" ;;
    no_diagnostic_focus_resolution) echo "--no-diagnostic-focus-resolution" ;;
    no_prompt_compression) echo "--no-prompt-compression" ;;
    *) echo "Lỗi: Không tìm thấy cấu hình ablation: $cfg" >&2; return 1 ;;
  esac
}

# 11. Các tham số benchmark chung của OUEG (khớp 100% với cấu hình chuẩn của bài báo)
common_args=(
  --dataset hybridqa
  --method online_unified_evidence_graph
  --tables-dir data/WikiTables-WithLinks/tables_tok
  --passages-dir data/WikiTables-WithLinks/request_tok
  --top-k 5
  --max-context-chars 24000
  --max-table-rows-for-kg 999999
  --no-path-focused-prompt
  --max-output-tokens 2048
  --temperature 0
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
  --max-workers "$workers"
  --llm-max-concurrent-requests "$workers"
  --quiet-records
)

[[ -n "$limit" ]] && common_args+=(--limit "$limit")
[[ "$resume" == true ]] && common_args+=(--resume)

# In banner thông tin phiên chạy
echo "=========================================================================="
echo "CHẠY ABLATION STUDY 500 MẪU HYBRIDQA VỚI GPT-OSS 20B (SERVER LOCAL)"
echo "=========================================================================="
echo "Provider:         $LLM_PROVIDER (OpenAI-compatible server nội bộ)"
echo "Base URL:         $COMPAT_BASE_URL"
echo "Model:            $COMPAT_MODEL"
echo "Reasoning:        $COMPAT_REASONING_ENABLED"
echo "Shards:           ${shards[*]} (Mặc định 06 + 07 + 08 = 500 mẫu)"
echo "Workers:          $workers"
echo "Limit per shard:  ${limit:-Toàn bộ shard}"
echo "Ablations (${#selected_ablations[@]}):  ${selected_ablations[*]}"
echo "Output Directory: $output_dir"
echo "Log Directory:    $log_dir"
echo "Bắt đầu lúc:      $(date --iso-8601=seconds)"
echo "=========================================================================="

# 12. Thực thi tuần tự các cấu hình ablation
for ablation in "${selected_ablations[@]}"; do
  extra_flag="$(get_ablation_flags "$ablation")"
  extra_args=()
  [[ -n "$extra_flag" ]] && extra_args+=("$extra_flag")

  ablation_dir="$output_dir/$ablation"
  ablation_log_dir="$log_dir/$ablation"
  mkdir -p "$ablation_dir" "$ablation_log_dir"

  echo ""
  echo "--------------------------------------------------------------------------"
  echo "[$(date --iso-8601=seconds)] >>> BẮT ĐẦU ABLATION: $ablation"
  echo "--------------------------------------------------------------------------"

  for shard in "${shards[@]}"; do
    if [[ "$shard" =~ ^[0-9]+$ ]]; then
      printf -v shard_fmt "%02d" "$((10#$shard))"
    else
      shard_fmt="$shard"
    fi

    shard_label="shard${shard_fmt}-of08"
    input="$repo_root/benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard${shard_fmt}.json"

    if [[ ! -f "$input" ]]; then
      echo "Lỗi: Không tìm thấy file shard dữ liệu: $input" >&2
      exit 1
    fi

    shard_records="$("$python_bin" -c "import json; print(len(json.load(open('$input'))))")"
    target_records="${limit:-$shard_records}"

    output="$ablation_dir/hybridqa__${shard_label}__${model_label}__online_unified_evidence_graph__${ablation}.jsonl"
    log="$ablation_log_dir/hybridqa__${shard_label}__${model_label}__online_unified_evidence_graph__${ablation}.log"

    # Kiểm tra resume: nếu đã đủ số lượng records thì bỏ qua
    if [[ "$resume" == true && -f "$output" ]]; then
      existing_lines="$(wc -l < "$output" || echo 0)"
      if [[ "$existing_lines" -ge "$target_records" ]]; then
        echo "[$(date --iso-8601=seconds)] Bỏ qua ablation=$ablation shard=$shard_fmt (Đã có $existing_lines / $target_records records)"
        continue
      fi
    fi

    echo "[$(date --iso-8601=seconds)] Chạy: ablation=$ablation | shard=$shard_fmt ($target_records records) | workers=$workers"

    cmd=(
      env
      "LLM_PROVIDER=$LLM_PROVIDER"
      "COMPAT_BASE_URL=$COMPAT_BASE_URL"
      "COMPAT_MODEL=$COMPAT_MODEL"
      "COMPAT_API_KEY=$COMPAT_API_KEY"
      "COMPAT_REASONING_ENABLED=$COMPAT_REASONING_ENABLED"
      "MAX_WORKERS=$workers"
      "LLM_MAX_CONCURRENT_REQUESTS=$workers"
      "$python_bin" -m src.run_baselines
      --input "$input"
      --output "$output"
      "${common_args[@]}"
      "${extra_args[@]}"
    )

    if [[ "$dry_run" == true ]]; then
      printf '  [DRY-RUN] '; printf '%q ' "${cmd[@]}"; printf '\n'
    else
      PYTHONUNBUFFERED=1 "${cmd[@]}" 2>&1 | tee "$log"
      echo "[$(date --iso-8601=seconds)] Hoàn thành: ablation=$ablation | shard=$shard_fmt"
    fi
  done
done

echo ""
echo "=========================================================================="
echo "TẤT CẢ ABLATION ĐÃ HOÀN THÀNH!"
echo "Kết quả lưu tại: $output_dir"
echo "Logs lưu tại:    $log_dir"
echo "=========================================================================="

# 13. Tự động xuất bảng tổng kết benchmark
if [[ "$dry_run" == false ]]; then
  echo ""
  echo "=== [TỔNG KẾT KẾT QUẢ BENCHMARK ABLATION TỰ ĐỘNG] ==="
  if [[ -f "$repo_root/scripts/fast_benchmark_summary.py" ]]; then
    "$python_bin" "$repo_root/scripts/fast_benchmark_summary.py" "$output_dir" || true
  fi
fi
