# SỔ TAY DỰ ÁN — vietnam-quant-research

**Lô 1/3** (Phần 0 + 1 + 2). Markdown là bản gốc; PDF sẽ xuất ở lô 3.
Viết cho 3 người đọc: chủ dự án tra nhanh mỗi sáng, chủ dự án tự đọc lại
sau 6 tháng, và người ngoài muốn hiểu vì sao hệ thống ở trạng thái hiện
tại. Mọi khẳng định về bằng chứng trích đúng report + commit hash; số
liệu/tên cột/tên file lấy trực tiếp từ repo tại commit `03bb13d` (nhánh
`main`, 2026-07-18) — không viết từ trí nhớ. Chỗ nào không xác minh được
ghi rõ **[chưa xác minh]**.

---

# PHẦN 0 — TRANG ĐẦU TIÊN

## 0.1. Hệ thống LÀ gì

Đây là một hạ tầng **dữ liệu sạch + sàng lọc + tra cứu dữ kiện** cho ~500
mã cổ phiếu đang niêm yết trên HOSE/HNX/UPCOM (Việt Nam), chạy tự động
hằng ngày. Cụ thể, hệ thống:

1. Thu thập và làm sạch dữ liệu giá (OHLCV) và dữ liệu công bố thông tin
   giao dịch nội bộ/cổ đông lớn ("disclosure") cho toàn bộ universe 500 mã
   — `data/full_history_v2/` (giá) và `data/disclosure/events.parquet`
   (disclosure), cập nhật incremental mỗi ngày (`scripts/update_prices_daily.py`,
   `scripts/update_disclosure_daily.py`).
2. Tính một tập chỉ số/nhân tố kỹ thuật-thống kê (biến động, thanh khoản,
   xu hướng, tương quan với VNINDEX...) cho từng mã, từng ngày.
3. **Sàng lọc** 500 mã xuống các danh sách nhỏ hơn theo tiêu chí dữ liệu
   sạch + đang giao dịch thật + đủ thanh khoản (`data/signals/final_watchlist.csv`
   và các bảng `data/output/*_watchlist.csv`) — xem Phần 2.1.
4. Cung cấp **dữ kiện thô có ngữ cảnh** để tra cứu khi tự nghiên cứu một
   mã cụ thể: chỉ số kỹ thuật (`stock-decision-engine/`, xem Phần 2.2-2.3),
   dữ liệu disclosure (Phần 2.6), xếp hạng thử nghiệm `alpha_score` (Phần
   2.2, 2.7).
5. Ghi lại toàn bộ quá trình kiểm định thống kê của chính nó — mọi nhân
   tố/chiến lược trước khi được tin dùng đều phải qua một quy trình
   pre-register → chạy một lần → báo cáo trung thực (kể cả khi kết quả
   âm tính), thay vì chọn tham số sau khi nhìn kết quả
   (`CLAUDE.md` mục 8).

## 0.2. Hệ thống KHÔNG là gì

**Hệ thống này không khuyến nghị mua/bán, và không xếp hạng "mã tốt
nhất".** Đây không phải một giới hạn tạm thời chờ hoàn thiện — đó là kết
luận của chính quá trình kiểm định nội bộ.

