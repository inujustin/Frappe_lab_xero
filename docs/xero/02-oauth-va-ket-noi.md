# 02. Kết nối: app, scope, token, tenant, và phần Frappe đã có sẵn

Nhãn độ tin cậy: xem `00-README.md`. Đây là bản tóm tắt để làm việc; bản đầy đủ để hiểu cơ chế OAuth (vì sao có code, state, hai token; từng request HTTP; bảng lỗi): `knowledge/oauth.md`.

## Trả lời trong năm dòng

1. Xero dùng **OAuth 2.0 authorization code flow** (luồng cấp quyền bằng mã): user đăng nhập ở Xero, đồng ý, ta nhận token. Ta không bao giờ thấy mật khẩu Xero.
2. Kết quả là ba thứ phải lưu: **access token** (30 phút), **refresh token** (60 ngày, dùng một lần), **tenant id** (organisation nào).
3. Frappe đã có OAuth client tổng quát: DocType **Connected App** + **Token Cache**. Không cần viết code OAuth.
4. Frappe **không** biết khái niệm tenant và không biết job nên dùng token của ai → hai chỗ ta phải tự lo.
5. Tên scope đã đổi cho app tạo từ 2026-03-02. Dùng tên mới.

## Luồng, một lần từ đầu tới cuối

```text
Bạn (trình duyệt)            Frappe (lab)                          Xero
     │  bấm "Connect"            │                                   │
     │──────────────────────────►│ dựng URL + state, lưu state       │
     │◄── redirect ──────────────│                                   │
     │──────────────────────────────────────────────────────────────►│ login.xero.com/identity/connect/authorize
     │        đăng nhập, CHỌN organisation (Demo Company), đồng ý     │
     │◄── redirect về redirect_uri?code=…&state=… ────────────────────│
     │──────────────────────────►│ so state                          │
     │                           │── POST code + client secret ─────►│ identity.xero.com/connect/token
     │                           │◄─ access_token + refresh_token ───│
     │                           │ lưu vào Token Cache (mã hóa)       │
     │                           │── GET /connections ──────────────►│ api.xero.com/connections     ← TA phải tự viết
     │                           │◄─ [{tenantId, tenantName}] ───────│
     │                           │ lưu tenant_id vào settings         │
   về sau, trong job:            │── API + Bearer + xero-tenant-id ─►│ api.xero.com/api.xro/2.0/…
   token hết hạn:                │── POST refresh_token ────────────►│ → cặp token MỚI, cái cũ chết
```

Các URL trên là [G] (ổn định nhiều năm; đối chiếu trang auth-flow của Xero khi tạo app).

### Ai mở kết nối tới ai: không cần deploy

Câu hỏi tự nhiên: "Xero không biết `localhost` của tôi, vậy phải deploy Docker lên internet?" **Không.** Trong luồng trên, server của Xero **không bao giờ** mở kết nối tới máy bạn. Mọi kết nối đều đi **từ phía bạn ra** Xero:

```text
MÁY CỦA BẠN                                                          INTERNET
┌───────────────────────────────────────────────┐
│ trình duyệt ──────────────────────────────────┼──► login.xero.com        (bạn đăng nhập, bấm đồng ý)
│     ▲   │                                     │◄── trả lời: "302, hãy đi tới http://lab.localhost:8000/…?code=…"
│     │   └─► http://lab.localhost:8000 ──┐     │        ↑ chỉ là một dòng chữ trong câu trả lời;
│     │        (TRÌNH DUYỆT tự đi, trên   │     │          Xero không hề gọi địa chỉ đó
│     │         chính máy này)            ▼     │
│  container frappe (Docker) ───────────────────┼──► identity.xero.com     (đổi code lấy token, refresh)
│  worker ──────────────────────────────────────┼──► api.xero.com          (tạo invoice…)
└───────────────────────────────────────────────┘
        ✘ không có mũi tên nào từ Xero đi VÀO máy bạn
```

