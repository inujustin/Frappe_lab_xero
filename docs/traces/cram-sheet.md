# Cram sheet (tờ ôn nhanh): sáu cơ chế của Frappe, mỗi cái một trang

Làn T của sprint (`plan/general/SPRINT.md`), viết thành một file để đọc một hơi. Mọi tham chiếu dòng được mở ngày 2026-10-11 trong Frappe 16.51.0; đường dẫn bắt đầu từ `frappe-bench/apps/frappe/`. Chỉ đọc, không chạy gì. Request và API nằm trong `rpc-and-document-api.md`.

---

## 1. Đăng nhập, session và cookie `sid`

**Trả lời.** Kiểu lai, nghiêng về stateful (server giữ trạng thái). Trình duyệt chỉ giữ một id mờ đục (`sid`, tức không mang nghĩa gì). Server giữ dữ liệu session (phiên đăng nhập) ở hai nơi: Redis cho nhanh, bảng `Sessions` là bản bền vững. Mọi request đều tra id này; không có gì về user được tin từ phía trình duyệt.

```text
POST /api/method/login {usr, pwd}
  HTTPRequest()                       frappe/auth.py:33      được dựng cho mọi request (app.py:242)
   └ LoginManager()                   frappe/auth.py:121
       ├ login() → authenticate()     :146 → :257            check_password :314
       ├ post_login() → make_session  :171 → :224
       │    Session.start()           frappe/sessions.py:252  sid mới, csrf token
       │    insert_session_record()   :300-317                dòng trong tabSessions + Redis hash "session"
       └ set_cookies()                frappe/auth.py:75       cookie sid đi tới trình duyệt

mọi request về sau
  Session(resume=True)                sid đọc từ cookie       frappe/sessions.py:225
   └ resume() → get_session_data()    :319 → :350
        ├ Redis trước                 :360   hết hạn? xóa
        └ không có thì database       :381   rồi đặt lại vào Redis
   không có bản ghi → Guest           :336-346
```

**Những dòng quan trọng**
- `frappe/sessions.py:354-357`: cache trước, database là phương án dự phòng.
- `frappe/auth.py:81-96`: CSRF (chống giả mạo request từ trang khác) chỉ được kiểm tra với các verb làm đổi trạng thái, so với token lưu trong session.
- `frappe/sessions.py:521`: thời gian sống mặc định `240:00:00` lấy từ System Settings.

**So với `HttpSession` của Tomcat** (kiến thức chung, không phải đã trace): cùng ý tưởng, một id trong cookie và trạng thái nằm trên server. Khác biệt: kho của Frappe là kho dùng chung (Redis + database), nên bất kỳ web worker nào cũng phục vụ được bất kỳ request nào mà không cần sticky session (ghim user vào một server); và một background job hoàn toàn không dùng session, nó được cho biết tên user (mục 4).

**Thử đi.** Đăng nhập, không copy gì cả, rồi trong dev tools của trình duyệt xóa cookie `sid` và reload `/lab`: trang hello hiện "Please log in". Đăng nhập lại và so sánh `sid` mới.

**Chưa biết.** API key và OAuth bearer token (`frappe/auth.py:629` `validate_auth`) chưa được lần theo.

---

## 2. Một permission (quyền) được quyết định thế nào

**Trả lời.** Một hàm, nhiều cổng, tất cả đều phải qua: user có phải Administrator không, các role (vai trò) của họ có cấp hành động này trên DocType không, User Permission (giới hạn theo bản ghi cho từng user) hoặc một hook của controller có thu hẹp nó cho tài liệu này không, hoặc tài liệu có được share (chia sẻ) cho họ không.

```text
doc.check_permission("write")         frappe/model/document.py:398 → has_permission :403
 └ frappe.permissions.has_permission  frappe/permissions.py:81
     ├ role permission                get_role_permissions :284   các dòng DocPerm của role mà user có (get_roles :542)
     ├ mức tài liệu                   get_doc_permissions :229    luật theo owner ("if owner")
     ├ User Permission                has_user_permission :353    "chỉ tài liệu của Company X"
     ├ controller / hook              has_controller_permissions :483   hook has_permission của một app
     └ có share cho user không?       false_if_not_shared, gần :140

danh sách được lọc trong SQL, không phải từng dòng một:
  build_match_conditions              frappe/model/db_query.py:1032
  hook permission_query_conditions    frappe/model/db_query.py:1164, frappe/database/query.py:1607
```

**Những dòng quan trọng**
- `frappe/permissions.py:81-90`: chữ ký hàm; `doc=None` nghĩa là "user này có được làm việc này với DocType nói chung hay không".
- `frappe/model/db_query.py:1166`: nơi hook `permission_query_conditions` của một app được đọc.

**Điều này có nghĩa gì với code của ta.** `@frappe.whitelist` chỉ cho phép hàm được gọi. Hàm vẫn phải tự hỏi: `frappe.has_permission("Lab Note", "create", throw=True)` cho một hành động ở mức DocType, `doc.check_permission("write")` cho một tài liệu, và dùng `frappe.get_list` (có xét quyền) cho danh sách, không bao giờ dùng `frappe.get_all` (bỏ qua quyền).

