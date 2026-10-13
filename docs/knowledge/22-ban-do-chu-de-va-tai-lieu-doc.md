# 22. Bản đồ chủ đề: danh sách muốn học so với kế hoạch gốc, chỗ thiếu, và tài liệu nên đọc

Viết ngày 2026-10-13, trước khi quay lại kế hoạch gốc (`plan/general/`). Đầu vào là danh sách nháp khoảng 60 mục của con người. File này trả lời ba câu: kế hoạch gốc đã phủ hết chưa; chỗ nào kế hoạch **không còn khớp** với dự án hiện tại; chủ đề nào **chưa có kiến thức viết sẵn** và nên đọc gì.

Nhãn như ở `00-README.md`: **[S]** đã mở trong phiên này, **[G]** từ trí nhớ, chưa đối chiếu. **Mọi URL trong file này là [G]**: viết từ trí nhớ, chưa mở để kiểm.

## 1. Kết luận

```text
 ~60 mục trong danh sách
      │
      ├── khoảng 50 mục  ĐÃ CÓ CHỖ trong các track A–M của plan/general/OVERVIEW.md      → học bằng thực hành theo track
      ├── 6 chỗ          KẾ HOẠCH KHÔNG CÒN KHỚP dự án (mục 3)                            → sửa kế hoạch trước khi bắt đầu
      ├── 7 chủ đề       CÓ TRACK nhưng CHƯA CÓ KIẾN THỨC viết sẵn (mục 4)                → đọc tài liệu trước khi thực hành
      ├── 5 thứ          CẦN TÀI KHOẢN NGOÀI và chưa có hướng dẫn (mục 5)                 → cần runbook, như đã làm với Xero
      └── 4 mục          CHƯA RÕ NGHĨA (mục 6)                                            → cần con người nói rõ
```

Kế hoạch gốc **đủ về phạm vi** (gần như mọi mục đều có track), **chưa đủ để bắt đầu ngay**: trạng thái của nó đã cũ sau đợt Xero, và các track I, I2, L chưa có một dòng kiến thức nào.

## Cách đọc (bắt đầu từ đây)

Không file nào bị dời chỗ. Pha Xero **giữ nguyên**; chỉ mở lại nó khi một track dẫn tới.

```text
 plan/general/      kế hoạch gốc: OVERVIEW.md (các track), TRACK-A.md        ← đang quay lại
 docs/knowledge/    kiến thức chung, đánh số 01–22, 90                        ← đọc theo bảng dưới
 docs/traces/       ghi chú trace có path:line (cram-sheet, rpc-and-document-api)
 docs/runbooks/     hướng dẫn cho con người chạy

 plan/done/xero/  docs/xero/  demo_xero/     PHA XERO: giữ nguyên, dùng làm ví dụ thật
```

**Ba bước chung, làm một lần (khoảng 40 phút):**

1. File này: mục 1 và mục 3 (kế hoạch lệch ở đâu).
2. `00-README.md`: bảng nhãn [S]/[T]/[I]/[G] và "Năm ý tưởng buộc mọi thứ lại với nhau".
3. `docs/traces/cram-sheet.md`: sáu cơ chế, mỗi cái một trang.

**Rồi theo từng track, đúng thứ tự của kế hoạch.** Mỗi track: đọc kiến thức đã viết → mở ví dụ thật → đối chiếu tài liệu gốc → thực hành → ghi trace.

