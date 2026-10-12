# 01. Xero là gì, nằm ở đâu, cần tài khoản gì

Nhãn độ tin cậy: xem `00-README.md`.

## Trả lời trong năm dòng

1. Xero là **phần mềm kế toán trên cloud** cho doanh nghiệp nhỏ và vừa (công ty New Zealand): hóa đơn, công nợ, ngân hàng, thuế, báo cáo. [G]
2. **Chỉ có bản online.** Không tải về, không self-host, không có bản chạy local để test. Thứ gần "sandbox" nhất là **Demo Company**. [G]
3. Bạn cần **một login Xero** (miễn phí) → dùng nó cho cả `go.xero.com` (phần mềm) và `developer.xero.com` (đăng ký app). [3]
4. Demo không tốn tiền: Demo Company miễn phí, bậc API **Starter** miễn phí (5 connection, 1000 lời gọi/ngày). [X]
5. ERPNext và Xero **trùng vai** (cả hai đều là sổ kế toán). Tích hợp nghĩa là: bán hàng làm ở ERPNext, kế toán chốt sổ ở Xero, nên invoice và payment phải chảy sang.

## Xero so với thứ bạn đã biết

| | ERPNext trong lab | Xero |
|---|---|---|
| Chạy ở đâu | Docker trên máy bạn | Server của Xero, truy cập qua web |
| Database | MariaDB của bạn, đọc được | Không bao giờ thấy; chỉ có API |
| Sửa hành vi | hook, override, custom field | Không sửa được; chỉ gọi những gì API cho |
| Môi trường test | tạo site mới | Demo Company (một cái, tự reset) |
| "Một công ty" gọi là | Company | **organisation** (tổ chức), trong API gọi là **tenant** |
| Chi phí | 0 | thuê bao theo tháng cho mỗi organisation thật; Demo Company thì 0 |

Hệ quả cho cách làm việc: không có `docker compose up xero`. Muốn thấy Xero phản ứng thế nào thì phải gọi thật qua internet vào Demo Company. Kế hoạch chỉ dùng **Xero thật**: mọi lần chạy thử đều là một lời gọi vào Demo Company, nên tài khoản và lần Connect (P0) phải có trước khi chạy được bất cứ gì. (Trong code còn sót một client thế chỗ từ sprint cũ; nó bị gỡ ở P1, xem `04`.)

## Từ vựng (đủ dùng cho cả gói)

| Từ | Nghĩa |
|---|---|
| **organisation / tenant** | sổ sách của một công ty bên Xero. Mỗi cái có một `tenantId` (GUID). |
| **Demo Company** | một organisation mẫu có sẵn khách hàng, hóa đơn, tài khoản; ai cũng mở được, tự reset định kỳ. |
| **app** | bản đăng ký của phần mềm ta tại `developer.xero.com`; cho ta `client_id` + `client_secret`. |
| **connection** | mối nối "app này được phép vào organisation kia", do một user Xero bấm đồng ý tạo ra. |
| **scope** | phạm vi quyền app xin (đọc/ghi invoice, contact…). |
| **access token / refresh token** | vé vào cửa sống 30 phút / vé đổi vé mới sống 60 ngày. |
| **contact** | khách hàng hoặc nhà cung cấp bên Xero (= Customer/Supplier của ERPNext). |
| **invoice `ACCREC` / `ACCPAY`** | hóa đơn bán (accounts receivable: phải thu) / hóa đơn mua (accounts payable: phải trả). |
| **chart of accounts** | hệ thống tài khoản kế toán; mỗi dòng hóa đơn phải chỉ vào một `AccountCode`. |
| **tax type** | mã thuế của dòng hóa đơn; **khác nhau theo quốc gia của organisation**. |
| **void** | hủy hiệu lực một invoice đã duyệt (không xóa cứng được). |
| **webhook** | Xero chủ động gọi URL của ta khi có thay đổi. |

## Ba thứ phải có, và cách lấy

```text
① login Xero ──► ② Demo Company (dữ liệu để ghi vào)
      │
      └────────► ③ app tại developer.xero.com ──► client_id + client_secret
                          │
                          └─ đăng ký redirect URI (địa chỉ Xero trả trình duyệt về) = URL callback của Frappe
```

