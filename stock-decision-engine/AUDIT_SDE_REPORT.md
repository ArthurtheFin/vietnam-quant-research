# AUDIT_SDE_REPORT — audit thuần cho `stock-decision-engine/`, không sửa code

**Ngày**: 2026-07-17. **Phạm vi**: audit-only, đọc + đối chiếu + một test dữ
liệu (ladder test), KHÔNG sửa một dòng logic nào của `stock-decision-engine/`,
KHÔNG chạy backtest. Bug tìm thấy ghi lại ở đây, sửa có kế hoạch ở Vòng 2.
Không đụng dữ liệu disclosure (firewall vẫn nguyên — không tìm thấy import
disclosure nào trong `stock-decision-engine/`, xem mục 2.4).

**Bối cảnh**: `stock-decision-engine/` là một notebook quyết định độc lập,
tách khỏi pipeline `alpha_score`/`final_watchlist` chính, người dùng đang
dùng thật (20 lần chạy phân tích, 172 file output cho 16 mã: ACB, BID, BMP,
CTG, GEX, HDB, HPG, POW, SSI, STB, TPB, VCB, VIB, VIX, VPB, VPL — không phải
"64 file" như mô tả trong `PUSH_REVIEW.md` dòng 313, con số đó có vẻ chỉ đếm
subset 6 mã gần nhất; xem mục 2.2 để có bảng đầy đủ). Engine này **chưa từng
được backtest** — không có test, không có notebook validation, không có
report nào trong lịch sử git nhắc đến việc kiểm định điểm số của nó (mục 3.1).

---

## 1. Bản đồ kiến trúc (NV1)

### 1.1 Luồng chạy thực tế

Người dùng sửa cell đầu của `notebooks/stock_buy_decision.ipynb`
(`TICKER = "..."`), chạy toàn bộ notebook. Không có CLI/script khác.

```
notebooks/stock_buy_decision.ipynb
  ├─ src/data.py       load_config, load_stock_ohlcv, load_benchmark_ohlcv, load_backtest_evidence
  ├─ src/features.py   enrich()  →  ~40 chỉ báo kỹ thuật + relative-strength vs benchmark
  ├─ src/simulation.py bootstrap_monte_carlo()  →  mô phỏng bootstrap 20 ngày
  ├─ src/scoring.py    score_decision()  →  8 sub-score có trọng số → final_score, decision, hard filters
  ├─ src/report.py     decision_summary(), save_outputs()  →  .txt + 2 .csv, KHÔNG có lineage metadata
  └─ src/visualization.py save_all_charts()  →  7 file .png
```

Output ghi vào `stock-decision-engine/outputs/{TICKER}_{ngày-cuối-trong-dữ-liệu}_*`.
Ngày trong tên file là ngày giao dịch cuối cùng có trong dữ liệu đã nạp
(`metrics['date']`), **không phải** ngày chạy hệ thống và **không phải** một
tham số cấu hình — đây là cách duy nhất để suy ra "dữ liệu tính đến ngày nào"
từ output, vì không có trường lineage nào khác (mục 2.3).

### 1.2 Công thức điểm số đầy đủ

`config.yaml` (không kèm bất kỳ chú thích/citation nào cho từng con số):

| Tham số | Giá trị | Nguồn gốc |
|---|---|---|
| `lookback_days` | 756 (~3 năm) | không rõ — hard-code |
| `mc_horizon_days` / `mc_paths` | 20 / 3000 | không rõ — hard-code |
| `min_avg_value_20d` | 10,000,000,000 (10 tỷ VND) | không rõ — hard-code |
| `atr_period` | 14 | quy ước TA chuẩn (Wilder), không phải điều tùy tiện, nhưng cũng không kiểm định riêng cho universe VN |
| `entry_atr_buffer` / `stop_atr_multiplier` / `target_atr_multiplier_1,2` | 0.5 / 2.0 / 3.0 / 5.0 | không rõ — hard-code |
| `score_thresholds.buy/watch/weak` | 75 / 60 / 45 | không rõ — hard-code |

`src/scoring.py` — 8 thành phần, trọng số cộng lại 100:

| Component | Weight | Công thức (điểm 0-100 nội bộ) |
|---|---|---|
| `market_regime` | 10 | Benchmark trên MA20/50/200 (20đ mỗi), slope MA50>0 (15đ), return 20d/60d>0 (10đ mỗi), drawdown>-8% (5đ), trừ 15đ nếu volatility percentile>85 |
| `trend` | 20 | Trên MA20/50/100/200 (10đ mỗi), MA-stack (20đ), slope MA20/50>0 (10đ mỗi), ADX≥20 & +DI>-DI (10đ), Donchian-20 breakout (5đ), cách đỉnh 52 tuần >-12% (5đ) |
| `momentum` | 15 | Return 5/20/60/120d dương (12đ mỗi), RSI trong [45,70] (20đ) hoặc biên (10đ), MACD hist dương & macd>signal (15đ), momentum acceleration>0 (17đ) |
| `relative_strength` | 15 | Excess return 20d/60d>0 (25đ mỗi), RS slope>0 (25đ), beta≤1.4 (15đ/5đ), corr<0.85 (10đ/5đ) |
| `alpha` | 15 | Jensen alpha>0 (20đ), Sharpe/Sortino/IR/Calmar theo ngưỡng cố định (15+15+15+15đ), backtest profit factor≥1.2 nếu có (20đ) |
| `risk` | 10 | ATR%≤3.5%/6% (25/15/5đ), volatility percentile≤60/85 (20/10/0đ), max drawdown>-25%/-40% (20/10/0đ), CVaR95>-4% (15/5đ), \|skew\|<1.5 (10/5đ), stop distance≤12% (10/0đ) |
| `liquidity` | 10 | avg_value_20d≥ngưỡng (40/20/0đ), volume 20d&60d>0 (20đ), volume_ratio∈[0.8,3.0] (15/8đ), volume_zscore∈[-2,3] (15/5đ), CMF>0 hoặc MFI≥50 (10đ) |
| `simulation` | 5 | Xác suất chạm target trước stop≥45%/30% (35/20/5đ), target>stop (25đ), expected return>0 (20đ), CVaR return>-8% (20/8đ) |

**Mọi ngưỡng số trong bảng trên (45/70 cho RSI, ADX≥20, beta≤1.4, corr<0.85,
CVaR>-4%, v.v.) là hard-code trong `src/scoring.py`, không có citation, không
có ghi chú nguồn gốc, không có test/notebook nào trong repo tính toán hoặc
kiểm định chúng.** Đây là bộ luật phân tích kỹ thuật rời rạc kiểu giáo trình
(textbook TA rules), không phải trọng số/ngưỡng suy ra từ dữ liệu VN thật.

---

## 2. Dữ liệu (NV2)

### 2.1 Nguồn giá — không tự fetch, đọc lại dữ liệu dùng chung của dự án chính

`src/data.py::load_stock_ohlcv` đọc theo thứ tự ưu tiên:
1. `data/processed/clean_daily_ohlcv.parquet` (toàn universe, lọc theo symbol)
2. Fallback nếu (1) không có dòng nào cho mã đó: `data/raw/daily_ohlcv/{TICKER}.parquet`

**Phát hiện A (MEDIUM)** — đường dẫn (2) là `LEGACY_PRICE_RAW_DIR` trong
`src/data/dataset_config.py`, bị đánh dấu tường minh "Forbidden... No
production code path (src/, scripts/) may read from here" (dataset_config.py
dòng 39-46) vì đây chính là nguồn dữ liệu **bẩn** (raw/adjusted-close mixing
bug). `stock-decision-engine/src/data.py` không import các hằng số
`OFFICIAL_*`/`LEGACY_PRICE_RAW_DIR` từ `dataset_config.py` — nó hard-code lại
chuỗi đường dẫn, nên không được convention "single source of truth" (thêm từ
28b9f60, 2026-07-13) bảo vệ. Hiện `data/raw/daily_ohlcv/` rỗng (đã dọn sang
`data/quarantine_existing_v1/` — mục 2.5) nên nhánh fallback này hiện không
kích hoạt được, nhưng code vẫn sẵn sàng đọc âm thầm không cảnh báo nếu thư
mục đó có file trở lại.

### 2.2 Ladder test — đúng như yêu cầu, áp cho toàn bộ 16 mã SDE đã chạy

Yêu cầu gốc là so HPG/TCB; SDE không có output cho TCB nên chạy ladder test
cho tất cả 16 mã có output thật. Phương pháp: nạp
`data/quarantine_existing_v1/clean_daily_ohlcv.parquet` (bản `clean_daily_ohlcv`
CŨ, TRƯỚC fix gate-6 — đây chính xác là file `stock-decision-engine` đã đọc
tại thời điểm tạo ra 20 output hiện có, xem mục 2.3 về mốc thời gian), so với
`data/full_history_v2/raw/{SYMBOL}.parquet` (dữ liệu đã xác nhận sạch) theo
từng ngày trùng nhau, tính `ratio = close_cũ / close_v2`.