| Thứ tự | Track | Đọc (theo đúng thứ tự) | Ví dụ thật đã có trong code | Tài liệu gốc |
|---|---|---|---|---|
| 1 | **A** Request, API | `plan/general/TRACK-A.md` → `traces/rpc-and-document-api.md` → `16` | `lab_core/api/xero.py`, `api/hello.py` | mục 7: REST và RPC, OpenAPI |
| 2 | **A2** Lỗi, response | `14` | `lab_core/errors.py`; lỗi của job Xero trên đơn (`demo_xero/06`, "Khi hỏng") | — |
| 3 | **B** Auth, session | cram-sheet mục 1 → `01` → `demo_xero/12` (OAuth theo ranh giới) | Connected App `xero` (`demo_xero/09`) | mục 7: token, OAuth provider, RFC 6749, OpenID Connect |
| 4 | **C** Phân quyền | cram-sheet mục 2 → `01` | điểm yếu "chỉ System Manager submit được" (`demo_xero/08`, mục 7 ①) | mục 7: user và phân quyền |
| 5 | **D** Hook, event | cram-sheet mục 3 → `02` → `19` → mục 4.4 | `lab_core/hooks.py`, `overrides/sales_order.py` | mục 7: hook |
| 6 | **E** Background job | cram-sheet mục 4 → `03` → `20` | `tasks/xero_sync.py`, `tasks/xero_pull.py` | mục 7: background job, RQ |
| 6 | **F** Realtime | cram-sheet mục 5 → `04` → `17` | — | mục 7: realtime, Socket.IO |
| 6 | **G** File | `06` | — | mục 5: Dropbox, object storage |
| 6 | **H** Mail, Jinja | `05` | — | mục 7: Jinja; mục 5: Gmail |
| 6 | **I**, **I2** Frontend | mục 4.1 → mục 4.2 (chưa có kiến thức viết sẵn) | `frontend/src/pages/` (mới có Hello) | trong mục 4.1, 4.2 |
| 6 | **J** Dữ liệu | cram-sheet mục 6 → `02` → `20` → `18` → mục 4.7 | outbox cùng transaction với đơn (`demo_xero/04`, mục 5) | trong mục 4.7 |
| 7 | **L** Hàng rào | mục 4.3 → 4.5 → 4.6 | cấu trúc code Xero (`demo_xero/05`) | trong mục 4.3–4.6 |
| xen kẽ | **M** Tối ưu | `15` | lịch kéo và hạn mức Xero (`demo_xero/03`) | — |
| cuối | tự kiểm | `90-self-check.md` | | |

Các track cùng số thứ tự 6 độc lập với nhau, làm theo thứ tự nào cũng được.

**Ba luật khi đọc:**
- Dòng mang nhãn **[G]** là từ trí nhớ: đối chiếu tài liệu gốc trước khi tin.
- Số file (`14`, `03`…) là file trong `docs/knowledge/`. Mục (`mục 4.4`) là mục trong chính file này.
- Đọc xong một track thì làm thí nghiệm của nó ngay; đừng đọc hết mọi thứ rồi mới làm.

## 2. Từng mục nằm ở track nào

Cột "Đã có" chỉ file kiến thức hoặc trace đã viết. "—" nghĩa là chưa có gì.

| Nhóm | Mục trong danh sách | Track | Đã có | Ghi chú |
|---|---|---|---|---|
| **Request, API** | RPC hay REST, công bố ra ngoài thế nào; Vue gọi RPC chứ không phải endpoint kiểu Spring; BFF; API docs, Swagger, Postman | A | `traces/rpc-and-document-api.md`, `16`, `plan/general/TRACK-A.md` | track A đang PAUSED, có Status riêng |
| | Response chung; middleware bắt exception theo request; xử lý lỗi một phần / toàn phần; "error handling really good" | A2 | `14` | kế hoạch Xero có phase PE (chưa làm) cùng ý này |
| **Auth** | Session, `sid`, stateful hay stateless, so với Tomcat HttpSession; đăng nhập bằng mật khẩu; access token trong Frappe; auth Vue → Frappe; user của background job | B | `traces/cram-sheet.md` mục 1, `01` | |
| | OAuth thuần; OAuth với Xero | B, K | `docs/xero/knowledge/oauth.md`, `demo_xero/02`, `demo_xero/12`, `11` | **đã xong** qua đợt Xero |
| | OAuth bằng Google | B | `01` (một dòng chỉ chỗ) | cần tài khoản ngoài (mục 5) |
| **Phân quyền** | Role permission; kiểm quyền ở từng lớp; buộc đổi dữ liệu qua operation; AI đảm bảo mỗi action có phần tử quyền; tìm `ignore_permissions` | C, L | `cram-sheet` mục 2, `01`, `AGENTS.md` B4 và B6, skill `red-flag-audit` | nội bộ perm level còn "Unknown" trong cram sheet |
| **Hook** | Hook chạy thế nào; override ERPNext, mọi chỗ có thể; CRM nối ERPNext; không dồn hook vào một file | D, L | `cram-sheet` mục 3, `02`, `19` | đã có một ví dụ thật: `lab_core/overrides/sales_order.py` |
| **Job** | Background job xuống tới process, OS; rủi ro khi một request xếp nhiều job; R-P2 (việc lâu đưa vào job) và bên gọi biết kết quả thế nào | E | `cram-sheet` mục 4, `03`, `19` | đã có ví dụ thật: `tasks/xero_sync.py`, `tasks/xero_pull.py` |
| **Realtime** | Realtime, SocketIO, pub/sub; chat Telegram | F | `cram-sheet` mục 5, `04` | Telegram cần tài khoản ngoài (mục 5) |
| **File** | Media lưu ở đâu, object storage; Dropbox sandbox | G | `06` (chỉ là bản đồ) | cần tài khoản ngoài (mục 5) |
| **Mail** | Email; Gmail; template (Jinja) | H | `05` | Gmail cần tài khoản ngoài (mục 5) |
| **Frontend** | TanStack, Vuetify; cache phía FE; tùy biến Desk tối thiểu; route Desk ↔ SPA | I, I2 | **—** | thiếu kiến thức (mục 4) |
| **Dữ liệu** | Transaction, rollback; DDL chỉ qua migrate + kiểm lệch; giảm áp lực database | J, M | `cram-sheet` mục 6, `02`, `15`, `18`, `20` | |
| **Xero** | Có cần Xero thật không, có hướng dẫn không; SAGA, Kafka | K | `docs/xero/`, `demo_xero/`, `12`, `13` | **đã xong phần chính**; Kafka đã hoãn vô thời hạn |
| **Hàng rào** | Lint cấu trúc cho cả Python + JS; OpenTelemetry; theo dõi sự cố; Clean Architecture; "không sinh DocType bằng code" | L | `AGENTS.md` B2, B4 | thiếu kiến thức (mục 4) |
| **Môi trường** | docker compose; cấu trúc code | runtime, `INIT.md` | `21`, `runbooks/dev-environment.md`, `demo_xero/05` | |

