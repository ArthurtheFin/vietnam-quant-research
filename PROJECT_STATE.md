# PROJECT_STATE — cửa ngõ cho mọi phiên tương lai

**Đọc file này ĐẦU TIÊN, trước `PUSH_REVIEW.md`/`audit/PATH_TO_100.md`.** Cập
nhật lần cuối: 2026-07-19 (mục 5 — trỏ về `docs/PROJECT_HANDBOOK.md` làm tài
liệu gốc mới cho vận hành/đọc hiểu output; 2026-07-18 mục 4 — chẩn đoán/sửa
`ModuleNotFoundError` chặn LaunchAgent, xác nhận qua chạy thật). Nếu thông
tin ở đây và ở report gốc lệch nhau, tin
report gốc (file này là bản tóm tắt điều hướng, không phải nguồn sự thật) và
sửa lại file này.

## 1. Đang chạy live

| | Trạng thái |
|---|---|
| `alpha_score` v2 (`realized_vol_20d` 70% + `value_ma20` 30%) | **Shadow only, KHÔNG vốn thật** — `docs/reports/scoring/SCORE_V2_REPORT.md` mục "Trạng thái sau GĐ5". IC ổn định + sống sót FDR, nhưng DSR=0.0083, bootstrap CI chứa 0. |
| `alpha_score_shadow_v1` (composite cũ) | Chạy song song, chỉ để so sánh, không consumer nào dùng. |
| `data/signals/alpha_score_shadow_log.parquet` | 3 mốc thưa trước tự động hóa (07-09, 07-13, 07-15) + **chuỗi liên tục thật từ 2026-07-16** (ngày `scripts/daily_run.sh`/LaunchAgent có hiệu lực — mục 4). Không dựng lại điểm số cho các ngày đã bỏ lỡ (sẽ là look-ahead ngụy tạo) — xem `docs/reports/scoring/SCORE_V2_REPORT.md` mục "Cập nhật 2026-07-16". |
| `final_watchlist.py` (`client_ready_watchlist`, `trading_watchlist`, ...) | **Không xếp hạng alpha** — sắp theo `value_ma20` (thanh khoản), dán nhãn rõ trong cột `reason`. Quyết định Nhánh C, `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`. |
| Cập nhật giá hằng ngày | `scripts/update_prices_daily.py --universe` — 500 mã, incremental từ `max(date)` mỗi mã. |
| Cập nhật disclosure hằng ngày | `scripts/update_disclosure_daily.py --universe` — 500 mã, anti-join theo `NATURAL_KEY`. |
| Vốn thật theo watchlist/score? | Không tìm thấy bằng chứng trong hồ sơ repo (`docs/reports/scoring/SCORE_V2_REPORT.md`). Nếu có, khuyến nghị đưa về 0/mức học phí tối thiểu — xem file đó. |

## 2. Đã đóng (kèm report)

