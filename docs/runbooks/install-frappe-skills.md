# Runbook: cài các skill Frappe chính thức

**Dùng khi:** thiết lập dự án này cho agent làm việc, và bất cứ khi nào bạn muốn cập nhật các skill (bộ chỉ dẫn đóng gói cho agent).
**Ai chạy:** bạn. Agent không bao giờ chạy `npx` hay cài bất cứ thứ gì.
**Thời gian:** khoảng 5 phút.
**Nguồn:** README của [frappe/skills](https://github.com/frappe/skills).
**Trạng thái:** chọn skill nào là quyền của bạn; danh sách dưới đây là gợi ý.
**Kiểm chứng lần cuối:** _chưa_

## Cái gì được cài

| Skill | Nó là gì | Gợi ý |
|---|---|---|
| `frappe-app-dev` | DocType, controller, whitelisted API, `frappe.db`/`frappe.qb`, hook, permission, job, cache, test | có: skill cốt lõi để viết code Frappe |
| `frappe-code-review` | checklist review: tính đúng đắn, bảo mật, hiệu năng, concurrency (xử lý đồng thời), API, test | có |
| `code-style` | hàm nhỏ, file dưới khoảng 300 dòng, comment ngắn | có |
| `deep-app-audit` | audit (rà soát) nhiều agent. Chỉ chạy khi bạn gọi `/deep-app-audit`. Cần một test site, semgrep và agent CLI | tùy bạn; xem các luật bên dưới |
| `technical-writing`, `ui-design` | hướng dẫn viết tài liệu và UI | tùy chọn |

Ở bước 2, bỏ những dòng `--skill` bạn không muốn.

## Mỗi công cụ tìm skill ở đâu
- Skill đã cài và skill của chính bộ kit đều nằm trong `.agents/skills/`. Codex và agy đọc thẳng thư mục đó; Claude Code được `CLAUDE.md` chỉ tới đó.
- Trình cài đặt cũng copy các skill đã cài sang `.claude/skills/`, nên Claude Code liệt kê chúng dưới `/skills`.
- Skill của chính bộ kit thì **không** nằm trong `.claude/skills/`, nên Claude Code không liệt kê chúng dưới `/skills`; nó đọc chúng như file khi một prompt nêu tên. `VERIFY:` quyết định xem bạn có muốn copy chúng sang `.claude/skills/` nữa không.

## Trước khi bắt đầu
- [ ] Node.js 18+ (`node --version`).
- [ ] Bạn đang ở thư mục gốc của dự án này (thư mục chứa `AGENTS.md`).

## Các bước
1. **Xem repo Frappe cung cấp gì** (không cài gì) (Chạy ở: host)
   ```bash
   npx skills add frappe/skills --list
   ```
   Mong đợi: một danh sách có chứa các skill ở trên.

2. ⚠️ CHANGES STATE (LÀM ĐỔI TRẠNG THÁI): **Cài các skill** (Chạy ở: host)
   ```bash
   npx skills add frappe/skills \
     --skill frappe-app-dev \
     --skill frappe-code-review \
     --skill code-style \
     --skill deep-app-audit \
     --agent claude-code codex antigravity-cli --copy
   ```
   Dòng cuối cài cho cả ba công cụ dưới dạng file thật mà bạn đọc được; bỏ nó đi thì trình cài đặt sẽ hỏi bạn cài cho công cụ nào.
   Mong đợi: thư mục mới dưới `.claude/skills/` (Claude Code) và `.agents/skills/` (Codex và agy), và một file `skills-lock.json` ghi lại các phiên bản.
   Rollback (hoàn tác): xóa các thư mục skill mà bước này thêm vào (`rm -r .agents/skills/<name> .claude/skills/<name>`) và `skills-lock.json`. Không xóa các thư mục của chính bộ kit: `code-reviewer`, `code-tracer`, `microtask-executor`, `microtask-planner`, `red-flag-audit`, `runbook-writer`, `test-writer`.

3. **Đọc những gì bạn đã cài.** Một skill là một chỉ dẫn mà agent tuân theo. (Chạy ở: host)
   ```bash
   ls .agents/skills .claude/skills
   ```
   Mong đợi: các thư mục của chính bộ kit cộng với mỗi skill bạn cài một thư mục. Đọc lướt từng `SKILL.md` mới.

4. **Kiểm tra từng công cụ thấy chúng.** Trong `claude` và trong `codex` gõ `/skills`; trong `agy` hỏi "list your skills".

## Cập nhật về sau
Chạy lại bước 2, rồi bước 3: đọc cái gì đã đổi trước khi bạn dựa vào nó. Một thay đổi trong skill làm đổi cách agent viết code.

## Các luật đi kèm skill
- `AGENTS.md` thắng một skill khi chúng mâu thuẫn (`AGENTS.md` Part B, B8).
- Phần Vue của `frappe-app-dev` (`references/frontend-vue.md`) dạy frappe-ui, Tailwind và `useList`/`useDoc`. Ở đây SPA duy nhất trong `lab_core` dùng Vuetify với Pinia Colada và TanStack Query, nên `AGENTS.md` bảo agent bỏ qua nó. Đừng sửa file bên trong skill: lần cập nhật sau sẽ ghi đè.
- `deep-app-audit` chạy lệnh trên một test site, nên nó nằm ngoài vòng công việc bình thường, nơi agent không chạy gì cả. Nếu bạn cài nó, hãy tự mình khởi chạy, có chủ đích, trên một test site dùng xong bỏ.

## Kiểm tra đã thành công
- `/skills` trong Claude và Codex liệt kê các skill bạn đã chọn.
- `ls .agents/skills` vẫn hiện bảy thư mục của chính bộ kit bên cạnh các thư mục mới.

## Nếu có gì trục trặc
| Triệu chứng | Nguyên nhân khả dĩ | Cách sửa |
|---|---|---|
| `npx: command not found` | thiếu Node.js | cài Node.js 18+ |
| một skill bị thiếu ở một công cụ | danh sách `--agent` không có công cụ đó | chạy lại bước 2 có nêu tên công cụ đó |
| một skill của chính bộ kit bị thay đổi | trùng tên | nói cho agent biết cái nào; nó có thể được viết lại từ bộ kit |
