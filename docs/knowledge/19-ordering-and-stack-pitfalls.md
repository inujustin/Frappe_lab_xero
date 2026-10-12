# 19. Thứ tự (request, hook, commit, job) và các bẫy của stack, của bên thứ ba

Viết ngày 2026-10-12. Kiến thức chung của kho này. Đọc sau `02`, `03` và `18`.

Nhãn: [S] đã thấy hôm nay (đường dẫn từ `frappe-bench/apps/frappe/`), [T] từ trace note hoặc file khác trong kho, [I] suy ra và chưa chạy, [G] kiến thức chung. Không chạy gì.

## Trả lời trong năm dòng

1. Trong **một process, một request**, thứ tự là cố định và đọc được từ code: auth → handler → commit hoặc rollback → hook `after_request`.
2. Trong **một document event**, thứ tự cũng cố định: controller của DocType → handler `doc_events` theo thứ tự app đã cài → notification → webhook → server script → automation.
3. Quanh **commit**: `before_commit` → SQL commit → `after_commit`, các callback chạy theo thứ tự đăng ký.
4. Giữa **hai job**, giữa hai request, và với **bên thứ ba**: **không có thứ tự nào được hứa**. Cần thứ tự thì phải tự tạo ra.
5. Phần lớn "lỗi lạ" của một stack nhiều tầng đến từ việc tưởng có một đảm bảo (thứ tự, bền, đúng một lần, cùng một bộ nhớ) mà tầng đó không hề hứa.

## 1. Thứ tự trong một request

[S] `frappe/app.py:135-204`

```text
application(request)
 ├─ init_request(request)                         :139
 │     … dựng context, kết nối database …
 │     các hook before_request                    :244-245
 ├─ validate_auth()                               :141      ← SAU before_request
 ├─ chọn nhánh xử lý (/api/, file, trang web…)    :143-179
 │
 ├─ có exception → handle_exception(e), rồi db.rollback()     :181-184
 ├─ không có     → sync_database()  (commit)                  :186-187
 │
 ├─ finally: các hook after_request               :195      lỗi trong hook chỉ bị ghi log   :196-198
 ├─ log_request                                   :200
 └─ process_response                              :201
```

Hệ quả:
- Hook `before_request` chạy **trước** `validate_auth()`. Phần xác thực bằng header (API key, bearer token) nằm trong `validate_auth` ([T] `01`), nên trong `before_request` chưa chắc đã biết người gọi là ai [I].
- Hook `after_request` chạy **sau** commit hoặc rollback. Nó sửa được response, không chặn được request, và thứ nó ghi vào database không nằm trong transaction của request.
- Hook `after_request` ném lỗi thì bị nuốt (chỉ ghi log). Đừng đặt việc bắt buộc phải xảy ra ở đó.
- Commit đến **sau** khi handler return. Bất cứ thứ gì handler "gửi đi" trước đó (một job đẩy thẳng, một lời gọi HTTP) đã rời đi trong khi dữ liệu chưa được lưu.

## 2. Thứ tự trong một document event

[S] `frappe/model/document.py:1247-1267` và `:1636-1661`

```text
doc.run_method("on_submit")
 1. method của controller (class của DocType)                      fn, chạy trước   :1638
 2. các handler doc_events[<DocType>]["on_submit"], theo thứ tự trong danh sách   :1657-1661
 3. các handler doc_events["*"]["on_submit"]
        (2 và 3 chạy với commit/rollback bị tắt                    :1641-1648)
 4. run_notifications                                              :1264
 5. run_webhooks                                                   :1265
 6. run_server_script_for_doc_event                                :1266
 7. run_automations                                                :1267
```

Thứ tự của các handler trong danh sách đến từ đâu: hook của mọi app được gộp bằng một vòng lặp qua **danh sách app đã cài, theo thứ tự cài** ([S] `frappe/__init__.py:965-988`). Với hai app cùng gắn vào một event, app cài trước chạy trước. Với hook chỉ nhận một giá trị (ví dụ override class), app cài sau thắng ([T] cram sheet).

