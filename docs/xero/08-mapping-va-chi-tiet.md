# 08. Chi tiết để xây: mapping đầy đủ, lời gọi HTTP, webhook, quyết định

File tra cứu: mở khi bắt tay vào một mảnh cụ thể, không cần đọc một lượt. Đủ để không phải mở `docs/knowledge/11` và `12`.

Nhãn: xem `00-README.md`. Tên field ERPNext là [K]: phiên trước đã xác nhận **sự có mặt** của chúng trong JSON DocType của ERPNext (`erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.json`, `sales_invoice_item/…`, `selling/doctype/customer/customer.json`, `accounts/doctype/payment_entry/…`), không kiểm tra kiểu; hôm nay không mở lại. Field Xero là [G].

> Viết trước khi có email đề bài. Mapping ở đây đi từ **Sales Invoice** và **Payment Entry**; đề bài thật đi từ **Sales Order** và chỉ đọc payment/credit note từ Xero. Mapping và custom field cho đề bài: `09` và `plan/xero/PLAN.md`. File này còn giá trị cho phần Customer → Contact, client HTTP, nút Connect, webhook, và cho việc mở rộng về sau.

## Xero id được lưu ở đâu

Custom Field trên DocType của ERPNext, tạo **trong code** ở `lab_core/setup/customizations.py` (file chưa tồn tại), tiền tố `lab_` (AGENTS.md B2a mục 1):

| DocType | Field | Kiểu | Tùy chọn |
|---|---|---|---|
| Customer | `lab_xero_contact_id` | Data | unique, read only, no copy |
| Sales Invoice | `lab_xero_invoice_id` | Data | unique, read only, no copy, allow on submit |
| Sales Invoice | `lab_xero_sync_status` | Select: Not Synced / Queued / Synced / Failed | read only, allow on submit |
| Payment Entry | `lab_xero_payment_id` | Data | read only, no copy (một entry có thể ra nhiều payment Xero) |

- **No copy**: nhân bản một invoice trong Desk không được mang theo Xero id.
- **Allow on submit**: job ghi các field này sau khi tài liệu đã submit; tài liệu đã submit từ chối thay đổi ở field khác. Ghi bằng `doc.db_set` (AGENTS.md B4).
- **Unique**: lớp chống trùng thứ hai (`07`).

## Mapping đầy đủ

**Customer → Contact**

| ERPNext `Customer` | Xero `Contact` | Ghi chú |
|---|---|---|
| `name` | `ContactNumber` | key để tra cứu (tối đa 50 ký tự [G]) |
| `customer_name` | `Name` | phải unique bên Xero; hai khách trùng tên sẽ đụng nhau |
| `tax_id` | `TaxNumber` | |
| `email_id` | `EmailAddress` | |
| `default_currency` | `DefaultCurrency` | currency phải được bật trong organisation |
| `disabled` | `ContactStatus` = `ARCHIVED` | contact đã archive từ chối invoice mới |
| `lab_xero_contact_id` | `ContactID` | câu trả lời ta lưu lại |

**Sales Invoice → Invoice**

| ERPNext `Sales Invoice` | Xero `Invoice` | Ghi chú |
|---|---|---|
| — | `Type` = `ACCREC` | |
| `name` | `InvoiceNumber` | tay nắm để tra cứu sau timeout |
| `customer` → `lab_xero_contact_id` của nó | `Contact.ContactID` | **phụ thuộc**: contact phải có trước |
| `posting_date` | `Date` | ngày lịch, không múi giờ |
| `due_date` | `DueDate` | |
| `po_no` | `Reference` | |
| `currency` | `CurrencyCode` | |
| `conversion_rate` | `CurrencyRate` | **chiều tỷ giá cần thử bằng một invoice**; hai hệ thống có thể định nghĩa ngược nhau |
| `items[]` | `LineItems[]` | bảng dưới |
| `total_taxes_and_charges`, `grand_total`, `rounded_total` | `TotalTax`, `Total` | so sánh sau khi tạo; không gửi |
| `docstatus` 1 | `Status` = `AUTHORISED` | |
| `docstatus` 2 (cancel) | `Status` = `VOIDED` | bị chặn nếu đã paid |
| `is_return` + `return_against` | một **Credit Note** + allocation | không phải invoice |
| `outstanding_amount` | `AmountDue` | cho báo cáo đối soát |

**Sales Invoice Item → LineItem**

| ERPNext | Xero | Ghi chú |
|---|---|---|
| `description` (hoặc `item_name`) | `Description` | bắt buộc |
| `qty` | `Quantity` | |
| `rate` | `UnitAmount` | 2 chữ số thập phân, 4 với `?unitdp=4` |
| `amount` | `LineAmount` | tùy chọn; Xero tự tính |
| `discount_percentage` | `DiscountRate` | hoặc gửi `rate` đã trừ |
| `income_account` | `AccountCode` | **cần bảng mapping** account ERPNext → mã Xero |
| `item_tax_template` | `TaxType` | **cần bảng mapping**; theo quốc gia |
| `item_code` | `ItemCode` | chỉ khi item tồn tại bên Xero; không thì bỏ |

