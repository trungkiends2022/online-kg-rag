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
[7] Path Evaluator          src/evaluation/evaluator.py         (chấm điểm DỰA TRÊN kết quả execute:
   │                                                              executability -> self-consistency ->
   │                                                              length penalty)
   ▼
[8] Answer Synthesizer      src/evaluation/answer_synthesizer.py
```

Orchestrator: `src/pipeline.py`

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
| `openai_compatible` | `openai` | `COMPAT_BASE_URL`, `COMPAT_MODEL`, `COMPAT_API_KEY` — dùng cho Ollama, vLLM, LM Studio, DeepSeek, Qwen, OpenRouter... |

Ví dụ chạy local với Ollama:
```bash
# .env
LLM_PROVIDER=openai_compatible
COMPAT_BASE_URL=http://localhost:11434/v1
COMPAT_MODEL=llama3.1
```

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
