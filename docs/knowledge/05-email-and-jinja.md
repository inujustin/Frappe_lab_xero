# 05. Email và Jinja

Nhãn: [S] đã thấy hôm nay, [I] suy ra, [G] kiến thức chung. Hôm nay đã đọc: `frappe/email/queue.py:129-200`, `frappe/email/doctype/email_queue/email_queue.py:163-275, :328-375, :515-568, :855-920`. Với `frappe/email/__init__.py`, `notification.py`, `email_account.py` và `utils/jinja.py` thì chỉ đọc danh sách hàm và vài dòng: những phần đó là **bản đồ**, và có ghi rõ như vậy.

## Trả lời trong năm dòng

1. `frappe.sendmail(...)` không gửi. Mặc định nó ghi một dòng **Email Queue** (hàng đợi email) trong transaction của bạn.
2. Mỗi 4 phút scheduler chạy `frappe.email.queue.flush`, lấy tối đa 500 dòng đang chờ và gửi từng dòng qua SMTP.
3. Mỗi dòng có một status (`Not Sent`, `Sending`, `Sent`, `Partially Sent`, `Error`) và một bộ đếm `retry`; mỗi recipient (người nhận) có dấu "đã gửi" riêng, nên một lần retry không gửi mail cho cùng một người hai lần.
4. Một hàm được lập lịch thứ hai giải cứu các dòng kẹt ở `Sending` quá 15 phút.
5. Đây là **outbox pattern** (mẫu hộp thư đi), đầy đủ và đang chạy production. Hãy đọc nó như thiết kế tham chiếu cho outbox của Xero (`12`).

## Đường đi của một email

```text
frappe.sendmail(recipients, subject, message | template+args, delayed=True, now=None, ...)
                                                    frappe/email/__init__.py:132      [S: chữ ký hàm]
 ├─ delayed mặc định là True                        :138
 ├─ "if not delayed:" (now được suy ra từ nó)       :232                              [S: chỉ dòng này]
 ├─ QueueBuilder(...)                               :235-237
 └─ q = builder.process(send_now=False)             :277                              [S: chỉ dòng này]

QueueBuilder.process()                              frappe/email/doctype/email_queue/email_queue.py:855   [S]
 ├─ không có recipient nào → return []              :862-863
 ├─ ≤ 100 recipient và không "separately": MỘT dòng Email Queue chứa mọi recipient    :869-873
 │      EmailQueue.new(..., ignore_permissions=True)                                   :871
 └─ còn lại: các batch 1000 → frappe.enqueue(self.send_emails, queue="long")           :874-888
          mỗi recipient một dòng; dùng lại một SMTP session                            :890-919

  … request commit; giờ dòng đã bền vững …

scheduler, mỗi 4 phút ("all")                       frappe/hooks.py:263-264           [S]
 frappe.email.queue.flush()                         frappe/email/queue.py:129         [S]
  ├─ việc gửi bị tạm ngưng (default "suspend_email_queue") → return                    :140-141
  ├─ get_queue(): status Not Sent hoặc Partially Sent, đã qua send_after,
  │     tạo cách đây hơn 10 s, order by priority desc, retry asc, creation asc,
  │     limit 500 (conf email_queue_batch_size)                                        :164-182
  └─ với mỗi dòng: get_doc(..., for_update=True) → email_queue.send()                  :148-151
        quá nhiều thất bại trong batch → dừng cả lần flush                             :152-161

EmailQueue.send()                                   email_queue.py:184                [S]
 ├─ bị mute, sai status hoặc bị tạm ngưng → return                                     :174-182, :192-193
 └─ with SendMailContext(self):
      __enter__: status = "Sending", COMMIT                                            :328-330
      với mỗi recipient chưa được gửi:                                                 :236-238
         dựng message cho recipient này                                                :240
         hook override_email_send → gọi nó thay cho SMTP                               :243-244
         còn lại SMTP sendmail (hoặc Frappe Mail)                                      :246-264
         đánh dấu recipient này là đã gửi                                              :266
      __exit__:                                                                        :332-348
         không lỗi → status "Sent"
         lỗi và retry < giới hạn (3) → "Not Sent" hoặc "Partially Sent", retry + 1     :335-341, :565-566
         lỗi và đã hết lượt retry → "Error" + một Notification Log tới owner           :342-344, :361-373
         COMMIT status                                                                 :348
```

