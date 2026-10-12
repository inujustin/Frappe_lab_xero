# Kịch bản demo: Sales Order ↔ Xero

Ba cảnh, khoảng mười phút. Kế hoạch: `plan/xero/PLAN.md`. Bản nghiên cứu đi kèm: `BAO-CAO.md`.

**Mức xác nhận:** viết ngày 2026-10-12 từ code và kế hoạch, **trước khi demo được chạy thật**. Kết nối Xero đã thử thành công; ba cảnh dưới đây thì chưa. Sau lần chạy thật đầu tiên, sửa lại file này theo những gì thực sự xảy ra (bước W3). Các chỗ chưa chắc được đánh dấu **(chưa thử)**.

## Một câu để mở đầu

"Người bán hàng làm việc trong ERPNext và không có tài khoản Xero. Kế toán làm việc trong Xero. Hai bên thấy cùng một hóa đơn, và mỗi con số chỉ có một nơi là thật: đơn hàng ở ERPNext, hóa đơn ở Xero."

## Chuẩn bị trước buổi demo (không làm trước mặt người xem)

| # | Việc | Kiểm tra |
|---|---|---|
| 1 | Hệ thống đang chạy; mở `http://localhost:8000/desk` (đúng `localhost`), đăng nhập | vào được Desk |
| 2 | Kết nối Xero còn sống: mở Connected App `xero`; nếu đã lâu không dùng hoặc Demo Company vừa reset thì bấm Connect lại | quay về Frappe không lỗi |
| 3 | `Lab Xero Settings` có đủ: connected app, connected user, tenant id, mã tài khoản `200`, mã thuế `NONE` | mở form xem |
| 4 | Có một Customer, một Item, và **hai** Sales Order nháp: không thuế, không chiết khấu, cùng tiền tệ với Demo Company | hai đơn ở trạng thái Draft |
| 5 | Mở sẵn hai tab: ERPNext (danh sách Sales Order) và Xero (Demo Company → Business → Invoices) | |
| 6 | Tên Customer chưa trùng contact nào trong Demo Company | tìm trong Xero → Contacts |

Vì sao hai đơn: đơn A cho cảnh 1 và 2 (sẽ được trả tiền), đơn B cho cảnh 3 (sẽ nhận credit note). Một hóa đơn đã trả đủ thì không còn gì để ghi giảm.

Hạn mức: mỗi lần bấm là một vài lời gọi vào Xero; bậc miễn phí cho 1000 lời gọi mỗi ngày (`01`). Tập dượt thoải mái, nhưng đừng để một vòng lặp chạy qua đêm.

## Cảnh 1: đơn hàng thành hóa đơn bên Xero (DEMO 1)

| Bước | Bấm | Nhìn ở đâu | Nói |
|---|---|---|---|
| 1 | ERPNext: mở Sales Order A, chỉ vào phần **Xero** trên form | `Xero Sync Status` = `Not Synced`, các ô khác trống | "Đơn này chưa từng sang Xero." |
| 2 | Bấm **Submit** | trạng thái đổi thành `Queued` | "Lúc submit, ERPNext không gọi Xero. Nó chỉ ghi lại một việc cần làm, cùng lúc với việc lưu đơn. Người dùng không phải chờ." |
| 3 | Chờ vài giây, tải lại form | `Synced`; có `Xero Invoice ID`, `Xero Invoice Number` (bằng tên đơn), `Xero Invoice Status` = `AUTHORISED` | "Một tác vụ nền đã gửi nó đi. Trước khi tạo, nó hỏi Xero xem hóa đơn mang số này đã có chưa." |
| 4 | Tab Xero: tải lại danh sách Invoices, mở hóa đơn mới | đúng khách, đúng dòng hàng, số hóa đơn là tên Sales Order | "Khách hàng cũng được tạo bên Xero ở lần đầu. Thuế do Xero tính; ở demo là 0%." |
| 5 | ERPNext: nhóm nút **Xero** → không còn nút Retry | | "Đã sang rồi thì không gửi lại được: một đơn, một hóa đơn." |

Nếu trạng thái là `Failed`: đọc ô `Xero Error` (lý do của Xero, nguyên văn), sửa nguyên nhân, rồi bấm **Xero → Retry**. Đây cũng là một cảnh đáng cho xem nếu còn giờ: "không gì hỏng trong im lặng".

## Cảnh 2: kế toán nhận tiền, ERPNext biết (DEMO 2)

