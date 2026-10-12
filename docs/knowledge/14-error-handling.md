# 14. Xử lý lỗi thống nhất: "middleware" của Frappe nằm ở đâu

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung (.NET, RFC). Hôm nay đã đọc: `frappe/app.py:176-212, :266-300, :380-470`, `frappe/utils/response.py:1-112, :140-221`, danh sách class trong `frappe/exceptions.py`. Không chạy gì. Phần "đề xuất" chưa có dòng code nào; đây là nội dung của track A2 trong `OVERVIEW.md`.

Mục tiêu chính của lab vẫn là tích hợp Xero ↔ ERPNext, nên file này trả lời hai câu: lỗi của **request** đi ra thế nào, và lỗi của **job gọi Xero** đi ra thế nào. Đó là hai kênh khác nhau.

## Trả lời trong năm dòng

1. Frappe **đã có** một chỗ bắt mọi exception của request, giống exception middleware (lớp giữa xử lý lỗi) của .NET: `handle_exception` trong `frappe/app.py:386`. Bạn không viết try/except ở endpoint.
2. Chỗ đó là code của framework: không sửa, không thay được (AGENTS.md B2a). Bạn điều khiển nó bằng ba điểm mở rộng: **class exception** (quyết định status code), **hook `after_request`** (định hình lại body), và **một lớp duy nhất ở frontend**.
3. **Không bao giờ** tạo dạng lỗi thống nhất bằng cách catch trong endpoint rồi return một dict: request khi đó "thành công" và transaction bị **commit**. Việc định hình lỗi phải xảy ra sau rollback.
4. v1 (`/api/method`) và v2 (`/api/v2/method`) trả lỗi theo hai dạng khác nhau; v2 đã gần với một dạng thống nhất mà không cần code.
5. Lỗi khi gọi Xero **không đi qua đường này**: nó xảy ra trong background job, không có HTTP response nào. Nó tới người dùng qua dòng outbox (`error`) và `sync_status`.

## Đường đi của một lỗi trong request

```text
endpoint / service / controller:  frappe.throw(msg, LabConflictError)     frappe/utils/messages.py:138   [S: chữ ký]
        │ exception bay lên, không ai catch
        ▼
application()  except Exception as e:                                     frappe/app.py:181-182          [S]
   ├─ HTTPException của Werkzeug → e.get_response(...)                    :182
   ├─ còn lại → handle_exception(e)                                       :182 → :386
   │     http_status_code = getattr(e, "http_status_code", 500)           :388   ← class exception quyết định status
   │     respond_as_json: Accept là JSON/ajax, hoặc path bắt đầu /api/    :390-392
   │     JSON → frappe.utils.response.report_error(status)                :403 → response.py:39
   │     không JSON → trang lỗi HTML (401, 403, 404, 429, còn lại)        :405-441
   │     status >= 500 hoặc developer_mode → log_error_snapshot(e)        :448-449
   └─ db.rollback()                                                       :183-184
finally:
   run_after_request_hooks(request, response)                             :195 → :206-210   ← "middleware" của app
        mỗi hook được gọi với response=..., request=...                   :210
        hook tự ném lỗi → chỉ bị log, response giữ nguyên                 :196-198
log_request(request, response)                                            :266   (chỉ khi conf enable_frappe_logger)
process_response(response)                                                :286
   header X-Frappe-Request-Id = frappe.monitor.get_trace_id()             :297-298
```

`report_error` dựng body [S] `frappe/utils/response.py:39-65`:

| | v1: `/api/method/...` | v2: `/api/v2/method/...` |
|---|---|---|
| Kiểu lỗi | `exc_type: "LabConflictError"` (`:53`) | `errors: [{"type": "LabConflictError", ...}]` (`:56-60`) |
| Message của `frappe.throw` | `_server_messages`: một chuỗi JSON chứa các chuỗi JSON (`:200-203`) | gộp thẳng vào phần tử `errors[0]` (`:79-87`); message khác nằm ở `messages` (`:214-215`) |
| Traceback | `exception` (dòng cuối) + `exc` | `errors[0].exception` (cả traceback) |
| Thành công | `{"message": ...}` [T] | `{"data": ...}` [T] |

**Vì sao bạn thấy traceback ở mọi lỗi** [S] `response.py:68-78`: traceback được phép khi đang chạy dev server (`frappe._dev_server`), hoặc khi System Settings bật `allow_error_traceback` **và** người gọi là system user. Lab chạy dev server nên luôn thấy. Ở production, user thường của SPA không thấy traceback. Đây là câu trả lời cho câu hỏi đầu của track A2.

