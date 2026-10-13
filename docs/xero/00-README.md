# Xero ↔ Frappe: gói tài liệu riêng cho việc tích hợp

Viết ngày 2026-10-12. Chỉ nói về một việc: đưa dữ liệu từ ERPNext (trên Frappe 16.51.0) sang Xero. **Gói này tự đủ: không cần mở `docs/knowledge/`.** Những phần của `docs/knowledge/` mà luồng Xero cần (transaction, hook, background job, scheduler, xử lý lỗi, SAGA, mapping, phần tối ưu cho Xero) đã được đưa vào đây, ở `06`–`08`. `docs/knowledge/` được giữ nguyên, không sửa gì, để bạn quay lại sau deadline; thứ duy nhất nằm lại bên đó là các chủ đề không phục vụ Xero (realtime, email + Jinja, file, Swagger, GraphQL/gRPC, chi tiết permission).

## Câu trả lời ngắn cho câu hỏi của bạn

- **Xero là phần mềm kế toán chạy online (SaaS: phần mềm thuê dùng qua web).** Không có bản cài đặt, không self-host (tự dựng server) được, không có Docker image. Server của Xero nằm ở phía Xero; ta chỉ gọi API của họ qua internet.
- **Phải tạo tài khoản**, miễn phí: một login Xero dùng chung cho cả phần mềm kế toán và trang developer. Không cần thẻ.
- **Không cần mua gì để demo.** Mỗi login có một **Demo Company** (công ty mẫu có sẵn dữ liệu) và bậc API **Starter** miễn phí.
- **Việc tích hợp là code của ta trong `lab_core`**: một job chạy nền đọc một dòng outbox (hộp thư đi) rồi gọi REST API của Xero bằng OAuth 2.0 token. Frappe đã có sẵn phần OAuth (DocType `Connected App`).

> **Ràng buộc cứng: demo này 0 đồng.** Không trả bất kỳ khoản nào cho Xero hay dịch vụ nào khác, không nhập thẻ ở đâu cả. Mọi lựa chọn trong gói này đã theo ràng buộc đó: Demo Company + app loại Web app ở bậc Starter. Danh sách "được dùng / không đụng vào" nằm ở `01`, mục "Luật 0 đồng". Nếu một bước nào đòi tiền hoặc thẻ: dừng lại, đó là dấu hiệu đi sai đường.

```text
 MÁY CỦA BẠN (Docker)                         INTERNET                 XERO (cloud, của Xero)
┌───────────────────────────────┐                              ┌──────────────────────────────┐
│ ERPNext: Sales Order          │                              │ login.xero.com   (đăng nhập)  │
│   │ submit                    │   1. trình duyệt của bạn ───►│ identity.xero.com (cấp token) │
│   ▼                           │◄── 2. code → token ──────────│                              │
│ Lab Xero Outbox (1 dòng)      │                              │ api.xero.com                 │
│   │ sau commit                │   3. HTTPS + Bearer token    │   /connections               │
│   ▼                           │      + xero-tenant-id        │   /api.xro/2.0/Invoices …    │
│ worker: tasks/xero_sync.py ───┼─────────────────────────────►│                              │
│   └─ integrations/xero/client │◄──── 4. InvoiceID ───────────│ Demo Company (sổ sách mẫu)   │
└───────────────────────────────┘                              └──────────────────────────────┘
        chiều ngược lại (Xero gọi ta = webhook) cần URL công khai → không làm trong demo
```

## Thứ tự đọc

```text
Vòng 1: hiểu bức tranh (~60 phút)          Vòng 2: hiểu vì sao nó đúng (~40 phút)      Tra cứu khi xây
 01 Xero là gì                              06 nền tảng Frappe                          08 mapping + chi tiết
 02 OAuth và kết nối                        07 thất bại, sweeper, SAGA
 03 Accounting API
 04 trong Frappe
 05 việc cần làm  ← mở lại mỗi khi ngồi vào bàn
 09 đề bài thật và hai luồng  ← đọc ngay sau 01 nếu muốn biết đích trước
                                            10 @xero_atomic, SAGA demo (phần thêm)
```

