# 13. SAGA: hệ thống khi không có và khi có

Nhãn: [S] đã thấy hôm nay (code của ta, đường dẫn dưới `frappe-bench/apps/lab_core/lab_core/`), [I] suy ra, [G] kiến thức chung về pattern SAGA (từ trí nhớ: bài báo "Sagas" của Garcia-Molina và Salem 1987, và cách cộng đồng microservices mô tả pattern này; **chưa đối chiếu với nguồn nào hôm nay**, kiểm chứng khi online). Không chạy gì. Phần "có SAGA" là **đề xuất thiết kế**, chưa có dòng code nào.

Đọc sau `02`, `03` và `12`.

## Trả lời trong năm dòng

1. **SAGA** là một chuỗi bước, mỗi bước là một transaction (giao dịch) riêng đã commit; nếu một bước hỏng hẳn thì các bước đã xong được hoàn tác bằng **compensation** (bù trừ: một hành động nghiệp vụ ngược lại), không phải bằng rollback. [G]
2. Hôm nay dự án **chưa có SAGA**. Nó có ba viên gạch nền của SAGA: outbox, idempotency key và row lock. Luồng hiện tại chỉ có **một** bước gọi Xero, và "compensation" của nó chỉ là đánh dấu `Failed` ở local. [S]
3. Với một bước thì không cần SAGA: outbox + idempotency là đủ. SAGA chỉ đáng giá khi một việc nghiệp vụ cần **từ hai lời gọi Xero trở lên** mà phải "cùng xong hoặc cùng không" (invoice + payment, credit note + allocation).
4. Khi không có SAGA, bước 2 hỏng sau khi bước 1 đã xong sẽ để lại một bản ghi **mồ côi** bên Xero, và không ai sở hữu kết quả chung. Khi có SAGA, có một bản ghi trạng thái cho cả chuỗi, một orchestrator (bộ điều phối) quyết định bước kế tiếp, và compensation chạy như một dòng outbox bình thường.
5. SAGA **không** cho lại tính isolation (cô lập): giữa hai bước, người khác nhìn thấy trạng thái dở dang. Phải tự bù bằng một "semantic lock" (khóa ngữ nghĩa: một field status chặn thao tác khác). [G]

## SAGA là gì, đủ để dùng [G]

```text
ACID transaction:      BEGIN ─ A ─ B ─ C ─ COMMIT            hỏng ở đâu cũng ROLLBACK, không ai thấy gì dở dang
SAGA:                  [T1 commit] → [T2 commit] → [T3 commit]
   T2 hỏng hẳn:        [T1 commit] → [T2 ✘] → [C1 commit]    C1 = compensation của T1, là một transaction MỚI
```

Ba loại bước, cần gọi đúng tên khi thiết kế:

| Loại bước | Nghĩa | Ví dụ với Xero |
|---|---|---|
| **Compensatable** (bù trừ được) | Đã commit nhưng còn hoàn tác được bằng một hành động ngược | Tạo invoice `AUTHORISED` (bù trừ: `VOIDED`); tạo credit note (bù trừ: void) |
| **Pivot** (điểm xoay) | Bước quyết định: qua được nó thì SAGA phải đi tới cùng, không quay lại nữa | Áp payment vào invoice: sau đó invoice không void được nữa (`10`) |
| **Retriable** (thử lại được) | Sau pivot; không được phép thất bại hẳn, chỉ được thử lại tới khi xong | Ghi Xero id về tài liệu local; gửi PDF đính kèm |

Hai cách điều phối:

| | **Orchestration** (điều phối tập trung) | **Choreography** (tự phối hợp bằng event) |
|---|---|---|
| Ai quyết định bước kế tiếp | Một orchestrator đọc trạng thái SAGA và ra lệnh | Không ai: mỗi service nghe event của service trước rồi tự làm |
| Trạng thái của cả chuỗi nằm ở | Một bản ghi SAGA | Rải rác; phải suy ra từ các event |
| Hợp khi | Một hệ thống làm chủ luồng (trường hợp của ta: ERPNext → Xero) | Nhiều service ngang hàng, có broker (trung gian tin nhắn) |
| Trong lab này | Outbox + job trong `tasks/`, **không cần hạ tầng mới** | Cần broker (Redpanda/Kafka): phần "so sánh về sau" của `OVERVIEW.md` |

