# Online-KG RAG: Path → Executable Program → Grounded Evaluation

Tài liệu kiến trúc cốt lõi cho paper: [Table-Aware Online KG](reports/kien_truc_table_kg.md).

Với FinQA, runner mặc định dùng bảng chuẩn hóa chính thức. Dùng
`--finqa-table-format raw` để đánh giá parser bảng phân cấp trên `table_ori`.
Output FinQA lưu cả `execution_accuracy` (ratio/percentage tương đương) và
`official_execution_accuracy` (quy ước chấm gốc của FinQA).

Hai pilot split cân bằng, có thể commit và chạy ngay trên server, nằm trong
[`benchmarks/finqa/`](benchmarks/finqa/). Xem
[`benchmarks/README.md`](benchmarks/README.md) để tái tạo đúng seed và kiểm tra
phân bố.

Pipeline hợp nhất **table + text + web** thành một Knowledge Graph tạm dựng
**online (per-query, on-the-fly)** — khác với các framework build-time KG như HydraRAG
(dựa trên Freebase/Wikidata có sẵn). Từ KG tạm này, hệ thống sinh nhiều **reasoning path**
ứng viên, chuyển mỗi path thành **code Python giới hạn** hoặc **typed Numerical
IR**, **chạy thử (execute) trước**, rồi dùng chính kết quả thực thi để **đánh giá
và chọn path đáng tin nhất**.

## Kiến trúc

```
Question
   │
   ▼
[1] Coarse Retrieval        src/retrieval/coarse_retrieval.py   (BM25, lọc top-k trước khi extract)
   ▼
[2] Entity/Relation Extractor  src/extraction/extractor.py       (table/text/web -> triples có provenance)
   ▼
[3] Online KG Builder       src/kg/builder.py                   (hợp nhất triples + entity resolution)
   ▼
[4] Path Planner            src/planning/planner.py             (sinh N candidate reasoning path)
   ▼
[5] Program Synthesizer     src/execution/                      (path -> Python hoặc typed Numerical IR)
   ▼
[6] Sandbox Executor        src/execution/sandbox.py            (CHẠY THỬ code, timeout, an toàn)
   ▼
[7] Path Evaluator          src/evaluation/evaluator.py         (grounded consistency:
   │                                                              evidence -> provenance diversity ->
   │                                                              path agreement -> length penalty)
   ▼
[8] Answer Synthesizer      src/evaluation/answer_synthesizer.py
```

Orchestrator: `src/pipeline.py`

Mỗi lần chạy pipeline đầy đủ còn có thể lưu `full_kg`: toàn bộ canonical node,
directed multi-edge, relation, provenance, alias, resolution log và rejection
log. Có thể dựng hình audit bằng `src.visualization.render_full_kg`.

### Grounded consistency và provenance diversity

Sandbox bọc KG bằng `TracingKG`, vì vậy mỗi path chỉ nhận evidence từ những
cạnh KG mà code thực sự truy vấn. Output không khớp bất kỳ cạnh evidence nào bị
loại là `ungrounded`; LLM không được tự khai báo nguồn.

Evaluator gom evidence của các path cho cùng output theo `(source_type,
source_id)`, không đếm nhiều triple trong cùng nguồn thành nhiều nguồn độc lập.
Provenance bonus mặc định:

```text
table support       +2.00
text support        +1.00
web support         +0.25
table + text bonus  +1.50
```

Vì vậy thứ tự ưu tiên là `TABLE + TEXT > TABLE only > TEXT only > WEB only`.
Path agreement vẫn được dùng nhưng chỉ là tín hiệu phụ; nhiều path lặp cùng một
lỗi từ một nguồn không thể thắng output có evidence table và text độc lập.

### Chuẩn hoá KG theo 4 tầng

`src/kg/normalization.py` chuẩn hoá relation và entity trước khi planning:

1. lexical: Unicode/case/whitespace/punctuation và camelCase → snake_case;
2. ontology: alias xác định như `hasNationality → nationality`,
   `Moroccan → Morocco`, `Bác Hồ → Hồ Chí Minh`;
3. structural: bỏ tiền/hậu tố tên CLB có kiểm soát, ví dụ
   `Cerro Porteño ≡ Club Cerro Porteño`, trước khi cần semantic;