## 3. Sáu chỗ kế hoạch gốc không còn khớp dự án hiện tại

| # | Kế hoạch gốc ghi | Thực tế hôm nay | Cần làm trước khi bắt đầu |
|---|---|---|---|
| 1 | "Không dùng git cho code của chính chúng ta" (`OVERVIEW.md`, Decisions) | **[S]** repo đã có git, public, một nhánh `main` | sửa dòng đó; thêm luật "repo public: không đưa tài liệu riêng lên" |
| 2 | "Hiện chưa có công cụ lint" | **[S]** `lab_core/pyproject.toml` đã cấu hình `ruff` (lint + format, thụt bằng tab) | sửa dòng đó; quyết định mục 4.6 |
| 3 | Sprint là CURRENT; track K NOT STARTED | **[S]** sprint đã bị kế hoạch Xero dùng và gỡ một phần; K là `plan/done/xero/PLAN.md`, giai đoạn 1 đã demo | đánh dấu lại bảng "Where we are"; quyết định bỏ hay giữ sprint |
| 4 | `SPRINT.md` mô tả "Xero giả", đường sync Lab Note | **[S]** không còn trong code | coi `SPRINT.md` là lịch sử |
| 5 | Thứ tự: nền (A, A2, B, C, D) trước, K sau | K đã làm trước, nên code Xero **chưa có** response chung (A2), guard quyền (L), và chỉ System Manager submit được Sales Order | khi làm A2, C, L: dùng luồng Xero làm đối tượng áp dụng, không dựng ví dụ mới |
| 6 | Mục R-C1 của sổ tay tham khảo: pre-commit với black, flake8, isort, pyupgrade, codespell; prettier, eslint; chạy trong CI. Danh sách ghi "áp dụng ở giai đoạn đầu" | **[S]** không có `.pre-commit-config.yaml`, không có CI, không có eslint/prettier; đã có `ruff` (thay được black, flake8, isort, pyupgrade **[G]**) | chưa track nào nhận việc này. Cần quyết định: theo đúng R-C1, hay dùng `ruff` + eslint. Cài công cụ là việc của con người |

Hai chỗ `AGENTS.md` cũng đang lệch với cách đã làm (ghi trong `plan/overview.md`): mục B5 đòi test cho mỗi endpoint; mục B2a ghi handler ở `<domain>/events/` trong khi code đặt ở `overrides/`. Quay lại kế hoạch gốc thì phải chọn một.

## 4. Bảy chủ đề chưa có kiến thức viết sẵn

Mỗi chủ đề: nó là gì, nó đứng ở đâu trong dự án này, đọc gì trước, thực hành ở track nào.