Thành phần có bằng chứng thống kê tốt nhất từng tìm được trong toàn bộ dự
án — `alpha_score` v2 (`realized_vol_20d` 70% + `value_ma20` 30%) — có hệ
số xếp hạng (IC) ổn định qua thời gian, nhưng khi kiểm định xem đây có
phải một **chiến lược đáng cược vốn thật** hay không, Deflated Sharpe
Ratio (đã khấu trừ trung thực cho 560 lần thử nghiệm trong lịch sử dự án)
chỉ đạt **0.0083** — nghĩa là chỉ còn 0.83% xác suất đây là kỹ năng thật
chứ không phải may mắn trong 560 lần thử; khoảng tin cậy bootstrap 95%
cho cả CAGR (`[−9.58%, +19.32%]`) lẫn Sharpe (`[−0.59, +1.32]`) đều
**chứa số 0** — không thể bác bỏ giả thuyết "hiệu suất thật bằng 0"
(`docs/reports/scoring/ROBUSTNESS_REPORT.md` mục 5; kết luận vận hành tại
`docs/reports/scoring/SCORE_V2_REPORT.md` mục "Trạng thái sau GĐ5").
Danh sách sàng lọc chính (`final_watchlist`) hiện xếp theo **thanh khoản**,
không xếp theo điểm số dự báo nào cả, sau khi cả điểm tổng hợp cũ lẫn một
phiên bản "tối giản" của nó đều không đạt tiêu chí kiểm định đã khóa
trước (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`, "Nhánh C").
Công cụ chấm điểm mã riêng lẻ (`stock-decision-engine/`) cũng đã trải qua
cùng số phận sau vòng kiểm định thứ 3 và gỡ bỏ hoàn toàn điểm tổng hợp/
nhãn quyết định (`stock-decision-engine/SDE_SCORING_REPORT.md`).

## 0.3. Trạng thái tại ngày viết (2026-07-18, commit `03bb13d`)

| Thành phần | Trạng thái |
|---|---|
| `alpha_score` v2 | **Shadow-only, không vốn thật**, live từ 2026-07-16 (`docs/reports/scoring/SCORE_V2_REPORT.md`) |
| `final_watchlist` | **Nhánh C** — xếp theo thanh khoản (`value_ma20`), không xếp theo điểm dự báo (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`) |
| `stock-decision-engine` (SDE) | **Bảng dữ kiện thô** — `final_score`/`decision` đã gỡ bỏ khỏi code, Nhánh C Vòng 3 (`stock-decision-engine/SDE_SCORING_REPORT.md`, commit `aa773a2`) |
| Tự động hóa hằng ngày | LaunchAgent lên lịch 19:00 các ngày trong tuần (`scripts/daily_run.sh`) |
| Điểm audit | Round 2: **78/100** (từ 58/100 Round 1), còn **1/4 critical gate mở** (Gate #3 — survivorship bias) (`audit/round2/delta_scorecard.md`, commit `03bb13d`) |

**Cập nhật cùng ngày (2026-07-18, sau khi lô 1 được duyệt)**: log thật
(`logs/daily_run.log`) cho thấy lần chạy tự động tối 2026-07-16 thành công
(`SUMMARY: 4/4 steps OK`), nhưng lần chạy theo lịch tối 2026-07-17 19:00
FAIL cả 4/4 bước vì `ModuleNotFoundError: No module named 'pandas'` (và
`requests`, `yaml`) — môi trường `launchd` không kế thừa PATH của shell
tương tác nên `python3` rơi về Python hệ thống macOS thay vì
`/opt/anaconda3/bin/python3` (nơi cài các thư viện này); rào cản TCC từng
chặn hoàn toàn trước đó đã tự hết (không phải nguyên nhân của lần fail
này). **Đã chẩn đoán + sửa + kiểm chứng** cùng ngày: `scripts/daily_run.sh`
giờ dùng đường dẫn tuyệt đối tới Python của dự án thay vì tra `PATH` (commit
`bcd61d2`), kiểm chứng qua đúng cơ chế `launchd` (`launchctl kickstart`,
không phải chạy tay `bash`) — `SUMMARY: 4/4 steps OK` tối 2026-07-18,
`freshness_status: OK`. Khoảng trống shadow log ngày 2026-07-17 đã đóng,
**0 ngày giao dịch bị mất** (chi tiết: `PROJECT_STATE.md` mục 4,
`docs/reports/scoring/SCORE_V2_REPORT.md` mục "Cập nhật 2026-07-18",
commit `3434bf2`) — xem ví dụ log FAIL thật (vẫn giữ nguyên trong lịch sử
log, không xóa) ở Phần 1.4.

## 0.4. Hai cuộc hẹn

**2027-01-16 — "phiên tòa" shadow v2.** Đây là mốc 6 tháng shadow-live
liên tục kể từ khi tự động hóa có hiệu lực (2026-07-16). Việc cần làm hôm
đó (`docs/reports/scoring/SCORE_V2_REPORT.md` mục "Conditions for
review", `docs/DAILY_OPERATING_GUIDE.md` mục 4/6):
1. Kiểm tra `alpha_score_shadow_log.parquet` có liên tục không (không đứt
   quãng dài) — nếu đứt quãng nhiều, dời mốc tương ứng, không tính máy móc.
2. Tính Sharpe ratio **out-of-sample thuần** (chỉ dùng return thật ghi
   trong shadow log) của danh mục v2-scored.
3. So với khoảng tin cậy bootstrap `[−0.59, +1.32]` (năm hoá) đã có sẵn.
4. Nếu nằm trong/dưới nửa dưới khoảng này → xác nhận thêm quyết định
   "chưa đủ bằng chứng dùng vốn thật" hiện tại, không cần làm gì khác.
5. Nếu vượt hẳn lên trên (gần/vượt +1.32) → mở một round xem xét lại có
   pre-register riêng — **không tự động chuyển sang vốn thật** chỉ vì một
   mốc số liệu tốt.

**Gate #3 — survivorship bias / point-in-time universe.** Gate mở lớn
nhất còn lại của audit — chưa có nguồn dữ liệu lịch sử niêm yết/hủy niêm
yết thật, nên mọi backtest chạy trên "500 mã đang niêm yết hôm nay chiếu
ngược về 2020", làm phồng hiệu suất biểu kiến của mọi chiến lược long-only
(`audit/PATH_TO_100.md` mục "Gate #3", `PROJECT_STATE.md` mục 3). Mức sàn
hiệu chỉnh ước tính hiện dùng: +0.4%/+1.2%/+2.9% ở cửa sổ 20/60/120 ngày
(`docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`). *(Chi tiết đầy đủ
về gate này — bước tiếp theo, chi phí, các phương án nguồn dữ liệu — dự
kiến mở rộng ở Phần 7.3 khi các lô sau của sổ tay này hoàn thành; ở lô
này chỉ nêu để người đọc biết gate tồn tại.)*

## 0.5. Bản đồ đọc — hôm nay bạn là ai?

| Bạn là ai | Đọc gì |
|---|---|
| Chủ dự án, buổi sáng, muốn tra nhanh | Phần 1 (Vận hành hằng ngày) của sổ tay này, hoặc trực tiếp `docs/DAILY_OPERATING_GUIDE.md` |
| Chủ dự án, đang cầm một watchlist/output cụ thể, không nhớ cột nào nghĩa là gì | Phần 2 của sổ tay này (đúng mục con tương ứng với file bạn đang xem) |
| Chủ dự án, quay lại sau 6 tháng, cần nhớ lại toàn cảnh | Phần 0 của sổ tay này trước, rồi `PROJECT_STATE.md` (cửa ngõ điều hướng chi tiết hơn) |
| Người ngoài, muốn hiểu vì sao hệ thống không phải "công cụ khuyến nghị" | Phần 0.2 sổ tay này, rồi `docs/reports/scoring/ROBUSTNESS_REPORT.md` + `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` |
| Một phiên làm việc code mới, cần sửa/mở rộng gì đó | `PROJECT_STATE.md` mục 5 (bản đồ 10 report) + `CLAUDE.md` (quy ước bắt buộc) + `PUSH_REVIEW.md` (nhật ký từng round) |
| Muốn hiểu khung ra quyết định đầu tư nên dùng dữ kiện hệ thống thế nào | `docs/DAILY_OPERATING_GUIDE.md` mục 3 (không lặp lại ở sổ tay này để tránh hai bản lệch nhau theo thời gian) |

---

# PHẦN 1 — VẬN HÀNH HẰNG NGÀY

## 1.1. Checklist buổi sáng (5 dòng)

| # | Việc | Lệnh/file cụ thể | Thế nào là ĐẠT |
|---|---|---|---|
| 1 | daily_run đêm qua chạy chưa | Dòng cuối `logs/daily_run.log` bắt đầu bằng `SUMMARY` | `4/4 steps OK`, mốc thời gian là tối ngày giao dịch gần nhất |
| 2 | Mốc ngày đúng | So `SUMMARY` timestamp với ngày giao dịch gần nhất (không phải hôm nay nếu hôm nay là thứ Hai — mốc phải là tối thứ Sáu) | Không lệch quá 1 ngày giao dịch |
| 3 | Watchlist tươi | `data/output/pipeline_metadata.json` → `freshness_status` | Phải là `"OK"`, và `lineage.lineage_generated_at` gần với mốc chạy đêm qua |
| 4 | Shadow log có mốc mới | `data/signals/alpha_score_shadow_log.parquet` cột `date`, giá trị lớn nhất | Có mốc ngày hôm qua/hôm nay, không đứt quãng dài |
| 5 | Liếc số mã qua gate | `data/output/pipeline_metadata.json` → `watchlist_counts` (hoặc `logs/daily_run.log` dòng `Applied post-cashflow overlay`) | `client_ready`/`trading` không cùng bằng 0; phần lớn không dồn vào `data_review` |

Nếu bước nào không đạt: dừng lại, đừng dùng dữ liệu hôm đó, sang mục 5
(Xử lý sự cố). Chi tiết đầy đủ hơn (kèm khung nguyên tắc "hệ thống không
chọn mã thay bạn"): `docs/DAILY_OPERATING_GUIDE.md` mục 1.

**Ví dụ thật, lịch sử gần nhất (xem 0.3)**: tối 2026-07-17, dòng cuối
`logs/daily_run.log` từng là `###### SUMMARY: 4/4 step(s) FAILED ######`
— chính xác tình huống mục này được thiết kế để bắt được. Đã chẩn đoán +
sửa + chạy lại thành công cùng ngày 2026-07-18 (`PROJECT_STATE.md` mục 4);
dòng `SUMMARY` cuối cùng tại thời điểm viết đã trở lại `4/4 steps OK`.

## 1.2. Cỗ máy tự động

**`~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist`**
(bản gốc versioned tại `scripts/com.vietnam-quant-research.dailyrun.plist`)
chạy `/bin/bash scripts/daily_run.sh`, lịch `StartCalendarInterval` =
19:00 các ngày thứ Hai–Sáu (`Weekday` 1-5 trong plist), cộng `RunAtLoad =
true` (chạy bù nếu máy tắt/ngủ đúng giờ hẹn, khi đăng nhập/khởi động lại
lần kế tiếp).

`scripts/daily_run.sh` gộp 4 bước theo đúng thứ tự sau (không `set -e` —
mỗi bước độc lập, một bước lỗi không chặn các bước sau chạy):
1. `update_prices_daily.py --universe` — cập nhật giá incremental.
2. `update_disclosure_daily.py --universe` — cập nhật disclosure incremental.
3. `update_index_data.py` — cập nhật VNINDEX/benchmark.
4. `run_daily_pipeline.py --offline` — tự chạy bên trong:
   `generate_features` → `generate_signals` → `run_alpha_scoring` (bước
   append `alpha_score_shadow_log.parquet`) → `generate_trade_cards` →
   `run_stealth_accumulation_screen` → `build_cashflow_board_symbols` →
   `run_meta_ranking` (xây `final_watchlist`) → `build_cashflow_board`
   (áp `apply_post_cashflow_overlay`, chốt tier `client_ready`).

Mỗi bước ghi một dòng `START`/`OK`/`###### FAIL ######` riêng vào
`logs/daily_run.log`; `daily_run.sh` tự kiểm tra dòng `SUMMARY` cuối cùng
trong log để không chạy trùng 2 lần/ngày (an toàn khi `RunAtLoad` kích
hoạt thêm lần nữa cùng ngày).

**Kiểm tra/tắt/bật (3 dòng, `PROJECT_STATE.md` mục 4)**:
```
launchctl list | grep vietnam-quant-research   # có dòng = đang nạp; cột đầu là PID nếu đang chạy, "-" nếu không
launchctl unload ~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist   # tắt
launchctl load ~/Library/LaunchAgents/com.vietnam-quant-research.dailyrun.plist     # nạp lại
```

**Trạng thái thật của cơ chế này, đã cập nhật sau khi xử lý (2026-07-18)**:
cả 2 rào cản từng chặn cơ chế này đều đã đóng. TCC (macOS chặn tiến trình
`launchd` truy cập `~/Desktop`) tự hết — không còn lỗi `Operation not
permitted` mới kể từ 2026-07-16 19:42. Rào cản thứ hai, phát hiện tối
2026-07-17 (môi trường `launchd` không có `PATH` trỏ tới Python của conda,
nơi cài `pandas`/`requests`/`pyyaml`, nên 4/4 bước báo `ModuleNotFoundError`),
đã sửa bằng cách hardcode đường dẫn tuyệt đối tới Python của dự án trong
`daily_run.sh` thay vì tra `PATH` (commit `bcd61d2`) — không dựa vào PATH
kế thừa shell nữa, đúng cho cả `launchd` lẫn chạy tay. **Đã kiểm chứng qua
đúng cơ chế launchd** (`launchctl kickstart -k gui/501/com.vietnam-quant-research.dailyrun`,
không phải chạy tay `bash`): `SUMMARY: 4/4 steps OK` tối 2026-07-18. Xem
log FAIL thật của sự cố (giữ nguyên trong lịch sử, không xóa) ở mục 1.4,
và chi tiết chẩn đoán/khoảng trống shadow log ở `PROJECT_STATE.md` mục 4.

## 1.3. Chạy tay

Hai lệnh (đúng thứ tự — chạy giá trước disclosure, theo quy ước
`CLAUDE.md` mục 7 và `PROJECT_STATE.md` mục 4):
```
python scripts/update_prices_daily.py --universe
python scripts/update_disclosure_daily.py --universe
```
rồi (nếu muốn sinh watchlist ngay, thay vì chờ 19:00): `bash
scripts/daily_run.sh` (thêm `--force` để chạy lại dù hôm nay đã chạy rồi).

**Khi nào nên chạy tay**: sau khi phiên giao dịch trong ngày đã đóng cửa
hoàn toàn (kể cả phiên ATC cuối chiều) — theo kiến thức thị trường chung
về giờ giao dịch HOSE/HNX/UPCOM, nên chạy sau ~15:00 giờ Việt Nam để chắc
chắn dữ liệu ngày hôm đó đã có đầy đủ trên nguồn dữ liệu **[mốc giờ cụ
thể "15:00" là suy luận thị trường chung, chưa xác minh được con số này
khóa cứng ở đâu trong code/tài liệu dự án]**. Nếu chạy quá sớm trong
ngày, script vẫn an toàn — chỉ đơn giản không có gì mới để cập nhật (xem
ngay dưới).

**Vì sao chạy trùng vô hại (idempotent)**: `update_prices_daily.py` fetch
incremental từ `max(date)` đã có của từng mã; nếu không có phiên giao
dịch mới, nó trả về trạng thái `NO_NEW_DATA` (không đổi file/manifest),
phân biệt rõ với `UPDATED` (có dữ liệu mới thật). Bằng chứng thật: chạy
kiểm chứng 3 lần liên tiếp trong cùng một vòng phát triển — lần 3 cho kết
quả `n_updated: 0, total_new_rows: 0`, tức no-op sạch, không nhân đôi dữ
liệu (`PUSH_REVIEW.md`, mục "Đồng bộ full_history_v2 + cơ chế cập nhật
giá hằng ngày — 2026-07-13 (vòng 3)", NV2).

## 1.4. Giải phẫu `logs/daily_run.log` — một block thật, chú thích từng dòng

**Block 1 — chạy tối 2026-07-16, thành công (4/4 OK)**, trích cuối log:
```
Appended 431 rows to data/signals/alpha_score_shadow_log.parquet (v2 vs v1 shadow comparison, date=2026-07-16)
=== Alpha Scoring Complete ===
```
→ Bước `run_alpha_scoring` (bên trong bước 4) đã ghi thêm 431 dòng mới
vào shadow log cho ngày 2026-07-16 — đây chính là dữ liệu tích lũy cho
"phiên tòa" v2 ở mục 0.4.
```
2026-07-16 20:24:06 | WARNING | ... dropping forward-looking column(s)
['forward_return_5d', ... ] before saving output (audit D5).
```
→ Đây **không phải lỗi** — là cảnh báo có chủ đích từ guard chống
look-ahead bias (`assert_no_forward_columns`, đã lock cứng theo
`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 5): guard tự
động loại các cột nhìn-về-tương lai khỏi output trước khi lưu, và LUÔN
báo `WARNING` khi làm việc đó — thấy dòng này lặp lại ở nhiều bước là
bình thường, không phải dấu hiệu hỏng.
```
2026-07-16 20:24:58,897 | INFO | final_watchlist | Applied post-cashflow overlay. client_ready=10 trading=20 research=189 data_review=281
...
[2026-07-16 20:24:59] OK   run_daily_pipeline (116s)
[2026-07-16 20:24:59] SUMMARY: 4/4 steps OK
```
→ Dòng `SUMMARY` này là dòng DUY NHẤT cần nhìn ở checklist buổi sáng
(mục 1.1 bước 1). `OK run_daily_pipeline (116s)` = bước 4 chạy hết 116
giây, không lỗi.

**Block 2 — chạy tối 2026-07-17, thất bại toàn bộ (4/4 FAIL)**, đây là ví
dụ thật cho trường hợp "FAIL từng bước" mà tài liệu này yêu cầu minh họa:
```
======================================================================
[2026-07-17 19:00:00] daily_run.sh starting
[2026-07-17 19:00:00] START update_prices_daily
Traceback (most recent call last):
  File ".../scripts/update_prices_daily.py", line 55, in <module>
    import pandas as pd
ModuleNotFoundError: No module named 'pandas'
[2026-07-17 19:00:01] ###### FAIL ###### update_prices_daily (1s, exit=1) -- see logs/daily_run.log for step output
```
→ Dấu `======` là ranh giới một lần chạy mới của `daily_run.sh` (dễ
`grep` để nhảy giữa các lần chạy trong log dài). `###### FAIL ######`
được bọc cố ý để dễ tìm bằng mắt/`grep FAIL`. Thông báo lỗi gốc luôn nằm
NGAY PHÍA TRÊN dòng FAIL (ở đây: `ModuleNotFoundError`) — đọc đúng dòng
đó, không phải dòng FAIL, để biết nguyên nhân thật.
```
[2026-07-17 19:00:01] START update_disclosure_daily
... ModuleNotFoundError: No module named 'requests'
[2026-07-17 19:00:01] ###### FAIL ###### update_disclosure_daily (0s, exit=1)
[2026-07-17 19:00:01] START update_index_data
... ModuleNotFoundError: No module named 'yaml'
[2026-07-17 19:00:01] ###### FAIL ###### update_index_data (0s, exit=1)
[2026-07-17 19:00:01] START run_daily_pipeline
... ModuleNotFoundError: No module named 'pandas'
[2026-07-17 19:00:02] ###### FAIL ###### run_daily_pipeline (1s, exit=1)
[2026-07-17 19:00:02] ###### SUMMARY: 4/4 step(s) FAILED: update_prices_daily update_disclosure_daily update_index_data run_daily_pipeline ######
```
→ Cả 4 bước fail trong <1-2 giây mỗi bước — thời gian chạy cực ngắn kèm
`ModuleNotFoundError` là dấu hiệu nhận biết nhanh "đây là lỗi môi trường
Python, script còn chưa kịp làm gì" (khác với một bước fail giữa chừng
sau khi đã chạy hàng chục giây — dấu hiệu đó thường là lỗi logic/dữ liệu
thật, cần đọc kỹ hơn). Xem mục 1.2 để biết nguyên nhân gốc đã xác định.

**Đã sửa cùng ngày 2026-07-18** (`scripts/daily_run.sh` commit `bcd61d2`,
kiểm chứng qua `launchctl kickstart`: `SUMMARY: 4/4 steps OK` tối
2026-07-18) — 2 block trên vẫn giữ nguyên làm ví dụ giáo dục thật cho
"FAIL từng bước" trông như thế nào, không phản ánh trạng thái hiện tại
của cơ chế (mục 1.2).

**Phân biệt `NO_NEW_DATA` (bình thường, ngày nghỉ)**: nếu một bước
`update_prices_daily`/`update_disclosure_daily` chạy xong với dòng `OK`
nhưng thân log của chính script đó báo trạng thái `NO_NEW_DATA` /
`n_updated: 0` thay vì `UPDATED`, đây **không phải lỗi** — đơn giản là
không có phiên giao dịch mới kể từ lần chạy trước (ngày nghỉ lễ/cuối
tuần, hoặc chạy hai lần cùng ngày). Chỉ dòng `###### FAIL ######` mới là
dấu hiệu cần xử lý.

## 1.5. Nhịp tuần/tháng

- **2-4 tuần/lần — liếc tính liên tục của shadow log** (đo cho "phiên
  tòa" v2 ở mục 0.4): khoảng trống **>3 ngày giao dịch liên tiếp** không
  có dòng mới trong `alpha_score_shadow_log.parquet` là mức báo động —
  không nguy hiểm ngay nhưng làm lùi ngày phiên tòa và làm yếu kết luận
  cuối cùng nếu tích lũy dài. Lệnh kiểm tra nhanh:
  ```
  python3 -c "import pandas as pd; d=pd.read_parquet('data/signals/alpha_score_shadow_log.parquet'); print(sorted(d['date'].unique())[-10:])"
  ```
- **Định kỳ (gợi ý hằng tuần, hoặc trước khi làm gì lớn) — bundle backup**:
  đảm bảo thư mục dự án được sao lưu (Time Machine hoặc tương đương) —
  đây là dữ liệu tài chính + lịch sử nghiên cứu, không có bản sao ở đâu
  khác ngoài git log local (dự án chỉ commit local, không push,
  `CLAUDE.md` mục 2). Lệnh copy-paste sẵn để đóng gói lịch sử git thành
  một file di động duy nhất:
  ```
  git bundle create ~/Desktop/vietnam-quant-research-backup-$(date +%Y%m%d).bundle --all
  ```

## 1.6. Những việc KHÔNG cần làm hằng ngày

- **Không backtest lại** `alpha_score`/`final_watchlist` mỗi ngày — các
  con số IC/DSR/bootstrap CI đã đo xong cho cấu hình hiện hành
  (`docs/reports/scoring/ROBUSTNESS_REPORT.md`), việc hằng ngày chỉ là
  *cập nhật dữ liệu*, không phải *đo lại chiến lược*. Chỉ backtest lại
  khi có nhân tố mới muốn kiểm định, qua đúng quy trình pre-register.
- **Không đụng vào notebook** (`notebooks/`) như một phần vận hành hằng
  ngày — notebook là công cụ nghiên cứu/tra cứu thủ công (Phần 2.8), pipeline
  sản xuất không phụ thuộc chạy notebook.
- **Không push mỗi ngày** — quy ước cố định của dự án là chỉ commit local
  (`CLAUDE.md` mục 2); push là quyết định riêng của người dùng, không nằm
  trong quy trình vận hành hằng ngày.
- **Không tự ý sửa tham số** `alpha_score`/`final_watchlist`/SDE dựa trên
  cảm giác watchlist "trông có vẻ sai" hôm đó — mọi thay đổi tham số phải
  qua quy trình pre-register + kiểm định (`CLAUDE.md` mục 8), không phải
  việc chỉnh nhanh trong lúc vận hành.

---

# PHẦN 2 — ĐỌC HIỂU TỪNG SẢN PHẨM ĐẦU RA

## 2.1. `final_watchlist` (CSV + XLSX)

**(i) Là gì & sinh từ đâu**: `src/screening/final_watchlist.py`, chạy như
bước cuối của `run_daily_pipeline.py` (mục 1.2). File chính:
`data/signals/final_watchlist.csv` (đồng thời cũng chính là nội dung của
`data/output/client_ready_watchlist.csv` — tại thời điểm viết, file này
chỉ chứa 10 dòng tier `Client Ready`; các tier khác nằm ở
`data/output/trading_watchlist.csv` [20 dòng] và
`data/output/research_candidates.csv` [189 dòng]). Bản Excel tương ứng:
`reports/final_watchlist.xlsx`. Nhãn cơ chế: **"Nhánh C"**
(`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`, thi hành trong
code tại commit `450b166`/`a76b69c`, regenerate + nhúng lineage tại
`ccad49f`).

**(ii) Từng cột — đọc trực tiếp từ header thật của
`data/signals/final_watchlist.csv`**:

| Cột | Ý nghĩa | Có bằng chứng dùng để xếp hạng? |
|---|---|---|
| `rank` | Thứ hạng — theo `value_ma20` giảm dần, KHÔNG theo điểm số | — (đây chính là cơ chế xếp hạng hiện tại) |
| `symbol`, `date`, `analysis_as_of`, `data_age_days` | Mã, ngày dữ liệu, ngày phân tích, độ trễ (ngày) | — (dùng để xác nhận độ tươi, Phần 1.1 bước 3) |
| `close`, `latest_volume` | Giá đóng cửa, khối lượng phiên gần nhất | — |
| `value_ma20` | Giá trị giao dịch bình quân 20 ngày (VND) — **cột quyết định thứ hạng** | Thước đo vận hành (thanh khoản), không phải nhân tố alpha đã kiểm định |
| `candidate_tier` | `Client Ready` / `Trading Watchlist` / `Research Candidate` / `Data Review` | — |
| `confidence_label` | Nhãn định tính (vd. "Medium-High") suy từ `final_score`/warning — **kế thừa từ cơ chế cũ, không phải đánh giá độc lập mới** | Không — cùng nguồn gốc với `final_score` |
| `is_research_candidate`, `is_trading_candidate`, `is_client_ready` | Cờ boolean tương ứng tier | — |
| `final_score`, `base_final_score` | Điểm tổng hợp 7 thành phần cũ — **chỉ tham khảo/nghiên cứu, KHÔNG điều khiển việc mã có vào watchlist hay xếp hạng** kể từ Nhánh C | **Không** — composite đã kiểm định và KHÔNG đạt tiêu chí (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 1, 4) |
| `warning_penalty` | Điểm trừ khỏi `base_final_score` do cảnh báo (vd. "Weak relative strength") | Không — chỉ ảnh hưởng `final_score` hiển thị, không ảnh hưởng tier/rank |
| `trend_score`, `momentum_score`, `relative_strength_score`, `volume_score` | Thành phần con của điểm cũ | **Không** — t-stat đều yếu (`\|t_NW\|<1`); `momentum_score` và `relative_strength_score` **về mặt toán học là một** (cùng công thức `_rank()` sau khi trừ hằng số benchmark, không đổi thứ hạng cross-sectional) — dư thừa đã phát hiện, chưa sửa (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2, phát hiện #1) |
| `liquidity_score` | Thành phần con cũ (thưởng `value_ma20` cao) | **Không — chiều SAI**: t_NW=−4.19 (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2); đã gỡ khỏi `base_final_score`, chỉ còn hiển thị |
| `risk_score` | Thành phần con đo biến động thấp | Có bằng chứng thống kê riêng (t_NW=+4.72) nhưng **trùng cụm** với `alpha_score` v2 (Spearman +0.822) — không phải nguồn thông tin độc lập, đã đóng hồ sơ (`docs/reports/scoring/ROBUSTNESS_REPORT.md` mục 3) |
| `signal_score` | Dựa trên `meta_ranking.parquet` | **Không tính được** — file nguồn là ảnh chụp một thời điểm (snapshot), không phải chuỗi lịch sử (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2, phát hiện #4) |
| `volatility_regime` | Nhãn định tính ("Normal Vol"/"Low Vol"...) suy từ percentile biến động | — |
| `risk_reward_estimate` | Tỷ lệ risk/reward tham khảo (không phải điểm đã kiểm định) | — |
| `reason` | Câu giải thích ngắn — **luôn có tiền tố cảnh báo** `[Không xếp hạng alpha, chỉ sắp theo thanh khoản -- xem WATCHLIST_VALIDATION_REPORT.md]` | — |
| `warning`, `exclusion_reason` | Cảnh báo dữ liệu / lý do loại khỏi tier cao hơn | — |
| `eligibility_status`, `eligibility_reason` | Có qua sàng lọc cơ bản không (thanh khoản, dữ liệu tươi, đang giao dịch) | — |
| `latest_volume`, `cashflow_data_status`, `confirmation_status`, `cashflow_verification` | Dữ liệu dòng tiền/xác nhận cùng ngày — ảnh hưởng việc mã bị hạ từ `Client Ready` xuống `Trading Watchlist` hay không | — |
| `rank_universe_size` | Cỡ universe dùng để tính `rank` (500 tại thời điểm viết) | — |

**Khối lineage**: bản thân `final_watchlist.csv` KHÔNG nhúng cột lineage
trực tiếp trong mỗi dòng — lineage nằm ở file sidecar cùng thư mục,
`data/output/watchlist_metadata.json` → khối `"lineage"`: `dataset_version`
(`full_history_v2`), `features_path` + `features_sha256` (băm SHA-256 của
`stock_features.parquet` dùng để sinh watchlist — đảm bảo biết chính xác
dữ liệu nào tạo ra output này), `features_row_count`, `config_path` +
`config_hash`, `git_commit_hash` (commit code lúc chạy), và
`lineage_generated_at` (dấu thời gian THẬT của lần sinh, dùng ở Phần 1.1
bước 3). Ví dụ thật tại thời điểm viết: `git_commit_hash =
59a9d576b81fc131f83565f54329abc11ab963a1`, `lineage_generated_at =
2026-07-16T13:24:58+00:00`.

**3 tier khác nhau tiêu chí gì**:
- **`Client Ready`**: qua đủ mọi gate chất lượng dữ liệu (eligibility,
  cashflow xác nhận cùng ngày, không cảnh báo chặn) — **không có nghĩa
  "chất lượng đầu tư cao hơn"**, chỉ có nghĩa "dữ liệu về mã này sạch và
  mới nhất".
- **`Trading Watchlist`**: qua sàng lọc cơ bản nhưng thiếu một xác nhận
  phụ (vd. cashflow board chưa build kịp hôm đó) — vẫn là mã hợp lệ.
- **`Research Candidate`**: qua sàng lọc tối thiểu nhưng nằm ngoài giới
  hạn số lượng của 2 tier trên (mặc định 10 + 20 mã).
- **`Data Review`**: bị loại — xem `eligibility_reason`.

**Vì sao xếp theo thanh khoản (Nhánh C)**: sau khi cả điểm tổng hợp 7
thành phần lẫn phiên bản "watchlist tối giản" (chỉ dùng `alpha_score` v2)
đều được kiểm định IC Newey-West + null-test theo đúng tiêu chí đã khóa
trước trong `docs/reports/scoring/WATCHLIST_VALIDATION_PREREG.md` và
**đều không đạt** (composite: IC gần 0 không cùng dấu qua 3 giai đoạn,
null-test một fold sụp xuống percentile 0.15; watchlist tối giản: null
avg 52.8<60, IC giai đoạn 1 chỉ 2.90<3.0 — sát nhưng không đạt), quyết
định đã khóa trước là "vùng xám → chọn nhánh thận trọng hơn" được áp dụng
đúng như thiết kế: không dùng bất kỳ điểm dự báo nào để xếp hạng, chỉ
dùng thanh khoản — một tiêu chí vận hành trung tính, không phải một tuyên
bố dự báo (`docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 4-5).

> ### ⚠️ KHÔNG ĐƯỢC SUY RA từ `final_watchlist`
> - **Đầu bảng ≠ mã đáng mua nhất.** Nó chỉ là mã thanh khoản cao nhất
>   trong rổ hôm đó.
> - **Có mặt trong watchlist ≠ khuyến nghị.** Đây là danh sách đã qua
>   sàng lọc dữ liệu/thanh khoản/đang giao dịch thật, không phải danh
>   sách đã được định giá hay đánh giá đầu tư.
> - **Vắng mặt ≠ mã xấu.** Có thể chỉ vì thanh khoản dưới ngưỡng, dữ liệu
>   cũ, hoặc đã ngừng giao dịch (`trading_status` INACTIVE_LONG) — không
>   liên quan gì đến chất lượng doanh nghiệp.
> - **`final_score`/`risk_score` cao ≠ nên mua** — các cột này chỉ tham
>   khảo/nghiên cứu (xem bảng trên), không phải căn cứ ra quyết định.

## 2.2. SDE — bảng dữ kiện (`facts_summary.txt` + `metrics.csv` + `facts.csv`)

**(i) Là gì & sinh từ đâu**: `stock-decision-engine/notebooks/stock_buy_decision.ipynb`,
gọi các hàm trong `stock-decision-engine/src/` cho MỘT mã do người dùng
chọn (không phải batch 500 mã như `final_watchlist`). Sau Vòng 3
(`stock-decision-engine/SDE_SCORING_REPORT.md`, commit `aa773a2`, đóng hồ
sơ tại `d25d00e`), `score_decision()` (điểm tổng hợp `final_score` + nhãn
`decision`) đã **gỡ bỏ hoàn toàn khỏi code**, thay bằng `build_facts_table()`.
Mỗi lần chạy sinh 3 file text/bảng cho `{TICKER}_{ngày}`, ví dụ thật
(`ACB`, 2026-06-26): `ACB_2026-06-26_facts_summary.txt` (tóm tắt đọc
nhanh), `ACB_2026-06-26_metrics.csv` (1 dòng, toàn bộ số liệu thô + khối
lineage), `ACB_2026-06-26_facts.csv` (8 dòng, bảng "facts breakdown").
Lưu ý đặt tên: khác với mô tả gốc "sub_scores.csv", tên file thật trong
`stock-decision-engine/outputs/` là `*_facts.csv` — đây chính là bảng
8 nhóm "reading" thay cho sub-score cũ.

**(ii) Từng chỉ số — đọc trực tiếp từ 3 file thật**:

`{TICKER}_facts.csv` (8 dòng, cột `component, reading, reason`) — ví dụ
thật ACB 2026-06-26:

| `component` | `reading` (0-100) | Định nghĩa (`reason`) |
|---|---|---|
| `market_regime` | 100.0 | Xu hướng, độ dốc, lợi nhuận, drawdown, biến động của benchmark |
| `trend` | 75.0 | Cấu trúc MA, độ dốc, ADX/+DI, bối cảnh breakout |
| `momentum` | 68.0 | Lợi nhuận đa khung thời gian, RSI, MACD, gia tốc |
| `relative_strength` | 75.0 | Excess return, độ dốc RS, beta, tương quan |
| `alpha` | 26.0 | CAPM alpha, Sharpe/Sortino/IR/Calmar, backtest edge (nếu có) |
| `risk` | 75.0 | ATR, percentile biến động, drawdown, CVaR, skew, độ rộng stop |
| `liquidity` | 93.0 | Giá trị giao dịch bình quân, tỷ lệ tham gia khối lượng, z-score, MFI, CMF |
| `simulation` | 28.0 | Xác suất Monte Carlo, lợi nhuận kỳ vọng, rủi ro đuôi mô phỏng |

**`reading` 0-100 = số tiêu chí phân tích kỹ thuật (TA) nội bộ đạt được,
KHÔNG phải xác suất hay điểm đã kiểm định thống kê** — không nhóm nào
trong 8 nhóm này đã qua kiểm định IC/null-test (chính `facts_summary.txt`
tự ghi rõ điều này ở mỗi lần chạy). `{TICKER}_metrics.csv` chứa toàn bộ số
liệu thô đứng sau các "reading" trên (MA/RSI/MACD/ATR/Sharpe/Sortino/
Monte Carlo probabilities/backtest stats...) cộng khối lineage
(`lineage_dataset_version`, `lineage_features_sha256`,
`lineage_git_commit_hash`, `lineage_lineage_generated_at`...) — cùng cấu
trúc lineage như `watchlist_metadata.json` ở mục 2.1, nhưng ở đây nhúng
trực tiếp vào từng dòng thay vì file sidecar riêng.

Ngưỡng tham chiếu duy nhất còn tồn tại trong bảng là các mức ATR
(`entry_zone_low/high`, `stop_loss`, `target_1/2`, `risk_reward`) —
`config.yaml`'s `score_thresholds` (ngưỡng cũ cho `decision`) **đã bị gỡ**
vì không còn ai đọc.

**(iii) Cách đọc đúng + ví dụ thật**: từ `ACB_2026-06-26_facts_summary.txt`
— văn bản này tự đóng khung ngay từ dòng đầu: *"BẢNG DỮ KIỆN THAM KHẢO --
KHÔNG PHẢI KHUYẾN NGHỊ MUA/BÁN"*, và giải thích lý do (Vòng 3 không đạt
tiêu chí IC/null-test). Đọc đúng là dùng từng dòng như một chỉ số kỹ
thuật đơn lẻ để tự nghiên cứu (vd. "ACB hiện trên MA50 và MA200, RS đang
cải thiện so với VNINDEX, vùng ATR quanh 22,331-22,667"), không cộng dồn
8 con số 0-100 lại thành một điểm duy nhất.

**(iv) KHÔNG ĐƯỢC SUY RA**: không "reading" nào trong 8 nhóm là một điểm
dự báo đã kiểm định; không có nhãn quyết định (BUY/WATCH/AVOID...) nào
còn tồn tại trong code để suy ra; vùng entry/stop/target là tham chiếu
theo ATR (biên độ biến động lịch sử), không phải điểm vào/ra lệnh khuyến
nghị; xác suất Monte Carlo (`simulation`) **chưa kiểm định calibration**
(tự văn bản gốc ghi rõ "chưa kiểm định calibration").

## 2.3. Từng loại chart PNG của SDE

Sinh bởi `stock-decision-engine/src/visualization.py::save_all_charts`,
mỗi lần chạy notebook cho một mã tạo đúng 7 file `{TICKER}_{tên}.png`
(đọc trực tiếp từ code, không phải suy đoán từ tên file):

1. **`{TICKER}_price_structure.png`** (`plot_price_structure`) — đường
   giá đóng cửa (đen) + MA20 (xanh dương)/MA50 (xanh lá)/MA200 (đỏ) nếu
   có; dải màu xanh nhạt = vùng entry tham chiếu
   (`entry_zone_low`-`entry_zone_high`); đường đứt đỏ = stop-loss tham
   chiếu; đường đứt xanh lá = target 1; đường chấm xanh lá đậm = target 2.
   **Bẫy đọc sai**: dải/đường này là tính theo ATR lịch sử, không phải
   điểm vào/ra hệ thống khuyến nghị.
2. **`{TICKER}_relative_strength.png`** (`plot_relative_strength`) —
   trục trái: lợi nhuận tích lũy của mã (đen) và benchmark (xám); trục
   phải (đường màu cam): đường RS (`relative_strength_line`, tỷ số giá
   mã/benchmark). **Bẫy đọc sai**: đường RS dốc lên chỉ có nghĩa mã đang
   *tăng nhanh hơn* VNINDEX tương đối, không có nghĩa mã đang tăng giá
   tuyệt đối (mã có thể giảm giá nhưng RS vẫn dốc lên nếu benchmark giảm
   nhanh hơn).
3. **`{TICKER}_rolling_alpha_beta.png`** (`plot_rolling_alpha_beta`) —
   trục trái (xanh dương): rolling Jensen alpha; trục phải: rolling beta
   (đỏ) và rolling correlation (xanh lá) so với benchmark; đường ngang
   xám tại 0 làm mốc tham chiếu cho alpha. **Bẫy đọc sai**: "alpha" ở đây
   là CAPM alpha thống kê mô tả (rolling window), không phải bằng chứng
   một chiến lược sinh lời — không liên quan đến `alpha_score` v2 của dự
   án chính (khác tên, khác định nghĩa, khác file nguồn hoàn toàn).
4. **`{TICKER}_momentum.png`** (`plot_momentum`) — 3 panel dọc dùng chung
   trục thời gian: RSI-14 (xanh dương, có 2 đường ngang tham chiếu 70/30);
   MACD histogram (cột xám); ADX (đen)/+DI (xanh lá)/−DI (đỏ). **Bẫy đọc
   sai**: ADX cao chỉ đo *cường độ* xu hướng (dù tăng hay giảm), không tự
   nó cho biết hướng — phải nhìn cùng +DI/−DI.
5. **`{TICKER}_risk.png`** (`plot_risk`) — 3 panel dọc: biến động 20 ngày
   (xanh dương) và 60 ngày (xám); ATR% (cam); drawdown tô đỏ nhạt (vùng
   dưới 0). **Bẫy đọc sai**: các con số này mô tả *biến động lịch sử*,
   không phải dự báo biến động tương lai.
6. **`{TICKER}_monte_carlo_fan.png`** (`plot_monte_carlo`) — tối đa 200
   đường mô phỏng mờ (xám, alpha thấp) làm "quạt" trực quan; đường median
   (đen, đậm); percentile 5/95 (đỏ/xanh lá); cộng 3 đường tham chiếu
   stop-loss/target 1/target 2 giống panel 1. **Bẫy đọc sai lớn nhất của
   toàn bộ SDE**: đây là mô phỏng dựa trên phân phối lợi nhuận lịch sử
   (bootstrap), KHÔNG phải dự báo giá tương lai có kiểm định calibration
   — dải quạt rộng hay hẹp phản ánh biến động lịch sử được resample,
   không phản ánh độ tin cậy dự báo thật.
7. **`{TICKER}_facts_breakdown.png`** (`plot_facts_breakdown`) — biểu đồ
   thanh ngang (màu xám đồng nhất, cố ý không dùng màu phân biệt
   tốt/xấu), trục 0-100, xếp theo giá trị `reading` tăng dần, đúng 8 nhóm
   ở mục 2.2. Tiêu đề chart tự ghi thẳng: *"không phải điểm quyết định --
   xem SDE_SCORING_REPORT.md"* (đọc trực tiếp từ docstring hàm
   `plot_facts_breakdown`, xác nhận đây là chủ đích thiết kế, không phải
   chú thích ngoài lề). **Bẫy đọc sai**: dễ nhầm biểu đồ thanh ngang kiểu
   này với một "bảng điểm tổng hợp" quen thuộc — nó KHÔNG PHẢI, 8 thanh là
   8 chỉ số độc lập, không cộng dồn.

## 2.4. Shadow log v2/v1 (`alpha_score_shadow_log.parquet`)

**Cấu trúc thật** (đọc trực tiếp từ file, không suy đoán): 4 cột —
`symbol`, `date`, `alpha_score` (v2, đang triển khai), `alpha_score_shadow_v1`
(composite cũ, chạy song song chỉ để so sánh). Tại thời điểm viết: 1,288
dòng, 4 mốc ngày phân biệt (`2026-07-09`, `2026-07-13`, `2026-07-15`,
`2026-07-16`) — 3 mốc đầu là chuỗi thưa trước khi tự động hóa có hiệu
lực, **không tính vào "6 tháng liên tục"** của mốc xem lại ở mục 0.4
(`docs/reports/scoring/SCORE_V2_REPORT.md`, mục "Cập nhật 2026-07-16").
Chuỗi liên tục thật bắt đầu từ 2026-07-16.

**Đọc để theo dõi SỨC KHỎE của thí nghiệm** (mục 1.5): chuỗi ngày có liên
tục không, số mã/ngày có ổn định không (431 mã ngày 2026-07-16). **Tuyệt
đối không dùng để chọn mã** — đây là bản ghi out-of-sample đang tích lũy
cho phiên xem lại 2027-01-16 (mục 0.4), không phải một bảng xếp hạng để
tra cứu hôm nay (bảng xếp hạng để tra cứu hằng ngày là `reports/daily_alpha_ranking.csv`,
mục 2.7 — khác file, khác mục đích: một file là *lịch sử thí nghiệm append-only*,
file kia là *snapshot ngày hiện tại*). Lý do kỹ thuật của việc không dùng
để chọn mã: `alpha_score` v2 có bằng chứng xếp hạng tốt (IC ổn định), NHƯNG
bằng chứng xếp hạng tốt ≠ bằng chứng chiến lược sinh lời (DSR=0.0083, xem
Phần 0.2) — dùng nó để chọn mã hôm nay tương đương hành động như thể
"chiến lược đáng cược" đã được xác nhận, trong khi kết luận chính thức
hiện tại là ngược lại.

## 2.5. `trading_status` — 3 trạng thái

**Cấu trúc thật** (`data/full_history_v2/trading_status.parquet`): 5 cột
— `symbol`, `last_trading_date`, `status`, `gap_days`, `updated_at`.
Bảng append-only, point-in-time (chỉ ghi dòng mới khi trạng thái một mã
thực sự đổi). Phân phối tại thời điểm viết: `ACTIVE` 466, `STALE_SHORT`
46, `INACTIVE_LONG` 21.

- **`ACTIVE`** (gap ≤2 ngày): giao dịch bình thường.
- **`STALE_SHORT`** (gap 3-10 ngày): thanh khoản thưa nhưng có thật, chưa
  bị loại khỏi watchlist chỉ vì lý do này.
- **`INACTIVE_LONG`** (gap >10 ngày): coi như đã ngừng giao dịch thật —
  bị loại khỏi rổ đủ điều kiện của `final_watchlist` qua cơ chế này (lý
  do một mã "biến mất" khỏi mọi tier dù còn trong universe 500 mã gốc).

**Tra khi nào**: khi một mã bạn quan tâm không xuất hiện ở watchlist nào
cả — kiểm tra `status` của mã đó trước khi nghi ngờ pipeline lỗi.
**Lưu ý quan trọng**: bảng này chỉ có lịch sử thật từ 2026-07-13 trở đi
(`docs/reports/data/DATA_BASELINE.md`) — đây là bước đầu cho Gate #3
(mục 0.4), không phải giải pháp đầy đủ: nó chỉ thấy mã đã có trong
universe 500 mã hiện tại rồi "im lặng dần", không thấy được mã đã hủy
niêm yết/sáp nhập *trước khi* vào được danh sách 500 mã này.

## 2.6. Disclosure events (`data/disclosure/events.parquet`)

**Cấu trúc thật**: 28 cột, 58,054 dòng tại thời điểm viết. Các cột chính
để tra cứu ngữ cảnh một mã: `symbol`, `event_type` (`insider_registration`/
`insider_result`...), `person_name` + `person_role` (ai), `direction`
(`buy`/`sell`), `shares_before`/`shares_registered_or_changed`/`shares_after`,
`registration_window_start/end`, `execution_date`, `disclosure_date`,
`available_at` (mốc point-in-time — thời điểm thông tin này *có thể biết
được*, dùng cho mọi kiểm định tôn trọng point-in-time), `is_backfilled`
(True = dữ liệu lấy hồi cố, dùng lag giả định +1 ngày giao dịch thay vì
mốc live thật), `raw_payload` (JSON gốc từ nguồn, chưa qua parse).

**Tra ngữ cảnh thế nào**: lọc theo `symbol`, đọc `direction`/`person_role`/
`shares_registered_or_changed`/`execution_date` để biết "ai liên quan gần
đây đã đăng ký/thực hiện giao dịch, mua hay bán, bao nhiêu, khi nào" —
dùng như bối cảnh khi tự nghiên cứu một mã cụ thể, đúng khung Bước 3 của
`docs/DAILY_OPERATING_GUIDE.md` mục 3.

**Nhắc 3 vòng prereg âm tính — dữ liệu ngữ cảnh, không phải tín hiệu**:
đã kiểm định pre-register 3 vòng độc lập (test chính, đối chứng
survivorship bias, đối chứng khớp cặp cụm/gia đình) — **kết quả âm tính ở
cả 3 vòng, không nhân tố disclosure nào đạt ngưỡng ứng viên**
(`docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`, commit
`b95cc37`; `docs/reports/disclosure/DISCLOSURE_PREREG_2_REPORT.md`). Phát
hiện phụ đáng chú ý: tín hiệu đối chứng S3 (đăng ký BÁN, kỳ vọng lợi
nhuận sau đó ≤0) lại có CAR dương gần bằng tín hiệu MUA — dẫn tới ước
lượng sàn survivorship bias ở mục 0.4/2.5. Dữ liệu vẫn cập nhật hằng ngày
vì có giá trị khác (dấu hiệu sớm cho hủy niêm yết, phục vụ Gate #3),
không phải vì nhánh tín hiệu giá còn mở.

## 2.7. `DATA_BASELINE` + `daily_alpha_ranking`

**`docs/reports/data/DATA_BASELINE.md`**: tra khi cần biết dữ liệu giá
gốc (`data/full_history_v2`) đáng tin đến đâu — bao nhiêu mã, khoảng
ngày, caveat nào còn mở. Caveat quan trọng nhất tại thời điểm viết: (1)
`data/processed/stock_features.parquet` vẫn còn lỗi trộn raw/adjusted
close cho một phần chưa xác định hết của universe (đã sửa ở
`full_history_v2` nhưng CHƯA merge ngược); (2) survivorship bias chưa
giải (Gate #3); (3) quy ước bỏ ngày volume=0 khác giữa 2 nguồn dữ liệu.
**Tin mức nào**: coi đây là nguồn caveat *bắt buộc đọc trước* khi diễn
giải bất kỳ con số CAGR/Sharpe/backtest nào trong dự án — không tự suy ra
"dữ liệu chắc sạch rồi" chỉ vì pipeline chạy không lỗi.

**`reports/daily_alpha_ranking.csv`**: snapshot NGÀY HIỆN TẠI (không phải
lịch sử tích lũy như shadow log, mục 2.4) cho toàn bộ 431 mã đủ điều kiện
tối thiểu, cột: `symbol, date, close, alpha_score, alpha_score_shadow_v1,
momentum_score, rs_score, trend_score, volume_score, volatility_score,
liquidity_score, market_regime`. `reports/top_watchlist.csv` là top-20
của cùng file này, xếp theo `alpha_score` (v2) — **khác hẳn cơ chế
`final_watchlist`** (xếp theo thanh khoản): đây là bảng xếp hạng thuần
theo điểm thử nghiệm, dùng để theo dõi nghiên cứu, không phải một watchlist
sản xuất chính thức. **Tra khi nào**: khi muốn xem điểm `alpha_score` v2
hiện tại của một mã cụ thể (kể cả mã không lọt vào `final_watchlist` do
thanh khoản thấp). **Tin mức nào**: đúng mức độ tin của `alpha_score` v2
nói chung — có bằng chứng xếp hạng, chưa có bằng chứng chiến lược (mục 0.2).

## 2.8. Notebook nào còn dùng được

| Notebook | Trạng thái | Mở để làm gì |
|---|---|---|
| `notebooks/01_data_pipeline/01_validate_environment.ipynb` | Sống | Kiểm tra môi trường/kết nối dữ liệu trước khi chạy sâu hơn |
| `notebooks/02_market_research/04_market_distribution.ipynb`, `05_volatility_regime.ipynb`, `06_market_regime.ipynb`, `08_monte_carlo_simulation.ipynb`, `10_benchmark_diagnostics.ipynb`, `13_advanced_quant_analysis.ipynb` | Sống (chưa bị phát hiện lệch code — không đồng nghĩa "đã xác nhận đúng 100%") | Nghiên cứu thị trường thủ công: phân phối lợi nhuận, chế độ biến động/thị trường, mô phỏng Monte Carlo, chẩn đoán benchmark |
| `notebooks/03_alpha_signals/07_breakout_research.ipynb`, `09_stealth_accumulation_screen.ipynb` | Sống | Nghiên cứu breakout, tầm soát tích lũy âm thầm |
| `notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb` | **⚠️ OUTDATED** (banner cảnh báo ở đầu file, xác nhận có tồn tại) | Đọc banner trước khi tin số liệu; không chạy lại rồi dùng kết quả như còn hợp lệ |
| `notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb`, `15_risk_management.ipynb`, `16_capital_allocation.ipynb` | Sống | Dựng danh mục, quản trị rủi ro, phân bổ vốn (nghiên cứu/mô phỏng) |
| `notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb`, `20_portfolio_backtester.ipynb` | **⚠️ OUTDATED** (banner xác nhận có tồn tại) | Tương tự trên — đọc banner trước |
| `notebooks/05_client_report/01_client_market_report.ipynb` | Sống | Sinh báo cáo thị trường dạng đọc được |
| `notebooks/00_archive/*` (6 file) | **Đóng băng** (thư mục archive) | Chỉ tham khảo lịch sử, không dùng |
| `stock-decision-engine/notebooks/stock_buy_decision.ipynb` | Sống, **đã cập nhật Nhánh C** (README + SDE_SCORING_REPORT.md xác nhận) | Tra cứu nhanh bảng chỉ số kỹ thuật/thống kê một mã (Phần 2.2-2.3) — không dùng để quyết định mua/bán |

**Với notebook "Sống" không có banner cảnh báo**: nghĩa là *chưa bị phát
hiện* lệch với code hiện tại, KHÔNG đồng nghĩa "đã xác nhận đúng 100%" —
nếu nghi ngờ một con số trong đó, đối chiếu với report tương ứng ở bản đồ
hồ sơ `PROJECT_STATE.md` mục 5 trước khi tin.

**Với notebook đi theo nhóm cell** (áp dụng cho các notebook nghiên cứu
thị trường/portfolio): cấu trúc chung là *nhập liệu* (đọc parquet/CSV từ
`data/processed/` hoặc `data/output/`) → *tính* (gọi hàm từ `src/`, không
định nghĩa lại logic trong cell) → *vẽ* (matplotlib/biểu đồ inline).
Output đọc đúng cách là đối chiếu ngay với report gốc cùng chủ đề (Phần 0.5
"bản đồ đọc"), không coi số ra từ notebook là kết luận độc lập mới nếu đã
có report chính thức về cùng câu hỏi.

---

*Hết Lô 1/3. Lô 2 sẽ tiếp tục Phần 3 trở đi theo đúng cấu trúc đã thống
nhất — dừng ở đây chờ duyệt.*
