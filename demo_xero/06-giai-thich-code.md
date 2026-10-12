# 06. Giải thích code: từng file, từng hàm, và transaction

Đi theo đúng thứ tự một đơn hàng đi qua hệ thống. Mỗi đoạn trích là code thật, có `file:dòng`. Client HTTP và OAuth đã có ở `03` và `02`; file này tập trung vào phần còn lại và vào câu hỏi "hỏng giữa chừng thì sao".

## Ý tưởng gốc, trước khi đọc code

Database của ta và Xero **không thể dùng chung một transaction**. Nếu gọi Xero ngay trong lúc submit thì có hai cách hỏng tệ: người dùng ngồi chờ Xero, và nếu Xero tạo xong mà lần lưu của ta hỏng thì Xero có hóa đơn còn ERPNext không có đơn.

Cách của ta: lúc submit **chỉ ghi lại ý định** (một dòng outbox) cùng với đơn hàng. Một job chạy sau làm việc thật, và nó được viết để **chạy lại bao nhiêu lần cũng ra một kết quả**.

```text
 TRONG TRANSACTION CỦA LẦN SUBMIT          │   SAU COMMIT (người dùng đã nhận "OK")
  ERPNext lưu đơn                          │   job process_outbox  (transaction RIÊNG)
  handler của ta: Queued + dòng outbox     │     gọi Xero, ghi kết quả
  hỏng ở đây → rollback tất cả             │   hỏng ở đây → đơn KHÔNG bị kéo lùi;
  người dùng thấy lỗi ngay                 │     dòng outbox + trạng thái trên đơn nói điều gì đã xảy ra
                                    COMMIT ┘
```

## Bước 1. Submit: `overrides/sales_order.py`

Frappe gọi hàm này sau code `on_submit` của ERPNext, trong cùng transaction (nối bằng `doc_events` trong `hooks.py`).

```python
# overrides/sales_order.py:12-16
def on_submit(doc: Document, method: str | None = None) -> None:
	if doc.docstatus != 1:
		return
	doc.db_set({"lab_xero_sync_status": "Queued", "lab_xero_error": None})
	outbox.queue(doc, operation="create_invoice")
```

- Chỉ hai việc: đánh dấu `Queued`, ghi dòng outbox. Không gọi Xero.
- `db_set` thay cho `save`: đơn đã submit, chỉ các field `allow_on_submit` được đổi, và `db_set` ghi thẳng field đó.
- Nếu `outbox.queue` ném lỗi, cả lần submit bị hủy. Đó là chủ đích: không có đơn đã submit mà thiếu dòng outbox.

Cancel đi qua cùng file, có thêm một luật nghiệp vụ:

```python
# overrides/sales_order.py:19-34
def on_cancel(doc: Document, method: str | None = None) -> None:
	if doc.docstatus != 2:
		return
	if flt(doc.lab_xero_amount_paid, doc.precision("lab_xero_amount_paid")) > 0:
		frappe.throw(
			_("Cannot cancel Sales Order {0}: its Xero invoice has payments applied.").format(doc.name),
			LabConflictError,
		)
	if flt(doc.lab_xero_amount_credited, doc.precision("lab_xero_amount_credited")) > 0:
		frappe.throw(
			_("Cannot cancel Sales Order {0}: its Xero invoice has credit applied.").format(doc.name),
			LabConflictError,
		)

	doc.db_set({"lab_xero_sync_status": "Queued", "lab_xero_error": None})
	outbox.queue(doc, operation="void_invoice")
```

- Hóa đơn đã có tiền trả hoặc đã bị ghi giảm thì **chặn cancel** bằng lỗi 409: ta không tự gỡ tiền của kế toán.
- Phép kiểm dùng số liệu đã lưu trên đơn, không gọi Xero trong request. Số liệu đó có thể cũ; nếu vậy Xero sẽ từ chối void ở bước sau và đơn báo `Failed` kèm lý do.
- `flt(value, precision)`: so sánh tiền luôn làm tròn theo độ chính xác của field, không so số thực thô.

