# 04. Realtime: publish / subscribe (phát / đăng ký nghe) trong Frappe

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung. File: `frappe/realtime.py` (dòng 12-180), `realtime/index.js`, `realtime/handlers.js` (dòng 1-70).

## Trả lời trong năm dòng

1. Python không bao giờ giữ một socket tới trình duyệt. Nó làm một việc: `PUBLISH` một message JSON lên Redis channel `events`.
2. Một tiến trình Node riêng (socket.io, cổng 9000) đang subscribe channel đó và chuyển tiếp mỗi message tới một **room** (phòng: nhóm kết nối nhận chung tin).
3. Một room chỉ là một chuỗi: `user:<email>`, `doc:<DocType>/<name>`, `doctype:<DocType>`, `task_progress:<id>`, `all`, `website`.
4. Trình duyệt vào các room; với room của tài liệu, server Node trước hết hỏi Frappe qua HTTP xem user này có được đọc tài liệu không.
5. Nó là best effort (cố hết sức, không đảm bảo). Một message gửi lúc không ai nghe là mất. Database vẫn là sự thật; realtime chỉ nói "đi mà xem".

## Đường đi

```text
frappe.publish_realtime(event, message, room, user, doctype, docname, task_id, after_commit)   frappe/realtime.py:23  [S]
 ├─ chọn tên event                                                         :48-56
 │     không đưa → "task_progress" nếu có task_id, không thì "global"
 │     "msgprint" không có user → user hiện tại
 │     "list_update" → room = room của doctype; "docinfo_update" → room của doc
 ├─ chọn room (khớp đầu tiên thắng)                                        :58-71
 │     task_id            → task_progress:<id>   và after_commit bị ép TẮT        :59-63
 │     user               → user:<user>                                    :64-66
 │     doctype + docname  → doc:<doctype>/<docname>                        :67-68
 │     không có gì        → room của site: mọi user Desk                   :69-71
 ├─ after_commit=True → ghi nhớ nó; gửi khi commit, quên khi rollback      :73-81
 │     frappe.db.after_commit.add(flush_realtime_log)                      :76
 │     frappe.db.after_rollback.add(clear_realtime_log)                    :77
 │     cùng một (event, message, room) hai lần thì chỉ giữ một             :79-81
 └─ còn lại emit_via_redis(event, message, room)                           :83
        r.publish("events", {event, message, room, namespace: <site>})     :109-115
        Redis sập → bị lặng lẽ bỏ qua                                      :108

Node: realtime/index.js                                                    [S]
 subscriber.subscribe("events", …)                                         :77
   namespace = "/" + message.namespace     (mỗi site một namespace)        :79
   io.of(namespace).to(message.room).emit(message.event, message.message)  :81

Trình duyệt kết nối (socket.io)
 middleware authenticate: cần cookie sid hoặc header Authorization         realtime/middlewares/authenticate.js:26-43  [T]
   hỏi Frappe "sid này là ai?"                                             :52-56  [T]
 khi connect, realtime/handlers.js                                         [S]
   vào room của user, vào "website"                                        :5-6
   System User → vào thêm "all" (room của site)                            :8-10
   "doctype_subscribe" → kiểm tra quyền → vào room của doctype             :33-37
   "doc_subscribe"     → kiểm tra quyền → vào room của doc                 :58-62
   "task_subscribe" / "progress_subscribe" → vào, KHÔNG kiểm tra quyền     :43-56
   kiểm tra quyền = lời gọi HTTP tới frappe.realtime.has_permission        :12-27 → frappe/realtime.py:119
```

Tên các room, [S] `frappe/realtime.py:159-176`:

| Hàm | Chuỗi room |
|---|---|
| `get_doctype_room(doctype)` `:159` | `doctype:<doctype>` |
| `get_doc_room(doctype, docname)` `:163` | `doc:<doctype>/<docname>` |
| `get_user_room(user)` `:167` | `user:<user>` |
| `get_task_progress_room(task_id)` `:175` | `task_progress:<task_id>` |
| `get_site_room()` `:171` | (thân hàm chưa mở; `handlers.js:2` dùng `"all"`) |

## Ba điều code nói với bạn

**1. Bảo mật nằm ở room, không nằm ở message.** Ai ở trong room thì nhận message nguyên trạng. Vì vậy:
- Gửi tới `user=` thì an toàn, chỉ cho user đó.
- Gửi tới room của doc thì an toàn vì việc vào room có kiểm tra quyền (`handlers.js:58-62`).
- **Room của task không được kiểm tra** (`handlers.js:43-46`): bất kỳ ai biết hoặc đoán ra một `task_id` đều vào được. Không đặt dữ liệu nghiệp vụ vào một message tiến độ: một con số phần trăm và một nhãn, không gì khác. [S]
- Gửi không có room thì tới mọi user Desk của site (`realtime.py:69-71`). Gần như không bao giờ là điều bạn muốn.

