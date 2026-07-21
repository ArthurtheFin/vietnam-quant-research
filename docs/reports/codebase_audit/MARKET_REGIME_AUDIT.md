# MARKET_REGIME_AUDIT — audit `notebooks/02_market_research/`

**Phạm vi**: audit thuần cho 6 file trong `notebooks/02_market_research/`
(công cụ đo market regime/thị trường, VNINDEX-focused). **Không sửa logic,
không backtest mới, không xóa gì** — đúng ràng buộc đã cho. Phương pháp:
verify-not-rediscover (đọc report cũ trước, đối chiếu bằng chứng thay vì
đoán), chạy thật từng notebook top-to-bottom (`jupyter nbconvert --execute`),
đọc source code từng hàm được gọi.

## Sự cố trong lúc audit — đã xử lý, ghi lại minh bạch

Chạy thật 6 notebook (để trả lời "chạy được không" theo đúng NV1) có tác
dụng phụ ngoài ý muốn: mỗi notebook có cell đầu tiên tự `os.chdir()` về
project root rồi ghi output bằng **đường dẫn tương đối** — vì lệnh
`jupyter nbconvert` được gọi từ chính project root thật (không phải sandbox),
3 file production thật đã bị ghi đè:

- `data/processed/stock_features.parquet` (từ notebook 05) — file này
  được ~20 script/module production đọc trực tiếp (`build_portfolio_stack.py`,
  `run_alpha_scoring.py`, `run_meta_ranking.py`, `final_watchlist.py`, v.v.).
  Bản notebook tự ghi **thiếu cột** so với bản chính thức (chỉ ~25-30 cột từ
  cell 3+5, thiếu `forward_return_5/10/20/60d`, `realized_vol_10d/60d`,
  `suspect_corporate_action`, `value_zscore_20d`, `volume_zscore_20d`,
  `above_ma20/50/200`, `distance_ma20/50/200`, `market`, ... so với 49 cột
  bản `scripts/generate_features.py` tạo ra).
- `data/processed/market_features.parquet` (từ notebook 06) — bị ghi đè
  với dữ liệu **có bug đã biết** (xem NV3 mục 06 dưới) — `market_regime`
  không bao giờ ra "Risk-on" (0/1631 ngày), `crash_severity`/`breakout_signal`
  toàn "Unknown"/"Normal".
- `data/processed/stock_features_distribution.parquet` (từ notebook 04) —
  xác nhận không có consumer nào khác (`grep -rl` trong `src/`, `scripts/`
  ra rỗng) nên rủi ro thấp, nhưng vẫn bị ghi đè ngoài ý muốn.
- `data/signals/monte_carlo_*.parquet` (từ notebook 08) — xác nhận không
  có consumer nào khác ngoài chính notebook (chỉ `src/models/monte_carlo.py`
  định nghĩa hàm, không script nào đọc lại các file này).

Đã báo cho người dùng ngay khi phát hiện (trước khi đi tiếp), được xác nhận
chạy `python scripts/generate_features.py` để khôi phục đúng — đây là chính
con đường production dùng để tạo 2 file trên (đọc `full_history_v2`, gọi
`add_market_regime(breadth, benchmark=benchmark)` đúng chữ ký, không phải
backtest/test mới). Đã chạy xong, xác nhận lại: `stock_features.parquet`
đủ 49 cột, `market_regime` value_counts ra `Neutral 857 / Risk-off 503 /
Risk-on 272` (không còn 0 Risk-on), `crash_severity` ra giá trị thật
(`Normal 1357 / Correction 179 / Crash 76 / Unknown 20`). `git status` xác
nhận các file này nằm trong `.gitignore` (`data/processed/**/*.parquet`),
không có gì cần commit cho phần này — chỉ cần biết rằng dữ liệu production
hiện tại đã đúng trở lại.

**Bài học cho vòng sau (không sửa trong vòng này theo ràng buộc)**: bất kỳ
ai chạy tay `notebooks/02_market_research/05_*` hoặc `06_*` từ đầu đến cuối
sẽ tự động ghi đè 2 file production kể trên bằng bản thiếu cột/có bug, không
có cảnh báo nào. Notebook 08 cũng ghi vào `data/signals/` dù output không ai
dùng.

