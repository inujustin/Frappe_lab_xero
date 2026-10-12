# Hướng dẫn Track A: một request đi thế nào, và vì sao Frappe là "RPC trước tiên"

Dành cho agent dẫn con người đi qua track A. Mục tiêu không phải là một tài liệu: mục tiêu là con người giải thích được, từ trí nhớ và với code đang mở, một lần gọi tới được một hàm ra sao, vì sao phần lớn lần gọi trong Frappe là RPC (Remote Procedure Call: gọi hàm từ xa) chứ không phải REST (URL chỉ tài nguyên, verb HTTP chỉ hành động), và nên dùng kiểu nào cho việc gì. Trace note (ghi chú lần theo code) là sản phẩm phụ.

## Status (Trạng thái)
Track đang đứng ở đâu. Bằng chứng cho mọi thứ đánh dấu xong nằm trong `docs/traces/rpc-and-document-api.md`.

| Stage (chặng) | Trạng thái | Đã xong gì | Còn lại gì |
|---|---|---|---|
| Hai từ (REST, RPC) | DONE (xong) | Đã thống nhất bảng; có mục so sánh trong note | — |
| 1. Một request từ đầu tới cuối | DONE | Điểm vào, init, session và CSRF, dispatch (phân nhánh xử lý), exception, commit hoặc rollback, hook after-request | — |
| 2. Router của `/api` | DONE, còn một câu hỏi mở | Bảng route của v1 và v2; `website_route_rules` và `override_whitelisted_methods` không thêm được đường dẫn `/api` | Có cách nào được hỗ trợ để thêm đường dẫn tùy biến như `/api/lab/notes/<id>` hay không |
| 3. Đường RPC | DONE | hello qua v1 và v2, registry whitelist (danh sách hàm được phép gọi từ ngoài), kiểm tra Guest và verb, truyền tham số, `message` so với `data` | Con người chưa chạy thí nghiệm 2 và 4 của note |
| 4. Đường resource | DONE trừ delete | List (fields, filters, phân trang, query có xét quyền, hook `get_list`), read, create, update | Delete: nó kiểm tra quyền ở đâu |
| 5. Một method trên một tài liệu | OPEN (mở) | — | Toàn bộ; làm khi viết action đầu tiên trên tài liệu |
| 6. Câu trả lời và lỗi | HALF (một nửa) | Dạng thành công và nơi nó được dựng, v1 so với v2 | Lỗi: chuyển sang track A2 |
| 7. Transaction | HALF | Đã thấy trong source: chỉ commit với method làm đổi trạng thái hoặc khi có cờ tường minh, còn lại và khi có bất kỳ exception nào thì rollback | Thí nghiệm (GET mà có save, rồi POST), và phần so sánh với `@Transactional` của Spring |
| 8. Phía trình duyệt | HALF | `frappe.call` dựng một method URL và mặc định dùng POST; CSRF được kiểm tra ở `frappe/auth.py:81` cho các method không an toàn | SPA phải gửi gì cho lần POST đầu tiên: chuyển sang track B |
| 9. Quyết định, rồi xây | OPEN | — | Bảng quyết định, rồi demo resource kiểu Spring Boot kèm test |

Tiếp theo, theo thứ tự này: thí nghiệm của stage 7; câu hỏi mở của stage 2; stage 9. Stage 5, 6 (lỗi) và 8 (POST đầu tiên) không chặn việc đóng track này.

Chỉ cập nhật khi con người yêu cầu, hoặc nói một stage đã xong: chỉ sửa đúng dòng đó.

## Cách chạy các phiên này

Bạn là người dẫn đường, không phải giảng viên. Tuân theo `AGENTS.md`; file này bổ sung phương pháp dạy.

- **Mỗi request một stage.** Làm stage con người nêu tên, hoặc stage chưa xong kế tiếp. Dừng ở cuối stage.
- **Hình dạng của mọi câu trả lời cho một stage**, theo thứ tự này và giữ ngắn:
  1. *Trong một câu:* câu trả lời cho câu hỏi của stage.
  2. *Đường đi:* hình vẽ bằng text của chuỗi lời gọi, mỗi bước nhảy có `path:line` mà bạn đã mở trong phiên này.
  3. *Nhìn vào đây:* ba hoặc bốn dòng source quan trọng nhất, trích nguyên văn, để con người mở file ra và thấy.
  4. *Thử đi:* một thí nghiệm cho con người, kèm cần quan sát gì và kết quả mong đợi.
  5. *Tự kiểm tra:* hai hoặc ba câu hỏi mà giờ con người phải trả lời được. Không đưa đáp án cho tới khi được hỏi.
  6. *Còn chưa biết:* những gì bạn không xác nhận được.
