# Runbook: dựng Frappe lab

**Dùng khi:** cài đặt lần đầu, reset toàn bộ, hoặc hằng ngày để khởi động lab.
**Ai chạy:** bạn. Agent không bao giờ chạy docker hay bench.
**Thời gian:** lần khởi động đầu 20 đến 40 phút (tải về và build); sau đó dưới một phút.
**Kiểm chứng lần cuối:** _chưa_

## Một lệnh
Từ thư mục gốc dự án, luôn luôn như nhau, dù chưa có gì hay đã có đủ mọi thứ:
```bash
docker compose up --build -d
```
Nó chỉ làm những gì còn thiếu:

| Nếu thiếu cái này | `up` làm việc này |
|---|---|
| image, hoặc Dockerfile đã đổi | build nó |
| thư mục `frappe-bench/` | tạo nó, chủ sở hữu là bạn |
| code của Frappe, ERPNext, CRM | tải chúng vào `frappe-bench/apps/` ở các branch ghi trong `docker/versions.env` |
| môi trường Python của container, hoặc package của một app mới | tạo và cài |
| site `lab.localhost`, hoặc database của nó | tạo site |
| một app có trong bench nhưng chưa có trên site | cài nó |
| SPA đã build, hoặc bản build cũ hơn source frontend | `bench build --app lab_core` |

Sau đó nó khởi động Frappe. Tất cả những việc này là `docker/entrypoint.sh`; mỗi dòng nó in ra bắt đầu bằng `[init]`.

```text
xero_demo_other_feat_frappe/            thư mục gốc dự án (host, filesystem của WSL2)
├── compose.yaml                        thứ `docker compose` đọc; trỏ tới docker/
├── docker/  compose.yml  Dockerfile.dev  entrypoint.sh  versions.env  .env
└── frappe-bench/                       cùng một thư mục, cùng đường dẫn tuyệt đối, trên host và trong container
    ├── apps/                           code: đọc và sửa nó trên host
    ├── env/                            rỗng trên host: môi trường Python là một Docker volume
    └── sites/lab.localhost/            site
```

## Trước lần khởi động đầu tiên
- [ ] Docker đang chạy (`docker ps`). Cổng 8000 và 9000 còn trống.
- [ ] ⚠️ CHANGES STATE (LÀM ĐỔI TRẠNG THÁI): `docker/.env` tồn tại (Chạy ở: host, thư mục gốc dự án)
  ```bash
  cp docker/.env.example docker/.env
  ```
  Đặt `MARIADB_ROOT_PASSWORD` và `ADMIN_PASSWORD` thành mật khẩu của riêng bạn. Kiểm tra `HOST_UID`/`HOST_GID` bằng với `id -u`/`id -g`.

## Các bước
1. ⚠️ CHANGES STATE: **Khởi động** (Chạy ở: host, thư mục gốc dự án)
   ```bash
   docker compose up --build -d
   docker compose logs -f frappe
   ```
   Mong đợi: các dòng `[init]` cho những gì còn thiếu, rồi `[init] bench is ready: starting`, rồi web ở cổng 8000 và socketio ở 9000. Ctrl+C dừng việc theo dõi log, không dừng Frappe.
   Rollback (hoàn tác): `docker compose down` (giữ lại mọi thứ).

## Kiểm tra đã thành công
- http://lab.localhost:8000 hiện trang đăng nhập có style; `Administrator` với `ADMIN_PASSWORD` của bạn đăng nhập được; ERPNext và CRM có trong danh sách app.
- Trên host, thêm một dòng trống vào `frappe-bench/apps/frappe/frappe/__init__.py` rồi lưu: log cho thấy tiến trình web reload (nạp lại). Hoàn tác chỉnh sửa đó.

## Hằng ngày
Tất cả trên host, ở thư mục gốc dự án. Bạn không cần vào trong container.