## Bước 2. Ghi ý định: `lab_xero/outbox.py`

```python
# lab_xero/outbox.py:10-41
def queue(doc, operation: str = "create_invoice") -> str:
	"""Write (or reopen) the outbox row for this document and queue the job. Return the row's name.

	The idempotency key is fixed per document and operation, so a retry reuses the same row
	and Xero sees the same key.
	"""
	key = f"{doc.doctype}:{doc.name}:{operation}"
	name = frappe.db.exists(OUTBOX, {"idempotency_key": key})
	if name:
		outbox = frappe.get_doc(OUTBOX, name, for_update=True)
		outbox.status = "Pending"
		outbox.error = None
		outbox.save()
	else:
		outbox = frappe.new_doc(OUTBOX)
		outbox.reference_doctype = doc.doctype
		outbox.reference_name = doc.name
		outbox.operation = operation
		outbox.idempotency_key = key
		outbox.status = "Pending"
		outbox.insert()

	# After the commit: the worker must be able to see the row and the document.
	frappe.enqueue(
		SYNC_JOB,
		queue="default",
		enqueue_after_commit=True,
		job_id=f"lab-xero-sync:{outbox.name}",
		deduplicate=True,
		outbox_name=outbox.name,
	)
	return outbox.name
```

| Dòng | Làm gì | Vì sao |
|---|---|---|
| `key = …` | khóa cố định cho mỗi (đơn, việc) | gọi lại vẫn ra cùng một dòng |
| `if name:` | đã có dòng → mở lại thành `Pending` | Retry dùng lại dòng cũ, `attempts` cộng dồn |
| `else:` | chưa có → tạo dòng | field `idempotency_key` là unique: hai request chen nhau thì cái thứ hai bị database từ chối |
| `enqueue_after_commit=True` | job chỉ được đẩy đi **sau khi** request commit | nếu đẩy ngay, worker có thể chạy trước và không thấy dòng outbox |
| `job_id` + `deduplicate` | không xếp hai job giống nhau cùng lúc | gọn hàng đợi; đây chưa phải lớp an toàn chính |

## Bước 3. Job chiều đi: `tasks/xero_sync.py`

### Khung của job

```python
# tasks/xero_sync.py:45-72
def process_outbox(outbox_name: str) -> None:
	if frappe.get_doc(OUTBOX, outbox_name, check_permission="write").status == "Done":
		return
	try:
		client = get_client()  # Refresh before any lock or business write: refresh may commit.
		outbox = frappe.get_doc(OUTBOX, outbox_name, for_update=True, check_permission="write")
		if outbox.status == "Done":
			return
		if outbox.reference_doctype != "Sales Order":
			frappe.throw(_("Only Sales Orders are supported by the Xero outbox."))
		doc = frappe.get_doc("Sales Order", outbox.reference_name, for_update=True, check_permission="write")
		outbox.attempts = cint(outbox.attempts) + 1
		if outbox.operation == "create_invoice":
			invoice_id = _create_invoice(client, doc, outbox.idempotency_key)
		elif outbox.operation == "void_invoice":
			invoice_id = _void_invoice(client, doc, outbox.idempotency_key)
		else:
			frappe.throw(_("Unsupported Xero outbox operation: {0}.").format(outbox.operation))
		outbox.status = "Done"
		outbox.xero_id = invoice_id
		outbox.error = None
		outbox.save()
	except Exception as error:
		# Remote writes cannot roll back. Retry recovers them by number before creating.
		frappe.db.rollback()
		_record_failure(outbox_name, _failure_reason(error))
		frappe.log_error(title="Xero outbound sync failed", message="Sales Order sync failed; see the outbox error and retry after correcting it.")
		raise
```

Đọc từ trên xuống, mỗi dòng có một lý do:

1. **`Done` thì thôi** (hai lần: trước và sau khi khóa). Job trùng không làm gì.
2. **`get_client()` đi trước mọi thứ.** Lấy token có thể làm Frappe refresh và **tự commit**. Nếu đã khóa dòng hay ghi gì đó trước, commit ấy sẽ nhả khóa và lưu nửa chừng.
3. **`for_update=True` trên dòng outbox**: khóa dòng. Job thứ hai cho cùng dòng phải đứng chờ; khi tới lượt, nó thấy `Done` và thoát.
4. **`for_update=True` trên Sales Order**: việc tạo và việc void của cùng một đơn không chạy chồng nhau.
5. **Rẽ theo `operation`.**
6. **Thành công**: ghi `Done` và id. Job return bình thường, Frappe commit.
7. **Bất kỳ lỗi nào**: rollback, ghi lại thất bại bằng một transaction riêng, ghi Error Log, rồi **ném lại** để Frappe biết job hỏng.

### Tạo hóa đơn

```python
# tasks/xero_sync.py:75-98
def _create_invoice(client: XeroClient, doc: Document, key: str) -> str | None:
	if doc.docstatus == 2:
		return None  # Cancel won before this job: leave the void job's status alone.
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted Sales Order can create a Xero invoice."))
	invoice_id = _find_invoice(client, doc)
	if not invoice_id:
		settings = frappe.get_doc("Lab Xero Settings")
		customer = frappe.get_doc("Customer", doc.customer, for_update=True, check_permission="write")
		# Validate the invoice before creating a contact in Xero.
		payload = sales_order_to_invoice(doc, "pending-contact", settings)
		contact_id = client.find_contact(customer.name)
		if customer.lab_xero_contact_id and customer.lab_xero_contact_id != contact_id:
			frappe.throw(_("The saved Xero contact does not match the Customer lookup."))
		if not contact_id:
			contact_id = client.create_contact(_key(f"Customer:{customer.name}:create_contact"), customer_to_contact(customer))
		customer.db_set("lab_xero_contact_id", contact_id)
		payload["Contact"]["ContactID"] = contact_id
		invoice_id = client.create_invoice(_key(key), payload)
	invoice = _read_invoice(client, doc, invoice_id)
	if invoice["status"] not in ("AUTHORISED", "PAID"):
		frappe.throw(_("The Xero invoice is not approved or paid; its state is outside this demo."))
	_save_invoice(doc, invoice)
	return invoice_id
```

Thứ tự này là trái tim của việc "chạy lại vẫn đúng":

```text
 ① hóa đơn mang số của đơn này đã có bên Xero chưa?   (_find_invoice)
        có  ─────────────────────────────────────────────────────────────┐
        chưa                                                             │
 ② dựng thử payload hóa đơn TRƯỚC  (mapping kiểm mọi luật: thuế, discount…)  │  → dữ liệu sai thì dừng ở đây,
 ③ khách này đã có bên Xero chưa?  (find_contact theo mã Customer)        │    chưa có gì được tạo bên Xero
        chưa → tạo contact                                                │
 ④ lưu contact id lên Customer                                            │
 ⑤ tạo hóa đơn                                                            │
 ⑥ đọc lại hóa đơn từ Xero  ◄─────────────────────────────────────────────┘
 ⑦ chép trạng thái và số tiền của Xero lên đơn
```

- **Bước ① trả lời tình huống khó nhất**: lần trước Xero đã tạo xong nhưng câu trả lời không về tới ta (timeout, job chết). Lần chạy lại thấy hóa đơn đã có, bỏ qua ②–⑤ và chỉ đọc lại.
- **Bước ② đứng trước ③** để một đơn sai luật không để lại một contact mồ côi bên Xero.
- **Một khách, nhiều hóa đơn**: ở đơn thứ hai của cùng khách, bước ③ tìm thấy contact cũ và dùng lại.
- **Bước ⑥–⑦**: số tiền trên đơn luôn là số **Xero trả về**, không tự tính.

Hai phép đối chiếu chống "gắn nhầm":

