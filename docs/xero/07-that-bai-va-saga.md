# 07. Thất bại, sweeper, idempotency ba lớp, và SAGA

Phần "khó" của tích hợp không phải gọi API; mà là: chuyện gì xảy ra khi hỏng giữa chừng. File này đủ để không phải mở `docs/knowledge/12` (phần thất bại), `13` và `14`.

Nhãn: xem `00-README.md`. Code của ta dưới `frappe-bench/apps/lab_core/lab_core/`.

## Trả lời trong năm dòng

1. Mọi thất bại rơi vào một trong **bốn loại**: Rejected (từ chối), Busy (bận), Unknown (không rõ), Auth lost (mất kết nối). Mỗi loại một nhánh trong job.
2. Chống tạo trùng có **ba lớp**: queue, database của ta, Xero. Chỉ lớp giữa và việc tra cứu là còn tác dụng sau 6 phút.
3. **Sweeper** (job quét định kỳ) là mảnh còn thiếu: nó cứu các dòng `Pending` bị bỏ quên và thực hiện việc "chờ rồi thử lại".
4. **SAGA** chỉ cần khi một việc nghiệp vụ gồm **từ hai lời gọi Xero** phải cùng xong hoặc cùng không. Luồng một bước hôm nay không cần.
5. Lỗi gọi Xero **không** đi ra qua HTTP response; nó tới người dùng qua `outbox.error` và `sync_status`.

## Sáu trường hợp thất bại của kế hoạch, dò qua code thật

Danh sách lấy từ `plan/general/OVERVIEW.md` ("The Xero transaction idea").

| # | Trường hợp | Hôm nay chuyện gì xảy ra | Bằng chứng | Kết luận |
|---|---|---|---|---|
| 1 | Crash **trước** commit | tài liệu + dòng outbox rollback; job đang chờ bị bỏ | [S] `frappe/database/database.py:1202-1203` | Đúng |
| 2 | Crash **sau** commit, trước khi đẩy job | dòng `Pending`, tài liệu `Queued`, không có job, mãi mãi | [S] đẩy ở `:1194`, sau SQL commit `:1190`; `hooks.py` chưa có sweeper | **Khoảng trống → sweeper** |
| 3 | **Timeout**, Xero đã tạo rồi | job hỏi `find_by_key`, thấy id, đánh dấu Done | [S] `tasks/xero_sync.py:23-25, :33-40` | Khung đúng; `find_by_key` chỉ có ở client thế chỗ sẽ bị gỡ. Với Xero thật: tra theo `InvoiceNumber` (`03`) |
| 4 | **Bị từ chối** | dòng `Failed` + lý do; tài liệu `Failed`; job return bình thường nên được commit | [S] `:29-31, :43-51` | Đúng |
| 5 | **Job trùng** | job thứ hai chờ row lock, thấy `Done`, return | [S] `:11-13` | Đúng. Đây mới là lớp bảo vệ thật |
| 6 | **Compensation thất bại** | compensation hôm nay chỉ là hai lần save local (`_mark_failed`); một cái throw → rollback hết, dòng vẫn `Pending` | [S] `:43-51` | Tạm chấp nhận; khi có void thật thì nó thành một dòng outbox riêng |

Ba trường hợp danh sách không nêu (suy ra, chưa chạy):

| Trường hợp | Hôm nay | Cách sửa |
|---|---|---|
| Lỗi transport không phải `XeroTimeout` (DNS, TLS, reset) hoặc bug | đường "raise": rollback (mất cả `attempts += 1`), tài liệu `Queued` mãi | client ánh xạ **mọi** lỗi transport sang class của nó |
| Worker bị kill ở timeout 300 s | như trên, không có cả Error Log của ta | HTTP timeout ngắn; sweeper |
| User sửa tài liệu trong lúc job đang save nó | hai lần save có thể đụng nhau [G] | job chỉ ghi các field của riêng nó (sau submit: `db_set`) |

## Bốn loại thất bại = bốn nhánh của job