- **Chờ.** Không sang stage kế tiếp cho tới khi con người nói stage đã rõ. Nếu họ trả lời sai một câu kiểm tra, hãy giải thích đúng điểm đó theo cách khác, kèm code, rồi mới đi tiếp.
- **Bằng chứng.** Các số dòng bên dưới được đọc ngày 2026-10-09 và sẽ trôi: hãy mở file và xác nhận trước khi dẫn. Gắn nhãn cho phát biểu là Seen (đã thấy), Inferred (suy ra) hoặc Unknown (chưa biết) (skill `code-tracer`). Không bao giờ giải thích từ trí nhớ về các phiên bản Frappe cũ.
- **Note.** Note của track là `docs/traces/rpc-and-document-api.md`. Sau mỗi stage con người chấp nhận, thêm phần mới vào file đó theo định dạng `code-tracer`; không mở note thứ hai cho track này.
- **Không xây gì trong một stage trace.** Khi một stage cần một endpoint tí hon để thí nghiệm, hãy nói ra và chờ: đó là một request riêng, có test riêng.
- **Thí nghiệm là việc của con người.** Ưu tiên trình duyệt: thanh địa chỉ cho GET, và tab Network của developer tools để đọc request, header và response. Giải thích mọi lệnh (A9). Không bao giờ hỏi, đọc hoặc in ra mật khẩu, cookie `sid` hay site config.

## Hai từ, trước khi đụng tới code

Thống nhất những điều này với con người trước; mọi thứ khác đều treo trên chúng.

| | REST | RPC |
|---|---|---|
| URL gọi tên | một vật: `/document/Lab Note/LN-0001` | một hành động: `/method/lab_core.api.hello.hello` |
| Verb có nghĩa | làm gì với vật đó: GET đọc, POST tạo, PUT/PATCH sửa, DELETE xóa | rất ít: nó chỉ nói "an toàn" hay "có thay đổi gì đó" |
| Bạn thêm tính năng bằng cách | thêm một resource | viết một hàm |
| Spring Boot | `@GetMapping("/notes/{id}")` | gần với việc gọi một service method qua HTTP hơn |

Frappe có cả hai. Câu hỏi của track là một lần gọi cụ thể thuộc loại nào, và vì sao.

## Các stage

### 1. Một request, từ socket tới response
**Câu hỏi:** mọi HTTP request đi qua những bước nào, theo thứ tự?

Bắt đầu: `frappe/app.py:135` `application(request)`.

```text
application()                         app.py:135
 ├─ init_request()                    app.py:214   site, kết nối database, form data, session
 ├─ validate_auth()                   app.py:141 → auth.py:629   ai đang gọi
 ├─ dispatch, khớp đầu tiên thắng:
 │    form field "cmd"   → frappe.handler.handle()        app.py:154   kiểu cũ, deprecated (đã lỗi thời)
 │    path /api/...      → frappe.api.handle(request)     app.py:158
 │    /backups, /private/files, /.well-known ...
 │    còn lại            → get_response()                 app.py:176   một trang web (Desk, /lab, www)
 ├─ có lỗi?  → handle_exception(e), rồi rollback database  app.py:182
 ├─ không lỗi → sync_database()                            app.py:186 → :458
 ├─ hook after_request                                     app.py:195
 └─ process_response()                                     app.py:286
```
Thử đi: mở log, nạp `/app`, `/lab` và `/api/method/ping` trong trình duyệt và ghép mỗi cái với nhánh của nó.
Con người phải nói được: nhánh nào phục vụ trang SPA, nhánh nào phục vụ dữ liệu của nó, và việc đăng nhập được quyết định ở đâu.

### 2. Router của `/api`: một bảng cố định
**Câu hỏi:** `/api/...` trở thành một hàm Python như thế nào, và một app có thêm được đường dẫn của riêng nó không?

