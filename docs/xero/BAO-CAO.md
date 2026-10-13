# Nghiên cứu tích hợp ERPNext ↔ Xero bằng Frappe

Bản nghiên cứu cho người giao việc, ngày 2026-10-12. Phạm vi: Sales Order → Invoice → trạng thái về, và Credit Note trên Xero → ảnh hưởng hiển thị trên Sales Order.

**Kết luận:** dùng API của Xero từ background job (tác vụ nền), outbox (bảng lưu việc cần gửi) cho chiều đi và polling (đọc định kỳ) cho chiều về. ERPNext giữ đơn hàng; Xero giữ sự thật về hóa đơn, thuế và công nợ. Demo dùng Desk, chạy local, kết nối Demo Company ở bậc API Starter.

**Mức xác nhận:** đây là thiết kế theo [kế hoạch hiện hành](../../plan/done/xero/PLAN.md), không phải báo cáo hai luồng đã chạy thành công. Khi viết, A2 còn TODO (`plan/done/xero/board/lane-a.md:8`); phiên này không chạy code, không đọc database và không gọi API của một organisation. Thông số bên dưới có nguồn chính thức; kết quả DEMO phải được bổ sung sau khi chạy thật ở W3.

## Cách tích hợp

```text
Cài đặt: admin cấp quyền OAuth → kết nối đã lưu + tenant (organisation Xero)

ERPNext / Frappe local                         Xero / Demo Company
Sales Order submit
  → lưu outbox cùng transaction
  → sau commit: xếp background job
  → tra Customer / số đơn qua API ───────────→ Contact / Invoice
  ← lưu ID Xero, trạng thái gửi

Scheduler hoặc nút Refresh
  → job đọc thay đổi qua API ────────────────→ Invoice / Credit Note
  ← ghi đè công nợ, trạng thái; upsert credit note
  → hiển thị field Xero + timeline trên Sales Order
```

Hình là **luồng dự kiến**, dựa trên `plan/done/xero/PLAN.md:103` (outbox), `:192` (chiều về) và mục “Luật nghiệp vụ của demo” (bên giữ sự thật). Không phải trace của code đã hoàn tất.

Admin nối Xero trước buổi demo bằng OAuth (cấp quyền cho app). Người dùng Frappe hằng ngày dùng kết nối đã lưu, không cần tài khoản Xero. Cấu hình kết nối và custom field nằm trong code; bí mật nằm ngoài repo. Connected App và Token Cache của Frappe là cơ chế dự kiến được sử dụng; khả năng đổi token và Redirect URI thực tế vẫn cần xác nhận trong P0. Xem [ghi chú kết nối](02-oauth-va-ket-noi.md).

Mọi lời gọi dữ liệu đi từ máy local ra Xero. Polling không cần Xero truy cập máy local, nên không cần triển khai URL nhận webhook cho demo.

## Luồng Sales Order → Invoice → trạng thái về

Khi submit đơn, hệ thống dự kiến lưu một dòng outbox với khóa duy nhất theo chứng từ và thao tác. Chỉ sau commit (chốt transaction database) mới xếp job; request không chờ Xero. Job nhận diện Customer bằng `ContactNumber`, invoice bằng `InvoiceNumber` là tên Sales Order: tra trước, chưa có mới tạo. ID Xero được lưu để nối hai phía.

Invoice gửi ở trạng thái `AUTHORISED` (đã duyệt), gồm khách, mô tả, số lượng, đơn giá và tiền tệ. Mã tài khoản doanh thu và mã thuế lấy từ Settings. Xero tính thuế và tổng; demo không gửi bảng thuế hoặc chiết khấu ERPNext.

Kế toán ghi payment bên Xero. Job chiều về sao chép trạng thái invoice, đã trả, còn nợ và đã ghi giảm vào các field `lab_xero_*`. Refresh chỉ xếp job: kết quả hiện sau khi job hoàn tất, không phải ngay khi HTTP trả lời. Chu kỳ định kỳ dự kiến là **5 phút**, theo `plan/done/xero/PLAN.md:257`; khi job lỗi hoặc queue chậm, dữ liệu có thể cũ hơn chu kỳ đó.

