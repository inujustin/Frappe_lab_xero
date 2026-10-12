# 10. Xero API: phía bên kia trông thế nào

**Mọi dòng trong file này là [G]: viết từ trí nhớ về tài liệu developer công khai của Xero, hôm nay chưa kiểm tra.** Trên đĩa này không có code Xero và không trang nào được tải về. Hình dạng và các ý tưởng thì ổn định và học an toàn. Con số chính xác, tên scope và các giới hạn thì thay đổi: những cái dễ đã đổi nhất được đánh dấu **(verify)** (cần kiểm chứng). Kiểm tra chúng tại `developer.xero.com` khi bạn online, trước khi bất kỳ code nào phụ thuộc vào chúng.

## Mô hình trong bảy dòng

1. Một **organisation** (tổ chức) của Xero là sổ sách của một công ty. Xero gọi nó là một **tenant**.
2. **App** của bạn (client id + secret) được đăng ký một lần tại Xero.
3. Một **user** của Xero kết nối app của bạn với một hoặc nhiều organisation của họ. Mỗi mối nối là một **connection**.
4. Bạn nhận một **access token** (sống ngắn) và một **refresh token** (sống dài) cho user đó.
5. Mọi lời gọi API nói rõ nó dành cho organisation nào bằng một header: `xero-tenant-id`.
6. API là REST trên JSON: `Contacts`, `Invoices`, `Payments`, `CreditNotes`, `Accounts`, `TaxRates`, `Items`…
7. Xero tự bảo vệ bằng rate limit (giới hạn tần suất gọi) và bảo vệ bạn bằng idempotency key (khóa chống gửi trùng).

```text
app của bạn ──(client id/secret)── Xero identity
   │                                 │
   │  user đăng nhập, chọn organisation, đồng ý (consent)
   │◄──────── code ──────────────────┘
   │──────── code → tokens ─────────►
   │◄─ access_token (30 phút) + refresh_token (60 ngày, dùng một lần) ─
   │
   │  GET /connections  → [{ tenantId, tenantName, tenantType }]
   │
   │  GET/POST/PUT https://api.xero.com/api.xro/2.0/<Resource>
   │      Authorization: Bearer <access_token>
   │      xero-tenant-id: <tenantId>
   │      Accept: application/json
   │      Idempotency-Key: <key của bạn>       (các lần ghi)
```

## OAuth 2.0 với Xero

Authorization code flow chuẩn.

| Bước | URL | Ghi chú |
|---|---|---|
| Đưa user tới | `https://login.xero.com/identity/connect/authorize` | query: `response_type=code`, `client_id`, `redirect_uri`, `scope`, `state` |
| Đổi code, và refresh | `https://identity.xero.com/connect/token` | POST form; client id + secret dưới dạng HTTP Basic auth |
| Liệt kê connection | `https://api.xero.com/connections` | GET với bearer token |
| Gỡ một connection | `https://api.xero.com/connections/{id}` | DELETE |
| Thu hồi refresh token | `https://identity.xero.com/connect/revocation` | POST |

Token:

| Token | Thời gian sống | Hành vi |
|---|---|---|
| Access token | 30 phút | một JWT; gửi dưới dạng `Authorization: Bearer` |
| Refresh token | 60 ngày nếu không dùng | **Rotate (xoay vòng)**: mỗi lần refresh trả về một refresh token mới và cái cũ ngừng hoạt động. Một khoảng ân hạn ngắn cho phép bạn thử lại với cái cũ nếu câu trả lời bị thất lạc **(verify độ dài)**. |
| ID token | — | chỉ có với scope `openid`; cho biết user là ai |