Sweeper thứ hai: [S] `frappe/email/queue.py:185-200` `retry_sending_emails`, cũng nằm dưới `"all"` (`frappe/hooks.py:265`): các dòng ở `Sending` có `modified` cũ hơn 15 phút được đặt lại (hoặc cho thất bại khi chạm giới hạn retry). Nó tồn tại vì một worker có thể chết giữa `__enter__` và `__exit__`.

## Email Queue như một bài học về thiết kế outbox

Mỗi lựa chọn thiết kế dưới đây có một bản song sinh trong outbox của Xero. Cột trái là source đã thấy; cột phải là lời khuyên [I].

| Email Queue làm | Dòng [S] | Lab Xero Outbox hôm nay (`lab_core/lab_core/lab_xero/outbox.py`, `tasks/xero_sync.py`) | Thiếu? |
|---|---|---|---|
| Dòng được ghi trong transaction của bên gọi | `email_queue.py:871` | Có: `outbox.py:24-30` từ `after_insert` | — |
| Một sweeper tìm các dòng đang chờ theo timer | `queue.py:129`, `hooks.py:264` | Không: chỉ có một lần `enqueue` sau commit | **Có** |
| Chọn có thứ tự: priority, ít retry nhất trước, cũ nhất trước | `queue.py:178` | không áp dụng | Khi có sweeper: `attempts asc, creation asc` |
| Bỏ qua các dòng trẻ hơn 10 s ("cửa sổ undo") | `queue.py:166, :176` | không áp dụng | Hữu ích: để job trực tiếp thắng cuộc đua |
| Lock dòng trước khi làm | `queue.py:150` `for_update=True` | Có: `xero_sync.py:11` | — |
| Đánh dấu "in progress" (đang xử lý) và commit trước lời gọi ra ngoài | `email_queue.py:329` | Không: status vẫn là `Pending` trong lúc gọi | Tùy chọn; chỉ cần khi có sweeper, để tránh bị nhặt hai lần |
| Dấu "đã gửi" theo từng recipient để một lần retry không lặp lại phần đã gửi | `email_queue.py:236-238, :266` | Idempotency key + "hỏi Xero trước" (`xero_sync.py:22`) | Cùng mục tiêu, công cụ tốt hơn |
| Bộ đếm retry có giới hạn, rồi một trạng thái cuối `Error` | `email_queue.py:335-344`, `:565-566` | `attempts` được đếm (`xero_sync.py:18`) nhưng không bao giờ giới hạn gì | **Có**, một khi có sweeper |
| Báo cho con người khi bỏ cuộc | `email_queue.py:361-373` | `sync_status = "Failed"` trên note | Đủ cho demo |
| Giải cứu các dòng kẹt ở "in progress" | `queue.py:185-200` | không áp dụng | Chỉ cần nếu thêm "in progress" |
| Công tắc dừng toàn cục | `queue.py:140`, `email_queue.py:541-545` | không có | Đáng có: "tạm dừng Xero sync" trong lúc có sự cố |
| Một batch tệ dừng cả lượt chạy | `queue.py:156-161` | không áp dụng | Ý hay: 20 thất bại liên tiếp thường nghĩa là Xero đang sập |

Một khác biệt cần để ý: SMTP không có idempotency key. Email Queue chỉ có thể tránh lặp lại cái nó **biết** là đã gửi; nếu worker chết ngay sau khi SMTP nhận mail và trước khi `:266` được commit, recipient đó nhận mail hai lần [I]. Xero cho ta một key, nên ta có thể làm tốt hơn email.

