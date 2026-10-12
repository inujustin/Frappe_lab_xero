# Bảng việc: giai đoạn 1 của kế hoạch Xero

Dùng cho **mọi agent** (Codex, Antigravity, Claude…) và cho **một, hai hoặc ba phiên cùng lúc**. Kế hoạch (làm gì, luật gì) là `plan/xero/PLAN.md`; bảng này chỉ chia việc đó thành các **làn** (lane) không đụng file của nhau, để nhiều phiên chạy song song an toàn.

## Luật của bảng

1. **Mỗi phiên nhận một làn**, do con người chỉ định trong lời nhắc. Phiên chỉ sửa các file thuộc làn của mình (bảng "Ai sở hữu file nào").
2. **Mỗi lần một bước.** Làm bước đầu tiên trong làn của mình còn `TODO` và không bị chặn; xong thì đổi trạng thái của bước đó trong **file làn của chính mình**, viết tóm tắt, rồi dừng. Không tự sang bước kế.
3. **Chỉ sửa file làn của mình.** Đọc file làn khác để biết một bước mình phụ thuộc đã `DONE` chưa; không bao giờ sửa chúng. Không sửa `README.md` này.
4. **`hooks.py` chỉ làn A được sửa.** Làn khác cần một dòng hook thì ghi dòng đó vào mục "Cần thêm vào hooks.py" trong file làn của mình; làn A áp chúng ở bước A5.
5. Bị chặn (thiếu DocType, thiếu kết nối Xero, bước phụ thuộc chưa xong): ghi `BLOCKED: <lý do>` vào bước đó, báo trong tóm tắt, dừng. Không lách.
6. **Giải thích thứ vừa viết.** Con người phải dễ dàng giải thích được code mà mình và AI viết cho tích hợp (không phải code lõi của Frappe). Vì vậy tóm tắt của mỗi bước có thêm mục "Giải thích": với từng file **của ta** vừa viết hoặc sửa, vài dòng bằng lời thường (tiếng Việt): nó làm gì, ai gọi nó, nó gọi ai, phần nào chạy trong transaction và phần nào sau commit, và một chỗ dễ hiểu sai. Không giảng về bên trong Frappe. Code viết sao cho đọc được: tên rõ, hàm ngắn, không mẹo.
7. Mọi luật của `AGENTS.md` và của `plan/xero/PLAN.md` vẫn giữ nguyên: không test, chỉ Xero thật, không chạy lệnh thuộc vùng của con người, handler gắn vào ERPNext nằm dưới `overrides/`.

Trạng thái của một bước: `TODO` · `DOING` · `DONE` · `BLOCKED: <lý do>`.

## Các làn và thứ tự ưu tiên

```text
Làn H (con người)  P0: tài khoản Xero, tạo DocType, đặt bí mật, bấm Connect   ← chặn mọi lần CHẠY THỬ, không chặn việc viết code
                   (cấu hình nằm trong code: Desk chỉ dùng để tạo DocType)
Làn A (ưu tiên 1)  đường chính: gỡ client thế chỗ → client thật → mapping + job → handler → hooks.py     → DEMO 1
Làn B (ưu tiên 2)  custom field, endpoint Retry/Refresh, nút trên form Sales Order                        → cần cho DEMO 1
Làn C (ưu tiên 3)  chiều về: kéo trạng thái invoice và credit note          (bắt đầu được khi A2 DONE)   → DEMO 2, 3
Làn W (ưu tiên 4)  bản nghiên cứu và kịch bản demo (P5), chỉ đụng docs/                                   → gửi người giao việc
```

| Số phiên | Chia thế nào |
|---|---|
| 1 | làm lần lượt: A → B → C → W |
| 2 | phiên 1: A rồi C · phiên 2: B rồi W |
| 3 | phiên 1: A · phiên 2: B rồi W · phiên 3: C (chờ A2), trong lúc chờ làm W |

A và B song song được ngay từ đầu. C phụ thuộc client của A (bước A2). W không phụ thuộc gì.

## Ai sở hữu file nào

Đường dẫn tính từ `frappe-bench/apps/lab_core/lab_core/`.