| # | File | Trả lời câu hỏi | Phút |
|---|---|---|---|
| 1 | `01-xero-la-gi.md` | Xero là gì, online hay self-host, tài khoản, Demo Company, tiền, Việt Nam | 10 |
| 2 | `02-oauth-va-ket-noi.md` | Làm sao app của ta được phép gọi Xero: app, scope, token, tenant; phần Frappe có sẵn | 15 |
| 3 | `03-accounting-api.md` | Gọi API thế nào: verb, invoice, lỗi, rate limit, idempotency, webhook | 15 |
| 4 | `04-trong-frappe.md` | Code nằm ở đâu trong `lab_core`, hôm nay có gì, còn thiếu gì | 15 |
| 5 | `05-viec-can-lam.md` | Danh sách việc theo thứ tự, việc nào song song, tự kiểm tra | 5 |
| 6 | `06-nen-tang-frappe.md` | Transaction và commit, hook `doc_events`, background job, scheduler: đúng phần Xero dựa vào | 20 |
| 7 | `07-that-bai-va-saga.md` | Sáu trường hợp thất bại, bốn loại lỗi, idempotency ba lớp, sweeper, hai kênh lỗi, SAGA, tối ưu | 20 |
| 8 | `08-mapping-va-chi-tiet.md` | Mapping đầy đủ, custom field, client HTTP, nút Connect, webhook, bảng quyết định | tra cứu |
| 9 | `09-yeu-cau-va-hai-luong.md` | **Đề bài thật** (`main-request.png`): Sales Order → Invoice → trạng thái về; Credit Note trên Xero → Sales Order; giao diện Desk, không SPA | 15 |
| 10 | `10-atomic-va-saga-demo.md` | `@xero_atomic` so với `@Transactional`; demo có SAGA và không SAGA; journal; vì sao không Kafka | 10 |
| 11 | `11-loi-va-response.md` | "Middleware" xử lý lỗi của Frappe ở đâu; lỗi có tên và status; một chỗ định hình body lỗi cho endpoint của ta; vì sao không catch trong endpoint | 10 |

**Kế hoạch** (làm gì, thứ tự nào, ai làm): `plan/done/xero/PLAN.md`. `05` là bản một trang của nó.

Nếu chỉ đọc được ba file hôm nay: `09` (đề bài), `02` (kết nối), `05` (việc của bạn).

Lưu ý: `04` và `08` được viết trước khi có email đề bài và lấy **Sales Invoice** làm ví dụ. Cơ chế trong đó vẫn đúng; tài liệu khởi đầu của luồng thật là **Sales Order**, và bản đúng là `09`.

**Thư mục con `knowledge/`**: kiến thức nền, mỗi khái niệm một file, đọc khi một từ trong `01`–`10` còn mơ hồ. Kho kiến thức chung `docs/knowledge/` vẫn giữ phần tương ứng, để nó còn đầy đủ khi bạn quay lại.

| File | Khái niệm | Bên `docs/knowledge/` |
|---|---|---|
| `knowledge/oauth.md` | OAuth 2.0 đầy đủ: bài toán, bốn vai, từng bước với HTTP thật, hai token, tenant, ba kiểu xin token, code Frappe từng dòng, bảng lỗi | `10` (mục OAuth) và `11`; file ở đây mới và đầy đủ hơn |
| `knowledge/webhook.md` | Webhook là gì, so với polling; DocType `Webhook` của Frappe; endpoint nhận; webhook của Xero; vì sao localhost không nhận được | `17-webhooks.md` (bản song sinh) |

