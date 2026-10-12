# 08. Bảo vệ demo: phải cẩn thận điều gì, bị hỏi thì đáp sao

Đọc file này cuối cùng, ngay trước buổi demo. Mỗi mục là một thứ có thể bị hỏi hoặc có thể hỏng, kèm câu trả lời ngắn và chỗ để chỉ vào. Chi tiết nằm ở `01`–`07`.

## 1. Ba câu luận điểm (thuộc lòng)

1. **Mỗi con số có một chủ.** Đơn hàng thuộc ERPNext, hóa đơn và credit note thuộc Xero. Bên không phải chủ chỉ chép lại.
2. **Gửi đi: ghi sổ trước, gửi sau.** Ý định được lưu cùng transaction với đơn (outbox), một job nền gửi, và job luôn hỏi "đã có chưa" trước khi tạo.
3. **Nhận về: hỏi định kỳ và ghi đè.** Chạy lại bao nhiêu lần cũng ra một kết quả.

Mọi câu hỏi khó đều quay về một trong ba câu này.

## 2. Nói đúng mức: đã chứng minh, đã viết, chưa có

| Mức | Việc | Cách nói |
|---|---|---|
| **Đã chạy thật** | Connect, tìm tenant, Sales Order → contact + invoice, một khách nhiều hóa đơn, lỗi hiện rõ + Retry, job kéo về chạy được | "đã chạy, đây là dữ liệu" |
| **Đã viết, chưa chạy thật** | trả tiền → `PAID`, credit note → đơn, cancel → void | "code đã có, tôi cho xem bây giờ" (chỉ nói vậy nếu đã tập trước) |
| **Chưa có** | đổi tên Customer sang Xero; cảnh báo khi hai bên lệch; tự thử lại; test tự động | "chưa xây, đây là lý do và hướng làm" |

Đừng nói "đồng bộ hai chiều". Nói đúng: **đơn đi một chiều sang Xero; trạng thái, số tiền và credit note đi một chiều về.**

## 3. Yêu cầu của lead và ta đáp ứng tới đâu

| Yêu cầu | Đáp ứng | Còn thiếu |
|---|---|---|
| Nghiên cứu cách tích hợp Xero với Frappe | `docs/xero/` (kiến thức), `demo_xero/` (giải thích code) | — |
| Luồng 1: tạo Sales Order → phát hành Invoice trên Xero → trạng thái Invoice quay về | chiều đi đã chạy; chiều về chạy được | một lần trả tiền thật để thấy `PAID` |
| Luồng 2: Credit Note trên Xero → ảnh hưởng tới Sales Order | code đã viết | một credit note thật; "ảnh hưởng" mới là **hiển thị** (số đã ghi giảm, còn nợ, một bản ghi, một dòng timeline) |

Câu dễ bị hỏi nhất ở luồng 2: "ảnh hưởng nghĩa là gì?". Đáp: "Demo chọn mức nhẹ nhất: hiển thị. Việc credit note có làm giảm tổng đơn, mở lại đơn hay tạo chứng từ trả hàng là luật nghiệp vụ của dự án thật; cơ chế nhận về đã sẵn, chỉ thêm luật."

## 4. Quyết định thiết kế: hỏi, đáp, đánh đổi

