# BÁO CÁO KIẾN TRÚC VÀ QUY TRÌNH HỎI ĐÁP ĐA BƯỚC VỚI ĐỒ THỊ TRI THỨC TRỰC TUYẾN (ONLINE-KG PATH-TEXT PIPELINE)

---

## 1. TỔNG QUAN VÀ ĐẶT VẤN ĐỀ

### 1.1. Bối cảnh bài toán
Hỏi đáp đa bước (Multi-hop Question Answering) trên dữ liệu lai kết hợp giữa **bảng bán cấu trúc (Semi-structured Tables)** và **đoạn văn phi cấu trúc (Unstructured Text Passages)** là bài toán trọng tâm trong các hệ thống thông tin thông minh hiện đại (điển hình như tập dữ liệu HybridQA). 

Trong bài toán này, câu trả lời không thể tìm thấy nếu chỉ đọc riêng rẽ từng nguồn:
- Thông tin trong bảng cung cấp cấu trúc, đối tượng và liên kết thực thể (ví dụ: một câu lạc bộ thể thao, một sân vận động, một bệnh viện).
- Đoạn văn Wikipedia gắn kèm (thông qua hyperlink tại các ô trong bảng) cung cấp ngữ cảnh chi tiết, lịch sử, thuộc tính mở rộng mà bảng không chứa.
- Người dùng cần một hệ thống có khả năng "nhảy" (hop) chính xác từ văn bản vào hàng của bảng hoặc ngược lại để tìm ra đáp án cuối cùng.

### 1.2. Lý do chuyển dịch và loại bỏ nhánh sinh code (No-Code Path-Text)
Trước đây, các kiến trúc lai thường sử dụng LLM để sinh mã lập trình (Python/Pandas/SQL) rồi thực thi trong môi trường sandbox. Tuy nhiên, qua thực nghiệm trên tập dữ liệu thực tế, nhánh sinh code bộc lộ các hạn chế:
1. **Chi phí và độ trễ cao**: Cần nhiều vòng lặp suy luận (LLM code generation $\rightarrow$ sandbox execution $\rightarrow$ error catching $\rightarrow$ replanning) khiến thời gian xử lý và số lượng token tăng vọt.
2. **Rủi ro môi trường thực thi (Execution Overhead)**: Đòi hỏi cơ chế sandbox an toàn, dễ gặp lỗi phiên bản thư viện hoặc xung đột môi trường hệ thống.
3. **Bản chất của các câu hỏi liên kết thực thể**: Đại đa số các câu hỏi trong HybridQA bản chất là **truy vết chuỗi quan hệ ngữ nghĩa (Relational / Semantic Path Traversal)** chứ không phải tính toán số học phức tạp.

Do đó, phiên bản kiến trúc **Online-KG Path-Text Pipeline** tập trung tối đa vào việc **kết hợp sức mạnh suy luận có cấu trúc của Đồ thị tri thức (Knowledge Graph)** với **năng lực thấu hiểu ngôn ngữ tự nhiên của LLM Trọng tài (Final Judge LLM)** mà hoàn toàn không cần sinh mã thực thi.

---

## 2. KIẾN TRÚC TỔNG THỂ ONLINE-KG PATH-TEXT PIPELINE

Kiến trúc gồm 5 giai đoạn liên hoàn khép kín:

```
[Câu hỏi (User Query)]
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Truy xuất & Neo thực thể (Two-Stage Retrieval & Anchoring)│
│    - Stage 1: BM25 lọc thô Table Rows & Text Passages       │
│    - Stage 2: Mở rộng theo Hyperlink trong ô bảng           │
│    - Phân tích câu hỏi: Entity Anchors, Category Filters    │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Xây dựng Đồ thị Trực tuyến (Online KG Construction)      │
│    - Dynamic Graph: Chỉ tạo cho ngữ cảnh câu hỏi hiện tại   │
│    - Biểu diễn cấu trúc hàng bảng (Row Nodes & Edge Split)   │
│    - Nối cạnh bắc cầu siêu liên kết (linked_passage edges)  │
│    - Chuẩn hóa thực thể & Giải quyết đồng nghĩa (Aliases)   │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Lập kế hoạch & Chấm điểm đường đi (Grounded Path Planner)│
│    - Duyệt đồ thị tìm chuỗi suy luận đa bước (Multi-hop)    │
│    - Hàm tính điểm đa tiêu chí (Multi-factor Path Scoring)  │
│    - Chọn lọc Top-N đường đi có độ tin cậy cao nhất         │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Tuần tự hóa Ngữ cảnh Giới hạn (Bounded Context Builder)  │
│    - Gom Top-N Paths, Cạnh KG và Trích đoạn Text liên quan  │
│    - Cắt tỉa thông minh theo từ khóa câu hỏi (Context Clip) │
│    - Ép dung lượng trong ngưỡng an toàn (max_context_chars) │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Trọng tài Suy luận Ngôn ngữ (Final Judge LLM)            │
│    - LLM đối chiếu các đường đi với toàn bộ câu hỏi        │
│    - Trích xuất nhãn thực thể ngắn nhất (Shortest Span)     │
│    - Cơ chế Hậu xử lý & Fallback an toàn                    │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
                        [ĐÁP ÁN CUỐI CÙNG]
```

---

## 3. CHI TIẾT TỪNG THÀNH PHẦN KỸ THUẬT

### 3.1. Giai đoạn 1: Truy xuất 2 giai đoạn & Neo thực thể (Two-Stage Retrieval)
- **Truy xuất thô (Stage 1)**: Dùng BM25 đánh chỉ mục nhanh các hàng bảng và toàn bộ đoạn văn, lấy ra Top-$K$ hàng bảng và đoạn văn có điểm từ khóa cao nhất với câu hỏi.
- **Mở rộng ngữ cảnh liên kết (Stage 2)**: Tại mỗi ô trong Top hàng vừa lấy, trích xuất tất cả các siêu liên kết Wikipedia (`url`). Toàn bộ đoạn văn tương ứng với các URL này được nạp bổ sung vào bộ nhớ truy xuất.
- **Bộ neo thực thể (Entity Anchoring)**: Trích xuất các thực thể được nhắc trực tiếp (`direct_mentions`), đồng thời phát hiện các thuộc tính lọc hoặc điều kiện ràng buộc trong câu hỏi để định hướng cho bộ lập kế hoạch.

### 3.2. Giai đoạn 2: Xây dựng Đồ thị Tri thức Động (Online KG Construction)
Thay vì tạo một cơ sở dữ liệu đồ thị tĩnh khổng lồ (vốn cực kỳ tốn chi phí và khó cập nhật), hệ thống tạo một **Đồ thị Tri thức Động tại thời điểm chạy (Online Dynamic KG)** dành riêng cho câu hỏi:
- **Biểu diễn Bảng**:
  - Mỗi hàng được định danh bởi một node bản ghi: `table:<table_id>:row:<i>`.
  - Mỗi ô trong cột tạo thành cạnh quan hệ có hướng: `(row_node) --[column_name]--> (cell_value)`.
  - Các ô chứa nhiều giá trị phân cách bằng dấu phẩy được tách tự động (`derived_from_cell_split`) thành các cạnh độc lập để không bỏ sót thực thể.
- **Biểu diễn Bắc cầu Văn bản (Cross-modal Bridging)**:
  - Nếu ô bảng có siêu liên kết dẫn tới đoạn văn Wikipedia, hệ thống tạo cạnh ngữ nghĩa: `(cell_entity) --[linked_passage]--> (passage_id)`.
  - Văn bản đoạn văn gốc được lưu trong từ điển `text_contexts` kèm chỉ mục ngược tới các node.
- **Chuẩn hóa thực thể (Entity Normalization & Resolution)**:
  - Xử lý đồng nghĩa (Aliases), loại bỏ cạnh tự lặp (Self-loops), chuẩn hóa viết hoa/thường và khoảng trắng.