Bắt đầu: `frappe/api/__init__.py:23` `handle`, `:91` `API_URL_MAP`; bảng route ở `frappe/api/v1.py:144` và `frappe/api/v2.py:274`.

```text
/api/...  và /api/v1/...  → luật v1        /api/v2/...  → luật v2
   /method/<path>                              /method/<method>, /method/<doctype>/<method>
   /resource/<doctype>[/<name>]                /document/<doctype>[/<name>][/method/<m>]
                                               /doctype/<doctype>/meta, /count
```
Xác lập bằng bằng chứng: bảng được dựng từ các list nằm bên trong Frappe; tìm xem có hook nào cho phép một app thêm luật không, và nói bạn đã tìm những gì. Điều này trả lời "vì sao tôi không viết được `/api/lab/notes/42` như trong Spring".
Thử đi: `/api/method/ping`, `/api/v2/method/ping`, và một đường dẫn bịa ra như `/api/v2/nothing`; so sánh ba response.

### 3. Đường RPC: một URL gọi tên một hàm
**Câu hỏi:** chính xác điều gì xảy ra giữa `/api/method/lab_core.api.hello.hello` và lệnh `return` trong `hello()`?

```text
v1: /api/method/<path>   → v1.py:35 handle_rpc_call → handler.py:47 handle → :66 execute_cmd
v2: /api/v2/method/<m>   → v2.py:28 handle_rpc_call
        │
        ├─ tìm hàm theo tên có dấu chấm                frappe.get_attr
        ├─ is_whitelisted(fn)                          __init__.py:479   registry ở :423-426, được điền bởi @frappe.whitelist :439
        ├─ is_valid_http_method(fn)                    handler.py:100    methods=[...] của decorator
        └─ frappe.call(fn, **frappe.form_dict)         __init__.py:1143  query string và body trở thành keyword argument
```
Những điểm cần làm rõ:
- Vì sao đây là RPC: URL chính là import path của hàm. Không có gì ánh xạ một đường dẫn sang một resource.
- `@frappe.whitelist` thật sự làm gì: nó thêm hàm vào một set. Tìm chỗ Guest bị từ chối và chỗ HTTP verb bị từ chối; đó là hai lỗi con người đã từng thấy.
- Kiểu của tham số được kiểm tra ở đâu: `frappe/utils/typing_validations.py:25`, được decorator `whitelist` bọc quanh hàm (`frappe/__init__.py:439`).
- `override_whitelisted_method` trên đường v2: một hook có thể tráo hàm.
Thử đi: gọi `hello` khi đã đăng nhập, khi đã đăng xuất, và bằng POST (dùng "edit and resend" của tab Network, hoặc một form); ghép mỗi kết quả với dòng code đã sinh ra nó.

### 4. Đường resource: một URL gọi tên một tài liệu
**Câu hỏi:** điều gì xảy ra với `GET /api/v2/document/Lab Note`, và nó khác stage 3 thế nào?

Bắt đầu: `frappe/api/v2.py:78` `document_list`, `:64` `read_doc`, `:171` `create_doc`, `:194` `update_doc`, `:210` `delete_doc`. Các bản song sinh của v1 nằm ở `frappe/api/v1.py:12-74`.

Trace đầy đủ list và read; với create, update và delete thì chỉ cần chỉ ra mỗi cái kiểm tra quyền ở đâu và save ở đâu. Làm rõ:
- Không hàm nào của ta chạy: chính DocType là API. Kiểm tra quyền nào canh giữ mỗi verb, và query nào dựng danh sách (fields, filters, phân trang: tìm tên các tham số).
- Cùng dữ liệu đó qua `/api/resource/Lab Note` (v1): khác gì ở URL, tham số và response.
- Đặt cạnh stage 3: ở đây bạn được miễn phí những gì, và ở đây bạn không diễn đạt được những gì.
Thử đi: list, đọc một cái, đọc một cái không tồn tại, đọc với tư cách một user không có quyền.

### 5. Kiểu lai: một method trên một tài liệu
**Câu hỏi:** làm sao chạy một action trên một tài liệu, và đó là REST hay RPC?

Bắt đầu: `frappe/api/v2.py:221` `execute_doc_method`; so với `frappe/handler.py:292` `run_doc_method`.

