# 04. Cơ sở dữ liệu: cái gì nằm ở đâu, luồng nào ghi gì

Phần tích hợp thêm vào database ba thứ: **ba DocType mới**, **mười một field trên hai DocType của ERPNext**, và **dùng lại hai DocType có sẵn của Frappe** cho OAuth. Bí mật nằm ngoài database, trong site config.

Trong Frappe, một DocType = một bảng (tên bảng là `tab<Tên DocType>`) + form + phân quyền. Bảng nào cũng có sẵn các cột `name` (khóa chính), `creation`, `modified`, `owner`, `docstatus`.

## Bản đồ

```text
                      ┌──────────────────────────┐
                      │ Lab Xero Settings (1 bản) │  connected_app ──► Connected App "xero" ──► Token Cache "xero-Administrator"
                      │  tenant_id, mã tài khoản, │  connected_user                              (access_token, refresh_token,
                      │  mã thuế, last_pull_at    │                                               expires_in, state)
                      └──────────────────────────┘

 Customer ──────────────── lab_xero_contact_id  = ContactID bên Xero
     ▲
     │ customer
 Sales Order ───────────── lab_xero_invoice_id  = InvoiceID bên Xero
     ▲   ▲                 lab_xero_sync_status, _invoice_status, _amount_due / _paid / _credited, _error …
     │   │
     │   └── Lab Xero Outbox        (reference_name → Sales Order)      "việc cần gửi sang Xero"
     └────── Lab Xero Credit Note   (sales_order → Sales Order)         "credit note Xero đã áp vào hóa đơn của đơn này"
```

## 1. Ba DocType mới (module `Lab Xero`)

File định nghĩa: `lab_xero/doctype/<tên>/<tên>.json`. Chúng vào database khi chạy `bench migrate`.

### `Lab Xero Outbox`: hộp thư đi

Mỗi dòng nói "việc này còn phải làm bên Xero". Nó được ghi **cùng transaction** với lần submit đơn, nên hoặc cả hai tồn tại, hoặc không cái nào.

| Field | Kiểu | Chứa gì |
|---|---|---|
| `reference_doctype` | Link → DocType | luôn là `Sales Order` |
| `reference_name` | Dynamic Link | tên đơn, ví dụ `SAL-ORD-2026-00007` |
| `operation` | Data | `create_invoice` hoặc `void_invoice` |
| `idempotency_key` | Data, **unique** | `Sales Order:<tên đơn>:<operation>` |
| `status` | Select | `Pending` → `Done` hoặc `Failed` |
| `attempts` | Int | số lần job đã thử |
| `error` | Small Text | lý do thất bại lần gần nhất |
| `xero_id` | Data | `InvoiceID` khi xong |

Ràng buộc `unique` trên `idempotency_key` là chốt chặn cuối: không thể có hai dòng cho cùng một đơn và cùng một việc.

Dữ liệu thật (đã quan sát):

| `reference_name` | `operation` | `status` | `attempts` | `error` |
|---|---|---|---|---|
| `SAL-ORD-2026-00007` | `create_invoice` | `Done` | 2 | — |
| `SAL-ORD-2026-00006` | `create_invoice` | `Failed` | 1 | The Xero demo supports Sales Order lines without discounts. |

Dòng đầu có `attempts` = 2: lần một hỏng (thiếu mô tả dòng hàng), sửa code, bấm Retry, lần hai xong. **Cùng một dòng** được mở lại, không sinh dòng mới.

### `Lab Xero Settings`: cấu hình, một bản ghi duy nhất

"Single" DocType: không có nhiều dòng, chỉ một bộ giá trị.

| Field | Kiểu | Chứa gì | Ai ghi |
|---|---|---|---|
| `connected_app` | Link → Connected App | `xero` | code setup, khi migrate |
| `connected_user` | Link → User | `Administrator` (người đã bấm Connect) | code setup |
| `tenant_id` | Data | id của tổ chức Xero | job `discover_tenant` |
| `tenant_name` | Data | "Demo Company (Global)" | job `discover_tenant` |
| `default_account_code` | Data | `200` | code setup |
| `default_tax_type` | Data | `NONE` | code setup |
| `last_pull_at` | Datetime | lần kéo dữ liệu thành công gần nhất | job `pull_changes` |

### `Lab Xero Credit Note`: credit note từ Xero

Mỗi dòng là một credit note mà kế toán đã tạo trong Xero **và đã áp vào hóa đơn của một Sales Order của ta**.