Khuyến nghị cho lab: **orchestration**, xây ngay trên outbox đang có. Choreography với broker để lại cho mục 6 của "Order" trong `OVERVIEW.md`.

## Hôm nay: không có SAGA

Đây là toàn bộ luồng thật [S]:

```text
request (1 transaction)
  note.insert()                              lab_core/notes.py:39-44
   ├ before_insert: sync_status = "Queued"   lab_core/doctype/lab_note/lab_note.py:10-11   (controller của ta, không hook)
   └ after_insert: outbox.queue(self)        :13-16
        dòng Lab Xero Outbox, key cố định    lab_xero/outbox.py:16-30
        enqueue sau commit                   :33-40
 ── commit: note + dòng outbox ──
job (1 transaction)                          tasks/xero_sync.py:10
  lock dòng, Done thì thôi                   :11-13
  find_by_key(key) or create_invoice(...)    :22          ← MỘT lời gọi Xero
  XeroTimeout → hỏi lại; không có → Failed   :23-28
  XeroRejected → Failed                      :29-31
  Done + xero_id; note Synced                :33-40
  _mark_failed: outbox Failed + note Failed  :43-51       ← docstring gọi đây là "compensation"
 ── commit ──
```

Vì sao đây chưa phải SAGA:
- Chỉ có một bước chạm Xero. Khi nó bị từ chối thì **bên Xero không có gì** để hoàn tác; `_mark_failed` chỉ ghi nhận sự thật ở local ([S] `tasks/xero_sync.py:44-45`).
- Không có bản ghi nào nói "việc nghiệp vụ này gồm các bước nào, đang ở bước mấy".
- `lab_core/hooks.py` chỉ có `website_route_rules` ([S] `:8-10`): chưa có sweeper, chưa có `doc_events`.
- Client giả chỉ có `find_by_key` và `create_invoice` ([S] `integrations/xero/client.py:30, :34`): chưa có thao tác nào để hoàn tác (void).

Với một bước, thiết kế hiện tại là **đúng và đủ**. Đừng thêm SAGA cho Lab Note một bước.

## Vấn đề xuất hiện khi có hai bước

Lấy việc nghiệp vụ nhỏ nhất cần hai lời gọi: tạo invoice rồi ghi payment cho nó (hoặc: tạo credit note rồi allocate, `12`).

**Không có SAGA**, cách tự nhiên là xếp hai dòng outbox độc lập trong cùng request:

```text
request:  dòng A create_invoice (Pending)   dòng B create_payment (Pending)   → commit → 2 job

job không có thứ tự (03):
  B chạy trước A  → chưa có InvoiceID       → B hỏng hoặc phải tự chờ
  A Done, B bị Xero từ chối (Rejected)      → A: Done ✔   B: Failed ✘
                                              Xero: có invoice, không có payment
                                              local: sync_status là gì? "Synced" hay "Failed"? không ai quyết
                                              không ai void invoice  → bản ghi MỒ CÔI bên Xero
```

**Có SAGA (orchestration)**, cùng tình huống đó:

```text
request:  bản ghi SAGA (Running, bước 1)  +  dòng A create_invoice (Pending)        → commit → 1 job
job A:    Xero OK → A Done; TRONG CÙNG transaction: SAGA sang bước 2 + tạo dòng B   → commit → job B
job B:    Xero từ chối → B Failed; TRONG CÙNG transaction: SAGA = Compensating
                                   + tạo dòng C void_invoice (is_compensation)       → commit → job C
job C:    Xero void OK → C Done; SAGA = Compensated; tài liệu local = Failed + lý do → commit

kết quả:  Xero: invoice VOIDED, không payment        local: Failed, có lý do, có nút retry
          hai bên nói cùng một điều
```