| Loại | Tín hiệu từ Xero | Có gì bên Xero? | Job làm | Dòng outbox |
|---|---|---|---|---|
| **Rejected** | `400` validation; `404` trên bản ghi được tham chiếu | Không | ghi message nguyên văn, dừng | `Failed` → người sửa dữ liệu, bấm retry |
| **Busy** | `429` (+ `Retry-After`), `500`, `503` | Không (giả định) | ghi mốc "không gọi trước thời điểm X" cho cả organisation, dừng | vẫn `Pending`; sweeper gửi lại |
| **Unknown** | timeout, đứt kết nối sau khi gửi | **Có thể** | tra cứu; câu trả lời của Xero quyết định | `Done` hoặc quay về `Pending` |
| **Auth lost** | `401` sau một lần refresh; `403`; token là `None` | Không | bật cờ `paused` toàn cục, báo "reconnect" | vẫn `Pending`; **không tính attempts** |

Hôm nay job chỉ có nhánh cho Rejected và Unknown ([S] `XeroRejected`, `XeroTimeout` ở `integrations/xero/client.py:18, :22`). Thiếu `XeroBusy(retry_after)` và `XeroAuthLost`.

Vì sao Auth lost không được tính là thất bại thường: token là `None` khi refresh hỏng ([S] `frappe/integrations/doctype/connected_app/connected_app.py:163-165`: log rồi `return None`, không raise). Nếu coi là lỗi thường, mọi dòng đang chờ đốt hết lượt retry trong khi nguyên nhân là một con người chưa bấm Connect.

## Idempotency: ba lớp, mỗi lớp bắt cái lớp trên bỏ sót

```text
1. Queue         job_id + deduplicate                 chặn phần lớn job trùng           gọn, CHƯA an toàn
2. Database ta   row lock (for_update) + status Done  mỗi lúc một worker; Done là cuối  an toàn trước chính ta
                 unique trên field xero id            không lưu được id thứ hai
3. Xero          a) tra cứu theo số của ta TRƯỚC khi tạo     dùng được bất cứ lúc nào    an toàn trước mạng
                 b) header Idempotency-Key                   chỉ che 6 phút [X*]
```

- Key hôm nay: `"<doctype>:<name>:<operation>"` ([S] `lab_xero/outbox.py:16`). Ổn định qua các lần retry, đọc được. `"Sales Invoice:ACC-SINV-2026-00042:create_invoice"` dài 48 ký tự, dưới trần 128 của Xero; naming series dài có thể vượt → thêm kiểm tra độ dài.
- Invoice ERPNext bị cancel rồi **amend** (sửa sau khi hủy) nhận tên mới (`…-1`) [G] → key mới, `InvoiceNumber` mới: đúng, đó là hóa đơn mới.
- Nếu cùng operation có thể gửi lại với **nội dung khác** (ví dụ "update contact" sau mỗi lần sửa), key phải thêm phần version (timestamp `modified`), vì cùng key với request khác bị Xero trả `400` [X*].
- Vì key chỉ sống 6 phút, lớp 3a (tra cứu) là bắt buộc, không phải tùy chọn. Client thế chỗ đang có trong code không cho thấy điều này; client thật phải làm.

## Sweeper: mảnh còn thiếu

```text
mỗi 5 phút (scheduler_events trong hooks.py; hàm không tham số, chạy với tư cách Administrator: 06)
 sweep_outbox()                                   trong tasks/
  ├─ settings.paused? (auth lost / dừng tay)  → return
  ├─ now < settings.not_before? (Xero vừa bảo chờ) → return
  ├─ lấy các dòng status = Pending
  │        và (next_attempt_at trống hoặc <= now)
  │        và creation < now - 1 phút            ← để job trực tiếp có cơ hội chạy trước
  │     sắp theo attempts, creation; giới hạn một lô
  └─ mỗi dòng: frappe.enqueue(process_outbox, job_id=…, deduplicate=True, outbox_name=…)
```

Cần những field chưa tồn tại (**bạn tạo trong Desk**, AGENTS.md B2):

| DocType | Field | Kiểu | Vì sao |
|---|---|---|---|
| Lab Xero Outbox | `next_attempt_at` | Datetime | back-off (giãn dần) và `Retry-After` |
| Lab Xero Outbox | `payload_hash` | Data | phát hiện "cùng key, khác nội dung" trước Xero (tùy chọn) |
| Lab Xero Settings | `paused`, `paused_reason`, `not_before` | Check, Small Text, Datetime | công tắc dừng toàn cục; đồng hồ rate limit dùng chung |