| Mã | Số mức ratio riêng biệt | % ngày lệch >5% | Lệch tối đa | Kết luận |
|---|---|---|---|---|
| BID | 4 | 28.8% | 37.9% | **DÍNH BUG** |
| HDB | 6 | 42.8% | 96.4% | **DÍNH BUG** |
| HPG | 4 | 47.4% | 47.9% | **DÍNH BUG** |
| TPB | 7 | 34.4% | 114.6% | **DÍNH BUG** |
| VCB | 4 | 30.8% | 77.8% | **DÍNH BUG** |
| ACB, BMP, CTG, GEX, POW, SSI, STB, VIB, VIX, VPB, VPL | 1 | 0.0% | 0.000 | Sạch (ratio=1.000 mọi ngày) |

Mẫu "nhiều mức ratio riêng biệt, không phải hằng số ≈1" chính là chữ ký bậc
thang của raw/adjusted-close mixing bug đã mô tả ở
`docs/reports/data/DATA_BASELINE.md` mục "Open caveats" #1 và
`src/data/dataset_config.py` dòng 11-14 (nơi HDB, BID, HPG, VCB được nêu tên
tường minh là 3 trong số các mã có "exact 2x close-price mismatch" đã xác
nhận độc lập). 5/16 mã SDE (31%) rơi vào nhóm này.

**20 lần chạy, gắn nhãn theo mã:**

| Lần chạy | Trạng thái dữ liệu |
|---|---|
| BID_2026-06-26, BID_2026-06-30, HDB_2026-07-02, HPG_2026-06-26, TPB_2026-06-26, VCB_2026-06-30 | **6/20 — trên mã dính bug** |
| ACB_2026-06-26, BMP_2026-06-26, CTG_2026-06-26, GEX_2026-06-30, GEX_2026-07-06, POW_2026-06-26, POW_2026-07-06, SSI_2026-06-26, STB_2026-06-26, STB_2026-07-02, VIB_2026-06-26, VIX_2026-07-06, VPB_2026-07-06, VPL_2026-06-24 | 14/20 — trên mã sạch (theo ladder test) |

### 2.3 Mốc thời gian xác nhận: TOÀN BỘ 20 lần chạy đều trước khi dữ liệu được vá