### 3.3. Giai đoạn 3: Lập kế hoạch và Chấm điểm chuỗi suy luận (Grounded Path Planning)
Module `GroundedPathPlanner` thực hiện duyệt đồ thị (Graph Traversal) để tìm mọi chuỗi đi hợp lệ từ thực thể câu hỏi tới thực thể đích:
$$\text{Passage Node} \longleftrightarrow \text{Cell Entity} \longleftrightarrow \text{Table Row Node} \longrightarrow \text{Target Candidate}$$

Mỗi đường đi $P$ được gán điểm số tin cậy $S(P)$ theo công thức tổng hợp:
$$S(P) = \sum_{i} w_i \cdot f_i(P)$$

Trong đó các trọng số thành phần gồm:
- **`grounded_edges`**: Điểm số chứng cứ cạnh có căn cứ từ dữ liệu gốc.
- **`hyperlink_passage_bridge` (+2.0)**: Thưởng điểm lớn khi đường đi bắc cầu thành công qua lại giữa Bảng và Đoạn văn (đặc trưng của suy luận multihop).
- **`numeric_literal_coverage` (+12.0)**: Thưởng điểm tuyệt đối nếu đường đi bao phủ chính xác các số liệu, năm, ngày tháng được hỏi trong truy vấn.
- **`relation_match` & `query_coverage`**: Đo lường tỷ lệ các từ khóa trong câu hỏi xuất hiện trên các quan hệ của đường đi.
- **`length_penalty`**: Hệ số phạt độ dài để ưu tiên chuỗi suy luận súc tích, tránh các đường đi vòng vo lãng phí ngữ cảnh.

Bộ lập kế hoạch sau đó chọn ra **Top-N** đường đi có điểm cao nhất (thường là Top 3 hoặc Top 5).

### 3.4. Giai đoạn 4: Tuần tự hóa Ngữ cảnh Giới hạn (Bounded Context Builder)
Để LLM tiếp nhận thông tin cô đọng nhất mà không bị tràn cửa sổ ngữ cảnh (Context Window Overflow):
- Toàn bộ các đường đi Top-N được chuyển thành định dạng JSON có cấu trúc gồm: `reasoning_paths`, `kg_edges`, `table_constraints`.
- Các trích đoạn văn bản liên quan được áp dụng hàm cắt tỉa thông minh (`_clip_text`): chỉ giữ lại đoạn văn ngắn (tối đa 1.400 ký tự) có tâm điểm xoay quanh các từ khóa chính của câu hỏi.
- Toàn bộ chuỗi payload được kiểm soát chặt chẽ dưới ngưỡng an toàn `max_context_chars` (mặc định 24.000 ký tự).

### 3.5. Giai đoạn 5: Trọng tài Suy luận Cuối cùng (Final Judge LLM)
LLM đóng vai trò thẩm phán tối cao (Judge):
- **Nhiệm vụ**: Đọc câu hỏi và kiểm chứng các đường đi ứng viên trong đồ thị. Lựa chọn đường đi nào thỏa mãn đồng thời cả điều kiện nêu trong đoạn văn và ràng buộc trong bảng.
- **Quy chuẩn đầu ra (Answer Contract)**:
  - Chỉ trả về chuỗi đáp án ngắn nhất (Shortest Span) hoặc giá trị số học cụ thể.
  - Không giải thích dài dòng, không sinh code.
- **Cơ chế Dự phòng An toàn (Fallback Mechanism)**:
  - Nếu phản hồi của LLM không khớp với cấu trúc mong đợi, hệ thống tự kích hoạt fallback: tự động trích xuất thực thể đích cuối cùng của đường đi có điểm cao nhất (`_fallback_path_answer`), đảm bảo hệ thống không bao giờ bị dừng đột ngột (Zero Fatal Crashes).

---

