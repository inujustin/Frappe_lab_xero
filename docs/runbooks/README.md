# Runbooks

Các hướng dẫn (runbook: tài liệu thao tác từng bước) mà **con người** tự tay chạy. Agent viết và cập nhật chúng nhưng không bao giờ thực thi.
Mọi thứ thuộc DevOps, database hoặc git nằm ở đây dưới dạng hướng dẫn, không phải việc agent làm.

| Runbook | Dùng khi nào | Lần cuối con người kiểm chứng |
|---|---|---|
| [add-dependency.md](add-dependency.md) | Một agent nói "Needs package" (cần package) | _chưa_ |
| [dev-environment.md](dev-environment.md) | Khởi động lab, lần đầu hoặc hằng ngày: `docker compose up --build -d` | _chưa_ |
| [build-tools.md](build-tools.md) | Công cụ build trên host/container, output và tác động lên database | _chưa_ |
| [new-apps.md](new-apps.md) | Tạo custom app duy nhất `lab_core`, gỡ một app lạc loài, thêm một module | một phần, 2026-10-09 |
| [install-frappe-skills.md](install-frappe-skills.md) | Cài đặt hoặc cập nhật các skill Frappe chính thức | _chưa_ |
