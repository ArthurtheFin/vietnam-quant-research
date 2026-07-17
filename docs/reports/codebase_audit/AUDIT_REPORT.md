# AUDIT REPORT — vietnam-quant-research

| | |
|---|---|
| **Ngày audit** | 2026-07-08 |
| **Phạm vi** | Toàn bộ repo tại HEAD `d7c283e` (universe/scanner, filter, backtest, scoring, portfolio/capital, output/report, workflow/tooling, notebooks, tests) |
| **Phương pháp** | Read-only: trinh sát bằng `grep`/`find`/AST scan trước, đọc code logic có chọn lọc, đối chiếu output thật trong repo (`final_watchlist.csv`, `research_notes/generated/*`, `reports/*`). Không sửa file nào ngoài file này. |
| **Tổng số phát hiện** | 40 (5 Critical, 12 High, 13 Medium, 7 Low, 3 Info/đã xác nhận ổn) |

---

## Bảng tổng hợp phát hiện (index)

### CRITICAL — làm sai lệch kết luận cốt lõi hoặc đầu ra gửi khách

| Mã | Vấn đề | Vị trí chính |
|---|---|---|
| B1 | "Full universe" tự tham chiếu — không hề quét toàn sàn; code fetch danh sách niêm yết thật bị mồ côi | `scripts/update_daily_data.py:38` |
| B2 | Freshness check tự tham chiếu — không thể phát hiện pipeline ngừng chạy; `data_age_days` luôn = 0 | `src/validation/freshness_check.py:222` |
| D1 | Same-bar look-ahead trong portfolio backtest — tín hiệu và khớp lệnh cùng ngày | `src/backtest/portfolio_backtest.py:90` |
| F1 | Eligibility gate luôn chạy TRƯỚC cashflow/sector board cùng ngày — gate cashflow dùng dữ liệu hôm qua hoặc fallback "OK" | `scripts/run_daily_pipeline.py:37-77, 858-869` |
| I1 | Research note gửi khách tự mâu thuẫn: WEAK_FLOW + volume 0.10x nhưng CONFIRMED + "dòng tiền cải thiện" + tỷ trọng 13.48% | `research_notes/generated/VIC.md`, `src/analytics/cashflow_board.py:549` |

### HIGH — sai logic/công thức, thổi phồng kết quả có hệ thống

| Mã | Vấn đề | Vị trí chính |
|---|---|---|
| C1 | `min_price` sai đơn vị (5-10 VND) — không lọc được gì | `src/screening/final_watchlist.py:57` |
| D2 | Không mô hình hoá biên độ trần/sàn (±7/±10/±15%) ở mọi backtest | `src/backtest/*` |
| D3 | Survivorship bias cấu trúc — không có dữ liệu mã delist | toàn repo |
| G1 | Điểm 0-100 là rank tương đối trong rổ ~25 mã, trình bày như chất lượng tuyệt đối | `src/analytics/meta_ranking.py:47`, `src/alpha/scoring.py` |
| G2 | Market proxy = trung bình chính rổ watchlist (nặng ngân hàng), không dùng VNINDEX thật | `src/screening/stealth_accumulation.py:413` |
| G4 | Return clip ±15% thay vì điều chỉnh corporate action — split vẫn bơm sốc giả vào mọi chuỗi | `src/features/returns.py:15` |
| H1 | Inverse-vol có thể dùng nhầm `final_score` làm volatility — điểm càng cao phân bổ càng ít | `scripts/build_portfolio_stack.py:165` |
| H2 | Allocator fail âm thầm thay bằng equal-weight nhưng report ghi "risk_parity" | `scripts/build_portfolio_stack.py:181` |
| H3 | Kelly sizing nối sai tham số: `median_return` làm avg_loss — capital plan vô nghĩa | `scripts/build_portfolio_stack.py:225` |
| I2 | Sector map gán VIC/VHM = "Financial Services" — lỗi factual trong văn bản gửi khách | `config/sector_map.csv` |
| I3 | Stop-loss trade cards optimize in-sample, báo cáo trên chính tập đã tối ưu (overfit) | `src/backtest/breakout_research.py:73` |
| J1 | `run_all_notebooks.sh` chết toàn bộ (path cũ) nhưng luôn in "executed successfully" | `scripts/run_all_notebooks.sh` |

### MEDIUM

| Mã | Vấn đề |
|---|---|
| A1 | Hai hệ thống chấm điểm song song (`src/alpha` vs `stock-decision-engine`) không đối chiếu nhau |
| C2 | Ngưỡng thanh khoản không gắn đặc thù VN (T+2.5, free-float, penny) |
| C3 | Bộ lọc lọc lại một tập đã pre-select — gần pass-through |
| C4b | Không có chart funnel input/loại bỏ của bộ lọc dù dữ liệu cờ lọc có sẵn |
| D4 | Bias-check chỉ chạy tay trong notebook 19, survivorship check dùng danh sách delisted giả (mock) |
| D5 | `forward_return_*` ghi thẳng vào `stock_features.parquet` — rủi ro rò rỉ tiềm ẩn, không có gate tự động |
| E1 | Các module nhất quán với nhau nhưng cùng kế thừa universe hẹp |
| E3 | `stock-decision-engine` không đối chiếu `eligibility_status` từ pipeline chính |
| F2 | Notebook 12 gộp 2 notebook chung kernel — chạy riêng phần 12b sẽ lỗi path |
| G3 | Meta ranking merge 3 nguồn không kiểm tra đồng bộ ngày theo từng mã |
| G5 | Dữ liệu thiếu mặc định 50 điểm thay vì bị loại/phạt |
| H4 | Gate danh mục bịa volume = 100,000 khi thiếu cột |
| H5 | "Danh mục tối ưu" = max-Sharpe từ 5000 danh mục ngẫu nhiên in-sample (noise mining) |
| I4 | Trade cards giả định vào lệnh tại close ngày tín hiệu (same-bar, cùng họ D1) |
| J2 | Code rác: `Monte Carlo Pipeline.py` orphan ở root (copy Instagram, yfinance không có trong requirements), patch residue trong `run_meta_ranking.py` |
| J3 | Tests không khoá hợp đồng giữa các bước pipeline — hổng đúng chỗ các lỗi Critical đang nằm |

### LOW / INFO

| Mã | Vấn đề |
|---|---|
| A2 | Notebook checkpoint rác đã liệt kê DELETE_CANDIDATE nhưng chưa xoá |
| A3 | Ngưỡng signal hardcode trong default argument thay vì config |
| B4 | Hardcode "501" làm fallback tổng số mã |
| D6 | Chi phí giao dịch không nhất quán giữa 2 backtest engine, có thể thấp hơn thực tế |
| E2 | Cột boolean cũ (`is_research_candidate`...) không còn phản ánh logic, dễ gây hiểu nhầm consumer |
| F3 | Đánh số mục lục client report lặp/xáo trộn |
| G6 | Synergy bonus double-count action labels |
| H6 | NAV hardcode 1 tỷ VND |
| I5 | `reports/` chứa bản sao gần trùng, cũ, của output trong `data/` |
| B3 | ✅ Xác nhận KHÔNG có vấn đề: lỗi fetch không bị nuốt âm thầm |
| C4 | ✅ Đã vá ở commit gần đây: zero-volume leak ABB/BVB |
| D7 | ✅ Công thức Sharpe/CAGR/MaxDD đúng chuẩn |

---

## A. Bản đồ dự án & trùng lặp