| Bị hỏi | Đáp | Đánh đổi phải nhận |
|---|---|---|
| Sao không gọi Xero ngay lúc Submit? | hai hệ thống không chung transaction; người dùng không phải chờ; Xero chết vẫn submit được | hóa đơn xuất hiện chậm vài giây; cần trạng thái `Queued` |
| Sao cần bảng outbox, không xếp job thẳng? | job trong Redis có thể mất; dòng outbox nằm trong database, cùng transaction với đơn, và ghi lại số lần thử, lỗi | thêm một bảng |
| Sao hỏi định kỳ, không dùng webhook? | webhook cần URL https công khai; demo chạy trên máy cá nhân, chi phí 0 | chậm tối đa khoảng 5 phút; tốn khoảng 580 lời gọi mỗi ngày |
| Sao dùng Connected App của Frappe, không tự viết OAuth? | Frappe đã có sẵn lưu token mã hóa, kiểm `state`, tự refresh có khóa | phụ thuộc hành vi của Frappe (ví dụ nó tự commit khi lưu token) |
| Sao số hóa đơn = tên Sales Order? | cần một khóa tự nhiên để **tìm lại** hóa đơn khi câu trả lời bị mất | kế toán không được đổi số hóa đơn bên Xero |
| Sao `PUT` mà không `POST`? | với Xero, `PUT` chỉ tạo; `POST` có thể ghi đè bản ghi cũ | phải tự tìm trước khi tạo |
| Sao tạo hóa đơn ở trạng thái `AUTHORISED` luôn? | để nhận tiền và áp credit note được ngay trong demo | bỏ qua bước duyệt của kế toán; dự án thật có thể gửi `DRAFT` |
| Sao dùng `doc_events` mà không override class Sales Order? | điểm mở rộng nhẹ nhất; code của ERPNext không bị đụng | handler chạy sau code ERPNext, không chen vào giữa được |
| Sao thêm field vào Sales Order mà không tạo bảng riêng? | người bán thấy ngay trên đơn; tạo bằng code (Custom Field), không sửa ERPNext | field `lab_xero_*` nằm trong bảng của ERPNext |
| Sao một user nối cho cả hệ thống? | người bán không cần tài khoản Xero; đúng kịch bản lead chọn | mọi thay đổi bên Xero mang tên một người; mất kết nối là mất cho tất cả |

## 5. Yêu cầu phi chức năng: ta làm gì, còn hở gì

| Thuộc tính | Ta làm gì | Ở đâu | Còn hở |
|---|---|---|---|
| **Không tạo trùng** (idempotency) | tìm theo số trước khi tạo; khóa cố định mỗi (đơn, việc); unique trên id của Xero; `Idempotency-Key` | `tasks/xero_sync.py`, `lab_xero/outbox.py` | key của Xero chỉ sống khoảng 6 phút, nên nó là lớp phụ |
| **Nhất quán** (transaction) | đơn + dòng outbox trong một transaction; job ghi kết quả trong một transaction; thất bại ghi bằng transaction riêng | `06`, mục "Khi hỏng" | hai hệ thống chỉ **nhất quán sau cùng**, không tức thì |
| **Chạy đồng thời** | khóa dòng outbox và Sales Order (`for_update`); lấy token trước khi khóa; Frappe khóa file khi refresh token | `process_outbox` | chưa thử hai worker thật chạy chồng nhau |
| **Chịu lỗi** | bốn loại lỗi; lỗi hiện trên đơn; nút Retry; job kéo hỏng thì con trỏ không tiến | `client.py`, `xero_sync.py`, `xero_pull.py` | **không tự thử lại**; đơn kẹt `Queued` cần người bấm |
| **Giới hạn của Xero** | 429 → `XeroBusy` kèm số giây nên chờ; chỉ kéo thứ đã đổi | `client.py` | lịch kéo đã dùng hơn nửa hạn mức ngày; nút Refresh đọc **mọi** credit note |
| **Hiệu năng** | request không bao giờ chờ Xero; timeout 10 giây nối, 30 giây đọc | `HTTP_TIMEOUT` | chưa đo; một đơn tốn 4–5 lời gọi nối tiếp |
| **Bảo mật** | secret trong site config; token mã hóa; 4 scope tối thiểu; endpoint chỉ POST, kiểm quyền ghi trên đúng đơn; không Guest | `api/xero.py`, `setup/xero_connection.py` | Error Log của Frappe có thể in secret trong traceback (đã gặp) |
| **Quan sát được** | trạng thái + lỗi trên đơn; dòng outbox (số lần thử); Error Log; `Last Pull At` | form, danh sách | không có bảng tổng hợp hay cảnh báo |
| **Thời gian** | giờ site đổi sang UTC, lùi 120 giây khi hỏi Xero | `_xero_utc` | — |
| **Tiền** | làm tròn theo độ chính xác của field; số của Xero được chép, không tính lại | `flt(value, precision)` | một tiền tệ |
| **Kiểm thử** | chạy tay trên Demo Company | — | **chưa có test tự động** (hoãn có chủ đích) |

