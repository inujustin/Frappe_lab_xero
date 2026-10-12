# 18. Yêu cầu phi chức năng: race condition, deadlock, và những thứ làm hệ thống hỏng dù logic đúng

Viết ngày 2026-10-12. Kiến thức chung của kho này, không riêng cho Xero.

Nhãn: [S] đã thấy hôm nay (đường dẫn từ `frappe-bench/apps/frappe/`), [T] từ trace note hoặc file khác trong kho, [I] suy ra và chưa chạy, [G] kiến thức chung từ trí nhớ (cơ sở dữ liệu, hệ phân tán). Không chạy gì.

## Trả lời trong năm dòng

1. **Yêu cầu chức năng** nói hệ thống *làm gì*. **Yêu cầu phi chức năng** (non-functional requirement) nói nó làm việc đó *tốt đến đâu khi điều kiện xấu*: hai người cùng lúc, mạng chậm, process chết, tải cao, kẻ xấu.
2. Lỗi phi chức năng không hiện khi một người thử một lần. Nó hiện khi có **đồng thời**, **thất bại giữa chừng**, hoặc **số lượng lớn**.
3. Với đồng thời, Frappe cho ba công cụ: kiểm tra `modified` (phát hiện ghi đè), row lock `for_update` (xếp hàng), ràng buộc unique (chốt chặn cuối).
4. Với thất bại, câu trả lời luôn là cùng một bộ: transaction, timeout, retry có giới hạn, idempotency, và một bản ghi trạng thái nhìn thấy được.
5. Không cái nào tự có. Mỗi tính năng phải được hỏi cùng một danh sách câu hỏi (cuối file).

## Bản đồ

| Nhóm | Câu hỏi | Frappe / lab có gì | Đọc thêm |
|---|---|---|---|
| **Đồng thời** (concurrency) | hai việc cùng lúc có phá nhau không? | kiểm tra `modified`, `for_update`, unique, document lock, file lock | file này |
| **Tin cậy** (reliability) | hỏng giữa chừng thì còn đúng không? | transaction theo request/job, `after_commit`, retry của job, outbox | `02`, `03`, `12` |
| **Giới hạn và tải** (capacity) | nhiều quá thì sao? | timeout job, trần queue, trần số lần ghi, rate limit | file này, `03`, `15` |
| **Hiệu năng** (performance) | nhanh đủ không, vì sao chậm? | cache, `fields`, Recorder | `15` |
| **Bảo mật** (security) | ai được làm gì, lộ gì? | permission, CSRF, field Password, whitelist | `01`, cram sheet |
| **Quan sát được** (observability) | hỏng thì biết bằng cách nào? | Error Log, RQ Job, Scheduled Job Log, request id | `14`, `03` |
| **Toàn vẹn dữ liệu** (integrity) | dữ liệu có thể sai dạng không? | unique, link, chuyển `docstatus`, transaction | file này, `02` |
| **Bảo trì và nâng cấp** | sửa và lên phiên bản có đau không? | không sửa core, điểm mở rộng, schema qua migrate | `AGENTS.md` B2a, B3 |
| **Khôi phục** (recoverability) | mất dữ liệu thì lấy lại thế nào? | backup là việc của con người | [G] |

## Race condition (tranh chấp)

**Race condition**: kết quả phụ thuộc vào *thứ tự tình cờ* của hai việc chạy cùng lúc. Code đúng khi chạy một mình, sai khi chạy chen nhau.

### Năm hình dạng hay gặp

```text
1. LOST UPDATE (mất cập nhật)                  2. CHECK-THEN-ACT (kiểm rồi mới làm)
 A đọc doc (v1)        B đọc doc (v1)           A: "đã có dòng key X chưa?" → chưa     B: "đã có chưa?" → chưa
 A lưu (v2)                                     A: insert X                            B: insert X
                       B lưu → đè mất v2        ⇒ hai dòng cho một việc

3. READ-MODIFY-WRITE (đọc, tính, ghi)          4. LÀM HAI LẦN                         5. ĐỌC TRƯỚC KHI CÓ
 A đọc tồn = 5         B đọc tồn = 5            bấm Submit hai lần; job trùng;         request xếp job rồi mới commit;
 A ghi 5 - 3 = 2       B ghi 5 - 4 = 1          retry sau timeout                      worker chạy trước, không thấy tài liệu
 ⇒ đã xuất 7, sổ ghi còn 1 (hoặc 2)             ⇒ hai hóa đơn, hai lần trừ tiền
```