4. semantic: similarity có threshold mặc định `0.93`, chỉ so các node cùng vai
   trò và bỏ qua ngày/số. Có thể truyền hàm cosine embedding qua
   `EntityResolver(similarity_fn=...)`; mặc định dùng string similarity bảo thủ.

Mọi lần merge được lưu trong `kg.resolution_log` với tầng, alias, canonical và
score để audit; `kg.summary()` trả thêm thống kê entity resolution.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # điền API key + chọn LLM_PROVIDER
```

## Đổi LLM provider

Hệ thống hỗ trợ nhiều LLM qua cơ chế provider (`src/llm/providers/`), chọn bằng
biến môi trường `LLM_PROVIDER` trong `.env` — **không cần sửa code** ở bất kỳ
module nào khác (extraction/planning/execution/evaluation đều chỉ gọi
`llm_call()` / `llm_call_json()`):

| `LLM_PROVIDER` | SDK cần cài | Biến env liên quan |
|---|---|---|
| `anthropic` (mặc định) | `anthropic` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| `openai` | `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| `gemini` | `google-genai` | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| `deepseek` | `openai` | `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL` |
| `groq` | `openai` | `GROQ_API_KEY`, `GROQ_MODEL` |
| `nvidia_nim` | `openai` | `NVIDIA_API_KEY`, `NVIDIA_NIM_MODEL` |
| `openrouter` | `openai` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` |
| `openai_compatible` | `openai` | `COMPAT_BASE_URL`, `COMPAT_MODEL`, `COMPAT_API_KEY` — dùng cho Ollama, vLLM, LM Studio, DeepSeek, Qwen, OpenRouter... |

Ví dụ chạy local với Ollama:
```bash
# .env
LLM_PROVIDER=openai_compatible
COMPAT_BASE_URL=http://localhost:11434/v1
COMPAT_MODEL=llama3.1
```

Ví dụ dùng Groq:

```bash
# .env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b

python -m src.llm.test_prompt "Trả lời ngắn gọn: 1+1 bằng bao nhiêu?" --max-tokens 1024
```

Với `openai/gpt-oss-20b`, free plan hiện công bố 30 RPM, 1.000 RPD,
8.000 TPM và 200.000 TPD. Rate limit áp dụng ở cấp organization và có thể
thay đổi; Groq Console là nguồn chính xác cho tài khoản của bạn.

Fallback đã kiểm tra cho workload JSON/IR là Gemini stable:

```bash
# .env
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-3.8-flash
```

Đối với benchmark chính thức, không đổi provider giữa các câu trong cùng một
run. `--resume` chỉ được dùng với đúng JSONL có manifest cùng fingerprint
(model/provider, code revision, input checksum, resource revision và cấu hình);
nếu provider lỗi quota, giữ nguyên mọi tham số rồi resume, hoặc tạo run mới với
`RUN_TAG`/output mới có tên provider-model rõ ràng. `openrouter/free` chỉ phù hợp
smoke test vì model thực tế và availability có thể thay đổi.

Ví dụ dùng DeepSeek V4 Flash qua OpenRouter, với reasoning của OpenRouter:

```bash
# .env -- API key chỉ lưu trong file này, không commit.
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=deepseek/deepseek-v4-flash
OPENROUTER_REASONING_ENABLED=true
OPENROUTER_SITE_URL=http://localhost
OPENROUTER_APP_NAME=Online KG RAG
```

`OPENROUTER_REASONING_ENABLED=true` làm client gửi trường
`reasoning: {"enabled": true}`. Tắt biến này nếu model/route không hỗ trợ
reasoning hoặc khi muốn kiểm soát chặt chi phí và độ trễ benchmark.

Ví dụ dùng NVIDIA NIM hosted API:

```bash
# .env
LLM_PROVIDER=nvidia_nim
NVIDIA_API_KEY=nvapi-...
NVIDIA_NIM_MODEL=openai/gpt-oss-20b