### 4.1 TanStack Query và Pinia Colada (lớp lấy và cache dữ liệu phía trình duyệt)

- **Là gì [G]:** thư viện giữ dữ liệu lấy từ server trong bộ nhớ trình duyệt, theo khóa; tự biết dữ liệu cũ, tự gọi lại, gộp request trùng. Đây là câu trả lời cho mục "cache ở FE chứ không phải Redis".
- **Trong dự án [S]:** đã cài `@tanstack/vue-query` 5.104.1 và `@pinia/colada` 1.4.8 (`frontend/package.json`); đã có thư mục `pages/colada`, `pages/tanstack`, `pages/together`; mới có các trang Hello.
- **Đọc:** https://tanstack.com/query/latest/docs/framework/vue/overview · https://pinia-colada.esm.dev/ · https://pinia.vuejs.org/
- **Thực hành:** track I, rồi I2 (một màn hình xây hai lần, bốn kịch bản).

### 4.2 Vuetify, Vue Router, và ranh giới Desk ↔ SPA

- **Là gì [G]:** Vuetify là bộ component; Vue Router điều hướng trong SPA. Desk là giao diện có sẵn của Frappe, một ứng dụng khác chạy cùng site.
- **Trong dự án [S]:** `vuetify` 4.2.4, `vue-router` 5.4.0; SPA phục vụ tại `/lab`. Câu hỏi chưa ai trả lời: hai bên dùng chung session thế nào, chuyển trang qua lại ra sao.
- **Đọc:** https://vuetifyjs.com/en/getting-started/installation/ · https://router.vuejs.org/guide/ · https://docs.frappe.io/framework/user/en/desk
- **Thực hành:** track I. Tham khảo cách Frappe CRM làm (`apps/crm/frontend/`), vì nó cùng hình dạng.

### 4.3 Clean Architecture và DDD trong một app Frappe

- **Là gì [G]:** chia code thành lớp, lớp trong không biết lớp ngoài: nghiệp vụ (domain) ở giữa, use case quanh nó, framework và hạ tầng ở ngoài cùng. DDD: chia theo miền nghiệp vụ, mỗi miền tự chứa.
- **Trong dự án [S]:** `AGENTS.md` B4 đã ghi hướng `interface → application → domain`, `infrastructure` gọi từ `application`, "khi phase 5 dựng xong". Code Xero hiện tại đã gần hình đó: `api/` + `overrides/` (interface), `tasks/` (application), `lab_xero/mapping.py` (domain), `integrations/xero/` (infrastructure). Chỗ khó thật: DocType của Frappe vừa là dữ liệu vừa là form vừa là quyền, nên "domain không import Frappe" chỉ làm được một phần.
- **Đọc:** https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html · https://martinfowler.com/bliki/DomainDrivenDesign.html
- **Thực hành:** track L. Dùng luồng Xero làm ví dụ, không viết ví dụ mới.

### 4.4 Event-driven (hướng sự kiện), bản thuần

- **Là gì [G]:** một bên phát "đã xảy ra việc X", các bên khác tự phản ứng; bên phát không biết ai nghe. Ba mức: gọi hàm trong cùng process (không bền), hàng đợi (bền, một người nhận), log sự kiện kiểu Kafka (bền, nhiều người nhận, đọc lại được).
- **Trong dự án:** Frappe có bốn thứ mang dáng sự kiện, không cái nào là broker: `doc_events` (trong cùng transaction), `frappe.enqueue` qua Redis (hàng đợi), `publish_realtime` (Redis pub/sub, không bền), DocType `Webhook` (gọi HTTP ra ngoài). Outbox của ta là cách làm cho sự kiện **bền** mà không cần broker. Kafka/Redpanda đã hoãn vô thời hạn.
- **Đọc:** https://martinfowler.com/articles/201701-event-driven.html · https://microservices.io/patterns/data/transactional-outbox.html · https://microservices.io/patterns/data/saga.html · https://redis.io/docs/latest/develop/interact/pubsub/
- **Đã có:** `02`, `03`, `04`, `13`, `17`, `20`. Thiếu đúng một trang nối bốn thứ trên lại và so với broker.
- **Thực hành:** track D, E, F; không cần thêm container.

### 4.5 OpenTelemetry và theo dõi sự cố

