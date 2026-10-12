# 02. OAuth: từng bước, vào gì, ra gì, đi đâu, để làm gì

OAuth 2.0 cho phép Frappe làm việc trên sổ sách Xero của một người mà **không cầm mật khẩu Xero** của họ. Người đó đăng nhập tại Xero, bấm đồng ý, và Xero đưa cho Frappe các token có phạm vi và có hạn.

Trong demo, phần OAuth do DocType có sẵn của Frappe làm (`Connected App`, `Token Cache`). Code của ta chỉ: (1) tạo bản ghi cấu hình, (2) lấy token ra dùng, (3) hỏi Xero organisation nào đã được nối.

## Bốn bên

| Vai | Là ai | Giữ gì |
|---|---|---|
| Chủ dữ liệu | admin có login Xero (bạn) | mật khẩu Xero |
| Client (phần mềm xin quyền) | app "Frappe App" đăng ký tại developer.xero.com, chạy trong Frappe | `client_id`, `client_secret` |
| Nơi cấp quyền | `login.xero.com`, `identity.xero.com` | biết ai đã đồng ý cho app nào |
| Nơi có dữ liệu | `api.xero.com` | invoice, contact, credit note |

Người bán hàng dùng Frappe không có vai nào ở đây và không cần tài khoản Xero.

## Chuẩn bị (làm một lần, trước mọi bước)

| # | Việc | Vào | Ra | Lưu ở đâu |
|---|---|---|---|---|
| P1 | Đăng ký app tại developer.xero.com | tên app, loại **Web app**, Company URL (https), **Redirect URI** | `client_id`, `client_secret` | phía Xero |
| P2 | Đặt bí mật vào Frappe | 5 giá trị gõ vào script (ẩn khi gõ) | — | **site config** của site (`xero_client_id`, `xero_client_secret`, `xero_connected_user`, `xero_default_account_code`, `xero_default_tax_type`) |
| P3 | Đặt URL của site | `host_name = http://localhost:8000` | — | site config |
| P4 | `bench migrate` | — | bản ghi Connected App tên `xero` | database |

Redirect URI đã đăng ký (đã quan sát, in ra khi migrate):

```text
http://localhost:8000/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/xero
```

Hai điều đã học được bằng lỗi thật:
- Xero chỉ nhận `http` với đúng tên `localhost`; `http://lab.localhost:8000/…` bị từ chối với "Must use https (except localhost which may use http)". Vì vậy có bước P3.
- Ô "Company or application URL" đòi `https`; dùng URL repo GitHub của bạn.

### Code của ta ở bước P4: `setup/xero_connection.py`

Chạy sau mỗi lần migrate (hook `after_migrate`). Nó đọc site config rồi tạo hoặc cập nhật bản ghi; bí mật không bao giờ nằm trong repo.

```python
# setup/xero_connection.py:6-12
CONNECTED_APP_NAME = "xero"
SCOPES = (
	"offline_access",
	"accounting.invoices",
	"accounting.contacts",
	"accounting.settings.read",
)
```

```python
# setup/xero_connection.py:53-70
exists = frappe.db.exists("Connected App", CONNECTED_APP_NAME)
app = (
	frappe.get_doc("Connected App", CONNECTED_APP_NAME)
	if exists
	else frappe.get_doc({"doctype": "Connected App"})
)
app.provider_name = "Xero"
app.authorization_uri = "https://login.xero.com/identity/connect/authorize"
app.token_uri = "https://identity.xero.com/connect/token"
app.client_id = values["xero_client_id"]
app.client_secret = values["xero_client_secret"]
if tuple(row.scope for row in app.scopes or []) != SCOPES:
	app.set("scopes", [{"scope": scope} for scope in SCOPES])
if exists:
	app.save()
else:
	app.insert(set_name=CONNECTED_APP_NAME)
print(f"[xero setup] Connected App xero ready; Redirect URI: {app.redirect_uri}")
```

- **Tên cố định `xero`** (`set_name`): Redirect URI chứa tên bản ghi, nên tên cố định thì URI không đổi dù dựng lại database.
- **Chạy lại an toàn**: có rồi thì cập nhật, chưa có thì tạo; scope chỉ ghi lại khi khác.
- Redirect URI không do ta viết: Frappe tự tính lúc lưu, từ URL của site:

