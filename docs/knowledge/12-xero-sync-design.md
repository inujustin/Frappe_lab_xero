# 12. Thiết kế Xero sync: outbox, idempotency, thất bại, mapping

Nhãn: [S] đã thấy hôm nay, [I] suy ra, [G] kiến thức chung (mọi thứ về hành vi của Xero; xem `10`). Code của chính ta đã được đọc đầy đủ hôm nay: `lab_core/lab_core/lab_xero/outbox.py`, `tasks/xero_sync.py`, `integrations/xero/client.py`, `lab_core/notes.py`, `lab_core/doctype/lab_note/lab_note.py` (đường dẫn nằm dưới `frappe-bench/apps/lab_core/lab_core/`).

## Trả lời trong năm dòng

1. Database của ta và Xero không thể dùng chung một transaction. Nên request chỉ **ghi lại ý định** (một dòng outbox: hộp thư đi) cùng với thay đổi nghiệp vụ; một job thực hiện nó về sau.
2. Job có thể chạy hai lần, chạy muộn, hoặc chết giữa chừng. Nó an toàn vì mỗi lần gửi có một **idempotency key** (khóa chống gửi trùng) cố định và vì job **hỏi Xero trước khi tạo**.
3. Mọi thất bại được xếp vào một trong bốn loại: rejected (bị từ chối: dừng, báo con người), busy (bận: chờ, thử lại), unknown (không rõ: hỏi Xero), connection lost (mất kết nối: dừng mọi thứ, reconnect).
4. Một bước không hoàn tất được thì được hoàn tác bằng một **compensation** (bù trừ): void bên Xero, hoặc đánh dấu tài liệu local.
5. Code của sprint đã có 1 và 2 cho happy path (đường suôn sẻ). Nó chưa có **sweeper** (job quét định kỳ) và chưa có đường "busy"; đó là hai mảnh kế tiếp.

## Hôm nay đang có gì

```text
SPA / Desk
 │ create_note (POST)                         api/notes.py:20-23            [S]
 ▼
notes.create_note → note.insert()             lab_core/notes.py:39-44       [S]
 ├─ before_insert: sync_status = "Queued"     doctype/lab_note/lab_note.py:10-11
 └─ after_insert: outbox.queue(self)          :13-16
       key = "<doctype>:<name>:<operation>"   lab_xero/outbox.py:16
       dòng đã có → Pending lại, không thì insert  :17-30
       enqueue(sau commit, job_id, deduplicate)    :33-40
 ── request commit: note + dòng outbox cùng nhau ──
 ▼ worker
process_outbox(outbox_name)                   tasks/xero_sync.py:10         [S]
 ├─ lock dòng (for_update)                    :11
 ├─ status Done → return (job trùng)          :12-13
 ├─ attempts += 1                             :18
 ├─ xero_id = find_by_key(key) or create_invoice(key, payload)   :22
 ├─ XeroTimeout → find_by_key lần nữa; không có → đánh dấu Failed   :23-28
 ├─ XeroRejected → đánh dấu Failed                               :29-31
 └─ dòng Done + xero_id; note Synced + xero_id                   :33-40
 ── job commit ──
```

Đối chiếu với các luật của AGENTS.md B4: outbox ✓, Xero id lưu trên tài liệu ✓ (unique được đặt trên field trong Desk, theo SPRINT.md), kiểm tra trước khi tạo ✓ (`:22`), lời gọi ra ngoài chỉ trong `tasks/` ✓.

## Sáu trường hợp thất bại của kế hoạch

`plan/general/OVERVIEW.md` liệt kê chúng ở cuối. Mỗi cái được dò qua code thật.