Đối chiếu git log:
- `data/full_history_v2` chỉ tồn tại từ **2026-07-10** (`ee248f2`).
- `data/processed/clean_daily_ohlcv.parquet` chỉ được quy định phải regenerate
  từ `full_history_v2` (và thực sự được regenerate lần đầu) từ **2026-07-13**
  (`28b9f60`, gate #6 fix).
- 20 lần chạy của `stock-decision-engine` có ngày nhúng trong tên file từ
  **2026-06-24 đến 2026-07-06** — **toàn bộ đều SỚM HƠN** mốc 2026-07-13.

Nghĩa là: tại thời điểm mỗi lần chạy, `data/processed/clean_daily_ohlcv.parquet`
**chắc chắn** là bản CŨ (dữ liệu mà ladder test ở mục 2.2 vừa xác nhận dính
bug cho 5/16 mã). Đối chiếu trực tiếp giá trị `close` ghi trong
`*_metrics.csv` của 6 lần chạy trên mã dính bug với cả bản cũ (quarantine) và
`full_history_v2` cho đúng ngày cuối: hai bản này KHỚP NHAU (vì bug là dạng
"lệch theo từng đoạn ~29 ngày", không phải lệch mọi ngày — ngày cuối cùng
thường rơi ngoài đoạn lỗi), nhưng cả hai đều lệch nhẹ (~0.3-0.6%) so với con
số SDE tự ghi — chênh lệch nhỏ này khớp với việc dữ liệu được cập nhật/điều
chỉnh bình thường giữa lúc SDE chạy và lúc snapshot quarantine (2026-07-13),
**không phải** dấu hiệu của bug raw/adjusted-close (bug đó gây lệch 30-115%,
không phải 0.3-0.6%).

**Điểm mấu chốt**: bug không nằm ở giá đóng cửa của NGÀY CUỐI (ngày tính
điểm), mà nằm rải rác trong 756 ngày lookback dùng để tính MA50/100/200,
volatility 20d/60d, RSI-14, ATR-14, percentile 252 ngày, drawdown, v.v. Với
5 mã dính bug, các chỉ báo rolling-window này nhiều khả năng đã bị nhiễu bởi
các đoạn giá sai trong lịch sử — mức độ nhiễu cụ thể lên từng sub-score CHƯA
được đo trong vòng audit này (đó là việc của Vòng 2, xem mục 5).

### 2.4 Firewall & phạm vi dữ liệu khác

Không tìm thấy import/tham chiếu nào tới dữ liệu disclosure trong
`stock-decision-engine/src/` hay notebook — firewall dự án chính
(`CLAUDE.md` mục 5) không bị vi phạm.

### 2.5 Độ tươi hiện tại — nếu chạy LẠI HÔM NAY sẽ sạch

`data/processed/clean_daily_ohlcv.parquet` hiện tại (ngày dữ liệu mới nhất:
2026-07-16) đã được xác nhận regenerate từ `full_history_v2` từ 2026-07-13
(gate #6) và tiếp tục được `daily_run.sh` cập nhật mỗi ngày (`PROJECT_STATE.md`
mục 4). **Nếu người dùng chạy lại `stock-decision-engine` HÔM NAY cho bất kỳ
mã nào (kể cả 5 mã dính bug), dữ liệu giá đầu vào sẽ sạch** — bug là thuộc
tính của các file output ĐÃ TỒN TẠI (vintage cũ), không phải lỗi đứng yên
trong code `stock-decision-engine`, miễn là (a) nó tiếp tục đọc
`data/processed/clean_daily_ohlcv.parquet` như hiện tại và (b) automation
hằng ngày của dự án chính tiếp tục chạy đều.

### 2.6 Lineage — vi phạm CLAUDE.md mục 6

**Phát hiện B (MEDIUM)** — không file output nào của
`stock-decision-engine` (`*_metrics.csv`, `*_sub_scores.csv`,
`*_decision_summary.txt`) có trường lineage: không git commit hash, không
đường dẫn nguồn dữ liệu, không dấu thời gian sinh. Cách duy nhất để suy luận
"dữ liệu tính đến ngày nào" là ngày nhúng trong TÊN FILE (= ngày giao dịch
cuối trong dữ liệu đã nạp, mục 1.1) — không phải trường dữ liệu tường minh,
dễ nhầm với ngày chạy hệ thống. Vi phạm `CLAUDE.md` mục 6 ("Mọi artifact tự
sinh phải có lineage metadata").

---

## 3. Phương pháp (NV3)

### 3.1 Trạng thái kiểm định — chưa từng có

`git log --all -- stock-decision-engine/` chỉ có 3 commit (khởi tạo, snapshot
WIP, khôi phục output người dùng) — không commit nào về validation/backtest.
Không có file test nào (`tests/` không có gì tham chiếu
`stock-decision-engine`). Không notebook nào khác ngoài
`stock_buy_decision.ipynb` (thuần chạy quyết định, không phải validation).

`load_backtest_evidence()` (`src/data.py`) có gắn "bằng chứng backtest" từ
`data/signals/breakout_20d_trade_cards.parquet` — đây LÀ dữ liệu đã được
kiểm định thật của dự án chính, nhưng chỉ đóng góp một phần nhỏ của sub-score
`alpha` (tối đa 20/100 điểm nội bộ × 15% trọng số ≈ 3% điểm cuối), và bị bỏ
qua âm thầm (`available: False`) cho bất kỳ mã nào không có tín hiệu
breakout gần đây — tức đa số quyết định không có bằng chứng backtest thật
nào đứng sau, dù tên sub-score là `alpha`.

**Lưu ý đặt tên gây nhầm lẫn**: `_alpha_score` trong `stock-decision-engine`
(CAPM alpha/Sharpe/Sortino/IR/Calmar) và `alpha_score` của dự án chính
(`realized_vol_20d` 70% + `value_ma20` 30%, nhân tố v2 đã kiểm định) là HAI
KHÁI NIỆM HOÀN TOÀN KHÁC dùng chung tên — cần cẩn thận khi trao đổi giữa hai
hệ thống để tránh lẫn.

### 3.2 Look-ahead — KHÔNG tìm thấy vi phạm (điểm tích cực, ghi nhận cân bằng)

Rà toàn bộ `features.py`/`risk.py`/`simulation.py`:
- Mọi thống kê rolling dùng `.rolling()`/`.pct_change()`/`.ewm()` — cửa sổ
  lùi về quá khứ, không dùng `min_periods` kiểu full-sample.
- `volatility_percentile` xếp hạng percentile trên cửa sổ **lùi** 252 ngày
  (`rolling(252,...).rank(pct=True)`), không phải full-sample — không leak.
- Donchian breakout so giá đóng cửa hôm nay với đỉnh N ngày trước đó có
  `.shift(1)` đúng quy ước (không tự so với chính nó).
- Không có `.expanding()`, không có `.ffill()/.bfill()` kéo dữ liệu từ tương
  lai về quá khứ (2 chỗ `.fillna(0.0)` tìm thấy chỉ điền NaN tại-điểm bằng 0,
  không phải forward-fill).
- `ratios()` (Sharpe/Sortino/alpha CAPM...) và Monte Carlo bootstrap chỉ dùng
  đúng cửa sổ `lookback_days` (756 ngày) đã nạp tính đến ngày cuối — không
  vượt ra ngoài "hôm nay" của lần chạy.
- Ngưỡng quyết định (`score_thresholds`, ATR multiplier...) là hằng số cấu
  hình tĩnh, không tự calibrate trên chính mẫu đang chấm điểm.

**Kết luận NV3.2**: không có bằng chứng look-ahead/leakage trong cách tính
đặc trưng. Đây là điểm engine làm đúng theo kỷ luật của dự án chính, dù chưa
từng được test edge (khác với "không có leakage" ≠ "có edge dự báo thật").

### 3.3 Trùng họ với nhân tố đã bị kết án ở dự án chính — bằng chứng gián tiếp mạnh nhất

`src/screening/final_watchlist.py` có đúng 5 sub-score **trùng tên hoàn
toàn** với `stock-decision-engine`: `trend_score`, `momentum_score`,
`relative_strength_score`, `liquidity_score`, `risk_score`. Composite này đã
được `WATCHLIST_VALIDATION_REPORT.md` kiểm định IC/null-test đầy đủ và
**đóng hồ sơ ÂM TÍNH** ("neither composite nor minimal-watchlist baseline
cleared the pre-registered bar — Nhánh C, final_watchlist has no validated
alpha ranking"). Đối chiếu từng thành phần (`WATCHLIST_VALIDATION_REPORT.md`
mục 2):

| Thành phần `final_watchlist` | t_NW (full, residualized) | Kết luận dự án chính | Thành phần tương ứng trong SDE (trọng số) |
|---|---|---|---|
| `trend_score` | +0.64 (không nhất quán dấu qua 3 giai đoạn: +0.71/−0.31/+0.95) | Không rõ ràng, chưa kiểm định độc lập | `trend` (20%) |
| `momentum_score` | −0.42 | Âm, và về mặt toán học **trùng lặp hoàn toàn** với relative_strength_score (cùng công thức rank sau khi trừ excess return) | `momentum` (15%) |
| `relative_strength_score` | −0.42 (giống hệt momentum_score) | Âm | `relative_strength` (15%) |
| `liquidity_score` | **−4.19** | **Đảo chiều có ý nghĩa thống kê xác nhận** — thưởng thanh khoản cao dự báo SAI hướng, đã gỡ khỏi ranking | `liquidity` (10%) |
| `risk_score` | **+4.72** (thành phần duy nhất có bằng chứng riêng) | Đóng hồ sơ sau vì tương quan Spearman +0.822 với `v2_score` và −0.870 với `realized_vol_20d` — **trùng cụm biến động, không phải nguồn tin độc lập** | `risk` (10%) |

Ngoài `final_watchlist.py`, `SCORE_FORENSIC_REPORT.md` (dự án chính, nhân tố
`alpha_score` v1) tìm thấy `momentum_score`(25%)+`rs_score`(25%)+`trend_score`(20%)
= 70% trọng số **đảo dấu IC** giữa 2023-2025 (+0.014/+0.016) và **2026**
(**−0.106/−0.105**) — đúng giai đoạn 20 lần chạy của `stock-decision-engine`
đều nằm trong đó (tháng 6-7/2026) — và khi tách theo decile, nhóm được chấm
momentum CAO NHẤT lại có return kỳ vọng 20 ngày kế tiếp THẤP HƠN nhóm thấp
nhất 3.6 điểm phần trăm — "component designed to chase strength was, in this
specific fold, an active contrarian indicator."

**Không kết luận** `stock-decision-engine`'s `momentum`/`relative_strength`/`trend`
(50% tổng trọng số) có cùng lỗi định lượng CHÍNH XÁC như hai composite trên —
công thức cụ thể khác nhau (SDE dùng RSI/MACD/return đa khung thời gian +
excess-return-vs-benchmark/RS-slope/beta, không phải cross-sectional rank).
Nhưng đây là CÙNG HỌ nhân tố về mặt khái niệm ("đuổi theo sức mạnh giá gần
đây", "outperform benchmark gần đây") — và đó chính xác là họ nhân tố mà
CHÍNH DỰ ÁN NÀY, trên cùng loại dữ liệu VN, cùng giai đoạn 2026, đã 2 lần độc
lập tìm thấy IC âm hoặc không xác định. Đây là bằng chứng gián tiếp mạnh cho
việc nghi ngờ 50% trọng số của `stock-decision-engine`, dù không thay thế
được một kiểm định IC trực tiếp trên chính công thức của nó (Vòng 2).

`distance_ma20`/`distance_ma50` (dùng trong `price_extension_warning` và
`pullback_quality`) được `FACTOR_RETEST_V2_REPORT.md` kiểm định trực tiếp:
**không có ý nghĩa cho average-return IC** (\|t_NW\|=1.61) nhưng **lift phát
hiện tail-event cao thứ 2/47 ứng viên** (1.35) — khuyến nghị dự án chính là
"giảm trọng số, không loại bỏ hoàn toàn". Cách dùng của SDE (cảnh báo giá bị
kéo giãn quá xa MA20 tại điểm vào lệnh) gần với vai trò "event/extension
gate" hơn là "yếu tố xếp hạng return trung bình" — tương đối phù hợp với
bằng chứng hỗn hợp này, dù bản thân ngưỡng cụ thể (0.08 / 2×ATR%) chưa từng
được đối chiếu với kết quả `FACTOR_RETEST_V2_REPORT.md`.

`_risk_score` của SDE thưởng biến động THẤP (ATR%, volatility percentile
thấp hơn → điểm cao hơn) — cùng chiều với `realized_vol_20d`, nhân tố DUY
NHẤT đã được kiểm định độc lập thành công trong dự án chính (`SCORE_V2_DESIGN.md`).
Đây là điểm tích cực về HƯỚNG, nhưng cũng đồng nghĩa: nếu risk sub-score của
SDE có giá trị dự báo thật, nhiều khả năng nó đến từ CÙNG một nguồn tin
(biến động) mà v2 đã khai thác, không phải thông tin độc lập mới — giống hệt
kết luận dự án chính rút ra cho `final_watchlist.risk_score`.

### 3.4 Bảng phân loại 8 sub-score

| Sub-score | Trọng số | Look-ahead | Phân loại |
|---|---|---|---|
| `market_regime` | 10% | Sạch | PLAUSIBLE_BUT_UNVALIDATED |
| `trend` | 20% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — cùng họ với `trend_score`/`final_watchlist` (IC không nhất quán dấu, "never independently validated", gap-matrix mục Signal/Alpha) |
| `momentum` | 15% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — **rủi ro cao**: cùng họ nhân tố đảo dấu IC 2026 trong `SCORE_FORENSIC_REPORT.md` (−0.105, từ +0.016) |
| `relative_strength` | 15% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — **rủi ro cao**: cùng họ `rs_score` đảo dấu IC 2026 (−0.106, từ +0.014) và `relative_strength_score`/`final_watchlist` (t_NW=−0.42) |
| `alpha` (CAPM+backtest) | 15% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — phần CAPM ratios tính đúng công thức chuẩn; phần backtest evidence thật nhưng chỉ phủ một phần nhỏ mã/điểm |
| `risk` | 10% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — hướng khớp với nhân tố v2 đã validated, nhưng nếu có tín hiệu nhiều khả năng trùng cụm với chính nhân tố đó, không phải tin độc lập |
| `liquidity` | 10% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — vai trò khác `final_watchlist.liquidity_score` (ngưỡng khả năng giao dịch, không phải yếu tố xếp hạng return) nên phát hiện "đảo chiều" của dự án chính không áp trực tiếp, nhưng ngưỡng 10 tỷ VND vẫn hoàn toàn hard-code |
| `simulation` (Monte Carlo) | 5% | Sạch | PLAUSIBLE_BUT_UNVALIDATED — kỹ thuật bootstrap chuẩn, cài đặt đúng, nhưng xác suất đầu ra chưa từng đối chiếu với kết quả thật |

Không có sub-score nào rơi vào INCORRECT (không tìm thấy bug logic độc lập
với vấn đề dữ liệu) hay NOT_VERIFIABLE (mọi input đều là dữ liệu giá lịch sử
sẵn có, không phải loại không thể kiểm định về nguyên tắc). LEAKAGE_RISK:
không áp dụng cho bất kỳ thành phần nào (mục 3.2). VALIDATED: không áp dụng
cho bất kỳ thành phần nào — chưa có thành phần nào từng qua IC/backtest test
độc lập trên chính công thức của `stock-decision-engine`.

---

## 4. Findings theo severity

| # | Severity | Phát hiện | Bằng chứng |
|---|---|---|---|
| 1 | **HIGH** | 6/20 lần chạy (BID×2, HDB, HPG, TPB, VCB) dùng dữ liệu giá xác nhận dính raw/adjusted-close mixing bug trên phần lịch sử feed vào các chỉ báo rolling-window (MA/vol/RSI/ATR/percentile) | Mục 2.2-2.3, ladder test trực tiếp + đối chiếu mốc thời gian git |
| 2 | **HIGH** | 50% trọng số cuối (`trend`+`momentum`+`relative_strength`) rơi vào họ nhân tố mà chính dự án này đã 2 lần độc lập tìm thấy IC âm/không rõ ràng trên cùng loại dữ liệu, cùng giai đoạn 2026 | Mục 3.3, `SCORE_FORENSIC_REPORT.md` + `WATCHLIST_VALIDATION_REPORT.md` |
| 3 | **MEDIUM** | Không có lineage metadata trong bất kỳ output nào — vi phạm `CLAUDE.md` mục 6 | Mục 2.6 |
| 4 | **MEDIUM** | Toàn bộ ngưỡng/trọng số (`config.yaml` + hằng số trong `scoring.py`) hard-code không citation, không quy trình hiệu chỉnh nào được ghi lại | Mục 1.2 |
| 5 | **MEDIUM** | Chưa từng có test/backtest/validation nào cho chính công thức của `stock-decision-engine` trong lịch sử repo | Mục 3.1 |
| 6 | **LOW** | Fallback đọc `data/raw/daily_ohlcv/{TICKER}.parquet` — đường dẫn dự án chính đánh dấu "Forbidden" — không cảnh báo nếu kích hoạt; hiện không kích hoạt được vì thư mục rỗng | Mục 2.1 |
| 7 | **LOW** | `data.py` hard-code lại đường dẫn thay vì import từ `src/data/dataset_config.py` — không được convention single-source-of-truth của dự án chính bảo vệ nếu đường dẫn chính thức đổi trong tương lai | Mục 2.1 |
| 8 | **INFO** | Tên `_alpha_score` trùng nhưng khác khái niệm với `alpha_score` dự án chính — rủi ro nhầm lẫn khi trao đổi | Mục 3.1 |

## 5. Kết luận dữ liệu sạch/bẩn

**Không đồng nhất theo mã, không đồng nhất theo thời điểm.** 11/16 mã
(ACB, BMP, CTG, GEX, POW, SSI, STB, VIB, VIX, VPB, VPL) sạch trên toàn lịch
sử theo ladder test. 5/16 mã (BID, HDB, HPG, TPB, VCB) dính bug trên một
phần lịch sử — và TOÀN BỘ 20 output hiện có (kể cả 14 lần chạy trên mã
"sạch") đều được sinh ra TRƯỚC khi pipeline dữ liệu chính thức được vá
(2026-07-13), nên dùng bản `clean_daily_ohlcv.parquet` cũ dù kết quả với các
mã sạch tình cờ không bị ảnh hưởng. Nếu chạy lại HÔM NAY, dữ liệu sẽ sạch
cho mọi mã (mục 2.5) — nhưng các vấn đề phương pháp ở mục 3 (chưa kiểm định,
trùng họ nhân tố đã kết án) áp dụng như nhau bất kể dữ liệu sạch hay bẩn.

## 6. Khuyến nghị tạm thời cho 172 file output hiện có (trong lúc chờ Vòng 2)

1. **6 lần chạy trên BID/HDB/HPG/TPB/VCB**: coi các sub-score phụ thuộc
   rolling-window (`trend`, `momentum`, `risk`'s volatility measures) là
   **không đáng tin** cho đến khi chạy lại trên dữ liệu hiện tại (đã sạch).
   Chạy lại rẻ (chỉ cần mở lại notebook, đổi TICKER, chạy — không cần code
   mới) — khuyến nghị làm việc này sớm, độc lập với Vòng 2 backtest.
2. **14 lần chạy còn lại**: dữ liệu giá bản thân nó không có bằng chứng lỗi,
   nhưng **final_score và decision label vẫn nên được đọc như một checklist
   TA có tổ chức, không phải một điểm số đã kiểm định** — 50% trọng số nằm
   trên họ nhân tố có tiền sử IC âm trong chính dữ liệu VN 2026 (mục 3.3,
   4#2). Không có cơ sở để nói decision label ("BUY CANDIDATE" v.v.) tương
   quan với return thực tế trong tương lai.
3. Không dùng bất kỳ file nào trong số 172 file để so sánh/backtest chéo với
   `alpha_score`/`final_watchlist` của dự án chính cho đến khi Vòng 2 xong —
   không đồng nhất về validation status.
4. Đây là khuyến nghị tạm thời dựa trên audit, **không phải kết luận cuối
   cùng** — Vòng 2 (mục 7) sẽ cho câu trả lời định lượng thay vì suy luận
   gián tiếp qua họ nhân tố.

## 7. Đề xuất kế hoạch Vòng 2 (CHƯA LÀM — chỉ đề xuất)

**Mục tiêu**: backtest điểm số `stock-decision-engine` bằng hạ tầng sạch của
dự án chính (`full_history_v2`, IC Newey-West, null-test percentile, prereg
trước khi chạy — đúng kỷ luật `CLAUDE.md` mục 8-9).

**Cần bridge gì:**
- **Point-in-time re-scoring**: `score_decision()` hiện chỉ tính cho MỘT
  ngày cuối cùng của dữ liệu đã nạp. Để backtest, cần chạy `enrich()` +
  `score_decision()` cho MỌI ngày trong lịch sử (rolling, dùng đúng
  `lookback_days=756` kết thúc tại từng ngày t) trên `full_history_v2` — đây
  là phần việc kỹ thuật chính, không có sẵn.
- **Universe**: 16 mã hiện có output là mẫu quá nhỏ và không phải chọn ngẫu
  nhiên (người dùng tự chọn mã để tra cứu) — không đại diện cho universe.
  Vòng 2 nên chạy trên toàn bộ 501 mã (hoặc ít nhất universe liquid như
  `final_watchlist` dùng) để có N đủ lớn cho Newey-West/null-test, không chỉ
  16 mã này.
- **Prereg trước khi chạy** (bắt buộc theo `CLAUDE.md` mục 8): khóa trước
  target (forward return bao nhiêu ngày — khớp `mc_horizon_days=20` có sẵn
  trong config là lựa chọn tự nhiên), ngưỡng chấp nhận, universe, giai đoạn
  test — trước khi chạy bất kỳ so sánh nào, tránh lặp lại rủi ro tune-theo-
  kết-quả.
- **FDR** (mục 9): nếu test riêng từng sub-score + composite (9 test), phải
  báo q-value BH-FDR cạnh t-stat thô, đúng quy ước đã áp cho
  `FACTOR_RETEST_V2`/`WATCHLIST_VALIDATION`.

**Cái gì KHÔNG kiểm định được (giới hạn đã biết trước):**
- `simulation` sub-score (Monte Carlo target-hit probability) không thể
  IC-test theo kiểu cross-sectional thông thường — cần một test khác (vd.
  calibration: trong số các lần model dự báo "45% xác suất chạm target
  trước stop", thực tế có đúng ~45% các trường hợp lịch sử chạm target
  trước không?). Đây là bài toán calibration, không phải IC, cần thiết kế
  riêng.
- `alpha` sub-score's phần `backtest.profit_factor` phụ thuộc
  `data/signals/breakout_20d_trade_cards.parquet` chỉ tồn tại khi có tín
  hiệu breakout gần đây — không thể tính point-in-time đầy đủ cho mọi
  ngày/mọi mã, sẽ có N nhỏ hơn hẳn các sub-score khác.
- Survivorship bias (Gate #3, `PROJECT_STATE.md` mục 3) áp dụng y hệt cho
  bất kỳ backtest nào chạy trên `full_history_v2` — kết quả Vòng 2 sẽ kế
  thừa giới hạn này, không có cách bypass trong phạm vi dự án hiện tại.
- `market_regime` sub-score tính trên VNINDEX — chỉ có MỘT chuỗi benchmark,
  không có cross-sectional variation, nên không IC-test được theo cách
  thông thường như sub-score cấp-mã; cần đánh giá riêng kiểu time-series
  (vd. có dự báo drawdown thị trường không).

---

**File này audit-only.** Không có thay đổi nào tới `stock-decision-engine/src/`,
`config.yaml`, hay notebook trong vòng này.
