# Audit Notebooks — 2026-07-26

> **Chế độ:** READ-ONLY tuyệt đối. Không sửa / xoá / format / execute bất kỳ notebook nào.
> File này là file DUY NHẤT được tạo.
> **Branch audit:** `claude/super-prompt-audit-notebooks-281814` (worktree `audit-gates-17-6-12-049aeb`).
> **Lưu ý quan trọng về branch:** một số lỗi ghi trong report này ĐÃ được fix trên branch khác
> (`claude/full-notebook-audit-949e88`, commit `aa97ae2`/`f6a0216`: thêm `production_guard.py`,
> `scripts/check_notebooks.py`, sửa `find_project_root` cho notebook 12, thêm `benchmark_features=`
> cho notebook 20). **Trên branch hiện tại, các fix đó KHÔNG tồn tại** — đã verify:
> `grep -rl "guard_production_write" .` → rỗng; `ls scripts/check_notebooks.py` → không có; không có `Makefile`.
> Report này mô tả trạng thái *branch hiện tại*, không phải trạng thái hợp nhất.
>
> **⇒ ĐÃ ĐỐI CHIẾU LẠI TRÊN `main` NGÀY 2026-07-27.** Xem mục "ĐỐI CHIẾU LẠI TRÊN `main`"
> ngay bên dưới: **8 finding STALE** (đã sửa trên main), **16 OPEN_MANUAL**, **4 OPEN_AUTO**,
> kèm **1 phát hiện mới** nghiêm trọng hơn tất cả các mục trong phần gốc, và **1 mục tự đính chính**
> vì phần gốc đã phóng đại. Khi phần gốc mâu thuẫn với mục đó, **mục đó đúng**.

---

# ĐỐI CHIẾU LẠI TRÊN `main` — 2026-07-27

> **Đọc phần này TRƯỚC phần audit gốc bên dưới.**
> Phần audit gốc (từ `## Tổng quan` trở xuống) được viết trên nhánh
> `claude/super-prompt-audit-notebooks-281814`, **fork từ một điểm CŨ** và thiếu nhiều fix đã có
> trên `main`. Nhánh đó nay **đóng băng, không merge** (merge sẽ revert các fix).
> Phần này phân loại lại **từng finding trên `main` @ `1dd67e9`**, bằng bằng chứng đo trực tiếp.
> Khi hai phần mâu thuẫn, **phần này đúng**.

## 0. Trạng thái đo được lúc đối chiếu

- `main` HEAD `1dd67e9` == `origin/main` (0 ahead / 0 behind).
- Working tree **không sạch**: 1508 mục. Gần hết là artifact nhịp ngày (463 file `data/` bị sửa,
  hàng loạt `data/disclosure/raw/*.json` chưa track, `reports/*`, `stock-decision-engine/outputs/*.png`).
- **9 notebook bị sửa trong working tree.** Phân tích: 4 notebook chỉ đổi `execution_count`/`outputs`
  (đã được **chạy tay**), 5 notebook (`04`, `05`, `06`, `13`, `14`) có **thay đổi source chưa commit** —
  nội dung là **thêm cell vẽ biểu đồ** (matplotlib rcParams, plot regime timeline, plot volatility
  estimators), **không phải fix bug**. Có người đang phát triển notebook bằng tay, chưa commit.
- `.ipynb_checkpoints/` **đã quay lại** (5 thư mục dưới `notebooks/`). `notebook_inventory.md` mục
  "Delete Candidates" ghi "(audit A2, 2026-07-08) verified none of these files exist on disk anymore"
  — **claim đó nay đã lỗi thời**. Chúng bị `.gitignore:7` che nên không hiện trong `git status`.

---

# ĐỢT 2 — ĐÃ XỬ LÝ TOÀN BỘ NHÓM OPEN_AUTO (2026-07-27)

Vòng này **chỉ** đụng nhóm OPEN_AUTO. 16 mục OPEN_MANUAL và 8 mục STALE **giữ nguyên**,
chuỗi `14/15/16` và `nb19` **không đụng tới**.

| Mục | Trạng thái | Cách xử lý | Commit |
|---|---|---|---|
| **OPEN_AUTO #1** — eligibility đóng băng 25 ngày | ✅ **ĐÃ CHẶN** | `assert_derived_artifact_fresh()` trong `generate_trade_cards.py`: so mtime `breakout_20d_setup_eligibility` / `volatility_rule` với `setup_signals`, quá **7 ngày** → `SystemExit`. Env `MAX_ELIGIBILITY_LAG_DAYS` để nới, `-1` để tắt | `eff0020` |
| **OPEN_AUTO #2** — `alpha_scores.parquet` ngoài vùng bảo vệ | ✅ **ĐÃ CHẶN** | `PROTECTED_DIRS` phủ cả `data/processed` · `data/signals` · `data/output` · `reports`; guard chuyển xuống tầng `save_parquet`/`save_csv_atomic` nên **mọi notebook** được phủ, không cần sửa từng file | `b053ede` |
| **OPEN_AUTO #3** — `reports/top_watchlist.csv` 2 producer | ✅ **ĐÃ SỬA + KHÔI PHỤC** | nb12 chuyển 3 đường ghi sang `notebooks/outputs/`; chạy lại `run_alpha_scoring.py` → schema có lại `alpha_score_shadow_v1`, 4 file cùng mtime, lineage đúng trở lại | `cb80949` |
| **OPEN_AUTO #4** — nb09 ghi `stealth_accumulation_latest` | ✅ **ĐÃ CHẶN** | Tự động phủ bởi guard tầng loader ở #2 — không cần sửa nb09 | `b053ede` |

**Vì sao KHÔNG tự động hoá việc sinh eligibility (hướng (a)):** `run_breakout_research()` chọn
stop-loss bằng `_select_best_stop_relaxed()` (`src/backtest/breakout_research.py:275`) — quét lưới
**in-sample** trên chính dữ liệu nó báo cáo. Cắm vào cron sẽ biến một lựa chọn overfit thành thứ
được **fit lại mỗi đêm**. Cần prereg riêng; xem "Đợt 2.1" ở mục 4.

**Mức nhiễm 25 ngày qua (NV1, đánh giá tác động ngược).** Chuỗi lan truyền đo được:

```
nb07 (tay, 2026-07-02) → breakout_20d_setup_eligibility.parquet
   → generate_trade_cards.py:44 (bước 4/7, mỗi đêm) → breakout_20d_trade_cards.parquet
   → run_meta_ranking.py:46 (bước 7/7) → meta_ranking.parquet
   → final_watchlist.py → data/output/{research_candidates, trading_watchlist, client_ready_watchlist}.parquet
   → notebooks/05_client_report/01_client_market_report.ipynb (đọc data/output/)
```

Nhiễm **có** tới watchlist khách hàng, nhưng **định lượng được và ở mức vừa**: `trade_edge_score`
và `setup_quality_score` (cả hai dẫn xuất từ `win_rate`/`profit_factor`/`avg_return` đóng băng) là
2 trong 3 thành phần của `signal_raw`, mà `signal` chỉ nặng **11.11/100** trong `final_score`
(`final_watchlist.py:127,580`). Tức khoảng **4–7 điểm trên thang 100** của thứ hạng bị lệch, cộng
với hai cờ boolean `eligible`/`watchlist_eligible` và mức `stop_loss` hiển thị trên trade card
(đóng băng ở `-0.10`). Không phải "watchlist sai hoàn toàn", nhưng thứ tự xếp hạng **có** bị dịch
bởi thống kê nghiên cứu cũ một tháng, và trade card hiển thị stop-loss không còn được kiểm chứng lại.

**Phát hiện phụ (ngoài scope, chỉ ghi nhận):** `data/output/research_notes_metadata.json` khai 4
note đã sinh (`MST.md`, `BVS.md`, `KLB.md`, `NAB.md`) mà `research_notes/generated/` **không có**.
Cùng họ "sidecar nói dối" nhưng không liên quan notebook, và `build_research_notes` không nằm trong
các bước mặc định hằng đêm. Không sửa vòng này.

**`.ipynb_checkpoints/`:** kiểm tra lại — **đã có sẵn** trong `.gitignore` dòng 7, không cần thêm.
Chỉ bổ sung `notebooks/outputs/**/*.csv` (trước đó chỉ có `*.parquet`).

---

## 1. Bảng phân loại

Ký hiệu: **STALE** = đã sửa trên main, report gốc nhầm do chạy nhánh cũ ·
**OPEN_MANUAL** = còn thật, chỉ gây hại khi có người chạy notebook tay ·
**OPEN_AUTO** = còn thật VÀ nằm trong đường chạy tự động hằng đêm
(**cả 4 mục OPEN_AUTO nay đã xử lý — xem mục ĐỢT 2 ở trên**).

| # | Finding (report gốc) | Phân loại trên `main` | Bằng chứng |
|---|---|---|---|
| 1 | nb05 ghi đè `stock_features.parquet` | **STALE** | `05_volatility_regime.ipynb` cell[5] nay bọc `guard_production_write(output_path)` + `try/except ProductionWriteBlocked` |
| 2 | nb06 ghi đè `market_features.parquet` | **STALE** | cell[5] cùng pattern guard |
| 3 | nb06 gọi `add_market_regime()` **thiếu `benchmark=`** | **STALE** | cell[3] main: `benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")` → `add_market_regime(breadth, benchmark=benchmark)`, kèm comment NV1 |
| 4 | nb20 **BROKEN** — thiếu `benchmark_features=` → `ValueError` | **STALE** | cell[3] main đọc `benchmark_vnindex.parquet` + raise nếu rỗng; cell[4] truyền `benchmark_features=benchmark_features` |
| 5 | nb12 `PROJECT_ROOT` sai layout → không chạy được từ Jupyter | **STALE** | cell[2] main dùng `find_project_root()`; `Path.cwd().name == "notebooks"` không còn |
| 6 | archive `02`/`03` ghi đè `clean_daily_ohlcv.parquet` | **STALE** | cả hai nay guard; `03` còn ghi rõ root cause `LEGACY_PRICE_RAW_DIR` inline |
| 7 | Thiếu rào chắn cấu trúc (`check_notebooks.py`, `Makefile`) | **STALE** | `scripts/check_notebooks.py` + `Makefile` (`make check-notebooks`) tồn tại; rsync sang `tempfile.TemporaryDirectory` rồi mới `nbconvert --inplace` → **không đụng dữ liệu thật** |
| 8 | nb19 "Sweeps and Sensitivities" truyền sai input (`clean_daily`) | **STALE (một phần)** | cell main truyền `signals` + comment NV2. Phần **trùng vai trò với nb07 vẫn còn** (vẫn gọi `run_breakout_research`) |
| 9 | **nb07 → `breakout_20d_setup_eligibility` / `volatility_rule`** | **OPEN_AUTO** ⛔ | Xem §2.1 — nghiêm trọng nhất |
| 10 | nb12 ghi `data/signals/alpha_scores.parquet` không guard | **OPEN_AUTO** | `PROTECTED_PATHS` chỉ gồm 3 path `data/processed/`; `scripts/run_meta_ranking.py:49` (bước 7/7 tự động) đọc lại file này. Xem §2.2 |
| 11 | nb12 ghi `reports/top_watchlist.csv` + `daily_alpha_ranking.csv` | **OPEN_AUTO** | Đúng 2 producer; file trên đĩa **hiện đang là bản của notebook**. Xem §2.3 |
| 12 | nb09 ghi `stealth_accumulation_latest.parquet` không guard | **OPEN_AUTO (nhẹ)** | `run_meta_ranking.py:47` đọc, nhưng bước 5/7 `run_stealth_accumulation_screen.py` tái sinh trước bước 7 → tự lành sau mỗi đêm |
| 13 | nb09 markdown mô tả "auto top 10" ≠ code scan full universe | **OPEN_MANUAL** | Nội dung nb09 **giống hệt** nhánh cũ (hash `abc7b8a11b` cả hai bên). `scan_input` vẫn bị bỏ; `load_auto_watchlist_symbols` vẫn import-không-dùng |
| 14 | nb14 universe hard-code 20 mã + overfit ~53.000 ứng viên | **OPEN_MANUAL** | `user_watchlist = ["NAB","VCB",...]` vẫn nguyên ở cell[3] main; `generate_sub_portfolios` vẫn ở cell[10]; `selected_col` vẫn ở cell[13] |
| 15 | nb14/nb15/nb16 → `selected_portfolio_weights` / `risk_overlay_weights` / `capital_allocation_plan` | **OPEN_MANUAL** | grep `src/` + `scripts/`: **0 reader**. Chỉ notebook đọc lẫn nhau → không chạm đường tự động |
| 16 | nb15 báo cáo NAV/Sharpe in-sample | **OPEN_MANUAL** | nb15 giống hệt nhánh cũ (hash `8d89fa9fe8`) |
| 17 | nb16 trùng 65 dòng với `00_archive/17`, cùng output path | **OPEN_MANUAL** | nb16 hash giống hệt; `00_archive/17` cell[14] vẫn ghi `risk_overlay_weights` + `capital_allocation_plan`, **không có guard** |
| 18 | nb19 cell "Run Leakage Verification" **chưa từng chạy** | **OPEN_MANUAL** | HEAD main: cell[8] `ec=None, nout=0`. **Thêm**: cell[10] "Sweeps and Sensitivities" nay **cũng** `ec=None` → 2 cell chưa chạy |
| 19 | nb19 nhãn "Out-of-Sample (2025-2026)" sai + validate nhầm danh mục | **OPEN_MANUAL** | cell[6] main vẫn dùng `weights_df[...]["max_sharpe"]` fit toàn mẫu; vẫn khác `mc_best_concentrated_3_5` mà nb15/16 dùng |
| 20 | nb19 survivorship không đo (`config/delisted_symbols.csv` thiếu) | **OPEN_MANUAL** | File vẫn không tồn tại trên main |
| 21 | nb13 + nb14 đọc `stock_features_volatility.parquet` mồ côi | **OPEN_MANUAL** | Vẫn **0 producer** toàn repo; mtime **2026-06-24** vs `stock_features.parquet` **2026-07-23** → lệch **29 ngày** |
| 22 | nb04 → `stock_features_distribution.parquet` mồ côi | **OPEN_MANUAL** | 0 consumer trong `src`/`scripts`; mtime 2026-07-20 |
| 23 | nb08 chỉ 1 mã HPG, stop 1% / target 20%, bootstrap IID | **OPEN_MANUAL** | cell[3] main: `symbol="HPG"`, `stop_pct=0.01`, `target_pct=0.20` — không đổi |
| 24 | nb12 biểu đồ "Top 5 cumulative return" = backfill illusion | **OPEN_MANUAL** | `top_5_symbols` vẫn ở cell[32] main |
| 25 | nb12 `execution_count` lộn xộn nặng | **OPEN_MANUAL** | HEAD main: `[None,4,5,...,12,15,...,20,23,25,27,29,31,33,34]` — y nguyên |
| 26 | nb20 `meta_ranking.parquet` là snapshot → look-ahead | **OPEN_MANUAL (đã phóng đại)** | Xem §3 — tự đính chính |
| 27 | `05_client_report` cell[21] chưa chạy + 2 chuỗi f-string hỏng | **OPEN_MANUAL** | Notebook giống hệt nhánh cũ (hash `d64f93297d`) |
| 28 | nb07 chọn `best_stop_row` in-sample (bias phương pháp) | **OPEN_AUTO** ⛔ | Bias thì thuộc nhóm phương pháp, nhưng **output của nó chảy thẳng vào pipeline tự động** — xem §2.1 |

