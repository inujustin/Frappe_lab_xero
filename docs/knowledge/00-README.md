# Knowledge pack (gói kiến thức): các cơ chế của Frappe và tích hợp Xero

Viết ngày 2026-10-11 để đọc offline. Frappe 16.51.0 (`frappe-bench/apps/frappe/frappe/__init__.py:58`). Không chạy gì; source chỉ được đọc.

Mọi đường dẫn framework bắt đầu từ `frappe-bench/apps/frappe/` trừ khi nó bắt đầu bằng `erpnext/` hoặc `lab_core/`.

> **Ghi chú 2026-10-12.** Nhiều file ở đây (`03`, `10`, `12`, `13`, `15`, `18`, `19`, `90`) nhắc tới một "Xero giả" / "client giả": đó là client thế chỗ của sprint, còn nằm trong code (`lab_core/integrations/xero/client.py`). Kế hoạch tích hợp Xero (`plan/done/xero/PLAN.md`) **chỉ dùng Xero thật** và gỡ client đó ở phase P1. Cơ chế mà các file này giải thích (outbox, khóa dòng, hỏi trước khi tạo, SAGA) vẫn đúng; các thí nghiệm "tạo một note có title `fail` / `timeout`" sẽ không còn chạy được sau khi nó bị gỡ.

## Tin mỗi dòng đến mức nào

Mọi phát biểu mang một trong bốn nhãn. Hãy đọc chúng; chúng cho bạn biết cần kiểm tra lại cái gì.

| Nhãn | Ý nghĩa |
|---|---|
| **[S]** Seen (đã thấy) | Dòng đó đã được mở trong phiên này. `path:line` là thật với 16.51.0. |
| **[T]** Trace | Được dẫn trong `docs/traces/cram-sheet.md` hoặc `rpc-and-document-api.md` bởi một phiên trước. Hôm nay không mở lại. |
| **[I]** Inferred (suy ra) | Một kết luận rút từ các dòng đã thấy. Hợp logic, nhưng chưa ai chạy. Mỗi cái có một thí nghiệm. |
| **[G]** General (kiến thức chung) | Từ trí nhớ: public API của Xero, Spring Boot, HTTP, các pattern. **Chưa đối chiếu** với tài liệu của Xero hay bất kỳ source nào. Kiểm chứng khi online. |

Mọi thứ về API của chính Xero (file 10) đều là **[G]**. Trên đĩa này không có code Xero nào để dẫn. Các phần về cách Frappe sẽ nói chuyện với Xero (file 11, 12) là **[S]** ở phía Frappe.

## Thứ tự đọc

Xero trước, vì nó là mục tiêu; nhưng Xero đứng trên job và transaction, nên đọc hai cái đó trước nó.

```text
02 hooks + transactions ──┐
03 background jobs ───────┼──► 10 Xero API ──► 11 Xero OAuth trong Frappe ──► 12 thiết kế Xero sync ──► 13 SAGA
                          │
01 request, auth, perms ──┘ (ngắn; hai trace note giữ phần chi tiết)

độc lập, lúc nào cũng được:   04 realtime    05 email + Jinja    06 files    14 xử lý lỗi    15 tối ưu + GraphQL/gRPC    16 Swagger/OpenAPI    17 webhook    18 phi chức năng (race, deadlock…)    19 thứ tự + bẫy của stack    20 xử lý transaction (tổng hợp)    21 bench và toolchain
cuối cùng:                    90 self-check (câu hỏi, đáp án ở cuối)
```

| File | Track trong `plan/general/OVERVIEW.md` | Độ sâu |
|---|---|---|
| `01-request-auth-permissions.md` | A, A2, B, C | Ngắn. Bổ sung API key và bearer token vào các trace note. |
| `02-hooks-and-transactions.md` | D, J | Vừa. Thứ tự commit, `after_commit`, savepoint. |
| `03-background-jobs.md` | E | Sâu. Enqueue, worker, retry, scheduler. |
| `04-realtime-pubsub.md` | F | Sâu. Room, auth, after-commit. |
| `05-email-and-jinja.md` | H | Sâu về queue; Jinja chỉ là một bản đồ. |
| `06-files.md` | G | Một bản đồ chỉ chỗ đọc. Thân hàm chưa được mở. |
| `10-xero-api.md` | K | Sâu, toàn bộ là **[G]**. |
| `11-xero-oauth-in-frappe.md` | K, B | Sâu, **[S]**. OAuth client của chính Frappe. |
| `12-xero-sync-design.md` | K, "The Xero transaction idea" | Sâu. Outbox, idempotency, sáu trường hợp lỗi, ánh xạ field. |
| `13-saga.md` | K, mục 6 của "Order" (SAGA) | Vừa. Hệ thống khi không có và khi có SAGA; phần "có" là đề xuất thiết kế, lý thuyết là **[G]**. |
| `14-error-handling.md` | A2 | Vừa, **[S]**. Lỗi của request đi đâu, hook `after_request`, dạng lỗi thống nhất; kênh lỗi của job Xero. |
| `15-performance-and-api-styles.md` | M | Một bản đồ. Cache, query, đo đạc; GraphQL/gRPC so với thứ Frappe có; cái gì giúp luồng Xero. |
| `16-api-docs-swagger.md` | A | Vừa. OpenAPI/Swagger: Frappe không có sẵn, làm được tới đâu, được và mất gì; chưa có code. |
| `17-webhooks.md` | K, F | Vừa, **[S]** ở phía Frappe. Webhook là gì, DocType `Webhook` (chiều đi ra), endpoint nhận (chiều đi vào), webhook của Xero, vì sao lab local không nhận được. Bản song sinh: `docs/xero/knowledge/webhook.md`. |
| `18-non-functional.md` | J, E, C, L | Vừa, **[S]** ở phía Frappe. Yêu cầu phi chức năng: race condition (năm hình dạng), bốn loại khóa, deadlock và lock wait timeout, mức cô lập, timeout/retry/idempotency, các giới hạn, và bảng các yêu cầu còn lại; mười câu hỏi cho mọi tính năng. |
| `19-ordering-and-stack-pitfalls.md` | A, D, E, J | Vừa, **[S]** ở phía Frappe. Thứ tự trong một request, một document event, quanh commit; vì sao job không có thứ tự và năm cách tạo ra thứ tự; giả định sai về bên thứ ba; bẫy theo từng tầng của stack. |
| `20-transaction-handling.md` | J, E, D | Ngắn, tổng hợp. Một mô hình cho mọi tình huống transaction: hỏng trước hay sau đường commit; response đã đi mà job hoặc hook hỏng thì làm gì; năm luật; bảng công cụ. Đọc sau `02` và `03`. |
| `21-bench-and-toolchain.md` | runtime của lab | Vừa, **[S]** cho Docker và Frappe, **[G]** cho bên trong CLI. bench tìm Python (virtualenv `env/`) và Node/yarn (PATH) thế nào; cái gì chạy ở host, cái gì ở container; các file cấu hình của một bench; so với kubectl. |
| `22-ban-do-chu-de-va-tai-lieu-doc.md` | tất cả | Bản đồ. Danh sách muốn học so với các track; sáu chỗ kế hoạch gốc không còn khớp dự án; bảy chủ đề chưa có kiến thức (frontend, Clean Architecture, event-driven, OpenTelemetry, pre-commit, kiểm lệch DDL); thứ cần tài khoản ngoài; URL tài liệu gốc (toàn bộ **[G]**). |
| `90-self-check.md` | tất cả | Các câu hỏi để trả lời từ trí nhớ. |

