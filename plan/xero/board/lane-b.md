# Làn B: custom field, endpoint, nút trên form (P1)

Luật của bảng: `README.md` cùng thư mục. Kế hoạch: `plan/xero/PLAN.md` (luật 9, 10). Kiến thức: `docs/xero/09`, mục "Giao diện: Desk, không SPA".

Không đụng `integrations/`, `tasks/`, `lab_xero/`, `overrides/`, `hooks.py`.

| Bước | Việc | Phụ thuộc | Trạng thái |
|---|---|---|---|
| B0 | **Kết nối bằng code** (làm trước tiên: nó mở khóa việc chạy thử). `setup/xero_connection.py`: hàm `apply()` chạy lại an toàn: tạo hoặc cập nhật bản ghi Connected App với **tên cố định** `xero` (provider name "Xero", authorization URI, token URI, bốn scope của `docs/xero/09`), lấy `client_id` và `client_secret` từ site config (`frappe.conf`), không bao giờ từ repo; điền `Lab Xero Settings` (connected app, connected user, mã tài khoản, mã thuế) cũng từ site config. Thiếu key nào thì bỏ qua phần đó và in ra thiếu gì, không ném lỗi làm hỏng migrate. Kiểm tra trong source cách đặt tên cố định cho một tài liệu trước khi dùng (không đoán API). Trong tóm tắt: ghi Redirect URI cố định để con người đăng ký bên Xero, và các lệnh `set-config` (mỗi lệnh kèm giải thích; từ ba lệnh thì một script tạm, AGENTS.md A18). Nếu con người đã tạo tay một Connected App khác: nói rõ, không xóa nó | H3 (DocType `Lab Xero Settings`) cho phần Settings; phần Connected App không phụ thuộc gì | TODO |
| B1 | `setup/customizations.py`: hàm `apply()` tạo các custom field trên Customer và Sales Order (danh sách ở `PLAN.md`), chạy lại an toàn | — | TODO |
| B2 | `api/xero.py`: `retry_sync(sales_order)` và `refresh(sales_order)`. POST, kiểm tra quyền ghi trên đơn, chỉ xếp job, không gọi Xero. Retry trên đơn đã `Synced` → `LabConflictError` | — (dùng tên trong bảng "Tên dùng chung") | TODO |
| B3 | `public/js/sales_order.js`: nút "Retry" (hiện khi `lab_xero_sync_status` là `Failed`) và "Refresh from Xero" (hiện khi đã có `lab_xero_invoice_id`), gọi hai endpoint trên | B2 | TODO |

## Cần thêm vào hooks.py (làn A áp ở bước A5)

Agent của làn B ghi các dòng chính xác vào đây khi xong B0, B1 và B3 (`after_migrate` cho hai hàm `apply()`, `doctype_js` cho Sales Order):

## Ghi chú của làn

