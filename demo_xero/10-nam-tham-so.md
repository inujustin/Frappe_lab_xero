# 10. Năm tham số đưa vào Frappe: mỗi cái là gì, đi đâu, dùng ở đâu

Năm giá trị nằm trong **site config** của site (ngoài repo). Sau mỗi lần migrate, `setup/xero_connection.py` đọc chúng và chép vào hai bản ghi. Code chạy hằng ngày không đọc site config nữa; nó đọc hai bản ghi đó.

## Hình

```text
 SITE CONFIG (con người gõ, một lần)        setup/xero_connection.py            DÙNG Ở ĐÂU
 ────────────────────────────────────       (sau mỗi migrate)                   ──────────
 xero_client_id            ───────────────► Connected App "xero".client_id  ──► URL authorize; đổi code; refresh
 xero_client_secret        ───────────────► Connected App "xero".client_secret ► CHỈ gửi tới identity.xero.com/connect/token
                                            (field Password, mã hóa)
 xero_connected_user       ───────────────► Lab Xero Settings.connected_user ─► chọn dòng Token Cache "xero-<user>"
 xero_default_account_code ───────────────► Lab Xero Settings.default_account_code ► mỗi dòng hóa đơn: AccountCode
 xero_default_tax_type     ───────────────► Lab Xero Settings.default_tax_type ──► mỗi dòng hóa đơn: TaxType
```

Hai nhóm: hai cái đầu là **danh tính của app với Xero** (do Xero cấp); ba cái sau là **lựa chọn của ta** cho demo.

## Từng tham số

| Tham số | Là gì | Lấy từ đâu | Giá trị trong demo | Bí mật? |
|---|---|---|---|---|
| `xero_client_id` | tên định danh của app với Xero | developer.xero.com, trang app | `<CLIENT_ID>` | không (nó nằm trong URL trình duyệt mở) |
| `xero_client_secret` | mật khẩu của **app** (không phải của người dùng) | cùng trang đó, nút tạo secret | `<CLIENT_SECRET>` | **có** |
| `xero_connected_user` | user Frappe nào đã bấm Connect | ta chọn | `Administrator` | không |
| `xero_default_account_code` | mã tài khoản doanh thu bên Xero cho mọi dòng hóa đơn | Chart of accounts của tổ chức Xero | `200` (Sales) | không |
| `xero_default_tax_type` | mã thuế bên Xero cho mọi dòng hóa đơn | danh sách Tax Rates của tổ chức Xero | `NONE` (Tax Exempt, 0%) | không |

## `client_secret`: dùng ở đâu, không dùng ở đâu

Nó chứng minh với Xero rằng **bên đang xin token đúng là app đã đăng ký**. `code` đi qua trình duyệt nên có thể lộ; không có secret thì `code` vô dụng.

```text
                                   có client_secret?
 ③ trình duyệt → login.xero.com/…/authorize          KHÔNG   (chỉ client_id)
 ⑥ Frappe → identity.xero.com/connect/token          CÓ      đổi code lấy token, lúc Connect
 ↻ Frappe → identity.xero.com/connect/token          CÓ      đổi refresh token lấy token mới, mỗi ~30 phút
   job → api.xero.com (Invoices, Contacts…)          KHÔNG   (chỉ access token + xero-tenant-id)
```

Hai chỗ dùng trong code của Frappe:

```python
# frappe/.../connected_app.py:223-229  (callback: đổi code lấy token)
token = oauth_session.fetch_token(
	connected_app.token_uri,
	code=code,
	client_secret=connected_app.get_password("client_secret"),
	include_client_id=True,
	**query_params,
)
```

```python
# frappe/.../connected_app.py:78-81  (get_oauth2_session: chuẩn bị cho refresh)
auto_refresh_kwargs = {"client_id": self.client_id}
client_secret = self.get_password("client_secret")
if client_secret:
	auto_refresh_kwargs["client_secret"] = client_secret
```