### A1. [Medium] Hai hệ thống chấm điểm song song, không đối chiếu nhau
- **Vị trí**: [src/alpha/scoring.py:9-17](src/alpha/scoring.py:9) vs [stock-decision-engine/src/scoring.py:8-31](stock-decision-engine/src/scoring.py:8)
- **Bằng chứng**: `src/alpha/scoring.py` chấm điểm **cross-sectional theo rank** (momentum 25%, relative strength 25%, trend 20%, volume 15%, volatility contraction 10%, liquidity 5%). `stock-decision-engine/src/scoring.py` chấm điểm **tuyệt đối theo ngưỡng** (market regime 10%, trend 20%, momentum 15%, RS 15%, alpha 15%, risk 10%, liquidity 10%, simulation 5%, dùng RSI 45-70, ADX≥20, MACD dấu...).
- **Vì sao là vấn đề**: Cùng một mã, cùng một ngày, hai engine có thể ra hai kết luận trái ngược (một bên "Client Ready", bên kia "Avoid") mà không ai đối chiếu. README của `stock-decision-engine` tự nhận là "independent" và không hề được `run_daily_pipeline.py`/scripts chính gọi tới (grep xác nhận 0 tham chiếu chéo).
- **Đề xuất**: Hoặc hợp nhất 1 nguồn công thức scoring duy nhất, hoặc bắt buộc `stock-decision-engine` phải load và hiển thị `eligibility_status`/`candidate_tier` từ pipeline chính để cảnh báo khi 2 hệ thống lệch nhau.

### A2. [Low] Notebook không phải nguồn trùng lặp logic đáng ngại — ngoại lệ nhỏ
- **Bằng chứng**: Quét toàn bộ 20 notebook chính (không tính archive): hầu hết chỉ có 1 hàm nội bộ (`find_project_root`) và import trực tiếp từ `src/` (`from_src_imports` 1-12 lần/notebook). Đây là thực hành tốt — không phải nguồn "2 hàm RSI khác nhau ở 2 nơi" như lo ngại trong yêu cầu.
- **Ngoại lệ**: `notebooks/05_client_report/01_client_market_report.ipynb` có 6 hàm nội bộ và 0 import từ `src/`, nhưng khi đọc thì đó chỉ là helper I/O (`load_parquet_safe`, `find_project_root`...), không phải logic nghiệp vụ — rủi ro thấp.
- `notebooks/notebook_inventory.md` đã tự liệt kê rõ các file `*-checkpoint.ipynb` là `DELETE_CANDIDATE` nhưng chưa xoá — nhiễu thư mục nhưng không ảnh hưởng logic.

### A3. [Info] Cấu hình screen không đồng nhất
- `config/screens/` chỉ có 1 file (`stealth_accumulation.yaml`). Các signal khác (breakout, pullback, volume spike) có ngưỡng hardcode ngay trong default argument của hàm ([src/backtest/setup_rules.py:6](src/backtest/setup_rules.py:6), dòng 23, 34) thay vì tập trung trong config — không sai nhưng thiếu nhất quán, khó review/tune.

---

## B. Công cụ quét thị trường (market scanner)

### B1. [CRITICAL] "Full universe" không phải toàn bộ HOSE/HNX/UPCOM — chỉ là danh sách đã fetch trước đó
- **Vị trí**: [scripts/update_daily_data.py:38-51](scripts/update_daily_data.py:38)
- **Bằng chứng**:
```python
def get_full_universe_symbols(base_dir=".") -> list[str]:
    for name in ("data/processed/stock_features.parquet", "data/processed/clean_daily_ohlcv.parquet"):
        ...
        return sorted(list(df["symbol"].dropna().astype(str).unique()))
    # fallback: watchlist 30 mã hardcode trong strategy_config.yaml
    return sorted(cfg.get("universe", {}).get("watchlist", []))
```
  Trong khi đó, `scripts/update_securities.py` **có thật** gọi `client.get_securities(market)` cho từng market HOSE/HNX/UPCOM (danh sách niêm yết thật, hàng nghìn mã) và lưu vào `data/raw/securities/{market}.parquet` — nhưng grep toàn repo cho thấy **không có bất kỳ file nào khác đọc lại `data/raw/securities/` hoặc gọi `get_securities()`** ngoài chính script này.
- **Vì sao là vấn đề**: `--scope full` chỉ tự tham chiếu chính nó (self-referential): dữ liệu "full" bị giới hạn bởi những gì đã từng fetch qua scope `core`/`custom`, mà `core` lại chính là watchlist 30 mã blue-chip trong `config/core_universe.csv`/`strategy_config.yaml`. Không có đường dẫn nào để hệ thống tự mở rộng ra toàn bộ sàn — công cụ "quét thị trường" trên thực tế chỉ quét lại một rổ ~30 mã đã chọn sẵn, dán nhãn "full" gây hiểu lầm nghiêm trọng về độ phủ.
- **Đề xuất**: Nối `get_full_universe_symbols()` với `data/raw/securities/*.parquet` (đã có sẵn logic fetch), hoặc đổi tên `scope=full` thành thứ trung thực hơn (`scope=tracked`) cho tới khi được nối lại.

### B2. [CRITICAL] Kiểm tra "freshness" tự tham chiếu chính nó, không so với ngày thực tế
- **Vị trí**: [src/validation/freshness_check.py:222-226](src/validation/freshness_check.py:222), [src/screening/final_watchlist.py:284-294](src/screening/final_watchlist.py:284)
- **Bằng chứng**:
```python
# freshness_check.py
baseline_ts = (inspected.get("clean_daily_ohlcv", {}).get("latest_timestamp")
               or inspected.get("stock_features", {}).get("latest_timestamp"))
# baseline_date = ngày lớn nhất CÓ SẴN trong chính dữ liệu, không phải date.today()
```
```python
# final_watchlist.py — as_of_date mặc định = max ngày có trong data
if as_of_date is None:
    as_of_date = out["date"].max()
out["analysis_as_of"] = pd.Timestamp(as_of_date)
out["data_age_days"] = (out["analysis_as_of"] - out["date"]).dt.days.astype(int)
```
  → với dòng dữ liệu mới nhất của mỗi mã, `data_age_days` luôn = 0 theo cấu trúc, bất kể toàn bộ dataset đã bị "đóng băng" (không ai chạy `update_daily_data.py`) bao lâu. Xác nhận thực tế: `final_watchlist.csv` hiện tại có `date=2026-07-02`, `analysis_as_of=2026-07-02`, `data_age_days=0` cho mọi dòng — trong khi ngày hệ thống hôm nay là 2026-07-07 (lệch 5 ngày, không hề bị cảnh báo).
- **Vì sao là vấn đề**: Đây trả lời trực tiếp câu hỏi "Nguồn dữ liệu có được cập nhật đúng ngày hay dùng cache cũ mà không refresh?" — câu trả lời là **hệ thống không có cách nào tự phát hiện việc pipeline ngừng chạy**. Baseline luôn "tự dịch chuyển" theo dữ liệu cũ, nên status luôn OK dù dữ liệu đã lỗi thời cả tuần.
- **Đối chiếu**: Có 1 điểm so sánh với ngày thật ở [scripts/update_daily_data.py:140-148](scripts/update_daily_data.py:140) (lấy `market_latest_date` từ VNINDEX) nhưng chỉ dùng để **in log cảnh báo**, không gate bất kỳ output nào.
- **Đề xuất**: Thêm một baseline độc lập = ngày giao dịch gần nhất thực tế (business day, có thể lấy qua `market_latest_date`) và so sánh TOÀN bộ dataset với mốc đó, không chỉ so các mã với nhau.

### B3. [Đã xác nhận KHÔNG có vấn đề] Mã lỗi khi fetch không bị âm thầm loại bỏ
- **Vị trí**: [scripts/update_daily_data.py:150-184](scripts/update_daily_data.py:150)
- Lỗi fetch từng mã được `print("[FAILED] SYMBOL...")`, phân loại (`_classify_fetch_error`) và ghi vào `failed_symbols`/`update_daily_data_summary.json` — không có `except: pass`/`except: continue` nào nuốt lỗi âm thầm trong luồng fetch chính. Điểm này ngược lại lo ngại trong yêu cầu — code làm đúng.

