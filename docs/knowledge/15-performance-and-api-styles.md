# 15. Tối ưu trong Frappe, và các stack ít gặp (GraphQL, gRPC)

Nhãn: [S] đã thấy hôm nay, [T] từ các trace note, [I] suy ra, [G] kiến thức chung. Hôm nay chỉ đọc **dòng định nghĩa và docstring** của các hàm dưới đây (trừ `read_only`, `process_response` đọc cả thân): đây là một **bản đồ**, giống `06`. Không chạy gì, không đo gì. Mọi con số "nhanh hơn" trong file này là [G] cho tới khi bạn tự đo.

Mục tiêu chính của lab là tích hợp Xero ↔ ERPNext. Vì vậy file này xếp các kỹ thuật theo một câu hỏi: **nó có làm luồng Xero tốt hơn không?** Phần lớn kỹ thuật "lạ" thì không; vài kỹ thuật rất thường thì có.

## Trả lời trong năm dòng

1. Frappe **không có GraphQL và không có gRPC**: không có trong core, ERPNext hay CRM trên đĩa này ([S]: thư mục `frappe-bench/apps/` chỉ có `frappe`, `erpnext`, `crm`, `lab_core`; không manifest nào nhắc tới `graphql`, `grpc` hay `protobuf`).
2. Bài toán mà GraphQL giải (một màn hình cần nhiều thứ, lấy đúng field cần) thì Frappe giải bằng **tham số `fields`** của document API và bằng **endpoint BFF** trả một view model cho cả màn hình.
3. Bài toán mà gRPC giải (hợp đồng có kiểu, nhị phân gọn, streaming giữa các service) gần như không xuất hiện trong lab: Xero chỉ nói REST/JSON [G], và trình duyệt nói HTTP/JSON với Frappe.
4. Với luồng Xero, nút cổ chai là **rate limit của Xero** (60 lời gọi mỗi phút, `10`) chứ không phải tốc độ của Frappe. Tối ưu đáng tiền nhất là gọi Xero ít lần hơn: batch, phân trang, `If-Modified-Since`, cache dữ liệu tham chiếu.
5. Luật chung: đo trước (Frappe có sẵn recorder), rồi mới tối ưu đúng chỗ đo được.

## Bạn quen cái gì, Frappe có cái gì

| Bạn biết ở .NET | Nó giải bài toán gì | Trong Frappe | Bằng chứng |
|---|---|---|---|
| GraphQL: client chọn field | Over-fetching (lấy thừa field) | `GET /api/v2/document/<DocType>?fields=[...]` | `frappe/api/v2.py:117` [T] |
| GraphQL: một query nhiều resource | Nhiều round trip cho một màn hình | Một endpoint BFF trong `lab_core/api/` trả đúng hình dạng màn hình cần | `docs/refer/`, mục BFF (ghi chú chưa kiểm chứng) |
| GraphQL: schema có kiểu | Hợp đồng rõ ràng | Type hint trên hàm `@frappe.whitelist`, được kiểm tra lúc gọi | `frappe/utils/typing_validations.py:25` [T]; AGENTS.md B4 bắt buộc type hint |
| gRPC: protobuf nhị phân | Payload nhỏ, serialize nhanh | JSON qua `orjson` (một thư viện JSON nhanh) | `frappe/pyproject.toml:55`, `frappe/utils/response.py:17, :154` [S] |
| gRPC: server streaming | Đẩy dữ liệu liên tục | Không có trong RPC. Đẩy về trình duyệt: socket.io (`04`) | `frappe/realtime.py:23` [S ở `04`] |
| gRPC giữa các service | Gọi nội bộ độ trễ thấp | Không có service thứ hai: BFF chạy **cùng tiến trình** với dữ liệu, một lời gọi hàm Python | `INIT.md`, "The system" |
| Output caching, `IMemoryCache`, `IDistributedCache` | Không tính lại | Ba tầng cache bên dưới | `frappe/utils/caching.py` [S] |
| EF Core `AsNoTracking`, projection | Đọc nhẹ | `frappe.db.get_value`, `get_list(fields=..., pluck=...)` thay cho `get_doc` | `frappe/database/database.py:517`, `frappe/model/db_query.py:135` [S] |
| `SqlBulkCopy` | Ghi nhiều dòng | `frappe.db.bulk_insert`, `bulk_update` | `database.py:1496`, `:1003` [S] |
| Read replica | Tách tải đọc | Decorator `@frappe.read_only()` khi conf `read_from_replica` bật | `frappe/__init__.py:500-520`, `:284` [S] |
| Rate limiting middleware | Tự bảo vệ | Decorator `rate_limit(key, limit, seconds, methods, ip_based)` | `frappe/rate_limiter.py:104` [S] |
| MiniProfiler | Đo từng query | Recorder (trang Recorder trong Desk) | `frappe/recorder.py:306` [S] |

