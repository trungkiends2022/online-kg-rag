# Online-KG RAG: Path → Code → Execution-based Evaluation

Pipeline hợp nhất **table + text + web** thành một Knowledge Graph tạm dựng
**online (per-query, on-the-fly)** — khác với các framework build-time KG như HydraRAG
(dựa trên Freebase/Wikidata có sẵn). Từ KG tạm này, hệ thống sinh nhiều **reasoning path**
ứng viên, chuyển mỗi path thành **code Python**, **chạy thử (execute) trước**, rồi dùng
chính kết quả thực thi để **đánh giá và chọn path đáng tin nhất**.

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
[5] Code Synthesizer        src/execution/code_synthesizer.py   (path -> code Python query trên kg)
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

## Chạy benchmark HybridQA và FinQA

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
file JSONL đang có; khi đó `--limit` là số câu mới cần chạy. Script tạo thêm file
`*.summary.json` chứa EM và token-F1 theo cách chuẩn hóa của evaluation script
HybridQA, cả dạng tỷ lệ và phần trăm.

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
trong output metadata. Phiên bản hiện tại dùng chúng để phân tích lỗi; program
accuracy/execution accuracy chuẩn của FinQA là bước tích hợp tiếp theo.

Mỗi dòng output JSONL gồm ID, question, gold answer, metadata và toàn bộ kết quả
của pipeline. Chạy `--limit 1` trước vì extraction/planning/code synthesis đều
gọi LLM; sau đó tăng dần lên 10, 100 và toàn bộ dev split.

## Test

```bash
pytest tests/ -v
```

Các test hiện tại (`test_online_kg.py`, `test_sandbox.py`, `test_evaluator.py`,
`test_llm_factory.py`) **không cần API key thật** — chỉ test phần logic thuần
(graph, sandbox, scoring, cơ chế chọn provider). Để test end-to-end
(`src/pipeline.py`) cần API key hợp lệ của provider đang chọn trong `.env`.

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
