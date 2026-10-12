# 06. Nền tảng Frappe mà luồng Xero đứng lên

Chỉ ba cơ chế của Frappe quyết định thiết kế Xero: **transaction**, **hook**, **background job** (kèm scheduler). File này đủ để không phải mở `docs/knowledge/02` và `03`.

Nhãn: xem `00-README.md`. Đường dẫn Frappe bắt đầu từ `frappe-bench/apps/frappe/`.

## Trả lời trong năm dòng

1. Một request = **một** database transaction; một job = một transaction khác. Xero không bao giờ nằm trong transaction nào.
2. `frappe.db.commit()` chạy SQL commit **rồi mới** chạy các callback `after_commit`. Job được đẩy lên Redis ở bước callback đó.
3. Một `doc_events` handler chạy **bên trong** transaction của lần lưu và không commit được. Đó là chỗ đúng để ghi dòng outbox.
4. Worker chỉ biết: site, **tên** user, tên hàm, tham số. Job lỗi thì rollback + Error Log và **không tự retry**.
5. Scheduler là cron của Frappe: gọi một hàm **không tham số** theo lịch. Sweeper của outbox sẽ là một hàm như vậy.

## 1. Transaction: commit, từng dòng

[S] `frappe/database/database.py:1176-1194`

```text
commit()
 ├─ đang ở trong document event? (_disable_transaction_control) → cảnh báo, RETURN, không commit   :1178-1180
 ├─ before_commit.run()                                                                           :1185
 ├─ SQL "commit", rồi begin() transaction kế                                                      :1190-1191
 └─ after_commit.run()        ← job enqueue_after_commit được đẩy lên Redis Ở ĐÂY                  :1194

rollback()                                                                                        :1196-1217
 ├─ before_commit.reset(), after_commit.reset()   ← mọi việc đang chờ "sau commit" bị vứt          :1202-1203
 └─ SQL "rollback"                                                                                :1211
```

Ba kết cục của một request tạo tài liệu + dòng outbox + job:

```text
                    request lỗi (rollback)   request xong (commit)   process chết giữa :1190 và :1194
 tài liệu           mất                      đã lưu                  đã lưu
 dòng outbox        mất                      đã lưu                  đã lưu
 job                bị bỏ (:1203)            đẩy lên Redis           KHÔNG BAO GIỜ được đẩy   ← lỗ hổng
```

Hai cột đầu đúng ngay từ cấu trúc. Cột thứ ba là lý do tồn tại của **sweeper** (`07`): dòng `Pending` nằm đó, không job nào tới. `after_commit` chỉ nằm trong bộ nhớ; "sau commit" không có nghĩa "được đảm bảo".

So với Spring (kiến thức chung, không phải thứ đã trace): `frappe.db.after_commit` ≈ `TransactionSynchronization.afterCommit`. Frappe không có `REQUIRES_NEW`: một request chỉ có một connection, nên không có transaction thứ hai độc lập.

### Ai được commit

| Ở đâu | Commit được không | Bằng chứng |
|---|---|---|
| Endpoint, hàm service | kỹ thuật thì được; luật của ta cấm (AGENTS.md B4). Request tự commit một lần ở cuối. | [K] `frappe/app.py:465-466` |
| Handler của document event (`validate`, `on_submit`, hook `doc_events`) | **Không**: cờ `_disable_transaction_control` được bật quanh handler; `commit()` chỉ cảnh báo | [S] `frappe/model/document.py:1641-1648`, `database.py:1178-1180` |
| Background job | được commit giúp khi hàm return bình thường; commit thêm được phép trong `tasks/` | [S] `frappe/utils/background_jobs.py:305` |

### Framework commit sau lưng bạn

