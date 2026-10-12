# Kế hoạch tích hợp Frappe/ERPNext ↔ Xero

Kế hoạch đang có hiệu lực (xem `plan/overview.md`). Viết ngày 2026-10-12. File này **tự đủ**: không cần mở `plan/general/` để làm việc. Kiến thức đi kèm nằm trọn trong `docs/xero/` (bắt đầu ở `docs/xero/00-README.md`; hai luồng của đề bài ở `docs/xero/09`).

File này chỉ nói: làm gì, thứ tự nào, ai làm, xong khi nào. Các phiên code (Codex) tự quyết chi tiết bên trong mỗi phase; mục "Dữ kiện chung" là thứ duy nhất mọi phiên phải giữ giống nhau.

## Yêu cầu

### A. Của người giao việc (email của Engineering Lead, 2026-10-04; ảnh: `docs/xero/main-request.png`)

> Research how to integrate with the Xero application using Frappe. Feel free to integrate any processes or functions you have in mind. Suggestions:
> 1. Create Sales Order → Issue Invoice on Xero → Sync Invoice status back
> 2. Issue Credit Note on Xero → Sync the effect to related Sales Order.

Ba thứ phải giao:
- **Luồng 1**: Sales Order (ERPNext) → Invoice (Xero) → trạng thái invoice quay về Sales Order.
- **Luồng 2**: Credit Note được tạo **bên Xero** → ảnh hưởng của nó hiện trên Sales Order liên quan.
- **Một bản nghiên cứu**: tích hợp thế nào, giới hạn gì, tốn gì, khuyến nghị gì (chữ "research" là đề bài).

### B. Yêu cầu thêm của con người (đã chốt trong các phiên ngày 2026-10-12)

| # | Yêu cầu | Hệ quả trong kế hoạch |
|---|---|---|
| 1 | **Demo 0 đồng** | chỉ Demo Company + app Web app bậc Starter của Xero; không thẻ, không nâng bậc, không dịch vụ trả phí |
| 2 | **Không SPA** | giao diện là Desk: form Sales Order + vài nút |
| 3 | **Không Kafka, không container mới; nhẹ và tối giản** | MariaDB + Redis queue của Frappe + một bảng outbox; "log" của luồng là một field `journal` trên dòng outbox |
| 4 | **Không deploy** | chạy trên Docker Compose local; mọi kết nối đi từ máy ra Xero; chiều Xero → ta bằng polling, không webhook |
| 5 | **Demo chỉ có kịch bản "không đăng nhập Xero"** (chốt 2026-10-12): người dùng Frappe làm việc mà không có và không cần tài khoản Xero | job dùng một kết nối đã lưu sẵn. Kết nối đó do một admin bấm Connect **một lần lúc cài đặt (P0), trước buổi demo**; đây là bước không tránh được của Xero ở mức 0 đồng, không phải một kịch bản của demo. Kịch bản còn lại (người dùng đăng nhập bằng tài khoản Xero, hoặc mỗi người một kết nối riêng) để sau demo |
| 6 | **Demo có SAGA và không SAGA**, bằng một wrapper kiểu `@Transactional` | phase P4: `@xero_atomic` |
| 7 | **Luật nghiệp vụ cẩn thận, nhưng đây là demo** | ít luật, mỗi luật kiểm được; có danh sách "cố ý không xử lý" |
| 8 | **Code của ta sửa trực tiếp; chỉ code của Frappe/ERPNext/CRM mới đổi bằng override** | thứ gắn vào ERPNext nằm mỏng trong `overrides/`; tính năng Xero nằm trong `lab_xero/`, `tasks/`, `integrations/xero/` |
| 9 | **Kế hoạch thô, Codex viết code** | phase + dữ kiện chung + "xong khi"; không có danh sách bước |
| 10 | **Tài liệu tiếng Việt**, thuật ngữ giữ tiếng Anh kèm chú giải | kiến thức Xero trong `docs/xero/`, kiến thức chung trong `docs/knowledge/` |
| 12 | **Chỉ Xero thật.** Không có "Xero giả", không có hai chế độ có/không Xero (chốt 2026-10-12) | một client duy nhất gọi Xero thật (Demo Company); không công tắc giả/thật, không từ khóa kích lỗi trong code; client thế chỗ của sprint và đường "sync Lab Note" bị gỡ ở P1; lỗi trong demo là lỗi **thật** do Xero trả về |
| 13 | **Không cần unit test** cho demo này (chốt 2026-10-12) | không phase nào viết test; kiểm bằng tay theo "xong khi". Đây là ngoại lệ có chủ đích so với AGENTS.md B5, chỉ cho kế hoạch này. Các test cũ chỉ kiểm client thế chỗ bị gỡ cùng nó |
| 14 | **Luật nghiệp vụ do bên lập kế hoạch tự quyết**, không chờ người giao việc xác nhận, để xong sớm (chốt 2026-10-12) | mục "Luật nghiệp vụ của demo" là quyết định cuối cho demo; các lựa chọn được nêu rõ khi trình bày |
| 17 | **Cấu hình bằng code, không bằng Desk.** Thứ duy nhất bắt buộc làm trong Desk là tạo DocType mới (chốt 2026-10-12; khớp AGENTS.md A4, B3) | bản ghi Connected App "Xero" (URI, scope, tên cố định) và các giá trị của `Lab Xero Settings` được tạo bằng một hàm setup chạy lại an toàn sau migrate. Bí mật (`client_id`, `client_secret`) không nằm trong repo: con người đặt vào site config bằng lệnh, code đọc từ đó. Còn làm tay: tạo DocType, đăng ký app bên Xero, bấm Connect một lần |
| 16 | **Con người phải dễ dàng giải thích được code mình và AI đã viết**: phần tích hợp, cách nó xử lý transaction, và về sau là lớp lỗi (middleware) và SAGA. Không phải giải thích code lõi của Frappe; hiểu sâu Frappe thuộc kế hoạch chung (chốt 2026-10-12) | mỗi bước của agent kết thúc bằng vài dòng giải thích code của ta bằng lời thường; làn W có bước W4 (bản đi qua từng file của ta, có mục riêng về transaction) và W5 (thêm middleware, SAGA khi giai đoạn 2 làm xong) |
| 15 | **Mọi phần thêm chỉ ở mức demo**; làm kỹ sau khi demo xong (chốt 2026-10-12) | xem mục "Mức demo: làm đến đâu thì dừng"; hai luồng của email đi trước mọi phần thêm |
| 11 | **Xử lý lỗi và response thống nhất, kiểu middleware** (yêu cầu từ một phiên trước: "stack log quite ugly and raw and responses also raw"; nhắc lại ngày 2026-10-12 cho demo này) | phase PE: lỗi có tên và status code, một chỗ duy nhất định hình body lỗi cho endpoint của `lab_core`, không traceback trong response, có request id |