Status code có sẵn trên class [S] `frappe/exceptions.py`: `ValidationError` 417 (`:25`), `AuthenticationError` 401 (`:33`), `PermissionError` 403 (`:41`), `DoesNotExistError` 404 (`:45`), `NameError` 409 (`:57`), `CSRFTokenError` 400 (`:82`), `TooManyRequestsError` 429 (`:86`). Của ta: `lab_core/lab_core/errors.py:10-13` `LabConflictError`, 409. Một exception không có `http_status_code` thành 500.

Lưu ý: `frappe.throw(msg)` không truyền class thì ném `ValidationError` → **417**, không phải 400. Client phải biết điều đó, hoặc ta luôn truyền class của ta.

## So với .NET [G]

| .NET | Frappe | Ghi chú |
|---|---|---|
| `app.UseExceptionHandler(...)` / `IExceptionHandler` | `handle_exception`, `app.py:386` | Có sẵn, cố định; không đăng ký thêm handler được |
| Exception → status qua bảng ánh xạ | attribute `http_status_code` trên class | Khai báo ngay trên class, không có bảng |
| `ProblemDetails` (RFC 9457) làm dạng lỗi chung | v1 và v2 mỗi cái một dạng riêng | Muốn dạng riêng: hook `after_request` hoặc lớp frontend |
| Middleware pipeline, thứ tự do bạn sắp | hook `before_request` (`app.py:244`) và `after_request` (`:206-210`) | Chỉ hai điểm, không bọc quanh được; thứ tự theo app đã cài |
| Exception filter theo controller | Không có | Decorator trên endpoint của ta là thứ gần nhất, nhưng xem cái bẫy bên dưới |
| Correlation id | `X-Frappe-Request-Id` (`app.py:297-298`) | Có sẵn trên response khi monitor cấp trace id |

Khác biệt lớn nhất: ở .NET middleware **bọc** request; ở Frappe hook `after_request` chạy **sau khi** response đã dựng xong và transaction đã rollback. Nó sửa được response, không chặn được gì.

## Cái bẫy: catch để "làm đẹp" lỗi

```text
SAI                                            ĐÚNG
@frappe.whitelist(methods=["POST"])            @frappe.whitelist(methods=["POST"])
def create_note(...):                          def create_note(...):
    try:                                           frappe.has_permission(..., throw=True)
        ...ghi dữ liệu...                          return notes.create_note(...)      # raise thì cứ để bay lên
    except Exception as e:
        return {"success": False, ...}         → handle_exception → ROLLBACK → after_request định hình body
→ không có exception → sync_database() COMMIT  frappe/app.py:186, :465-466 [T]
  nửa dữ liệu đã ghi nằm lại trong database
```

Một decorator "bắt lỗi rồi trả dạng chuẩn" bọc endpoint cũng rơi đúng vào bẫy này. Decorator của ta (guard decorator mà AGENTS.md B4 nhắc tới) chỉ nên làm phần **trước** và phần **thành công**: kiểm tra quyền, bọc giá trị return. Phần lỗi để cho exception đi hết đường của nó.

## Ba cách có một dạng lỗi thống nhất

| | Cách | Cần gì | Rủi ro | Khi nào |
|---|---|---|---|---|
| **A** | Một lớp ở frontend: `frontend/src/api/` là nơi duy nhất gọi backend (`INIT.md`), nó đọc status + `exc_type`/`errors` + message rồi ném một kiểu lỗi duy nhất cho cả SPA | Chỉ code frontend | Không đụng server | **Ngay bây giờ**; đủ cho demo Xero |
| **B** | Gọi endpoint của ta qua v2: `/api/v2/method/lab_core.api.notes.<name>` | Đổi URL trong lớp A; `SPRINT.md` đang ghi v1 và câu trả lời dưới `message` | Bảng endpoint của sprint phải đổi (`data` thay cho `message`): mọi phiên đang xây dựa vào nó | Sau sprint, khi chốt ADR |
| **C** | Hook `after_request` đăng ký từ `lab_core`: chỉ với path `/api/method/lab_core.` hoặc `/api/v2/method/lab_core.`, status ≥ 400, body JSON → viết lại body thành một dạng. Thứ bị đổi ở đây là **dạng lỗi do Frappe dựng** (`report_error`, code của framework), không phải endpoint của ta: endpoint của ta vẫn chỉ raise và không bị hook hay override | Một hàm dưới `lab_core/overrides/` (vì nó đổi hành vi của Frappe) + **một dòng trong `hooks.py`** (con người thêm, AGENTS.md B2) | Hook ném lỗi thì bị nuốt và trả dạng gốc của Frappe (`app.py:196-198`): lớp A vẫn phải hiểu dạng gốc. Phải lọc theo path, không thì đổi luôn response của Desk, ERPNext, CRM | Khi cần client ngoài SPA (mobile, hệ thống khác) |

