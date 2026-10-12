# Runbook: kiểm chứng và thêm một dependency

**Dùng khi:** một agent nói `Needs package: ...`, hoặc một kế hoạch ghi "verify and install" (kiểm chứng rồi cài).
**Ai chạy:** bạn. Agent không bao giờ cài package hay sửa manifest (file khai báo dependency) và lockfile (file khóa phiên bản).
**Vì sao:** LLM đôi khi bịa ra tên package nghe có vẻ đúng. Kẻ tấn công đăng ký sẵn những tên như vậy ("slopsquatting"), nên cài một cái tên bịa có thể chạy code của người khác trên máy bạn.
**Kiểm chứng lần cuối:** _chưa_

Mọi lệnh đều gõ trên host. Package Python được cài trong container (từ thư mục gốc dự án); package frontend được cài trên host, trong thư mục `frontend/` của app. `<APP>` là custom app cần package đó, ví dụ `lab_core`.

## 1. Nó có thật không, và có đúng cái cần không?
- [ ] Tự mở trang registry (kho đăng ký package) (đừng tin link do agent đưa): `https://pypi.org/project/<name>/` hoặc `https://www.npmjs.com/package/<name>`.
- [ ] Nó dẫn tới một source repository thật, có commit gần đây, có issue, và có hơn một maintainer (người bảo trì) hoặc thuộc một tổ chức có tiếng.
- [ ] Lượt tải tương xứng với độ phổ biến mà nó tự nhận; nó không phải mới ra vài ngày; tên của nó không lệch một chữ cái so với một package nổi tiếng.
- [ ] Licence (giấy phép) tương thích (MIT/BSD/Apache thì dễ; GPL/AGPL cần một quyết định).
- [ ] Bạn không làm được việc đó bằng standard library (thư viện chuẩn) hoặc một dependency đã có sẵn.

Các kiểm tra chỉ đọc (Chạy ở: host):
```bash
npm view <name> version repository.url maintainers time.created   # JS: hỏi npm registry, không thay đổi gì
```
Với Python, đọc các phiên bản trên trang PyPI.

## 2. Thêm nó, có pin (ghim đúng phiên bản)
⚠️ CHANGES STATE (LÀM ĐỔI TRẠNG THÁI): manifest và lockfile của app, và môi trường của container.

**Python:** tự tay thêm `"<name>==<version>"` vào `dependencies` trong `frappe-bench/apps/<APP>/pyproject.toml`, rồi (Chạy ở: host):
```bash
docker compose exec frappe bench setup requirements --python
docker compose restart frappe
```

**Frontend:** (Chạy ở: host, bằng Node và yarn của host)
```bash
cd frappe-bench/apps/<APP>/frontend
node --version                        # phải hiện cùng phiên bản major với NODE_VERSION trong docker/versions.env
yarn add <name>@<exact version>       # thêm package vào package.json và yarn.lock, tải nó vào node_modules/
cd -
```
Thư mục `node_modules/` nằm bên trong thư mục bench được chia sẻ, nên container thấy cùng những file đó.

Mong đợi: manifest (và `yarn.lock` với frontend) thay đổi, ngoài ra không gì khác.
Rollback (hoàn tác): xóa dòng bạn đã thêm rồi chạy lại đúng lệnh cài đó (Python), hoặc `yarn remove <name>` trong cùng thư mục `frontend/` trên host (frontend).

## Kiểm tra đã thành công
- Bảo agent tiếp tục công việc đang bị chặn; giờ nó có thể import package.
- Chỉ manifest và lockfile của `<APP>` thay đổi.