---

## NV1 — Kiểm kê từng notebook

Tất cả 6 file đều là `.ipynb` thuần (không có script/module đi kèm riêng
trong thư mục này — logic dùng chung nằm ở `src/features/`, `src/models/`,
`src/analytics/`, được import vào từng notebook).

| # | Notebook | Chạy được top-to-bottom? | Input | Output | Dùng ở đâu ngoài chính nó? |
|---|---|---|---|---|---|
| 04 | `04_market_distribution.ipynb` | **Có**, 0 lỗi/warning | `data/processed/clean_daily_ohlcv.parquet` (nguồn sạch, từ `full_history_v2`) | `data/processed/stock_features_distribution.parquet` (`dist_skew_60d`, `dist_kurt_60d`, `tail_ratio_60d`, rolling 60d) | **Không** — `grep -rl` trong `src/`+`scripts/` không ra kết quả. Orphan output. Nhưng 3 cột nó tính (`dist_skew_60d`/`dist_kurt_60d`/`tail_ratio_60d`) cũng được `scripts/generate_features.py` tính lại vào `stock_features.parquet` (dùng chung `src/features/distribution.py`) — đó mới là bản các script khác đọc. |
| 05 | `05_volatility_regime.ipynb` | **Có**, 0 lỗi/warning | `data/processed/clean_daily_ohlcv.parquet` | Ghi đè **`data/processed/stock_features.parquet`** — file production thật, nhưng bản notebook tự ghi thiếu cột (xem sự cố ở trên) | **Có, rất nhiều** (~20 script/module) — nhưng chỉ đúng khi được tạo bởi `scripts/generate_features.py`, không phải khi chạy tay notebook này. |
| 06 | `06_market_regime.ipynb` | **Có**, 0 lỗi/warning (nhưng output sai — xem NV3) | `data/processed/stock_features.parquet` | Ghi đè **`data/processed/market_features.parquet`** | `scripts/run_stealth_accumulation_screen.py` (`regime_pass` filter), `scripts/generate_features.py` tự tạo lại đúng. |
| 08 | `08_monte_carlo_simulation.ipynb` | **Có**, 0 lỗi/warning | `data/processed/clean_daily_ohlcv.parquet`, 1 mã cổ phiếu do người dùng chọn tay (mặc định `HPG`, `stop_pct=0.01`/`target_pct=0.20` là default demo, có ghi "CUSTOMIZABLE") | `data/signals/monte_carlo_{exits,path_summary,probability_table,terminal_summary}.parquet` — bị ghi đè mỗi lần chạy cho **1 mã duy nhất** | **Không** — không script nào đọc lại 4 file này. Công cụ tương tác/scratch, không phải batch pipeline. |
| 10 | `10_benchmark_diagnostics.ipynb` | **Có**, 0 lỗi/warning (nhưng có bug số liệu — xem NV3) | `data/processed/clean_daily_ohlcv.parquet`, `data/processed/benchmark_vnindex.parquet`, `data/signals/stealth_accumulation_backtest_{summary,by_date}.parquet` | Không ghi file nào (đọc-only, thuần diagnostic/QA) | Tự thân là công cụ QA (đối chiếu benchmark thật vs market-proxy tự dựng), không feed pipeline nào. |
| 13 | `13_advanced_quant_analysis.ipynb` | **Có**, 0 lỗi/warning | `data/signals/setup_signals.parquet` (output pipeline alpha-signals, có fallback về `stock_features_volatility.parquet`/`stock_features_distribution.parquet` nếu rỗng) | Không ghi file nào (đọc-only) | Không — thuần explore (correlation, momentum rank, pair divergence, rolling beta). |

Ghi chú NV1 chung: cả 6 notebook đều tự `os.chdir()` về project root ở cell
đầu và không phụ thuộc state ẩn từ cell chạy tay trước đó — xác nhận bằng
cách chạy `nbconvert --execute` trên kernel sạch, không có bất kỳ cell nào
lỗi vì thiếu biến/import.

---

## NV2 — Phân loại theo chuẩn dự án

