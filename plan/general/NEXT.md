# Hướng đi sau pha Xero: đọc gì, làm gì trước, giao việc cho agent thế nào

Viết ngày 2026-10-13, theo yêu cầu của con người. Dành cho **con người** và **agent** (trợ lý AI: Codex, Claude Code) mở một phiên mới sau khi pha Xero đã xong.

File này **không thay** kế hoạch nào. Nó chỉ nối các file đã có thành một đường đi. Khi nó lệch với `plan/overview.md` hoặc `OVERVIEW.md` thì hai file đó thắng. Trạng thái (xong / chưa) **không** ghi ở đây: xem bảng "Where we are" của `plan/overview.md` và mục Status của từng `TRACK-<chữ>.md`.

## Trong năm dòng

1. Kế hoạch đang có hiệu lực là `plan/general/OVERVIEW.md` (các track A–N). Kế hoạch Xero nằm ở `plan/done/xero/` và chỉ để tra cứu.
2. Pha Xero làm track K **trước** phần nền, nên code Xero còn thiếu đúng những thứ phần nền dạy: response và lỗi chung (A2), quyền (C), hàng rào (L).
3. Vì vậy hướng đi là: **quay lại phần nền A → A2 → B → C → D, và mỗi track áp ngay lên luồng Xero có sẵn**, không dựng ví dụ mới.
4. Song song với phần nền có ba việc không đụng file của nhau: sweeper (job quét outbox) của Xero, track N (OAuth, trong `oauth_lab/`), và việc đọc tài liệu.
5. Trước khi bắt đầu, con người chốt ba quyết định còn mở (mục "Chốt trước").

## Bức tranh

```text
 CHỐT TRƯỚC (con người, khoảng 15 phút): quyết định 3, 4, 5 trong plan/overview.md
        │
        ▼
 LÀN NỀN (đúng thứ tự, mỗi lúc một track)
   A (đang dở) ──► A2 ──► B ──► C ──► D ──► L ──► I2
                    │                  │
                    │                  └─ D và sweeper cùng sửa hooks.py: không làm cùng lúc
                    └─ A2 = phase PE còn nợ của Xero (lỗi và response chung)

 SONG SONG VỚI LÀN NỀN (không đụng file của làn nền)
   ├─ Nợ Xero 1: sweeper          tasks/, một dòng hooks.py, một field mới do con người tạo trong Desk
   ├─ Track N: OAuth từ lõi       chỉ oauth_lab/ (stage cuối chờ B)
   ├─ E, F, G, H, I, J            sau D; thứ tự nào cũng được; F, G, H cần runbook tài khoản ngoài trước
   └─ Đọc tài liệu                docs/knowledge/22, mục 4 (không đụng file nào)

 SAU SWEEPER (đúng thứ tự):  @xero_atomic và SAGA ──► mất kết nối Xero
 XEN KẼ:                     M (tối ưu), chỉ khi một luồng thật cho thấy cần
```

Thứ tự này lấy từ `OVERVIEW.md` mục "Order", `plan/overview.md` mục "Việc còn nợ từ pha Xero", và `docs/knowledge/22-ban-do-chu-de-va-tai-lieu-doc.md` mục 8.

## Đọc gì, theo thứ tự nào

**Con người, một lần (khoảng 40 phút):** `docs/knowledge/22-…` mục 1 và 3 → `docs/knowledge/00-README.md` (bảng nhãn, năm ý tưởng) → `docs/traces/cram-sheet.md`.

**Agent, mỗi phiên:** `AGENTS.md` → `plan/overview.md` → file này → hướng dẫn của track đang làm (`TRACK-<chữ>.md`, nếu có) → bảng "Cách đọc" của `docs/knowledge/22-…` cho đúng dòng của track đó. Chỉ mở `plan/done/xero/PLAN.md` (mục "Dữ kiện chung" và luật nghiệp vụ) khi sắp sửa code Xero.

## Chốt trước (việc của con người)

Ba quyết định trong `plan/overview.md`, mục "Quyết định còn mở". Đề xuất bên dưới là của agent viết file này, chưa được chốt.

| # | Câu hỏi | Chặn việc gì | Đề xuất |
|---|---|---|---|
| 3 | Handler gắn vào ERPNext nằm ở `overrides/` hay `<domain>/events/`? | track D, và mọi phiên viết handler | giữ `overrides/` như code đang có; sửa câu chữ `AGENTS.md` B2a cho khớp |
| 4 | `SPRINT.md` còn cần không? | bảng "Where we are" của `OVERVIEW.md` | coi là lịch sử; không làm tiếp |
| 5 | Các dòng đã cũ trong `OVERVIEW.md` ("không dùng git", "chưa có lint", sprint CURRENT, K chưa bắt đầu) | agent đọc nhầm hiện trạng | một yêu cầu riêng: sửa đúng các dòng đó |

Quyết định 1 (bộ công cụ lint) chỉ cần trước track L. Quyết định 2 (test) đã chốt: viết test bình thường trở lại.

## Từng chặng

"Áp lên" là thứ có sẵn trong code Xero mà track đó dùng làm đối tượng, thay vì dựng ví dụ mới.

