# 07. Hỏi đáp: những câu dễ bị hỏi

Mỗi câu: trả lời ngắn trước, rồi chỗ để chỉ vào. Ký hiệu mức xác nhận như ở `00`: **đã quan sát**, **theo code**, **từ trí nhớ**.

## A. Về Xero và chi phí

**Xero là gì, có tự host được không?**
Phần mềm kế toán chạy trên cloud của Xero. Không có bản cài đặt, không tự host. Ta nói chuyện với nó qua HTTPS tại `api.xero.com`.

**Demo tốn bao nhiêu?**
0 đồng. Dùng **Demo Company** (tổ chức mẫu có sẵn dữ liệu, miễn phí) và bậc API miễn phí: 60 lời gọi mỗi phút, 1000 mỗi ngày (nguồn ghi ở `docs/xero/03`). Lịch kéo 5 phút tốn khoảng 580 lời gọi mỗi ngày.

**Xero có cần gọi vào máy tôi không? Có phải deploy không?**
Không. Mọi lời gọi đều đi **từ** Frappe **ra** Xero. Ngay cả trong OAuth, Xero chỉ trả lời trình duyệt bằng một lệnh chuyển hướng, và chính trình duyệt trên máy bạn mở `localhost`. Chỉ webhook mới cần địa chỉ công khai, và demo không dùng webhook (`docs/xero/knowledge/webhook.md`).

**Vì sao hỏi định kỳ (polling) mà không dùng webhook?**
Webhook cần một URL https công khai → phải deploy hoặc dùng tunnel. Demo chạy trên máy cá nhân nên hỏi mỗi 5 phút, kèm nút Refresh để xem ngay. Đổi lại: chậm tối đa 5 phút và tốn lời gọi ngay cả khi không có gì đổi.

## B. Về OAuth

**Người dùng Frappe có phải đăng nhập Xero không?**
Không. Một admin đồng ý một lần; từ đó server giữ token. Người bán hàng chỉ thấy các field và hai nút trên Sales Order.

**Token nằm ở đâu, có an toàn không?**
Trong DocType `Token Cache` của Frappe, dòng `xero-Administrator`; `access_token` và `refresh_token` là field Password nên được mã hóa. `client_secret` nằm trong site config (ngoài repo) và trong field Password của Connected App. Không cái nào nằm trong code, tài liệu hay log của ta.

**Token hết hạn thì sao?**
Access token sống 30 phút (**đã quan sát**: `expires_in` = 1800). Mỗi lần job cần token, Frappe kiểm hạn và tự đổi bằng refresh token (`02`, mục "Làm mới token"). **Có vẻ đã chạy**: Token Cache được cập nhật lúc 14:48:02 đúng nhịp scheduler, không ai bấm gì. Refresh token của Xero sống 60 ngày nếu không dùng (**từ trí nhớ**); quá hạn thì Connect lại.

**Vì sao phải dùng `http://localhost:8000` mà không phải `lab.localhost`?**
Xero chỉ nhận Redirect URI là `https` hoặc đúng `http://localhost` (**đã quan sát** lỗi "Must use https (except localhost which may use http)"). Cookie đăng nhập lại gắn theo tên host, nên phải làm cả lượt Connect từ tab `localhost:8000`.

**Tenant là gì, sao OAuth xong vẫn chưa gọi được?**
Một login Xero có thể vào nhiều tổ chức. Token nói "app được phép"; header `xero-tenant-id` nói "vào tổ chức nào". Job `discover_tenant` hỏi `GET /connections` một lần và lưu vào `Lab Xero Settings`.

## C. Về luồng và dữ liệu

**Một khách có nhiều hóa đơn được không?**
Được, và **đã chạy thật**: `SAL-ORD-2026-00007` và `-00008` cùng khách "West View Software Ltd.", cùng một `Xero Contact ID`, hai hóa đơn riêng. Contact được tạo ở đơn đầu; từ đơn thứ hai job tìm thấy nó theo mã khách và dùng lại:

```python
# tasks/xero_sync.py:86-91
contact_id = client.find_contact(customer.name)
if customer.lab_xero_contact_id and customer.lab_xero_contact_id != contact_id:
	frappe.throw(_("The saved Xero contact does not match the Customer lookup."))
if not contact_id:
	contact_id = client.create_contact(_key(f"Customer:{customer.name}:create_contact"), customer_to_contact(customer))
customer.db_set("lab_xero_contact_id", contact_id)
```

