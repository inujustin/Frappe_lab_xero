# 90. Self-check (tự kiểm tra)

Trả lời từ trí nhớ trước, rồi mới mở file ghi trong ngoặc. Đáp án ngắn nằm ở cuối; đừng cuộn xuống cho tới khi bạn đã thử.

## Transaction và hook (`02`)

1. Những việc này xảy ra theo thứ tự nào bên trong `frappe.db.commit()`: SQL commit, các callback `after_commit`, các callback `before_commit`?
2. Một request xếp một job với `enqueue_after_commit=True`, rồi throw. Chuyện gì xảy ra với job, và dòng nào làm việc đó?
3. Bạn gọi `frappe.db.commit()` bên trong một method `validate`. Chuyện gì xảy ra?
4. Kể tên hai hàm của framework tự commit và có thể cắt đôi transaction của bạn.
5. Một savepoint rollback cái gì, và để yên cái gì?

## Background job (`03`)

6. Chính xác có gì trong message mà `enqueue` ghi vào Redis?
7. Một job raise `ValueError`. Nó có được retry không? Còn lại gì trong database?
8. Một job chạy với tư cách user nào khi (a) một user đã đăng nhập xếp nó, (b) scheduler xếp nó?
9. Timeout mặc định của queue `default` là bao nhiêu, và vì sao nó quan trọng với một lời gọi HTTP?
10. `enqueue(..., enqueue_after_commit=True)` trả về gì? Điều đó có nghĩa gì với việc "trả một job reference cho bên gọi"?
11. Mặc định, một hàm `scheduler_events["all"]` chạy thường xuyên cỡ nào?
12. Vì sao `RetryBackgroundJobError` là công cụ sai cho một `429` của Xero?

## Realtime (`04`)

13. Việc duy nhất Python làm để gửi một realtime event là gì?
14. Một socket vào những room nào mà không qua kiểm tra quyền nào?
15. Một realtime event được publish trong lúc trình duyệt đang reconnect. Chuyện gì xảy ra với nó? Luật thiết kế nào rút ra từ đó?
16. Vì sao một message có `task_id` bỏ qua `after_commit=True`?

## Email (`05`)

17. `frappe.sendmail(...)` return. Mail đã rời server chưa?
18. Liệt kê các status của một dòng Email Queue.
19. Cái gì ngăn một lần retry gửi mail cho cùng một recipient hai lần? Trong trường hợp nào nó vẫn có thể xảy ra?
20. Cái gì giải cứu một dòng kẹt ở `Sending`?

## Xero (`10`, `11`, `12`)

21. Header nào cho Xero biết một lời gọi dành cho organisation nào?
22. Access token và refresh token sống bao lâu, và việc refresh có gì đặc biệt?
23. Trong Xero, verb nào tạo và verb nào tạo-hoặc-update?
24. Sau một timeout ở "create invoice", hai cách thật để biết nó có tồn tại không là gì? Client giả của ta cung cấp cách nào mà Xero thật không có?
25. Xếp vào rejected (bị từ chối) / busy (bận) / unknown (không rõ) / auth lost (mất xác thực): `400`, `429`, connection reset sau khi gửi, `503`, token refresh trả về `None`.
26. `ConnectedApp.get_active_token()` trả về token của ai khi được gọi không có tham số bên trong một job? Vì sao đó là một bug chực xảy ra?
27. Vì sao job phải lấy token trước lần ghi đầu tiên của nó?
28. Một crash ngay sau SQL commit để lại gì trong database của ta? Cái gì sửa nó?
29. Một Payment Entry của ERPNext trả ba invoice. Bao nhiêu payment của Xero, và idempotency key phải chứa gì?
30. Compensation cho một invoice Xero đã authorised mà tài liệu local bị cancel là gì, và khi nào nó bị chặn?

---

## Đáp án