| Chặng | Việc | Áp lên | Đọc trước | Xong khi |
|---|---|---|---|---|
| A | đóng track đang dở: thí nghiệm stage 7, câu hỏi mở stage 2, stage 9 | `lab_core/api/xero.py`, `api/hello.py` | `TRACK-A.md` mục Status; `docs/traces/rpc-and-document-api.md` | đạt mục "Track xong khi" của `TRACK-A.md` |
| A2 | lỗi có tên và status; một dạng response cho mọi endpoint của `lab_core`, áp ở một chỗ | `lab_core/errors.py`, endpoint Xero, lỗi của job Xero trên đơn | `docs/knowledge/14`; `docs/xero/11-loi-va-response.md` | endpoint Xero trả lỗi theo một dạng, không endpoint nào tự try/except; dạng đó được ghi trong `docs/adr/` |
| B | session, `sid`, CSRF, token, user của job; đăng nhập Google | Connected App `xero` | cram-sheet mục 1; `docs/knowledge/01`; `demo_xero/12` | con người tự giải thích được đường đăng nhập; SPA gửi được POST đầu tiên |
| C | quyền theo role, từng lớp kiểm ở đâu | điểm yếu "chỉ System Manager submit được Sales Order" | cram-sheet mục 2; `docs/knowledge/01` | một role không phải System Manager chạy được luồng Xero; mỗi endpoint có test quyền theo role |
| D | `hooks.py` nạp và gộp thế nào, thứ tự `doc_events`, các kiểu override | `lab_core/hooks.py`, `overrides/sales_order.py` | cram-sheet mục 3; `docs/knowledge/02`, `19` | chứng minh handler không cộng dồn khi tài liệu được lưu lại |
| Nợ Xero 1 | sweeper: job theo lịch nhặt dòng outbox `Pending` bị bỏ quên và dòng `Failed` còn thử lại được | `tasks/xero_sync.py`, `Lab Xero Outbox` | `plan/overview.md` mục "Việc còn nợ"; `docs/knowledge/13`, `03` | đơn kẹt ở `Queued` tự sang Xero không cần bấm Retry; hai lượt quét chồng nhau vẫn ra một invoice |
| N | OAuth từ lõi, ngoài Frappe | `oauth_lab/` | `TRACK-N.md` | theo từng stage của `TRACK-N.md` |
| E–J, L, I2, M | theo `OVERVIEW.md` | cột "Ví dụ thật" trong bảng "Cách đọc" của `docs/knowledge/22-…` | cùng bảng đó | con người yêu cầu một `TRACK-<chữ>.md` khi tới lượt |

Chặng chưa có hướng dẫn riêng (A2, B, C, D và về sau): yêu cầu đầu tiên của chặng nên là "viết `plan/general/TRACK-<chữ>.md`", theo mẫu của `TRACK-A.md`.

## Dữ kiện chung (mọi phiên giữ giống nhau)

- **Một app:** mọi code của ta ở `frappe-bench/apps/lab_core`; riêng track N ở `oauth_lab/`.
- **`hooks.py` là một file:** hai phiên không sửa nó cùng lúc. Hôm nay nó đã có `doc_events` cho Sales Order và một `scheduler_events` cho `xero_pull` (`lab_core/hooks.py:18-29`); sweeper và track D đều đụng vào đây.
- **Một yêu cầu là code hoặc test, không cả hai** (`AGENTS.md` A2). Phiên viết test không sửa code để test qua.
- **Con người chạy mọi lệnh**; DocType và field mới do con người tạo trong Desk. Sweeper cần một field mới trên `Lab Xero Outbox` (ví dụ `next_attempt_at`, kiểu Datetime) trước khi viết code.
- **Idempotency:** trước khi coi một chặng là xong, trả lời câu hỏi của chặng đó trong bảng "Idempotency: yêu cầu xuyên suốt khi quay lại" (`README.md` cùng thư mục).
- **Luồng Xero là ví dụ thật** cho mọi track (`plan/overview.md`, chỉ dẫn 3).
- **Xero vẫn 0 đồng:** chỉ Demo Company và bậc miễn phí.

## Giao việc cho agent: mỗi yêu cầu một việc

```text
 Trace:   "Track <chữ>, stage <số>. Đọc TRACK-<chữ>.md và dẫn tôi qua stage đó."
 Code:    "Chặng <tên> trong plan/general/NEXT.md. Viết <một việc>. Chỉ code, không test."
 Test:    "Viết test cho <endpoint hoặc job>. Chỉ file test."
 Review:  "Review <file> theo skill code-reviewer."
 Tiếp:    "Làm gì bây giờ?"   → agent trả lời theo AGENTS.md A17: việc nào song song, file nào đụng nhau
```

Agent dừng ở cuối yêu cầu, không tự sang việc kế. Khi con người nói một stage hoặc một chặng đã xong, agent mới sửa đúng dòng trạng thái đó trong file của nó.

## Ngoài phạm vi

Kafka/Redpanda và cụm container cho log (hoãn vô thời hạn, `README.md` cùng thư mục); webhook của Xero (cần URL công khai, lab không có: `docs/knowledge/17-webhooks.md`); mọi thứ tốn tiền.
