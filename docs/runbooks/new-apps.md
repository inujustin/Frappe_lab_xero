# Runbook: custom app duy nhất, `lab_core`

**Dùng khi:** lab đã chạy và `lab_core` cần được tạo hoặc đưa lên site.
**Ai chạy:** bạn. Agent không bao giờ chạy docker hay bench.
**Thời gian:** vài phút.
**Kiểm chứng lần cuối:** `bench new-app` qua `docker compose exec` đã chạy được ngày 2026-10-09; phần còn lại thì chưa.

Mọi thứ được xây trong một app duy nhất này (`plan/general/OVERVIEW.md`, "One app"). Mọi lệnh đều gõ trên host, ở thư mục gốc dự án.

## Các bước
1. ⚠️ CHANGES STATE (LÀM ĐỔI TRẠNG THÁI): **Tạo app** (bỏ qua nếu `frappe-bench/apps/lab_core` đã tồn tại)
   ```bash
   docker compose exec frappe bench new-app --no-git lab_core
   ```
   Chấp nhận các giá trị mặc định; trả lời **no** cho GitHub workflow. Không nhập secret (thông tin bí mật).
   Rollback (hoàn tác): `docker compose exec frappe bench remove-app lab_core` (xóa thư mục).

2. ⚠️ CHANGES STATE: **Gỡ một app tạo nhầm** (ví dụ `lab_spa`)
   ```bash
   docker compose exec frappe bench remove-app <APP_NAME>
   ```
   Mong đợi: thư mục của nó biến mất khỏi `frappe-bench/apps/` và dòng của nó biến mất khỏi `frappe-bench/sites/apps.txt`.
   Nếu bench nói app đang được cài trên một site, hãy uninstall nó trước: `docker compose exec frappe bench --site lab.localhost uninstall-app <APP_NAME>` (lệnh này xóa dữ liệu của app đó).

3. ⚠️ CHANGES STATE: **Restart: việc này cài `lab_core` lên site**
   ```bash
   docker compose restart frappe
   docker compose logs -f frappe
   ```
   Mong đợi: `[init] installing app lab_core on lab.localhost`, rồi `[init] bench is ready: starting`. Script khởi động cài mọi app của bench chưa có trên site, nên hãy gỡ các app không mong muốn (bước 2) trước khi restart.

4. **Xác nhận**
   ```bash
   docker compose exec frappe bench --site lab.localhost list-apps
   ```
   Mong đợi: `frappe`, `erpnext`, `crm`, `lab_core`.

## Thêm một domain về sau
Một domain (miền nghiệp vụ) là một module của Frappe, không phải một app. Trong Desk (developer mode): **Module Def → New**, app `lab_core`, ví dụ "Lab Xero". Thư mục của nó xuất hiện dưới `frappe-bench/apps/lab_core/lab_core/`.

## Nếu có gì trục trặc
| Triệu chứng | Nguyên nhân khả dĩ | Cách sửa |
|---|---|---|
| `bench remove-app` từ chối | app đang được cài trên site | uninstall nó khỏi site trước (bước 2) |
| `lab_core` không có trong `list-apps` | lần restart bị bỏ qua hoặc thất bại | đọc các dòng `[init]` trong `docker compose logs frappe` |
| `frappe` thoát sau khi restart | một bước khởi động thất bại | dòng `[init]` cuối cùng nêu tên nó; shell không chạy khởi động: `docker compose run --rm frappe bash` |
