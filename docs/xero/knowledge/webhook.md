# Webhook: là gì, Frappe có gì, Xero dùng thế nào

Kiến thức nền cho gói Xero. Bản song sinh của file này nằm ở `docs/knowledge/17-webhooks.md` (cùng nội dung; sửa một nơi thì sửa cả hai).

Nhãn: xem `../00-README.md`. Đường dẫn Frappe bắt đầu từ `frappe-bench/apps/frappe/`. Đã đọc hôm nay: `frappe/integrations/doctype/webhook/__init__.py` (cả file), `webhook.py` (cả file), `frappe/model/document.py:1265`.

## Trả lời trong năm dòng

1. **Webhook** = "đừng hỏi tôi, có gì tôi sẽ gọi": khi có sự kiện, hệ thống A tự gửi một HTTP POST tới URL của hệ thống B. Ngược với **polling** (B hỏi A định kỳ).
2. Có hai chiều, đừng lẫn: **outgoing** (Frappe gọi ra: có sẵn DocType `Webhook`) và **incoming** (bên ngoài gọi vào Frappe: không có sẵn, ta tự viết một endpoint).
3. Webhook của Xero là chiều **incoming**: Xero gọi vào ta. Đây là thứ **duy nhất** trong cả tích hợp đòi máy ta truy cập được từ internet.
4. Vì ai cũng gọi được một URL công khai, webhook được bảo vệ bằng **chữ ký HMAC** trên body, không phải bằng đăng nhập.
5. Demo **không cần** webhook: chiều chính là ERPNext → Xero (ta gọi ra). Nếu cần biết thay đổi bên Xero thì polling thưa là đủ, và 0 đồng.

## Polling so với webhook

```text
POLLING: ta hỏi                                WEBHOOK: họ báo
 ta ──"có gì mới không?"──► Xero                ta                         Xero
 ta ◄──"không"────────────  Xero                 │   (im lặng, không tốn gì)  │
 ta ──"có gì mới không?"──► Xero                 │◄── POST "invoice X đã đổi" ─│   ← Xero mở kết nối VÀO ta
 ta ◄──"invoice X đã đổi"─  Xero                 │── 200 OK ──────────────────►│
 mọi mũi tên đi RA từ ta → chạy được ở localhost  ta ── GET invoice X ────────►│   (event chỉ là gợi ý)
```

| | Polling | Webhook |
|---|---|---|
| Ai mở kết nối | ta → Xero | **Xero → ta** |
| Cần URL công khai | không | **có**, HTTPS |
| Độ trễ | bằng chu kỳ hỏi | vài giây |
| Tốn rate limit | mỗi lần hỏi một lời gọi, kể cả khi không có gì | chỉ khi có thay đổi (rồi một `GET`) |
| Mất event | không (lần hỏi sau vẫn thấy) | có thể → vẫn phải có polling làm lưới an toàn |
| Độ khó | thấp | cao hơn: chữ ký, trùng, sai thứ tự |

## Năm tính chất của mọi webhook [G]

Đúng với Xero, Stripe, GitHub và cả webhook của chính Frappe:

1. **Payload mỏng.** Thường chỉ nói *cái gì* đổi (id + loại), không kèm dữ liệu. Muốn dữ liệu thì gọi API lấy.
2. **Có chữ ký.** Bên gửi tính HMAC của body bằng một khóa bí mật chung, đặt vào header. Bên nhận tính lại và so. Sai → từ chối.
3. **Phải trả lời nhanh.** Bên gửi chờ vài giây. Vậy: kiểm chữ ký → ghi lại → trả `200` → xử lý **sau**, trong job.
4. **At-least-once (ít nhất một lần).** Cùng event có thể tới hai lần → bên nhận phải chống trùng.
5. **Không đảm bảo thứ tự.** "update" có thể tới trước "create" → đừng tin nội dung event, hãy đọc trạng thái hiện tại qua API.

Hệ quả: bên nhận cần một bảng **inbox** (hộp thư đến): mỗi event một dòng, có ràng buộc unique để bản trùng tự rơi. Đó là tấm gương của outbox (`../04`, `../07`).

## Chiều đi ra: DocType `Webhook` của Frappe

Frappe có sẵn tính năng "khi tài liệu X có sự kiện Y thì POST tới URL Z", cấu hình trong Desk. Đọc nó để thấy một webhook được làm đúng cách trông thế nào.

