# Làn A: đường chính của chiều đi (P1)

Luật của bảng: `README.md` cùng thư mục. Kế hoạch và luật nghiệp vụ: `plan/xero/PLAN.md` (luật 1–5, 9). Kiến thức: `docs/xero/09`, `03`, `02`.

| Bước | Việc | Phụ thuộc | Trạng thái |
|---|---|---|---|
| A1 | Gỡ client thế chỗ và đường "sync Lab Note sang Xero" (danh sách ở `PLAN.md`, "Đã có trong code"). Con người đã yêu cầu rõ: xóa các test trong `api/test_notes.py` dựa vào đường đó. Lab Note còn lại là DocType thường với list/get/create | — | TODO |
| A2 | Client HTTP thật trong `integrations/xero/`: các hàm và class lỗi ở `PLAN.md`, "Client". Token qua `get_active_token(user=settings.connected_user)`, tenant từ `Lab Xero Settings`, timeout tường minh, không thêm package | A1 | TODO |
| A3 | `lab_xero/mapping.py` (Customer → Contact, Sales Order → Invoice) và viết lại job `tasks/xero_sync.py` cho `create_invoice` và `void_invoice`: tra bên Xero trước, chưa có mới tạo, lưu id bằng `db_set` | A2 | TODO |
| A4 | Handler mỏng `overrides/sales_order.py`: `on_submit`, `on_cancel` (chặn cancel theo luật 5), chỉ gọi `outbox.queue` | — (song song được với A2, A3) | TODO |
| A5 | `hooks.py`: thêm `doc_events` của Sales Order, và mọi dòng các làn khác ghi ở mục "Cần thêm vào hooks.py" của họ. Lời nhắc của con người cho bước này phải nêu tên `hooks.py`. **Bước này làm được nhiều lần và làm sớm được**: ngay khi làn B xong B0, con người có thể bảo làn A "áp các dòng hook của làn B vào hooks.py" để mở khóa việc kết nối, không cần chờ A4 | các dòng cần áp đã được ghi | TODO |

Sau A5 con người restart và migrate rồi chạy DEMO 1 (làn H, H7).

## Ghi chú của làn (agent viết ở đây: giả định đã dùng, thứ chưa kiểm chứng)