Luật back-off [G]: chờ `min(60 × 2^attempts, 3600)` giây, hoặc `Retry-After` nếu dài hơn; sau khoảng 8 lần → `Failed`. Thời gian lấy từ `frappe.utils` (`now_datetime`, `add_to_date`), không bao giờ `datetime.now()` (AGENTS.md B4).

Sweeper chạy với tư cách Administrator nên nó cũng trả lời câu hỏi mở của `SPRINT.md` ("ai sở hữu dòng outbox"): khi có sweeper, câu trả lời tự nhiên là hệ thống. Đó là một quyết định của bạn.

## Hai kênh lỗi

```text
LỖI CỦA REQUEST                                   LỖI KHI GỌI XERO (trong job)
frappe.throw(msg, <class có http_status_code>)    XeroRejected / XeroTimeout / XeroBusy / XeroAuthLost
  → Frappe bắt ở một chỗ, rollback, trả HTTP 4xx    không có client nào đang chờ, không có HTTP response
  → client thấy ngay                                → outbox.status + outbox.error, tài liệu.sync_status
                                                    → lỗi bất ngờ: rollback + Error Log
                                                    → client biết bằng: poll trạng thái
```

- Kênh request: endpoint **chỉ raise, không catch**. Catch rồi return `{"success": False}` làm request "thành công" và transaction bị **commit** với nửa dữ liệu [K, `frappe/app.py`]. Class lỗi của ta nằm trong `lab_core/errors.py`, mỗi class mang HTTP status (`SPRINT.md`).
- Kênh job: bốn class lỗi của client Xero đóng vai trò của "HTTP status": mỗi class một nhánh, mỗi nhánh một kết cục cho dòng outbox.
- Message validation của Xero (body của `400`) lưu **nguyên văn** vào `outbox.error`: con người phải đọc nó để sửa dữ liệu.
- Khoảng trống nhỏ đáng sửa sớm [K]: endpoint `get_note` chưa trả nội dung lỗi của outbox, nên người dùng thấy `Failed` mà không thấy lý do.
- Không token, `sid` hay traceback trong response hay log (AGENTS.md B6).

## SAGA: khi một việc cần hai lời gọi Xero

Thuật ngữ SAGA ở đây là [G] (từ trí nhớ về pattern, chưa đối chiếu nguồn).

**SAGA** = chuỗi bước, mỗi bước là một transaction đã commit; một bước hỏng hẳn thì các bước đã xong được hoàn tác bằng **compensation** (hành động nghiệp vụ ngược lại), không phải rollback.

```text
transaction thường:  BEGIN ─ A ─ B ─ COMMIT              hỏng đâu cũng rollback, không ai thấy dở dang
SAGA:                [T1 commit] → [T2 ✘ hỏng hẳn] → [C1 commit]     C1 = compensation của T1, một transaction MỚI
```

Vấn đề chỉ xuất hiện ở bước thứ hai:

```text
KHÔNG SAGA: hai dòng outbox độc lập                    CÓ SAGA (orchestration: điều phối tập trung)
 A create_invoice  Done ✔                               bản ghi SAGA (Running, bước 1) + dòng A
 B create_payment  Failed ✘ (Xero từ chối)              job A xong → CÙNG transaction: SAGA sang bước 2 + tạo dòng B
 ⇒ Xero: có invoice, không payment                      job B bị từ chối → CÙNG transaction: SAGA = Compensating
   local: "Synced" hay "Failed"? không ai quyết                            + tạo dòng C void_invoice
   không ai void → bản ghi MỒ CÔI bên Xero              job C xong → SAGA = Compensated; local = Failed + lý do
                                                        ⇒ hai bên nói cùng một điều
```

| Loại bước | Nghĩa | Ví dụ |
|---|---|---|
| Compensatable (bù được) | đã commit nhưng còn hoàn tác được | tạo invoice `AUTHORISED` → bù: void |
| Pivot (điểm xoay) | qua rồi thì phải đi tới cùng | áp payment: sau đó invoice không void được nữa |
| Retriable (thử lại được) | sau pivot; chỉ được thử tới khi xong | ghi Xero id về tài liệu local |

Hai SAGA cụ thể:

| Việc | Bước 1 | Bước 2 | Bước 3 |
|---|---|---|---|
| Invoice kèm payment | `ensure_contact` (không cần bù: để lại contact) | `create_invoice` (bù: `void_invoice`) | `create_payment` (pivot) |
| Trả hàng | `create_credit_note` (bù: void) | `allocate_credit` (pivot) | ghi id về local (retriable) |

