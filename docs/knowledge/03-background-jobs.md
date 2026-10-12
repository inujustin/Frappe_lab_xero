# 03. Background job (việc chạy nền) và scheduler (bộ lập lịch)

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung. File chính: `frappe/utils/background_jobs.py` (hôm nay đã đọc các dòng 30-375 và 535-735).

## Trả lời trong năm dòng

1. `frappe.enqueue` (đưa vào hàng đợi) ghi một message vào một list của Redis: site, **tên user**, đường dẫn hàm, tham số. Đó là tất cả những gì worker (tiến trình xử lý job) biết được.
2. Một tiến trình worker lấy message, dựng một Frappe context mới tinh cho site đó, đặt user theo tên, gọi hàm, rồi tự commit hoặc rollback.
3. Một job thất bại thì bị rollback, được ghi vào Error Log, và **không được retry (thử lại)**, trừ khi gặp database deadlock (khóa chết) hoặc khi code raise `RetryBackgroundJobError`.
4. Scheduler là một vòng lặp nhỏ: thức dậy, đọc các dòng `Scheduled Job Type`, và gọi chính `enqueue` đó cho những dòng đã tới hạn.
5. Không gì báo cho user rằng một job đã xong hay đã lỗi. Bạn tự xây: một field status, polling (hỏi lại định kỳ), hoặc realtime (`04`).

## Đường đi

```text
frappe.enqueue(method, queue="default", ..., **kwargs)        background_jobs.py:76        [S]
 ├─ deduplicate=True → bắt buộc có job_id                      :119-121
 │    job có id đó đang QUEUED hoặc STARTED → log, return None :122-125
 │    job tồn tại nhưng đã xong → xóa nó, đi tiếp              :126-129
 ├─ job_id = "<site>||<id với ':' → '|'>"                      :134, :649-659
 ├─ now=True → frappe.call(method) ngay tại đây, không queue   :152-154
 ├─ queue quá đầy → frappe.throw(QueueOverloaded)              :166, :717-735
 ├─ timeout = mặc định của queue (short 300, default 300, long 1500) :168-169, :62-69
 ├─ queue_args = {site, user: frappe.session.user, method, event, job_name, is_async, kwargs}   :177-185
 ├─ enqueue_after_commit=True → frappe.db.after_commit.add(enqueue_call); return None           :205-207
 └─ còn lại q.enqueue_call("frappe.utils.background_jobs.execute_job", kwargs=queue_args, ...)  :193-203, :209
                                │
                    Redis (redis-queue), list "<bench id>:<queue>"                               :622-629
                                │
tiến trình worker: start_worker → Worker(queues).work()         :320-358
 execute_job(site, method, event, job_name, kwargs, user, is_async, retry=0)   :239
   ├─ frappe.init(site, force=True, is_job=True); frappe.connect()             :244-245
   ├─ if user: frappe.set_user(user)                                           :251-252
   ├─ method = frappe.get_attr(method)        (chuỗi → hàm)                    :254-256
   ├─ frappe.local.job = {site, method, job_name, kwargs, user, after_job}     :260-267
   ├─ hook before_job                                                          :269-270
   ├─ retval = method(**kwargs)                                                :273
   │
   ├─ InternalError hoặc RetryBackgroundJobError → rollback                    :275-276
   │     retry < 5 và (retry tường minh, deadlock, lock timeout):
   │        destroy, sleep(retry + 1), execute_job(... retry + 1)              :278-290
   │     còn lại: log_error, raise                                             :292-294
   ├─ Exception khác bất kỳ → rollback, log_error, commit bản log, raise       :296-302
   ├─ thành công → commit                                                      :304-306
   └─ finally: hook after_job, frappe.local.job.after_job.run(), destroy       :308-317
```

## Các con số

Tất cả là [S], `frappe/utils/background_jobs.py`.

| Thứ | Giá trị | Dòng |
|---|---|---|
| Queue | `short`, `default`, `long`, cộng với các queue tùy biến từ `workers` trong common site config | `:60-73` |
| Timeout | short 300 s, default 300 s, long 1500 s | `:62-69` |
| Tên queue không biết | `frappe.throw("Queue should be one of …")` | `:547-560` |
| Kết quả được giữ trong Redis | 10 phút | `:39`, `:201` |
| Job thất bại được giữ trong Redis | 7 ngày | `:37`, `:200` |
| Số job thất bại được giữ tối đa | 1000 | `:38`, `:702-714` |
| Queue đầy | 500 job + 50 mỗi site; sau đó `enqueue` **throw** | `:44`, `:717-735` |
| Retry tự động | 5 lần, ngủ 1, 2, 3, 4, 5 giây, cùng worker | `:278-290` |

