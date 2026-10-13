# 09. Yêu cầu thật và hai luồng phải demo

Email giao việc: `main-request.png` (cùng thư mục). Kế hoạch làm: `plan/done/xero/PLAN.md`. File này giải thích **hai luồng đó hoạt động thế nào**, từ đầu tới cuối.

Nhãn: xem `00-README.md`. Tên field của Sales Order là [S]: hôm nay đã xác nhận sự có mặt trong `frappe-bench/apps/erpnext/erpnext/selling/doctype/sales_order/sales_order.json` và `sales_order_item/sales_order_item.json` (chỉ sự có mặt, không kiểm tra kiểu). Field của Xero là [G] trừ khi ghi khác.

## Trả lời trong năm dòng

1. Đề bài: nghiên cứu cách tích hợp Xero bằng Frappe, với hai gợi ý: **(1)** tạo Sales Order → phát hành Invoice trên Xero → đồng bộ trạng thái invoice về; **(2)** phát hành Credit Note trên Xero → đồng bộ ảnh hưởng về Sales Order liên quan.
2. Luồng 1 có hai nửa: **đi** (ta ghi sang Xero: outbox + job) và **về** (ta đọc từ Xero: polling).
3. Luồng 2 **bắt đầu bên Xero**: kế toán tạo Credit Note trong giao diện Xero. Ta chỉ **đọc** và phản ánh lên Sales Order.
4. **Không cần SPA.** Mọi thứ người dùng thấy nằm trên form Sales Order của Desk: vài field read-only và hai nút.
5. Chiều về làm bằng polling vì lab chạy local không nhận được webhook (`knowledge/webhook.md`); 0 đồng, không deploy.

## Ai làm gì, ở đâu

```text
NGƯỜI BÁN HÀNG (Frappe, không có tài khoản Xero)          KẾ TOÁN (giao diện web của Xero)
  tạo + submit Sales Order                                   thấy invoice mới
        │  ① chiều đi                                        duyệt / ghi nhận thanh toán
        ▼                                                    tạo Credit Note, áp vào invoice
  Sales Order hiện: Xero invoice, trạng thái,                      │
  còn nợ, đã trả, đã ghi giảm     ◄──────── ② ③ chiều về ──────────┘
```

Một admin bấm "Connect to Xero" **một lần**; sau đó không ai phải đăng nhập Xero để dùng Frappe (`02`).

## Luồng 1, nửa đi: Sales Order → Invoice trên Xero

```text
submit Sales Order (Desk)
 └─ on_submit (doc_events → handler mỏng trong overrides/)  trong transaction của lần submit
      ghi dòng Lab Xero Outbox: operation=create_invoice, reference=Sales Order
      lab_xero_sync_status = "Queued"
 ── commit ──
 ▼ worker (tasks/)
 lấy token + tenant                                          trước lần ghi đầu tiên (06)
 khách đã có bên Xero chưa?  lab_xero_contact_id trống →
      tìm theo ContactNumber; không có → tạo Contact; lưu ContactID lên Customer
 invoice đã có bên Xero chưa?  GET /Invoices?InvoiceNumbers=<tên Sales Order>
      có  → lấy InvoiceID                                    ← chống tạo trùng (03, 07)
      chưa → POST /Invoices  (+ Idempotency-Key)
 ghi lên Sales Order: lab_xero_invoice_id, _number, _status, sync_status = "Synced"
 lỗi → theo bốn loại (07): Rejected → "Failed" + lab_xero_error; người sửa dữ liệu, bấm Retry
```

Mapping (ánh xạ field):

| ERPNext `Sales Order` | Xero `Invoice` | Ghi chú |
|---|---|---|
| — | `Type` = `ACCREC` | hóa đơn bán |
| `name` | `InvoiceNumber` | tay nắm để tra cứu; quyết định tạm |
| `customer` → `lab_xero_contact_id` | `Contact.ContactID` | contact phải có trước |
| `transaction_date` | `Date` | |
| `delivery_date` | `DueDate` | tạm; hạn thanh toán thật là câu hỏi cho kế toán |
| `po_no` | `Reference` | |
| `currency` | `CurrencyCode` | phải được bật trong organisation |
| `items[].description` / `item_name`, `qty`, `rate` | `LineItems[].Description`, `Quantity`, `UnitAmount` | |
| — | `LineItems[].AccountCode`, `TaxType` | lấy từ `Lab Xero Settings` (mặc định) cho demo; về sau là bảng mapping. **Giá trị cho Demo Company (Global), đã xác nhận ngày 2026-10-12** bằng màn hình Chart of accounts và `GET /TaxRates` trong API Explorer: `AccountCode` = `200` (Sales, loại Revenue), `TaxType` = `NONE` ("Tax Exempt", 0%, áp được cho doanh thu, đang ACTIVE) |
| `grand_total`, `total_taxes_and_charges` | `Total`, `TotalTax` | **không gửi**: trong demo thuế và tổng do Xero tính; bảng thuế và chiết khấu của ERPNext không sang Xero (luật 3 trong `plan/done/xero/PLAN.md`). Vì vậy đơn demo không có thuế phía ERPNext |
| `docstatus` 1 | `Status` = `AUTHORISED` | quyết định tạm |
| `docstatus` 2 (cancel) | `Status` = `VOIDED` | bị Xero chặn nếu đã có payment/credit |