- Mũi tên `◄── redirect về redirect_uri` trong hình lớn là Xero **trả lời trình duyệt** bằng một HTTP redirect. Chính trình duyệt của bạn, đang chạy trên máy bạn, mới mở `localhost`. Với Xero, redirect URI chỉ là một **chuỗi để so khớp** với chuỗi đã đăng ký trong app; nó không cần truy cập được từ internet.
- Bước đổi code lấy token và mọi lời gọi API là container `frappe` gọi **ra** qua HTTPS. Docker cho container ra internet theo mặc định; file compose của lab không tắt điều đó ([S] `docker/compose.yml`: không có `internal:` hay `network_mode`, cổng web publish ra `${WEB_PORT:-8000}` ở `:54-55`).
- Vậy tích hợp "dựa vào" cả hai theo nghĩa: **code chạy trên Docker của bạn**, **dữ liệu kế toán nằm ở Xero**; nhưng chiều kết nối luôn là bạn → Xero.

Chỉ có một tính năng mà Xero chủ động gọi vào ta: **webhook** (`03`). Cái đó mới cần URL HTTPS công khai (deploy hoặc tunnel). Demo không làm webhook, nên **không cần deploy, không cần tunnel, không tốn tiền**.

Điều kiện thật duy nhất: lúc đăng ký app, Xero phải **chấp nhận chuỗi** redirect URI. Đó là kiểm tra định dạng (cho `http://localhost…` khi phát triển, còn lại đòi `https` [G]), không phải kiểm tra truy cập được. Xem "Hai điều chưa biết" ở cuối file.

### Ai phải đăng nhập Xero: một người, một lần

Người dùng Frappe **không cần tài khoản Xero**. Token thuộc về *kết nối*, không thuộc về người submit chứng từ.

```text
MỘT LẦN (cài đặt)                                  HẰNG NGÀY (sử dụng)
 admin / kế toán bấm "Connect to Xero"              bất kỳ user Frappe nào, không có tài khoản Xero
 đăng nhập Xero, chọn organisation, đồng ý          submit Sales Order
        ▼                                                  ▼
 Frappe lưu token + tenant id                       job dùng kết nối ĐÃ LƯU (connected_user) → invoice sang Xero
```

Phải đăng nhập Xero lại chỉ khi kết nối chết: 60 ngày không gọi gì, ai đó gỡ connection bên Xero, Demo Company reset, hoặc ta xin thêm scope. Vẫn là admin đó, không phải mọi user. "Sign in with Xero" (dùng danh tính Xero để đăng nhập vào chính Frappe) là một tính năng khác, không thuộc tích hợp này.

**Lựa chọn cho demo (chốt 2026-10-12): chỉ kịch bản "không đăng nhập".** Demo cho thấy một user Frappe bình thường, không có tài khoản Xero, submit đơn và hóa đơn sang Xero. Lần Connect của admin được làm **trước buổi demo**, như một bước cài đặt (P0); nó không phải một cảnh của demo, nhưng không bỏ được: ở mức 0 đồng, Xero luôn đòi một người đồng ý một lần. Luồng hoàn toàn không có người đồng ý (Custom connection) có tồn tại nhưng trả phí và giới hạn vùng (bảng bên dưới).

Để sau demo: kịch bản "có đăng nhập", tức người dùng dùng tài khoản Xero của họ bên trong Frappe (đăng nhập Frappe bằng Xero, hoặc mỗi người một kết nối riêng).

## Ba loại app của Xero

| Loại | Flow | Khi nào | Ta? |
|---|---|---|---|
| **Web app** | authorization code + client secret | server giữ được secret | **Có** |
| Mobile / desktop | authorization code + PKCE (không secret) | app không giữ được secret | không |
| **Custom connection** | client credentials: máy với máy, một organisation, không có bước của user | tích hợp nội bộ của một công ty | hấp dẫn nhưng chỉ có ở AU/NZ/UK/US [3] và là tùy chọn trả phí [G] |

Ghi chú để sau: Frappe cũng làm được client credentials ([S] `frappe/integrations/doctype/connected_app/connected_app.py:169` `get_backend_app_token`), nên nếu dự án thật ở một trong bốn nước đó thì Custom connection bỏ được toàn bộ chuyện "user nào bấm Connect". Với demo: Web app.

## Scope: dùng tên mới

App tạo **từ 2026-03-02** không còn được dùng scope rộng `accounting.transactions`; app cũ có hạn tới tháng 9/2027 (devblog Xero ghi 2027-09-13) [3]. App của ta sẽ được tạo bây giờ, nên chỉ có tên mới:

| Scope | Cho phép (đọc + ghi; thêm `.read` nếu chỉ đọc) [3] | Demo cần? |
|---|---|---|
| `offline_access` | được cấp refresh token. Thiếu nó: 30 phút rồi hết. [G] | **có** |
| `accounting.invoices` | invoice, credit note, quote, purchase order, item | **có** |
| `accounting.contacts` | contact (không đổi tên) | **có** |
| `accounting.payments` | payment, batch payment, overpayment, prepayment | khi làm payment |
| `accounting.settings` | account, tax rate, currency, tracking (không đổi tên); `.read` là đủ để lấy `AccountCode`, `TaxType` | **có** (`.read`) |
| `accounting.banktransactions`, `accounting.manualjournals` | giao dịch ngân hàng, bút toán tay | không |
| `accounting.attachments` | tệp đính kèm | không |
| `openid profile email` | biết user Xero là ai [G] | không |

Gọi một endpoint mà thiếu scope tương ứng → bị từ chối với lỗi `insufficient_scope` [3]. Xin thêm scope sau này = user phải bấm Connect lại. Nên xin đủ ngay từ đầu, nhưng không xin thừa (nguyên tắc quyền tối thiểu).

## Token: ba luật sống còn

| Token | Sống | Hành vi |
|---|---|---|
| Access token | 30 phút [3] | gửi trong `Authorization: Bearer …` |
| Refresh token | 60 ngày không dùng thì chết [3] | **rotate (xoay vòng)**: mỗi lần đổi trả về cặp mới, cái cũ bị vô hiệu [3]; có khoảng ân hạn 30 phút để thử lại bằng cái cũ nếu câu trả lời thất lạc [3] |

1. **Lưu refresh token mới ngay.** Mất nó = connection chết, con người phải bấm Connect lại.
2. **Không hai worker refresh cùng lúc.** Một cái thắng, cái kia cầm token chết (`invalid_grant`). Cần lock; Frappe có ([S] `connected_app.py:151`).
3. **60 ngày không gọi gì = chết.** Hệ thống thật cần một job "giữ sống" định kỳ. Demo thì không tới mức đó, nhưng Demo Company reset 28 ngày cũng cắt connection (`01`).

## Phần Frappe đã có: Connected App + Token Cache

Mọi dòng [S], file `frappe/integrations/doctype/connected_app/connected_app.py` và `…/token_cache/token_cache.py`:

```text
form Connected App "Xero" trong Desk → nút Connect
 ▼ initiate_web_application_flow(user, success_uri)        connected_app.py:94    whitelisted document method
     dựng authorize URL, lưu state vào Token Cache "<app>-<user>"
 ▼ Xero trả trình duyệt về:
   callback(code, state)                                   :197-198  GET, allow_guest (Guest bị đưa qua /login trước)
     fetch_token(…, include_client_id=True)                :223-227  đổi code lấy token
     token_cache.update_data(token)                        token_cache.py:40
        save(ignore_permissions=True) + frappe.db.commit() :70-71    ← tự commit
 ▼ về sau:
   get_active_token(user)                                  connected_app.py:146
     hết hạn (token_cache.py:81) → with filelock(…)        :151      → refresh → update_data → commit
   token_cache.get_auth_header()                           token_cache.py:35   {"Authorization": "Bearer …"}
   has_token(connected_app, connected_user)                connected_app.py:237   "đã nối chưa?"
```

**Bản ghi Connected App được tạo bằng code, không gõ tay trong Desk** (kế hoạch, yêu cầu 17): một hàm setup chạy sau migrate tạo nó với tên cố định `xero`, nên Redirect URI không đổi qua các lần dựng lại database. `client_id` và `client_secret` không nằm trong repo: bạn đặt chúng vào site config bằng lệnh, hàm setup đọc từ đó. Việc làm tay còn lại: bấm Connect.

Các giá trị hàm setup đặt (các URL là [G]):

