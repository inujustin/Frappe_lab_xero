# 05. Cấu trúc code: cái gì nằm ở đâu, ai gọi ai

Toàn bộ code của phần tích hợp nằm trong một app, `frappe-bench/apps/lab_core/lab_core/`. Khoảng 1000 dòng, chia thành mười file. Không file nào của Frappe hay ERPNext bị sửa.

## Cây thư mục (chỉ phần Xero)

```text
lab_core/
├── hooks.py                          ĐẤU NỐI: 4 hook, không có logic
│
├── setup/                            CẤU HÌNH BẰNG CODE (chạy sau mỗi lần migrate)
│   ├── xero_connection.py              tạo Connected App "xero", điền Lab Xero Settings      92 dòng
│   └── customizations.py               thêm field lab_xero_* vào Customer, Sales Order       47 dòng
│
├── overrides/                        THỨ GẮN VÀO ERPNEXT (mỏng, chỉ gọi sang module của ta)
│   └── sales_order.py                  on_submit, on_cancel                                  34 dòng
│
├── lab_xero/                         MODULE NGHIỆP VỤ CỦA TA
│   ├── outbox.py                       ghi "việc cần gửi", xếp job                           41 dòng
│   ├── mapping.py                      Customer → Contact, Sales Order → Invoice             64 dòng
│   ├── inbound.py                      credit note từ Xero → dòng của ta + comment           78 dòng
│   └── doctype/                        3 DocType: Outbox, Settings, Credit Note
│
├── tasks/                            BACKGROUND JOB (nơi duy nhất được gọi Xero)
│   ├── xero_sync.py                    chiều đi: process_outbox, discover_tenant            179 dòng
│   └── xero_pull.py                    chiều về: pull_changes, pull_sales_order             108 dòng
│
├── integrations/xero/                NÓI CHUYỆN VỚI XERO (nơi duy nhất dựng HTTP request)
│   └── client.py                       XeroClient, get_client, 4 class lỗi                  224 dòng
│
├── api/
│   └── xero.py                       ENDPOINT cho 2 nút: retry_sync, refresh                 63 dòng
│
└── public/js/
    └── sales_order.js                NÚT trên form Sales Order                               39 dòng
```

## Ai gọi ai

Mũi tên chỉ đi một chiều, từ trên xuống. Không file nào ở dưới gọi ngược lên.

```text
   Desk (form Sales Order)          Scheduler của Frappe             bench migrate
        │           │                        │                            │
   Submit/Cancel   nút Retry/Refresh         │ mỗi 5 phút                 │ after_migrate
        │           │                        │                            │
        ▼           ▼                        │                            ▼
 overrides/      api/xero.py                 │                     setup/xero_connection.py
 sales_order.py     │                        │                     setup/customizations.py
        │           │                        │
        └─────┬─────┘                        │
              ▼                              │
      lab_xero/outbox.py                     │
        (ghi dòng, xếp job)                  │
              │ sau commit                   │
              ▼                              ▼
      tasks/xero_sync.py             tasks/xero_pull.py
        │        │                     │         │
        │        ▼                     │         ▼
        │  lab_xero/mapping.py         │   lab_xero/inbound.py
        ▼                              ▼
      integrations/xero/client.py  ───────────►  Xero (HTTPS)
```

## Năm luật giữ cho cấu trúc này đúng

| # | Luật | Nhìn thấy ở đâu trong code |
|---|---|---|
| 1 | **Chỉ `tasks/` được gọi Xero.** Request của người dùng không bao giờ chờ Xero. | `overrides/sales_order.py` và `api/xero.py` không import `client`; chúng chỉ gọi `outbox.queue` hoặc `frappe.enqueue` |
| 2 | **Chỉ `integrations/xero/` dựng HTTP request.** | chỉ `client.py` có `import requests` |
| 3 | **Code của ERPNext không bị sửa.** Thứ gắn vào ERPNext nằm mỏng trong `overrides/`. | `overrides/sales_order.py` dài 34 dòng, chỉ kiểm tra và gọi `outbox.queue` |
| 4 | **Code của ta không bao giờ bị hook hay override.** Muốn đổi thì sửa thẳng. | `lab_xero/`, `tasks/`, `integrations/`, `api/` đều là file của ta |
| 5 | **Cấu hình nằm trong code**, bí mật nằm trong site config. | `setup/` tạo bản ghi; không ai gõ form trong Desk |

