# Làn B: custom field, endpoint, nút trên form (P1)

Luật của bảng: `README.md` cùng thư mục. Kế hoạch: `plan/xero/PLAN.md` (luật 9, 10). Kiến thức: `docs/xero/09`, mục "Giao diện: Desk, không SPA".

Không đụng `integrations/`, `tasks/`, `lab_xero/`, `overrides/`, `hooks.py`.

| Bước | Việc | Phụ thuộc | Trạng thái |
|---|---|---|---|
| B0 | **Kết nối bằng code** (làm trước tiên: nó mở khóa việc chạy thử). `setup/xero_connection.py`: hàm `apply()` chạy lại an toàn: tạo hoặc cập nhật bản ghi Connected App với **tên cố định** `xero` (provider name "Xero", authorization URI, token URI, bốn scope của `docs/xero/09`), lấy `client_id` và `client_secret` từ site config (`frappe.conf`), không bao giờ từ repo; điền `Lab Xero Settings` (connected app, connected user, mã tài khoản, mã thuế) cũng từ site config. Thiếu key nào thì bỏ qua phần đó và in ra thiếu gì, không ném lỗi làm hỏng migrate. Kiểm tra trong source cách đặt tên cố định cho một tài liệu trước khi dùng (không đoán API). Trong tóm tắt: ghi Redirect URI cố định để con người đăng ký bên Xero, và các lệnh `set-config` (mỗi lệnh kèm giải thích; từ ba lệnh thì một script tạm, AGENTS.md A18). Nếu con người đã tạo tay một Connected App khác: nói rõ, không xóa nó | H3 (DocType `Lab Xero Settings`) cho phần Settings; phần Connected App không phụ thuộc gì | DONE |
| B1 | `setup/customizations.py`: hàm `apply()` tạo các custom field trên Customer và Sales Order (danh sách ở `PLAN.md`), chạy lại an toàn | — | DONE |
| B2 | `api/xero.py`: `retry_sync(sales_order)` và `refresh(sales_order)`. POST, kiểm tra quyền ghi trên đơn, chỉ xếp job, không gọi Xero. Retry trên đơn đã `Synced` → `LabConflictError` | — (dùng tên trong bảng "Tên dùng chung") | DONE |
| B3 | `public/js/sales_order.js`: nút "Retry" (hiện khi `lab_xero_sync_status` là `Failed`) và "Refresh from Xero" (hiện khi đã có `lab_xero_invoice_id`), gọi hai endpoint trên | B2 | DONE |

## Cần thêm vào hooks.py (làn A áp ở bước A5)

Agent của làn B ghi các dòng chính xác vào đây khi xong B0, B1 và B3 (`after_migrate` cho hai hàm `apply()`, `doctype_js` cho Sales Order):

```python
after_migrate = [
    "lab_core.setup.xero_connection.apply",
    "lab_core.setup.customizations.apply",
]
```

Nếu đã có danh sách `after_migrate`, thêm các chuỗi này vào danh sách hiện có; không ghi đè hook khác. Chưa thêm hook B3.

**Trạng thái hook của làn B (2026-10-12):** hai dòng `after_migrate` ở trên **đã có trong `hooks.py`** (con người bảo Claude thêm); đừng thêm lại. Dòng còn phải thêm, cho B3:

```python
doctype_js = {"Sales Order": "public/js/sales_order.js"}
```

Nếu đã có dict `doctype_js`, thêm khóa này vào dict hiện có.

## Ghi chú của làn

- B3 (Claude, 2026-10-12): `public/js/sales_order.js` đã viết, chưa chạy. Trên đơn không phải nháp: nút "Retry" hiện khi `lab_xero_sync_status` khác `Synced` (rộng hơn "chỉ khi `Failed`", để cứu được đơn kẹt ở `Queued` khi chưa có sweeper; khớp với endpoint ở B2); nút "Refresh from Xero" hiện khi đã có `lab_xero_invoice_id`. Cả hai nằm trong nhóm nút "Xero", gọi endpoint bằng POST, rồi tải lại form sau 3 giây. API đã đọc: `add_custom_button(label, fn, group)` tại `frappe-bench/apps/frappe/frappe/public/js/frappe/form/form.js:1590`; `frappe.call` tại `.../frappe/request.js:31` (mặc định POST, `:110`); `frappe.show_alert` tại `.../frappe/ui/messages.js:430`. **Làn B đã xong hết các bước.**