| Field | Giá trị |
|---|---|
| Client Id, Client Secret (Password) | từ app Xero; gõ trong Desk |
| Authorization URI | `https://login.xero.com/identity/connect/authorize` |
| Token URI | `https://identity.xero.com/connect/token` |
| Scopes (mỗi dòng một cái) | `offline_access`, `accounting.invoices`, `accounting.contacts`, `accounting.settings.read` (+ `accounting.payments` khi cần) |
| Redirect URI | read-only, Frappe tự tính lúc lưu ([S] `:60-65`): `<URL site>/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/<tên app>`. Nó phụ thuộc URL của site, nên khác nhau giữa lab và môi trường khác. **Copy đúng chuỗi này vào app Xero.** |

## Bốn chỗ Frappe không lo giúp

| # | Khoảng trống | Hệ quả | Việc phải làm |
|---|---|---|---|
| 1 | **Không có tenant id.** Token Cache chỉ giữ token. | Không biết gọi vào organisation nào. | Sau khi nối, gọi `GET /connections`, lưu `tenantId` vào một single DocType `Lab Xero Settings` (bạn tạo trong Desk). |
| 2 | **Token gắn với một user Frappe** ("`<app>-<user>`"); `get_active_token()` mặc định lấy user của session ([S] `:146`). | Alice bấm Connect, Bob tạo invoice → job chạy với tên Bob → không có token. | Job **luôn** truyền `user=settings.connected_user`. Một organisation = một user đã lưu. |
| 3 | **Refresh hỏng trả về `None`**, không raise: exception bất kỳ → ghi Error Log "Token Refresh Error" rồi `return None` ([S] `:163-165`). | Coi `None` như lỗi thường sẽ đốt hết lượt retry của mọi dòng. | `None` → lỗi riêng `XeroAuthLost` → tạm dừng toàn bộ sync, báo "reconnect". |
| 4 | **`update_data` tự commit** ([S] `token_cache.py:71`). | Refresh giữa job = commit nửa chừng mọi thứ job đã ghi. | Trong job: **lấy token trước tiên**, rồi mới lock và ghi dòng outbox. |

Hai điều chưa biết, chỉ một lần nối thật mới trả lời:
- ~~Xero có chấp nhận redirect URI `http://lab.localhost:<port>/…` không.~~ **Đã có câu trả lời (con người thử ngày 2026-10-12): không.** Form tạo app của Xero báo "Must use https (except localhost which may use http)". Vậy với demo local, redirect URI phải là `http://localhost:8000/api/method/frappe.integrations.doctype.connected_app.connected_app.callback/xero`. Ba hệ quả:
  1. Frappe phải **tự sinh ra đúng chuỗi đó**: Redirect URI được tính từ URL của site ([S] `connected_app.py:60-65`), nên URL của site phải được đặt thành `http://localhost:8000` rồi bản ghi Connected App được lưu lại (hàm setup làm việc này khi migrate). Chỉ sửa bên Xero là không khớp.
  2. `http://localhost:8000` phải mở đúng site của lab.
  3. **Làm cả lượt Connect trong một tab mở bằng `http://localhost:8000`** (đăng nhập Frappe ở đó, rồi bấm Connect). Cookie đăng nhập gắn với tên host: nếu bắt đầu ở `lab.localhost` thì lúc Xero trả về `localhost` bạn là Guest, bị đưa qua trang login, và dễ lệch `state`.
- **Đã thử ngày 2026-10-12: bước đổi code lấy token chạy được.** Con người bấm Connect, đồng ý bên Xero và được đưa về Frappe không có lỗi (callback của Frappe ném lỗi nếu đổi token hỏng). Vậy Xero nhận cách Frappe gửi credential. Còn chưa thử: lần **refresh** token đầu tiên (sau 30 phút), nơi Frappe gửi kèm tham số thừa `redirect_uri`. Ghi chú gốc:
- Frappe gửi client credential trong body (`include_client_id=True`, [S] `:227`) trong khi tài liệu Xero mô tả HTTP Basic [G]; và lời gọi refresh kèm thêm `redirect_uri` ([S] `:159`). Xero có nhận cả hai không: thử là biết. Nếu không, phải tự viết bước đổi token trong `integrations/xero/` thay vì dùng Connected App.

## Tự kiểm tra

1. Sau khi OAuth xong, ba giá trị nào phải được lưu, và Frappe tự lưu được mấy cái?
2. Vì sao job không được gọi `get_active_token()` không tham số?
3. App tạo hôm nay xin scope `accounting.transactions` thì sao, và phải xin gì thay?