**Payment Entry → Payment(s)**

| ERPNext `Payment Entry` | Xero `Payment` | Ghi chú |
|---|---|---|
| `payment_type` = Receive, `party_type` = Customer | — | lúc đầu chỉ những cái này |
| mỗi dòng `references[]` có `reference_doctype` = Sales Invoice | **một Payment mỗi dòng** | Xero: một payment trả một invoice |
| `reference_name` → `lab_xero_invoice_id` | `Invoice.InvoiceID` | invoice phải sync trước |
| `allocated_amount` | `Amount` | |
| `paid_to` | `Account.Code` | mapping tài khoản ngân hàng |
| `posting_date` | `Date` | |
| `reference_no` hoặc `name` | `Reference` | tay nắm để tra cứu |
| cancel | `Status` = `DELETED` | |

Vì một Payment Entry ra nhiều payment Xero, key phải có cả dòng: `"Payment Entry:<name>:<reference_name>:create_payment"`.

Luật về tiền (AGENTS.md B4): `flt(value, precision)`; không `float()`; không `==`. So tổng: kiểu `abs(flt(a - b, 2)) <= tolerance`, với tolerance là một setting có tên.

Nơi đặt bảng mapping thuế/tài khoản: một DocType nhỏ trong module "Lab Xero" mà code chỉ đọc (khuyến nghị), hoặc với demo: một `AccountCode` và một `TaxType` mặc định trên `Lab Xero Settings`.

## Thứ tự giữa các dòng

```text
Customer ──► Contact
   └─► Sales Invoice ──► Invoice                 cần ContactID
            ├─► Payment Entry ──► Payment        cần InvoiceID
            └─► Return ──► Credit Note ──► Allocation    cần InvoiceID, rồi CreditNoteID
```
Job không có thứ tự (`06`). Hai cách: **kéo phụ thuộc vào** (job của invoice tự tạo contact trước, cùng luật tra-rồi-tạo; hợp cho demo) hoặc **chờ** (đặt `next_attempt_at` lùi một phút, sweeper đưa lại; sạch hơn khi nhiều loại tài liệu).

## Trigger trên Sales Invoice

```python
# lab_core/hooks.py — do con người thêm, hoặc agent chỉ khi yêu cầu nêu tên hooks.py (AGENTS.md B2)
doc_events = {
    "Sales Invoice": {
        "on_submit": "lab_core.overrides.sales_order.on_submit",
        "on_cancel": "lab_core.overrides.sales_order.on_cancel",
    },
}
```
Handler làm đúng một việc: gọi hàm public của module Xero, `outbox.queue(doc, operation="create_invoice")` (hoặc `"void_invoice"`). Không logic nào khác, không gọi Xero.

**Hai loại code, hai chỗ đặt** (luật của dự án, `plan/general/INIT.md`):

```text
overrides/sales_order.py      thứ GẮN VÀO ERPNext (code không phải của ta): handler mỏng, chỉ gọi sang module của ta
lab_xero/ (outbox, mapping…)  tính năng CỦA TA: viết và sửa trực tiếp, không bao giờ bị hook hay override
```

Handler gắn vào tài liệu của ERPNext là một thay đổi hành vi của ERPNext, nên nằm dưới `overrides/`. Tính năng Xero là code của ta, nên nằm trong `lab_xero/` và không đặt dưới `overrides/`. (AGENTS.md B2a mục 2 ghi đường dẫn handler là `<app>/<domain>/events/`, khác với B1 và `INIT.md`; con người đã chốt theo `overrides/` ngày 2026-10-12. Dòng đó của AGENTS.md là của con người sửa.)

Chưa biết: `on_submit` của chính ERPNext có làm gì xung đột với một handler ghi custom field trong cùng lần lưu hay không.

## Client HTTP: hình dạng đề xuất

```text
integrations/xero/client.py     (nơi DUY NHẤT biết URL, header, tenant id: AGENTS.md B1)
   find_contact(contact_number) → contact_id | None
   create_contact(key, payload) → contact_id
   find_invoice(invoice_number) → invoice_id | None
   create_invoice(key, payload) → invoice_id
   void_invoice(key, invoice_id)
   raises:  XeroRejected   400, 404-khi-ghi               vĩnh viễn     ┐ đã có: client.py:18, :22  [S]
            XeroTimeout    không có trả lời               không rõ      ┘
            XeroBusy       429, 500, 503 (+ retry_after)  tạm thời      ← mới
            XeroAuthLost   401 sau refresh, 403, token None             ← mới
```

Hai cách gửi request, cả hai đã có trên đĩa:

| Cách | Là gì | Nhận xét |
|---|---|---|
| A. `connected_app.get_oauth2_session(user)` | một `requests_oauthlib.OAuth2Session` đã gắn token ([S] `connected_app.py:67`; thư viện đã cài: [S] `frappe-bench/apps/frappe/pyproject.toml:70`) | nó tự refresh và **tự commit** khi refresh → đừng dựa vào auto-refresh; gọi `get_active_token` trước rồi dựng header |
| B. `frappe.integrations.utils.make_request` | helper của Frappe [K `frappe/integrations/utils.py:49-93`] | `raise_for_status()` biến mọi 4xx/5xx thành exception, **mất body** chứa message validation của Xero; `timeout` mặc định `None` |

