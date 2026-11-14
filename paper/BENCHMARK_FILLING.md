# Điền kết quả benchmark

Các ô `TBD` trong `main.tex` nằm ở `Results and Error Analysis`. Chỉ thay chúng
sau khi một run đã hoàn tất trên fixed split với cùng model, prompt, decoding,
và retrieval configuration giữa các phương án so sánh.

## Bảng kết quả chính (Table 1: Main benchmark results)

- **HybridQA**:
  - Primary metric: `exact_match` (EM).
  - Secondary metric: `token_f1` (F1) hoặc `semantic_exact_match` (Semantic EM).
  - Performance: `mean_llm_calls` và `mean_wall_time_ms` từ file `*.summary.json`;
    đổi latency từ milliseconds sang seconds ($s$).
  - Các method so sánh: `direct_llm`, `flat_table_bm25`, `graph_retrieval_no_path`,
    `online_kg_path_text`, `online_unified_evidence_graph` (OUEG, ours), `online_kg` (Python).
- **FinQA**:
  - Dùng `official_execution_accuracy` làm primary metric và `execution_accuracy`
    (ratio/percentage-equivalent) làm secondary diagnostic.
- **HiTab**:
  - Dùng `official_denotation_accuracy` làm primary metric và `denotation_accuracy`
    làm secondary diagnostic.

## Bảng Ablation (Table 2: Ablation study)

Chạy các configuration trên cùng danh sách ID trên tập HybridQA:
- **Full OUEG**: Phương pháp đề xuất đầy đủ (`online_unified_evidence_graph`).
- **w/o suggested paths (No-Path)**: `graph_retrieval_no_path`.
- **w/ strict path filtering**: `online_kg_path_text`.
- **w/o second-stage retrieval**: chạy với cờ `--second-stage-k 0`.
- **w/o hyperlink bridge queries**: tắt mở rộng hyperlink ô bảng sang passage.
- **w/o rule-based text triples**: tắt `use_rule_text_triples`.
- **w/o lexical tiebreak**: tắt tiebreaker từ vựng cho các trường hợp `SCORE_COLLISION_TIE`.

Các cột trong Table 2:
- `EM (%)`, `F1 (%)`, `Semantic EM (%)`.
- `Ambiguity Rate (%)`: Tỷ lệ example có `ambiguity.status == "SCORE_COLLISION_TIE"`
  hoặc `ambiguity.is_ambiguous == True`.

Mọi bảng phải kèm model identifier, commit hash, prompt/configuration, exact
input split, số example hoàn thành và số failed example. Chạy paired bootstrap
trên các prediction theo ID trước khi viết claim về chênh lệch giữa methods.