| Nhánh | Kết quả | Report |
|---|---|---|
| Data hygiene GĐ1-2 (backfill, dedup disclosure, lịch nghỉ, coverage) | Xong | `docs/reports/data/DATA_BASELINE.md`, `docs/reports/data/DISCLOSURE_BASELINE.md`, `PUSH_REVIEW.md` GĐ2 |
| Disclosure như tín hiệu dự báo bùng nổ/vượt trội | **Đóng vĩnh viễn, âm tính** — 3 round pre-register (test gốc → survivorship bias → đối chứng khớp cặp cho cụm/gia đình), không nhân tố nào đạt ngưỡng ứng viên | `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`, `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`, `docs/reports/disclosure/DISCLOSURE_PREREG_2_REPORT.md` |
| Kiểm định composite `final_watchlist` (75/100 điểm trọng số) | **Nhánh C** — composite lẫn "watchlist tối giản" đều không đạt tiêu chí đã khóa | `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` |
| `risk_score` — ứng viên nhân tố độc lập? | **Đóng, bằng chứng trùng cụm vol** (corr +0.822 với v2), không prereg riêng | `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2, `docs/reports/scoring/ROBUSTNESS_REPORT.md` mục 3 |
| Nghịch lý null-test percentile 71.0 vs 52.8 | **Giải xong** — nguyên nhân là gate `minimal_eligible` của `final_watchlist.py`, không phải dữ liệu/universe | `docs/reports/scoring/V2_STABILITY_NOTE.md` |
| Robustness thống kê (DSR/FDR/bootstrap CI) | Đo xong, không tune | `docs/reports/scoring/ROBUSTNESS_REPORT.md` |

**Pipeline disclosure vẫn chạy live** dù nhánh tín hiệu đã đóng — dữ liệu vẫn
phục vụ tiềm năng point-in-time universe (mục 3 dưới) và mọi hướng nghiên cứu
khác trong tương lai.

## 3. Đang chờ / còn mở

**4 điều kiện xem lại trạng thái shadow-only của v2** (`docs/reports/scoring/SCORE_V2_REPORT.md`):
1. **Mốc thời gian**: 6 tháng live shadow — **hạn 2027-01-16** (tính từ
   2026-07-16, ngày tự động hóa hằng ngày có hiệu lực — mục 4 dưới; dời từ
   hạn danh nghĩa cũ 2027-01-09 vì chuỗi 07-09→07-15 quá thưa để tính là "6
   tháng liên tục", xem `docs/reports/scoring/SCORE_V2_REPORT.md`). Nếu agent tự động lại ngừng
   chạy đều (mục 4), dời hạn tương ứng, không tính máy móc theo lịch.
2. **Drawdown**: xem lại ngay nếu danh mục v2-scored drawdown tệ hơn −25%.
3. **Lệch shadow v1**: xem lại nếu v2 kém hơn shadow v1 >10 điểm % tích lũy
   trong bất kỳ cửa sổ 60 phiên nào.
4. **Sharpe out-of-sample vs bootstrap CI** (mới, GĐ5.5): khi đủ 6 tháng, tính
   Sharpe out-of-sample thuần, so với CI `[−0.59, +1.32]` (năm hoá,
   `docs/reports/scoring/ROBUSTNESS_REPORT.md`).

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

**✅ ĐÃ XỬ LÝ XONG — cả 2 rào cản trước đây, xác nhận bằng chạy thật qua
launchd (`launchctl kickstart`, không phải chạy tay `bash`)**:

1. **TCC (macOS Privacy & Security)** — từng chặn hoàn toàn (`launchctl load`
   thành công, agent đăng ký được, nhưng khi launchd thực sự chạy `/bin/bash`
   vào script, báo `Operation not permitted` ngay khi vào thư mục dự án, do
   macOS bảo vệ `~/Desktop`/`~/Documents`/`~/Downloads` bằng TCC và tiến
   trình launchd sinh ra không tự thừa hưởng quyền Full Disk Access của
   phiên Terminal tương tác). **Đã tự hết chặn** — không rõ thời điểm/cách
   người dùng cấp quyền chính xác, chỉ xác nhận bằng bằng chứng gián tiếp:
   `logs/launchd_stderr.log` không còn dòng `Operation not permitted` mới
   nào sau 2026-07-16 19:42, và lần chạy 19:00 tối 2026-07-17 đã vượt qua
   được bước vào thư mục dự án (thất bại ở một nguyên nhân khác, xem dưới).
2. **`ModuleNotFoundError` (pandas/requests/yaml) — phát hiện MỚI, khác
   TCC, tối 2026-07-17**: `scripts/daily_run.sh`'s `PYTHON_BIN` mặc định là
   `python3` tra theo `PATH` kế thừa từ shell. Trong phiên Terminal tương
   tác, `python3` trỏ tới `/opt/anaconda3/bin/python3` (đúng env có cài
   `pandas==2.3.3`/`requests==2.32.3`/`PyYAML==6.0.2` theo
   `requirements.txt` đã pin) — nhưng môi trường `launchd` không kế thừa
   `PATH` đó, nên `python3` rơi về Python hệ thống của macOS (không có gói
   nào trong số này), khiến cả 4 bước fail ngay trong <2 giây với
   `ModuleNotFoundError`. **Đã sửa** (commit `bcd61d2`): `PYTHON_BIN` giờ
   mặc định là đường dẫn tuyệt đối `/opt/anaconda3/bin/python3` (vẫn override
   được qua biến môi trường), cộng một kiểm tra file thực thi tồn tại trước
   khi chạy bước nào, fail rõ ràng vào log thay vì để traceback
   `ModuleNotFoundError` mù mờ. **Đã kiểm chứng qua đúng cơ chế launchd**
   (`launchctl kickstart -k gui/501/com.vietnam-quant-research.dailyrun`,
   không phải chạy tay `bash`): `SUMMARY: 4/4 steps OK` tối 2026-07-18,
   `data/output/pipeline_metadata.json`'s `freshness_status: OK`,
   `latest_stock_date: 2026-07-17`; `alpha_score_shadow_log.parquet` có
   dòng mới `date=2026-07-17` (440 mã).

**Khoảng trống shadow log ngày 2026-07-17 — đã đóng, KHÔNG mất dữ liệu
thật**: lần chạy theo lịch 19:00 tối Thứ Sáu 2026-07-17 (nhằm chấm điểm
cho phiên giao dịch Thứ Sáu 2026-07-17) đã FAIL vì lỗi `ModuleNotFoundError`
ở trên. Lần chạy khắc phục tối Thứ Bảy 2026-07-18 (qua `launchctl
kickstart`) đã fetch được đúng dữ liệu giá THẬT của phiên Thứ Sáu
2026-07-17 (không có gì mới hơn để fetch vì Thứ Bảy không phải phiên giao
dịch — `latest_trading_date: 2026-07-17` xác nhận qua
`update_prices_daily.py`), và `run_alpha_scoring.py` chấm điểm/append vào
shadow log đúng ngày `2026-07-17` (dùng `scored["date"].max()`, không
phải ngày chạy thực tế 2026-07-18) — tức **KHÔNG phải dựng lại điểm cho
một ngày đã bỏ lỡ bằng thông tin nhìn-về-sau**, chỉ đơn giản là lấy dữ
liệu thật của phiên Thứ Sáu muộn hơn dự kiến ~28 giờ. Kết quả: chuỗi ngày
phân biệt trong `alpha_score_shadow_log.parquet` hiện là `..., 2026-07-16
(Thứ Năm), 2026-07-17 (Thứ Sáu)` — **liên tục ở cấp phiên giao dịch, 0
ngày giao dịch nào thực sự bị mất** (xác nhận: 2026-07-16/17 là 2 ngày
làm việc liền kề, không có ngày nghỉ lễ nào xen giữa theo
`config/vn_market_holidays.csv`). **Khuyến nghị: KHÔNG cần dời mốc "6
tháng" ở mục 3** — sự cố chỉ làm chậm một lần ghi log (SUMMARY tối
2026-07-17 vẫn đứng nguyên là FAIL trong lịch sử log, không sửa/xóa), chứ
không tạo lỗ hổng dữ liệu thật trong chuỗi out-of-sample. Đây là khuyến
nghị, không phải quyết định tự động — người dùng có thể xem lại nếu muốn
một tiêu chuẩn chặt hơn (vd. tính cả các lần SUMMARY FAIL là một dạng rủi
ro vận hành cần theo dõi, dù không làm mất dữ liệu lần này).

**LaunchAgent tự nhiên đã xác nhận qua dữ liệu thật, không chỉ qua log —
2026-07-22**: 2 ngày liên tiếp không ai chạy tay (2026-07-19, 2026-07-20),
`daily_run.sh` vẫn tự chạy đúng lịch qua launchd — xác nhận bằng chính dữ
liệu mới sinh (không chỉ đọc `logs/daily_run.log`, file cục bộ dễ mất khi
đổi máy): `data/full_history_v2/daily_price_update_log.jsonl` có 2 dòng
`run_at` mới (`2026-07-19T03:21:40Z`, `2026-07-20T16:08:27Z`),
`data/disclosure/daily_update_log.jsonl` tương tự (2 dòng mới, 0 lỗi fetch
mỗi lần), cộng 500+ symbol × 2 ngày disclosure raw JSON mới trong
`data/disclosure/raw/`, `data/signals/final_watchlist.csv` + `reports/*`
được regenerate, và `stock-decision-engine/outputs/` có thêm 1 lượt phân
tích mới (TCB, cùng GEX cũ được cập nhật). Toàn bộ đã commit
(`7582996`, message `data: automated daily sync 2026-07-19 → 2026-07-20`)
và push lên `origin/main`. Đây là bằng chứng mạnh hơn 1 bậc so với "log nói
đã chạy" — dữ liệu thật ở nhiều tầng độc lập (giá, disclosure, watchlist,
SDE) đều nhất quán với 2 lần chạy đó.

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
  không chạy. Cả 2 nguyên nhân đã gặp trước đây (TCC chưa cấp quyền, xem
  `logs/launchd_stderr.log`; `ModuleNotFoundError` do PATH launchd không
  thấy Python conda) đã xử lý (xem ngay trên) — nếu tái phát (vd. sau khi
  cài lại/di chuyển anaconda3), kiểm tra `logs/daily_run.log` xem lỗi cụ
  thể là gì trước khi giả định lại nguyên nhân cũ — chạy tay `bash scripts/daily_run.sh` trong
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

**Không phải dev, chỉ muốn vận hành hằng ngày, đọc hiểu một output, hay hiểu
toàn cảnh dự án?** Đọc `docs/PROJECT_HANDBOOK.md` trước (bản PDF đi kèm:
`docs/PROJECT_HANDBOOK.pdf`) — sổ tay toàn thư, viết để không cần đọc code:
Phần 0 (hệ thống là/không là gì, trạng thái hiện tại), Phần 1 (vận hành hằng
ngày), Phần 2 (đọc hiểu từng output), Phần 3 (khung ra quyết định), Phần 4
(kiến thức nền), Phần 5 (biên niên sử + hồ sơ đã đóng), Phần 6 (xử lý sự
cố), Phần 7 (tương lai/điều kiện thay đổi) + Phụ lục A-D (bản đồ repo, 15
report quan trọng, thuật ngữ, lệnh hay dùng). `docs/DAILY_OPERATING_GUIDE.md`
(cẩm nang cũ, đã hợp nhất vào Phần 0-3 của sổ tay) vẫn còn, giữ làm bản rút
gọn. 10 report dưới đây (đã trích dẫn xuyên suốt sổ tay) dành cho việc hiểu
SÂU một kết luận cụ thể.

1. **`PROJECT_STATE.md`** (file này) — điều hướng.
2. **`PUSH_REVIEW.md`** — nhật ký đầy đủ mọi round, mọi commit.
3. **`audit/PATH_TO_100.md`** — lộ trình điểm số + 4 critical gate.
4. **`docs/reports/data/DATA_BASELINE.md`** — dữ liệu giá (`full_history_v2`), caveat, coverage.
5. **`docs/reports/data/DISCLOSURE_BASELINE.md`** — dữ liệu disclosure, caveat, coverage.
6. **`docs/reports/scoring/SCORE_V2_REPORT.md`** — trạng thái `alpha_score` v2, điều kiện xem lại.
7. **`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`** — vì sao `final_watchlist` không xếp
   hạng alpha, bằng chứng từng thành phần.
8. **`docs/reports/scoring/ROBUSTNESS_REPORT.md`** — DSR/FDR/bootstrap, các con số cần trích khi
   đánh giá độ tin cậy bất kỳ nhân tố/chiến lược nào trong dự án.
9. **`docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`** — cận trên thô
   (+0.4%/+1.2%/+2.9% ở 20/60/120 ngày, hỗn hợp survivorship+size-tilt, KHÔNG
   phải mức trừ chính xác — sửa 2026-07-22) đối chiếu với MỌI số CAGR/Sharpe
   long-only.
10. **`docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`** + **`docs/reports/disclosure/DISCLOSURE_PREREG_2_REPORT.md`**
    — vì sao nhánh disclosure đóng, để không mở lại mà không có lý do mới.

`CLAUDE.md` — quy ước làm việc bắt buộc mọi session (đọc cùng lúc với file
này, không thay thế nhau).
