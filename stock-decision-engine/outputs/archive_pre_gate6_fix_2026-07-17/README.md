# archive_pre_gate6_fix_2026-07-17 — sinh từ dữ liệu nhiễm, chỉ để đối chiếu

60 file (`*_decision_summary.txt`, `*_sub_scores.csv`, `*_metrics.csv` cho 20
lần chạy, 16 mã) di dời từ `stock-decision-engine/outputs/` vào đây ngày
2026-07-17, trước khi regenerate lại toàn bộ trên dữ liệu sạch.

**Không dùng các file này cho bất kỳ quyết định/so sánh nào** — xem
`stock-decision-engine/AUDIT_SDE_REPORT.md` (finding #1, HIGH) và
`stock-decision-engine/GATE6_REGEN_COMPARISON.csv` để biết lý do và mức độ
ảnh hưởng cụ thể.

## Vì sao bị coi là nhiễm

Toàn bộ 20 lần chạy có ngày nhúng trong tên file từ 2026-06-24 đến
2026-07-06 — **sớm hơn** ngày `data/processed/clean_daily_ohlcv.parquet`
được vá thật từ `full_history_v2` (2026-07-13, commit `28b9f60`, audit gate
#6). Hai vấn đề độc lập được xác nhận ảnh hưởng tới các file này:

1. **Giá bị lỗi** (5/16 mã: BID, HDB, HPG, TPB, VCB) — bug trộn
   raw/adjusted-close đã biết, xác nhận qua ladder test
   (`AUDIT_SDE_REPORT.md` mục 2.2).
2. **Cửa sổ lịch sử bị cắt ngắn** (phát hiện khi regenerate vòng này, không
   có trong audit gốc) — trước khi backfill đầy đủ hoàn tất (2026-07-10),
   `data/processed/clean_daily_ohlcv.parquet` chỉ có lịch sử ngắn cho hầu
   hết các mã (vd. POW chỉ 295 dòng, SSI 328, STB 332, ACB/GEX 345, VIX 295,
   VPL 288 — so với `lookback_days: 756` mà `config.yaml` yêu cầu). Với các
   mã này, `alpha`/`risk` sub-score (Sharpe/Sortino/Calmar/Jensen
   alpha/information ratio/max drawdown/CVaR/skewness — tính trên TOÀN cửa
   sổ, không phải rolling-window) bị tính trên mẫu ngắn hơn nhiều so với
   cấu hình dự định, không liên quan tới bug raw/adjusted-close.

Chi tiết dòng-theo-dòng (điểm cuối, từng sub-score, quyết định có lật
không) nằm ở `stock-decision-engine/GATE6_REGEN_COMPARISON.csv`, script
tái tạo ở `scratch/sde_regenerate_gate6.py`.

## Không xóa

File này giữ nguyên vĩnh viễn (không xóa) — bằng chứng cho việc dữ liệu đã
thay đổi và tại sao, đúng quy ước "không xóa artifact, chỉ đánh dấu" của dự
án chính (xem `data/quarantine_existing_v1/README.md` cho tiền lệ tương
tự).
