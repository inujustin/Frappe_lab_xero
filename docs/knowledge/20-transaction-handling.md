# 20. Xử lý transaction: một mô hình thay cho danh sách tình huống

Viết ngày 2026-10-12. Bản tổng hợp; chi tiết từng dòng code nằm ở `02` (commit, hook), `03` (job), `18` (lock, deadlock), `19` (thứ tự). Chỉ nói về bên trong hệ thống Frappe.

Nhãn: [S] đã thấy hôm nay (đường dẫn từ `frappe-bench/apps/frappe/`), [T] từ file khác trong kho, [I] suy ra, [G] kiến thức chung.

## Trả lời trong năm dòng

1. Mọi tình huống "hỏng thì sao" quy về một câu hỏi: **nó hỏng ở phía nào của đường commit?**
2. **Trước commit** (trong request, trong mọi hook của tài liệu): cứ raise. Frappe rollback tất cả, người dùng thấy lỗi ngay. Không phải tự xử lý gì.
3. **Sau commit** (job, callback `after_commit`, hook `after_request`): response đã đi rồi, **không rollback được nữa và cũng không nên**. Thứ duy nhất còn lại là một dòng database đã ghi *trước* commit.
4. Vì vậy response của request nghĩa là **"đã nhận"**, không phải "đã xong". "Đã xong" là một trạng thái trên bản ghi, do job ghi sau.
5. Muốn hoàn tác thứ đã commit thì không có rollback; chỉ có một **hành động mới theo chiều ngược lại** (compensation), cũng là một transaction.

## Mô hình: một đường kẻ

```text
        TRONG TRANSACTION CỦA REQUEST                 │        SAU COMMIT
  endpoint → service → doc.insert()/submit()          │  callback after_commit → đẩy job lên Redis
     controller: validate, on_submit …                │  worker: job chạy trong transaction RIÊNG của nó
     handler doc_events (của app khác gắn vào)        │  hook after_request
                                                      │
  hỏng ở đây → raise → ROLLBACK tất cả                │  hỏng ở đây → request KHÔNG bị ảnh hưởng
  người dùng nhận lỗi; không có gì nửa vời            │  người dùng đã nhận "OK"; ai biết là hỏng?
                                               COMMIT ┘
```

Bằng chứng cho đường kẻ: request commit ở `sync_database()` sau khi handler return, rollback khi có exception, rồi mới chạy hook `after_request` ([S] `frappe/app.py:181-198`); `commit()` chạy SQL commit rồi mới chạy các callback `after_commit`, `rollback()` vứt chúng ([S] `frappe/database/database.py:1176-1203`); mỗi job là một transaction riêng: thành công thì commit, exception thì rollback ([S] `frappe/utils/background_jobs.py:273-306`).

## Hỏng ở đâu, thì sao

| Hỏng ở | Bị rollback | Ai biết | Việc phải làm |
|---|---|---|---|
| **Trước commit**: endpoint, service, controller, **handler `doc_events`** | toàn bộ request, kể cả job đang chờ xếp | người dùng, ngay lập tức (HTTP lỗi) | chỉ raise bằng `frappe.throw`; không catch |
| **Ngay tại commit**: process chết giữa SQL commit và lúc đẩy job; hoặc một callback `after_commit` ném lỗi | không gì: dữ liệu đã lưu, tác động sau đó bị mất | **không ai** | dòng trạng thái đã ghi trước commit + một sweeper (job quét định kỳ) |
| **Trong job, lỗi dự kiến** (bên kia từ chối, dữ liệu không hợp lệ) | không gì, nếu job **return bình thường** sau khi ghi `Failed` + lý do | người dùng, khi màn hình đọc lại trạng thái | người sửa dữ liệu rồi bấm thử lại |
| **Trong job, lỗi bất ngờ** (bug, mất mạng, worker bị giết) | mọi thứ job đã ghi, kể cả bộ đếm số lần thử | chỉ Error Log | bản ghi kẹt ở "đang chờ" → sweeper phát hiện "chờ quá lâu" và xếp lại hoặc đánh dấu hỏng |
| **Hook `after_request`** | không gì; lỗi bị nuốt, chỉ ghi log | chỉ log | không đặt việc bắt buộc ở đó |

Hàng đầu tiên trả lời câu "hook hỏng thì sao" cho các hook của tài liệu: chúng chạy **bên trong** transaction, với commit bị tắt ([S] `frappe/model/document.py:1641-1648`), nên hỏng là hủy cả lần lưu. Đó là hành vi đúng, không cần xử lý thêm. Hệ quả cần nhớ: một handler ta gắn vào tài liệu của app khác mà ném lỗi sẽ chặn luôn thao tác của người dùng trên tài liệu đó; chỉ để nó làm việc mà ta *muốn* là điều kiện bắt buộc.