| Lời gọi | Commit ở | Hệ quả cho job Xero |
|---|---|---|
| `TokenCache.update_data()` (token vừa refresh) | [S] `frappe/integrations/doctype/token_cache/token_cache.py:70-71` | **Lấy token trước lần ghi đầu tiên của job** |
| `ConnectedApp.initiate_web_application_flow()` | [K] `connected_app.py:113-114` | chỉ trong request "Connect"; vô hại |
| `create_request_log()` (Integration Request) | [K] `frappe/integrations/utils.py:209-210` | đừng gọi giữa hai lần ghi phải đi cùng nhau |

```text
SAI                                       ĐÚNG
 outbox.attempts += 1; save               token = get_active_token(user=…)   ← có thể commit; chưa có gì của ta đang mở
 token = get_active_token()  ← COMMIT     lock dòng outbox, attempts += 1
 gọi Xero → lỗi → rollback                gọi Xero
   (attempts đã commit: nửa trạng thái)   lưu kết quả → job commit một lần ở cuối
```

## 2. Hook: gắn vào ERPNext mà không sửa ERPNext

`hooks.py` là file chứa các cái tên; Frappe đọc nó để tìm handler của mỗi app. So với Spring (kiến thức chung): gần với `@Configuration` + event listener, nhưng bằng chuỗi.

```text
doc.submit()
 └─ doc.run_method("on_submit")                       frappe/model/document.py:1247   [S]
       1. method của controller ERPNext (code của họ)
       2. các handler doc_events["Sales Invoice"]["on_submit"] của mọi app   ← TA Ở ĐÂY   [K: thứ tự]
       3. doc_events["*"]
    tất cả chạy trong transaction của lần submit, commit bị tắt              :1641-1648     [S]
```

- `doc_events` có thật ở [S] `frappe/hooks.py:179` và ERPNext cũng dùng nó ([S] `erpnext/erpnext/hooks.py:377`).
- Hook được cache theo vòng đời process → **sửa `hooks.py` cần restart** [K].
- `hooks.py` của ta hôm nay chưa có `doc_events` ([S] chỉ có `website_route_rules`, `lab_core/hooks.py:8-10`).

Vòng đời của tài liệu (thứ tự đầy đủ là [G]; xác nhận trong `document.py` khi cần):

```text
insert:  before_insert → validate → (DB insert) → after_insert → on_update
submit:  validate → before_submit → (DB update, docstatus 1) → on_submit      ← ghi dòng outbox "create_invoice" ở đây
cancel:  before_cancel → (DB update, docstatus 2) → on_cancel                 ← ghi dòng outbox "void_invoice" ở đây
```

**Luật dự án (AGENTS.md B2a):** hook và override chỉ dành cho code ta không sở hữu. Với DocType của ta (Lab Note) lời gọi nằm thẳng trong controller ([S] `lab_core/lab_core/doctype/lab_note/lab_note.py:13-16`); với Sales Invoice của ERPNext nó nằm trong một handler `doc_events`.

## 3. Background job

```text
frappe.enqueue(method, queue, …, **kwargs)                       frappe/utils/background_jobs.py:76    [S]
 ├─ deduplicate=True (cần job_id): job cùng id đang chờ/đang chạy → không xếp nữa   :119
 ├─ ghi lại user = frappe.session.user  (chỉ là TÊN)                                 :179
 ├─ enqueue_after_commit=True → frappe.db.after_commit.add(…); chưa đẩy gì           :205-206
 └─ không thì đẩy ngay lên Redis
                    │
worker: execute_job(site, method, …, user, retry=0)              :239
 ├─ dựng context mới cho site, connect; if user: frappe.set_user(user)               :252
 ├─ gọi hàm của bạn
 ├─ deadlock / RetryBackgroundJobError → rollback; retry tối đa 5 lần,
 │     ngủ retry+1 giây NGAY TRONG worker                                            :275-290
 ├─ exception khác → rollback, log_error, commit bản log, raise                      :297-300
 └─ thành công → commit                                                              :305
```