```python
# frappe/integrations/doctype/connected_app/connected_app.py:60-65  (code của Frappe)
def validate(self):
	base_url = frappe.utils.get_url()
	callback_path = (
		"/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/" + self.name
	)
	self.redirect_uri = urljoin(base_url, callback_path)
```

Bốn scope và lý do:

| Scope | Cho phép | Dùng ở |
|---|---|---|
| `offline_access` | được cấp **refresh token** (không có nó: 30 phút là hết) | làm mới token |
| `accounting.invoices` | đọc/ghi invoice và credit note | tạo, void, đọc hóa đơn; đọc credit note |
| `accounting.contacts` | đọc/ghi contact | tìm, tạo khách |
| `accounting.settings.read` | đọc tài khoản, mã thuế | tra mã `200`, `NONE` |

### Scope đến từ đâu, và chỉ dùng một phần thì cấu hình thế nào

Có **ba danh sách** khác nhau, mỗi cái hẹp hơn cái trước:

```text
 ① Danh sách ở developer.xero.com → app → Configuration → "Authorisation / Scopes"
      (accounting.*, payroll.*, …; vài chục dòng)
      = TRẦN: những scope app này ĐƯỢC PHÉP xin. Do Xero định cho app.
                    │  ta chỉ xin một phần
                    ▼
 ② Hằng SCOPES trong code của ta (setup/xero_connection.py:7-12)  →  bảng con "scopes" của Connected App
      →  tham số  scope=…  trong URL authorize
      = những scope app XIN ở lần Connect này. Do ta chọn.
                    │  người dùng bấm Allow trên màn hình đồng ý của Xero
                    ▼
 ③ Scope nằm trong token Xero cấp
      = những gì token THẬT SỰ làm được. Gọi API ngoài phạm vi này thì Xero từ chối.
```

Danh sách ① dài không có nghĩa là app có ngần ấy quyền. Quyền thật là ③, và ③ không bao giờ rộng hơn ②. Ta xin 4 scope, nên token không đụng được payroll, ngân hàng hay báo cáo, dù chúng có trong ①.

Tên scope đọc như sau: `accounting.invoices` = đọc **và** ghi; `accounting.invoices.read` = chỉ đọc. `offline_access` không phải quyền trên dữ liệu: nó xin Xero cấp refresh token.

**Chỉ dùng một phần = sửa danh sách ②, ở một chỗ:**

| # | Việc | Ai làm | Kết quả |
|---|---|---|---|
| 1 | Sửa hằng `SCOPES` trong `setup/xero_connection.py` | sửa code | — |
| 2 | Chạy `bench migrate` | con người | hook `after_migrate` ghi lại bảng `scopes` của Connected App (dòng 65-66 ở trên: chỉ ghi khi khác) |
| 3 | Bấm **Connect to Xero** lại | admin | Xero hiện màn hình đồng ý với danh sách mới; token mới mang scope mới |

Thiếu bước 3 thì không có gì đổi: token đang lưu vẫn mang scope của lần Connect trước. Không cần sửa gì ở developer.xero.com, miễn là scope muốn xin có trong danh sách ①.

**Mỗi scope ứng với lời gọi nào trong code** (đối chiếu với `integrations/xero/client.py`):

| Scope ta xin | Lời gọi dùng nó | Có thể hẹp hơn không |
|---|---|---|
| `offline_access` | làm mới token | không: bỏ thì 30 phút phải Connect lại |
| `accounting.contacts` | `GET /Contacts`, `PUT /Contacts` | không: cần ghi để tạo contact |
| `accounting.invoices` | `GET`/`PUT`/`POST /Invoices`, `GET /CreditNotes` | không: cần ghi để tạo và void. Đã quan sát: job kéo gọi `/CreditNotes` mỗi lượt mà không bị từ chối |
| `accounting.settings.read` | **không lời gọi nào trong code hiện tại** | **có: bỏ được.** Nó chỉ phục vụ việc tra mã tài khoản và mã thuế bằng tay lúc cài đặt |

