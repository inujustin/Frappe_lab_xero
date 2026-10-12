# Công cụ build: chạy ở đâu, ảnh hưởng gì

**Dùng khi:** phân biệt build Docker, build giao diện, migrate và restart.
**Ai chạy:** con người; tài liệu này không thực thi lệnh.
**Thời gian:** đọc khoảng 3 phút; thời gian build tùy máy.
**Kiểm chứng lần cuối:** đối chiếu source; chưa chạy kiểm chứng.

## Trước khi bắt đầu

- Lệnh Docker gõ trên host, từ thư mục gốc dự án. `docker compose exec frappe ...` chạy phần sau `frappe` trong container.
- Python và Bench dùng môi trường trong container. Làm frontend trực tiếp trên host tại `frappe-bench/apps/lab_core/frontend/`, với Node major **24** (`docker/versions.env:13`).
- Hướng dẫn khởi động/dừng nằm ở [dev-environment.md](dev-environment.md).

## Bức tranh

```text
Host: Docker Compose
  → Dockerfile: tạo image chứa Python + Node + Yarn + Bench
  → container frappe: entrypoint chuẩn bị bench/site → bench start
      ├─ Python: chạy backend
      ├─ Bench build → đóng gói JS/CSS + gọi build của app
      │   └─ lab_core: Yarn → Vite → file giao diện /lab
      └─ Bench migrate → đồng bộ site/database

Host: Yarn → Vite → cùng thư mục output của /lab
MariaDB: dữ liệu; Redis: cache và hàng đợi job
Xero: dịch vụ bên ngoài, không được build trong Docker này
```

## Chọn thao tác (không phải chuỗi lệnh phải chạy hết)

| Công cụ / thao tác | Chạy ở đâu | Ảnh hưởng |
|---|---|---|
| Docker image build | Docker, gọi từ host | Tạo image chứa Python 3.14, Node 24, Yarn và Bench 5.31.0; không phải migrate site (`docker/Dockerfile.dev:5–29`, `docker/versions.env:12–19`). |
| Compose up | Host, gốc dự án | ⚠️ CHANGES STATE: tạo/khởi động dịch vụ. Entrypoint có thể tải code, cài package, tạo site/database và cài app còn thiếu; có thể build giao diện (`docker/entrypoint.sh:20–107`). Dừng bằng Compose down giữ volume; không hoàn tác dữ liệu đã tạo. |
| Restart `frappe` | Host, gọi vào container | ⚠️ CHANGES STATE: khởi động lại tiến trình và chạy lại entrypoint. Có thể build SPA nếu output thiếu hoặc source mới hơn; **không có migrate tự động** trong entrypoint (`docker/entrypoint.sh:100–122`). Restart không hoàn tác database. |
| Bench build | Container `frappe` | ⚠️ CHANGES STATE: đóng gói JS/CSS và translations (`frappe-bench/apps/frappe/frappe/commands/utils.py:51–110`). Với `lab_core`, script còn chạy **yarn install** rồi Vite build (`frappe-bench/apps/lab_core/package.json:7`). Vì vậy không chỉ biên dịch file. Hoàn tác output bằng build lại source đã khôi phục. |
| Yarn build → Vite | Host, thư mục frontend | ⚠️ CHANGES STATE: tạo file ở `lab_core/public/frontend/`, thay output cũ, copy entry HTML sang `lab_core/www/lab.html`; không migrate database (`frappe-bench/apps/lab_core/frontend/vite.config.mjs:6–25`). Hoàn tác bằng build lại source đã khôi phục. |
| Yarn dev → Vite | Host, thư mục frontend | ⚠️ CHANGES STATE: mở dev server ở `127.0.0.1:5173`, proxy API tới cổng 8000; không tạo bản build để phục vụ `/lab` (`frappe-bench/apps/lab_core/frontend/vite.config.mjs:27–36`). Ctrl+C dừng dev server. |
| Bench migrate | Container `frappe` | ⚠️ CHANGES STATE: thay đổi site/database theo schema, patch và cấu hình app; không thay thế build giao diện (`frappe-bench/apps/frappe/frappe/commands/site.py:712–726`). Không có hoàn tác chung; cần quy trình khôi phục phù hợp. |

## Các bước cho tình huống thường gặp

**Sau khi đổi Dockerfile hoặc cấu hình Compose:** chạy trên host, từ gốc dự án:

```bash
docker compose up --build -d
```

⚠️ CHANGES STATE: build image và khởi động/cập nhật dịch vụ; entrypoint có các tác động trong bảng trên. Mong đợi: log tới `bench is ready: starting`, rồi Desk mở được. Dừng bằng `docker compose down`; dữ liệu đã tạo vẫn còn.

**Sau khi đổi schema/patch của site:** gõ trên host, từ gốc dự án; Bench chạy trong container `frappe`:

```bash
docker compose exec frappe bench --site lab.localhost migrate
```

⚠️ CHANGES STATE: đồng bộ site/database. Mong đợi: migrate hoàn tất không lỗi. Không có lệnh undo chung. Dùng tên site thực tế nếu khác mặc định `lab.localhost` (`docker/compose.yml:39`).

## Kiểm tra đã thành công / nếu có trục trặc

- Build image thành công chưa chứng minh site đã migrate hoặc kết nối Xero đã hoạt động.
- Output `/lab` mới chưa chứng minh Desk assets đã được build; hai phần đi qua các công đoạn khác nhau.
- Debug mode chỉ chạy web, không worker/scheduler: không phù hợp để chạy demo job Xero (`docker/entrypoint.sh:111–120`).
- Nếu khởi động lỗi, dùng mục xử lý sự cố trong [dev-environment.md](dev-environment.md#nếu-có-gì-trục-trặc).
