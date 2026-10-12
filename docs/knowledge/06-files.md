# 06. File: một bản đồ đọc

Nhãn: [S] đã thấy hôm nay (số dòng của các định nghĩa hàm), [I] suy ra, [G] kiến thức chung.

**File này là một bản đồ, không phải một trace.** Chỉ đọc danh sách hàm của `frappe/core/doctype/file/file.py` và vài dòng của `frappe/handler.py`. Dùng nó để đọc source đúng thứ tự khi offline; đừng xây trên các dòng [G] mà không kiểm tra chúng.

## Mô hình trong năm dòng

1. Một file là hai thứ: **byte** nằm ở đâu đó (một thư mục trên đĩa, hoặc một URL) và một **tài liệu `File`** trỏ tới chúng. [G]
2. Tài liệu `File` có thể được đính kèm vào một tài liệu khác (`attached_to_doctype`, `attached_to_name`). [G]
3. File **public** được web server phục vụ cho bất kỳ ai có URL; file **private** được Python phục vụ sau một lần kiểm tra quyền. [G]
4. Upload là một hàm đã whitelist; mọi thứ khác (tên, hash, kiểm tra trùng, giới hạn kích thước) do controller của `File` làm lúc insert.
5. `File` có hàm permission riêng và bộ lọc danh sách riêng, nên "user này có thấy file này không" được quyết định bằng code, không chỉ bằng các dòng role.

## Đọc ở đâu

```text
POST /api/method/upload_file
 upload_file()                              frappe/handler.py:130            [S]
   is_private lấy từ form                   :152
   file đã có được dùng lại theo URL        :168-171
   một đường dẫn tạm dưới thư mục files     :191
   dựng tài liệu File                       :234
 File controller                            frappe/core/doctype/file/file.py [S: tên + số dòng]
   before_insert            :107
   validate                 :176
     validate_attachment_references  :198
     enforce_public_file_restrictions :218
     validate_private_file_access    :227
     validate_file_extension :481
     validate_duplicate_entry :501   (content hash; generate_content_hash :542)
     validate_attachment_limit :415
   save_file                :806     → save_file_on_filesystem :876 → write_file :788
   check_max_file_size      :887
   get_full_path            :753     byte nằm ở đâu trên đĩa
   after_insert             :149
   handle_is_private_changed :337    chuyển giữa public và private
   on_trash                 :261     → delete_file_from_filesystem :908
   on_rollback              :270     ← hoàn tác việc ghi file khi transaction thất bại

GET một file private
 download_private_file(path)                frappe/utils/response.py:294     [S]
 send_private_file(path, filename)          frappe/utils/response.py:327     [S]
 download_file(file_url)                    frappe/handler.py:258            [S]

Permissions
 has_permission(doc, ptype, user)           frappe/core/doctype/file/file.py:1020   [S]
 get_permission_query_conditions(user)      :1060                                   [S]
```

## Vì sao `on_rollback` là dòng thú vị

`02` đã nói: một transaction chỉ bao phủ database. Một file trên đĩa nằm ngoài nó. Controller của `File` có một method `on_rollback` (`file.py:270` [S]), và `frappe/database/database.py:1224-1226` [S] cảnh báo: "rollback watchers can not work with save points … Avoid using savepoints when writing to filesystem." (rollback watcher không hoạt động với savepoint; tránh dùng savepoint khi ghi ra filesystem).

Đọc gộp lại [I]: khi một file đã được ghi và request sau đó thất bại, framework xóa các byte trong một rollback callback, để đĩa và database khớp nhau. Đó là một **compensation** (bù trừ) nhỏ, cùng ý tưởng với "void invoice bên Xero nếu tài liệu local bị cancel" (`12`). Đọc `file.py:261-303` là một bài học 40 dòng hay về điều đó.

## Các câu hỏi kế hoạch đặt ra (track G), và câu trả lời ở đâu

| Câu hỏi | Đọc |
|---|---|
| Byte được ghi vào đâu? | `file.py:753` `get_full_path`, `:788` `write_file` |
| Public so với private: ai phục vụ cái gì? | `frappe/utils/response.py:294-340`; và web server phơi thư mục nào ra ([G]: `sites/<site>/public/files` so với `sites/<site>/private/files`; không mở `sites/`, AGENTS.md B2) |
| Ai được đọc một file private? | `file.py:1020-1058`, `:227` |
| Cái gì chặn một lần upload 2 GB? | `file.py:887` `check_max_file_size` |
| Cùng một file upload hai lần? | `file.py:501` `validate_duplicate_entry`, `:542` |
| Object storage (kiểu S3), Dropbox | Không có trong `file.py` của core, theo những gì danh sách hàm cho thấy. `is_remote_file` (`:91`) và `validate_remote_file` (`:443`) xử lý các file chỉ là một URL. Chuyển byte sang object storage là việc tùy biến hoặc một app bổ sung: một quyết định thiết kế, và một dependency mới (AGENTS.md A6). |

## File và Xero [G]

- Xero có một endpoint Attachments cho từng invoice. Gửi PDF của invoice là thêm một lời gọi đi ra: cùng job, cùng kiểu operation của outbox (`operation = "attach_pdf"`), idempotency key riêng.
- Không bao giờ gửi URL của một file private cho Xero: nó cần session của ta. Hãy gửi byte.

## Các luật của dự án này có đụng tới file

- AGENTS.md A12: không bao giờ mở các bản export dữ liệu thật. Một lần upload thử nên là file bạn tự tạo cho việc thử.
- AGENTS.md B2: `frappe-bench/sites/**` không bao giờ được agent đọc hay ghi, và đó là nơi các byte nằm.

## Còn chưa biết

Mọi thứ đánh dấu [G], và mọi thân hàm. Chủ đề này chưa được trace; nó là trace kế tiếp tự nhiên sau job.
