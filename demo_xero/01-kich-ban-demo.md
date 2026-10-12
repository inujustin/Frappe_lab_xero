# 01. Kịch bản demo: một mạch, khoảng 15 phút

Một user (Administrator), một địa chỉ (`http://localhost:8000`), hai tab (Frappe và Xero). Phần kỹ thuật phía sau: `13`.

## Cả buổi trong một hình

```text
 ① Đăng nhập ─► ② Nối Xero ─► ③ Tạo đơn A, Submit ─► ④ Xem hóa đơn bên Xero ─► ⑤ Xem số liệu quay về Frappe
                                                                                        │
                                                                                        ▼
 ⑨ Credit note bên Xero ◄── ⑧ Trả tiền bên Xero ◄── ⑦ Đổi tên khách ◄── ⑥ Đơn B, cùng khách
    → về đơn B                 → về đơn A               (giới hạn)          (một khách, hai hóa đơn)
```

## Trước khi người xem vào

- Mở Frappe bằng `http://localhost:8000/desk`, đăng nhập Administrator.
- Mở tab Xero: Demo Company (Global) → Invoices.
- Mở **Lab Xero Settings**: `Tenant Name` có giá trị, `Last Pull At` vừa mới đây.
- Có sẵn một khách và một mặt hàng có giá niêm yết.

## Các bước

| # | Làm | Thấy | Ý nghĩa |
|---|---|---|---|
| **① Đăng nhập** | | | |
| 1 | Chỉ vào tên user ở góc phải | Administrator | Người dùng Frappe không cần tài khoản Xero |
| **② Nối Xero** | | | |
| 2 | Tìm **Connected App** → mở `xero` → bấm **Connect to Xero** (một lần) | tab mới: trang của Xero | Frappe gửi tôi sang Xero để xin phép |
| 3 | Chọn **Demo Company (Global)** → **Allow access** | quay về Frappe | Tôi đồng ý tại Xero; mật khẩu Xero không đi qua Frappe |
| **③ Tạo đơn A** | | | |
| 4 | **Sales Order → New**: chọn khách, ngày giao, mặt hàng, số lượng 2. Không sửa giá, không thêm thuế. **Save** | phần **Xero**: `Not Synced` | Đơn nháp không sang Xero |
| 5 | **Submit** | `Queued` | Đơn được lưu ngay; việc gửi sang Xero chạy ở nền |
| 6 | Chờ 5 giây, tải lại | `Synced`, `AUTHORISED`, `Xero Amount Due` = tổng đơn | Hóa đơn đã có bên Xero |
| **④ Xem bên Xero** | | | |
| 7 | Tab Xero → Invoices → **Awaiting Payment** → mở hóa đơn mới | số hóa đơn = số đơn; đúng khách, đúng hàng | Số đơn là chiếc khóa nối hai bên |
| **⑤ Xem số liệu quay về** | | | |
| 8 | Frappe: mở khách của đơn | có `Xero Contact ID` | Khách được tạo bên Xero ở đơn đầu tiên |
| 9 | Mở danh sách **Lab Xero Outbox** | một dòng `Done` | Sổ ghi việc đã gửi |
| **⑥ Đơn B, cùng khách** | | | |
| 10 | Tạo đơn thứ hai cho **cùng khách**, Submit, chờ, tải lại | `Synced`; `Xero Contact ID` của khách không đổi | Một khách, nhiều hóa đơn; không tạo khách trùng |
| **⑦ Đổi tên khách** | | | |
| 11 | Trên khách: sửa ô **Customer Name** → **Save**. Không bấm vào tiêu đề để Rename | lưu được | — |
| 12 | Tab Xero → Contacts → mở khách đó | tên **vẫn là tên cũ** | Giới hạn đã biết: đổi tên chưa được đẩy sang Xero |
| **⑧ Trả tiền bên Xero** | | | |
| 13 | Xero: hóa đơn của đơn A → **Receive a payment** đủ số tiền → **Add Payment** | hóa đơn **Paid** | Việc của kế toán, làm trong Xero |
| 14 | Frappe: đơn A → **Xero → Refresh from Xero** → chờ form tải lại | `PAID`, `Xero Amount Due` = 0 | Frappe hỏi Xero và chép lại; không bấm thì khoảng 5 phút tự cập nhật |
| 15 | Thử **Cancel** đơn A | bị chặn, có lý do | Hóa đơn đã có tiền thì không hủy đơn được |
| **⑨ Credit note bên Xero** | | | |
| 16 | Xero: hóa đơn của đơn B → **Add Credit Note** một phần số tiền → **Approve** → **Allocate** vào hóa đơn này | số còn nợ của hóa đơn giảm | Kế toán ghi giảm công nợ |
| 17 | Frappe: đơn B → **Refresh from Xero** → chờ | `Xero Amount Credited` có số; `Xero Amount Due` giảm | Số trên đơn là số của Xero |
| 18 | Kéo xuống cuối đơn B; mở danh sách **Lab Xero Credit Note** | một dòng ghi chú trên đơn; một bản ghi credit note | Có dấu vết ngay trong Frappe |
| 19 | Bấm **Refresh from Xero** lần nữa | vẫn một dòng, một bản ghi | Hỏi lại bao nhiêu lần cũng không sinh trùng |

## Nếu vấp

| Thấy | Làm |
|---|---|
| Đơn vẫn `Queued` sau 10 giây | bấm **Xero → Retry** |
| Đơn `Failed` | đọc to ô `Xero Error`, rồi tạo đơn mới đúng luật: giá niêm yết, không thuế |
| Lỗi khi Connect | bấm **Connect to Xero** lại, đúng một lần |

## Ba câu để kết

1. "Đơn hàng thuộc ERPNext, hóa đơn thuộc Xero; mỗi con số chỉ có một chủ."
2. "Gửi đi thì ghi sổ trước rồi mới gửi; nhận về thì hỏi định kỳ và chép lại."
3. "Chi phí là 0: Demo Company và bậc API miễn phí."

## Lưu ý

- Bước 1–10 đã chạy thật. Bước 11–19 **chưa chạy thật**, và tên nút bên Xero viết từ trí nhớ: tập trọn bảng một lần trước buổi demo.
- Sau lần tập, dùng **khách mới và đơn mới** cho buổi thật: hóa đơn đã trả thì không trả lại được.
- Không mở Error Log trước người xem.