Cancel chỉ được phép khi số liệu đã đồng bộ cho thấy chưa trả tiền và chưa ghi giảm. Job gửi void (hủy hiệu lực) sang Xero. Số liệu local có thể cũ: nếu Xero từ chối, phải hiện `Failed` và lý do để xử lý, không coi cancel local là bằng chứng Xero đã void. Luật: `plan/done/xero/PLAN.md:256`.

## Luồng Credit Note → Sales Order

Kế toán tạo Credit Note (chứng từ ghi giảm công nợ) bên Xero rồi allocate (áp số tiền) vào invoice của ta. Job đọc thay đổi, tìm Sales Order qua InvoiceID, upsert (tạo nếu chưa có, cập nhật nếu đã có) `Lab Xero Credit Note` theo ID Xero. Lần đầu thấy mới thêm comment vào timeline; kéo lại không tạo dòng hoặc comment trùng.

Ảnh hưởng là **hiển thị** số đã ghi giảm, còn nợ, trạng thái invoice và chứng từ liên quan. Không giảm tổng đơn, không đổi trạng thái có sẵn của ERPNext, không tạo chứng từ trả hàng. Số công nợ lấy từ invoice Xero, không tự trừ lại từ các credit note. Credit note chưa áp hoặc invoice không thuộc ta được bỏ qua; credit note áp nhiều invoice nằm ngoài demo. Đây là quyết định cuối theo `plan/done/xero/PLAN.md:258–269`, dù [ghi chú hai luồng cũ](09-yeu-cau-va-hai-luong.md) còn nêu phương án rộng hơn.

## Những lựa chọn đã chốt và còn mở cho dự án thật

| Vấn đề | Demo đã chọn | Dự án thật cần quyết |
|---|---|---|
| Sổ hóa đơn | Xero giữ hóa đơn; ERPNext giữ đơn | Có cần Sales Invoice song song trong ERPNext? |
| Phát hành | Một đơn → một invoice đã duyệt; số invoice = tên đơn | Nháp rồi duyệt, dãy số Xero, hóa đơn từng phần |
| Thuế và tiền tệ | Xero tính thuế; tiền tệ hai phía trùng nhau | Mapping thuế theo vùng, chiết khấu, tỷ giá, làm tròn |
| Credit note | Chỉ hiển thị; thuộc đơn qua allocation | Trả hàng ERPNext, nhiều invoice, gỡ allocation |
| Quyền | Retry/Refresh cần quyền ghi đơn; Settings và kết nối dành cho System Manager | Ai sở hữu outbox, quyền của worker, nhiều organisation |
| Thay đổi sau phát hành | Không cập nhật nội dung từ ERPNext | Chính sách sửa đơn, sửa hóa đơn bên Xero và đối soát |

Các quyết định demo lấy từ `plan/done/xero/PLAN.md:249–279`. Field trạng thái gửi (`Synced`/`Failed`) và trạng thái kế toán (`AUTHORISED`/`PAID`) có nghĩa khác nhau. Không nên trình bày `Synced` thành “khách đã trả tiền”.

## Giới hạn và độ tin cậy