## Status (Trạng thái)

Đọc từ file trên đĩa ngày 2026-10-12. Trạng thái database, site, container: agent không xem được.

| Phase | Trạng thái | Ghi chú |
|---|---|---|
| P0. Chuẩn bị (bạn) | **NEXT** | Desk chưa làm: `lab_note.json` mới có `title`, `content` (`lab_core/lab_core/doctype/lab_note/lab_note.json:14, :21`); chưa có DocType nào dưới `lab_core/lab_xero/` |
| Code có sẵn từ sprint | WRITTEN, NOT RUN | **Giữ lại**: outbox (`lab_xero/outbox.py`) và khung job (`tasks/xero_sync.py`). **Phải gỡ ở P1** (yêu cầu 12): client thế chỗ `integrations/xero/client.py` (cả file là `FakeXeroClient`, `:26-52`), lời gọi `find_by_key` và payload `{"title": …}` trong job (`tasks/xero_sync.py:22-25`), và đường "sync Lab Note sang Xero" cùng các test dựa vào nó |
| P1. Luồng 1 chiều đi: Sales Order → Invoice | NOT STARTED | `hooks.py` chỉ có `website_route_rules` (`lab_core/hooks.py:8-10`); chưa có `setup/`, chưa có `overrides/` |
| P2. Chiều về: trạng thái invoice + Credit Note | NOT STARTED | |
| P5. Bản nghiên cứu + kịch bản demo | NOT STARTED | hết giai đoạn 1 |
| PE. Lỗi và response (tối thiểu) | WAITING (chờ giai đoạn 1) | `errors.py` mới có `LabConflictError`; chưa có hook `after_request` |
| P4. `@xero_atomic`, SAGA và không SAGA (tối thiểu) | WAITING (chờ giai đoạn 1) | |
| P3. Mất kết nối (tối thiểu) | WAITING (chờ giai đoạn 1) | |
| Sau nữa | DEFERRED | kịch bản đăng nhập bằng tài khoản Xero, webhook, sweeper, SAGA bền, deploy |

Đường dẫn code trong file này tính từ `frappe-bench/apps/lab_core/lab_core/`. Chỉ cập nhật bảng này khi con người yêu cầu hoặc nói một phase đã xong.

## Bức tranh

```text
P0 (bạn) ── tài khoản Xero + app + Connect ────────────────┐   rủi ro lớn nhất, làm TRƯỚC
         └─ Desk: DocType, role; ERPNext có Company/Customer/Item

P1 chiều đi (Codex viết được ngay; CHẠY được khi P0 xong) ─────────┤
        │                                                          ▼
        ▼                                             ★ DEMO 1: submit Sales Order → invoice hiện trong Demo Company
P2 chiều về (polling) ─────────────► ★ DEMO 2: duyệt/trả tiền bên Xero → trạng thái về Sales Order
        │                            ★ DEMO 3: tạo Credit Note bên Xero → số đã ghi giảm hiện trên Sales Order
        ▼
P5 bản nghiên cứu ─────────────────► thứ gửi lại cho người giao việc

════════ GIAI ĐOẠN 1 XONG: tích hợp Xero hoàn tất. Chỉ khi đó mới sang giai đoạn 2 ════════

PE lỗi và response (tối thiểu) ────► ★ DEMO E: cùng một lỗi, trước và sau: body gọn, đúng status, không traceback
P4 @xero_atomic (tối thiểu) ───────► ★ DEMO 5: cùng một lỗi thật, có SAGA và không SAGA
P3 mất kết nối (tối thiểu) ────────► ★ DEMO 4: gỡ connection → báo rõ → nối lại → Retry
```