Hệ quả:
- **Một lần gọi Xero phải xong hẳn trong vòng 300 s**, và bạn phải truyền HTTP timeout của riêng mình: `frappe.integrations.utils.make_request` truyền `timeout=None` trừ khi bạn đưa một giá trị ([S] `frappe/integrations/utils.py:59, :75`), và không có timeout nghĩa là "chờ mãi mãi" [G].
- `enqueue` có thể raise ngay trong request của user khi queue đầy. Với `enqueue_after_commit=True`, việc đẩy xảy ra sau commit, nên lúc đó dữ liệu đã được lưu và job đơn giản là bị thiếu [I]. Thêm một lý do cho sweeper trong `12`.
- Retry có sẵn ngủ tổng cộng tối đa 15 giây. Nó được làm cho deadlock, **không phải** cho "Xero bảo chờ 60 giây".

## Job là ai?

Đây là phần người ta hay hiểu sai.

```text
lúc enqueue:  queue_args["user"] = frappe.session.user          :179   TÊN của người đã xếp nó vào hàng đợi
trong worker: frappe.connect() → set_user("Administrator")       frappe/__init__.py:280-281
              rồi, if user: frappe.set_user(user)                background_jobs.py:251-252
```

- Job có **tên** user, không có session: không `sid`, không cookie, không CSRF. Các kiểm tra quyền bên trong job (`doc.save()`, `frappe.get_list`) chạy với tư cách user đó. [S]
- **Job do scheduler xếp hàng thì chạy với tư cách Administrator** [I]: tiến trình scheduler làm `frappe.init(site); frappe.connect()` ([S] `frappe/utils/scheduler.py:115-116`), `connect` đặt Administrator ([S] `frappe/__init__.py:280-281`), và `enqueue` copy `frappe.session.user` (`:179`).
- **Sau một lần retry do deadlock, user bị mất** [I]: lời gọi retry ở `:290` là `execute_job(site, method, event, job_name, kwargs, is_async=is_async, retry=retry + 1)`. Trong đó không có `user=`, nên `user` là `None`, `:251` bị bỏ qua, và job chạy với tư cách bất cứ thứ gì `connect` đã đặt: Administrator. Chưa chạy thử; có một thí nghiệm bên dưới. Nếu đúng, đó là một sự thay đổi đặc quyền ngay bên trong một lần retry, và code trong `tasks/` không được dựa vào giả định "job chính là user đã tạo tài liệu".

Ý nghĩa với ta: [S] `lab_core/lab_core/tasks/xero_sync.py:36, :40` gọi `outbox.save()` và `doc.save()` với tư cách người tạo note, đó là lý do SPRINT.md cấp cho `Lab User` quyền write trên `Lab Xero Outbox` và gọi nó là một lối tắt. Một sweeper job (scheduler → Administrator) sẽ không cần dòng permission đó. Đây là câu hỏi thiết kế còn mở của track permissions; đó là một quyết định của bạn, không phải một dữ kiện.

## `enqueue_after_commit`, `job_id`, `deduplicate`: chúng kết hợp thế nào

Lời gọi của chính ta, [S] `lab_core/lab_core/lab_xero/outbox.py:33-40`:

```python
frappe.enqueue(SYNC_JOB, queue="default", enqueue_after_commit=True,
               job_id=f"lab-xero-sync:{outbox.name}", deduplicate=True, outbox_name=outbox.name)
```

Dò nó qua source:

1. `deduplicate` (chống trùng job) được kiểm tra **ngay bây giờ**, trong lúc request (`:119-129`).
2. Id trở thành `lab.localhost||lab-xero-sync|<name>` (`:134`, `:657-659`).
3. Việc đẩy vào Redis được cất trong `after_commit` và `enqueue` trả về `None` (`:205-207`). **Không có đối tượng job nào để trả về cho bên gọi**, nên một endpoint không thể trao lại "job reference" (tham chiếu tới job) từ lời gọi này; tên của dòng outbox chính là reference.
4. Nếu request rollback, lần đẩy đã cất bị bỏ (`02`). Nếu nó commit, lần đẩy được chạy.

