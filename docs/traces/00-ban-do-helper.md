# Bản đồ các helper dùng chung của Frappe: cái gì ở đâu, đã trace chưa

Viết ngày 2026-10-13. Đây là **bản đồ**, chưa phải trace: nó liệt kê các cơ chế dùng chung của Frappe, chỉ đúng điểm vào trong source, và nói cái nào đã có ghi chú. Mỗi dòng sau này thành **một trace note riêng** trong thư mục này.

- Phiên bản: Frappe 16.51.0 (`frappe/__init__.py:58`).
- Mọi đường dẫn tính từ `frappe-bench/apps/frappe/frappe/`, trừ `realtime/` là `frappe-bench/apps/frappe/realtime/`.
- Mức xác nhận: mỗi `file:dòng` dưới đây là **đã thấy** (tìm bằng tên hàm trong phiên này). **Thân hàm chưa được đọc**, trừ các dòng ghi "đã có". Vì vậy cột "Làm gì" là theo tên hàm, chưa phải kết luận.
- Thứ tự trace con người đã chọn: **nhắn tin trước, rồi background job**; dữ liệu và request để sau.

## Cách dùng

Nói với agent: **"trace M7"** (hoặc số khác). Mỗi lần một số, ra một file `docs/traces/<chủ-đề>.md` theo mẫu của skill `code-tracer`: chuỗi lời gọi có `file:dòng`, ranh giới process, sơ đồ, điểm mở rộng, thí nghiệm cho con người.

```text
 NHẮN TIN (M)  ──►  BACKGROUND JOB (J)  ──►  DỮ LIỆU (D)  ──►  REQUEST (R)
 làm trước           làm thứ hai              sau                sau; phần lớn đã có
```

## M. Nhắn tin: mọi cách Frappe đưa một thông điệp tới người hoặc hệ thống khác

| # | Cơ chế | Điểm vào | Câu hỏi cần trả lời | Trạng thái |
|---|---|---|---|---|
| M1 | Email gửi đi | `email/__init__.py:132` `sendmail` → `email/doctype/email_queue/email_queue.py:569` `QueueBuilder`, `:855` `process` → `email/queue.py:129` `flush` → `email_queue.py:184` `send` → `email/smtp.py:17` `SMTPServer` | thư đi qua hàng đợi thế nào, thử lại ra sao | **đã có**: `docs/knowledge/05` |
| M2 | Email nhận về | `email/receive.py:66` `EmailServer`, `:396` `Email`, `:674` `InboundMail` | ai kéo thư, bao lâu một lần, thư thành bản ghi nào, chống nhận trùng thế nào | chưa |
| M3 | Notification (luật báo tự động theo sự kiện của tài liệu) | `model/document.py:1274` `run_notifications` → `email/doctype/notification/notification.py:848` `trigger_notifications`, `:878` `evaluate_alert`, `:403` `send` | chạy trong transaction nào, điều kiện được tính ra sao, gửi qua những kênh nào | chưa (`05` có nhắc) |
| M4 | Notification Log (chuông thông báo trong Desk) | `desk/doctype/notification_log/notification_log.py:132` `enqueue_create_notification`, `:165` `make_notification_logs`, `:200` `send_notification_email` | ai tạo dòng, tới trình duyệt bằng đường nào, có kèm email không | chưa |
| M5 | Realtime tới trình duyệt | `realtime.py:23` `publish_realtime`, `:12` `publish_progress`, `:86` `flush_realtime_log` | sự kiện đi từ Python tới trình duyệt thế nào, room, quyền | **đã có**: `docs/knowledge/04`, `cram-sheet.md` mục 5 |
| M6 | **Pub/sub** trên Redis (cơ chế nằm dưới M5) | bên phát: `realtime.py:100` `emit_via_redis`; bên nghe: `realtime/index.js:73` `get_redis_subscriber`, `:77` `subscriber.subscribe("events", …)`, `:81` `io.of(namespace).to(message.room).emit(…)` | kênh nào, ai phát, ai nghe, thông điệp có hình dạng gì, **mất khi nào** (không ai nghe, Node chết), khác hàng đợi của job ra sao | một phần trong `04`; chưa có note riêng |
| M7 | **Push notification** (tới điện thoại, trình duyệt qua dịch vụ trung gian) | `push_notification.py:12` `PushNotification`, `:19` `add_token`, `:65` `subscribe_topic`, `:91` `send_notification_to_user`, `:136` `send_notification_to_topic`, `:181` `is_enabled`, `:191` `_get_credential` | gọi tới dịch vụ nào, cần cấu hình gì, token của thiết bị lưu ở đâu, lab local dùng được không | chưa |
| M8 | Webhook đi ra | `integrations/doctype/webhook/__init__.py:33` `run_webhooks`, `:73` `_add_webhook_to_queue`, `:82` `flush_webhook_execution_queue`; `webhook.py:148` `enqueue_webhook`, `:219` `get_webhook_headers` | khi nào được xếp, gửi sau commit thế nào, chữ ký | **đã có**: `docs/knowledge/17` |
| M9 | SMS | `core/doctype/sms_settings/sms_settings.py:84` `send_sms`, `:89` `_send_sms`, `:115` `send_via_gateway` | gọi cổng SMS nào, đồng bộ hay qua job, cấu hình gì | chưa |
| M10 | Comment trên timeline và giao việc | `model/document.py:1746` `add_comment`; `desk/form/assign_to.py:44` `add` | một comment là bản ghi gì, ai được báo, giao việc tạo những gì | chưa (code Xero đã dùng `add_comment`) |
| M11 | Thông điệp trả về trong chính response | `utils/messages.py:11` `msgprint`; `model/document.py:1496` `notify_update` | `msgprint` và `throw` đi vào response thế nào; `notify_update` báo cho các tab khác ra sao | chưa (`docs/knowledge/14` có phần lỗi) |
| M12 | Gọi HTTP ra ngoài (helper chung) | `integrations/utils.py:49` `make_request`, `:96` `make_get_request`, `:108` `make_post_request` | timeout, lỗi, log; so với cách `lab_core/integrations/xero/client.py` tự gọi `requests` | chưa |