## 6. Luật nghiệp vụ và lý do (đủ để bảo vệ)

| Luật | Lý do | Nếu bị vặn |
|---|---|---|
| Chỉ đơn đã Submit mới sang Xero | đơn nháp còn đổi được | — |
| Một đơn ↔ một hóa đơn | giữ demo nhỏ | "hóa đơn từng phần là luật của dự án thật" |
| Có thuế, discount, hoặc khác tiền tệ → từ chối, có lý do | ánh xạ thuế và discount cần quyết định của kế toán; từ chối rõ ràng tốt hơn gửi sai | "thà dừng có lý do còn hơn tạo hóa đơn sai số" |
| Số tiền trên đơn là số của Xero | một chủ cho mỗi con số | — |
| Hóa đơn đã có tiền hoặc credit → không cho cancel đơn | ta không tự gỡ tiền của kế toán | phép kiểm dùng số đã lưu, có thể cũ; nếu cũ, Xero từ chối void và đơn báo `Failed` |
| Cancel đơn → void hóa đơn | hai bên không lệch | chưa chạy thật |
| Credit note chưa áp vào hóa đơn → bỏ qua | chưa biết nó thuộc đơn nào | — |
| Id đã lưu không khớp kết quả tra cứu → dừng, không đoán | gắn nhầm hóa đơn tệ hơn là dừng | — |

## 7. Điểm yếu thật: phải biết trước khi người khác tìm ra

Xếp theo mức nguy hiểm cho buổi demo.

**① Chỉ System Manager submit được Sales Order (theo code, chưa thử với user khác).**
Ba DocType của ta chỉ cấp quyền cho role System Manager. Handler lúc submit gọi `outbox.insert()`, và Frappe kiểm quyền tạo:

```python
# lab_xero/outbox.py:24-30
outbox = frappe.new_doc(OUTBOX)
...
outbox.insert()          # frappe/model/document.py:478 → self.check_permission("create")
```

Job nền lại chạy với danh nghĩa **người đã submit** (`frappe/utils/background_jobs.py:179`, `251-252`) và đòi quyền ghi trên outbox, Sales Order, Customer. Một người bán hàng bình thường (không phải System Manager) vì thế sẽ **không submit được đơn nào**.
- Trong demo: **luôn dùng Administrator**. Đừng đổi user giữa chừng.
- Nếu bị hỏi: "Demo chạy với một admin. Phân quyền cho người bán là việc chưa làm; hướng làm là cấp quyền cho role bán hàng trên outbox, hoặc cho job chạy bằng một user hệ thống."
- Đừng "sửa nhanh" bằng `ignore_permissions`: luật dự án cấm.

**② Đổi tên bản ghi Customer làm gãy đơn kế tiếp** (`13`, mục 3). Đừng làm trước mặt người xem.

**③ Hệ thống phụ thuộc ba thứ đang chạy:** worker (chạy job), scheduler (kéo mỗi 5 phút), và token còn sống. Thiếu worker thì đơn đứng ở `Queued` mãi.

**④ Demo Company bị Xero reset định kỳ** (khoảng 28 ngày, từ trí nhớ). Sau reset: phải Connect lại, tìm lại tenant, và mọi `Xero Invoice ID` đã lưu trỏ vào hư không. Dùng đơn mới và khách mới sau reset.

**⑤ Mọi Sales Order đều đi Xero.** Không có công tắc bật/tắt hay lọc theo company. Nếu outbox hỏng, **không ai submit được Sales Order**. Đây là chủ đích ("không có đơn thiếu việc gửi") nhưng là một sự ràng buộc chặt, phải nói ra.

**⑥ Một lần "Xero authorization was refused" chưa rõ nguyên nhân.** Nếu gặp lại: Connect lại, Retry, và nói thẳng là đang tìm hiểu.

