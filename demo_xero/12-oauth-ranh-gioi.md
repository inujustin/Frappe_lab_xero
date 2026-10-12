# 12. OAuth nhìn theo ranh giới: ba vùng, ai gọi ai, vào gì, ra gì

Ba câu hỏi, ba phần: (1) ba vùng và thứ đi qua ranh giới; (2) Connected App giúp ta khỏi viết gì; (3) làm sao chặn việc dev xin scope nhiều hơn cần.

## 1. Ba vùng và ba ranh giới

```text
 ┌─ VÙNG 1: FE ─────────────┐     ┌─ VÙNG 2: BE (Frappe) ───────────┐     ┌─ VÙNG 3: XERO ───────────────────┐
 │ trình duyệt của admin    │     │ server của ta, trong Docker     │     │ cloud của Xero                   │
 │                          │     │                                 │     │                                  │
 │ • form Connected App     │  A  │ • web: initiate_…flow, callback │  C  │ • login.xero.com   (đăng nhập,   │
 │   (nút Connect)          │◄───►│ • database:                     │────►│                     đồng ý)      │
 │ • cookie sid (localhost) │     │    Connected App (id, secret)   │     │ • identity.xero.com (cấp token)  │
 │ • cookie đăng nhập Xero  │     │    Token Cache (state, token)   │     │ • api.xero.com      (dữ liệu)    │
 │                          │     │ • worker: job gọi Xero          │     │ • sổ của Xero: app đã đăng ký,   │
 └────────────┬─────────────┘     └─────────────────────────────────┘     │   redirect URI, scope được phép, │
              │                                B                          │   kết nối app ↔ tổ chức          │
              └──────────────────────────────────────────────────────────►│                                  │
                                                                          └──────────────────────────────────┘
 A = FE ↔ BE        B = FE ↔ Xero        C = BE → Xero (server tới server)
 KHÔNG có: Xero → BE (Xero không bao giờ mở kết nối vào server của ta)
 KHÔNG có: FE → api.xero.com (trình duyệt không bao giờ gọi API dữ liệu)
```

### Thứ đi qua từng ranh giới

| Ranh giới | Ai mở kết nối | Tới đâu | Bên nhận tin bên gọi nhờ | VÀO | RA |
|---|---|---|---|---|---|
| **A** ① | FE | BE `localhost:8000` | cookie `sid` | "tôi bấm Connect" | URL authorize |
| **B** ③ | FE | Xero `login.xero.com` | người dùng đăng nhập Xero | `client_id`, `redirect_uri`, `scope`, `state` | lệnh chuyển hướng kèm `code`, `state` |
| **A** ⑤ | FE | BE `…/callback/xero` | cookie `sid` + `state` trùng | `code`, `state` | lệnh chuyển hướng về form |
| **C** ⑥ | BE | Xero `identity.xero.com/connect/token` | `client_id` + **`client_secret`** | `code`, `redirect_uri` | `access_token`, `refresh_token`, `expires_in` |
| **C** refresh | BE | Xero `identity.xero.com/connect/token` | `client_id` + **`client_secret`** | `refresh_token` | bộ token mới |
| **C** dữ liệu | BE (job) | Xero `api.xero.com` | `access_token` + `xero-tenant-id` | request (invoice, contact…) | JSON dữ liệu |

Số ①③⑤⑥ khớp với sơ đồ ở `02`.

### Mỗi vùng: giữ gì, kiểm gì, không bao giờ thấy gì

| Vùng | Giữ | Tự kiểm | **Không bao giờ thấy** |
|---|---|---|---|
| **FE** | cookie `sid`; trong vài giây: `code`, `state` trên thanh địa chỉ | không kiểm gì | `client_secret`, access token, refresh token |
| **BE** | `client_id`, `client_secret`, `state`, hai token, `tenant_id` | ở ⑤: đã đăng nhập chưa, `state` có trùng không | mật khẩu Xero của người dùng |
| **Xero** | mật khẩu người dùng; bản đăng ký app; kết nối app ↔ tổ chức | ở ③: `client_id` có thật, `redirect_uri` đã đăng ký, scope được phép, người dùng đồng ý. Ở ⑥: `code` còn hạn và chưa dùng, secret đúng, `redirect_uri` trùng. Ở mỗi lời gọi API: token còn hạn, scope đủ, tổ chức đã nối | cookie `sid`; dữ liệu trong database Frappe |

### Vì sao chia ba chặng mà không đưa token thẳng cho trình duyệt

```text
 chặng qua TRÌNH DUYỆT (B, A)        chỉ mang thứ ÍT GIÁ TRỊ:  code (một lần, vài phút), state
 chặng SERVER ↔ SERVER (C)           mang thứ CÓ GIÁ TRỊ:       client_secret, access token, refresh token
```