| Làn | File được sửa |
|---|---|
| A | `integrations/xero/**`, `lab_xero/outbox.py`, `lab_xero/mapping.py`, `tasks/xero_sync.py`, `overrides/**`, `hooks.py`, và để gỡ đường cũ: `lab_core/doctype/lab_note/lab_note.py`, `lab_core/notes.py`, `api/notes.py`, `api/test_notes.py` |
| B | `setup/**`, `api/xero.py`, `public/js/sales_order.js` |
| C | `tasks/xero_pull.py`, `lab_xero/inbound.py` |
| W | `docs/xero/BAO-CAO.md`, `docs/xero/KICH-BAN-DEMO.md`, `docs/xero/GIAI-THICH-CODE.md` |
| H | Desk, Xero, và mọi lệnh |

File không có trong bảng: không làn nào sửa; cần thì ghi vào tóm tắt để con người quyết.

## Tên dùng chung (để các làn xây song song mà không chờ nhau)

Bổ sung cho "Dữ kiện chung" của `plan/xero/PLAN.md` (DocType, field, hàm của client nằm ở đó).

| Thứ | Tên | Làn viết | Làn dùng |
|---|---|---|---|
| Job chiều đi | `lab_core.tasks.xero_sync.process_outbox(outbox_name: str)` | A | — |
| Operation của outbox | `create_invoice`, `void_invoice` | A | B |
| Xếp việc chiều đi | `lab_core.lab_xero.outbox.queue(doc, operation)` (đã có) | A | B |
| Handler của Sales Order | `lab_core.overrides.sales_order.on_submit`, `.on_cancel` | A | — |
| Áp custom field | `lab_core.setup.customizations.apply()` (không tham số, chạy lại an toàn) | B | A (dòng hook `after_migrate`) |
| Dựng kết nối bằng code | `lab_core.setup.xero_connection.apply()` (không tham số, chạy lại an toàn) | B | A (dòng hook `after_migrate`) |
| Tên bản ghi Connected App | `xero` (cố định, để Redirect URI không đổi qua các lần dựng lại) | B | A, C (đọc qua `Lab Xero Settings.connected_app`) |
| Key trong site config (con người đặt bằng lệnh; code đọc bằng `frappe.conf`) | `xero_client_id`, `xero_client_secret`, `xero_connected_user`, `xero_default_account_code`, `xero_default_tax_type` | B | — |
| Endpoint Retry | `lab_core.api.xero.retry_sync(sales_order: str)`, POST, trả `{"queued": true}` | B | B (nút) |
| Endpoint Refresh | `lab_core.api.xero.refresh(sales_order: str)`, POST, trả `{"queued": true}`; xếp job `pull_sales_order` | B | B (nút) |
| Job kéo một đơn | `lab_core.tasks.xero_pull.pull_sales_order(sales_order: str)` | C | B |
| Job kéo theo lịch | `lab_core.tasks.xero_pull.pull_changes()` (không tham số) | C | A (dòng hook `scheduler_events`) |
| File JS của form | `public/js/sales_order.js` | B | A (dòng hook `doctype_js`) |

## Giai đoạn 2

PE, P4, P3 **khóa** cho tới khi giai đoạn 1 xong (DEMO 1, 2, 3 đã chạy và làn W xong). Khi đó con người yêu cầu thì mới thêm làn cho chúng.

## Khi con người hỏi "làm gì bây giờ?" (what should I do now / what next)

Agent đọc năm file làn trong thư mục này rồi trả lời theo mẫu của AGENTS.md A17, không làm gì khác:

```text
Now, in parallel:
  Session 1: lane <X>, step <id>: <việc> (files: <file>)
  Session 2: lane <Y>, step <id>: <việc> (files: <file>)
  You:       lane H, step <id>: <việc của con người>
After that:  <bước nào đang chờ, chờ cái gì>
```

Cách chọn: với mỗi làn lấy bước đầu tiên còn `TODO` mà mọi phụ thuộc đã `DONE`; xếp theo ưu tiên A, B, C, W; nêu luôn bước kế tiếp của làn H. Nếu con người nói chỉ có một phiên: chỉ nêu một bước, của làn ưu tiên cao nhất còn việc. Bước nào đang `BLOCKED` thì nói rõ lý do và ai gỡ được.

## Lời nhắc khởi động (dán vào bất kỳ agent nào, chỉ đổi chữ cái của làn)

```
Read AGENTS.md, plan/overview.md, plan/xero/PLAN.md and plan/xero/board/README.md.
You are lane A. Open plan/xero/board/lane-a.md, do the first step that is TODO and not blocked,
set its status in that file, give the short summary, then stop and wait for "next".
Edit only the files your lane owns.
```

Một phiên duy nhất: thay dòng thứ hai bằng `You are the only session: take the lanes in the order A, B, C, W.`
