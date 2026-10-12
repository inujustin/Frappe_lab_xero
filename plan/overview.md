# Kế hoạch: tổng quan

File duy nhất ở tầng trên của `plan/`. Nó chỉ nói: có những kế hoạch nào, cái nào đang có hiệu lực, và agent (trợ lý AI) phải đọc gì. Kiến thức không nằm ở đây; nó nằm trong `docs/`.

```text
plan/
  overview.md      file này
  xero/            ĐANG LÀM: việc người giao việc yêu cầu + các yêu cầu thêm của con người
    PLAN.md
  general/         ĐỂ ĐÓ: mọi kế hoạch và trạng thái đã có từ trước (lab học và trace Frappe)
    README.md  OVERVIEW.md  INIT.md  SPRINT.md  TRACK-A.md

docs/              kiến thức, không phải kế hoạch
  xero/            mọi thứ cần hiểu cho tích hợp Xero (tự đủ)
  knowledge/       kiến thức chung về Frappe
  traces/  runbooks/  refer/
```

## Where we are (Hiện trạng)

| Phần | Trạng thái | Chi tiết |
|---|---|---|
| **Tích hợp Xero** (email của Engineering Lead ngày 2026-10-04, và các yêu cầu thêm) | **CURRENT (đang làm)** | `plan/xero/PLAN.md`, mục Status |
| Lab học và trace Frappe (sprint, các track A–M) | PARKED (để đó) từ 2026-10-12 | `plan/general/README.md` |

Chỉ cập nhật bảng này khi con người yêu cầu, hoặc nói một phần đã xong.

## Chỉ dẫn cho agent

1. **Kế hoạch đang có hiệu lực là `plan/xero/PLAN.md`.** Đọc nó trước mọi việc trong dự án. Nó tự đủ: không cần mở `plan/general/` để làm việc.
2. **`plan/general/` không có hiệu lực.** Không làm việc theo nó, không cập nhật trạng thái trong nó, không coi `SPRINT.md` ở đó là kế hoạch hiện hành, trừ khi chính lời nhắc của con người yêu cầu.
3. Việc không phục vụ tích hợp Xero thì **không làm bây giờ**: ghi một dòng vào phần tóm tắt và để lại.
4. Kiến thức để làm việc: `docs/xero/00-README.md`. Kiến thức chung: `docs/knowledge/00-README.md`.
5. **Khi con người hỏi "làm gì bây giờ?"** (what should I do now, what next): đọc `plan/xero/board/README.md` và các file làn ở đó, rồi trả lời theo mẫu trong file ấy. Việc được chia sẵn thành các làn không đụng file của nhau, nên một, hai hay ba phiên của các agent khác nhau cùng làm được.
6. Không tạo file kế hoạch mới ở tầng trên của `plan/`. Kế hoạch cho Xero vào `plan/xero/`; mọi thứ khác vào `plan/general/` khi con người yêu cầu.

## Những điều đúng cho mọi kế hoạch

Rút từ `plan/general/OVERVIEW.md` và `INIT.md`, nhắc lại ở đây để không phải mở chúng:

- **Một app**: mọi code của ta nằm trong `frappe-bench/apps/lab_core`. Bố cục: `api/` (endpoint), `lab_core/` và `lab_xero/` (module nghiệp vụ), `integrations/xero/` (client Xero), `tasks/` (background job), `overrides/` (chỉ chứa thay đổi hành vi của Frappe, ERPNext, CRM), `setup/` (custom field tạo bằng code).
- **Hai loại code, hai cách thay đổi.** Code của ta: sửa trực tiếp trong chính file của nó, không bao giờ bị hook hay override. Code của Frappe, ERPNext, CRM: không bao giờ sửa; hành vi của nó được đổi từ `overrides/` qua các điểm mở rộng, bằng handler mỏng gọi sang module của ta.
- **Một lệnh dựng lab**: `docker compose up --build -d` từ thư mục gốc; con người chạy mọi lệnh. Site: `lab.localhost`, cổng 8000 và 9000.
- **DocType** do con người tạo trong Desk; agent không viết DocType JSON.
- **Idempotency là yêu cầu xuyên suốt, ở cả hai kế hoạch.** Mọi thao tác có thể bị chạy lại (request bị gửi lại, job trùng, hook chạy lại khi lưu lại, lịch chạy chồng, kéo dữ liệu lần hai) phải cho cùng một kết quả. Mỗi phần việc có ít nhất một test "chạy hai lần → một kết quả". Chi tiết cho Xero: `plan/xero/PLAN.md`, mục "Idempotency"; cho lab: `plan/general/README.md`.

## Hai chỗ kế hoạch này khác AGENTS.md, có chủ đích

Con người chốt ngày 2026-10-12, chỉ cho kế hoạch Xero; `AGENTS.md` chưa được sửa ở hai điểm này:
- **Không viết test** cho demo (AGENTS.md B5 đòi test cho mỗi endpoint).
- **Handler gắn vào ERPNext nằm dưới `overrides/`** (AGENTS.md B2a mục 2 ghi `<domain>/events/`).