Trình duyệt là nơi dễ lộ nhất (lịch sử, tiện ích, log). Nên thứ đi qua nó phải vô dụng nếu bị lấy: `code` không đổi được thành token nếu thiếu `client_secret`, mà secret chỉ có ở BE.

## 2. Connected App: thứ có sẵn, khỏi viết từ đầu

Đúng: `Connected App` là bộ OAuth client dựng sẵn của Frappe. App nào trên Frappe muốn nối một nhà cung cấp OAuth 2.0 thì tạo một bản ghi, không phải tự viết luồng.

| Việc trong luồng OAuth | Nếu tự viết | Connected App đã có |
|---|---|---|
| Dựng URL authorize, sinh `state` | phải viết | `initiate_web_application_flow` (dòng 94-116) |
| Endpoint nhận `code` | phải viết + đăng ký route | `callback` (dòng 198-233) |
| Kiểm `state`, kiểm đã đăng nhập | phải viết | trong `callback` |
| Đổi `code` lấy token | phải viết | trong `callback` |
| Lưu token có mã hóa, theo từng user | phải thiết kế bảng | DocType `Token Cache` |
| Biết token hết hạn; tự refresh; hai worker không refresh chồng nhau | phải viết | `get_active_token` (dòng 146-167) |
| Tạo header `Authorization: Bearer …` | phải viết | `Token Cache.get_auth_header` |
| Màn hình cấu hình + nút Connect | phải viết | form của DocType |

Phần ta vẫn phải viết (vì là chuyện riêng của Xero hoặc của demo): tạo bản ghi bằng code, tìm tenant, chọn token của ai, gọi API, báo lỗi cho người dùng. Chi tiết: `09`.

## 3. Dev xin scope nhiều hơn cần: chặn ở đâu

Code của ta là nơi **xin**. Có bốn chốt, ba cái nằm ngoài tay dev:

```text
 dev sửa SCOPES trong code
        │
        ▼
 ① TRẦN ở developer.xero.com     app chỉ xin được scope có trong danh sách của app
        │
        ▼
 ② MÀN HÌNH ĐỒNG Ý của Xero      admin thấy TỪNG scope trước khi bấm Allow; thấy thừa thì từ chối
        │                        (xin thêm scope = phải Connect lại = admin thấy lại màn hình này)
        ▼
 ③ TOKEN mang đúng scope đã cấp  Xero kiểm ở mỗi lời gọi; ngoài scope thì từ chối
        │
        ▼
 ④ SOÁT LẠI SAU ĐÓ               Frappe ghi scope đã cấp vào Token Cache; Xero liệt kê app đã nối
```

| Chốt | Ai giữ | Chặn được gì | Mức xác nhận |
|---|---|---|---|
| Hằng `SCOPES` nằm **một chỗ** trong code (`setup/xero_connection.py:7-12`) | người review code | thấy ngay khi dev thêm scope | theo code |
| ① Danh sách scope của app trên developer.xero.com | chủ app bên Xero | scope ngoài danh sách | thấy danh sách trong ảnh chụp; **chưa rõ** có thu hẹp được trên trang đó không |
| ② Màn hình đồng ý | admin của tổ chức Xero | mọi scope thừa, nếu admin đọc | từ trí nhớ: chỉ Allow cả gói hoặc từ chối, không bỏ từng dòng |
| ③ Xero kiểm scope ở mỗi lời gọi | Xero | dùng quyền chưa được cấp | mới thấy nửa: lời gọi trong scope chạy được; chưa thử lời gọi ngoài scope |
| ④ Soát lại | admin Frappe, admin Xero | phát hiện sau | theo code: `Token Cache.update_data` lưu danh sách `scope` Xero trả về vào bảng con `scopes` |

Câu trả lời thẳng: **không có** (theo những gì tôi kiểm được) một công tắc bên Xero kiểu "app này tối đa chỉ được 3 scope". Chốt thật là ②: **không ai lấy được quyền mà admin chưa nhìn thấy và bấm Allow**. Và dev không lách được ②, vì token cũ giữ nguyên scope cũ cho tới lần Connect kế.

Việc nên làm trong dự án thật: review mọi thay đổi của `SCOPES`; sau mỗi lần Connect, mở dòng Token Cache xem scope được cấp có đúng danh sách mong đợi không. Hiện demo xin thừa một scope (`accounting.settings.read`, xem `08` mục 11.1).

Chưa kiểm chứng: mọi mô tả về màn hình và trang web của Xero ở mục 3 là từ trí nhớ; việc Xero có trả `scope` trong câu trả lời token (để chốt ④ có dữ liệu) chưa xem trên bản ghi thật.