Ba trường hợp biên, tất cả là [I]:
- **Hai lời gọi `queue()` trong một request** cho cùng một dòng: cả hai đều qua được kiểm tra ở bước 1 (chưa có gì trong Redis) và cả hai đều đẩy sau commit với cùng job id. RQ làm gì với job thứ hai cùng id thì chưa đọc. Dù sao bản thân job vẫn an toàn: nó lock dòng và return khi status là `Done` ([S] `tasks/xero_sync.py:11-13`).
- **Một job đang STARTED và job mới bị từ chối** (`:123-125`): nếu job đang chạy sau đó thất bại, không gì được xếp hàng. Hiếm, và một lần nữa sweeper che được.
- **`deduplicate` bảo vệ queue, không bảo vệ tác động.** Tính exactly-once (đúng một lần) đối với Xero đến từ idempotency key và row lock (khóa dòng), không bao giờ đến từ job id.

## Bên gọi biết kết quả bằng cách nào?

Frappe cho các công cụ sau; không cái nào là tự động.

| Công cụ | Bằng chứng | Hợp cho |
|---|---|---|
| Một field status trên tài liệu của bạn, được poll | của ta: `sync_status` trên Lab Note | Sự thật. Sống sót qua restart. Luôn xây cái này trước. |
| `frappe.publish_realtime` từ job | `04` | Làm màn hình cập nhật mà không phải chờ lần poll. |
| `get_job_status(job_id)` / `is_job_enqueued(job_id)` | [S] `:664-671` | Hỏi Redis "queued, started, finished, failed?". Biến mất 10 phút sau khi thành công (`:39`). |
| Callback `on_success` / `on_failure` | [S] `:86-87`, `:195-196` | Hiếm dùng. `on_failure` mặc định là cắt bớt danh sách job thất bại (`:187`). |
| Danh sách RQ Job trong Desk | [S] `frappe/core/doctype/rq_job/rq_job.py:42` (một DocType đọc từ Redis: `load_from_db` `:63`, `get_list` `:80`) | Xem bằng tay. |
| Error Log | [S] `:298` | Vì sao nó lỗi. |

## "Thất bại" nghĩa là gì

```text
hàm của bạn raise SomeError
 → rollback (mọi thứ job đã ghi đều mất, kể cả attempts += 1)               :297
 → dòng Error Log, rồi commit dòng đó                                       :298-300
 → exception đi lên RQ; job rơi vào failed registry (sổ job thất bại)       :302
 → không ai retry nó
```

Vậy một job có hai cách kết thúc trung thực:
- **Return bình thường** sau khi ghi "Failed" lên bản ghi của chính bạn: status được commit. Đây là điều [S] `tasks/xero_sync.py:29-31, :43-51` làm khi bị từ chối.
- **Raise**: mọi thứ bị rollback; chỉ Error Log biết. Dùng nó cho bug.

Một cái bẫy trong job của ta [I]: bộ đếm `attempts` được tăng ở [S] `tasks/xero_sync.py:18`, nhưng bất kỳ exception nào không phải `XeroTimeout` cũng không phải `XeroRejected` (một lỗi mạng thật, một bug) sẽ đi đường "raise", rollback xóa mất lần tăng đó, và note nằm ở `Queued` mãi mãi. Với một HTTP client thật, mọi lỗi transport (tầng truyền tải) phải được ánh xạ sang một trong các class exception của chính client, hoặc job cần một `except` cuối cùng ghi lại thất bại rồi re-raise sau một commit (commit được phép trong `tasks/`).

## Scheduler

```text
tiến trình worker hoặc scheduler → start_scheduler()              frappe/utils/scheduler.py:38     [S]
 ├─ file lock "config/scheduler_process": mỗi bench chỉ một scheduler      :45-52, :59-60
 └─ vòng lặp: ngủ tới tick kế tiếp, rồi enqueue_events_for_all_sites()     :54-56
       mỗi site: frappe.init, frappe.connect                                :115-116
         scheduler bị tắt / không hoạt động → bỏ qua                        :117-118
         enqueue_events()                                                   :132
           mọi dòng Scheduled Job Type có stopped = 0, xáo trộn             :135-136
           job_type.enqueue()                                               :140

ScheduledJobType.enqueue()            frappe/core/doctype/scheduled_job_type/scheduled_job_type.py:71   [S]
 ├─ is_event_due(): lần chạy kế tiếp (cron tính từ last_execution) <= now   :90-93, :107-141
 ├─ đã có trong queue? (job id "scheduled_job||<name>") → bỏ qua            :74, :95-101
 └─ frappe.enqueue(run_scheduled_job, queue=default|long, job_id=...)       :75-81, :187-188

trong worker: run_scheduled_job → doc.execute()                             :211-218, :143
 ├─ log "Start", đặt last_execution                                         :150, :183-184
 ├─ frappe.get_attr(self.method)()   ← hàm của bạn, KHÔNG có tham số        :156
 ├─ commit, log "Complete"                                                  :157-158
 └─ exception bất kỳ → rollback, log "Failed" (Scheduled Job Log)           :159-161
```