**Hai giai đoạn, không trộn.** Giai đoạn 1 (P0, P1, P2, P5) là việc được giao: làm xong hẳn trước. Giai đoạn 2 (PE, P4, P3) là các ý thêm của con người, mỗi cái ở mức nhỏ nhất còn cho xem được, và **không phase nào của giai đoạn 2 được bắt đầu khi giai đoạn 1 chưa xong**. Trong giai đoạn 1, không xây trước thứ gì "cho PE" hay "cho P4": endpoint chỉ dùng các class lỗi đang có, Settings chưa có field của P4.

## Mức demo: làm đến đâu thì dừng

Hai luồng của email (P1, P2) và bản nghiên cứu (P5) là **lõi** (giai đoạn 1): làm cho chạy đúng. Mọi thứ còn lại là **phần thêm** (giai đoạn 2): chỉ bắt đầu sau khi DEMO 1, 2, 3 đã chạy và P5 đã viết, và mỗi cái chỉ cần một lát mỏng đủ để cho xem, không gia cố.

| Phần thêm | Mức tối thiểu (giai đoạn 2) | Để sau nữa |
|---|---|---|
| PE lỗi và response | hai class lỗi mới + một hàm thêm khối `error` và gỡ traceback cho endpoint của `lab_core` | dòng log riêng, ghi chú ADR, áp cho mọi endpoint, dạng thành công thống nhất |
| P4 `@xero_atomic` (SAGA) | **một** luồng hai bước, **một** lỗi thật, hai chế độ; wrapper giữ danh sách hoàn tác trong bộ nhớ của job | SAGA bền qua outbox, thử lại sau khi đã bù trừ, xử lý bù trừ hỏng ngoài việc báo `STUCK:`, mọi luồng khác |
| P3 mất kết nối | đơn báo `Failed` kèm lý do "cần nối lại", settings `paused`; nối lại rồi bấm Retry là chạy | sweeper tự động, giãn thời gian thử lại, đồng hồ rate limit dùng chung |
| Journal | một mảng các bước trên dòng outbox (làm cùng P4) | màn hình xem riêng, lưu request/response đầy đủ |

Riêng **idempotency** không phải phần thêm: hai thứ rẻ của nó (tra trước khi tạo; ghi đè/upsert khi kéo về) nằm ngay trong P1 và P2, vì thiếu chúng thì demo lõi sai. Phần còn lại của bảng Idempotency để sau.

Luật khi phân vân: nếu một việc không làm cho DEMO 1, 2, 3 chạy được, nó không thuộc giai đoạn 1.

## Dữ kiện chung (mọi phiên xây dựa vào)

### Đã có trong code (viết rồi, chưa chạy)

Giữ và xây tiếp:
- `lab_xero/outbox.py`: `queue(doc, operation="create_invoice")` ghi hoặc mở lại một dòng `Lab Xero Outbox` với key `"<doctype>:<name>:<operation>"`, rồi xếp job sau commit.
- `tasks/xero_sync.py`: `process_outbox(outbox_name)`: khung đúng (khóa dòng, bỏ qua dòng đã `Done`, ghi `Done` hoặc `Failed`); phần gọi client phải viết lại cho Xero thật.
- `errors.py`: `LabConflictError` (409). Endpoint chỉ raise, không catch.

Gỡ ở P1 (yêu cầu 12: chỉ Xero thật):
- `integrations/xero/client.py`: hôm nay cả file là một client thế chỗ lưu "invoice" trong cache và kích lỗi theo chữ trong title. Thay bằng client HTTP thật; hai class `XeroRejected`, `XeroTimeout` được giữ tên.
- Đường "sync Lab Note sang Xero": lời gọi `outbox.queue` trong `lab_core/doctype/lab_note/lab_note.py`, `retry_sync` trong `lab_core/notes.py` và `api/notes.py`, và các test của `api/test_notes.py` dựa vào hành vi `fail` / `timeout`. Một Lab Note không phải hóa đơn; đường này chỉ tồn tại để chạy client thế chỗ. `Lab Note` còn lại như một DocType mẫu của kế hoạch chung, không thuộc kế hoạch này.

Xóa hoặc sửa test là việc cần con người nói rõ (AGENTS.md A11): yêu cầu 12 là lời nói rõ đó cho các test chỉ kiểm hành vi của client thế chỗ.

### DocType do con người tạo trong Desk (P0)

| DocType | Field |
|---|---|
| `Lab Xero Outbox` (module Lab Xero) | `reference_doctype` (Link → DocType), `reference_name` (Dynamic Link → reference_doctype), `operation` (Data), `idempotency_key` (Data, unique), `status` (Select: Pending, Done, Failed; mặc định Pending), `attempts` (Int), `error` (Small Text), `xero_id` (Data). **Thêm sau, khi tới P4**: `journal` (JSON, read only). Permission: System Manager (tất cả) |
| `Lab Xero Settings` (single, module Lab Xero) | `connected_app` (Link → Connected App), `connected_user` (Link → User), `tenant_id`, `tenant_name` (Data), `default_account_code`, `default_tax_type` (Data), `last_pull_at` (Datetime). **Thêm sau, chỉ khi tới giai đoạn 2**: cho P3 `paused` (Check), `paused_reason` (Small Text); cho P4 `issue_mode` (Select: Invoice only / Invoice + payment / Invoice + payment (atomic); mặc định Invoice only), `payment_account_code` (Data) |
| `Lab Xero Credit Note` (module Lab Xero) | `sales_order` (Link → Sales Order), `xero_credit_note_id` (Data, unique), `credit_note_number` (Data), `xero_invoice_id` (Data), `date` (Date), `total` (Currency), `allocated_amount` (Currency), `status` (Data) |