| Bước | Bấm | Nhìn ở đâu | Nói |
|---|---|---|---|
| 1 | Tab Xero: trong hóa đơn của đơn A, phần **Receive a payment**: nhập đủ số tiền, chọn tài khoản ngân hàng, **Add Payment** | hóa đơn chuyển sang **Paid** | "Việc này do kế toán làm, trong Xero. ERPNext không ghi payment." |
| 2 | ERPNext: Sales Order A → **Xero → Refresh from Xero** | sau vài giây form tải lại: `Xero Invoice Status` = `PAID`, `Xero Amount Paid` = tổng, `Xero Amount Due` = 0 | "ERPNext hỏi Xero và chép lại đúng con số của Xero, không tự tính. Không bấm nút thì cứ năm phút hệ thống cũng tự hỏi." |
| 3 | Thử **Cancel** đơn A | bị chặn, có thông báo nêu lý do | "Hóa đơn đã có tiền trả thì không hủy đơn được: ta không tự gỡ tiền của kế toán." **(chưa thử)** |

Vì sao là "hỏi" chứ không phải "được báo": Xero có thể chủ động báo (webhook), nhưng cần một địa chỉ công khai trên internet; bản demo chạy trên máy cá nhân nên dùng cách hỏi định kỳ (`knowledge/webhook.md`).

## Cảnh 3: credit note bên Xero hiện lên đơn hàng (DEMO 3)

Làm trước: submit Sales Order B và chờ nó `Synced`, như cảnh 1.

| Bước | Bấm | Nhìn ở đâu | Nói |
|---|---|---|---|
| 1 | Tab Xero: mở hóa đơn của đơn B → **Options → Add Credit Note**; giữ một phần số tiền (ví dụ một nửa), **Approve** | Xero hỏi áp credit vào đâu; chọn chính hóa đơn này, **Allocate Credit** | "Kế toán ghi giảm công nợ cho khách, ngay trên hóa đơn." **(đường menu chưa thử)** |
| 2 | ERPNext: Sales Order B → **Xero → Refresh from Xero** | `Xero Amount Credited` = số đã ghi giảm; `Xero Amount Due` giảm tương ứng | "Số còn nợ trên đơn là số của Xero sau khi trừ credit." |
| 3 | Kéo xuống timeline của đơn | một dòng: "Xero credit note … allocated to this order's invoice." | "Có dấu vết ngay trên đơn, không cần mở Xero." |
| 4 | Mở danh sách **Lab Xero Credit Note** | một dòng trỏ về Sales Order B: số credit note, ngày, tổng, số đã áp | "Mỗi credit note là một bản ghi, tìm lại được." |
| 5 | Bấm **Refresh from Xero** lần nữa | vẫn một dòng credit note, vẫn một dòng timeline | "Hỏi lại bao nhiêu lần cũng không sinh dữ liệu trùng." |

Điều nên nói thẳng: "ảnh hưởng" của credit note ở demo này là **hiển thị**. Nó không tự sửa tổng tiền hay trạng thái của Sales Order, và không tạo chứng từ trong ERPNext. Đó là lựa chọn có chủ đích; dự án thật có thể chọn khác (`BAO-CAO.md`).

## Ba câu để kết

1. "Đơn hàng thuộc về ERPNext, hóa đơn thuộc về Xero; mỗi con số chỉ có một chủ."
2. "Gửi đi thì ghi sổ trước rồi mới gửi; nhận về thì hỏi định kỳ và chép lại. Cả hai chiều chạy lại bao nhiêu lần cũng ra một kết quả."
3. "Chi phí của bản demo là 0: Demo Company và bậc API miễn phí."

## Nếu có sự cố khi đang demo

| Thấy | Nghĩa là | Làm |
|---|---|---|
| Đơn đứng mãi ở `Queued` | tác vụ nền chưa chạy hoặc đã hỏng | mở danh sách **Lab Xero Outbox** xem dòng của đơn; xem **Error Log**; bấm **Xero → Retry** |
| `Failed`, lỗi nói về kết nối hoặc quyền | token hết hạn hoặc kết nối bị gỡ | Connected App `xero` → Connect lại, rồi Retry |
| `Failed`, lỗi là câu của Xero về tài khoản, thuế, khách | dữ liệu gửi đi bị Xero từ chối | sửa đúng thứ được nêu, rồi Retry |
| Refresh không đổi gì | Xero chưa có thay đổi, hoặc tác vụ kéo về hỏng | xem **Error Log**; chờ vài giây rồi tải lại form |
| Không thấy nhóm nút **Xero** | đơn còn là nháp, hoặc file JS của form chưa được nạp | submit đơn; tải lại trang bằng Ctrl+Shift+R |
| Xero báo trùng tên contact | Customer trùng tên một contact có sẵn | đổi tên Customer, dùng đơn khác |

## Những gì demo này cố ý không cho xem

Nhiều tiền tệ; thuế và chiết khấu từ ERPNext; một đơn nhiều hóa đơn; credit note chưa áp vào hóa đơn; ghi payment từ ERPNext; webhook; nhiều tổ chức Xero. Mỗi thứ là một quyết định của dự án thật, đã ghi trong `BAO-CAO.md`.