python -m src.llm.test_prompt "Trả lời ngắn gọn: 1+1 bằng bao nhiêu?" --max-tokens 1024
```

Tạo key từ trang model trên build.nvidia.com. Hosted prototype endpoint miễn
phí phù hợp để thử nghiệm; NVIDIA không công bố một quota RPD cố định trên
trang model, nên kiểm tra giới hạn thực tế trong tài khoản NVIDIA.

Đổi provider ngay trong code (không qua `.env`), ví dụ để so sánh 2 model:
```python
from src.llm.client import set_provider, llm_call

set_provider("openai", model="gpt-4o")
llm_call("...")

set_provider("anthropic", model="claude-sonnet-4-6")
llm_call("...")
```

Thêm provider mới: tạo file trong `src/llm/providers/`, kế thừa `LLMProvider`
(`src/llm/base.py`), chỉ cần implement `complete()`, rồi đăng ký vào
`_REGISTRY` trong `src/llm/factory.py`.

Mở project trong VS Code: `code .` (đảm bảo interpreter đang trỏ vào `.venv`,
xem `.vscode/settings.json`).

## Chạy

```bash
python -m src.pipeline
```

Sẽ chạy demo với dữ liệu mẫu nhỏ (table + text + web) hard-code sẵn trong
`src/pipeline.py`. Thay `table_rows` / `text_passages` / `web_snippets` bằng
dữ liệu thật (VD từ OTT-QA/HybridQA) khi tích hợp.

## Chạy benchmark HybridQA, FinQA và HiTab

Không cần cài MySQL, PostgreSQL, Neo4j hay một database server nào. `OnlineKG`
dùng NetworkX trong bộ nhớ và được dựng lại cho từng câu hỏi. Dataset chỉ là các
file JSON lưu trong `data/` (thư mục này đã được git-ignore).

### Đồng bộ dataset

Chạy từ thư mục gốc của project. Lệnh dưới đây sẽ clone dataset nếu chưa có,
hoặc cập nhật repository hiện có bằng fast-forward:

```bash
cd /workspace/kiennt/online-kg-rag

if [[ -d data/HybridQA/.git ]]; then
   git -C data/HybridQA pull --ff-only
else
   git clone https://github.com/wenhuchen/HybridQA data/HybridQA
fi

if [[ -d data/WikiTables-WithLinks/.git ]]; then
   git -C data/WikiTables-WithLinks pull --ff-only
else
   git clone https://github.com/wenhuchen/WikiTables-WithLinks data/WikiTables-WithLinks
fi

if [[ -d data/FinQA/.git ]]; then
   git -C data/FinQA pull --ff-only
else
   git clone https://github.com/czyssrs/FinQA data/FinQA
fi
```

Kiểm tra nhanh các file đầu vào sau khi đồng bộ:

```bash
test -f data/HybridQA/released_data/dev.json
test -d data/WikiTables-WithLinks/tables_tok
test -d data/WikiTables-WithLinks/request_tok
test -f data/FinQA/dataset/dev.json
```

### HybridQA — bắt đầu bằng oracle context

Tải câu hỏi và bảng/passage chính thức:

```bash
git clone https://github.com/wenhuchen/HybridQA data/HybridQA
git clone https://github.com/wenhuchen/WikiTables-WithLinks data/WikiTables-WithLinks
```

Chạy smoke test một câu từ dev split:

```bash
python -m src.run_dataset \
  --dataset hybridqa \
  --input data/HybridQA/released_data/dev.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --limit 1 \
  --n-paths 3 \
  --max-replans 0 \
  --output data/results/hybridqa-dev.jsonl
