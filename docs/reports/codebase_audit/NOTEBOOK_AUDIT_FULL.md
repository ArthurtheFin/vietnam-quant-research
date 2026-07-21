# NOTEBOOK_AUDIT_FULL — audit toàn bộ notebook còn lại (cả 2 dự án)

**Phạm vi**: audit thuần (không sửa logic, không backtest mới, không xóa gì)
cho **13 notebook còn lại** sau `notebooks/02_market_research/` (6 file, đã
audit riêng trong `MARKET_REGIME_AUDIT.md`, loại khỏi vòng này theo đúng yêu
cầu) — 12 notebook trong dự án chính + 1 notebook trong
`stock-decision-engine/`. Phương pháp: kiểm kê → chạy thật top-to-bottom
trong **sandbox cô lập** (bản rsync đầy đủ của repo, KHÔNG chạy trực tiếp ở
thư mục gốc — bài học từ sự cố ghi-đè production trong `MARKET_REGIME_AUDIT.md`)
→ đối chiếu chữ ký hàm với `src/` hiện tại → phân loại.

**CẢNH BÁO NGHIÊM TRỌNG phát hiện giữa chừng, đã báo ngay cho người dùng
trước khi tiếp tục** (xem mục "Phát hiện nguy cơ ghi-đè-production" bên
dưới) — người dùng xác nhận tiếp tục quét sau khi ghi nhận.

---

## Phương pháp cô lập (rút kinh nghiệm từ sự cố `MARKET_REGIME_AUDIT.md`)

`MARKET_REGIME_AUDIT.md` từng vô tình ghi đè 3 file production vì chạy
`nbconvert` trực tiếp tại thư mục gốc thật. Vòng này: mọi notebook được
`rsync -a` toàn bộ repo (code + `data/`, trừ `.git/`) vào một thư mục sandbox
biệt lập trong scratch trước, rồi chạy `jupyter nbconvert --execute --inplace`
**bên trong sandbox đó**, không bao giờ trỏ vào thư mục gốc thật. Đã xác nhận
bằng cách đối chiếu mtime/`git status`/`git diff` của thư mục gốc thật
TRƯỚC và SAU mỗi lần chạy — không file nào ở thư mục gốc thật bị đổi trong
suốt vòng audit này (kể cả 2 lần notebook cố ý ghi đè `clean_daily_ohlcv.parquet`
— tác động chỉ nằm trong sandbox).

**Lưu ý phương pháp quan trọng**: khi `nbconvert` gặp lỗi/timeout không bắt
(`CellExecutionError`/`CellTimeoutError`), nó **không ghi file `.ipynb` output
ra đĩa** — file trên đĩa vẫn giữ nguyên nội dung/output CŨ từ lần chạy thật
gần nhất (thường là của người dùng, ở thư mục gốc thật, trước khi được
commit vào git). Hai lần đầu chạy `07_breakout_research.ipynb` (timeout 600s)
và `12_meta_ranking_optimization.ipynb` (lỗi `ModuleNotFoundError`) đã đọc
nhầm output CŨ này là "output vừa chạy" — phải luôn đối chiếu traceback
trong log terminal thật của `nbconvert`, không chỉ đọc lại `.ipynb` sau khi
chạy xong.

---

## Phát hiện nguy cơ ghi-đè-production (đã báo ngay, người dùng xác nhận tiếp tục quét)

2 notebook trong `notebooks/00_archive/` ghi thẳng vào
`data/processed/clean_daily_ohlcv.parquet` — 1 trong 3 path chính thức
(`OFFICIAL_CLEAN_OHLCV_PATH`, `src/data/dataset_config.py`) — **hoàn toàn
không qua `guard_production_write()`**, giống hệt lỗ hổng đã sửa cho
notebook 06 nhưng **chưa từng được mở rộng ra ngoài `02_market_research/`**:

| Notebook | Dòng ghi | Vấn đề |
|---|---|---|
| `00_archive/02_fetch_daily_ohlcv.ipynb:327` | `save_parquet(daily, "data/processed/clean_daily_ohlcv.parquet")` | Ghi thẳng dữ liệu vừa fetch, **chưa qua `standardize_ohlcv`/`validate_ohlcv`** — tệ hơn cả bug notebook 06 vì không hề validate |
| `00_archive/03_clean_validate_data.ipynb:30` | `save_parquet(clean, "data/processed/clean_daily_ohlcv.parquet")` | Đọc từ `data/raw/daily_ohlcv/` — thư mục này hiện **RỖNG HOÀN TOÀN** (0 file, đã bị `full_history_v2` thay thế) → notebook "chạy thành công" (exit 0, không lỗi) nhưng tạo ra DataFrame **rỗng (0,0)** → sẽ ghi đè production bằng **file rỗng**, không một exception nào cảnh báo |

Xác nhận qua chạy thật trong sandbox: cả 2 trường hợp trên chỉ ảnh hưởng bản
sao sandbox (đã kill tiến trình `02_fetch_daily_ohlcv` trước khi tới bước
ghi vì nó gọi SSI API sống không giới hạn cho toàn thị trường — chi phí/rủi
ro không cần thiết cho việc audit; xác nhận signature vẫn khớp
`src/data/fetch_daily.py`/`ssi_client.py` hiện tại qua đọc code tĩnh thay vì
chạy đến cùng). `03_clean_validate_data.ipynb` chạy hết nhưng xác nhận
output `(0, 0)` — **không một real project file nào bị đụng** (đối chiếu
`cmp`/mtime/`git status` thư mục gốc thật trước/sau, khớp 100%).

**Phạm vi guard hiện tại**: `grep -rl guard_production_write` toàn repo chỉ
ra 3 kết quả — `src/data/production_guard.py` (định nghĩa),
`notebooks/02_market_research/05_volatility_regime.ipynb`,
`notebooks/02_market_research/06_market_regime.ipynb`. **0 trong 13 notebook
của vòng này** gọi guard. Ngoài 2 notebook ở trên (ghi thẳng vào 1 trong 3
path được bảo vệ), một lớp rủi ro thứ hai (thấp hơn) cũng được phát hiện:
`notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb` ghi thẳng
vào `data/signals/alpha_scores.parquet` — **không nằm trong 3 path được
`production_guard.py` bảo vệ**, nhưng vẫn là file production thật, được đọc
bởi `scripts/run_daily_pipeline.py`, `scripts/run_meta_ranking.py`,
`src/screening/final_watchlist.py` (`_merge_latest_alpha`),
`src/analytics/meta_ranking.py`, `src/validation/freshness_check.py`. Rủi ro
thấp hơn 2 case trên vì notebook này gọi đúng hàm sản xuất hiện tại
(`calculate_alpha_scores`, không phải bản logic cũ) — nội dung ghi ra đúng,
chỉ thiếu lineage/nằm ngoài orchestration chính thức của pipeline.

**Đề xuất chưa làm** (để vòng sau quyết định, đúng ràng buộc audit-thuần):
mở rộng `PROTECTED_PATHS` hoặc phạm vi review sang toàn bộ notebook có
`save_parquet`/`save_csv_atomic` vào đường dẫn production (không chỉ 3 path
gốc), đặc biệt 2 notebook `00_archive` ở trên — dù đã "đóng băng", chúng vẫn
là file `.ipynb` thật, ai mở và chạy tay không qua sandbox sẽ ghi đè
`clean_daily_ohlcv.parquet` bằng dữ liệu sai/rỗng ngay lập tức.

---

## NV1 — Kiểm kê toàn bộ (cả 2 dự án)