| # | Trường hợp | Hôm nay chuyện gì xảy ra | Bằng chứng | Kết luận |
|---|---|---|---|---|
| 1 | Crash **trước** commit | Note và dòng outbox cùng rollback; lần `enqueue` đang chờ bị bỏ | `frappe/database/database.py:1202-1203` [S] | Đúng. Không cần làm gì. |
| 2 | Crash **sau** commit, trước khi job được đẩy | Dòng là `Pending`, note là `Queued`, không có job. Nó nằm như vậy mãi mãi. | việc đẩy xảy ra ở `database.py:1194`, sau SQL commit ở `:1190` [S]; không có sweeper trong `lab_core/hooks.py` [S] | **Khoảng trống.** Cần một sweeper. Con người có thể bấm retry (`notes.py:47-55`). |
| 3 | Xero **timeout**, nhưng Xero đã tạo rồi | Job hỏi `find_by_key`; tìm thấy id; đánh dấu Done | `tasks/xero_sync.py:23-25, :33-40` [S] | Đúng với bản giả. Xero thật không có `find_by_key`: dùng tra cứu theo `InvoiceNumber`, hoặc gửi lại với cùng key (`10`). |
| 4 | **Bị từ chối** | Dòng `Failed` kèm lý do; note `Failed`; job return bình thường nên điều này được commit | `:29-31, :43-51` [S] | Đúng. |
| 5 | **Job trùng** | Job thứ hai chờ row lock, rồi thấy `Done` và return | `:11-13` [S] | Đúng. Đây mới là lớp bảo vệ thật; `deduplicate` trên queue chỉ là cho gọn (`03`). |
| 6 | **Compensation thất bại** | Hôm nay compensation là hai lần save local trong cùng transaction (`_mark_failed`); nếu một cái throw, job raise, mọi thứ rollback, dòng vẫn `Pending`, note vẫn `Queued`, và chỉ Error Log biết | `:43-51`; `frappe/utils/background_jobs.py:296-302` [S] | Chấp nhận được chừng nào compensation còn là local. Với một compensation thật (void bên Xero) nó trở thành một operation outbox riêng: xem bên dưới. |

Ba trường hợp nữa mà danh sách không nêu, tất cả là [I]:

| Trường hợp | Hôm nay chuyện gì xảy ra | Cách sửa |
|---|---|---|
| Một lỗi transport không phải `XeroTimeout` (DNS, TLS, connection reset) hoặc bất kỳ bug nào | Đường exception chung: rollback (lần `attempts += 1` bị mất), Error Log, job thất bại, note nằm ở `Queued` mãi mãi | Client ánh xạ **mọi** lỗi transport sang một trong các class của chính nó; job có một nhánh cho mỗi class |
| Worker bị kill ở timeout 300 s | Như trên, thậm chí không có Error Log từ code của ta | HTTP timeout thấp hơn 300 s rất nhiều; sweeper |
| Note bị user sửa trong lúc job đang save nó | `doc.save()` của job và lần save của user có thể đụng nhau (kiểm tra "document has been modified") [G] | Cho job chỉ đổi các field của riêng nó theo cách không tranh chấp với form; một business rule cần quyết định |

## Bốn loại thất bại

Bảng này là trái tim của thiết kế. Mỗi dòng là một nhánh trong job.

| Loại | Tín hiệu [G] | Có gì bên Xero không? | Job làm | Dòng trở thành |
|---|---|---|---|---|
| **Rejected** | 400 validation, 404 trên một bản ghi được tham chiếu | Không | ghi lại message, dừng | `Failed` (con người sửa dữ liệu, rồi retry) |
| **Busy** | 429 (+ `Retry-After`), 500, 503 | Không (giả định) | ghi mốc "không trước thời điểm", dừng | vẫn `Pending`; sweeper gửi nó sau |
| **Unknown** | timeout, đứt kết nối sau khi gửi | Có thể | tra cứu nó (hoặc gửi lại với cùng key); câu trả lời quyết định | `Done` hoặc quay về `Pending` |
| **Auth lost** | 401 sau một lần refresh; token là `None` (`11`) | Không | bật một cờ toàn cục "paused: reconnect" | vẫn `Pending`; **không tính attempts** |

Vì sao "busy" không được dùng `RetryBackgroundJobError`: retry của Frappe ngủ 1–5 giây ngay trong worker ([S] `frappe/utils/background_jobs.py:278-290`), chiếm giữ worker trong lúc ngủ, và sau đó job có thể chạy với tư cách một user khác (`03`). Một `Retry-After` cỡ một phút cần dòng quay về trạng thái chờ và worker được giải phóng.