### B4. [Low] Hardcode "501" làm fallback tổng số mã
- **Vị trí**: [scripts/run_daily_pipeline.py:679](scripts/run_daily_pipeline.py:679) — `total_uni = ... or 501`. Con số đoán chừng tổng số mã HOSE, không lấy từ danh sách niêm yết thật (liên quan trực tiếp B1).

---

## C. Bộ lọc (filter logic)

### C1. [High] Ngưỡng `min_price` sai đơn vị — lọc gần như không có tác dụng
- **Vị trí**: [src/screening/final_watchlist.py:57](src/screening/final_watchlist.py:57) (`min_price: 5.0`), [config/screens/stealth_accumulation.yaml:24](config/screens/stealth_accumulation.yaml:24) (`min_price: 10.0`), áp dụng tại [final_watchlist.py:469](src/screening/final_watchlist.py:469) và [stealth_accumulation.py:490](src/screening/stealth_accumulation.py:490)
- **Bằng chứng**: giá đóng cửa trong output thực tế (`data/signals/final_watchlist.csv`) là VND thô: 16,300 – 217,200. Ngưỡng "giá tối thiểu" 5-10 (VND) sẽ không loại bất kỳ mã nào — kể cả penny stock rẻ nhất trên HOSE/UPCOM cũng giao dịch ở mức hàng nghìn VND.
- **Vì sao là vấn đề**: Đây là bằng chứng cụ thể cho đúng lo ngại "bộ lọc lỏng đến mức pass-through" trong yêu cầu — ngưỡng này chỉ mang tính trang trí, không lọc được gì trên thực tế.
- **Đề xuất**: Sửa thành ngưỡng có ý nghĩa (vd 3,000-10,000 VND tuỳ khẩu vị rủi ro penny stock) hoặc bỏ hẳn nếu liquidity threshold (`min_avg_value_20d`) đã đủ.

### C2. [Medium] Ngưỡng thanh khoản không gắn với đặc thù thị trường VN nêu trong yêu cầu
- **Vị trí**: `min_avg_value_20d` (25 tỷ / 5 tỷ VND), `min_volume_ma20` (50,000 cp) — [final_watchlist.py:58-59](src/screening/final_watchlist.py:58), [stealth_accumulation.yaml:25](config/screens/stealth_accumulation.yaml:25)
- Không tìm thấy bất kỳ chỗ nào trong code xử lý biên độ giá trần/sàn (±7%/±10%/±15%), chu kỳ T+2.5, hay free-float — các ngưỡng thanh khoản là số tuyệt đối hợp lý cho blue-chip nhưng không được giải thích/hiệu chỉnh theo các đặc thù này (xem thêm D2).

### C3. [Medium] Bộ lọc đang lọc trên một universe đã được lọc sẵn từ trước
- Vì candidate pool thực tế chỉ ~30 mã thanh khoản cao (B1), các điều kiện "strict_pass"/"fallback_eligible" trong [`_mark_filters`](src/screening/final_watchlist.py:467) gần như luôn đúng với phần lớn watchlist — vì các mã này được chọn vào watchlist chính vì đã thanh khoản cao/trend tốt. Bộ lọc tạo cảm giác chọn lọc nhưng thực chất đang lọc lại một tập đã pre-selected.

### C4b. [Medium] Cell notebook không hề chart "input" hay funnel của bộ lọc — chỉ chart kết quả sau lọc
- **Vị trí**: [notebooks/03_alpha_signals/09_stealth_accumulation_screen.ipynb](notebooks/03_alpha_signals/09_stealth_accumulation_screen.ipynb) — cell 5 ("Validate Scan Universe"), cell 9 ("Visualize Scan Diagnostics"); logic cờ lọc tại [src/screening/stealth_accumulation.py:600-649](src/screening/stealth_accumulation.py:600).
- **Bằng chứng**:
  - `screen_df` có 4 cột boolean riêng biệt cho từng điều kiện lọc: `history_pass`, `liquidity_pass`, `regime_pass`, `trend_pass`, gộp thành `screen_pass = history_pass & liquidity_pass & regime_pass & trend_pass` ([stealth_accumulation.py:649](src/screening/stealth_accumulation.py:649)). Dữ liệu để vẽ funnel (bao nhiêu mã bị loại vì lý do gì) **đã có sẵn** trong dataframe.
  - Nhưng toàn bộ 36 hàm chart trong [src/reporting/chart_factory.py](src/reporting/chart_factory.py) không có hàm nào tham chiếu 4 cột này riêng lẻ hay vẽ funnel/waterfall — chỉ có `screen_score_bar_chart`, `stage_distribution_chart`, `sector_distribution_chart` (cell 9), tất cả đều chart **sau khi đã lọc xong** (leaders/watchlist), không chart input hay tỷ lệ rơi rụng qua từng bước lọc.
  - Cell 5 ("Validate Scan Universe") có in ra bảng (không phải chart) `raw_symbols_in_dataset` vs `effective_symbols_to_scan`, nhưng gọi mode mặc định là `"full_local_market_dataset"` — tức tự gán nhãn "full market" cho đúng tập dữ liệu đã bị giới hạn ở B1, củng cố thêm ảo giác về độ phủ toàn thị trường ngay trong chính notebook.
- **Vì sao là vấn đề**: Một reviewer chạy notebook để "soi logic" (đúng mục đích notebook theo `docs/OPERATIONS.md`) sẽ không có cách nào nhìn thấy trực quan rằng: (a) hầu hết mã đã bị loại từ vòng liquidity/trend trước khi đến ngưỡng `min_price` vô nghĩa (C1), hay (b) universe đầu vào chỉ ~30 mã chứ không phải "full market" như tên biến ngụ ý (B1). Thiếu chart funnel khiến các vấn đề C1/C3/B1 rất khó bị phát hiện bằng mắt thường khi review notebook, kể cả với người quen thuộc dự án.
- **Đề xuất**: Thêm 1 chart funnel/bar đơn giản đếm số mã pass/fail theo từng cột `history_pass/liquidity_pass/regime_pass/trend_pass` ngay sau cell 6 ("Run Full Market Stealth Scan"), và đổi tên `scan_mode` mặc định thành thứ trung thực hơn (vd `"tracked_watchlist_dataset"`) thay vì `"full_local_market_dataset"`.

### C4. [Đã xác nhận: đã được xử lý ở commit gần đây] Zero-volume leak (ABB/BVB) trong báo cáo tự-audit cũ
- File có sẵn [data/output/screening_logic_audit_report.md](data/output/screening_logic_audit_report.md) (được tạo trước đó, không phải do audit này) ghi nhận ABB/BVB (volume=0) từng lọt vào `client_ready_watchlist`. Đối chiếu với code hiện tại: [`apply_eligibility_gate()`](src/screening/final_watchlist.py:825-905) đã có hard-reject cho `ZERO_VOLUME_OR_MISSING_DATA`, `CASHFLOW_CHECK_REQUIRED`, `STALE_DATA`, `LOW_LIQUIDITY`, `SEVERE_DISTRIBUTION_RISK`, và `data/signals/final_watchlist.csv` hiện tại không còn ABB/BVB ở top. Ghi nhận là **đã fix** (khớp với message commit `9a27e7f stabilize eligibility gate...`, `5ef81a4 fix post-gate tier distribution...`) — nêu ra để không báo nhầm vấn đề cũ là vấn đề mới.

---

## D. Backtest engine

