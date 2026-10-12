# 21. bench tìm Python, Node và yarn bằng cách nào

Viết ngày 2026-10-12. Kiến thức chung của kho này.

Nhãn: [S] đã thấy hôm nay, [I] suy ra, [G] kiến thức chung từ trí nhớ. Đã đọc: `docker/Dockerfile.dev`, `docker/entrypoint.sh`, `docker/versions.env`, các dòng mount của `docker/compose.yml`, `frappe-bench/Procfile`, `frappe/utils/bench_helper.py`, `frappe/bundler.py`, `package.json` của Frappe và của `lab_core`. **Chưa đọc được**: source của chính công cụ `bench` (nó được cài bằng pip bên trong image, không nằm trên đĩa của host), và mọi thứ dưới `frappe-bench/env/`, `sites/`, `config/` (agent không được đọc). Phần nói về bên trong CLI vì vậy là [G].

## Trả lời trong năm dòng

1. `bench` **không có file đăng ký** nào trong thư mục home, không có token, không có "context" lưu sẵn. Cấu hình của nó là **chính thư mục bench** cộng với **PATH** của process đang chạy.
2. **Python**: được chốt một lần, lúc tạo virtualenv `env/`. Sau đó bench luôn gọi `env/bin/python` theo đường dẫn tương đối. Không tìm lại.
3. **Node, npm, yarn**: không được ghi ở đâu cả. Mỗi lần cần, code gọi thẳng `node`, `yarn` và hệ điều hành tìm chúng trong PATH.
4. Ở cách cài thông thường (không Docker), "PATH" và "python3" là của máy bạn, nên bench dùng Node và Python của host. **Trong lab này bench chạy trong container**, nên nó dùng Node và Python của container; host chỉ góp thư mục code, và Node + yarn cho riêng phần frontend của `lab_core`.
5. So với `kubectl`: kubectl là client nói chuyện với một server ở xa nên cần file ghi địa chỉ và chứng thực. bench là công cụ **tại chỗ**: nó thao tác trên một thư mục và khởi chạy các process con.

## Ba thứ cùng mang tên "bench"

```text
① công cụ dòng lệnh `bench`      một chương trình Python (package frappe-bench), cài bằng pip
                                  [S] docker/Dockerfile.dev:29   → chạy bằng Python CỦA HỆ THỐNG
② thư mục bench                   frappe-bench/: apps/  sites/  env/  config/  logs/  Procfile  patches.txt
                                  [S] liệt kê thư mục
③ các lệnh của Frappe             migrate, run-tests, build… định nghĩa trong các app, không trong ①
                                  [S] frappe/utils/bench_helper.py:74-91   → chạy bằng Python CỦA env/
```

Đường đi của một lệnh:

```text
bạn gõ:  bench --site lab.localhost migrate          (đứng trong thư mục bench)
 ① bench (CLI)
     ├─ lệnh của riêng nó (init, get-app, setup, start, set-config, use…)  → tự làm                      [G]
     └─ lệnh khác → giao cho Frappe, bằng đúng một kiểu gọi:
          cd <bench>/sites
          ../env/bin/python -m frappe.utils.bench_helper frappe --site lab.localhost migrate
              [S] đúng dạng lệnh này được viết tay ở docker/entrypoint.sh:116-120 (chế độ debug)
 ③ bench_helper gom lệnh của mọi app trong bench thành một nhóm tên "frappe"                              [S] bench_helper.py:80-91
     site nào? theo thứ tự: --site  →  biến môi trường FRAPPE_SITE  →  default_site trong config         [S] bench_helper.py:112-120
```

Hai hệ quả: bench chỉ hoạt động khi **đứng trong** một thư mục bench (thư mục hiện tại chính là "context") [G]; và có **hai Python** tham gia: Python của hệ thống chạy công cụ ①, Python trong `env/` chạy Frappe.

## Python: chốt một lần bằng virtualenv

```text
bench init --python python3 <thư mục>        [S] docker/entrypoint.sh:25-26
bench setup env --python python3             [S] :37-40     tạo env/ nếu chưa có env/bin/python
bench setup requirements --python            [S] :41-46     cài package Python của mọi app vào env/
```

- `--python python3` nghĩa là "lấy `python3` đang đứng đầu PATH **lúc này**". Virtualenv ghi lại interpreter gốc trong file `env/pyvenv.cfg` và các script trong `env/bin/` mang đường dẫn tuyệt đối tới nó [G]. Đây là thứ gần nhất với "file cấu hình được tạo tự động" mà bạn hỏi: nó được viết một lần, lúc tạo, bởi công cụ tạo venv.
- Từ đó về sau không ai tìm Python nữa: bench gọi `env/bin/python`. Đổi phiên bản Python = **dựng lại `env/`**, không phải sửa một dòng config.
- Các app được cài vào env ở dạng "editable": env trỏ ngược về `apps/<app>` bằng **đường dẫn tuyệt đối** [G]. Vì vậy một env không dời chỗ được: copy sang đường dẫn khác là hỏng.