Làm rõ mỗi route kiểm tra quyền nào trước khi gọi method (luật của dự án nói action trên một tài liệu là các controller method đã whitelist, gọi qua `/api/v2/document/<DocType>/<name>/method/<method>`; chỉ ra vì sao route đó được chọn).

### 6. Câu trả lời và lỗi: ai định hình chúng
**Câu hỏi:** vì sao v1 trả `{"message": ...}` còn v2 trả `{"data": ...}`, và một exception trở thành status code ở đâu?

Bắt đầu: `frappe/api/__init__.py:63-69` (giá trị return đi vào response), `frappe/utils/response.py:91` `build_response`, `:146` `as_json`, `:39` `report_error`, `frappe/app.py:386` `handle_exception`, status code trên các class trong `frappe/exceptions.py`.

Làm rõ: traceback lọt vào response ở đâu và với điều kiện nào (`frappe/utils/response.py:68`), và ở production một client sẽ thấy gì. Stage này bàn giao sang track A2.

### 7. Transaction bao quanh một request
**Câu hỏi:** khi nào database được commit, và khi nào bị rollback?

Bắt đầu: `frappe/app.py:181-186` và `:458` `sync_database`.

Con người đến từ `@Transactional` của Spring; hãy so sánh tường minh và đánh dấu đó là kiến thức chung, không phải đã trace. Dữ kiện cần đọng lại: một request là một transaction; nó chỉ được commit với method làm đổi trạng thái (hoặc khi một cờ yêu cầu), bị rollback khi có bất kỳ exception nào, và bị rollback với một GET thông thường.
Thử đi (cần một endpoint thí nghiệm tí hon, là một request riêng): một endpoint GET có save một tài liệu, rồi kiểm tra tài liệu không có ở đó; làm lại với POST.

### 8. Phía trình duyệt
**Câu hỏi:** `frappe.call` trong Desk thật sự gửi gì, và SPA của ta gửi gì thay vào đó?

Bắt đầu: `frappe/public/js/frappe/request.js:31` `frappe.call`, `:91` (tiền tố `/api/method/`), `:128` `frappe.request.call`, `:261` (header CSRF). Của ta: `frappe-bench/apps/lab_core/frontend/src/api/hello.js`.

Làm rõ: Desk nói chuyện bằng RPC gần như ở mọi nơi, đó là lý do Frappe là "RPC trước tiên"; CSRF token đến từ đâu (còn phải tìm) và server kiểm tra nó ở đâu (`frappe/auth.py:81`, với các method không an toàn); SPA của ta phải gửi gì cho lần POST đầu tiên.

### 9. Quyết định, rồi xây
**Câu hỏi:** với lab này và dự án sắp tới, kiểu nào cho việc nào?

Đặt ba kiểu cạnh nhau cùng với những gì các stage đã cho thấy, rồi so với đề xuất trong `docs/refer/` (đọc dữ liệu cho màn hình phức tạp qua các hàm BFF; list và CRUD đơn giản qua `/api/v2/document`; action là controller method). Nói rõ chỗ nào bằng chứng ủng hộ và chỗ nào còn mở, kể cả câu hỏi về đường dẫn tùy biến ở stage 2.

Chỉ sau đó mới đề xuất demo của track A trong `OVERVIEW.md`: một resource xây theo kiểu Spring Boot (endpoint mỏng trong `api/`, logic trong một hàm service, input và output có kiểu, đúng verb và status code), dưới dạng các request build và test riêng biệt.

## Track xong khi
Con người, với các file đang mở và không cần agent, có thể:
1. Lần theo `/api/method/lab_core.api.hello.hello` từ `app.py` tới hàm rồi quay lại, gọi tên từng file.
2. Làm tương tự với `GET /api/v2/document/Lab Note`.
3. Nói vì sao cái thứ nhất là RPC còn cái thứ hai là REST, và Frappe cho gì, giữ lại gì ở mỗi cái.
4. Nói đăng nhập, phân quyền, HTTP verb, kiểu tham số và CSRF mỗi thứ được kiểm tra ở đâu.
5. Nói khi nào công việc database của một request được giữ lại và khi nào bị vứt bỏ.
6. Chọn một kiểu cho một endpoint mới và bảo vệ được lựa chọn đó.
