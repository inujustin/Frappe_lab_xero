# 03. Từng lời gọi sang Xero: gửi gì, nhận gì, hỏng thế nào

Mọi lời gọi HTTP tới Xero đi qua **một** hàm, `XeroClient._request`, trong `integrations/xero/client.py`. Không file nào khác dựng request. Client chỉ được gọi từ background job (`tasks/`), không bao giờ từ request của người dùng.

Phần "Ra" bên dưới liệt kê đúng những field mà **code của ta đọc**. Xero trả nhiều hơn thế; tên field của Xero là từ tài liệu và trí nhớ, trừ chỗ ghi "đã quan sát".

## Khung chung của mọi request

```text
<METHOD> https://api.xero.com/api.xro/2.0/<Resource>[?tham số]
  Authorization:     Bearer <access_token>          ← từ Token Cache (02)
  xero-tenant-id:    <tenant_id>                    ← từ Lab Xero Settings
  Accept:            application/json
  Idempotency-Key:   <64 ký tự hex>                 ← chỉ với lời gọi ghi
  If-Modified-Since: <giờ UTC>                      ← chỉ khi kéo thay đổi
  timeout: 10 giây để nối, 30 giây để đọc
```

```python
# integrations/xero/client.py:11-12
API_URL = "https://api.xero.com/api.xro/2.0/"
HTTP_TIMEOUT = (10, 30)
```

```python
# integrations/xero/client.py:152-169  (trong _request)
headers = dict(self.headers)
url = API_URL + path
if resource is None:
	url = "https://api.xero.com/connections"
	headers.pop("xero-tenant-id", None)
elif "xero-tenant-id" not in headers:
	raise XeroAuthLost("Xero tenant is not configured; run the tenant discovery job first.")
if key is not None:
	if not key or len(key) > 128:
		raise XeroRejected("Xero idempotency key must contain 1 to 128 characters.")
	headers["Idempotency-Key"] = key
if modified_since:
	headers["If-Modified-Since"] = modified_since
try:
	response = requests.request(method, url, headers=headers, params=params,
		json=payload, timeout=HTTP_TIMEOUT, allow_redirects=False)
except requests.exceptions.RequestException:
	raise XeroTimeout("No reliable response from Xero; look up the record before retrying a write.") from None
```

## Câu trả lời được xếp vào bốn loại lỗi

Client không bao giờ để lọt một mã HTTP thô ra ngoài. Mỗi tình huống thành một class, và job quyết định theo class.

| Xero trả | Class | Nghĩa | Job làm (`06`) |
|---|---|---|---|
| không trả lời, đứt mạng, body không đọc được | `XeroTimeout` | **không biết** Xero đã làm hay chưa | ghi `Failed`; lần Retry sẽ tra cứu trước khi tạo |
| 401, 403 | `XeroAuthLost` | token hoặc quyền có vấn đề | ghi `Failed` kèm "reconnect Xero" |
| 429, 5xx (kèm `Retry-After` nếu có) | `XeroBusy(retry_after)` | Xero bận hoặc ta gọi quá nhiều | ghi `Failed` kèm "Retry after N seconds" |
| body có `ValidationErrors`, hoặc mã ngoài 2xx | `XeroRejected` | Xero từ chối dữ liệu này; gửi lại y nguyên sẽ lại hỏng | ghi `Failed` kèm **nguyên văn** lời của Xero |

```python
# integrations/xero/client.py:170-195  (trong _request, rút gọn)
if response.status_code in (401, 403):
	raise XeroAuthLost("Xero authorization was refused; check access and reconnect Xero.")
if response.status_code == 429 or response.status_code >= 500:
	retry_after = response.headers.get("Retry-After", "")
	raise XeroBusy(int(retry_after) if retry_after.isdigit() else None)
try:
	body = response.json()
except ValueError:
	raise XeroTimeout("Xero returned an unreadable response; look up before retrying a write.") from None
...
messages = _validation_messages(elements + rows)
if messages:
	raise XeroRejected("; ".join(messages))
if not 200 <= response.status_code < 300:
	raise XeroRejected(f"Xero refused the request (HTTP {response.status_code}).")
```

Nguyên tắc xuyên suốt: **dữ liệu thiếu hoặc lạ không bao giờ được coi là "không có" hay "bằng 0"**. Ví dụ một invoice thiếu `AmountDue` làm cả lần đọc hỏng (`XeroTimeout`), thay vì ghi 0 lên đơn.

## Danh sách các lời gọi

### 1. Hỏi tổ chức đã nối: `GET /connections`

