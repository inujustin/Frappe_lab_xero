# Hướng dẫn Track N: OAuth từ lõi, bằng một dự án riêng ngoài Frappe

Viết ngày 2026-10-13 theo yêu cầu của con người. Mục tiêu: hiểu OAuth tới mức **tự dựng được cả hai đầu** (bên cấp quyền và bên xin quyền) bằng công nghệ đã quen (Spring Boot, FastAPI, React), rồi quay lại nhìn `Connected App` của Frappe và thấy nó chỉ là một trường hợp của cùng cơ chế.

Kế hoạch này thô có chủ đích: stage, dữ kiện chung, xong khi nào. Chi tiết bên trong mỗi stage do phiên làm việc quyết.

## Status (Trạng thái)

| Stage | Trạng thái |
|---|---|
| S0 Chốt dữ kiện, dựng khung | NOT STARTED |
| S1 Đọc lõi OAuth | NOT STARTED |
| S2 Thử với Google thật | NOT STARTED |
| S3 Trace Connected App | NOT STARTED (đã có nguyên liệu: `demo_xero/02`, `09`, `10`, `12`) |
| S4 Tự dựng bên cấp quyền + client + FE | NOT STARTED |
| S5 Các kịch bản | NOT STARTED |
| S6 Nối ngược về Frappe | NOT STARTED |

Chỉ cập nhật khi con người yêu cầu.

## Bốn điều con người đã chốt (2026-10-13)

| Câu hỏi | Chốt |
|---|---|
| Code nằm ở đâu | thư mục mới `oauth_lab/` ở gốc repo này, có file compose riêng, tách hẳn khỏi `frappe-bench/` |
| Ai đóng vai gì | **FastAPI = bên cấp quyền, viết tay** (thấy mọi endpoint và mọi phép kiểm); **Spring Boot = client**, dùng thư viện OAuth của Spring (đúng việc Connected App làm trong Frappe); **React = frontend** |
| Ai viết code | agent viết toàn bộ, có chú thích; con người chạy và lần theo từng request |
| Hình dạng kế hoạch | track mới, file này |

## Bức tranh

```text
 S1 đọc lõi ──► S2 Google thật ──► S3 trace Connected App ──► S4 tự dựng 3 container ──► S5 kịch bản ──► S6 về lại Frappe
   (khái niệm)    (thấy một bên        (Frappe làm client          (thay Google bằng         (bắt buộc      (Frappe làm client
                   cấp quyền thật)      thế nào, từng tham số)      bên cấp quyền của ta)      trước, rồi     của server ta dựng)
                                                                                               mở rộng)
```

Bốn vai, ba container (S4):

```text
 ┌ fe (React) ─────────┐   ┌ client (Spring Boot) ───────┐   ┌ auth (FastAPI, viết tay) ──────────────┐
 │ trang của app       │◄─►│ giữ client_secret           │──►│ BÊN CẤP QUYỀN: /authorize /token       │
 │ chỉ nói với client  │   │ giữ token theo từng user    │   │   /userinfo /revoke /introspect /jwks  │
 │ (trừ kịch bản PKCE) │   │ session riêng với trình duyệt│   │   trang đăng nhập, trang đồng ý        │
 └─────────┬───────────┘   └─────────────────────────────┘   │ BÊN GIỮ DỮ LIỆU: /api/…  (kiểm token)  │
           └────────── trình duyệt được chuyển hướng ───────►│ sổ đăng ký client (id, secret, URI,    │
                                                             │   scope được phép) = "developer portal"│
                                                             └────────────────────────────────────────┘
```

So với đợt Xero: `auth` đóng cả ba vai của Xero (`login.xero.com`, `identity.xero.com`, `api.xero.com`); `client` đóng vai Frappe + Connected App + Token Cache; `fe` đóng vai Desk.

## Dữ kiện chung (mọi phiên giữ giống nhau)

