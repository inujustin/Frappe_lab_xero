# 03. Accounting API: gọi thế nào, hỏng thế nào, giới hạn gì

Nhãn độ tin cậy: xem `00-README.md`. Hình dạng request và tên field là [G] trừ khi ghi khác; chúng ổn định nhiều năm, nhưng lời gọi thử đầu tiên vào Demo Company mới là bằng chứng.

## Trả lời trong năm dòng

1. REST + JSON tại `https://api.xero.com/api.xro/2.0/<Resource>`; mỗi lời gọi kèm `Authorization: Bearer` và `xero-tenant-id`.
2. Verb ngược thói quen: **`PUT` = tạo**, **`POST` = tạo hoặc cập nhật**.
3. Ba đối tượng cho demo: `Contacts` (khách), `Invoices` (hóa đơn), `Payments` (thanh toán). Invoice cần Contact trước; Payment cần Invoice trước.
4. Xero giới hạn 60 lời gọi/phút và 1000/ngày (bậc Starter) cho mỗi organisation; vượt thì `429` + `Retry-After`. [X]
5. Header `Idempotency-Key` chống tạo trùng, nhưng Xero chỉ nhớ key **6 phút** [X*]. Lưới an toàn thật là tra cứu theo số hiệu của chính ta.

## Một lời gọi trông thế nào

```text
POST https://api.xero.com/api.xro/2.0/Invoices
  Authorization:   Bearer <access_token>          ← từ Token Cache (02)
  xero-tenant-id:  <tenantId>                     ← từ Lab Xero Settings (02)
  Accept:          application/json
  Content-Type:    application/json
  Idempotency-Key: <tối đa 128 ký tự>             ← chỉ có nghĩa với POST/PUT/PATCH
```

| Verb | Nghĩa trong Xero | Bẫy |
|---|---|---|
| `GET` | đọc | danh sách không có `?page=` chỉ trả bản tóm tắt, thiếu line item |
| `PUT` | **tạo mới** | không bao giờ cập nhật |
| `POST` | **tạo hoặc cập nhật** | có id (hoặc một số hiệu/tên unique đã tồn tại) thì thành cập nhật → có thể lỡ tay ghi đè |

## Ba đối tượng của demo

**Contact** (từ `Customer`):
```json
POST /Contacts
{ "Name": "Công ty ABC", "ContactNumber": "CUST-00012", "EmailAddress": "ap@abc.example", "TaxNumber": "…" }
```
`Name` phải unique trong organisation. `ContactNumber` là chỗ đặt mã của ERPNext để tìm lại. Trả về `ContactID` → lưu lên Customer.

**Invoice** (từ `Sales Invoice`):
```json
POST /Invoices
{ "Type": "ACCREC",
  "Contact": { "ContactID": "…" },
  "InvoiceNumber": "ACC-SINV-2026-00042",
  "Date": "2026-10-12", "DueDate": "2026-11-11",
  "CurrencyCode": "AUD", "LineAmountTypes": "Exclusive",
  "Status": "AUTHORISED",
  "LineItems": [ { "Description": "Widget", "Quantity": 2, "UnitAmount": 50.00,
                   "AccountCode": "200", "TaxType": "OUTPUT" } ] }
```

| Field | Ý nghĩa | Lưu ý |
|---|---|---|
| `Type` | `ACCREC` hóa đơn bán, `ACCPAY` hóa đơn mua | |
| `InvoiceNumber` | số hóa đơn, unique với `ACCREC` | **đặt `name` của ERPNext vào đây**: tay nắm để tìm lại |
| `Status` | `DRAFT` → `SUBMITTED` → `AUTHORISED` (đã duyệt) → `PAID` (Xero tự đặt) / `VOIDED` | gửi `AUTHORISED` khi ERPNext đã submit |
| `LineAmountTypes` | `Exclusive` / `Inclusive` / `NoTax` | giá dòng trước hay sau thuế |
| `AccountCode` | mã trong chart of accounts của organisation (`GET /Accounts`) | cần bảng mapping từ account của ERPNext |
| `TaxType` | mã thuế (`GET /TaxRates`) | **theo quốc gia của organisation**; cần bảng mapping |