| # | Notebook | Sửa lần cuối (git) | Đã audit trước? |
|---|---|---|---|
| — | `notebooks/02_market_research/*.ipynb` (6 file) | 2026-07-21 | **CÓ** — `MARKET_REGIME_AUDIT.md`, loại khỏi vòng này |
| 1 | `notebooks/00_archive/00_project_overview.ipynb` | 2026-07-01 | Không |
| 2 | `notebooks/00_archive/02_fetch_daily_ohlcv.ipynb` | 2026-07-01 | Không |
| 3 | `notebooks/00_archive/03_clean_validate_data.ipynb` | 2026-07-01 | Không |
| 4 | `notebooks/00_archive/11_trade_card_generation.ipynb` | 2026-07-01 | Không |
| 5 | `notebooks/00_archive/17_live_watchlist_dashboard.ipynb` | 2026-07-01 | Không |
| 6 | `notebooks/00_archive/18_client_watchlist_report.ipynb` | 2026-07-01 | Không |
| 7 | `notebooks/01_data_pipeline/01_validate_environment.ipynb` | 2026-07-02 | Không |
| 8 | `notebooks/03_alpha_signals/07_breakout_research.ipynb` | 2026-07-01 | Không |
| 9 | `notebooks/03_alpha_signals/09_stealth_accumulation_screen.ipynb` | 2026-07-01 | Không |
| 10 | `notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb` | 2026-07-17 (thêm banner OUTDATED) | Không (banner tự cảnh báo, chưa audit sâu) |
| 11 | `notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb` | 2026-07-01 | Không |
| 12 | `notebooks/04_watchlist_portfolio/15_risk_management.ipynb` | 2026-07-01 | Không |
| 13 | `notebooks/04_watchlist_portfolio/16_capital_allocation.ipynb` | 2026-07-01 | Không |
| 14 | `notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb` | 2026-07-17 (thêm banner OUTDATED) | Không |
| 15 | `notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb` | 2026-07-17 (thêm banner OUTDATED) | Không |
| 16 | `notebooks/05_client_report/01_client_market_report.ipynb` | 2026-07-02 | Không |
| 17 | `stock-decision-engine/notebooks/stock_buy_decision.ipynb` | 2026-07-17 | Một phần — `AUDIT_SDE_REPORT.md`/`SDE_SCORING_REPORT.md` đã audit toàn bộ engine (3 vòng), notebook chỉ là entry point mỏng gọi engine đó |

13 notebook thực sự nằm trong phạm vi vòng này (hàng 1-6, 8-17 ở trên, không
tính hàng "—" là 02_market_research đã loại trừ).

---

## NV1b — Chạy top-to-bottom thật (sandbox cô lập) — kết quả

| Notebook | Chạy được? | Chi tiết |
|---|---|---|
| `00_project_overview.ipynb` | **Có**, 0 lỗi | Read-only, in tổng quan dự án |
| `02_fetch_daily_ohlcv.ipynb` | **Không chạy hết** (chủ động dừng) | Gọi SSI API sống không giới hạn cho toàn thị trường (`fetch_mode="full_market_light"`, `max_symbols=None`) — chi phí/rủi ro không cần thiết cho audit; đã kill tiến trình. Xác nhận signature qua đọc code tĩnh: khớp `src/data/fetch_daily.py::update_symbol_history`/`src/data/ssi_client.py::SSIDataClient` hiện tại (không lỗi tham số) |
| `03_clean_validate_data.ipynb` | **"Có"** (exit 0) nhưng output sai | Đọc `data/raw/daily_ohlcv/` — RỖNG (0 file) → DataFrame (0, 0) |
| `11_trade_card_generation.ipynb` | **Có**, 0 lỗi | Ghi `data/signals/breakout_20d_trade_cards.parquet` (không phải path bảo vệ) |
| `17_live_watchlist_dashboard.ipynb` | **KHÔNG** | `AttributeError: 'float' object has no attribute 'abs'` ở cell "Build Capital Candidates" — `capital_candidates.get("forward_return_20d", np.nan)` trả về scalar (không phải Series) khi cột này không tồn tại trong schema hiện tại, `.abs()` trên scalar `float` lỗi |
| `18_client_watchlist_report.ipynb` | **Có**, 0 lỗi | Read-mostly, build report thị trường |
| `01_validate_environment.ipynb` | **Có**, 0 lỗi | Gọi SSI API thật nhưng nhỏ/có giới hạn (1 mã, 1 tháng dữ liệu) — sanity check hợp lý |
| `07_breakout_research.ipynb` | **Có**, 0 lỗi (lần 2) | Lần 1 timeout ở 600s (mặc định `nbconvert`) — cell `run_breakout_research` (grid 15 tổ hợp stop-loss × ATR trên toàn universe) mất **~18 phút thật**. Lần 2 với timeout 1800s: hoàn tất sạch |
| `09_stealth_accumulation_screen.ipynb` | **Có**, 0 lỗi | Full-market scan + backtest, ~vài phút |
| `12_meta_ranking_optimization.ipynb` | **KHÔNG** | `ModuleNotFoundError: No module named 'src'` — xem NV3 |
| `14_portfolio_construction.ipynb` | **Có**, 0 lỗi | Monte Carlo 10.000 mô phỏng + tối ưu Scipy |
| `15_risk_management.ipynb` | **Có**, 0 lỗi | |
| `16_capital_allocation.ipynb` | **Có**, 0 lỗi | Phụ thuộc `data/signals/risk_overlay_weights.parquet` (output của notebook 15) — file này đã có sẵn từ lần chạy thật trước đó nên không chặn; là phụ thuộc thứ tự có ghi chú rõ trong code (`# Load risk overlay weights from Notebook 15`), không phải state ẩn bất ngờ |
| `19_validation_and_stress_test.ipynb` | **KHÔNG** | Timeout ngay cả ở 1800s (30 phút) — xem NV3 |
| `20_portfolio_backtester.ipynb` | **KHÔNG** | `ValueError` từ `run_portfolio_backtest` — xem NV3 |
| `01_client_market_report.ipynb` | **Có**, 0 lỗi | Hoàn toàn read-only (load output đã có, hiển thị report) |
| `stock_buy_decision.ipynb` (SDE) | **Có**, 0 lỗi | Ghi trong phạm vi riêng `stock-decision-engine/outputs/`, không đụng path production dự án chính |

