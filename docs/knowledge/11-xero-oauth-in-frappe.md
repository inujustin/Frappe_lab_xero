# 11. Xero OAuth và các lời gọi HTTP, dùng thứ Frappe đã có sẵn

Nhãn: [S] đã thấy hôm nay, [I] suy ra, [G] kiến thức chung. Hôm nay đã đọc: `frappe/integrations/doctype/connected_app/connected_app.py:60-235`, `frappe/integrations/doctype/token_cache/token_cache.py:35-82`, `frappe/integrations/utils.py:49-95, :164-213`.

## Trả lời trong năm dòng

1. Frappe có sẵn một **OAuth 2.0 client** tổng quát: DocType **Connected App** (cấu hình và luồng xử lý) và DocType **Token Cache** (các token, mỗi app và user một dòng).
2. Nó làm trọn điệu nhảy: dựng authorize URL, giữ `state`, nhận callback, đổi code lấy token, lưu chúng dạng mã hóa, refresh chúng dưới một lock.
3. Vì vậy với Xero **không cần viết code OAuth nào**. Cái còn thiếu thì nhỏ: tenant id, và một luật về việc background job dùng token *của user nào*.
4. Nó tự commit khi lưu token. Một job phải lấy token của mình **trước** lần ghi đầu tiên.
5. Frappe còn có một HTTP helper nhỏ và một log "Integration Request"; cả hai đều là tùy chọn, và cả hai đều có bẫy.

## Luồng, với từng bước nhảy

```text
Desk: form Connected App "Xero" → nút "Connect to …"
 │
 ▼ ConnectedApp.initiate_web_application_flow(user, success_uri)     connected_app.py:94    [S]
 ├─ cho một user khác → cần quyền write trên app                     :96-98
 ├─ OAuth2Session(client_id, redirect_uri, scope)                    :101 → :67-91
 ├─ authorization_url, state = oauth.authorization_url(self.authorization_uri, **query_params)   :103
 ├─ Token Cache "<app name>-<user>": lưu state và success_uri        :104-113, tên ở :133
 ├─ frappe.db.commit()                                               :114
 └─ return authorization_url   → trình duyệt đi tới Xero
 
   … user đăng nhập tại Xero, chọn organisation, đồng ý …

 ▼ GET /api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<app name>?code=…&state=…
 callback(code, state)                                               connected_app.py:197-198   [S]
 ├─ GET đã whitelist, allow_guest=True                               :197
 ├─ nhưng một Guest được đưa tới /login trước, rồi quay lại đây      :206-209
 ├─ tên app là phần thứ 4 của path                                   :211-215
 ├─ Token Cache của (app, session user)                              :216
 ├─ state != state đã lưu → throw                                    :218-219
 ├─ token = oauth_session.fetch_token(token_uri, code=…, client_secret=…, include_client_id=True)   :221-229
 ├─ token_cache.update_data(token)                                   :230
 │     access_token, refresh_token (field Password), expires_in, scopes; state bị xóa;
 │     save(ignore_permissions=True); frappe.db.commit()             token_cache.py:40-72   [S]
 └─ redirect tới success_uri hoặc form Connected App                 :232-233

về sau, trong một background job
 ▼ app.get_active_token(user)                                        connected_app.py:146   [S]
 ├─ token_cache.is_expired()?  (modified + expires_in < now, theo UTC) token_cache.py:74-82
 ├─ hết hạn → with filelock("token_cache_<name>"):                   :151
 │     reload; người khác đã refresh trong lúc đó? → dùng nó         :152-155
 │     oauth_session.refresh_token(token_url=self.token_uri, …)      :157-161
 │     token_cache.update_data(token)   ← lưu refresh token MỚI, commit   :162
 ├─ exception bất kỳ → Error Log "Token Refresh Error", return None  :163-165
 └─ return token_cache
 ▼ token_cache.get_auth_header() → {"Authorization": "Bearer …"}     token_cache.py:35-38
```

Redirect URI được tính ra, không phải gõ vào: [S] `connected_app.py:60-65`: `<site URL>/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<app name>`. **Đúng chuỗi đó là thứ phải được đăng ký trong app Xero.** Nó phụ thuộc vào URL của site (`frappe.utils.get_url()`), nên nó thay đổi giữa lab và bất kỳ môi trường nào khác.

## Điền một Connected App cho Xero

Các field được đọc trong code dưới dạng attribute [S]; các giá trị của Xero là [G] từ `10`.

| Field của Connected App (dùng ở) | Giá trị cho Xero |
|---|---|
| `client_id` (`:84`), `client_secret` (Password, `:79`) | lấy từ app Xero; do bạn gõ trong Desk, không bao giờ trong repo |
| `authorization_uri` (`:103`) | `https://login.xero.com/identity/connect/authorize` |
| `token_uri` (`:87`, `:160`, `:224`) | `https://identity.xero.com/connect/token` |
| child table `scopes` (`:140-141`) | `offline_access`, `accounting.transactions`, `accounting.contacts`, `accounting.settings` (tên cần verify, `10`) |
| child table `query_parameters` (`:143-144`) | không cần gì |
| `redirect_uri` (`:65`) | read-only; copy nó vào app Xero |
| nút OpenID configuration (`:53-54`) | tùy chọn: có thể điền hai URI từ một discovery URL |

