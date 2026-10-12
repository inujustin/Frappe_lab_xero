# OAuth 2.0 trong tích hợp Xero: toàn bộ cơ chế

Kiến thức nền cho gói Xero. `../02-oauth-va-ket-noi.md` là bản tóm tắt để làm việc; file này là bản đầy đủ để **hiểu**. Nguồn tương ứng bên kho chung: `docs/knowledge/10` (mục OAuth, viết từ trí nhớ) và `docs/knowledge/11`; khi khác nhau, file này mới hơn.

Nhãn: xem `../00-README.md`. Đã đọc hôm nay, cả file: `frappe/integrations/doctype/connected_app/connected_app.py` và `…/token_cache/token_cache.py` (đường dẫn từ `frappe-bench/apps/frappe/`). Phần giao thức OAuth là [G] (chuẩn RFC 6749, từ trí nhớ); phần Xero mang nhãn riêng từng dòng.

## Trả lời trong năm dòng

1. OAuth 2.0 giải một bài toán: cho **một phần mềm** (Frappe) quyền làm việc trên **dữ liệu của một người ở nơi khác** (sổ sách bên Xero) mà **không đưa mật khẩu** cho phần mềm đó.
2. Người chủ dữ liệu đăng nhập **tại Xero**, bấm đồng ý; Xero đưa cho Frappe một **token** có phạm vi (scope) và có hạn.
3. Có hai token: **access token** ngắn hạn để gọi API, **refresh token** dài hạn để xin access token mới mà không cần người.
4. OAuth trả lời "app này được làm gì"; nó **không** nói "organisation nào". Xero thêm khái niệm **connection / tenant** cho việc đó.
5. Trong Frappe, toàn bộ điệu nhảy đã có sẵn ở DocType `Connected App` và `Token Cache`; ta chỉ cấu hình và lo bốn chỗ nó không lo.

## Bài toán, bằng một ví dụ đời thường

```text
KHÔNG CÓ OAUTH                                  CÓ OAUTH
 bạn đưa mật khẩu Xero cho Frappe                bạn đưa Frappe một "thẻ ra vào":
 → Frappe làm được MỌI THỨ bạn làm được            chỉ mở được vài cửa (scope)
 → muốn thu hồi phải đổi mật khẩu                  hết hạn sau 30 phút, gia hạn được
 → mật khẩu nằm trong database của Frappe          thu hồi được bất cứ lúc nào, không đổi mật khẩu
                                                   Frappe không bao giờ thấy mật khẩu
```

## Bốn vai, áp vào trường hợp của ta

| Vai trong OAuth | Là ai ở đây | Giữ gì |
|---|---|---|
| **Resource owner** (chủ dữ liệu) | admin hoặc kế toán có login Xero và có quyền trên organisation | mật khẩu Xero của họ |
| **Client** (phần mềm xin quyền) | app của ta: Frappe + `lab_core`, đã đăng ký tại `developer.xero.com` | `client_id`, `client_secret` |
| **Authorization server** (nơi cấp quyền) | Xero identity: `login.xero.com`, `identity.xero.com` | biết ai đã đồng ý cho app nào, scope gì |
| **Resource server** (nơi có dữ liệu) | `api.xero.com` | invoice, contact, credit note… |

Người dùng thường của Frappe (người bán hàng) **không có vai nào** trong bảng này. Họ không cần tài khoản Xero.

## Từ vựng

| Từ | Nghĩa | Bí mật? |
|---|---|---|
| `client_id` | tên định danh của app tại Xero | không |
| `client_secret` | "mật khẩu" của app; chứng minh lời gọi tới từ đúng app | **có** |
| `redirect_uri` | địa chỉ Xero bảo trình duyệt quay về sau khi đồng ý; phải khớp từng ký tự với cái đã đăng ký | không |
| `scope` | danh sách quyền xin, cách nhau bằng dấu cách | không |
| `state` | chuỗi ngẫu nhiên Frappe tạo cho mỗi lần Connect, để nhận ra đúng lần quay về của mình | ngắn hạn |
| **authorization code** | mã dùng **một lần**, sống vài phút, đổi lấy token | ngắn hạn |
| **access token** | "thẻ ra vào"; gửi kèm mỗi lời gọi API | **có** |
| **refresh token** | "phiếu gia hạn"; đổi lấy cặp token mới | **có, quan trọng nhất** |
| ID token | cho biết người đăng nhập là ai (chỉ khi xin scope `openid`); ta không cần | có |
| consent | hành động bấm "Allow access" của chủ dữ liệu | |
| grant type | kiểu xin token: authorization code, refresh token, client credentials… | |

