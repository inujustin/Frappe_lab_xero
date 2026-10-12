# Sprint: cả kế hoạch trong khoảng hai giờ

Một lượt đi nhanh qua `OVERVIEW.md`: một tính năng nhỏ đi qua gần như mọi cơ chế đúng một lần, vừa xây vừa đọc. Bây giờ lấy bề rộng, sau này mới đào sâu; các track vẫn giữ nguyên để dành khi có thời gian.

## Tính năng
Một Lab Note được tạo trong SPA, lưu qua các endpoint của chính ta, và được "gửi sang Xero" bởi một background job (việc chạy nền) thông qua outbox (hộp thư đi: bảng ghi việc cần gửi ra ngoài). Xero là một client giả nằm trong app, nên không gì phải chờ một tài khoản bên ngoài.

```text
Trang SPA (colada / tanstack)
  │  POST create_note            CSRF, session, permission, một dạng lỗi
  ▼
api/notes.py  →  lab_core/lab_core/notes.py (service)  →  Lab Note        một request = một transaction
                                   │ cùng transaction
                                   ▼
                          dòng Lab Xero Outbox (idempotency key)
                                   │ enqueue sau khi commit
                                   ▼
tasks/xero_sync.py  →  integrations/xero/client.py (giả)                  job, retry, "nó đã tới chưa?"
        │ ghi xero_id, sync_status             │ lỗi theo yêu cầu
        ▼                                      ▼
   SPA poll trạng thái của note           compensation: đánh dấu Failed, giữ dòng outbox
```

## Luật của sprint này (đè lên các thói quen chậm, không đè lên luật an toàn)
- Không hỏi trừ khi thật sự bị chặn: coi các dữ kiện bên dưới là đã quyết, và với thứ gì nhỏ thì dùng câu trả lời bạn khuyến nghị; nói rõ đã dùng cái nào.
- Các stage (chặng) có hướng dẫn của `TRACK-A.md` bị tạm ngưng. Một trace ở đây là **một trang**: câu trả lời trong năm dòng, đường đi dưới dạng hình vẽ bằng text có `path:line`, ba dòng source quan trọng nhất, một thí nghiệm. Ghi vào `docs/traces/<topic>.md`.
- Test: mỗi endpoint một test phân quyền theo role, và một test cho "cùng một idempotency key (khóa chống gửi trùng) gọi hai lần cho ra một Xero id". Hiện chưa cần gì thêm.
- Phần tóm tắt giữ ngắn. Lệnh dành cho con người thì gom vào một script tạm khi có nhiều lệnh (A18).
- A3, A4, A11, B2 (DocType tạo trong Desk), B4 và B9 vẫn giữ nguyên như mọi khi.

## Các dữ kiện mà mọi phiên đều xây dựa vào
**DocType (con người tạo trong Desk trước):**
- `Lab Note` thêm: `sync_status` (Select: Not Synced, Queued, Synced, Failed; mặc định Not Synced; read only), `xero_id` (Data; read only; unique; no copy). Một dòng permission cho role `Lab User`: read, write, create.
- `Lab Xero Outbox` (module Lab Xero): `reference_doctype` (Link → DocType), `reference_name` (Dynamic Link → reference_doctype), `operation` (Data), `idempotency_key` (Data, unique), `status` (Select: Pending, Done, Failed; mặc định Pending), `attempts` (Int), `error` (Small Text), `xero_id` (Data). Các dòng permission: System Manager (tất cả), và `Lab User`: read, write, create. Dòng thứ hai là một lối tắt: dòng outbox được ghi và cập nhật dưới danh nghĩa user đã tạo note, và luật của ta cấm `ignore_permissions`. Một bản ghi thuộc sở hữu hệ thống nên được ghi thế nào là câu hỏi thiết kế còn mở, dành cho track permissions.
- Role `Lab User`, và một user `lab-user@example.test` giữ role đó.

**Endpoint**, tất cả trong `lab_core/api/notes.py`, gọi dưới dạng `/api/method/lab_core.api.notes.<name>`, câu trả lời nằm dưới `message`:

| Hàm | Verb | Tham số | Trả về |
|---|---|---|---|
| `list_notes` | GET | `start: int = 0`, `limit: int = 20` | `{"items": [{"name", "title", "sync_status", "xero_id"}], "has_next": bool}` |
| `get_note` | GET | `name: str` | `{"name", "title", "content", "sync_status", "xero_id"}` |
| `create_note` | POST | `title: str`, `content: str = ""` | `{"name"}`; note bắt đầu ở `Queued` và một dòng outbox đã tồn tại |
| `retry_sync` | POST | `name: str` | `{"queued": true}` |

**Xero giả** (`lab_core/integrations/xero/client.py`): `create_invoice(idempotency_key, payload) -> xero_id` trả về cùng một id cho cùng một key; một note có title chứa `fail` thì bị từ chối; title chứa `timeout` thì raise (ném lỗi) sau khi đã "tới nơi", nên job phải hỏi `find_by_key(idempotency_key)` trước khi retry (thử lại).

**Lỗi:** `lab_core/errors.py` chứa các lớp exception của riêng ta, mỗi lớp kèm HTTP status của nó (đến giờ có `LabConflictError`, 409). Không tìm thấy và không được phép thì dùng `DoesNotExistError` (404) và `PermissionError` (403) của chính Frappe. Endpoint chỉ raise và không catch gì cả.

## Đang ở đâu và tiếp theo là gì
```text
DONE (đã viết, chưa chạy)  Backend: endpoint, use case, controller, outbox, job, Xero giả, 8 test
DONE                       Học: sáu cơ chế trong docs/traces/cram-sheet.md

NEXT (tiếp theo), làm cùng lúc:
  Bạn    1. Desk: role Lab User, user, hai field + dòng permission trên Lab Note, DocType Lab Xero Outbox
         2. chạy test (lệnh bên dưới); dán các lỗi cho phiên backend
         3. tạo một note trong Desk, xem nó đi từ Queued → Synced
  Codex  F1  danh sách note và form tạo trên trang colada và trên trang tanstack (chỉ trong frontend/);
             CSRF token cho POST theo cách trang của CRM làm
         F2  trạng thái bằng polling (hỏi lại định kỳ), nút retry; năm dòng về việc hai thư viện khác nhau thế nào

THEN (sau đó), nếu còn thời gian:
  B3  một thay đổi hành vi ERPNext qua overrides/ (một document event trên Customer); đụng tới hooks.py
```
F1 chỉ cần bảng endpoint ở trên, nên nó bắt đầu ngay, trong lúc bạn làm phần Desk. Sửa backend và frontend không bao giờ đụng cùng một file. B3 là bước duy nhất sửa `hooks.py`, và sau đó cần restart.

Test, chạy trên host từ thư mục gốc dự án (chạy bên trong container Frappe; tạo hai user test trên site nếu chưa có):
```bash
docker compose exec frappe bench --site lab.localhost run-tests --module lab_core.api.test_notes
```

## Để ngoài hai giờ này
Xero OAuth và API thật, đăng nhập Google, Telegram, file và object storage, email và Jinja, OpenTelemetry, SAGA dựa trên broker, structural lint, kiểm tra schema drift (lệch cấu trúc giữa code và database), phần so sánh thư viện bốn kịch bản, response envelope (vỏ bọc phản hồi) dùng chung, và mọi thứ `TRACK-A.md` còn liệt kê là mở. Mỗi thứ vẫn nằm trong `OVERVIEW.md` để làm sau.

## Xong khi
Một note gõ ở một trong hai trang SPA xuất hiện trong danh sách với `Queued` và chuyển thành `Synced` kèm một Xero id; một note `fail` chuyển thành `Failed` và `retry_sync` chạy được sau khi đổi tên nó; một note `timeout` kết thúc với đúng một Xero id; user không có role thì bị từ chối; hai test pass; có sáu bản một-trang và con người đã đọc chúng.