`Lab Note`, role `Lab User` và user test của sprint thuộc kế hoạch chung; kế hoạch này không cần chúng.

### Custom field trên DocType của ERPNext

Tạo bằng code trong `setup/customizations.py` (AGENTS.md B2a mục 1), tất cả read only, no copy, allow on submit:

| DocType | Field |
|---|---|
| Customer | `lab_xero_contact_id` (Data, unique) |
| Sales Order | `lab_xero_sync_status` (Select: Not Synced / Queued / Synced / Failed), `lab_xero_invoice_id` (Data, unique), `lab_xero_invoice_number` (Data), `lab_xero_invoice_status` (Data), `lab_xero_amount_due`, `lab_xero_amount_paid`, `lab_xero_amount_credited` (Currency), `lab_xero_last_synced_at` (Datetime), `lab_xero_error` (Small Text) |

### Client (`integrations/xero/`)

**Một client duy nhất, gọi Xero thật.** Không có bản thế chỗ trong code của app, không có công tắc chọn bản.

```text
find_contact(contact_number) / create_contact(key, payload)      → contact_id
find_invoice(invoice_number) / create_invoice(key, payload)      → invoice_id
void_invoice(key, invoice_id)
create_payment(key, payload)                                     → payment_id      (chỉ cho P4)
get_invoices(ids | modified_since)                               → [{id, number, status, amount_due, amount_paid, amount_credited}]
get_credit_notes(modified_since)                                 → [{id, number, status, date, total, allocations: [{invoice_id, amount}]}]
exception: XeroRejected, XeroTimeout (giữ tên đang có) · XeroBusy(retry_after), XeroAuthLost (mới)
```

**Không viết test tự động** (yêu cầu 13). Bằng chứng là các DEMO chạy tay trên Demo Company; mỗi phase có danh sách "xong khi" để kiểm bằng mắt.

### Lỗi và response

Trong giai đoạn 1: endpoint của `lab_core` **chỉ raise, không catch**, bằng các class đang có (`frappe.PermissionError`, `frappe.DoesNotExistError`, `LabConflictError`). Thế là đủ.

Phần dưới đây chỉ dành cho PE (giai đoạn 2): hai class mới và lớp định hình body.

| Tình huống | Class | Status |
|---|---|---|
| không có quyền | `frappe.PermissionError` (của Frappe) | 403 |
| không tìm thấy | `frappe.DoesNotExistError` (của Frappe) | 404 |
| trạng thái không cho phép (Retry một đơn đã `Synced`, cancel một đơn đã có tiền trả) | `LabConflictError` (đang có trong `errors.py`) | 409 |
| dữ liệu đầu vào sai | `LabValidationError` (mới) | 422 |
| Xero chưa nối hoặc đang tạm dừng | `LabIntegrationUnavailableError` (mới) | 503 |

Body của một lỗi trên đường dẫn `/api/method/lab_core.` và `/api/v2/method/lab_core.`, sau khi đi qua lớp định hình:

```text
{ …các key gốc của Frappe được giữ lại, để Desk vẫn hiện được thông báo…,
  "error": { "code": "<tên class>", "message": "<thông báo đã dịch>", "status": 409, "request_id": "<X-Frappe-Request-Id>" } }
không có traceback trong body
```

Chỉ **thêm** key `error` và **gỡ** traceback; không đổi hay xóa các key Desk đang đọc. Request thành công không bị đụng tới. Lỗi của job gọi Xero không đi đường này: nó hiện trên Sales Order (luật 9).

### Luật kỹ thuật giữ nguyên

Gọi Xero chỉ trong `tasks/`; HTTP chỉ dựng trong `integrations/xero/`; ghi đi qua outbox và tra cứu trước khi tạo; `InvoiceNumber` bên Xero = `name` của Sales Order; sau submit ghi bằng `db_set`; lấy token (`get_active_token(user=settings.connected_user)`) trước lần ghi đầu tiên của job; không token nào trong log; không thêm package (chỉ `requests-oauthlib` đã có trong Frappe).

## Các phase

Giai đoạn 1 (việc được giao): **P0 → P1 → P2 → P5**. Giai đoạn 2 (ý thêm, tối thiểu, chỉ sau giai đoạn 1): **PE → P4 → P3**. Các mục dưới đây xếp theo số, không theo thứ tự làm.

### P0. Chuẩn bị (bạn)
- Xero: login, Demo Company (ghi lại quốc gia + currency), app Web app. Hướng dẫn: `docs/xero/01`, `02`.
- ERPNext: có một Company, một Customer, một Item bán được, tạo thử được một Sales Order.
- Desk: tạo ba DocType ở trên (chỉ các field của giai đoạn 1). Đây là việc duy nhất phải làm trong Desk.
- Kết nối được dựng **bằng code** (làn B, bước B0): hàm setup tạo Connected App "Xero" với tên cố định, URI và scope, và điền `Lab Xero Settings`. Bạn chỉ: đặt `client_id`, `client_secret`, mã tài khoản doanh thu và mã thuế vào site config bằng các lệnh mà làn B đưa kèm giải thích; migrate; đăng ký Redirect URI (cố định, làn B ghi ra) trong app Xero; rồi bấm Connect một lần và chọn Demo Company.
- **Xong khi:** Token Cache có token; bạn biết câu trả lời cho hai điều chưa biết (Xero có nhận redirect URI của lab không; Frappe có đổi được token với Xero không). Nếu câu thứ hai là "không", báo ngay: P1 phải tự viết bước đổi token.

