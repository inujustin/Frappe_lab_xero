# 09. Connected App là hộp đen: code của ta lấy "client" rồi làm nghiệp vụ qua nó

**Được, coi nó là hộp đen.** Ta chỉ cần biết: đưa gì vào, lấy gì ra. Một chỗ cần chỉnh trong cách hình dung: `client` **không phải một kết nối mở sẵn** và không dùng chung giữa các job. Nó là một object nhỏ, tạo **đầu mỗi job**, chỉ giữ ba header; mỗi lời gọi là một request HTTPS riêng.

## Hộp đen: vào gì, ra gì

```text
            VÀO                         HỘP ĐEN (của Frappe)                  RA
 ─────────────────────────       ┌──────────────────────────┐       ─────────────────────────────
 tên app:  "xero"          ───►  │ Connected App            │  ───► token còn hạn  → dùng được
 user:     "Administrator" ───►  │  + Token Cache           │  ───► None           → phải Connect lại
                                 │ (tự làm mới token khi    │
                                 │  hết hạn, ta không lo)   │
                                 └──────────────────────────┘
```

Ta không cần biết bên trong nó dựng URL, kiểm `state` hay refresh thế nào. (Nếu bị hỏi: `02`.)

## Từng bước, có đích đến (một job tạo hóa đơn)

```text
 JOB NỀN (tasks/xero_sync.py)                                                  ĐÍCH
 ───────────────────────────────────────────────────────────────────────────────────────────────
 ① get_client()
     a. đọc Lab Xero Settings                         ──►  DATABASE FRAPPE   (app nào, user nào, tenant nào)
     b. app.get_active_token(user)                    ──►  HỘP ĐEN           (trả token; nếu hết hạn nó tự gọi
                                                                               identity.xero.com để đổi token mới)
     c. token.get_auth_header()                       ──►  HỘP ĐEN           (trả "Authorization: Bearer …")
     d. XeroClient(tenant_id, headers)                ──►  BỘ NHỚ CỦA JOB    (object giữ 3 header, chưa gọi mạng)

 ② nghiệp vụ, tất cả qua cùng một client:
     client.find_invoice("SAL-ORD-…")                 ──►  api.xero.com  GET  /Invoices
     client.find_contact("<mã khách>")                ──►  api.xero.com  GET  /Contacts
     client.create_contact(key, payload)              ──►  api.xero.com  PUT  /Contacts
     client.create_invoice(key, payload)              ──►  api.xero.com  PUT  /Invoices
     client.get_invoices(ids=[…])                     ──►  api.xero.com  GET  /Invoices

 ③ ghi kết quả                                        ──►  DATABASE FRAPPE   (Sales Order, Customer, Outbox)
 ④ job kết thúc: client bị bỏ. Job sau tạo client mới.
```

Chỉ có **ba đích**: database Frappe, hộp đen, `api.xero.com`. Trình duyệt không có mặt trong hình này.

## Code: lấy client

```python
# integrations/xero/client.py:15-30
def get_client(*, require_tenant: bool = True) -> "XeroClient":
	"""Obtain before taking outbox locks: Frappe's token refresh can commit."""
	settings = frappe.get_doc("Lab Xero Settings")
	if not settings.connected_app or not settings.connected_user:
		raise XeroAuthLost("Xero connection settings are incomplete; ask a System Manager to connect Xero.")
	if require_tenant and not settings.tenant_id:
		raise XeroAuthLost("Xero tenant is not configured; run the tenant discovery job first.")
	app = frappe.get_doc("Connected App", settings.connected_app)      # ← mở hộp đen
	token = app.get_active_token(user=settings.connected_user)         # ← lấy token
	if not token:
		raise XeroAuthLost("Xero authorization is unavailable; reconnect Xero.")
	try:
		headers = token.get_auth_header()                              # ← lấy header
	except frappe.DoesNotExistError:
		raise XeroAuthLost("Xero access token is missing; reconnect Xero.") from None
	return XeroClient(settings.tenant_id, headers)
```

Ba dòng có mũi tên là toàn bộ chỗ code của ta chạm vào hộp đen. (Chú thích mũi tên thêm ở đây cho dễ đọc; file thật không có.)

## Code: client là gì

```python
# integrations/xero/client.py:55-59
class XeroClient:
	def __init__(self, tenant_id: str | None, auth_headers: dict):
		self.headers = {**auth_headers, "Accept": "application/json"}
		if tenant_id:
			self.headers["xero-tenant-id"] = tenant_id
```

Client = ba header, không hơn:

| Header | Từ đâu | Để Xero biết |
|---|---|---|
| `Authorization: Bearer <access_token>` | hộp đen | app này được phép |
| `xero-tenant-id: <tenant_id>` | `Lab Xero Settings` | vào tổ chức nào |
| `Accept: application/json` | cố định | trả JSON |

## Code: mỗi lời gọi nghiệp vụ đi đâu

Mọi method (`find_invoice`, `create_contact`…) đều đi qua một hàm:

```python
# integrations/xero/client.py:150-169 (rút gọn)
headers = dict(self.headers)
url = API_URL + path                                  # https://api.xero.com/api.xro/2.0/<Invoices|Contacts|…>
...
if key is not None:
	headers["Idempotency-Key"] = key                  # chỉ cho lời gọi ghi
if modified_since:
	headers["If-Modified-Since"] = modified_since     # chỉ cho lời gọi "đã đổi từ lúc…"
response = requests.request(method, url, headers=headers, params=params,
	json=payload, timeout=HTTP_TIMEOUT, allow_redirects=False)
```

Một request, một câu trả lời, không giữ kết nối. Danh sách đầy đủ các lời gọi: `03`.

## Ta phải tự lo gì quanh hộp đen

| Hộp đen trả | Nghĩa | Code của ta làm |
|---|---|---|
| token | dùng được | tạo client, chạy nghiệp vụ |
| `None` | chưa Connect, hoặc refresh hỏng | ném `XeroAuthLost` → đơn `Failed`: "…reconnect Xero." |
| token nhưng Xero trả 401/403 | token bị thu hồi, hoặc thiếu quyền | ném `XeroAuthLost` (trong `_request`) |
| — (thiếu `tenant_id`) | chưa chạy `discover_tenant` | ném `XeroAuthLost`, chưa gọi mạng |

## Ba luật khi dùng client

1. **Lấy client trước tiên trong job**, trước mọi khóa và mọi lần ghi. Hộp đen có thể tự commit khi làm mới token.
2. **Chỉ `tasks/` gọi `get_client()`** (bốn chỗ: `xero_sync.py:22`, `:49`; `xero_pull.py:25`, `:37`). Request của người dùng không bao giờ cầm client.
3. **Một job, một client.** Token sống 30 phút, job chạy vài giây, nên không cần làm mới giữa chừng.

## Một lần duy nhất phải "mở hộp": Connect

Hộp đen chỉ có token **sau khi** admin bấm **Connect to Xero** một lần (`01`, bước 2–3). Từ đó về sau mọi thứ ở trên tự chạy, không cần người.
