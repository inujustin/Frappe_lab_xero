# 01. Request, authentication (xác thực), permissions (phân quyền)

Cố ý viết ngắn. Phần chi tiết đã có trong `docs/traces/rpc-and-document-api.md` và các mục 1, 2 và 6 của `docs/traces/cram-sheet.md`. File này là bản tóm tắt một trang cộng với những gì các note đó để ngỏ: **API key và bearer token**, là thứ quan trọng với webhook của Xero và với bất kỳ máy nào gọi vào ta.

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung. Xem `00-README.md`.

## Cả request trên một màn hình

```text
HTTP request
 │
 ▼ application()                         frappe/app.py:135                 [T]
 ├─ init_request()                       frappe/app.py:214                 [T]  site, kết nối DB, form data
 │    └─ HTTPRequest()                   frappe/auth.py:33                 [T]
 │         ├─ set_session   :78          cookie sid → Session.resume            [S: chỉ cái tên]
 │         └─ validate_csrf_token :81    chỉ với verb không an toàn             [T]
 ├─ validate_auth()                      frappe/auth.py:629                [S]  header Authorization (bên dưới)
 ├─ /api/...  → router                   frappe/api/__init__.py:59,91      [T]
 │     ├─ /method/<path>  → handler.execute_cmd   frappe/handler.py:66     [T]  whitelist + verb, rồi tới hàm của bạn
 │     └─ /document/<doctype>...         frappe/api/v2.py:288              [T]  CRUD tổng quát có xét quyền
 ├─ exception → handle_exception + rollback        frappe/app.py:181-184   [T]
 └─ không exception → sync_database()    frappe/app.py:186 → :458          [T]
        POST/PUT/PATCH/DELETE → commit   :465-466
        GET                   → rollback :467-468
```

## Bốn cách chứng minh bạn là ai

`validate_auth` chạy trên mọi request sau khi session cookie đã được xem xét. [S] `frappe/auth.py:629-652`.

```text
Header Authorization được tách bởi một dấu cách              frappe/auth.py:633
 ├─ không đúng 2 phần → bỏ qua; session cookie (hoặc Guest) giữ nguyên
 └─ 2 phần:
     ├─ "Bearer <token>"  → validate_oauth          :655
     │     tra token trong DocType "OAuth Bearer Token"         :682
     │     hợp lệ → frappe.set_user(<user của token>)           :689
     ├─ "Basic <base64(api_key:api_secret)>"        :706-708
     ├─ "token <api_key>:<api_secret>"              :709-711
     │     cả hai → validate_api_key_secret         :721
     │       tìm một User đang enabled có api_key đó            :728-730
     │       so secret với field Password đã giải mã            :737-738
     │       khớp → frappe.set_user(user)                       :744
     └─ rồi tới auth_hooks của mọi app              :750-752
 có header nhưng vẫn là Guest → AuthenticationError            :644-645
 user bị đổi bởi header → IP allow-list (danh sách IP cho phép) được áp dụng   :651-652
```

| Cách | Ai dùng | Trạng thái trên server | Có cần CSRF |
|---|---|---|---|
| cookie `sid` | Desk, SPA của ta | Session trong Redis + `tabSessions` [T] | Có, với verb không an toàn [T] |
| `token key:secret` | Script, server khác | Không có gì theo từng lần gọi; key và secret nằm trên User | Cần xác nhận: CSRF gắn với session ở `auth.py:81-96`; chưa trace cho auth bằng header |
| `Bearer` | App đã nhận token từ **Frappe đóng vai OAuth server** | Dòng trong `OAuth Bearer Token` | Như trên: cần xác nhận |
| `auth_hooks` | Cơ chế của riêng bạn | Của bạn | Của bạn |

Ba điều đáng nhớ:

- **Hai vai trò OAuth khác nhau.** `validate_oauth` là Frappe đóng vai OAuth **server** (người khác đăng nhập *vào ta*). Xero cần Frappe làm OAuth **client** (ta đăng nhập *vào Xero*). Đó là một mảng code khác: Connected App, file `11`. Đừng lẫn hai cái khi đọc `frappe/oauth.py` và `frappe/integrations/oauth2.py`.
- **Header sai thì chết, thiếu header thì không.** Không có header `Authorization` thì request đi tiếp với tư cách user của cookie hoặc Guest. Có header mà không hợp lệ thì dòng 644 chặn nó lại. [S]
- **Webhook của Xero không có cái nào trong bốn cái trên.** Xero không gửi cookie, không gửi key của ta, không gửi bearer token. Nó ký (sign) phần body. Vì vậy endpoint đó phải là `allow_guest=True` và tự kiểm tra chữ ký. Xem `12`, "Xero gọi ta".

## Permissions, phần bạn cần cho mọi endpoint

Tất cả là [T], từ mục 2 của cram sheet. Giữ ở đây vì nó được dùng trong mọi file về sau.

```text
@frappe.whitelist            cho phép hàm được GỌI. Nó không kiểm tra gì về dữ liệu.
frappe.has_permission(dt, ptype, throw=True)      "user này có được làm việc này với DocType nói chung không"
doc.check_permission(ptype)                       "… với đúng một tài liệu này"
frappe.get_list(...)                              danh sách có xét quyền (SQL được lọc)
frappe.get_all(...)                               KHÔNG xét quyền
```

Endpoint của chính ta cho thấy pattern này: [S] `lab_core/lab_core/api/notes.py:8-29` (dòng kiểm tra quyền trước, rồi tới use case), và [S] `lab_core/lab_core/lab_core/notes.py:29` (`frappe.get_doc(NOTE, name, check_permission="read")`).

**Về background job và permission, đọc `03`, mục "Job là ai?".** Đó là chỗ duy nhất mà user không phải là người bạn tưởng.

## Lỗi, trong ba dòng

- `frappe.throw(msg, ExcClass)` raise (ném lỗi); class exception mang theo HTTP status. Của ta: [S] `lab_core/lab_core/errors.py:10-13` (`LabConflictError`, `http_status_code = 409`).
- v1 (`/api/method`) và v2 (`/api/v2`) định dạng lỗi khác nhau; chỗ rẽ nằm ở `frappe/utils/response.py:34` [T]. Chi tiết thuộc về track A2 và chưa được trace.
- Một exception ở bất kỳ đâu trong request làm rollback cả transaction (`frappe/app.py:181-184` [T]). Đó là lý do một endpoint không bao giờ được "catch rồi return `{success: false}`": dữ liệu sẽ bị commit.

## Đọc tiếp trong source (offline)

1. `frappe/auth.py:629-752`: toàn bộ những điều trên trong 120 dòng. Dễ đọc.
2. `frappe/auth.py:75-99`: cookie, session, CSRF theo thứ tự.
3. `frappe/sessions.py:225-390` [T]: resume (tiếp tục) một session; Redis trước, database sau.

## Còn chưa biết

- CSRF có được kiểm tra với request xác thực bằng API key hoặc bearer token hay không.
- Đăng nhập Google: `frappe/integrations/oauth2_logins.py:11-13` là callback (`login_via_google`, `allow_guest=True`) [S: chỉ chữ ký hàm]; luồng xử lý nằm trong `frappe/utils/oauth.py:121-275` (đã đọc danh sách hàm, chưa đọc thân hàm).