| # | Hình dạng | Công cụ của Frappe | Bằng chứng |
|---|---|---|---|
| 1 | Lost update | **Optimistic lock** (khóa lạc quan: không khóa, phát hiện lúc lưu): `check_if_latest` so `modified` trong database với `modified` lúc mở; lệch → `TimestampMismatchError` "has been modified after you have opened it" | [S] `frappe/model/document.py:1090-1116`, `frappe/exceptions.py:166` |
| 2 | Check-then-act | **Ràng buộc unique** trong database là chốt chặn cuối; phép kiểm `exists` chỉ để báo lỗi đẹp | [S] `frappe/exceptions.py:194` `UniqueValidationError`, `:106` `DuplicateEntryError` |
| 3 | Read-modify-write | **Row lock** (khóa dòng, khóa bi quan): `frappe.get_doc(..., for_update=True)`; `frappe.db.get_value(..., for_update=True)`. Người thứ hai **chờ** tới khi người thứ nhất commit, rồi đọc giá trị mới | [S] `document.py:82, :167-174`; `frappe/database/database.py:527-573` |
| 4 | Làm hai lần | kiểm tra chuyển `docstatus` (0→1→2, không lùi); `job_id` + `deduplicate`; và **idempotency** ở chỗ có tác động ra ngoài | [S] `document.py:1121-1132`; [T] `03` |
| 5 | Đọc trước khi có | `enqueue_after_commit=True` | [S] `frappe/utils/background_jobs.py:205-206` |

Chính Frappe dùng hình dạng 3 cho bộ đếm naming series: đọc dòng `tabSeries` với `for_update()` rồi mới tăng ([S] `frappe/model/naming.py:408-417`). Đó là lý do hai người tạo tài liệu cùng lúc không nhận cùng một số.

Trong code của ta:
- [S] `lab_core/lab_xero/outbox.py:17-30`: `frappe.db.exists` rồi `insert` là hình dạng 2. Hai request cùng key chen nhau → cả hai thấy "chưa có". Thứ cứu là field `idempotency_key` **unique** (`SPRINT.md`): lần insert thứ hai thất bại thay vì tạo dòng đôi. Không có unique thì lỗi này im lặng.
- [S] `lab_core/tasks/xero_sync.py:11-13`: lấy dòng outbox với `for_update=True` rồi kiểm tra `status == "Done"`: hình dạng 4 được chặn bằng công cụ của hình dạng 3.

### Ba điều về row lock mà người mới hay vấp

1. **Lock sống tới hết transaction**, không tới hết câu lệnh. Nó được nhả khi commit hoặc rollback. Vậy một `frappe.db.commit()` giữa chừng (kể cả do code framework gọi, `02`) **nhả lock sớm**.
2. **Giữ lock trong lúc gọi mạng là giữ người khác đứng chờ.** Job của ta giữ lock dòng outbox suốt lời gọi Xero, có chủ đích; cái giá là timeout HTTP phải ngắn (`15`).
3. **Lock chỉ có nghĩa nếu mọi đường ghi đều lấy nó.** Một chỗ ghi thẳng bằng `frappe.db.set_value` không qua lock là một lỗ. (Luật dự án cấm `set_value` trên tài liệu: AGENTS.md B4.)

### Bốn loại khóa có trong Frappe