**GraphQL thật** có tồn tại dưới dạng app cộng đồng cho Frappe [G]; nó không có trên đĩa. Cài nó là thêm một app và các dependency (AGENTS.md A6, và B1: "không tạo app khác" nói về code của ta, còn cài app ngoài là quyết định của bạn). **gRPC** thì không thể đi qua `/api`: bảng route của Frappe là cố định (`TRACK-A.md`, stage 2), nên một server gRPC phải là một tiến trình riêng nằm cạnh Frappe.

## Các tầng cache [S: docstring]

```text
gần nhất, rẻ nhất                                                    xa nhất, dùng chung
@request_cache  →  @site_cache(ttl, maxsize)  →  @redis_cache(ttl, user, shared)  →  frappe.cache (Redis)
caching.py:26       caching.py:78                 caching.py:170
chỉ trong 1 request  trong 1 process worker,       mọi worker, mọi request;
                     KHÔNG chia sẻ giữa worker      mặc định ttl 3600 s; có .clear_cache()
```

- `frappe.get_cached_doc` (`frappe/model/document.py:2281`) và `frappe.get_cached_value` (`:2344`): tài liệu ít đổi (Settings, master data).
- `frappe.client_cache` (`frappe/utils/redis_wrapper.py:448`): docstring nói rõ nó là **nội bộ của framework**, có thể đổi không báo trước. Không dùng.
- Mọi response mặc định là `Cache-Control: no-store` trừ khi endpoint tự chọn khác ([S] `frappe/app.py:290-291`): trình duyệt không cache API của bạn. Cache phía client là việc của Pinia Colada / TanStack Query (track I2).

Cái giá của cache là invalidation (làm mất hiệu lực đúng lúc). `@site_cache` trên nhiều worker nghĩa là mỗi worker có một bản, có thể lệch nhau trong ttl.

## Đọc và ghi database [S: dòng định nghĩa]