Rotation có nghĩa gì trong thực tế:
- Refresh token mới **phải được lưu trước khi bất cứ thứ gì khác có thể hỏng**. Mất nó là connection chết; một con người phải bấm "Connect" lại.
- **Hai worker không được refresh cùng lúc.** Một cái thắng, cái kia cầm một token chết. Bắt buộc phải có lock. Client của Frappe có một cái (`11`).
- Nếu không gì gọi Xero trong 60 ngày thì connection chết. Một lần refresh "keep alive" (giữ sống) nhỏ theo lịch ngăn được việc đó.

Scope (phạm vi quyền; cách nhau bằng dấu cách):

| Scope | Cho |
|---|---|
| `offline_access` | một refresh token. Không có nó bạn được 30 phút và không gì thêm. |
| `openid profile email` | user là ai |
| `accounting.transactions` | invoice, credit note, payment, bank transaction (đọc + ghi) |
| `accounting.contacts` | contact |
| `accounting.settings` | account, tax rate, tracking category, currency |
| `accounting.attachments` | attachment (tệp đính kèm) |
| các biến thể `….read` | chỉ đọc |

**(verify)** Xero đang chuyển sang các scope chi tiết hơn cho những app mới tạo (khoảng đầu 2026), tách cái `accounting.transactions` rộng ra. Kiểm tra trang scope trước khi đăng ký app: một app tạo hôm nay có thể cần những cái tên khác với bảng trên.

Loại app:

| Loại | Flow | Dành cho |
|---|---|---|
| Web app | authorization code + client secret | ta: một server giữ được secret |
| Mobile / desktop | authorization code + PKCE, không secret | các app không giữ được secret |
| Custom connection | client credentials, một organisation, không có bước của user | máy với máy; một tùy chọn trả phí, giới hạn theo vùng **(verify)** |

Các dữ kiện khác: một app chưa được Xero chứng nhận có trần nhỏ về số connection (25 **(verify)**); Xero đã đưa ra các bậc giá API theo số connection **(verify)**; và mọi tài khoản đều mở được một **Demo Company** miễn phí, có dữ liệu mẫu, tự reset sau vài tuần. Hãy dùng Demo Company cho mọi thứ trong lab này.

Redirect URI phải khớp chính xác với cái đã đăng ký trong app, kể cả scheme, host, port và path. Với một lab cục bộ, điều này nghĩa là đăng ký URL cục bộ (Xero cho phép `http://localhost` để phát triển **(verify)**; `lab.localhost` có thể được hoặc không được chấp nhận).

## Gọi API

Base URL: `https://api.xero.com/api.xro/2.0/`

### Các verb khác thường

| Verb | Trong Xero | Bẫy |
|---|---|---|
| `GET` | đọc | — |
| `PUT` | **tạo** | không bao giờ update |
| `POST` | **tạo hoặc update** | với một id đã tồn tại (hoặc, với vài resource, một số hiệu hay tên unique đã tồn tại) thì nó update |

Điều này ngược với thói quen REST thông thường. Hệ quả với bản trùng: `POST /Contacts` với một `Name` đã tồn tại sẽ update contact đó thay vì tạo cái thứ hai; `POST /Invoices` với một `InvoiceNumber` đã tồn tại sẽ nhắm vào invoice đang có **(verify cả hai trên Demo Company)**. Hành vi đó tự nó là một dạng idempotency tự nhiên, và cũng là một cách tự nhiên để lỡ tay ghi đè thứ gì đó.

### Đọc

| Công cụ | Cách | Dùng cho |
|---|---|---|
| Một bản ghi | `GET /Invoices/{InvoiceID}` | chi tiết đầy đủ, có line item (dòng hàng) |
| Phân trang | `?page=1` (mặc định 100 mỗi trang; `pageSize` tới 1000 **(verify)**) | danh sách **có** line item. Không có `page`, một danh sách chỉ trả bản tóm tắt. |
| Thay đổi kể từ | header `If-Modified-Since: <giờ UTC>` | sync tăng dần |
| Lọc | `?where=Status=="AUTHORISED"` | linh hoạt, chậm với organisation lớn |
| Lọc nhanh | `?Statuses=…`, `?ContactIDs=…`, `?InvoiceNumbers=…`, `?IDs=…` | ưu tiên những cái này |
| Sắp xếp | `?order=UpdatedDateUTC` | phân trang ổn định |