Các dữ kiện cần giữ:

| Dữ kiện | Bằng chứng [S] |
|---|---|
| Các dòng được tạo từ `scheduler_events` trong `hooks.py` bởi `sync_jobs` (chạy lúc migrate [G]) | `scheduled_job_type.py:221-225`, `:258-293` |
| Các tần suất và cron của chúng | `:113-127`: Hourly `0 * * * *`, Daily `0 0 * * *`, Weekly, Monthly, Yearly, và các biến thể "Long" |
| `"all"` nghĩa là mỗi `scheduler_interval // 60` phút, mặc định 240 s → **mỗi 4 phút** | `:126` |
| `"cron"` nhận một dict `{ "<cron>": [methods] }` | `:230-246`; ví dụ `frappe/hooks.py:231` |
| Tần suất "Long" và "Maintenance" đi vào queue `long`, còn lại vào `default` | `:187-188` |
| Một hàm được lập lịch **không nhận tham số** | `:156` |
| Một hàm được lập lịch bị lỗi không bao giờ raise ra ngoài; nó được log là Failed | `:159-161`, `:215-218` |
| Scheduled job bị bỏ qua ở maintenance mode (chế độ bảo trì) | `:213-214` |
| Sửa `scheduler_events` cần migrate, không chỉ restart [I] | các dòng được đồng bộ bởi `sync_jobs` |

Ví dụ từ framework, [S] `frappe/hooks.py:263-265`: dưới `"all"`: `frappe.email.queue.flush` và `frappe.email.queue.retry_sending_emails`. Đó là sweeper của email (`05`), và là hình mẫu cho một sweeper của outbox:

```python
# hooks.py  (con người thêm dòng này; AGENTS.md B2)
scheduler_events = {
    "cron": {"*/5 * * * *": ["lab_core.tasks.xero_sync.sweep_outbox"]},
}
```

## Nhiều job từ một request

- Mỗi `enqueue` là một lần ghi Redis: rẻ. [S] `:193-203`
- Không có thứ tự nào được hứa giữa hai job; với nhiều worker chúng chạy cùng lúc [G]. Nếu B cần kết quả của A, hãy xếp B từ bên trong A, hoặc gộp thành một job.
- Không có `enqueue_after_commit` thì worker có thể bắt đầu trước khi request commit và không tìm thấy tài liệu [T] (cram sheet 4). Luôn dùng nó khi job đọc thứ mà request đã ghi.
- 500 job đang chờ là trần mặc định (`:44`). Một vòng lặp xếp mỗi dòng một job sẽ đụng trần. Hãy xếp một job tự lặp, hoặc chia batch (lô).

## Thử đi (Desk)

1. Tạo một Lab Note. Mở `RQ Job` trong Desk: job `lab_core.tasks.xero_sync.process_outbox` xuất hiện và kết thúc. Mở `Lab Xero Outbox`: `attempts = 1`, status `Done`.
2. Tạo một note có title `fail one`. Outbox: `Failed`, kèm nội dung lỗi; Error Log: không có gì mới (job đã return bình thường).
3. Mở `Scheduled Job Type` trong Desk, tìm `queue.flush`, và đọc tần suất cùng lần chạy cuối của nó: đây là tick 4 phút.
4. Với suy luận "user bị mất khi retry": đọc `background_jobs.py:239-290` thêm một lần và tự quyết định xem `user` có tới được lời gọi thứ hai không. Đó là năm phút đọc và giải quyết được mà không phải chạy gì.

## Đọc tiếp trong source (offline)

1. `frappe/utils/background_jobs.py:76-209` rồi `:239-317`. Hai hàm đó là toàn bộ cơ chế.
2. `frappe/core/doctype/scheduled_job_type/scheduled_job_type.py:71-188`.
3. `frappe/utils/scheduler.py:38-147`.
4. `frappe/core/doctype/rq_job/rq_job.py`: Desk hiển thị dữ liệu Redis như thể nó là một DocType bằng cách nào.

## Còn chưa biết

- RQ làm gì khi hai job cùng id được đẩy vào.
- Tiến trình nào chạy vòng lặp scheduler trong lab này (một tiến trình `bench schedule` riêng hay một worker thông qua `FrappeWorker.start_frappe_scheduler`, `:361-375`); cả hai đường đều có trong source.
- Số worker và mức concurrency (chạy đồng thời) của `bench start` trong lab này; chưa đọc (nó nằm trong `docker/` và Procfile).