Nói thẳng khi bảo vệ: ba scope là tối thiểu thật; scope thứ tư là dư và bỏ được bằng một dòng code.

Chưa kiểm chứng: danh sách ① có sửa được trên trang đó không (ảnh chụp chỉ thấy dạng chữ); `GET /connections` cần scope nào (nó đã chạy với bốn scope hiện tại); và việc **bỏ bớt** scope có cần gỡ kết nối cũ bên Xero trước khi Connect lại không. Thông báo trên trang đó nói app tạo trước một mốc ngày còn giữ các scope rộng kiểu cũ tới tháng 9/2027; app của ta dùng tên scope mới, chi tiết hơn.

### Giới hạn app từ phía Xero: làm được gì trên web Xero

Scope tuy do code của ta **xin**, nhưng do Xero **thi hành**: token mang danh sách scope, và mỗi lời gọi ngoài danh sách bị Xero từ chối. App không tự nới được: xin thêm scope thì phải Connect lại, và danh sách mới hiện ra trên màn hình đồng ý của Xero cho admin thấy.

```text
 Ai giới hạn            Ở đâu                                  Mịn tới mức nào
 ───────────            ─────                                  ───────────────
 ta (app)               SCOPES trong code                      từng loại dữ liệu, đọc / đọc+ghi
 admin lúc Connect      màn hình đồng ý của Xero               chọn TỔ CHỨC nào; Allow hoặc từ chối cả gói
 admin về sau           web Xero: Settings → Connected apps    gỡ kết nối (tất cả hoặc không)
 kế toán                web Xero: lock dates, quy trình duyệt  chặn sửa chứng từ theo kỳ, kể cả qua API
 Xero                   kiểm scope ở mỗi lời gọi               đúng theo token
```

| Muốn giới hạn | Làm được trên web Xero? | Cách |
|---|---|---|
| App chỉ vào **một** tổ chức | Có | chọn tổ chức ở màn hình đồng ý |
| Cắt hẳn quyền của app | Có | gỡ app trong Connected apps của tổ chức; token đang lưu hết dùng được |
| Ai được phép nối app | Có | chỉ user có vai trò đủ cao trong tổ chức mới Allow được |
| Không cho sửa chứng từ của kỳ đã khóa | Có | lock dates |
| Bỏ từng scope ở màn hình đồng ý | **Không** | chỉ Allow cả gói hoặc từ chối |
| "Được tạo hóa đơn nhưng không được void" | **Không** | Xero không có mức mịn như vậy; scope chỉ tới mức loại dữ liệu + đọc/ghi. Giới hạn kiểu này nằm trong code của ta |
| Hóa đơn phải có người duyệt | Gián tiếp | app gửi `DRAFT`, kế toán bấm Approve trên Xero (`08`, mục 11.2) |

Kết luận để nói: phía Xero có các chốt **thô** (tổ chức nào, nối hay gỡ, khóa kỳ); chốt **mịn** duy nhất cho từng app là scope; mịn hơn nữa là việc của code ta.

Cả mục này là kiến thức chung về Xero, **từ trí nhớ**, chưa đối chiếu trên màn hình hay tài liệu: tên menu, vai trò nào được nối app, và việc lock dates áp dụng cho API. Về scope, mới thấy một nửa: token của ta gọi được những gì đã xin; chưa thử một lời gọi ngoài scope để thấy Xero từ chối.

## Luồng Connect: chín bước

```text
        TRÌNH DUYỆT                      FRAPPE                                  XERO
 ①  bấm "Connect to Xero" ───────────►  tạo state, lưu vào Token Cache
 ②  ◄── địa chỉ authorize ────────────
 ③  ───────────────────────────────────────────────────────────────────────►  login.xero.com (đăng nhập, chọn tổ chức, Allow)
 ④  ◄── 302 về redirect_uri?code=…&state=… ─────────────────────────────────
 ⑤  ───────────────────────────────►  so state
 ⑥                                     POST code + client_id + secret ──────►  identity.xero.com/connect/token
 ⑦                                     ◄── access_token, refresh_token, expires_in
                                       lưu vào Token Cache (mã hóa), commit
 ⑧  ◄── 302 về form Connected App ───
 ⑨                                     (job) GET /connections ──────────────►  api.xero.com
                                       ◄── tenantId, tenantName → Lab Xero Settings
```