Hệ quả:
- Handler của ta trên một DocType của ERPNext chạy **sau** controller của ERPNext cho cùng event đó. Thứ ERPNext làm trong `on_submit` đã xong khi ta được gọi.
- Tất cả nằm trong **một transaction**. Handler của ta ném lỗi thì cả lần submit của người dùng bị hủy. Với việc "ghi dòng outbox" đó là điều mong muốn (cùng lưu hoặc cùng mất); với việc phụ (gửi thông báo) thì không.
- Webhook và notification được tính ở bước 4–5 nhưng chỉ **được gửi sau commit** (`17`).
- Thứ tự giữa các *event* của một lần lưu (`validate` → `before_save` → … → `on_update`) là [G]; xem `02`.
- Hook được cache theo vòng đời process: sửa `hooks.py` cần restart ([T]).

## 3. Thứ tự quanh commit

[S] `frappe/database/database.py:1176-1194`; `frappe/utils/__init__.py:1120-1156`

```text
commit():  before_commit.run() → SQL COMMIT → after_commit.run()
callback được chạy THEO THỨ TỰ ĐĂNG KÝ ("executed in order of addition")     utils/__init__.py:1145-1147
           vòng lặp lấy từng cái ra rồi gọi, không có try/except              :1152-1156
```

- Job xếp bằng `enqueue_after_commit`, realtime event và webhook đều đăng ký vào cùng danh sách `after_commit`; chúng rời đi theo thứ tự đã đăng ký trong request.
- Vòng lặp không bắt lỗi: nếu một callback ném exception, các callback **đứng sau nó không chạy trong lần đó** [I]. Dữ liệu đã commit rồi; chỉ các tác động ra ngoài bị thiếu. Thêm một lý do để mọi tác động quan trọng có một dòng database đứng sau (outbox).
- Rollback vứt cả danh sách (`database.py:1202-1203`).

## 4. Thứ tự của job: không có

| Câu hỏi | Trả lời | Bằng chứng |
|---|---|---|
| Hai job xếp theo thứ tự A, B có chạy A trước B không? | Trong một queue, job được lấy ra theo thứ tự vào [G]; nhưng với hơn một worker, A và B **chạy cùng lúc**, và B có thể xong trước | [G], [T] `03` |
| Có chen hàng được không? | có: `at_front=True`; và `at_front_when_starved` tự chen khi queue quá dài | [S] `frappe/utils/background_jobs.py:88, :91, :109-113, :189-190, :199` |
| Giữa các queue? | worker nghe nhiều queue lấy theo thứ tự khai báo: `short`, `default`, `long` ("Order matters here") | [S] `background_jobs.py:63-64` |
| Job bị retry? | chạy lại **sau**, có thể sau những job xếp muộn hơn nó | [S] `:275-290` |
| Job của request trước có chạy trước job của request sau không? | không đảm bảo: tùy lúc mỗi request commit và worker nào rảnh | [I] |
| Scheduled job có thứ tự không? | không: mỗi tick, danh sách site và danh sách job đều bị **xáo ngẫu nhiên** | [S] `frappe/utils/scheduler.py:100-101, :136` |

Vậy khi B cần kết quả của A, đừng dựa vào thứ tự xếp hàng. Các cách tạo ra thứ tự, từ đơn giản tới chắc chắn:

| Cách | Làm thế nào | Khi nào |
|---|---|---|
| Gộp | một job làm A rồi B | hai bước luôn đi cùng nhau |
| Nối chuỗi | A xếp B ở cuối, sau khi đã ghi kết quả (cùng transaction, `enqueue_after_commit`) | chuỗi vài bước |
| Kiểm điều kiện rồi lùi | B chạy, thấy A chưa xong → đặt "thử lại sau" và thoát | phụ thuộc giữa các bản ghi khác loại |
| Máy trạng thái | một cột status; mỗi bước chỉ chạy được từ đúng trạng thái trước nó, dưới row lock | luồng nhiều bước, cần nhìn thấy tiến độ |
| Số phiên bản | bản ghi mang số tăng dần hoặc `modified`; bước tới muộn với số cũ thì bỏ qua | cập nhật có thể tới lộn thứ tự |

Cách nào cũng cần hai thứ đã nói ở `18`: **idempotency** (chạy lại không hại) và **row lock** (hai bên không cùng quyết định).