Kiểm tra theo luật dự án: một Connected App là một **bản ghi tạo trong Desk**, nên nó chỉ sống trong database. AGENTS.md B3 đặt secret trong "site config hoặc field Password": client secret ở đây là một field Password, nên điều đó được thỏa. Các thiết lập không bí mật (URI, scope) là cấu hình mà luật muốn thấy trong code hơn; có ship chúng dưới dạng fixture (dữ liệu mẫu export theo app) hay không là quyết định của bạn.

## Bốn khoảng trống giữa Connected App và Xero

**Khoảng trống 1: không có tenant id.** Token Cache lưu token và scope, không có gì về organisation. Sau callback, phải có thứ gì đó gọi `GET https://api.xero.com/connections` [G] và lưu `tenantId` được chọn. Việc đó cần một chỗ: một DocType settings trong module "Lab Xero" (ví dụ một single DocType `Lab Xero Settings` với `connected_app` (Link), `connected_user` (Link → User), `tenant_id` (Data), `tenant_name` (Data)). Một DocType do bạn tạo trong Desk (AGENTS.md B2); agent chỉ có thể nêu tên các field.

**Khoảng trống 2: token thuộc về một user của Frappe.** Dòng cache là `"<app>-<user>"` ([S] `:133`), và `get_active_token(user=None)` rơi về `frappe.session.user` ([S] `:147`). Một background job chạy với tư cách người đã xếp nó, hoặc Administrator (`03`). Vậy:

```text
Alice bấm "Connect"       → Token Cache "Xero-alice@…"
Bob tạo một invoice       → job chạy với tư cách Bob → get_active_token() tìm "Xero-bob@…" → None
```

Luật: job **không bao giờ** dùng giá trị mặc định. Nó đọc connected user từ settings và gọi `get_active_token(user=settings.connected_user)`. Một organisation, một connection, một user được lưu.

**Khoảng trống 3: `None` nghĩa là "reconnect".** Một lần refresh thất bại được log và trả về `None` ([S] `:163-165`); không có exception. Bên gọi phải biến `None` thành lỗi rõ ràng của riêng mình ("Xero connection lost; reconnect"), đánh dấu dòng outbox là đang chờ chứ không phải failed, và ngừng gửi cho tới khi một con người reconnect. Coi nó như một thất bại bình thường sẽ đốt hết lượt retry của mọi dòng đang chờ.

**Khoảng trống 4: lock là một file.** `filelock` ([S] `:151`) bảo vệ hai worker **trên cùng một máy**. Với các worker trên nhiều máy dùng chung một database thì không [G]. Ổn cho lab này và cho một server đơn; một ghi chú để sau.

## Bẫy commit

`update_data` kết thúc bằng `frappe.db.commit()` ([S] `token_cache.py:70-71`). Nếu một lần refresh token xảy ra giữa chừng một job, mọi thứ job đã ghi tới lúc đó bị commit ngay tại thời điểm ấy, kể cả khi job thất bại ngay sau đó.

```text
SAI                                     ĐÚNG
 outbox.attempts += 1; outbox.save()     token = get_active_token(user=…)     ← có thể commit; chưa có gì của ta đang mở
 token = get_active_token(...)  ← COMMIT lock dòng outbox, attempts += 1
 gọi Xero → exception → rollback         gọi Xero
   (attempts đã bị commit,               lưu kết quả  → job commit một lần ở cuối
    nửa trạng thái nằm trong database)
```

Điều tương tự áp dụng cho `OAuth2Session` khi nó tự refresh: `get_oauth2_session` nối `token_updater=token_cache.update_data` ([S] `:77`, `:86-88`), nên một lần auto-refresh trong lúc request cũng commit. Kỷ luật đơn giản nhất: **gọi `get_active_token` trước, rồi dựng header từ nó, và không dựa vào auto-refresh.**

Commit bên trong một job có được phép không? Theo luật của ta thì có, trong `tasks/` (AGENTS.md B4). Điểm mấu chốt không phải là được phép hay không; mà là biết ranh giới transaction thật sự nằm ở đâu.

## Thực hiện lời gọi HTTP

Có hai cách trên đĩa.

**A. Session do Frappe dựng.** `connected_app.get_oauth2_session(user)` trả về một `requests_oauthlib.OAuth2Session` ([S] `:8`, `:67-91`), là một `requests.Session` đã gắn token. `requests_oauthlib` được chính Frappe import, nên nó đã là một dependency được cài (AGENTS.md A6 được thỏa; xác nhận nó trong manifest của Frappe trước lần import đầu tiên).

**B. Helper của Frappe.** [S] `frappe/integrations/utils.py:49-93` `make_request(method, url, auth, headers, data, json, params, session=None, timeout=None)`, với các lớp bọc `make_get_request` `:96`, `make_post_request` `:108`, `make_put_request` `:122`.

