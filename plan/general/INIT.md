# Init plan: bộ khung trước khi làm tính năng

Những thứ phải có trước khi bắt đầu trace (lần theo code) và làm tính năng. File này mô tả cấu trúc, là thứ ổn định; nội dung các file thì sẽ thay đổi. Đây là các phát biểu, không phải checklist: con người quyết định yêu cầu cái gì và khi nào.

## Hệ thống
```text
Trình duyệt
  ├─ Desk  (/app/...)        UI của chính Frappe: DocType được tạo ở đây
  └─ SPA   (/lab/...)        app Vue của chúng ta
        │  HTTP, một session cookie dùng cho cả hai
        ▼
frappe container ── web (8000) ──┬── MariaDB        dữ liệu
                 ── socketio (9000)  ├── redis-cache   cache
                 ── worker ──────────┼── redis-queue   job + realtime event
                 ── scheduler        └── Xero API      chỉ gọi từ worker
```

## App
```text
frappe-bench/apps/lab_core/
├── frontend/                  một SPA Vue + Vuetify, build vào thư mục public của app
│   └── src/
│       ├── main               khởi động app: router, Vuetify, cả hai plugin data layer
│       ├── api/               nơi duy nhất gọi backend
│       ├── pages/colada/      các trang Pinia Colada
│       ├── pages/tanstack/    các trang TanStack Query
│       └── pages/together/    cả hai, có chủ đích
└── lab_core/
    ├── hooks.py               chỉ đấu nối: route, event, override, scheduler
    ├── www/lab.html           phục vụ SPA; route rule gửi /lab/<bất kỳ> về đây
    ├── api/                   các endpoint mà SPA gọi (BFF)
    ├── lab_core/              module "Lab Core": DocType
    ├── lab_xero/              module "Lab Xero": DocType
    ├── integrations/xero/     Xero client và OAuth
    ├── overrides/             chỉ chứa thay đổi hành vi của Frappe, ERPNext, CRM
    └── tasks/                 background job
```

## Ai phụ thuộc vào ai
```text
frontend ──► api ──► code của module (Lab Core, Lab Xero) ──► DocType
                         │
                         ├──► tasks ──► integrations/xero ──► Xero
                         └──► overrides ──► ERPNext, CRM
hooks.py trỏ tới api, tasks, overrides và event của module; không gì import hooks.py.
```
Mũi tên chỉ đi một chiều. `integrations/xero` không biết gì về request hay trang; frontend chỉ biết `api`.

Hai loại code, hai cách thay đổi:
- **Của ta** (`lab_core`): sửa trực tiếp, trong chính file của nó. Không thứ gì của ta bị override (ghi đè) bao giờ.
- **Không phải của ta** (Frappe, ERPNext, CRM): không bao giờ sửa. Hành vi của nó được đổi từ `overrides/` thông qua hook (điểm móc mở rộng): document event (sự kiện của tài liệu), class extension (mở rộng lớp), endpoint override (ghi đè endpoint).

## Bộ khung gồm những gì
1. **Trạng thái site.** `lab_core` là custom app duy nhất trên `lab.localhost`. Một app lạc loài như `lab_spa` phải được gỡ trước (`docs/runbooks/new-apps.md`), vì script khởi động cài mọi app có trong bench.
2. **Module.** "Lab Core" có từ lúc tạo app. "Lab Xero" được tạo trong Desk (Module Def); sau đó thư mục của nó xuất hiện trong app.
3. **Các package backend.** `api/`, `tasks/`, `integrations/xero/` tồn tại dưới dạng package Python rỗng, để công việc về sau có chỗ đặt đã thống nhất. `overrides/` chỉ được tạo khi cần thay đổi đầu tiên đối với hành vi của Frappe, ERPNext hoặc CRM.
4. **Một endpoint.** `lab_core.api.hello`: chỉ cho user đã đăng nhập, trả về `message` và `user`. Nó chứng minh đường đi trình duyệt → endpoint → session, và cho SPA một thứ để gọi.
5. **Một DocType.** Tạo trong Desk, thuộc module "Lab Core"; các file của nó xuất hiện trên host. Nó chứng minh đường Desk → code.
6. **Vỏ SPA.** Một dự án Vite trong `frontend/` với Vue, Vue Router, Vuetify, Pinia + Pinia Colada và TanStack Query; mỗi thư mục `colada/`, `tanstack/`, `together/` có một trang hiển thị câu trả lời của hello; `www/lab.html` cộng với route rule (luật định tuyến) để `/lab` nạp nó. Nó chứng minh hai data layer sống chung được, và SPA dùng chung session của Desk.
7. **Test.** Mỗi role (vai trò) một test cho endpoint hello: được phép khi đã đăng nhập, bị từ chối khi là Guest (khách chưa đăng nhập).

Bộ khung xong khi: `/lab` nạp được sau khi đăng nhập và cả ba trang đều hiện câu trả lời của hello; DocType tạo trong Desk đã có trên host; các test pass.

## Cái gì phụ thuộc vào cái gì
```text
1 trạng thái site ──► 2 module ───────────► 5 DocType
                   └► 3 package backend ──► 4 endpoint ──► 7 test
                                                  └──────► 6 vỏ SPA
```
Sau mục 3, endpoint (4) và vỏ SPA (6) có thể được xây trong hai phiên riêng: SPA chỉ cần tên của endpoint và dạng câu trả lời, đã cố định ở trên. `hooks.py` chỉ bị mục 6 đụng tới (route rule).

## Những việc chỉ con người làm
- Mọi thứ trong Desk: module, DocType.
- Cài package frontend: agent nêu tên từng package và phiên bản chính xác trước (AGENTS.md A6); `docs/runbooks/add-dependency.md`.
- Việc frontend chạy trên host, trong `frappe-bench/apps/lab_core/frontend/`, bằng Node và yarn của host: install, Vite dev server, build, test frontend. Dev server tới được Frappe qua cổng 8000 đã publish.
- Việc Python và bench chạy trong container: restart, migrate, test Python: `docker compose exec frappe bench ...` và `docker compose restart frappe`.
- Thêm route rule vào `hooks.py`, trừ khi yêu cầu nêu đích danh file đó.

## Làm việc với agent về phần này
- Yêu cầu một mục có đánh số, hoặc một phần của nó, bằng lời của bạn. Nêu tên file khi bạn muốn phạm vi chặt.
- Với bất cứ thứ gì đụng tới nội bộ Frappe (một trang trong `www/` được phục vụ thế nào, CRM build frontend của nó vào `public/` ra sao), hãy yêu cầu một trace hoặc đọc `apps/crm` trước; agent phải dẫn `path:line`.
- Mỗi câu trả lời kết thúc bằng cái gì đã đổi và bạn cần chạy gì. Chạy, xem, rồi yêu cầu việc tiếp theo.

## Sau bộ khung
Các track và thứ tự của chúng nằm trong `OVERVIEW.md`: request và API, auth và session, permissions (phân quyền), hook trước tiên.