| Field | Kiểu | Chứa gì |
|---|---|---|
| `sales_order` | Link → Sales Order | đơn được hưởng |
| `xero_credit_note_id` | Data, **unique** | `CreditNoteID` bên Xero |
| `credit_note_number` | Data | số credit note |
| `xero_invoice_id` | Data | hóa đơn mà nó được áp vào |
| `date` | Date | ngày credit note |
| `total` | Currency | tổng giá trị credit note |
| `allocated_amount` | Currency | phần đã áp vào hóa đơn này |
| `status` | Data | trạng thái bên Xero |

`unique` trên `xero_credit_note_id` + "tìm trước, có thì cập nhật" làm cho việc kéo lại không sinh dòng trùng. Bảng này hiện còn trống: chưa có credit note thật nào đi qua.

## 2. Field thêm vào DocType của ERPNext

Ta không sửa file của ERPNext. Các field được thêm bằng **Custom Field** tạo từ code, chạy sau mỗi lần migrate:

```python
# setup/customizations.py:6-34
def apply() -> None:
	"""Create or update the demo fields without copying Xero identities on amend."""
	create_custom_fields(
		{
			"Customer": [
				_field("lab_xero_contact_id", "Xero Contact ID", "Data", "customer_name", unique=1),
			],
			"Sales Order": [
				_field("lab_xero_section", "Xero", "Section Break", "amended_from"),
				_field(
					"lab_xero_sync_status",
					"Xero Sync Status",
					"Select",
					"lab_xero_section",
					options="Not Synced\nQueued\nSynced\nFailed",
					default="Not Synced",
				),
				_field("lab_xero_invoice_id", "Xero Invoice ID", "Data", "lab_xero_sync_status", unique=1),
				...
			],
		},
		update=True,
	)
```

```python
# setup/customizations.py:37-47
def _field(fieldname: str, label: str, fieldtype: str, insert_after: str, **properties) -> dict:
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"insert_after": insert_after,
		"read_only": 1,
		"no_copy": 1,
		"allow_on_submit": 1,
		**properties,
	}
```

Ba thuộc tính áp cho mọi field, và lý do:

| Thuộc tính | Nghĩa | Vì sao cần |
|---|---|---|
| `read_only` | người dùng không gõ được | chỉ job được ghi; các số này là của Xero |
| `no_copy` | không mang theo khi nhân bản hay amend đơn | đơn mới không được thừa hưởng `InvoiceID` của đơn cũ |
| `allow_on_submit` | được đổi sau khi đơn đã submit | job ghi kết quả **sau** submit; không có nó thì Frappe từ chối |

Danh sách đầy đủ:

| DocType | Field | Kiểu | Chứa gì |
|---|---|---|---|
| Customer | `lab_xero_contact_id` | Data, unique | `ContactID` bên Xero |
| Sales Order | `lab_xero_sync_status` | Select | `Not Synced` / `Queued` / `Synced` / `Failed`: trạng thái **việc gửi đi** |
| | `lab_xero_invoice_id` | Data, unique | `InvoiceID` |
| | `lab_xero_invoice_number` | Data | số hóa đơn (bằng tên đơn) |
| | `lab_xero_invoice_status` | Data | trạng thái **của Xero**: `AUTHORISED`, `PAID`, `VOIDED`… |
| | `lab_xero_amount_due` | Currency | còn nợ, theo Xero |
| | `lab_xero_amount_paid` | Currency | đã trả, theo Xero |
| | `lab_xero_amount_credited` | Currency | đã ghi giảm, theo Xero |
| | `lab_xero_last_synced_at` | Datetime | lần cuối chép số liệu từ Xero |
| | `lab_xero_error` | Small Text | lý do thất bại, đọc được |

Đừng lẫn hai trạng thái: `lab_xero_sync_status` là của **ta** (việc gửi đã xong chưa), `lab_xero_invoice_status` là của **Xero** (hóa đơn đang ở đâu trong vòng đời).

Dữ liệu thật (đã quan sát):

| Đơn | `sync_status` | `invoice_status` | `amount_due` | `amount_paid` | `error` |
|---|---|---|---|---|---|
| `SAL-ORD-2026-00007` | `Synced` | `AUTHORISED` | 1000.0 | 0.0 | — |
| `SAL-ORD-2026-00008` | `Synced` | `AUTHORISED` | 500.0 | 0.0 | — |
| `SAL-ORD-2026-00006` | `Failed` | — | 0.0 | 0.0 | …lines without discounts. |

Hai đơn 00007 và 00008 cùng thuộc Customer "West View Software Ltd.", và Customer đó có đúng một `lab_xero_contact_id`: **một khách, một contact, nhiều hóa đơn**.

