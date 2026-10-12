# 10. `@xero_atomic`: demo có SAGA và không SAGA, trên Xero thật

Phần thêm của kế hoạch (P4 trong `plan/xero/PLAN.md`), làm ở **mức demo**: một luồng, một lỗi, hai chế độ. Chạy trên Xero thật (Demo Company); không có client thế chỗ nào. Lý thuyết SAGA: `07`. File này là thiết kế của demo và là hợp đồng mà phiên code xây theo.

Nhãn: xem `00-README.md`. Phần so với Spring là kiến thức chung, không phải thứ đã trace. Chưa có dòng code nào của phần này.

## Trả lời trong năm dòng

1. `@Transactional` của Spring làm **một database** nguyên tử bằng rollback. Không gì rollback được Xero, nên `@xero_atomic` không thể "nguyên tử" theo nghĩa đó.
2. Thứ nó làm được: **mọi bước xong, hoặc các bước Xero đã xong được hoàn tác bằng compensation** (bù trừ), theo thứ tự ngược.
3. Demo: cùng một đơn, cùng một lỗi **thật** ở bước hai, chạy hai chế độ. Không wrapper → hóa đơn còn sống trong Xero. Có wrapper → hóa đơn bị void, hai bên khớp.
4. Hàm được bọc chạy **trong background job**, không trong request (AGENTS.md B4).
5. Không Kafka, không container: người vận chuyển là Redis queue của Frappe, thứ sống sót qua crash là dòng outbox, "log" là một field `journal` trên dòng đó.

## So với `@Transactional`

```text
@Transactional (Spring, MỘT database)             @xero_atomic (Frappe + Xero)
 begin                                             (job đã có sẵn transaction của Frappe cho phần local)
   A: ghi DB                                         ① gọi Xero: tạo invoice     → nhớ cách hoàn tác: void
   B: ghi DB                                         ② gọi Xero: tạo payment     ✘ Xero từ chối
   ✘ exception                                       chạy danh sách hoàn tác NGƯỢC LẠI: void invoice
 rollback → như chưa có gì xảy ra                    ghi kết quả local: Failed + lý do
                                                    → Xero: invoice VOIDED (vẫn còn dấu vết, không "biến mất")
```

Ba khác biệt phải nói thật khi demo:
- Rollback xóa sạch; compensation để lại dấu vết (một hóa đơn đã void). Kế toán nhìn thấy nó.
- Giữa bước ① và lúc bù trừ, người khác **thấy** hóa đơn. Không có tính cô lập.
- Compensation tự nó có thể hỏng. Khi đó phải có một trạng thái có tên (`STUCK`) và một con người.

## Luồng của demo

Luồng bình thường của đề bài (P1) chỉ có một lần ghi hóa đơn. Để có **hai** lần ghi, demo này thêm một bước chỉ dùng cho P4: ghi một payment cho hóa đơn vừa tạo. Đây là ngoại lệ có chủ đích so với luật "ERPNext không ghi payment"; nó mặc định tắt.

```python
# lab_core/lab_xero/atomic.py (wrapper) — tên và hình dạng là hợp đồng, phần thân do phiên code viết
@xero_atomic
def invoice_with_payment(tx, sales_order, key):
    invoice_id = tx.step("create_invoice",
                         do=lambda: client.create_invoice(f"{key}:create_invoice", {...}),
                         compensate=lambda invoice_id: client.void_invoice(f"{key}:void_invoice", invoice_id))
    tx.step("create_payment",
            do=lambda: client.create_payment(f"{key}:create_payment", {...}))
    return invoice_id
```

Tên tham số `compensate` theo ý tưởng `@xero_atomic(compensate=...)` của kế hoạch chung. Bản không SAGA là cùng thân hàm, gọi client trực tiếp, không `tx`.

| Chuyện xảy ra trong một bước | Wrapper làm | Job ghi lên đơn |
|---|---|---|
| mọi bước xong | không gì thêm | `Synced` |
| Xero từ chối (`XeroRejected`) | chạy `compensate` của các bước đã xong, **ngược thứ tự** | `Failed`, lý do + "compensated" |
| không có câu trả lời (`XeroTimeout`) | tra bên Xero xem bước đó đã thành chưa; có → đi tiếp; không → như bị từ chối | theo kết quả |
| một `compensate` hỏng | dừng, không thử vô hạn | `Failed`, lý do bắt đầu bằng `STUCK:` |
| exception khác (bug) | **không nuốt**: để bay lên | job rollback + Error Log |

Trong bốn dòng đầu, job ghi `journal` rồi **return bình thường**, để trạng thái được commit (`06`: raise là mất hết).

Chỉ một lời từ chối của Xero (và "không rõ" đã được Xero xác nhận là "không có") mới kích hoạt bù trừ. Xero bận hay mất kết nối là chuyện của thử lại; bù trừ lúc đó sẽ void một hóa đơn hợp lệ (`07`).

## Điều khiển demo: bằng cấu hình thật, không bằng thủ thuật