| Việc | Dùng | Tránh | Vì sao |
|---|---|---|---|
| Cần 1–2 field của một tài liệu | `frappe.db.get_value` (`database.py:517`), `get_values` (`:595`) | `frappe.get_doc(...).field` | `get_doc` nạp cả tài liệu và mọi bảng con [G] |
| Danh sách | `frappe.get_list(fields=[...], limit...)`; `pluck="name"` khi chỉ cần một cột (`db_query.py:135`) | `fields=["*"]`; `get_all` ở endpoint (bỏ qua quyền, `01`) | Ít cột, có phân trang, có quyền |
| N+1 (gọi query trong vòng lặp) | Một `get_list` với filter `in`, rồi ghép trong Python | `get_doc` / `get_value` trong `for` | Lỗi hiệu năng phổ biến nhất [G] |
| Đếm | `frappe.db.count(..., cache=True)` (`:1285`); bảng rất lớn: `estimate_count` (`:1306`) | `len(get_list(...))` | |
| Ghi nhiều dòng | `bulk_insert` (`:1496`), `bulk_update` (`:1003`) | `doc.insert()` trong vòng lặp hàng nghìn lần | Nhưng bulk **bỏ qua** validate, hook và permission của tài liệu [G]: chỉ dùng trong `patches/` hoặc job nhập liệu có chủ đích |
| Đọc kết quả khổng lồ | `with frappe.db.unbuffered_cursor():` + `as_iterator=True` (`:1550-1563`) | nạp hết vào list | Docstring: bộ nhớ O(1). Cần `frappe.db.sql`, mà AGENTS.md B4 cấm SQL thô: hỏi trước khi dùng |
| Lọc/sắp xếp chậm | Index: `search_index` trên field (tạo trong Desk), hoặc `frappe.db.add_index` (`:1382`) trong một patch | thêm index bằng tay trong DB | AGENTS.md B3: schema chỉ qua code |
| Giao dịch quá lớn | Chia batch, mỗi batch một commit trong `tasks/` | một transaction ghi hàng trăm nghìn dòng | Có trần `MAX_WRITES_PER_TRANSACTION = 200_000` (`:99`, kiểm tra ở `:479`) |
| Sau submit | `doc.db_set(...)` | `doc.save()` trên tài liệu đã submit | AGENTS.md B4 |

`get_lazy_doc` (`frappe/model/document.py:166`) tồn tại trong v16: nạp tài liệu kiểu lười. Thân hàm và thời điểm bảng con được nạp thì chưa đọc.

## Đưa việc ra khỏi request

Đã có đủ trong `02`–`04`, nhắc lại vì đây là "tối ưu" lớn nhất mà người dùng cảm nhận được: request chỉ ghi ý định rồi trả về; job làm phần chậm; realtime hoặc polling báo kết quả. Luồng Xero của lab đã làm đúng như vậy.

Bảo vệ hệ thống: `rate_limit` cho endpoint công khai (webhook của Xero là ứng viên, `12`); trần queue 500 job (`03`); HTTP timeout tường minh cho mọi lời gọi ra ngoài (`03`, `11`).

## Đo trước khi tối ưu

| Công cụ | Cho biết | Bằng chứng |
|---|---|---|
| Recorder | Mỗi request chạy những query nào, mất bao lâu, có trùng lặp không | `frappe/recorder.py:306` `record`, `:467` `start`, `:498` `stop` [S] |
| Monitor | Một dòng số liệu cho mỗi request/job, kèm trace id | `frappe/monitor.py:24-51` [S]; header `X-Frappe-Request-Id`, `app.py:297-298` |
| RQ Job trong Desk | Job nào chạy lâu, job nào hỏng | `03` |
| Header rate limit của Xero | Còn bao nhiêu lời gọi | `10` [G] |

Recorder là công cụ tìm N+1: bật trong Desk, bấm qua màn hình, đọc danh sách query. Việc bật/tắt là thao tác của bạn trong Desk.

## Áp vào luồng Xero: thứ thật sự đáng làm

Xếp theo lợi ích với mục tiêu chính. Mọi dữ kiện về Xero là [G] từ `10`.