## Mảnh còn thiếu: sweeper

Sao chép email queue (`05`). Bằng lời:

```text
mỗi N phút (scheduler_events, "cron")                              ← dòng hooks.py, do con người thêm
 sweep_outbox()                  trong tasks/, không tham số (hàm được lập lịch không nhận tham số: 03)
  ├─ sync đang paused (auth lost / dừng thủ công)? → return
  ├─ các dòng có status = Pending
  │        và (next_attempt_at là null hoặc next_attempt_at <= now)
  │        và creation < now - 1 phút           ← để job trực tiếp thắng trước ("cửa sổ undo" của email)
  │     order by attempts asc, creation asc, limit một batch
  └─ với mỗi dòng: frappe.enqueue(process_outbox, job_id=…, deduplicate=True, outbox_name=…)
```

Những thứ việc này cần mà chưa tồn tại. **Field của DocType do bạn tạo trong Desk** (AGENTS.md B2); liệt kê kèm kiểu để yêu cầu sẵn sàng:

| DocType | Field | Kiểu | Vì sao |
|---|---|---|---|
| Lab Xero Outbox | `next_attempt_at` | Datetime | back-off và `Retry-After` |
| Lab Xero Outbox | `payload_hash` | Data | phát hiện "cùng key, khác body" trước khi Xero phát hiện |
| Lab Xero Outbox | option `Sending` của `status` | Select option | chỉ khi hai lượt sweep có thể chồng nhau; row lock có thể là đủ |
| Lab Xero Settings (mới, single) | `connected_app`, `connected_user`, `tenant_id`, `tenant_name`, `paused`, `paused_reason`, `not_before` | Link, Link, Data, Data, Check, Small Text, Datetime | `11`, khoảng trống 1 và 2; công tắc dừng toàn cục; đồng hồ rate-limit dùng chung |

Luật back-off (giãn dần thời gian chờ) [G]: chờ `min(60 × 2^attempts, 3600)` giây, hoặc `Retry-After` nếu Xero đưa, cái nào dài hơn thì lấy; sau khoảng 8 lần thử thì đánh dấu `Failed`. Thời gian lấy từ `frappe.utils` (`now_datetime`, `add_to_date`), không bao giờ `datetime.now()` (AGENTS.md B4).

Sweeper chạy với tư cách Administrator (`03`, [I]). Điều đó lặng lẽ trả lời câu hỏi mở trong SPRINT.md về việc ai sở hữu dòng outbox: có sweeper thì là hệ thống. Hãy quyết định việc đó một cách có chủ đích.

## Idempotency: ba lớp, mỗi lớp bắt cái lớp trên nó bỏ sót

```text
1. Queue        job_id + deduplicate            chặn phần lớn job trùng              gọn, chưa an toàn
2. Database ta  row lock + kiểm tra status      mỗi lúc một worker, Done là cuối     an toàn trước chính ta
                unique xero_id trên tài liệu    không lưu được id thứ hai
3. Xero         header Idempotency-Key          gửi lại không tạo gì mới             an toàn trước mạng
                + tra cứu theo số của chính ta  dùng được sau khi key đã hết hạn
```

Key hôm nay: [S] `outbox.py:16` `f"{doc.doctype}:{doc.name}:{operation}"`. Tính chất tốt: ổn định qua các lần retry, đọc được, mỗi tài liệu và operation một key. Các giới hạn cần biết:
- Giới hạn của Xero là 128 ký tự [G]. `"Sales Invoice:ACC-SINV-2026-00042:create_invoice"` dài 48. Ổn; một naming series tùy biến dài có thể vượt. Chặn bằng một kiểm tra độ dài.
- Một invoice ERPNext bị cancel rồi **amend** (sửa đổi sau khi hủy) nhận tên mới (`…-1`) [G], nên là key mới: đúng, đó là một invoice mới.
- Nếu cùng một operation có thể được gửi lại với **nội dung khác** (một "update contact" sau mỗi lần sửa), key phải có thêm version, ví dụ timestamp `modified` của tài liệu, không thì Xero sẽ trả lời bằng kết quả đầu tiên hoặc một lỗi [G].