### P1. Chiều đi: Sales Order → Invoice trên Xero
Việc đầu tiên: gỡ client thế chỗ và đường "sync Lab Note" (mục "Đã có trong code"), thay bằng client HTTP thật. Sau đó: custom field; handler `on_submit` / `on_cancel` của Sales Order (mỏng, trong `overrides/`) ghi dòng outbox; mapping Customer → Contact và Sales Order → Invoice; client hai bản; job xử lý `create_invoice` và `void_invoice`; nút "Retry" trên form Sales Order. Đụng `hooks.py` (`doc_events`, `doctype_js`, chỗ áp custom field).
- Xây đúng luật 1–5, 9, 10 ở mục "Luật nghiệp vụ của demo"; không thêm trường hợp ngoài danh sách đó.
- **Xong khi (DEMO 1):** submit một Sales Order → invoice hiện trong Demo Company với đúng khách và dòng hàng; `lab_xero_invoice_id` được lưu; chạy job lần hai không tạo invoice thứ hai; dữ liệu sai (ví dụ mã thuế) → `Failed` kèm lý do đọc được trên form, sửa rồi Retry được; cancel một đơn chưa có tiền trả → invoice `VOIDED`; cancel một đơn đã có tiền trả → bị chặn kèm lý do.

### P2. Chiều về: trạng thái invoice và Credit Note
Một job kéo theo lịch (và một nút "Refresh from Xero"): lấy invoice và credit note đã đổi kể từ `last_pull_at`; cập nhật các field `lab_xero_*` trên Sales Order; với mỗi credit note có allocation vào một invoice của ta → upsert một `Lab Xero Credit Note` và ghi một comment lên timeline của Sales Order. Đụng `hooks.py` (`scheduler_events`; cần migrate).
- Xây đúng luật 6–9; credit note chưa áp vào invoice nào thì bỏ qua.
- **Xong khi (DEMO 2):** ghi một payment cho invoice trong Xero → trong vòng một chu kỳ kéo, Sales Order hiện `PAID` và số đã trả.
- **Xong khi (DEMO 3):** tạo một Credit Note trong Xero và áp vào invoice → Sales Order hiện số đã ghi giảm, số còn nợ mới, và một dòng `Lab Xero Credit Note`; kéo hai lần không tạo dòng thứ hai.

### PE. Lỗi và response thống nhất (giai đoạn 2, tối thiểu)
Hai class lỗi mới trong `errors.py`; một hàm định hình body lỗi, đăng ký bằng hook `after_request`, chỉ tác động lên đường dẫn của `lab_core`. Hàm đó đổi **dạng lỗi do Frappe dựng**, tức hành vi của code không phải của ta, nên nằm dưới `overrides/`; endpoint của ta không bị hook hay override. Đụng `hooks.py`. Kiến thức và lý do: `docs/xero/11`.
- Không được làm: catch trong endpoint rồi trả một dict "thất bại" (request sẽ commit nửa dữ liệu); không viết lại body của request thành công; không đụng response của Desk, ERPNext, CRM.
- **Xong khi (DEMO E):** gọi Retry trên một đơn đã `Synced` từ ngoài Desk (ví dụ tab Network hoặc một công cụ gọi HTTP) → status 409, body có `error.code`, `error.message`, `error.request_id`, không có traceback; cùng thao tác đó trong Desk vẫn hiện một thông báo đọc được; request thành công có body y như trước.

### P3. Mất kết nối (giai đoạn 2, tối thiểu)
Chỉ một tình huống: mất kết nối với Xero. Job nhận ra token không còn dùng được → đơn báo `Failed` với lý do "cần nối lại Xero", `Lab Xero Settings.paused` bật kèm lý do; các lần submit sau đó không gọi Xero khi đang `paused`. Sweeper tự động và xử lý Xero bận để sau nữa.
- **Xong khi (DEMO 4):** gỡ connection bên Xero → submit một đơn → đơn báo `Failed` kèm lý do, settings `paused`; Connect lại, bỏ `paused`, bấm Retry → đơn sang Xero.

### P4. `@xero_atomic`: SAGA và không SAGA (giai đoạn 2, tối thiểu)
Phạm vi cố ý nhỏ: một luồng, một lỗi, hai chế độ, một field `journal`. Trên Xero thật (Demo Company): một luồng hai bước, tạo invoice rồi ghi một payment cho nó, chạy hai kiểu: có wrapper và không. Kiểu chạy chọn bằng `Lab Xero Settings.issue_mode`. Lỗi ở bước hai là **lỗi thật của Xero**: đặt `payment_account_code` thành một mã không nhận được tiền, Xero từ chối payment. Cần thêm scope `accounting.payments` (miễn phí; phải Connect lại). Thiết kế và hợp đồng của wrapper: `docs/xero/10`.
- Đây là ngoại lệ có chủ đích với danh sách "cố ý không xử lý" (ghi payment từ ERPNext): chỉ tồn tại để demo wrapper, mặc định tắt (`Invoice only`).
- **Xong khi (DEMO 5):** cùng một đơn, cùng một cấu hình sai → chế độ không wrapper: invoice còn sống trong Xero, đơn báo `Failed` (hai bên lệch); chế độ atomic: invoice bị void trong Xero, đơn báo `Failed` kèm "compensated" (hai bên khớp); sửa cấu hình cho đúng → cả hai bước xong. Nhìn thẳng trong giao diện Xero và trong `journal` của dòng outbox.