| Dữ kiện | Giá trị | Ghi chú |
|---|---|---|
| Thư mục | `oauth_lab/auth/`, `oauth_lab/client/`, `oauth_lab/fe/`, `oauth_lab/compose.yaml`, `oauth_lab/README.md` | không file nào ở đây import hay gọi vào `frappe-bench/` |
| Cổng trên host | `auth` 9100, `client` 8100, `fe` 3100 | tránh 8000 và 9000 của site Frappe; con người xác nhận cổng trống ở S0 |
| Tên host | mọi thứ là `localhost` | bài học Xero: nhiều nhà cung cấp chỉ nhận `http` với đúng `localhost` |
| Cookie | `auth` và `client` dùng **tên cookie khác nhau** | cookie không phân biệt cổng: cùng `localhost` mà trùng tên là ghi đè nhau |
| Hai địa chỉ của `auth` | trình duyệt gọi `http://localhost:9100`; container `client` gọi qua mạng nội bộ của compose | đây là bẫy thật ("issuer" phải là một); cách xử lý được chốt ở S0 và ghi vào `oauth_lab/README.md` |
| Phiên bản | ghim trong `oauth_lab/versions.env`; con người kiểm từng package trên trang chính thức trước khi cài (`AGENTS.md` A6) | agent không đoán số phiên bản |
| Bí mật | secret của Google và của client nằm trong file `.env` không commit; trong tài liệu viết `<…>` | repo công khai |
| Lưu trữ của `auth` | đơn giản nhất chạy được (bộ nhớ hoặc SQLite) | mục tiêu là cơ chế, không phải sản phẩm |
| Ai chạy | con người chạy mọi lệnh (`docker compose`, cài đặt, build); agent chỉ viết file | `AGENTS.md` A3, B10 |

## Các stage

### S0. Chốt dữ kiện, dựng khung

Chốt cổng, cách xử lý hai địa chỉ của `auth`, phiên bản; tạo ba thư mục rỗng chạy được "hello" trong container. **Xong khi:** một lệnh dựng cả ba, mỗi cái trả lời ở cổng của nó.

### S1. Đọc lõi OAuth

Đọc theo thứ tự ở mục "Tài liệu đọc". Đã có sẵn ba bản viết từ đợt Xero để đọc trước: `docs/xero/knowledge/oauth.md`, `demo_xero/02-oauth.md`, `demo_xero/12-oauth-ranh-gioi.md`. **Xong khi:** con người trả lời được từ trí nhớ mười câu ở mục "Tự kiểm".

### S2. Thử với Google thật (chưa có server của ta)

Chỉ container `client` (và một trang tối thiểu): "Đăng nhập bằng Google", rồi gọi một API của Google bằng token nhận được. Cần một OAuth client trong Google Cloud Console: việc của con người, viết thành runbook trước (`docs/runbooks/`). **Xong khi:** con người chỉ được trong log của `client` từng request ở sơ đồ ba vùng của `demo_xero/12`, và nói được Google khác Xero ở điểm nào (có ID token, không có tenant).

### S3. Trace Connected App của Frappe

Một trace note `docs/traces/connected-app-oauth-client.md`, mỗi bước có `path:line`: từng field cấu hình để làm gì; nó xử lý thế nào ở chế độ dev (`http`, nới kiểm scope); token lưu theo user; refresh có khóa; và **nó không làm gì** (PKCE, thu hồi, kiểm ID token). Kèm một bảng đối chiếu từng field với cấu hình client của Spring ở S2. **Xong khi:** với mỗi field của Connected App, con người nói được field tương ứng bên Spring và hậu quả nếu đặt sai.

### S4. Tự dựng bên cấp quyền, client và FE

`auth` viết tay bằng FastAPI: sổ đăng ký client, trang đăng nhập, trang đồng ý, `/authorize`, `/token`, một API dữ liệu được bảo vệ. `client` ở S2 được **đổi cấu hình** để trỏ sang `auth` thay cho Google, không đổi code. **Xong khi:** luồng authorization code chạy trọn với server của ta, và việc chuyển qua lại giữa Google và `auth` chỉ là đổi cấu hình (đó là bằng chứng client không phụ thuộc nhà cung cấp, giống Connected App).

### S5. Các kịch bản

Mỗi kịch bản: chạy cho đúng, **rồi cố ý làm hỏng** và đọc lỗi ở cả hai đầu. Bảng ở mục dưới. Làm hết nhóm bắt buộc trước.

