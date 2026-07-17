# IMPLEMENTATION PLAN — Remediation `vietnam-quant-research`

Nguồn: `docs/reports/codebase_audit/docs/reports/codebase_audit/AUDIT_REPORT.md` (40 phát hiện). Trạng thái: **CHỜ DUYỆT — chưa sửa file nào.**

Nguyên tắc thực thi đã cam kết: fix tối thiểu đúng trọng tâm; mỗi cụm fix = 1 commit `fix(<mã>): ...`; mỗi fix logic tài chính kèm test reproduce-bug-trước-fix-sau; không bịa dữ liệu — thiếu dữ liệu thì fail loudly.

---

## 0. Điều chỉnh so với wave gợi ý (và lý do)

Giữ nguyên khung 5 wave của yêu cầu, với 3 điều chỉnh:

1. **G2 chuyển từ Wave 4 → Wave 3** (đi cùng nhóm backtest realism): stealth backtest dùng benchmark để tính excess return — sửa market proxy cùng lúc với sửa backtest tránh phải chạy lại verify 2 lần trên cùng module `stealth_accumulation.py`.
2. **G3 (đồng bộ ngày per-symbol) thêm vào Wave 5** dưới dạng contract test + warning (audit xếp Medium nhưng fix rẻ, cùng chỗ với J3).
3. **G6 (synergy double-count) gộp vào Wave 4** cùng file `meta_ranking.py` với G1/G5 — 1 commit riêng nhưng cùng đợt sửa file đó.

**Phát hiện kiến trúc quan trọng cho F1** (đã xác minh code trước khi lập plan): `build_cashflow_board()` gồm 2 phần tách được — `compute_symbol_cashflow_metrics()` **chỉ cần** `stock_features` + `sector_map` (không cần tier watchlist); chỉ `build_watchlist_cashflow_confirmation` mới cần 3 tier frames. Ngoài ra `apply_post_cashflow_overlay()` đã tồn tại sẵn ở `final_watchlist.py:925`. → F1 đi theo **Plan A (tách 2 giai đoạn)**, không cần Plan B (chỉ harden gate).

---

## WAVE 1 — Chặn thiệt hại đầu ra khách hàng

Độc lập hoàn toàn với hạ tầng. 4 commit. ~4 file code + 1 CSV + 4 file test. Rủi ro: THẤP (không đụng pipeline order).

### 1.1 `fix(I1)`: rule CONFIRMED phải đồng thuận label + state + vol_ratio

- **File/dòng**: `src/analytics/cashflow_board.py:544-560` (nhánh tier `client_ready`), `560-580` (tier `trading_watchlist`); `src/reporting/research_notes.py:162-199` (thesis generator).
- **Thay đổi**:
  ```
  # TRƯỚC (client_ready):
  elif label == "IMPROVING": status = "CONFIRMED"  # không nhìn state/vol_ratio
  # SAU:
  elif label == "IMPROVING":
      if state in ("WEAK_FLOW", "DRY_UP_WATCH") or vol_ratio < 0.7:
          status = "WATCH"
          reason = "Mâu thuẫn tín hiệu: label IMPROVING nhưng state {state}, volume ratio {x}x — hạ về theo dõi."
      else: status = "CONFIRMED"
  ```
  Thêm guard tổng quát cuối hàm: mọi status thuộc nhóm CONFIRMED* mà `vol_ratio < 0.7` hoặc `state == "WEAK_FLOW"` → hạ về WATCH kèm reason nêu rõ mâu thuẫn. Tier `trading_watchlist` nhánh `label in (STRONG, IMPROVING)` áp cùng guard.
  `research_notes.py`: thesis chọn theo **cặp (label, state)** — nếu status sau guard là WATCH thì dùng template trung tính ("cần thêm xác nhận dòng tiền"), không dùng template "cải thiện tích cực".
- **Test** (`tests/test_cashflow_board.py` mở rộng): fixture row label=IMPROVING, state=WEAK_FLOW, vol_ratio=0.10, tier=client_ready → assert code cũ trả CONFIRMED (reproduce, sẽ xoá assert này sau khi fix), code mới trả WATCH + reason chứa "Mâu thuẫn". Case đối chứng: label=IMPROVING, state=CONFIRMED_INFLOW, vol_ratio=1.2 → vẫn CONFIRMED.
- **Rủi ro phụ / downstream**: VIC và các mã tương tự đổi CONFIRMED→WATCH; research notes đổi giọng; eligibility gate KHÔNG đổi (gate chỉ reject CHECK_REQUIRED/REJECT, WATCH không reject) → watchlist không ngắn đi vì fix này.

