# 12. Log và lịch sử phía Xero: có gì, lấy bằng cách nào

Viết ngày 2026-10-13. **Trả lời ngắn:** chưa tìm thấy API công khai để kéo "log server" nội bộ của Xero. Có năm thứ gần với "log", mỗi thứ ở một chỗ khác; muốn có nhật ký đầy đủ thì **app tự ghi lấy**.

**Kiểm tra ngày 2026-10-13 (Asia/Bangkok), qua kết quả tìm kiếm tài liệu chính thức:**

```text
Xero bị sự cố?          → trang API Status
Một hóa đơn đã đổi gì?  → Invoice History API
App gọi Xero bị lỗi gì? → tự ghi response trong Frappe
Log server nội bộ Xero? → chưa tìm thấy API công khai
```

- [API Status](https://status.developer.xero.com/) công bố tình trạng dịch vụ; không phải log riêng của app.
- [Invoices](https://developer.xero.com/documentation/api/accounting/invoices) có đường dẫn `GET /Invoices/{InvoiceID}/History`; không phải log thực thi server.
- [Requests and Responses](https://developer.xero.com/documentation/api/accounting/requests-and-responses/) có hướng dẫn debug và ghi validation warning từ response.

Chưa kiểm tra trực tiếp trang Logs trong tài khoản của ta, nên chưa xác nhận khả năng tải/xuất log. "Chưa tìm thấy" không khẳng định API đó không tồn tại. Xero có thể thay đổi: kiểm tra lại các nguồn trên trước khi thiết kế hệ thống gom log.

Mức xác nhận. Các trang tài liệu chính thức của Xero không đọc được nội dung bằng công cụ (trang trả về chỉ có tiêu đề), nên:

| Nhãn | Nghĩa |
|---|---|
| **[K]** | lấy từ kết quả tìm kiếm trích trang của Xero (developer.xero.com, devblog.xero.com); chưa đọc trọn trang |
| **[3]** | chỉ có nguồn bên thứ ba, các nguồn không khớp nhau hoàn toàn |
| **[C]** | đọc từ code của ta |

## Bản đồ

```text
 "Log" bạn cần                         Nằm ở đâu                                   Lấy bằng
 ───────────────────────────────────   ─────────────────────────────────────────   ─────────────────────
 ① App của ta đã gọi Xero những gì     developer.xero.com → app → Logs / Usage      xem trên web (không API)
 ② Ai đã đổi gì trên MỘT hóa đơn        Xero API: History and Notes                  GET …/Invoices/{id}/History
 ③ Cái gì đã đổi kể từ lúc T            Xero API: If-Modified-Since                  ĐÃ LÀM (tasks/xero_pull.py)
 ④ Xero báo ngay khi có thay đổi        webhook                                      cần URL công khai → lab không có
 ⑤ Nhật ký đầy đủ mọi lời gọi của ta    database Frappe                              ta tự ghi (Outbox, Error Log)
```

## ① Trang Logs và Usage của developer portal

- **[K]** Trong Developer Centre, mở app, có tab **History**; mục Metrics cho chọn khoảng thời gian để xem hoạt động API của app, gồm cả những lần chạm giới hạn tần suất. Một bài blog của Xero ghi trang này "sắp đổi tên thành Logs" và hiện rate-limit hit, connection usage, các lời gọi gần đây.
- **[K]** Trang **Usage** hiện lượng dùng API theo ngày và theo tháng.
- Ảnh chụp ngày 2026-10-12 của app ta cho thấy menu đã có **Logs** và **Usage** (tức việc đổi tên đã xong với app này).
- **Chưa xác nhận:** trang Logs có hiện từng request kèm thời điểm hay không; có xuất ra file được không. Không tìm thấy API nào để kéo dữ liệu này.
- **[K]** Xero nói rõ họ không cung cấp danh sách "lần dùng cuối" theo từng tổ chức, và gợi ý app tự ghi các lời gọi thành công của mình.

Việc cho con người (2 phút): mở developer.xero.com → app → Logs, xem nó hiện những cột gì, rồi ghi lại vào đây.

## ② Lịch sử của một bản ghi (History and Notes)

- **[3]** `GET https://api.xero.com/api.xro/2.0/Invoices/{InvoiceID}/History` trả về mảng `HistoryRecords`; mỗi phần tử có `Changes`, `DateUTC`, `User`, `Details`. Cùng kiểu đường dẫn có cho các loại khác (contact, credit note, payment…).
- **[3]** `PUT` vào cùng đường dẫn để **thêm một ghi chú** vào lịch sử; tên field trong body chưa xác nhận.
- Đây là thứ duy nhất trả lời được "ai bên Xero đã sửa hóa đơn này, lúc nào".
- **[C]** Code của ta chưa gọi endpoint này. Scope cần: chưa xác nhận (nhiều khả năng cùng scope với loại bản ghi, tức `accounting.invoices`).
- Trang chính thức: https://developer.xero.com/documentation/api/accounting/historyandnotes (chưa đọc được nội dung).

## ③ Cái đã đổi kể từ lần hỏi trước (đang dùng)

**[C]** `tasks/xero_pull.py` gửi header `If-Modified-Since` để chỉ lấy invoice và credit note đã đổi, mỗi lượt scheduler. Đây không phải log (không nói ai đổi, đổi gì), chỉ là "bản ghi này vừa đổi, đây là trạng thái mới". Chi tiết: `demo_xero/03`, lời gọi 7 và 8.

## ④ Webhook

Xero chủ động báo từng thay đổi. Cần URL https công khai, lab không có: `knowledge/webhook.md`.

## ⑤ Nhật ký của chính ta (đã có, và là thứ Xero khuyên)

| Ghi gì | Ở đâu | Thiếu gì |
|---|---|---|
| mỗi việc gửi đi: loại việc, trạng thái, số lần thử, lỗi, id bên Xero | `Lab Xero Outbox` | không ghi từng request HTTP |
| lỗi hiện cho người dùng | field `Xero Error` trên Sales Order | — |
| lỗi của job, kèm traceback | `Error Log` | có thể chứa secret: không dán ra ngoài |
| lần kéo gần nhất | `Lab Xero Settings.last_pull_at`; `Xero Last Synced At` trên đơn | không ghi mỗi lượt kéo lấy được gì |

Chỗ hở thật: **không có nhật ký từng lời gọi HTTP sang Xero** (thời điểm, method, đường dẫn, mã trả về, thời gian chạy). Muốn có thì thêm ở một chỗ duy nhất, `integrations/xero/client.py: _request`, ghi ra logger của Frappe (không ghi header `Authorization`, không ghi body chứa dữ liệu khách). Việc này thuộc track A2/L của kế hoạch chung.

## Header giới hạn tần suất

Xero trả số lời gọi còn lại trong header của mỗi response. Tên header chưa xác nhận trong phiên này (trang tài liệu không đọc được): https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits

## Nguồn

- https://developer.xero.com/faq
- https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits
- https://developer.xero.com/documentation/best-practices/managing-connections/identifying-inactive-connections
- https://devblog.xero.com/webinar-recap-api-optimisation-and-managing-connections-5e50fed63063
- https://developer.xero.com/documentation/api/accounting/historyandnotes
- bên thứ ba, cho mục ②: https://databuzz.com.au/fmaccounting-link-xero-edition-update-notes-history-and-attachments
