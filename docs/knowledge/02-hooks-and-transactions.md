# 02. Hook và transaction

Nền tảng cho job, realtime, email và Xero. Nếu bạn chỉ đọc một file trước `10`–`12`, hãy đọc file này.

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung.

## Trả lời trong năm dòng

1. Một request hoặc một job chạy bên trong **một** database transaction (giao dịch). Bạn không mở nó và bạn không nên đóng nó.
2. `frappe.db.commit()` làm bốn việc theo thứ tự: chạy các callback `before_commit`, SQL `COMMIT`, bắt đầu transaction kế tiếp, chạy các callback `after_commit`.
3. `frappe.db.rollback()` **vứt bỏ** các callback `before_commit` và `after_commit` đang chờ, rồi chạy các callback `after_rollback`.
4. Bên trong một handler của document event (sự kiện của tài liệu), commit và rollback bị tắt: chúng chỉ in ra một cảnh báo.
5. `after_commit` là cách Frappe nói "chỉ làm tác động ra bên ngoài này nếu dữ liệu thật sự đã được lưu". Nó chỉ nằm trong bộ nhớ: crash là mất.

## Commit, từng dòng một

[S] `frappe/database/database.py:1176-1194`

```text
commit()
 ├─ _disable_transaction_control đang bật?  → cảnh báo và RETURN, không commit gì   :1178-1180
 ├─ before_rollback.reset(), after_rollback.reset()                             :1182-1183
 ├─ before_commit.run()                                                         :1185
 ├─ SQL "commit"  rồi begin()   (hoặc "commit and chain")                       :1187-1191
 ├─ value_cache.clear()                                                         :1193
 └─ after_commit.run()            ← job được đẩy vào Redis Ở ĐÂY                :1194
                                    realtime event được publish Ở ĐÂY
                                    webhook được xếp hàng Ở ĐÂY
```

[S] `frappe/database/database.py:1196-1217`

```text
rollback()
 ├─ có save_point → "rollback to savepoint X", không gì khác                    :1198-1200
 ├─ transaction control bị tắt → chỉ cảnh báo                                   :1216-1217
 └─ còn lại:
     ├─ before_commit.reset(), after_commit.reset()   ← các tác động đang chờ biến mất   :1202-1203
     ├─ before_rollback.run()                                                   :1205
     ├─ SQL "rollback" rồi begin()                                              :1207-1212
     └─ after_rollback.run()                                                    :1215
```

Bốn danh sách callback được tạo theo từng connection: [S] `frappe/database/database.py:129-132`.

### Điều này cho bạn cái gì, và lỗ hổng trong nó

```text
                        request thất bại        request thành công        process chết giữa
                        (rollback)              (commit)                  :1190 và :1194
 dòng tài liệu          mất                     đã lưu                    đã lưu
 dòng outbox            mất                     đã lưu                    đã lưu
 job after_commit       bị bỏ (:1203)           đẩy vào Redis             KHÔNG BAO GIỜ được đẩy   ← lỗ hổng
```

- Cột trái và cột giữa: đúng ngay từ cấu trúc. Không ai phải nghĩ.
- Cột phải [I]: dòng ghi `Pending` mà không có job nào tồn tại. Không gì trong Frappe sửa việc này giúp bạn. Cách sửa là một **sweeper** (job quét định kỳ): một scheduled job tìm các dòng `Pending` cũ và xếp chúng vào hàng đợi lần nữa. Email queue của chính Frappe hoạt động đúng như vậy (`05`). Outbox của ta chưa có sweeper (`12`).

## Ai được phép commit

| Ở đâu | Có được commit không? | Bằng chứng |
|---|---|---|
| Một endpoint, một hàm service | Về kỹ thuật thì có; luật của ta cấm (AGENTS.md B4). Request commit một lần ở cuối. | `frappe/app.py:465-466` [T] |
| Một handler của document event (`validate`, `on_update`, một hook `doc_events`) | Không. `_disable_transaction_control` được bật trong lúc nó chạy; `commit()` return sớm kèm cảnh báo. | `frappe/model/document.py:1642-1649` [T], `database.py:1178-1180` [S] |
| Một background job | Nó được commit giúp bạn khi thành công. Commit thêm được phép trong `tasks/` theo luật của ta. | `frappe/utils/background_jobs.py:305` [S] |
| Một patch | Có (luật của ta). | — |

**Code framework commit sau lưng bạn.** Bốn chỗ đã thấy hôm nay (bản gốc ghi "ba" nhưng bảng có bốn dòng); mỗi chỗ kết thúc sớm transaction *của bạn* nếu bạn gọi nó giữa chừng công việc:

| Lời gọi | Commit ở | Hệ quả |
|---|---|---|
| `TokenCache.update_data()` (một OAuth token vừa được refresh) | `frappe/integrations/doctype/token_cache/token_cache.py:70-71` [S] | Lấy Xero token **trước** lần ghi đầu tiên của job. |
| `ConnectedApp.initiate_web_application_flow()` | `frappe/integrations/doctype/connected_app/connected_app.py:113-114` [S] | Chỉ trong request "Connect to Xero"; ở đó vô hại. |
| `create_request_log()` (Integration Request) | `frappe/integrations/utils.py:209-210` [S] | Đừng dùng nó giữa hai lần ghi phải đi cùng nhau. |
| `SendMailContext.__enter__` / `__exit__` (status `Sending`, `Sent`) | `frappe/email/doctype/email_queue/email_queue.py:329, :348` [S] | Ổn: nó chạy trong scheduler job riêng. |

## Savepoint: hoàn tác một phần