### 1.2 `fix(I2)`: sửa sector map các mã vốn hoá lớn

- **File**: `config/sector_map.csv`.
- **Thay đổi**: `VIC` → `Real Estate` (industry: Diversified conglomerate / real estate), `VHM` → `Real Estate`, `VRE` → `Real Estate` (Vincom Retail — vận hành TTTM, chuẩn phân loại BĐS bán lẻ). Cột `source` → `manual review 2026-07-08`, `updated_at` cập nhật. Rà nhanh thêm ~top-30 vốn hoá trong file (chỉ sửa khi chắc chắn sai, ghi hết vào commit message). 18 mã UNKNOWN: **giữ nguyên UNKNOWN** (không bịa), liệt kê trong plan-note để bổ sung sau.
- **Test** (`tests/test_sector_board.py` mở rộng): đọc CSV, assert VIC/VHM/VRE == "Real Estate"; assert không mã nào trong top watchlist (30 mã core) có sector UNKNOWN.
- **Downstream**: sector board xếp lại; ngành "Financial Services" mất 2 mã lớn → sector cashflow rank đổi; research notes đổi câu "trong ngành ..."; cap `max_names_per_sector` có thể đổi mã được chọn.

### 1.3 `fix(H3)`: gỡ Kelly sai tham số — fail loudly khi thiếu thống kê thua lỗ thật

- **File/dòng**: `scripts/build_portfolio_stack.py:220-227`; `src/capital/management.py:275-288`.
- **Thay đổi**:
  ```
  # TRƯỚC: avg_loss_col="median_return"
  # SAU:  avg_loss_col="avg_loss" (chỉ kích hoạt khi cột tồn tại thật từ trade cards)
  ```
  Trong `build_capital_plan`: thêm guard — nếu giá trị avg_loss truyền vào **≥ 0** (không phải thống kê thua lỗ) → `kelly_risk = None` + append warning `"Kelly disabled for {sym}: avg_loss input is non-negative"` vào cột warning của plan. KHÔNG tự chế avg_loss từ dữ liệu khác (nguyên tắc 5).
- **Test** (`tests/test_portfolio_risk_capital.py` mở rộng): candidate có win_rate=0.6, avg_return=0.05, median_return=0.03 → code cũ: `kelly_scale != 1` (reproduce misfire); code mới: kelly bị tắt, sizing rơi về ATR/conviction, có warning. Case đối chứng: avg_loss=-0.04 thật → Kelly hoạt động.
- **Downstream**: `capital_plan.parquet` — cột kelly_scale về 1.0 cho hầu hết mã (vì hiện không có avg_loss thật); position sizes đổi; "Tỷ trọng gợi ý" trong research notes đổi. **Đây là thay đổi ĐÚNG, không phải regression.**

### 1.4 `fix(H1,H2)`: inverse-vol dùng vol thật; allocator fallback phải khai thật

- **File/dòng**: `scripts/build_portfolio_stack.py:165-184, 211`.
- **Thay đổi**:
  ```
  # H1 TRƯỚC: ["atr_pct_14" if ... else "final_score"]
  # H1 SAU:
  if "atr_pct_14" in candidates.columns: latest_vol = ...atr_pct_14...
  else:
      latest_vol = return_matrix.std(ddof=0) * sqrt(252)   # realized vol per symbol, luôn có sẵn
      warnings.append("atr_pct_14 missing; using realized vol from return matrix")
  # H2 TRƯỚC: except Exception: allocations[name] = equal_weight(...)  (im lặng)
  # H2 SAU:
  fallback_used: set[str]; trong except: fallback_used.add(name); warnings.append(f"{name} allocation failed: {exc}; equal-weight substituted")
  risk_report["allocator_used"] = "risk_parity" if "risk_parity" not in fallback_used else "equal_weight (risk_parity FAILED)"
  weights_table thêm cột allocation_fallbacks = ",".join(fallback_used)
  ```
- **Test**: (H1) candidates không có atr_pct_14, return matrix 2 mã vol khác nhau rõ → code cũ: mã final_score cao nhất nhận trọng số inverse-vol nhỏ nhất (reproduce); mới: trọng số tỉ lệ nghịch realized vol. (H2) monkeypatch `risk_parity_allocation` raise → metadata chứa warning + allocator_used chứa "FAILED".
- **Downstream**: cột `inverse_volatility` trong portfolio_weights đổi khi thiếu ATR; risk report trung thực hơn — có thể lộ ra rằng risk_parity từng fail âm thầm trước giờ.

---

## WAVE 2 — Nền pipeline

