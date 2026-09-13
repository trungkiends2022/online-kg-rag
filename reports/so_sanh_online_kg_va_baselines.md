---
title: "SO SÁNH ONLINE-KG VÀ CÁC BASELINE"
subtitle: "Case study HybridQA multi-hop"
date: "11/09/2026"
lang: vi-VN
---

# 1. Thiết lập thử nghiệm

Thử nghiệm sử dụng cùng một câu hỏi HybridQA cần reasoning qua text và table:

| Thuộc tính | Giá trị |
|---|---|
| Question ID | `00c4fbc89bffe739` |
| Question | What is the nationality of the manager who was born on 15 February 1968? |
| Gold answer | `Morocco` |
| Provider/model | Groq — `openai/gpt-oss-20b` |
| Retrieval | Oracle table, top-5 passages |
| Path methods | 3 candidate paths, không replan |

Chuỗi reasoning đúng:

```text
15 February 1968
    ← birth_date — Karim Bencherifa
    — nationality → Morocco
```

Direct, Flat, Iterative và Oracle dùng `temperature=0`. Hai path run được thực
hiện trước khi temperature được truyền xuyên suốt mọi module pipeline, nên dùng
provider default ở các bước extraction/planning/code. Vì vậy đây là **kết quả
thăm dò trên một case**, chưa phải bảng định lượng chính thức của paper.

# 2. Kết quả

| Method | Prediction | EM | F1 | LLM calls | Wall time | LLM time | Prompt chars |
|---|---|---:|---:|---:|---:|---:|---:|
| Direct LLM | Morocco | 1.00 | 1.00 | 1 | 3.90 s | 2.42 s | 4,903 |
| Flat-Table BM25 | Moroccan | 0.00 | 0.00 | 1 | 2.74 s | 1.37 s | 3,111 |
| Iterative Entity RAG | Moroccan | 0.00 | 0.00 | 2 | 3.46 s | 1.81 s | 6,280 |
| Oracle Evidence | Morocco | 1.00 | 1.00 | 1 | 2.71 s | 1.33 s | 3,052 |
| Path Consistency | Morocco | 1.00 | 1.00 | 14 | 147.08 s | 145.43 s | 48,897 |
| Online-KG Full | Morocco | 1.00 | 1.00 | 14 | 170.28 s | 168.69 s | 48,548 |

Token usage để trống vì abstraction provider hiện chưa trả usage tokenizer thật.
Hệ thống chủ động không suy diễn token từ số ký tự để tránh đưa số ước lượng vào
paper.

# 3. Phân tích từng phương pháp

## 3.1. Direct LLM

Direct LLM nhận bảng nguyên vẹn và năm passage BM25. Passage Karim Bencherifa
đứng đầu và bảng chứa nationality `Morocco`, nên model trả đúng chỉ với một call.

Ưu điểm là nhanh và rẻ. Hạn chế là không tạo reasoning trace hoặc evidence chain;
với case khó hơn như Walter Payton, one-shot retrieval đã bỏ passage cần thiết.

## 3.2. Flat-Table BM25

Các table rows được biến thành text và trộn chung với passages. Top-5 của run này
đều là passage, không có row table. Model chỉ nhìn thấy cách diễn đạt `Moroccan`
trong text nên trả `Moroccan` thay vì gold span `Morocco`.

Kết quả đúng về ngữ nghĩa nhưng bị official exact-match normalization chấm sai.
Failure này cho thấy flatten và retrieval chung có thể làm mất cân bằng modality:
passage chiếm toàn bộ top-k, đẩy table evidence ra ngoài context.

## 3.3. Iterative Entity RAG

Vòng đầu xác định đúng bridge entity `Karim Bencherifa`. Tuy nhiên, query vòng hai
vẫn trả cùng nhóm passage và không đưa row nationality của table vào top-5. Answer
cuối vẫn là `Moroccan`.

Baseline chứng minh sinh đúng intermediate entity chưa đủ; retrieval vòng sau
phải có cơ chế bảo đảm diversity giữa table và text.

## 3.4. Oracle Evidence

Oracle Evidence nhận supporting rows/passages từ annotation traced. Nó trả đúng
`Morocco`, dùng context nhỏ nhất và có LLM latency thấp nhất. Đây là retrieval
upper bound, không phải một hệ thống triển khai thực tế.

Khoảng cách giữa Oracle và các retriever cho biết phần lỗi do evidence selection.

## 3.5. Path Consistency

Phương pháp dựng KG, sinh ba paths và chọn output được nhiều path đồng ý nhất.
Ba path đồng ý với `Morocco`, nên best score theo voting là 3.0. Executed value và
answer cuối đều đúng.

Phương pháp có reasoning trace nhưng không phân biệt ba path cùng dựa trên một lỗi
với ba path có evidence độc lập.

## 3.6. Online-KG Full

Online-KG tạo 103 nodes và 111 edges. Best path thực hiện:

```text
birth date → Karim Bencherifa → nationality → Morocco
```

Executed value là `Morocco`; answer cuối trùng gold. Grounded score là 8.58 do
answer có evidence thực thi và provenance support. Không cần replan.

Online-KG cung cấp mức giải thích và kiểm chứng tốt nhất, nhưng đắt hơn Direct LLM:
14 logical calls và wall time cao hơn khoảng 43.7 lần trên case này.

# 4. So sánh hiệu năng

| Nhóm | Nhận xét |
|---|---|
| RAG trực tiếp | 1–2 calls, khoảng 2.7–3.9 giây |
| KG/path methods | 14 calls, khoảng 147–170 giây |
| Bottleneck | Hơn 98% wall time của path methods nằm ở LLM |
| Xử lý cục bộ | Khoảng 1.6 giây cho retrieval, KG, sandbox và ghi kết quả |

Chênh lệch giữa Path Consistency và Online-KG trong một run không đủ để kết luận
grounded evaluator chậm hơn, vì hai phương pháp được chạy độc lập và extraction/
generation có biến động. Đánh giá chính thức cần tái sử dụng cùng cached KG và
cùng candidate paths, sau đó chỉ thay evaluator.

# 5. Kết luận từ case study

1. Direct LLM có thể thắng trên câu dễ khi cả hai evidence đã nằm rõ trong context.
2. Flattened retrieval có nguy cơ chọn một modality duy nhất và mất table evidence.
3. Iterative retrieval cần modality-aware retrieval, không chỉ query rewriting.
4. Path Consistency và Online-KG đều suy ra đúng answer trong case này.
5. Online-KG cung cấp evidence-grounded reasoning nhưng chi phí LLM hiện rất cao.
6. Extraction là phần cần cache và song song hóa trước khi chạy benchmark lớn.

# 6. Yêu cầu cho bảng paper chính thức

- Chạy cùng danh sách example IDs trên mọi method.
- Truyền `temperature=0` xuyên suốt mọi module.
- Cache retrieval, extracted triples, normalized KG và candidate paths.
- Path Consistency và Online-KG phải dùng đúng cùng candidates.
- Báo mean, median, p95 latency; tổng calls; API attempts; failure rate.
- Báo EM/F1 trên toàn split, không kết luận từ một case.
- Bổ sung retrieval recall, executable-path rate và grounded-answer rate.
- Lấy token usage thật từ LLM nội bộ hoặc provider response trước khi báo chi phí.