```python
# tasks/xero_sync.py:117-128
def _find_invoice(client: XeroClient, doc: Document) -> str | None:
	invoice_id = client.find_invoice(doc.name)
	if doc.lab_xero_invoice_id and doc.lab_xero_invoice_id != invoice_id:
		frappe.throw(_("The saved Xero invoice does not match the Sales Order number lookup."))
	return invoice_id


def _read_invoice(client: XeroClient, doc: Document, invoice_id: str) -> dict:
	rows = client.get_invoices(ids=[invoice_id])
	if len(rows) != 1 or rows[0]["id"] != invoice_id or rows[0]["number"] != doc.name:
		raise XeroRejected("Xero did not return the invoice belonging to this Sales Order.")
	return rows[0]
```

Nếu id đã lưu và kết quả tra cứu không khớp, job **dừng và báo**, không đoán bên nào đúng.

### Các luật của mapping: `lab_xero/mapping.py`

```python
# lab_xero/mapping.py:15-28
def sales_order_to_invoice(doc: Document, contact_id: str, settings: Document) -> dict:
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted Sales Order can create a Xero invoice."))
	if not contact_id or not doc.currency or not doc.transaction_date or not doc.items:
		frappe.throw(_("Contact, currency, order date and lines are required for Xero."))
	if not settings.default_account_code or not settings.default_tax_type:
		frappe.throw(_("Set the Xero revenue account and tax type before syncing."))
	if doc.taxes:
		frappe.throw(_("The Xero demo supports Sales Orders without ERPNext taxes or charges."))
	if _has_discount(doc):
		frappe.throw(_("The Xero demo supports Sales Orders without discounts."))
	company = frappe.get_doc("Company", doc.company, check_permission="read")
	if doc.currency != company.default_currency:
		frappe.throw(_("The Xero demo requires the Sales Order to use the Company currency."))
```

Mỗi `frappe.throw` là một luật của demo được viết thành code. Câu trong ngoặc là thứ người dùng sẽ đọc trong ô `Xero Error`. Đã quan sát hai câu chạy thật:

| Đơn | Lỗi hiện trên đơn | Nguyên nhân thật |
|---|---|---|
| `SAL-ORD-2026-00006` | "The Xero demo supports Sales Order lines without discounts." | gõ giá 100 trong khi giá niêm yết 500 → ERPNext ghi discount 400 |
| `SAL-ORD-2026-00007` (lần đầu) | "Xero invoice lines require a description, positive quantity and nonnegative rate." | item "Book" không có mô tả |

Lỗi thứ hai là một bug thật, đã sửa: khi mô tả trống thì dùng tên item.

```python
# lab_xero/mapping.py:52-57
quantity = flt(item.qty, item.precision("qty"))
rate = flt(item.rate, min(item.precision("rate") or 2, 4))
# Many items have no description; the item name (or code) is what the customer should read then.
description = strip_html(item.description or "").strip() or (item.item_name or item.item_code or "").strip()
if quantity <= 0 or rate < 0 or not description:
	frappe.throw(_("Xero invoice lines require a description, positive quantity and nonnegative rate."))
```

### Ghi kết quả lên đơn

```python
# tasks/xero_sync.py:131-149
def _save_invoice(doc: Document, invoice: dict) -> None:
	values = {
		"lab_xero_invoice_id": invoice["id"],
		"lab_xero_invoice_number": invoice["number"],
		"lab_xero_invoice_status": invoice["status"],
		"lab_xero_sync_status": "Synced",
		"lab_xero_error": None,
		"lab_xero_last_synced_at": now_datetime(),
	}
	for field in ("amount_due", "amount_paid", "amount_credited"):
		value = invoice[field]
		try:
			valid = Decimal(str(value)).is_finite()
		except InvalidOperation:
			valid = False
		if not valid:
			raise XeroRejected("Xero returned an invalid invoice amount; no amount was saved.")
		values["lab_xero_" + field] = flt(value, doc.precision("lab_xero_" + field))
	doc.db_set(values)
```

Một số tiền không phải là số hữu hạn thì **không ghi gì cả**. Một lần `db_set` cho cả bộ: hoặc mọi field cùng đổi, hoặc không field nào.