### Bước ①–②: Frappe tạo địa chỉ authorize

| | |
|---|---|
| Ai gọi ai | trình duyệt → Frappe (nút trên form Connected App) |
| Vào | tên Connected App, user đang đăng nhập |
| Ra | một URL để trình duyệt đi tới |
| Lưu | `state` (chuỗi ngẫu nhiên) vào dòng Token Cache tên `xero-Administrator` |
| Để làm gì | `state` giúp Frappe nhận ra đúng lần quay về của chính lần bấm này |

```python
# frappe/.../connected_app.py:101-116  (code của Frappe)
oauth = self.get_oauth2_session(user, init=True)
query_params = self.get_query_params()
authorization_url, state = oauth.authorization_url(self.authorization_uri, **query_params)
token_cache = self.get_token_cache(user)

if not token_cache:
	token_cache = frappe.new_doc("Token Cache")
	token_cache.user = user
	token_cache.connected_app = self.name

token_cache.success_uri = success_uri
token_cache.state = state
token_cache.save(ignore_permissions=True)
frappe.db.commit()

return authorization_url
```

URL trình duyệt đi tới (không có bí mật nào trong đó):

```text
https://login.xero.com/identity/connect/authorize
   ?response_type=code
   &client_id=<CLIENT_ID>
   &redirect_uri=http://localhost:8000/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/xero
   &scope=offline_access accounting.invoices accounting.contacts accounting.settings.read
   &state=<chuỗi ngẫu nhiên>
```

#### URL này được dựng thế nào, và đi về bằng đường nào

Frappe không tự nối chuỗi. Nó tạo một `OAuth2Session` (thư viện `requests_oauthlib`) từ các field của Connected App, rồi thư viện ghép URL:

```python
# frappe/.../connected_app.py:83-91  (code của Frappe, trong get_oauth2_session)
return OAuth2Session(
	client_id=self.client_id,
	token=token,
	token_updater=token_updater,
	auto_refresh_url=self.token_uri,
	auto_refresh_kwargs=auto_refresh_kwargs,
	redirect_uri=self.redirect_uri,
	scope=self.get_scopes(),
)
```

| Phần của URL | Giá trị | Lấy từ đâu | Ai đặt giá trị đó |
|---|---|---|---|
| địa chỉ gốc | `https://login.xero.com/identity/connect/authorize` | `Connected App.authorization_uri` | code của ta, `setup/xero_connection.py:61` |
| `response_type` | `code` | thư viện tự thêm: "tôi muốn nhận một `code`" | chuẩn OAuth (authorization code) |
| `client_id` | `<CLIENT_ID>` | `Connected App.client_id` | site config `xero_client_id` → `setup/xero_connection.py` |
| `redirect_uri` | `http://localhost:8000/api/method/…callback/xero` | `Connected App.redirect_uri` | Frappe tính lúc lưu: URL của site (`host_name`) + đường dẫn callback + tên bản ghi |
| `scope` | bốn scope, cách nhau bằng dấu cách | bảng con `scopes` (`get_scopes()`, dòng 140-141) | hằng `SCOPES` trong `setup/xero_connection.py` |
| `state` | chuỗi ngẫu nhiên | thư viện sinh ra ở mỗi lần bấm | Frappe lưu nó vào Token Cache ngay sau đó |
| tham số thêm | (không có) | bảng con `query_parameters` (`get_query_params()`, dòng 143-144) | code setup của ta không thêm dòng nào |

Không có `client_secret` trong URL: nó chỉ được gửi ở bước ⑥, từ server tới server.

Đường đi của URL và của câu trả lời:

```text
   TRÌNH DUYỆT                        FRAPPE                                XERO
   (tab localhost:8000)               (server, localhost:8000)              (cloud)
        │                                  │                                  │
  ①     │── bấm "Connect to Xero" ────────►│                                  │
        │   mang: cookie sid               │ dựng URL, sinh state,            │
        │                                  │ lưu state vào Token Cache        │
  ②     │◄── JSON: URL authorize ──────────│                                  │
        │                                  │                                  │
  ③     │── GET https://login.xero.com/identity/connect/authorize ───────────►│ login.xero.com
        │   mang: client_id, redirect_uri, scope, state                       │
        │   (đăng nhập Xero, chọn tổ chức, Allow)                             │
  ④     │◄── 302  Location: <redirect_uri>?code=…&state=… ────────────────────│
        │                                  │                                  │
  ⑤     │── GET http://localhost:8000/api/method/…callback/xero ─►│           │
        │   mang: code, state, cookie sid  │ so state với Token Cache         │
        │                                  │                                  │
  ⑥     │                                  │── POST https://identity.xero.com/connect/token ─►│ identity.xero.com
        │                                  │   mang: code, client_id, client_secret, redirect_uri
  ⑦     │                                  │◄── JSON: access_token, refresh_token, expires_in ─│
        │                                  │ lưu vào Token Cache (mã hóa)     │
  ⑧     │◄── 302 về form Connected App ────│                                  │
```

| # | Từ | **Tới (đích)** | Mang theo | Ai thấy được |
|---|---|---|---|---|
| ① | trình duyệt | Frappe `localhost:8000` | cookie `sid` | — |
| ② | Frappe | trình duyệt | URL authorize | trình duyệt |
| ③ | trình duyệt | **`login.xero.com`** | `client_id`, `redirect_uri`, `scope`, `state` | trình duyệt, Xero |
| ④ | Xero | trình duyệt | `code`, `state` (trong địa chỉ chuyển hướng) | trình duyệt |
| ⑤ | trình duyệt | **Frappe `localhost:8000/…callback/xero`** | `code`, `state`, cookie `sid` | trình duyệt, Frappe |
| ⑥ | Frappe | **`identity.xero.com/connect/token`** | `code`, `client_id`, **`client_secret`**, `redirect_uri` | chỉ hai server |
| ⑦ | Xero | Frappe | **`access_token`, `refresh_token`**, `expires_in` | chỉ hai server |
| ⑧ | Frappe | trình duyệt | địa chỉ form Connected App | trình duyệt |

`redirect_uri` có hai vai: ở ③ nó là **dữ liệu** gửi cho Xero ("xong thì trả người dùng về đây"); ở ⑤ nó là **đích** thật mà trình duyệt mở. Không mũi tên nào đi từ Xero vào Frappe: ⑦ là câu trả lời cho lời gọi ⑥ do Frappe mở.

Ba điều rút ra từ hình:
- Xero **không bao giờ gọi vào máy bạn**. Ở bước ④ nó trả lời trình duyệt; ở bước ⑤ chính trình duyệt gọi `localhost`.
- Thứ đi qua trình duyệt chỉ là `code` (dùng một lần, sống vài phút) và `state`. **Token không bao giờ tới trình duyệt.**
- `redirect_uri` phải trùng từng ký tự với cái đã đăng ký ở Xero; nó được gửi ở bước ③ và gửi lại ở bước ⑥ để Xero đối chiếu.

Chưa đọc code bên trong thư viện `requests_oauthlib` (thư mục `env/` nằm ngoài phạm vi được đọc); tên các tham số là theo chuẩn OAuth 2.0, và URL thật chưa được chụp lại. Frappe không gửi PKCE trong luồng này (không thấy trong code đã đọc).

### Bước ③: người dùng đồng ý tại Xero

| | |
|---|---|
| Ai gọi ai | trình duyệt → `login.xero.com` |
| Vào | email + mật khẩu Xero, chọn **Demo Company (Global)**, bấm **Allow access** |
| Ra | Xero ghi nhận một *connection* giữa app và tổ chức đó |
| Frappe thấy gì | không gì cả; mật khẩu không bao giờ tới Frappe |

### Bước ④–⑤: Xero trả trình duyệt về, Frappe kiểm `state`