## `hooks.py`: bốn dòng đấu nối

`hooks.py` là file Frappe đọc để biết khi nào gọi code của ta. Nó không chứa logic.

```python
# hooks.py:12-29
# Xero demo: configuration lives in code and is applied after every migrate.
after_migrate = [
	"lab_core.setup.xero_connection.apply",
	"lab_core.setup.customizations.apply",
]

doc_events = {
	"Sales Order": {
		"on_submit": "lab_core.overrides.sales_order.on_submit",
		"on_cancel": "lab_core.overrides.sales_order.on_cancel",
	},
}

doctype_js = {"Sales Order": "public/js/sales_order.js"}

scheduler_events = {
	"cron": {"*/5 * * * *": ["lab_core.tasks.xero_pull.pull_changes"]},
}
```

| Hook | Frappe làm gì | Đổi xong cần |
|---|---|---|
| `after_migrate` | gọi hai hàm setup sau mỗi `bench migrate` | restart + migrate |
| `doc_events` | khi một Sales Order được submit hoặc cancel, gọi handler của ta **sau** code của ERPNext, trong cùng transaction | restart |
| `doctype_js` | nạp file JS của ta vào form Sales Order | restart, tải lại trang |
| `scheduler_events` | chạy `pull_changes` theo lịch | restart + **migrate** (Frappe tạo dòng lịch lúc migrate) |

Đã quan sát: lịch `*/5` thực tế chạy vào các mốc 4 phút của scheduler (14:48, 14:52…), tức là "khoảng mỗi 5 phút", không đúng từng giây.

## Vì sao chia thành các lớp này

| Lớp | Biết về | Không biết về | Lợi ích |
|---|---|---|---|
| `overrides/`, `api/` | Sales Order, quyền, trạng thái | Xero, HTTP | request luôn nhanh; Xero chết thì người dùng vẫn submit được |
| `lab_xero/outbox.py` | "có một việc cần làm" | việc đó làm thế nào | việc không bao giờ mất dù job hỏng |
| `lab_xero/mapping.py` | hình dạng dữ liệu hai bên | HTTP, database | đổi luật ánh xạ ở một chỗ; hàm thuần, dễ đọc |
| `tasks/` | thứ tự các bước, khóa, lỗi thì làm gì | chi tiết HTTP | toàn bộ "kịch bản" của một lần đồng bộ nằm trong một file |
| `integrations/xero/client.py` | URL, header, mã lỗi của Xero | Sales Order, Customer | đổi nhà cung cấp hoặc phiên bản API chỉ đụng một file |

## Ba đường đi chính, theo file

**Chiều đi (Sales Order → Xero):**

```text
Submit ─► overrides/sales_order.py:on_submit ─► lab_xero/outbox.py:queue ─► [commit]
       ─► tasks/xero_sync.py:process_outbox ─► _create_invoice
              ├─► integrations/xero/client.py: find_invoice, find_contact, create_contact, create_invoice, get_invoices
              └─► lab_xero/mapping.py: customer_to_contact, sales_order_to_invoice
```

**Chiều về (Xero → Sales Order):**

```text
Scheduler ─► tasks/xero_pull.py:pull_changes ─► client: get_invoices, get_credit_notes
                 ├─► _apply_invoices            (ghi đè field trên Sales Order)
                 └─► lab_xero/inbound.py:apply_credit_notes   (Lab Xero Credit Note + comment)

Nút Refresh ─► api/xero.py:refresh ─► [commit] ─► tasks/xero_pull.py:pull_sales_order ─► (như trên, cho một đơn)
```

**Thử lại:**

```text
Nút Retry ─► api/xero.py:retry_sync ─► lab_xero/outbox.py:queue (mở lại cùng dòng) ─► [commit] ─► process_outbox
```