Lab xử lý điều đó thế nào:

| Quyết định | Bằng chứng |
|---|---|
| Thư mục bench được mount vào container ở **cùng đường dẫn tuyệt đối** như trên host | [S] `docker/Dockerfile.dev:12-13`; `docker/compose.yml:15, :23, :51` |
| `env/` là một **volume riêng** của container (`bench-env`), đè lên thư mục `env/` trong bind mount | [S] `docker/compose.yml:53`; `Dockerfile.dev:32-36` |
| Image dựng từ `python:${PYTHON_VERSION}-slim-bookworm`; phiên bản lấy từ một file | [S] `Dockerfile.dev:7`; `docker/versions.env` (`PYTHON_VERSION=3.14`) |

Kết luận cho lab: **Python của host không bao giờ được bench dùng.** Môi trường Python chỉ tồn tại trong container; thư mục `env/` bạn thấy trên host không phải là thứ container chạy.

## Node, npm, yarn: tìm qua PATH mỗi lần

Không có bước "đăng ký Node". Code của Frappe gọi chúng bằng tên:

| Việc | Code | Bằng chứng |
|---|---|---|
| kiểm tra trước khi build | chạy `node -v`; tìm `yarn` bằng `shutil.which("yarn")`; chỉ **cảnh báo** nếu Node cũ hơn 18 hoặc thiếu yarn | [S] `frappe/bundler.py:286-293` |
| build asset | `yarn run build` (hoặc `production`) trong thư mục app `frappe`, qua một process con | [S] `bundler.py:237-238, :260-262` |
| script đó là gì | `"build": "node esbuild"` | [S] `frappe-bench/apps/frappe/package.json:3-7` |
| watch khi phát triển | `yarn run watch` | [S] `bundler.py:268-283` |
| biến môi trường truyền cho Node | chỉ `NODE_OPTIONS` (giới hạn bộ nhớ) | [S] `bundler.py:296-297` |
| phiên bản Node yêu cầu | khai báo `"engines": {"node": ">=24"}`: một lời khai trong package.json, không phải thứ bench ghi nhớ | [S] `frappe/package.json:18-20` |
| build của một app riêng | lệnh build được chạy với cờ `--run-build-command`; `lab_core` khai script `build` của nó là `cd frontend && yarn install --frozen-lockfile … && yarn build` | [S] `bundler.py:254-257`; `frappe-bench/apps/lab_core/package.json` |

"Tìm qua PATH" nghĩa là: process nào chạy bench thì PATH **của process đó** quyết định. Hai terminal với hai PATH khác nhau (ví dụ một cái đã bật nvm, một cái chưa) sẽ cho hai Node khác nhau cho cùng một bench. Đây là nguồn của phần lớn lỗi "máy tôi chạy được".

Trong container của lab, Node nằm trên PATH vì image chép nó vào đó:

```text
FROM node:${NODE_VERSION}-bookworm-slim AS node                          [S] Dockerfile.dev:5
COPY --from=node /usr/local/bin/node  →  /usr/local/bin/node             :23
COPY --from=node …/node_modules       →  npm                             :24-26
npm install -g yarn                                                      :27
```

## Trong lab: cái gì chạy ở đâu

```text
HOST (máy bạn)                                   CONTAINER frappe
 thư mục frappe-bench/  ◄──── bind mount, cùng đường dẫn tuyệt đối ────►  thư mục frappe-bench/
 Node + yarn của host                                                     bench (CLI), Python 3.14 hệ thống
   chỉ cho apps/lab_core/frontend:                                        env/ (volume riêng): Python của Frappe
   cài package, Vite dev server, lint, test                               Node 24 + npm + yarn trên PATH
 KHÔNG có Python của Frappe                                               bench start → các process trong Procfile
```

- `bench start` đọc `Procfile` và chạy từng dòng: `bench serve`, `bench socketio`, `bench watch`, `bench schedule`, `bench worker` ([S] `frappe-bench/Procfile`). Mỗi dòng lại là một lệnh bench, đi theo đường ở trên. `socketio` và `watch` là hai chỗ cần Node lúc chạy.
- Lúc khởi động, container tự build SPA của `lab_core` nếu chưa build hoặc source mới hơn ([S] `docker/entrypoint.sh:96-108`): việc này dùng **Node của container**.
- Khi bạn phát triển frontend, lệnh chạy trên **host** (AGENTS.md B2). Cùng một thư mục `frontend/` và cùng một `node_modules` được cả hai phía dùng, nên phiên bản major của Node trên host phải bằng `NODE_VERSION` trong `docker/versions.env` ([S] `NODE_VERSION=24`). `node_modules` có chứa file nhị phân theo nền tảng [G]; host (WSL2) và container đều là Linux nên dùng chung được [I].

## "File cấu hình" của một bench là những gì