Hàng thứ ba và thứ tư trả lời câu "request đã có response mà job hỏng thì sao": **không rollback request.** Người dùng đã thấy "OK", có thể đã làm việc tiếp trên bản ghi đó. Request chỉ hứa "đã nhận"; việc hỏng về sau được **ghi thành trạng thái**, không được che đi và không kéo lùi quá khứ.

## Năm luật, đủ cho mọi trường hợp

1. **Trong transaction: raise, không catch.** Catch rồi return một kết quả "thất bại" làm request thành công và commit nửa dữ liệu ([T] `14`).
2. **Không tự commit, và biết ai commit hộ.** `frappe.db.commit()` chỉ trong `tasks/` và `patches/` (AGENTS.md B4). Vài hàm framework tự commit (lưu token, ghi request log: [T] `02`); gọi chúng trước lần ghi đầu tiên.
3. **Việc gì xảy ra sau response thì phải có một dòng ghi trước commit.** Dòng đó nói "việc này còn phải làm" và mang một cột trạng thái. Nó được lưu cùng transaction với thay đổi nghiệp vụ, nên hoặc cả hai tồn tại, hoặc không cái nào. Job được xếp bằng `enqueue_after_commit=True` để không chạy trước khi dòng đó có thật.
4. **Việc chạy sau phải chạy lại được, và tự ghi kết cục của mình.** Idempotent (chạy hai lần ra một kết quả), khóa dòng trạng thái khi làm, lỗi dự kiến thì ghi `Failed` rồi **return**, lỗi bất ngờ thì **raise**. Cộng một sweeper cho những dòng không ai đụng tới nữa.
5. **Sau commit không có rollback, chỉ có bù trừ.** Muốn hủy thứ đã lưu: một thao tác nghiệp vụ mới (cancel tài liệu, đánh dấu, hoàn lại) chạy trong transaction của riêng nó, có thể hỏng và phải thử lại được.

Luật 3 và 4 cộng lại chính là pattern **outbox** (hộp thư đi). Email Queue của Frappe là một ví dụ có sẵn ([T] `05`); `Lab Xero Outbox` của lab là một ví dụ khác ([S] `lab_core/lab_xero/outbox.py:16-40`, `lab_core/tasks/xero_sync.py:10-51`).

## Công cụ, mỗi cái một dòng

| Công cụ | Dùng khi | Bằng chứng |
|---|---|---|
| `frappe.throw(msg, <class lỗi>)` | hủy mọi thứ trong transaction hiện tại | [T] `14` |
| `frappe.db.savepoint(name)` + `rollback(save_point=name)` | hoàn tác **một phần** bên trong một transaction ("thử cái này, hỏng thì bỏ riêng nó") | [S] `frappe/database/database.py:1198-1200`; [T] `02` |
| `frappe.db.after_commit.add(fn)` | tác động ra ngoài chỉ được xảy ra nếu dữ liệu thật sự đã lưu; chỉ nằm trong bộ nhớ | [S] `database.py:1194` |
| `frappe.db.after_rollback.add(fn)` | dọn thứ **không phải database** đã làm trong transaction (một file đã ghi ra đĩa) khi nó bị rollback | [S] `database.py:1215` |
| `frappe.enqueue(..., enqueue_after_commit=True)` | job đọc thứ request vừa ghi | [S] `frappe/utils/background_jobs.py:205-206` |
| `get_doc(..., for_update=True)` | job giữ quyền làm việc trên dòng trạng thái | [S] `frappe/model/document.py:167-174` |
| return bình thường / raise trong job | chọn giữa "ghi lại thất bại" và "vứt hết" | [S] `background_jobs.py:296-306` |
| hàm trong `scheduler_events` | sweeper; lỗi của nó chỉ được ghi "Failed", lần sau chạy lại | [S] `frappe/core/doctype/scheduled_job_type/scheduled_job_type.py:150-161` |

## Kiểm tra một thiết kế trong ba câu hỏi

1. Vẽ đường commit. Mọi thứ phải "cùng xong hoặc cùng không" có nằm **cùng một phía** không?
2. Với mỗi thứ nằm bên phải đường kẻ: dòng nào trong database nói rằng nó còn nợ, và ai đọc dòng đó khi không còn ai đang chờ?
3. Nếu thứ bên phải hỏng hẳn: người dùng thấy gì, ở đâu, và hành động ngược lại (nếu cần) là gì?

Không trả lời được câu 2 là dấu hiệu chắc chắn nhất của một lỗi sẽ chỉ hiện ở production.

## Còn chưa biết

- Callback `after_commit` đứng sau một callback ném lỗi: bị bỏ hẳn hay chạy ở lần commit kế tiếp (`19`, mục 3).
- Frappe còn có một bộ quản lý "commit after response" ([S] `frappe/database/utils.py:177-195`, mỗi hàm chạy trong một savepoint riêng); nó được dùng ở đâu và có nên dùng cho việc của ta không thì chưa đọc.
- Nhánh retry khi deadlock của job có thật sự chạy không (`18`).