### Ghi: một invoice

```json
POST /Invoices          Idempotency-Key: Sales Invoice:ACC-SINV-2026-00042:create_invoice
{
  "Type": "ACCREC",
  "Contact": { "ContactID": "…" },
  "Date": "2026-10-11",
  "DueDate": "2026-11-10",
  "InvoiceNumber": "ACC-SINV-2026-00042",
  "Reference": "PO-7781",
  "CurrencyCode": "AUD",
  "LineAmountTypes": "Exclusive",
  "Status": "AUTHORISED",
  "LineItems": [
    { "Description": "Widget", "Quantity": 2, "UnitAmount": 50.00,
      "AccountCode": "200", "TaxType": "OUTPUT" }
  ]
}
```

| Field | Giá trị | Ý nghĩa |
|---|---|---|
| `Type` | `ACCREC`, `ACCPAY` | sales invoice (hóa đơn bán) / bill (hóa đơn mua) |
| `Status` | `DRAFT`, `SUBMITTED`, `AUTHORISED`, rồi do Xero đặt: `PAID`, `VOIDED`, `DELETED` | xem bảng trạng thái bên dưới |
| `LineAmountTypes` | `Exclusive`, `Inclusive`, `NoTax` | số tiền của dòng là trước hay sau thuế |
| `AccountCode` | một mã từ `GET /Accounts` | tài khoản doanh thu |
| `TaxType` | một mã từ `GET /TaxRates` | **khác nhau theo quốc gia của organisation** |
| `InvoiceNumber` | text tự do, unique với `ACCREC` | **đặt tên (name) của ERPNext vào đây**: đó là cách bạn tìm lại invoice |

Các trạng thái của invoice và bạn được làm gì:

| Từ | Sang | Cách | Bị chặn khi |
|---|---|---|---|
| `DRAFT` / `SUBMITTED` | `AUTHORISED` | POST với status mới | validation thất bại |
| `DRAFT` / `SUBMITTED` | `DELETED` | POST `Status: DELETED` | — |
| `AUTHORISED` | `VOIDED` | POST `Status: VOIDED` | có payment hoặc credit đang được áp vào: gỡ nó trước |
| `AUTHORISED` | `PAID` | tự động, khi các payment phủ đủ tổng tiền | — |
| `PAID` | bất kỳ | không sửa được | gỡ payment trước |

Không có xóa cứng một invoice đã authorised. **Void (hủy hiệu lực) chính là compensation (bù trừ).**

### Ghi: một payment

```json
PUT /Payments
{ "Invoice": { "InvoiceID": "…" }, "Account": { "Code": "090" },
  "Date": "2026-10-12", "Amount": 110.00, "Reference": "ACC-PAY-2026-00017" }
```
Account phải là một tài khoản ngân hàng, hoặc một account có bật "enable payments". Một payment không sửa được: muốn đổi thì xóa nó (`POST /Payments/{id}` với `Status: DELETED`) và tạo cái mới. Một payment của Xero trả một invoice; một Payment Entry của ERPNext trả ba invoice thì thành ba payment của Xero.

### Trả hàng

Một lần trả hàng là một **credit note** (giấy báo có/ghi giảm công nợ): `CreditNotes`, `Type: ACCRECCREDIT`, rồi một **allocation** (phân bổ) vào invoice (`PUT /CreditNotes/{id}/Allocations`). Hai lời gọi, nên là hai operation của outbox (`12`).

### Định dạng

