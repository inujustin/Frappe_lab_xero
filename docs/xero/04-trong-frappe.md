# 04. Trong Frappe: code nằm ở đâu, hôm nay có gì, còn thiếu gì

Nhãn độ tin cậy: xem `00-README.md`. Code của ta (đường dẫn dưới `frappe-bench/apps/lab_core/lab_core/`) đã đọc hôm nay: `integrations/xero/client.py`, `lab_xero/outbox.py`, `tasks/xero_sync.py`, `lab_core/doctype/lab_note/lab_note.py`, `hooks.py`.

> Viết trước khi có email đề bài. Các ví dụ dùng **Sales Invoice**; luồng thật bắt đầu từ **Sales Order** (`09`). Cơ chế (outbox, job, client, năm mảnh còn thiếu) không đổi.

## Trả lời trong năm dòng

1. Database của ta và Xero **không chung được một transaction**. Nên request chỉ ghi "ý định" (một dòng **outbox**: hộp thư đi) cùng lúc với tài liệu; một **background job** (việc chạy nền) gửi nó sau.
2. Job có thể chạy hai lần, chạy muộn, chết giữa chừng. Nó an toàn nhờ **hỏi Xero trước khi tạo** và nhờ khóa dòng outbox.
3. Khung của luồng này (outbox + job) **đã được viết** trong lab, chưa ai chạy. Hôm nay nó gọi một client thế chỗ thay cho Xero; kế hoạch chỉ dùng **Xero thật**, nên client đó bị gỡ ở P1 (`plan/xero/PLAN.md`).
4. Để lên Xero thật thiếu năm mảnh: client HTTP thật, settings + tenant, custom field trên DocType ERPNext, event của Sales Invoice, sweeper (job quét định kỳ).
5. Luật của dự án đã quyết sẵn phần lớn hình dạng: gọi Xero chỉ trong `tasks/`, HTTP chỉ dựng trong `integrations/xero/`, không sửa code ERPNext.

## Vì sao phải có outbox (ý tưởng duy nhất cần nhớ)

```text
CÁCH NGÂY THƠ: gọi Xero ngay trong lúc submit         CÁCH CỦA TA: outbox
 submit invoice                                        submit invoice
   ├─ gọi Xero … 3 giây … user ngồi chờ                  ├─ ghi dòng outbox "create_invoice"   ┐ cùng một
   ├─ Xero tạo xong                                      └─ commit                             ┘ transaction
   └─ lưu DB → LỖI → rollback                           worker (sau commit):
 ⇒ Xero có invoice, ERPNext không có. Không ai biết.       ├─ hỏi Xero: đã có chưa?
                                                           ├─ chưa → tạo (kèm Idempotency-Key)
                                                           └─ lưu InvoiceID, đánh dấu Done
                                                        ⇒ hỏng ở đâu cũng còn dòng outbox để làm tiếp
```
So với Spring Boot (kiến thức chung, không phải thứ đã trace): đây là "transactional outbox pattern"; job của Frappe đóng vai `@Async`/message consumer, dòng outbox đóng vai bảng outbox mà một relay đọc.

## Luồng đang có trong lab [S]

```text
Lab Note.insert()
 ├─ before_insert: sync_status = "Queued"                     lab_core/doctype/lab_note/lab_note.py:10-11
 └─ after_insert → outbox.queue(self)                         :13-16 → lab_xero/outbox.py:10
      key = "<doctype>:<name>:<operation>"                    :16
      đã có dòng với key này → mở lại thành Pending            :17-22
      chưa có → insert dòng Lab Xero Outbox                    :23-30
      frappe.enqueue(…, enqueue_after_commit=True,             :33-40
                     job_id=…, deduplicate=True)
 ── request commit: tài liệu + dòng outbox cùng sống hoặc cùng mất ──
 ▼ worker
process_outbox(outbox_name)                                   tasks/xero_sync.py:10
 ├─ lấy dòng với for_update (khóa dòng)                       :11
 ├─ status == Done → return (job trùng)                       :12-13
 ├─ attempts += 1                                             :18
 ├─ xero_id = find_by_key(key) or create_invoice(key, …)      :22    ← hỏi trước, rồi mới tạo
 ├─ XeroTimeout → hỏi lại; vẫn không có → Failed              :23-28
 ├─ XeroRejected → Failed kèm lý do                           :29-31
 └─ dòng Done + xero_id; tài liệu Synced + xero_id            :33-40
```