**Thứ tự đề xuất trong nhóm M:** M7 → M6 → M2 → M3 + M4 → M9 → M10 → M11 → M12.
M7 và M6 trước vì đó là hai nghĩa của "push sub"; M3 và M4 đi cùng nhau vì dùng chung đường.

## J. Background job và những thứ quanh nó

| # | Cơ chế | Điểm vào | Câu hỏi cần trả lời | Trạng thái |
|---|---|---|---|---|
| J1 | `enqueue` → Redis → worker | `utils/background_jobs.py:76` `enqueue`, `:239` `execute_job`, `:320` `start_worker`, `:535` `get_queue` | một lời gọi hàm thành job thế nào, chạy với user nào, transaction nào | **đã có**: `docs/knowledge/03`, `cram-sheet.md` mục 4 |
| J2 | Scheduler | `utils/scheduler.py:38` `start_scheduler`, `:132` `enqueue_events`; `core/doctype/scheduled_job_type/scheduled_job_type.py:71` `enqueue`, `:90` `is_event_due`, `:143` `execute`, `:211` `run_scheduled_job`, `:221` `sync_jobs` | nhịp tick, vì sao `*/5` chạy theo mốc 4 phút, chạy bù, hai lượt chồng nhau | **đã có**: `docs/knowledge/03` |
| J3 | Bên gọi biết kết quả job thế nào | `utils/background_jobs.py:664` `is_job_enqueued`, `:668` `get_job_status`, `:674` `get_job`; `realtime.py:12` `publish_progress` | trạng thái job đọc ở đâu, sống bao lâu, báo tiến độ cho trình duyệt (yêu cầu R-P2 trong danh sách của con người) | chưa |
| J4 | Xếp một method của tài liệu | `utils/background_jobs.py:212` `enqueue_doc`, `:235` `run_doc_method`; `model/document.py:1874` `queue_action` | khác `enqueue` thường ở đâu, khóa tài liệu trong lúc chờ thế nào | chưa |
| J5 | Commit, rollback, savepoint, "sau commit" | `database/database.py:1176` `commit`, `:1196` `rollback`, `:1219` `savepoint`, `:1579` `savepoint` (context manager) | thứ tự quanh đường commit | **đã có**: `docs/knowledge/02`, `20`, `cram-sheet.md` mục 6 |
| J6 | Các loại khóa | `utils/synchronization.py:18` `filelock`; `utils/file_lock.py:25` `create_lock`, `:50` `check_lock`; `utils/redis_semaphore.py:9` `RedisSemaphore` | mỗi khóa nằm ở đâu (file, Redis), sống qua worker chết không, dùng cái nào khi nào | chưa (`docs/knowledge/18` có bảng bốn loại khóa) |
| J7 | Giới hạn số request chạy đồng thời | `concurrency_limiter.py:82` `concurrent_limit`, `:35` `web_tier_concurrency`, `:130` `get_stats` | giới hạn theo gì, hết chỗ thì chờ hay từ chối | chưa |
| J8 | Ghi hoãn (gom nhiều insert rồi ghi một lần) | `deferred_insert.py:15` `deferred_insert`, `:28` `save_to_db` | dữ liệu chờ ở đâu, ai ghi, mất khi nào | chưa |
| J9 | Bên trong worker | `utils/background_jobs.py:411` `start_worker_pool`, `:684` `set_niceness`, `:717` `_check_queue_size`, `:702` `truncate_failed_registry`; `utils/redis_queue.py:7` `RedisQueue` | process, fork, tín hiệu, hàng đợi đầy thì sao (mục "xuống tới CPU và OS" trong danh sách) | một phần trong `03` |
| J10 | Monitor (đo từng request và từng job) | `monitor.py:24` `start`, `:29` `stop`, `:41` `get_trace_id`, `:51` `Monitor` | ghi gì, ghi ở đâu, `trace_id` có nối request với job không (liên quan request id của track A2, OpenTelemetry của track L) | chưa |