| Thứ | Ở đâu | Giá trị |
|---|---|---|
| Chế độ | `Lab Xero Settings.issue_mode` | `Invoice only` (mặc định, luồng P1) · `Invoice + payment` (không wrapper) · `Invoice + payment (atomic)` (có wrapper) |
| Lỗi ở bước hai | `Lab Xero Settings.payment_account_code` | một mã tài khoản **không nhận được tiền** trong Demo Company → Xero tự từ chối payment. Đặt lại mã đúng thì bước hai thành công |
| Quyền | scope `accounting.payments` | thêm vào Connected App rồi Connect lại (miễn phí) |

Không có dòng code nào "giả vờ hỏng": lỗi là câu trả lời thật của Xero cho một dữ liệu cấu hình sai, đúng loại lỗi sẽ gặp trong đời thật.

## Bảng kết quả: chính là nội dung demo

Cùng một loại đơn, `payment_account_code` đang sai:

| Chế độ | Trên Sales Order | Trong Xero (nhìn bằng mắt) | Hai bên |
|---|---|---|---|
| `Invoice + payment` | `Failed`, lý do của Xero | hóa đơn **còn hiệu lực**, không có payment | **lệch**: ERPNext nói hỏng, Xero có một hóa đơn sống |
| `Invoice + payment (atomic)` | `Failed`, lý do + "compensated" | hóa đơn **đã void** | khớp |
| sửa mã cho đúng, đơn mới, chế độ atomic | `Synced` | hóa đơn + payment | khớp |

Ở mức demo, một đơn đã bị bù trừ thì **không Retry trên chính nó**: số hóa đơn (tên đơn) đã được dùng cho hóa đơn bị void. Muốn chạy lại thì dùng một đơn mới (hoặc cancel rồi amend, đơn nhận tên mới). Thử lại sau bù trừ là việc để sau demo.

## Journal: "log" của cả luồng mà không cần container

Mỗi bước thêm một phần tử vào một mảng; job ghi mảng đó vào field `journal` (kiểu JSON) của dòng outbox **một lần ở cuối**:

```text
[ {"step": "create_invoice", "kind": "do",         "result": "ok",       "xero_id": "<InvoiceID>", "at": "…"},
  {"step": "create_payment", "kind": "do",         "result": "rejected", "message": "<lý do của Xero>", "at": "…"},
  {"step": "create_invoice", "kind": "compensate", "result": "ok",       "xero_id": "<InvoiceID>", "at": "…"} ]
```

- Đọc ở đâu: form `Lab Xero Outbox` trong Desk. Một dòng = câu chuyện đầy đủ của một lần đồng bộ.
- Vì sao ghi một lần ở cuối: commit giữa job sẽ nhả row lock trên dòng outbox, và job trùng lọt vào. Helper có sẵn của Frappe `create_request_log` tự commit ([S] `frappe/integrations/utils.py:209-210`), nên không dùng nó giữa các bước.
- Không bao giờ chứa token hay header (AGENTS.md B6).

Về ý tưởng "một container kéo log của Frappe và Xero":
- **Xero không cho log nào để kéo.** Nó là dịch vụ thuê; phía Xero của câu chuyện chỉ là thứ ta tự ghi về mỗi lời gọi (gửi gì, nhận gì, id nào), cộng với những gì nhìn thấy trong giao diện Xero.
- Một bộ gom log chỉ **quan sát**; nó không quyết định bước kế tiếp và không hoàn tác được gì. Nó không thay được wrapper.
- Với một hệ thống và một bên ngoài, journal trên dòng outbox + Error Log + danh sách RQ Job của Desk đã là "một chỗ để nhìn".

## Vì sao không cần Kafka

| Việc broker làm | Lab đã có |
|---|---|
| chở message | Redis queue + `frappe.enqueue` |
| giữ message khi process chết | dòng `Lab Xero Outbox` (một dòng database sống sót qua crash) |
| giao lại | nút Retry |
| thứ tự các bước | wrapper chạy tuần tự trong một job |

Broker **không** thay được ba thứ ta vẫn phải tự làm: idempotency ở bên nhận, compensation, và trạng thái nhìn thấy được. Nó đáng tiền khi nhiều service cùng nghe một sự kiện; ở đây chỉ có một.

## Giới hạn đã biết của mức demo

- Danh sách hoàn tác nằm trong bộ nhớ của job. **Worker chết** giữa bước ① và lúc bù trừ: hóa đơn nằm lại trong Xero, journal không được ghi. Lần chạy lại sẽ tìm thấy hóa đơn theo số của nó và đi tiếp, nên phần lớn trường hợp tự lành.
- Bù trừ hỏng: chỉ được báo (`STUCK:`), con người xử lý trong Xero.
- Bản bền hơn (sau demo): mỗi bước và mỗi compensation là một dòng outbox riêng, có một bản ghi trạng thái cho cả chuỗi (`07`, cuối mục SAGA).

## Chưa biết, phải thử trên Demo Company

- Mã tài khoản nào khiến Xero từ chối một payment (tài khoản không phải ngân hàng và không bật "enable payments" là phỏng đoán từ trí nhớ).
- Xero có cho tạo hóa đơn mới với số của một hóa đơn đã void không.
- Void một hóa đơn vừa tạo vài giây trước có bị chặn gì không.

## Tự kiểm tra

1. `@xero_atomic` khác `@Transactional` ở ba điểm nào mà người xem demo cần biết?
2. Vì sao Xero bận ở bước hai **không** được kích hoạt void?
3. Vì sao journal được ghi một lần ở cuối job chứ không sau mỗi bước?
