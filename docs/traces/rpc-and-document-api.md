# Trace: RPC method tùy biến và document resource API

Câu hỏi: Vì sao các API Python tùy biến của Frappe thường dùng RPC (gọi hàm từ xa), và điều này liên quan thế nào tới resource API (API theo tài nguyên)?
Phiên bản: Frappe 16.51.0, `frappe-bench/apps/frappe/frappe/__init__.py:58`.

Trả lời ngắn: Frappe đưa ra hai abstraction (lớp trừu tượng) khác nhau qua HTTP. Các resource route cố định của nó thao tác trên DocType, còn một method route cố định thì dispatch (điều phối) tới các hàm Python đã whitelist (được phép gọi từ ngoài). Lập trình viên không cần đăng ký một URL cho từng hàm tùy biến. Đây là một thiết kế quan sát được; lý do lịch sử khiến những người thiết kế chọn nó thì chưa được xác lập. API v2 hỗ trợ cả endpoint RPC lẫn resource. Whitelist cho phép việc gọi, không cho quyền truy cập tài liệu không giới hạn.

Mọi đường dẫn framework bên dưới bắt đầu từ `frappe-bench/apps/frappe/`.

Nhãn: Seen = đã thấy trong source; Inferred = suy ra; Unknown = chưa biết.

## Chuỗi lời gọi

1. Seen: `frappe/app.py:135` `application(request)` khởi tạo request, xác thực authentication, và dispatch các request `/api/` ở dòng 158.
2. Seen: `frappe/app.py:214` `init_request` chọn site, khởi tạo context, kết nối database, parse dữ liệu request, dựng `HTTPRequest`, và chạy các hook `before_request`.
3. Seen: `frappe/auth.py:33` `HTTPRequest` nạp cookie, khởi tạo/tiếp tục một session, và kiểm tra CSRF. Việc kiểm tra CSRF của nó có điều kiện: với các method không an toàn và các điều kiện khác ở dòng 81. Điều này áp dụng trước khi dispatch tới cả hai kiểu API.
4. Seen: `frappe/api/__init__.py:91` gắn các luật v1 tại `/api` và `/api/v1`, và các luật v2 tại `/api/v2`. Ở dòng 59 router so khớp request; dòng 63 gọi endpoint được chọn với các tham số trích từ URL.

### RPC hello tùy biến, v1

5. Seen: `frappe/api/v1.py:145` ánh xạ `/method/<path:method>` tới `handle_rpc_call`. Dòng 35 đặt đường dẫn hàm vào `frappe.form_dict.cmd` và gọi `frappe.handler.handle()`.
6. Seen: `frappe/handler.py:66` `execute_cmd` áp dụng method override, kiểm tra nhánh server-script, tìm ra hàm Python, kiểm tra hàm có trong whitelist và HTTP method, rồi gọi nó với các tham số của request thông qua `frappe.call`. Server script là một nhánh của framework, không phải cách hiện thực được khuyến nghị cho dự án.
7. Seen: `frappe/__init__.py:1132` `get_attr` kiểm tra app đã được cài, tách đường dẫn module và tên hàm, import module, và lấy ra hàm. `frappe.call` ở dòng 1143 ghép tham số vào hàm.
8. Seen: `frappe/__init__.py:439` `whitelist` đăng ký các method được phép và bọc thêm kiểm tra kiểu. `is_whitelisted` ở dòng 479 từ chối các method chưa đăng ký và các lần gọi của Guest không được phép. `frappe/handler.py:100` kiểm tra verb của request.
9. Seen: `frappe-bench/apps/lab_core/lab_core/api/hello.py:5` cho phép GET một cách tường minh, từ chối Guest khi được gọi trực tiếp, và trả về một lời chào cùng username của session. Nó không query DocType nào.
10. Seen: `frappe/handler.py:63` lưu giá trị return dưới `message`. Vì handler RPC của v1 không trả về giá trị dữ liệu thông thường nào, handler API bên ngoài không thay cái này bằng một giá trị `data` (`frappe/api/__init__.py:67`).

### Document resource API, v2

