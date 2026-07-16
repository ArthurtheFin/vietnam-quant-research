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
| `data/signals/alpha_score_shadow_log.parquet` | 3 mốc thưa trước tự động hóa (07-09, 07-13, 07-15) + **chuỗi liên tục thật từ 2026-07-16** (ngày `scripts/daily_run.sh`/LaunchAgent có hiệu lực — mục 4). Không dựng lại điểm số cho các ngày đã bỏ lỡ (sẽ là look-ahead ngụy tạo) — xem `SCORE_V2_REPORT.md` mục "Cập nhật 2026-07-16". |
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
1. **Mốc thời gian**: 6 tháng live shadow — **hạn 2027-01-16** (tính từ
   2026-07-16, ngày tự động hóa hằng ngày có hiệu lực — mục 4 dưới; dời từ
   hạn danh nghĩa cũ 2027-01-09 vì chuỗi 07-09→07-15 quá thưa để tính là "6
   tháng liên tục", xem `SCORE_V2_REPORT.md`). Nếu agent tự động lại ngừng
   chạy đều (mục 4), dời hạn tương ứng, không tính máy móc theo lịch.
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

**Tự động hóa từ 2026-07-16**: `scripts/daily_run.sh` gộp cả 4 bước dưới đây
thành một lệnh (`update_prices_daily` → `update_disclosure_daily` →
`update_index_data` → `run_daily_pipeline --offline`), log vào
`logs/daily_run.log` (mỗi bước có dòng START/OK/FAIL riêng, FAIL bọc trong
`######` để dễ tìm). Chạy tay: `bash scripts/daily_run.sh` (thêm `--force`
để chạy lại dù hôm nay đã chạy rồi).

**LaunchAgent** (`~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist`,
bản gốc versioned tại `scripts/com.vietnam-quant-research.dailyrun.plist`):
lên lịch chạy `daily_run.sh` 19:00 các ngày trong tuần (`StartCalendarInterval`)
+ chạy bù khi máy khởi động/đăng nhập lại nếu lỡ mốc (`RunAtLoad=true`,
`daily_run.sh` tự kiểm tra mốc SUMMARY cuối trong log để không chạy trùng 2
lần/ngày).

**⚠️ ĐANG BỊ CHẶN bởi macOS TCC (Privacy & Security), cần người dùng thao
tác thủ công**: đã xác nhận bằng thử nghiệm thật — `launchctl load` thành
công, agent đăng ký được, nhưng khi launchd thực sự chạy `/bin/bash` vào
script, nó báo `Operation not permitted` ngay khi vào thư mục dự án. Nguyên
nhân xác định qua thử nghiệm đối chứng (một job launchd trỏ vào `/tmp`
chạy trơn tru; job giống hệt trỏ vào `~/Desktop/...` thì lỗi): macOS bảo vệ
thư mục `~/Desktop` (và `~/Documents`, `~/Downloads`) bằng TCC — tiến trình
launchd sinh ra không tự động thừa hưởng quyền Full Disk Access mà phiên
Terminal tương tác đang có. **Cách sửa (chỉ người dùng làm được, cần giao
diện, không thể làm qua script)**: System Settings → Privacy & Security →
Full Disk Access → bấm "+" → thêm `/bin/bash` (Cmd+Shift+G, gõ `/bin/bash`)
→ bật toggle. Sau đó không cần làm gì thêm — lần chạy theo lịch/đăng nhập
kế tiếp sẽ tự hoạt động. Cho đến khi đó: agent vẫn cài/nạp đúng nhưng mỗi
lần trigger chỉ ghi lỗi vào `logs/launchd_stderr.log`, không có tác dụng —
chạy tay `bash scripts/daily_run.sh` vẫn hoạt động bình thường (không qua
launchd nên không dính TCC).

**Kiểm tra/tắt agent (3 dòng)**:
```
launchctl list | grep vietnam-quant-research   # có dòng kết quả = đang nạp; cột đầu là PID nếu đang chạy, "-" nếu không
launchctl unload ~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist   # tắt (đến lần đăng nhập sau vẫn tắt, trừ khi load lại)
launchctl load ~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist     # nạp lại
```

`run_daily_pipeline.py` (bên trong `daily_run.sh`) tự chạy: `generate_features`
→ `generate_signals` → `run_alpha_scoring` (đây là bước append
`alpha_score_shadow_log.parquet`) → `generate_trade_cards` →
`run_stealth_accumulation_screen` → `build_cashflow_board_symbols` →
`run_meta_ranking` (xây `final_watchlist`) → `build_cashflow_board` (áp
`apply_post_cashflow_overlay`, chốt `client_ready`).

**Dấu hiệu bất thường cần chú ý ngay:**
- **`logs/daily_run.log` không có dòng SUMMARY mới trong 2-3 ngày** → agent
  không chạy (nhiều khả năng vẫn là TCC chưa được cấp quyền, xem
  `logs/launchd_stderr.log`) — chạy tay `bash scripts/daily_run.sh` trong
  lúc chờ, và mốc "6 tháng" ở mục 3 sẽ dời tương ứng nếu gián đoạn kéo dài.
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

**Không phải dev, chỉ muốn vận hành hằng ngày?** Đọc
`docs/DAILY_OPERATING_GUIDE.md` trước — cẩm nang một trang cho chủ dự án
(checklist buổi sáng, đọc hiểu watchlist, khung ra quyết định đầu tư, xử lý
sự cố, điều kiện xem lại v2), viết để không cần đọc code. 10 report dưới
đây dành cho việc hiểu SÂU một kết luận cụ thể.

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