- Ngày đi ra: `"/Date(1760140800000+0000)/"` (một kiểu .NET cũ) cộng với đôi khi một bản song sinh `…String`. Ngày đi vào: `"2026-10-11"` được chấp nhận. Mọi thứ là UTC; `Date` của một invoice không có time zone, nó là một ngày lịch trong sổ sách của organisation.
- Tiền: 2 chữ số thập phân. `UnitAmount` cho phép 4 với `?unitdp=4`.
- Xero tính thuế **theo từng dòng** và làm tròn theo từng dòng. Tổng của bạn và của Xero có thể lệch nhau một cent. So sánh `Total` sau khi tạo và quyết định một tolerance (dung sai); đừng giả định bằng nhau.
- Kích thước request có giới hạn (vài MB **(verify)**); được phép ghi theo batch (một mảng invoice) và khoảng 50 mỗi request là lời khuyên thường gặp.

## Lỗi

| Status | Ý nghĩa | Job làm gì |
|---|---|---|
| `200` | xong | lưu id |
| `400` | lỗi validation: body có `Type: "ValidationException"`, `Message`, và `Elements[].ValidationErrors[].Message` | **vĩnh viễn**: đánh dấu Failed kèm các message; con người sửa dữ liệu |
| `401` | token hết hạn hoặc không hợp lệ | refresh một lần rồi thử lại; nếu refresh thất bại → "cần reconnect" |
| `403` | không có quyền vào tenant này, hoặc thiếu scope, hoặc connection đã bị gỡ | vĩnh viễn cho tới khi con người reconnect |
| `404` | không có bản ghi đó | tùy: với một lần tra cứu thì đó là câu trả lời, không phải lỗi |
| `429` | rate limit; header `Retry-After: <giây>`, `X-Rate-Limit-Problem: minute \| day \| …` | **tạm thời**: chờ đúng chừng đó |
| `500` | lỗi của Xero | tạm thời, có back-off (giãn dần thời gian chờ) |
| `503` | không sẵn sàng (cũng được dùng cho vài kiểu throttling) | tạm thời |
| không có trả lời | timeout hoặc đứt kết nối | **kết quả không rõ**: lần ghi có thể đã xảy ra |

Các message validation điển hình đáng nhận ra: không tìm thấy account code hoặc đã archive; tax type không hợp lệ với account; contact đã archive; ngày nằm trong kỳ đã khóa sổ; invoice number đã dùng; currency chưa bật cho organisation.

Với ghi theo batch, thêm `?summarizeErrors=false`: khi đó Xero trả `200` kèm `StatusAttributeString` theo từng phần tử là `OK` hoặc `ERROR`, nên một invoice hỏng không che mất kết quả của 49 cái kia.

## Rate limit

| Giới hạn | Giá trị **(verify)** | Header cho biết còn lại bao nhiêu |
|---|---|---|
| Theo organisation, mỗi phút | 60 lời gọi | `X-MinLimit-Remaining` |
| Theo organisation, mỗi ngày | 5000 lời gọi | `X-DayLimit-Remaining` |
| Theo organisation, cùng lúc | 5 lời gọi đồng thời | — |
| Theo app, mọi organisation, mỗi phút | 10 000 lời gọi | `X-AppMinLimit-Remaining` |

Hệ quả thiết kế:
- 60 mỗi phút là một mỗi giây. Một lần import đầu tiên 20 000 invoice, từng cái một, là hơn 5 giờ và bốn ngày của giới hạn theo ngày. Hãy **batch** (50 mỗi lời gọi) và **page** (100–1000 mỗi lời gọi).
- Hơn 5 worker trên một organisation không được thêm gì và còn chạm giới hạn concurrency. Một queue, một hoặc hai worker cho Xero.
- Sau một `429`, cả organisation phải chậm lại, không chỉ riêng job đó: giữ một mốc "không gọi trước thời điểm này" (trong cache hoặc trên một dòng settings) mà mọi job đều kiểm tra.
- Retry có sẵn của job trong Frappe ngủ 1–5 giây (`03`). Nó là công cụ sai cho `Retry-After: 47`.

## Idempotency