Cách đọc khi khó tập trung: mỗi file một lượt, không mở file khác giữa chừng; cuối mỗi file có 3 câu hỏi, trả lời được thì sang file sau. Nếu chỉ có một giờ: vòng 1 là đủ để bắt tay làm; vòng 2 đọc khi bắt đầu viết job thật.

## Tin mỗi dòng đến mức nào

| Nhãn | Nghĩa |
|---|---|
| **[X]** | Đọc hôm nay trên trang chính thức của Xero (`developer.xero.com/pricing`, `/faq/limits`, `/faq/pricing-and-policy-updates`). |
| **[X*]** | Trang chính thức của Xero nhưng chỉ đọc được qua trích đoạn của công cụ tìm kiếm (trang `documentation/…` của Xero không tải được nội dung bằng công cụ của tôi). Đáng tin, nên mở trang đó một lần để chắc. |
| **[3]** | Bài của bên thứ ba (Apideck, Nango, Hookdeck…) đọc hôm nay. Khớp nhau nhưng không phải lời của Xero. |
| **[G]** | Kiến thức chung từ trí nhớ, hôm nay chưa đối chiếu. |
| **[S]** | Source trên đĩa đã mở hôm nay, có `path:line`. Đường dẫn Frappe bắt đầu từ `frappe-bench/apps/frappe/`, của ta từ `frappe-bench/apps/lab_core/lab_core/`. |
| **[K]** | Chép từ `docs/knowledge/` (phiên 2026-10-11 đã mở source và ghi `path:line`); hôm nay **không** mở lại dòng đó. |

Chưa ai chạy gì với một tài khoản Xero thật. Thứ duy nhất chứng minh được một dòng [G] là một lời gọi thử vào Demo Company.

## Bốn điều hôm nay tìm ra khác với `docs/knowledge/10-xero-api.md`

File cũ viết hoàn toàn từ trí nhớ và vẫn giữ nguyên bên đó. Bốn điểm này làm đổi thiết kế; **khi hai nơi khác nhau, gói này đúng hơn**:

1. **Scope đã đổi tên.** App tạo từ 2026-03-02 không còn `accounting.transactions`; phải dùng `accounting.invoices`, `accounting.payments`… [3] (`02`)
2. **Idempotency key chỉ được Xero nhớ 6 phút** [X*], không phải nhiều ngày. Lần retry muộn phải tự tra cứu theo `InvoiceNumber`. (`03`)
3. **Bậc Starter miễn phí: 5 connection, 1000 lời gọi/ngày mỗi organisation** [X], không phải 25 connection và 5000/ngày. (`01`, `03`)
4. **Request tối đa 3.5 MB, thực tế khoảng 50 bản ghi mỗi lần ghi** [X]. (`03`)

## Nguồn

- [Xero developer pricing](https://developer.xero.com/pricing) · [FAQ: pricing and policy updates](https://developer.xero.com/faq/pricing-and-policy-updates) · [FAQ: limits](https://developer.xero.com/faq/limits)
- [Xero: Idempotent requests](https://developer.xero.com/documentation/guides/idempotent-requests/idempotency/) · [Xero devblog: changes to Accounting API scopes](https://devblog.xero.com/upcoming-changes-to-xero-accounting-api-scopes-705c5a9621a0)
- [Apideck: Xero scopes](https://apideck.com/blog/xero-scopes) · [Nango: Xero refresh token invalid_grant](https://nango.dev/blog/xero-oauth-refresh-token-invalid-grant) · [Hookdeck: guide to Xero webhooks](https://hookdeck.com/webhooks/platforms/guide-to-xero-webhooks-features-and-best-practices)
- [Xero devblog: test orgs](https://devblog.xero.com/test-xero-orgs-for-certified-apps-9643a8475390) · [Xero free trial](https://www.xero.com/my/xero-free-trial/) · [Digita: Xero và VAS](https://digita.vn/?p=759) · [Fivetran: Xero connector](https://fivetran.com/docs/connectors/applications/xero)