## Thời điểm bạn dự đoán được

- Đường mặc định: tới **4 phút** trước khi một mail đang chờ rời đi (tick `"all"`, `03`), cộng với cửa sổ undo 10 giây. [S]
- "Send now": dòng có một endpoint `send_now` cho Desk, [S] `email_queue.py:533-538` (kiểm tra quyền, rồi `record.send(force_send=...)`). Với `frappe.sendmail(now=True)` thì các dòng giữa `:232` và `:277` của `frappe/email/__init__.py` quyết định; chúng chưa được mở. Hãy đọc chúng trước khi dựa vào việc gửi ngay.
- Trong test không gì được gửi: [S] `email_queue.py:246` và `:268-270` (message cuối được giữ trong `frappe.flags.sent_mail`).
- Email có thể bị mute (tắt tiếng) toàn cục (`frappe.are_emails_muted()`, `email_queue.py:176`); cờ đó đến từ đâu thì chưa đọc. Trên một site dev, hãy chờ đợi các dòng nằm ở `Not Sent` cho tới khi có một Email Account gửi đi.

## Account nào gửi

[S] `email_queue.py:163-169`: `email_account` của chính dòng đó, không có thì `EmailAccount.find_outgoing(match_by_email=sender, match_by_doctype=reference_doctype)`.

Bản đồ của `frappe/email/doctype/email_account/email_account.py` (chỉ danh sách hàm, [S] cho số dòng):

| Hàm | Dòng | Vai trò |
|---|---|---|
| `find_outgoing` | `:506` | chọn account cho một sender / DocType |
| `find_default_outgoing` | `:535` | account mặc định |
| `find_from_config` / `get_account_details_from_site_config` | `:493` / `:563` | một account định nghĩa trong site config thay vì một dòng DocType |
| `get_smtp_server` | `:624` | dựng kết nối SMTP (`frappe/email/smtp.py:17` `SMTPServer`) |
| `get_oauth_token` / `get_access_token` | `:892` / `:602` | SMTP với OAuth (Google, Microsoft) thông qua một Connected App |
| `receive` / `get_inbound_mails` | `:691` / `:726` | mail đến |
| `pull` → `pull_emails` → `pull_from_email_account` | `:987` → `:1034` → `:1047` | kéo inbox theo lịch (`frappe/hooks.py:249`, dưới `"cron"`) |

Mật khẩu của account là một field Password (`_password`, `:463`): được mã hóa trong database, không bao giờ nằm trong repo (AGENTS.md B3). Với lab, một mail catcher cục bộ (một SMTP server chỉ lưu những gì nó nhận) là cách an toàn để xem mail mà không gửi cái nào [G]; thêm một cái là thay đổi ở `docker/` do bạn quyết định.

## Notification: mail không cần code

Một **Notification** là một dòng DocType: "khi một Sales Invoice được submit và `grand_total > 1000`, gửi cho những người này template Jinja này". Bản đồ của `frappe/email/doctype/notification/notification.py` (chỉ danh sách hàm):

| Hàm | Dòng | Vai trò |
|---|---|---|
| `trigger_notifications(doc, method)` | `:848` | điểm vào từ document event |
| `evaluate_alert(doc, alert, event)` | `:878` | đánh giá điều kiện cho một notification |
| `Notification.queue_send(doc, enqueue_after_commit=True)` | `:366` | bàn giao cho một background job, sau commit |
| `Notification.send(doc)` | `:403` | dựng context, chọn kênh |
| `send_notification_by_channel` | `:443` | Email, Slack, SMS, System Notification |
| `send_an_email` | `:543` | kết thúc ở đường Email Queue bên trên |
| `create_system_notification` | `:485` | icon chuông trong Desk (Notification Log) |
| `get_documents_for_today` / `trigger_daily_alerts` | `:270` / `:844` | cảnh báo theo ngày, từ scheduler (`frappe/hooks.py:288`) |
| `trigger_offset_alerts` | `:840` | cảnh báo mức phút (`frappe/hooks.py:234`, dưới `"cron"`) |

