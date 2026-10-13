# 05. Việc cần làm: bảng điều khiển

Một trang để mở mỗi khi ngồi vào bàn. **Kế hoạch đầy đủ là `plan/done/xero/PLAN.md`**; trang này chỉ nhắc: đang ở đâu, việc kế tiếp của bạn là gì.

> **0 đồng.** Chỉ Demo Company + Web app bậc Starter. Không nhập thẻ, không nâng bậc, không Custom connection, không tunnel trả phí. Bước nào đòi tiền thì dừng (`01`, "Luật 0 đồng").
>
> **Chỉ Xero thật.** Không có Xero giả, không có chế độ "không Xero". Mọi lần chạy thử là một lời gọi vào Demo Company.

## Đề bài (email: `main-request.png`)

1. Tạo Sales Order → phát hành Invoice trên Xero → đồng bộ trạng thái invoice về.
2. Phát hành Credit Note trên Xero → đồng bộ ảnh hưởng về Sales Order liên quan.
3. Và chữ "research": một bản nghiên cứu gửi lại.

Hai luồng hoạt động thế nào: `09`.

## Hai giai đoạn, không trộn

```text
GIAI ĐOẠN 1: việc được giao. Làm xong hẳn trước.
  P0 (bạn)   tài khoản Xero + app + Connect; Desk: 3 DocType; ERPNext có Company/Customer/Item   ← ĐANG Ở ĐÂY
  P1         Sales Order → Invoice trên Xero                       ★ DEMO 1
  P2         trạng thái invoice về + Credit Note về (polling)      ★ DEMO 2, 3
  P5         bản nghiên cứu + kịch bản demo

GIAI ĐOẠN 2: ý thêm, mỗi cái ở mức tối thiểu. Chỉ bắt đầu khi giai đoạn 1 đã xong.
  PE         lỗi và response thống nhất (kiểu middleware)          ★ DEMO E      (11)
  P4         @xero_atomic: có SAGA và không SAGA                   ★ DEMO 5      (10)
  P3         mất kết nối → báo rõ → nối lại → Retry                ★ DEMO 4
```

Không viết test tự động cho demo này; mỗi phase được kiểm bằng tay theo danh sách "xong khi" trong kế hoạch. Thứ duy nhất của "phần thêm" nằm ngay trong giai đoạn 1 là hai việc rẻ về idempotency: tra bên Xero trước khi tạo, và ghi đè khi kéo về.

## Việc của bạn ngay bây giờ (P0)

Làm theo thứ tự này, vì cái đầu là rủi ro lớn nhất và không gì chạy được khi chưa có nó:

Cấu hình nằm trong code; việc của bạn chỉ là những thứ code không làm được. Danh sách đầy đủ và trạng thái: `plan/done/xero/board/lane-h.md`.

1. Login Xero → mở Demo Company → ghi lại **quốc gia** và **tiền tệ** (`01`).
2. Desk: tạo ba DocType `Lab Xero Outbox`, `Lab Xero Settings`, `Lab Xero Credit Note` (field: `plan/done/xero/PLAN.md`, "Dữ kiện chung"; chỉ các field của giai đoạn 1). **Việc duy nhất phải làm trong Desk.**
3. `developer.xero.com` → New app → **Web app**, với Redirect URI cố định mà agent ghi ra (bước B0 của bảng việc).
4. Chạy các lệnh agent đưa để đặt `client_id`, `client_secret`, mã tài khoản doanh thu và mã thuế vào site config; rồi migrate. Code tự tạo Connected App `xero` và điền Settings.
5. Mở Connected App `xero`, bấm Connect, chọn Demo Company.
   Hai câu trả lời bạn sẽ có ngay: Xero có nhận redirect URI của lab không; Frappe có đổi được token không. Nếu một trong hai là "không", báo lại trước khi P1 đi xa.
6. ERPNext: một Company cùng tiền tệ với Demo Company, một Customer, một Item; tạo thử một Sales Order **không thuế, không chiết khấu**.

Lần Connect ở bước 5 là lần duy nhất có người đăng nhập Xero. Demo chỉ có kịch bản "không đăng nhập": người dùng Frappe làm việc mà không cần tài khoản Xero (`02`).

Trong lúc đó Codex có thể bắt đầu viết P1, nhưng **chỉ chạy thử được khi P0 xong**.

## Luật nghiệp vụ: đã quyết, không chờ xác nhận

Demo dùng mười luật trong `plan/done/xero/PLAN.md`, "Luật nghiệp vụ của demo". Bốn lựa chọn đáng nhắc khi trình bày, vì dự án thật có thể chọn khác:

| Lựa chọn của demo | Lựa chọn còn lại |
|---|---|
| "Effect" của Credit Note = hiển thị trên đơn | tự sửa đơn, hoặc sinh chứng từ trong ERPNext |
| Xero tính thuế theo một mã thuế mặc định | ERPNext quyết định thuế từng dòng |
| Hóa đơn sang Xero ở trạng thái đã duyệt | sang ở dạng nháp, kế toán duyệt |
| Số hóa đơn = tên Sales Order | dãy số của Xero |

## Thử đầu tiên với Demo Company (mỗi cái xóa một dấu "chưa biết")

1. `GET /connections` → có `tenantId` của Demo Company.
2. `GET /TaxRates`, `GET /Accounts` → mã thuế và mã tài khoản thật của vùng đã chọn.
3. Tạo một invoice hai lần cùng `InvoiceNumber`: cập nhật hay báo lỗi?
4. Tạo tay một Credit Note trong Xero, áp vào một invoice, rồi `GET /CreditNotes`: allocation trông thế nào; invoice có được tính là "đã đổi" không.
5. Header `X-DayLimit-Remaining` → đúng là 1000 ở Starter?

Các lời gọi này đi qua code trong `tasks/` khi P1 có client, hoặc do bạn thực hiện; agent không chạy script hay lệnh mạng (AGENTS.md A3). Mỗi lời gọi tính vào 1000 lời gọi/ngày.

## Cố ý chưa làm

SPA; Xero giả; test tự động; webhook; ghi Payment sang Xero (trừ một bước trong P4); kịch bản đăng nhập bằng tài khoản Xero; trả hàng từ phía ERPNext; nhiều organisation; Kafka và container log; deploy.

## Tự kiểm tra cả gói (trả lời không nhìn)

1. Xero chạy ở đâu, ai mở kết nối tới ai, và vì sao không cần deploy?
2. Kể đường đi của một Sales Order từ lúc bấm Submit tới lúc có `InvoiceID`, nêu tên từng phần.
3. Kế toán tạo Credit Note bên Xero: con số tới Sales Order bằng cách nào?
4. Cái gì ngăn một đơn sinh ra hai hóa đơn khi job chạy hai lần?
5. Vì sao người dùng Frappe không cần tài khoản Xero?
