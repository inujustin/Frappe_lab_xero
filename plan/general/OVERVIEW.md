# Frappe lab: tổng quan

Mục tiêu, các quyết định và các track (nhánh công việc). Cấu trúc và bộ khung ban đầu nằm trong `INIT.md`. Con người tự chia nhỏ công việc và điều khiển các agent (trợ lý AI); ở đây không có gì là danh sách bước.

## Where we are (Hiện trạng)
Ghi lại cái gì đã xong và cái gì kế tiếp, dùng khi con người hoặc agent cần nhìn toàn cảnh.

| Phần | Trạng thái | Chi tiết |
|---|---|---|
| Runtime (môi trường chạy) của lab: một lệnh, tự cài đặt | DONE (xong) | `docs/runbooks/dev-environment.md` |
| Bộ khung: `lab_core`, module "Lab Xero", DocType "Lab Note", endpoint hello kèm test, vỏ SPA tại `/lab` | DONE (xong) | `INIT.md` |
| **Sprint: một tính năng đi qua mọi cơ chế, khoảng hai giờ** | **CURRENT (đang làm)** | `SPRINT.md` |
| Track A: request và API | PAUSED (tạm dừng) trong lúc sprint | `TRACK-A.md`, mục Status |
| Track A2, B, C, D | NOT STARTED (chưa bắt đầu) | làm tiếp sau A, theo đúng thứ tự đó |
| Mọi track còn lại | NOT STARTED (chưa bắt đầu) | xem mục Order bên dưới |

Chỉ cập nhật khi con người yêu cầu, hoặc nói một phần đã xong: chỉ sửa đúng dòng đó.

## Goal (Mục tiêu)
1. Hiểu Frappe v16 bằng cách trace (lần theo) code thật, mỗi lần một cơ chế (`docs/traces/`).
2. Demo tích hợp ERPNext ↔ Xero (OAuth 2.0, sync (đồng bộ), idempotency (gọi lặp lại vẫn chỉ ra một kết quả)).
3. Thử các ý tưởng kiến trúc: Clean Architecture + DDD trong một app Frappe, một response shape (dạng phản hồi) duy nhất, guard (lớp chặn kiểm tra) dùng chung, structural lint (kiểm tra cấu trúc code tự động), một pattern mang tính transaction (giao dịch) cho các lần gọi Xero.
4. Về sau: một cụm container cho log và trace, và SAGA (chuỗi bước có bù trừ) giữa các service.

## Decisions (Các quyết định)
- **Một lệnh:** `docker compose up --build -d` chạy từ thư mục gốc của dự án, dù từ thư mục rỗng hay từ một lab đang chạy (`docs/runbooks/dev-environment.md`). Lệnh được gõ trên host (máy chủ chứa container, tức máy của bạn); lệnh bench có dạng `docker compose exec frappe bench ...`.
- **Runtime:** container dev của Frappe, MariaDB, hai Redis. `frappe-bench/` được chia sẻ với host ở cùng một đường dẫn tuyệt đối; môi trường Python chỉ tồn tại trong Docker. Phiên bản: `docker/versions.env`.
- **Frontend chạy trên host:** các package, Vite dev server, build và test frontend chạy bằng Node và yarn của host trong `lab_core/frontend/`; thư mục này được chia sẻ, nên container phục vụ đúng thứ host build ra. Phiên bản major của Node trên host phải theo `NODE_VERSION` trong `docker/versions.env`. Python và bench vẫn ở trong container.
- **Không dùng git** cho code của chính chúng ta. Hiện chưa có công cụ lint.
- **Agent:** chỉ viết file; con người chạy mọi thứ (`AGENTS.md`). DocType (kiểu tài liệu/bảng dữ liệu của Frappe) được tạo trong Desk (giao diện quản trị của Frappe), agent không bao giờ tự viết.
- **Một app:** mọi thứ được xây trong `lab_core`, để thấy các phần chạy cùng nhau chứ không chỉ từng phần riêng lẻ. Bố cục ở bên dưới.
- **Site:** `lab.localhost`, cổng 8000 và 9000.