### Khi hỏng: ghi lại bằng một transaction riêng

```python
# tasks/xero_sync.py:152-165
def _record_failure(outbox_name: str, reason: str) -> None:
	outbox = frappe.get_doc(OUTBOX, outbox_name, for_update=True, check_permission="write")
	if outbox.status == "Done":
		return  # Another worker completed it after rollback released the lock.
	outbox.attempts = cint(outbox.attempts) + 1
	outbox.status = "Failed"
	outbox.error = reason
	outbox.save()
	if outbox.reference_doctype == "Sales Order":
		doc = frappe.get_doc("Sales Order", outbox.reference_name, for_update=True, check_permission="write")
		if not (outbox.operation == "create_invoice" and doc.docstatus == 2):
			doc.db_set({"lab_xero_sync_status": "Failed", "lab_xero_error": reason})
	# Preserve failure indicators before re-raising into the worker's rollback.
	frappe.db.commit()
```

Vấn đề nó giải: khi job ném lỗi, Frappe rollback **mọi thứ** job đã ghi, kể cả dấu "Failed". Nên trình tự là:

```text
lỗi xảy ra
 → frappe.db.rollback()          vứt mọi thay đổi dở dang của job
 → _record_failure(...)          ghi Failed + lý do
 → frappe.db.commit()            giữ lại đúng hai dấu vết đó
 → raise                         cho Frappe biết job hỏng (Error Log, danh sách job lỗi)
```

Đây là chỗ duy nhất trong code của ta gọi `commit` trực tiếp, và nó nằm trong `tasks/`, nơi luật dự án cho phép.

Lý do được dịch thành câu cho người đọc:

```python
# tasks/xero_sync.py:168-175
def _failure_reason(error: Exception) -> str:
	if isinstance(error, XeroBusy):
		if error.retry_after is not None:
			return _("Xero is busy. Retry after {0} seconds.").format(error.retry_after)
		return _("Xero is busy. Retry later.")
	if isinstance(error, (XeroError, frappe.ValidationError)):
		return str(error)
	return _("Xero sync failed unexpectedly. Ask a System Manager to inspect the failed job before retrying.")
```

Lỗi đã biết (của Xero hoặc luật của ta) hiện nguyên văn. Lỗi lạ (bug) không lộ chi tiết kỹ thuật ra form; chi tiết nằm trong Error Log.

### Void

```python
# tasks/xero_sync.py:101-114
def _void_invoice(client: XeroClient, doc: Document, key: str) -> str | None:
	if doc.docstatus != 2:
		frappe.throw(_("Only a cancelled Sales Order can void its Xero invoice."))
	invoice_id = _find_invoice(client, doc)
	if not invoice_id:
		# The create job also locks this order and skips cancelled orders.
		doc.db_set({"lab_xero_sync_status": "Synced", "lab_xero_error": None})
		return None
	client.void_invoice(_key(key), invoice_id)
	invoice = _read_invoice(client, doc, invoice_id)
	if invoice["status"] != "VOIDED":
		frappe.throw(_("Xero has not confirmed that the invoice is voided."))
	_save_invoice(doc, invoice)
	return invoice_id
```

Trường hợp tinh tế: cancel xảy ra **trước khi** job tạo kịp chạy. Khi đó bên Xero chưa có gì để void (job void đánh dấu xong), và job tạo, khi tới lượt, thấy đơn đã cancel nên không phát hành nữa (`_create_invoice` dòng 76-77). Cả hai job khóa cùng một đơn nên không thể chen nhau.

Chưa thử với Xero thật.

## Bước 4. Chiều về: `tasks/xero_pull.py`