4 commit. ~5 file code + 1 shell + tests. Rủi ro: **TRUNG BÌNH-CAO** (đụng thứ tự pipeline & semantics scope). Yêu cầu chạy verify offline sau wave.

### 2.1 `fix(F1)`: cashflow board (symbol-level) chạy TRƯỚC meta ranking; gate không còn fallback "OK" âm thầm

- **File/dòng**: `scripts/run_daily_pipeline.py:37-77` (PIPELINE_STEPS), `858-869`; `scripts/build_cashflow_board.py` (thêm mode `--symbol-only`); `src/screening/final_watchlist.py:148-162` (gate load), `825-905` (apply_eligibility_gate).
- **Thay đổi** (Plan A — đã xác minh khả thi):
  1. `build_cashflow_board.py` thêm flag `--symbol-only`: chỉ chạy `attach_sector` + `compute_symbol_cashflow_metrics` + ghi `cashflow_board.parquet` (không cần tier frames).
  2. `PIPELINE_STEPS` chèn step mới `build_cashflow_board_symbols` (`--symbol-only`) **ngay sau `generate_features`, trước `run_meta_ranking`** — thành step mặc định, không còn opt-in.
  3. Sau `run_meta_ranking`: step `build_cashflow_board` (full — confirmation theo tier + `apply_post_cashflow_overlay`) cũng thành mặc định (giữ flag `--skip-cashflow` cho ai muốn tắt, thay vì opt-in như hiện tại).
  4. `apply_eligibility_gate`: khi `cashflow_board.parquet` **thiếu** hoặc `latest_date < analysis_as_of` → KHÔNG mặc định `cf_status="OK"` nữa; thay bằng `cashflow_data_status="UNVERIFIED_STALE_ARTIFACT"`, mã liên quan bị **demote khỏi client_ready xuống trading_watchlist** (không REJECT hẳn — tránh watchlist rỗng), kèm warning vào watchlist_metadata.json.
  5. Cập nhật `docs/OPERATIONS.md` quy trình 8 bước → thêm bước board (fix luôn lỗ hổng tài liệu đã nêu trong F1).
- **Test** (`tests/test_pipeline_helpers.py` + test mới `tests/test_pipeline_contracts.py`): (a) assert vị trí step: index(`build_cashflow_board_symbols`) < index(`run_meta_ranking`) trong steps resolved; (b) gate với board stale 1 ngày → symbol bị demote + status UNVERIFIED (code cũ: ELIGIBLE với cf_status OK — reproduce); (c) board cùng ngày → hành vi như cũ.
- **Downstream**: **client_ready có thể ngắn lại** trong các lần chạy mà board chưa build kịp/lỗi — đây là chủ đích. Pipeline chạy lâu hơn ~1 step. Lần chạy đầu sau fix: nhiều mã có thể bị demote nếu board hiện tại đứng ở ngày cũ.

### 2.2 `fix(B1)`: scope `full` = danh sách niêm yết thật; tên trung thực cho scope cũ

- **File/dòng**: `scripts/update_daily_data.py:38-51, 84`; `scripts/run_daily_pipeline.py:736`; `src/validation/freshness_check.py:365` (choices).
- **Thay đổi**:
  ```
  # SAU:
  def get_full_universe_symbols(base_dir):
      files = glob("data/raw/securities/*.parquet")
      if not files: raise SystemExit("No securities lists found. Run scripts/update_securities.py first (requires SSI creds).")
      symbols = union các cột symbol, lọc qua filter_primary_equity_symbols (bỏ CW/ETF/bond, giữ mã 3 ký tự)
      return sorted(symbols)
  def get_tracked_universe_symbols(...):  # logic self-referential CŨ, đổi tên trung thực
  ```
  Scope mới: `core` (như cũ) / `tracked` (= "full" cũ, tự tham chiếu) / `full` (= securities thật, fail loudly nếu thiếu) / `batch` (chia theo full mới) / `custom`. `--update-scope` các script đồng bộ choices.
- **Test** (`tests/test_freshness_check.py` mở rộng): tmp_path với securities parquet giả (HOSE=[AAA,BBB], HNX=[CCC]) → full trả [AAA,BBB,CCC]; không có file → SystemExit có hướng dẫn; scope tracked giữ hành vi cũ.
- **Downstream**: `--scope full` giờ NGỪNG chạy được cho tới khi user chạy `update_securities.py` (cần SSI credentials — **dependency dữ liệu ngoài, cần bạn xác nhận có creds**). Sau khi có universe thật (~1600+ mã): thời gian fetch tăng mạnh (đã có sẵn batch mode + rate limit sleep), **toàn bộ phân phối rank/score đổi** (xem bảng expected changes).