### D1. [CRITICAL] Same-bar look-ahead trong `portfolio_backtest.py` — tín hiệu và khớp lệnh cùng một ngày
- **Vị trí**: [src/backtest/portfolio_backtest.py:90-217](src/backtest/portfolio_backtest.py:90)
- **Bằng chứng**:
```python
if current_date in rebalance_dates and day_idx < len(all_dates) - 1:
    features_today = df[df["date"] == current_date].set_index("symbol")   # dùng giá đóng cửa NGÀY current_date
    ...
    selected_symbols = merged.head(portfolio_size).index.tolist()
    ...
    current_holdings = target_holdings   # vào lệnh NGAY LẬP TỨC ở NAV của current_date
```
- **Vì sao là vấn đề**: Backtest giả định có thể quan sát giá đóng cửa ngày T (để tính MA/trend/momentum) rồi khớp lệnh NGAY tại giá đóng cửa ngày T đó — không có độ trễ thực thi. Đây là look-ahead/same-bar-fill bias kinh điển, làm Sharpe/CAGR bị thổi phồng.
- **Đối chiếu**: `config/screens/stealth_accumulation.yaml` có `backtest.entry_delay_days: 1` và `entry_price_col: open` — tức engine stealth-accumulation làm ĐÚNG (trễ 1 ngày, vào lệnh ở giá mở cửa hôm sau). Vậy codebase biết cách làm đúng ở một engine nhưng không áp dụng cho engine kia — bất nhất giữa 2 backtest engine trong cùng dự án.
- **Đề xuất**: Sửa `portfolio_backtest.py` để tín hiệu tính từ ngày T, khớp lệnh ở ngày T+1 (open), giống pattern đã có ở stealth_accumulation.

### D2. [High] Không mô hình hoá biên độ giá trần/sàn (price band) ở bất kỳ backtest engine nào
- Quét toàn bộ `src/backtest/` và `src/screening/stealth_accumulation.py`: không có logic kiểm tra trạng thái trần/sàn (±7% HOSE, ±10% HNX, ±15% UPCOM) trước khi giả định khớp lệnh ở giá open/close. Trong thực tế VN, đúng lúc breakout/tín hiệu mạnh nhất (thường là lúc giá trần) lại là lúc khó khớp lệnh nhất — backtest hiện tại bỏ qua hoàn toàn rủi ro này.

### D3. [High] Survivorship bias mang tính cấu trúc, không có đường sửa
- **Vị trí**: [src/validation/bias_checks.py:52-75](src/validation/bias_checks.py:52) định nghĩa `check_survivorship_bias()` nhưng grep toàn repo xác nhận **hàm này không được gọi ở bất kỳ đâu** ngoài file định nghĩa và `__init__.py`. Không tìm thấy bất kỳ danh sách mã đã huỷ niêm yết/delist nào trong `config/` hay `data/` (tìm bằng `find -iname "*delist*"` → rỗng).
- **Vì sao là vấn đề**: Mọi backtest (`portfolio_backtest.py`, stealth-accumulation backtest, `breakout_research.py`) chỉ chạy trên universe hiện tại (mã đang niêm yết/đang theo dõi) áp ngược lại quá khứ 2020-2025 — 100% survivorship bias, không có dữ liệu để đo hay sửa.

### D4. [Medium — đã đính chính] Bias-check chỉ chạy thủ công trong 1 notebook, không nằm trong pipeline tự động, và dùng dữ liệu giả
- **Đính chính**: Lần kiểm tra trước (grep chỉ `--include="*.py"`) bỏ sót notebook. `check_lookahead_bias()`, `check_data_leakage()`, `check_survivorship_bias()` **có được gọi**, nhưng chỉ trong [notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb](notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb), cell 7 ("Run Leakage Verification") — một notebook phải mở tay và chạy thủ công, **không nằm trong `scripts/run_daily_pipeline.py`** hay bất kỳ step tự động nào.
- **Bằng chứng nghiêm trọng hơn**: trong chính cell đó, `check_survivorship_bias()` được gọi với dữ liệu giả:
```python
# Mock delisted check (VNINDEX active list vs mock delisted historical stocks)
mock_delisted = ["FLC", "ROS", "ART"]
survivorship_check = check_survivorship_bias(signals["symbol"].unique(), mock_delisted)
```
  Đây là danh sách delisted **hardcode/mock**, không phải dữ liệu delisted thật (khớp với D3 — repo không có bất kỳ danh sách delisted thật nào). Người review chạy notebook này sẽ thấy dòng in "Survivorship Bias check details: ..." và dễ tưởng đây là một kiểm tra thật, trong khi thực chất luôn kiểm tra trên đúng 3 mã giả định cố định.
- **Vì sao là vấn đề**: Không có gate tự động nào chặn pipeline khi phát hiện look-ahead/leakage — các hàm này chỉ mang tính "trình diễn" khi có người mở notebook 19 lên chạy tay, và ngay cả khi đó, phần survivorship lại kiểm tra trên dữ liệu giả nên không phản ánh rủi ro thật.

### D5. [Medium] `forward_return_{h}d` được tính thẳng vào `stock_features.parquet` — rủi ro rò rỉ dữ liệu tiềm ẩn
- **Vị trí**: [src/features/returns.py:19-29](src/features/returns.py:19), gọi từ `scripts/generate_features.py`.
- Cột `forward_return_5d/10d/20d` (dùng `shift(-h)`, tức return tương lai thật) được ghi vào chính bảng feature dùng cho scoring/screening sống, và (theo `data/output/screening_logic_audit_report.md` mục 6) lan sang `setup_signals.parquet`/`meta_ranking.parquet`. Grep hiện tại không thấy `alpha/scoring.py`, `final_watchlist.py`, `generate_signals.py` dùng trực tiếp cột này trong điều kiện chấm điểm sống (không có bug xác nhận), nhưng vì D4 (không có gate tự động), rủi ro này chưa từng được kiểm chứng bằng tool, chỉ dựa vào review thủ công.

### D6. [Low] Mô hình chi phí giao dịch không nhất quán, có thể bị đánh giá thấp
- `portfolio_backtest.py`: `transaction_cost_pct=0.0015` (0.15%), không có slippage ([portfolio_backtest.py:26](src/backtest/portfolio_backtest.py:26)).
- `stealth_accumulation.py`: `round_trip_cost=0.004` + slippage theo ATR/volatility regime + phạt thanh khoản thấp ([stealth_accumulation.py:70-139](src/screening/stealth_accumulation.py:70)).
- Chi phí round-trip thực tế ở VN (phí môi giới + 0.1% thuế bán) thường ~0.25-0.45%+slippage — `portfolio_backtest.py` nhiều khả năng đánh giá thấp chi phí thật, làm Sharpe/CAGR báo cáo lạc quan hơn thực tế.

### D7. [Info — không phát hiện lỗi] Công thức Sharpe/CAGR/MaxDD đúng chuẩn
- [src/risk/management.py:40-70](src/risk/management.py:40): annualization dùng `√252`, CAGR dùng geometric compounding đúng kỳ hạn. Không phát hiện lỗi tính toán ở đây.

### D8. [Info] Không có pipeline dữ liệu cơ bản (báo cáo tài chính/EPS)
- Grep toàn repo cho từ khoá EPS/BCTC/financial statement không ra kết quả liên quan — hệ thống hiện tại thuần kỹ thuật (giá/khối lượng), nên câu hỏi "point-in-time fundamentals" trong yêu cầu chưa áp dụng được (không phải bug, nhưng nên biết rõ giới hạn phạm vi).

---

## E. Tính nhất quán tổng thể

### E1. [Medium] Các module nhất quán với NHAU nhưng cùng sai theo B1
- Scanner → filter → backtest → report đều đọc cùng `stock_features.parquet`/`clean_daily_ohlcv.parquet`, nên không có hiện tượng "backtest chạy trên universe khác scanner" — nhưng đó là vì tất cả cùng kế thừa một universe bị bó hẹp (B1), chứ không phải vì đã verify với universe thị trường thật.