```

Đây là **oracle-context mode**: mỗi câu hỏi dùng đúng table và tập passage liên
kết bởi HybridQA; BM25 hiện tại chỉ xếp hạng passage bên trong context đó. Nên
ổn định extraction, KG, planning và execution ở chế độ này trước khi đánh giá
open-domain retrieval. Adapter cũng đọc được JSON export có object `table` đã
nhúng trực tiếp, khi đó không cần `--tables-dir`; nếu summary passage cũng được
nhúng trong cell thì không cần `--passages-dir`.

> Cấu trúc một số snapshot của WikiTables-WithLinks có thể khác tên thư mục.
> Hãy trỏ `--tables-dir` và `--passages-dir` tới các thư mục thực sự chứa file
> `<table_id>.json`.

### Baseline HybridQA dùng cho paper

Baseline đối chứng là **Oracle-context BM25 + Direct LLM**. Với mỗi câu hỏi,
baseline giữ nguyên bảng oracle do HybridQA cung cấp, dùng BM25 chọn top-5
passage trong tập passage liên kết, rồi đưa toàn bộ context vào đúng một lần gọi
LLM. Baseline không dựng KG, không lập kế hoạch, không sinh code và không dùng
evaluator. Gold answer chỉ được đọc sau khi dự đoán để tính metric, không xuất
hiện trong prompt.

Smoke test 10 câu:

```bash
python -m src.run_hybridqa_baseline \
  --input data/HybridQA/released_data/dev.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-vanilla-rag-dev.jsonl \
  --passage-top-k 5 \
  --max-context-chars 24000 \
  --max-output-tokens 1024 \
  --temperature 0 \
  --limit 10
```

Khi chạy toàn bộ dev split, bỏ `--limit`. Có thể thêm `--resume` để tiếp tục từ
file JSONL đang có; khi đó `--limit` là số câu mới cần chạy. Lần chạy đầu tạo
`*.jsonl.manifest.json`; resume chỉ được phép khi fingerprint của model, code,
input, resource và cấu hình khớp. Runner cũng tạo `*.summary.json` chứa EM và
token-F1 theo cách chuẩn hóa của evaluation script HybridQA, cả dạng tỷ lệ và phần trăm.

Để chạy lại đúng một câu đã biết, thêm `--example-id <question_id>`.

Để so sánh công bằng trong paper, chạy baseline và Online-KG trên cùng split,
cùng provider/model, cùng giới hạn output token và `temperature=0`. Báo cáo ít
nhất EM, F1, số LLM call/câu và latency trung bình. Bảng kết quả đề xuất:

| Method | Context | EM | F1 | LLM calls/question | Latency |
|---|---|---:|---:|---:|---:|
| BM25 + Direct LLM | Oracle table + top-5 passages | — | — | 1 | — |
| Online-KG (ours) | Cùng oracle context | — | — | đo từ log | — |

Đây là baseline kiểm soát nội bộ, không phải kết quả SOTA đã công bố. Nếu paper
so sánh với nghiên cứu trước, cần bổ sung riêng các số chính thức từ HybridQA và
ghi rõ khác biệt về model, split và retrieval setting.

### Bộ baseline thống nhất

Runner `src.run_baselines` hỗ trợ các phương án:

| Method | Mô tả |
|---|---|
| `direct_llm` | Bảng oracle + passage BM25, một LLM call |
| `flat_table_bm25` | Flatten từng row, trộn với passage rồi BM25 top-k |
| `online_kg_path_text` | Dựng KG và sinh path dạng text, không sinh/thực thi code |
| `oracle_evidence` | Chỉ dùng supporting facts do dataset annotate |
| `path_consistency` | Online-KG nhưng chọn output bằng số path đồng ý |
| `numerical_ir` | Online-KG + typed numerical IR có operator đóng và provenance |
| `online_kg` | Pipeline đầy đủ với grounded consistency |

### Benchmark HybridQA 1500: Chia Shard, Theo dõi Tqdm & Đối sánh Direct LLM

Tập benchmark 1500 mẫu phân tầng của HybridQA được lưu trữ trong [`benchmarks/hybridqa/`](benchmarks/hybridqa/):
* **Tập tổng:** `benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027.json` (1500 mẫu từ `dev.traced.json`).
* **Các Shard:** Chia đều thành 8 shard cân bằng phân tầng (*stratified reasoning*):
  * `shard01` đến `shard07`: Mỗi shard gồm **200 mẫu**.
  * `shard08`: Gồm **100 mẫu**.

Tái tạo hoặc xuất mới bộ dữ liệu và các shard bằng lệnh:
```bash
python3 -m src.sample_hybridqa \
  --input data/HybridQA/released_data/dev.traced.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027.json \
  --size 1500 \
  --shard-size 200 \
  --seed 2027 \
  --require-answer-node \
  --stratify-reasoning