---

## NV2 — Phân loại theo chuẩn dự án

| Notebook | Phân loại | Bằng chứng |
|---|---|---|
| `00_project_overview.ipynb` | **ARCHIVE / DEAD** (đề xuất, không xóa) | Đã ở `00_archive/`, chạy sạch nhưng chỉ là overview tĩnh, đã có `notebooks/README.md` thay thế theo `notebook_inventory.md` |
| `02_fetch_daily_ohlcv.ipynb` | **DEAD + rủi ro ghi-đè-production nghiêm trọng** | Superseded bởi `scripts/update_prices_daily.py` (dùng `get_daily_ohlc` trực tiếp, không qua đường chunked `fetch_daily.py` này); nếu chạy tay sẽ ghi dữ liệu chưa validate đè `clean_daily_ohlcv.parquet` |
| `03_clean_validate_data.ipynb` | **INCORRECT + rủi ro ghi-đè-production nghiêm trọng** | Nguồn đọc (`data/raw/daily_ohlcv/`) rỗng hoàn toàn kể từ khi `full_history_v2` thay thế — chạy "thành công" nhưng âm thầm tạo dữ liệu rỗng, không cảnh báo |
| `11_trade_card_generation.ipynb` | **CONVERTED_TO_SCRIPT** (xác nhận lại) | `scripts/generate_trade_cards.py` tồn tại và đã thay thế, notebook vẫn chạy đúng nhưng dư thừa |
| `17_live_watchlist_dashboard.ipynb` | **BROKEN** | `AttributeError` xác nhận qua chạy thật — schema hiện tại thiếu cột `forward_return_20d` mà notebook giả định luôn tồn tại |
| `18_client_watchlist_report.ipynb` | **ARCHIVE** (superseded) | Thay thế bởi `notebooks/05_client_report/01_client_market_report.ipynb` theo đúng `PROJECT_HANDBOOK.md` mục 2.8 hiện tại |
| `01_validate_environment.ipynb` | **VALIDATED** | Chạy đúng, mục đích rõ ràng (sanity check kết nối), không có logic cần kiểm định |
| `07_breakout_research.ipynb` | **VALIDATED** (chạy đúng) — hiệu năng cần lưu ý | Logic khớp `src/backtest/breakout_research.py` hiện tại; **~18 phút runtime thật** — vượt xa timeout mặc định 600s của `nbconvert`/nhiều pipeline CI, cần ghi chú cho ai chạy lại |
| `09_stealth_accumulation_screen.ipynb` | **VALIDATED** (chạy đúng) | Khớp `src/screening/stealth_accumulation.py` hiện tại |
| `12_meta_ranking_optimization.ipynb` | **BROKEN + OUTDATED_LOGIC (một phần)** | Xem NV3 — lỗi cấu trúc (project-root cell), cộng banner tự nhận cột hiển thị (momentum/rs/trend) thuộc v1 shadow không còn dẫn dắt `alpha_score`. Bản thân hàm tính điểm gọi đúng `calculate_alpha_scores` (v2) hiện tại — KHÔNG phải toàn bộ notebook outdated, chỉ phần hiển thị + project-root cell |
| `14_portfolio_construction.ipynb` | **VALIDATED** (chạy đúng) | Khớp `src/portfolio/construction.py` hiện tại |
| `15_risk_management.ipynb` | **VALIDATED** | Import trực tiếp `expanding_sharpe_series`/`rolling_sharpe_series` từ `src.risk.management` — module đã hợp nhất + sửa `ddof=1` (commit `fe253e5`/`d69f85e`) — notebook tự động kế thừa fix, không có phép tính std/sharpe cục bộ nào cần sửa riêng |
| `16_capital_allocation.ipynb` | **VALIDATED** | Khớp `src/capital/management.py` hiện tại |
| `19_validation_and_stress_test.ipynb` | **BROKEN (hiệu năng)** + banner OUTDATED sẵn có | Xem NV3 |
| `20_portfolio_backtester.ipynb` | **BROKEN + OUTDATED_LOGIC (gọi hàm lỗi thời)** | Xem NV3 — đúng loại phát hiện "gọi hàm lỗi thời" giống vụ `06_market_regime` |
| `01_client_market_report.ipynb` | **VALIDATED** | Read-only, không có logic tính toán riêng để kiểm định |
| `stock_buy_decision.ipynb` (SDE) | **VALIDATED (như công cụ bảng dữ kiện, KHÔNG phải khuyến nghị mua/bán)** | Đã khớp Nhánh C: không còn `final_score`/`decision` (xác nhận `grep` cả notebook lẫn `src/scoring.py`); toàn bộ audit sâu đã có ở `AUDIT_SDE_REPORT.md`/`SDE_SCORING_REPORT.md`, không lặp lại ở đây |