Chưa xác nhận: `trigger_notifications` được nối với document event thế nào (một mục `"*"` trong `doc_events` là phỏng đoán tự nhiên; các dòng `frappe/hooks.py:179-200` đã thấy thì cho thấy những handler khác).

Luật của dự án áp dụng ở đây: Notification tạo trong Desk chỉ sống trong database. AGENTS.md B3 muốn cấu hình nằm trong code; một Notification có thể được đánh dấu "standard" và export vào app (`validate_standard`, `:229`; `get_notification_templates`, `:1005`) [S: chỉ cái tên]. Hãy hỏi trước khi tạo một cái bằng tay.

## Jinja: một engine, bốn chỗ dùng

Bản đồ của `frappe/utils/jinja.py` (chỉ danh sách hàm, [S] cho số dòng):

| Hàm | Dòng | Vai trò |
|---|---|---|
| `get_jenv` | `:9` | Jinja environment dùng chung (sandboxed: chạy trong hộp cát [G]) |
| `render_template(template, context, is_path, safe_render)` | `:111` | render một chuỗi hoặc một file template |
| `get_template(path)` | `:72` | nạp một template từ thư mục `templates/` của một app |
| `get_email_from_template(name, args)` | `:79` | `templates/emails/<name>.html` (+ `.txt`) |
| `validate_template(html)` | `:96` | kiểm tra cú pháp, dùng khi lưu template trong Desk |
| `get_jinja_hooks` | `:223` | các method và filter do app thêm vào qua hook `jinja` |
| `get_jloader` | `:179` | template được tìm ở đâu: mọi app |

Cùng engine đó được dùng ở đâu [G cho danh sách; đã thấy một chỗ dùng]:
1. **Email**: `frappe.sendmail(template="x", args={...})`.
2. **Print format**: PDF của invoice.
3. **Trang web**: các file dưới `www/`, như `lab_core/www/lab.html` của ta.
4. **Template nhỏ nằm trong dữ liệu**: subject và message của Notification, body và URL của Webhook. Đã thấy: [S] `frappe/integrations/doctype/webhook/webhook.py:155` (`frappe.render_template(webhook.request_url, get_context(doc))`).

Các luật suy ra [G]: một template nhận `doc` và một bộ helper `frappe.*` giới hạn, không phải cả module; giá trị được HTML-escape trừ khi đánh dấu safe, nên `{{ doc.title }}` an toàn còn `{{ doc.html | safe }}` là một rủi ro có chủ đích; và dịch bên trong template là `{{ _("Text") }}`.

## Thử đi (Desk)

1. Mở `Email Queue` trong Desk. Nếu có dòng nào, mở nó ra: status, `retry`, bảng recipient với status theo từng recipient.
2. Mở `Scheduled Job Type`, tìm `queue.flush` và `retry_sending_emails`: tần suất "All".
3. Đọc `frappe/email/queue.py:129-182` (55 dòng) và `email_queue.py:328-348` (20 dòng). Rồi viết ra, không nhìn, năm trạng thái của một dòng và cái gì đưa nó từ trạng thái này sang trạng thái kia. Sơ đồ đó chính là state machine (máy trạng thái) của outbox Xero của bạn với tên đổi đi.

## Còn chưa biết

- `frappe/email/__init__.py:232-277`: `now=True` gửi thế nào, và nó có chờ commit không.
- `are_emails_muted` lấy giá trị từ đâu.
- Thân hàm của mọi thứ ghi là "bản đồ".
- Mail đến → tài liệu Communication: hoàn toàn chưa lần theo.