Điểm then chốt [I]: "đánh dấu bước xong" và "tạo dòng outbox của bước kế tiếp" nằm trong **cùng một transaction của job**. Vậy bản thân tiến trình của SAGA cũng được outbox bảo vệ: job chết ở đâu thì hoặc cả hai đã lưu, hoặc cả hai chưa. Kết hợp với sweeper (`12`), SAGA không bao giờ kẹt im lặng.

## Cả hệ thống, đặt cạnh nhau

```text
                KHÔNG SAGA (hôm nay)                         CÓ SAGA (đề xuất)

SPA / Desk      như nhau                                     như nhau
   │
api/ → service  như nhau                                     như nhau
   │
controller /    outbox.queue(doc)                            saga.start(doc, "invoice_with_payment")
doc_events      → 1 dòng outbox                              → 1 bản ghi SAGA + dòng outbox của BƯỚC 1
   │            (Lab Note: controller; ERPNext: doc_events)   (cùng chỗ gọi, cùng transaction)
 commit
   │
tasks/          process_outbox(row)                          process_outbox(row)   ← không đổi phần gọi Xero
                 gọi Xero, ghi Done/Failed                    gọi Xero, ghi Done/Failed
                 hết                                          rồi saga.advance(row) ← THÊM: quyết định bước kế / bù trừ
   │
integrations/   create_invoice, find_by_key                  + create_payment, void_invoice, ... (mỗi thao tác một hàm)
xero/client
   │
sweeper         chưa có (khoảng trống của 12)                BẮT BUỘC: quét dòng Pending cũ và SAGA Running quá lâu
   │
trạng thái      sync_status trên tài liệu                    sync_status trên tài liệu (semantic lock)
nhìn thấy       + N dòng outbox rời nhau                     + 1 bản ghi SAGA: bước mấy, đang tiến hay đang bù trừ
```

Thứ **không đổi** khi thêm SAGA: endpoint, service, SPA, cách ghi dòng outbox, idempotency key, row lock, luật "lời gọi ra ngoài chỉ trong `tasks/`", luật không override code của ta. SAGA là một lớp mỏng phía trên outbox, không thay nó.

## Từng tình huống: không SAGA so với có SAGA

Sáu trường hợp đầu là của `OVERVIEW.md` ("The Xero transaction idea"), đã dò qua code trong `12`.

| # | Tình huống | Không SAGA | Có SAGA | SAGA có giúp? |
|---|---|---|---|---|
| 1 | Crash trước commit | Mọi thứ rollback, job bị bỏ | Như vậy; bản ghi SAGA cũng rollback | Không cần |
| 2 | Crash sau commit, trước khi đẩy job | Dòng `Pending` mãi mãi, không có job | Y hệt, cho từng bước | **Không.** Thứ sửa là sweeper. SAGA cần sweeper hơn nữa |
| 3 | Timeout, Xero đã tạo | Hỏi lại / gửi lại cùng key | Như vậy, cho từng bước | Không. Đây là việc của idempotency |
| 4 | Bước **đầu** bị từ chối | `Failed`, không có gì bên Xero | SAGA `Compensated` ngay (không có gì để bù) | Chỉ thêm một chỗ ghi trạng thái |
| 5 | Job trùng | Row lock + `Done` là cuối | Như vậy; thêm: `advance` phải idempotent (bước kế đã có dòng thì không tạo nữa) | Không |
| 6 | Compensation thất bại | Không áp dụng (chưa có compensation thật) | Dòng compensation được retry như mọi dòng; hết lượt → SAGA `Stuck`, báo con người | **Có**: thất bại có tên, có chỗ nhìn |
| 7 | Bước **sau** bị từ chối khi bước trước đã xong | Mồ côi bên Xero; hai bên lệch nhau | Void bước trước; hai bên khớp | **Có. Đây là lý do tồn tại của SAGA** |
| 8 | Thứ tự các bước | Job không có thứ tự; phải tự chờ hoặc kéo phụ thuộc (`12`) | Bước 2 chỉ được tạo sau khi bước 1 `Done` | **Có** |
| 9 | User cancel/sửa tài liệu giữa chừng | Tranh chấp với job | `sync_status` làm semantic lock: chặn cancel khi SAGA `Running`; cancel sau đó là một SAGA khác (void) | **Có**, nếu thêm kiểm tra đó |
| 10 | "Việc này xong chưa?" | Phải đọc N dòng outbox rồi tự suy | Một bản ghi, một status | **Có** |
| 11 | Xero bận (`429`), mất auth | Dòng nằm `Pending`, chờ | Y hệt: đây **không** phải quyết định của SAGA, không kích hoạt compensation | Không |

