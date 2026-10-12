# 11. ERP xem dữ liệu Xero bằng cách nào: gọi API hay đọc database?

**Trả lời:** màn hình ERP **chỉ đọc database của Frappe**. Nó không gọi Xero lúc bạn mở form. Thứ bạn thấy là một **bản sao** số liệu của Xero, do job nền chép về trước đó.

## Hình

```text
 XEM (mở form, mở danh sách)                         LÀM MỚI BẢN SAO (chạy ở nền)
 ────────────────────────────                         ─────────────────────────────
 trình duyệt                                           3 thời điểm:
     │  mở Sales Order                                   a) ngay sau khi tạo hóa đơn
     ▼                                                   b) scheduler, khoảng 5 phút một lần
 Frappe ── SELECT ──► DATABASE FRAPPE                    c) nút "Refresh from Xero"
     ▲                 ├─ Sales Order.lab_xero_*  ◄──┐           │
     │                 └─ Lab Xero Credit Note    ◄──┤           ▼
 hiện lên form                                       │   job nền ── GET ──► api.xero.com
                                                     └──── ghi đè bản sao ◄── JSON
 KHÔNG có mũi tên nào từ trình duyệt hay từ lúc mở form tới Xero.
```

## Bản sao nằm ở đâu

| Thấy trên ERP | Lưu ở (database Frappe) | Bản gốc bên Xero | Job nào chép |
|---|---|---|---|
| Phần **Xero** trên Sales Order: id và số hóa đơn, trạng thái, còn nợ, đã trả, đã ghi giảm, giờ đồng bộ | các field `lab_xero_*` trên bảng Sales Order | Invoice | `tasks/xero_sync.py` (lúc tạo), `tasks/xero_pull.py` (về sau) |
| Danh sách **Lab Xero Credit Note** | bảng `Lab Xero Credit Note`: `sales_order`, `xero_credit_note_id`, `credit_note_number`, `xero_invoice_id`, `date`, `total`, `allocated_amount`, `status` | Credit Note + allocation | `lab_xero/inbound.py` |
| Dòng timeline trên đơn | `Comment` | — | `lab_xero/inbound.py` |
| `Xero Contact ID` trên Customer | 1 field trên bảng Customer | Contact (chỉ id) | `tasks/xero_sync.py` |

Không lưu: dòng hàng của hóa đơn, tổng, thuế, từng khoản payment, tên và email của contact. Muốn xem những thứ đó thì mở Xero.

## Nút Refresh cũng không cho trình duyệt gọi Xero

```javascript
// public/js/sales_order.js:28-39
function lab_xero_call(frm, method, queued_message) {
	frappe.call({
		method: method,
		args: { sales_order: frm.doc.name },
		freeze: true,
		callback() {
			frappe.show_alert(queued_message);
			// The job runs after this request; give it a moment, then show the new status.
			setTimeout(() => frm.reload_doc(), 3000);
		},
	});
}
```

```python
# api/xero.py:55-63  (trong refresh)
frappe.enqueue(
	PULL_JOB,
	queue="default",
	enqueue_after_commit=True,
	job_id=f"lab-xero-pull:{doc.name}",
	deduplicate=True,
	sales_order=doc.name,
)
return {"queued": True}
```

```text
 bấm Refresh ─► Frappe: xếp job, trả {"queued": true}      (request KHÔNG gọi Xero)
                   └─► job nền ─► GET api.xero.com ─► ghi đè field trong database
 3 giây sau  ─► trình duyệt tải lại form ─► đọc DATABASE ─► thấy số mới
```

Câu trả lời của nút không chứa dữ liệu Xero. Dữ liệu mới tới màn hình bằng lần đọc database kế tiếp.

## Vì sao chọn bản sao, không gọi API lúc xem

| | Bản sao trong database (đang dùng) | Gọi Xero mỗi lần mở form |
|---|---|---|
| Tốc độ mở form | như mọi form khác | chờ Xero mỗi lần |
| Xero chết hoặc mất kết nối | vẫn xem được số cũ | form không hiện được |
| Hạn mức 1000 lời gọi mỗi ngày | chỉ job dùng, đếm được | mỗi lần mở form tốn lời gọi |
| Tìm, lọc, báo cáo theo trạng thái Xero | được (là field bình thường) | không |
| Token | chỉ job nền cầm | request của người dùng phải cầm |
| Độ tươi | **có thể cũ tới khoảng 5 phút** | luôn mới |

Cái giá duy nhất là độ tươi. Ô **`Xero Last Synced At`** trên đơn nói bản sao được chép lúc nào; nút Refresh để lấy mới ngay.

## Ba điều để nói

1. "ERP không hỏi Xero lúc xem. Nó đọc bản sao của chính nó; job nền giữ bản sao cho mới."
2. "Bản sao chỉ gồm những con số Xero làm chủ: trạng thái, còn nợ, đã trả, đã ghi giảm, và credit note."
3. "Bản sao luôn bị **ghi đè** bằng số của Xero, không bao giờ tự tính, nên chép lại bao nhiêu lần cũng đúng."

Đã quan sát: `Xero Last Synced At` đổi sau mỗi lần kéo. Chưa quan sát: một thay đổi thật bên Xero (payment, credit note) hiện lên form.
