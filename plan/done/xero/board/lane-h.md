# Làn H: con người (P0 và các lần chạy demo)

Agent chỉ đọc file này để biết môi trường đã sẵn sàng tới đâu. Con người tự đổi trạng thái.

Nguyên tắc: **cấu hình nằm trong code**. Việc của con người chỉ còn là những thứ code không làm được: tạo DocType trong Desk, thao tác trên trang của Xero, giữ bí mật, bấm đồng ý một lần, và chạy lệnh.

| Bước | Việc | Trạng thái |
|---|---|---|
| H1 | Login Xero, mở Demo Company, ghi lại quốc gia và tiền tệ | TODO |
| H2 | Tạo app loại Web app tại `developer.xero.com`; Redirect URI là chuỗi cố định mà làn B ghi ra ở bước B0. Giữ `client_id` và `client_secret` ở chỗ riêng, không dán vào chat hay repo | TODO |
| H3 | Desk: tạo ba DocType `Lab Xero Outbox`, `Lab Xero Settings`, `Lab Xero Credit Note` (field ở `plan/done/xero/PLAN.md`, "Dữ kiện chung"). **Việc duy nhất phải làm trong Desk** | TODO |
| H4 | Sau B0, và sau khi làn A đã áp dòng hook `after_migrate` của làn B vào `hooks.py` (bảo làn A làm, hoặc tự dán): chạy các lệnh làn B đưa (đặt `client_id`, `client_secret`, mã tài khoản doanh thu, mã thuế vào site config), rồi migrate. Code tự tạo Connected App và điền Settings | TODO |
| H5 | Mở Connected App `xero` trong Desk, bấm Connect, đăng nhập Xero, chọn Demo Company, đồng ý. Đây là lần duy nhất có người đăng nhập Xero | TODO |
| H6 | ERPNext: một Company cùng tiền tệ với Demo Company, một Customer, một Item; tạo thử một Sales Order không thuế, không chiết khấu | TODO |
| H7 | Chạy DEMO 1 | TODO |
| H8 | Sau C3 và khi làn A đã áp dòng hook: migrate; chạy DEMO 2 và DEMO 3 | TODO |

Ghi chú của con người (kết quả H5: Xero có nhận redirect URI không, Frappe có đổi được token không; quốc gia và tiền tệ của Demo Company):
