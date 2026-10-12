# Kế hoạch chung (để đó từ 2026-10-12)

Thư mục này giữ **mọi kế hoạch và trạng thái đã có trước khi chuyển sang tập trung vào Xero**: lab học và trace Frappe. Không file nào ở đây đang có hiệu lực; kế hoạch hiện hành là `plan/xero/PLAN.md` (xem `plan/overview.md`). Nội dung các file được giữ nguyên như lúc chuyển vào.

## Có gì ở đây

| File | Là gì |
|---|---|
| `OVERVIEW.md` | Tổng quan của lab: mục tiêu, các quyết định, bố cục "One app", các track A–M và thứ tự, ý tưởng transaction cho Xero |
| `INIT.md` | Cấu trúc hệ thống và app, bộ khung ban đầu, luật "code của ta / code không phải của ta" |
| `SPRINT.md` | Lượt đi nhanh hai giờ: một Lab Note đi qua endpoint, outbox, job và một Xero giả; bảng dữ kiện của nó |
| `TRACK-A.md` | Hướng dẫn track A (request và API), có mục Status riêng |

Các file này gọi nhau bằng tên trần (`INIT.md`, `SPRINT.md`…), nên vẫn đúng khi nằm cùng một thư mục. Chỗ nào chúng ghi `docs/plan/…` thì nay là `plan/general/…`.

## Trạng thái lúc để đó

Chép từ mục "Where we are" của `OVERVIEW.md` và mục "Đang ở đâu" của `SPRINT.md`, cộng với những gì thấy trên đĩa ngày 2026-10-12.

| Phần | Trạng thái |
|---|---|
| Runtime của lab (một lệnh, tự cài đặt) | DONE |
| Bộ khung: `lab_core`, module "Lab Xero", DocType "Lab Note", endpoint hello kèm test, vỏ SPA tại `/lab` | DONE |
| Sprint: backend (endpoint, service, controller, outbox, job, Xero giả, 8 test) | đã viết, **chưa chạy** |
| Sprint: phần Desk của con người (role `Lab User`, hai field trên Lab Note, DocType `Lab Xero Outbox`) | chưa làm (`lab_note.json` mới có `title`, `content`) |
| Sprint: trang SPA F1, F2 | chưa bắt đầu (`frontend/src/pages/` mới có các trang Hello) |
| Sprint: sáu cơ chế trong `docs/traces/cram-sheet.md` | DONE |
| Track A | PAUSED; xem mục Status trong `TRACK-A.md` |
| Track A2, B, C, D và mọi track còn lại | NOT STARTED |

## Kế hoạch Xero đã lấy gì từ đây

Để khi quay lại không làm trùng:

- Outbox và khung job đồng bộ của sprint được giữ làm **nền** của `plan/xero/PLAN.md`.
- Client thế chỗ ("Xero giả") của sprint, đường "sync Lab Note sang Xero" và các test dựa vào chúng **bị gỡ** trong kế hoạch Xero (con người chốt ngày 2026-10-12: chỉ Xero thật, không viết test cho demo). Khi quay lại, `SPRINT.md` mô tả thứ không còn trong code.
- Track K (Xero) của `OVERVIEW.md` chính là `plan/xero/PLAN.md`.
- Ý tưởng `@xero_atomic` trong "The Xero transaction idea" được làm ở P4 của kế hoạch Xero.

## Kế hoạch Xero đã bỏ hoặc đổi gì so với đây

Con người quyết định ngày 2026-10-12; các file ở đây **chưa** được sửa theo.

- Không SPA cho tích hợp Xero (F1, F2 của sprint không cần cho việc đó); SPA vẫn là một phần của lab này khi quay lại.
- Không Kafka/Redpanda và không cụm container cho log: phần "so sánh với broker" và Goal 4 của `OVERVIEW.md` được hoãn vô thời hạn.
- Track K được làm trước các track nền (A2, B, C, D, L) vì deadline.

## Idempotency: yêu cầu xuyên suốt khi quay lại

Con người yêu cầu ngày 2026-10-12: cẩn thận với idempotency (chạy lại bao nhiêu lần cũng ra một kết quả) ở cả kế hoạch Xero và kế hoạch học này. Các file kế hoạch cũ chưa nói rõ điều đó; khi tiếp tục một track, hỏi câu này trước khi coi nó là xong:

| Track | Thứ có thể bị chạy lại | Phải chứng minh |
|---|---|---|
| A, A2 (request, lỗi) | client gửi lại một POST (bấm đôi, retry khi mạng chập chờn) | thao tác tạo không sinh bản ghi thứ hai; thao tác trên trạng thái sai trả lỗi có tên (409), không lặng lẽ làm lại |
| D (hook, event) | handler chạy lại mỗi lần tài liệu được lưu | handler không cộng dồn, không tạo thêm bản ghi con ở lần lưu sau |
| E (background job) | job trùng, retry, job chạy lại sau khi worker chết | `deduplicate` chỉ bảo vệ queue; tính idempotent phải nằm trong chính job (khóa dòng + kiểm tra trạng thái) |
| scheduler | hai lượt chạy chồng nhau, chạy bù sau khi tắt máy | lượt thứ hai không xử lý lại thứ lượt đầu đã xong |
| F (realtime), webhook | cùng một event tới hai lần, tới sai thứ tự | bên nhận bỏ được bản trùng; coi event là gợi ý, đọc lại trạng thái |
| H (mail) | job gửi mail chạy lại | không gửi hai thư cho một việc (Email Queue là ví dụ đáng trace) |
| J (dữ liệu) | migrate và patch chạy nhiều lần | patch idempotent (AGENTS.md B2); schema chỉ qua migrate |
| K (Xero) | mọi thứ ở trên, cộng với một hệ thống bên ngoài | đã thành một mục riêng trong `plan/xero/PLAN.md` |

Kiến thức đã viết: `docs/knowledge/18-non-functional.md` (race, làm hai lần), `20-transaction-handling.md` (luật 4), `12-xero-sync-design.md` (ba lớp chống trùng).

## Khi quay lại

Thứ tự gợi ý: (1) đánh dấu lại trạng thái trong `OVERVIEW.md` theo những gì kế hoạch Xero đã làm xong; (2) quyết định sprint còn cần không, vì phần lớn nó đã được dùng; (3) tiếp tục track A từ mục Status của nó; (4) rồi A2, B, C, D theo "Order". Kiến thức đã viết sẵn cho các track nằm ở `docs/knowledge/` và `docs/traces/`.