## Từ Lab Note tới các tài liệu ERPNext thật

### Trigger đặt ở đâu

Không đặt trong code của ERPNext (AGENTS.md B2a). Một document event, điểm mở rộng thứ hai. Đây là code ta **không** sở hữu, nên mới dùng hook; với Lab Note (code của ta) thì lời gọi nằm thẳng trong controller, như phần "Hôm nay đang có gì" ở trên.

```python
# lab_core/hooks.py — do con người thêm, hoặc agent chỉ khi yêu cầu nêu tên hooks.py
doc_events = {
    "Sales Invoice": {
        "on_submit": "lab_core.overrides.sales_invoice.on_submit",
        "on_cancel": "lab_core.overrides.sales_invoice.on_cancel",
    },
}
```

Handler làm một việc: `outbox.queue(doc, operation="create_invoice")`. Nó chạy bên trong transaction của lần submit, với commit bị tắt ([T] `frappe/model/document.py:1642-1649`), điều đó hoàn toàn đúng: dòng được lưu hoặc mất cùng với lần submit. `on_submit`, không phải `after_insert`: một bản nháp chưa phải là invoice.

Handler nằm dưới `overrides/` vì nó gắn vào tài liệu của ERPNext (code không phải của ta): mỏng, chỉ gọi hàm public của `lab_xero/`. Phần tính năng (outbox, mapping) là code của ta, nằm trong `lab_xero/`, sửa trực tiếp và không bao giờ bị hook hay override (`INIT.md`, `OVERVIEW.md`). Con người chốt ngày 2026-10-12; AGENTS.md B2a mục 2 còn ghi `<domain>/events/`.

### Xero id được lưu ở đâu

Custom Field trên các DocType của ERPNext, tạo **trong code** ở `lab_core/setup/customizations.py`, có tiền tố `lab_` (AGENTS.md B2a, mục 1). File đó chưa tồn tại. Các field:

| DocType | Field | Kiểu | Tùy chọn |
|---|---|---|---|
| Customer | `lab_xero_contact_id` | Data | unique, read only, no copy |
| Sales Invoice | `lab_xero_invoice_id` | Data | unique, read only, no copy, allow on submit |
| Sales Invoice | `lab_xero_sync_status` | Select | Not Synced / Queued / Synced / Failed; read only, allow on submit |
| Payment Entry | `lab_xero_payment_id` | Data | read only, no copy (một entry có thể tạo nhiều payment Xero: xem bên dưới) |

"No copy" quan trọng: nhân bản một invoice trong Desk không được copy Xero id. "Allow on submit" quan trọng: job ghi các field này sau khi tài liệu đã submit, và một tài liệu đã submit từ chối thay đổi ở các field khác. Dùng `doc.db_set` sau submit (AGENTS.md B4).

### Field mapping (ánh xạ field)

Cột trái: tên field **đã xác nhận là tồn tại** hôm nay trong JSON DocType của ERPNext ([S]: `erpnext/erpnext/accounts/doctype/sales_invoice/sales_invoice.json`, `sales_invoice_item/…json`, `erpnext/erpnext/selling/doctype/customer/customer.json`, `erpnext/erpnext/accounts/doctype/payment_entry/payment_entry.json`, `payment_entry_reference/…json`; chỉ kiểm tra sự có mặt, không kiểm tra kiểu). Cột phải: field của Xero, [G].

**Customer → Contact**

| ERPNext `Customer` | Xero `Contact` | Ghi chú |
|---|---|---|
| `name` | `ContactNumber` | key của ta để tra cứu (tối đa 50 ký tự [G]) |
| `customer_name` | `Name` | phải unique bên Xero; hai customer cùng một tên sẽ đụng nhau |
| `tax_id` | `TaxNumber` | |
| `email_id` | `EmailAddress` | |
| `default_currency` | `DefaultCurrency` | currency phải được bật trong organisation |
| `disabled` | `ContactStatus` = `ARCHIVED` | một contact đã archive từ chối invoice mới |
| `lab_xero_contact_id` | `ContactID` | câu trả lời ta lưu lại |