**Thứ tự đề xuất trong nhóm J:** J3 → J4 → J6 → J10 → J9 → J7 → J8.

## D. Dữ liệu (để sau)

| # | Cơ chế | Điểm vào | Trạng thái |
|---|---|---|---|
| D1 | Các tầng cache | `utils/caching.py:26` `request_cache`, `:78` `site_cache`, `:170` `redis_cache`, `:212` `http_cache`; `utils/redis_wrapper.py:38` `RedisWrapper`, `:64` `set_value`, `:79` `get_value`; `model/document.py:2281` `get_cached_doc`; `cache_manager.py:92`–`202` (các hàm xóa cache) | chưa (`docs/knowledge/15` là bản đồ) |
| D2 | Đặt tên bản ghi | `model/naming.py:141` `set_new_name`, `:271` `make_autoname`, `:408` `getseries` | chưa |
| D3 | Tìm kiếm toàn cục | `utils/global_search.py:242` `update_global_search`, `:371` `sync_global_search`, `:66` `rebuild_for_doctype` | chưa |
| D4 | File | `core/doctype/file/file.py:52` `File`, `:806` `save_file`, `:788` `write_file`, `:717` `get_content`; `utils/file_manager.py:41` `upload` | chưa (`docs/knowledge/06` là bản đồ) |
| D5 | PDF và in | `utils/pdf.py:106` `get_pdf`; `utils/print_format.py:374` `download_pdf` | chưa |
| D6 | Jinja | `utils/jinja.py:9` `get_jenv`, `:111` `render_template` | chưa (`docs/knowledge/05` có bản đồ) |
| D7 | Dịch | `translate.py:135` `get_all_translations`, `:129` `get_messages_for_boot` | chưa |
| D8 | Mật khẩu và mã hóa field Password | `utils/password.py:23` `get_decrypted_password`, `:51` `set_encrypted_password`, `:189` `encrypt`, `:201` `decrypt`, `:83` `check_password` | chưa (Token Cache và `client_secret` của Xero dựa vào đây) |
| D9 | Workflow | `model/workflow.py:120` `apply_workflow`, `:45` `get_transitions` | chưa |
| D10 | Lịch sử thay đổi | `core/doctype/version/version.py:15` `Version`, `:102` `get_diff` | chưa |