```

#### Chạy benchmark từ Shard bằng script runner `scripts/run_hybridqa_shard.sh`

Script [`scripts/run_hybridqa_shard.sh`](scripts/run_hybridqa_shard.sh) hỗ trợ:
1. **Cấu hình số luồng chạy song song:** Qua `--workers <1..8>` (hoặc `-w`), tối đa là 8 luồng (nếu truyền > 8 sẽ tự động điều chỉnh về 8).
2. **Theo dõi tiến độ trực quan bằng `tqdm`:** Tích hợp thanh tiến trình sạch sẽ (`--quiet-records`), cập nhật tức thời EM% và số lượt gọi LLM trung bình.
3. **Tự động đối sánh với `direct_llm`:** Chạy phương pháp được chọn song song đối chứng với `direct_llm` trên cùng shard, sau đó xuất bảng Markdown so sánh chi tiết.
4. **Ghi log đầy đủ:** Ghi nhận Exact Match (EM), Semantic Exact Match (ACC), F1, số lần gọi LLM (`total_llm_calls`, `mean_llm_calls`), thời gian chạy (`wall_time_ms`, `llm_latency_ms`) vào các file `.jsonl` và `.summary.json`.

**Các câu lệnh mẫu:**

* Chạy Shard 01 với 8 luồng song song, đối sánh `online_kg_path_text` với `direct_llm`:
  ```bash
  ./scripts/run_hybridqa_shard.sh --shard 01 --workers 8
  ```

* Chạy thử nhanh 5 mẫu đầu của Shard 02 với 4 luồng:
  ```bash
  ./scripts/run_hybridqa_shard.sh --shard 02 --workers 4 --limit 5
  ```

* Chạy phương pháp Full Online KG (`online_kg`) trên Shard 01 với 8 luồng:
  ```bash
  ./scripts/run_hybridqa_shard.sh --shard 01 --workers 8 --method online_kg
  ```

* Chạy tuần tự toàn bộ 8 Shard (1500 mẫu) với 8 luồng:
  ```bash
  ./scripts/run_hybridqa_shard.sh --shard all --workers 8
  ```

* Chạy trực tiếp qua Python module `src.run_baselines`:
  ```bash
  python3 -m src.run_baselines \
    --dataset hybridqa \
    --method online_kg_path_text \
    --input benchmarks/hybridqa/hybridqa-dev-table-text-traced-1500-seed2027-shard01.json \
    --tables-dir data/WikiTables-WithLinks/tables_tok \
    --passages-dir data/WikiTables-WithLinks/request_tok \
    --output data/results/shard01_online_kg_path_text.jsonl \
    --top-k 5 --second-stage-k 3 --n-paths 3 \
    --max-workers 8 --llm-max-concurrent-requests 8 \
    --quiet-records --force-progress --resume
  ```


Các phương án thực thi Online-KG dùng retrieval hai giai đoạn: BM25 theo câu hỏi,
sau đó bổ sung tối đa `--second-stage-k` passage bằng query expansion deterministic
từ numerical intent, thời gian và schema bảng. Stage 2 không gọi thêm LLM; tải API
chỉ tăng khi các passage bổ sung được đưa qua triple extractor. Dùng
`--second-stage-k 0` để tắt khi chạy ablation.

Ví dụ chạy các baseline HybridQA trên cùng 100 câu:

```bash
for method in direct_llm flat_table_bm25 online_kg_path_text path_consistency online_kg; do
  python -m src.run_baselines \
    --dataset hybridqa \
    --method "$method" \
    --input data/HybridQA/released_data/dev.json \
    --tables-dir data/WikiTables-WithLinks/tables_tok \
    --passages-dir data/WikiTables-WithLinks/request_tok \
    --output "data/results/hybridqa-${method}.jsonl" \
    --top-k 5 --temperature 0 --limit 100
done
```

Oracle Evidence của HybridQA cần split traced vì file thường không có annotation
`answer-node`:

```bash
python -m src.run_baselines \
  --dataset hybridqa \
  --method oracle_evidence \
  --input data/HybridQA/released_data/dev.traced.json \
  --tables-dir data/WikiTables-WithLinks/tables_tok \
  --passages-dir data/WikiTables-WithLinks/request_tok \
  --output data/results/hybridqa-oracle-evidence.jsonl \
  --temperature 0 --limit 100