---

## NV3 — Lỗi kỹ thuật cơ bản (chi tiết 3 notebook BROKEN)

### `12_meta_ranking_optimization.ipynb` — `ModuleNotFoundError: No module named 'src'`

Cell "Setup Project Root" dùng logic khác — và **kém bền vững hơn** — so với
mọi notebook khác trong dự án:

```python
PROJECT_ROOT = Path.cwd().resolve().parents[0] if Path.cwd().name == "notebooks" else Path.cwd().resolve()
```

So với hàm `find_project_root()` chuẩn (dùng ở 15/16 notebook khác, kể cả
toàn bộ 6 notebook `02_market_research/`) tự tìm ngược lên cây thư mục cho
tới khi gặp cả `src/` lẫn `config/`. Cell trên **không tìm ngược** — chỉ
kiểm tra "nếu thư mục hiện tại tên đúng là `notebooks`, lùi 1 cấp; nếu
không, dùng luôn thư mục hiện tại". Khi chạy qua `nbconvert` (cwd của kernel
= thư mục CHỨA chính file notebook, tức `03_alpha_signals`, không phải
`notebooks`), điều kiện sai → `PROJECT_ROOT` bị gán nhầm thành
`03_alpha_signals` — thư mục không có `src/`, khiến `import src.analytics...`
ở cell kế tiếp lỗi ngay. Đây là lỗi **tái lập được, không phải do sandbox
audit** — bất kỳ pipeline tự động nào chạy notebook này qua `nbconvert`
(không phải mở tay qua Jupyter với server root đúng là `notebooks/`) đều sẽ
gặp lỗi y hệt.

### `19_validation_and_stress_test.ipynb` — không hoàn thành trong 30 phút