### P5. Bản nghiên cứu và kịch bản demo (kết thúc giai đoạn 1)
Một tài liệu ngắn gửi lại người giao việc: cách tích hợp, sơ đồ, hai luồng đã chạy, giới hạn (rate limit, key 6 phút, polling so với webhook, reset 28 ngày), chi phí khi lên thật, các quyết định nghiệp vụ còn mở, khuyến nghị. Kèm kịch bản demo từng bước.
- **Xong khi:** người chưa đọc code hiểu được trong mười phút, và mọi con số có nguồn.

### Sau deadline
Webhook (cần URL công khai); Payment Entry → Payment; SAGA bền qua outbox; nhiều organisation; deploy.

## Cách chạy các phiên

**Giai đoạn 1 được chia sẵn thành các làn không đụng file của nhau: `plan/xero/board/README.md`.** Mọi agent, dù một hay ba phiên, làm việc từ bảng đó: nhận một làn, làm một bước, ghi trạng thái vào file làn của mình, dừng. Khi con người hỏi "làm gì bây giờ?", câu trả lời lấy từ bảng đó.

```text
Làn H (bạn)  P0, rồi chạy các DEMO           Làn A  đường chính của P1        Làn B  field, endpoint, nút
Làn C        P2 (chờ client của làn A)       Làn W  P5: bản nghiên cứu, kịch bản demo, bản giải thích code

Giai đoạn 2, chỉ sau đó, từng cái một (đều nhỏ, đều đụng hooks.py hoặc job nên không song song):
  PE        errors.py, overrides/, hooks.py
  P4        lab_xero/atomic.py, client (create_payment), tasks/xero_sync.py; bạn: thêm field, thêm scope, Connect lại
  P3        tasks/xero_sync.py; bạn: thêm hai field paused
```

- `hooks.py` là điểm va chạm: P1, P2, PE, P3 đều sửa nó. Mỗi lúc một phiên; sau `doc_events` cần restart, sau `scheduler_events` cần migrate.
- Không phase nào viết test (yêu cầu 13). Mỗi phase kết thúc bằng việc con người chạy tay danh sách "xong khi" trên Demo Company, trong đó luôn có một lần "làm hai lần → một kết quả".
- Mọi lần chạy thử đều gọi Xero thật: nhớ hạn mức 1000 lời gọi/ngày của bậc Starter.
- Lệnh cho con người đi kèm giải thích; từ ba lệnh trở lên thì một script tạm (AGENTS.md A18).

## Luật nghiệp vụ của demo

Đây là demo: **ít luật, mỗi luật một câu kiểm được, không cố phủ mọi trường hợp.** Thứ gì không nằm trong các luật dưới đây thì nằm ở "Cố ý không xử lý", và được nói thẳng khi trình bày. Các phase chỉ xây đúng những luật này.

**Luật gốc: bên nào giữ sự thật về cái gì.** Mọi luật khác suy ra từ bảng này.

| Dữ liệu | Bên giữ sự thật | Bên kia |
|---|---|---|
| Đơn hàng: khách, dòng hàng, số lượng, đơn giá | ERPNext | Xero nhận **một lần**, lúc phát hành |
| Hóa đơn: số, thuế, tổng, trạng thái, đã trả, còn nợ | Xero | ERPNext chỉ hiển thị |
| Credit note | Xero | ERPNext chỉ hiển thị |

| # | Luật | Phase |
|---|---|---|
| 1 | **Phát hành.** Sales Order được submit → đúng một hóa đơn bán bên Xero, ở trạng thái đã duyệt (`AUTHORISED`). Đơn nháp không bao giờ sang Xero. | P1 |
| 2 | **Một đơn, một hóa đơn.** Số hóa đơn bên Xero là tên của Sales Order; id của Xero được lưu trên đơn và là duy nhất. Thử lại, bấm hai lần hay job trùng không bao giờ sinh hóa đơn thứ hai. | P1 |
| 3 | **Nội dung gửi đi.** Khách hàng (contact được tạo ở lần đầu, nhận diện bằng mã Customer), và từng dòng: mô tả, số lượng, đơn giá, theo tiền tệ của đơn. Tài khoản doanh thu và mã thuế lấy từ Settings. **Thuế và tổng tiền do Xero tính**; bảng thuế và chiết khấu của ERPNext không được gửi. | P1 |
| 4 | **Sau khi phát hành, ERPNext không sửa nội dung hóa đơn.** Việc duy nhất ERPNext còn làm với nó là hủy hiệu lực (void) khi đơn bị cancel. | P1 |
| 5 | **Cancel.** Chỉ cancel được khi, theo số liệu đã đồng bộ, hóa đơn chưa có tiền trả và chưa bị ghi giảm; khi đó hóa đơn bị void. Ngược lại: chặn, với thông báo nói rõ lý do. | P1 |
| 6 | **Trạng thái về.** Các field `lab_xero_*` trên đơn là bản sao của Xero, cũ tối đa một chu kỳ kéo (5 phút), hoặc mới ngay khi bấm Refresh. Không field có sẵn nào của ERPNext bị đổi. | P2 |
| 7 | **Credit note thuộc về một đơn** khi và chỉ khi nó được **áp (allocate)** vào hóa đơn của đơn đó bên Xero. Số tiền tính là số tiền được áp. | P2 |
| 8 | **"Ảnh hưởng" lên đơn là hiển thị**: đã ghi giảm, còn nợ, danh sách credit note, một dòng trên timeline. Không đổi tổng tiền, không đổi trạng thái của đơn, không sinh chứng từ ERPNext. | P2 |
| 9 | **Không gì hỏng trong im lặng.** Mọi thất bại hiện trên đơn (trạng thái + lý do đọc được), và sửa xong thì thử lại được. Gặp trường hợp ngoài luật, hệ thống **không đoán**: nó đánh dấu `Failed` kèm lý do, hoặc bỏ qua bản ghi không thuộc về mình. | P1, P2 |
| 10 | **Quyền.** Ai submit được đơn thì kích hoạt được đồng bộ. Retry và Refresh cần quyền ghi trên đơn đó. Nối Xero và sửa Settings: System Manager. Không ai cần tài khoản Xero ngoài người nối. | P1 |