| | |
|---|---|
| Ai gọi ai | Xero **trả lời trình duyệt** bằng một lệnh chuyển hướng; chính trình duyệt mở `localhost`. Xero không gọi vào máy bạn |
| Vào | `GET <redirect_uri>?code=<mã dùng một lần>&state=<chuỗi>` |
| Kiểm | user phải đang đăng nhập Frappe (không thì bị đưa qua `/login`); `state` phải trùng cái đã lưu |
| Lỗi đã quan sát | "Invalid token state! Check if the token has been created by the OAuth user." khi bấm Connect hai lần hoặc quay về bằng một lượt cũ |

```python
# frappe/.../connected_app.py:206-219  (code của Frappe)
if frappe.session.user == "Guest":
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = "/login?" + urlencode({"redirect-to": frappe.request.url})
	return

path = frappe.request.path[1:].split("/")
if len(path) != 4 or not path[3]:
	frappe.throw(_("Invalid Parameters."))

connected_app = frappe.get_doc("Connected App", path[3])
token_cache = frappe.get_doc("Token Cache", connected_app.name + "-" + frappe.session.user)

if state != token_cache.state:
	frappe.throw(_("Invalid token state! Check if the token has been created by the OAuth user."))
```

Vì sao phải làm cả lượt từ một tab mở bằng `http://localhost:8000`: cookie đăng nhập gắn với tên host. Bắt đầu ở `lab.localhost` thì khi quay về `localhost` bạn là Guest.

### Bước ⑥–⑦: đổi `code` lấy token

| | |
|---|---|
| Ai gọi ai | Frappe (server) → `https://identity.xero.com/connect/token` |
| Vào | `grant_type=authorization_code`, `code`, `redirect_uri`, `client_id`, `client_secret` (gửi trong body) |
| Ra | `access_token`, `refresh_token`, `expires_in` (= 1800 giây, đã quan sát), `token_type` (Bearer), `scope` |
| Lưu | dòng Token Cache `xero-Administrator`; hai token là field Password (Frappe mã hóa) |
| Để làm gì | `code` đi qua trình duyệt nên dễ lộ; token chỉ đi trên đường server với server, và cần `client_secret` mới đổi được |

```python
# frappe/.../connected_app.py:221-233  (code của Frappe)
oauth_session = connected_app.get_oauth2_session(init=True)
query_params = connected_app.get_query_params()
token = oauth_session.fetch_token(
	connected_app.token_uri,
	code=code,
	client_secret=connected_app.get_password("client_secret"),
	include_client_id=True,
	**query_params,
)
token_cache.update_data(token)

frappe.local.response["type"] = "redirect"
frappe.local.response["location"] = token_cache.get("success_uri") or connected_app.get_url()
```

```python
# frappe/integrations/doctype/token_cache/token_cache.py:53-72  (code của Frappe)
self.token_type = token_type
self.access_token = cstr(data.get("access_token", ""))
self.expires_in = cint(data.get("expires_in", 0))

if "refresh_token" in data:
	self.refresh_token = cstr(data.get("refresh_token"))
...
self.state = None
self.save(ignore_permissions=True)
frappe.db.commit()
return self
```

Lưu ý dòng `frappe.db.commit()`: việc lưu token **tự commit**. Đây là lý do mọi job của ta lấy token trước khi ghi bất cứ thứ gì (`06`).

### Bước ⑧: quay về Frappe

Trình duyệt được đưa về form Connected App. Không có thông báo "thành công"; cách kiểm là hỏi `has_token` (trả `true` hoặc `false`).

### Bước ⑨: hỏi tổ chức nào đã được nối (code của ta)

OAuth trả lời "app này được phép". Nó không nói "vào tổ chức nào". Xero thêm khái niệm **tenant**: mỗi lời gọi API phải kèm header `xero-tenant-id`. Frappe không biết khái niệm này, nên ta phải tự hỏi và tự lưu.

| | |
|---|---|
| Ai gọi ai | job của ta → `GET https://api.xero.com/connections` |
| Vào | header `Authorization: Bearer <access_token>`; **không** có `xero-tenant-id` |
| Ra | một mảng; mỗi phần tử có `tenantId`, `tenantName`, `tenantType` |
| Lưu | `Lab Xero Settings.tenant_id`, `.tenant_name` (đã quan sát: "Demo Company (Global)") |
| Khi nào chạy | con người xếp job `discover_tenant` một lần sau khi Connect |