| | |
|---|---|
| Mục đích | lấy `tenantId` để dùng cho mọi lời gọi sau |
| Gọi từ | `tasks/xero_sync.py: discover_tenant` → `client.get_connections()` |
| Request | `GET https://api.xero.com/connections`, chỉ có `Authorization`; **không** có `xero-tenant-id` |
| Ra (code đọc) | mảng; mỗi phần tử: `tenantId`, `tenantName`, `tenantType` (chỉ lấy `ORGANISATION`) |
| Ghi về | `Lab Xero Settings.tenant_id`, `.tenant_name` |
| Đã quan sát | `tenant_name` = "Demo Company (Global)" |

### 2. Tìm contact: `GET /Contacts?where=…`

| | |
|---|---|
| Mục đích | khách này đã có bên Xero chưa? (tra trước khi tạo) |
| Gọi từ | `_create_invoice` → `client.find_contact(customer.name)` |
| Request | `GET /Contacts?where=ContactNumber=="<mã Customer>"&page=1` |
| Ra | 0 dòng → `None`; đúng 1 dòng → `ContactID`; nhiều hơn 1 hoặc không khớp → `XeroRejected` |

```python
# integrations/xero/client.py:118-129
def _find(self, resource: str, field: str, value: str, id_field: str, extra: str = "") -> str | None:
	if not value:
		raise XeroRejected("A Xero lookup requires a nonempty identifier.")
	where = f"{field}=={json.dumps(value)}"
	if extra:
		where += " AND " + extra
	rows = self._request("GET", resource, resource, params={"where": where, "page": 1})
	if not rows:
		return None
	if len(rows) != 1 or not rows[0].get(id_field) or rows[0].get(field) != value:
		raise XeroRejected("Xero lookup did not return one matching record.")
	return rows[0][id_field]
```

`json.dumps(value)` bọc giá trị trong dấu nháy kép và thoát ký tự đặc biệt, nên tên khách có dấu nháy không phá câu lọc.

### 3. Tạo contact: `PUT /Contacts`

| | |
|---|---|
| Mục đích | tạo khách bên Xero, ở lần đầu khách đó có hóa đơn |
| Request | `PUT /Contacts`, header `Idempotency-Key: sha256("Customer:<mã>:create_contact")` |
| Body | `{"Contacts": [{"ContactNumber": "<mã Customer>", "Name": "<tên khách>"}]}` |
| Ra | `Contacts[0].ContactID` |
| Ghi về | `Customer.lab_xero_contact_id` |
| Đã quan sát | Customer "West View Software Ltd." có contact id sau đơn đầu tiên |

```python
# lab_xero/mapping.py:9-12
def customer_to_contact(customer: Document) -> dict:
	if not customer.name or not customer.customer_name:
		frappe.throw(_("Customer code and name are required for Xero."))
	return {"ContactNumber": customer.name, "Name": customer.customer_name}
```

- `ContactNumber` = **mã của Customer trong ERPNext** (tên bản ghi). Đây là tay nắm để tìm lại.
- `Name` phải là duy nhất trong tổ chức Xero; trùng tên một contact có sẵn thì Xero từ chối.

### 4. Tìm invoice: `GET /Invoices?where=…`

| | |
|---|---|
| Mục đích | đơn này đã có hóa đơn bên Xero chưa? Đây là lớp chống tạo trùng chính |
| Gọi từ | `_find_invoice` → `client.find_invoice(doc.name)` |
| Request | `GET /Invoices?where=InvoiceNumber=="<tên Sales Order>" AND Type=="ACCREC"&page=1` |
| Ra | `None` hoặc `InvoiceID` |

### 5. Tạo invoice: `PUT /Invoices?unitdp=4`

| | |
|---|---|
| Mục đích | phát hành hóa đơn bán cho đơn hàng |
| Request | `PUT /Invoices?unitdp=4`, header `Idempotency-Key: sha256("<key của dòng outbox>")` |
| Ra | `Invoices[0].InvoiceID` |
| Đã quan sát | `SAL-ORD-2026-00007` → một `InvoiceID`, trạng thái `AUTHORISED`, còn nợ 1000 |

Body, dựng bởi `lab_xero/mapping.py`:

```python
# lab_xero/mapping.py:30-41
date = getdate(doc.transaction_date).isoformat()
return {
	"Type": "ACCREC",
	"Contact": {"ContactID": contact_id},
	"InvoiceNumber": doc.name,
	"Date": date,
	"DueDate": date,
	"CurrencyCode": doc.currency,
	"LineAmountTypes": "Exclusive",
	"Status": "AUTHORISED",
	"LineItems": [_line_item(item, settings) for item in doc.items],
}
```

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