```text
doc.save() / submit() …
 └─ run_method(...) → run_webhooks(self, method)              frappe/model/document.py:1265                    [S]
      chỉ các event: after_insert, on_update, on_submit,      frappe/integrations/doctype/webhook/__init__.py:6-14
        on_cancel, on_trash, on_update_after_submit, on_change
      bỏ qua khi đang import / patch / install / migrate      :40-41
      lấy các dòng Webhook đang bật cho DocType này (có cache) :44-47
      điều kiện (condition) đúng và event khớp → xếp hàng      :61-70
 └─ _add_webhook_to_queue: cất vào bộ nhớ,
      frappe.db.after_commit.add(flush…)                      :73-79     ← chỉ gửi nếu dữ liệu THẬT SỰ đã lưu
 ── commit ──
 flush_webhook_execution_queue                                 :82-119
      gộp trùng theo (webhook, tài liệu), giữ bản cuối         :98-104
      frappe.enqueue(enqueue_webhook, …)                       :112-118   ← gửi trong background job, không trong request
 ▼ worker
 enqueue_webhook(doc, webhook)                                 webhook.py:148
      dựng body (bảng field hoặc template Jinja) và header     :156-157, :242-252
      thử tối đa 3 lần, timeout mặc định 5 giây                :164-172
      lỗi → ngủ 1 giây rồi 4 giây giữa các lần                 :185-187
      MỌI lần thử ghi một dòng "Webhook Request Log"           :175, :180, :184, :192-216
 chữ ký (nếu bật enable_security):                             :219-232
      header X-Frappe-Webhook-Signature                        :20
      = base64( HMAC-SHA256( webhook_secret, JSON body ) )
```

Bốn bài học thiết kế nằm sẵn trong đoạn code đó, và luồng Xero của ta dùng lại cả bốn:
- gửi **sau commit** (`../06`);
- gửi trong **job**, không trong request;
- **log mọi lần thử**;
- **ký** body bằng HMAC-SHA256 rồi base64: đúng công thức Xero dùng cho chiều ngược lại.

### Dùng luôn DocType `Webhook` để đẩy Sales Invoice sang Xero được không?

Không, và đây là câu hỏi đáng hiểu rõ:

| Xero cần | DocType `Webhook` có |
|---|---|
| `Authorization: Bearer` đổi mỗi 30 phút, phải refresh (`../02`) | header **tĩnh** gõ trong Desk |
| tra cứu trước khi tạo, lưu `InvoiceID` trả về (`../03`) | gửi rồi thôi; không đọc kết quả để ghi lại |
| phân loại lỗi thành bốn loại, chờ `Retry-After` (`../07`) | 3 lần thử trong vài giây rồi bỏ cuộc |
| dòng outbox sống sót qua crash, có sweeper | hàng đợi nằm trong bộ nhớ tới lúc commit; mất là mất |
| cấu hình nằm trong code (AGENTS.md B3) | một bản ghi tạo trong Desk, chỉ sống trong database |

DocType `Webhook` hợp cho "báo cho hệ thống khác biết có thay đổi" khi mất một thông báo không sao. Ghi sổ kế toán thì không được mất và không được trùng → outbox + job của riêng ta.

## Chiều đi vào: Frappe không có sẵn, ta viết một endpoint

Xero không gửi cookie, API key hay bearer token của ta; nó chỉ **ký body**. Nên endpoint phải cho Guest gọi và tự kiểm chữ ký.

```text
POST /api/method/lab_core.api.xero_webhook.receive      @frappe.whitelist(methods=["POST"], allow_guest=True)
                                                        (allow_guest chỉ khi yêu cầu nói rõ: AGENTS.md B4)
 1. raw = frappe.request.get_data()                      đúng các BYTE đã nhận; không parse rồi serialize lại
 2. expected = base64( HMAC-SHA256( signing key, raw ) ) signing key nằm trong một field Password
    hmac.compare_digest(expected, header x-xero-signature)   lệch → HTTP 401, không làm gì khác
 3. mỗi event → một dòng inbox                           unique: tenant + resource + event date → trùng tự rơi
 4. trả 200 ngay                                          không gọi Xero ở đây
 5. job đọc inbox, GET từng resource, cập nhật ERPNext    lời gọi ra ngoài chỉ trong tasks/
```

Lớp chặn thêm có sẵn: decorator `rate_limit` ([S] `frappe/rate_limiter.py:104`) cho một endpoint công khai. Bước 2 là lý do **không** được để framework hay thư viện nào "sửa" body trước khi tính chữ ký: lệch một byte là sai chữ ký [X*].

## Webhook của Xero

[X*] = trích đoạn từ trang "Xero API webhooks" chính thức; [3] = bài của Hookdeck.