```python
# tasks/xero_sync.py:16-39
def discover_tenant(tenant_id: str | None = None) -> None:
	"""Store the sole connected organisation, or an explicitly selected tenant."""
	frappe.only_for("System Manager")
	settings = frappe.get_doc("Lab Xero Settings", check_permission="write")
	try:
		# Token refresh can commit; do all local writes after the HTTP call.
		connections = get_client(require_tenant=False).get_connections()
		organisations = [row for row in connections if row.get("tenantType") == "ORGANISATION"]
		...
		if len(matches) != 1:
			frappe.throw(_("Expected one connected Xero organisation. If several are connected, pass its tenant_id explicitly."))
		connection = matches[0]
		...
		settings.tenant_id = connection["tenantId"]
		settings.tenant_name = connection["tenantName"]
		settings.save()
```

Nếu nối nhiều tổ chức, job từ chối đoán và đòi truyền `tenant_id` cụ thể.

## Dùng token: mỗi lần job gọi Xero

```python
# integrations/xero/client.py:15-30
def get_client(*, require_tenant: bool = True) -> "XeroClient":
	"""Obtain before taking outbox locks: Frappe's token refresh can commit."""
	settings = frappe.get_doc("Lab Xero Settings")
	if not settings.connected_app or not settings.connected_user:
		raise XeroAuthLost("Xero connection settings are incomplete; ask a System Manager to connect Xero.")
	if require_tenant and not settings.tenant_id:
		raise XeroAuthLost("Xero tenant is not configured; run the tenant discovery job first.")
	app = frappe.get_doc("Connected App", settings.connected_app)
	token = app.get_active_token(user=settings.connected_user)
	if not token:
		raise XeroAuthLost("Xero authorization is unavailable; reconnect Xero.")
	try:
		headers = token.get_auth_header()
	except frappe.DoesNotExistError:
		raise XeroAuthLost("Xero access token is missing; reconnect Xero.") from None
	return XeroClient(settings.tenant_id, headers)
```

Ba ý quan trọng:
1. **Token của ai?** Luôn của `settings.connected_user` (người đã bấm Connect), không phải của người submit đơn. Frappe lưu token theo từng user (`xero-<user>`); nếu lấy theo user hiện tại thì người bán hàng sẽ "không có token".
2. **Header gửi đi** là `Authorization: Bearer <access_token>` cộng `xero-tenant-id: <tenant_id>`.
3. **Mọi trục trặc về quyền thành một loại lỗi**, `XeroAuthLost`, với câu nói rõ phải làm gì.

## Làm mới token (refresh): không cần người

Access token sống 30 phút. Khi nó hết hạn, Frappe dùng refresh token để xin cặp mới.

| | |
|---|---|
| Ai gọi ai | Frappe → `https://identity.xero.com/connect/token` |
| Vào (đã quan sát trong log lỗi) | `grant_type=refresh_token`, `refresh_token`, `client_id`, `client_secret`, `scope`, và một `redirect_uri` thừa |
| Ra | `access_token` mới **và** `refresh_token` mới; cái cũ hết hiệu lực |
| Lưu | ghi đè dòng Token Cache, commit |
| Khi nào | khi `get_active_token` thấy token đã hết hạn |

```python
# frappe/.../connected_app.py:146-167  (code của Frappe)
def get_active_token(self, user=None):
	user = user or frappe.session.user
	token_cache = self.get_token_cache(user)
	if token_cache and token_cache.is_expired():
		try:
			with filelock(f"token_cache_{token_cache.name}"):
				# Another worker may have refreshed while we waited for the lock.
				token_cache.reload()
				if not token_cache.is_expired():
					return token_cache

				oauth_session = self.get_oauth2_session(user)
				token = oauth_session.refresh_token(
					body=f"redirect_uri={self.redirect_uri}",
					token_url=self.token_uri,
				)
				token_cache.update_data(token)
		except Exception:
			self.log_error("Token Refresh Error")
			return None

	return token_cache
```