Thứ đứng ở chỗ của Xero trong code hôm nay ([S] `integrations/xero/client.py`) không phải Xero: nó lưu "invoice" vào cache và tự tạo lỗi theo chữ trong title của Lab Note. Nó là di sản của sprint và **không thuộc kế hoạch**: P1 gỡ nó, cùng với đường "sync Lab Note", và thay bằng một client gọi Xero thật. Hình vẽ trên được giữ lại chỉ để thấy cái khung (outbox, khóa dòng, hỏi trước khi tạo) vốn đã đúng.

## Code hôm nay còn cách Xero thật bao xa

| | Code hôm nay (client thế chỗ, sẽ gỡ) | Xero thật | Phải viết ở P1 |
|---|---|---|---|
| Tra cứu | `find_by_key(key)` | không có; tra theo `InvoiceNumber` (`03`) | `find_invoice(number)` |
| Nhớ key | mãi mãi (tới khi xóa cache) | 6 phút [X*] | tra cứu trước mọi lần tạo |
| Loại lỗi | Rejected, Timeout | thêm Busy (`429/5xx`), Auth lost (`401/403`) | hai class + hai nhánh trong job |
| Auth, tenant | không có | token + `xero-tenant-id` (`02`) | settings + Connected App |
| Payload | `{"title": …}` | Contact/Invoice đầy đủ, có mapping | module mapping |
| Mạng | không | HTTPS, timeout, rate limit | client HTTP thật |

Cái **giữ nguyên** là xương sống: outbox, khóa dòng, "hỏi trước khi tạo", trạng thái `Pending/Done/Failed`. Đó là phần đáng demo.

## Năm mảnh còn thiếu

| # | Mảnh | Ở đâu | Ai làm |
|---|---|---|---|
| A | **Client HTTP thật**: `create_contact`, `find_invoice`, `create_invoice`, `void_invoice`; trả status + header + body; ánh xạ sang 4 class lỗi | `integrations/xero/client.py` | agent |
| B | **Settings + kết nối**: single DocType `Lab Xero Settings` (`connected_app` Link, `connected_user` Link → User, `tenant_id` Data, `tenant_name` Data, `paused` Check, `paused_reason` Small Text, `not_before` Datetime) + một Connected App "Xero" | Desk | **bạn** (AGENTS.md B2) |
| C | **Custom field trên DocType ERPNext**, tiền tố `lab_`: `Customer.lab_xero_contact_id`; `Sales Invoice.lab_xero_invoice_id`, `lab_xero_sync_status` (unique / read only / no copy / allow on submit) | `setup/customizations.py` (chưa tồn tại) | agent |
| D | **Event của Sales Invoice** → `outbox.queue(doc, "create_invoice")` khi `on_submit`, `"void_invoice"` khi `on_cancel`; và **mapping** Sales Invoice → payload | handler mỏng trong `overrides/` (gắn vào ERPNext) + `hooks.py` (`doc_events`); mapping trong `lab_xero/` (code của ta) | agent viết handler; dòng `hooks.py` do bạn thêm hoặc yêu cầu nêu tên file |
| E | **Sweeper**: job theo lịch, nhặt các dòng `Pending` bị bỏ quên hoặc đang chờ `Retry-After` (cần field `next_attempt_at` Datetime trên outbox) | `tasks/` + `scheduler_events` trong `hooks.py` | agent + bạn |