## R. Request (để sau; phần lớn đã có)

| # | Cơ chế | Điểm vào | Trạng thái |
|---|---|---|---|
| R1 | Vòng đời một request | `app.py:135` `application`, `:214` `init_request`, `:286` `process_response`, `:386` `handle_exception`, `:458` `sync_database` | **đã có**: `rpc-and-document-api.md`, `plan/general/TRACK-A.md` |
| R2 | RPC | `handler.py:47` `handle`, `:66` `execute_cmd`, `:292` `run_doc_method` | **đã có**: `rpc-and-document-api.md` |
| R3 | Đăng nhập, session, cookie | `auth.py:121` `LoginManager`, `:384` `CookieManager`, `:629` `validate_auth`, `:655` `validate_oauth`; `sessions.py:127` `get`, `:37` `clear_sessions` | **đã có**: `cram-sheet.md` mục 1 |
| R4 | Phân quyền | `permissions.py:81` `has_permission`, `:229` `get_doc_permissions`, `:284` `get_role_permissions`, `:353` `has_user_permission` | **đã có** một phần: `cram-sheet.md` mục 2 (perm level còn "Unknown") |
| R5 | Giới hạn tần suất | `rate_limiter.py:32` `RateLimiter`, `:104` `rate_limit`, `:15` `apply` | chưa |
| R6 | Log và Error Log | `utils/logger.py:38` `get_logger`; `utils/error.py:44` `log_error`, `:106` `get_error_fingerprint` | một phần: `docs/knowledge/14` |
| R7 | Recorder (ghi lại SQL của request) | `recorder.py:306` `record`, `:63` `record_sql`, `:316` `dump` | chưa (`docs/knowledge/15` có nhắc) |
| R8 | Sentry | `utils/sentry.py:19` `FrappeIntegration`, `:94` `before_send` | chưa (track L: theo dõi sự cố) |
| R9 | Dựng response | `utils/response.py:91` `build_response`, `:146` `as_json`, `:39` `report_error` | một phần: `docs/knowledge/14` |
| R10 | Frappe làm bên cấp quyền OAuth | `oauth.py:15` `OAuthWebRequestValidator`; `integrations/oauth2.py:38` `get_oauth_server`, `:94` `authorize`, `:67` `approve` | chưa (track B; track N stage S6) |
| R11 | Đăng nhập bằng bên thứ ba | `integrations/oauth2_logins.py:12` `login_via_google`, `:17` `login_via_github`, `:27` `login_via_frappe` | chưa (track B; track N) |
| R12 | Xác thực hai bước | `twofactor.py:65` `should_run_2fa`, `:80` `authenticate_for_2factor`, `:146` `confirm_otp_token` | chưa |
| R13 | Chạy code không tin cậy (Server Script) | `utils/safe_exec.py:95` `safe_exec` | chưa |
| R14 | File tĩnh | `middlewares.py:14` `StaticDataMiddleware` | chưa |

## Đếm

| Nhóm | Tổng | Đã có | Một phần | Chưa |
|---|---|---|---|---|
| M Nhắn tin | 12 | 3 (M1, M5, M8) | 1 (M6) | 8 |
| J Background job | 10 | 3 (J1, J2, J5) | 1 (J9) | 6 |
| D Dữ liệu | 10 | 0 | 0 | 10 |
| R Request | 14 | 3 (R1, R2, R3) | 3 (R4, R6, R9) | 8 |
| **Cộng** | **46** | **9** | **5** | **32** |

## Không có trong bản đồ này

- Các helper của ERPNext và CRM (chỉ liệt kê Frappe).
- Phía JS của Desk (`frappe.call`, `frappe.realtime` trong trình duyệt): thuộc track I.
- Những cơ chế tìm không thấy bằng tên thì không được thêm vào từ trí nhớ.