| Khóa | Phạm vi | Qua nhiều máy? | Hết khi | Bằng chứng |
|---|---|---|---|---|
| Row lock của database (`for_update`) | một dòng | có (database dùng chung) | commit / rollback | [S] `document.py:167-174` |
| Kiểm tra `modified` (optimistic) | một tài liệu | có | không giữ gì; chỉ phát hiện | [S] `document.py:1090-1116` |
| Document lock: `doc.lock()` / `doc.unlock()`, một file khóa cho tài liệu; ném `DocumentLockedError`; dùng khi một tài liệu đang "queued for execution" | một tài liệu | **không** (file trên đĩa của site) | `unlock()`, hoặc quá hạn | [S] `document.py:1901-1927`, `:545-553`; `exceptions.py:214` |
| `filelock(name, timeout=30)`: file khóa đặt tên, chờ tối đa `timeout` giây rồi ném `LockTimeoutError` | bất kỳ đoạn code nào | **không** (cùng bench) | ra khỏi khối `with` | [S] `frappe/utils/synchronization.py:18-45` |

Quy tắc chọn [G]: xung đột hiếm và người dùng sửa form → optimistic. Xung đột thường xuyên hoặc là phép tính trên số (tồn kho, hạn mức, bộ đếm) → row lock. Bảo vệ một việc không phải dòng database (refresh token, một file) → `filelock`, và nhớ nó chỉ đúng trên một máy.

## Deadlock (khóa chết)

**Deadlock**: hai transaction, mỗi cái giữ một lock mà cái kia cần. Không ai tiến được.

```text
Transaction A                      Transaction B
 lock dòng 1 ✔                      lock dòng 2 ✔
 muốn lock dòng 2 … chờ B           muốn lock dòng 1 … chờ A
                 └────────── vòng tròn chờ ──────────┘
database phát hiện, GIẾT một bên (bên đó nhận lỗi và bị rollback); bên kia đi tiếp        [G]
```

Họ hàng gần: **lock wait timeout**: không có vòng tròn, chỉ là chờ một lock quá lâu rồi bỏ cuộc.

Frappe nhận ra cả hai và đổi thành exception có tên:

| Lỗi của MariaDB | Frappe coi là | Thành exception | Bằng chứng |
|---|---|---|---|
| `LOCK_DEADLOCK`, và `CHECKREAD` (bản ghi đã đổi kể từ lần đọc: xung đột snapshot) | deadlock | `frappe.QueryDeadlockError` | [S] `frappe/database/mariadb/database.py:27-29`; `frappe/database/database.py:277-278`; `frappe/exceptions.py:258` |
| `LOCK_WAIT_TIMEOUT` | timed out | `frappe.QueryTimeoutError` | [S] `mariadb/database.py:32-33`; `database.py:280-281`; `exceptions.py:254` |

Chuyện gì xảy ra sau đó:

- **Trong background job**: có nhánh retry: tối đa 5 lần, ngủ 1, 2, 3, 4, 5 giây, cho deadlock (1213), lock wait timeout (1205) và `RetryBackgroundJobError` ([S] `frappe/utils/background_jobs.py:275-290`).
  Một điểm đáng kiểm bằng thí nghiệm [I]: nhánh đó bắt `frappe.db.InternalError` (`:275`), trong khi một deadlock đi qua `frappe.db.sql` đã được đổi thành `QueryDeadlockError`, là lớp con trực tiếp của `Exception` (`exceptions.py:258`), không phải `InternalError`. Nếu đúng như đọc, deadlock kiểu đó rơi vào nhánh `except Exception` chung (`:296-302`: rollback, Error Log, **không retry**). Chưa chạy; đừng dựa vào "job tự retry khi deadlock" cho tới khi thử.
- **Trong request**: không có retry. `frappe/app.py` không nhắc tới hai lớp exception này ([S] tìm trong `app.py`, `handler.py`, `utils/response.py`: không có); chúng không mang `http_status_code`, nên theo đường lỗi chung thành HTTP 500 [I, dựa trên `14`]. Người dùng thấy lỗi và bấm lại.
- Trong cả hai trường hợp transaction đã bị rollback: **không có gì ghi dở**. Deadlock là lỗi về *tiến độ*, không phải lỗi về *dữ liệu*.

### Tránh deadlock [G]