Dòng 11 là cái bẫy quan trọng nhất [I]: chỉ **Rejected** (từ chối vĩnh viễn) mới làm SAGA quay đầu. Busy, Unknown và Auth lost (`12`, "Bốn loại thất bại") là chuyện của retry; coi chúng là thất bại sẽ void những invoice hoàn toàn hợp lệ.

## Isolation: thứ SAGA không trả lại [G]

Giữa bước 1 và bước 2, invoice đã tồn tại bên Xero và ai cũng thấy. Các cách bù thường dùng:

| Cách | Nghĩa | Trong lab |
|---|---|---|
| Semantic lock | Một field nói "đang xử lý", các thao tác khác tôn trọng nó | `sync_status = "Queued"` trên tài liệu; chặn cancel/amend khi đang chạy. Với ERPNext: field `lab_xero_sync_status` (`12`) |
| Reread value | Đọc lại trước khi ghi, thấy đã đổi thì dừng | Job đọc lại tài liệu sau khi lock dòng outbox (đang làm: `tasks/xero_sync.py:11, :15`) |
| Commutative update | Thiết kế bước sao cho thứ tự không quan trọng | Hiếm dùng được với kế toán |
| Pivot đặt muộn nhất có thể | Mọi thứ còn hoàn tác được càng lâu càng tốt | Payment là bước cuối |

Hệ quả nghiệp vụ phải nói với người dùng: một invoice có thể **xuất hiện rồi bị void** bên Xero trong vài giây. Nếu kế toán không chấp nhận điều đó, tạo invoice ở `DRAFT`, chỉ `AUTHORISED` ở bước cuối (draft thì xóa được, `10`).

## Hai SAGA cụ thể cho Xero

**Trả hàng** (đã phác trong `12`):

| Bước | Operation | Loại | Compensation |
|---|---|---|---|
| 1 | `create_credit_note` | compensatable | `void_credit_note` |
| 2 | `allocate_credit` | pivot | không có: bị từ chối thì chạy bù trừ của bước 1 |
| 3 | ghi id về tài liệu local | retriable | không có: thử tới khi xong |

**Invoice kèm payment**:

| Bước | Operation | Loại | Compensation |
|---|---|---|---|
| 1 | `ensure_contact` | compensatable, nhưng **không cần bù** | để lại contact: vô hại, lần sau dùng lại |
| 2 | `create_invoice` | compensatable | `void_invoice` |
| 3 | `create_payment` | pivot | không có |

Luật viết compensation (nhắc lại từ `12`, áp dụng nguyên xi): mỗi lời gọi Xero một dòng outbox; compensation là một dòng có key riêng (`"<DocType>:<name>:void_invoice"`); chạy hai lần phải an toàn; hỏng hẳn thì báo con người. Compensation chạy theo thứ tự **ngược** với các bước đã `Done`.

## Orchestrator, bằng lời

Một hàm trong `tasks/`, gọi ở cuối `process_outbox`, trong cùng transaction với việc ghi kết quả của dòng:

```text
advance(row):
  row không thuộc SAGA nào            → return           (Lab Note một bước vẫn chạy như cũ)
  lock bản ghi SAGA (for_update)
  row là bước thường, Done:
      còn bước sau  → tạo dòng outbox của bước sau (nếu chưa có), SAGA.current_step += 1
      hết bước      → SAGA = Completed; tài liệu local = Synced
  row là bước thường, Failed (Rejected):
      SAGA = Compensating
      tạo dòng compensation cho bước Done gần nhất có compensation   (từng cái một, theo thứ tự ngược)
      không có bước nào để bù → SAGA = Compensated; tài liệu local = Failed + lý do
  row là compensation, Done:
      còn bước Done cũ hơn cần bù → tạo dòng compensation kế
      hết                          → SAGA = Compensated; tài liệu local = Failed + lý do
  row là compensation, Failed hẳn:
      SAGA = Stuck; báo con người                        (điểm dừng của tự động hóa, có chủ đích)
  row vẫn Pending (busy / unknown / auth lost):
      không làm gì; sweeper sẽ đưa dòng quay lại
```