Customer → Contact: `name` → `ContactNumber`, `customer_name` → `Name` (unique bên Xero), kết quả `ContactID` → `lab_xero_contact_id`. Bảng đầy đủ: `08`.

Hai hệ quả cần nói với người xem demo:
- **ERPNext vẫn nghĩ đơn chưa được lập hóa đơn.** Field có sẵn của Sales Order (`status` với các giá trị "To Bill", "To Deliver and Bill"…, `per_billed`, `billing_status`) được ERPNext tính từ Sales Invoice **của chính nó**. Ta không tạo Sales Invoice trong ERPNext và không đụng các field đó; sự thật về hóa đơn nằm ở các field `lab_xero_*`. Dự án thật phải quyết: Xero là nơi duy nhất có hóa đơn, hay ERPNext cũng có một bản.
- **Sales Order đã submit thì không sửa được.** Muốn sửa phải cancel rồi amend → tên mới (`…-1`) → invoice mới bên Xero; cái cũ bị void.

## Luồng 1, nửa về: trạng thái invoice quay về

Trạng thái thay đổi **bên Xero**, do kế toán: duyệt, nhận tiền, void. Ta không được báo; ta phải hỏi.

```text
mỗi N phút (scheduler)  hoặc  nút "Refresh from Xero" trên Sales Order
 ▼ job kéo (tasks/)
 GET /Invoices   header If-Modified-Since: <last_pull_at>      chỉ những invoice đã đổi [X: Xero khuyên dùng]
 với mỗi invoice có InvoiceID khớp một Sales Order của ta:
      lab_xero_invoice_status   ← Status        DRAFT | SUBMITTED | AUTHORISED | PAID | VOIDED | DELETED
      lab_xero_amount_due       ← AmountDue
      lab_xero_amount_paid      ← AmountPaid
      lab_xero_amount_credited  ← AmountCredited
      lab_xero_last_synced_at   ← bây giờ
 lưu xong hết rồi mới đẩy last_pull_at lên
```

| Kế toán làm bên Xero | Sales Order hiện |
|---|---|
| ghi nhận một phần tiền | `AUTHORISED`, đã trả > 0, còn nợ giảm |
| ghi nhận đủ tiền | `PAID`, còn nợ 0 |
| void invoice | `VOIDED` |

Vì sao an toàn khi chạy lại: job chỉ **ghi đè giá trị hiện tại** của Xero lên các field; kéo hai lần cho cùng kết quả. Vì vậy con trỏ `last_pull_at` có thể lùi lại một chút cho chắc, không sợ trùng.

Chi phí rate limit: một lời gọi trả về mọi invoice đã đổi (100 mỗi trang). Kéo 5 phút một lần ≈ 290 lời gọi/ngày; bậc Starter cho 1000/ngày [X]. Đừng kéo theo phút.

## Luồng 2: Credit Note trên Xero → Sales Order

**Credit note** (giấy báo có / ghi giảm công nợ) là chứng từ kế toán dùng khi giảm số tiền khách phải trả: trả hàng, giảm giá sau khi đã xuất hóa đơn, xuất nhầm. Trong Xero nó là một bản ghi riêng (`Type: ACCRECCREDIT`), và để "trừ" vào một invoice cụ thể thì kế toán **allocate** (phân bổ, áp) nó vào invoice đó. Allocation trỏ tới invoice bằng `InvoiceID` [3].

```text
kế toán (Xero): New Credit Note cho khách → Approve → "Allocate credit" vào invoice SAL-ORD-…
        │
        ▼  cùng job kéo ở trên, thêm một lời gọi
 GET /CreditNotes   If-Modified-Since: <last_pull_at>
 với mỗi credit note, với mỗi allocation của nó:
      allocation.Invoice.InvoiceID  ──khớp──►  Sales Order có lab_xero_invoice_id đó
      upsert một dòng "Lab Xero Credit Note"   (unique theo xero_credit_note_id → kéo lại không sinh dòng thứ hai)
      lần đầu thấy: thêm một comment vào timeline của Sales Order
 và invoice liên quan cũng "đã đổi" → nửa về của luồng 1 cập nhật amount_credited, amount_due, có thể thành PAID
```

"Ảnh hưởng lên Sales Order" trong demo nghĩa là:

| Thấy trên Sales Order | Từ đâu |
|---|---|
| Đã ghi giảm (`lab_xero_amount_credited`) | `AmountCredited` của invoice |
| Còn nợ (`lab_xero_amount_due`) | `AmountDue` của invoice |
| Trạng thái (có thể thành `PAID` nếu credit phủ hết) | `Status` của invoice |
| Danh sách credit note (số, ngày, số tiền áp) | các dòng `Lab Xero Credit Note` |
| Một dòng trên timeline: "Credit Note CN-… 110.00 được áp trên Xero" | comment |