**⑦ Sửa bên Xero thứ thuộc ERPNext** (dòng hàng, số hóa đơn, tên contact) → hai bên lệch nhau, không cảnh báo (`13`, mục 4).

**⑧ Tên contact trùng bên Xero** → Xero từ chối tạo (từ trí nhớ) → đơn `Failed`. Dùng tên khách chưa có trong Demo Company.

## 8. Hiểu đúng OAuth để không nói sai

"Connect to Xero" và "Login with Google" dùng **cùng một cơ chế** nhưng để làm **hai việc khác nhau**.

| | Login with Google | Connect to Xero (demo này) |
|---|---|---|
| Để làm gì | biết **người này là ai** để cho vào app (xác thực) | app được **phép làm việc trên dữ liệu** của người đó ở nơi khác (ủy quyền) |
| Ai làm | mọi người dùng, mỗi lần đăng nhập | một admin, một lần |
| App nhận gì | danh tính (ID token: mã người dùng, email) | access token + refresh token để gọi API |
| Sau đó | app tạo **session của chính nó** cho người dùng | không có session nào được tạo; server cất token và dùng dần |
| Người dùng Frappe là ai với Xero | — | không là ai cả: Xero chỉ thấy "app này, thay mặt người đã Allow" |

Ba câu dễ nói sai:

| Nói sai | Nói đúng |
|---|---|
| "Sau khi đăng nhập Xero, trình duyệt nhận được token" | trình duyệt chỉ mang về một `code` dùng một lần; server đổi `code` + `client_secret` lấy token; **token không bao giờ tới trình duyệt** |
| "Người dùng đăng nhập Frappe bằng Xero" | hai danh tính tách rời: Frappe nhận ra người dùng bằng cookie `sid`; Xero nhận ra app bằng token của người đã nối. Ai submit đơn thì Xero cũng chỉ thấy cùng một kết nối |
| "Xero gọi về server của ta" | Xero trả lời trình duyệt bằng lệnh chuyển hướng; trình duyệt tự mở `localhost` |

Nếu bị hỏi rộng ra "Login with Google làm thế nào cho đúng" (kiến thức chung về OAuth, không phải code của demo):

| Cách làm | Đánh giá |
|---|---|
| Frontend báo backend "email này đã đăng nhập Google, cấp token cho tôi" | **Không an toàn.** Backend không được tin lời frontend; phải có bằng chứng |
| Frontend nhận ID token từ Google, gửi cho backend; backend kiểm chữ ký và kiểm token được cấp cho đúng `client_id` của mình, rồi tạo session của app | Dùng được. Chỉ gọi Google bằng access token để "hỏi lại" là chưa đủ: token cấp cho app khác cũng qua được |
| Backend tự đổi `code` lấy token (authorization code flow), có `state`, thêm PKCE | **Tốt nhất.** Token của Google không bao giờ tới trình duyệt; trình duyệt chỉ giữ session của app |

Frappe làm theo cách thứ ba cho Xero (có `state`; không thấy PKCE trong code đã đọc). Google không "đẩy" token về: nó chuyển hướng trình duyệt kèm `code`, backend mới là bên đi lấy token.

`client_id` + `client_secret` là **danh tính của app** với Xero (đăng ký một lần ở developer.xero.com). `state` chống việc kẻ khác cài một lượt callback giả vào phiên của bạn. Sơ đồ đầy đủ: `02`, mục "URL này được dựng thế nào".

## 9. Trước và trong buổi demo: danh sách cẩn thận

**Trước (nên tập một lượt đầy đủ trong ngày):**

| Kiểm | Vì sao |
|---|---|
| Mở Desk bằng `http://localhost:8000`, user Administrator | cookie theo tên host; quyền (mục 7 ①) |
| `has_token` trả `true`; `Tenant Name` có giá trị | không có thì mọi đơn `Failed` |
| Submit thử một đơn → `Synced` trong vài giây | chứng tỏ worker đang chạy |
| `Last Pull At` trong Lab Xero Settings đang tiến | chứng tỏ scheduler đang chạy |
| Có sẵn hai đơn nháp đúng luật: giá niêm yết, không thuế, tiền tệ của Company | đơn A để trả tiền, đơn B để credit note |
| Đã tập trả tiền, credit note, cancel ít nhất một lần | ba cảnh này chưa từng chạy thật |