**Payment** (từ `Payment Entry`):
```json
PUT /Payments
{ "Invoice": { "InvoiceID": "…" }, "Account": { "Code": "090" },
  "Date": "2026-10-13", "Amount": 110.00, "Reference": "ACC-PAY-2026-00017" }
```
Một payment Xero trả **một** invoice. Một Payment Entry của ERPNext trả ba invoice → ba payment Xero. Payment không sửa được: xóa rồi tạo lại.

## Vòng đời invoice, và "undo" là gì

```text
DRAFT ──► SUBMITTED ──► AUTHORISED ──(payment đủ)──► PAID
  │           │              │
  └── DELETED ┘              └──► VOIDED     (bị chặn nếu đang có payment/credit: gỡ chúng trước)
```
Không xóa cứng được một invoice đã `AUTHORISED`. **Void chính là compensation (thao tác bù trừ)** khi ERPNext cancel. Trả hàng không phải void mà là một **credit note** (`/CreditNotes`, `Type: ACCRECCREDIT`) rồi allocate (phân bổ) vào invoice: hai lời gọi.

## Lỗi: bốn loại, job xử lý khác nhau

| HTTP | Nghĩa | Loại | Job làm |
|---|---|---|---|
| `200` | xong | | lưu id |
| `400` | validation: body có `Elements[].ValidationErrors[].Message` | **Rejected** (từ chối) | dừng, ghi message; con người sửa dữ liệu rồi retry |
| `401` | token hết hạn/sai, hoặc thiếu scope [3] | **Auth lost** nếu refresh rồi vẫn 401 | tạm dừng mọi sync, báo reconnect |
| `403` | không còn quyền vào tenant (connection bị gỡ) | Auth lost | như trên |
| `429` | vượt rate limit; có `Retry-After: <giây>` [X] | **Busy** (bận) | chờ đúng chừng đó, cả organisation cùng chậm lại |
| `500` / `503` | Xero lỗi / quá tải | Busy | thử lại, giãn dần |
| không trả lời | timeout, đứt mạng | **Unknown** (không rõ) | **có thể Xero đã tạo rồi** → tra cứu trước khi gửi lại |

Message validation hay gặp: account code không tồn tại/đã archive; tax type không hợp với account; contact đã archive; ngày rơi vào kỳ đã khóa sổ; invoice number đã dùng; currency chưa bật.

"Unknown" là loại nguy hiểm nhất và là lý do cả thiết kế outbox tồn tại (`04`).

## Rate limit [X]

| Giới hạn | Giá trị | Header báo số còn lại |
|---|---|---|
| Mỗi organisation, đồng thời | 5 lời gọi đang chạy | |
| Mỗi organisation, mỗi phút | 60 | `X-MinLimit-Remaining` |
| Mỗi organisation, mỗi ngày | **1000 (Starter)**, 5000 (các bậc trả phí) | `X-DayLimit-Remaining` |
| Cả app, mọi organisation, mỗi phút | 10 000 | `X-AppMinLimit-Remaining` |

Xero không nâng giới hạn theo yêu cầu [X]. Hệ quả:
- 1000/ngày là dư cho demo, nhưng **một vòng polling sai là hết**: 1 lời gọi/phút đã là 1440/ngày. Đừng poll Xero theo phút.
- Một queue, một hoặc hai worker cho Xero. Hơn 5 worker cùng lúc chỉ chạm giới hạn đồng thời.
- Ghi theo lô: một request chứa nhiều invoice. Trần 3.5 MB, thực tế khoảng 50 bản ghi mỗi request [X]. Thêm `?summarizeErrors=false` để mỗi phần tử có kết quả riêng [G].
- Đọc tiết kiệm: `?page=` (100 bản ghi/trang [X]) và header `If-Modified-Since` để chỉ lấy thứ đã đổi [X].
- Retry có sẵn của job Frappe chỉ ngủ vài giây ngay trong worker (`06`, mục 3), sai công cụ cho `Retry-After: 47`. Dòng outbox phải quay về trạng thái chờ.

## Idempotency: Xero giúp được tới đâu