5. Seen: `frappe/api/v2.py:288` ánh xạ GET `/document/<doctype>` tới `document_list`; các luật kề bên chọn handler create/read/update/delete dựa trên URL và verb.
6. Seen: `frappe/api/v2.py:117` đọc fields, filters, thứ tự sắp xếp, offset và limit. Dòng 127 dựng query với `ignore_permissions=False`; dòng 133 xin thêm một dòng dư để phục vụ phân trang.
7. Seen: `frappe/database/query.py:257` dùng user của session trừ khi một user khác được truyền vào; dòng 260 và 277 bật xử lý quyền và kiểm tra quyền select. Toàn bộ thuật toán phân quyền không được lần theo ở đây.
8. Seen: `frappe/api/v2.py:139` cung cấp điểm mở rộng `get_list(query)` ở controller; dòng 158 thực thi query, đặt `has_next_page`, và trả về trang được yêu cầu.
9. Seen: `frappe/api/v2.py:64` việc đọc một tài liệu đơn kiểm tra quyền read và khả năng thấy ở mức field. Create và update dùng `doc.insert()` và `doc.save()` ở dòng 180 và 200. Các thao tác tài liệu đó kiểm tra quyền create và write ở `frappe/model/document.py:478` và `:585`, và gọi xử lý validation/lifecycle (vòng đời) ở `:487` và `:595`.
10. Seen: `frappe/api/__init__.py:68` đặt giá trị return thông thường của handler dưới `data`.

### Response dùng chung và dọn dẹp

11. Seen: `frappe/api/__init__.py:69` dựng JSON response. `frappe/utils/response.py:146` tạo response, xử lý status được cung cấp tường minh, đặt content type JSON, và serialize dữ liệu response cục bộ của request.
12. Seen: `frappe/app.py:181` xử lý exception và rollback. Request thành công thì gọi `sync_database`; ở dòng 458 hàm đó commit với các method không an toàn hoặc khi có cờ commit tường minh, còn lại thì rollback.
13. Seen: `frappe/app.py:195` chạy các hook after-request; dòng 201 xử lý header/cookie của response, rồi dòng 203 trả response. Việc xử lý header/cookie nằm ở dòng 286.

## Ranh giới process và dữ liệu

| Từ → Tới | Cái gì đi qua | Được ghi ở | Được đọc ở |
|---|---|---|---|
| Trình duyệt → tiến trình web của Frappe | GET URL và session cookie same-origin (cùng nguồn gốc) cho SPA này | `frappe-bench/apps/lab_core/frontend/src/api/hello.js:4` | `frappe/app.py:135`, `frappe/auth.py:33` |
| Trình duyệt Desk → tiến trình web của Frappe | Method URL, tham số, HTTP verb, header CSRF | `frappe/public/js/frappe/request.js:91`, `:110`, `:253` | `frappe/app.py:214`, `frappe/auth.py:81`, `frappe/handler.py:87` |
| Tiến trình web của Frappe → database | Query danh sách tài liệu | `frappe/api/v2.py:158` | Việc thực thi ở database driver không được lần theo |
| Tiến trình web của Frappe → client | JSON đã serialize và HTTP status | `frappe/utils/response.py:146` | SPA bóc `message` ở `frappe-bench/apps/lab_core/frontend/src/api/hello.js:22` |

## Sơ đồ

```text
HTTP request → site/session/auth/CSRF → so khớp API route
                                       ├─ method route
                                       │   → tìm ra hàm Python
                                       │   → kiểm tra whitelist + verb
                                       │   → business logic tùy biến
                                       └─ document route
                                           → thao tác DocType tổng quát
                                           → quyền theo tài liệu/query
                                           → validation/query/save
                 ← JSON response ← transaction và hoàn tất request
```

## Các điểm mở rộng tìm thấy

- Seen: `@frappe.whitelist(methods=[...])` đưa một hàm tùy biến ra ngoài mà không cần khai báo route cho từng hàm (`frappe/__init__.py:439`). Hàm phải tự hiện thực các kiểm tra quyền mà hành động nghiệp vụ của nó đòi hỏi.
- Seen: `override_whitelisted_methods` thay đổi hàm được RPC dispatcher chọn (`frappe/__init__.py:1580`); nó không đăng ký route pattern mới.
- Seen: `get_list(query)` của controller ở list v2 có thể sửa một resource query (`frappe/api/v2.py:139`).
- Seen: các hook before/after request chạy ở `frappe/app.py:244` và `:206`; việc dùng chúng một cách an toàn để làm một REST router tùy biến thì chưa được xác lập.
- Seen: `website_route_rules` được diễn giải bởi bộ phân giải đường dẫn của website (`frappe/website/path_resolver.py:215`). Cái này tách biệt với `API_URL_MAP` cố định; nó không phải bằng chứng cho việc đăng ký route `/api` tùy biến.
- Seen: các API handler có thể trả thẳng một `Response` của Werkzeug (`frappe/api/__init__.py:64`); việc serialize JSON cũng tôn trọng status tường minh của response (`frappe/utils/response.py:150`).