**Tổng:** 8 STALE · 16 OPEN_MANUAL · 4 OPEN_AUTO.

## 2. NV3 — Phơi nhiễm tự động (đo trực tiếp, không suy đoán)

**Lịch chạy tự động duy nhất:** LaunchAgent `com.vietnam-quant-research.dailyrun`
(`~/Library/LaunchAgents/`), `StartCalendarInterval` T2–T6 19:00 + `RunAtLoad`, gọi
`/bin/bash scripts/daily_run.sh`. **Không có crontab** (`crontab -l` → "no crontab for jamesb").

`daily_run.sh` gọi **đúng 4 bước, toàn bộ là `.py`**:

1. `scripts/update_prices_daily.py --universe`
2. `scripts/update_disclosure_daily.py --universe`
3. `scripts/update_index_data.py`
4. `scripts/run_daily_pipeline.py --offline`

`run_daily_pipeline` (`PIPELINE_STEPS`, không cờ thêm) chạy 7 bước, cũng **toàn `.py`**:
`generate_features` → `generate_signals` → `run_alpha_scoring` → `generate_trade_cards` →
`run_stealth_accumulation_screen` → `build_cashflow_board --symbol-only` → `run_meta_ranking`.
(`build_portfolio_stack` / `build_sector_board` / `build_research_notes` chỉ chạy khi có cờ —
`daily_run.sh` **không** truyền cờ nào.)

**→ Không một bước tự động nào chạy notebook.** `grep -rn "nbconvert\|\.ipynb" scripts/ Makefile <plist>`
chỉ trúng `run_all_notebooks.sh` và `check_notebooks.py`.

**`run_all_notebooks.sh` — ai gọi?** Chỉ `tests/test_pipeline_contracts.py:37`, và gọi với cờ
**`--list`** (liệt kê, không execute). Không cron, không LaunchAgent, không script nào khác.
→ **Chỉ chạy tay.**

**`check_notebooks.py`** dùng `nbconvert --execute --inplace` nhưng `sync_sandbox()` rsync repo sang
`tempfile.TemporaryDirectory` rồi mới chạy **trong sandbox** → **không đụng dữ liệu/notebook thật**. An toàn.

### 2.1 ⛔ OPEN_AUTO #1 — pipeline tự động phụ thuộc artifact chỉ notebook 07 sinh ra được (25 ngày cũ)

Đây là phát hiện **mới**, không có trong report gốc, và nghiêm trọng hơn mọi mục còn lại.

| | |
|---|---|
| Producer duy nhất toàn repo | `save_breakout_research_outputs()` — **chỉ được gọi từ `notebooks/03_alpha_signals/07_breakout_research.ipynb`**. `grep` `src/`+`scripts/`: không script nào gọi |
| Files | `data/signals/breakout_20d_setup_eligibility.parquet`, `breakout_20d_volatility_rule.parquet` |
| Consumer | `scripts/generate_trade_cards.py:44-45` — **bước 4/7 của pipeline tự động hằng đêm** |
| mtime thực tế | **2026-07-02 12:55** |
| So sánh | `setup_signals.parquet` và `breakout_20d_trade_cards.parquet`: **2026-07-23 08:37** |