- **Là gì [G]:** chuẩn mở để thu **trace** (một request đi qua những bước nào, mỗi bước bao lâu), **metric** và **log**, gửi về một nơi xem chung. Theo dõi sự cố (kiểu Sentry) gom lỗi kèm ngữ cảnh.
- **Trong dự án:** chưa có gì. Frappe có sẵn Error Log và Recorder (`15`). Một nơi xem trace thường là thêm container, trong khi Goal 4 (cụm container cho log) đã hoãn. Điều nên học trước là **request id xuyên suốt** từ request sang job (track A2 đã ghi "dòng log có request id").
- **Đọc:** https://opentelemetry.io/docs/concepts/ · https://opentelemetry.io/docs/languages/python/ · https://docs.sentry.io/platforms/python/
- **Thực hành:** track L, sau A2. Bắt đầu bằng xuất trace ra console, chưa cần hạ tầng.

### 4.6 pre-commit, lint và "eslint cho cả cấu trúc code"

- **Là gì [G]:** pre-commit chạy các bộ kiểm trước mỗi commit; CI chạy lại đúng cấu hình đó. Lint thường kiểm từng dòng; **lint cấu trúc** kiểm luật giữa các thư mục, ví dụ "ngoài `integrations/xero/` không ai được `import requests`".
- **Trong dự án [S]:** có `ruff` trong `pyproject.toml`; chưa có pre-commit, CI, eslint, prettier. Các luật cấu trúc hiện chỉ nằm bằng chữ trong `AGENTS.md` B4, B6 và được kiểm bằng skill `red-flag-audit` (do AI đọc), chưa có công cụ nào tự chặn.
- **Đọc:** https://pre-commit.com/ · https://docs.astral.sh/ruff/ · https://eslint.org/docs/latest/ · https://prettier.io/docs/ · https://import-linter.readthedocs.io/ (luật import giữa các package Python) · https://github.com/sverweij/dependency-cruiser (tương tự cho JS)
- **Thực hành:** track L. Xem mục 3, dòng 6: cần một quyết định trước.

**Việc này để làm gì.** Dự án có nhiều luật viết bằng chữ (`AGENTS.md` B4, B6): không `ignore_permissions`, không `frappe.db.commit()` ngoài `tasks/`, chỉ `integrations/` được gọi HTTP, endpoint phải có `methods=[...]`… Hiện chỉ có người review và AI nhớ các luật đó. Mục tiêu: **máy tự chặn** trước khi code vào repo, cho cả Python lẫn JS, giống eslint làm với JS.

**Đề xuất bộ công cụ [G]** (chưa cài, chưa thử; tên và khả năng viết từ trí nhớ, con người kiểm trang chính thức rồi mới cài):

| Việc cần chặn | Công cụ | Vì sao chọn | Ví dụ luật của dự án |
|---|---|---|---|
| Kiểu viết, import, lỗi Python thường gặp | **ruff** (đã cấu hình) | một công cụ thay black, flake8, isort, pyupgrade | — |
| Cấm gọi một hàm cụ thể, trừ vài thư mục | **ruff**, luật `banned-api` + `per-file-ignores` | không cần cài thêm gì | cấm `requests` ngoài `integrations/`; cấm `datetime.datetime.now` |
| Mẫu code nguy hiểm, **cả Python lẫn JS** | **semgrep** (luật tự viết bằng YAML) | đây là thứ gần "eslint cho cả dự án" nhất; Frappe có công bố bộ luật semgrep riêng | `ignore_permissions=True`; `frappe.set_user("Administrator")`; `@frappe.whitelist()` thiếu `methods=`; `allow_guest=True`; f-string trong `_()`; `frappe.db.sql(` |
| Luật giữa các thư mục Python (lớp nào được import lớp nào) | **import-linter** | khai báo "hợp đồng" giữa các package | `api/` và `overrides/` không import `integrations/`; `lab_xero/` không import `tasks/` |
| Kiểu viết và lỗi JS/Vue | **eslint** + `eslint-plugin-vue`, **prettier** | chuẩn chung của frontend | — |
| Luật giữa các thư mục frontend | **dependency-cruiser** (hoặc `eslint-plugin-boundaries`) | giống import-linter, cho JS | `pages/colada/` không import TanStack; `pages/tanstack/` không import Pinia Colada |
| Chạy tất cả trước mỗi commit | **pre-commit** | một file cấu hình, CI chạy lại đúng file đó | — |
| Lỗi chính tả trong code và tài liệu | codespell (tùy chọn) | có trong R-C1 | — |

