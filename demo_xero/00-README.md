# demo_xero: kịch bản demo và giải thích toàn bộ phần tích hợp Xero

Viết ngày 2026-10-12, sau khi luồng chính đã chạy thật với Demo Company của Xero. Thư mục này dùng cho hai việc: **chạy demo** và **giải thích mọi thứ đã xây** (code của ta, database, OAuth, từng lời gọi sang Xero). Nó không giải thích bên trong Frappe; chỗ nào dựa vào Frappe thì nói một dòng "ta dựa vào X" và trích đúng đoạn cần.

Kế hoạch: `plan/xero/PLAN.md`. Kiến thức nền rộng hơn: `docs/xero/`.

## Đọc theo thứ tự nào

| File | Trả lời câu hỏi |
|---|---|
| `01-kich-ban-demo.md` | Tờ chạy demo một mạch: một hình, 19 bước (làm, thấy, ý nghĩa). Cố ý ngắn, ít kỹ thuật |
| `02-oauth.md` | OAuth từ đầu tới cuối: mỗi bước ai gọi ai, gửi gì, nhận gì, lưu ở đâu, để làm gì |
| `03-xero-api.md` | Từng lời gọi sang Xero: URL, header, tham số, body, câu trả lời, lỗi |
| `04-co-so-du-lieu.md` | Dữ liệu nằm ở đâu: DocType mới, field thêm vào ERPNext, site config; mỗi luồng ghi gì |
| `05-cau-truc-code.md` | Code nằm ở đâu, ai gọi ai, vì sao chia như vậy |
| `06-giai-thich-code.md` | Từng file, từng hàm, có trích code; transaction ở đâu; hỏng thì sao |
| `07-hoi-dap.md` | Các câu dễ bị hỏi, kèm câu trả lời ngắn |
| `08-bao-ve-demo.md` | Bảo vệ demo: quyết định và đánh đổi, phi chức năng, luật nghiệp vụ, điểm yếu thật, việc phải cẩn thận trong buổi demo |
| `09-connected-app.md` | `Connected App` như một hộp đen: code của ta lấy `client` thế nào, mỗi bước đi tới đâu, phải tự lo gì quanh nó |
| `10-nam-tham-so.md` | Năm tham số trong site config: mỗi cái là gì, chép vào đâu, dùng ở dòng code nào; riêng `client_secret` dùng ở đâu |
| `11-xem-du-lieu-xero.md` | ERP xem dữ liệu Xero thế nào: đọc bản sao trong database Frappe, không gọi API lúc xem |
| `12-oauth-ranh-gioi.md` | OAuth theo ranh giới: ba vùng (FE, BE, Xero), thứ đi qua mỗi ranh giới; Connected App cho sẵn gì; chặn xin thừa scope ở đâu |
| `13-chi-tiet-canh-demo.md` | Kỹ thuật phía sau kịch bản: lệnh kiểm, luật điền form, vì sao đổi tên khách không sang Xero, đổi gì bên Xero thì về Frappe, sự cố |

## Bức tranh trong một hình

```text
 TRÌNH DUYỆT (Desk)                 FRAPPE (Docker trên máy)                          XERO (cloud)
 ───────────────────                ─────────────────────────                          ────────────
 admin bấm Connect  ──────────────► Connected App "xero"  ─── OAuth (một lần) ───────► login.xero.com
                                    Token Cache (token đã mã hóa) ◄── token ────────── identity.xero.com

 user Submit Sales Order ─────────► overrides/sales_order.py  (trong transaction của lần submit)
                                      └─ lab_xero/outbox.py: ghi 1 dòng "Lab Xero Outbox"
                                    ── commit ──
                                    worker: tasks/xero_sync.py
                                      ├─ integrations/xero/client.py ── tìm / tạo Contact ─► api.xero.com
                                      ├─ lab_xero/mapping.py          ── tìm / tạo Invoice ─►
                                      └─ ghi id + trạng thái lên Sales Order  ◄── InvoiceID ──

 kế toán trả tiền / tạo credit note trong Xero ──────────────────────────────────────► (dữ liệu đổi ở Xero)
                                    scheduler (5 phút) hoặc nút Refresh
                                    worker: tasks/xero_pull.py
                                      ├─ client: đọc invoice, credit note đã đổi ◄─────── api.xero.com
                                      ├─ ghi đè các field lab_xero_* trên Sales Order
                                      └─ lab_xero/inbound.py: 1 dòng "Lab Xero Credit Note" + 1 comment
```

## Cái gì đã chạy thật, cái gì chưa

Bằng chứng là dữ liệu đọc từ site ngày 2026-10-12 (lệnh chỉ đọc), không phải suy đoán.

| Việc | Trạng thái | Bằng chứng |
|---|---|---|
| Connect bằng OAuth, lưu token | **Đã chạy** | `has_token` trả `true`; dòng Token Cache `xero-Administrator`, `expires_in` = 1800 |
| Tìm organisation (tenant) | **Đã chạy** | `Lab Xero Settings.tenant_name` = "Demo Company (Global)" |
| Sales Order → Contact + Invoice bên Xero | **Đã chạy** | `SAL-ORD-2026-00007`: `Synced`, hóa đơn `AUTHORISED`, còn nợ 1000; Customer có `lab_xero_contact_id` |
| Một khách, nhiều hóa đơn | **Đã chạy** | `SAL-ORD-2026-00007` và `-00008` cùng khách "West View Software Ltd.", cùng một contact id |
| Lỗi hiện rõ, sửa rồi Retry | **Đã chạy** | `-00006` `Failed` vì có discount; `-00007` `Failed` vì thiếu mô tả → sửa code → Retry → `Done`, `attempts` = 2 |
| Kéo trạng thái về (job chạy được) | **Đã chạy** | `lab_xero_last_synced_at` đổi sau mỗi lần kéo; `last_pull_at` tiến đều theo lịch |
| Tự làm mới token sau 30 phút | **Có vẻ đã chạy** | Token Cache được cập nhật lúc 14:48:02, đúng nhịp scheduler, không có người bấm; không có "Token Refresh Error" mới |
| Trạng thái đổi thật (trả tiền → `PAID`) | **Chưa thử** | chưa ai ghi payment trong Xero |
| Credit note → Sales Order | **Chưa thử** | bảng `Lab Xero Credit Note` còn trống |
| Cancel đơn → void hóa đơn | **Chưa thử** | |
| Đổi tên Customer → Xero | **Chưa có code** | xem `13`, mục 3, và câu hỏi ở cuối `07` |

Một lỗi đã gặp mà chưa rõ nguyên nhân: `SAL-ORD-2026-00009` lúc 14:26 báo "Xero authorization was refused" (Xero trả 401 hoặc 403). Các lần gọi sau đó chạy bình thường. Đơn này dù sao cũng có discount nên sẽ bị từ chối bởi luật demo. Nếu gặp lại khi demo: Connect lại rồi Retry.

## Quy ước trong thư mục này

- Đường dẫn code tính từ `frappe-bench/apps/lab_core/lab_core/`; code của Frappe tính từ `frappe-bench/apps/frappe/`.
- Đoạn code trích là code thật tại thời điểm viết, có ghi `file:dòng`. Code đổi thì đoạn trích có thể lệch; file thật luôn là bản đúng.
- Không có bí mật nào ở đây: `client_id`, `client_secret`, token được viết là `<…>`.
- "Đã quan sát" = thấy trong dữ liệu hoặc log thật. "Theo code" = đọc từ code, chưa thấy chạy. "Từ trí nhớ" = kiến thức chung về Xero, chưa đối chiếu.