[X*] trang "Idempotent requests" của Xero:
- Header `Idempotency-Key`, chỉ xử lý với `POST`, `PUT`, `PATCH`. Dài quá 128 ký tự → `400`.
- Cùng key, cùng request → Xero trả lại câu trả lời đã cache, không tạo gì mới.
- Cùng key, request khác → `400` (key xung đột với request).
- **Key hết hạn sau 6 phút kể từ lời gọi đầu.**

Sáu phút đổi cách nghĩ: key chỉ che được **lần retry ngay lập tức** (timeout rồi gửi lại trong vài phút). Một job chạy lại sau một giờ, hay một người bấm "retry" hôm sau, **không còn được key bảo vệ**. Và Xero **không có** endpoint "tìm theo idempotency key" (client thế chỗ còn sót trong code có một hàm `find_by_key`, [S] `integrations/xero/client.py:30`; Xero thật không có thứ tương đương, và client đó bị gỡ ở P1).

```text
trước MỌI lần tạo, kể cả lần đầu:
   GET /Invoices?InvoiceNumbers=<name của ERPNext>      ← "check before create" (AGENTS.md B4)
      có  → lấy InvoiceID, đánh dấu Done, KHÔNG tạo
      không → POST /Invoices + Idempotency-Key          ← key che khoảng 6 phút sau đó
```
Tương tự: contact tìm theo `ContactNumber`, payment theo `Reference`. Đây là lý do luôn gửi kèm định danh của chính ta. Cái giá: mỗi lần tạo tốn 2 lời gọi (nhớ tới 1000/ngày).

Chưa kiểm chứng [G]: `POST /Invoices` với `InvoiceNumber` đã tồn tại sẽ cập nhật invoice cũ hay báo lỗi. Thử trên Demo Company trước khi dựa vào.

## Xero gọi ta: webhook (biết để biết, demo không làm)

- Cấu hình trong developer portal: URL nhận (HTTPS công khai) + một **signing key** (khóa ký) cho mỗi app [3].
- Xero POST danh sách event mỏng: `resourceId`, `resourceUrl`, `eventCategory` (`CONTACT`, `INVOICE`, `CREDITNOTE`…), `eventType` (`CREATE`, `UPDATE`), `tenantId`, `eventDateUtc` [3]. Event chỉ nói **cái gì** đổi; muốn dữ liệu phải `GET`.
- Header `x-xero-signature` = base64(HMAC-SHA256(**byte thô của body**, signing key)). Đúng → trả `200`; sai → trả `401`. Xero cố ý gửi chữ ký sai lúc thiết lập ("intent to receive") để kiểm tra ta có từ chối không [3].
- Phải trả lời nhanh (vài giây [3]); có thể tới trùng, không đảm bảo thứ tự [3].

Lab chạy local không có URL công khai → không nhận được webhook nếu không có tunnel. Chiều Xero → ERPNext (ví dụ "invoice đã được trả") trong demo, nếu cần, làm bằng một lần đọc `If-Modified-Since` thưa (vài lần mỗi giờ), không phải webhook.

## Định dạng dễ vấp [G]

- Ngày Xero trả về: `"/Date(1760140800000+0000)/"`; ngày gửi lên: `"2026-10-12"`. `Date` của invoice là ngày lịch, không có múi giờ.
- Tiền: 2 chữ số thập phân (`UnitAmount` 4 chữ số với `?unitdp=4`). Xero làm tròn thuế **theo từng dòng** → tổng của Xero và của ERPNext có thể lệch 0.01. So sánh `Total` sau khi tạo với một dung sai có tên; không giả định bằng nhau. Trong code: `flt(value, precision)`, không `float()`, không `==` (AGENTS.md B4).

## Tự kiểm tra

1. Timeout khi `POST /Invoices`. Hai phút sau job chạy lại; một ngày sau có người bấm retry. Mỗi trường hợp cái gì ngăn việc tạo invoice thứ hai?
2. `400` và `429` khác nhau thế nào về việc job phải làm với dòng outbox?
3. Vì sao một vòng poll Xero mỗi phút là ý tồi ở bậc Starter?