1. `before_commit` → SQL commit (và begin) → `after_commit`. `frappe/database/database.py:1185-1194`.
2. Nó bị bỏ: `rollback()` reset `after_commit` ở `database.py:1203`. Không gì tới được Redis.
3. Một cảnh báo và return sớm; không gì được commit (`database.py:1178-1180`), vì các method của tài liệu chạy với transaction control bị tắt.
4. `TokenCache.update_data` (`token_cache.py:70-71`) và `create_request_log` (`frappe/integrations/utils.py:209-210`). Còn có `initiate_web_application_flow` (`connected_app.py:114`).
5. Chỉ phần SQL kể từ savepoint. Các callback (`after_commit` và các bạn của nó) và mọi thứ ngoài database, như file, không bị đụng tới (`database.py:1198-1200`, `:1224-1226`).
6. Site, tên user, đường dẫn method, event, tên job, `is_async`, và các keyword argument (`background_jobs.py:177-185`).
7. Không được retry. Mọi thứ job đã ghi bị rollback; một dòng Error Log được commit; RQ đánh dấu job là failed (`:296-302`).
8. (a) User đó, theo tên, không có session (`:179`, `:251-252`). (b) Administrator, suy ra từ `scheduler.py:115-116` và `frappe/__init__.py:280-281`.
9. 300 giây (`:62-69`). Một lời gọi HTTP không có timeout riêng có thể treo cho tới khi worker bị kill, và `make_request` mặc định không có timeout (`integrations/utils.py:59`).
10. `None` (`:205-207`). Chưa có đối tượng job nào, nên reference để trao lại là bản ghi của chính bạn (dòng outbox), không phải một job id.
11. Mỗi 4 phút (`scheduled_job_type.py:126`: 240 giây // 60).
12. Nó chỉ ngủ 1–5 giây, ngay trong worker, chiếm giữ worker (`:278-290`); `Retry-After` thường là một phút. Thay vào đó dòng nên quay về trạng thái chờ.
13. `PUBLISH` một message JSON lên Redis channel `events` (`realtime.py:109-115`).
14. Room user của chính nó, `website`, `all` với System User (`handlers.js:5-10`), và bất kỳ room tiến độ task nào nó xin vào (`:43-56`).
15. Nó bị mất; pub/sub không lưu gì. Luật: event mang một id, client refetch, và polling ở lại làm phương án dự phòng.
16. Tiến độ là để được thấy trong lúc làm việc, trước bất kỳ commit nào (`realtime.py:59-60`).
17. Chưa. Mặc định một dòng đã được ghi vào Email Queue (`email/__init__.py:138`, `:277`); scheduler gửi nó trong vòng khoảng 4 phút.
18. Not Sent, Sending, Partially Sent, Sent, Error (`email_queue.py:172`, `:329`, `:338`, `:343`, `:346`).
19. Một dấu "đã gửi" theo từng recipient (`email_queue.py:236-238`, `:266`). Nó vẫn có thể lặp nếu worker chết sau khi SMTP nhận mail và trước khi dấu đó được commit.
20. `retry_sending_emails`, mỗi 4 phút, cho các dòng ở `Sending` lâu hơn 15 phút (`queue.py:185-192`).
21. `xero-tenant-id`. [G]
22. 30 phút và 60 ngày; refresh token chỉ dùng một lần và được thay ở mỗi lần refresh, nên cái mới phải được lưu và hai worker không được refresh cùng lúc. [G]
23. `PUT` tạo; `POST` tạo hoặc update. [G]
24. Gửi lại với cùng `Idempotency-Key`, hoặc tra bản ghi theo số hiệu của chính ta (`InvoiceNumber`). Client giả có `find_by_key` (`client.py:30`); Xero không có endpoint như vậy. [G]
25. `400` rejected; `429` busy; reset sau khi gửi là unknown; `503` busy; `None` là auth lost.
26. Token của `frappe.session.user`, user mà job đang chạy dưới danh nghĩa (`connected_app.py:147`), thường không phải user đã bấm "Connect". Lần tra cứu không trả về token nào. Luôn truyền connected user đã lưu.
27. Vì một lần refresh có commit (`token_cache.py:70-71`); bất cứ thứ gì ghi trước nó sẽ bị commit ngay cả khi job sau đó thất bại.
28. Một dòng outbox `Pending` và một tài liệu `Queued`, không có job. Một sweeper trên scheduler, giống `flush` của email queue.
29. Ba. Key cần có invoice của từng dòng: `Payment Entry:<name>:<invoice>:create_payment`.
30. Void nó (`Status: VOIDED`). Bị chặn khi còn một payment hoặc credit đang áp vào nó. [G]