**Đây là cách đọc tối thiểu của chữ "effect", và là câu hỏi phải hỏi lại người giao việc.** Các cách đọc mạnh hơn (tự giảm tổng tiền của Sales Order, tự close/cancel đơn khi được ghi giảm hết, tạo Sales Invoice trả hàng trong ERPNext) đều là luật nghiệp vụ, đụng tới chứng từ đã submit, và khó hoàn tác; không làm khi chưa được xác nhận.

Các trường hợp biên:

| Trường hợp | Xử lý trong demo |
|---|---|
| Credit note chưa áp vào invoice nào | bỏ qua (không biết thuộc Sales Order nào) |
| Một credit note áp vào hai invoice | hai allocation → mỗi Sales Order một dòng với số tiền riêng (khóa unique khi đó phải là credit note + invoice) |
| Allocation bị gỡ, hoặc credit note bị void sau khi đã kéo về | lần kéo sau thấy `status` mới / không còn allocation → cập nhật dòng, không xóa |
| Credit note cho invoice không do ta tạo | không khớp `lab_xero_invoice_id` nào → bỏ qua |

## Giao diện: Desk, không SPA

| Thứ | Làm bằng | Bằng chứng điểm mở rộng |
|---|---|---|
| Một section "Xero" trên form Sales Order với các field `lab_xero_*` | Custom Field tạo bằng code (`create_custom_fields`) trong `setup/customizations.py` | [S] `frappe/custom/doctype/custom_field/custom_field.py:322`; chạy sau migrate qua hook `after_migrate` ([S] `frappe/hooks.py:328`) |
| Nút "Retry" và "Refresh from Xero" | một file JS gắn vào form qua hook `doctype_js` | [S] hook có thật: `frappe/hooks.py:47`, `erpnext/erpnext/hooks.py:64` |
| Nút gọi hai endpoint của ta | `@frappe.whitelist(methods=["POST"])`, có kiểm tra quyền; endpoint chỉ **xếp job**, không gọi Xero | AGENTS.md B4 |
| Xem hàng đợi và lỗi | danh sách `Lab Xero Outbox` trong Desk | |
| Xem credit note | danh sách `Lab Xero Credit Note`, lọc theo Sales Order | |
| Nối / nối lại Xero | form `Connected App` (nút Connect có sẵn) + `Lab Xero Settings` | `02` |

Vì sao bỏ SPA là đúng với đề bài: người dùng của luồng này đang ở trong Desk (Sales Order là form của ERPNext). Một SPA riêng chỉ thêm việc mà không thêm gì cho câu hỏi "tích hợp Xero thế nào".

## Scope cần xin

`offline_access`, `accounting.invoices` (gồm cả credit note [3]), `accounting.contacts`, `accounting.settings.read`. Không cần `accounting.payments`: ta chỉ **đọc** số đã trả từ invoice, không ghi payment.

## Kịch bản demo (ba cảnh, khoảng năm phút)

1. **Đi:** trong Desk, tạo và submit một Sales Order → mở Xero (Demo Company) → invoice ở đó, đúng khách, đúng dòng hàng. Trên Sales Order: `Synced`, có số invoice.
2. **Về:** trong Xero, ghi nhận thanh toán cho invoice → trong Desk bấm "Refresh from Xero" → `PAID`, còn nợ 0.
3. **Credit Note:** với một Sales Order khác đã sync: trong Xero tạo Credit Note, áp vào invoice → Refresh → Sales Order hiện số đã ghi giảm, một dòng credit note, một comment trên timeline.

Cảnh thêm nếu còn giờ: submit một đơn có dữ liệu sai → `Failed` kèm lý do của Xero → sửa → Retry (`07`); và demo `@xero_atomic` (`10`).

## Chưa biết, phải thử trên Demo Company

- Tên chính xác của các field trong allocation của credit note, và danh sách credit note có trả sẵn `Allocations` hay phải `GET` từng cái.
- `GET /Invoices` với `If-Modified-Since` có coi "được áp credit note" là một thay đổi của invoice hay không (nếu không: lấy invoice theo `IDs` từ các allocation).
- `POST /Invoices` với `InvoiceNumber` đã tồn tại: cập nhật hay báo lỗi.
- Xero có chặn `InvoiceNumber` trùng với dãy số tự động của nó không.

## Tự kiểm tra

1. Trong hai luồng, lúc nào ta **ghi** sang Xero và lúc nào ta chỉ **đọc**? Cơ chế nào dùng cho mỗi chiều?
2. Kế toán tạo một Credit Note bên Xero. Kể đường đi cho tới khi con số hiện trên Sales Order, và nói vì sao kéo hai lần không tạo dòng trùng.
3. Vì sao field `status` có sẵn của Sales Order không đổi thành "đã lập hóa đơn" dù invoice đã có bên Xero?