**Điều kiện của kịch bản demo** (dữ liệu được chuẩn bị để nằm gọn trong các luật):
- một Company, một tiền tệ, trùng với tiền tệ gốc của Demo Company;
- Customer có tên không trùng contact nào đã có bên Xero;
- đơn một hoặc hai dòng, không thuế và không chiết khấu phía ERPNext;
- Settings có một mã tài khoản doanh thu và một mã thuế lấy từ chính Demo Company.

**Cố ý không xử lý** (mỗi cái là một quyết định nghiệp vụ của dự án thật, không phải của demo): đa tiền tệ và tỷ giá; thuế, chiết khấu, phí vận chuyển từ ERPNext; một đơn nhiều hóa đơn, lập hóa đơn từng phần; hóa đơn bị sửa nội dung bên Xero; credit note chưa áp, hoặc áp vào nhiều hóa đơn; ghi payment từ ERPNext; trả hàng khởi tạo từ ERPNext; nhiều organisation; ERPNext có Sales Invoice riêng song song.

**Các lựa chọn đã quyết cho demo** (yêu cầu 14: không chờ xác nhận). Mỗi dòng là một chỗ dự án thật có thể chọn khác; nói ra khi trình bày, như một phần của bản nghiên cứu.

| Luật | Đã chọn | Vì sao chọn vậy cho demo | Lựa chọn còn lại |
|---|---|---|---|
| 8 | "Effect" của Credit Note = **hiển thị** trên đơn | không đụng chứng từ đã submit; thấy được ngay; không có gì phải hoàn tác | tự giảm tổng, tự đóng đơn, hoặc sinh chứng từ trả hàng trong ERPNext |
| 3 | **Xero tính thuế** theo một mã thuế mặc định | Xero là sổ kế toán, nên con số thuế của nó là con số được báo cáo; tránh lệch do làm tròn giữa hai hệ thống | ERPNext quyết định thuế và gửi sang từng dòng (cần bảng ánh xạ mã thuế) |
| 1 | Hóa đơn sang Xero ở trạng thái **đã duyệt** | luồng 2 cần một hóa đơn đã duyệt để áp credit note; demo không phải dừng lại bấm duyệt | sang ở dạng nháp, kế toán duyệt trong Xero |
| 2 | Số hóa đơn = **tên Sales Order** | tra cứu chống trùng đơn giản và nhìn là biết đơn nào | dùng dãy số của Xero, đưa tên đơn vào `Reference` |
| — | Tiền tệ và vùng: **theo Demo Company** bạn mở ở P0; Company trong ERPNext dùng cùng tiền tệ | tránh đa tiền tệ | tổ chức thật có thể ở vùng khác: mã thuế và tài khoản nằm trong Settings nên đổi được |

## Idempotency (chạy lại bao nhiêu lần cũng ra một kết quả)

Yêu cầu xuyên suốt của kế hoạch này, không phải một phase. Mọi thứ dưới đây **sẽ** bị chạy lại trong đời thật: bấm đôi, job trùng, retry sau timeout, sweeper, lịch chạy chồng. Mỗi phase xây dòng nào thì phần "xong khi" của nó có một lần làm tay "hai lần → một kết quả" cho dòng đó (không viết test tự động: yêu cầu 13).