## 4. BẢNG SO SÁNH: ONLINE-KG PATH-TEXT VỚI CÁC PHƯƠNG PHÁP KHÁC

| Tiêu chí | Direct LLM (RAG Thường) | Online-KG Sinh Code (Legacy) | Online-KG Path-Text (Đề xuất) |
| :--- | :--- | :--- | :--- |
| **Cơ chế chính** | Nạp toàn bộ text & bảng vào prompt | Sinh mã Python/Pandas & chạy Sandbox | Duyệt đồ thị trực tuyến & LLM phán xử |
| **Khả năng giải thích (Explainability)** | Rất thấp (hộp đen) | Trung bình (qua đoạn code sinh ra) | **Rất cao** (có chuỗi node/cạnh minh bạch) |
| **Số lần gọi LLM / mẫu** | 1 lần | 3 – 12 lần (kèm Re-planning) | **1 – 2 lần** |
| **Thời gian phản hồi (Latency)** | Nhanh (~7s) | Rất chậm (30s – 120s) | **Ổn định (15s – 25s)** |
| **Rủi ro môi trường thực thi** | Không | Rất cao (lỗi runtime, bảo mật sandbox) | **Hoàn toàn an toàn (Không cần sandbox)** |
| **Độ chính xác trên Multi-hop** | Dễ bị ảo giác (hallucination) | Dễ lỗi cú pháp code | **Chính xác, có neo chứng cứ thực tế** |

---

## 5. MINH HỌA MỘT CA SUY LUẬN THỰC TẾ (CASE STUDY)

- **Câu hỏi**: *"What was the original name of the city with an AFL club that formed in 1989 ?"*
- **Quy trình xử lý của Online-KG Path-Text**:
  1. **Truy xuất**: Nhận diện bảng `AFL_Ontario_0` (danh sách câu lạc bộ bóng bầu dục tại Ontario).
  2. **Xây dựng Đồ thị**: 
     - Hàng chứa câu lạc bộ `High Park Demons` có năm thành lập `formed = 1989`.
     - Cột thành phố trỏ tới ô `Toronto`, mang siêu liên kết dẫn tới bài viết Wikipedia `/wiki/Toronto`.
     - Tạo cạnh bắc cầu: `(Toronto) --linked_passage--> (/wiki/Toronto)`.
  3. **Lập kế hoạch đường đi**:
     - Chuỗi suy luận: `(formed: 1989) --> (table_row) --> (city: Toronto) --> (/wiki/Toronto)`.
     - Điểm số của đường đi này đạt mức cao nhất nhờ bao phủ số `1989` và cạnh bắc cầu hyperlink.
  4. **Thẩm phán LLM**:
     - LLM đọc trích đoạn của `/wiki/Toronto` gắn với đường đi trên, tìm thấy câu: *"The city was founded as York..."*.
     - Trích xuất đáp án cuối cùng: **`York`** (Khớp hoàn toàn 100% với Ground Truth).

---

## 6. KẾT LUẬN VÀ ĐỊNH HƯỚNG

Kiến trúc **Online-KG Path-Text** đã loại bỏ hoàn toàn sự cồng kềnh, phức tạp và rủi ro của nhánh sinh mã lập trình, đồng thời giữ trọn vẹn ưu điểm cốt lõi của Đồ thị Tri thức Động:
- Đảm bảo tính minh bạch, bám sát chứng cứ thực tế (Grounded).
- Tối ưu hóa chi phí token và thời gian phản hồi.
- Dễ dàng tích hợp và mở rộng trên mọi môi trường máy chủ sản xuất.

**Các cải tiến tiếp theo đang triển khai**:
1. Thêm bộ lọc đa dạng hóa đích đến (**Target Diversity Deduplication**) để tránh việc các biến thể của cùng một thực thể chiếm hết các vị trí trong Top-N.
2. Tinh chỉnh trọng số lọc từ khóa loại câu hỏi nhằm loại bỏ bias khi câu hỏi chứa các danh từ chỉ loại (ví dụ: *county, city, country*).