## 5. Thứ tự với bên thứ ba [G]

Một dịch vụ bên ngoài là một hệ thống khác, có đồng hồ khác và hàng đợi khác. Các giả định sai hay gặp:

| Tưởng là | Thật ra | Cách sống chung |
|---|---|---|
| webhook tới theo thứ tự xảy ra | "update" có thể tới trước "create"; cùng event tới hai lần (`17`) | coi event là gợi ý, đọc trạng thái hiện tại qua API; chống trùng bằng unique |
| ghi xong là đọc lại thấy ngay | nhiều API nhất quán cuối cùng: đọc ngay sau khi ghi có thể chưa thấy | thử lại có giới hạn trước khi kết luận "không có" |
| timeout nghĩa là chưa làm | có thể đã làm xong, chỉ mất câu trả lời | hỏi lại trước khi làm lại (`12`, `18`) |
| lần gửi lại tới sau lần gửi đầu | lần đầu có thể đang kẹt và tới **sau** lần gửi lại | idempotency key; phía ta không ghi đè kết quả mới bằng kết quả cũ |
| đồng hồ hai bên giống nhau | lệch vài giây tới vài phút | con trỏ "đã kéo tới đâu" dùng thời gian **của họ**, và lùi lại một khoảng chồng lấn |
| phân trang ổn định | dữ liệu đổi trong lúc đang lật trang → sót hoặc lặp | sắp theo thời điểm cập nhật; xử lý idempotent |
| API hôm nay là API năm sau | tên quyền, giá, giới hạn đổi theo thông báo của họ | gom mọi hiểu biết về họ vào một module; ghi ngày kiểm chứng cho từng con số |
| giới hạn tần suất tính theo job của ta | tính theo tài khoản: mọi worker dùng chung | một đồng hồ "không gọi trước thời điểm X" dùng chung |
| môi trường thử là vĩnh viễn | sandbox bị reset, token bị thu hồi | coi "mất kết nối" là một trạng thái bình thường có đường quay lại |

## 6. Bẫy theo từng tầng của stack