| Thứ | Nó nói gì | Ai viết |
|---|---|---|
| `env/` (và `env/pyvenv.cfg`) | Python nào chạy Frappe; package nào đã cài | `bench init`, `bench setup env`, `bench setup requirements` |
| `sites/apps.txt` | bench này có những app nào | `bench get-app`, `bench new-app` ([S] được đọc ở `entrypoint.sh:22, :41`) |
| `sites/common_site_config.json` | cấu hình chung của bench: địa chỉ database, ba Redis, cổng… | `bench set-config -g …` ([S] `entrypoint.sh:49-52`) |
| `sites/<site>/site_config.json` | riêng một site: tên database, **mật khẩu database**, `developer_mode`… | `bench new-site`, `bench --site … set-config` ([S] `entrypoint.sh:59-65`) |
| site mặc định | lệnh không có `--site` thì dùng site nào | `bench use <site>` ([S] `entrypoint.sh:77`; đọc ở `bench_helper.py:119-120`) |
| `Procfile` | `bench start` chạy những process nào | `bench init`; lab xóa các dòng redis ([S] `entrypoint.sh:53`) |
| `config/` | file cấu hình sinh ra cho redis, và cho nginx/supervisor khi lên production | `bench setup …` [G] |
| PATH của process | `node`, `yarn`, `git`, client của MariaDB, `wkhtmltopdf` ở đâu | hệ điều hành / image |

Không có gì trong bảng nằm ở thư mục home của người dùng. Hai bench trên cùng một máy hoàn toàn độc lập, mỗi cái một `env/` và một bộ site.

## So với kubectl [G]

| | `kubectl` | `bench` |
|---|---|---|
| Bản chất | client gọi HTTPS tới API server của một cluster | công cụ tại chỗ: sửa file trong một thư mục, khởi chạy process con |
| Biết "nói chuyện với ai" từ đâu | file **kubeconfig** (`~/.kube/config`, hoặc biến `KUBECONFIG`): danh sách cluster, user, context | thư mục đang đứng |
| Ai viết file đó | công cụ dựng cluster (kubeadm, kind, minikube, k3s, CLI của cloud) tự ghi vào, nên bạn thấy "cài xong là chạy được" | không có file tương đương; `bench init` tạo ra cả thư mục |
| Chứng thực | chứng chỉ hoặc token trong kubeconfig | bench không cần đăng nhập; bí mật duy nhất là mật khẩu database trong `site_config.json` |
| Chọn đích | `--context`, `--namespace` | thư mục hiện tại (bench nào) + `--site` (site nào) |
| Quan hệ với container runtime | kubectl **không** nói chuyện với containerd. kubelet trên mỗi node mới gọi containerd qua một socket; containerd có file cấu hình riêng, và công cụ `crictl` cũng có file riêng trỏ tới socket đó | bench không "kết nối" tới Node hay Python; nó chỉ **thực thi** chúng |
| Thứ được "tự cấu hình khi cài" | kubeconfig | `env/` (chốt Python) và hai file config của site; **không có gì cho Node** |

Điểm giống thật sự duy nhất: cả hai đều có một khái niệm "đích hiện tại" (context của kubectl, thư mục + site mặc định của bench), và làm sai đích là lỗi hay gặp nhất.

## Bẫy

| Dấu hiệu | Nguyên nhân | Sửa ở đâu |
|---|---|---|
| `bench: command not found` trên host | CLI chỉ được cài trong image | chạy qua `docker compose exec frappe bench …` (AGENTS.md B2) |
| lệnh bench báo không phải thư mục bench | đứng sai thư mục | container đặt sẵn thư mục làm việc là bench ([S] `Dockerfile.dev:42`) |
| build báo thiếu yarn / Node cũ | PATH của process không có chúng | image ([S] `Dockerfile.dev:23-27`); trên host: Node của host |
| lỗi lạ sau khi đổi phiên bản Python hoặc dời thư mục | `env/` vẫn trỏ interpreter và đường dẫn cũ | dựng lại env; trong lab: đổi `docker/versions.env` rồi build lại image |
| frontend build ra khác nhau giữa host và container | hai phiên bản Node khác major | giữ host bằng `NODE_VERSION` |
| `import` một package Python "có trên máy tôi" mà Frappe không thấy | package nằm ở Python của host hoặc của hệ thống, không nằm trong `env/` | khai báo trong manifest của app; con người cài (AGENTS.md A6) |

## Còn chưa biết

- Bên trong công cụ `bench`: cách nó nhận ra thư mục bench, danh sách chính xác lệnh nó tự xử lý, và `bench socketio` gọi Node ra sao. Source không nằm trên đĩa của host.
- Nội dung thật của `env/pyvenv.cfg` và cách các app được cài (pip hay uv): `env/` nằm ngoài tầm đọc của agent. `entrypoint.sh:115` có dùng `uv pip`, gợi ý rằng uv có mặt.
- Script `esbuild` của Frappe làm gì với cờ `--run-build-command` (chưa mở); việc nó chạy script `build` của từng app là theo lời chú thích ở `entrypoint.sh:96-98`.
- Host và container dùng chung `node_modules` có luôn an toàn không, hay chỉ vì cả hai cùng là Linux cùng kiến trúc.