### S6. Nối ngược về Frappe

Tạo một Connected App trong Frappe trỏ vào `auth` của ta (bằng code trong `lab_core/setup/`, như đã làm với Xero). Tùy chọn: chiều ngược lại, Frappe làm bên cấp quyền cho `client` của ta (đây cũng là một phần của track B). **Xong khi:** Frappe lấy được token từ `auth` và gọi được API dữ liệu của nó; con người giải thích được từng tham số mà không mở tài liệu.

## Các kịch bản của S5

**Bắt buộc: những thứ đã gặp thật trong đợt Xero.** Cột cuối là chỗ đã gặp.

| # | Kịch bản | Cố ý làm hỏng | Đã gặp ở |
|---|---|---|---|
| M1 | Authorization code với client có secret, có `state` | sửa `state`; dùng một `code` hai lần; để `code` hết hạn | Connect Xero; lỗi "Invalid token state!" |
| M2 | Redirect URI phải khớp từng ký tự | đổi một ký tự; đổi `localhost` thành tên khác; `http` với tên không phải `localhost` | Xero từ chối `http://lab.localhost:8000/…` |
| M3 | Hạn token, refresh, xoay vòng refresh token | dùng lại refresh token cũ; hai lần refresh cùng lúc; không xin quyền refresh | `expires_in` 1800; khóa file khi refresh; lỗi "Refresh token is missing" |
| M4 | Scope: được phép xin, đã xin, đã cấp | gọi API ngoài scope (với Xero chưa từng thử); xin scope không được phép; thêm scope mà không đồng ý lại | bốn scope của ta, một cái thừa; danh sách ở developer portal |
| M5 | Đăng nhập (biết người dùng là ai) khác ủy quyền (được gọi API). ID token → session của app | ba cách con người đã nêu: FE tự khai email (phải bị từ chối); FE gửi ID token cho BE kiểm; BE tự đổi `code`. Thử đưa token cấp cho client khác | phần kiểm tra hiểu biết ngày 2026-10-12 (`demo_xero/08`, mục 8) |
| M6 | `client_secret`: dùng ở đâu, không bao giờ tới trình duyệt, đổi khi lộ | secret sai; đổi secret khi đang có token sống | secret bị lộ hai lần và phải đổi |
| M7 | Token của ai: mỗi user một token, hay một "tài khoản dịch vụ" cho cả hệ thống | user chưa từng nối gọi API | `connected_user`, dòng `xero-Administrator` |
| M8 | Hai session khác nhau: session của app và session ở bên cấp quyền | mất cookie của app giữa chừng; đăng xuất app nhưng vẫn còn đăng nhập ở bên cấp quyền | bị đưa về `/login` khi đổi từ `lab.localhost` sang `localhost` |
| M9 | Sau khi đồng ý: token này vào **tổ chức nào** | gọi API thiếu định danh tổ chức; dùng định danh của tổ chức chưa nối | `xero-tenant-id`, job `discover_tenant` |

**Mở rộng: chưa gặp, nhưng cần để gọi là hiểu OAuth.**

| # | Kịch bản | Vì sao cần |
|---|---|---|
| E1 | PKCE: React tự làm client, không có secret; rồi thêm PKCE cho cả client có secret | Frappe không gửi PKCE; đây là chuẩn hiện nay cho ứng dụng chạy trên trình duyệt |
| E2 | Client credentials: máy gọi máy, không có người dùng | Connected App có sẵn đường này (`get_backend_app_token`), ta chưa dùng |
| E3 | Hai dạng token: chuỗi mờ + hỏi lại bên cấp (introspection), hoặc JWT tự kiểm bằng khóa công khai | trả lời "bên giữ dữ liệu tin token bằng cách nào", và stateful hay stateless (track B) |
| E4 | Thu hồi: người dùng gỡ app; token còn sống thì sao với mỗi dạng ở E3 | bên Xero có nút gỡ app; ta chưa xem hệ quả |
| E5 | Tấn công thường gặp, mỗi cái một thí nghiệm nhỏ: callback không có `state`, chuyển hướng mở, token nằm trong URL (implicit flow, vì sao bị bỏ) | hiểu vì sao luồng có hình dạng như vậy |
| E6 | Tùy chọn: device flow; Gmail qua XOAUTH2 (thuộc track H) | chỉ khi còn thời gian |