### E2. [Low] Cột boolean cũ (`is_research_candidate`, `is_trading_candidate`) không còn phản ánh logic hiện tại
- **Vị trí**: `data/signals/final_watchlist.csv` hiện tại — mọi dòng đều `is_research_candidate=False`, `is_trading_candidate=False` dù `candidate_tier="Client Ready"` và `is_client_ready=True`. Sau refactor ở commit `02b87e3`, việc phân tier thực tế dựa vào `candidate_tier` (string) + `eligibility_status`, không còn dùng 3 cột boolean gốc để lọc — nhưng các cột này vẫn được xuất ra và dễ gây hiểu nhầm cho bất kỳ script/consumer nào đọc trực tiếp CSV (ví dụ stock-decision-engine, hoặc phân tích ad-hoc).

### E3. [Medium] `stock-decision-engine` đọc chung dữ liệu nhưng không đối chiếu `eligibility_status`
- Xem A1 — engine phụ đọc `data/processed/*`, `data/signals/*` nhưng không kiểm tra `eligibility_status`/`candidate_tier` từ pipeline chính trước khi đưa ra quyết định Buy/Wait/Avoid riêng — một mã bị `REJECTED` ở gate chính vẫn có thể được `stock-decision-engine` đề xuất mua.

---

## F. Thứ tự thực thi (pipeline step order & notebook cell order)

### F1. [CRITICAL — vẫn còn tồn tại, không phải vấn đề cũ] `run_meta_ranking` (và eligibility gate) luôn chạy TRƯỚC khi cashflow/sector board được build cùng ngày
- **Vị trí**: [scripts/run_daily_pipeline.py:37-77](scripts/run_daily_pipeline.py:37) (`PIPELINE_STEPS`, chạy ở dòng 772-773) so với [scripts/run_daily_pipeline.py:858-869](scripts/run_daily_pipeline.py:858) (`_run_sector_board`, `_run_cashflow_board`, chạy SAU đó).
- **Bằng chứng**:
```python
# Thứ tự thực thi thật trong main():
for step in steps_to_run:            # dòng 772: PIPELINE_STEPS = [..., "run_meta_ranking"] chạy Ở ĐÂY trước
    report = _run_step(step, ...)
...
freshness = evaluate_freshness(...)  # dòng 858
if args.build_sector:                # dòng 860 — CHẠY SAU run_meta_ranking, và mặc định action="store_true" => False
    sector_result = _run_sector_board()
if args.build_cashflow:              # dòng 866 — tương tự, mặc định False
    cashflow_result = _run_cashflow_board()
```
  `--build-sector`/`--build-cashflow` là cờ `action="store_true"` ([run_daily_pipeline.py:731-734](scripts/run_daily_pipeline.py:731)), **mặc định là False** nếu không truyền thêm tham số. Chính help text của cờ này còn tự thừa nhận thứ tự: `"Build cashflow board outputs after watchlists are available."`
- **Vì sao là vấn đề**: `apply_eligibility_gate()` trong `run_meta_ranking.py` → `build_watchlist_tiers()` đọc `data/output/cashflow_board.parquet` và `watchlist_cashflow_confirmation.parquet` **nếu file đã tồn tại từ trước** ([final_watchlist.py:148-162](src/screening/final_watchlist.py:148)). Vì `build_cashflow_board.py` luôn chạy SAU (hoặc không chạy nếu không bật flag), gate không bao giờ thấy dữ liệu cashflow **của cùng lần chạy hôm đó** — nó chỉ thấy: (a) file cashflow từ lần chạy trước đó (đã cũ ít nhất 1 chu kỳ), hoặc (b) hoàn toàn không có file nếu build-cashflow chưa từng được bật, khi đó gate fallback về `cf_status="OK"`, `confirm_status="WATCH"` mặc định — tức bỏ qua hoàn toàn lớp bảo vệ cashflow.
- **Đây chính là vấn đề #2 mà báo cáo tự-audit cũ của dự án** (`data/output/screening_logic_audit_report.md`, mục 3 "Pipeline order issue... watchlist generation runs before sector/cashflow board") **đã nêu — và nó VẪN CÒN TỒN TẠI**. Khác với C4 (bug zero-volume cụ thể trên ABB/BVB đã được vá bằng cách kiểm tra trực tiếp `close`/`volume`/`data_age_days` của chính dòng dữ liệu, không cần cashflow_board), phần gate dựa trên `cashflow_data_status`/`confirmation_status`/`cashflow_state` ở [final_watchlist.py:880-895](src/screening/final_watchlist.py:880) vẫn bị ảnh hưởng bởi lỗi thứ tự này — nghĩa là các lý do reject `CASHFLOW_CHECK_REQUIRED`/`SEVERE_DISTRIBUTION_RISK` trong output hiện tại có thể đang dựa trên dữ liệu cashflow của **hôm qua**, không phải hôm nay.
- **Thêm bằng chứng gián tiếp**: `docs/OPERATIONS.md` mục "1. Quy trình hàng ngày" liệt kê 8 bước chuẩn nhưng **không hề nhắc đến** `build_cashflow_board.py` hay `build_sector_board.py` — nghĩa là quy trình "chính thức" theo tài liệu vận hành còn không biết tới bước này, càng củng cố khả năng cashflow board hiếm khi được build đúng lúc trong vận hành thực tế.
- **Đề xuất**: Đảo thứ tự — build cashflow board & sector board TRƯỚC `run_meta_ranking`, hoặc bắt `apply_eligibility_gate` từ chối/flag rõ ràng (thay vì fallback âm thầm về "OK"/"WATCH") khi cashflow artifact không tồn tại/không cùng ngày với `analysis_as_of`.

### F2. [Medium] Notebook `12_meta_ranking_optimization.ipynb` gộp 2 notebook độc lập trong 1 file, chia sẻ chung 1 kernel — dễ vỡ nếu chạy lại từ giữa
- **Vị trí**: [notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb](notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb) — cell 0-10 là "12 — Meta Ranking & Alpha Scoring", cell 11 chỉ là `---`, sau đó cell 12-32 là hẳn một notebook khác "12b — Alpha Research & Scoring System" với H1 riêng.
- **Bằng chứng**: Cell "Setup Project Root" (`os.chdir(PROJECT_ROOT)`, `sys.path.insert`) **chỉ xuất hiện 1 lần duy nhất ở cell 1**, đầu file. Phần "12b" (cell 13 trở đi) gọi thẳng `read_parquet("data/processed/stock_features.parquet")` mà không tự thiết lập lại project root/sys.path.
- **Vì sao là vấn đề**: Vì file được chia rõ bằng markdown `---` + H1 mới trông như 2 notebook tách biệt, người dùng rất dễ restart kernel rồi chỉ "Run From Cell 12" để chạy riêng phần "12b" — khi đó mọi lệnh đọc file tương đối sẽ lỗi path vì working directory chưa được `chdir` về project root trong kernel session đó. Đây là một dạng "cell order trap" cụ thể do cấu trúc file gây ra.
- **Đề xuất**: Tách "12b" ra file `.ipynb` riêng (đúng như tên file `notebook_inventory.md` gợi ý các notebook nên độc lập), hoặc lặp lại cell setup project root ở đầu phần "12b".

### F3. [Low] Đánh số mục lục trong `01_client_market_report.ipynb` bị lặp/xáo trộn — dấu hiệu vá chắp nối không rà lại cấu trúc
- **Vị trí**: cell 10 `## 5. Watchlist Overview and 6. Client-Ready Watchlist` và cell 20 `### 5. Mã cần kiểm tra dữ liệu trước khi hành động` — **cùng dùng số "5"** cho 2 mục khác nhau. Các mục "Sector Board", "Cashflow Board", "Mã cần kiểm tra dữ liệu" nằm sau mục "11. Disclaimer"... thật ra là chèn xen giữa mục 10 và 11 mà không đánh số lại toàn bộ.
- **Vì sao là vấn đề**: Không ảnh hưởng logic chạy code, nhưng là bằng chứng trực tiếp cho đúng cảm nhận của bạn — notebook được chỉnh sửa nhiều lần (thêm Sector Board, Cashflow Board, Data Review) theo kiểu chèn thêm cell mà không rà soát lại cấu trúc/đánh số tổng thể, dễ gây khó hiểu khi đọc báo cáo cuối cùng.