| Thao tác | Bị chạy lại khi | Thứ giữ cho nó idempotent | Phase |
|---|---|---|---|
| Submit → dòng outbox | bấm đôi, lưu lại, Retry | một dòng cho mỗi `"<doctype>:<name>:<operation>"` (field unique); `queue()` mở lại dòng cũ chứ không tạo dòng mới | P1 |
| Job tạo contact, tạo invoice | job trùng, retry sau timeout, sweeper | khóa dòng outbox + kiểm tra `Done`; **tra cứu bên Xero trước khi tạo** (theo `ContactNumber`, `InvoiceNumber`); id của Xero lưu vào field unique; header `Idempotency-Key` chỉ là lớp phụ (Xero nhớ key 6 phút) | P1 |
| Void khi cancel | cancel lại, retry | void một invoice đã void là không làm gì | P1 |
| Nút Retry, Refresh | bấm nhiều lần | endpoint chỉ xếp job, có `job_id` + `deduplicate`; Retry trên đơn đã `Synced` → 409 | P1, P2 |
| Kéo trạng thái invoice về | lịch chạy chồng, Refresh, kéo lại từ con trỏ cũ | **ghi đè** bằng giá trị hiện tại của Xero, không bao giờ cộng dồn; con trỏ `last_pull_at` chỉ tiến sau khi đã lưu | P2 |
| Kéo credit note về | như trên | upsert theo `xero_credit_note_id` (unique); comment trên timeline chỉ ghi ở lần đầu thấy | P2 |
| Áp custom field | migrate nhiều lần | tạo bằng `create_custom_fields` (cập nhật cái đã có, không tạo trùng) | P1 |
| Các bước của `@xero_atomic` | job chạy lại trong cùng một lần thử; Retry sau khi đã bù trừ | key của từng bước có số lần thử; bù trừ chạy hai lần vẫn an toàn (`docs/xero/10`) | P4 |

Ba luật rút gọn:
1. **Ghi sang Xero**: luôn "tra bằng số của ta → chưa có mới tạo → lưu id vào field unique". Không dựa vào `deduplicate` của queue hay vào key của Xero.
2. **Đọc từ Xero**: luôn ghi đè hoặc upsert; không có phép cộng nào.
3. **Tác động phụ không tự idempotent** (comment, thông báo): chỉ làm khi bản ghi chuyển từ "chưa thấy" sang "đã thấy".

Kiến thức: `docs/xero/07` (ba lớp chống trùng), `docs/xero/03` (key của Xero).

## Quyết định kỹ thuật đã chốt

- **Handler của Sales Order nằm dưới `overrides/`** (con người, 2026-10-12): thứ gắn vào ERPNext (handler `doc_events`, file JS của form) là thay đổi hành vi của code không phải của ta, nên mỏng và chỉ gọi hàm public của `lab_xero/`. Tính năng Xero là code của ta: sửa trực tiếp, không bao giờ bị hook hay override. AGENTS.md B2a mục 2 còn ghi `<domain>/events/`; dòng đó của con người sửa.
- **Chặn cancel (luật 5) dùng số liệu đã lưu trên đơn**, không gọi Xero trong request. Nếu số liệu cũ và Xero từ chối void: dòng outbox `Failed` kèm lý do (luật 9).
- **Dòng outbox** trong demo được ghi bởi user có quyền System Manager; ai sở hữu nó ở dự án thật để ngỏ.

## Demo vẫn phải đúng ở ba chỗ

Không phủ mọi trường hợp không có nghĩa là làm ẩu. Ba tính chất này được kiểm bằng tay trước buổi demo, vì thiếu chúng thì demo sai ngay trước mặt người xem:

1. **Chạy hai lần ra một kết quả**: submit, Retry, job trùng, kéo về hai lần (luật 2, 7).
2. **Hỏng thì thấy và thử lại được**: dữ liệu bị Xero từ chối; mất kết nối (luật 9).
3. **Tiền không bị bịa**: mọi con số trên đơn là số Xero trả về, không tự tính lại (luật gốc).

Tầm với khi gỡ tính năng: các hook trong `hooks.py` và các field `lab_xero_*`.

## Quan hệ với kế hoạch chung (`plan/general/`)

Không cần đọc để làm việc; ghi lại để khi quay lại lab không làm trùng hoặc ngược nhau. Các file bên đó chưa được sửa theo.

- Outbox và khung job được viết trong sprint của kế hoạch chung và được giữ lại ở đây.
- Sprint chạy trên một client thế chỗ thay cho Xero, với Lab Note làm "hóa đơn", và có 8 test cho đường đó. Kế hoạch này chỉ dùng Xero thật: client thế chỗ, đường sync của Lab Note và các test dựa vào chúng bị gỡ ở P1. Khi quay lại kế hoạch chung, sprint phải được viết lại theo đó.
- Sprint có các trang SPA cho Lab Note (F1, F2): không cần cho kế hoạch này.
- Kế hoạch chung muốn so sánh với một broker (Redpanda/Kafka) và có một cụm container cho log và trace: con người đã chọn không làm; ở đây thay bằng outbox + journal.
- Kế hoạch chung đặt track Xero sau các track nền và guardrails: ở đây nó đi trước vì deadline, nên guard decorator và response shape chung chưa có; endpoint mới theo đúng kiểu của `api/notes.py` hiện tại.
- `docs/xero/04` và `08` lấy **Sales Invoice** làm ví dụ; đề bài thật bắt đầu từ **Sales Order**. Bản đúng: `docs/xero/09`.

## Xong khi

**Giai đoạn 1 xong** khi DEMO 1, 2, 3 chạy trước mặt người xem trên Demo Company, bản nghiên cứu P5 đã gửi, con người giải thích được code của ta cho tích hợp, kể cả cách nó xử lý transaction (bước W4), và không khoản nào bị tính tiền. Đó là lúc việc được giao hoàn tất.

**Giai đoạn 2** là tùy chọn: DEMO E, 5, 4, mỗi cái ở mức tối thiểu. Làm kỹ hơn nữa chỉ khi con người yêu cầu.