**Hệ quả:** mỗi đêm, `generate_trade_cards.py` sinh trade card từ bảng eligibility **đóng băng
từ 2026-07-02 — 25 ngày trước**, và bảng đó chính là `best_stop_row` **chọn in-sample** của
notebook 07 (finding #28). Không có bước tự động nào làm mới nó; cách duy nhất là **một người mở
notebook 07 và chạy tay**. Không có cảnh báo staleness nào cho path này.

Đây là đường duy nhất mà một finding "chỉ hại khi chạy tay" thực sự **đã** chảy vào sản phẩm tự động —
và nó chảy vào theo hướng ngược đời: **không chạy** notebook mới là thứ đang gây hại (dữ liệu đóng băng).

### 2.2 OPEN_AUTO #2 — `alpha_scores.parquet` ngoài vùng bảo vệ

`PROTECTED_PATHS` (`src/data/production_guard.py`) = **đúng 3 path**, đều thuộc `data/processed/`:
`clean_daily_ohlcv` · `stock_features` · `market_features`. Mọi thứ dưới `data/signals/` và
`reports/` **không được bảo vệ**.

- Ghi bởi: `scripts/run_alpha_scoring.py:47` (tự động, bước 3/7) **và** `notebooks/.../12_*.ipynb` cell[16] (tay).
- Đọc bởi: `scripts/run_meta_ranking.py:49` (tự động, bước 7/7), `src/screening/final_watchlist.py:153`,
  `scripts/main_visual_dashboard.py:51`.
- **Tự lành:** bước 3 chạy trước bước 7 trong cùng một lần chạy → bản notebook bị ghi đè lại mỗi đêm.
  Cửa sổ phơi nhiễm = từ lúc chạy notebook tay đến lần chạy tự động kế tiếp.

### 2.3 OPEN_AUTO #3 — `reports/top_watchlist.csv`: đúng 2 producer, và **bản trên đĩa hiện là bản của notebook**

Xác nhận **đúng hai** producer sống:

1. `scripts/run_alpha_scoring.py:73` — `save_csv_atomic(...)`, **tự động mỗi đêm**, kèm ghi sidecar
   lineage `reports/alpha_scoring_metadata.json` (audit gate #12).
2. `notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb` cell[33] —
   `ranking.head(20).to_csv(...)`, **chạy tay**, **không atomic, không cập nhật lineage**.

(Thêm 2 bản `-checkpoint.ipynb` trong `.ipynb_checkpoints/` cũng chứa dòng ghi này — bất động
trừ khi có người mở và chạy chúng.)

**Bằng chứng hiện trường ngày 2026-07-23:**

| Thời điểm | Sự kiện | Bằng chứng |
|---|---|---|
| 08:36:59–08:38:08 | Pipeline tự động chạy xong | `logs/daily_run.log`: `SUMMARY: 4/4 steps OK`; mtime `stock_features` 08:36:59, `market_features` 08:37:01, `alpha_scoring_metadata.json` 08:37:14 |
| **10:47:25–10:47:38** | **Notebook 12 chạy tay** | mtime `meta_ranking.parquet` 10:47:25, `alpha_scores.parquet` 10:47:36, `daily_alpha_ranking.csv` + `top_watchlist.csv` **10:47:38** — sau pipeline **2h10m** |
| 11:02:12 | Notebook 14 chạy tay | mtime `selected_portfolio_weights.parquet` |

Và schema đã đổi — bản trên đĩa **không phải** bản pipeline:

```
HEAD (pipeline): symbol,date,close,alpha_score,alpha_score_shadow_v1,momentum_score,...,market_regime
DISK (notebook): symbol,date,close,alpha_score,momentum_score,...,rolling_beta_60d,market_regime
```

Bản notebook **mất cột `alpha_score_shadow_v1`** (cột nuôi so sánh shadow v2-vs-v1 của
`SCORE_V2_REPORT`) và **thêm `rolling_beta_60d`**. Sidecar `alpha_scoring_metadata.json` (08:37:14)
vẫn khai `generated_files: [... "reports/top_watchlist.csv"]` — **lời khai đó hiện đang sai**:
file nó mô tả đã bị ghi đè bởi một producer khác 2 giờ sau đó.

**Mức độ thật:** `grep` toàn `src/` + `scripts/` + `tests/` → **không ai ĐỌC lại**
`top_watchlist.csv` / `daily_alpha_ranking.csv`. Đây là **deliverable đầu cuối** (người/khách đọc).
Nên thiệt hại là **sai deliverable + gãy lineage**, không phải gãy pipeline. Vẫn xếp OPEN_AUTO vì
nó là artifact do bước tự động sở hữu và đang bị bên khác chiếm chỗ **ngay lúc này**.

### 2.4 Các file notebook ghi mà **không** ai tự động đọc (⇒ OPEN_MANUAL, không khẩn cấp)

`selected_portfolio_weights.parquet` · `portfolio_construction_weights.parquet` ·
`risk_overlay_weights.parquet` · `capital_allocation_plan.parquet` · `monte_carlo_*.parquet` ·
`stock_features_distribution.parquet` · `live_dashboard_*.parquet` — **0 reader** trong
`src/` + `scripts/`. Toàn bộ chuỗi `14 → 15 → 16` và `00_archive/17` nằm gọn ngoài đường tự động.

## 3. Tự đính chính: mục 26 (nb20 / `meta_ranking` look-ahead) đã bị phóng đại

Report gốc viết: *"tại các ngày được phủ, việc chọn cổ phiếu dùng điểm tính từ dữ liệu cuối kỳ =
look-ahead trực tiếp"*. Đo lại phân bố thực tế của `meta_ranking.parquet` (500 dòng, 1 dòng/mã):

```
2026-07-22 → 435 mã (87.0%)      2026-07-21 → 20      2026-07-20 → 12
2026-07-17 →   9 mã              2026-07-15 →  3      còn lại 21 ngày × 1-2 mã
```

`run_portfolio_backtest` join theo **đúng cặp `(date, symbol)`** (`ranking.set_index(["date","symbol"])`),
và `rebalance_dates = all_dates[::20]` + ngày cuối. Vì 87% số dòng dồn vào **ngày cuối cùng**
(đây là artifact "mỗi mã 1 dòng ở ngày cuối nó có dữ liệu", không phải panel lịch sử), nên:

- Các ngày rebalance **lịch sử** hầu như không khớp dòng nào → chạy bằng **fallback**
  `score_reversal_quality`, đúng như docstring dòng 50-52.
- Chỉ **lần rebalance cuối** (ngày cuối chuỗi) khớp 435 mã — mà sau nó không còn ngày nào để sinh
  lợi nhuận, nên ảnh hưởng lên equity curve ≈ 0.

**Kết luận đúng:** đây **không phải** look-ahead lan rộng. Vấn đề thật là **nhãn sai**: notebook
trình bày `meta_ranking` như nguồn xếp hạng của backtest, trong khi thực tế gần như toàn bộ quyết
định đến từ một fallback mà notebook **không hề nhắc tới**. Hạ từ "look-ahead nghiêm trọng" xuống
**minh bạch/nhãn sai**, giữ OPEN_MANUAL.

## 4. NV4 — Đề xuất thứ tự sửa cho các đợt sau (CHỈ đề xuất, chưa làm gì)

| Đợt | Việc | Vì sao đứng ở đây |
|---|---|---|
| **2.1** | **`breakout_20d_setup_eligibility` / `volatility_rule`**: quyết định một trong hai — (a) viết `scripts/run_breakout_research.py` và cắm vào `PIPELINE_STEPS` **trước** `generate_trade_cards`, hoặc (b) nếu cố ý đóng băng thì thêm cảnh báo staleness ở `generate_trade_cards.py` | Đường **duy nhất** một finding đã thực sự chảy vào sản phẩm tự động. Đang phục vụ dữ liệu 25 ngày tuổi mỗi đêm mà không ai biết |
| **2.2** | Mở rộng `PROTECTED_PATHS` sang `data/signals/alpha_scores.parquet` + `reports/top_watchlist.csv` + `reports/daily_alpha_ranking.csv` (món đã 2 vòng bị bỏ ngoài scope) | Rào chắn rẻ, chặn đúng 2 đường ghi tay đang va nhau. Đã có sẵn cơ chế guard, chỉ thêm path |
| **2.3** | Notebook 12: bỏ cell ghi `alpha_scores.parquet` + `reports/*.csv` (hoặc trỏ sang `data/scratch/`) | Sau 2.2 notebook sẽ báo lỗi; cần dọn để `make check-notebooks` còn xanh |
| **3.1** | Notebook 19: chạy cell "Run Leakage Verification" và cell "Sweeps"; sửa nhãn "Out-of-Sample"; đổi sang validate đúng `mc_best_concentrated_3_5` | Chốt chặn kiểm định — phải đúng trước khi bàn tới bias của 14/15/16 |
| **3.2** | Notebook 14: `user_watchlist = None`; tách fit/evaluate theo thời gian; thêm benchmark VNINDEX | Gốc của cả chuỗi overfit `14→15→16`. Sửa sau 3.1 để có công cụ đo |
| **3.3** | Notebook 15/16: báo cáo out-of-sample thay vì in-sample; nêu rõ mã nào dùng `fillna` hằng số | Hệ quả của 3.2 |
| **4.1** | `stock_features_volatility.parquet`: đổi input nb13 + nb14 sang `stock_features.parquet`, xoá file mồ côi | Âm thầm sai (NaN im lặng), nhưng ngoài đường tự động |
| **4.2** | Notebook 09: đồng bộ markdown ↔ code (hoặc dùng `scan_input`, hoặc sửa markdown + bỏ import thừa); đổi tiêu đề "# 14" | Rủi ro hiểu nhầm cho người đọc, không rủi ro dữ liệu |
| **4.3** | Notebook 20: ghi rõ trong markdown rằng fallback `score_reversal_quality` mới là nguồn xếp hạng thực tế | Theo đính chính §3 — chỉ là vấn đề nhãn |
| **5.1** | `05_client_report`: sửa 2 chuỗi f-string hỏng; chạy cell[21] | Lỗi hiển thị trực tiếp trong báo cáo khách, nhưng cosmetic về dữ liệu |
| **5.2** | Dọn cell trống (nb01, 04, 06, 10) + import thừa (nb12, 14, 16); `00_archive/17` thêm guard hoặc đổi output path | Nhóm ❌ cosmetic + rào chắn cuối |
| **5.3** | Cập nhật `notebook_inventory.md`: mục "Delete Candidates" ghi `.ipynb_checkpoints` đã hết — **claim này nay sai**, checkpoint đã quay lại | Vệ sinh tài liệu |

**Không đề xuất** đưa nhánh `claude/super-prompt-audit-notebooks-281814` vào bất kỳ đợt nào —
merge nó sẽ revert 8 mục STALE ở §1.

---

# PHẦN AUDIT GỐC (viết trên nhánh cũ — đọc kèm bảng phân loại ở trên)

## Tổng quan

| Hạng mục | Số lượng |
|---|---|
| Tổng notebook | **22** |
| `00_archive` | 6 |
| `01_data_pipeline` | 1 |
| `02_market_research` | 6 |
| `03_alpha_signals` | 3 |
| `04_watchlist_portfolio` | 5 |
| `05_client_report` | 1 |

**Phân bố trạng thái (16 notebook active, không tính `00_archive`):**

| Trạng thái | Số lượng | Notebook |
|---|---|---|
| ✅ KEEP | **0** | — |
| ⚠️ REVIEW | **0** | — |
| ❌ CẦN XỬ LÝ | **16** | tất cả |

Trong 16 notebook "cần xử lý", cần phân biệt rõ hai loại ❌ (nếu không, mức độ nghiêm trọng bị bóp méo):

- **❌ cosmetic** — chỉ vướng tiêu chí #3 (cell trống cuối notebook). Không ảnh hưởng kết quả.
  → 4 notebook: `01_validate_environment`, `04_market_distribution`, `10_benchmark_diagnostics`, và
  phần cell trống của `06_market_regime`.
- **❌ nội dung** — sai logic, bias, ghi đè production, hoặc không chạy được.
  → **12 notebook**. Đây mới là danh sách thật sự cần hành động.

**Quy ước ghi chú:** "**Suy luận**" = kết luận rút từ đọc code, không có tài liệu xác nhận.

### Bối cảnh hệ thống (cần để đọc phần sau)

Repo có **hai đường ghi song song** vào cùng một tập file production:

| Artifact | Producer chính thức (script) | Notebook cũng ghi cùng path |
|---|---|---|
| `data/processed/clean_daily_ohlcv.parquet` | `scripts/generate_features.py:57` | `00_archive/02`, `00_archive/03` |
| `data/processed/stock_features.parquet` | `scripts/generate_features.py:78` | `02/05_volatility_regime` |
| `data/processed/market_features.parquet` | `scripts/generate_features.py:107` | `02/06_market_regime` |
| `data/signals/alpha_scores.parquet` | `scripts/run_alpha_scoring.py` | `03/12_meta_ranking` |
| `data/signals/stealth_accumulation_*.parquet` | `scripts/run_stealth_accumulation_screen.py` | `03/09_stealth_screen` |
| `data/signals/breakout_20d_*.parquet` | `scripts/generate_trade_cards.py` | `03/07_breakout_research` |
| `data/signals/risk_overlay_weights.parquet`, `capital_allocation_plan.parquet` | *(không có script)* | `04/15`, `04/16`, **và `00_archive/17`** |
| `reports/daily_alpha_ranking.csv`, `reports/top_watchlist.csv` | `scripts/run_alpha_scoring.py` | `03/12_meta_ranking` |

Và `scripts/run_all_notebooks.sh` chạy **toàn bộ** notebook active bằng
`jupyter nbconvert --execute --inplace` trên `data/` thật, **không sandbox, không guard**.
Nghĩa là một lần chạy runner sẽ ghi đè toàn bộ bảng trên bằng tham số hard-code trong notebook.
Đây là gốc rễ của phần lớn rủi ro trong report này.

---

## Chi tiết theo folder

### `01_data_pipeline` — 1 notebook

**Mục đích folder:** sanity-check môi trường / kết nối dữ liệu trước khi chạy notebook nghiên cứu.

#### `01_validate_environment.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | Markdown cell[0]: "Run this first after filling `.env`" |
| 2 | Trùng lặp | ⚠️ | Trùng một phần `scripts/check_fcdata_setup.py` (cũng check `.env` + package `ssi_fc_data`). Notebook thêm phần gọi thật `get_securities` / `get_daily_ohlc`; script chỉ check config. ~40% chức năng chồng nhau |
| 3 | Cell rác | ❌ (cosmetic) | 2/6 code cell trống (cell[5], cell[6]) = 33% |
| 4 | Thứ tự chạy | ⚠️ | `execution_count` = 3,4,5,6 — liên tục nhưng không bắt đầu từ 1 |
| 5 | Input/Output | ✅ | Input = SSI FCData API live; output = console. Đúng vai trò smoke test, không cần ai tiêu thụ |
| 6 | Tái lập | ⚠️ | Phụ thuộc `.env` credentials (`SSIDataClient(validate_credentials=True)`) — không chạy được offline |
| 7 | Hiệu quả | n/a | Không phải notebook alpha |
| 8 | Staleness | ✅ | Sửa 2026-07-02 (`d7c283e`), vẫn là bước 1 trong `notebooks/README.md` |

**Kết luận folder:** GIỮ. Chỉ cần xoá 2 cell trống. Cân nhắc ghi rõ trong markdown quan hệ với
`scripts/check_fcdata_setup.py` để người mới không phân vân dùng cái nào.

---

### `02_market_research` — 6 notebook

**Mục đích folder:** phân phối lợi nhuận, volatility, market regime, mô phỏng, chẩn đoán benchmark, phân tích tương quan/beta.

#### `04_market_distribution.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "Measure return distribution, skewness, kurtosis, quantiles and tails" |
| 2 | Trùng lặp | ⚠️ | `05_volatility_regime` cell[5] cũng gọi `add_rolling_distribution_stats(features, window=60)` rồi lưu vào `stock_features.parquet` (superset của output notebook 04). Trùng logic thực chất ~60% (21 dòng code chung sau khi bỏ boilerplate) |
| 3 | Cell rác | ❌ (cosmetic) | 4/9 code cell trống (cell[6]–cell[9]) = 44% |
| 4 | Thứ tự chạy | ⚠️ | ec = 3,4,5,6,7 — liên tục, không từ 1 |
| 5 | Input/Output | ⚠️ **mồ côi** | Ghi `data/processed/stock_features_distribution.parquet`. Grep toàn `src/` + `scripts/`: **0 consumer**. Chỉ `02/13_advanced_quant_analysis` đọc. File trên đĩa: 2026-07-20 |
| 6 | Tái lập | ⚠️ | Cần `clean_daily_ohlcv.parquet` do `generate_features.py` sinh trước |
| 7 | Hiệu quả | ✅ | Thống kê mô tả thuần, không có claim alpha → không có bias để bắt |
| 8 | Staleness | ⚠️ | Sửa lần cuối 2026-07-01 (`b437c5d`, commit gộp "organize notebooks") — không rõ còn ai chạy |

**Tác dụng phụ ẩn:** `add_returns()` (`src/features/returns.py:14`) có default
`flags_output_path="data/output/corporate_action_flags.csv"` và **ghi thật** file đó
(`returns.py:45`). Notebook 04, 05, 08 đều gọi `add_returns` → mỗi lần chạy đều ghi đè
file production này. Không notebook nào ghi chú điều đó.

#### `05_volatility_regime.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "ATR, realized volatility, EWMA volatility and volatility percentile" |
| 2 | Trùng lặp | ⚠️ | Xem #2 của notebook 04 |
| 3 | Cell rác | ⚠️ | 1/6 code cell trống |
| 4 | Thứ tự chạy | ⚠️ | ec = 2,3,4,5,6 |
| 5 | Input/Output | ❌ **ghi đè production** | cell[5]: `save_parquet(features, "data/processed/stock_features.parquet")` — **cùng path** với `scripts/generate_features.py:78`. File này là input của gần như toàn bộ hệ thống (screen, meta ranking, backtest, client report) |
| 6 | Tái lập | ⚠️ | Cần `clean_daily_ohlcv.parquet` |
| 7 | Hiệu quả | ✅ | Feature engineering thuần |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**Chi tiết #5 — vì sao đây là ❌ chứ không phải ⚠️:** notebook và script tạo ra **hai phiên bản khác nhau** của cùng một file:

| | `scripts/generate_features.py` | `02/05_volatility_regime.ipynb` |
|---|---|---|
| Nguồn raw | `data/full_history_v2/raw` + lọc `filter_primary_equity_symbols` + `config/excluded_symbols.csv` | `clean_daily_ohlcv.parquet` (đã lọc sẵn) |
| `horizons` | đọc từ `config/strategy_config.yaml` | mặc định `add_returns` = `[1,5,10,20]` |
| Cửa sổ ATR/vol/percentile | từ config | hard-code 14 / 20 / 20 / 252 |
| `add_moving_averages` | từ config `ma_windows` | hard-code `[20,50,200]` |
| Ghi kèm `index_features` / `benchmark_vnindex` | ✅ có | ❌ không |

Nếu config khác default, chạy notebook 05 sẽ **âm thầm thay** feature set production bằng phiên bản
hard-code. Không có cảnh báo, không có guard.

#### `06_market_regime.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "Rule-based first. HMM/ML can be added later" |
| 2 | Trùng lặp | ⚠️ | Lặp lại Step 5 của `scripts/generate_features.py:99-107` (breadth → regime → entropy → save) |
| 3 | Cell rác | ❌ (cosmetic) | 3/8 code cell trống; `import importlib` ở cell[2] không dùng |
| 4 | Thứ tự chạy | ⚠️ | ec = 3,4,5,6,7 |
| 5 | Input/Output | ❌ **ghi đè production** | cell[5]: `save_parquet(market, "data/processed/market_features.parquet")` — cùng path `generate_features.py:107` |
| 6 | Tái lập | ⚠️ | Cần `stock_features.parquet` |
| 7 | Hiệu quả | ❌ **logic lệch production** | Xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**❌ #7 — finding cụ thể và nghiêm trọng nhất của folder 02:**

```
notebook 06 cell[3]:      market = add_market_regime(breadth)
generate_features.py:104: market = add_market_regime(breadth, benchmark=benchmark)
```

Comment ngay trên dòng script nói rõ vì sao benchmark là bắt buộc:

> `# Step 5: Generate market features and regime (crash_severity/breakout_signal need the real VNINDEX price series from Step 4 -- see src/models/regime.py)`

Notebook **không truyền `benchmark`**. Chạy notebook 06 → `market_features.parquet` bị ghi đè bằng
regime tính **thiếu chuỗi giá VNINDEX thật**, tức `crash_severity` / `breakout_signal` bị suy giảm
hoặc mất. Mọi consumer hạ nguồn (`09_stealth_screen` đọc `market_features` để lấy entropy/regime;
`run_daily_pipeline.py`; client report) sẽ dùng regime kém chất lượng mà **không có tín hiệu nào báo**.

#### `08_monte_carlo_simulation.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | Markdown liệt kê 3 việc rõ ràng |
| 2 | Trùng lặp | ✅ | Không trùng (notebook 14 cũng có "Monte Carlo" nhưng là random portfolio trên simplex — khái niệm khác hẳn) |
| 3 | Cell rác | ⚠️ | 2/13 code cell trống; cell[5] (80 dòng matplotlib dark-theme) vẽ lại gần như đúng cái `chart_factory` đã có ở cell[6] |
| 4 | Thứ tự chạy | ✅ | ec = 1..11 tuần tự hoàn hảo |
| 5 | Input/Output | ⚠️ **mồ côi** | Ghi 4 file `data/signals/monte_carlo_*.parquet`. `monte_carlo_exits` → **0 consumer** trong `src`/`scripts` (chỉ `00_archive/18` đọc). 3 file còn lại chỉ được nhắc trong docstring `src/models/monte_carlo.py`, không có script nào đọc |
| 6 | Tái lập | ✅ | Độc lập (`random_state=42`), chỉ cần `clean_daily_ohlcv.parquet` |
| 7 | Hiệu quả | ❌ | 4 vấn đề, xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**❌ #7 — chi tiết:**

1. **Chạy trên đúng 1 mã.** cell[3]: `symbol = "HPG"`. Kết luận xác suất (`p_target_before_stop`, VaR,
   CVaR) chỉ đúng cho HPG nhưng cell[11] "Monte Carlo Readout" trình bày như một summary card chung.
2. **Tham số base tự mâu thuẫn với scenario grid.** Base dùng `stop_pct=0.01`, `target_pct=0.20`
   → risk/reward **20:1**, một mức stop 1% gần như chắc chắn bị quét bởi nhiễu intraday.
   Nhưng `scenario_grid` ở cell[7] lại chỉ khảo sát 3%–6% stop. Nghĩa là con số được "đọc" ở cell[11]
   nằm ngoài vùng mà chính notebook coi là hợp lý. **Suy luận:** base params là giá trị demo còn sót.
3. **Bootstrap IID** (`bootstrap_price_paths` lấy mẫu `returns` có hoàn lại) → phá vỡ autocorrelation
   và volatility clustering. Với horizon 60 ngày, đây là giả định lạc quan có hệ thống về đường giá
   (đường đi mượt hơn thực tế → xác suất chạm stop bị đánh giá thấp).
4. **Không có benchmark/baseline.** Không so với buy-and-hold hay random-entry cùng horizon.

#### `10_benchmark_diagnostics.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | Markdown giải thích rõ: đối chiếu VNINDEX thật vs `market_proxy`, chỉ ra fallback |
| 2 | Trùng lặp | ✅ | Không |
| 3 | Cell rác | ❌ (cosmetic) | 3/11 code cell trống = 27% |
| 4 | Thứ tự chạy | ✅ | ec = 1..8 |
| 5 | Input/Output | ✅ | Chỉ đọc, không ghi — đúng vai trò diagnostics |
| 6 | Tái lập | ⚠️ | Cần `benchmark_vnindex.parquet` + output backtest của notebook 09 |
| 7 | Hiệu quả | ✅ | Đây là notebook **duy nhất** trong repo chủ động cảnh báo khi benchmark rơi về proxy (cell[8]) — đúng tinh thần |
| 8 | Staleness | ⚠️ **tham chiếu sai** | cell[7] in ra `"No screener backtest summary found. Run notebook 14 or the screen script first."` — nhưng file sinh ra `stealth_accumulation_backtest_summary.parquet` hiện là `03_alpha_signals/09_stealth_accumulation_screen.ipynb`, không phải "notebook 14". Số hiệu này là di sản trước lần đổi tên/tổ chức lại |

**Đây là notebook chất lượng cao nhất folder 02.** Chỉ vướng ❌ cosmetic.

#### `13_advanced_quant_analysis.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "phân tích tương quan nâng cao, momentum và beta" |
| 2 | Trùng lặp | ⚠️ | Chồng lấn với nửa sau `03/12_meta_ranking` (12b): cả hai đều tính `compute_rolling_beta(..., window=60)` + `correlation_heatmap` của top holdings |
| 3 | Cell rác | ✅ | 0 cell trống — sạch nhất repo |
| 4 | Thứ tự chạy | ✅ | ec = 1..9 |
| 5 | Input/Output | ❌ **đọc file mồ côi, đã cũ 1 tháng** | Xem dưới |
| 6 | Tái lập | ⚠️ | Cần `setup_signals.parquet` |
| 7 | Hiệu quả | ⚠️ | Chọn cặp phân tích bằng `top_pairs.iloc[0]` — cặp tương quan cao nhất **trên toàn mẫu**, rồi vẽ rolling correlation của chính cặp đó → selection bias nhẹ. Với notebook diagnostics thì chấp nhận được, nhưng nếu số này lên báo cáo khách hàng thì phải ghi rõ |
| 8 | Staleness | ⚠️ **tham chiếu sai** | cell[3] raise message: `"Khong tim thay input cho notebook 10..."` — nhưng đây là notebook **13** |

**❌ #5 — chi tiết:**

cell[3] đọc `data/processed/stock_features_volatility.parquet`. Grep toàn repo:

- **Không có producer.** Không script nào, không notebook nào ghi file này (notebook 05 ghi
  `stock_features.parquet`, khác tên).
- **Chỉ 2 consumer**, đều là notebook: `02/13` và `04/14_portfolio_construction`.
- **Timestamp trên đĩa: 2026-06-24 22:48** — trong khi `stock_features.parquet` là 2026-07-23 08:36.

Nghĩa là hai notebook đang enrich phân tích bằng `volatility_regime` / `atr_pct_14` / `volatility_percentile`
lấy từ file **cũ hơn 1 tháng, không còn ai sinh ra**. Merge theo `["symbol","date"]` nên với các
ngày sau 2026-06-24, các cột enrich sẽ **toàn NaN mà không báo lỗi** — và ở notebook 14, NaN đó
được xử lý bằng `latest_vol.median()` fallback (cell[4]).

**Tổng kết folder 02:**
- Giữ nguyên vai trò: `10_benchmark_diagnostics` (tốt nhất), `04`, `08` (sau khi sửa params).
- **Chặn gấp:** `05` và `06` — hai notebook này ghi đè trực tiếp file production, và `06` còn ghi
  bằng logic *khác* production (thiếu `benchmark=`).
- `13` không ghi gì nhưng đang đọc file chết → số liệu sai lệch âm thầm.
- Cân nhắc gộp `04` vào `05` (04 là tập con), giữ `04` như notebook giải thích cho khách.

---

### `03_alpha_signals` — 3 notebook

**Mục đích folder:** nghiên cứu tín hiệu breakout, stealth accumulation, và meta ranking / alpha scoring.

#### `07_breakout_research.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ⚠️ | Markdown tiêu đề là **"07b — Breakout Stop-loss And Regime Validation"** nhưng file tên `07_breakout_research.ipynb` — lệch tên |
| 2 | Trùng lặp | ⚠️ | `04/19_validation` cell[9] cũng gọi `run_breakout_research(clean_daily)` — nhưng **với tham số mặc định**, trong khi notebook 07 gọi với `cost=0.004`, `holding_period=20`, lưới stop 5 mức. Hai notebook cùng chạy một nghiên cứu ra hai kết quả khác nhau, không notebook nào nhắc tới notebook kia |
| 3 | Cell rác | ⚠️ | 1/8 code cell trống |
| 4 | Thứ tự chạy | ✅ | ec = 1..7 |
| 5 | Input/Output | ⚠️ | Ghi `data/signals/breakout_20d_*` — có consumer thật (`trade_card_pipeline.py`, `meta_ranking.py`, `freshness_check.py`, `run_daily_pipeline.py`). **Nhưng** `scripts/generate_trade_cards.py` cũng ghi cùng prefix → hai producer |
| 6 | Tái lập | ⚠️ | Fallback 4 tầng path (cell[3]) — chạy được nhưng **kết quả phụ thuộc file nào tồn tại**: `setup_signals` → `stock_features` → `stock_features_full` → `clean_daily_ohlcv`. Bốn input này có feature set khác nhau hoàn toàn, nên cùng một notebook có thể cho ra kết quả rất khác mà chỉ in một dòng `"Loaded features from: ..."` |
| 7 | Hiệu quả | ❌ | Xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**❌ #7 — in-sample parameter selection:**

```python
results = run_breakout_research(features, signal_col="breakout_20d", holding_period=20,
                                cost=0.004, stop_losses=[None,-0.05,-0.07,-0.10,-0.12],
                                atr_multiples=[1.5, 2.0, 2.5])
...
display(pd.DataFrame([results["best_stop_row"]]))
```

Notebook quét **5 mức stop × 3 hệ số ATR = 15 cấu hình trên cùng một mẫu**, rồi lấy `best_stop_row`.
Không có train/test split, không walk-forward, không hiệu chỉnh multiple-testing (Deflated Sharpe /
White's Reality Check). Kết quả "best stop" gần như chắc chắn lạc quan quá mức, và nó được **ghi
xuống `breakout_20d_setup_eligibility.parquet`** rồi chảy tiếp vào trade card và notebook 16
(dùng `win_rate` / `avg_return` từ chính bảng eligibility này để sizing Kelly). Bias được nhân lên
dọc chuỗi.

Ngoài ra: universe là 500 mã **đang niêm yết** (`stock_features.parquet` có đúng 500 symbol,
không có VNINDEX). Không có danh sách mã đã huỷ niêm yết ở bất kỳ đâu trong repo
(`config/delisted_symbols.csv` **không tồn tại** — đã verify) → **survivorship bias không được đo,
cũng không được nêu**.

#### `09_stealth_accumulation_screen.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ❌ **markdown mâu thuẫn code** | Xem dưới |
| 2 | Trùng lặp | ⚠️ | Lặp lại `scripts/run_stealth_accumulation_screen.py` (cùng ghi 8 file `stealth_accumulation_*`) |
| 3 | Cell rác | ⚠️ | 2/15 code cell trống; `load_auto_watchlist_symbols` được import ở cell[2] và **không bao giờ được gọi** |
| 4 | Thứ tự chạy | ⚠️ | ec = 3..15, liên tục |
| 5 | Input/Output | ✅ | Ghi 8 file `data/signals/stealth_accumulation_*`, có consumer thật (`freshness_check.py`, `run_daily_pipeline.py`, `run_meta_ranking.py`, notebook 10) |
| 6 | Tái lập | ⚠️ | Cần `clean_daily_ohlcv` + `stock_features` + `market_features` + `config/screens/stealth_accumulation.yaml` |
| 7 | Hiệu quả | ❌ | Xem dưới |
| 8 | Staleness | ❌ | Markdown mô tả một workflow không còn tồn tại (xem #1) |

**❌ #1 và #8 — markdown nói A, code làm B:**

Markdown cell[0] có tiêu đề **"# 14 — Full Market Scan And Watchlist"** (file là `09_...`) và mô tả:

> "universe full market duoc quet nhe tu notebook 02 · notebook 02 se tu dong tao `auto top 10 watchlist`
> · notebook 14 uu tien scan sau tren `auto top 10` nay · Muc tieu: khong tinh toan nang tren toan bo
> thi truong neu chua can thiet."

Code làm **ngược lại**: cell[5] đặt `scan_input = price_df.copy()` với
`scan_mode = "full_local_market_dataset"`, và cell[6] gọi
`run_stealth_accumulation_screen(price_df=price_df, ...)` — tức truyền **toàn bộ** price_df,
thậm chí không dùng `scan_input` vừa lọc. Hàm `load_auto_watchlist_symbols` (đúng thứ markdown mô tả)
được import nhưng không gọi. `notebook 02` mà markdown nhắc tới hiện nằm trong `00_archive`.

Đây là dạng lệch nguy hiểm: người đọc markdown tin rằng screen chạy trên 10 mã đã lọc trước, thực tế
nó chạy trên cả 500 mã — và ngược lại, `scan_input` (biến được validate cẩn thận ở cell[5], có cả
bảng `scan_summary` để người dùng yên tâm) **bị bỏ rơi hoàn toàn**. Bảng chẩn đoán ở cell[5] đang
mô tả một universe không được dùng.

**❌ #7:**

- `compare_screen_backtests` (cell[11]) chọn top-N theo score tại mỗi ngày rồi đo forward return —
  đây là điểm cộng thật (có `by_date`, có `benchmark_return`, `excess_return`, `beat_benchmark`).
  Nhưng **toàn bộ chuỗi thời gian nằm trong cùng một mẫu** đã dùng để hiệu chỉnh
  `config/screens/stealth_accumulation.yaml`. Không có out-of-sample thật.
- Universe = 500 mã đang niêm yết → survivorship bias, không đo, không nêu.
- `top_n`, `holding_periods`, ngưỡng `watchlist_flag` đều đến từ YAML — tốt cho tái lập, nhưng
  không có ghi chép nào về việc các ngưỡng đó được chọn thế nào.

#### `12_meta_ranking_optimization.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ⚠️ | Markdown nói "kết hợp tín hiệu và điểm số để xếp hạng" — đúng cho nửa đầu. Nửa sau (cell[12] trở đi, "12b — Alpha Research & Scoring System") là **một notebook khác bị dán vào**, không được nhắc trong markdown đầu |
| 2 | Trùng lặp | ⚠️ | Nửa sau lặp `scripts/run_alpha_scoring.py` (cùng ghi `alpha_scores.parquet` + `reports/daily_alpha_ranking.csv` + `reports/top_watchlist.csv`). Chồng lấn beta/correlation với `02/13` |
| 3 | Cell rác | ⚠️ | `import numpy as np` và `load_auto_watchlist_symbols` (cell[2]) không dùng; `pandas`/`Path`/`display` được import lại ở cell[13], cell[23] |
| 4 | Thứ tự chạy | ❌ **lộn xộn nặng** | ec = 3,4,5,6,7,8,9,10,11,12, **15**,16,17,18,19,20, **23,25,27,29,31,33,34**. Đứt ở 13-14, rồi từ 21 trở đi chỉ còn số lẻ. Không thể tin output cache: notebook chưa từng chạy sạch từ đầu tới cuối trong một session |
| 5 | Input/Output | ⚠️ | Ghi `data/signals/alpha_scores.parquet` — file này **có consumer production thật** (`run_daily_pipeline.py`, `run_meta_ranking.py`, `final_watchlist.py`, `freshness_check.py`, `main_visual_dashboard.py`). Cũng ghi `reports/*.csv` trùng path với `run_alpha_scoring.py` |
| 6 | Tái lập | ❌ **không chạy được từ Jupyter** | Xem dưới |
| 7 | Hiệu quả | ❌ | Xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**❌ #6 — cell setup project root bị hỏng:**

```python
PROJECT_ROOT = Path.cwd().resolve().parents[0] if Path.cwd().name == "notebooks" else Path.cwd().resolve()
```

Đây là notebook **duy nhất trong repo** không dùng helper `find_project_root()` (21 notebook còn lại
đều dùng). Hệ quả:

- Mở bằng Jupyter đúng cách (cwd = thư mục notebook = `notebooks/03_alpha_signals`):
  `Path.cwd().name` = `"03_alpha_signals"` ≠ `"notebooks"` → nhánh `else` → `PROJECT_ROOT` =
  `notebooks/03_alpha_signals` → `os.chdir()` vào đó → **mọi path `data/...` đều sai**.
- Chạy qua `scripts/run_all_notebooks.sh` (cwd = project root): vô tình chạy đúng.
- Điều kiện `== "notebooks"` chỉ đúng nếu notebook nằm trực tiếp trong `notebooks/` — cấu trúc
  **trước** lần tổ chức lại thành 6 sub-folder. Đây là code chưa được cập nhật theo layout mới.

`notebooks/README.md` có dặn "Open Jupyter from the project root" — nhưng đó là workaround ngầm,
và nó chỉ đúng nếu người dùng đọc README trước.

**❌ #7 — hai vấn đề:**

1. **cell[31] "Historical Cumulative Returns of Top 5 Alpha Stocks" là biểu đồ gây hiểu lầm.**
   `top_5_symbols = ranking["symbol"].head(5)` — 5 mã có `alpha_score` cao nhất **tại `latest_date`**,
   tức chọn bằng thông tin cuối kỳ. Sau đó vẽ **cumulative return 120 phiên đã qua** của đúng 5 mã đó.
   Biểu đồ này gần như chắc chắn đi lên đẹp, và người xem sẽ đọc nó như "chiến lược alpha đã sinh lời
   thế này" — trong khi nó chỉ nói "mã đang được chấm điểm cao thì vừa tăng giá xong"
   (`momentum_score` là thành phần của `alpha_score`, nên đây gần như là quan hệ vòng tròn).
   Đây là backfill/lookahead illusion điển hình. Không có benchmark trên cùng biểu đồ.
   Với `reports/top_watchlist.csv` được export ở cell[32], rủi ro biểu đồ này lọt vào tài liệu
   khách hàng là có thật.
2. Không có bất kỳ đánh giá out-of-sample nào cho `alpha_score`: không IC/rank-IC theo thời gian,
   không decile spread, không so với equal-weight baseline.

**Tổng kết folder 03:** đây là folder rủi ro cao nhất về mặt phương pháp.
Cả 3 notebook đều **chọn tham số/cấu hình rồi báo cáo kết quả trên chính mẫu đó**, và cả 3 đều ghi
vào artifact production mà pipeline thật đang tiêu thụ. Notebook 12 nên **tách làm hai** (`12_meta_ranking`
và `12b_alpha_scoring`) vì hai nửa không dùng chung biến nào ngoài `read_parquet`.

---

### `04_watchlist_portfolio` — 5 notebook

**Mục đích folder:** xây danh mục, quản trị rủi ro, phân bổ vốn, kiểm định và backtest.

Folder này là một **chuỗi phụ thuộc file**: `14 → 15 → 16`, cộng `19` và `20` đứng riêng.

```
14 ─ selected_portfolio_weights.parquet ─→ 15 ─ risk_overlay_weights.parquet ─→ 16
 └─ portfolio_construction_weights.parquet ─────────────────────────────────→ 19
```

#### `14_portfolio_construction.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "xây dựng danh mục từ watchlist bằng tối ưu hóa Scipy và giả lập Monte Carlo" |
| 2 | Trùng lặp | ⚠️ | Chồng lấn `00_archive/17` (cùng build target weights + overlay) |
| 3 | Cell rác | ⚠️ | Khối import cell[2] có ~45 dòng, trong đó ≥12 symbol không dùng (`maximize_sharpe_ratio`, `efficient_frontier`, `calculate_portfolio_return`, `calculate_covariance_matrix`, `calculate_correlation_matrix`, `calculate_portfolio_variance`, `calculate_risk_contribution`, `check_weight_constraints`, `check_risk_constraint`, `check_sector_constraints`, `check_liquidity_constraints`, `check_turnover_constraint`, `generate_random_weights`, `evaluate_portfolio`, `portfolio_risk_contributions`, `risk_contribution_chart`) |
| 4 | Thứ tự chạy | ⚠️ | ec = 3..15 liên tục |
| 5 | Input/Output | ❌ | Đọc `stock_features_volatility.parquet` — file mồ côi từ **2026-06-24, không có producer** (xem notebook 13). Ghi `selected_portfolio_weights.parquet` + `portfolio_construction_weights.parquet` — **0 consumer trong `src`/`scripts`**, chỉ notebook 15/19 đọc |
| 6 | Tái lập | ⚠️ | Cần `setup_signals` + `breakout_20d_trade_cards` |
| 7 | Hiệu quả | ❌ **nghiêm trọng** | Xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**❌ #7 — ba tầng bias chồng lên nhau:**

**(a) Universe bị hard-code, bỏ qua toàn bộ pipeline alpha.** cell[3]:

```python
user_watchlist = ["NAB","VCB","SAB","STB","POW","SSB","OCB","KLB","MSB","VAB",
                  "MCM","VIB","LAF","BID","MBB","ASP","VIC","BWE","GEG","TCB"]
```

Biến này **không phải `None`**, nên nhánh `elif not latest_trade_cards.empty` (lọc theo `edge_tier`
từ trade card — tức đường đi qua signal thật) **không bao giờ chạy**. 20 mã này phần lớn là ngân hàng
(VCB, STB, SSB, OCB, KLB, MSB, VAB, VIB, BID, MBB, TCB = 11/20), tức danh mục "tối ưu hoá" xuất phát
từ một rổ tập trung ngành nặng, chọn thủ công, không có ghi chép lý do. Comment ngay trên nó nói
"Set to a list of symbols to override, or None to use default trade card candidates" — vậy đây là
giá trị override còn sót lại, **Suy luận** từ một lần thử nghiệm.

**(b) Expected return = trung bình lịch sử toàn mẫu.**
`estimate_expected_returns(return_matrix[symbols], annualized=True)` rồi đưa thẳng vào
`optimize_max_sharpe` / `optimize_max_return_under_risk` / `optimize_min_risk_for_target_return`.
Mean-variance với μ ước lượng từ chính mẫu là bài toán nổi tiếng bất ổn — nhiễu ước lượng bị khuếch
đại thành trọng số cực đoan. Có `shrink_covariance(shrinkage=0.15)` cho Σ nhưng **không có shrinkage
nào cho μ** (không Black-Litterman, không James-Stein).

**(c) Tối đa hoá lựa chọn trên cùng một mẫu — hai lần liên tiếp.**

- cell[8]: sinh **10,000 danh mục ngẫu nhiên**, cell[9] lấy `max_sharpe` trong số đó.
- cell[10]: `generate_sub_portfolios(min_size=3, max_size=5)` — duyệt **mọi tổ hợp 3–5 mã** từ 20 mã
  (C(20,3)+C(20,4)+C(20,5) = 1140+4845+15504 = **21,489 tổ hợp**, mỗi tổ hợp 2 biến thể
  Equal-Weight/Optimized → ~43,000 danh mục), rồi `sort_values("sharpe_ratio").head(1)`.

Chọn Sharpe cao nhất trong ~53,000 ứng viên đánh giá **trên chính chuỗi lợi nhuận đã dùng để ước
lượng μ và Σ** thì Sharpe thắng cuộc gần như hoàn toàn là nhiễu. Không có OOS, không có
Deflated Sharpe Ratio, không có bootstrap CI, không có benchmark VNINDEX ở bất kỳ đâu trong notebook.

**Và kết quả đó được ghi ra file cho hạ nguồn dùng** (cell[13]):

```python
selected_col = "mc_best_concentrated_3_5"
save_parquet(selected_weights, "data/signals/selected_portfolio_weights.parquet")
```

Danh mục **overfit nhất trong toàn bộ 53,000 ứng viên** chính là danh mục được chọn làm output
chính thức, và notebook 15 + 16 xây tiếp trên đó.

#### `15_risk_management.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ⚠️ | Markdown nói "VaR, ES, Beta" nhưng code không tính VaR/ES/Beta trực tiếp — nó gọi `build_portfolio_risk_report` (nội dung phụ thuộc `src/risk/management.py`) và tập trung vào NAV/drawdown/Sharpe stability. Lệch mô tả |
| 2 | Trùng lặp | ⚠️ | 28 dòng chung với `00_archive/17` (cùng chuỗi `apply_symbol_caps → apply_volatility_target → apply_drawdown_overlay → save risk_overlay_weights`) |
| 3 | Cell rác | ⚠️ | `import os, pandas as pd` lặp lại ở cell[3]; `save_parquet` import giữa cell[5] |
| 4 | Thứ tự chạy | ✅ | ec = 1..6 |
| 5 | Input/Output | ⚠️ | Ghi `risk_overlay_weights.parquet` — **0 consumer trong `src`/`scripts`**; chỉ notebook 16, 19 và `00_archive/17`, `00_archive/18` đọc |
| 6 | Tái lập | ⚠️ | Không chạy được nếu notebook 14 chưa chạy (có fallback HRP toàn universe, nhưng fallback đó cho ra danh mục hoàn toàn khác → cùng notebook, hai chế độ, không cảnh báo rõ) |
| 7 | Hiệu quả | ❌ | Xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**❌ #7 — đánh giá in-sample của một bộ trọng số đã được chọn in-sample:**

Notebook nạp `base_weights` từ `selected_portfolio_weights.parquet` (danh mục thắng trong ~53,000
ứng viên ở notebook 14), rồi dựng `return_matrix` từ **cùng `setup_signals.parquet`, cùng khoảng
thời gian** đã dùng để chọn nó, và báo cáo NAV, drawdown, expanding/rolling Sharpe.

Đường NAV và Sharpe hiển thị ở cell[6] vì thế **không phải bằng chứng về chất lượng danh mục** —
chúng là hệ quả toán học của việc chọn max-Sharpe trên chính chuỗi đó. `sharpe_stability_chart`
(expanding vs rolling Sharpe) trông có vẻ là một kiểm định robustness, nhưng cả hai đường đều tính
trên mẫu in-sample nên không phản bác được overfitting.

Ngoài ra: không có benchmark VNINDEX trên biểu đồ NAV; `apply_volatility_target(target_volatility=0.12,
max_gross_leverage=1.25)` và `apply_symbol_caps(max_weight=0.20)` dùng hằng số hard-code không có
nguồn gốc ghi chép.

#### `16_capital_allocation.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "phân bổ vốn chi tiết theo tiêu chuẩn Kelly và quản trị NAV" — khớp code |
| 2 | Trùng lặp | ❌ | **65 dòng code chung (≈47% notebook)** với `00_archive/17_live_watchlist_dashboard.ipynb`. Cả hai chạy `build_capital_plan → align_capital_plan_to_target_weights → save_parquet(..., "data/signals/capital_allocation_plan.parquet")` — **cùng output path**. Archived notebook có thể ghi đè output của notebook active |
| 3 | Cell rác | ⚠️ | `import os, pandas as pd` lặp ở cell[3]; `numpy`, `inspect` import không dùng |
| 4 | Thứ tự chạy | ⚠️ | ec = 2..8 |
| 5 | Input/Output | ⚠️ | Ghi `capital_allocation_plan.parquet` — **0 consumer trong `src`/`scripts`**, chỉ 2 notebook archive đọc |
| 6 | Tái lập | ❌ | cell[6] `raise FileNotFoundError("Empty risk overlay weights! Make sure Notebook 15 was run.")` — bắt buộc notebook 15 chạy trước, mà 15 lại bắt buộc 14 chạy trước. Không thể "Restart & Run All" độc lập |
| 7 | Hiệu quả | ⚠️ | Xem dưới |
| 8 | Staleness | ⚠️ | 2026-07-01 |

**⚠️ #7 — Kelly sizing trên tham số không đáng tin:**

`build_capital_plan(..., p_win_col="win_rate", avg_gain_col="avg_gain_proxy", avg_loss_col="avg_loss_proxy",
kelly_fraction=0.50)` lấy `win_rate` / `avg_return` / `stop_loss` từ
`breakout_20d_setup_eligibility.parquet` — tức từ **`best_stop_row` in-sample của notebook 07**.
Kelly rất nhạy với sai số của p_win: p_win lạc quan 5 điểm phần trăm đủ để size lệch đáng kể.
Có `kelly_fraction=0.50` (half-Kelly) và trần `max_position_pct=0.20` / `max_total_risk_pct=0.018`
làm đệm — đây là điểm cộng thật, nên chấm ⚠️ chứ không ❌.

Điểm cần lưu ý: cell[3] fillna hàng loạt cho "manual watchlist items with missing statistics":
`win_rate → 0.40`, `avg_return → 0.05`, `stop_loss → -0.05`, `trade_edge_score → 50`,
`edge_tier → "Valid Edge"`. Với các mã hard-code ở notebook 14 (NAB, LAF, ASP, VAB, KLB, MCM...) —
phần lớn khó có trade card breakout — sizing sẽ chạy hoàn toàn trên các **hằng số giả định** này
mà bảng kết quả không phân biệt mã nào dùng số thật, mã nào dùng số mặc định.

#### `19_validation_and_stress_test.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | "Kiểm định hệ thống, rà soát data leakage, look-ahead bias và stress testing" |
| 2 | Trùng lặp | ⚠️ | cell[9] gọi lại `run_breakout_research(clean_daily)` với **tham số mặc định**, trùng vai trò notebook 07 nhưng khác cấu hình |
| 3 | Cell rác | ✅ | 0 cell trống, cấu trúc markdown 6 mục rõ ràng |
| 4 | Thứ tự chạy | ❌ | ec = 1,2,3,4,**None**,6,7,8,9. Cell chưa chạy nằm **giữa** notebook — và nó là cell quan trọng nhất (xem dưới) |
| 5 | Input/Output | ⚠️ | Chỉ đọc, không ghi. Đọc `portfolio_construction_weights.parquet` |
| 6 | Tái lập | ⚠️ | Phụ thuộc output notebook 14 |
| 7 | Hiệu quả | ❌ **nghiêm trọng** | Xem dưới |
| 8 | Staleness | ✅ | Sửa 2026-07-08 (`000ca32` "fix(D4): wire bias checks into the automated pipeline, drop mock delisted list") — mới nhất nhì repo |

**❌ #4 — cell kiểm tra leakage chưa từng được chạy.**

cell[7] "Run Leakage Verification" có `execution_count: null` và `outputs: []`. Đây là cell duy nhất
trong toàn repo gọi `check_lookahead_bias()` và `check_data_leakage()`. Notebook mang tên
"Validation & Stress Test", mục 2 tên "Bias & Leakage Checks" — và mục đó **trống**.
Mọi cell sau nó (ec=6,7,8,9) đã chạy, nên đây không phải notebook bị dừng giữa chừng: cell này
bị **bỏ qua có chủ đích hoặc vô ý** trong lần chạy gần nhất.

**❌ #7 — "Out-of-Sample" không phải out-of-sample.**

cell[5]:

```python
w_series = weights_df.set_index("symbol")["max_sharpe"]
port_returns = return_matrix.reindex(columns=w_series.index).mul(w_series, axis=1).sum(axis=1)
segments = {
    "Train (2020-2022)":        port_returns.loc[:"2022-12-31"],
    "Validation (2023-2024)":   port_returns.loc["2023-01-01":"2024-12-31"],
    "Out-of-Sample (2025-2026)": port_returns.loc["2025-01-01":],
}
```

Bộ trọng số `max_sharpe` được notebook 14 tối ưu hoá trên **toàn bộ mẫu 2020–2026**, bao gồm cả
đoạn 2025–2026. Áp trọng số đó lên đoạn 2025–2026 rồi gắn nhãn "Out-of-Sample" là **sai về định
nghĩa**: cả ba đoạn đều in-sample. Một OOS thật phải fit trọng số chỉ trên 2020–2022 rồi mới áp
sang các đoạn sau. Bảng CAGR/Sharpe/MaxDD ở cell[5] vì thế không mang thông tin kiểm định nào,
nhưng lại là **bảng có sức thuyết phục nhất** trong notebook — rủi ro bị trích dẫn ra ngoài là cao.

**Ba vấn đề đi kèm:**

1. **Survivorship bias không được đo.** cell[7]: `config/delisted_symbols.csv` **không tồn tại**
   (đã verify) → nhánh `else` in `"SKIPPED: ... survivorship bias is not being measured."`
   Điểm cộng: notebook nói thẳng là không đo thay vì fake pass — commit `000ca32` đã cố ý bỏ
   mock list. Điểm trừ: cell này chưa chạy nên **ngay cả dòng cảnh báo đó cũng không xuất hiện**
   trong output notebook.
2. **Validate nhầm danh mục.** Notebook 19 dùng cột `max_sharpe` và `max_ret_under_risk` từ
   `portfolio_construction_weights.parquet`. Nhưng danh mục **thực sự chảy xuống notebook 15/16**
   là `mc_best_concentrated_3_5` (qua `selected_portfolio_weights.parquet`). Nghĩa là notebook
   kiểm định đang stress-test một danh mục **khác** với danh mục đang được đề xuất.
3. cell[11] `analyze_performance_by_regime(res["best_fixed_trades"], ...)` — phân tích theo regime
   trên tập trade của **stop tốt nhất in-sample**, tức điều kiện hoá lên chính người thắng cuộc.

#### `20_portfolio_backtester.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | Markdown mô tả rất rõ: rebalance 20 phiên, lọc thanh khoản ≥10 tỷ, MA200, top 5 |
| 2 | Trùng lặp | ✅ | Không |
| 3 | Cell rác | ⚠️ | `import numpy as np` không dùng |
| 4 | Thứ tự chạy | ✅ | ec = 1..6 |
| 5 | Input/Output | ✅ | Chỉ đọc, không ghi |
| 6 | Tái lập | ❌ **BROKEN** | Xem dưới |
| 7 | Hiệu quả | ❌ | Xem dưới |
| 8 | Staleness | ✅ | 2026-07-09 (`31b1710`) — mới nhất repo |

**❌ #6 — notebook hiện KHÔNG chạy được; output đang hiển thị là cache cũ.**

cell[4] gọi `run_portfolio_backtest(...)` **không truyền `benchmark_features=`**.
`src/backtest/portfolio_backtest.py:484-494` có nhánh:

```python
vnindex_rows = df[df["symbol"].str.upper() == "VNINDEX"]
if not vnindex_rows.empty: ...
elif benchmark_features is not None and not benchmark_features.empty: ...
else:
    raise ValueError("run_portfolio_backtest: no benchmark available -- 'VNINDEX' is not a symbol in `features` ...")
```

Đã verify: `data/processed/stock_features.parquet` có **500 symbol, không có VNINDEX**.
Vậy nhánh `else` sẽ chạy → **`ValueError`**. Notebook không thể hoàn tất cell[4], và cell[5]/cell[6]
(equity curve, CAGR, Sharpe, trade log) **đang hiển thị output lưu từ trước khi `src/` đổi**.

Đây đúng là cái bẫy "stale output": đọc file `.ipynb` sẽ thấy kết quả đẹp, đầy đủ, có vẻ vừa chạy —
nhưng chúng không còn tái lập được. Bất kỳ ai trích số CAGR/Sharpe từ notebook này đang trích số
của một phiên bản code không còn tồn tại. **Không sửa** (chế độ read-only), chỉ ghi nhận.

**❌ #7 — hai vấn đề phương pháp:**

1. **`meta_ranking.parquet` là snapshot, không phải panel lịch sử.** Đã verify:
   **500 dòng, 24 ngày phân biệt, min 2022-01-21, max 2026-07-22** — tức mỗi mã đúng 1 dòng, tại
   ngày cuối của riêng nó. Đưa file này vào `run_portfolio_backtest` như nguồn xếp hạng lịch sử
   nghĩa là: tại mỗi ngày rebalance được `meta_ranking` "phủ", điểm số dùng để chọn cổ phiếu được
   tính từ dữ liệu **cuối kỳ** → **look-ahead bias trực tiếp**. Ở các ngày không được phủ, hàm rơi
   về `score_reversal_quality` (docstring dòng 50-52) — nghĩa là backtest chạy trên **hai hệ điểm
   khác nhau** tuỳ ngày, và notebook không hiển thị tỷ lệ ngày nào dùng hệ nào.
2. **Tham số take-profit được chọn sau khi đã thử và loại các phương án khác trên cùng dữ liệu** —
   chính comment trong cell[4] thừa nhận:

   > "Không dùng stop-loss / regime filter / give-back stop -- cả 3 đã thử và đều làm tệ hơn hoặc
   > không giúp gì trên dữ liệu này (report mục 5)."

   Đây là mô tả trung thực của một quy trình **in-sample model selection**. Điểm cộng: có ghi lại
   (nhiều repo giấu bước này). Điểm trừ: kết quả cuối không được điều chỉnh cho số phương án đã thử,
   và `take_profit_pct=0.10` / `trend_break_col="above_ma20"` được trình bày như tham số đã chọn
   chứ không phải "người thắng của một cuộc thi 4 ứng viên".

   Điểm cộng thật của notebook này: **có benchmark VNINDEX trên equity curve** (cell[5]) và
   **có transaction cost 0.15%/chiều** — hai thứ mà notebook 14/15 hoàn toàn thiếu.

**Tổng kết folder 04:** chuỗi `14 → 15 → 16` là **một đường ống khuếch đại overfitting**:
14 chọn danh mục thắng trong ~53,000 ứng viên in-sample → 15 báo cáo NAV/Sharpe của nó trên cùng mẫu →
16 size vốn cho nó bằng win-rate cũng in-sample. Notebook 19 lẽ ra là chốt chặn, nhưng
(a) cell leakage chưa chạy, (b) nhãn "Out-of-Sample" sai, (c) nó validate nhầm danh mục.
Notebook 20 là notebook **có kỷ luật phương pháp tốt nhất folder** (có benchmark, có cost, ghi rõ
quá trình chọn tham số) nhưng đang hỏng.

---

### `05_client_report` — 1 notebook

**Mục đích folder:** notebook đọc artifact đã có sẵn dưới `data/output/` và trình bày cho khách hàng.

#### `01_client_market_report.ipynb`

| # | Tiêu chí | Đánh giá | Bằng chứng |
|---|---|---|---|
| 1 | Mục đích | ✅ | Markdown nói rõ: "khong chay lai pipeline va khong ghi de len output production" + lệnh cần chạy trước |
| 2 | Trùng lặp | ⚠️ | Thay thế `00_archive/18_client_watchlist_report` (đúng như `notebook_inventory.md` ghi). Khác biệt thực chất: 18 đọc thẳng `data/signals/`, 01 đọc `data/output/` do pipeline sinh — thiết kế tốt hơn |
| 3 | Cell rác | ⚠️ | 1 cell trống cuối; `pandas`/`json`/`Path`/`display` được import lại ở cell[23] dù đã import ở cell[1] |
| 4 | Thứ tự chạy | ❌ | ec = 3,5,7,9,11,13,15,17,19,21,**None**,23,**None**. Bước nhảy 2 đơn vị đều đặn + **cell[21] chưa từng chạy** |
| 5 | Input/Output | ✅ | Chỉ đọc `data/output/*` + `data/processed/*`; có `load_parquet_safe`/`load_json_safe` gom `missing_files` và hiển thị — xử lý thiếu file rất tốt |
| 6 | Tái lập | ✅ | `find_project_root()` riêng, kiểm tra `data`+`src`+`scripts`; degrade an toàn khi thiếu input |
| 7 | Hiệu quả | ✅ | Không tự tính alpha, chỉ trình bày. Có cảnh báo `fresh_coverage_ratio < 0.90` và ghi rõ "không nên hiểu là toàn bộ 501 mã đều đã được cập nhật" — minh bạch tốt |
| 8 | Staleness | ✅ | 2026-07-02, là notebook client chính thức theo `notebooks/README.md` |

**❌ #4 — cell[21] chưa chạy:** đó là mục "5. Mã cần kiểm tra dữ liệu trước khi hành động", đọc
`data/output/data_review_watchlist.parquet` và hiển thị **"CẢNH BÁO ĐẶC BIỆT: Phát hiện cổ phiếu lỗi
dữ liệu..."**. Trong một báo cáo gửi khách, cell cảnh báo chất lượng dữ liệu là cell không được phép
trống. Cell[23] (ec=23) sau nó đã chạy → không phải notebook bị cắt ngang.

**Lỗi phụ — chuỗi f-string bị hỏng, hiển thị ra báo cáo khách:** cell[19] có 2 chỗ:

```python
display(Markdown("Cashflow Board output is missing. Run  or add  to the daily pipeline when you want money flow context."))
...
display(Markdown(f"**Warning:** Ngành  có số lượng mã rất nhỏ ({row['n_symbols_with_valid_cashflow']} mã), ..."))
```

Chỗ thứ nhất thiếu tên script (2 khoảng trắng đôi ở "Run  or add  to"), chỗ thứ hai thiếu tên ngành
("Ngành  có số lượng"). **Suy luận:** các placeholder `{...}` đã bị mất trong một lần chỉnh sửa,
hoặc chuỗi thứ nhất từng là f-string và bị bỏ tiền tố `f`. Văn bản lỗi này hiển thị trực tiếp trong
báo cáo khách hàng.

---

### `00_archive` — 6 notebook

**Mục đích folder:** notebook cũ, luồng đã chuyển thành script, và các bản report/dashboard đời trước.

Xác nhận: **cả 6 đều đúng là đã "chết"** về vai trò — không notebook active nào import chúng,
`scripts/run_all_notebooks.sh` loại trừ rõ ràng (`-not -path "notebooks/00_archive/*"`),
và `notebooks/notebook_inventory.md` đã phân loại đúng.

**Nhưng "chết" ≠ "vô hại".** 3/6 notebook vẫn ghi vào path production đang hoạt động:

| Notebook | Phân loại inventory | Ghi vào | Rủi ro |
|---|---|---|---|
| `00_project_overview.ipynb` | ARCHIVE | — | ✅ vô hại. ec = 3,7 (đứt) |
| `02_fetch_daily_ohlcv.ipynb` | CONVERTED_TO_SCRIPT | `data/raw/securities/*.parquet`, **`data/processed/clean_daily_ohlcv.parquet`** | ❌ ghi đè dataset giá gốc. cell[6] còn lưu **420 output** trong file (log bulk fetch) — notebook nặng vô ích |
| `03_clean_validate_data.ipynb` | CONVERTED_TO_SCRIPT | **`data/processed/clean_daily_ohlcv.parquet`** | ❌ ghi đè dataset giá gốc, từ nguồn legacy khác với `generate_features.py` (đọc `data/full_history_v2/raw`) |
| `11_trade_card_generation.ipynb` | CONVERTED_TO_SCRIPT | chỉ đọc | ✅ vô hại |
| `17_live_watchlist_dashboard.ipynb` | ARCHIVE | **`risk_overlay_weights.parquet`**, **`capital_allocation_plan.parquet`**, + `live_dashboard_*` | ❌ **ghi đè output của notebook 15 và 16 đang active** — 65 dòng code chung với notebook 16 |
| `18_client_watchlist_report.ipynb` | ARCHIVE | chỉ đọc | ⚠️ đọc `benchmark_comparison.parquet` và `monte_carlo_scenarios.parquet` — **hai file không tồn tại** trong `data/signals/` → notebook này chắc chắn đã hỏng |

**Tổng kết folder 00:** giữ nguyên vị trí archive. Không có notebook nào cần "cứu".
Điều cần lưu ý là 3 notebook archive vẫn có khả năng phá dữ liệu production nếu ai đó mở và Run All —
archive hiện chỉ là quy ước thư mục, không phải cơ chế bảo vệ.

---

## Bảng tổng hợp toàn repo

Cột **Loại ❌**: `nội dung` = sai logic/bias/hỏng · `cosmetic` = chỉ cell trống.

| Folder | Notebook | Mục đích (1 dòng) | Trạng thái | Loại ❌ | Vấn đề chính | Đề xuất |
|---|---|---|---|---|---|---|
| 01_data_pipeline | `01_validate_environment.ipynb` | Smoke test kết nối SSI FCData | ❌ | cosmetic | 2 cell trống; chồng lấn `check_fcdata_setup.py` | **GIỮ** — xoá cell trống |
| 02_market_research | `04_market_distribution.ipynb` | Skew/kurtosis/tail ratio theo mã | ❌ | cosmetic | 4 cell trống (44%); output `stock_features_distribution` mồ côi | **GIỮ** — cân nhắc GỘP vào 05 |
| 02_market_research | `05_volatility_regime.ipynb` | ATR/realized vol/percentile/regime | ❌ | **nội dung** | Ghi đè `stock_features.parquet` (production) bằng logic hard-code khác config | **CẦN NGƯỜI KIỂM TRA LẠI** — thêm guard hoặc đổi sang path scratch |
| 02_market_research | `06_market_regime.ipynb` | Breadth + entropy + market regime | ❌ | **nội dung** | Ghi đè `market_features.parquet`, và `add_market_regime()` **thiếu `benchmark=`** so với production | **CẦN NGƯỜI KIỂM TRA LẠI — ƯU TIÊN CAO** |
| 02_market_research | `08_monte_carlo_simulation.ipynb` | Mô phỏng đường giá + stop/target | ❌ | **nội dung** | Chỉ 1 mã (HPG); stop 1%/target 20% mâu thuẫn scenario grid; bootstrap IID; không benchmark | **GIỮ** — sửa params, ghi rõ giới hạn |
| 02_market_research | `10_benchmark_diagnostics.ipynb` | Đối chiếu VNINDEX thật vs proxy | ❌ | cosmetic | 3 cell trống; message trỏ "notebook 14" đã đổi tên | **GIỮ** — chất lượng tốt nhất folder |
| 02_market_research | `13_advanced_quant_analysis.ipynb` | Correlation/beta/momentum/divergence | ❌ | **nội dung** | Đọc `stock_features_volatility.parquet` — file **không có producer, cũ từ 2026-06-24** | **CẦN NGƯỜI KIỂM TRA LẠI** — đổi input sang `stock_features.parquet` |
| 03_alpha_signals | `07_breakout_research.ipynb` | Backtest breakout + quét stop/ATR | ❌ | **nội dung** | Chọn `best_stop_row` in-sample trên 15 cấu hình; không OOS; survivorship không đo | **CẦN NGƯỜI KIỂM TRA LẠI LOGIC** |
| 03_alpha_signals | `09_stealth_accumulation_screen.ipynb` | Screen tích luỹ ngầm toàn thị trường | ❌ | **nội dung** | Markdown mô tả workflow "auto top 10" mà code **không thực hiện**; `scan_input` được validate rồi bị bỏ; tiêu đề "# 14" | **CẦN NGƯỜI KIỂM TRA LẠI** — đồng bộ markdown ↔ code |
| 03_alpha_signals | `12_meta_ranking_optimization.ipynb` | Meta ranking + alpha scoring | ❌ | **nội dung** | `PROJECT_ROOT` sai layout → không chạy từ Jupyter; ec lộn xộn nặng; biểu đồ "Top 5 cumulative return" là backfill illusion; 2 notebook dán vào 1 | **TÁCH LÀM 2 + KIỂM TRA LẠI LOGIC — ƯU TIÊN CAO** |
| 04_watchlist_portfolio | `14_portfolio_construction.ipynb` | Tối ưu danh mục (Scipy + MC) | ❌ | **nội dung** | Universe hard-code 20 mã (11 ngân hàng); μ = mean lịch sử; chọn max-Sharpe trong ~53,000 ứng viên in-sample rồi **ghi làm output chính thức** | **CẦN NGƯỜI KIỂM TRA LẠI LOGIC — ƯU TIÊN CAO NHẤT** |
| 04_watchlist_portfolio | `15_risk_management.ipynb` | Overlay rủi ro + NAV/drawdown | ❌ | **nội dung** | Báo cáo NAV/Sharpe in-sample của danh mục đã chọn in-sample; không benchmark | **CẦN NGƯỜI KIỂM TRA LẠI LOGIC** |
| 04_watchlist_portfolio | `16_capital_allocation.ipynb` | Kelly sizing + kế hoạch vốn | ❌ | **nội dung** | Trùng **47% (65 dòng)** với `00_archive/17`, **cùng output path**; Kelly dùng win_rate in-sample; fillna hằng số cho mã thiếu số liệu | **GỘP với `00_archive/17`** (giữ 16, xoá phần trùng ở 17) |
| 04_watchlist_portfolio | `19_validation_and_stress_test.ipynb` | Kiểm định bias + stress test | ❌ | **nội dung** | Cell leakage check **chưa từng chạy**; nhãn "Out-of-Sample" sai (trọng số fit trên toàn mẫu); validate nhầm danh mục | **CẦN NGƯỜI KIỂM TRA LẠI LOGIC — ƯU TIÊN CAO NHẤT** |
| 04_watchlist_portfolio | `20_portfolio_backtester.ipynb` | Backtest rebalance top-5 | ❌ | **nội dung** | **BROKEN**: thiếu `benchmark_features=` → `ValueError`; output đang xem là cache cũ. `meta_ranking` là snapshot → look-ahead | **SỬA (1 dòng) + KIỂM TRA LẠI nguồn ranking** |
| 05_client_report | `01_client_market_report.ipynb` | Báo cáo thị trường cho khách | ❌ | **nội dung** (nhẹ) | Cell cảnh báo chất lượng dữ liệu (cell[21]) chưa chạy; 2 chuỗi f-string hỏng hiển thị ra báo cáo khách | **GIỮ** — sửa 2 lỗi nhỏ, thiết kế tốt nhất repo |
| 00_archive | `00_project_overview.ipynb` | Bản đồ vận hành đời cũ | ✅ (archive) | — | ec đứt (3,7) | **GIỮ ARCHIVE** |
| 00_archive | `02_fetch_daily_ohlcv.ipynb` | Fetch OHLCV từ SSI | ⚠️ (archive) | — | Vẫn ghi `clean_daily_ohlcv.parquet`; 420 output cached | **GIỮ ARCHIVE + cảnh báo ghi đè** |
| 00_archive | `03_clean_validate_data.ipynb` | Làm sạch dữ liệu | ⚠️ (archive) | — | Vẫn ghi `clean_daily_ohlcv.parquet` từ nguồn legacy | **GIỮ ARCHIVE + cảnh báo ghi đè** |
| 00_archive | `11_trade_card_generation.ipynb` | Sinh trade card | ✅ (archive) | — | Chỉ đọc | **GIỮ ARCHIVE** |
| 00_archive | `17_live_watchlist_dashboard.ipynb` | Dashboard watchlist đời cũ | ⚠️ (archive) | — | **Ghi đè output của notebook 15 & 16 active** | **GIỮ ARCHIVE + cảnh báo ghi đè** |
| 00_archive | `18_client_watchlist_report.ipynb` | Report khách đời cũ | ✅ (archive) | — | Đọc 2 file không tồn tại → chắc chắn hỏng | **GIỮ ARCHIVE** |

---

## Top 5 vấn đề nghiêm trọng nhất cần xử lý trước

### 1. Chuỗi `14 → 15 → 16` là một đường ống khuếch đại overfitting, và output của nó được lưu thành artifact

`14_portfolio_construction.ipynb` chọn danh mục "tốt nhất" trong **~53,000 ứng viên**
(10,000 random simplex + ~43,000 tổ hợp con 3–5 mã × 2 biến thể) **đánh giá trên chính chuỗi lợi
nhuận đã dùng để ước lượng μ và Σ**, không OOS, không Deflated Sharpe, không benchmark — rồi ghi
người thắng cuộc ra `data/signals/selected_portfolio_weights.parquet` (cell[13]).
`15` báo cáo NAV/Sharpe của danh mục đó **trên cùng mẫu**; `16` size vốn Kelly cho nó bằng
`win_rate` cũng lấy từ backtest in-sample của notebook 07.

Cộng thêm: universe đầu vào là **20 mã hard-code** (11/20 là ngân hàng), khiến nhánh chọn ứng viên
từ trade card thật không bao giờ chạy.

**Ảnh hưởng:** mọi con số hiệu năng danh mục trong folder 04 hiện không có giá trị dự báo.
**Hành động đề xuất:** đặt `user_watchlist = None`; tách fit/evaluate theo thời gian; thêm benchmark
VNINDEX vào mọi bảng so sánh; nếu vẫn muốn giữ bước quét tổ hợp thì báo cáo kèm Deflated Sharpe.

### 2. `19_validation_and_stress_test.ipynb` — chốt chặn kiểm định đang không hoạt động

Đây là notebook duy nhất có nhiệm vụ bắt bias, và cả ba chức năng chính đều hỏng:

- Cell "Run Leakage Verification" (cell[7]) có `execution_count: null` — **chưa từng chạy**.
  `check_lookahead_bias` / `check_data_leakage` không được gọi ở bất kỳ đâu khác trong repo.
- Bảng "Out-of-Sample (2025-2026)" dùng trọng số `max_sharpe` **đã fit trên toàn bộ 2020–2026**
  → không phải OOS, chỉ là in-sample được gắn nhãn sai.
- Notebook stress-test cột `max_sharpe`, trong khi danh mục **thực sự** chảy xuống 15/16 là
  `mc_best_concentrated_3_5`. Validate nhầm đối tượng.
- Survivorship bias: `config/delisted_symbols.csv` không tồn tại → không đo. (Notebook trung thực
  in "SKIPPED" thay vì fake pass — nhưng vì cell chưa chạy, ngay cả dòng SKIPPED cũng không hiện.)

**Ảnh hưởng:** repo hiện **không có bằng chứng nào** rằng pipeline sạch look-ahead/leakage.

### 3. Notebook ghi đè trực tiếp artifact production, bằng logic khác với script — nguy hiểm nhất là `06_market_regime`

Không có `production_guard` trên branch này (đã verify). 8 notebook ghi vào path mà
`scripts/generate_features.py` / `run_alpha_scoring.py` / `run_stealth_accumulation_screen.py`
cũng ghi, và `scripts/run_all_notebooks.sh` chạy tất cả chúng `--inplace` trên `data/` thật.

Trường hợp cụ thể nhất:

```
notebook 06 cell[3]:      market = add_market_regime(breadth)
generate_features.py:104: market = add_market_regime(breadth, benchmark=benchmark)
```

Comment trong script nói rõ benchmark là bắt buộc cho `crash_severity` / `breakout_signal`.
Chạy notebook 06 → `market_features.parquet` bị thay bằng regime tính thiếu VNINDEX,
**âm thầm**, và mọi consumer hạ nguồn dùng regime kém chất lượng đó.

Tương tự với `05` → `stock_features.parquet` (hard-code cửa sổ thay vì đọc `strategy_config.yaml`),
và `00_archive/17` → ghi đè `risk_overlay_weights.parquet` + `capital_allocation_plan.parquet`
của notebook 15/16 đang active.

### 4. `20_portfolio_backtester.ipynb` đang hỏng nhưng vẫn hiển thị kết quả đẹp (stale output)

cell[4] thiếu `benchmark_features=` → `src/backtest/portfolio_backtest.py:484` raise `ValueError`
("no benchmark available — 'VNINDEX' is not a symbol in `features`"). Đã verify
`stock_features.parquet` có 500 symbol và **không có VNINDEX**.

Nhưng file `.ipynb` vẫn chứa equity curve, CAGR, Sharpe, trade log từ lần chạy trước khi `src/` đổi.
Ai mở notebook sẽ thấy một backtest hoàn chỉnh, có benchmark, có transaction cost — và không có dấu
hiệu nào cho biết nó không còn tái lập được.

Kèm theo: `meta_ranking.parquet` được dùng làm nguồn xếp hạng lịch sử nhưng thực chất là **snapshot**
(500 dòng = 1 dòng/mã, 24 ngày phân biệt) → tại các ngày được phủ, việc chọn cổ phiếu dùng điểm tính
từ dữ liệu cuối kỳ = **look-ahead trực tiếp**.

### 5. Markdown mô tả sai code ở 2 notebook alpha, và 1 file input đã chết 1 tháng vẫn đang được đọc

**(a) `09_stealth_accumulation_screen.ipynb`** — markdown (tiêu đề "# 14 — Full Market Scan") mô tả
quy trình "notebook 02 tạo auto top 10 → scan sâu trên top 10 đó, không tính nặng trên toàn thị trường".
Code làm ngược lại: `run_stealth_accumulation_screen(price_df=price_df, ...)` truyền **toàn bộ**
price_df; biến `scan_input` (được lọc và validate cẩn thận ở cell[5], kèm bảng `scan_summary` cho
người dùng yên tâm) **không được dùng ở đâu cả**; `load_auto_watchlist_symbols` import rồi bỏ.
Bảng chẩn đoán đang mô tả một universe không tồn tại trong lần chạy thật.

**(b) `12_meta_ranking_optimization.ipynb`** — cell "Historical Cumulative Returns of Top 5 Alpha
Stocks" chọn 5 mã bằng `alpha_score` **tại ngày cuối** rồi vẽ lợi nhuận tích luỹ **120 phiên đã qua**
của chúng. Vì `momentum_score` là thành phần của `alpha_score`, biểu đồ này gần như tất yếu đi lên
và sẽ bị đọc nhầm thành bằng chứng hiệu quả. Không có benchmark. Notebook cũng export
`reports/top_watchlist.csv` nên đường ra tài liệu khách hàng là có thật.

**(c) `stock_features_volatility.parquet`** — **không có producer** ở bất kỳ đâu trong `src/`,
`scripts/` hay notebook nào; timestamp **2026-06-24**, trong khi `stock_features.parquet` là
2026-07-23. Vậy mà `02/13` và `04/14` vẫn đọc nó để enrich `volatility_regime` / `atr_pct_14` /
`volatility_percentile`. Merge theo `["symbol","date"]` → mọi ngày sau 2026-06-24 nhận **NaN im lặng**,
và ở notebook 14 số NaN đó được lấp bằng `latest_vol.median()`.

---

## Ghi chú về phạm vi audit

- **Không sửa, không xoá, không chạy** bất kỳ notebook nào. Toàn bộ kết luận rút từ đọc JSON cấu
  trúc cell + code cell (không load output), `git log`, `grep` trên `src/`/`scripts/`, và đọc metadata
  parquet (chỉ đọc, không ghi).
- Trạng thái `execution_count` được đọc trực tiếp từ file `.ipynb` — phản ánh lần chạy gần nhất đã
  được lưu, không phải khả năng chạy hiện tại.
- Các phát biểu về "file không tồn tại" / "không có consumer" đã được verify bằng `ls` và
  `grep -rl` trên `src/` + `scripts/` tại thời điểm audit.
- Vì `data/` không được commit, việc kiểm tra file dữ liệu thực hiện trên repo chính
  `/Users/jamesb/Desktop/vietnam-quant-research/`, không phải trong worktree.
