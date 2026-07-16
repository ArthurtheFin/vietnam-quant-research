# PROJECT_STATE — cửa ngõ cho mọi phiên tương lai

**Đọc file này ĐẦU TIÊN, trước `PUSH_REVIEW.md`/`audit/PATH_TO_100.md`.** Cập
nhật lần cuối: 2026-07-16. Nếu thông tin ở đây và ở report gốc lệch nhau, tin
report gốc (file này là bản tóm tắt điều hướng, không phải nguồn sự thật) và
sửa lại file này.

## 1. Đang chạy live

| | Trạng thái |
|---|---|
| `alpha_score` v2 (`realized_vol_20d` 70% + `value_ma20` 30%) | **Shadow only, KHÔNG vốn thật** — `SCORE_V2_REPORT.md` mục "Trạng thái sau GĐ5". IC ổn định + sống sót FDR, nhưng DSR=0.0083, bootstrap CI chứa 0. |
| `alpha_score_shadow_v1` (composite cũ) | Chạy song song, chỉ để so sánh, không consumer nào dùng. |
| `data/signals/alpha_score_shadow_log.parquet` | Bắt đầu **2026-07-09**. Tính đến 2026-07-16 mới có 3 mốc ngày (07-09, 07-13, 07-15) — **KHÔNG chạy đều mỗi ngày**, chỉ append khi có phiên chạy `scripts/run_alpha_scoring.py` (không có cron/launchd, xem mục 3). Mốc "6 tháng live" chỉ đến đúng hạn nếu pipeline thực sự chạy đều — nếu thưa, dời hạn tương ứng, không tính máy móc theo lịch. |
| `final_watchlist.py` (`client_ready_watchlist`, `trading_watchlist`, ...) | **Không xếp hạng alpha** — sắp theo `value_ma20` (thanh khoản), dán nhãn rõ trong cột `reason`. Quyết định Nhánh C, `WATCHLIST_VALIDATION_REPORT.md`. |
| Cập nhật giá hằng ngày | `scripts/update_prices_daily.py --universe` — 500 mã, incremental từ `max(date)` mỗi mã. |
| Cập nhật disclosure hằng ngày | `scripts/update_disclosure_daily.py --universe` — 500 mã, anti-join theo `NATURAL_KEY`. |
| Vốn thật theo watchlist/score? | Không tìm thấy bằng chứng trong hồ sơ repo (`SCORE_V2_REPORT.md`). Nếu có, khuyến nghị đưa về 0/mức học phí tối thiểu — xem file đó. |

## 2. Đã đóng (kèm report)

| Nhánh | Kết quả | Report |
|---|---|---|
| Data hygiene GĐ1-2 (backfill, dedup disclosure, lịch nghỉ, coverage) | Xong | `DATA_BASELINE.md`, `DISCLOSURE_BASELINE.md`, `PUSH_REVIEW.md` GĐ2 |
| Disclosure như tín hiệu dự báo bùng nổ/vượt trội | **Đóng vĩnh viễn, âm tính** — 3 round pre-register (test gốc → survivorship bias → đối chứng khớp cặp cho cụm/gia đình), không nhân tố nào đạt ngưỡng ứng viên | `DISCLOSURE_EVENT_STUDY_REPORT.md`, `SURVIVORSHIP_BIAS_ESTIMATE.md`, `DISCLOSURE_PREREG_2_REPORT.md` |
| Kiểm định composite `final_watchlist` (75/100 điểm trọng số) | **Nhánh C** — composite lẫn "watchlist tối giản" đều không đạt tiêu chí đã khóa | `WATCHLIST_VALIDATION_REPORT.md` |
| `risk_score` — ứng viên nhân tố độc lập? | **Đóng, bằng chứng trùng cụm vol** (corr +0.822 với v2), không prereg riêng | `WATCHLIST_VALIDATION_REPORT.md` mục 2, `ROBUSTNESS_REPORT.md` mục 3 |
| Nghịch lý null-test percentile 71.0 vs 52.8 | **Giải xong** — nguyên nhân là gate `minimal_eligible` của `final_watchlist.py`, không phải dữ liệu/universe | `V2_STABILITY_NOTE.md` |
| Robustness thống kê (DSR/FDR/bootstrap CI) | Đo xong, không tune | `ROBUSTNESS_REPORT.md` |

**Pipeline disclosure vẫn chạy live** dù nhánh tín hiệu đã đóng — dữ liệu vẫn
phục vụ tiềm năng point-in-time universe (mục 3 dưới) và mọi hướng nghiên cứu
khác trong tương lai.

## 3. Đang chờ / còn mở

**4 điều kiện xem lại trạng thái shadow-only của v2** (`SCORE_V2_REPORT.md`):
1. **Mốc thời gian**: 6 tháng live shadow — **hạn danh nghĩa 2027-01-09**
   (tính từ 2026-07-09), NHƯNG xem cảnh báo ở mục 1: shadow log hiện không
   chạy đều, hạn thật có thể trễ hơn nếu pipeline không chạy thường xuyên hơn.
2. **Drawdown**: xem lại ngay nếu danh mục v2-scored drawdown tệ hơn −25%.
3. **Lệch shadow v1**: xem lại nếu v2 kém hơn shadow v1 >10 điểm % tích lũy
   trong bất kỳ cửa sổ 60 phiên nào.