Cell "Sweeps and Sensitivities" gọi
`run_breakout_research(clean_daily)` — truyền thẳng
`data/processed/clean_daily_ohlcv.parquet` (dữ liệu giá thô, CHƯA qua feature
engineering) làm tham số `features`, khác với `07_breakout_research.ipynb`
gọi đúng cách: `run_breakout_research(features, signal_col="breakout_20d", ...)`
với `features` đã tính sẵn từ `stock_features.parquet`. Vì `clean_daily`
thiếu cột `breakout_20d`/các cột dẫn xuất, `ensure_breakout_features()` bên
trong phải tự tính lại toàn bộ đặc trưng từ dữ liệu thô cho **toàn universe**
thay vì đọc cột đã tính sẵn — khiến cell này chậm hơn hẳn cùng lệnh gọi ở
notebook 07 (đã tốn tới ~18 phút với input ĐÚNG, nên input SAI ở đây rất có
thể tốn thời gian gấp nhiều lần). Đã thử timeout 1800s (30 phút, gấp 3 lần
mặc định) — vẫn không xong. Đây là lỗi sử dụng sai tham số của chính notebook
(nên truyền `features`/`stock_features.parquet` như notebook 07), không phải
lỗi của `run_breakout_research` hay do sandbox.

### `20_portfolio_backtester.ipynb` — gọi hàm với chữ ký đã lỗi thời

```
ValueError: run_portfolio_backtest: no benchmark available -- 'VNINDEX' is
not a symbol in `features` ... no `benchmark_features` was supplied. A prior
version of this function silently substituted an arbitrary other stock's
data here and labeled it as the benchmark -- that has been removed. Pass
benchmark_features=<DataFrame with 'date'/'return_1d' columns> explicitly.
```

Notebook gọi `run_portfolio_backtest(features=..., meta_ranking=..., ...)`
**không truyền `benchmark_features=`** — tham số này **bắt buộc phải truyền
tay** kể từ commit `bef0de6` (`fix(backtest): remove silent benchmark
fallback, raise a clear error instead`, PUSH_REVIEW.md Phase 3), thay cho
hành vi cũ (đã bị gỡ) là âm thầm lấy đại một mã cổ phiếu khác làm benchmark
giả. Notebook được viết TRƯỚC thay đổi này và **chưa từng được cập nhật
theo** — **đúng loại phát hiện "gọi hàm lỗi thời" y hệt vụ `06_market_regime`
thiếu tham số `benchmark=`**, chỉ khác là lần này hàm chủ động raise lỗi rõ
ràng thay vì âm thầm tính sai (một cải tiến an toàn đã có sẵn, nhưng khiến
notebook này giờ BROKEN thay vì chỉ INCORRECT âm thầm).

### Look-ahead / chuẩn hóa full-sample

Không tìm thấy trường hợp nào trong 13 notebook (loại 3 notebook BROKEN
không hoàn thành phần tính toán chính — không có gì để kiểm tra thêm về
mặt này). Toàn bộ notebook còn lại gọi hàm từ `src/` (không tự định nghĩa
lại logic rolling/percentile trong cell), các hàm nguồn đã xác nhận dùng
`rolling()`/tính lại theo từng cửa sổ ở vòng audit `MARKET_REGIME_AUDIT.md`
trước.

### Nguồn dữ liệu

Toàn bộ notebook đọc từ `data/processed/*.parquet` hoặc `data/signals/*.parquet`
dẫn xuất từ `full_history_v2` (nguồn chính thức hiện tại) — NGOẠI TRỪ 2
notebook đã nêu ở trên (`02_fetch_daily_ohlcv`, `03_clean_validate_data`) đọc
từ `data/raw/daily_ohlcv/` — đường dẫn **cũ, đã bị thay thế và hiện rỗng**.

### Chạy độc lập / phụ thuộc state ẩn

12/13 notebook chạy sạch qua kernel mới (`nbconvert --execute`), không phụ
thuộc cell chạy tay trước đó. Duy nhất `16_capital_allocation.ipynb` có phụ
thuộc thứ tự RÕ RÀNG (không phải ẩn) vào output của notebook 15
(`risk_overlay_weights.parquet`) — đã có comment nguồn gốc trong code, không
tính là "state ẩn" theo đúng nghĩa NV2 yêu cầu kiểm tra.

---

## NV4 — Bảng tổng hợp toàn dự án (khớp cấu trúc `MARKET_REGIME_AUDIT.md`)