**① Login Xero.** Đăng ký tại `xero.com` (nút dùng thử). Bản dùng thử 30 ngày đi kèm một Demo Company [X* trang trial của Xero]. Bạn không cần tạo organisation thật nào; nếu trang đăng ký bắt tạo, cứ tạo một cái trial rồi bỏ đó. Demo Company vẫn mở được sau khi trial hết [G].

**② Demo Company.** Trong Xero: bấm tên organisation ở góc → "Demo Company" (vị trí menu có thể khác, các hướng dẫn mô tả không giống nhau [3]). Cần biết:
- Dữ liệu **reset mỗi 28 ngày** [3, từ devblog của Xero], và bạn có thể reset tay. Sau reset, mọi invoice ta đã đẩy sang biến mất, **connection cũng mất** [G] → phải bấm Connect lại. Đừng coi Demo Company là nơi lưu lâu dài.
- Chọn được quốc gia cho Demo Company [G]. Quốc gia quyết định bộ **tax type** và đơn vị tiền mặc định. Chọn một lần và giữ nguyên (ví dụ Australia hoặc Global), vì mapping thuế phụ thuộc nó.
- Không dùng cho dữ liệu khách hàng thật hay test tải [3].

**③ App.** Tại `developer.xero.com` → My Apps → New app [3]:
- Loại: **Web app** (server giữ được secret; đây là loại của ta). Loại khác ở `02`.
- Tên app, URL công ty (điền gì cũng được với demo).
- **Redirect URI**: chuỗi mà Frappe tính ra trên form Connected App (`02`). Phải khớp từng ký tự.
- Nhận `client_id`; bấm tạo `client_secret` (chỉ hiện một lần). Hai giá trị này bạn gõ vào Desk, **không bao giờ vào repo** (AGENTS.md B3).

## Tiền

Có hai khoản khác nhau, đừng lẫn:

| Khoản | Ai trả | Demo |
|---|---|---|
| **Thuê bao Xero** của một organisation thật | công ty dùng Xero để làm kế toán | 0: dùng Demo Company |
| **Phí API theo bậc của app** (từ 2026-03-02) [X] | bên viết app (ta) | 0: bậc Starter |

Bậc API [X] `developer.xero.com/pricing`, giá AUD/tháng chưa thuế:

| Bậc | Phí | Connection tối đa | Lời gọi/ngày mỗi organisation | Egress (dữ liệu đọc ra) |
|---|---|---|---|---|
| **Starter** | 0 | **5** | **1000** | không tính |
| Core | 35 | 50 | 5000 | 10 GB |
| Plus | 245 | 1000 | 5000 | 50 GB |
| Advanced | 1445 | 10 000 | 5000 | 250 GB |
| Enterprise | thỏa thuận | không giới hạn | 5000 | thỏa thuận |

- "Connection" đếm theo organisation đã nối với app. Một công ty dùng một organisation = một connection. Starter đủ cho demo và cho cả một công ty chỉ nối sổ của chính mình.
- Ghi vào Xero (ingress) không tính phí ở mọi bậc [X]; chỉ đọc ra mới tính dung lượng. Luồng của ta chủ yếu là ghi.
- Endpoint `Journals` chỉ có từ bậc Advanced và phải qua thẩm định [X]. Ta không cần nó.
- Điều khoản developer cấm dùng dữ liệu lấy qua API để huấn luyện mô hình AI [X]. Với lab: chỉ dữ liệu Demo Company, và agent vốn không được đọc dữ liệu thật (AGENTS.md A12).

## Luật 0 đồng (ràng buộc của demo này)

Bạn đã quyết: **không trả gì cho demo.** Làm được, với điều kiện ở yên trong cột trái.

