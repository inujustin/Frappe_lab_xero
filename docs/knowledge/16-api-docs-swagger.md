# 16. Tài liệu API kiểu Swagger: có làm được không, được gì, mất gì

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung (OpenAPI, Swagger UI, pydantic, Xero). Hôm nay đã đọc: `frappe/__init__.py:418-445`, phần import của `frappe/utils/typing_validations.py`, bảng route `frappe/api/v2.py:274-303`, các manifest của `frappe`, `erpnext`, `crm`, và `lab_core/frontend/package.json`. Không chạy gì. Chưa có dòng code nào cho việc này; `OVERVIEW.md` đã nêu nó trong track A ("API docs, Swagger/Postman").

Thuật ngữ: **OpenAPI** là định dạng file (JSON/YAML) mô tả một HTTP API. **Swagger UI** là một trang web đọc file đó và cho bấm "Try it out" (gọi thử). Hai thứ tách rời nhau: có thể có file mà không có trang.

## Trả lời trong năm dòng

1. Frappe **không có sẵn** OpenAPI hay Swagger: không có trong `frappe`, `erpnext`, `crm` trên đĩa này ([S]: tìm `openapi|swagger|redoc` chỉ ra một file test không liên quan; không manifest nào khai báo).
2. **Làm được, và phần khó nhất đã có sẵn**: Frappe giữ một registry (sổ đăng ký) các hàm whitelist cùng verb của chúng, và đã dùng **pydantic** để kiểm tra type hint của tham số. Từ đúng hai thứ đó sinh ra được file OpenAPI cho endpoint của ta mà **không cần package mới**.
3. Phần **trang Swagger UI** thì cần một package JavaScript mới. UI của lab đang bị khóa (AGENTS.md B9), nên đó là quyết định của bạn. Không có nó vẫn dùng được file: import vào Postman/Bruno/Insomnia.
4. Lợi ích thật với lab: frontend và test có một hợp đồng đọc được bằng máy thay cho bảng viết tay trong `SPRINT.md`. Giới hạn thật: kiểu **trả về** của ta đang là `dict` trần, nên file sinh ra chỉ mô tả tốt phần **đầu vào** cho tới khi ta khai báo kiểu trả về.
5. Với mục tiêu chính (Xero): phía Xero **đã công bố** OpenAPI cho API của họ [G]. Dùng nó để đối chiếu bảng field mapping của `12` có giá trị hơn nhiều so với việc làm đẹp tài liệu cho bốn endpoint của Lab Note.

## Frappe đã có gì để dựa vào [S]

```text
@frappe.whitelist(methods=["POST"])                    frappe/__init__.py:439
 ├─ thêm hàm vào set  frappe.whitelisted               :423
 ├─ guest được gọi?   frappe.guest_methods             :424
 ├─ verb cho phép     frappe.allowed_http_methods_for_whitelisted_func[fn]   :426
 └─ bọc kiểm tra kiểu tham số bằng pydantic TypeAdapter
        frappe/utils/typing_validations.py:8-10, :25   (pydantic ~=2.12.5: frappe/pyproject.toml:63)

endpoint của ta:  /api/method/<đường dẫn import của hàm>            [T] TRACK-A stage 3
document API:     /api/v2/document/<doctype>...                     frappe/api/v2.py:288-298
schema DocType:   GET /api/v2/doctype/<doctype>/meta                frappe/api/v2.py:216, :300
```

Ba hệ quả:
- **Danh sách endpoint** lấy được bằng code: mọi hàm trong `frappe.whitelisted` có module bắt đầu bằng `lab_core.api.`.
- **Schema đầu vào** lấy được từ chữ ký hàm (`inspect.signature`) và type hint; pydantic sinh được JSON Schema từ một kiểu [G: API `TypeAdapter(...).json_schema()` chưa mở trong source hôm nay]. Vì cùng type hint đó được **kiểm tra lúc chạy**, tài liệu đầu vào không thể nói sai.
- **Schema đầu ra** thì không: bốn endpoint của ta khai báo `-> dict` ([S] `lab_core/lab_core/api/notes.py:9, :15, :21, :27`) và không gì kiểm tra giá trị return. Muốn tài liệu đầu ra có ích, phải khai báo kiểu trả về (ví dụ `TypedDict`, nằm trong standard library) và có test giữ nó đúng.