```

FinQA dùng cùng runner. Không dùng `--limit 100` cho số liệu pilot vì lệnh đó
chỉ lấy 100 record đầu. Dùng split cân bằng đã commit:

```bash
python -m src.run_baselines \
  --dataset finqa \
  --method flat_table_bm25 \
  --input benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --output data/results/finqa-flat-table.jsonl \
  --top-k 5 --temperature 0 --resume
```

Ablation typed numerical IR giữ nguyên retrieval, KG, planner và grounded
evaluator; chỉ thay Python tự do bằng chương trình JSON với các operator
`lookup`, `const`, `add`, `subtract`, `multiply`, `divide`, `exp`, `compare`,
`greater`, `table_sum`, `table_average`, `table_max`, `table_min`:

```bash
python -m src.run_baselines \
  --dataset finqa \
  --method numerical_ir \
  --input benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --output data/results/finqa-balanced-100-numerical-ir.jsonl \
  --top-k 5 --n-paths 3 --max-replans 1 \
  --max-output-tokens 2048 --temperature 0 --resume
```

Các bước `lookup` đọc trực tiếp từ KG nên evidence của toán hạng được trace tự
động. `ratio` được biểu diễn bằng `divide`. Với FinQA, câu hỏi hỏi percentage
vẫn phải trả ratio thập phân theo gold annotation (ví dụ `0.57031` cho
`57.031%`); không nhân thêm 100. Symbolic fallback bị tắt trong biến thể này để
kết quả không lẫn với một cơ chế thực thi khác.

Với FinQA, runner còn báo `ir_parse_rate`, `schema_validity_rate`,
`execution_success_rate`, `operator_accuracy`, `step_accuracy`,
`grounding_precision` và `grounding_recall`. Operator và intermediate result
được căn chỉnh theo chuỗi phép toán canonical trong gold program; các bước
`lookup`/`const` không bị ép căn chỉnh theo ID. Grounding được đối chiếu riêng
với `gold_inds`. Nếu gold program không chuyển được sang IR hỗ trợ, metric cấp
bước là `null` thay vì tính thành sai. Error taxonomy chính gồm
`serialization_schema`, `pipeline_failure`, `arithmetic_execution`, `grounding`,
`operand_selection`, `operator_selection`, `operand_or_operator_selection`,
`unit_scale_or_unclassified` và `answer_rendering`. Các metric
validity/execution vẫn được giữ như chỉ số vận hành, không được xem là các lớp
reasoning error cạnh tranh với taxonomy trên.

Malformed hoặc non-JSON output không làm dừng benchmark. Nếu chỉ một candidate
IR lỗi, candidate đó nhận execution failure và các path còn lại vẫn được chấm.
Nếu lỗi xảy ra ở extraction/planning khiến cả câu không thể tiếp tục, runner ghi
một record có `run_status="failed"`, accuracy bằng 0 và error category tương
ứng, flush JSONL rồi chuyển sang câu kế tiếp. `--resume` bỏ qua cả record đúng
lẫn record sai đã được ghi, bảo đảm không lặp API call ngoài ý muốn.

### Chạy FinQA theo batch song song và theo dõi tiến độ

Runner chạy các sample độc lập song song bằng thread (phù hợp với LLM HTTP
I/O). Cấu hình số worker bằng `--max-workers` hoặc biến môi trường
`BENCHMARK_MAX_WORKERS`; giá trị CLI được ưu tiên. `tqdm` hiển thị số sample đã
xong, throughput và ETA khi chạy trong terminal. Không truyền `--no-progress`
nếu muốn xem progress bar.

Số worker và số request LLM đang bay là hai giới hạn tách biệt. Mặc định đều là
8: worker vẫn có thể dựng KG/retrieval đồng thời, còn client chỉ cho tối đa 8
HTTP request tới cùng provider. Đặt `LLM_MAX_CONCURRENT_REQUESTS` cho mọi
provider hoặc, ví dụ, `GROQ_MAX_CONCURRENT_REQUESTS=12` cho riêng Groq. Cờ
`--llm-max-concurrent-requests` có độ ưu tiên cao nhất. Hạ giới hạn này khi có
429/timeout; không cần hạ `--max-workers` trước.

Ví dụ chạy batch đầu 50 câu của shard 02 trên OpenRouter/DeepSeek:
```bash
LLM_PROVIDER=openrouter \
OPENROUTER_MODEL=deepseek/deepseek-v4-flash \
OPENROUTER_REASONING_ENABLED=false \
BENCHMARK_MAX_WORKERS=8 \
LLM_MAX_CONCURRENT_REQUESTS=8 \
.venv/bin/python -m src.run_baselines \
  --dataset finqa \
  --method online_kg \
  --input benchmarks/finqa/finqa-dev-1to2step-core-100-seed2027-shard02.json \
  --output data/results/finqa-shard02-online-kg.jsonl \
  --limit 50 \
  --max-workers 8 \
  --llm-max-concurrent-requests 8 \
  --n-paths 3 \
  --max-replans 1 \
  --top-k 5 \
  --second-stage-k 3 \
  --max-output-tokens 1024