| Luật | Vì sao |
|---|---|
| **Luôn lấy lock theo cùng một thứ tự** (ví dụ: dòng cha trước dòng con; theo `name` tăng dần) | vòng tròn chờ chỉ sinh ra khi hai bên lấy ngược thứ tự |
| **Transaction ngắn** | giữ lock ít thời gian thì ít cơ hội chen nhau |
| **Không gọi mạng trong lúc giữ nhiều lock** | lời gọi chậm kéo dài mọi lock đang giữ |
| **Lock ít dòng nhất** (có index trên cột lọc) | thiếu index, database khóa cả dải dòng nó quét qua |
| **Việc theo lô: chia nhỏ, mỗi lô một commit** | một transaction khổng lồ khóa cả bảng trong thực tế |
| **Thiết kế để retry được** | deadlock không loại hết được; bên bị giết phải chạy lại an toàn → idempotency |

Ví dụ trong lab [I]: job đồng bộ lock dòng outbox rồi `save()` tài liệu gốc (`tasks/xero_sync.py:11, :36-40`); một người dùng đang lưu chính tài liệu đó rồi (qua controller) đụng tới dòng outbox sẽ lấy hai lock theo thứ tự ngược lại. Hiếm, nhưng là đúng hình dạng trong hình vẽ.

## Mức cô lập (isolation) [G]

Mỗi transaction thấy gì từ những transaction khác đang chạy?

| Hiện tượng | Nghĩa |
|---|---|
| Dirty read (đọc bẩn) | thấy dữ liệu người khác chưa commit |
| Non-repeatable read | đọc lại cùng một dòng, giá trị đã đổi |
| Phantom (dòng ma) | chạy lại cùng một truy vấn, số dòng đã đổi |
| Lost update | hình dạng 1 ở trên |

MariaDB/InnoDB mặc định `REPEATABLE READ`: trong một transaction, đọc thường thấy một ảnh chụp cố định. Hôm nay không tìm thấy chỗ nào trong `frappe/database/` đặt lại mức cô lập ([S] tìm chữ `isolation`: chỉ có một dòng chú thích), nên giả định là mặc định của database. Hai hệ quả thực tế:
- Một job chạy lâu **không thấy** thay đổi người khác commit sau khi nó bắt đầu đọc, trừ khi nó đọc bằng `for_update` (đọc có khóa luôn lấy bản mới nhất đã commit).
- "Đọc rồi quyết định" mà không khóa là quyết định trên ảnh cũ.

## Thất bại giữa chừng: năm công cụ luôn đi cùng nhau

| Công cụ | Trả lời câu hỏi | Trong Frappe |
|---|---|---|
| **Transaction** | hỏng thì dữ liệu của ta có nửa vời không? | một request = một transaction, một job = một transaction (`02`) |
| **Timeout** | chờ tới bao giờ? | job: 300 s / 1500 s ([S] `background_jobs.py:62-69`); câu lệnh SQL: tùy chọn, bật bằng `enable_db_statement_timeout`, bằng 1.5 lần `http_timeout` (mặc định 300) hoặc timeout của job ([S] `database/database.py:1615-1626`); lời gọi HTTP ra ngoài: **không có mặc định, phải tự truyền** (`03`) |
| **Retry có giới hạn** | thử lại mấy lần, cách nhau bao lâu? | job: xem mục deadlock; ngoài ra tự xây (back-off: giãn dần, có trần) |
| **Idempotency** | thử lại có làm hai lần không? | tự xây: key cố định, tra cứu trước khi tạo, unique (`12`) |
| **Trạng thái nhìn thấy được** | ai biết nó đã hỏng? | một field status + Error Log; không gì tự báo cho người dùng (`03`) |

Ba sự thật về hệ phân tán nên thuộc lòng [G]:
- **Không có "đúng một lần" (exactly-once) qua mạng.** Chỉ có "ít nhất một lần" cộng với bên nhận idempotent.
- **Timeout không có nghĩa là thất bại.** Nó có nghĩa là *không biết*. Phải hỏi lại bên kia trước khi làm lại.
- **Hai hệ thống không chung transaction.** Giữa chúng chỉ có nhất quán cuối cùng (eventual consistency): sẽ khớp, sau một lúc, nếu có cơ chế đẩy cho tới khi khớp (outbox + sweeper).