## Bốn cách, từ rẻ tới đắt

| | Cách | Cần gì | Được | Mất / rủi ro |
|---|---|---|---|---|
| **0** | Không Swagger: bảng endpoint trong `SPRINT.md`, test làm ví dụ sống, tab Network của trình duyệt | Không gì (đang như vậy) | Không tốn công; đủ cho 4 endpoint | Bảng viết tay sẽ lệch khỏi code; không máy nào đọc được; người mới phải đọc code |
| **1** | Viết tay một file `openapi.yaml` trong repo | Chỉ một file | Import được vào Postman; review được trong diff | Lệch khỏi code nhanh như bảng viết tay, lại dài hơn nhiều |
| **2** | **Sinh file từ code**: một endpoint GET của ta (ví dụ `lab_core.api.docs.openapi`) duyệt registry và trả JSON OpenAPI | Một module trong `lab_core/api/`, test của nó; **không package mới** | Luôn khớp với code phần đầu vào; import vào Postman/Bruno; nền cho cách 3 | Phải tự viết bộ sinh (khoảng một file); đầu ra chỉ tốt khi có kiểu trả về; phải giới hạn quyền xem |
| **3** | Cách 2 + trang Swagger UI trong lab | Package JS `swagger-ui-dist` (hoặc tương đương): **thay đổi khóa UI**, block "Needs package" (AGENTS.md A6, B9) | Bấm thử ngay trong trình duyệt, cùng session | Thêm dependency và bề mặt tấn công; phải xử lý CSRF cho POST; chỉ nên bật ở dev |
| **4** | Cài một app cộng đồng sinh Swagger cho Frappe [G] | App ngoài, chưa kiểm chứng với v16 | Nhanh nếu nó chạy | Code không phải của ta; AGENTS.md B1 nói code ta viết chỉ nằm trong `lab_core`; phải tự thẩm định như một dependency (`docs/runbooks/add-dependency.md`) |

Khuyến nghị: **cách 2**, xem bằng Postman/Bruno trước. Quyết cách 3 sau, khi đã thấy file có ích.

## Có và không có: so sánh thẳng

| Khía cạnh | Không có OpenAPI | Có OpenAPI sinh từ code |
|---|---|---|
| Frontend biết gọi gì | Đọc `SPRINT.md` hoặc đọc Python | Đọc một file; có thể sinh type/clients (cần công cụ mới ở frontend: lại là khóa UI) |
| Test API bằng tay | Tab Network, tự gõ URL | Import collection, có sẵn tham số và verb |
| Tài liệu lệch code | Chắc chắn xảy ra | Đầu vào: không thể. Đầu ra: có thể, trừ khi có kiểu trả về + test |
| Người/hệ thống ngoài tích hợp vào ta | Phải viết tài liệu riêng | Đưa file là xong |
| Công bỏ ra | 0 | Một module + test; rồi bảo trì khi Frappe đổi cách whitelist |
| Rủi ro bảo mật | Không thêm | File lộ danh sách endpoint và tham số: phải giới hạn role, không `allow_guest` |
| Kiểu API của Frappe | Không vấn đề | RPC là chính: mỗi hàm thành một path dài `/api/method/lab_core.api.notes.create_note`; mô tả được nhưng không "đẹp" như REST |
| Lỗi | Hai dạng v1/v2 (`14`) | Phải mô tả dạng lỗi **một lần** làm thành phần dùng chung: cần chốt ADR về dạng lỗi trước |

## Những chỗ Frappe làm việc này khác .NET [I]