Các luật giữ cho nó quản lý được:
1. Mỗi lời gọi Xero **một** dòng outbox. Không bao giờ hai lời gọi dưới một dòng.
2. Compensation chỉ là **một dòng khác** với key riêng (`"<DocType>:<name>:void_invoice"`), được retry như mọi dòng.
3. Compensation chạy hai lần phải an toàn (void cái đã void: no-op hoặc một lỗi đã biết, bắt đúng tên, không `except` trần).
4. Compensation hỏng hẳn → trạng thái `Stuck`, báo con người. Đó là điểm dừng có chủ đích của tự động hóa.
5. **Chỉ Rejected mới làm SAGA quay đầu.** Busy, Unknown, Auth lost là chuyện của retry; coi chúng là thất bại sẽ void những invoice hoàn toàn hợp lệ.

SAGA **không** trả lại tính cô lập: giữa hai bước, kế toán nhìn thấy invoice rồi có thể thấy nó bị void vài giây sau. Cách bù: một "semantic lock" (field `sync_status = Queued` chặn cancel/amend khi đang chạy), và đặt pivot muộn nhất có thể. Nếu kế toán không chấp nhận "hiện rồi biến mất": tạo `DRAFT`, chỉ `AUTHORISED` ở bước cuối.

Vì sao khớp với Frappe: mỗi job là một transaction commit khi thành công ([S] `frappe/utils/background_jobs.py:305`), nên "ghi kết quả bước này + tạo dòng của bước kế" là nguyên tử; dòng kế được `enqueue_after_commit` nên không thể chạy trước khi bước trước commit.

Nếu xây (chưa có gì): DocType `Lab Xero Saga` (`saga_type` Data, `reference_doctype` Link, `reference_name` Dynamic Link, `status` Select: Running/Completed/Compensating/Compensated/Stuck, `current_step` Int, `error` Small Text) và trên outbox thêm `saga` (Link), `step_no` (Int), `is_compensation` (Check). Một hàm `advance(row)` gọi ở cuối `process_outbox`.

**Cho deadline:** demo một bước (Sales Invoice → Invoice) **không cần SAGA**. Cancel → void là một operation outbox riêng, cũng không cần SAGA. SAGA và ý tưởng `@xero_atomic(compensate=…)` trong `OVERVIEW.md` chỉ vào cuộc khi làm invoice + payment hoặc trả hàng; **sweeper phải có trước SAGA**. So sánh với broker (Redpanda/Kafka) để sau: broker không thay được idempotency, compensation và semantic lock.

## Tối ưu: chỉ những thứ giúp luồng Xero

Nút cổ chai là rate limit của Xero (`03`), không phải tốc độ Frappe.

| # | Kỹ thuật | Lợi gì | Khi nào |
|---|---|---|---|
| 1 | Lấy token một lần ở đầu job | tránh refresh giữa chừng và bẫy commit (`06`) | ngay khi có client thật |
| 2 | HTTP timeout ngắn, tường minh | job giữ row lock suốt lời gọi Xero ([S] `tasks/xero_sync.py:11, :22`) | ngay |
| 3 | Đồng hồ rate limit dùng chung (`not_before`) | sau `429` cả organisation cùng chậm lại, không đốt lượt retry | cùng sweeper |
| 4 | Cache dữ liệu tham chiếu (accounts, tax rates) | bớt lời gọi khi dựng payload; quan trọng với 1000/ngày | khi có mapping |
| 5 | Một queue riêng, 1–2 worker cho Xero | Xero chỉ cho 5 lời gọi đồng thời | hạ tầng, của bạn |
| 6 | Ghi theo lô (~50), đọc `If-Modified-Since` + phân trang | import đầu kỳ, đồng bộ ngược | sau demo |

GraphQL, gRPC, read replica: không giúp gì luồng Xero (Xero chỉ nói REST/JSON). Bỏ qua tới sau deadline.

## Tự kiểm tra

1. Xếp mỗi tín hiệu vào một loại và nói dòng outbox thành gì: `400`, `429`, timeout, token `None`.
2. Vì sao `deduplicate=True` trên queue không đủ để tránh hai invoice bên Xero?
3. Bước 2 của một SAGA nhận `503`. Có chạy compensation không? Vì sao?