```

Để chạy batch 50 tiếp theo, giữ nguyên `--output`, thêm `--resume` và tiếp tục
giữ `--limit 50`. Runner sẽ đọc các ID đã có trong JSONL rồi chỉ xử lý 50 ID
chưa chạy; kết quả và `*.summary.json` được cập nhật nối tiếp.

```bash
LLM_PROVIDER=openrouter \
OPENROUTER_MODEL=deepseek/deepseek-v4-flash \
OPENROUTER_REASONING_ENABLED=false \
BENCHMARK_MAX_WORKERS=8 \
.venv/bin/python -m src.run_baselines \
  --dataset finqa \
  --method online_kg \
  --input benchmarks/finqa/finqa-dev-1to2step-core-100-seed2027-shard02.json \
  --output data/results/finqa-shard02-online-kg.jsonl \
  --limit 50 \
  --resume \
  --max-workers 8 \
  --n-paths 3 \
  --max-replans 1 \
  --top-k 5 \
  --second-stage-k 3 \
  --max-output-tokens 1024
```

Khởi đầu với 6--8 worker, rồi tăng dần nếu provider không trả 429/timeout.
Rate pacing, retry và JSONL logging vẫn được áp dụng cho từng LLM call.

Mỗi output JSONL có metric theo dataset, một `*.summary.json` và một
`*.jsonl.manifest.json`. Manifest ghi provider/model, code revision, checksum
input, revision resource, configuration và fingerprint để audit/resume. HybridQA
dùng EM/token-F1; FinQA dùng numeric execution accuracy. `program_accuracy`
hiện để `null` vì code Python path chưa được canonicalize sang DSL chính thức
của FinQA. Annotation `answer-node` của HybridQA là weak/approximate label, nên
Oracle Evidence cần được mô tả đúng như vậy trong paper.

Runner cũng ghi các chỉ số hiệu năng trên từng câu và giá trị total/mean trong
summary: `wall_time_ms`, `llm_latency_ms`, `non_llm_time_ms`, logical
`llm_calls`, `llm_api_attempts`, số call thành công/thất bại, tổng ký tự prompt
và response. Token counts để `null` cho đến khi provider-neutral interface đọc
được usage thật; không dùng phép ước lượng ký tự/token trong kết quả paper.
Rate-limit 429 được retry có backoff (mặc định tối đa 3 retry, cấu hình bằng
`LLM_RATE_LIMIT_RETRIES`) và số attempt vẫn được ghi để audit.

### FinQA

```bash
git clone https://github.com/czyssrs/FinQA data/FinQA
python -m src.run_dataset \
  --dataset finqa \
  --input data/FinQA/dataset/dev.json \
  --limit 1 \
  --n-paths 3 \
  --max-replans 0 \
  --output data/results/finqa-dev.jsonl