---

## G. Logic tính điểm (alpha / stealth / meta ranking)

### G1. [High] Điểm 0-100 thực chất là xếp hạng tương đối trong rổ ~25-30 mã — không phải chất lượng tuyệt đối
- **Vị trí**: [src/analytics/meta_ranking.py:47-56](src/analytics/meta_ranking.py:47) (`_rank_score` dùng `rank(pct=True)*100`), [src/alpha/scoring.py:12-19](src/alpha/scoring.py:12) (cross-sectional rank theo ngày).
- **Bằng chứng**: `reports/daily_alpha_ranking.csv` chỉ có **25 dòng**; các điểm thành phần lộ rõ bước nhảy của rank trên mẫu nhỏ (vd `volatility_score = 28.000000000000004` = bậc 4%/mã của rank 25 mã). 
- **Vì sao là vấn đề**: Rank phần trăm trên một rổ đã pre-select **luôn** trải điểm từ 0-100 bất kể thị trường thế nào — trong thị trường giảm toàn diện, mã "đỡ tệ nhất" vẫn được 90-100 điểm momentum và đóng nhãn "Client Ready / High confidence". Điểm số trông như thang chất lượng tuyệt đối nhưng thực chất là "nhất bảng trong 25 mã tự chọn". Cộng hưởng với B1 (universe hẹp), đây là cơ chế thổi phồng tín hiệu có hệ thống.
- **Đề xuất**: Thêm điều kiện tuyệt đối (vd return_20d > 0, RS vs VNINDEX thật > 0) làm sàn trước khi rank, và/hoặc hiển thị rõ "rank trong N mã" trên mọi output.

### G2. [High] "Thị trường" trong stealth screen là proxy tự tham chiếu từ chính rổ watchlist (nặng ngân hàng)
- **Vị trí**: [src/screening/stealth_accumulation.py:413-421](src/screening/stealth_accumulation.py:413) — `market_proxy_return_1d = df.groupby("date")["return_1d"].mean()`.
- **Bằng chứng**: proxy thị trường = trung bình cộng đều return của các mã trong dataset đầu vào — mà dataset này (B1) là ~30 blue-chip, quá nửa là ngân hàng. `relative_strength_20d = return_20d - market_proxy_return_20d` do đó đo "mạnh hơn rổ ngân hàng" chứ không phải "mạnh hơn thị trường". Sector proxy cũng vậy: ngành chỉ có 1 mã thì `sector_relative_strength ≈ 0` vĩnh viễn (tự so với chính mình).
- **Vì sao là vấn đề**: Toàn bộ điểm relative strength / sector support / market down alpha — chiếm ~45% trọng số relative_strength_score — bị lệch hệ thống. Có benchmark VNINDEX thật trong repo (`benchmark_vnindex.parquet`) nhưng screen không dùng cho RS.
- **Đề xuất**: Dùng VNINDEX thật cho market proxy; vô hiệu hoá sector RS khi ngành < 3 mã.

### G3. [Medium] Meta ranking merge 3 nguồn không kiểm tra đồng bộ ngày theo từng mã
- **Vị trí**: [src/analytics/meta_ranking.py:59-68](src/analytics/meta_ranking.py:59) (`_latest_by_symbol` lấy `tail(1)` mỗi mã, không cap theo as-of date), [scripts/run_meta_ranking.py:32-41](scripts/run_meta_ranking.py:32).
- **Bằng chứng**: `_assert_not_stale` trong script chỉ so **max date của cả frame** — nếu stealth_latest có 1 mã mới nhất hôm nay nhưng 5 mã còn lại đứng ở tuần trước, assert vẫn pass và meta score trộn tín hiệu lệch ngày mà không cảnh báo (`analysis_date` chỉ coalesce lặng lẽ).
- **Đề xuất**: Assert theo per-symbol date, hoặc gắn cột `signal_age_days` cho từng nguồn và phạt điểm khi lệch.

### G4. [High] Return bị clip ±15% "để trung hoà split" — không phải điều chỉnh corporate action, chỉ là che triệu chứng
- **Vị trí**: [src/features/returns.py:15-17](src/features/returns.py:15) — `out["return_1d"] = daily_ret.clip(-0.15, 0.15)`.
- **Vì sao là vấn đề**: (a) Một split 2:1 không điều chỉnh tạo return giả -50%, clip còn -15% — vẫn là cú sốc giả bơm vào `return_20d`, `forward_return_*`, alpha momentum, mọi backtest; clip không "trung hoà" mà chỉ giới hạn mức phá hoại. (b) Biên độ UPCOM là ±15% — move trần/sàn hợp lệ của UPCOM nằm đúng tại biên clip, nếu mở rộng universe sang UPCOM (mục tiêu đã khai báo trong config) sẽ cắt cụt return thật. (c) Không có bất kỳ pipeline điều chỉnh cổ tức/split nào trong repo — nghĩa là dữ liệu giá chưa adjusted, mọi chỉ số dài hạn (MA200, return_120d, CAGR backtest) đều nhiễm lỗi corporate action.
- **Đề xuất**: Dùng giá đã điều chỉnh từ nguồn (hoặc tự xây bảng sự kiện), bỏ clip hoặc chỉ clip sau khi đã adjust.

### G5. [Medium] Dữ liệu thiếu được mặc định điểm trung vị 50 thay vì bị loại/phạt
- **Vị trí**: [src/analytics/meta_ranking.py:277-288](src/analytics/meta_ranking.py:277) — hàng loạt `_clip_score(..., default=50)` / risk score mặc định 25-35.
- **Vì sao là vấn đề**: Mã không có dữ liệu stealth/trade card nhận điểm "trung bình" ở các thành phần đó thay vì bị flag — thiếu dữ liệu được đối xử ngang bằng "dữ liệu bình thường", tạo meta score trông ổn cho những mã lẽ ra phải bị gắn cờ thiếu evidence.

### G6. [Low] Bonus cộng dồn trùng lặp trong meta score
- [src/analytics/meta_ranking.py:345-353](src/analytics/meta_ranking.py:345): `synergy_bonus` cộng thêm điểm cho `action == "Valid Breakout Setup"` trong khi action đó đã được chấm trong `action_score` → `breakout_component_score`. Double-counting nhẹ, thiên vị hệ thống cho nhóm breakout.

---

## H. Portfolio, capital allocation & Monte Carlo

### H1. [High] Inverse-volatility có thể nhận nhầm `final_score` làm "volatility" — mã điểm càng cao càng bị phân bổ ÍT
- **Vị trí**: [scripts/build_portfolio_stack.py:165-171](scripts/build_portfolio_stack.py:165)
- **Bằng chứng**:
```python
latest_vol = (candidates.set_index("symbol")
    .reindex(return_matrix.columns)["atr_pct_14" if "atr_pct_14" in candidates.columns else "final_score"]
    ...)
allocations["inverse_volatility"] = inverse_volatility_allocation(latest_vol.abs()...)
```
- **Vì sao là vấn đề**: Nếu frame candidates không có cột `atr_pct_14` (tuỳ nguồn watchlist được resolve), "độ biến động" trở thành điểm 0-100 → trọng số nghịch đảo điểm: mã tốt nhất nhận trọng số nhỏ nhất. Sai âm thầm, không log.

### H2. [High] Allocator lỗi thì âm thầm thay bằng equal-weight nhưng báo cáo vẫn ghi "risk_parity"
- **Vị trí**: [scripts/build_portfolio_stack.py:181-184](scripts/build_portfolio_stack.py:181) (`except Exception: allocations[name] = equal_weight_allocation(...)`) và dòng 211 (`risk_report["allocator_used"] = "risk_parity" if "risk_parity" in allocations else "equal_weight"` — key luôn tồn tại vì fallback đã điền vào).
- **Vì sao là vấn đề**: Nếu risk parity/HRP fail (covariance suy biến, thiếu lịch sử...), client report vẫn tuyên bố danh mục được xây bằng "risk_parity" trong khi thực tế là equal weight. Sai lệch mô tả sản phẩm gửi khách hàng.