## Luồng authorization code, từng bước, với HTTP thật

```text
        TRÌNH DUYỆT của admin              FRAPPE (máy bạn)                     XERO
 ①  bấm Connect ───────────────────────►  tạo state, lưu lại
 ②  ◄── 302 tới authorize URL ──────────
 ③  ─────────────────────────────────────────────────────────────────────────► login.xero.com
        đăng nhập, chọn organisation, bấm Allow
 ④  ◄── 302 tới redirect_uri?code=…&state=… ──────────────────────────────────
 ⑤  ───────────────────────────────────►  so state
 ⑥                                        POST code + client_id + secret ────► identity.xero.com/connect/token
 ⑦                                        ◄── access_token, refresh_token, expires_in
                                          lưu (mã hóa)
 ⑧                                        GET /connections ──────────────────► api.xero.com
                                          ◄── tenantId
 ⑨  ◄── 302 về trang thành công ────────
```

**Bước ②–③: authorize URL** (trình duyệt đi tới; không có bí mật nào trong đó):

```text
https://login.xero.com/identity/connect/authorize
   ?response_type=code
   &client_id=<client_id>
   &redirect_uri=<đúng chuỗi đã đăng ký, đã URL-encode>
   &scope=offline_access accounting.invoices accounting.contacts accounting.settings.read
   &state=<chuỗi ngẫu nhiên>
```

**Bước ④: Xero trả trình duyệt về**: `GET <redirect_uri>?code=<mã một lần>&state=<chuỗi đó>`. Đây là Xero **trả lời trình duyệt**, không phải Xero gọi vào máy bạn (`../02`, "Ai mở kết nối tới ai").

**Bước ⑥: đổi code lấy token** (Frappe gọi ra; đây là lúc `client_secret` được dùng):

```text
POST https://identity.xero.com/connect/token
   grant_type=authorization_code
   code=<mã>
   redirect_uri=<cùng chuỗi>
   + chứng minh là app: client_id và client_secret
       (Xero mô tả cách gửi bằng header Authorization: Basic base64(id:secret) [G];
        Frappe gửi trong body — xem "Chưa biết")
```

**Bước ⑦: câu trả lời**:

```json
{ "access_token": "eyJ…",  "token_type": "Bearer", "expires_in": 1800,
  "refresh_token": "…",    "scope": "offline_access accounting.invoices …" }
```
`expires_in` 1800 giây = 30 phút [3]. Access token của Xero là một JWT (chuỗi có chữ ký, chứa hạn và scope) [G]; ta không cần giải mã nó.

**Bước ⑧** không thuộc OAuth chuẩn; xem mục "Tenant" bên dưới.

### Vì sao luồng phải vòng vèo như vậy

| Chi tiết | Nó chặn điều gì |
|---|---|
| Đăng nhập xảy ra ở trang của **Xero** | Frappe không bao giờ chạm vào mật khẩu |
| Trả về **code** trước, token sau | code đi qua trình duyệt (thanh địa chỉ, lịch sử: nơi dễ lộ); token chỉ đi trên đường server-với-server. Kẻ nhặt được code vẫn thiếu `client_secret` |
| `client_secret` ở bước đổi | chỉ đúng app mới đổi được code |
| `redirect_uri` phải khớp chính xác | kẻ xấu không thể bảo Xero gửi code tới địa chỉ của hắn |
| `state` | kẻ xấu không thể dụ trình duyệt của admin "hoàn tất" một lần Connect do hắn bắt đầu (nối Frappe vào organisation của hắn) |
| code dùng một lần, sống vài phút | nhặt lại code cũ là vô dụng |
| scope | app chỉ có đúng các quyền đã xin; lộ token cũng không vượt được |

