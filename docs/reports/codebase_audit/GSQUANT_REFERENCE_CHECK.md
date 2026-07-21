# GSQUANT_REFERENCE_CHECK — đối chiếu công thức với gs-quant (Goldman Sachs, Apache-2.0)

**Cập nhật 2026-07-21 — Finding #1 (ddof=0 vs ddof=1) RESOLVED.** 10 điểm
`ddof=0` đã đổi thành `ddof=1` (`src/risk/management.py` 6 điểm,
`stock-decision-engine/src/risk.py` 4 điểm), 2 implementation Sharpe đã hợp
nhất về `src.risk.management.sharpe_ratio` (một nguồn sự thật, đúng nguyên
tắc Gate #6). Commit: `d69f85e` (10 điểm ddof), `fe253e5` (hợp nhất Sharpe),
`fb8bce8` (test hồi quy). Đánh giá tác động ngược lên report đã công bố: xem
mục "Cập nhật 2026-07-21 — đánh giá tác động ngược (NV4)" cuối file. Finding
#2 (annualization hardcode) và #3 (percentile tie-handling) **CHƯA sửa**,
đúng RÀNG BUỘC vòng này (chỉ sửa ddof + hợp nhất Sharpe) — vẫn còn nguyên
trong danh sách chờ.

---

**Phạm vi**: khảo sát THUẦN, đối chiếu công thức. **Không cài gs-quant làm
dependency của dự án, không import bất kỳ hàm nào từ gs-quant vào production
code.** `requirements.txt` không đổi (xác nhận: `grep -i "gs.quant\|gs_quant"
requirements.txt` ra rỗng, cả trước và sau vòng này). `src/`, `scripts/`,
`stock-decision-engine/src/` không có `import gs_quant` nào (xác nhận:
`grep -rl "import gs_quant\|from gs_quant" src/ scripts/ stock-decision-engine/src/`
ra rỗng).

**Nguồn đọc**: `gs_quant` **1.2.60**, đã cài sẵn trong môi trường Python hệ
thống (`/opt/anaconda3/lib/python3.12/site-packages/gs_quant`) từ trước, không
do vòng này cài — chỉ đọc source trực tiếp bằng `Read`/`grep`, không chạy bất
kỳ hàm nào (nhiều hàm cần Marquee auth để chạy thật; đọc source/docstring
không cần auth).

**Đính chính con số ban đầu**: bối cảnh nêu "~23/36 file" trong
`gs_quant.timeseries` — kiểm đếm trực tiếp trên bản 1.2.60 đã cài: thư mục
này có **22 file `.py`** (không phải 36), trong đó **10 file có 0
`@plot_session_function`/`@plot_measure*` decorator VÀ 0 lệnh gọi
`GsDataApi`/`GsAssetApi`/`GsSession`** (`__init__.py`, `algebra.py`,
`analysis.py`, `backtesting.py`, `datetime.py`, `helper.py`,
`measure_registry.py`, `measures_helper.py`, `statistics.py`,
`technicals.py`), **1 file gần như hoàn toàn offline nhưng có 2/~15 hàm cần
session** (`econometrics.py` — xem NV1), và **11 file phụ thuộc Marquee rõ
ràng** (10 file `measures_*.py` + `tca.py`, mỗi file ≥1 hàm decorator
`@plot_session_function`/tương đương). Có thể phiên bản khác của gs-quant có
số file khác — số liệu trong báo cáo này lấy từ bản đã cài, ghi rõ để không
lẫn với số liệu chưa xác minh.

---

## NV1 — Hàm gs-quant offline liên quan đến vol/correlation/dispersion/drawdown/risk-adjusted-return/statistical-test

### `gs_quant.timeseries.econometrics` (offline trừ 2 hàm ghi chú riêng)

| Hàm | Chữ ký | Tóm tắt docstring | Offline? |
|---|---|---|---|
| `_get_annualization_factor` | `(x) -> AnnualizationFactor` | Suy ra hệ số annualize (252/52/26/12/4/1) từ khoảng cách ngày TRUNG BÌNH giữa các quan sát thật trong `x`; raise lỗi nếu không khớp bucket nào | Có |
| `annualize` | `(x: pd.Series) -> pd.Series` | `Y_t = X_t * sqrt(F)`, F suy ra tự động (bảng trên) | Có |
| `volatility` | `(x, w=Window(None,0), returns_type=SIMPLE) -> pd.Series` | `annualize(std(returns(x)))*100` — rolling annualized realized vol, trả về dạng %(20.0 = 20%) | Có |
| `correlation` | `(x, y, w=Window(None,0), type_=PRICES, returns_type=SIMPLE) -> pd.Series` | Rolling Pearson correlation của 2 chuỗi return (hoặc price, tự tính return) | Có |
| `beta` | `(x, b, w=Window(None,0), prices=True) -> pd.Series` | `Cov(R,S)/Var(S)` rolling, `ddof=1` tường minh cho cả cov và var | Có |
| `max_drawdown` | `(x, w=Window(None,0)) -> pd.Series` | `(x / rolling_max(x) - 1).rolling(w).min()` — âm nếu lỗ, vd -0.2 = drawdown 20% | Có |
| `returns` / `prices` | `(series, obs=1, type=SIMPLE/LOG/ABSOLUTE)` | Chuyển đổi price↔return, 3 kiểu (simple/log/absolute) | Có |
| `sharpe_ratio` | `(series, currency=USD, w, curve_type=PRICES, method=NAN) -> pd.Series` | `S_t = ((E_t/E_{t-w+1})^{365.25/(D_t-D_{t-w})}-1) / volatility(E,w)_t`, E = excess return so với risk-free rate | **Không** (`@plot_session_function` — cần fetch risk-free rate curve qua `GsDataApi`, xác nhận dòng 175/78-79) |
| `excess_returns_` | `(price_series, currency=USD) -> pd.Series` | `E_t = E_{t-1} + P_t - P_{t-1}*(1+R*ΔD/360)`, Actual/360 day count | **Không** (cùng lý do — cần risk-free rate curve thật) |

### `gs_quant.timeseries.statistics` (100% offline, 0 decorator session, 0 lệnh gọi API)

| Hàm | Chữ ký | Tóm tắt docstring | 
|---|---|---|
| `std` | `(x, w=Window(None,0)) -> pd.Series` | Rolling **unbiased estimator** của std: `sqrt(1/(N-1) * Σ(X_i-mean)²)` — tài liệu tự gọi rõ "unbiased estimator" |
| `var` | `(x, w) -> pd.Series` | Rolling variance, cùng công thức `N-1` |
| `cov` | `(x, y, w) -> pd.Series` | Rolling covariance, cùng công thức `N-1` |
| `exponential_std` | `(x, beta=0.75) -> pd.Series` | `x.ewm(alpha=1-beta, adjust=False).std()` — EWM std có debiasing factor (unbiased weighted variance) |
| `zscores` | `(x, w) -> pd.Series` | `(X_t - mean)/std` rolling, dùng `scipy.stats.zscore(..., ddof=1)` |
| `percentile` | `(x, n, w=None) -> pd.Series\|float` | Quantile thứ n (0-100) — `numpy.percentile` (toàn mẫu) hoặc `.rolling().quantile()` (có window) |
| `percentiles` | `(x, y=None, w) -> pd.Series` | **Percentile RANK** của y trong phân phối x, dùng `scipy.stats.percentileofscore(kind='mean')`: `(L + 0.5*k)/N*100%` với L=số giá trị nhỏ hơn hẳn, k=số giá trị bằng nhau |
| `winsorize` | `(x, limit=2.5, w) -> pd.Series` | Cắt giá trị ngoài `limit` độ lệch chuẩn so với rolling mean/std |

### `gs_quant.timeseries.technicals` (100% offline)

| Hàm | Tóm tắt |
|---|---|
| `exponential_volatility` | `annualize(exponential_std(returns(x), beta))*100` — EWM vol, annualized |
| `exponential_spread_volatility` | Như trên nhưng trên `diff(x)` (chênh lệch tuyệt đối) thay vì return |
| `bollinger_bands`, `relative_strength_index`, `macd`, `moving_average` | Chỉ báo kỹ thuật cổ điển — không trực tiếp so sánh được với `src/models/regime.py` (không cùng loại chỉ báo), liệt kê cho đầy đủ, không đào sâu |

### Không tìm thấy (bằng chứng phủ định, đã grep toàn bộ `gs_quant`)

- **`dispersion`**: `grep -rln "dispersion" gs_quant/timeseries/*.py` → rỗng. `grep -rn "def dispersion" gs_quant/` (toàn package) → rỗng. Không có hàm dispersion nào trong gs-quant để đối chiếu.
- **`regime`**: `grep -rln "regime" gs_quant/timeseries/*.py` → rỗng. gs-quant KHÔNG có khái niệm market-regime classification — chỉ cung cấp các primitive (vol/corr/beta/drawdown), không có tầng phân loại trạng thái thị trường nào để so sánh trực tiếp với `src/models/regime.py::classify_market_regime`.
- **Statistical hypothesis test** (t-test, ADF stationarity, p-value framework): `grep -rln "ttest\|adfuller\|stationarity\|p_value\|pvalue\|hypothesis" gs_quant/timeseries/*.py` → rỗng. gs-quant chỉ có thống kê mô tả (zscore/percentile/winsorize), không có khung kiểm định giả thuyết chính thức nào — xác nhận `MARKET_REGIME_STUDY_REPORT.md` dùng `scipy.stats` trực tiếp + block-bootstrap tự viết là đúng hướng, không bỏ lỡ công cụ có sẵn nào từ gs-quant cho việc đó.

---

## NV2 — Đối chiếu với công thức đang dùng trong dự án

### Bảng đối chiếu

| Chỉ số | gs-quant | Dự án | Khớp? |
|---|---|---|---|
| `max_drawdown` | `x/rolling_max(x) - 1`, âm = lỗ | `src/analytics/drawdown.py::calculate_drawdown`: `(equity-running_max)/running_max` (đại số tương đương); `src/risk/management.py::rolling_drawdown`: `nav/running_peak - 1` (giống hệt) | **Khớp** |
| `correlation`/`beta` rolling mechanics | Rolling trên return, dropna trước khi corr, không look-ahead | `src/analytics/advanced.py::compute_rolling_beta`/correlation functions dùng `.rolling().cov()`/`.var()`, cùng cơ chế | **Khớp** |
| Realized vol (feature layer) | `annualize(std(returns))*100`, `std` dùng **ddof=1** | `src/features/volatility.py::add_realized_volatility`: `.rolling(w).std()*sqrt(252)` — pandas mặc định **ddof=1** | **Khớp** (khác đơn vị: dự án trả fraction, gs-quant trả %×100 — quy ước hiển thị, không phải lỗi) |
| EWM vol | `annualize(exponential_std(returns,beta))*100`, EWM std có debiasing factor (pandas `.ewm().std()` mặc định `bias=False`) | `src/features/volatility.py::add_ewma_volatility`: `.ewm(span=span, adjust=False).std()*sqrt(252)` — cùng cơ chế pandas, tham số hóa khác (`span` vs `beta`, quan hệ toán học `beta=(span-1)/(span+1)`) | **Khớp** |
| Annualization factor | **Tự suy ra** từ khoảng cách ngày trung bình của chuỗi input, raise lỗi nếu không khớp bucket nào | **Hardcode cố định** `sqrt(252)` (hoặc `periods_per_year=252` mặc định) ở MỌI nơi — 12 file dùng `252`/`sqrt(252)` trực tiếp, 0 file có logic suy luận tần suất | **Khác convention** — xem Finding #2 |
| `std`/`var`/`cov`/`beta` (risk/portfolio layer) | **`ddof=1`** tường minh, tài liệu tự gọi "unbiased estimator" | `src/risk/management.py`: **`ddof=0`** tường minh ở 6 vị trí (`annualized_volatility`, `sharpe_ratio`, `rolling_sharpe_series`, `expanding_sharpe_series`, `sharpe_stability_report`, guard-check trong `portfolio_beta`); `stock-decision-engine/src/risk.py`: **`ddof=0`** ở 4 vị trí; `scripts/build_portfolio_stack.py:98`: **`ddof=0`** | **Khác convention, KHÔNG NHẤT QUÁN nội bộ** — xem Finding #1 |
| Percentile rank (tie-handling) | `scipy.stats.percentileofscore(kind='mean')`: `(L + 0.5k)/N` | `src/features/volatility.py::add_volatility_percentile`: `pd.Series(arr).rank(pct=True)` (pandas `method='average'` mặc định): `(L + k/2 + 0.5)/N` | **Khác công thức, lệch hằng số nhỏ** — xem Finding #3 |

### Finding #1 — `ddof=0` vs `ddof=1`: không nhất quán NỘI BỘ dự án, khác convention gs-quant

**Bằng chứng đầy đủ** (`grep -rn "ddof" src/ scripts/ stock-decision-engine/src/`):

| File:dòng | `ddof` | Dùng cho |
|---|---|---|
| `src/features/volatility.py`, `src/features/liquidity.py`, `src/features/distribution.py` | `1` (mặc định pandas, không truyền tham số) | `realized_vol_20d`, `value_zscore_20d`, `dist_*` |
| `src/simulation/var_cvar.py:38` | `1` | parametric VaR std |
| `src/validation/stress_test.py:27` | `1` | market variance cho beta stress |
| `src/risk/management.py:56,64,79,94,122` | `0` | `annualized_volatility`, `sharpe_ratio`, `rolling_sharpe_series`, `expanding_sharpe_series`, `sharpe_stability_report` |
| `src/risk/management.py:183` | `1` | `portfolio_beta`'s denominator (dòng 180 dùng `ddof=0` chỉ để check bằng-0 — không ảnh hưởng số beta thật vì beta = cov/var là tỷ số bất biến với ddof, cov và var đều ddof=1 ở đây) |
| `scripts/build_portfolio_stack.py:98` | `0` | inverse-volatility weighting (fallback khi thiếu `atr_pct_14`) |
| `scripts/main_visual_dashboard.py:37` | `1` | `calculate_sharpe_ratio` — **implementation Sharpe THỨ HAI, độc lập với `src/risk/management.py`, dùng ddof KHÁC** |
| `stock-decision-engine/src/risk.py:14,41,52,53` | `0` | `downside_deviation`, portfolio vol, `information_ratio`, `tracking_error` |
| `stock-decision-engine/src/features.py:158` | `0` | `downside_deviation` (bản trùng lặp khác) |

**Mức độ ảnh hưởng thực tế**: hệ số lệch giữa `ddof=0` và `ddof=1` là
`sqrt(N/(N-1))` — nhỏ với N lớn, đáng kể hơn với N nhỏ:

| N (số quan sát) | Hệ số phóng đại Sharpe/thu hẹp vol khi dùng `ddof=0` |
|---|---|
| 252 (1 năm, full-sample `sharpe_ratio`/`annualized_volatility`) | ×1.002 (+0.2%) |
| 63 (`rolling_sharpe_series` mặc định) | ×1.008 (+0.8%) |
| 21 (`expanding_sharpe_series`'s `min_periods` mặc định, đầu chuỗi) | ×1.025 (+2.5%) |

**Chiều lệch nhất quán, không ngẫu nhiên**: `ddof=0` LUÔN cho std/vol NHỎ
HƠN `ddof=1` → Sharpe/information ratio tính bằng `ddof=0` LUÔN bị **phóng
đại nhẹ** so với quy ước "unbiased" mà gs-quant dùng và chính
`src/features/volatility.py` của dự án cũng đang dùng (qua mặc định pandas).
Đây không phải khác biệt ngẫu nhiên giữa các lần chạy — là một lựa chọn công
thức có thể tái lập, chỉ là KHÔNG THỐNG NHẤT giữa tầng feature-engineering
(luôn `ddof=1`) và tầng risk/portfolio-metrics (đa số `ddof=0`, trừ
`var_cvar.py`/`stress_test.py` dùng `ddof=1`) — và ngay trong tầng
risk/portfolio-metrics cũng có 2 implementation Sharpe độc lập
(`src/risk/management.py` vs `scripts/main_visual_dashboard.py`) dùng 2
`ddof` khác nhau, sẽ cho ra 2 con số Sharpe hơi khác nhau cho CÙNG một chuỗi
return nếu ai đó so sánh trực tiếp.

### Finding #2 — Annualization factor: hardcode vs suy luận tự động

gs-quant's `_get_annualization_factor` đo khoảng cách ngày trung bình thật
của chuỗi input và tự chọn 252/52/26/12/4/1, raise `MqValueError` rõ ràng
nếu không khớp bucket nào (khoảng cách "lạ", vd dữ liệu có lỗ hổng lớn).
Toàn bộ dự án (12 file, xác nhận qua `grep -rc "sqrt(252)\|np\.sqrt(252)\|\*
252\b"`) hardcode `252`/`sqrt(252)` trực tiếp hoặc qua tham số mặc định
`periods_per_year=252`, không có logic kiểm tra/suy luận tần suất dữ liệu
đầu vào nào. **Không phải lỗi cho cách dùng hiện tại** (toàn bộ dữ liệu dự
án là daily VN stock, tần suất cố định biết trước) — nhưng khác biệt về
tính phòng vệ: nếu một ngày nào đó một script vô tình nhận dữ liệu đã
resample (weekly/monthly) mà quên đổi `periods_per_year`, dự án sẽ annualize
SAI trong im lặng (không có gì báo lỗi), trong khi cách gs-quant làm sẽ tự
điều chỉnh đúng hoặc raise lỗi rõ ràng.

### Finding #3 — Percentile rank tie-handling (rất nhỏ, chỉ ghi nhận)

`add_volatility_percentile` (`src/features/volatility.py`) dùng
`pd.Series(arr).rank(pct=True).iloc[-1]` — pandas `rank(method='average')`
mặc định. Với giá trị bị trùng (k bản sao, L giá trị nhỏ hơn hẳn), công thức
này cho `(L + (k+1)/2)/N`. gs-quant's `percentiles()` dùng
`scipy.stats.percentileofscore(kind='mean')`: `(L + k/2)/N`. Hai công thức
lệch nhau đúng **0.5/N** — với `window=252` (dùng trong
`add_volatility_percentile`), lệch ~0.002 (0.2 điểm phần trăm) — **không có
ý nghĩa thực tế**, chỉ ghi nhận vì đúng loại khác biệt "cách tính rolling
khác" mà NV2 yêu cầu tìm, không phải một lỗi đáng sửa.

### Không tìm thấy khác biệt (khớp hoàn toàn)

- `max_drawdown`: công thức đại số tương đương chính xác ở cả 2 nơi trong dự
  án (`src/analytics/drawdown.py`, `src/risk/management.py`) so với
  `econometrics.py::max_drawdown`.
- Rolling correlation/beta mechanics: cùng cách dùng pandas `.rolling().cov()`/
  `.var()`/`.corr()`, cùng quy ước return-from-price, không look-ahead ở cả
  hai bên.
- `src/models/regime.py` (đối tượng chính NV2 nêu tên): **không tính
  std/var/cov trực tiếp** — chỉ tiêu thụ `volatility_percentile` (từ
  `volatility.py`, đã khớp gs-quant), `pct_above_ma50`/`advance_decline_ratio`
  (tỷ lệ đơn giản, không có ddof), và `index_drawdown_pct` (khớp gs-quant).
  **Không tìm thấy khác biệt công thức nào trong chính `regime.py`** — rủi ro
  `ddof` nằm ở tầng risk/portfolio-metrics (Finding #1), không phải ở
  `regime.py`.

---

## Đề xuất (CHƯA sửa gì trong vòng này)

Đúng RÀNG BUỘC — chỉ liệt kê, không tự sửa. Ưu tiên theo mức ảnh hưởng:

1. **Finding #1 (ddof)** — đáng sửa nhất, có bằng chứng rõ nhất, ảnh hưởng
   trực tiếp tới con số Sharpe/vol hiển thị cho người dùng. Đề xuất: thống
   nhất về `ddof=1` (khớp gs-quant, khớp tầng feature-engineering của chính
   dự án, khớp `var_cvar.py`/`stress_test.py`/`main_visual_dashboard.py` đã
   sẵn dùng `ddof=1`) tại `src/risk/management.py` (6 vị trí),
   `stock-decision-engine/src/risk.py` (4 vị trí),
   `stock-decision-engine/src/features.py:158`,
   `scripts/build_portfolio_stack.py:98` — **RESOLVED cho `src/risk/management.py`
   và `stock-decision-engine/src/risk.py`** (commit `d69f85e`); đánh giá tác
   động ngược lên số đã công bố xem mục "Cập nhật 2026-07-21 — đánh giá tác
   động ngược (NV4)" cuối file. `src/analytics/entropy.py:15` và
   `scripts/build_portfolio_stack.py:98` **vẫn còn `ddof=0`, chưa sửa** —
   ngoài phạm vi vòng vừa rồi (chỉ giới hạn 2 file/10 điểm đã nêu), còn trong
   danh sách chờ.
2. **Finding #2 (annualization hardcode)** — chi phí thấp nếu muốn thêm một
   assertion/warning khi tần suất dữ liệu đầu vào không phải daily, nhưng
   không cấp bách (dự án luôn dùng daily data).
3. **Finding #3 (percentile tie-handling)** — không đáng sửa, chênh lệch
   không có ý nghĩa thực tế ở window hiện dùng.

**Không đề xuất**: import bất kỳ hàm nào từ gs-quant, hoặc thêm gs-quant vào
`requirements.txt` — nếu muốn áp dụng Finding #1/#2, viết lại bằng tay theo
convention hiện có của repo (không phải copy code gs-quant), đúng RÀNG BUỘC.

---

## Cập nhật 2026-07-21 — chuẩn hóa ddof=1 + đánh giá tác động ngược (NV4)

### Sửa gì (NV1-NV3, tóm tắt — chi tiết trong message từng commit)

- **NV1** (`d69f85e`): 10 điểm `ddof=0`→`ddof=1`, xác nhận lại bằng grep tươi
  trước khi sửa (không tin report suông) — khớp chính xác với bảng Finding #1
  gốc, không có điểm nào lệch giữa lúc audit và lúc sửa.
- **NV2** (`fe253e5`): `scripts/main_visual_dashboard.py::calculate_sharpe_ratio`
  (implementation Sharpe độc lập thứ hai) đã gỡ bỏ, thay bằng import trực
  tiếp `sharpe_ratio` từ `src.risk.management` — xác nhận đại số 2 công thức
  đã tương đương từ trước (trừ hằng số risk-free không đổi std; `252/sqrt(252)
  = sqrt(252)`), giờ cho ra CÙNG một object hàm, không chỉ cùng kết quả.
- **NV3** (`fb8bce8`): `tests/test_ddof_consistency.py`, 9 test — AST-scan 2
  file đã sửa (chặn tái xuất hiện `ddof=0`), snapshot test so khớp công thức
  unbiased qua numpy (sai số <1e-9), test xác nhận `ddof` THẬT SỰ đổi số (không
  phải no-op), test xác nhận 2 nơi gọi Sharpe giờ là CÙNG MỘT function object.

### NV4 — đánh giá tác động ngược lên 3 report đã nêu

**Phương pháp**: truy theo import chain thật (không suy đoán) từ mỗi report
tới `src.risk.management`/`stock-decision-engine/src/risk.py`, bằng `grep`
trực tiếp — không chạy lại backtest nào.

| Report | Có dùng module bị ảnh hưởng không? | Bằng chứng |
|---|---|---|
| `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` | **Không** | `grep -n "sharpe\|volatility\|\.std("` → chỉ 1 dòng nhắc tên factor `volatility_percentile` (từ `src/features/volatility.py`, tầng feature-engineering, KHÔNG phải `src/risk/management.py`) — không có phép tính Sharpe/vol portfolio nào trong report này |
| `docs/reports/scoring/SCORE_V2_REPORT.md` | **Gián tiếp, qua trích dẫn** | Report này không tự tính Sharpe/DSR — trích dẫn nguyên số từ `ROBUSTNESS_REPORT.md` (`[−0.59, +1.32]`) — cùng kết luận với dòng dưới |
| `docs/reports/scoring/ROBUSTNESS_REPORT.md` | **Có, xác nhận qua chuỗi import thật** | `Sharpe(năm hoá)=0.32` (mục 5, N=1,120 ngày) sinh bởi `scratch/dsr_and_bootstrap_v2.py` → gọi `src.backtest.run_portfolio_backtest` → `src/backtest/portfolio_backtest.py:464` gọi `calculate_sharpe(...)` → import từ `src/validation/metrics.py:19` → chính là `src.risk.management.sharpe_ratio` (hàm đã sửa NV1) |

**Độ lệch định lượng cho `ROBUSTNESS_REPORT.md`**: hệ số lệch giữa số CŨ
(`ddof=0`, đã công bố) và số ĐÚNG (`ddof=1`, sau khi sửa) là
`sqrt(N/(N-1))`. Với N=1,120 (đúng N đã ghi trong report):
`sqrt(1120/1119) ≈ 1.00045` — **lệch +0.045%**, tức Sharpe=0.32 đã công bố
trước đây cao hơn số đúng khoảng 0.00014 — **dưới độ chính xác hiển thị của
report (3 chữ số thập phân, "0.319"/"0.32")**. Đúng dự đoán trong
`GSQUANT_REFERENCE_CHECK.md` gốc ("N lớn, sai lệch <1%"). **Không chạy lại
backtest** (đúng NV4) — kết luận dựa trên tính hệ số lệch trực tiếp, không
cần recompute.

**Không đổi kết luận nào của `ROBUSTNESS_REPORT.md`**:
- **DSR=0.0083** — tính ĐỘC LẬP trong `scratch/dsr_and_bootstrap_v2.py:48`
  (`sr_hat = daily_returns.mean() / daily_returns.std(ddof=1)`) — **đã dùng
  `ddof=1` từ trước**, không đi qua `src.risk.management`, không bị ảnh hưởng
  bởi vòng sửa này chút nào.
- **Bootstrap CI `[−0.59, +1.32]`** — tính từ `block_bootstrap_returns`
  (`src/simulation/bootstrap.py`, không sửa) + `sims.std(axis=1)` tại
  `scratch/dsr_and_bootstrap_v2.py:125` — đây là **numpy array**, không phải
  pandas Series, nên `.std()` không tham số mặc định `ddof=0` (khác pandas!)
  — một điểm `ddof=0` khác, **KHÔNG nằm trong 10 điểm đã sửa vòng này** (file
  không được nêu tên trong NV1), **không do vòng này gây ra, cũng không được
  vòng này sửa**. Ghi vào danh sách chờ bên dưới vì phát hiện được trong lúc
  đánh giá tác động, không phải vì thuộc phạm vi sửa.

**Cửa sổ ngắn (N<63) làm căn cứ quyết định — không tìm thấy trường hợp nào
trong 3 report đã nêu**: `rolling_sharpe_series`/`expanding_sharpe_series`/
`sharpe_stability_report` (các hàm cửa sổ ngắn N=21/63 trong
`src/risk/management.py`) chỉ được gọi nội bộ bởi `build_portfolio_risk_report`,
được `scripts/build_portfolio_stack.py` gọi — nhưng **không có field nào từ
đó** (`sharpe_stability_score`, `rolling_sharpe_latest`, `expanding_sharpe_latest`)
**xuất hiện trong bất kỳ file `docs/` nào** (`grep -rn` toàn bộ `docs/` ra
rỗng) — xác nhận các số cửa sổ ngắn này chưa từng được trích dẫn làm căn cứ
quyết định ở đâu. Không cần gắn cờ.

**Adjacent, chưa sửa (phát hiện mới trong lúc NV4, không thuộc phạm vi vòng
này)**: `scratch/dsr_and_bootstrap_v2.py:125` (`sims.std(axis=1)`, numpy
mảng, mặc định `ddof=0`) — trực tiếp sinh ra khoảng CI Sharpe đã công bố
`[−0.59, +1.32]` trong `ROBUSTNESS_REPORT.md`. Vì đây là numpy (không phải
pandas), lệch số tiềm năng cần tính riêng (không giống hệ số `sqrt(N/(N-1))`
ở trên — block bootstrap có N khác, cấu trúc khác) — **chưa định lượng**,
cần một round riêng nếu muốn theo đuổi.

Commit tài liệu này: xem `PUSH_REVIEW.md` round tương ứng.

---

*Khảo sát 2026-07-21. Không sửa dòng logic nào trong `src/`/`scripts/`/
`stock-decision-engine/`. Không thêm gs-quant vào `requirements.txt`. Không
import gs_quant ở bất kỳ đâu trong production code — xác nhận bằng grep ở
đầu báo cáo.*