```text
 gõ "git commit"
      │
      ▼
 pre-commit ──► ruff (kiểu viết + hàm bị cấm) ──► semgrep (mẫu nguy hiểm, Py + JS) ──► import-linter (lớp Python)
            ──► eslint + prettier (JS/Vue)     ──► dependency-cruiser (lớp frontend)
      │
      ├── tất cả qua  → commit được
      └── một cái hỏng → commit bị chặn, in ra file:dòng và tên luật
```

**Thứ tự nên làm, nhỏ trước:**

1. pre-commit + ruff (đã có cấu hình): gần như không tốn công.
2. semgrep với 8–10 luật chép từ `AGENTS.md` B6: chặn được phần lớn "cờ đỏ".
3. eslint + prettier khi bắt đầu viết trang SPA thật (track I).
4. import-linter và dependency-cruiser khi cấu trúc lớp đã ổn (track L).

So với R-C1 của sổ tay tham khảo: R-C1 liệt kê black, flake8, isort, pyupgrade riêng lẻ; ruff làm cùng việc trong một công cụ và dự án đã chọn nó. Nếu dự án sắp tới bắt buộc đúng danh sách R-C1 thì theo R-C1; còn ở lab này, ruff là đủ.

Skill `red-flag-audit` (AI đọc code) vẫn giữ làm lớp thứ hai: nó bắt được thứ mà mẫu cú pháp không bắt được, ví dụ "endpoint có kiểm quyền nhưng kiểm sai tài liệu".

Tài liệu: https://semgrep.dev/docs/ · https://github.com/frappe/semgrep-rules · https://docs.astral.sh/ruff/rules/banned-api/ · https://import-linter.readthedocs.io/ · https://eslint.vuejs.org/ · https://github.com/sverweij/dependency-cruiser · https://pre-commit.com/

### 4.7 Kiểm lệch giữa code và database (DDL chỉ qua migrate)

- **Là gì:** mọi thay đổi cấu trúc bảng phải đến từ DocType JSON + `bench migrate`. "Lệch" là khi database có thứ code không có (ai đó sửa tay, hoặc Customize Form để lại Property Setter chỉ trong database).
- **Trong dự án:** luật đã có (`AGENTS.md` A4, B3). Chưa có cách **phát hiện** vi phạm. Custom Field của ta tạo bằng code (`setup/customizations.py`), đó là mẫu đúng.
- **Đọc:** https://docs.frappe.io/framework/user/en/database-migrations · https://docs.frappe.io/framework/user/en/guides/app-development/how-to-create-custom-fields-during-app-installation
- **Thực hành:** track J. Việc cụ thể: một lệnh chỉ đọc so danh sách Custom Field / Property Setter trong database với thứ code khai báo.

## 5. Năm thứ cần tài khoản ngoài, chưa có hướng dẫn

Với Xero, phần khó nhất không phải code mà là: đăng ký app, redirect URI, secret, tài khoản thử. Năm mục dưới đây cùng dạng đó. Tất cả có bậc miễn phí **[G]**; cần kiểm lại trước khi làm.

| Mục trong danh sách | Cần gì bên ngoài | Chỗ Frappe đã có sẵn [G] | Đọc | Track |
|---|---|---|---|---|
| Đăng nhập bằng Google | một OAuth client trong Google Cloud Console; redirect URI `localhost` | DocType `Social Login Key`; callback ở `frappe/integrations/oauth2_logins.py` (**[S]** qua `01`) | https://developers.google.com/identity/protocols/oauth2/web-server · https://docs.frappe.io/framework/user/en/guides/integration/social_login_key | B |
| Gmail | tài khoản Google; app password, hoặc OAuth cho IMAP/SMTP | `Email Account`, `Email Queue` (`05`) | https://developers.google.com/gmail/imap/xoauth2-protocol · https://docs.frappe.io/framework/user/en/email | H |
| Chat Telegram | một bot (tạo qua BotFather), token của bot | không có sẵn; là một lời gọi HTTP ra ngoài, phải chạy trong job (`04`, mục Telegram) | https://core.telegram.org/bots/api | F |
| Dropbox sandbox | một app trong Dropbox App Console | `06` ghi: không có trong `file.py` của core | https://www.dropbox.com/developers/documentation/http/overview | G |
| Object storage | một dịch vụ kiểu S3. Chạy local thì là **thêm một container**, cần con người quyết | không có trong core, theo `06` | https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html | G |