Hai lớp chống tạo contact trùng: tìm theo `ContactNumber` trước khi tạo, và field `lab_xero_contact_id` có ràng buộc unique.

**Một đơn có nhiều hóa đơn được không?**
Không, cố ý. Một Sales Order ↔ một Invoice, nối bằng `InvoiceNumber` = tên đơn và `lab_xero_invoice_id` (unique). Giao hàng từng phần, hóa đơn từng phần là việc của dự án thật.

**Vì sao không gọi Xero ngay lúc Submit?**
Ba lý do: người dùng không phải chờ Xero; Xero chết thì vẫn submit được; và quan trọng nhất, hai hệ thống không dùng chung transaction, nên "gọi ngay" có thể để lại hóa đơn bên Xero cho một đơn đã bị rollback. Ghi ý định vào outbox trong cùng transaction với đơn, rồi gửi sau, tránh được cả ba (`06`, mục "Ý tưởng gốc").

**Outbox là gì, sao không xếp job thẳng?**
Job trong hàng đợi (Redis) có thể mất hoặc chết mà không để lại dấu vết. Dòng `Lab Xero Outbox` nằm trong database, cùng transaction với đơn: việc cần làm không bao giờ mất, và luôn có nơi ghi "đã thử mấy lần, lỗi gì".

**Job chạy hai lần thì có hai hóa đơn không?**
Không. Ba lớp, từ yếu tới mạnh: hàng đợi khử job trùng theo `job_id`; job khóa dòng outbox và thoát nếu đã `Done`; và trước khi tạo, job **luôn hỏi Xero** hóa đơn mang số này đã có chưa. Lớp cuối là lớp quyết định, vì nó đúng cả khi lần trước Xero đã tạo xong mà câu trả lời không về tới ta.

**`Idempotency-Key` để làm gì nếu đã tìm trước khi tạo?**
Nó che khoảng hở nhỏ: hai lần gửi sát nhau. Xero chỉ nhớ key khoảng 6 phút, nên không thể dựa vào nó cho Retry sau một giờ. Vì vậy nó là lớp phụ.

**Job hỏng giữa chừng thì dữ liệu ra sao?**
Mọi thứ job đã ghi bị rollback; rồi một transaction nhỏ riêng ghi `Failed` + lý do lên dòng outbox và lên đơn; rồi lỗi được ném lại để Frappe ghi Error Log. Thứ đã tạo bên Xero thì không rollback được, nên Retry tìm lại nó theo số thay vì tạo mới (`06`, mục "Khi hỏng").

**Số tiền trên đơn lấy từ đâu?**
Từ Xero, luôn luôn. Ta gửi dòng hàng (số lượng, đơn giá); Xero tính tổng và thuế; ta đọc lại và chép `AmountDue`, `AmountPaid`, `AmountCredited`. ERPNext không tự tính số nào trong phần Xero.

**Thuế xử lý thế nào?**
Demo: đơn có thuế ERPNext thì bị từ chối; mọi dòng gửi với `TaxType` = `NONE` (0%) và tài khoản `200`. Ánh xạ thuế thật là quyết định của dự án thật.

**Dữ liệu mới nằm ở đâu trong database?**
Ba DocType mới (`Lab Xero Outbox`, `Lab Xero Settings`, `Lab Xero Credit Note`), một field trên Customer, mười field trên Sales Order, và hai DocType có sẵn của Frappe (`Connected App`, `Token Cache`). Không bảng nào của ERPNext bị sửa cấu trúc bằng tay; field thêm vào là Custom Field tạo bằng code (`04`).

## D. Về hai luồng lead yêu cầu

**Luồng 1: Sales Order → Invoice → trạng thái quay về. Xong chưa?**
Chiều đi: **đã chạy thật**. Chiều về: job kéo **đã chạy** (giờ đồng bộ đổi), nhưng chưa có thay đổi thật nào để kéo. Còn thiếu một lần ghi payment trong Xero để thấy `PAID` quay về.

**Luồng 2: Credit Note ở Xero → ảnh hưởng tới Sales Order. Xong chưa?**
Code đã viết, **chưa chạy thật**. "Ảnh hưởng" trong demo là: `Xero Amount Credited` và `Xero Amount Due` trên đơn đổi theo, một dòng `Lab Xero Credit Note`, một comment trên timeline. Không sửa tổng tiền hay trạng thái của đơn.