**Thử đi.** Với tư cách `lab-user@example.test`, mở `/api/v2/document/Lab Note` trước và sau khi thêm dòng permission của role trong Desk.

**Chưa biết.** Permission level trên field (permlevel) và thứ tự chính xác của các cổng bên trong `has_permission` (các dòng 120-200 mới đọc lướt, chưa lần theo).

---

## 3. `hooks.py` được nạp thế nào và một document event nổ ra sao

**Trả lời.** Một hook (điểm móc mở rộng) chỉ là một cái tên ở mức module trong `hooks.py` của một app. Frappe import module `hooks` của mọi app đã cài, gộp các giá trị theo tên thành các list, và cache kết quả. Một document event (sự kiện của tài liệu) cũng là list đó, được tra theo DocType và tên method, chạy ngay sau method của chính controller.

```text
frappe.get_hooks("doc_events")        frappe/__init__.py:995
 └ _load_app_hooks()                  :965   với mỗi app đã cài: import <app>.hooks,
                                             nối mọi giá trị public vào dưới tên của nó
    được cache: theo process ở developer mode (:1009), còn lại thì trong Redis (:1011)

doc.save() → run_before_save_methods  frappe/model/document.py:1394 → run_method("validate") :1247
 └ hook(f) → composer                 :1617, :1654
      validate() của chính controller  trước
      rồi từng handler của doc_events[<DocType>][validate] và doc_events["*"][validate]

class bị thay hoặc mở rộng lúc nạp:   frappe/model/base_document.py:110 override_doctype_class
                                      frappe/model/base_document.py:190 extend_doctype_class
```

**Những dòng quan trọng**
- `frappe/__init__.py:1009-1010`: ở developer mode, hook được cache suốt vòng đời của process, nên **thay đổi `hooks.py` cần restart**.
- `frappe/model/document.py:1642-1649`: trong lúc một handler chạy, `frappe.db._disable_transaction_control` được bật lên: handler không thể commit hay rollback transaction của bên gọi.
- `frappe/model/document.py:1657-1660`: handler cho DocType đó, rồi tới handler cho `"*"`.

**Thứ tự giữa các app** là thứ tự các app đã cài (`get_installed_apps`, dùng ở `:967`); giá trị của app cuối cùng chỉ thắng với những hook được đọc như một giá trị đơn.

**Áp dụng cho code của ta.** `doc_events`, `override_doctype_class` và `extend_doctype_class` chỉ dùng cho code ta không sở hữu (Frappe, ERPNext, CRM), đặt dưới `overrides/`. DocType của chính `lab_core` thì không hook, không override: logic viết thẳng vào controller của nó. Lab Note làm đúng như vậy: `lab_core/lab_core/lab_core/doctype/lab_note/lab_note.py:10-16` (`before_insert` đặt `sync_status`, `after_insert` gọi `outbox.queue`).

**Thử đi.** Tạo một note trong Desk và một note trong SPA: cùng các controller method của Lab Note chạy cho cả hai (mỗi note có một dòng `Lab Xero Outbox`). Còn `doc_events` thì xem ở bước B3 của sprint: một handler trên `Customer` của ERPNext.
---

## 4. `frappe.enqueue` → Redis → worker

**Trả lời.** `enqueue` (đưa vào hàng đợi) ghi một message nhỏ (site, tên user, đường dẫn hàm, tham số) vào một list của Redis. Một tiến trình worker riêng lấy nó ra, tự thiết lập như một request mới tinh cho site và user đó, gọi hàm, và tự commit hoặc rollback. Job không chia sẻ gì với request đã xếp nó vào hàng đợi, ngoài những gì được đặt trong message.

```text
frappe.enqueue(method, queue="default", **kwargs)   frappe/utils/background_jobs.py:76
 ├ queue_args = {site, user, method, kwargs...}      :177-185   user là frappe.session.user
 ├ enqueue_after_commit=True → chạy sau commit       :205-206
 └ q.enqueue_call(execute_job, kwargs=queue_args)    :193       vào Redis (redis-queue)

tiến trình worker (bench worker, do bench start khởi chạy)
 execute_job(site, method, ..., user)                :239
   ├ frappe.init(site); frappe.connect()             :244-245   kết nối mới, transaction mới
   ├ frappe.set_user(user)                           :252       chỉ cái tên: không session, không cookie
   ├ hook before_job, rồi tới hàm
   ├ deadlock hoặc RetryBackgroundJobError → rollback, retry tối đa 5 lần   :275-290
   ├ lỗi khác bất kỳ → rollback, frappe.log_error, commit bản log           :296-300
   └ thành công → commit                             :305
```