Khuyến nghị: client mỏng của riêng ta trả về (status, header, body) rồi ánh xạ sang bốn class. Luôn truyền `timeout`. Log lời gọi bằng `create_request_log` (Integration Request) là tùy chọn và có hai bẫy [K]: nó tự commit, và nó lưu header nguyên văn → **không bao giờ đưa header `Authorization` vào** (AGENTS.md B6). Với demo, dòng outbox đã ghi đủ attempts, lỗi và Xero id.

## "Connect to Xero" từ SPA của ta

- `initiate_web_application_flow` là document method đã whitelist ([S] `connected_app.py:94`) → SPA gọi được, nhận URL, đặt `window.location`. `success_uri` đưa user về một route của SPA (chỉ path cùng site sống sót [K]).
- `has_token(connected_app, connected_user)` ([S] `:237`) cho badge "đã nối / chưa nối".
- Một ngoại lệ đã biết: callback của Frappe đổi code lấy token **ngay trong request** ([S] `:223`), trong khi AGENTS.md B4 nói lời gọi ra ngoài chạy trong job. Đây là code framework, một lời gọi, user đang chờ đúng lần redirect đó: hình dạng bình thường của OAuth.
- Đừng lẫn hai vai OAuth: Xero cần Frappe làm OAuth **client** (ta đăng nhập vào Xero: Connected App). Frappe còn có vai OAuth **server** (người khác đăng nhập vào ta: `frappe/oauth.py`) — không liên quan.
- Còn thiếu sau khi nối: lời gọi `GET /connections` để lấy `tenantId` (`02`). Nó là lời gọi ra ngoài → trong một job, kết quả ghi vào `Lab Xero Settings`.

## Endpoint webhook (hình dạng, không xây trong demo)

Xero không gửi cookie, API key hay bearer token của ta; nó **ký body**. Nên endpoint phải là guest và tự kiểm tra chữ ký.

```text
POST /api/method/lab_core.api.xero_webhook.receive     allow_guest=True (yêu cầu phải nói rõ: AGENTS.md B4)
 1. raw = frappe.request.get_data()                     đúng các byte; không serialize lại JSON
 2. expected = base64(HMAC-SHA256(signing key, raw))    key từ một field Password
    hmac.compare_digest(expected, header)               lệch → HTTP 401, không gì khác
 3. mỗi event một dòng inbox (unique: tenant + resource + event date → bản trùng tự rơi)
 4. return 200 ngay                                     Xero chờ vài giây
 5. một job đọc inbox và GET từng resource              event chỉ là gợi ý
```
Bảng inbox (hộp thư đến) là tấm gương của outbox. Frappe ký webhook **đi ra** của nó theo cùng kiểu, là hình mẫu để đọc [K `frappe/integrations/doctype/webhook/webhook.py:225-232`].

## Các quyết định nghiệp vụ là của bạn (AGENTS.md A15)

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| 1 | Bên nào là master (nguồn chính) cho invoice? | ERPNext. Invoice đã sync không sửa tay bên Xero. |
| 2 | Sync khi submit hay khi bấm nút? | Khi submit, có status nhìn thấy được và nút retry. |
| 3 | Cancel bên ERPNext khi invoice Xero đã paid? | Chặn cancel với message rõ; không tự gỡ payment. |
| 4 | Payment chảy chiều nào? | Chọn **một**. Hai chiều là đếm trùng. Demo: ERPNext → Xero. |
| 5 | Customer: tạo ở invoice đầu tiên hay sync tất cả? | Ở invoice đầu tiên. |
| 6 | Dung sai khi tổng lệch do làm tròn | 0.01 theo currency; lớn hơn → `Failed`, người xem. |
| 7 | Ai sở hữu dòng outbox: user hay hệ thống? | Hệ thống, một khi có sweeper. |
| 8 | Mapping thuế/tài khoản: bảng trong Desk hay hằng số? | Một DocType mapping nhỏ; code chỉ đọc. |
| 9 | Invoice tạo `AUTHORISED` ngay hay `DRAFT` rồi duyệt sau? | `AUTHORISED` ngay cho demo; dự án thật hỏi kế toán. |
| 10 | Compensation hỏng hẳn thì sao? | `Stuck` + báo người; không thử vô hạn. |

## Còn chưa biết (ngoài danh sách thử ở `05`)

- Field của Connected App và Token Cache như form hiển thị (mới thấy attribute dùng trong Python).
- Ý nghĩa chính xác của `conversion_rate` bên ERPNext.
- Xero phản ứng thế nào khi void một invoice lần hai (no-op hay lỗi).
- Cách chặn cancel trên tài liệu ERPNext khi sync đang chạy mà không sửa ERPNext: handler `before_cancel` qua `doc_events` là phỏng đoán tự nhiên, chưa trace.