Bài học mang từ Xero sang: redirect URI phải là `https` hoặc đúng `http://localhost`; secret chỉ nằm trong site config; viết runbook **trước** khi làm; không dán Error Log ra ngoài.

Nhận chiều vào từ bên ngoài (Telegram gửi tin tới ta, webhook) cần một URL công khai, mà lab không có (`17`). Hướng đi đã dùng với Xero: ta chủ động hỏi định kỳ.

## 6. Bốn mục chưa rõ nghĩa

| Mục | Có thể hiểu là | Tạm hiểu |
|---|---|---|
| "push sub feature in the Frappe" | (a) pub/sub: phát và nghe sự kiện; (b) push notification tới trình duyệt/điện thoại | (a): đã có `04` và mục 4.4 |
| "custome build template UI" | (a) Jinja: print format, trang web, mẫu email; (b) trang SPA dựng bằng Vuetify; (c) tùy biến form Desk | (a) + (c): track H và I |
| "Try integrate the API docs" | (a) sinh trang Swagger từ endpoint của ta; (b) chỉ dùng Postman để gọi thử | (a): `16` đã phân tích, chưa có code |
| "tracking accident as much as possible but not slow down QA" | (a) gom lỗi kiểu Sentry; (b) chặn thao tác nguy hiểm trong môi trường thử | (a): mục 4.5. (b) là luật vận hành, chưa có chỗ trong kế hoạch |

## 7. Tài liệu gốc nên đọc cho các track đã có kiến thức

Để đối chiếu những gì đã trace với lời của chính tác giả. Tất cả **[G]**.

| Chủ đề | URL |
|---|---|
| Frappe: hook | https://docs.frappe.io/framework/user/en/python-api/hooks |
| Frappe: REST và RPC | https://docs.frappe.io/framework/user/en/api/rest |
| Frappe: token, API key | https://docs.frappe.io/framework/user/en/guides/integration/rest_api/token_based_authentication |
| Frappe làm OAuth provider | https://docs.frappe.io/framework/user/en/guides/integration/how_to_set_up_oauth |
| Frappe: user và phân quyền | https://docs.frappe.io/framework/user/en/basics/users-and-permissions |
| Frappe: background job | https://docs.frappe.io/framework/user/en/api/background_jobs |
| Frappe: realtime | https://docs.frappe.io/framework/user/en/api/realtime |
| Frappe: Jinja | https://docs.frappe.io/framework/user/en/api/jinja |
| RQ (thư viện hàng đợi Frappe dùng) | https://python-rq.org/docs/ |
| Socket.IO | https://socket.io/docs/v4/ |
| OAuth 2.0 (RFC 6749), PKCE (RFC 7636) | https://datatracker.ietf.org/doc/html/rfc6749 · https://datatracker.ietf.org/doc/html/rfc7636 |
| OpenID Connect (đăng nhập bằng bên thứ ba) | https://openid.net/specs/openid-connect-core-1_0.html |
| Xero: luồng OAuth, scope, Accounting API | https://developer.xero.com/documentation/guides/oauth2/auth-flow · https://developer.xero.com/documentation/guides/oauth2/scopes · https://developer.xero.com/documentation/api/accounting/overview |
| OpenAPI, Postman | https://spec.openapis.org/oas/latest.html · https://learning.postman.com/docs/ |
| Docker Compose | https://docs.docker.com/compose/ |

Trang tài liệu của Frappe đã đổi địa chỉ vài lần; nếu một link hỏng, tìm cùng tiêu đề tại https://docs.frappe.io/framework. Source trên đĩa (`frappe-bench/apps/frappe/`) luôn là bản đúng cho phiên bản 16.51.0.

## 8. Thứ tự gợi ý khi quay lại

```text
 0. Sửa kế hoạch cho khớp (mục 3)  ──►  1. A (đang dở) ─► A2 ─► B ─► C ─► D     nền: áp ngay lên luồng Xero có sẵn
                                              │
                                              ├──►  E, F, G, H, I, J            song song được; G, H, F cần runbook tài khoản ngoài trước (mục 5)
                                              │
                                              └──►  L (cần quyết định 4.6)  ─►  I2
```

Việc đọc cho mục 4 làm được ngay, song song với mọi thứ, vì không đụng file nào.