**Sales Invoice → Invoice**

| ERPNext `Sales Invoice` | Xero `Invoice` | Ghi chú |
|---|---|---|
| — | `Type` = `ACCREC` | |
| `name` | `InvoiceNumber` | tay nắm để tra cứu sau một timeout |
| `customer` → `lab_xero_contact_id` của nó | `Contact.ContactID` | **phụ thuộc**: contact phải tồn tại trước |
| `posting_date` | `Date` | một ngày lịch, không có time zone |
| `due_date` | `DueDate` | |
| `po_no` | `Reference` | |
| `currency` | `CurrencyCode` | |
| `conversion_rate` | `CurrencyRate` | **chiều cần verify bằng một invoice thử**; hai hệ thống có thể định nghĩa tỷ giá ngược nhau |
| `items[]` | `LineItems[]` | bên dưới |
| `total_taxes_and_charges`, `grand_total`, `rounded_total` | `TotalTax`, `Total` | so sánh sau khi tạo; không gửi |
| `docstatus` 1 | `Status` = `AUTHORISED` | |
| `docstatus` 2 (cancel) | `Status` = `VOIDED` | bị chặn nếu đã paid: gỡ payment trước |
| `is_return` + `return_against` | một **Credit Note** + allocation | hoàn toàn không phải invoice |
| `outstanding_amount` | `AmountDue` | cho một báo cáo đối soát |

**Sales Invoice Item → LineItem**

| ERPNext | Xero | Ghi chú |
|---|---|---|
| `description` (hoặc `item_name`) | `Description` | bắt buộc |
| `qty` | `Quantity` | |
| `rate` | `UnitAmount` | 2 chữ số thập phân, 4 với `unitdp=4` |
| `amount` | `LineAmount` | tùy chọn; Xero tự tính |
| `discount_percentage` | `DiscountRate` | hoặc gửi `rate` đã trừ và không có discount |
| `income_account` | `AccountCode` | **cần một bảng mapping** account ERPNext → mã Xero |
| `item_tax_template` | `TaxType` | **cần một bảng mapping**; tùy theo vùng |
| `item_code` | `ItemCode` | chỉ khi item tồn tại bên Xero; không thì bỏ ra |

**Payment Entry → Payment(s)**

| ERPNext `Payment Entry` | Xero `Payment` | Ghi chú |
|---|---|---|
| `payment_type` = Receive, `party_type` = Customer | — | lúc đầu chỉ những cái này nằm trong phạm vi |
| các dòng `references[]` có `reference_doctype` = Sales Invoice | **mỗi dòng một Payment** | Xero trả một invoice mỗi payment |
| `reference_name` của dòng → `lab_xero_invoice_id` của nó | `Invoice.InvoiceID` | phụ thuộc: invoice phải được sync rồi |
| `allocated_amount` của dòng | `Amount` | |
| `paid_to` | `Account.Code` | mapping: tài khoản ngân hàng ERPNext → tài khoản ngân hàng Xero |
| `posting_date` | `Date` | |
| `reference_no` hoặc `name` | `Reference` | tay nắm để tra cứu |
| cancel | `Status` = `DELETED` | |

Vì một Payment Entry cho ra nhiều payment Xero, idempotency key cần có cả dòng: `"Payment Entry:<name>:<reference_name>:create_payment"`.

Luật về tiền (AGENTS.md B4): `flt(value, precision)` trên mọi số tiền, không bao giờ `float()`, không bao giờ `==` giữa hai số tiền. Để so tổng của ta với của Xero: kiểu `abs(flt(a - b, 2)) <= 0.01`, với tolerance là một setting có tên.

### Phụ thuộc giữa các dòng: bài toán thứ tự

```text
Customer ──► Contact                         phải Done trước
   └─► Sales Invoice ──► Invoice             cần ContactID
            ├─► Payment Entry ──► Payment    cần InvoiceID
            └─► Return ──► Credit Note ──► Allocation   cần InvoiceID, rồi CreditNoteID
```