[S] `frappe/database/database.py:1219-1230`: `savepoint(name)`, rồi `rollback(save_point=name)` chỉ hoàn tác phần SQL kể từ savepoint (điểm lưu tạm trong transaction). Các callback **không** bị đụng tới (`:1198-1200`), và source cảnh báo rằng các rollback watcher không hoạt động với savepoint (`:1224-1226`).

Còn có một decorator / context helper: [S] `frappe/database/database.py:1579` `savepoint(catch=Exception)`. Được dùng trong framework ở [S] `frappe/email/doctype/email_queue/email_queue.py:360` (`@savepoint(catch=Exception)` trên `notify_failed_email`): "thử cái này, và nếu nó lỗi thì chỉ hoàn tác riêng nó".

Một chỗ dùng thật, đã thấy: [S] `frappe/core/doctype/scheduled_job_type/scheduled_job_type.py:286-293`: insert, và khi gặp lỗi unique key thì rollback về savepoint rồi đi đường khác.

So sánh [G]: savepoint là thứ `Propagation.NESTED` của Spring dùng. Frappe không có gì giống `REQUIRES_NEW`: chỉ có một connection, nên không có transaction thứ hai, độc lập, bên trong một request. Nếu có thứ gì phải sống sót qua rollback (một dòng audit, một error log), các lựa chọn là: ghi nó sau rollback (đây là điều job runner làm với Error Log, `03`), hoặc làm trong một job khác.

## Hook, bản ngắn

Tất cả là [T] từ mục 3 của cram sheet, nhắc lại vì các file sau dựa vào:

```text
frappe.get_hooks(name)                  frappe/__init__.py:995        gộp hooks.py của mọi app đã cài
doc.run_method("validate")              frappe/model/document.py:1247
   method của controller trước, rồi các handler doc_events[<DocType>], rồi doc_events["*"]   :1654-1660
hook được cache suốt vòng đời của process ở developer mode              frappe/__init__.py:1009-1010
   → sửa hooks.py cần restart
```

Tên các hook gặp trong gói này, mỗi cái đã thấy trong `frappe/hooks.py` hôm nay [S]:

| Hook | Dòng trong `frappe/hooks.py` | Dùng để làm gì | Dùng trong file |
|---|---|---|---|
| `doc_events` | `:179` | handler trên vòng đời của tài liệu | `12` |
| `scheduler_events` | `:230` (`"cron"` `:231`, `"all"` `:263`) | job kiểu cron | `03` |
| `before_request` / `after_request` | `:474` / `:481` | bao quanh mọi HTTP request | `01` |
| `before_job` / `after_job` | `:486` / `:499` | bao quanh mọi background job | `03` |
| `auth_hooks` | đọc ở `frappe/auth.py:751` | authentication tùy biến | `01` |
| `override_email_send` | đọc ở `frappe/email/doctype/email_queue/email_queue.py:243` | thay thế việc gửi SMTP | `05` |

ERPNext dùng cùng những hook đó, nên nó có thể được mở rộng theo cùng cách: [S] `erpnext/erpnext/hooks.py:82` (`extend_doctype_class`), `:377` (`doc_events`), `:466` (`scheduler_events`).

**Luật của dự án (AGENTS.md B2a):** `doc_events`, class override và endpoint override chỉ dành cho code ta không sở hữu (Frappe, ERPNext, CRM). DocType của chính `lab_core` không bao giờ bị hook hay override: sửa thẳng controller của nó. Hai ví dụ ngay bên dưới chính là hai phía của luật này.

## Lifecycle (vòng đời) mà bạn sẽ treo Xero lên

Thứ tự các controller method cho một lần insert và một lần submit. [G] cho thứ tự đầy đủ (chỉ `validate` và hook composer là đã được trace, [T]); xác nhận trong `frappe/model/document.py` quanh `:478-600` khi bạn đọc nó.

```text
insert:  before_insert → validate → before_save → (DB insert) → after_insert → on_update → on_change
save:    validate → before_save → (DB update) → on_update → on_change
submit:  validate → before_submit → (DB update, docstatus 1) → on_submit → on_change
cancel:  before_cancel → (DB update, docstatus 2) → on_cancel → on_change
```

Ta đã làm gì với nó (DocType của ta, viết thẳng trong controller): [S] `lab_core/lab_core/lab_core/doctype/lab_note/lab_note.py:10-16`: `before_insert` đặt `sync_status = "Queued"`, `after_insert` gọi `outbox.queue(self)`. Cả hai chạy bên trong transaction của lần insert, nên note và dòng outbox của nó cùng được lưu hoặc cùng mất.

Với tài liệu của ERPNext (code không phải của ta), cùng lời gọi đó được đặt trong một handler `doc_events` trên `on_submit` (không phải `after_insert`: một invoice nháp chưa phải là invoice). Xem `12`.

## Thử đi (chỉ Desk, không có lệnh)

1. Mở một Lab Note trong Desk, đổi title, lưu. Trong danh sách `Lab Xero Outbox`, dòng của note đó không đổi: `after_insert` chỉ chạy một lần.
2. Đọc `frappe/database/database.py:1176-1217` với file này bên cạnh, và nói thành tiếng chuyện gì xảy ra với một job `enqueue_after_commit` khi request throw sau khi đã xếp nó vào hàng đợi.

## Còn chưa biết

- Thứ tự chính xác của các lifecycle method (sơ đồ ở trên) hôm nay chưa được mở ra xem.
- `before_commit` được dùng làm gì trong framework; mới chỉ thấy vị trí của nó trong thứ tự.