| Field | Giá trị trong demo | Vì sao |
|---|---|---|
| `Type` | `ACCREC` | hóa đơn bán (phải thu) |
| `InvoiceNumber` | tên Sales Order | để tìm lại ở lời gọi 4 |
| `Date`, `DueDate` | ngày của đơn | demo: hạn trả bằng ngày đơn |
| `CurrencyCode` | tiền tệ của đơn (THB) | tiền tệ này phải được bật trong tổ chức Xero |
| `LineAmountTypes` | `Exclusive` | đơn giá chưa gồm thuế |
| `Status` | `AUTHORISED` | đã duyệt ngay, để trả tiền và áp credit note được |
| `AccountCode` | `200` (từ Settings) | tài khoản doanh thu "Sales" của Demo Company |
| `TaxType` | `NONE` (từ Settings) | "Tax Exempt", 0% |

Không gửi tổng tiền và thuế: Xero tự tính từ các dòng. `unitdp=4` cho phép đơn giá tới bốn chữ số thập phân.

`PUT` chứ không phải `POST`: với Xero, `PUT` luôn tạo mới; `POST` có thể **cập nhật** một bản ghi đã có. Dùng `PUT` để một lỗi của ta không vô tình ghi đè hóa đơn cũ.

```python
# integrations/xero/client.py:131-137
def _create(self, resource: str, id_field: str, key: str, payload: dict) -> str:
	# PUT creates; POST may update an existing record. The job must look up before creating.
	params = {"unitdp": 4} if resource == "Invoices" else None
	rows = self._request("PUT", resource, resource, key=key, payload={resource: [payload]}, params=params)
	if len(rows) != 1 or not rows[0].get(id_field):
		raise XeroTimeout("Xero did not confirm the created record; look it up before retrying.")
	return rows[0][id_field]
```

### 6. Đọc invoice theo id: `GET /Invoices?IDs=…`

| | |
|---|---|
| Mục đích | lấy trạng thái và số tiền hiện tại của hóa đơn |
| Gọi từ | ngay sau khi tạo (`_read_invoice`); nút Refresh (`pull_sales_order`); lần kéo đầu tiên |
| Request | `GET /Invoices?where=Type=="ACCREC"&IDs=<id1>,<id2>&page=1`, rồi `page=2`… tới khi trang rỗng |
| Ra (code đọc) | `InvoiceID`, `InvoiceNumber`, `Status`, `AmountDue`, `AmountPaid`, `AmountCredited` |
| Ghi về | sáu field `lab_xero_*` trên Sales Order |

```python
# integrations/xero/client.py:89-104
def get_invoices(self, ids: list[str] | None = None, modified_since: str | None = None) -> list[dict]:
	"""modified_since must be an ISO UTC timestamp, not the site's local time."""
	if ids is not None and modified_since is not None:
		raise XeroRejected("Use invoice IDs or modified_since, not both.")
	if ids == []:
		return []
	params = {"where": 'Type=="ACCREC"'}
	if ids is not None:
		params["IDs"] = ",".join(ids)
	rows = self._pages("Invoices", params, modified_since)
	try:
		return [{"id": row["InvoiceID"], "number": row["InvoiceNumber"], "status": row["Status"],
			"amount_due": row["AmountDue"], "amount_paid": row["AmountPaid"],
			"amount_credited": row["AmountCredited"]} for row in rows]
	except KeyError:
		raise XeroTimeout("Xero returned incomplete invoice data; no amounts should be saved.") from None
```

`ids == []` trả về rỗng ngay: một danh sách id rỗng **không** được hiểu là "lấy tất cả".

### 7. Đọc invoice đã đổi: `GET /Invoices` + `If-Modified-Since`

| | |
|---|---|
| Mục đích | chỉ lấy những hóa đơn đã đổi kể từ lần kéo trước (tiết kiệm lời gọi) |
| Gọi từ | `tasks/xero_pull.py: pull_changes`, do scheduler chạy |
| Request | như lời gọi 6 nhưng không có `IDs`, thêm header `If-Modified-Since: 2026-10-12T07:46:03` (giờ UTC) |
| Đã quan sát | `Lab Xero Settings.last_pull_at` tiến đều (ví dụ 14:48, 14:52) |

### 8. Đọc credit note: `GET /CreditNotes`