Job không có thứ tự (`03`). Hai cách trung thực để có thứ tự:
- **Kéo phụ thuộc vào:** job của invoice thấy customer chưa có `lab_xero_contact_id`, tạo contact trước (cùng các luật idempotency, dòng outbox riêng), rồi đi tiếp. Đơn giản, hợp cho demo.
- **Chờ:** dòng của invoice đặt `next_attempt_at` lùi một phút khi phụ thuộc của nó chưa `Done`; sweeper đưa nó quay lại. Sạch hơn khi có nhiều loại tài liệu.

### Một operation nhiều bước là một saga nhỏ

Saga = một chuỗi bước, mỗi bước có transaction riêng, bước sau hỏng thì chạy compensation cho các bước trước. Chi tiết và so sánh "có / không có SAGA": `13-saga.md`.

Trả hàng: tạo credit note (bước 1), allocate nó (bước 2). Nếu bước 2 bị từ chối, bước 1 đã tồn tại bên Xero.

```text
dòng A  operation=create_credit_note   Done ✔  (đã lưu xero id)
dòng B  operation=allocate_credit      Failed ✘  "invoice already fully paid"
 → compensation: dòng C  operation=void_credit_note  (được xếp bởi job đã đánh dấu B là Failed)
 → và lần trả hàng local nhận status "Failed", kèm lý do
```

Các luật làm cho việc này quản lý được [G]:
1. Mỗi lời gọi tới Xero một dòng outbox. Không bao giờ hai lời gọi dưới một dòng.
2. Một compensation chỉ là một dòng khác với key riêng. Nó được retry như mọi dòng khác.
3. Một compensation phải an toàn khi chạy hai lần (void một note đã void là no-op (không làm gì) hoặc một lỗi đã biết, được nuốt theo đúng tên, không bao giờ bằng một `except` trần).
4. Nếu một compensation `Failed` hẳn, một con người được báo. Đó là điểm kết thúc của tự động hóa, có chủ đích.

Ý tưởng decorator trong kế hoạch, `@xero_atomic(compensate=...)`, là lớp đường bọc ngoài luật 2: "nếu bước này kết thúc `Failed`, xếp operation kia vào hàng đợi". Hãy xây bản mộc trước; thêm decorator khi cùng bốn dòng đó xuất hiện lần thứ ba.

## Xero gọi ta: endpoint webhook

Không xây được trong một lab cục bộ khi không có URL công khai (`10`). Hình dạng của nó, để biết:

```text
POST /api/method/lab_core.api.xero_webhook.receive      allow_guest=True (yêu cầu phải nói rõ điều đó: AGENTS.md B4)
 1. raw = frappe.request.get_data()                      đúng các byte; không serialize lại JSON đã parse
 2. expected = base64(HMAC-SHA256(signing key, raw))     key lấy từ một field Password, không bao giờ trong repo
    so sánh constant time (hmac.compare_digest)          lệch → HTTP 401, không gì khác
 3. insert mỗi event một dòng inbox (unique trên tenant + resource + event date → bản trùng tự rơi ra)
 4. return 200 ngay                                      Xero chờ câu trả lời trong vài giây
 5. một job đọc các dòng inbox và GET từng resource      event chỉ là một gợi ý
```

Frappe tính cùng loại chữ ký cho các webhook **đi ra** của nó, là một hình mẫu hữu ích để đọc: [S] `frappe/integrations/doctype/webhook/webhook.py:225-232` (base64 của HMAC-SHA256 trên JSON body, header `X-Frappe-Webhook-Signature`, `:20`). Cùng file đó cho thấy chính sách giao nhận của chính Frappe: xếp hàng ở `after_commit` ([S] `frappe/integrations/doctype/webhook/__init__.py:73-79`), ba lần thử với các lần ngủ ngắn (`webhook.py:164-189`), mọi lần thử được log trong `Webhook Request Log` (`:192-216`).