**Credit note thuộc đơn nào, làm sao biết?**
Qua **allocation**: credit note được áp vào hóa đơn nào → hóa đơn đó thuộc Sales Order nào (`lab_xero_invoice_id`). Credit note chưa áp vào đâu thì bị bỏ qua.

**Cancel đơn thì hóa đơn bên Xero ra sao?**
Được void. Nếu hóa đơn đã có tiền trả hoặc credit thì **chặn cancel** ngay trong ERPNext. **Chưa chạy thật.**

## E. Về giới hạn (nói thẳng trước khi bị hỏi)

| Giới hạn | Hệ quả | Hướng cho dự án thật |
|---|---|---|
| Đổi tên Customer không sang Xero | contact giữ tên cũ; rename bản ghi làm đơn kế tiếp `Failed` | cập nhật contact khi Customer đổi; tìm contact theo id đã lưu |
| Sửa hóa đơn bên Xero (dòng, số tiền, số hóa đơn) | hai bên lệch nhau, không cảnh báo | so tổng hai bên khi kéo về và báo lệch |
| Void bên Xero | đơn vẫn submitted | luật riêng: báo cho người bán |
| Không thuế, không discount, một tiền tệ | đơn như vậy bị từ chối, có lý do | ánh xạ thuế và discount |
| Credit note áp vào nhiều hóa đơn của ta | chỉ ghi hóa đơn đầu | một dòng cho mỗi allocation |
| Không tự thử lại; đơn kẹt `Queued` phải bấm Retry | cần người | job quét các dòng `Pending`/`Failed` theo lịch, có giới hạn số lần |
| Polling 5 phút | chậm tối đa 5 phút | webhook khi đã có URL công khai |
| Một tổ chức Xero, một user nối | — | nhiều tenant |
| Chưa có test tự động | bằng chứng là chạy tay | viết test sau demo (đã hoãn có chủ đích) |
| Một lần "Xero authorization was refused" chưa rõ nguyên nhân | có thể gặp lại | Connect lại rồi Retry; ghi thêm mã HTTP vào lỗi để phân biệt 401 và 403 |

## F. Câu hỏi còn mở, cần bạn quyết

Mỗi câu kèm phương án đề xuất.

**1. Cảnh đổi tên Customer: xây thêm hay trình bày như một giới hạn?**

| Phương án | Việc | Rủi ro |
|---|---|---|
| **A (đề xuất): xây bản nhỏ** | khi Customer đã có `Xero Contact ID` được lưu với tên mới → ghi một dòng outbox `update_contact` → job gọi `POST /Contacts/<ContactID>` với `Name` (và `ContactNumber`) mới (đường API này viết từ trí nhớ; phải đối chiếu tài liệu Xero trước khi code). Đồng thời sửa `_create_invoice` để ưu tiên contact theo id đã lưu, hết gãy khi rename bản ghi | đụng `hooks.py` (thêm `doc_events` cho Customer), `outbox`/`xero_sync` hiện chỉ nhận Sales Order, `client.py`, `mapping.py`; cần chạy thật một lần trước demo |
| B: giữ nguyên | trình bày 5a như một giới hạn đã biết | lead thấy một cảnh "không đồng bộ" |

Hai điểm cần bạn xác nhận nếu chọn A: tên bên Xero bị ERPNext **ghi đè** (kế toán sửa tên bên Xero sẽ mất ở lần đổi sau); và contact trùng tên bên Xero sẽ bị Xero từ chối, đơn báo `Failed` kèm lý do.

**2. Cảnh "đổi trong Xero": demo những thay đổi nào?**
Đề xuất: **trả tiền** (đơn A) và **credit note** (đơn B), vì đó đúng là hai luồng trong yêu cầu của lead. Không demo việc sửa dòng hàng hay tên contact bên Xero; nếu bị hỏi thì trả lời bằng bảng ở `13`, mục 4 ("Xero không phải chủ của những thứ đó").

**3. Có thêm cảnh báo lệch khi hóa đơn bị sửa hoặc void bên Xero không?**
Đề xuất: **không** cho buổi demo này. Ghi nó là giới hạn (bảng E). Thêm sau nếu lead hỏi.

**4. Có chụp lại request và response thật của Xero để đưa vào `03` không?**
Đề xuất: **có, nhưng làm sau lần tập** trả tiền và credit note, bằng một lệnh chỉ đọc (GET) do bạn chạy; token và id sẽ được che. Hiện `03` mô tả hình dạng theo code và theo tài liệu Xero, chưa phải dữ liệu chụp từ đường truyền.