## Hai token và vòng đời của chúng

```text
Connect ──► access #1 (30 phút) ──hết hạn──► dùng refresh #1 ──► access #2 + refresh #2   (refresh #1 CHẾT)
                                              ──hết hạn──► dùng refresh #2 ──► access #3 + refresh #3 …
            refresh token không được dùng trong 60 ngày ──► chết ──► phải Connect lại bằng tay
```

**Gọi API**: mọi request kèm `Authorization: Bearer <access_token>`.

**Refresh** (không cần người, không cần trình duyệt):

```text
POST https://identity.xero.com/connect/token
   grant_type=refresh_token
   refresh_token=<cái đang giữ>
   + client_id và client_secret
→ trả về access_token MỚI và refresh_token MỚI
```

| Luật | Vì sao | Nếu sai |
|---|---|---|
| Xin scope `offline_access` | không có nó thì không được cấp refresh token [G] | 30 phút sau là hết, phải Connect lại |
| **Lưu refresh token mới ngay lập tức** | Xero xoay vòng: cái cũ bị vô hiệu khi cái mới được cấp [3] | mất cái mới = connection chết |
| **Mỗi lúc chỉ một tiến trình refresh** | hai worker cùng refresh: một cái thắng, cái kia cầm token chết | `invalid_grant`, connection chết |
| Còn một đường lui | Xero cho thử lại bằng refresh token cũ trong 30 phút nếu câu trả lời thất lạc [3] | |
| Gọi Xero ít nhất một lần mỗi 60 ngày | refresh token không dùng 60 ngày thì hết hạn [3] | phải Connect lại |

Access token **không thu hồi được** trước hạn theo cách thông thường; đó là lý do nó chỉ sống 30 phút. Refresh token thì thu hồi được: người dùng gỡ app trong Xero, hoặc app gọi endpoint thu hồi.

## Tenant và connection: phần Xero thêm vào OAuth

Một login Xero có thể vào nhiều organisation. Lúc đồng ý ở bước ③, người dùng **chọn organisation** để nối. Kết quả là một **connection** giữa app và organisation đó.

```text
GET https://api.xero.com/connections        Authorization: Bearer <access_token>
→ [ { "id": "<connection id>", "tenantId": "<GUID>", "tenantType": "ORGANISATION", "tenantName": "Demo Company (…)" } ]
```

- Token nói "app này được phép"; header **`xero-tenant-id: <tenantId>`** trên mỗi lời gọi nói "vào organisation nào". Thiếu header: bị từ chối.
- Một token có thể mở nhiều tenant (nếu người đó nối nhiều organisation). Với ta: một organisation, lưu một `tenant_id`.
- Gỡ một connection: `DELETE /connections/{id}`, hoặc người dùng gỡ trong Xero (Settings → Connected apps). Sau đó lời gọi vào tenant ấy bị `403`.
- Bậc Starter cho tối đa 5 connection [X].
- Demo Company reset (28 ngày) làm mất connection [G]: phải Connect lại và `tenantId` có thể đổi → sau mỗi lần Connect, đọc lại `/connections`.

## Ba kiểu xin token của Xero

| Grant type | Có người bấm đồng ý? | Dùng khi | Ta |
|---|---|---|---|
| **Authorization code** + client secret | có, một lần | web app có server giữ được secret | **dùng cái này** |
| Authorization code + **PKCE** | có | app không giữ được secret (mobile, desktop); thay secret bằng một cặp mã tạo tại chỗ | không |
| **Client credentials** (Xero gọi là Custom connection) | không; app tự xin token bằng id + secret | tích hợp nội bộ, đúng một organisation | không: trả phí [G], chỉ ở AU/NZ/UK/US [3] |

## Frappe làm việc này ở đâu