| Được dùng, miễn phí | Không đụng vào (tốn tiền hoặc dễ dẫn tới tốn tiền) |
|---|---|
| Login Xero | Đăng ký gói thuê bao cho một organisation thật (Starter/Standard/Premium của **phần mềm** Xero) |
| **Demo Company** làm nơi ghi dữ liệu | Nhập thẻ thanh toán ở bất kỳ màn hình nào của Xero |
| App loại **Web app** ở bậc API **Starter**: 0 AUD, 5 connection, 1000 lời gọi/ngày [X] | Nâng app lên Core / Plus / Advanced (35 / 245 / 1445 AUD mỗi tháng) [X] |
| OAuth authorization code flow qua Connected App của Frappe | **Custom connection** (tùy chọn trả phí [G], và chỉ có ở AU/NZ/UK/US [3]) |
| Đọc dữ liệu bằng polling thưa | Endpoint `Journals` (chỉ từ bậc Advanced [X]); dịch vụ tunnel/hosting trả phí để nhận webhook |
| Mọi thứ chạy trên máy bạn (Docker, Frappe, ERPNext: mã nguồn mở) | Công cụ tích hợp trung gian trả phí (Apideck, Codat, Fivetran…) và connector viết thuê |

Bốn điều cần để ý để không trả tiền một cách vô ý:
1. **Trial 30 ngày.** Nếu lúc đăng ký Xero tạo cho bạn một organisation dùng thử, cứ để nó hết hạn; đừng bấm "Subscribe"/"Buy now". Demo chỉ nối với Demo Company. Các hướng dẫn nói trial không đòi thẻ [3, chưa tự xác nhận]; nếu màn hình nào đòi thẻ thì thoát ra.
2. **Chỉ nối app với Demo Company.** Lúc bấm Connect, Xero cho chọn organisation: chọn đúng "Demo Company". Starter chỉ có 5 connection; nối lại sau mỗi lần reset là bình thường.
3. **1000 lời gọi/ngày là trần cứng của bậc miễn phí**, không mua thêm được ở Starter. Hết thì chờ sang ngày, không nâng bậc. Vì vậy: không poll theo phút, cache dữ liệu tham chiếu (`03`, `07`).
4. **Webhook** cần URL HTTPS công khai. Demo không làm webhook, nên không cần tunnel hay hosting nào.

Chưa xác nhận được từ trang của Xero: connection vào Demo Company có được tính vào hạn mức 5 connection hay không [chưa biết]. Không ảnh hưởng: ta chỉ cần một.

Ghi chú cho sau demo, không phải cho bây giờ: dự án thật thì công ty khách hàng trả thuê bao Xero của họ; phần của bên viết app vẫn có thể là 0 nếu chỉ nối tối đa 5 organisation và 1000 lời gọi/ngày là đủ.

## Việt Nam và dự án sắp tới

- Xero không có bản dành riêng cho Việt Nam; các nước không được hỗ trợ riêng dùng bản "Global" [3]. Thuế suất mặc định và báo cáo thuế **không khớp quy định Việt Nam**, phải cấu hình tay; hóa đơn điện tử VAT cần phần mềm khác [3, Digita].
- Điều này không cản demo: API giống nhau ở mọi vùng, chỉ khác bộ `TaxType` và `AccountCode`. Nó là lý do mapping thuế và tài khoản phải là **dữ liệu cấu hình**, không phải hằng số trong code (`04`).
- **Custom connection** (kiểu nối máy-với-máy, không cần user bấm đồng ý) chỉ có cho organisation ở Australia, New Zealand, UK, US [3] → đừng thiết kế dựa vào nó nếu organisation thật không ở bốn nước đó.
- Câu hỏi phải hỏi người giao việc, vì nó đổi thiết kế: organisation Xero thật của dự án thuộc **quốc gia nào**, và dùng **đơn vị tiền nào**.

## Có app Xero ↔ ERPNext làm sẵn không?

Tìm hôm nay không thấy connector mã nguồn mở nào đáng tin trên GitHub; chỉ thấy một dịch vụ viết thuê [3]. Xero có SDK Python chính thức `xero-python` [G], nhưng nó **không** nằm trong dependency của dự án (AGENTS.md A6: muốn thêm phải qua con người). Không cần: API là REST + JSON, và Frappe đã cài sẵn `requests-oauthlib` ([S] `frappe-bench/apps/frappe/pyproject.toml:70`).

## Tự kiểm tra

1. Vì sao không thể "chạy Xero trong Docker" cho lab, và lab dùng gì thay?
2. Hai khoản tiền nào liên quan tới Xero, và demo trả bao nhiêu cho mỗi khoản?
3. Chuyện gì xảy ra với các invoice đã sync và với connection khi Demo Company reset?