- B2 (Claude, 2026-10-12): `api/xero.py` đã viết, chưa chạy. `retry_sync`: lấy đơn có kiểm quyền ghi; đơn nháp hoặc đã `Synced` → `LabConflictError` (409); còn lại đặt `Queued`, xóa lỗi cũ bằng `db_set` rồi gọi `outbox.queue` với `create_invoice` (đơn đã submit) hoặc `void_invoice` (đơn đã cancel). `refresh`: cần có `lab_xero_invoice_id`, rồi xếp job `lab_core.tasks.xero_pull.pull_sales_order` (làn C viết ở C1; trước đó job sẽ lỗi khi chạy). Không endpoint nào gọi Xero.
- B2, điều làn A cần biết: Retry cho phép cả trạng thái `Queued` và `Not Synced` (để cứu dòng bị bỏ quên khi chưa có sweeper); chỉ chặn nháp và `Synced`. Người bấm cần quyền tạo/ghi trên `Lab Xero Outbox`, vì `outbox.queue` lưu dòng bằng quyền của người gọi.
- B2 API đã đọc: `get_doc(..., check_permission=...)` tại `frappe-bench/apps/frappe/frappe/model/document.py:167-179`; `db_set` nhận dict tại `:1518-1531`; `frappe.enqueue` tại `frappe-bench/apps/frappe/frappe/utils/background_jobs.py:76-93`.

- B1: `setup/customizations.py` đã viết, chưa chạy. `apply()` được hook sau migrate gọi, dùng `create_custom_fields(..., update=True)` để tạo/cập nhật đúng field theo tên, không sinh bản sao khi migrate lại. Customer có Contact ID unique; Sales Order có section Xero, chín field dữ liệu, Invoice ID unique và ba số tiền theo field `currency`. Các field read only, no copy, allow on submit; đơn amend không mang ID Xero của đơn cũ. Không HTTP, không job sau commit, không tự commit; migrate quản lý transaction và đồng bộ schema. Unique constraint có thể báo lỗi nếu dữ liệu cũ bị trùng; không bỏ qua validation. Code không sửa status/tổng tiền có sẵn của ERPNext.
- B1 API: `create_custom_fields` tại `frappe-bench/apps/frappe/frappe/custom/doctype/custom_field/custom_field.py:322`; cập nhật field hiện có tại `:368–378`, đồng bộ schema tại `:383–385`. Vị trí field lõi đã đọc: Customer `customer_name` tại `frappe-bench/apps/erpnext/erpnext/selling/doctype/customer/customer.json:119`; Sales Order `amended_from` tại `frappe-bench/apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.json:263`, `currency` tại `:493`.

- B0: code đã viết, chưa chạy. H3 vẫn TODO; Settings được bỏ qua nếu chưa có DocType. Không đọc site config hoặc database để kiểm tra tình trạng thật.
- `setup/xero_connection.py`: `apply()` được hook sau migrate gọi; đọc năm key từ `frappe.conf`, lưu Connected App `xero` và Settings bằng API tài liệu có kiểm tra quyền. Thiếu key thì báo tên key, giữ giá trị cũ; thiếu một trong hai credential thì bỏ qua toàn bộ Connected App. Scope được thay bằng đúng bốn scope, không cộng thêm dòng khi chạy lại. Tenant và con trỏ kéo dữ liệu không bị sửa. Không HTTP, không job sau commit, không tự commit: ghi nằm trong transaction do migrate quản lý.
- `setup/__init__.py`: package marker để import module setup; không có logic.
- `temp.sh` ở gốc dự án: script tạm B0 cho con người đọc rồi chạy; hỏi năm giá trị (ẩn credential), kiểm tra Docker Compose và service, đặt từng key qua `bench set-config`. Chỉ thay site config, không sửa database, không migrate. Nếu một lệnh lỗi, script dừng; chạy lại để hoàn tất các key còn thiếu. Không bật `set -x`. Hoàn tác bằng đặt lại giá trị cũ. Chờ con người chạy và báo lại để xóa script.
- Redirect URI cố định theo tên bản ghi: `<SITE_BASE_URL>/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/xero`. Với URL lab mặc định: `http://lab.localhost:8000/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/xero`. Base URL phụ thuộc cấu hình site; setup in URI thực tế sau khi lưu, con người đăng ký đúng URI đó bên Xero. Không tự đổi hostname hoặc TLS nếu Xero từ chối HTTP `lab.localhost`.
- API đã đọc: `Document.insert(set_name=...)` tại `frappe-bench/apps/frappe/frappe/model/document.py:439,746`; `save()` tại `:556`; `get_single()` tại `:2388`; child table `set()` tại `frappe-bench/apps/frappe/frappe/model/base_document.py:348`; `db.exists()` tại `frappe-bench/apps/frappe/frappe/database/database.py:1250`; `get_list()` tại `frappe-bench/apps/frappe/frappe/__init__.py:1363`; callback URI tại `frappe-bench/apps/frappe/frappe/integrations/doctype/connected_app/connected_app.py:60`; CLI `set-config` tại `frappe-bench/apps/frappe/frappe/commands/utils.py:934`.
- Connected App khác tên `xero`: không thể xác nhận có hay không mà không đọc database; code báo tên bản ghi Xero khác mà quyền hiện tại cho phép thấy và giữ nguyên chúng.

