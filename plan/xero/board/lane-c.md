# Làn C: chiều về, trạng thái invoice và credit note (P2)

Luật của bảng: `README.md` cùng thư mục. Kế hoạch: `plan/xero/PLAN.md` (luật 6–9, và hai dòng "kéo về" của bảng Idempotency). Kiến thức: `docs/xero/09`, hai mục "nửa về" và "Luồng 2".

Không đụng `integrations/` (chỉ **gọi** client của làn A), `tasks/xero_sync.py`, `hooks.py`.

| Bước | Việc | Phụ thuộc | Trạng thái |
|---|---|---|---|
| C1 | `tasks/xero_pull.py`: `pull_sales_order(sales_order)` và `pull_changes()`. Lấy invoice đã đổi kể từ `last_pull_at`, ghi đè các field `lab_xero_*` trên Sales Order; con trỏ chỉ tiến sau khi đã lưu | A2 DONE | TODO |
| C2 | `lab_xero/inbound.py`: với mỗi credit note có allocation vào một invoice của ta, upsert một `Lab Xero Credit Note` (theo `xero_credit_note_id`) và ghi một comment lên timeline của Sales Order ở lần đầu thấy. Credit note chưa áp thì bỏ qua | C1 | TODO |
| C3 | Ghi dòng `scheduler_events` cần thêm (kéo mỗi 5 phút) vào mục bên dưới | C1 | TODO |

Sau khi làn A áp dòng hook và con người migrate: DEMO 2 và DEMO 3 (làn H, H8).

## Cần thêm vào hooks.py (làn A áp)

## Ghi chú của làn