## Giới hạn và tải

| Giới hạn | Giá trị | Chạm vào thì | Bằng chứng |
|---|---|---|---|
| Số lần ghi trong một transaction | 200 000 (đổi bằng `max_writes_per_transaction`) | `TooManyWritesError`, thay đổi bị hoàn lại; hoặc tự commit nếu `auto_commit_on_many_writes` được bật | [S] `database/database.py:99, :472-485` |
| Hàng đợi job | khoảng 500 job chờ | `enqueue` ném `QueueOverloaded` (HTTP 503) | [S] `exceptions.py:270-271`; [T] `03` |
| Thời gian chạy một job | 300 s (`short`, `default`), 1500 s (`long`) | worker bị dừng | [S] `background_jobs.py:62-69` |
| Tần suất gọi một endpoint | decorator `rate_limit(key, limit=5, seconds=86400, methods, ip_based=True)`, đếm bằng Redis | `TooManyRequestsError` (HTTP 429) | [S] `frappe/rate_limiter.py:104-125, :75`; `exceptions.py:85` |
| Site ở chế độ chỉ đọc | — | `InReadOnlyMode` (HTTP 503) | [S] `exceptions.py:262-263` |

Nguyên tắc [G]: hệ thống tốt **từ chối sớm và rõ ràng** khi quá tải (backpressure: đẩy áp lực ngược về bên gọi), thay vì nhận hết rồi chết. Trần queue và rate limit là hai ví dụ có sẵn. Việc lớn thì chia lô; vòng lặp xếp mỗi dòng một job sẽ chạm trần queue.

## Các yêu cầu phi chức năng khác, mỗi cái một dòng

| Yêu cầu | Câu hỏi cụ thể | Ở lab này |
|---|---|---|
| **Hiệu năng** (performance) | mỗi request mấy truy vấn? có N+1 không? | đo bằng Recorder trước khi tối ưu (`15`) |
| **Co giãn** (scalability) | thêm worker có nhanh hơn không? | chỉ khi việc không tranh nhau một lock hay một rate limit bên ngoài (`15`) |
| **Sẵn sàng** (availability) | một phần chết thì phần còn lại sống không? | bên ngoài chết: request vẫn trả về vì việc chậm nằm trong job (`03`, `12`) |
| **Bền** (durability) | đã báo "xong" thì có mất không? | đã commit vào MariaDB thì bền; thứ chỉ nằm trong Redis hay bộ nhớ (job chờ, callback `after_commit`) thì không (`02`) |
| **Nhất quán** (consistency) | hai nơi lưu cùng một sự thật có lệch không, bao lâu? | trong một database: transaction; với hệ ngoài: nhất quán cuối cùng |
| **Bảo mật** (security) | xác thực, phân quyền, CSRF, bí mật, đầu vào | permission ở endpoint và ở tài liệu; bí mật trong field Password; không `ignore_permissions` (`01`, AGENTS.md B4) |
| **Riêng tư** (privacy) | dữ liệu cá nhân có lọt vào log, response không? | không token, `sid`, traceback trong response hay log (AGENTS.md B6) |
| **Quan sát được** (observability) | lỗi lúc 2 giờ sáng, sáng ra có lần lại được không? | Error Log, RQ Job, Scheduled Job Log, `X-Frappe-Request-Id` (`14`) |
| **Kiểm toán được** (auditability) | ai đổi cái gì, khi nào? | timeline và lịch sử phiên bản của tài liệu trong Desk [G]; với tích hợp: journal trên dòng outbox |
| **Toàn vẹn** (integrity) | có thể tồn tại dữ liệu vô nghĩa không? | unique, link, chuyển `docstatus` có kiểm soát ([S] `document.py:1121-1132`) |
| **Đúng về số và thời gian** | làm tròn, tiền tệ, múi giờ | `flt(value, precision)`, không `==` trên số tiền, thời gian qua `frappe.utils` (AGENTS.md B4) |
| **Bảo trì được** (maintainability) | người mới đọc có hiểu không, sửa có lan không? | file ngắn, lớp rõ, một chiều import (AGENTS.md B4) |
| **Nâng cấp được** (upgradability) | lên phiên bản Frappe mới có vỡ không? | không sửa core; chỉ dùng điểm mở rộng (AGENTS.md B2a) |
| **Kiểm thử được** (testability) | chứng minh được mà không cần hệ ngoài không? | bản giả của hệ ngoài sau cùng một interface; test phân quyền cho mỗi endpoint (AGENTS.md B5) |
| **Triển khai được** (deployability) | dựng lại từ đầu mất mấy bước? | một lệnh (`docs/runbooks/dev-environment.md`); schema chỉ qua migrate (AGENTS.md B3) |
| **Khôi phục được** (recoverability) | mất database thì mất bao nhiêu (RPO), bao lâu thì chạy lại (RTO)? | backup và restore là việc của con người (AGENTS.md A3); lab chưa có quy trình [G] |
| **Dùng được, đa ngôn ngữ** | thông báo lỗi có đọc được, dịch được không? | `_("Text {0}").format(x)` (AGENTS.md B4) |