Vì sao khớp với Frappe [I], dựa trên các dòng đã thấy trong `02` và `03`:
- Mỗi job là một transaction, commit khi thành công (`frappe/utils/background_jobs.py:305`): "ghi kết quả + tạo dòng kế" là nguyên tử.
- Dòng kế được `enqueue` với `enqueue_after_commit=True` như hiện nay (`lab_xero/outbox.py:33-40`): job kế không thể chạy trước khi bước trước commit.
- Job có thể raise và rollback hết (`03`, "Thất bại nghĩa là gì"): khi đó dòng vẫn `Pending`, SAGA không tiến, không lùi. Đúng.
- Row lock trên dòng outbox (`tasks/xero_sync.py:11`) cộng lock trên bản ghi SAGA: hai job của cùng một SAGA không cùng quyết định.

Về `@xero_atomic(compensate=...)` trong `OVERVIEW.md`: nó là cách **khai báo** bảng bước ở trên ngay tại hàm của bước. Xây bảng bước dạng dữ liệu thuần trước; decorator là lớp đường, thêm sau (`12` cũng khuyên vậy).

## Cần gì để xây (chưa có gì trong số này)

**Bạn tạo trong Desk** (AGENTS.md B2: agent không viết DocType JSON):

| DocType | Field | Kiểu | Vì sao |
|---|---|---|---|
| Lab Xero Saga (mới, module Lab Xero) | `saga_type` | Data | tên bảng bước, ví dụ `invoice_with_payment` |
| | `reference_doctype`, `reference_name` | Link → DocType, Dynamic Link | tài liệu nghiệp vụ |
| | `status` | Select: Running, Completed, Compensating, Compensated, Stuck | trạng thái của cả chuỗi |
| | `current_step` | Int | đang ở bước mấy |
| | `error` | Small Text | lý do quay đầu |
| Lab Xero Outbox | `saga` | Link → Lab Xero Saga | dòng thuộc SAGA nào (trống = dòng một bước như hôm nay) |
| | `step_no` | Int | bước mấy |
| | `is_compensation` | Check | dòng bù trừ |
| | `next_attempt_at` | Datetime | cho sweeper (đã nêu trong `12`) |

Permission của `Lab Xero Saga`: cùng câu hỏi mở với outbox (`SPRINT.md`): user hay hệ thống sở hữu.

**Code** (mỗi dòng là một yêu cầu riêng):

```text
            ┌─ A. sweeper + next_attempt_at         tasks/xero_sync.py         (điều kiện tiên quyết; 12 mục B)
 Desk ──────┤
 (bạn)      ├─ B. client giả: create_payment,       integrations/xero/client.py
            │     void_invoice, title "payfail"
            └─ C. bảng bước + advance()             lab_xero/saga.py (mới), gọi từ tasks/xero_sync.py
                         │                           ↑ A và C cùng sửa tasks/xero_sync.py: KHÔNG song song
                         ▼
              D. test: bước 2 bị từ chối → invoice bị void, SAGA Compensated; chạy advance hai lần → một dòng bù
                         │
                         ▼
              E. áp vào ERPNext: doc_events trên Sales Invoice / Payment Entry   overrides/ (handler mỏng) + hooks.py
```

B song song được với A. C chờ A (cùng file). E đụng `hooks.py`: mỗi lúc một phiên.

## Xem "có và không có SAGA" bằng mắt

Đề xuất demo, dùng client giả nên không cần tài khoản Xero:

1. Thêm vào client giả hai thao tác (`create_payment`, `void_invoice`) và một title kích hoạt: chứa `payfail` thì `create_payment` bị từ chối.
2. Một setting `saga_enabled` (Check, trên `Lab Xero Settings`, DocType đã được đề xuất trong `11`/`12`).
3. Tạo hai note cùng title `payfail demo`, một với setting tắt, một với setting bật, rồi so:

