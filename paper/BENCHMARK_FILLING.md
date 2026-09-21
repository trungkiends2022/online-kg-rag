# Điền kết quả benchmark

Các ô `TBD` trong `main.tex` nằm ở `Results and Error Analysis`. Chỉ thay chúng
sau khi một run đã hoàn tất trên fixed split với cùng model, prompt, decoding,
và retrieval configuration giữa các phương án so sánh.

## Bảng kết quả chính

- HybridQA: dùng `exact_match`, `f1`, `mean_llm_calls`, và
  `mean_wall_time_ms` từ file `*.summary.json`; đổi latency từ milliseconds sang
  seconds khi điền bảng.
- FinQA: dùng `official_execution_accuracy` làm primary metric và
  `execution_accuracy` làm secondary diagnostic. Không thay metric primary bằng
  metric ratio/percentage-equivalent.
- HiTab: dùng `official_denotation_accuracy` làm primary metric và
  `denotation_accuracy` làm secondary diagnostic.

## Ablation và audit

Chạy các configuration trên cùng danh sách ID. `--second-stage-k 0` tắt stage 2.
Lưu retrieval trace của từng example để tính:

- anchor coverage: tỷ lệ example có `entity_anchor.bridge_entities` không rỗng;
- bridge recall: trong các example anchorable, tỷ lệ passage chứa bridge entity
  được chọn vào context; cần định nghĩa chính xác passage gold/linked trước khi
  báo cáo;
- cross-modal paths: tỷ lệ selected path có cả `table` và `text` trong
  `path_metrics.path_source_types`.

Mọi bảng phải kèm model identifier, commit hash, prompt/configuration, exact
input split, số example hoàn thành và số failed example. Chạy paired bootstrap
trên các prediction theo ID trước khi viết claim về chênh lệch giữa methods.
