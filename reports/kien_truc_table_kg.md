# Kiến trúc Table-Aware Online KG

Tài liệu này ghi lại thiết kế cốt lõi để sử dụng trong phần Method, Implementation
và Ablation của paper. Ý tưởng trung tâm là: **không phẳng hóa bảng thành văn bản
và không giao toàn bộ việc hiểu cấu trúc bảng cho LLM**. Cấu trúc hàng–cột được
bảo toàn thành triple xác định, sau đó hợp nhất với triple text/web trong Online KG
dựng riêng cho từng câu hỏi.

## 1. Động cơ

Bảng tài chính và Wiki thường mã hóa ngữ nghĩa trong hàng, cột và header nhiều
tầng. Giá trị `.450` chỉ có nghĩa đầy đủ khi gắn với hàng `March 31`, header năm
`2002`, cột con `Dividend` và đơn vị/ngữ cảnh bảng. Relation mơ hồ như
`value_2002` có thể khiến `.450` bị nhầm với `High = 26.50` hoặc `Low = 22.92`.

## 2. Luồng kiến trúc

```text
Raw table
   ├── phát hiện header một/nhiều tầng
   ├── mở rộng column path: 2002 → Dividend ⇒ 2002_dividend
   ├── deterministic cell triples
   ├── LLM semantic triples bổ sung
   └── provenance + normalization
                  ↓
          Table-aware Online KG
                  ├── hợp nhất text/web triples
                  ├── entity resolution
                  ├── reasoning paths
                  ├── sandbox execution
                  └── grounded-consistency scoring
```

## 3. Biểu diễn bảng

FinQA được chạy với hai protocol tách biệt:

- `official`: dùng trường `table` đã chuẩn hóa, phù hợp so sánh benchmark chuẩn;
- `raw`: dùng `table_ori` để đánh giá đóng góp hierarchical-header parsing.

Không trộn kết quả hai protocol trong cùng một bảng so sánh.

### 3.1. Header một tầng

| Player | Nation | Club |
|---|---|---|
| Darlington Nagbe | United States | Columbus Crew |

Node hàng lấy từ cột định danh đầu tiên; các ô còn lại trở thành edge:

```text
(Darlington Nagbe, nation, United States)
(Darlington Nagbe, club, Columbus Crew)
```

### 3.2. Header nhiều tầng

|  | 2002 | 2002 | 2002 | 2001 | 2001 | 2001 |
|---|---|---|---|---|---|---|
| Quarter Ended | High | Low | Dividend | High | Low | Dividend |
| March 31 | 26.50 | 22.92 | .450 | 25.44 | 21.85 | .43 |

Column path được ghép từ cấp cao xuống cấp thấp:

```text
2002 + High      → 2002_high
2002 + Low       → 2002_low
2002 + Dividend  → 2002_dividend
```

Triple kết quả:

```text
(March 31, 2002_high, 26.50)
(March 31, 2002_low, 22.92)
(March 31, 2002_dividend, .450)
```

### 3.3. Hai lớp triple

1. **Deterministic structural triples**: sinh trực tiếp từ cell và column path,
   bảo đảm không mất ô, không phụ thuộc model và giữ đúng schema.
2. **LLM semantic triples**: bổ sung alias và quan hệ ngữ nghĩa cấp cao khó suy ra
   chỉ từ vị trí bảng.

Structural triples là nguồn sự thật cho truy vấn số học. Semantic triples hỗ trợ
retrieval và reasoning tự nhiên nhưng không được thay thế định danh cột.

## 4. Node, edge và provenance

Node gồm row entity, linked entity, literal số/ngày/phần trăm và contextual entity
từ text/web. Mỗi edge có dạng:

```text
(head, normalized_relation, tail, provenance)
```

Provenance chứa `source_type`, `source_id`, `raw_snippet`, `row_index`,
`column_name`, `header_path`, và tùy chọn `source_group/domain`. KG là directed
multigraph để nhiều nguồn cùng hỗ trợ một fact mà không mất provenance độc lập.