| Công cụ (nguồn) | Phân loại | Bằng chứng | Trùng lặp với gì |
|---|---|---|---|
| `dist_skew_60d`, `dist_kurt_60d` (04, `src/features/distribution.py`) | **VALIDATED (một phần)** — bản thân 2 factor này đã qua kiểm định IC thật, nhưng **không phải trong notebook này** | `docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md` mục NV5: `dist_kurt_60d` full/residualized t_NW=+4.47 (top combo, |t|>3). `dist_skew_60d` nằm trong danh sách 11 tổ hợp sống sót BH-FDR nhưng không đạt |t|>3 thủ công (`docs/reports/scoring/ROBUSTNESS_REPORT.md` dòng 92-95). Kiểm định này chạy qua `scratch/diagnose_factor_ic_robust.py`, không phải notebook 04 — notebook chỉ hiển thị bảng sort theo `tail_ratio_60d`, không tự làm IC test. | Không trùng công cụ nào khác trong dự án — đây là nguồn duy nhất tính 2 factor này (dùng chung `src/features/distribution.py` với `generate_features.py`). |
| `tail_ratio_60d` (04) | **WEAK / hướng chưa xác định** | `audit/PATH_TO_100.md` mục 3: "hướng xếp hạng có thể sai (chưa kiểm định riêng), việc nhỏ còn treo". `ROBUST_FACTOR_IC_REPORT.md` dòng 58: raw t_NW=+2.53 (top150, residualized) — dưới ngưỡng |t|>3. Cùng factor được dùng trong `risk_score` (đã đóng, trùng cụm vol, xem `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2). | `risk_score` (`src/screening/*`) dùng cùng cột này — đã có kết luận riêng (đóng, trùng cụm vol). |
| `realized_vol_20d`, `atr_pct_14` (05, `src/features/volatility.py`) | **VALIDATED** | Top combo trong `FACTOR_RETEST_V2_REPORT.md` NV5 (t_NW=-5.41 và -5.76/-5.65). `realized_vol_20d` là 1 trong 2 thành phần của `alpha_score` v2 đang chạy shadow thật (`PROJECT_STATE.md` mục 1, `docs/reports/scoring/SCORE_V2_REPORT.md`). | Tính lại y hệt trong `scripts/generate_features.py` (cùng module) — không phải trùng lặp xấu, là cùng một nguồn. |
| `volatility_percentile`/`volatility_regime` (5 tier: Low/Normal/High/Stress/Panic, 05) | **WEAK — đã kiểm định như hypothesis vol-regime timing và bị bác** | `docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` NV2: label "index 60d realized vol vs. its own history" (cùng họ với `volatility_regime`) được test làm biến phân tách disaster-fold, kết luận "Neither label cleanly separates the disasters" — 2022 disaster rơi vào vol thấp, 2026 disaster rơi vào vol cao, ngược nhau. Đây chính là **trùng lặp user hỏi cụ thể** ("vol-regime đã thử ở FOLD_AUTOPSY_REPORT"). | `FOLD_AUTOPSY_REPORT.md` NV2 (index vol regime). Kết quả: không dùng được làm regime-timing overlay, nhưng vẫn hợp lệ làm nhãn mô tả. |
| `market_regime` (Risk-on/Neutral/Risk-off, 06, `src/models/regime.py::classify_market_regime`) | **WEAK (đã test, không tách được disaster fold) + INCORRECT như notebook đang chạy** | *Weak*: label "index above MA200" (thành phần của market_regime) test trong `FOLD_AUTOPSY_REPORT.md` NV2 — không tách sạch 2 fold thảm họa khỏi 3 fold tốt. *Incorrect*: notebook gọi `add_market_regime(breadth)` **không truyền `benchmark=`** (cell 3, `06_market_regime.ipynb`) → tái hiện đúng bug đã biết và đã sửa: "index_above_ma50/200 were always False ... making Risk-on structurally unreachable" (docstring `add_index_trend_features`, `src/models/regime.py` dòng 25-30). Xác nhận bằng chạy thật: value_counts ra `Risk-off 1296 / Neutral 335 / Risk-on 0` khi chạy notebook, so với `Risk-off 503 / Neutral 857 / Risk-on 272` khi gọi đúng qua `scripts/generate_features.py` (dòng 113: `add_market_regime(breadth, benchmark=benchmark)`). Notebook cuối sửa `b437c5d` (2026-07-01); fix ở `regime.py` là commit `86412ed` (2026-07-09) — **notebook có trước fix 8 ngày và chưa bao giờ được cập nhật theo**. `tests/test_market_regime_upgrade.py::test_market_regime_backward_compatible_without_benchmark` xác nhận đây là hành vi "backward-compatible" CÓ CHỦ ĐÍCH ở cấp hàm (không phải bug code) — nhưng notebook vô tình rơi vào đúng nhánh cũ này. | `FOLD_AUTOPSY_REPORT.md` NV2 (index-above-MA200). `CRASH_RISK_RESEARCH_REPORT.md` (breadth-collapse, xem hàng dưới). |
| `crash_severity`, `breakout_signal` (06) | **NOT_VERIFIABLE (đúng ra) / INCORRECT (như notebook đang chạy)** | Cùng lý do thiếu `benchmark=`: `index_drawdown_pct` luôn NaN → `crash_severity` toàn "Unknown" (xác nhận value_counts khi chạy notebook), `breakout_signal` toàn "Normal". Không tìm thấy report nào kiểm định riêng khả năng dự báo của `crash_severity`/`breakout_signal` (đây là chỉ báo mô tả trực tiếp từ drawdown, không phải factor IC-tested) — `grep` toàn bộ `docs/`/`audit/` không ra kết quả nào ngoài chính docstring nguồn. | Không trùng công cụ khác được tìm thấy. |
| `pct_above_ma50`/breadth score (06, `src/features/breadth.py`) | **WEAK — biến thể đã test và có 1 biến thể khác đầy hứa hẹn hơn nhưng notebook không dùng** | `market_regime`'s `pct_above_ma50 >= 0.55` (ngưỡng đơn, không có persistence filter) là bản legacy. `CRASH_RISK_RESEARCH_REPORT.md` đã test một biến thể khác của **cùng cột `pct_above_ma50`**: ngưỡng cực trị `<0.10` + yêu cầu bền vững 3 ngày liên tiếp — cải thiện 4/5 fold, giảm gần nửa lỗ năm 2022 (-27.6%→-15.1%), nhưng tự nhận "candidate, chưa confirmed fix" (2 caveat: chọn tham số nhìn thẳng vào fold 2022, và check out-of-sample 2020 không kết luận được vì thiếu dữ liệu warmup). Notebook 06 chỉ hiển thị bản ngưỡng đơn cũ, không có bản persistence-filtered mới hơn. | `CRASH_RISK_RESEARCH_REPORT.md` (breadth<0.10 persist-3d) — cùng cột nguồn, khác cách dùng, một bên đã research sâu hơn. |
| `market_entropy_21d/63d/126d`, `market_entropy_regime`, `market_entropy_shift` (06, `src/analytics/entropy.py`) | **WEAK / MIẤU-CALIBRATED — xem kết luận riêng NV4 bên dưới** | Xem mục NV4. | Không tìm thấy report nào đề cập "entropy" ngoài `docs/OPERATIONS.md` (liệt kê file, không phải kiểm định). `FOLD_AUTOPSY_REPORT.md` test 3 label khác (MA200, vol regime, breadth-vs-history) nhưng **không test entropy** — đây là khoảng trống thật, chưa từng bị bác bỏ, cũng chưa từng được xác nhận. |
| Monte Carlo bootstrap (08, `src/models/monte_carlo.py`) | **PLAUSIBLE_BUT_UNVALIDATED** | `bootstrap_price_paths` dùng IID resample (`rng.choice(..., replace=True)`) trên **toàn bộ lịch sử** `return_1d` của 1 mã (2020-2026 gộp chung, không phân biệt regime/giai đoạn) — bỏ qua volatility clustering/autocorrelation, một giới hạn phương pháp luận đã biết của bootstrap i.i.d. cho time series tài chính. `grep` toàn bộ `docs/`/`audit/` không ra kết quả nào đối chiếu xác suất Monte Carlo dự báo (`p_hit_target`, `var_95`, ...) với kết quả thật đã xảy ra — chưa từng kiểm định out-of-sample. | Không trùng công cụ nào khác. |
| Correlation heatmap, `top_correlation_pairs`, `pair_divergence_zscore`, `screen_pair_divergences`, `compute_rolling_beta`, `correlations_by_regime` (13, `src/analytics/advanced.py` + `src/analytics/correlation.py`) | **NOT_VERIFIABLE** | `grep` toàn bộ `docs/`, `audit/`, `PUSH_REVIEW.md` cho từng tên hàm/khái niệm (`pair_divergence`, `divergence_zscore`, `cross_sectional_momentum`, `momentum_rank`, "pairs trading") ra **0 kết quả** — chưa từng được nhắc tới trong bất kỳ report kiểm định nào. Có unit test (`tests/test_advanced_quant.py`) xác nhận code chạy đúng theo spec toán học của nó, nhưng unit test không phải kiểm định thống kê/dự báo. | `add_cross_sectional_momentum_rank` (momentum_20d = `pct_change(20)` xếp hạng cross-sectional) trùng họ trực tiếp với `return_20d`/`relative_strength_20d` — 2 factor NÀY đã được test và **thất bại**: `FACTOR_RETEST_V2_REPORT.md` NV5: "Pure return/momentum factors (return_5d/10d/20d/60d, relative_strength_20d, sector_relative_strength_20d) show no combination clearing the bar" (0/192 với |t_NW|>3). Notebook 13 hiển thị "Top 10 Momentum Names" mà không nói rõ họ factor này đã test và không có edge — rủi ro đọc nhầm. |
| `correlation_matrix_by_regime` (13) | **NOT_VERIFIABLE + lưu ý ngữ nghĩa** | Filter theo `volatility_regime` **của từng mã riêng lẻ** (không phải regime toàn thị trường) — nghĩa là correlation giữa A và B trong bucket "Low Vol" chỉ tính trên những ngày CẢ HAI mã cùng tự ở "Low Vol" theo lịch sử riêng của chính nó, không phải ngày thị trường chung ở trạng thái low-vol. Notebook không giải thích điều này — dễ đọc nhầm thành "correlation trong giai đoạn thị trường yên tĩnh". Xác nhận qua code (`src/analytics/advanced.py::correlation_matrix_by_regime` dòng 186: `subset = df[df[regime_col] == regime_value]` áp trực tiếp lên frame long-format theo mã). Nhiều NaN trong output thật (nhiều cặp mã không đủ `min_periods=20` ngày trùng regime) — mẫu thưa. | Không trùng công cụ khác. |
| Benchmark diagnostics tự thân (10, `src/analytics/benchmark.py`) | **INCORRECT** (bug số liệu trong chính công cụ QA) | Xem NV3 mục 10 bên dưới — `mean_return_spread = -inf` là số thật notebook hiển thị. | Không áp dụng (đây là công cụ QA, không phải alpha signal). |

---

## NV3 — Lỗi kỹ thuật cơ bản

**Look-ahead / full-sample normalize thay vì rolling**: **không tìm thấy
trường hợp nào** trong 6 notebook. Đã đọc trực tiếp từng hàm được gọi:
- `add_rolling_distribution_stats` (`src/features/distribution.py`) — toàn
  bộ `rolling(window, min_periods=20)` theo `groupby("symbol")`.
- `add_volatility_percentile` (`src/features/volatility.py`) — percentile
  tính bằng `rolling(window).apply(rank(pct=True))`, không phải rank trên
  toàn mẫu.
- `rolling_shannon_entropy` (`src/analytics/entropy.py`) — bin edges tính
  lại cho từng cửa sổ trượt (comment nguồn ghi rõ: "Compute bin edges per-
  window to avoid look-ahead bias (no global edges)").
- `calculate_market_breadth` (`src/features/breadth.py`) — aggregate cross-
  sectional theo từng ngày, dữ liệu input mỗi ngày chỉ dùng thông tin đã có
  đến ngày đó.
- `compute_rolling_beta`, `add_cross_sectional_momentum_rank`,
  `pair_divergence_zscore` (`src/analytics/advanced.py`) — toàn bộ
  `rolling()`/`pct_change(lookback)`, không có thao tác full-sample.
- `bootstrap_price_paths` (08) dùng toàn bộ lịch sử làm pool để mô phỏng
  **tương lai** — đây là thiết kế đúng cho một công cụ mô phỏng forward-
  looking tại thời điểm hiện tại (không phải backtest lịch sử), không tính
  là look-ahead.

**Nguồn dữ liệu**: cả 6 notebook đọc từ `data/processed/clean_daily_ohlcv.parquet`
hoặc dẫn xuất của nó (`stock_features.parquet`, `market_features.parquet`,
`setup_signals.parquet`) — tất cả cuối cùng bắt nguồn từ
`OFFICIAL_PRICE_RAW_DIR = data/full_history_v2/raw` (`src/data/dataset_config.py`
dòng 25, xác nhận qua `scripts/generate_features.py` Step 1). **Không có
notebook nào trỏ đường cũ/quarantine** (`grep -i "quarantine\|data/raw/daily_ohlcv"`
trong cả 6 file ra rỗng).

**Hard-code không rõ nguồn gốc**:
- `classify_entropy_regime` (`src/analytics/entropy.py` dòng 87-97):
  `low_threshold=0.35`, `high_threshold=0.70` — không tìm thấy report nào
  giải thích cách chọn. Thực tế đã làm cho nhãn "Structured" chết hoàn toàn
  (xem NV4).
- `classify_market_regime` (06): ngưỡng `pct_above_ma50>=0.55`,
  `advance_decline_ratio>=1.2`, `vol_pct<0.8`, `score>=4`/`score>=2` — docstring
  tự ghi "Legacy 3-tier breadth score ... Formula unchanged from before",
  tức tự nhận là kế thừa không có nguồn gốc thống kê mới.
- `classify_breakout_signal` (06): `near_high_threshold=-0.03`,
  `breadth_threshold=0.60`, `ad_ratio_threshold=1.3`, `volume_ratio_threshold=1.2`
  — không tìm thấy report nào trích dẫn cách chọn 4 số này.
- `classify_crash_severity` (06): `-10%`/`-20%` có giải thích trong docstring
  (khớp đặc điểm crash 2022 thật: min drawdown -29.2%, so với correction
  2023-2026 max -8.9% đến -18.1%) — **có căn cứ**, không tính là hard-code
  vô căn cứ.
- 08 (`stop_pct=0.01`, `target_pct=0.20`, `horizon_days=60`,
  `simulations=100000`): cell tự ghi rõ "CUSTOMIZABLE — Change the symbol
  ticker/parameters here" — đây là default demo cho người dùng tự sửa mỗi
  lần chạy, không phải tham số đã kiểm định, nhưng minh bạch về việc đó nên
  không tính là "hard-code che giấu".

**Bug số liệu cụ thể tìm thấy — notebook 10 (`10_benchmark_diagnostics.ipynb`)**:
Cell 5 hiển thị `mean_return_spread = -inf`. Đã truy nguyên tận gốc (không
đoán): `build_market_proxy_benchmark` (`src/analytics/benchmark.py` dòng 82-104)
tính `market_proxy_return_1d` bằng trung bình cross-sectional của
`return_1d` mọi mã mỗi ngày, **không có guard chống giá trị vô cực**. Dữ
liệu gốc `clean_daily_ohlcv.parquet` có 387 dòng `close == 0` (166 mã, toàn
bộ nằm trong 2020-01-13 → 2020-02-25 — giai đoạn warmup dữ liệu sớm nhất;
xác nhận: 0 dòng `close==0` sau 2020-02-25). Một mã có `close=0` rồi
`close>0` ngày kế tiếp tạo `pct_change()=inf` (887 dòng bị ảnh hưởng theo
cách tính này). Chỉ cần 1 mã có `return_1d=inf` trong ngày đó là đủ kéo
`market_proxy_return_1d` của CẢ THỊ TRƯỜNG ngày đó thành `inf` (xác nhận
trực tiếp: đúng 25 ngày trong Jan-Mar 2020 có `market_proxy_return_1d=inf`,
làm `return_spread=-inf` các ngày đó, kéo `mean_return_spread` toàn kỳ
xuống `-inf`). Đáng chú ý: `_clean_benchmark_returns` (cùng file, áp cho
phía `benchmark_df`) **có** guard chống giá trị bất thường (`ratio.abs() <= 0.30`
fallback), nhưng `build_market_proxy_benchmark` (áp cho phía market-proxy)
thì **không có** guard tương đương — đây là điểm bất đối xứng cụ thể gây
ra bug. Lưu ý: 387 dòng `close==0` **đã được validator sản xuất
(`validate_ohlcv`) ghi nhận từ trước** (`non_positive_close: 387`, xác nhận
lại qua log chạy `scripts/generate_features.py` hôm nay) — không phải phát
hiện mới về chất lượng dữ liệu, cái mới là: notebook 10 không có phòng vệ
trước hậu quả của vấn đề đã biết đó, khiến số liệu QA tự nó bị hỏng mà
không có cảnh báo nào hiển thị cho người đọc.

**Chạy độc lập / phụ thuộc state ẩn**: cả 6 notebook chạy sạch qua
`nbconvert --execute` trên kernel mới (không kế thừa bất kỳ cell nào chạy
tay trước đó) — **không có notebook nào phụ thuộc state ẩn**.

---

## NV4 — Kết luận riêng cho entropy

`market_entropy_{21,63,126}d` + `market_entropy_regime` +
`market_entropy_shift` (`src/analytics/entropy.py`, dùng trong notebook 06):

1. **Chưa từng được kiểm định như một tín hiệu dự báo.** `grep` toàn bộ
   `docs/`, `audit/`, `PUSH_REVIEW.md` cho "entropy": kết quả duy nhất là
   `docs/OPERATIONS.md` (liệt kê file tồn tại, không phải kiểm định).
   `FOLD_AUTOPSY_REPORT.md` — report kiểm định regime-label kỹ nhất đang có
   trong dự án — test 3 label khác (index-vs-MA200, vol regime,
   breadth-vs-history) nhưng **không test entropy**. Đây là khoảng trống
   thật (chưa test), khác với "đã test và thất bại" của 3 label kia.

2. **Có lỗi hiệu chỉnh (calibration) cụ thể, xác nhận bằng dữ liệu thật.**
   `classify_entropy_regime` chia 3 vùng: Structured (≤0.35), Transitional
   (0.35-0.70), Chaotic (≥0.70). Đo trực tiếp trên `market_features.parquet`
   (dữ liệu 2020-01 → 2026-07, sau khi phục hồi đúng):

   | Cửa sổ | Min | Max | Số ngày <0.35 |
   |---|---|---|---|
   | `market_entropy_21d` | 0.529 | 0.896 | **0 / 1611** |
   | `market_entropy_63d` | 0.495 | 0.941 | **0 / 1569** |
   | `market_entropy_126d` | 0.455 | 0.889 | **0 / 1506** |

   Nhãn **"Structured" chưa bao giờ xuất hiện, ở BẤT KỲ cửa sổ nào, trong
   toàn bộ 6.5 năm dữ liệu**. Value_counts thật của `market_entropy_regime`
   (dựa trên cửa sổ 21d): `Chaotic 1316 / Transitional 295 / Unknown 21 /
   Structured 0`. Về mặt thực hành, đây là bộ phân loại 2 nhãn (Transitional/
   Chaotic), không phải 3 nhãn như thiết kế.

3. **Cơ chế kỹ thuật khả dĩ gây ra hiện tượng trên** (quan sát, chưa kiểm
   chứng bằng thực nghiệm riêng — ghi rõ đây là suy luận có căn cứ, không
   phải đã test): `rolling_shannon_entropy` dùng `n_bins=24` cố định cho cả
   3 cửa sổ. Với `window=21` (cửa sổ ngắn nhất, cũng là cửa sổ dùng để phân
   loại `market_entropy_regime`), tỷ lệ mẫu/bin ≈ 21/24 ≈ 0.88 — dưới 1
   mẫu/bin trung bình. Ước lượng Shannon entropy từ histogram thưa mẫu như
   vậy có thiên lệch dương đã biết trong thống kê (entropy ước lượng cao
   hơn entropy thật khi số bin gần hoặc vượt số mẫu) — khả năng đây là
   nguyên nhân cấu trúc khiến entropy đo được hiếm khi xuống thấp, độc lập
   với trạng thái thị trường thật. Đây là giả thuyết kỹ thuật hợp lý dựa
   trên thiết kế code, **chưa phải kết luận đã kiểm định** — cần một test
   riêng (vd. so `n_bins` khác nhau, hoặc entropy trên dữ liệu giả lập biết
   trước) để xác nhận trước khi sửa.

**Kết luận entropy**: WEAK — không phải vì sai code (unit test
`tests/test_entropy_analytics.py` xác nhận hàm chạy đúng theo spec toán học
của chính nó, không có look-ahead), mà vì (a) chưa từng kiểm định khả năng
dự báo, và (b) ngưỡng phân loại 3-tier trên thực tế chỉ hoạt động như 2-tier
do miscalibration đã đo được trực tiếp, không phải suy đoán.

---

## Đề xuất (CHƯA làm — để quyết định ở vòng sau)

**Ưu tiên theo chi phí thấp / bằng chứng đã có sẵn** (không cần dữ liệu
mới, không cần backtest mới):

1. **Sửa `06_market_regime.ipynb` truyền thiếu `benchmark=`** — chi phí S
   (1 dòng), bằng chứng đã đủ (test suite đã có, production script đã làm
   đúng, chỉ cần đồng bộ notebook). Rủi ro cao nhất trong toàn bộ audit này
   vì nó âm thầm ghi đè file production mỗi khi ai đó chạy tay.
2. **Thêm guard chống `inf`/`close<=0` vào `build_market_proxy_benchmark`**
   (`src/analytics/benchmark.py`) — chi phí S, cùng pattern guard đã có sẵn
   ở `_clean_benchmark_returns` ngay trong cùng file, chỉ cần áp tương tự
   cho phía market-proxy.
3. **Đồng bộ cột output của `05_volatility_regime.ipynb` với
   `scripts/generate_features.py`** hoặc đổi tên/đường dẫn output của
   notebook để không trùng file production — chi phí S/M tùy hướng chọn
   (thêm bước hoặc đổi path).
4. **Cân nhắc đổi output path của notebook 04/08** sang thư mục
   `scratch/`/không trùng `data/processed/`, `data/signals/` — vì xác nhận
   không ai đọc lại các file này, việc chúng nằm trong thư mục "production
   look-alike" chỉ tạo rủi ro nhầm lẫn/ghi đè như đã xảy ra trong audit này.

**Cần prereg mới hoàn toàn (việc lớn hơn, không làm ở đây)**:

5. **Kiểm định predictive power của `market_entropy_regime`** cho cùng mục
   đích `FOLD_AUTOPSY_REPORT.md` đã dùng cho 3 label khác (tách disaster
   fold) — đây là khoảng trống thật, chưa test, không phải đã-test-và-fail.
6. **Kiểm định `pair_divergence_zscore`/`screen_pair_divergences`** như một
   ứng viên tín hiệu pairs-trading thật — hiện chỉ có unit test đúng công
   thức, chưa có IC/backtest nào.
7. **Kiểm định `bootstrap_price_paths`** — so xác suất Monte Carlo dự báo
   (`p_hit_target`, `var_95`, `cvar_95`) với kết quả thật đã xảy ra trên một
   mẫu giao dịch lịch sử (walk-forward), và cân nhắc block-bootstrap thay
   cho i.i.d. bootstrap để giữ lại volatility clustering.
8. Nếu muốn dùng `pct_above_ma50<0.10` persist-3d (từ
   `CRASH_RISK_RESEARCH_REPORT.md`) thay cho ngưỡng đơn 0.55 hiện tại trong
   `classify_market_regime` — báo cáo đó đã tự nhận "candidate, chưa
   confirmed fix", cần re-validate thêm thời gian/dữ liệu trước khi đổi.

---

*Audit thực hiện 2026-07-20/21. Không có thay đổi logic nào trong
`02_market_research/` hay `src/`. Thay đổi dữ liệu duy nhất: khôi phục 2
file production (`stock_features.parquet`, `market_features.parquet`) về
đúng trạng thái sau khi bị notebook execution ghi đè ngoài ý muốn trong lúc
audit — cả hai đều gitignored, không có gì cần commit cho phần đó.*