### H3. [High] Kelly sizing bị nối sai tham số: `median_return` được truyền làm "avg_loss"
- **Vị trí**: [scripts/build_portfolio_stack.py:223-225](scripts/build_portfolio_stack.py:223) — `avg_loss_col="median_return"`; tiêu thụ tại [src/capital/management.py:276-288](src/capital/management.py:276) (`avg_loss=abs(float(avg_loss))`).
- **Vì sao là vấn đề**: `median_return` của một chiến lược có lãi là số **dương**, không phải thống kê thua lỗ; `abs()` biến nó thành "mức lỗ trung bình" giả. Tỷ lệ gain/loss của công thức Kelly do đó vô nghĩa → toàn bộ `kelly_scale`, `risk_amount`, khối lượng cổ phiếu đề xuất trong `capital_plan.parquet` (đầu vào của báo cáo khách hàng, mục "Tỷ trọng danh mục gợi ý") được suy ra từ công thức sai tham số.
- **Đề xuất**: Truyền đúng thống kê thua lỗ (vd trung bình `net_return` của các lệnh thua từ trade cards) hoặc tắt nhánh Kelly cho tới khi có input đúng.

### H4. [Medium] Gate danh mục bịa dữ liệu volume khi thiếu cột
- **Vị trí**: [src/portfolio/input_resolver.py:62-67](src/portfolio/input_resolver.py:62) — nếu cột `volume` không tồn tại: `vol = 100000.0`.
- **Vì sao là vấn đề**: Gate "ZERO_VOLUME" được vượt qua bằng giá trị bịa 100k cổ phiếu. Đây đúng loại lỗi "âm thầm cho qua" mà eligibility gate được sinh ra để chặn — cùng họ với bug ABB/BVB cũ.

### H5. [Medium] "Danh mục tối ưu" = chọn max-Sharpe từ 5000 danh mục ngẫu nhiên trên expected return quá khứ
- **Vị trí**: [src/portfolio/monte_carlo.py:210](src/portfolio/monte_carlo.py:210) (`valid.sort_values("sharpe_ratio", ascending=False).iloc[0]`), dùng trong notebook 14 cell "Select Optimal Random Portfolios".
- **Vì sao là vấn đề**: Chọn cực trị từ nhiễu ngẫu nhiên trên μ/Σ ước lượng in-sample là noise-mining kinh điển — Sharpe "tối ưu" báo cáo gần như chắc chắn không lặp lại out-of-sample. Không có shrinkage cho expected returns, không có resampling/bootstrap cho lựa chọn cuối.

### H6. [Low] NAV hardcode 1 tỷ VND trong script sản xuất
- [scripts/build_portfolio_stack.py:222,232](scripts/build_portfolio_stack.py:222) — mọi capital plan/khối lượng cổ phiếu tính trên NAV cứng 1B, không đọc từ config.

---

## I. Chất lượng đầu ra (reports, research notes, trade cards)

### I1. [CRITICAL] Research note gửi khách tự mâu thuẫn: WEAK_FLOW + volume 0.10x nhưng kết luận "dòng tiền cải thiện tích cực" + gợi ý tỷ trọng 13.48%
- **Vị trí**: [research_notes/generated/VIC.md](research_notes/generated/VIC.md) (output thật đang nằm trong repo); logic sinh tại [src/analytics/cashflow_board.py:546-552](src/analytics/cashflow_board.py:546) và [src/reporting/research_notes.py:182-187](src/reporting/research_notes.py:182).
- **Bằng chứng** (trích nguyên văn từ VIC.md): `Trạng thái dòng tiền: WEAK_FLOW` + `Xác nhận từ hệ thống: CONFIRMED` + `volume ratio 0.10x` + thesis "*xu hướng cải thiện tích cực của dòng tiền*" + `Tỷ trọng danh mục gợi ý: 13.48%`. Nguyên nhân: nhánh `label == "IMPROVING"` → `status = "CONFIRMED"` không kiểm tra lại `state`/`vol_ratio`; template thesis chỉ nhìn label, không nhìn state — hai tầng phân loại (label vs state) được tính từ công thức khác nhau và có thể mâu thuẫn, nhưng văn bản gửi khách ghép cả hai không đối soát.
- **Vì sao là vấn đề**: Đây là văn bản khuyến nghị trực tiếp cho khách hàng ("Khuyến nghị NẮM GIỮ hoặc TÍCH LŨY THÊM") dựa trên volume bằng 1/10 trung bình — chính xác loại tín hiệu mà một hệ thống "cashflow confirmation" phải chặn. Mâu thuẫn nằm ngay trong một trang note, người đọc kỹ sẽ mất niềm tin toàn hệ thống.
- **Đề xuất**: Bắt buộc `CONFIRMED` phải thoả đồng thời label VÀ state VÀ vol_ratio sàn (vd ≥0.7x); thêm rule "nếu các trường mâu thuẫn → hạ về WATCH".

### I2. [High] Sector map gán sai ngành các mã trọng yếu — VIC/VHM là "Financial Services"
- **Vị trí**: [config/sector_map.csv](config/sector_map.csv) — `VIC,Financial Services`, `VHM,Financial Services`; 18 mã `UNKNOWN`.
- **Vì sao là vấn đề**: Vingroup/Vinhomes là tập đoàn đa ngành/bất động sản, không phải dịch vụ tài chính. Sai ngành lan vào: sector board, sector relative strength (G2), giới hạn `max_names_per_sector`, và xuất hiện nguyên văn trong research note gửi khách ("*trong ngành Financial Services*" — lỗi factual khách hàng nhìn thấy ngay). Nguồn "HF Vietnam metadata + rule normalization" chưa được rà tay cho các mã vốn hoá lớn nhất thị trường.

### I3. [High] Tham số stop-loss của trade cards được chọn in-sample rồi báo cáo trên chính tập đã tối ưu
- **Vị trí**: [src/backtest/breakout_research.py:73-79](src/backtest/breakout_research.py:73) — `select_best_stop` sweep các stop, chọn `profit_factor` cao nhất, không có validation out-of-sample; kết quả đổ vào trade cards → edge tier → meta ranking → watchlist.
- **Vì sao là vấn đề**: Trả lời trực tiếp câu hỏi "overfit" trong yêu cầu gốc: tham số được optimize và performance được báo cáo trên **cùng một dữ liệu**. "Edge" của trade card là ước lượng lạc quan có hệ thống.

### I4. [Medium] Trade card / breakout stats giả định vào lệnh tại giá đóng cửa NGÀY tín hiệu
- **Vị trí**: [src/backtest/breakout_research.py:62-64](src/backtest/breakout_research.py:62) — dùng `forward_return_{h}d` (compound từ T+1 nhưng mốc giá gốc là close ngày T).
- **Vì sao là vấn đề**: Breakout xác nhận bằng chính close ngày T; thực tế VN không thể khớp tại close sau khi đã thấy close (lệnh ATC phải đặt trước). Cùng họ với D1 nhưng ở tầng trade cards — tức cả HAI nguồn "edge" chính (trade cards + portfolio backtest) đều có same-bar bias, chỉ stealth backtest là làm đúng (`entry_delay_days: 1`, giá open).

### I5. [Low] Thư mục `reports/` chứa bản sao gần trùng và đã cũ của output trong `data/`
- `reports/daily_alpha_ranking.csv` (25 dòng) và `reports/top_watchlist.csv` (20 dòng) trùng nội dung head-12, đều đứng ở 2026-07-02; song song tồn tại với `data/signals/*.parquet`. Hai "nguồn sự thật" cho cùng một thông tin, không có cơ chế đồng bộ.