| Việc | Chi tiết |
|---|---|
| Bật ở đâu | trong developer portal, theo từng app: nhập delivery URL, chọn loại event; portal cấp một **webhook signing key** [3] |
| Header chữ ký | `x-xero-signature` = base64 của HMAC-SHA256(body, signing key) [X*] |
| Luật trả lời | chữ ký đúng → `2xx`; chữ ký sai → **`401`** [X*] |
| "Intent to receive" (xác nhận sẵn sàng nhận) | trước khi kích hoạt, Xero gửi một loạt POST qua HTTPS, **cố ý có cái ký sai**, để xem ta có trả đúng 2xx/401 không; có thể mất tới 30 giây; trượt thì bấm Validate lại [X*] |
| Thời gian trả lời | nhanh, cỡ vài giây (con số 5 giây là [G], chưa thấy trên trang chính thức) |
| Khi ta không trả lời | Xero thử lại thưa dần trong **24 giờ**; hết thì **tắt webhook** [X*] |
| Loại event | `CONTACT`, `INVOICE`, `CREDITNOTE`, `SUBSCRIPTION` [3]; devblog của Xero có thêm bài về webhook cho prepayment và overpayment [X*, mới thấy tiêu đề] |
| Kiểu event | `CREATE`, `UPDATE` [3] |
| Payload | mảng `events`, mỗi phần tử: `resourceId`, `resourceUrl`, `eventCategory`, `eventType`, `eventDateUtc`, `tenantId`, `tenantType` [3]. Mỏng: không có dữ liệu invoice |
| Trùng và thứ tự | có thể trùng; chống trùng theo `resourceId` + `eventDateUtc` [3] |

Lưu ý: không có event cho `Payment` trong danh sách trên. "Invoice đã được trả" tới dưới dạng `INVOICE` / `UPDATE` (trạng thái đổi thành `PAID`) [G]; phải `GET` invoice mới biết.

## Vì sao lab local không nhận được, và làm gì thay

```text
ta gọi Xero:   container ──► api.xero.com                          luôn được: kết nối đi RA
Xero gọi ta:   Xero ──► http://lab.localhost:8000/…   ✘            "localhost" của Xero là chính máy của Xero
```

| Cách | Là gì | Với demo 0 đồng |
|---|---|---|
| **Polling thưa** | job định kỳ `GET /Invoices` kèm header `If-Modified-Since` | **chọn cái này.** 15 phút một lần = 96 lời gọi/ngày, nằm gọn trong 1000/ngày của bậc Starter |
| Tunnel (đường hầm) | một công cụ cho máy bạn một URL HTTPS công khai tạm thời (chính devblog của Xero hướng dẫn với ngrok [X*, tiêu đề bài]) | có gói miễn phí [G], nhưng là công cụ cài thêm do con người chạy (AGENTS.md A3) và mở máy bạn ra internet. Không cần cho demo |
| Deploy | đưa cả hệ thống lên một server có tên miền + HTTPS | tốn tiền và công. Việc của dự án thật |

Ngay cả khi có webhook, vẫn giữ một lần polling định kỳ làm lưới an toàn: sau 24 giờ không nhận được, Xero tắt webhook và mọi event sau đó mất.

## Tự kiểm tra

1. Vì sao OAuth chạy được ở `localhost` còn webhook thì không? (Ai mở kết nối trong mỗi trường hợp?)
2. Endpoint nhận webhook của Xero cho Guest gọi. Cái gì ngăn một người lạ gửi event giả?
3. Vì sao không dùng DocType `Webhook` có sẵn của Frappe để tạo invoice bên Xero?

## Còn chưa biết

- Một POST của Guest không có session vào `/api/method/…` có bị kiểm tra CSRF chặn hay không; chưa trace (`frappe/auth.py`).
- Giới hạn thời gian trả lời chính xác của Xero, và danh sách loại event hiện hành: xem trang webhook của Xero khi cần xây.
- `"Webhook Request Log": 30` ở `frappe/hooks.py:541` [S: chỉ thấy dòng]: nhiều khả năng là số ngày giữ log; chưa đọc phần bao quanh.

## Nguồn

- [Xero API webhooks](https://developer.xero.com/documentation/guides/webhooks/overview/) · [Xero devblog: webhooks với Node, Express và ngrok](https://devblog.xero.com/keeping-your-integration-in-sync-implementing-xero-webhooks-using-node-express-and-ngrok-6d2976baac6d) · [Xero devblog: Prepayments webhooks](https://devblog.xero.com/introducing-prepayments-webhooks-a-more-efficient-way-to-sync-data-e0c469abad0b)
- [Hookdeck: guide to Xero webhooks](https://hookdeck.com/webhooks/platforms/guide-to-xero-webhooks-features-and-best-practices)