## One app: `lab_core` (Một app)
Cùng hình dạng với Frappe CRM, vốn là một app chứa backend, frontend Vue, các integration (tích hợp) và override (ghi đè hành vi) (`apps/crm/crm/`, `apps/crm/frontend/`, `apps/crm/crm/hooks.py:71`).

```text
frappe-bench/apps/lab_core/
├── frontend/                  MỘT SPA Vue + Vuetify, phục vụ tại /lab
│   └── src/pages/colada/      các trang lấy dữ liệu bằng Pinia Colada
│       src/pages/tanstack/    cũng các trang đó nhưng dùng TanStack Query
│       src/pages/together/    cả hai trên một trang, có chủ đích
└── lab_core/
    ├── hooks.py               chỉ để đấu nối (wiring)
    ├── api/                   các endpoint BFF cho SPA
    ├── lab_core/              module "Lab Core": các DocType thử nghiệm (tạo trong Desk)
    ├── lab_xero/              module "Lab Xero": cấu hình Xero, các DocType outbox (tạo trong Desk)
    ├── integrations/xero/     Xero client và OAuth, không có code xử lý request của Frappe
    ├── overrides/             chỉ chứa thay đổi hành vi của Frappe, ERPNext, CRM (code của ta thì sửa trực tiếp)
    ├── tasks/                 background job (việc chạy nền)
    └── www/lab.html           trang nạp SPA
```

Kết hợp, không ràng buộc:
- **Vuetify** là bộ UI; **Pinia Colada** và **TanStack Query** đều là data layer (lớp lấy và cache dữ liệu từ server). Mỗi cái giữ client, cache và devtools riêng, và có các trang riêng gọi vào cùng những endpoint, nên có thể so sánh ngang hàng. Cần xác nhận lúc cài đặt: hai plugin sống chung được trong một app Vue.
- **Xero** là một module cộng với một package `integrations/` bên trong app: có DocType, job và client riêng, không phần nào khác import nội bộ của nó.
- Domain (miền nghiệp vụ) là các **module** của Frappe (`modules.txt`), không phải các app riêng. Một module được tạo trong Desk (Module Def), giống như một DocType.

Chỗ các phần gặp nhau, tức là thứ mà "một app" cho phép bạn quan sát:
1. Trang SPA → endpoint BFF (Backend For Frontend: backend viết riêng cho giao diện) trong `api/` → code domain → DocType.
2. Document event (sự kiện của tài liệu) → background job trong `tasks/` → Xero client → dòng outbox (hộp thư đi: bảng ghi việc cần gửi ra ngoài).
3. Tiến độ của job → realtime event (sự kiện thời gian thực) → SPA, nơi mỗi data layer tự làm mới cache của mình.
4. Form trong Desk ↔ trang SPA: routing (định tuyến) và một session (phiên đăng nhập) dùng chung.
5. `lab_core` → ERPNext và CRM thông qua `overrides/` và hook (điểm móc mở rộng của Frappe).

Cái giá của một app: Xero không thể cài hoặc gỡ riêng, và `hooks.py` là một file duy nhất, nên hai phiên làm việc không được sửa nó cùng lúc.

## Tracks (Các track)
Mỗi track là một nhóm câu hỏi cần trả lời bằng cách trace, sau đó là một demo nhỏ chứng minh câu trả lời.