Khuyến nghị: **A trước** (không rủi ro, không đụng `hooks.py`), rồi quyết B hay C trong một ADR. AGENTS.md B4 nói response theo dạng chung "một khi `docs/adr/` định nghĩa nó": thư mục `docs/adr/` hiện chưa tồn tại, nên dạng dưới đây mới là đề xuất.

Dạng đề xuất, lấy ý từ RFC 9457 [G]:

```text
thành công   { "data": <kết quả> }
lỗi          { "error": { "code": "LabConflictError",          ← tên class: client rẽ nhánh theo cái này, không theo message
                          "message": "Note LN-0001 is already synced.",   ← đã dịch, hiện được cho người dùng
                          "status": 409,
                          "request_id": "<X-Frappe-Request-Id>",          ← để tìm trong log
                          "details": [ ... ] } }                          ← tùy chọn: lỗi theo field
```

Không bao giờ đưa traceback, tên bảng, `sid` hay token vào body (AGENTS.md B6).

## Kênh thứ hai: lỗi khi gọi Xero

```text
REQUEST                                        JOB (gọi Xero)
frappe.throw → handle_exception → HTTP 4xx     XeroRejected / XeroTimeout / XeroBusy / XeroAuthLost   (11, 12)
client thấy ngay, trong response                không có client nào đang chờ
                                                → outbox.status + outbox.error, tài liệu.sync_status   tasks/xero_sync.py:43-51 [S]
                                                → lỗi bất ngờ: rollback + Error Log                    frappe/utils/background_jobs.py:296-302 [S]
                                                client biết bằng: poll get_note / realtime (04)
```

Vậy "thống nhất" với tích hợp Xero nghĩa là hai việc:
1. **Bốn class lỗi của client Xero** (`11`) là bảng ánh xạ lỗi của kênh job, đóng vai trò của `http_status_code` ở kênh request: mỗi class một nhánh, mỗi nhánh một kết cục cho dòng outbox (`12`, "Bốn loại thất bại").
2. **SPA hiển thị cả hai kênh ở một chỗ**: lỗi request (dạng trên) và `sync_status = Failed` kèm `error` của outbox. `get_note` hôm nay chưa trả về nội dung lỗi của outbox ([S] `lab_core/lab_core/notes.py:28-36`): người dùng thấy `Failed` mà không thấy lý do. Đó là một khoảng trống nhỏ, đáng sửa trước mọi thứ khác trong file này.

Message validation của Xero (body của một `400`, `10`) nên được lưu nguyên vào `outbox.error`, vì con người phải đọc nó để sửa dữ liệu.

## Log dễ đọc

- Dòng log request có sẵn: `log_request`, [S] `app.py:266-280` (site, user, path, method, status), chỉ ghi khi conf `enable_frappe_logger` bật. Giá trị conf nằm trong site config, agent không đọc (AGENTS.md B2).
- `X-Frappe-Request-Id` có trên response ([S] `app.py:297-298`); client có thể gửi sẵn id của mình và Frappe dùng lại nếu nó giống UUID ([S] `frappe/monitor.py:81-84`). Đưa id này vào `error.request_id` và vào dòng log của job là cách nối một lỗi người dùng báo với dòng log.
- Trong job: `frappe.log_error` rồi re-raise (AGENTS.md B4); không log token (`11`, mục "Log các lời gọi").

## Thử đi (trình duyệt, không cần lệnh)

1. Gọi `retry_sync` cho một note đã `Synced` qua v1 rồi qua v2 (đổi `/api/method/` thành `/api/v2/method/`), xem tab Network: status 409 ở cả hai, body khác nhau đúng như bảng trên.
2. Trong response đó, tìm header `X-Frappe-Request-Id`.
3. Đọc `frappe/app.py:176-212` (36 dòng) và nói thành tiếng: hook `after_request` chạy trước hay sau rollback? Nó có chạy khi request thành công không?

## Còn chưa biết

- `frappe.monitor.get_trace_id()` có trả giá trị khi monitor không bật hay không; thân hàm chưa đọc.
- Thứ tự hook `after_request` giữa các app, và các hook có sẵn của Frappe ở `frappe/hooks.py:481` làm gì với response.
- `handle_exception` được bọc bởi `@handle_does_not_exist_error` (`app.py:385`); decorator đó làm gì thì chưa đọc.
- Lỗi kiểm tra kiểu tham số (`frappe/utils/typing_validations.py:25` [T]) ra status nào: `FrappeTypeError` là 417 (`exceptions.py:28-29`), chưa xác nhận đó là class được ném.