**Trong:**

- Sau khi Submit hoặc bấm Refresh, **chờ vài giây rồi tải lại form**. Việc chạy ở nền.
- **Không mở Error Log lên màn hình chiếu.** Traceback của Frappe in cả giá trị biến và đã từng chứa secret.
- Không gõ giá khác giá niêm yết; không thêm thuế; không rename Customer; không đổi user.
- Không bấm Connect hai lần liên tiếp ("Invalid token state!").
- Hỏng thì đọc ô `Xero Error` to lên: đó là tính năng ("không gì hỏng trong im lặng"), không phải sự cố.

## 10. Khi không biết câu trả lời

Dùng đúng ba câu, không đoán:

1. "Phần đó **chưa chạy thật**; code đã có ở `<file>`, tôi có thể mở cho xem."
2. "Phần đó **ngoài phạm vi demo, có chủ đích**; dự án thật sẽ cần quyết định `<luật>`."
3. "Tôi **chưa kiểm chứng**; tôi sẽ đối chiếu tài liệu Xero rồi trả lời."

Những gì được đánh dấu "từ trí nhớ" trong thư mục này thuộc loại 3: hạn 60 ngày của refresh token, chu kỳ reset của Demo Company, đường menu bên Xero, hành vi Xero khi trùng tên contact.

## 11. Bị hỏi "vậy sửa thế nào?": code hiện tại → code thay thế

Bảo vệ tốt nhất cho một điểm yếu là chỉ ra đúng chỗ sẽ sửa. Mọi đoạn "thay bằng" dưới đây là **đề xuất**: chưa viết vào code, chưa chạy. Đoạn "hiện tại" là code thật.

| # | Câu hỏi | Sửa ở | Cỡ |
|---|---|---|---|
| 11.1 | "Scope xin có dư không?" | `setup/xero_connection.py` | 1 dòng |
| 11.2 | "Kế toán phải duyệt hóa đơn thì sao?" | `mapping.py`, `xero_sync.py` | 2 dòng |
| 11.3 | "Rename Customer làm gãy đơn sau, sửa sao?" | `xero_sync.py` | 3 dòng |
| 11.4 | "Đơn kẹt, Xero bận: ai thử lại?" | `xero_sync.py`, `hooks.py` | 1 hàm + 1 dòng hook |
| 11.5 | "Lỗi 401 hay 403, sao không biết?" | `client.py` | 2 dòng |
| 11.6 | "Kế toán sửa số tiền bên Xero thì ai biết?" | `client.py`, `xero_pull.py` | khoảng 8 dòng |
| 11.7 | "5 phút chậm quá / tốn hạn mức quá?" | `hooks.py` | 1 dòng |
| 11.8 | Những chỗ **không** sửa được bằng vài dòng | — | nói thẳng |

### 11.1 Bỏ scope không dùng

```python
# HIỆN TẠI  setup/xero_connection.py:7-12
SCOPES = (
	"offline_access",
	"accounting.invoices",
	"accounting.contacts",
	"accounting.settings.read",
)
```

```python
# THAY BẰNG
SCOPES = (
	"offline_access",
	"accounting.invoices",
	"accounting.contacts",
)
```

Vì sao được: không lời gọi nào trong `client.py` đọc tài khoản hay mã thuế. Làm kèm: migrate, rồi **Connect lại** (token cũ vẫn mang scope cũ).

### 11.2 Gửi hóa đơn ở trạng thái nháp, để kế toán duyệt

```python
# HIỆN TẠI  lab_xero/mapping.py:39
"Status": "AUTHORISED",

# HIỆN TẠI  tasks/xero_sync.py:95-96
if invoice["status"] not in ("AUTHORISED", "PAID"):
	frappe.throw(_("The Xero invoice is not approved or paid; its state is outside this demo."))
```