```python
# tasks/xero_pull.py:35-59
def pull_changes() -> None:
	"""Refresh every order whose Xero invoice changed since the last pull. Run by the scheduler."""
	client = get_client()  # first: a token refresh inside it may commit
	settings = frappe.get_doc(SETTINGS)
	started = now_datetime()

	if settings.last_pull_at:
		since = _xero_utc(settings.last_pull_at)
		invoices = client.get_invoices(modified_since=since)
		credit_notes = client.get_credit_notes(modified_since=since)
	else:
		# First pull: read only the invoices we created, not the whole organisation.
		invoices = client.get_invoices(ids=_known_invoice_ids())
		credit_notes = client.get_credit_notes()
	_apply_invoices(invoices)
	inbound.apply_credit_notes(credit_notes)
	# An allocation changes the invoice's credited and due amounts. Read those invoices again
	# by id, in case Xero does not report them as modified on their own.
	credited_ids = sorted({a["invoice_id"] for note in credit_notes for a in note["allocations"]})
	_apply_invoices(client.get_invoices(ids=credited_ids))

	# The pointer moves only now, in the same transaction as the updates above:
	# if anything failed before this line, the next run starts from the old pointer.
	settings.last_pull_at = started
	settings.save()
```

- **Con trỏ `last_pull_at`**: "đã kéo tới thời điểm nào". Lấy `started` **trước** khi gọi Xero, để thay đổi xảy ra trong lúc đang kéo không bị bỏ sót ở lần sau.
- **Con trỏ được lưu sau cùng, cùng transaction với các cập nhật.** Job hỏng giữa chừng thì cả hai cùng rollback, lần sau kéo lại từ mốc cũ.
- **Lần kéo đầu tiên** (chưa có con trỏ): chỉ hỏi các hóa đơn của ta theo id, không kéo cả tổ chức.

```python
# tasks/xero_pull.py:62-87
def _apply_invoices(invoices: list[dict]) -> None:
	"""Overwrite the Xero fields of each order that owns one of these invoices."""
	by_id = {invoice["id"]: invoice for invoice in invoices}
	if not by_id:
		return

	orders = frappe.get_list(
		SALES_ORDER,
		filters={"lab_xero_invoice_id": ["in", list(by_id)]},
		fields=["name", "lab_xero_invoice_id"],
		limit_page_length=0,
	)
	for row in orders:
		invoice = by_id[row.lab_xero_invoice_id]
		order = frappe.get_doc(SALES_ORDER, row.name)
		# The order is submitted (or cancelled): only its allow-on-submit fields change, by db_set.
		order.db_set(
			{
				"lab_xero_invoice_number": invoice["number"],
				"lab_xero_invoice_status": invoice["status"],
				"lab_xero_amount_due": _money(order, "lab_xero_amount_due", invoice["amount_due"]),
				"lab_xero_amount_paid": _money(order, "lab_xero_amount_paid", invoice["amount_paid"]),
				"lab_xero_amount_credited": _money(order, "lab_xero_amount_credited", invoice["amount_credited"]),
				"lab_xero_last_synced_at": now_datetime(),
			}
		)
```

- Xero trả về mọi hóa đơn đã đổi của tổ chức; ta chỉ đụng tới những cái có `InvoiceID` khớp một Sales Order. Hóa đơn không phải của ta bị bỏ qua.
- **Ghi đè, không cộng dồn.** Chạy hai lần cho cùng kết quả. Đây là lý do con trỏ được phép lùi lại một chút:

```python
# tasks/xero_pull.py:104-108
def _xero_utc(site_time) -> str:
	"""Turn a datetime stored in the site's time zone into the UTC text Xero expects."""
	local = get_datetime(add_to_date(site_time, seconds=-OVERLAP_SECONDS))
	utc = local.replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(datetime.UTC)
	return utc.strftime("%Y-%m-%dT%H:%M:%S")
```

Site ở múi giờ Asia/Bangkok, Xero đòi giờ UTC. Hàm này lùi 120 giây (đồng hồ hai bên có thể lệch) rồi đổi múi giờ.

## Bước 5. Credit note: `lab_xero/inbound.py`

