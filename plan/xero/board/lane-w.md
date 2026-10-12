# Làn W: bản nghiên cứu và kịch bản demo (P5)

Luật của bảng: `README.md` cùng thư mục. Chỉ viết trong `docs/xero/`; không đụng code. Viết bằng tiếng Việt, thuật ngữ giữ tiếng Anh kèm chú giải ngắn. Mọi con số phải có nguồn (các file `docs/xero/01`–`11` đã ghi nguồn và nhãn độ tin cậy).

| Bước | Việc | Phụ thuộc | Trạng thái |
|---|---|---|---|
| W1 | `docs/xero/BAO-CAO.md`: bản nghiên cứu gửi người giao việc, đọc trong mười phút: cách tích hợp (sơ đồ), hai luồng, các lựa chọn nghiệp vụ đã quyết và lựa chọn còn lại, giới hạn (rate limit, key 6 phút, polling so với webhook, Demo Company reset), chi phí khi lên thật, khuyến nghị | — | TODO |
| W2 | `docs/xero/KICH-BAN-DEMO.md`: kịch bản từng bước cho DEMO 1, 2, 3: chuẩn bị gì, bấm gì, nhìn ở đâu, nói gì | — | TODO |
| W3 | Sau khi các demo đã chạy thật: sửa W1 và W2 theo những gì thực tế xảy ra, xóa các dấu "chưa kiểm chứng" đã được kiểm | H7, H8 | TODO |
| W4 | `docs/xero/GIAI-THICH-CODE.md`: bản để con người **dễ dàng giải thích code mà mình và AI đã viết cho tích hợp**. Phạm vi: **chỉ code của ta trong `lab_core`** thuộc kế hoạch này. Không giải thích code lõi của Frappe; chỗ nào ta dựa vào một cơ chế của Frappe thì một dòng "ta dựa vào X" là đủ. Đọc code thật (không viết từ trí nhớ), rồi: (1) một hình vẽ đường đi của hai luồng có `path:line` trong code của ta; (2) từng file của ta: nó ở đó để làm gì, từng hàm làm gì, vì sao viết như vậy; (3) riêng một mục về **transaction** trong code của ta: cái gì nằm trong transaction của lần submit, cái gì chạy sau commit, hỏng thì sao; (4) mười câu hỏi dễ bị hỏi nhất kèm câu trả lời ngắn; (5) những chỗ còn yếu, nói thẳng | A5, B3, C3 DONE | TODO |
| W5 | Khi giai đoạn 2 làm xong phần nào thì thêm mục đó vào `GIAI-THICH-CODE.md`, cùng cách viết: lớp định hình lỗi (middleware) sau PE; wrapper `@xero_atomic` và so sánh có/không SAGA sau P4 | PE, P4 (giai đoạn 2) | TODO |

## Ghi chú của làn