- .NET (Swashbuckle/NSwag) đọc controller và attribute; ở đây ta đọc **một set các hàm**. Không có khái niệm route template: path chính là đường dẫn import của hàm.
- Vỏ response: v1 bọc kết quả trong `message`, v2 trong `data` ([T]). Bộ sinh phải bọc schema đầu ra đúng theo đường mà SPA gọi.
- **"Try it out" với session**: trang nằm cùng origin nên cookie `sid` đi kèm, nhưng mọi POST cần header CSRF ([T] kiểm tra ở `frappe/auth.py:81`; phía Desk gắn header ở `frappe/public/js/frappe/request.js:261`). Swagger UI phải được cấu hình để gắn token đó; token lấy từ đâu cho SPA là câu hỏi còn mở của track B.
- **Gọi bằng API key** (`Authorization: token key:secret`, `01`) hợp với Postman hơn. CSRF có bị kiểm tra với kiểu auth này không thì `01` ghi là chưa biết.
- **Document API** (`/api/v2/document/<DocType>`) mô tả được bằng cách sinh schema từ meta của DocType. Đó là một việc lớn hơn, tổng quát cho mọi DocType; chỉ làm khi có client ngoài cần.
- Endpoint sinh tài liệu là code của ta nên viết thẳng trong `lab_core/api/`; không hook, không override gì của Frappe.

## Liên hệ với mục tiêu chính: Xero

1. **Dùng OpenAPI của Xero** [G]: Xero công bố spec cho Accounting API. Nó là nguồn tra tên field, kiểu, enum (`Status`, `LineAmountTypes`, `TaxType`) khi viết `integrations/xero/client.py` và bảng mapping của `12`, thay cho trí nhớ. Cần online để lấy; đưa nó vào repo là thêm một file tham chiếu, không phải dependency.
2. **Endpoint của ta mà luồng Xero cần tài liệu**: `retry_sync`, sau này là "Connect to Xero", trạng thái kết nối, và webhook receiver (`12`). Webhook là endpoint duy nhất có **bên ngoài** gọi vào: mô tả nó (header chữ ký, body, mã trả về) có giá trị thật.
3. **Không phải việc gấp**: SPA đang xây dựa trên bảng trong `SPRINT.md` và nó đủ. Làm cách 2 sau khi dạng response/lỗi được chốt (`14`), không thì phải sinh lại.

## Thứ tự làm, nếu bạn chọn cách 2

```text
1. chốt dạng response + lỗi (ADR, xem 14)          ← quyết định của bạn
        │
        ▼
2. khai báo kiểu trả về cho 4 endpoint notes        lab_core/api/notes.py (và service)
        │
        ▼
3. bộ sinh OpenAPI + endpoint xem (giới hạn role)   lab_core/api/docs.py (mới)     ┐ song song được:
4. test: spec liệt kê đủ endpoint, đúng verb        lab_core/api/test_docs.py      ┘ khác file, chung tên endpoint
        │
        ▼
5. (tùy chọn) Swagger UI                            cần "Needs package" + đổi bảng khóa UI trong AGENTS.md B9
```

Bước 2 và việc frontend của sprint (F1, F2) đụng các file khác nhau; bước 2 đổi kiểu khai báo chứ không đổi dữ liệu trả về, nên không phá bảng endpoint.

## Các quyết định là của bạn

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| 1 | Có làm không | Có, cách 2, sau sprint |
| 2 | Ai được xem file spec | System Manager (hoặc một role dev); không Guest |
| 3 | Có Swagger UI trong lab không | Chưa; dùng Postman/Bruno trước. Nếu có: chỉ ở dev |
| 4 | Mô tả cả document API không | Chưa; chỉ `lab_core.api.*` |
| 5 | Sinh type cho frontend từ spec | Chưa; frontend đang là JavaScript (`frontend/src/api/hello.js`) và công cụ sinh là dependency mới |

## Còn chưa biết

- API chính xác của pydantic để lấy JSON Schema từ một type hint, và nó xử lý tham số không có hint thế nào.
- Frappe có biến thể nào khác của việc whitelist (method trên controller, `run_doc_method`) cần gom vào spec hay không; mới xem đường hàm thường.
- App cộng đồng nào sinh Swagger cho Frappe, và có chạy trên v16 không.
- Giấy phép và vị trí chính xác của bộ OpenAPI do Xero công bố.
- Tên header CSRF và cách SPA lấy token (track B).