```python
# lab_xero/inbound.py:17-36
def apply_credit_notes(credit_notes: list[dict]) -> None:
	"""Create or update one row per credit note. Safe to run again with the same data."""
	for note in credit_notes:
		allocated = _allocated_to_our_orders(note)
		existing = frappe.db.exists(CREDIT_NOTE, {"xero_credit_note_id": note["id"]})

		if not allocated:
			if existing:
				# It was allocated before and no longer is: keep the row, show the new facts.
				_save(frappe.get_doc(CREDIT_NOTE, existing), note, allocated_amount=0)
			continue  # not allocated to any invoice of ours: it is not ours to record

		# Demo scope: one credit note belongs to one order. If Xero allocated it to several
		# of our invoices, the first one (by invoice id) is recorded.
		invoice_id, order_name, amount = allocated[0]
		if existing:
			_save(frappe.get_doc(CREDIT_NOTE, existing), note, amount, order_name, invoice_id)
		else:
			_save(frappe.new_doc(CREDIT_NOTE), note, amount, order_name, invoice_id)
			_say_on_timeline(order_name, note, amount)
```

Luật nghiệp vụ nằm trong ba nhánh:

| Tình huống | Làm |
|---|---|
| credit note chưa áp vào hóa đơn nào của ta, và ta chưa từng ghi nó | bỏ qua: không biết nó thuộc đơn nào |
| đã áp vào hóa đơn của ta, lần đầu thấy | tạo dòng + ghi **một** comment lên timeline của đơn |
| đã áp, đã có dòng | cập nhật dòng; **không** ghi comment lần nữa |
| trước đây đã ghi, nay hết allocation | giữ dòng, đặt số tiền áp về 0, cập nhật trạng thái |

"Thuộc về đơn nào" được quyết bằng allocation: credit note → hóa đơn → Sales Order có `lab_xero_invoice_id` đó.

```python
# lab_xero/inbound.py:39-54
def _allocated_to_our_orders(note: dict) -> list[tuple[str, str, float]]:
	"""Return (invoice id, Sales Order name, amount) for allocations that hit our invoices."""
	amounts: dict[str, float] = {}
	for allocation in note["allocations"]:
		amounts[allocation["invoice_id"]] = amounts.get(allocation["invoice_id"], 0) + flt(allocation["amount"])
	if not amounts:
		return []

	orders = frappe.get_list(
		SALES_ORDER,
		filters={"lab_xero_invoice_id": ["in", list(amounts)]},
		fields=["name", "lab_xero_invoice_id"],
		order_by="lab_xero_invoice_id asc",
		limit_page_length=0,
	)
	return [(row.lab_xero_invoice_id, row.name, amounts[row.lab_xero_invoice_id]) for row in orders]
```

Module này **không đổi gì trên Sales Order** ngoài dòng timeline. Số "đã ghi giảm" và "còn nợ" trên đơn đến từ hóa đơn, qua `_apply_invoices`. Chưa thử với credit note thật.

## Bước 6. Hai nút: `api/xero.py` và `public/js/sales_order.js`

```python
# api/xero.py:20-42
@frappe.whitelist(methods=["POST"])
def retry_sync(sales_order: str) -> dict:
	"""Queue the outbound sync of this order again: the invoice if the order is submitted,
	the void if it is cancelled."""
	doc = frappe.get_doc(SALES_ORDER, sales_order, check_permission="write")

	if doc.docstatus not in (SUBMITTED, CANCELLED):
		frappe.throw(
			_("Sales Order {0} is a draft. Only a submitted order goes to Xero.").format(sales_order),
			LabConflictError,
		)
	if doc.lab_xero_sync_status == "Synced":
		frappe.throw(
			_("Sales Order {0} is already synced to Xero.").format(sales_order),
			LabConflictError,
		)

	operation = "void_invoice" if doc.docstatus == CANCELLED else "create_invoice"
	# The order is submitted, so only its allow-on-submit Xero fields may change: db_set, not save.
	doc.db_set({"lab_xero_sync_status": "Queued", "lab_xero_error": None})
	outbox.queue(doc, operation=operation)
	return {"queued": True}
```

