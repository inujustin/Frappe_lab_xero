# Runbook: <tên>

**Dùng khi:** <tình huống>
**Ai chạy:** con người. Agent không bao giờ thực thi runbook.
**Thời gian:** <số phút ước chừng>
**Kiểm chứng lần cuối:** <ngày, bởi ai, trên môi trường nào>

## Trước khi bắt đầu
- [ ] <điều kiện tiên quyết, ví dụ công cụ và phiên bản>
- [ ] <quyền truy cập bạn cần, ví dụ VPN, credential (thông tin đăng nhập) lấy từ trình quản lý mật khẩu>

## Các bước
1. **<bước này làm gì>** (Chạy ở: host | container <tên>)
   ```bash
   <lệnh chính xác kèm <PLACEHOLDER>>
   ```
   Mong đợi: <bạn sẽ thấy gì>

2. ⚠️ CHANGES STATE (LÀM ĐỔI TRẠNG THÁI): **<bước này thay đổi gì>** (Chạy ở: host | container <tên>)
   ```bash
   <lệnh>
   ```
   Mong đợi: <...>
   Rollback (hoàn tác): <lệnh hoặc các bước chính xác>

## Kiểm tra đã thành công
- <phép kiểm tra quan sát được>

## Nếu có gì trục trặc
| Triệu chứng | Nguyên nhân khả dĩ | Cách sửa |
|---|---|---|
| <nội dung lỗi> | <nguyên nhân> | <cách sửa> |