### 2.3 `fix(B2)`: freshness so với lịch giao dịch thực tế

- **File/dòng**: `src/validation/freshness_check.py:213-250`; `scripts/update_daily_data.py:139-148` (persist `market_latest_date`).
- **Thay đổi**:
  1. `update_daily_data.py`: ghi `market_latest_date` (đã detect từ VNINDEX) vào `update_daily_data_summary.json`.
  2. `freshness_check.py`: thêm `expected_trading_date(now)` = ngày làm việc T2-T6 gần nhất theo `Asia/Ho_Chi_Minh`, trừ các ngày trong `config/vn_market_holidays.csv` **nếu file tồn tại** (tạo file với các ngày lễ cố định đã biết chắc: 01/01, 30/04, 01/05, 02/09±1 — Tết âm lịch để trống kèm comment hướng dẫn tự thêm; không bịa ngày âm lịch).
  3. `evaluate_freshness`: ưu tiên baseline = `market_latest_date` từ summary (nếu có, tuổi < 7 ngày); so `baseline_data_date` với `expected_trading_date`: lệch 1 ngày giao dịch → WARNING "dataset frozen?", ≥ 2 → ERROR. Giữ nguyên toàn bộ logic per-symbol hiện có (chạy sau lớp mới).
- **Test**: freeze clock thứ Tư, data max = thứ Hai → ERROR; data max = thứ Ba → OK; thứ Hai với data max = thứ Sáu → OK (cuối tuần).
- **Downstream**: **với dữ liệu hiện tại trong repo (đứng 2026-07-02), freshness sẽ báo ERROR ngay sau fix** — đúng chủ đích, không phải hỏng. Ngày lễ chưa khai báo → false WARNING (chấp nhận, đã ghi chú cách thêm).

### 2.4 `fix(J1)`: notebook runner hết green-light giả

- **File**: `scripts/run_all_notebooks.sh`.
- **Thay đổi**: NOTEBOOKS resolve bằng glob `notebooks/0[1-9]_*/*.ipynb` (loại `00_archive`) sort theo tên; file trong danh sách mà không tồn tại → `exit 1` (bỏ skip-return-0); thêm `--list` in danh sách rồi thoát (phục vụ test); tổng kết cuối in số ran/failed thật.
- **Test** (`tests/test_pipeline_contracts.py`): subprocess `run_all_notebooks.sh --list` → mọi path in ra tồn tại, count ≥ 15, không chứa `00_archive`.
- **Downstream**: chạy full script giờ thực thi notebook thật (lâu); notebook nào vốn đã hỏng sẽ **lộ ra fail thật** — cần chạy ở Phase 4 để biết.

---

## WAVE 3 — Backtest realism

5 commit. ~6 file + config mới `config/vn_market_rules.yaml`. Rủi ro: TRUNG BÌNH (logic tài chính — mỗi fix bắt buộc test reproduce trước).

### 3.1 `fix(D1)`: portfolio backtest quyết định bằng dữ liệu T-1, khớp tại T

- **File/dòng**: `src/backtest/portfolio_backtest.py:90-100`.
- **Thay đổi**:
  ```
  # TRƯỚC: scores_today/features_today lấy tại current_date (T) rồi set holdings tại close T
  # SAU:   decision_date = all_dates[day_idx - 1]; scores/features lấy tại decision_date;
  #        execution giữ tại close T (ngày rebalance). Ngày đầu tiên: bỏ qua rebalance.
  ```
  (Tương đương chuẩn "signal T-1, trade T" — cùng semantics với stealth backtest `entry_delay_days: 1`.)
- **Test** (test mới `tests/test_portfolio_backtest.py`): dựng 2 mã, mã A chỉ vượt ma200/momentum NHỜ dữ liệu ngày T → code cũ chọn A tại T (reproduce look-ahead); code mới không chọn A tại T (chỉ chọn được từ kỳ sau). Assert thêm: tổng NAV cũ ≠ mới trên fixture có gap lớn.
- **Downstream**: **Sharpe/CAGR của notebook 20 GIẢM** — dự báo trước, không phải regression.

### 3.2 `fix(I4)`: trade cards vào lệnh tại open T+1

- **File/dòng**: `src/backtest/engine.py` (thêm `attach_forward_returns_from_next_open`), `src/backtest/breakout_research.py:56-79`, `src/backtest/simulator.py:98-133, 176-213` (entry_price = open của bar i+1, cửa sổ future giữ i+1..i+holding).
- **Thay đổi**:
  ```
  forward_return_open_{h}d = close.shift(-h) / open.shift(-1) - 1   # entry open T+1
  simulator: entry_price = symbol_prices.loc[i+1, "open"] (fallback close i+1 + warning nếu thiếu open)
  breakout_research: dùng cột _open_ variant cho net_return
  ```