| # | Kỹ thuật | Lợi gì | Đặt ở đâu |
|---|---|---|---|
| 1 | **Batch write**: tới ~50 invoice một lời gọi, kèm `summarizeErrors=false` | Import đầu kỳ: từ hàng giờ xuống hàng phút; ít chạm rate limit | `integrations/xero/client.py` + một operation outbox kiểu batch |
| 2 | **Đồng hồ rate limit dùng chung**: sau `429` ghi mốc `not_before`, mọi job kiểm tra trước khi gọi | Không đốt lượt retry, không bị khóa cả ngày | field `not_before` trên `Lab Xero Settings` (`12`) |
| 3 | **Đọc tăng dần**: `If-Modified-Since` + phân trang | Đồng bộ ngược chỉ kéo cái đã đổi | job định kỳ trong `tasks/` |
| 4 | **Cache dữ liệu tham chiếu** của Xero (accounts, tax rates): `@redis_cache(ttl=...)` | Bớt lời gọi lặp khi dựng payload | hàm đọc trong `integrations/xero/` |
| 5 | **Lấy token một lần ở đầu job**, trước lần ghi đầu tiên | Tránh refresh giữa chừng (và cái bẫy commit, `11`) | `tasks/xero_sync.py` |
| 6 | **Một queue riêng, 1–2 worker** cho Xero | Xero chỉ cho 5 lời gọi đồng thời; nhiều worker hơn chỉ gây `429` | queue tùy biến qua `workers` trong common site config ([S] `background_jobs.py:60-73`); là thay đổi hạ tầng của bạn |
| 7 | **Dựng payload không N+1**: một `get_doc` cho invoice (đã kèm items), customer qua `get_cached_value` | Job ngắn, giữ row lock ít hơn | `lab_xero/mapping…` |
| 8 | **Webhook làm gợi ý**, pull định kỳ làm lưới an toàn | Gần thời gian thực mà không poll dày | `12`, cần URL công khai |

Một điểm cần biết [I]: job hiện giữ row lock trên dòng outbox **trong suốt** lời gọi Xero ([S] `tasks/xero_sync.py:11, :22`). Đó là chủ đích (chống job trùng), nhưng nó là lý do HTTP timeout phải ngắn.

## Các stack ít gặp: đáng thử tới đâu trong lab này

| Stack | Giúp luồng Xero? | Chi phí | Đề xuất |
|---|---|---|---|
| Batch + `If-Modified-Since` của Xero | **Có, nhiều** | Chỉ code trong app | Làm, sau khi có client HTTP thật |
| Redis cache cho mapping/tham chiếu | Có | Không có gì mới | Làm khi có bảng mapping |
| SSE / WebSocket đẩy `sync_status` về SPA | Có, cho trải nghiệm | `socket.io-client` chưa nằm trong khóa UI (AGENTS.md B9) | Quyết định riêng; polling đủ cho demo |
| Read replica | Không | Một MariaDB thứ hai trong `docker/` | Chỉ đọc code `frappe/__init__.py:284-520` để hiểu |
| GraphQL (app cộng đồng) | Không | App ngoài + dependency; trùng vai với BFF | Bỏ qua, hoặc một buổi đọc riêng |
| gRPC | Không | Tiến trình riêng, dependency mới, không qua `/api` | Chỉ có nghĩa ở giai đoạn SAGA nhiều service (`13`, mục broker) |
| Broker (Redpanda/Kafka) | Chỉ để so sánh | Hạ tầng mới | Đã nằm trong kế hoạch, mục 6 của "Order" |

## Thử đi (đọc và Desk)

1. Mở Recorder trong Desk, bật, tạo một Lab Note, tắt: đếm số query của request `create_note` và tìm dòng insert `Lab Xero Outbox`.
2. Đọc `frappe/utils/caching.py:26-34, :78-90, :170-186` (ba docstring) và trả lời: cache nào **không** chia sẻ giữa hai worker?
3. Tính nhẩm: 3 000 invoice, mỗi lời gọi một cái, 60 lời gọi/phút, 5 000/ngày thì mất bao lâu? Với batch 50 thì sao?

## Còn chưa biết

- Thân của hầu hết các hàm ở trên; hành vi của `bulk_insert`/`bulk_update` với hook và permission là [G].
- `unbuffered_cursor` ở lớp cha chỉ `raise NotImplementedError` (`database.py:1563`); bản hiện thực cho MariaDB chưa mở.
- Lab chạy mấy worker web và mấy worker job (`03`).
- Mọi con số của Xero: checklist cuối `10`.
- App GraphQL cộng đồng: tên, độ trưởng thành và độ tương thích với v16 chưa kiểm tra.