4. **Sharpe out-of-sample vs bootstrap CI** (mới, GĐ5.5): khi đủ 6 tháng, tính
   Sharpe out-of-sample thuần, so với CI `[−0.59, +1.32]` (năm hoá,
   `ROBUSTNESS_REPORT.md`).

**Gate #3 — survivorship bias / point-in-time universe** (`audit/PATH_TO_100.md`
critical gate, vẫn OPEN, việc lớn nhất còn lại): chưa có nguồn dữ liệu lịch sử
niêm yết/hủy niêm yết thật. Đã có bước đầu (không phải giải pháp đầy đủ):
`src/validation/trading_status.py`'s bảng point-in-time (`ACTIVE`/`STALE_SHORT`/
`INACTIVE_LONG`, chỉ có lịch sử thật từ 2026-07-13) + coverage-ratio proxy
(gộp vào `LOW_LIQUIDITY`). 18 mã `INACTIVE_LONG` bị loại khỏi rổ đủ điều kiện
ở MỌI ngày lịch sử (không phải chỉ từ khi họ ngừng giao dịch) — một hạn chế đã
biết, không phải point-in-time thật. Con đường tiếp theo: tìm nguồn dữ liệu
hủy niêm yết chính thức (SSI/HOSE/HNX/UPCOM bulletin hoặc vendor thứ ba); dữ
liệu disclosure (mục 2) là một nguồn tiềm năng phụ trợ (hoạt động nội bộ bất
thường trước khi hủy niêm yết) nhưng chưa được khai thác theo hướng này.

**`tail_ratio_60d` trong `risk_score`**: hướng xếp hạng có thể sai (chưa kiểm
định riêng), việc nhỏ còn treo từ `audit/PATH_TO_100.md` mục 3.

**Tách holdout riêng cho tham số portfolio construction** (size/sector cap):
chưa làm, `audit/PATH_TO_100.md` mục 9.

## 4. Quy trình vận hành định kỳ

**Hằng ngày (thủ công — KHÔNG có cron/launchd nào cài, xác nhận GĐ2):**
```
python scripts/update_prices_daily.py --universe
python scripts/update_disclosure_daily.py --universe
python scripts/update_index_data.py          # trước generate_features, tránh benchmark lệch mốc
python scripts/run_daily_pipeline.py --offline   # hoặc bỏ --offline nếu muốn fetch online trong bước features
```
`run_daily_pipeline.py` tự chạy: `generate_features` → `generate_signals` →
`run_alpha_scoring` (đây là bước append `alpha_score_shadow_log.parquet`) →
`generate_trade_cards` → `run_stealth_accumulation_screen` →
`build_cashflow_board_symbols` → `run_meta_ranking` (xây `final_watchlist`) →
`build_cashflow_board` (áp `apply_post_cashflow_overlay`, chốt `client_ready`).

**Dấu hiệu bất thường cần chú ý ngay:**
- **Shadow log ngắt quãng**: `alpha_score_shadow_log.parquet`'s ngày mới nhất
  cách ngày hôm nay >2-3 phiên giao dịch → pipeline không chạy đều, mốc "6
  tháng" ở mục 3 sẽ sai nếu tính máy móc theo lịch.
- **Update fail**: `n_fetch_errors > 0` trong log của `update_prices_daily.py`/
  `update_disclosure_daily.py`, hoặc `n_updated` bất thường thấp so với ~440+
  thường thấy.
- **Gate loại gần hết universe**: `client_ready=0` VÀ `trading=0` cùng lúc,
  hoặc phần lớn 500 mã rơi vào `data_review` — dấu hiệu lặp lại lỗi
  STALE_DATA hàng loạt đã gặp ở GĐ1-2 (`audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md`),
  thường do giá và benchmark lệch mốc ngày vì quên chạy `update_index_data.py`.
- **`freshness_status` khác `OK`** trong output `run_daily_pipeline.py`.

## 5. Bản đồ hồ sơ — 10 report nên đọc theo thứ tự này

1. **`PROJECT_STATE.md`** (file này) — điều hướng.
2. **`PUSH_REVIEW.md`** — nhật ký đầy đủ mọi round, mọi commit.
3. **`audit/PATH_TO_100.md`** — lộ trình điểm số + 4 critical gate.
4. **`DATA_BASELINE.md`** — dữ liệu giá (`full_history_v2`), caveat, coverage.
5. **`DISCLOSURE_BASELINE.md`** — dữ liệu disclosure, caveat, coverage.
6. **`SCORE_V2_REPORT.md`** — trạng thái `alpha_score` v2, điều kiện xem lại.
7. **`WATCHLIST_VALIDATION_REPORT.md`** — vì sao `final_watchlist` không xếp
   hạng alpha, bằng chứng từng thành phần.
8. **`ROBUSTNESS_REPORT.md`** — DSR/FDR/bootstrap, các con số cần trích khi
   đánh giá độ tin cậy bất kỳ nhân tố/chiến lược nào trong dự án.
9. **`SURVIVORSHIP_BIAS_ESTIMATE.md`** — mức sàn hiệu chỉnh
   (+0.4%/+1.2%/+2.9% ở 20/60/120 ngày) áp cho MỌI số CAGR/Sharpe long-only.
10. **`DISCLOSURE_EVENT_STUDY_REPORT.md`** + **`DISCLOSURE_PREREG_2_REPORT.md`**
    — vì sao nhánh disclosure đóng, để không mở lại mà không có lý do mới.

`CLAUDE.md` — quy ước làm việc bắt buộc mọi session (đọc cùng lúc với file
này, không thay thế nhau).