- **Test** (`tests/test_quant_tooling.py` mở rộng): fixture có gap open T+1 = close T × 1.05 → avg_return cũ cao hơn mới ~5% (reproduce số cụ thể); stop-loss tính từ entry mới.
- **Downstream**: profit factor / avg_return của trade cards GIẢM, đặc biệt các setup gap mạnh; `edge_tier` một số mã tụt hạng → meta ranking đổi theo.

### 3.3 `fix(I3)`: chọn stop-loss trên train, báo cáo trên validation

- **File/dòng**: `src/backtest/breakout_research.py:73-79` + hàm `run_breakout_research`; `scripts/generate_trade_cards.py` (tiêu thụ kết quả).
- **Thay đổi**: split theo thời gian (mặc định train ≤ 70% timeline, configurable); `select_best_stop` chỉ nhìn train; metrics công bố (profit_factor, avg_return, win_rate trong trade cards) tính trên **validation**; nếu validation < `min_trades` (50) → gắn `edge_tier="Unvalidated"` + action `Watch - Limited Sample` (fail loudly, không im lặng dùng in-sample).
- **Test**: synthetic entries mà stop A tốt nhất nửa đầu, stop B nửa sau → assert stop được chọn = A (train-only) và metrics báo cáo = tính trên nửa sau.
- **Downstream**: edge số liệu giảm/đổi; một số trade cards thành "Unvalidated" → rơi điểm action_score trong meta ranking.

### 3.4 `fix(D2)`: mô hình trần/sàn (heuristic có kiểm soát)

- **File mới**: `config/vn_market_rules.yaml` (bands: HOSE 0.07 / HNX 0.10 / UPCOM 0.15; lot 100; T+2.5 — làm nguồn sự thật chung, C2 dùng lại). **File/dòng sửa**: `src/backtest/simulator.py` (2 hàm backtest), `src/backtest/portfolio_backtest.py` (chặn entry).
- **Thay đổi** (heuristic — không có dữ liệu giá tham chiếu chính thức, ghi rõ trong docstring):
  - Entry: nếu bar vào lệnh có `(open_{T+1}/close_T - 1) ≥ band×0.98` (limit-up gap) → **bỏ lệnh** đó, log `skipped_limit_up`.
  - Exit stop: nếu bar chạm stop có `close==low` và `return_1d ≤ -band×0.98` (sàn cạn thanh khoản) → dời exit sang bar kế tiếp tại close của nó (trượt giá thực tế hơn).
  - Thiếu cột `market` → mặc định band HOSE 0.07 + warning.
- **Test**: synthetic limit-up entry bar → trade bị skip; floor-stop bar → exit price xấu hơn mức stop danh nghĩa.
- **Rủi ro/scope-guard**: nếu lúc implement thấy phải đụng > 3 hàm backtest → dừng, chỉ giữ phần **entry-skip** (giá trị nhất), ghi phần floor-exit vào NEW_FINDINGS/deferred. Downstream: số trade giảm, win_rate đổi.

### 3.5 `fix(G4)`: bỏ clip ±15%; flag corporate action thay vì che

- **File/dòng**: `src/features/returns.py:13-17`.
- **Thay đổi**:
  ```
  # TRƯỚC: return_1d = pct_change.clip(-0.15, 0.15)
  # SAU:
  band = band_limit theo cột market (từ vn_market_rules.yaml; thiếu market → 0.07) + buffer 0.02
  suspect = |raw_return| > band + buffer
  return_1d = raw_return.where(~suspect, np.nan)      # KHÔNG clip — NaN + flag
  df["suspect_corporate_action"] = suspect
  ghi events ra data/output/corporate_action_flags.csv (symbol, date, raw_return) để rà tay
  ```
  NaN lan qua rolling → feature các cửa sổ dính split thành NaN → mã tạm rơi khỏi scoring thay vì mang return giả (fail loudly đúng nghĩa).
- **Test** (`tests/test_features.py` mở rộng): split giả -50% trên mã HOSE → cũ: return_20d nhiễm -15% (reproduce con số); mới: NaN + flag ghi file. Mã UPCOM +15% hợp lệ → GIỮ NGUYÊN 0.15 (cũ: vẫn 0.15 nhưng mã HOSE 8% cũng từng bị… không, HOSE 8% không chạm clip; case chính: UPCOM và split).
- **Downstream**: mã từng split trong lịch sử mất cửa sổ feature quanh ngày split → có thể rơi khỏi rank vài chục phiên quanh sự kiện; backtest bớt các cú "return" giả. **G2 lưu ý**: `market_proxy` mean sẽ tự bỏ NaN — an toàn.