| Con số | Giá trị | Bằng chứng |
|---|---|---|
| Timeout của job | `short` 300 s, `default` 300 s, `long` 1500 s | [S] `:62-69` |
| Retry tự động | 5 lần, ngủ 1…5 giây, chỉ cho deadlock hoặc khi code raise `RetryBackgroundJobError` | [S] `:275-290` |
| Queue đầy | khoảng 500 job chờ; sau đó `enqueue` throw | [K] `:44`, `:717-735` |
| Kết quả job giữ trong Redis | 10 phút | [K] `:39` |

Hệ quả cho Xero:
- Một lời gọi Xero phải xong **rất lâu trước 300 s** → luôn truyền HTTP timeout của riêng mình (ví dụ 30 s). Không có timeout nghĩa là chờ mãi [G].
- Retry có sẵn ngủ tổng cộng 15 giây và giữ luôn worker trong lúc ngủ. Nó cho deadlock, **không** cho `Retry-After: 47` của Xero. Với `429`, dòng outbox phải quay về trạng thái chờ và worker được giải phóng (`07`).
- Luôn dùng `enqueue_after_commit=True` khi job đọc thứ request vừa ghi; không thì worker có thể chạy trước commit và không thấy tài liệu [K].
- `deduplicate` bảo vệ **queue**, không bảo vệ **tác động**. Thứ chống tạo trùng bên Xero là row lock + tra cứu trước khi tạo (`07`).
- Với `enqueue_after_commit`, `enqueue` trả về `None`: không có "job id" để trả cho client. **Tên dòng outbox chính là tham chiếu.**

### Job là ai

```text
lúc enqueue:   user = frappe.session.user                 :179   tên của người đã xếp job
trong worker:  frappe.set_user(user)                      :252   không session, không cookie, không CSRF
```

- Kiểm tra quyền trong job (`doc.save()`, `frappe.get_list`) chạy với tư cách user đó. Vì vậy `SPRINT.md` cấp cho `Lab User` quyền write trên `Lab Xero Outbox` (một lối tắt).
- Job do **scheduler** xếp thì chạy với tư cách Administrator [K, suy ra]. Sweeper sẽ là như vậy.
- Lời gọi retry ở [S] `:290` **không truyền `user=`** → sau một lần retry do deadlock, job có thể chạy với tư cách khác [suy ra, chưa chạy thử]. Code trong `tasks/` không được giả định "job chính là người tạo tài liệu".
- Nối với `02`: job không bao giờ gọi `get_active_token()` không tham số; nó truyền `user=settings.connected_user`.

### "Thất bại" có hai nghĩa

```text
RETURN bình thường sau khi ghi "Failed" lên dòng của ta   → status ĐƯỢC commit            ← dùng cho lỗi nghiệp vụ (Xero từ chối)
RAISE                                                     → rollback HẾT, kể cả attempts += 1; chỉ Error Log biết   ← dùng cho bug
```

Job hôm nay làm đúng kiểu thứ nhất khi Xero từ chối ([S] `lab_core/tasks/xero_sync.py:29-31, :43-51`). Cái bẫy: một lỗi không phải `XeroTimeout` hay `XeroRejected` (đứt mạng thật, bug) đi đường "raise" → tài liệu nằm `Queued` mãi mãi. Client thật phải ánh xạ **mọi** lỗi transport sang một trong các class của nó.

### Người dùng biết kết quả bằng cách nào

Không gì tự báo. Thứ tự nên xây: (1) một field status trên tài liệu, SPA poll nó (đang có: `sync_status`); (2) về sau `frappe.publish_realtime` để màn hình cập nhật ngay; (3) danh sách `RQ Job` và `Error Log` trong Desk để xem tay.

## 4. Scheduler (cho sweeper)

```text
tiến trình scheduler: mỗi tick → đọc các dòng "Scheduled Job Type" → dòng nào tới hạn thì frappe.enqueue
trong worker:  frappe.get_attr(self.method)()     ← hàm của bạn, KHÔNG tham số        scheduled_job_type.py:156   [S]
               lỗi → rollback, ghi log "Failed", không raise ra ngoài                 :159-161                   [S]
```
(file: `frappe/core/doctype/scheduled_job_type/scheduled_job_type.py`)