Hôm nay `hooks.py` chưa có `doc_events` hay `scheduler_events` ([S] chỉ có `website_route_rules`, `hooks.py:8-10`).

Vì sao cần E: nếu process chết giữa lúc SQL commit và lúc job được đẩy lên queue, dòng nằm `Pending` mãi mãi, không có job nào (`06` mục 1; cả sáu trường hợp thất bại ở `07`).

Vì sao D dùng hook chứ không sửa ERPNext: code ERPNext là read-only (AGENTS.md B2a); `doc_events` là điểm mở rộng đúng. `on_submit` chứ không phải `after_insert`: bản nháp chưa phải hóa đơn.

## Mapping tối thiểu cho demo

Tên field ERPNext bên dưới là [K] (phiên trước đã xác nhận sự có mặt trong JSON DocType của ERPNext; hôm nay không mở lại). Field Xero là [G].

| ERPNext | Xero | Ghi chú |
|---|---|---|
| `Customer.name` | `Contact.ContactNumber` | để tra cứu |
| `Customer.customer_name` | `Contact.Name` | unique bên Xero: hai khách trùng tên sẽ đụng nhau |
| `Sales Invoice.name` | `Invoice.InvoiceNumber` | **tay nắm chống trùng** |
| `customer` → `lab_xero_contact_id` | `Contact.ContactID` | contact phải có trước |
| `posting_date`, `due_date` | `Date`, `DueDate` | |
| `currency` | `CurrencyCode` | currency phải được bật trong organisation |
| `items[].description`, `qty`, `rate` | `LineItems[].Description`, `Quantity`, `UnitAmount` | |
| `items[].income_account` | `AccountCode` | **cần bảng mapping** |
| `items[].item_tax_template` | `TaxType` | **cần bảng mapping**, theo quốc gia |
| `docstatus` 1 / 2 | `Status` `AUTHORISED` / `VOIDED` | |

Bảng đầy đủ (Payment Entry, trả hàng, tỷ giá, custom field): `08`. Đường tắt cho demo: một `AccountCode` và một `TaxType` cố định đặt trong `Lab Xero Settings`, ghi rõ là đường tắt.

## Thứ tự phụ thuộc

```text
Customer ──► Contact (ContactID)
                └─► Sales Invoice ──► Invoice (InvoiceID)
                                         └─► Payment Entry ──► Payment      (sau demo đầu)
```
Job không có thứ tự. Cách đơn giản cho demo: job của invoice thấy customer chưa có `lab_xero_contact_id` thì tạo contact trước (cùng luật: tra cứu rồi mới tạo), rồi đi tiếp.

## Các luật dự án áp vào luồng này (AGENTS.md B4)

- Gọi Xero **chỉ trong `tasks/`**, không bao giờ trong request. Request trả về ngay.
- HTTP tới Xero **chỉ dựng trong `integrations/xero/`**.
- Ghi sang Xero phải idempotent: qua outbox, lưu Xero id sau một ràng buộc unique, kiểm tra trước khi tạo.
- Sau submit dùng `doc.db_set`, không `frappe.db.set_value`.
- Không `ignore_permissions`. Hệ quả còn mở: dòng outbox hiện được ghi dưới tên user tạo tài liệu (`plan/general/SPRINT.md`); khi có sweeper thì ai sở hữu dòng outbox là một quyết định phải đưa ra.
- Không token, secret nào trong log, trace note hay response.

## Tự kiểm tra

1. Chỉ ra trong `tasks/xero_sync.py` dòng nào bảo vệ khỏi job trùng, dòng nào bảo vệ khỏi "Xero đã tạo nhưng ta không biết".
2. Hai loại lỗi nào của Xero thật mà job hôm nay chưa có nhánh?
3. Vì sao với Xero thật không có `find_by_key`, và thay bằng gì?