| | |
|---|---|
| Mục đích | tìm các credit note kế toán đã tạo trong Xero và đã áp vào hóa đơn của ta |
| Request | `GET /CreditNotes?where=Type=="ACCRECCREDIT"&page=N`, có hoặc không có `If-Modified-Since` |
| Ra (code đọc) | `CreditNoteID`, `CreditNoteNumber`, `Status`, `Date`, `Total`, và `Allocations[]` với `Invoice.InvoiceID`, `Amount` (bỏ qua cái có `IsDeleted`) |
| Ghi về | một dòng `Lab Xero Credit Note` + một comment trên Sales Order |
| Chưa thử | chưa có credit note thật nào đi qua |

Ngày của Xero có dạng lạ, `"/Date(1760140800000+0000)/"` (số mili giây từ 1970). Client đổi về `YYYY-MM-DD`:

```python
# integrations/xero/client.py:217-224
def _xero_date(value: str) -> str:
	match = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", value)
	if match:
		value = add_to_date("1970-01-01 00:00:00", seconds=int(match[1]) / 1000, as_string=True)
	date = getdate(value)
	if date is None:
		raise ValueError("Invalid Xero date")
	return date.isoformat()
```

### 9. Void invoice: `GET` rồi `POST /Invoices/{id}`

| | |
|---|---|
| Mục đích | hủy hiệu lực hóa đơn khi Sales Order bị cancel |
| Request 1 | `GET /Invoices/<InvoiceID>`: nếu đã `VOIDED` thì dừng, không gọi tiếp |
| Request 2 | `POST /Invoices/<InvoiceID>`, body `{"Invoices": [{"InvoiceID": "<id>", "Status": "VOIDED"}]}`, có `Idempotency-Key` |
| Ra | `Invoices[0].Status` phải là `VOIDED` |
| Chưa thử | chưa cancel đơn nào đã sync |

```python
# integrations/xero/client.py:77-87
def void_invoice(self, key: str, invoice_id: str) -> None:
	path = "Invoices/" + quote(invoice_id, safe="")
	rows = self._request("GET", path, "Invoices")
	if len(rows) != 1 or rows[0].get("InvoiceID") != invoice_id:
		raise XeroRejected("Xero invoice was not found.")
	if rows[0].get("Status") == "VOIDED":
		return
	rows = self._request("POST", path, "Invoices", key=key,
		payload={"Invoices": [{"InvoiceID": invoice_id, "Status": "VOIDED"}]})
	if len(rows) != 1 or rows[0].get("Status") != "VOIDED":
		raise XeroTimeout("Xero did not confirm that the invoice was voided; look it up before retrying.")
```

Đây là chỗ duy nhất dùng `POST` (cập nhật), vì void chính là sửa trạng thái của một bản ghi đã có. Xero không cho void một hóa đơn đã có payment hoặc credit; khi đó Xero trả lỗi validation → `XeroRejected` → đơn báo `Failed` kèm lý do.

## Một lần submit tốn mấy lời gọi

| Tình huống | Lời gọi | Số |
|---|---|---|
| Khách mới, đơn mới | tìm invoice, tìm contact, tạo contact, tạo invoice, đọc invoice | 5 |
| Khách đã có, đơn mới | tìm invoice, tìm contact, tạo invoice, đọc invoice | 4 |
| Retry sau khi Xero đã tạo xong | tìm invoice, đọc invoice | 2 |
| Một lượt kéo theo lịch, không có gì đổi | invoice đã đổi, credit note đã đổi | 2 (cộng 1 nếu có credit note mới) |
| Nút Refresh | đọc invoice theo id, đọc mọi credit note | 2 trở lên |

Giới hạn của bậc miễn phí: 60 lời gọi mỗi phút và 1000 mỗi ngày cho mỗi tổ chức (nguồn: trang giá và FAQ của Xero, `docs/xero/03`). Lịch kéo 5 phút tốn khoảng 580 lời gọi mỗi ngày, nên còn chỗ cho vài chục đơn. Đừng rút ngắn lịch kéo.

## Idempotency-Key: nó giúp tới đâu

```python
# tasks/xero_sync.py:178-179
def _key(value: str) -> str:
	return sha256(value.encode()).hexdigest()
```

Key gốc là `"Sales Order:<tên đơn>:create_invoice"`. Nó được băm thành 64 ký tự hex vì Xero giới hạn key ở 128 ký tự và tên có thể dài hoặc có ký tự lạ.

Xero chỉ nhớ một key trong khoảng 6 phút (trích đoạn tài liệu Xero, `docs/xero/03`). Vì vậy key chỉ che được lần gửi lại tức thì. Thứ thật sự chống tạo trùng là lời gọi 4: **luôn tìm theo số hóa đơn trước khi tạo**.