## Cố ý không đề cập

Nói thẳng để bạn khỏi tìm:
- **Frontend (track I, I2):** Pinia Colada so với TanStack Query, routing Desk ↔ SPA. Không đọc gì trong `frontend/` hay `node_modules`; viết từ trí nhớ sẽ là đoán API của component (AGENTS.md B9).
- **Guardrails và observability (track L):** structural lint, OpenTelemetry. Chưa bắt đầu.
- **Nội bộ của permission:** perm level và thứ tự các cổng bên trong `has_permission` vẫn là "Unknown" trong cram sheet.
- **Thân hàm trong `file.py`, `notification.py`, `email_account.py`, `utils/jinja.py`, `utils/oauth.py`:** chỉ đọc danh sách hàm kèm số dòng. Những mục đó là bản đồ, và được đánh dấu như vậy.

## Năm ý tưởng buộc mọi thứ lại với nhau

1. **Một request = một transaction; một job = một transaction.** Không gì ngoài database là một phần của nó: Redis không, SMTP không, Xero không. (`02`)
2. **Vì vậy mọi tác động ra bên ngoài đều bị hoãn tới sau commit**, và Frappe có một công cụ cho việc đó, `frappe.db.after_commit`. Job, realtime event và webhook (lời gọi HTTP tự động báo sự kiện) đều dùng nó. (`02`, `03`, `04`)
3. **"Sau commit" không có nghĩa là "được đảm bảo".** Nếu process chết giữa lúc SQL commit và callback, tác động đó bị mất. Chỉ một dòng trong database là sống sót. Dòng đó là **outbox** (hộp thư đi). (`12`)
4. **Email Queue của Frappe vốn đã là một outbox.** Hãy đọc `05` như một ví dụ hoàn chỉnh của pattern bạn sắp xây cho Xero: một dòng, một status, một bộ đếm retry, một sweeper (job quét định kỳ).
5. **Một background job không phải là request của user.** Nó có tên user nhưng không có session, có transaction riêng, và sau một loại retry nhất định nó có thể còn không có cả tên user đó. (`03`)

## Từ của Frappe, kèm ý tưởng gần nhất bên Spring Boot

Cột bên phải là **[G]**: một phép so sánh để dễ nhớ, không phải thứ đã trace.

| Frappe | Nó là gì | Ý tưởng gần nhất bên Spring |
|---|---|---|
| DocType | Một bảng + form của nó + permission của nó, mô tả bằng JSON | `@Entity` + một màn hình CRUD sinh tự động |
| Controller (`lab_note.py`) | Một class có các lifecycle method (method vòng đời) (`validate`, `after_insert`) | Entity listener / một service gắn với một entity |
| `hooks.py` | Một file chứa các cái tên mà Frappe đọc để tìm handler của bạn | `@Configuration` + event listener, nhưng bằng chuỗi |
| `@frappe.whitelist` | Đánh dấu một hàm gọi được qua HTTP | `@RequestMapping` trên một method, với sơ đồ URL cố định |
| `frappe.local` | Biến toàn cục theo từng request (từng job) | `RequestContextHolder` / thread-local |
| `frappe.enqueue` | Đặt một lời gọi hàm lên một Redis queue | `@Async` với một broker thật, hoặc một lần gửi JMS |
| Scheduled Job Type | Một dòng cron tạo từ `scheduler_events` | `@Scheduled` |
| `frappe.db.after_commit` | Danh sách callback chạy sau SQL commit | `TransactionSynchronization.afterCommit` |
| Site | Một database + một config; một bench chứa được nhiều site | Một tenant (khách thuê) |
| bench | Thư mục chứa các app, site và môi trường Python | Server đã deploy và bộ công cụ của nó |
