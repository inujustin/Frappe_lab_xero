# 13. Chi tiết phía sau kịch bản demo

`01` là tờ chạy một mạch, cố ý ngắn. File này giữ phần kỹ thuật đi kèm: lệnh kiểm, luật điền form, vì sao đổi tên khách không sang Xero, và đổi gì bên Xero thì về tới Frappe.

## 1. Hai lệnh kiểm kết nối

Kiểm đã có token (chạy trên host từ thư mục gốc dự án; lệnh bên trong gọi hàm `has_token` của Frappe trong container; chỉ đọc, không đổi gì):

```bash
docker compose exec frappe bench --site lab.localhost execute frappe.integrations.doctype.connected_app.connected_app.has_token --kwargs '{"connected_app":"xero","connected_user":"Administrator"}'
```

Kết quả mong đợi: `true`.

Tìm tenant (chạy trên host; nó xếp một job nền trong container; job hỏi Xero rồi ghi `tenant_id`, `tenant_name` vào `Lab Xero Settings`). Chỉ cần khi ô `Tenant ID` còn trống, hoặc sau khi Demo Company bị reset:

```bash
docker compose exec frappe bench --site lab.localhost execute frappe.enqueue --kwargs '{"method":"lab_core.tasks.xero_sync.discover_tenant","queue":"default","enqueue_after_commit":True,"job_id":"lab-xero-discover-tenant","deduplicate":True}'
```

Kiểm: mở **Lab Xero Settings**, ô `Tenant Name` = "Demo Company (Global)".

## 2. Luật điền Sales Order

| Ô | Giá trị | Nếu sai thì |
|---|---|---|
| Customer | khách đã chuẩn bị | — |
| Delivery Date | hôm nay hoặc sau | ERPNext không cho lưu |
| Item / Qty | ví dụ "Book" / 2 | — |
| Rate | **để nguyên giá niêm yết** | gõ giá khác → ERPNext ghi thành discount → đơn `Failed` (đã gặp ở `SAL-ORD-2026-00006`) |
| Taxes and Charges | **để trống** | có thuế → đơn `Failed` |
| Currency | tiền tệ của Company | khác → đơn `Failed` |

Điều xảy ra khi bấm Submit, và thứ gửi sang Xero: `06` (bước 1–3) và `03` (lời gọi 5).

## 3. Đổi tên Customer: vì sao không sang Xero

**Hiện chưa có code nào đẩy việc đổi tên khách sang Xero.** Contact chỉ được ghi một lần, lúc tạo.

| | 3a. Sửa ô **Customer Name** rồi Save | 3b. Bấm vào tiêu đề form → **Rename** (đổi tên bản ghi) |
|---|---|---|
| Đổi gì ở ERPNext | field `customer_name`; mã bản ghi (`name`) giữ nguyên | chính `name` của bản ghi (và `customer_name` theo sau) |
| Sang Xero? | **Không.** Contact vẫn mang tên cũ | **Không.** |
| Đơn kế tiếp của khách này | sang Xero bình thường, gắn vào contact cũ | **`Failed`**: "The saved Xero contact does not match the Customer lookup." |
| Dùng khi demo | được, an toàn | **đừng làm** |

Contact được nối bằng **mã**; tên chỉ gửi lúc tạo:

```python
# lab_xero/mapping.py:9-12
def customer_to_contact(customer: Document) -> dict:
	if not customer.name or not customer.customer_name:
		frappe.throw(_("Customer code and name are required for Xero."))
	return {"ContactNumber": customer.name, "Name": customer.customer_name}
```

Ở đơn kế tiếp, job tìm contact theo mã hiện tại và so với id đã lưu:

```python
# tasks/xero_sync.py:86-90
contact_id = client.find_contact(customer.name)
if customer.lab_xero_contact_id and customer.lab_xero_contact_id != contact_id:
	frappe.throw(_("The saved Xero contact does not match the Customer lookup."))
if not contact_id:
	contact_id = client.create_contact(_key(f"Customer:{customer.name}:create_contact"), customer_to_contact(customer))
```

- **3a:** mã không đổi → tìm thấy contact cũ → dùng lại. Tên mới không được gửi đi.
- **3b:** mã đã đổi → Xero không có contact mang mã mới → khác id đã lưu → job dừng. Nó dừng thay vì tạo contact thứ hai: an toàn, nhưng người dùng bị kẹt.