| Nhu cầu | Lệnh |
|---|---|
| khởi động, hoặc áp dụng bất kỳ thay đổi nào ở các file Docker | `docker compose up --build -d` |
| xem log | `docker compose logs -f frappe` |
| dừng (giữ lại mọi thứ) | `docker compose down` |
| restart Frappe (sau khi đổi hook, có app mới, hoặc khi nó treo) | `docker compose restart frappe` |
| migrate (đồng bộ cấu trúc vào database) sau khi đổi DocType, hook hoặc patch | `docker compose exec frappe bench --site lab.localhost migrate` |
| build lại SPA để `/lab` hiện code frontend mới | `docker compose exec frappe bench build --app lab_core` (một lần restart cũng làm việc này khi file frontend đã đổi) |
| làm SPA với refresh tức thì | trên host, trong `frappe-bench/apps/lab_core/frontend/`: `yarn dev`, rồi mở địa chỉ nó in ra |
| gắn một Python debugger | đặt `LAB_DEBUG=1` trong `docker/.env`, `docker compose up -d`; cổng 5678. Ở chế độ này chỉ web server chạy: đặt lại về `0` để có job, realtime và reload |
| chạy test của một module | `docker compose exec frappe bench --site lab.localhost run-tests --module <module>` (được phép vì script khởi động đặt `allow_tests`; công tắc: `LAB_ALLOW_TESTS` trong `docker/.env`) |
| bật lại scheduler (bộ lập lịch) sau một lần chạy test bị crash | `docker compose exec frappe bench --site lab.localhost enable-scheduler` |
| bất kỳ lệnh bench nào khác | `docker compose exec frappe bench <command>` |
| ⚠️ xóa sạch database và môi trường Python, giữ code | `docker compose down -v`, rồi lệnh khởi động |
| ⚠️ xóa sạch mọi thứ, kể cả code | `docker compose down -v --rmi local`, `rm -rf frappe-bench`, rồi lệnh khởi động |

## Nếu có gì trục trặc
| Triệu chứng | Nguyên nhân khả dĩ | Cách sửa |
|---|---|---|
| `frappe` thoát ngay sau khi khởi động | một bước cài đặt thất bại | `docker compose logs frappe`; dòng `[init]` cuối cùng cho biết bước nào và vì sao |
| `[init] ERROR: ... is not set in docker/.env` | thiếu một mật khẩu | thêm nó vào `docker/.env`, khởi động lại |
| `[init] ERROR: apps/frappe exists but the bench is incomplete` | một lần tải trước đó dừng giữa chừng | `docker compose down -v`, `rm -rf frappe-bench`, khởi động lại |
| `[init] ERROR: cannot reach MariaDB as root` | `MARIADB_ROOT_PASSWORD` khác với giá trị lúc volume database được tạo | khôi phục giá trị cũ, hoặc `docker compose down -v` để bắt đầu sạch |
| asset bị 404, `ENOENT` trong log, link trong `sites/assets/` trỏ tới đường dẫn không tồn tại | thư mục dự án đã bị di chuyển | xóa sạch mọi thứ (bảng trên) rồi khởi động lại |
| file trong `frappe-bench/` thuộc sở hữu của root | `HOST_UID`/`HOST_GID` khác với `id -u`/`id -g` | sửa `docker/.env`, `sudo chown -R $(id -u):$(id -g) frappe-bench`, khởi động lại |
| `port is already allocated` | một bench khác đang dùng 8000 hoặc 9000 | đặt `WEB_PORT`/`SOCKETIO_PORT` trong `docker/.env` |
| `env file docker/.env not found` | file env chưa được tạo | xem "Trước lần khởi động đầu tiên" |
| cần một shell trong khi Frappe không chịu khởi động | | `docker compose run --rm frappe bash` (không chạy bước cài đặt nào) |
| lệnh `bench` trên host bị lỗi | do thiết kế: môi trường Python và database của bench nằm trong Docker | dùng `docker compose exec frappe bench ...` |