---

## J. Workflow & tooling

### J1. [High] `run_all_notebooks.sh` chết hoàn toàn nhưng luôn báo thành công
- **Vị trí**: [scripts/run_all_notebooks.sh](scripts/run_all_notebooks.sh) — toàn bộ 20 đường dẫn dạng phẳng `notebooks/01_validate_environment.ipynb`... trong khi notebooks đã được dời vào thư mục con (`notebooks/01_data_pipeline/...`) từ đợt tái tổ chức (commit `b437c5d`).
- **Bằng chứng**: hàm `run_notebook` gặp file không tồn tại thì `echo "[SKIP] Missing notebook"` và `return 0` → cả 20 notebook đều SKIP, script kết thúc bằng "**All requested notebooks executed successfully.**"
- **Vì sao là vấn đề**: Công cụ chạy-lại-toàn-bộ (regression runner duy nhất cho notebooks) là một green light giả — ai chạy nó sẽ tin rằng mọi notebook còn thực thi được, trong khi thực tế không notebook nào được chạy. Đây là ví dụ điển hình của rủi ro "vá mà không rà workflow" xuyên suốt repo.

### J2. [Medium] Code rác/patch residue trong script production
- [scripts/run_meta_ranking.py:49](scripts/run_meta_ranking.py:49) đọc `auto_watchlist_top10.parquet` nhưng không bao giờ dùng; dòng 109-110 lặp `candidate_symbols = None` hai lần liên tiếp.
- [Monte Carlo Pipeline.py](Monte Carlo Pipeline.py) ở **thư mục gốc**: file copy từ nguồn ngoài (header "Author: quant.traderr (Instagram)... This is proprietary info"), phụ thuộc `yfinance` **không có trong requirements.txt**, trùng chức năng với `src/models/monte_carlo.py`, không được ai import. Kèm `monte_carlo_static.png` 212KB ở root. Orphan gây nhiễu và rủi ro license.

### J3. [Medium] Tests dày về số lượng nhưng hổng đúng chỗ rủi ro nhất
- 23 file test, có `test_logic_fixes.py` tốt (test look-ahead cho similarity/monte carlo models), nhưng **không có test nào** cho: same-bar bias của `portfolio_backtest.py` (D1), thứ tự step trong `run_daily_pipeline.py` (F1), fallback `final_score`-làm-volatility (H1), hay Kelly input (H3). Test hiện tại chủ yếu khoá happy-path của từng hàm đơn lẻ, không khoá **hợp đồng giữa các bước pipeline** — đúng nơi các lỗi nghiêm trọng nhất đang nằm.

---

## Tóm tắt điều hành (Executive Summary)

Dự án hiện đáng tin cậy ở mức **"công cụ theo dõi nội bộ cho một rổ ~30 mã blue-chip đã chọn sẵn"**, chứ **chưa đáng tin cậy** như một hệ thống "quét toàn thị trường VN và backtest thực chiến" — vốn là điều tên gọi "market scanner"/"full universe" ngụ ý. Có 2 lỗ hổng cấu trúc làm giảm giá trị cốt lõi bất kể công thức chấm điểm có tốt đến đâu: (1) không hề có universe toàn thị trường thật — scope `full` tự tham chiếu chính nó, còn đoạn code fetch danh sách niêm yết thật (`update_securities.py`) bị mồ côi, không ai dùng; (2) hai backtest engine trong cùng repo có mức độ thực tế khác nhau — một cái trễ tín hiệu đúng chuẩn, cái kia khớp lệnh cùng ngày với tín hiệu (look-ahead), nên các số Sharpe/CAGR từ `portfolio_backtest.py` gần như chắc chắn lạc quan hơn thực tế. Thêm vào đó, **thứ tự chạy pipeline (`run_daily_pipeline.py`) khiến eligibility gate luôn chấm điểm với dữ liệu cashflow board cũ hoặc không tồn tại** (F1) — đây là vấn đề mà chính báo cáo tự-audit cũ của dự án đã nêu và **vẫn còn nguyên**, chỉ phần bug zero-volume cụ thể (ABB/BVB) là đã được vá. Cộng thêm survivorship bias mang tính cấu trúc (không có dữ liệu mã delist; bias-check tồn tại nhưng chỉ chạy tay trong 1 notebook và dùng danh sách delisted giả — D4), và một engine chấm điểm thứ hai (`stock-decision-engine`) chạy song song với công thức khác hẳn mà không đối chiếu với gate chính — kết luận thực tế là: **danh sách Client-Ready hiện tại lọc được các trường hợp zero-volume/invalid-close rõ ràng, nhưng phần gate dựa trên trạng thái cashflow/tiền vào-ra gần như chắc chắn đang chạy trên dữ liệu không đồng bộ theo ngày**; **không nên tin bất kỳ con số hiệu suất backtest, tuyên bố độ phủ thị trường, hay tín hiệu "mua" chéo giữa 2 engine nào** cho tới khi các mục dưới đây được xử lý.

**Bổ sung sau vòng audit sâu (mục G-J):** Vòng đào sâu thứ hai xác nhận các vấn đề không chỉ nằm ở hạ tầng (universe, thứ tự pipeline) mà xuyên vào tận **chất lượng con số gửi khách hàng**: (1) research note thật trong repo tự mâu thuẫn — VIC được kết luận "dòng tiền cải thiện tích cực, CONFIRMED, gợi ý tỷ trọng 13.48%" trong khi cùng trang ghi WEAK_FLOW và volume ratio 0.10x (I1); (2) VIC/VHM bị gán sai ngành "Financial Services" ngay trong văn bản gửi khách (I2); (3) Kelly sizing dùng sai tham số đầu vào (`median_return` làm avg_loss — H3) và inverse-vol có thể dùng nhầm điểm số làm volatility (H1) — tức các con số tỷ trọng/khối lượng cụ thể trong capital plan không đáng tin; (4) mọi điểm 0-100 là rank tương đối trong rổ ~25 mã tự chọn, so với "thị trường" là chính rổ đó (G1, G2); (5) `run_all_notebooks.sh` chết toàn bộ nhưng luôn in "executed successfully" (J1) — biểu tượng cho tình trạng chung: hệ thống được vá nhiều lần, mỗi lần vá tạo thêm một lớp lệch mà không có công cụ hồi quy nào còn hoạt động để phát hiện.

**Top 5 cần xử lý trước (đã cập nhật sau audit sâu):**
1. **Đầu ra gửi khách** (I1, I2, H3): Chặn ngay research notes/capital plan hiện tại — sửa rule CONFIRMED (bắt buộc đồng thuận label+state+vol_ratio), sửa sector map cho các mã vốn hoá lớn, sửa hoặc tắt nhánh Kelly. Đây là các lỗi khách hàng nhìn thấy trực tiếp.
2. **Thứ tự pipeline** (F1): Đảo thứ tự để `build_cashflow_board.py`/`build_sector_board.py` chạy TRƯỚC `run_meta_ranking.py`, hoặc bắt `apply_eligibility_gate` báo lỗi rõ ràng thay vì âm thầm fallback "OK" khi thiếu dữ liệu cashflow cùng ngày.
3. **Universe & điểm số tương đối** (B1, G1, G2): Nối universe với danh sách niêm yết thật; dùng VNINDEX thật làm market proxy; ghi rõ "rank trong N mã" trên mọi score.
4. **Backtest realism** (D1, I3, I4, D2, D6): Sửa same-bar bias ở cả `portfolio_backtest.py` lẫn trade cards; thêm out-of-sample cho việc chọn stop-loss; mô hình hoá trần/sàn.
5. **Khôi phục công cụ hồi quy** (J1, J3, B2): Sửa đường dẫn `run_all_notebooks.sh`, thêm test khoá hợp đồng giữa các bước pipeline, thay freshness baseline tự tham chiếu bằng ngày giao dịch thực tế.