- Header `Idempotency-Key: <text tối đa 128 ký tự>` trên các lần ghi.
- Cùng key + cùng request trong thời gian lưu giữ → Xero trả lại câu trả lời đầu tiên và không tạo gì mới.
- Cùng key với body khác → một lỗi **(verify)**. Vì vậy key phải gắn với *cái gì* đang được làm, không chỉ với tài liệu: `"<DocType>:<name>:<operation>"` dùng được chừng nào payload của operation đó không bao giờ đổi; nếu một tài liệu có thể được amend (sửa đổi sau submit) và gửi lại, key cần thêm phần version.
- Xero nhớ một key trong bao lâu là có giới hạn **(verify thời gian lưu giữ)**. Một lần retry ba ngày sau có thể không còn được key bảo vệ nữa.

**Không có endpoint "tìm theo idempotency key".** Client giả của lab có `find_by_key` (`lab_core/lab_core/integrations/xero/client.py:30`); Xero thật thì không. Sau một kết quả không rõ, bạn có hai lựa chọn thật:
1. **Gửi lại đúng request đó với cùng key** (trong thời gian lưu giữ). Đơn giản, và key sinh ra để làm việc này.
2. **Tìm theo số hiệu của chính bạn**: `GET /Invoices?InvoiceNumbers=<ERPNext name>`; contact theo `ContactNumber` hoặc tên; payment theo `Reference`. Dùng được bất cứ lúc nào, và là lý do để luôn gửi kèm định danh của chính bạn.

Dùng cả hai: key cho lần retry nhanh, tra cứu cho lần retry muộn.

## Xero gọi ta: webhook

- Được cấu hình theo từng app trong developer portal, với một delivery URL (HTTPS công khai) và một **signing key** (khóa ký).
- Xero POST một JSON nhỏ: một danh sách event, mỗi cái có `resourceId`, `resourceUrl`, `eventCategory` (`INVOICE`, `CONTACT`, …), `eventType` (`CREATE`, `UPDATE`), `tenantId`, `eventDateUtc`, cộng với các số thứ tự.
- Header `x-xero-signature` = base64 của HMAC-SHA256 trên **các byte thô của body** với signing key.
- Bạn phải trả lời **nhanh** (khoảng 5 giây) với `200` nếu chữ ký đúng và `401` nếu sai. Xero kiểm tra điều này khi bạn thiết lập webhook ("intent to receive": nó cố ý gửi cả chữ ký đúng lẫn sai).
- Event chỉ nói bản ghi *nào* đã đổi. Sau đó bạn `GET` nó. Vậy một webhook là một gợi ý, cùng ý tưởng với một realtime event (`04`).
- Giao nhận là at-least-once (ít nhất một lần) và không theo thứ tự: cùng một event có thể tới hai lần, một update có thể tới trước create của nó.

Vì vậy: kiểm tra chữ ký → ghi event vào một bảng → trả 200 → xử lý trong một job. Và giữ một lần pull `If-Modified-Since` định kỳ làm lưới an toàn, vì webhook hay bị mất.

Một lab cục bộ không truy cập được từ internet, nên không nhận được webhook nếu không có tunnel (đường hầm). Với demo, polling pull là đủ.

## Cần verify gì đầu tiên khi online

Theo thứ tự này; mỗi cái có thể làm đổi một quyết định thiết kế.

1. Tên scope cho một app mới tạo.
2. `http://lab.localhost:8000/...` có được chấp nhận làm redirect URI không, hay chỉ `http://localhost`.
3. Idempotency key: thời gian lưu giữ, và câu trả lời cho "cùng key, khác body".
4. `POST /Invoices` với một `InvoiceNumber` đã tồn tại: update, hay lỗi?
5. Các con số rate limit và tên header.
6. Khoảng ân hạn của refresh token.
7. Trần connection và bậc giá cho một app chưa chứng nhận.
8. Các tax type của vùng mà Demo Company thuộc về (`GET /TaxRates`).