Frappe có hai mảng OAuth, **đừng lẫn**: nó làm OAuth **server** (người khác đăng nhập vào Frappe: `frappe/oauth.py`) và OAuth **client** (Frappe đăng nhập vào nơi khác: `Connected App`). Xero cần mảng thứ hai.

| Bước của luồng | Code Frappe [S] |
|---|---|
| Redirect URI được tính lúc lưu form: `<URL site>/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<tên app>` | `connected_app.py:60-65` |
| ① tạo authorize URL và `state` | `initiate_web_application_flow`, `:94-116`; URL ở `:103` |
| lưu `state` vào dòng Token Cache tên `"<app>-<user>"`, rồi commit | `:104-114`; tên dòng ở `:133` |
| ④ nhận callback: GET, cho Guest nhưng Guest bị đưa qua `/login` trước | `:197-209` |
| ⑤ so `state`; lệch thì throw | `:218-219` |
| ⑥ đổi code lấy token, gửi kèm client secret, `include_client_id=True` | `:223-229` |
| ⑦ lưu token | `token_cache.update_data`, `token_cache.py:40-72` |
| access token và refresh token là field **Password** (Frappe mã hóa khi lưu) | `token_cache.py:22, :26` |
| xóa `state` sau khi dùng; tự `commit` | `token_cache.py:69-71` |
| ⑨ đưa trình duyệt về `success_uri` hoặc form Connected App | `connected_app.py:232-233` |
| token hết hạn chưa: `modified + expires_in` so với bây giờ (UTC) | `token_cache.py:74-82` |
| lấy token còn sống; hết hạn thì refresh **dưới một file lock**, kiểm tra lại sau khi có lock | `get_active_token`, `connected_app.py:146-167` |
| refresh hỏng: ghi Error Log, **trả về `None`** (không raise) | `:163-165` |
| dựng header `Authorization: Bearer …` | `token_cache.py:35-38` |
| "đã nối chưa?" | `has_token`, `connected_app.py:237-240` |
| client credentials (cho Custom connection, nếu sau này dùng) | `get_backend_app_token`, `:169-194` |

Ba chi tiết đọc ra từ code, đáng biết trước khi viết job:

- **Không có biên an toàn khi kiểm tra hết hạn.** `is_expired()` chỉ đúng khi thời gian còn lại nhỏ hơn 0 (`token_cache.py:81-82`). Token còn 2 giây vẫn được coi là sống, và có thể chết giữa lời gọi. Client của ta phải coi `401` là "refresh một lần rồi thử lại".
- **Đồng hồ hết hạn tính từ `modified` của dòng Token Cache** (`:76-77`). Bất cứ thứ gì lưu lại dòng đó (kể cả bấm Connect lần nữa, vì nó lưu `state`: `connected_app.py:111-113`) làm token trông "mới" trong khi chưa hề được đổi. Lại một lý do để xử lý `401`.
- **Trong job chỉ dùng `get_active_token(user=…)`.** Đường còn lại, `get_oauth2_session(user)`, khi không có token sẽ cố bắt đầu một lần Connect và đặt một redirect vào response (`:118-129`), điều vô nghĩa trong job. Nó cũng tự refresh và tự commit giữa chừng (`:77`, `:86-88`).

## Bốn chỗ Frappe không lo giúp

Chi tiết ở `../02`; nhắc lại cho đủ:

1. **Tenant**: không có chỗ lưu `tenantId` → `Lab Xero Settings`.
2. **Token gắn với một user Frappe** (`"<app>-<user>"`): job phải truyền `user=settings.connected_user`, không dùng user của session.
3. **`None` nghĩa là "phải nối lại"**: biến nó thành `XeroAuthLost`, tạm dừng mọi sync.
4. **Tự commit khi lưu token**: lấy token trước lần ghi đầu tiên của job.

## Khi hỏng: thấy gì, nghĩa là gì, làm gì

