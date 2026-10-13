# Kế hoạch: tổng quan

File duy nhất ở tầng trên của `plan/`. Nó chỉ nói: có những kế hoạch nào, cái nào đang có hiệu lực, và agent (trợ lý AI) phải đọc gì. Kiến thức không nằm ở đây; nó nằm trong `docs/`.

```text
plan/
  overview.md      file này
  general/         ĐANG LÀM: lab học và trace Frappe (các track A–M)
    README.md  OVERVIEW.md  INIT.md  SPRINT.md  TRACK-A.md
  done/            ĐÃ XONG: kế hoạch đã hoàn thành, giữ để tra cứu, không còn hiệu lực
    xero/            tích hợp Xero (demo ngày 2026-10-12)
      PLAN.md  board/

docs/              kiến thức, không phải kế hoạch
  knowledge/       kiến thức chung về Frappe (bắt đầu ở 22: bản đồ chủ đề và cách đọc)
  xero/            mọi thứ cần hiểu cho tích hợp Xero (tự đủ)
  traces/  runbooks/  refer/
demo_xero/         kịch bản demo và giải thích toàn bộ phần tích hợp Xero
oauth_lab/         (sẽ tạo ở track N) dự án thực hành OAuth, ngoài Frappe: FastAPI + Spring Boot + React
```

## Where we are (Hiện trạng)

| Phần | Trạng thái | Chi tiết |
|---|---|---|
| **Lab học và trace Frappe** (các track A–N) | **CURRENT (đang làm)** từ 2026-10-13 | `plan/general/OVERVIEW.md`; cách đọc: `docs/knowledge/22-ban-do-chu-de-va-tai-lieu-doc.md`. Track N (OAuth từ lõi, thêm 2026-10-13): `plan/general/TRACK-N.md` |
| Tích hợp Xero (email của Engineering Lead ngày 2026-10-04, và các yêu cầu thêm) | DONE (xong giai đoạn 1, đã demo 2026-10-12); lưu trữ 2026-10-13 | `plan/done/xero/PLAN.md` |

Chỉ cập nhật bảng này khi con người yêu cầu, hoặc nói một phần đã xong.

## Chỉ dẫn cho agent

1. **Kế hoạch đang có hiệu lực là `plan/general/OVERVIEW.md`** (mục tiêu, quyết định, các track và thứ tự), cùng `INIT.md` (cấu trúc) và hướng dẫn của track đang làm (`TRACK-<chữ>.md`, nếu có).
2. **`plan/done/` không có hiệu lực.** Không làm việc theo nó, không cập nhật trạng thái trong nó. Đọc `plan/done/xero/PLAN.md` (mục "Dữ kiện chung" và các luật nghiệp vụ) **trước khi sửa code Xero**, vì nó vẫn mô tả đúng code đó.
3. **Code Xero là ví dụ thật cho các track.** Khi một track cần một đối tượng để áp dụng (response chung, guard quyền, lint cấu trúc…), dùng luồng Xero có sẵn thay vì dựng ví dụ mới.
4. Kiến thức chung: `docs/knowledge/00-README.md`; bản đồ chủ đề và cách đọc: `docs/knowledge/22-ban-do-chu-de-va-tai-lieu-doc.md`. Kiến thức Xero: `docs/xero/00-README.md`, `demo_xero/00-README.md`.
5. **Khi con người hỏi "làm gì bây giờ?"** (what should I do now, what next): đọc bảng "Where we are" và mục "Order" của `plan/general/OVERVIEW.md`, và mục Status của hướng dẫn track đang làm. Trả lời theo `AGENTS.md` A17: việc nào làm song song được, file nào đụng nhau.
6. Không tạo file kế hoạch mới ở tầng trên của `plan/`. Kế hoạch mới vào `plan/general/` khi con người yêu cầu; kế hoạch xong thì con người yêu cầu chuyển vào `plan/done/`.

## Những điều đúng cho mọi kế hoạch