Theo code ERPNext (`erpnext/selling/doctype/customer/customer.py:443-445`), sau khi rename bản ghi thì `customer_name` cũng được đặt bằng tên mới. Chưa chạy thử cả 3a lẫn 3b. Hướng sửa: `08` mục 11.3 và 11.8; câu hỏi còn mở: cuối `07`.

## 4. Đổi gì bên Xero thì về tới Frappe

Luật: **Xero là chủ của hóa đơn** (trạng thái, đã trả, còn nợ, đã ghi giảm) và của credit note; ERPNext chỉ chép về. Thứ thuộc ERPNext (khách, dòng hàng) mà bị sửa bên Xero thì **không** được chép về.

| Đổi gì bên Xero | Về Frappe? | Thấy gì ở Frappe | Hợp lệ? |
|---|---|---|---|
| **Nhận tiền đủ** | Có | `Xero Invoice Status` = `PAID`, `Xero Amount Paid` = tổng, `Xero Amount Due` = 0 | Đúng luật |
| Nhận tiền một phần | Có | vẫn `AUTHORISED`; `Amount Paid` tăng, `Amount Due` giảm | Đúng luật |
| **Credit note áp vào hóa đơn** | Có | `Xero Amount Credited` tăng, `Amount Due` giảm; một dòng **Lab Xero Credit Note**; một comment trên timeline | Đúng luật |
| Credit note chưa áp vào hóa đơn nào | Không | không gì | Đúng: chưa biết nó thuộc đơn nào |
| Void hóa đơn trong Xero | Có | `Xero Invoice Status` = `VOIDED`, `Amount Due` = 0; Sales Order **vẫn** submitted | Chép đúng, nhưng hai bên lệch nhau, không cảnh báo |
| Sửa dòng hàng / số tiền của hóa đơn | Một phần | `Amount Due` đổi theo; dòng hàng của Sales Order không đổi | **Lệch**, không cảnh báo |
| Đổi số hóa đơn | Một phần | `Xero Invoice Number` đổi theo | **Gãy về sau**: Retry hoặc Cancel báo "The saved Xero invoice does not match the Sales Order number lookup." |
| Sửa tên, email của contact | Không | không gì | Ngoài phạm vi |

Đọc từ `tasks/xero_pull.py` và `lab_xero/inbound.py`; chưa dòng nào trong bảng được chạy thật. Các field được chép về, và không field nào khác:

```python
# tasks/xero_pull.py:78-87
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

"Ảnh hưởng" của credit note lên Sales Order trong demo là **hiển thị**: số đã ghi giảm, số còn nợ, một bản ghi, một dòng timeline. Nó không sửa tổng tiền hay trạng thái của đơn.

## 5. Cảnh phụ, nếu còn giờ

**Lỗi hiện rõ.** Tạo một đơn có giá khác giá niêm yết, Submit → `Failed`, ô `Xero Error` = "The Xero demo supports Sales Order lines without discounts." Chưa có gì được tạo bên Xero. Đơn đã submit không sửa giá được, nên đơn này chỉ để cho xem lỗi; Retry có ích khi nguyên nhân nằm ngoài đơn (mất kết nối, cấu hình thiếu).

**Cancel → void** (chưa thử). Cancel một đơn đã `Synced` và chưa có tiền: `Queued` → `Xero Invoice Status` = `VOIDED`; bên Xero hóa đơn nằm ở tab Voided.

## 6. Sự cố giữa buổi

| Thấy | Nghĩa | Làm |
|---|---|---|
| Đơn đứng mãi ở `Queued` | job chưa chạy hoặc đã chết | xem dòng trong **Lab Xero Outbox**; bấm **Xero → Retry** |
| `Failed`: "…reconnect Xero." | token mất hoặc bị từ chối | Connect lại, rồi Retry |
| `Failed`: câu về discount, thuế, tiền tệ | luật của demo | tạo đơn khác cho đúng |
| `Failed`: câu của Xero (tài khoản, mã thuế, tiền tệ chưa bật) | Xero từ chối dữ liệu | sửa đúng thứ được nêu, Retry |
| Refresh không đổi gì | Xero chưa có gì đổi, hoặc job kéo hỏng | chờ vài giây rồi tải lại |
| Không thấy nhóm nút **Xero** | đơn còn nháp, hoặc JS chưa nạp | Submit; Ctrl+Shift+R |
| "Invalid token state!" hoặc bị đưa tới `/login` khi Connect | bấm Connect hai lần, hoặc đang ở sai tên host | bấm lại một lần, từ tab `localhost:8000` |

Không mở hay dán nguyên văn Error Log trước người xem: traceback của Frappe in cả giá trị biến, có thể chứa secret.