| Tầng | Bẫy | Dấu hiệu | Cách tránh | Bằng chứng |
|---|---|---|---|---|
| **Process web** (nhiều worker) | mỗi process có bộ nhớ riêng; biến toàn cục và cache trong bộ nhớ không chia sẻ | lúc đúng lúc sai tùy request rơi vào process nào | trạng thái chung chỉ ở database hoặc Redis | [G]; [T] `15` |
| **Hook** | được cache theo process | sửa `hooks.py` mà không thấy tác dụng | restart; `scheduler_events` còn cần migrate | [T] `02`, `03` |
| **Worker job** | nạp code lúc khởi động; đang chạy code cũ sau khi bạn sửa | request thấy hành vi mới, job thấy hành vi cũ | restart worker sau khi sửa code job | [G] |
| **Redis queue** | job chờ nằm trong bộ nhớ của Redis, không phải trong database | Redis khởi động lại → job biến mất, không lỗi nào | thứ quan trọng có một dòng database + sweeper | [G]; `02` |
| **Tham số của job** | được đóng gói lúc xếp, mở ra lúc chạy: là **ảnh chụp cũ** | job làm việc trên dữ liệu đã lỗi thời | truyền tên bản ghi, đọc lại trong job | [G]; của ta: `outbox_name` ([S] `lab_core/lab_xero/outbox.py:39`) |
| **Redis cache** | có thể bị xóa bất cứ lúc nào | dữ liệu "mất" sau khi clear cache | cache không bao giờ là nguồn sự thật (Xero giả của lab cố ý vi phạm điều này: [S] `lab_core/integrations/xero/client.py:27-28`) | |
| **MariaDB** | lệnh đổi cấu trúc (DDL) tự commit ngầm | Frappe ném `ImplicitCommitError` nếu transaction đang có thay đổi | không DDL trong code nghiệp vụ; schema chỉ qua migrate | [S] `frappe/database/database.py:487-489` |
| **MariaDB** | deadlock, lock wait timeout, trần số lần ghi | lỗi chỉ hiện khi có tải | `18` | [S] `18` |
| **Transaction** | code framework tự commit giữa chừng (lưu token, ghi request log) | nửa trạng thái nằm lại; row lock bị nhả sớm | gọi chúng trước lần ghi đầu tiên | [T] `02`, `11` |
| **Scheduler** | mỗi bench chỉ một; bị bỏ qua ở maintenance mode; hàm lỗi chỉ ghi "Failed", không ai được báo | việc định kỳ lặng lẽ ngừng | xem Scheduled Job Log; việc quan trọng phải tự phát hiện "lâu rồi chưa chạy" | [T] `03` |
| **Realtime** (Socket.IO, một process Node riêng) | event chỉ tới client đang nối; không có giao lại | màn hình không cập nhật | status trong database là sự thật, realtime chỉ là gợi ý | [T] `04` |
| **Khóa bằng file** | chỉ đúng trên một máy | hai server cùng refresh một token | đủ cho một máy; nhiều máy cần khóa ở database hoặc Redis | [S] `frappe/utils/synchronization.py:18-30` |
| **Thời gian** | hạn của token tính từ `modified` của dòng lưu nó, theo múi giờ hệ thống rồi đổi sang UTC | token trông còn hạn mà đã chết | luôn xử lý được câu trả lời "hết hạn" | [S] `frappe/integrations/doctype/token_cache/token_cache.py:74-79` |
| **HTTP ra ngoài** | không có timeout mặc định; helper của Frappe biến 4xx/5xx thành exception và làm mất body | job treo tới khi bị giết; mất thông báo lỗi của bên kia | luôn truyền timeout; client mỏng của riêng ta | [T] `03`, `11` |
| **Docker dev** | Python chỉ có trong container, frontend chạy trên host; phiên bản Node phải khớp | "chạy ở máy tôi" | lệnh Python qua `docker compose exec`; Node theo `docker/versions.env` | [T] `OVERVIEW.md`, AGENTS.md B2 |
| **Thư viện bên thứ ba** | tên package nghe có vẻ đúng nhưng không tồn tại, hoặc không nằm trong manifest | lỗi import lúc chạy | chỉ import thứ đã khai báo; package mới phải qua con người | AGENTS.md A6 |

## Mẫu số chung

Mỗi dòng ở trên là cùng một sai lầm: **tin vào một đảm bảo mà không ai hứa**. Trước khi dựa vào một tầng, hỏi bốn câu:

1. Nó có **giữ** thứ tôi đưa không, nếu process chết ngay sau đó?
2. Nó có **giữ thứ tự** không, khi có hơn một worker?
3. Nó có thể **làm hai lần** không?
4. Hai process có **thấy cùng một thứ** không?

Câu trả lời mặc định cho cả bốn là "không", cho tới khi đọc được dòng code hoặc dòng tài liệu nói "có".

## Thử đi (đọc, không cần lệnh)

1. Đọc `frappe/app.py:135-204` và chỉ ra: một hook `after_request` ghi vào database thì thay đổi đó được commit bởi cái gì?
2. Đọc `frappe/model/document.py:1636-1661`: hai app cùng gắn `on_submit` vào Sales Order, cái nào chạy trước, và điều gì quyết định?
3. Đọc `frappe/utils/__init__.py:1152-1156`: callback thứ hai trong ba callback `after_commit` ném lỗi. Cái thứ ba thì sao?
4. Với tính năng bạn đang làm, liệt kê mọi chỗ nó ngầm giả định một thứ tự, rồi tìm dòng code đảm bảo thứ tự đó.

## Còn chưa biết

- Callback `after_commit` còn lại sau khi một cái ném lỗi: bị bỏ hẳn hay chạy ở lần commit sau (mục 3). Cần đọc tiếp hoặc thử.
- Trong hook `before_request`, `frappe.session.user` đã là gì với từng kiểu xác thực (mục 1).
- Thứ tự app đã cài của lab này (quyết định thứ tự handler giữa `erpnext`, `crm`, `lab_core`); nằm trong dữ liệu của site, agent không đọc.
- RQ xử lý thế nào khi worker chết giữa job (job bị bỏ, hay được đưa lại); chưa đọc.
- Dev server của lab có tự nạp lại code cho worker job hay không.