- **Rate limit:** Starter tối đa **1.000 lời gọi/ngày/organisation**, **5 connection**. Giới hạn theo organisation còn có **60 lời gọi/phút** và **5 lời gọi đồng thời**. Nguồn: [Xero Pricing](https://developer.xero.com/pricing), [Limits FAQ](https://developer.xero.com/faq/limits). Hết hạn mức hoặc Xero bận là lỗi vận hành phải hiển thị; demo chưa cam kết có bộ retry tự động đầy đủ.
- **Ngân sách polling:** với lịch **5 phút** của kế hoạch, giả định mỗi chu kỳ đọc một trang invoice và một trang credit note: `24 × 60 / 5 × 2 = 576` lời gọi/ngày. Đây là **ước tính tự tính**, chưa đo; chưa gồm phân trang, đọc chi tiết, Refresh, tra/tạo và retry. Có thêm dữ liệu thì Starter có thể không đủ.
- **Idempotency-Key** (khóa chống xử lý lặp) chỉ được Xero giữ **6 phút** từ lời gọi đầu. Vì vậy timeout không có nghĩa là Xero chưa tạo: retry phải tra số hiệu trước. Khóa outbox duy nhất, xử lý tuần tự cùng dòng và ID Xero là các lớp bổ sung theo kế hoạch; header một mình không bảo vệ retry muộn. Nguồn: [Idempotent requests](https://developer.xero.com/documentation/guides/idempotent-requests/idempotency/).
- **Transaction local không bao phủ Xero.** Xero có thể đã ghi nhưng local chưa lưu được kết quả. Outbox giữ ý định gửi; tra lại giúp khôi phục. Thiết kế này không cam kết atomic transaction giữa hai hệ thống. SAGA (bù trừ thao tác đã làm) thuộc giai đoạn sau, không phải điều kiện của hai luồng này.
- **Polling so với webhook:** polling đơn giản cho local nhưng tốn API và có độ trễ. Webhook cần endpoint HTTPS công khai, kiểm chữ ký và xử lý sự kiện lặp; thông báo không thay thế việc đọc dữ liệu hiện tại. Dự án thật nên cân nhắc webhook kèm đối soát định kỳ. Nguồn: [Xero Webhooks](https://developer.xero.com/documentation/guides/webhooks/overview), [ghi chú API](03-accounting-api.md).
- **Demo Company reset sau 28 ngày**, xóa dữ liệu đã thêm; có thể reset bằng tay. Không dùng nó để giữ bằng chứng lâu dài. Sau reset cần kiểm lại connection, tenant và các ID local trước khi demo tiếp; ảnh hưởng chính xác tới kết nối của lab chưa kiểm chứng. Nguồn: [Xero: Use the demo company](https://central.xero.com/0/article/Use-the-demo-company).

## Chi phí khi lên thật

Demo dùng Demo Company và API Starter miễn phí; không nâng bậc, không nhập thẻ. Dự án thật có các khoản riêng: thuê bao phần mềm Xero của organisation, phí API của app nếu cần nâng bậc, hạ tầng Frappe, vận hành và bảo trì tích hợp. Chưa biết quốc gia, gói thuê bao, lượng chứng từ và dung lượng đọc nên chưa thể đưa tổng chi phí.

Giá API công bố, **AUD/tháng, chưa thuế**: Starter miễn phí; Core **35**; Plus **245**; Advanced **1.445**; Enterprise báo giá riêng. Các bậc trả phí cho **5.000 lời gọi/ngày/organisation**; dung lượng đọc và phí vượt mức là khoản cần dự toán thêm. Đây là phí API, khác thuê bao kế toán Xero. Nguồn: [Xero Developer Pricing](https://developer.xero.com/pricing), đối chiếu khi viết báo cáo; giá cần kiểm lại trước khi mua.

## Khuyến nghị và phần chưa kiểm chứng

Hoàn tất hai luồng trên Demo Company trước, giữ ranh giới dữ liệu và phạm vi demo đã chốt. Trước khi kết luận tích hợp thành công, cần chứng minh bằng tay: gửi lại không tạo invoice trùng; payment quay về đúng; credit note kéo lại không tạo dòng/comment trùng; lỗi hiện rõ và Retry được. Bản này chưa có kết quả của các kiểm tra đó.

P0 cần xác nhận Redirect URI và token thực tế. P2 cần xác nhận dữ liệu allocation trả về, phân trang và việc áp credit note có làm invoice xuất hiện trong danh sách thay đổi hay cần đọc lại theo ID. Sau demo, quyết định các nghiệp vụ còn mở với kế toán, đo ngân sách API, rồi bổ sung đối soát, phục hồi job bị bỏ lỡ và điều phối token khi nhiều worker. Không mở rộng sang SAGA, middleware lỗi hay mất kết nối trước khi phần được giao chạy xong.

Nguồn nội bộ: [kế hoạch](../../plan/done/xero/PLAN.md), [Xero và chi phí](01-xero-la-gi.md), [OAuth](02-oauth-va-ket-noi.md), [API và giới hạn](03-accounting-api.md), [hai luồng](09-yeu-cau-va-hai-luong.md). Quyết định trong kế hoạch hiện hành được ưu tiên hơn ghi chú nghiên cứu cũ; không dùng ghi chú cũ làm bằng chứng code đã chạy.