### 3.6 `fix(G2)`: VNINDEX thật làm market proxy trong stealth screen

- **File/dòng**: `src/screening/stealth_accumulation.py:413-421` (market proxy), vùng sector proxy ngay dưới.
- **Thay đổi**: nếu `data/processed/benchmark_vnindex.parquet` khả dụng (truyền vào qua tham số `benchmark_df` — hàm run đã nhận benchmark cho backtest, mở rộng dùng cho proxy) → `market_proxy_return_1d/20d` = return VNINDEX; thiếu → giữ equal-weight proxy + cột mới `market_proxy_source="internal_equal_weight"` + warning. Sector RS: ngành có `< 3` mã → `sector_relative_strength_20d = NaN` và thành phần sector trong score nhận neutral 50 kèm flag `sector_rs_reliable=False` (không tự so chính mình).
- **Test** (`tests/test_stealth_accumulation.py` mở rộng): có benchmark → proxy đúng bằng benchmark return (assert từng giá trị); ngành 1 mã → sector RS NaN (cũ: 0.0 — reproduce).
- **Downstream**: relative_strength_score đổi cho toàn bộ mã (nhất là ngân hàng — trước giờ được so với chính nhóm mình); watchlist stealth đổi thành phần.

---

## WAVE 4 — Chất lượng điểm số & minh bạch

4 commit. ~4 file. Rủi ro: THẤP-TRUNG BÌNH.

### 4.1 `fix(C1)`: min_price đúng đơn vị VND

- `src/screening/final_watchlist.py:57`: `5.0` → `5000.0`; `config/screens/stealth_accumulation.yaml`: `10.0` → `10000.0`. Grep toàn config/src tìm ngưỡng giá cùng lỗi đơn vị (đã biết 2 chỗ này; nếu thấy thêm → cùng commit).
- **Test**: mã close 3,000 VND → fail `valid` mask ở `_mark_filters` (cũ: pass — reproduce).
- **Downstream**: với universe 30 blue-chip hiện tại: không đổi gì (đều > 10k). Sau B1 (universe thật): penny < 5k bị chặn — chủ đích.

### 4.2 `fix(G1)`: minh bạch rank tương đối + sàn tuyệt đối cho Client Ready

- `src/alpha/scoring.py`, `src/analytics/meta_ranking.py`: thêm cột `rank_universe_size` vào output. `src/screening/final_watchlist.py` `_reason_text`/columns: thêm `(rank trong N mã)` vào reason + cột mới trong FINAL_WATCHLIST_COLUMNS. Sàn tuyệt đối: điều kiện client_ready thêm `excess_return_20d ≥ 0` (cột đã tồn tại — đang chỉ là warning "Weak relative strength" phạt 8 điểm) — chuyển từ soft-penalty thành hard-demote xuống trading tier.
- **Test** (`tests/test_final_watchlist.py` mở rộng): mã final_score 70 nhưng excess_return_20d < 0 → cũ: Client Ready với warning (reproduce — đúng case SAB/BID trong CSV hiện tại); mới: demote trading tier.
- **Downstream**: **SAB, BID rơi khỏi Client Ready** (nhìn thấy ngay trong final_watchlist.csv hiện tại — 2 mã này đang có warning "Weak relative strength"); client_ready ngắn lại ~2 mã.

### 4.3 `fix(G5,G6)`: thiếu evidence thì cap bucket; bỏ double-count

- `src/analytics/meta_ranking.py`: (G5) thêm `evidence_coverage` = tỷ lệ nguồn có dữ liệu thật (features/trade_card/stealth); nếu thiếu ≥ 2 nguồn → `priority_bucket` cap tối đa "Secondary Watchlist" + cột `insufficient_evidence=True` (giữ default 50 trong công thức để không phá scale, nhưng bucket bị cap). (G6) bỏ 3 dòng cộng action-label trong `synergy_bonus` (đã tính trong action_score).
- **Test**: mã chỉ có features (không trade card/stealth) mà meta_score 78 → cũ: "Prime Candidate" (reproduce); mới: cap Secondary + flag. Synergy: mã action="Valid Breakout Setup" → meta_score mới < cũ đúng 3.0 điểm.
- **Downstream**: vài mã tụt bucket; meta_score nhóm breakout giảm ~3-4.5 điểm đồng loạt.