| Nhìn vào | Tắt (không SAGA) | Bật (có SAGA) |
|---|---|---|
| Dòng outbox | A `Done`, B `Failed` | A `Done`, B `Failed`, C (void) `Done` |
| Xero giả | invoice còn sống, không payment | invoice đã void |
| Note | `Failed` trong khi Xero vẫn có invoice: **lệch** | `Failed`, Xero không còn gì hiệu lực: **khớp** |
| Bản ghi SAGA | không có | `Compensated`, kèm lý do |

Bảng đó chính là câu trả lời cho "SAGA mua được gì". Nhánh "tắt" chỉ tồn tại để so sánh trong lab; không mang sang dự án thật.

## Về sau: cùng các kịch bản, với broker

`OVERVIEW.md` muốn so sánh với Redpanda/Kafka. Khác biệt cần quan sát khi tới đó [G]:

| | Outbox + job (orchestration, lab) | Broker (choreography) |
|---|---|---|
| Vận chuyển | Redis queue, at-most-once; outbox + sweeper bù thành at-least-once | Log bền, at-least-once, replay theo offset |
| Thứ tự | Orchestrator tạo từng bước | Theo partition key |
| Trạng thái chuỗi | Một bản ghi SAGA | Suy ra từ event, hoặc thêm một service theo dõi |
| Vẫn phải có | Idempotency ở consumer, compensation, semantic lock | Y hệt: broker **không** thay được ba thứ này |
| Hạ tầng thêm | Không | Một cụm broker, một bước relay outbox → topic |

Dự đoán [I]: với một hệ thống làm chủ luồng và một bên ngoài (Xero), broker không sửa được tình huống nào trong bảng 11 dòng mà outbox + sweeper chưa sửa. Nó đáng giá khi có nhiều service cùng nghe.

## Các quyết định là của bạn (AGENTS.md A15)

| # | Câu hỏi | Khuyến nghị |
|---|---|---|
| 1 | Kiểu điều phối | Orchestration trên outbox đang có; broker để sau |
| 2 | Lab Note có dùng SAGA không | Không. Giữ một bước; SAGA demo trên một luồng hai bước riêng |
| 3 | Invoice tạo `AUTHORISED` ngay hay `DRAFT` rồi authorise ở cuối | `AUTHORISED` ngay cho demo (thấy được void); dự án thật hỏi kế toán |
| 4 | Compensation hỏng hẳn thì sao | `Stuck` + báo người; không tự thử vô hạn |
| 5 | Contact tạo dở có bù không | Không; để lại |
| 6 | Sweeper trước hay SAGA trước | Sweeper trước: không có nó, SAGA kẹt ở trường hợp 2 |
| 7 | Nhánh "không SAGA" trong code | Chỉ là một setting của lab để so sánh |

## Thử đi (chỉ đọc)

1. Đọc `tasks/xero_sync.py` (51 dòng) và chỉ ra dòng mà `advance(row)` sẽ được gọi. Có hai chỗ return sớm sau `_mark_failed` và một chỗ ở cuối: cả ba đều phải gọi.
2. Với bảng bước "trả hàng", viết ra giấy trạng thái của SAGA và của ba dòng outbox sau từng job khi bước 2 bị từ chối. So với mục "Có SAGA" ở trên.
3. Trả lời không nhìn: vì sao một `429` ở bước 2 **không** được kích hoạt compensation?

## Còn chưa biết

- Mọi thứ [G]: thuật ngữ và phân loại bước của SAGA được viết từ trí nhớ.
- Hành vi thật của Xero khi void một invoice vừa tạo, và khi void lần hai (no-op hay lỗi): `10` đánh dấu là cần verify trên Demo Company.
- `advance` chạy với tư cách user nào sau một lần retry do deadlock (`03`, "Job là ai?"): ảnh hưởng tới permission trên `Lab Xero Saga`.
- Cách chặn cancel trên tài liệu ERPNext khi SAGA đang chạy mà không sửa ERPNext: một handler `doc_events` `before_cancel` là phỏng đoán tự nhiên, chưa trace.