- Khai báo trong `hooks.py` dưới `scheduler_events` (có thật ở [S] `frappe/hooks.py:230`). `"all"` = mỗi 4 phút theo mặc định ([S] `:126`); `"cron"` nhận biểu thức cron.
- Các dòng `Scheduled Job Type` được tạo từ `hooks.py` lúc migrate → **đổi `scheduler_events` cần migrate, không chỉ restart** [K, suy ra].
- Hình mẫu có sẵn: chính Email Queue của Frappe là một outbox có sweeper (`frappe.email.queue.flush` chạy dưới `"all"`) [K].

```python
# hooks.py — do con người thêm (AGENTS.md B2)
scheduler_events = {
    "cron": {"*/5 * * * *": ["lab_core.tasks.xero_sync.sweep_outbox"]},
}
```

## 5. Tóm lại: hỏng trước hay sau đường commit

Mọi câu hỏi "hỏng thì sao" của luồng Xero quy về một câu: nó hỏng ở phía nào của đường commit?

```text
   TRONG TRANSACTION CỦA LẦN SUBMIT            │   SAU COMMIT (response đã đi)
 submit Sales Order                            │  job: gọi Xero, ghi kết quả    (transaction RIÊNG)
   controller của ERPNext                      │  job kéo trạng thái / credit note về
   handler của ta (overrides/) → dòng outbox   │
 hỏng → raise → rollback TẤT CẢ                │  hỏng → lần submit KHÔNG bị kéo lùi
 người dùng thấy lỗi ngay                      │  thứ còn lại: dòng outbox + trạng thái trên Sales Order
                                        COMMIT ┘
```

| Hỏng ở | Chuyện gì xảy ra | Việc của ta |
|---|---|---|
| Handler `on_submit` (không ghi được dòng outbox) | cả lần submit bị rollback; không có đơn đã submit mà thiếu dòng outbox | không gì: đó là điều ta muốn |
| Giữa commit và lúc job được đẩy | đơn đã submit, dòng `Pending`, không có job | sweeper (`07`) |
| Job: Xero từ chối | job ghi `Failed` + lý do rồi **return** → được commit; Sales Order vẫn submitted | người sửa dữ liệu, bấm Retry |
| Job: lỗi bất ngờ, worker chết | transaction của job rollback; dòng vẫn `Pending`; chỉ Error Log biết | sweeper; chạy lại an toàn vì tra-rồi-tạo (`07`) |
| Job kéo về chết giữa chừng (thiết kế ở `09`: một lần kéo là một transaction) | những Sales Order đã cập nhật trong lần đó bị rollback cùng con trỏ `last_pull_at` | lần sau kéo lại từ con trỏ cũ; ghi đè giá trị nên không trùng (`09`) |

Ba điều rút ra:
- **Không bao giờ rollback lần submit vì Xero hỏng.** Người dùng đã nhận "OK". Response nghĩa là "đã nhận"; "đã sang Xero" là `lab_xero_sync_status`, do job ghi sau.
- **Thứ nối hai phía của đường kẻ là dòng outbox**, ghi *trước* commit, trong cùng transaction với lần submit. Không có nó, việc hỏng sau commit không để lại dấu vết nào.
- **Hoàn tác sau commit là một hành động mới**, không phải rollback: cancel Sales Order → một dòng outbox `void_invoice` → job void bên Xero (`07`, `10`).

## Tự kiểm tra

1. Request throw **sau khi** đã gọi `frappe.enqueue(..., enqueue_after_commit=True)`. Job có chạy không? Dòng nào quyết định?
2. Vì sao handler `on_submit` là chỗ an toàn để ghi dòng outbox, nhưng là chỗ sai để gọi Xero?
3. Job nhận `429` với `Retry-After: 60`. Vì sao không raise `RetryBackgroundJobError`?