## 5. Numerical reasoning

Code chỉ dùng API KG giới hạn. Pipeline phải xử lý rõ:

- dấu phẩy, tiền tệ và phần trăm;
- cộng, trừ, nhân, chia, trung bình, tỷ lệ và percent change;
- đổi đơn vị `thousands ↔ millions ↔ billions`;
- chiều thời gian;
- không tự điền toán hạng thiếu bằng giả định.

Ví dụ FinQA đã xác nhận:

```text
TABLE: (March 31, 2002_dividend, .450)
TEXT:  (company, declared_dividend, $.455 per share)

(.455 - .450) / .450 × 100 = 1.11111%
```

## 6. Grounded consistency

Output chỉ hợp lệ khi đường thực thi đã truy cập evidence trong KG. Điểm số ưu
tiên số nguồn/triple độc lập, table support, text support, cross-modality support,
agreement, evidence precision và path ngắn. Nhiều path lặp một lỗi không được
thắng một path có table và text hỗ trợ độc lập.

## 7. Invariant bắt buộc

1. Không bỏ cell do header không đều hoặc nhiều tầng.
2. Relation cell chứa đủ column path để phân biệt giá trị.
3. Literal ngày/số không fuzzy-merge với entity.
4. Mỗi deterministic cell edge có table provenance.
5. Answer scalar phải khớp executed value.
6. Path lỗi chỉ bị loại riêng, không làm hỏng toàn câu hỏi.
7. Numeric output thiếu evidence cho toán hạng không được xem là grounded.
8. Chuyển đổi đơn vị phải xuất hiện trong execution trace.

## 8. Đóng góp đề xuất cho paper

> **Schema-Preserving Table-to-KG Construction for Query-Time Multimodal Reasoning**

Đóng góp gồm bảo toàn hierarchical header thành relation path; kết hợp deterministic
structural extraction với LLM semantic extraction; nối table–text trong KG per-query;
execution-grounded numerical reasoning; và provenance-aware cross-modal selection.
Claim phải được kiểm chứng trên toàn tập, không suy ra từ một case study.

Typed arithmetic IR và operand-level provenance là hạng mục bắt buộc tiếp theo;
edge-access tracing hiện tại chưa đủ để chứng minh mọi toán hạng đều grounded.

## 9. Ablation cần chạy

| Cấu hình | Mục tiêu đo |
|---|---|
| Flatten table → text | Chi phí của việc mất schema |
| LLM-only table triples | Độ bất ổn khi bỏ deterministic layer |
| Deterministic-only triples | Giá trị của semantic extraction |
| Header một tầng giả lập | Ảnh hưởng của việc bỏ hierarchy |
| Full hierarchical header | Hệ thống đề xuất |
| Agreement-only | So với path consistency |
| Grounded + provenance diversity | Đóng góp evaluator |

Metric: FinQA execution accuracy, HybridQA EM/F1, path success rate, calls/question,
latency, token usage và failure rate theo retrieval/extraction/planning/execution.

Với câu hỏi tỷ lệ/phần trăm, báo cáo hai metric song song:

- `execution_accuracy`: coi dạng ratio `x` và percentage-point `100 × x` là tương đương;
- `official_execution_accuracy`: giữ phép so sánh FinQA gốc sau khi làm tròn 5 số.

Không thay thế hoặc xóa official score khi dùng quy ước semantic tương đương.

## 10. Artefact kiểm chứng hiện có

- FinQA debt/unit conversion: executed `1041.531`, execution accuracy 1.
- FinQA dividend percent change: executed `1.111111...`, execution accuracy 1.
- Unit/integration tests tại thời điểm ghi tài liệu: 71 tests pass.

Đây là bản ghi kiến trúc chuẩn. Khi implementation thay đổi, invariant, ablation
và ví dụ paper trong tài liệu phải được cập nhật đồng thời.