| Nhóm | Số lượng | VALIDATED | BROKEN | INCORRECT/DEAD+rủi ro | ARCHIVE/DEAD (đề xuất) |
|---|---|---|---|---|---|
| `02_market_research/` (đã audit trước, không tính lại) | 6 | — | — | — | — |
| `00_archive/` | 6 | 2 (00, 18) | 1 (17) | 2 (02, 03 — rủi ro ghi-đè-production) | 1 (11, CONVERTED_TO_SCRIPT) |
| `01_data_pipeline/` | 1 | 1 (01) | 0 | 0 | 0 |
| `03_alpha_signals/` | 3 | 2 (07, 09) | 1 (12) | 0 | 0 |
| `04_watchlist_portfolio/` | 5 | 3 (14, 15, 16) | 2 (19, 20) | 0 | 0 |
| `05_client_report/` | 1 | 1 (01) | 0 | 0 | 0 |
| `stock-decision-engine/` | 1 | 1 (SDE) | 0 | 0 | 0 |
| **Tổng (13 notebook vòng này)** | **13** | **10** | **4** | **2** | **1** |

(4 BROKEN = 12, 17, 19, 20; 2 INCORRECT/rủi ro = 02, 03; 1 CONVERTED_TO_SCRIPT
= 11 — 02/03 vừa BROKEN-về-mặt-dữ-liệu vừa mang rủi ro ghi-đè-production nên
không trùng đếm với cột BROKEN ở trên.)

---

## Danh sách ưu tiên sửa (CHƯA làm — để vòng sau quyết định, đúng ràng buộc audit-thuần)

**Ưu tiên 1 — rủi ro ghi-đè-production (nghiêm trọng nhất, nên xử lý trước
mọi việc khác)**:
1. Mở rộng `guard_production_write()` (hoặc tối thiểu thêm cảnh báo tương tự)
   vào `00_archive/02_fetch_daily_ohlcv.ipynb` và
   `00_archive/03_clean_validate_data.ipynb` — cả 2 ghi thẳng
   `clean_daily_ohlcv.parquet` không qua guard, một cái ghi dữ liệu chưa
   validate, một cái ghi dữ liệu RỖNG.
2. Cân nhắc mở rộng `PROTECTED_PATHS` sang `data/signals/alpha_scores.parquet`
   (ghi bởi notebook 12, đọc bởi ≥5 script/module production khác).

**Ưu tiên 2 — sửa lỗi kỹ thuật cụ thể (chi phí thấp, bằng chứng đã đủ)**:
3. `12_meta_ranking_optimization.ipynb`: thay cell project-root bằng
   `find_project_root()` chuẩn (đã dùng ở các notebook khác).
4. `20_portfolio_backtester.ipynb`: truyền `benchmark_features=` (đọc từ
   `data/processed/benchmark_vnindex.parquet`) vào lệnh gọi
   `run_portfolio_backtest`.
5. `19_validation_and_stress_test.ipynb`: sửa lệnh gọi
   `run_breakout_research(clean_daily)` thành truyền `features` đã tính sẵn
   (giống notebook 07) thay vì dữ liệu giá thô.
6. `17_live_watchlist_dashboard.ipynb`: sửa `.get("forward_return_20d", np.nan)`
   để xử lý đúng trường hợp cột thực sự không tồn tại (trả Series NaN, không
   phải scalar).

**Ưu tiên 3 — dọn dẹp/archive (đề xuất, KHÔNG xóa theo đúng ràng buộc)**:
7. Đề xuất archive/xóa 2 notebook rủi ro cao ở Ưu tiên 1 nếu xác nhận không
   ai còn dùng (đã có script thay thế cho toàn bộ luồng fetch/clean).
8. Cân nhắc xóa/archive `11_trade_card_generation.ipynb` (đã có
   `scripts/generate_trade_cards.py` thay thế hoàn toàn).

---

*Audit thực hiện 2026-07-21, cùng ngày/vòng theo dõi trực tiếp với
`MARKET_REGIME_AUDIT.md`. Không có notebook nào bị sửa hay xóa trong vòng
này — đúng ràng buộc audit-thuần đã cho.*