```

FinQA adapter giữ lại `program`, `program_re`, `gold_inds` và execution answer
để tính execution, operator/step và grounding metrics. Kết quả luôn tách metric
strict chính thức khỏi metric semantic coi ratio và percentage tương đương.

Mỗi dòng output JSONL gồm ID, question, gold answer, metadata và toàn bộ kết quả
của pipeline. Chạy `--limit 1` trước vì extraction/planning/code synthesis đều
gọi LLM; sau đó tăng dần lên 10, 100 và toàn bộ dev split.

### HiTab

HiTab kiểm tra numerical reasoning trên bảng phân cấp. Adapter vật chất hóa đầy
đủ row-header path và column-header path, đồng thời tắt LLM table enrichment để
tránh làm mất cấu trúc hoặc sinh cạnh không có căn cứ:

```bash
git clone https://github.com/microsoft/HiTab data/HiTab

python -m src.run_baselines \
  --dataset hitab \
  --method numerical_ir \
  --input data/HiTab/data/dev_samples.jsonl \
  --hitab-tables-dir data/HiTab/data/tables/raw \
  --output data/results/hitab-dev-numerical-ir.jsonl \
  --top-k 5 --n-paths 3 --max-replans 1 \
  --temperature 0 --resume
```

HiTab lưu `official_denotation_accuracy` theo scale nguyên gốc và
`denotation_accuracy` với ratio/percentage normalization. Đây là table-only
benchmark; không dùng kết quả HiTab để claim provenance diversity giữa table và
text.

### Pilot FinQA 50/100 câu trên server nội bộ

Sau khi cấu hình `COMPAT_BASE_URL`, `COMPAT_MODEL` và `COMPAT_API_KEY`:

```bash
LLM_PROVIDER=openai_compatible .venv/bin/python -m src.run_baselines \
  --dataset finqa \
  --method numerical_ir \
  --input benchmarks/finqa/finqa-dev-balanced-100-seed2027.json \
  --output data/results/finqa-dev-balanced-100-numerical-ir-internal.jsonl \
  --top-k 5 --n-paths 3 --max-replans 1 \
  --max-output-tokens 2048 --temperature 0 \
  --finqa-table-format official --resume
```

Tập 50/100 chỉ dùng cho smoke test và pilot. Số liệu cuối của paper cần chạy
toàn bộ fixed dev split sau khi đã khóa model, prompt, seed và cấu hình.

## Test

```bash
pytest tests/ -v
```

Unit/integration tests **không cần API key thật**: chúng kiểm tra graph,
normalization, sandbox, typed IR, metrics, sampling và provider factory. Chỉ các
lượt end-to-end thực sự mới cần API key hoặc server LLM nội bộ.

## Việc cần làm tiếp (TODO)

- [ ] Thay entity resolution heuristic (`src/kg/builder.py::_resolve_entities`)
      bằng LLM-based hoặc embedding-based dedup khi domain phức tạp hơn.
- [ ] Thêm LLM-plausibility scoring vào tầng 3 của `PathEvaluator`
      (hiện chỉ có length penalty).
- [ ] Viết script `scripts/download_data.sh` để tải OTT-QA/HybridQA vào `data/`
      (không commit data lớn — đã có trong `.gitignore`).
- [ ] Thêm `--no-table` / `--no-text` / `--no-web` flag ở `src/pipeline.py`
      để chạy ablation study (tham khảo pattern CLI của HydraRAG).
- [ ] Cân nhắc thêm cross-source contradiction check (tri-factor verification
      kiểu HydraRAG) nếu muốn nâng độ tin cậy khi 2 nguồn mâu thuẫn nhau.

## Ghi chú thiết kế

- **Không fork trực tiếp từ HydraRAG** vì kiến trúc lõi khác nhau: HydraRAG
  build-time (Freebase/Wikidata offline), project này runtime/on-the-fly.
  Có tham khảo pattern prompt/CLI của HydraRAG nhưng viết lại phần retrieval/KG
  từ đầu.
- **Sandbox an toàn**: code do LLM sinh chỉ được truy cập qua API giới hạn của
  `OnlineKG` (`get_neighbors`, `get_relations`, `filter`), không có `import`,
  không I/O, có timeout — xem `src/execution/sandbox.py`.
- **Nguyên tắc đánh giá path**: luôn "chạy thử trước, chấm điểm sau" — không
  bao giờ để LLM tự đoán path nào tốt chỉ dựa vào đọc văn bản path.