Một bảng inbox (hộp thư đến) cho các event đi vào là tấm gương của outbox: cùng pattern, chỉ theo chiều ngược lại.

## Các quyết định là của bạn (business rule: AGENTS.md A15)

Liệt kê kèm một khuyến nghị cho mỗi cái, để "ok" là đủ khi bạn quay lại.

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| 1 | Bên nào là master (nguồn chính) cho invoice? | ERPNext. Xero chỉ được ghi vào, không bao giờ sửa tay với các invoice đã sync. |
| 2 | Sync khi submit, hay khi bấm nút? | Khi submit, với một status nhìn thấy được và một nút retry. |
| 3 | Cancel bên ERPNext khi invoice Xero đã paid? | Chặn việc cancel với một message rõ ràng; không tự động gỡ payment. |
| 4 | Payment chảy ERPNext → Xero, hay Xero → ERPNext (bank feed)? | Chọn **một**. Payment hai chiều sẽ đếm trùng. Cho demo: ERPNext → Xero. |
| 5 | Customer: tạo bên Xero ở invoice đầu tiên, hay sync tất cả? | Ở invoice đầu tiên. |
| 6 | Tolerance khi tổng lệch nhau do làm tròn | 0.01 theo currency của invoice; lớn hơn → `Failed`, con người xem. |
| 7 | Ai sở hữu các dòng outbox: user hay hệ thống? | Hệ thống, một khi sweeper tồn tại. |
| 8 | Mapping thuế và account: một bảng trong Desk, hay hằng số trong code? | Một DocType mapping nhỏ trong "Lab Xero"; code chỉ đọc nó. |

## Thứ tự xây, và cái gì chạy song song được

```text
            ┌─ A. client: HTTP thật + các class lỗi     integrations/xero/client.py
 settings ──┤                                            (cần: DocType Lab Xero Settings, Connected App)
 (bạn,Desk) ├─ B. sweeper + back-off                     tasks/xero_sync.py   (cần: field next_attempt_at)
            └─ C. customizations (các field lab_xero_*)  setup/customizations.py
                         │
                         ▼
              D. event của Sales Invoice + mapping        overrides/ (handler mỏng), lab_xero/mapping…   + hooks.py (mỗi lúc một người sửa)
                         │
                         ▼
              E. phụ thuộc Customer, rồi payment, rồi trả hàng (saga)
```

A, B và C đụng các file khác nhau và có thể là ba phiên cùng lúc. A và B đều kết thúc ở các nhánh của job, nên hãy thống nhất bốn tên class exception trước (chúng nằm trong `11`). D sửa `hooks.py`: chỉ một phiên được làm việc đó, và sau đó cần restart.

## Thử đi (với những gì đang có)

1. Note có title `timeout x`: kết thúc `Synced` với một Xero id (trường hợp 3).
2. Note có title `fail x`: kết thúc `Failed`. Đổi tên nó trong Desk, gọi `retry_sync` từ SPA: `Queued` → `Synced`. Xem dòng outbox: cùng dòng đó, `attempts = 2`, cùng `idempotency_key` (`outbox.py:17-22`).
3. Thí nghiệm tưởng tượng cho trường hợp 2: đọc `frappe/database/database.py:1187-1194` và chỉ ra chính xác hai dòng mà một crash ở giữa chúng để lại một dòng `Pending` không có job.
4. Đọc `tasks/xero_sync.py` (51 dòng) và đánh dấu, từng dòng một, mỗi nhánh xử lý loại nào trong bốn loại thất bại. Thiếu hai loại: gọi tên chúng.

## Còn chưa biết

- Mọi thứ [G] về Xero: xem checklist ở cuối `10`.
- `on_submit` của chính ERPNext cho Sales Invoice có làm gì xung đột với một handler `doc_events` ghi custom field trong cùng lần save hay không; `erpnext/erpnext/hooks.py:377` mới chỉ được thấy như chỗ bắt đầu của `doc_events`.
- Ngữ nghĩa của `conversion_rate` bên ERPNext: sự có mặt của field đã xác nhận, ý nghĩa thì chưa đọc.
