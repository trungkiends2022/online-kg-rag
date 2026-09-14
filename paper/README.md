# Bản thảo ACIIDS 2027

Đây là khung bản thảo tiếng Anh, chưa phải bài hoàn chỉnh để nộp. Phần related work, trích dẫn, thực nghiệm và thông tin tác giả còn thiếu. Chưa khẳng định novelty hoặc cải thiện accuracy.

## Overleaf

Nhập `reports/aciids2027-overleaf.zip` bằng chức năng upload project của Overleaf, chọn `main.tex` làm main document và pdfLaTeX làm compiler. File ZIP chứa class/style chính thức của Springer. Có thể sửa trực tiếp các file nguồn trong thư mục này rồi đóng gói lại.

## Quy định đã kiểm tra ngày 13/09/2026

- ACIIDS: tiếng Anh, LNCS/LNAI, PDF; 12–15 trang bao gồm hình, bảng, references; tối đa 25 trang và có thể phát sinh phí vượt trang; hạn hiện công bố 30/09/2026; nộp qua EasyChair.
- Nguồn: https://aciids.pwr.edu.pl/2027/submit.html
- Template chính thức: https://link.springer.com/series/558/information-for-authors-and-editors
- Template tải về chứa `llncs.cls` và `splncs04.bst`. Không chỉnh margin/font để ép số trang. Kiểm tra lại hướng dẫn bibliography mới nhất khi hoàn thiện camera-ready.
- Trang submission đã đọc chưa nêu rõ yêu cầu ẩn danh; cần xác minh trước khi điền bản nộp, không tự suy ra double-blind.

## Phân bổ dự kiến 14 trang

Introduction 1.5; Related Work 1.5; Problem 0.5; Method 4; Experimental Setup 1.5; Results/Error Analysis 3; Limitations/Conclusion 0.5; References 1.5. Điều chỉnh theo số trang PDF thật, không kéo dài bằng nội dung lặp.

## Công việc cần hoàn thành

1. Chốt đóng góp chính và đối chiếu literature từ paper gốc.
2. Audit mô tả với code, đặc biệt evaluator, provenance, sandbox và numerical IR. Tài liệu trong reports có thể phản ánh phiên bản cũ.
3. Chốt tập câu hỏi và cấu hình trước khi chạy so sánh; tách dev để phát triển khỏi tập đánh giá cuối.
4. Chạy các baseline cùng model/context; đo correctness, latency, model calls và ablation. Không chạy API trả phí chỉ để biên soạn bản thảo.
5. Điền bảng kết quả từ artifact có revision/config rõ ràng, không suy rộng từ case đã debug.
6. Thêm references đã xác minh, hình kiến trúc, pseudocode, thông tin tác giả và các khai báo theo yêu cầu nhà xuất bản.

## Bằng chứng đã đọc

- `README.md` và `reports/kien_truc_table_kg.md` của repository.
- `data/results/finqa-dre-2002-dividend-percent-online-kg-groq.jsonl.summary.json`: một mẫu, execution_accuracy 0.0, 14 model calls, 173548.46 ms; không có official_execution_accuracy. Chỉ là quan sát debug.

Khung hiện tại không bao hàm một cuộc audit code đầy đủ hoặc literature review. Các nội dung chưa được xác minh đã được ghi rõ trong bản thảo.