### 4.4 `fix(C2)`: ngưỡng theo đặc thù VN (dùng vn_market_rules.yaml từ 3.4)

- `config/screens/stealth_accumulation.yaml` backtest: `holding_periods` bỏ 5 → thay bằng min 5 ngày thực tế? KHÔNG — giữ holding 5/10/20 nhưng thêm ghi chú T+2.5: cost model thêm dòng `min_holding_constraint_days: 3` và backtest loại các exit < 3 phiên (bán trước khi hàng về là không thể). Chỉ sửa mức này — không đụng thêm ngưỡng khác nếu chưa có universe thật (C3 chỉ verify được sau B1, để Phase 4 đo funnel).
- **Test**: trade có exit ngày thứ 2 → bị loại/dời sang ngày 3.
- **Downstream**: một ít trades ngắn hạn biến mất khỏi thống kê holding-5d.

---

## WAVE 5 — Hạ tầng chất lượng & dọn dẹp

4 commit. Rủi ro: THẤP.

### 5.1 `fix(J3,G3,D5)`: contract tests + gate look-ahead tự động

- **File mới** `tests/test_pipeline_contracts.py` (gom các contract test đã tạo rải rác ở wave trước + bổ sung):
  - Step order (F1), gate-stale (F1), scope-full-fail-loudly (B1), freshness frozen (B2), notebook list (J1) — đã viết ở các wave, gom về đây.
  - (G3) `prepare_meta_ranking_dataset`: nếu chênh lệch date giữa các nguồn per-symbol > 3 ngày → cột `signal_age_warning` + test.
  - (D5) util mới `src/validation/guards.py: assert_no_forward_columns(df, context)` — gọi trong `save_meta_ranking_outputs`, `save_watchlist_outputs`, `_score` của final_watchlist: nếu input chứa cột `forward_*`/`future_*` → **drop + warning** khi save, **raise** khi scoring. Test cả 2 nhánh.
- **File sửa**: `src/analytics/meta_ranking.py`, `src/screening/final_watchlist.py` (chèn guard).

### 5.2 `fix(D4)`: bias-check chạy thật trong pipeline, bỏ mock

- `scripts/run_daily_pipeline.py`: thêm step nhẹ `validate_biases` sau generate_signals: chạy `check_lookahead_bias` trên các cột mà **consumer** dùng (whitelist forward trong setup_signals cho research), fail → WARNING trong metadata. Notebook 19 cell 7: bỏ `mock_delisted = ["FLC","ROS","ART"]` → đọc `config/delisted_symbols.csv` nếu có, không có thì in `"SKIPPED: no real delisted data (see AUDIT D3)"` — không fake pass.
- **Test**: metadata sau run chứa key `bias_checks`.

### 5.3 `fix(J2,A2,H6,B4,H4)`: dọn rác & bỏ giá trị bịa

- Xoá `Monte Carlo Pipeline.py` + `monte_carlo_static.png` (root — orphan copy ngoài, yfinance không có trong requirements). 
- `scripts/run_meta_ranking.py`: bỏ đọc `auto_watchlist_top10.parquet` không dùng + dòng lặp `candidate_symbols = None`.
- (A2) xoá các mục checkpoint đã liệt kê DELETE_CANDIDATE nếu còn trên đĩa; cập nhật `notebook_inventory.md`.
- (H6) `build_portfolio_stack.py`: NAV đọc `strategy_config.yaml: portfolio.nav` (thiếu → 1e9 + warning ghi vào metadata).
- (B4) `run_daily_pipeline.py:679`: bỏ `or 501` → dùng count từ securities thật (sau B1) hoặc `None` + warning.
- (H4) `src/portfolio/input_resolver.py:62-67`: bỏ `vol = 100000.0` → thiếu cột volume = lý do reject `VOLUME_DATA_MISSING` (fail loudly).
- **Test**: input_resolver với frame không có cột volume → mã bị reject với lý do đúng (cũ: pass với vol bịa — reproduce).

### 5.4 Ghi nhận DEFERRED (chờ quyết định của bạn — KHÔNG làm đợt này)