Code của ta chỉ đụng tới secret ở **một dòng**, để chép nó vào field Password:

```python
# setup/xero_connection.py:62-63
app.client_id = values["xero_client_id"]
app.client_secret = values["xero_client_secret"]
```

Nó nằm ở hai nơi: site config (file trên server, ngoài repo) và field Password của Connected App (mã hóa). Nó không bao giờ tới trình duyệt, không nằm trong repo, tài liệu hay câu lỗi của ta. Lộ thì: tạo secret mới bên Xero → đặt lại site config → migrate → Connect lại.

## Ba tham số còn lại: dùng ở đâu

**`xero_connected_user`** quyết định dùng token của ai. Frappe lưu token theo từng user, dòng tên `xero-<user>`:

```python
# integrations/xero/client.py:22-25
app = frappe.get_doc("Connected App", settings.connected_app)
token = app.get_active_token(user=settings.connected_user)
if not token:
	raise XeroAuthLost("Xero authorization is unavailable; reconnect Xero.")
```

Nó phải **trùng với user đã bấm Connect**. Ghi `Administrator` mà người khác bấm Connect thì không tìm thấy token.

**`xero_default_account_code`** và **`xero_default_tax_type`** đi vào từng dòng hóa đơn gửi sang Xero:

```python
# lab_xero/mapping.py:58-64
return {
	"Description": description,
	"Quantity": quantity,
	"UnitAmount": rate,
	"AccountCode": settings.default_account_code,
	"TaxType": settings.default_tax_type,
}
```

Chúng là mã **của tổ chức Xero**, không phải của ERPNext. Đổi tổ chức thì phải tra lại.

## Sai hoặc thiếu thì thấy gì

| Tham số | Thiếu trong site config | Sai giá trị |
|---|---|---|
| `xero_client_id` / `xero_client_secret` | migrate in "Skipping Connected App: both credential keys are required."; bản ghi `xero` không được tạo | Connect hỏng ở bước đổi `code` (Xero từ chối); không có token |
| `xero_connected_user` | field trong Settings giữ giá trị cũ; nếu trống: "Xero connection settings are incomplete…" | "Xero authorization is unavailable; reconnect Xero." |
| `xero_default_account_code` / `xero_default_tax_type` | đơn `Failed`: "Set the Xero revenue account and tax type before syncing." | đơn `Failed` với câu từ chối của Xero, nguyên văn |

Hai hành vi của code setup đáng nhớ:

```python
# setup/xero_connection.py:30-35
for key in keys:
	value = frappe.conf.get(key)
	if value is None or value == "":
		print(f"[xero setup] Missing site config: {key}; skipping that configuration.")
	else:
		values[key] = value
```

- **Thiếu thì bỏ qua, không xóa**: giá trị đã lưu trong database được giữ nguyên.
- **Đổi giá trị thì phải migrate**: site config chỉ được đọc lúc migrate. Riêng đổi `client_id`/`client_secret` còn phải Connect lại.

## Không phải năm cái này

| Thứ | Ở đâu | Ai đặt |
|---|---|---|
| `host_name` (`http://localhost:8000`) | site config | con người; Frappe dùng nó để tính Redirect URI |
| Redirect URI | Connected App, chỉ đọc | Frappe tự tính |
| scope | hằng `SCOPES` trong code | ta |
| `tenant_id`, `tenant_name` | Lab Xero Settings | job `discover_tenant`, hỏi Xero |
| access token, refresh token | Token Cache | Frappe, lúc Connect và refresh |

Chưa kiểm chứng: site config chưa từng được đọc (luật dự án cấm), nên "năm khóa nằm ở đó" là theo code setup và theo kết quả migrate đã thấy; cách thư viện OAuth đặt secret vào request (body hay header) chưa đọc trong code thư viện; câu lỗi khi `client_secret` sai chưa thấy thật.
