# GSQUANT_REFERENCE_CHECK — đối chiếu công thức với gs-quant (Goldman Sachs, Apache-2.0)

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
   `scripts/build_portfolio_stack.py:98` — cần một prereg/round riêng để đo
   xem việc đổi ddof có làm lệch số nào đã báo cáo trước đây không (vd. các
   con số Sharpe trong `docs/reports/scoring/ROBUSTNESS_REPORT.md` có dùng qua
   `src/risk/management.py` không — chưa kiểm tra trong vòng này).
2. **Finding #2 (annualization hardcode)** — chi phí thấp nếu muốn thêm một
   assertion/warning khi tần suất dữ liệu đầu vào không phải daily, nhưng
   không cấp bách (dự án luôn dùng daily data).
3. **Finding #3 (percentile tie-handling)** — không đáng sửa, chênh lệch
   không có ý nghĩa thực tế ở window hiện dùng.

**Không đề xuất**: import bất kỳ hàm nào từ gs-quant, hoặc thêm gs-quant vào
`requirements.txt` — nếu muốn áp dụng Finding #1/#2, viết lại bằng tay theo
convention hiện có của repo (không phải copy code gs-quant), đúng RÀNG BUỘC.

---

*Khảo sát 2026-07-21. Không sửa dòng logic nào trong `src/`/`scripts/`/
`stock-decision-engine/`. Không thêm gs-quant vào `requirements.txt`. Không
import gs_quant ở bất kỳ đâu trong production code — xác nhận bằng grep ở
đầu báo cáo.*