**2. Lại là `after_commit`.** Cùng công cụ với job (`02`). Dùng `after_commit=True` bất cứ khi nào message mang nghĩa "cái này đã được lưu": nếu không, trình duyệt có thể refetch (lấy lại dữ liệu) trước khi commit và thấy dữ liệu cũ, hoặc thấy tin về một thứ sau đó bị rollback. Ngoại lệ: message có `task_id` được gửi ngay (`:59-60`), vì tiến độ hữu ích trong lúc làm việc, không phải sau đó.

**3. Mất là mất.** Redis pub/sub không giữ lại gì [G]; `emit_via_redis` thậm chí nuốt luôn lỗi kết nối Redis (`:108`). Nếu tiến trình Node restart, hoặc tab trình duyệt reconnect chậm một giây, message không bao giờ tới. Luật thiết kế: **event mang một cái tên và một id, trình duyệt phản ứng bằng cách fetch.** Khi đó một event bị mất chỉ làm màn hình cập nhật trễ, và polling có thể ở lại làm phương án dự phòng.

## Tiến độ của một job dài

[S] `frappe/realtime.py:12`: `publish_progress(percent, title, doctype, docname, description, task_id)`. Nó là một lớp bọc mỏng quanh `publish_realtime` (thân hàm chưa mở, chỉ xem chữ ký). Pattern [I]:

```text
request:  tạo dòng outbox → trả về tên của nó              (cái tên chính là "job reference")
job:      publish_realtime("lab_xero_sync", {"name": <note>, "status": "Synced"},
                           doctype="Lab Note", docname=<note>, after_commit=True)
browser:  đã subscribe doc:Lab Note/<note> → khi có event, refetch get_note
```

Gửi bên trong một job với `after_commit=True` hoạt động giống như trong một request, vì đường thành công của job kết thúc bằng `frappe.db.commit()` ([S] `frappe/utils/background_jobs.py:305`), thứ chạy các callback.

## Với SPA của ta

- Muốn nghe thì cần `socket.io-client`, thứ **không** nằm trong khóa UI (AGENTS.md B9). Dùng nó cần block "Needs package" và quyết định của bạn. Cho tới lúc đó SPA dùng polling. [T]
- Socket xác thực bằng cùng cookie `sid` như HTTP [T], nên một user SPA đã đăng nhập không cần gì thêm.
- Server socket ở cổng 9000 trong lab này (`plan/general/OVERVIEW.md`, "Site"). Một Vite dev server ở cổng khác phải proxy `/socket.io` tới nó [G]; chưa kiểm tra trong config của frontend.
- Với data layer nào thì phản ứng cũng cùng một ý [G]: khi có event, invalidate (đánh dấu hết hiệu lực) query của note đó, và để thư viện tự refetch. Cách đó giữ một nguồn sự thật duy nhất (HTTP endpoint) và biến realtime thành tùy chọn.

## Telegram, Slack và các bạn của chúng không phải là cái này

"Realtime" trong Frappe nghĩa là socket của trình duyệt. Gửi tới Telegram là một lời gọi HTTP đi ra bình thường: nó thuộc về một background job dưới `tasks/` (AGENTS.md B4), với cùng các luật như Xero: timeout, retry, idempotency. Một "bridge" (cầu nối: tiến độ job → Telegram) chỉ là một job thực hiện lời gọi đó tại điểm mà lẽ ra nó sẽ publish.

## So với thứ bạn đã biết [G]

| | Frappe realtime | Spring WebSocket + STOMP | Kafka / Redpanda |
|---|---|---|---|
| Truyền tới trình duyệt | socket.io (Node) | WebSocket trong JVM | không có (server tới server) |
| Fan-out (tỏa tin) giữa các process | Redis pub/sub | một broker relay, tùy chọn | chính cái log |
| Giao nhận | at most once (tối đa một lần), không replay (phát lại) | at most once | at least once (ít nhất một lần), replay theo offset |
| Topic | chuỗi room | destination `/topic/...` | topic + partition |
| Dùng cho | "có gì đó đổi, xem đi" | như trên | các dữ kiện không được phép mất |

Dòng cuối đó là điểm mấu chốt: **pub/sub dành cho gợi ý, queue hoặc outbox dành cho nghĩa vụ.** Xero sync là một nghĩa vụ.

## Thử đi (Desk)

1. Mở một Lab Note ở hai tab trình duyệt. Lưu ở một tab. Tab kia báo rằng tài liệu đã đổi: một message tới `doc:Lab Note/<name>`. [T]
2. Mở dev tools của trình duyệt, tab Network, lọc `WS` (hoặc `socket.io`), reload Desk: xem kết nối tới cổng 9000 và các frame. Không copy giá trị `sid` đi đâu cả.
3. Đọc `realtime/handlers.js:1-70` từ trên xuống dưới: 70 dòng chứa toàn bộ mô hình subscription.

## Còn chưa biết

- Thân hàm của `get_site_room` và `get_website_room` (`realtime.py:171, :179`).
- `frappe.realtime.has_permission` (`:119`) kiểm tra chính xác cái gì: quyền read là phỏng đoán tự nhiên, chưa xác nhận.
- Client của Desk subscribe thế nào (phía JS dưới `frappe/public/js/`), và hành vi reconnect.