## 3. DocType có sẵn của Frappe mà ta dùng

| DocType | Ta dùng để | Ghi bởi |
|---|---|---|
| `Connected App` (bản ghi tên `xero`) | cấu hình OAuth: `client_id`, `client_secret` (Password), hai URI, scope, `redirect_uri` | code setup |
| `Token Cache` (bản ghi tên `xero-Administrator`) | `access_token`, `refresh_token` (Password, mã hóa), `expires_in`, `state` | Frappe, khi Connect và khi refresh |
| `Error Log` | lỗi của job, kèm traceback | Frappe và `frappe.log_error` của ta |
| `Comment` | dòng timeline "Xero credit note …" trên Sales Order | `lab_xero/inbound.py` |
| `Scheduled Job Type` | dòng lịch cho `pull_changes` | Frappe, từ `hooks.py` khi migrate |

## 4. Thứ không nằm trong database: site config

Năm giá trị do con người đặt bằng lệnh `bench set-config`, code đọc bằng `frappe.conf`:

| Key | Chứa gì | Bí mật? |
|---|---|---|
| `xero_client_id` | id của app Xero | không |
| `xero_client_secret` | secret của app Xero | **có** |
| `xero_connected_user` | user Frappe đã bấm Connect | không |
| `xero_default_account_code` | `200` | không |
| `xero_default_tax_type` | `NONE` | không |
| `host_name` | `http://localhost:8000` (để Redirect URI dùng `localhost`) | không |

Vì sao tách: file site config nằm ngoài repo và ngoài tầm đọc của agent. Code setup chép chúng vào Connected App và Settings khi migrate, nên dựng lại database vẫn có lại cấu hình mà không ai phải gõ tay trong Desk.

```python
# setup/xero_connection.py:27-36
def _read_config() -> dict:
	keys = ("xero_client_id", "xero_client_secret", *SETTINGS_CONFIG.values())
	values = {}
	for key in keys:
		value = frappe.conf.get(key)
		if value is None or value == "":
			print(f"[xero setup] Missing site config: {key}; skipping that configuration.")
		else:
			values[key] = value
	return values
```

## 5. Luồng nào ghi gì, và trong transaction nào

| Lúc | Transaction của | Bảng bị ghi |
|---|---|---|
| `bench migrate` | lệnh migrate | Connected App, Lab Xero Settings, Custom Field |
| Bấm Connect | request của Frappe (tự commit) | Token Cache |
| Job `discover_tenant` | job đó | Lab Xero Settings (`tenant_id`, `tenant_name`) |
| **Submit Sales Order** | **request submit** | Sales Order (`sync_status` = `Queued`), **Lab Xero Outbox** (1 dòng `Pending`) |
| Job `process_outbox`, thành công | job đó | Customer (`contact_id`), Sales Order (6 field), Lab Xero Outbox (`Done`) |
| Job `process_outbox`, thất bại | rollback, rồi một transaction nhỏ riêng | Lab Xero Outbox (`Failed`, `error`), Sales Order (`Failed`, `lab_xero_error`), Error Log |
| Bấm Retry | request đó | Sales Order (`Queued`), Lab Xero Outbox (mở lại `Pending`) |
| Job `pull_changes` / `pull_sales_order` | job đó | Sales Order (6 field), Lab Xero Credit Note, Comment, Lab Xero Settings (`last_pull_at`) |
| Làm mới token | trong job, **tự commit** | Token Cache |

Điểm cần nhớ nhất: **dòng outbox và đơn hàng được lưu trong cùng một transaction**. Không thể có một đơn đã submit mà thiếu dòng outbox của nó.

## 6. Cùng một sự thật, hai nơi lưu

| Sự thật | Bên giữ bản gốc | Bản sao ở bên kia | Nối bằng |
|---|---|---|---|
| Khách hàng | ERPNext `Customer` | Xero Contact | `Customer.name` = `ContactNumber`; `lab_xero_contact_id` = `ContactID` |
| Đơn hàng (dòng hàng, số lượng, giá) | ERPNext `Sales Order` | các dòng của Xero Invoice, gửi **một lần** | `Sales Order.name` = `InvoiceNumber`; `lab_xero_invoice_id` = `InvoiceID` |
| Hóa đơn (trạng thái, đã trả, còn nợ, đã ghi giảm) | **Xero** | các field `lab_xero_*` trên Sales Order | `InvoiceID` |
| Credit note | **Xero** | `Lab Xero Credit Note` | `CreditNoteID`; allocation → `InvoiceID` |