- **Khóa** (`filelock`): hai worker không refresh cùng lúc. Nếu cùng lúc, một bên sẽ cầm refresh token đã chết.
- **Hỏng thì trả `None`**, không ném lỗi; `get_client` của ta biến `None` thành `XeroAuthLost` "reconnect Xero".
- **Hết hạn được tính thế nào**: thời điểm sửa cuối của dòng Token Cache cộng `expires_in`, so với bây giờ.

```python
# frappe/.../token_cache.py:74-82  (code của Frappe)
def get_expires_in(self):
	system_timezone = ZoneInfo(get_system_timezone())
	modified: datetime.datetime = get_datetime(self.modified).replace(tzinfo=system_timezone)
	expiry_utc = modified.astimezone(datetime.UTC) + datetime.timedelta(seconds=self.expires_in)
	now_utc = datetime.datetime.now(datetime.UTC)
	return cint((expiry_utc - now_utc).total_seconds())

def is_expired(self):
	return self.get_expires_in() < 0
```

Đã quan sát: dòng Token Cache được cập nhật lúc 14:48:02 (đúng nhịp scheduler, không ai bấm gì), và không có "Token Refresh Error" mới. Vậy refresh với Xero chạy được, kể cả với tham số `redirect_uri` thừa.

Điểm yếu cần biết: vì hạn tính từ thời điểm sửa cuối, bất cứ thứ gì lưu lại dòng Token Cache (ví dụ bấm Connect rồi bỏ dở, vì bước ① lưu `state`) làm token trông "mới" trong khi nó đã hết hạn. Khi đó lời gọi kế tiếp bị Xero từ chối và đơn báo "Xero authorization was refused". Cách chữa: Connect lại cho xong, rồi Retry.

## Hạn của mọi thứ

| Thứ | Sống bao lâu | Hết thì |
|---|---|---|
| `code` | vài phút, dùng một lần | Connect lại |
| `state` | tới khi callback xong | Connect lại |
| access token | 30 phút (`expires_in` = 1800, đã quan sát) | tự refresh |
| refresh token | 60 ngày không dùng (từ tài liệu bên thứ ba) | Connect lại bằng tay |
| connection tới Demo Company | tới khi Demo Company reset (khoảng 28 ngày) hoặc bị gỡ | Connect lại, chạy lại `discover_tenant` |
| `client_secret` | tới khi bạn tạo cái mới | đặt lại vào site config, migrate, Connect lại |

## Khi hỏng: thấy gì, nghĩa là gì, làm gì

| Thấy | Ở đâu | Nghĩa | Làm |
|---|---|---|---|
| "Must use https (except localhost…)" | form tạo app của Xero | Redirect URI không phải `https` hay `localhost` | dùng `http://localhost:8000/…` |
| "Invalid token state!" | Frappe, sau khi quay về | callback không khớp lượt Connect đang chờ | bấm Connect lại, làm một mạch |
| bị đưa tới `/login` | Frappe | mất session trong lúc ở Xero (khác tên host) | làm cả lượt từ tab `localhost:8000` |
| "Refresh token is missing" (trong Error Log) | job | Token Cache không có token (Connect chưa từng xong) | Connect lại |
| "Xero authorization is unavailable; reconnect Xero." | trên đơn, hoặc Error Log | không có token, hoặc refresh hỏng | Connect lại |
| "Xero authorization was refused; check access and reconnect Xero." | trên đơn | Xero trả 401 hoặc 403 | Connect lại, rồi Retry |
| "Xero tenant is not configured; run the tenant discovery job first." | trên đơn | chưa có `tenant_id` | chạy job `discover_tenant` |

## Luật an toàn

- `client_secret` và token không bao giờ nằm trong repo, tài liệu, chat hay log. Đã có lần Error Log của Frappe in cả secret (traceback kèm biến); vì vậy **không dán nguyên văn Error Log ra ngoài** mà chưa che.
- Lộ secret thì tạo cái mới bên Xero, đặt lại vào site config, migrate, Connect lại.
- Chỉ xin đúng bốn scope đang dùng.