**Những dòng quan trọng**
- `:205-206`: không có `enqueue_after_commit` thì worker có thể bắt đầu trước khi request commit và không tìm thấy tài liệu mà nó được giao xử lý.
- `:119-122`: `job_id` cùng với `deduplicate=True` từ chối một job thứ hai giống hệt.
- `:296-300`: một job thất bại để lại một dòng Error Log; không gì báo cho user trừ khi ta tự làm.

**Nhiều job trong một request:** mỗi job là một lần ghi Redis, rẻ; rủi ro là thứ tự (không có đảm bảo nào giữa các job) và job nhìn thấy trạng thái chưa commit, điều mà `enqueue_after_commit` loại bỏ.

**Thử đi.** Sprint B2: tạo một note, theo dõi `frappe-bench/logs/worker.log` và `sync_status` của note thay đổi một lát sau khi response đã trả về.

---

## 5. `publish_realtime` → Redis → socketio → trình duyệt

**Trả lời.** Python không bao giờ nói chuyện với socket của trình duyệt. Nó publish (phát) một message lên một Redis channel tên `events`; server socketio viết bằng Node đang subscribe (đăng ký nghe) và chuyển tiếp nó vào một room (phòng: nhóm kết nối nhận chung tin). Socket chứng minh nó là ai bằng chính cookie `sid` đó, thứ mà server Node kiểm tra bằng cách gọi Frappe qua HTTP.

```text
frappe.publish_realtime(event, message, user=... | doctype+docname | room)   frappe/realtime.py:23
 ├ after_commit=True → giữ lại cho tới khi transaction commit                 :73-76
 └ emit_via_redis → r.publish("events", {event, message, room})               :100-111

server socketio bằng node (bench socketio, cổng 9000)
 subscriber.subscribe("events")       realtime/index.js:77
  └ io.of(namespace).to(room).emit    realtime/index.js:81

trình duyệt kết nối
 middleware authenticate              realtime/middlewares/authenticate.js:26-43   cần cookie sid hoặc Authorization
  └ hỏi Frappe sid này là ai          :52-56 (Cookie: sid=...)
 vào các room                         realtime/handlers.js:5-9    room của user, room của site; room của doc khi yêu cầu :35-55
```

**Những dòng quan trọng**
- `frappe/realtime.py:110-111`: mối nối duy nhất giữa Python và Node là lần publish Redis này.
- `frappe/realtime.py:163-171`: tên room cho một tài liệu, một user, cả site.

**Với SPA.** Muốn nghe thì cần package `socket.io-client`, thứ không nằm trong khóa UI (AGENTS.md B9). Sprint dùng polling (hỏi lại định kỳ) trạng thái của note thay vào đó; realtime trong SPA là một quyết định riêng, để sau.

**Thử đi.** Trong Desk mở một Lab Note ở hai tab, lưu ở một tab: tab kia hiện "document has been modified", chính là đường đi này.

---

## 6. Commit và rollback, so với `@Transactional`

**Trả lời.** Mọi request là một transaction (giao dịch database) mà không cần annotation nào. Nó chỉ được giữ lại nếu request kết thúc không có exception **và** HTTP verb của nó là loại làm đổi trạng thái; một GET bị rollback ngay cả khi không có gì hỏng.

```text
application()                          frappe/app.py:135
 ├ exception → handle_exception, db.rollback           :181-184
 └ không exception → sync_database()                   :186 → :458
       POST, PUT, PATCH, DELETE hoặc flags.commit → commit   :465-466
       còn lại → rollback                                    :467-468

bên trong một handler của document event: commit và rollback bị tắt   frappe/model/document.py:1642-1649
một background job: transaction riêng của nó, commit khi thành công   frappe/utils/background_jobs.py:305
```

| | Spring `@Transactional` (kiến thức chung) | Frappe |
|---|---|---|
| Ranh giới | method được gắn annotation | cả HTTP request, hoặc cả job |
| Phải bật | có, theo từng method | không, luôn bật |
| Chỉ đọc | `readOnly = true` | tự động với GET |
| Lồng nhau | các thiết lập propagation | một transaction; `frappe.db.savepoint` để hoàn tác một phần |
| Commit thủ công | không khuyến khích | bị luật của ta cấm ngoài `tasks/` và `patches/` |

**Vì sao lần gọi Xero không thể nằm "trong" transaction.** Một commit chỉ bao phủ database của ta. Nếu request gọi Xero rồi sau đó thất bại, Xero sẽ giữ invoice còn ta thì rollback; nếu nó commit rồi lần gọi mới thất bại, ta sẽ có một note mà Xero chưa từng thấy. Vì vậy request ghi note **và một dòng outbox** trong một transaction, và một job (mục 4), được xếp hàng sau commit, thực hiện lần gọi với một idempotency key (khóa chống gửi trùng). Đó là bước B2 của sprint.

**Thử đi.** Sau B1: gọi `create_note` bằng GET thay vì POST (nó bị từ chối bởi bước kiểm tra verb); rồi thử nghĩ xem chuyện gì sẽ xảy ra nếu nó được cho phép: dòng sẽ được insert rồi bị rollback ở `:468`.
