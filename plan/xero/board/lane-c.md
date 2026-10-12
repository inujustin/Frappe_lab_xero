# Làn C: chiều về, trạng thái invoice và credit note (P2)

Luật của bảng: `README.md` cùng thư mục. Kế hoạch: `plan/xero/PLAN.md` (luật 6–9, và hai dòng "kéo về" của bảng Idempotency). Kiến thức: `docs/xero/09`, hai mục "nửa về" và "Luồng 2".

Không đụng `integrations/` (chỉ **gọi** client của làn A), `tasks/xero_sync.py`, `hooks.py`.

| Bước | Việc | Phụ thuộc | Trạng thái |
|---|---|---|---|
| C1 | `tasks/xero_pull.py`: `pull_sales_order(sales_order)` và `pull_changes()`. Lấy invoice đã đổi kể từ `last_pull_at`, ghi đè các field `lab_xero_*` trên Sales Order; con trỏ chỉ tiến sau khi đã lưu | A2 DONE | DONE |
| C2 | `lab_xero/inbound.py`: với mỗi credit note có allocation vào một invoice của ta, upsert một `Lab Xero Credit Note` (theo `xero_credit_note_id`) và ghi một comment lên timeline của Sales Order ở lần đầu thấy. Credit note chưa áp thì bỏ qua | C1 | DONE |
| C3 | Ghi dòng `scheduler_events` cần thêm (kéo mỗi 5 phút) vào mục bên dưới | C1 | DONE |

Sau khi làn A áp dòng hook và con người migrate: DEMO 2 và DEMO 3 (làn H, H8).

## Cần thêm vào hooks.py (làn A áp)

```python
scheduler_events = {
    "cron": {"*/5 * * * *": ["lab_core.tasks.xero_pull.pull_changes"]},
}
```

Nếu đã có dict `scheduler_events`, thêm mục này vào dict hiện có. Sau khi thêm cần **migrate** (không chỉ restart) để Frappe tạo dòng lịch. Kéo mỗi 5 phút: mỗi lượt hai lời gọi (invoice, credit note), thêm một lời gọi khi có credit note mới; nằm trong hạn mức 1000 lời gọi/ngày.

## Ghi chú của làn

- Làn C do Claude nhận từ 2026-10-12.
- C1: `tasks/xero_pull.py` đã viết, chưa chạy. `pull_sales_order(sales_order)` đọc một invoice theo id; `pull_changes()` đọc các invoice đã đổi kể từ `last_pull_at` (lần đầu: chỉ các invoice của ta, theo id). Cả hai ghi đè sáu field `lab_xero_*` trên Sales Order bằng `db_set`, tiền qua `flt(value, precision)`. Con trỏ `last_pull_at` được lưu sau cùng, cùng transaction với các cập nhật; lấy lùi 120 giây khi hỏi Xero. Lấy client trước mọi lần ghi. Lỗi của client không bị bắt: job hỏng thì rollback và Frappe ghi log.
- C1 API đã đọc: `get_invoices` tại `lab_core/integrations/xero/client.py:81-96`; `db_set` nhận dict tại `frappe-bench/apps/frappe/frappe/model/document.py:1518-1531`; `precision` tại `frappe/model/base_document.py:1385`; `now_datetime`, `get_system_timezone` tại `frappe/utils/data.py:372, :389`; cách đổi giờ site sang UTC theo `frappe/integrations/doctype/token_cache/token_cache.py:74-79`.
- C2: `lab_xero/inbound.py` đã viết, chưa chạy. `apply_credit_notes(credit_notes)`: với mỗi credit note, tìm các allocation trúng invoice của ta; có thì tạo hoặc cập nhật một dòng `Lab Xero Credit Note` (tìm theo `xero_credit_note_id`, nên kéo lại không sinh dòng thứ hai), và chỉ ở lần tạo mới ghi một comment loại Info lên Sales Order. Credit note chưa áp vào invoice nào của ta: bỏ qua; nếu trước đây đã ghi mà nay hết allocation: giữ dòng, đặt số tiền áp về 0 và cập nhật trạng thái. Giới hạn mức demo: một credit note áp vào nhiều invoice của ta thì chỉ ghi invoice đầu tiên. `tasks/xero_pull.py` gọi nó ở cả hai job, và đọc lại theo id các invoice có credit note để lấy số đã ghi giảm.
- C2 API đã đọc: `get_credit_notes` tại `lab_core/integrations/xero/client.py:98-108`; `save()` tự insert tài liệu mới tại `frappe-bench/apps/frappe/frappe/model/document.py:579-580`; `add_comment` tại `:1746`.
- C3: dòng `scheduler_events` đã ghi ở mục trên. **Làn C đã xong hết các bước.**
- **Lỗ hổng thấy được, thuộc làn A/B (không phải file của làn C):** `get_client()` đòi `Lab Xero Settings.tenant_id` (`client.py:18`), nhưng chưa có code nào gọi `GET /connections` để điền nó. Cho tới khi có, mọi job (cả chiều đi lẫn chiều về) sẽ dừng ở `XeroAuthLost`.