Helper làm gì, từng dòng một [S]:
- `:67-76` gửi bằng session được đưa hoặc session dùng chung của Frappe.
- `:77` `raise_for_status()`: bất kỳ 4xx hay 5xx nào cũng thành một exception. **Khi đó response body nằm ngoài tầm với của bên gọi**, mà các message validation của Xero lại nằm trong body của một 400. Response cuối được giữ ở `frappe.flags.integration_request` (`:67`), đó là cách lấy được nó.
- `:80-86` trả về JSON đã parse với các câu trả lời JSON.
- `:88-93` khi có exception bất kỳ thì ghi một Error Log và re-raise.
- `:59`, `:75` `timeout` mặc định là `None`: **luôn truyền một giá trị**.

Với Xero, cách B vướng víu: ta cần status code, header `Retry-After` và body để quyết định giữa "retry", "reject" và "unknown". Một client mỏng của riêng ta trong `lab_core/integrations/xero/`, trả về status, header và body, và ánh xạ chúng sang các class exception, thì hợp hơn. Đó cũng là nơi AGENTS.md B1 nói mọi HTTP request tới Xero phải được dựng.

```text
integrations/xero/client.py   (nơi duy nhất biết URL, header, tenant id)
   create_invoice(key, payload) → xero_id
   find_invoice(number)         → xero_id | None
   raises:  XeroRejected   400, 403, 404-khi-ghi       vĩnh viễn      ┐ hai cái đang tồn tại hôm nay:
            XeroTimeout    không có trả lời            không rõ       ┘ client.py:18, :22  [S]
            XeroBusy       429, 500, 503 (+ retry_after)  tạm thời      ← mới
            XeroAuthLost   401 sau một lần refresh, hoặc token None     ← mới
```

Job trong `tasks/` khi đó có mỗi class một nhánh (`12`).

## Log các lời gọi

[S] `frappe/integrations/utils.py:164-212` `create_request_log(data, service_name=…, request_headers=…, output=…, error=…, reference_doctype=…, reference_docname=…)` insert một tài liệu **Integration Request**. Các bẫy:
- `:209` `insert(ignore_permissions=True)`: đó là code của framework, nên không phải luật của ta bị phá, nhưng hãy biết rằng nó bỏ qua permission.
- `:210` `frappe.db.commit()`: lại là bẫy commit. Chỉ gọi nó ở điểm mà một commit là vô hại: trước lần ghi đầu tiên của job, hoặc sau lần ghi cuối.
- Và: `request_headers` được lưu nguyên như được đưa (`:196`). **Không bao giờ truyền header `Authorization`** vào đó (AGENTS.md B6: không token nào trong log).

Với demo, dòng outbox đã ghi lại attempts, nội dung lỗi và Xero id; Integration Request là tùy chọn.

## "Connect to Xero" từ UI của chính ta

Các mảnh đã thấy có thể dùng lại:
- `initiate_web_application_flow` là một **document method** đã whitelist ([S] `:93-94`), nên SPA có thể gọi nó và nhận lại URL, rồi đặt `window.location`. `success_uri` đưa user quay lại một route của SPA; nó được đưa qua `sanitize_redirect` ([S] `:99`), nên hãy chờ đợi chỉ các path cùng site mới sống sót.
- `has_token(connected_app, connected_user)` ([S] `:236-237`) trả lời "ta đã kết nối chưa?" cho một badge trạng thái.

Một lời gọi ra ngoài bên trong một request: callback đổi code ở [S] `:223-229`, bên trong HTTP request. AGENTS.md B4 nói lời gọi ra ngoài chạy trong background job. Ở đây framework làm việc đó, chỉ là một lời gọi, và user đang chờ trên chính lần redirect đó; đó là hình dạng bình thường của OAuth. Được ghi nhận là một ngoại lệ đã biết, không che giấu.

## Thử đi (đọc và Desk, không cần tài khoản Xero)

1. Trong Desk mở danh sách `Connected App` và bấm New: so các field của form với bảng trên. Không lưu.
2. Đọc `connected_app.py:93-116` và `:197-233` song song với hình vẽ luồng. 60 dòng.
3. Đọc `token_cache.py:74-82` và trả lời: thời điểm hết hạn được tính từ timestamp nào? Chuyện gì xảy ra với nó nếu ai đó sửa và lưu dòng Token Cache bằng tay?

## Còn chưa biết

- Các field của Connected App và Token Cache như form hiển thị (JSON chưa được mở; mới chỉ thấy các attribute được dùng trong Python).
- `sanitize_redirect` cho phép những gì.
- Token endpoint của Xero có hài lòng với cách `fetch_token(..., include_client_id=True)` gửi credential (trong body) hay nó đòi HTTP Basic. [G] nói Xero ghi trong tài liệu là Basic; nhiều provider chấp nhận cả hai. Thứ đầu tiên cần thử với một app thật.
- Lời gọi refresh thêm `body="redirect_uri=…"` ([S] `:159`); Xero bỏ qua hay từ chối tham số thừa này.