| Track | Câu hỏi |
|---|---|
| A. Request và API | Đường đi của một request từ điểm vào WSGI (chuẩn giao tiếp web server ↔ ứng dụng Python) đến response. `/api/method` (RPC) so với `/api/resource` so với `/api/v2/document`: dùng cái nào, công bố cái nào. `frappe.call` gửi đi những gì. Dạng của response và của lỗi được dựng ở đâu. Một exception handler (bộ xử lý ngoại lệ) theo từng request thì gắn vào đâu. Tài liệu API, Swagger/Postman, một endpoint BFF. **Endpoint kiểu Spring Boot:** xây một resource (list, get, create, update, delete) theo cách một `@RestController` sẽ làm: endpoint mỏng trong `api/`, logic trong một hàm service, truy cập dữ liệu nằm phía sau nó, input và output có kiểu, đúng verb (động từ HTTP) và status code (mã trạng thái) cho từng trường hợp. Rồi trả lời: các route `/api` cố định của Frappe cho phép điều này đến mức nào, và một đường dẫn tùy biến như `/api/lab/customers/42` có làm được mà không đụng vào core (lõi framework) hay không. |
| A2. Lỗi và response | Vì sao mọi lỗi API đều hiện traceback (vết ngăn xếp lỗi) của Python trong dev server, trong response và trong log, và ở production client nhận được gì. Vì sao `/api/method` và `/api/v2` trả lỗi theo hai dạng khác nhau. Một exception trở thành status code như thế nào. Xây: các lớp exception của riêng ta kèm status code; một dạng lỗi và một dạng thành công cho mọi endpoint của `lab_core`, áp dụng ở một chỗ duy nhất để không endpoint nào phải lặp try/except; dòng log ngắn, dễ đọc, có request id; SPA hiển thị lỗi ở một chỗ. |
| B. Auth và session | Đăng nhập bằng mật khẩu, từng bước. Cookie `sid`, session nằm ở đâu, hết hạn, CSRF (giả mạo request từ trang khác). Stateful (server giữ trạng thái), stateless (không giữ) hay lai, so với `HttpSession` của Tomcat. API key, OAuth bearer và access token. Một background job lấy user của nó từ đâu. Auth Vue → Frappe. Đăng nhập Google. |
| C. Permissions (phân quyền) | Role permission (quyền theo vai trò), perm level (mức quyền theo field), User Permission (giới hạn theo bản ghi cho từng user), hook `has_permission` và hook query-condition (điều kiện thêm vào câu truy vấn). Việc kiểm tra diễn ra ở đâu trong mỗi lớp. `ignore_permissions` bỏ qua những gì. Buộc thay đổi phải đi qua operation (thao tác nghiệp vụ) thay vì sửa trực tiếp. |
| D. Hook và event | `hooks.py` được nạp và gộp thế nào. Thứ tự của `doc_events`. Override class và override endpoint. Mọi chỗ có thể tùy biến ERPNext. CRM nói chuyện với ERPNext ra sao. |
| E. Background job | `enqueue` (đưa vào hàng đợi) → Redis → worker (tiến trình xử lý job), xuống tới mức process. Enqueue so với commit. Nhiều job trong một request. Bên gọi biết kết quả bằng cách nào. |
| F. Realtime | `publish_realtime` → Redis → socketio → trình duyệt, auth của socket. Tiến độ job trực tiếp. Cầu nối Telegram. |
| G. File | DocType File, public so với private, byte được ghi vào đâu, object storage (lưu trữ đối tượng kiểu S3), sandbox của Dropbox. |
| H. Mail và Jinja | Email Account, Email Queue, Notification. Jinja (ngôn ngữ template) trong print format, trang web, email. |
| I. Frontend | Routing Desk ↔ SPA, tùy biến Desk ở mức tối thiểu, dữ liệu phía client được cache ở đâu, TanStack so với Pinia Colada. |
| I2. So sánh data layer | Pinia Colada so với TanStack Query, lựa chọn mà dự án sắp tới còn để ngỏ (`docs/refer/`, "Cần thử"). Một màn hình thật (chi tiết Quotation kèm danh sách của nó) được xây hai lần trên cùng endpoint, rồi chạy bốn kịch bản của sổ tay trên mỗi bản: user không có quyền nhận 403; hai tab cùng sửa và submit một tài liệu; bấm nhanh qua năm tài liệu; submit rồi quay lại danh sách. Ghi lại theo từng thư viện và kịch bản: có chạy đúng mà không cần code riêng cho màn hình không, đã gửi bao nhiêu request, màn hình cần bao nhiêu code, thêm bao nhiêu vào bundle (gói JS build ra), tài liệu và devtools rõ đến đâu. Kết quả: một ghi chú quyết định trong `docs/adr/` có bảng và lựa chọn. |
| J. Dữ liệu | Transaction của request và rollback (hoàn tác), DDL (lệnh đổi cấu trúc bảng) chỉ qua migrate cộng với kiểm tra drift (lệch giữa code và database), caching và áp lực lên DB. |
| K. Xero | OAuth với Xero, sync Customer/Invoice/Payment, idempotency, outbox. |
| L. Guardrails (hàng rào an toàn) | Permission guard, tách hook theo domain, structural lint, OpenTelemetry (chuẩn thu thập trace/metric), theo dõi sự cố. |
| M. Tối ưu và các kiểu API ít gặp | Phục vụ mục tiêu chính (tích hợp Xero), không phải mục tiêu riêng. Frappe có gì thay cho GraphQL và gRPC, và khi nào chúng mới đáng dùng. Các tầng cache, đọc/ghi database không N+1, bulk, index, read replica, rate limit. Đo bằng Recorder trước khi tối ưu. Với Xero: batch write, `If-Modified-Since`, đồng hồ rate limit dùng chung, cache dữ liệu tham chiếu. Bản đồ: `docs/knowledge/15-performance-and-api-styles.md`. |