## Tài liệu đọc (S1)

Mọi URL viết từ trí nhớ, chưa mở để kiểm. Đọc theo thứ tự; ba cái đầu là đủ để bắt đầu S2.

| # | Đọc | Để hiểu |
|---|---|---|
| 1 | https://www.oauth.com/ (OAuth 2.0 Simplified) | toàn cảnh, viết cho người làm |
| 2 | RFC 6749, mục 1, 4.1, 5, 6, 10: https://datatracker.ietf.org/doc/html/rfc6749 | định nghĩa gốc của bốn vai, authorization code, refresh, phần an toàn |
| 3 | OpenID Connect Core, mục 2 và 3.1: https://openid.net/specs/openid-connect-core-1_0.html | ID token, "đăng nhập bằng…" |
| 4 | RFC 7636 (PKCE): https://datatracker.ietf.org/doc/html/rfc7636 | E1 |
| 5 | RFC 6750 (bearer token): https://datatracker.ietf.org/doc/html/rfc6750 | token được gửi và bị từ chối thế nào |
| 6 | RFC 9700 (thực hành an toàn hiện nay): https://datatracker.ietf.org/doc/html/rfc9700 · OAuth 2.1: https://oauth.net/2.1/ | cái gì đã bị bỏ và vì sao (E5) |
| 7 | RFC 7009 (thu hồi), RFC 7662 (introspection): https://datatracker.ietf.org/doc/html/rfc7009 · https://datatracker.ietf.org/doc/html/rfc7662 | E3, E4 |
| 8 | Google: https://developers.google.com/identity/protocols/oauth2/web-server · https://developers.google.com/identity/openid-connect/openid-connect | S2 |
| 9 | Spring Security, OAuth2 client: https://docs.spring.io/spring-security/reference/servlet/oauth2/client/index.html | container `client` |
| 10 | FastAPI, phần security: https://fastapi.tiangolo.com/tutorial/security/ | container `auth` (ta viết tay bên cấp quyền; phần này chỉ để biết công cụ có gì) |
| 11 | Xero: https://developer.xero.com/documentation/guides/oauth2/auth-flow | đối chiếu với thứ đã làm |

## Tự kiểm (xong S1 khi trả lời được, không nhìn tài liệu)

1. Bốn vai trong OAuth là ai? Trong đợt Xero, mỗi vai là thành phần nào?
2. Vì sao có bước `code` thay vì trả token thẳng cho trình duyệt?
3. `state` chống điều gì? PKCE chống điều gì? Hai cái có thay nhau được không?
4. `client_secret` được gửi ở những lời gọi nào, và không bao giờ ở lời gọi nào?
5. Access token khác refresh token ở hạn sống, nơi dùng và hậu quả khi lộ thế nào?
6. Scope do ai xin, ai cho, ai thi hành?
7. "Đăng nhập bằng Google" khác "Connect to Xero" ở mục đích và ở thứ app nhận được ra sao?
8. Bên giữ dữ liệu biết một token hợp lệ bằng hai cách nào?
9. Vì sao redirect URI phải đăng ký trước và khớp từng ký tự?
10. Client có secret khác client công khai ở đâu, và React thuộc loại nào?

## Chạy song song được gì

```text
 Con người:  S1 (đọc)  ─────────────────────────────►  runbook Google (cho S2)
 Phiên 1:    S0 (khung oauth_lab/)  ─►  S2  ─►  S4  ─►  S5        (chỉ đụng oauth_lab/)
 Phiên 2:    S3 (trace Connected App)                              (chỉ đụng docs/traces/)
 Sau cùng:   S6 (đụng lab_core/setup/ và hooks.py: không song song với việc khác trên hooks.py)
```

## Ngoài phạm vi

SAML, đăng nhập một lần cho doanh nghiệp, hạ tầng khóa thật (HSM), giao diện đẹp, lưu trữ bền, triển khai ra internet. Mọi thứ chạy trên `localhost`.