```python
# THAY BẰNG
"Status": "DRAFT",

if invoice["status"] not in ("DRAFT", "SUBMITTED", "AUTHORISED", "PAID"):
	frappe.throw(_("The Xero invoice is in a state this integration does not handle."))
```

Đánh đổi: hóa đơn nháp chưa nhận tiền, chưa áp credit note được, nên hai cảnh demo phải có thêm bước "kế toán bấm Approve". Chiều về không cần sửa: `Xero Invoice Status` sẽ tự đổi từ `DRAFT` sang `AUTHORISED` ở lần kéo sau. Tên các trạng thái là của Xero (từ trí nhớ; đối chiếu tài liệu trước khi sửa).

### 11.3 Tìm contact theo id đã lưu, không theo mã

```python
# HIỆN TẠI  tasks/xero_sync.py:86-88
contact_id = client.find_contact(customer.name)
if customer.lab_xero_contact_id and customer.lab_xero_contact_id != contact_id:
	frappe.throw(_("The saved Xero contact does not match the Customer lookup."))
```

```python
# THAY BẰNG
# The id we stored is the link; the code is only how we find a contact we have not linked yet.
contact_id = customer.lab_xero_contact_id or client.find_contact(customer.name)
```

Được gì: rename bản ghi Customer không còn làm gãy đơn kế tiếp; bớt một lời gọi cho khách đã nối. Mất gì: bỏ một phép đối chiếu. Nếu contact đã bị xóa hoặc gộp bên Xero, lỗi sẽ đến từ Xero ở bước tạo hóa đơn (vẫn hiện trên đơn, vẫn chưa tạo gì sai). Việc **đẩy tên mới** sang Xero là phần khác, lớn hơn (11.8).

### 11.4 Tự thử lại: một job quét outbox

```python
# THÊM VÀO  tasks/xero_sync.py
MAX_ATTEMPTS = 5

def retry_unfinished() -> None:
	"""Queue again every outbox row that is not done and has attempts left. Run by the scheduler."""
	names = frappe.get_list(
		OUTBOX,
		filters={"status": ["in", ["Pending", "Failed"]], "attempts": ["<", MAX_ATTEMPTS]},
		pluck="name",
		limit_page_length=50,
	)
	for name in names:
		frappe.enqueue(
			"lab_core.tasks.xero_sync.process_outbox",
			queue="default",
			job_id=f"lab-xero-sync:{name}",
			deduplicate=True,
			outbox_name=name,
		)
```

```python
# THÊM VÀO  hooks.py, trong scheduler_events["cron"]
"*/10 * * * *": ["lab_core.tasks.xero_sync.retry_unfinished"],
```

Vì sao an toàn: nó chỉ xếp lại **cùng một job** đã có. Job đó tự kiểm `Done`, tự khóa dòng, và tự tìm hóa đơn trước khi tạo, nên xếp thừa cũng không sinh trùng. Chỗ còn thô: nó thử lại cả lỗi do luật (thuế, discount), vốn thử lại cũng vô ích, cho tới khi hết 5 lần. Bản tốt hơn cần một field "loại lỗi" trên outbox để chỉ thử lại `XeroBusy` và `XeroTimeout`; field mới là việc tạo trong Desk. Mỗi lần thử tốn ít nhất 2 lời gọi trong hạn mức.

### 11.5 Ghi mã HTTP vào lỗi quyền

```python
# HIỆN TẠI  integrations/xero/client.py:170-171
if response.status_code in (401, 403):
	raise XeroAuthLost("Xero authorization was refused; check access and reconnect Xero.")
```

```python
# THAY BẰNG
if response.status_code in (401, 403):
	raise XeroAuthLost(f"Xero authorization was refused (HTTP {response.status_code}); check access and reconnect Xero.")
```

