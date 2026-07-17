# docs/reports/ — mọi research/design/audit report, theo chủ đề

Trước đây các file này nằm rải rác ở thư mục gốc. Đọc `PROJECT_STATE.md` mục 5
("Bản đồ hồ sơ") trước — đó là thứ tự đọc khuyến nghị cho 10 report quan
trọng nhất, không phải danh sách này.

- `data/` — baseline + audit cho dữ liệu giá và disclosure (`DATA_BASELINE.md`,
  `DISCLOSURE_BASELINE.md`, thiết kế backfill/pipeline).
- `disclosure/` — nhánh nghiên cứu disclosure-làm-tín-hiệu (đã đóng, âm
  tính): prereg + report từng round.
- `scoring/` — nghiên cứu factor/alpha_score/final_watchlist: design,
  backtest, forensic, robustness, validation.
- `deploy/` — prompt/plan/report của lần triển khai công thức chấm điểm vào
  production.
- `codebase_audit/` — audit tổng thể pipeline/codebase (khác `audit/` ở gốc
  dự án, vốn là audit riêng cho điểm số/gate).

Report gốc ở thư mục gốc (`README.md`, `CLAUDE.md`, `PROJECT_STATE.md`,
`PUSH_REVIEW.md`) và `audit/` (lộ trình + gate) giữ nguyên vị trí — đó là các
file cửa ngõ đọc đầu mỗi phiên theo `CLAUDE.md` mục 3.