## Danh sách câu hỏi cho mọi tính năng

Trùng với "Cover the angles" của AGENTS.md A15, viết ra thành câu hỏi:

1. **Hai người làm việc này cùng lúc** trên cùng một bản ghi thì sao? (hình dạng nào trong năm cái?)
2. **Làm hai lần** (bấm đôi, retry, job trùng) có ra hai kết quả không?
3. **Chết ở giữa** bước 1 và bước 2 thì dữ liệu ở trạng thái nào, và ai đưa nó đi tiếp?
4. Có **lời gọi ra ngoài** không? Timeout bao nhiêu? Không trả lời thì coi là gì?
5. Nó giữ **lock nào, trong bao lâu, theo thứ tự nào**?
6. **Một nghìn bản ghi** thay vì một thì sao? Chạm giới hạn nào trước?
7. **Ai không được làm** việc này, và test nào chứng minh họ bị chặn?
8. Khi hỏng, **người dùng thấy gì**, và người vận hành tìm nguyên nhân ở đâu?
9. Có **bí mật** hay dữ liệu cá nhân nào đi qua log hay response không?
10. **Gỡ tính năng** này thì phải dọn những gì?

## Thử đi (trình duyệt và đọc, không cần lệnh)

1. Lost update: mở cùng một Lab Note ở hai tab, sửa và lưu ở tab 1, rồi sửa và lưu ở tab 2. Đọc thông báo; tìm nó ở `frappe/model/document.py:1109-1116`.
2. Đọc `frappe/model/naming.py:408-423` và trả lời: nếu bỏ `.for_update()`, hai người tạo tài liệu cùng lúc có thể nhận gì?
3. Deadlock trong job: đọc `frappe/utils/background_jobs.py:275-302` cùng `frappe/database/database.py:270-281` và `frappe/exceptions.py:254-259`, rồi tự quyết: một deadlock xảy ra bên trong `frappe.db.sql` có tới được nhánh retry không?
4. Lấy một tính năng bất kỳ của lab và trả lời mười câu hỏi ở trên.

## Còn chưa biết

- Nhánh retry khi deadlock của job có thật sự được kích hoạt cho deadlock đi qua `frappe.db.sql` hay không (mục Deadlock). Cần một thí nghiệm.
- Mức cô lập thật của kết nối trong lab (giả định mặc định của MariaDB); cấu hình database nằm ngoài tầm đọc của agent.
- Request có được tự chạy lại ở tầng nào khác khi deadlock không (ví dụ ở web server); chưa thấy trong ba file đã tìm.
- `DOCUMENT_LOCK_EXPIRY` là bao lâu, và những đường nào của framework gọi `doc.lock()`; mới thấy định nghĩa và một chỗ ném lỗi.
- Trần hàng đợi và các con số của nó: lấy từ `03`, hôm nay không mở lại.