- `@frappe.whitelist(methods=["POST"])`: hàm này gọi được qua HTTP, chỉ bằng POST.
- `check_permission="write"`: người gọi phải có quyền ghi trên **đúng đơn đó**, không thì Frappe trả 403.
- Hai tình huống sai trạng thái trả 409 qua `LabConflictError`. Endpoint chỉ ném lỗi, không bắt lỗi nào.
- Trả `{"queued": true}` nghĩa là "đã nhận", chưa phải "đã sang Xero".

```javascript
// public/js/sales_order.js:4-26
frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 0) {
			return; // a draft never goes to Xero
		}

		if (frm.doc.lab_xero_sync_status !== "Synced") {
			frm.add_custom_button(
				__("Retry"),
				() => lab_xero_call(frm, "lab_core.api.xero.retry_sync", __("Sync to Xero queued")),
				__("Xero")
			);
		}

		if (frm.doc.lab_xero_invoice_id) {
			frm.add_custom_button(
				__("Refresh from Xero"),
				() => lab_xero_call(frm, "lab_core.api.xero.refresh", __("Refresh from Xero queued")),
				__("Xero")
			);
		}
	},
});
```

Nút Retry chỉ hiện khi đơn chưa `Synced`; nút Refresh chỉ hiện khi đã có hóa đơn. Server vẫn kiểm lại cả hai điều kiện: giao diện ẩn nút không phải là lớp bảo vệ.

## Ba lớp chống tạo trùng

```text
1. Hàng đợi      job_id + deduplicate                 chặn phần lớn job trùng            gọn, CHƯA an toàn
2. Database ta   khóa dòng outbox + kiểm Done         mỗi lúc một worker                 an toàn trước chính ta
                 unique trên idempotency_key,
                 lab_xero_invoice_id, contact_id      không lưu được bản thứ hai
3. Xero          TÌM theo số của ta trước khi tạo     dùng được bất cứ lúc nào           an toàn trước mạng
                 header Idempotency-Key               chỉ che khoảng 6 phút
```

## Hỏng ở đâu thì sao

| Hỏng ở | Chuyện gì xảy ra | Người dùng thấy | Làm gì |
|---|---|---|---|
| Handler lúc submit | cả lần submit rollback | lỗi ngay trên màn hình | sửa, submit lại |
| Sau commit, job không bao giờ chạy | đơn kẹt ở `Queued`, dòng outbox `Pending` | `Queued` mãi | bấm **Retry** (chưa có job quét tự động) |
| Luật của demo (thuế, discount, tiền tệ…) | chưa gọi tạo gì bên Xero | `Failed` + câu của luật | tạo đơn khác cho đúng |
| Xero từ chối dữ liệu | chưa có gì bên Xero | `Failed` + nguyên văn của Xero | sửa dữ liệu, Retry |
| Timeout sau khi Xero đã tạo | Xero có hóa đơn, ta chưa biết | `Failed` | Retry: bước ① tìm thấy hóa đơn và chỉ đọc lại |
| Token / quyền | không gọi được | `Failed` + "reconnect Xero" | Connect lại, Retry |
| Job kéo về hỏng giữa chừng | rollback cả cập nhật lẫn con trỏ | không gì đổi | lần kéo sau làm lại từ mốc cũ |

## Những chỗ còn yếu, nói thẳng

- **Chưa có job quét** cho đơn kẹt ở `Queued`; hiện dựa vào nút Retry.
- **Xero bận** (`XeroBusy`) được ghi thành `Failed` kèm số giây nên chờ; chưa có tự thử lại.
- **Đổi tên Customer** không được đẩy sang Xero, và nếu tên **bản ghi** Customer đổi thì đơn kế tiếp của khách đó sẽ báo "The saved Xero contact does not match the Customer lookup." (xem `07`).
- **Credit note áp vào nhiều hóa đơn của ta**: chỉ ghi hóa đơn đầu tiên.
- **Một lần `Xero authorization was refused`** đã xảy ra mà chưa rõ nguyên nhân.
- **Chưa có test tự động**; mọi bằng chứng là chạy tay trên Demo Company.
- Trả tiền, credit note và cancel/void: code đã viết, **chưa chạy thật**.