## Order (Thứ tự)
1. Dựng lab, `lab_core` có trên site, vỏ SPA tại `/lab` (`docs/runbooks/new-apps.md`).
2. A, rồi A2, B, C, D: phần nền móng. Mọi thứ về sau đều dựa vào chúng. A2 đi ngay sau A, để mọi demo sau đó đã có sẵn lỗi và response gọn gàng.
3. E, F, G, H, I, J: thứ tự nào cũng được, độc lập với nhau. I2 đi sau C và I, vì nó cần phân quyền thật và SPA đã sẵn sàng.
4. L: kiến trúc và guardrails trong `lab_core`, xây trên những gì mục 2 và 3 đã cho thấy.
5. K: Xero, đặt trên E (job), B (OAuth) và L (outbox, guard).
6. Observability (khả năng quan sát hệ thống) và phần so sánh SAGA phân tán. Trước đó, SAGA kiểu orchestration (điều phối tập trung) trên outbox được làm ngay trong K, khi có luồng hai bước đầu tiên: `docs/knowledge/13-saga.md`.
7. M: làm xen kẽ, từng mục một, khi một luồng thật cho thấy cần (đo trước). Phần của Xero trong M đi cùng K.

Ghi chú đọc kèm cho A2 (dạng lỗi thống nhất, hook `after_request`): `docs/knowledge/14-error-handling.md`. Cho phần "API docs, Swagger/Postman" của A: `docs/knowledge/16-api-docs-swagger.md`.

## The Xero transaction idea (Ý tưởng transaction cho Xero)
Frappe bọc một request trong một DB transaction (cần xác nhận ở track A); một lần gọi Xero không thể tham gia vào transaction đó. Vì vậy:
1. Thay đổi nghiệp vụ và một **dòng outbox** được ghi trong cùng một transaction.
2. Một background job gửi dòng đó sang Xero kèm idempotency key (khóa chống gửi trùng) và lưu lại Xero ID.
3. Khi kết quả không rõ, job hỏi Xero xem bản ghi đã tồn tại chưa; câu trả lời của Xero là thứ quyết định.
4. Một bước thất bại hẳn thì chạy **compensation** (bù trừ) của nó (void (hủy) invoice bên Xero, hoặc cancel tài liệu phía local).
5. Được gói lại thành một decorator, ví dụ `@xero_atomic(compensate=...)`.

Về sau, chạy lại đúng các kịch bản lỗi đó với một broker (trung gian tin nhắn: Redpanda/Kafka) để so sánh: crash trước commit, crash sau commit, Xero timeout nhưng phía họ đã thành công, bị từ chối, job trùng, compensation thất bại.