| Thấy | Ở bước | Nghĩa | Làm |
|---|---|---|---|
| trang lỗi của Xero về redirect URI | ③ | chuỗi `redirect_uri` không khớp cái đã đăng ký (thừa dấu `/`, `http`/`https`, cổng, tên app) | copy lại đúng chuỗi từ form Connected App |
| `invalid_scope` / `unauthorized_client` | ③ | xin scope app không được dùng (ví dụ tên cũ `accounting.transactions` với app tạo sau 2026-03-02 [3]) | sửa danh sách scope |
| "Invalid token state!" trong Frappe | ⑤ | callback không thuộc lần Connect đang chờ: bấm Connect hai lần, hoặc đăng nhập Frappe bằng user khác giữa chừng | bấm Connect lại từ đầu |
| bị đưa tới `/login` của Frappe | ④ | trình duyệt mất session Frappe trong lúc ở Xero | đăng nhập; Frappe đưa về callback |
| `invalid_client` | ⑥ | sai `client_id`/`client_secret`, hoặc Xero không nhận cách gửi credential | kiểm tra secret; xem "Chưa biết" |
| `invalid_grant` khi đổi code | ⑥ | code đã dùng hoặc hết hạn, hoặc `redirect_uri` khác với lúc xin | Connect lại |
| `invalid_grant` khi refresh | refresh | refresh token đã bị xoay, hết 60 ngày, hoặc bị thu hồi | **Connect lại bằng tay**; không retry |
| `401` khi gọi API | gọi API | access token hết hạn, hoặc thiếu scope cho endpoint đó | refresh một lần rồi thử lại; vẫn `401` → Auth lost |
| `403` khi gọi API | gọi API | connection tới tenant đó đã bị gỡ, hoặc sai `xero-tenant-id` | Connect lại; đọc lại `/connections` |
| `get_active_token` trả `None` | trong job | chưa có token cho user đó, hoặc refresh hỏng | Auth lost: tạm dừng, báo người |

## Luật an toàn

- `client_secret`, access token, refresh token: chỉ trong field Password của Frappe; **không** trong repo, log, trace note, response, hay tài liệu (AGENTS.md B3, B6). Trong tài liệu dùng `<CLIENT_SECRET>`.
- Không bao giờ ghi header `Authorization` vào log hay journal.
- Xin ít scope nhất đủ dùng. Với đề bài: `offline_access`, `accounting.invoices`, `accounting.contacts`, `accounting.settings.read`.
- Lộ `client_secret`: tạo secret mới trong developer portal của Xero, sửa trong Desk.
- Ngừng dùng: gỡ connection (trong Xero hoặc `DELETE /connections/{id}`) và xóa dòng Token Cache.

## Chưa biết: chỉ một lần Connect thật mới trả lời

1. Xero có nhận `client_id`/`client_secret` **trong body** (cách Frappe gửi: `include_client_id=True`, `connected_app.py:227`) hay chỉ nhận HTTP Basic. Chuẩn OAuth yêu cầu server hỗ trợ Basic và cho phép hỗ trợ thêm body [G].
2. Lời gọi refresh của Frappe kèm một tham số thừa `redirect_uri` (`:159`); Xero bỏ qua hay từ chối.
3. Xero có nhận redirect URI `http://lab.localhost:8000/…` không (cho `http://localhost` khi phát triển, còn lại đòi `https` [G]).
4. File lock của Frappe (`:151`) chỉ bảo vệ các worker trên **cùng một máy**; đủ cho lab.

Nếu 1 hoặc 2 là "không": tự viết bước đổi và refresh token trong `integrations/xero/`, vẫn lưu vào Token Cache.

## Tự kiểm tra

1. Kể tên bốn vai của OAuth trong trường hợp của ta. Người bán hàng trong Frappe là vai nào?
2. Vì sao Xero trả về một `code` trước rồi mới cho đổi lấy token, thay vì trả token luôn?
3. `state` chặn kiểu tấn công nào?
4. Hai worker cùng refresh một lúc thì chuyện gì xảy ra, và Frappe chặn bằng gì?
5. Token đúng, vẫn bị từ chối khi gọi `/Invoices`. Hai nguyên nhân liên quan tới tenant và scope là gì?
6. Vì sao job phải gọi `get_active_token(user=…)` **trước** khi ghi gì vào database?