Vì sao: 401 nghĩa là token không hợp lệ hoặc hết hạn; 403 nghĩa là token hợp lệ nhưng thiếu quyền (scope, tenant). Lỗi chưa rõ nguyên nhân hôm 12/10 không phân biệt được hai trường hợp này. Chỉ ghi mã số, không ghi nội dung câu trả lời hay header (có thể chứa token). Kiểu viết này đã có sẵn ở dòng 181 và 195 của cùng file.

### 11.6 Báo khi tổng hóa đơn bên Xero khác tổng đơn

```python
# HIỆN TẠI  integrations/xero/client.py:100-102  (trong get_invoices)
return [{"id": row["InvoiceID"], "number": row["InvoiceNumber"], "status": row["Status"],
	"amount_due": row["AmountDue"], "amount_paid": row["AmountPaid"],
	"amount_credited": row["AmountCredited"]} for row in rows]
```

```python
# THAY BẰNG: đọc thêm tổng của Xero
return [{"id": row["InvoiceID"], "number": row["InvoiceNumber"], "status": row["Status"],
	"total": row["Total"],
	"amount_due": row["AmountDue"], "amount_paid": row["AmountPaid"],
	"amount_credited": row["AmountCredited"]} for row in rows]
```

```python
# THÊM VÀO  tasks/xero_pull.py, trong _apply_invoices, sau order.db_set(...)
precision = order.precision("grand_total")
difference = flt(flt(invoice["total"], precision) - flt(order.grand_total, precision), precision)
if difference and invoice["status"] != "VOIDED":
	order.db_set("lab_xero_error", _("Xero invoice total differs from this order by {0}.").format(difference))
```

Cần thêm `from frappe import _` ở đầu file. Đây là **cảnh báo**, không tự sửa bên nào: đúng luật "mỗi con số một chủ". Chỗ phải cẩn thận: ô `Xero Error` hiện cũng là nơi ghi lỗi gửi đi; một field riêng cho "lệch" thì sạch hơn (field mới, tạo trong `setup/customizations.py`). Field `Total` của invoice là theo tài liệu Xero (từ trí nhớ; code của ta mới chỉ đọc `Total` của credit note).

### 11.7 Đổi nhịp kéo về

```python
# HIỆN TẠI  hooks.py
"cron": {"*/5 * * * *": ["lab_core.tasks.xero_pull.pull_changes"]},
```

| Nhịp | Lời gọi mỗi ngày (2 mỗi lượt) | Nhận xét |
|---|---|---|
| `*/5` (hiện tại) | khoảng 580 | hơn nửa hạn mức 1000 |
| `*/15` | khoảng 190 | chậm hơn, còn nhiều chỗ cho đơn |
| `*/2` | khoảng 1440 | **vượt hạn mức miễn phí** |

Đổi xong cần restart và **migrate** (Frappe tạo dòng lịch lúc migrate). Muốn nhanh hơn 5 phút thì câu trả lời đúng là webhook, không phải kéo dày hơn.

### 11.8 Những chỗ không sửa được bằng vài dòng

| Điểm yếu | Vì sao không phải vài dòng | Việc thật |
|---|---|---|
| Người bán (không phải System Manager) không submit được | là quyết định phân quyền, nằm trong DocType JSON và role, không nằm trong logic | cấp quyền cho role bán hàng trên `Lab Xero Outbox`; quyết định job chạy bằng ai. **Không** dùng `ignore_permissions` |
| Đẩy tên Customer mới sang Xero | cần lời gọi cập nhật contact (chưa có trong `client.py`), một loại việc mới trong outbox (hiện chỉ nhận Sales Order), và một `doc_events` cho Customer | khoảng 5 file; cần đối chiếu API của Xero |
| Credit note áp vào nhiều hóa đơn của ta | `xero_credit_note_id` đang unique: một credit note = một dòng | đổi cấu trúc: một dòng cho mỗi allocation |
| Void bên Xero nhưng đơn vẫn submitted | là luật nghiệp vụ chưa có ai quyết: tự cancel đơn, hay chỉ báo? | hỏi người làm nghiệp vụ trước khi code |
| Webhook thay cho polling | cần URL https công khai và kiểm chữ ký | hạ tầng, không phải code |