| Mã | Lý do defer | Đề xuất |
|---|---|---|
| D3 | Cần dữ liệu delist thật (mua/thu thập) | Nguồn khả dĩ: HOSE/HNX công bố huỷ niêm yết; hoặc chấp nhận backtest chỉ từ 2020 với disclaimer |
| H5 | Thay noise-mining cần thiết kế: đề xuất Ledoit-Wolf shrinkage (sklearn có sẵn trong requirements) + báo cáo percentile thay vì max | 0.5-1 ngày riêng |
| A1/E3 | Hợp nhất 2 engine chấm điểm = thay đổi kiến trúc | Đề xuất: bước 1 rẻ — stock-decision-engine load `eligibility_status` và in cảnh báo khi mâu thuẫn |
| D6 | Số phí/thuế chính xác cần xác nhận broker của bạn | Hiện giữ 0.4% round-trip của stealth làm chuẩn chung |
| C3/C4b | Chỉ đo được sau khi B1 chạy với dữ liệu thật; funnel chart là enhancement | Phase 4 sẽ in funnel counts dạng text |
| F2/F3/E2/I5 | Cosmetic/tổ chức file, không đụng số liệu | Gom 1 commit dọn dẹp riêng nếu bạn muốn |

---

## Bảng EXPECTED OUTPUT CHANGES (thay đổi ĐÚNG ≠ hỏng mới)

| Output | Thay đổi dự kiến | Nguyên nhân |
|---|---|---|
| Notebook 20 / portfolio backtest Sharpe, CAGR | **GIẢM** (mức chưa biết, có thể đáng kể) | D1 bỏ same-bar |
| Trade cards: profit_factor, avg_return, win_rate | **GIẢM**; một số mã thành `Unvalidated` | I4 entry open T+1, I3 OOS validation, D2 skip limit-up |
| `capital_plan.parquet`: kelly_scale, quantity | kelly_scale → 1.0 hầu hết; sizes đổi | H3 tắt Kelly sai input |
| `portfolio_risk_report.json: allocator_used` | Có thể lộ "equal_weight (risk_parity FAILED)" | H2 khai thật fallback |
| `client_ready_watchlist` | **Ngắn lại**: SAB/BID rớt (G1 floor); thêm mã demote nếu cashflow board stale (F1); VIC-type đổi CONFIRMED→WATCH không rớt tier (I1) | G1, F1, I1 |
| Research notes | VIC: thesis đổi giọng trung tính; sector "Real Estate" thay "Financial Services"; tỷ trọng gợi ý đổi | I1, I2, H3 |
| Sector board | Financial Services mất VIC/VHM; Real Estate xuất hiện/mạnh lên | I2 |
| Freshness status trên repo hiện tại | OK → **ERROR** (data đứng 2026-07-02) cho tới khi fetch mới | B2 — chủ đích |
| `--scope full` | Fail với hướng dẫn chạy update_securities.py cho tới khi có securities data | B1 — chủ đích |
| relative_strength/stealth scores | Đổi toàn bộ (so VNINDEX thật thay vì rổ ngân hàng) | G2 |
| meta_score nhóm breakout | Giảm đồng loạt ~3-4.5 điểm | G6 |
| Mã có split lịch sử | Mất feature vài chục phiên quanh ngày split (NaN), có file flags để rà | G4 |
| `run_all_notebooks.sh` | Có thể FAIL THẬT ở notebook nào đó vốn đã hỏng — sẽ lộ ở Phase 4 | J1 |

---

## Ước lượng khối lượng & rủi ro

| Wave | Commits | Files code đụng | Tests mới/mở rộng | Rủi ro | Ghi chú |
|---|---|---|---|---|---|
| 1 | 4 | 4 + 1 CSV | 4 | Thấp | Độc lập, làm trước, giá trị khách hàng cao nhất |
| 2 | 4 | 6 + 1 sh + 1 md | 4 | **Trung bình-cao** | F1 đụng xương sống; B1 cần SSI creds của bạn để verify online |
| 3 | 6 | 7 + 1 yaml mới | 6 | Trung bình | Toàn logic tài chính — test reproduce bắt buộc; D2 có scope-guard |
| 4 | 4 | 5 | 4 | Thấp-TB | SAB/BID rớt watchlist — cần bạn biết trước |
| 5 | 4 | 7 (xoá 2) | 3 | Thấp | Dọn dẹp + contract tests |

**Điểm cần bạn xác nhận khi APPROVE:**
1. Có SSI FCData credentials để chạy `update_securities.py` + verify B1 online không? (Không có → B1 vẫn fix được, verify bằng fixture offline, phần online để bạn tự chạy.)
2. Đồng ý demote (không REJECT hẳn) khi cashflow board stale ở F1?
3. Đồng ý sector mới cho VIC/VHM/VRE = "Real Estate"?
4. Wave 3 mục D2: chấp nhận heuristic trần/sàn (không có dữ liệu giá tham chiếu chính thức)?

## NEW_FINDINGS (phát hiện mới trong lúc fix — sẽ ghi vào đây, không tự fix)

*(trống)*

---

**DỪNG TẠI ĐÂY — chờ APPROVED (toàn bộ hoặc theo wave).**