## Phát hiện

- Seen: v2 vẫn có RPC `/method/<method>` (`frappe/api/v2.py:280`). Đổi tiền tố phiên bản không biến một lần gọi hàm thành một thao tác trên resource.
- Seen: RPC của v2 tìm ra hàm tùy biến và trả thẳng kết quả của nó (`frappe/api/v2.py:28`), nên kết quả thông thường nhận lớp bọc `data` bên ngoài. hello của v1 dùng `message`.
- Seen: `frappe.call` phía trình duyệt dựng method URL và mặc định dùng POST (`frappe/public/js/frappe/request.js:91`, `:110`). Nó hỗ trợ các tùy chọn URL và verb tường minh. `frappe.call` phía Python là một helper khác, dùng để gọi hàm Python (`frappe/__init__.py:1143`).
- Seen: định dạng lỗi phụ thuộc vào phiên bản API: các field exception của v1 so với `errors` của v2 (`frappe/utils/response.py:34`). Xử lý lỗi chi tiết thuộc về Track A2.
- Inferred: thiết kế này ưu tiên CRUD tổng quát trên DocType cộng với việc dễ dàng đưa các thao tác nghiệp vụ ra ngoài, vì cả hai đường đều được cung cấp tường minh và helper của Desk dùng method URL. Đây là diễn giải về kiến trúc, không phải lý do lịch sử đã được kiểm chứng.
- Inferred: đặt code vào một thư mục tên `api` không đăng ký một resource URL tùy biến, vì dispatcher import một đường dẫn Python còn các route thì được định nghĩa trong map của framework.
- Unknown: điểm mở rộng được hỗ trợ cho các route tùy ý kiểu `/api/lab/notes/<id>` mà không sửa core. Không tìm thấy hook đăng ký route tổng quát nào trên đường dispatch đã xem xét này; điều đó không chứng minh rằng không có ở bất kỳ đâu.

## So sánh (khái niệm thiết kế API nói chung)

RPC nhắm tới một thao tác, như một lời chào, tính toán báo giá, hoặc submit. API HTTP hướng resource nhắm tới một resource và dùng verb để diễn đạt thao tác trên nó. Cả hai đều dùng HTTP và có thể dùng JSON, session, permission và status code. Một API bên ngoài kiểu REST đòi hỏi các resource contract (hợp đồng tài nguyên) có chủ đích; chỉ riêng việc chọn GET thay cho POST không định nghĩa được một contract.

## Thí nghiệm cho con người

1. GET `/api/method/lab_core.api.hello.hello` với một session hợp lệ → mong đợi một lời chào dưới `message`.
2. GET `/api/v2/method/lab_core.api.hello.hello` với cùng session đó → mong đợi lời chào dưới `data`; đặt breakpoint ở `frappe/api/v2.py:44` để so sánh việc dispatch.
3. GET `/api/v2/document/Lab%20Note` → mong đợi các bản ghi tài liệu dưới `data`, kèm metadata phân trang, tùy theo quyền.
4. POST tới URL hello v1 với authentication hợp lệ và có xử lý CSRF → mong đợi bị từ chối vì method này chỉ cho phép GET. Nếu không, một lỗi auth/CSRF xảy ra sớm hơn có thể che mất bước kiểm tra method.
5. Lặp lại GET hello và GET document trong ngữ cảnh Guest → xem mỗi lần từ chối quyền xảy ra ở đâu. Đừng suy ra quyền trên tài liệu chỉ từ việc đăng nhập hợp lệ.

## Không lần theo

Toàn bộ việc lưu trữ session, kiểm tra OAuth/API key, thuật toán phân quyền theo field/dòng, việc thực thi SQL ở database driver, background job, realtime, và toàn bộ hành vi của error hook. Không service, test, database shell hay thí nghiệm mạng nào được thực thi.

## Câu hỏi mở / các trace kế tiếp

Tìm hiểu các điểm mở rộng cho resource route tùy biến trước khi xây demo CRUD kiểu Spring. Trace riêng việc tập trung hóa response/lỗi trong Track A2.
