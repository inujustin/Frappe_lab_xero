# 11. Lỗi và response thống nhất: "middleware" xử lý lỗi cho demo

Kiến thức cho phase PE của `plan/done/xero/PLAN.md`. PE thuộc **giai đoạn 2**: chỉ làm sau khi tích hợp Xero (hai luồng của đề bài) đã xong, và chỉ ở mức tối thiểu: hai class lỗi mới và một hàm thêm khối `error`. Trong giai đoạn 1, điều duy nhất cần nhớ từ file này là: endpoint chỉ raise, không catch. Bản chung, rộng hơn (v1 so với v2, ba cách làm, phía frontend): `docs/knowledge/14-error-handling.md`; file này đủ để làm PE mà không cần mở nó.

Nhãn: xem `00-README.md`. Đã đọc hôm nay: `frappe/app.py:135-212, :385-404, :443-452`, `frappe/utils/response.py:39-90`, `frappe/monitor.py:41-44` (đường dẫn từ `frappe-bench/apps/frappe/`). Phần so với .NET là kiến thức chung.

## Trả lời trong năm dòng

1. Frappe **đã có** một chỗ duy nhất bắt mọi exception của request: `handle_exception`. Nó là thứ gần nhất với exception middleware của .NET, nhưng là code của framework: không sửa, không thay.
2. Ta điều khiển nó bằng hai điểm mở rộng: **class của exception** (quyết định HTTP status) và **hook `after_request`** (sửa body sau khi nó đã được dựng).
3. Endpoint của ta **chỉ raise, không catch**. Mọi việc "làm đẹp" lỗi xảy ra sau khi Frappe đã rollback.
4. Demo không có SPA: bên gọi endpoint là Desk. Vì vậy lớp định hình chỉ **thêm** một khối `error` và **gỡ** traceback; nó không được xóa những key mà Desk đang đọc.
5. Lỗi khi gọi Xero **không đi đường này**: nó xảy ra trong job, không có HTTP response. Nó tới người dùng qua trạng thái và lý do trên Sales Order (`07`, "Hai kênh lỗi").

## Vì sao hôm nay lỗi trông "xấu và thô"

```text
endpoint / service:  frappe.throw(msg, <class lỗi>)
        │ exception bay lên, không ai catch
        ▼
application():  except Exception → handle_exception(e)                 frappe/app.py:181-182 → :386   [S]
   status = getattr(e, "http_status_code", 500)                        :388   ← class không có thuộc tính này → 500
   là request JSON hoặc đường /api/ → report_error(status)             :389-403
        v1: body có exc_type; nếu được phép: exception + traceback     frappe/utils/response.py:49-53
        v2: body có errors[{type, …}]; nếu được phép: cả traceback     :54-60
   status ≥ 500 hoặc developer mode → ghi lại lỗi                      app.py:448-449
   rồi rollback                                                        :183-184
finally:  các hook after_request(response=…, request=…)                :195 → :206-211   ← chỗ của ta
process_response: gắn header X-Frappe-Request-Id nếu có trace id       :297-298
```

Ba nguyên nhân của cái "thô":
- **Traceback luôn hiện trong lab.** Nó được phép khi đang chạy dev server, *hoặc* khi cài đặt `allow_error_traceback` bật và người gọi là system user ([S] `response.py:68-79`). Lab chạy dev server nên điều kiện đầu luôn đúng. Ở production, user thường không thấy traceback.
- **Sai status.** `frappe.throw(msg)` không truyền class thì ném `ValidationError`, status 417 [K `frappe/exceptions.py:25`]; exception lạ thì 500.
- **Mỗi đường một dạng body.** `/api/method` (v1) và `/api/v2/method` trả lỗi theo hai hình khác nhau ([S] `response.py:48-60`).

## Cái bẫy phải tránh

```text
SAI                                              ĐÚNG
def retry(name):                                 def retry(name):
    try:                                             frappe.has_permission(..., throw=True)
        …ghi dữ liệu…                                return service.retry(name)      # raise thì để bay lên
    except Exception as e:
        return {"success": False, "msg": str(e)}  → handle_exception → ROLLBACK → hook after_request định hình body
→ request "thành công" → Frappe COMMIT
  nửa dữ liệu đã ghi nằm lại trong database
```

Catch trong endpoint (hay trong một decorator bọc endpoint) biến một lỗi thành một lần commit ([S] `app.py:186-187`: không có exception thì `sync_database()`). Đây cũng là luật dự án: lỗi qua `frappe.throw`, không bao giờ trả `{"success": False}` (AGENTS.md B4).

## Thiết kế cho demo

**Một: lỗi có tên và có status.** Class quyết định status; endpoint chỉ chọn class.

| Tình huống | Class | Status |
|---|---|---|
| không có quyền | `frappe.PermissionError` | 403 |
| không tìm thấy | `frappe.DoesNotExistError` | 404 |
| trạng thái không cho phép (Retry một đơn đã `Synced`; cancel một đơn đã có tiền trả) | `LabConflictError` (đã có: [S] `lab_core/errors.py`) | 409 |
| dữ liệu đầu vào sai | `LabValidationError` (mới) | 422 |
| Xero chưa nối hoặc đang tạm dừng | `LabIntegrationUnavailableError` (mới) | 503 |

**Hai: một chỗ duy nhất định hình body lỗi.** Một hàm đăng ký ở hook `after_request`:

```text
after_request(response, request):
   chỉ khi  path bắt đầu bằng /api/method/lab_core.  hoặc  /api/v2/method/lab_core.
        và  status ≥ 400   và  body là JSON
   → thêm:  "error": { "code": <tên class>, "message": <thông báo đã dịch>, "status": <status>, "request_id": <id> }
   → gỡ:    traceback khỏi body
   → giữ nguyên mọi key khác
   mọi trường hợp khác: không đụng gì
```

Vì sao **thêm** chứ không **thay**: Desk hiển thị thông báo lỗi từ các key gốc của Frappe [G: cách `frappe.call` của Desk đọc response chưa được trace]. Thay cả body có thể làm nút Retry trong Desk báo lỗi trống. Thêm một khối `error` thì client bên ngoài có một dạng ổn định để đọc, còn Desk vẫn chạy như cũ. Đây là điều đầu tiên phải thử khi làm PE.

Vì sao hàm này nằm dưới `overrides/`: thứ nó đổi là body lỗi do **Frappe** dựng (`report_error`), tức hành vi của code không phải của ta. Endpoint của ta không bị hook hay override; chúng vẫn chỉ raise.

**Ba: dòng log đọc được (để sau, không thuộc mức tối thiểu).** Mỗi request lỗi của `lab_core` ghi một dòng ngắn: thời điểm, user, path, status, `error.code`, request id. Không token, không `sid`, không body (AGENTS.md B6). Traceback đầy đủ vẫn nằm ở Error Log của Frappe cho lỗi ≥ 500.

## Bốn tính chất của hook `after_request` phải biết trước khi viết

| Tính chất | Hệ quả | Bằng chứng |
|---|---|---|
| Chạy **sau** rollback/commit | sửa được response, không chặn được request; đừng ghi database ở đây | [S] `app.py:181-195` |
| Chạy cho **mọi** request của site, kể cả Desk, ERPNext, CRM, và cả request thành công | **bắt buộc lọc theo path**; quên lọc là đổi response của cả hệ thống | [S] `app.py:189-195` |
| Hook tự ném lỗi thì bị nuốt, chỉ ghi log; response gốc vẫn được trả | client vẫn phải hiểu được dạng gốc; khi làm PE, thử tay một lần trường hợp hàm định hình hỏng | [S] `app.py:194-198` |
| Bị bỏ qua nếu request hỏng trước khi Frappe khởi tạo xong | vài lỗi rất sớm không đi qua nó | [S] `app.py:206-208` |

## So với middleware của .NET

| .NET | Frappe |
|---|---|
| `UseExceptionHandler` / `IExceptionHandler`: bạn đăng ký handler | `handle_exception`: có sẵn, cố định |
| bảng ánh xạ exception → status | thuộc tính `http_status_code` ngay trên class |
| `ProblemDetails` làm dạng lỗi chung | không có sẵn; tự thêm bằng hook `after_request` |
| middleware **bọc** request (trước và sau) | chỉ có hai điểm: `before_request` và `after_request`; không bọc được |
| correlation id | header `X-Frappe-Request-Id` |

Khác biệt lớn nhất: middleware của .NET có thể chặn và thay cả response; hook của Frappe chạy khi mọi thứ đã xong, chỉ sửa được kết quả.

## Kênh thứ hai: lỗi của job gọi Xero

```text
REQUEST (bấm Retry, Refresh)                    JOB (gọi Xero)
 raise → handle_exception → HTTP 4xx             XeroRejected / XeroTimeout / XeroBusy / XeroAuthLost
 → hook của ta thêm khối "error"                 không có HTTP response nào
 người dùng thấy ngay                            → lab_xero_sync_status = Failed, lab_xero_error = lý do (nguyên văn của Xero)
                                                 → người dùng thấy khi mở hoặc Refresh đơn
```

"Thống nhất" trong demo nghĩa là cả hai kênh cùng theo một nguyên tắc: **lỗi có tên, có lý do đọc được, không có traceback trước mặt người dùng, và tìm lại được trong log.** Chúng không dùng chung một cơ chế, và không cần.

## Kịch bản DEMO E (khoảng hai phút)

1. Trước: gọi Retry trên một đơn đã `Synced`, xem tab Network: body thô của Frappe, có traceback.
2. Sau khi bật lớp định hình: cùng lời gọi → status 409, có `error.code = "LabConflictError"`, `error.message`, `error.request_id`; không còn traceback.
3. Trong Desk, cùng thao tác vẫn hiện một thông báo đọc được.
4. Một request thành công: body y như trước.
5. Một đơn bị Xero từ chối: lý do hiện ngay trên form (kênh thứ hai).

## Chưa biết, phải thử khi làm

- Desk đọc những key nào của response lỗi; gỡ traceback có làm đổi cách Desk hiện lỗi không.
- `X-Frappe-Request-Id` chỉ có khi Frappe cấp trace id ([S] `app.py:297-298`; `monitor.py:41-44` trả `None` nếu không có monitor cho request). Nếu trong lab nó trống, lớp định hình phải tự sinh một id và ghi cùng id đó vào dòng log.
- Thứ tự giữa hook của ta và các hook `after_request` có sẵn của Frappe.
- Lỗi kiểm tra kiểu tham số của endpoint ra status nào.

## Tự kiểm tra

1. Vì sao catch exception trong endpoint rồi trả một dict lại nguy hiểm hơn là để nó bay lên?
2. Hook `after_request` của ta quên lọc theo path thì chuyện gì xảy ra?
3. Một lỗi do Xero từ chối hóa đơn có đi qua lớp định hình này không? Người dùng thấy nó ở đâu?