- **Một app**: mọi code của ta nằm trong `frappe-bench/apps/lab_core`. Bố cục: `api/` (endpoint), `lab_core/` và `lab_xero/` (module nghiệp vụ), `integrations/xero/` (client Xero), `tasks/` (background job), `overrides/` (chỉ chứa thay đổi hành vi của Frappe, ERPNext, CRM), `setup/` (cấu hình và custom field tạo bằng code).
- **Hai loại code, hai cách thay đổi.** Code của ta: sửa trực tiếp trong chính file của nó, không bao giờ bị hook hay override. Code của Frappe, ERPNext, CRM: không bao giờ sửa; hành vi của nó được đổi từ `overrides/` qua các điểm mở rộng, bằng handler mỏng gọi sang module của ta.
- **Một lệnh dựng lab**: `docker compose up --build -d` từ thư mục gốc; con người chạy mọi lệnh. Site: `lab.localhost`, cổng 8000 và 9000.
- **DocType** do con người tạo trong Desk; agent không viết DocType JSON.
- **Repo dùng git và là repo công khai**, một nhánh `main`. Tài liệu riêng (`docs/refer/`, ảnh chụp màn hình) không bao giờ được đưa lên.
- **Idempotency là yêu cầu xuyên suốt.** Mọi thao tác có thể bị chạy lại (request bị gửi lại, job trùng, hook chạy lại khi lưu lại, lịch chạy chồng, kéo dữ liệu lần hai) phải cho cùng một kết quả. Bảng theo từng track: `plan/general/README.md`.

## Việc còn nợ từ pha Xero (làm trong track K/L, theo đúng thứ tự)

Thêm ngày 2026-10-13 theo yêu cầu của con người. Kế hoạch gốc của chúng: `plan/done/xero/PLAN.md` (giai đoạn 2).

| Thứ tự | Việc | Vì sao đứng ở đây | Đọc trước |
|---|---|---|---|
| 1 | **Sweeper**: job theo lịch, nhặt các dòng outbox `Pending` bị bỏ quên và các dòng `Failed` còn thử lại được | luồng một bước hiện tại đã cần nó (đơn kẹt ở `Queued` phải bấm Retry tay); SAGA không chạy được nếu thiếu nó | `docs/knowledge/13-saga.md`, `docs/knowledge/05` (Email Queue là ví dụ của Frappe), `docs/xero/04-trong-frappe.md` mục E, bản nháp code ở `demo_xero/08` mục 11.4 |
| 2 | Lỗi và response chung (PE) | thuộc track A2; sweeper cần phân biệt lỗi thử lại được với lỗi không | `docs/knowledge/14` |
| 3 | `@xero_atomic` và SAGA (P4) | đứng trên sweeper | `docs/knowledge/13-saga.md` |
| 4 | Mất kết nối Xero (P3) | sau cùng | `demo_xero/02`, mục "Khi hỏng" |

Cần con người làm trước việc 1: một field mới trên DocType `Lab Xero Outbox` (ví dụ `next_attempt_at`, kiểu Datetime), tạo trong Desk. Sweeper thêm một dòng vào `hooks.py`.

## Idempotency: những gì kế hoạch còn thiếu để gọi là "đã triển khai"

Thêm ngày 2026-10-13 sau khi rà lại. Nguyên tắc đã có đủ: bảng theo track ở `plan/general/README.md`, bảng theo thao tác ở `plan/done/xero/PLAN.md` (mục Idempotency), ba lớp chống trùng ở `demo_xero/06`. Thứ còn thiếu là **việc cụ thể** và **bằng chứng**:

| # | Thiếu gì | Vì sao là lỗ hổng | Làm ở track |
|---|---|---|---|
| 1 | **Bằng chứng "chạy hai lần → một kết quả" cho luồng Xero.** Chưa lần nào được ghi lại: submit hai lần, hai job cùng một dòng outbox, Retry sau khi Xero đã tạo, kéo về hai lần, cùng một credit note tới hai lần | code đã viết để idempotent nhưng chưa ai chứng minh; pha Xero bỏ test | K (làm đầu tiên; cần chốt quyết định số 2 bên dưới về test) |
| 2 | **Idempotency cho request đi VÀO endpoint của ta**: client gửi lại một POST (bấm đôi, mạng chập chờn). Bảng track A chỉ nêu yêu cầu, chưa có cơ chế | hiện chỉ `retry_sync`/`refresh` an toàn nhờ `job_id`; một endpoint "tạo" bất kỳ sẽ sinh bản ghi thứ hai | A2: một cơ chế dùng chung (client gửi một khóa, server nhớ khóa và trả lại kết quả cũ), không viết riêng từng endpoint |
| 3 | **Sweeper** (đã có ở mục trên) phải tự idempotent: hai lượt quét chồng nhau, quét trúng dòng đang chạy | sweeper là nguồn "chạy lại" lớn nhất | K, việc 1 |
| 4 | **Khóa gửi sang Xero khi thử lại sau 6 phút**: Xero chỉ nhớ `Idempotency-Key` khoảng 6 phút; hiện lớp chống trùng thật là "tra trước khi tạo". Các thao tác **không tra được** (cập nhật contact, ghi chú) chưa có cách chống trùng | thêm thao tác mới là thêm lỗ hổng | K, cùng `@xero_atomic` |
| 5 | **Đổi tên Customer** làm hỏng phép tra theo mã, tức làm hỏng chính lớp chống trùng contact | `demo_xero/13` mục 3; bản sửa nháp ở `demo_xero/08` mục 11.3 | K |
| 6 | **Phía trình duyệt**: khóa nút khi đang gửi, không gửi lại mutation tự động | lớp chặn rẻ nhất, chưa có trong track I | I, I2 (thêm một kịch bản "bấm đôi" vào bốn kịch bản so sánh) |
| 7 | **Một danh sách kiểm dùng chung** cho mọi tính năng mới: thứ gì có thể chạy lại, khóa tự nhiên là gì, ràng buộc unique nào, tác động phụ nào chỉ được làm một lần | hiện mỗi phiên tự nhớ | L: đưa vào guard/lint và vào mẫu tóm tắt của agent |
| 8 | **Hai worker thật chạy chồng nhau** chưa từng được thử (khóa dòng mới chỉ đúng trên giấy) | `demo_xero/08` mục 5 | E, J |

Thứ tự đề xuất: 1 → 3 → 2 → 5 → 4 → 7 → 6 → 8. Các dòng còn lại của bảng theo track (mail không gửi hai lần, patch chạy lại được, event realtime tới hai lần) đã có chỗ ở track H, J, F và không cần thêm gì.

## Quyết định còn mở (con người chưa chốt)

Mỗi cái cần được chốt trước khi track liên quan bắt đầu.

| # | Câu hỏi | Liên quan | Ghi chú |
|---|---|---|---|
| 1 | Bộ công cụ lint và pre-commit: theo đúng R-C1 của sổ tay tham khảo, hay `ruff` (đã cấu hình) + semgrep + eslint? | track L | con người chọn "quyết định sau" ngày 2026-10-13; đề xuất ở `docs/knowledge/22-…`, mục 4.6 |
| 2 | ~~Có viết test không?~~ **ĐÃ CHỐT 2026-10-13: viết test bình thường trở lại.** `AGENTS.md` B5 có hiệu lực đầy đủ (mỗi endpoint có test quyền theo role); ngoại lệ "không test" chỉ thuộc pha Xero đã xong | mọi track | luật tách việc vẫn giữ (`AGENTS.md` A2): một yêu cầu là code **hoặc** test; phiên viết test không sửa code để test qua; con người chạy test |
| 3 | Handler gắn vào ERPNext nằm ở đâu? `AGENTS.md` B2a ghi `<domain>/events/`; code Xero đặt ở `overrides/` | track D | chọn một, rồi sửa bên còn lại |
| 4 | Sprint (`plan/general/SPRINT.md`) còn cần không? Nó mô tả code mà kế hoạch Xero đã dùng và gỡ một phần | `plan/general/` | bảng "Where we are" của `OVERVIEW.md` vẫn ghi sprint là CURRENT |
| 5 | Bảng trạng thái và vài dòng trong `plan/general/OVERVIEW.md` đã cũ ("không dùng git", "chưa có công cụ lint", track K chưa bắt đầu) | `plan/general/` | danh sách đầy đủ: `docs/knowledge/22-…`, mục 3 |
