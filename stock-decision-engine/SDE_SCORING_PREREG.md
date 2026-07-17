# SDE_SCORING_PREREG — kiểm định điểm số stock-decision-engine, khóa trước khi chạy

**Viết và commit TRƯỚC mọi phép chạy — đây là "phiên tòa" Vòng 3, CHƯA chạy
trong vòng này.** Không đổi tham số/tiêu chí sau khi nhìn kết quả. Đối tượng:
`final_score` (composite 8 thành phần, `stock-decision-engine/src/scoring.py`)
+ từng sub-score riêng lẻ. Máy đo, tiêu chí, cây quyết định đều dùng ĐÚNG bộ
đã khóa cho `final_watchlist.py` (`docs/reports/scoring/WATCHLIST_VALIDATION_PREREG.md`) —
không phát minh phương pháp mới.

**Trích dẫn nguồn**: `stock-decision-engine/AUDIT_SDE_REPORT.md` (mục 7, kế
hoạch Vòng 2 đề xuất — round này hiện thực hóa phần "cần bridge gì"),
`docs/reports/scoring/WATCHLIST_VALIDATION_PREREG.md`/`WATCHLIST_VALIDATION_REPORT.md`
(khuôn mẫu phương pháp + kết quả đối chiếu trực tiếp), `docs/reports/scoring/SCORE_FORENSIC_REPORT.md`
(kỳ vọng trước — mục "Caveat" dưới), `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`,
`CLAUDE.md` mục 8-9 (không tune, FDR bắt buộc).

---

## 1. Bridge kỹ thuật cần xây TRƯỚC khi chạy (Vòng 3, không phải vòng này)

`score_decision()` hiện chỉ tính cho MỘT ngày (ngày cuối dữ liệu đã nạp).
Kiểm định IC/null-test cần một **panel point-in-time**: `final_score` + 8
sub-score, tính cho MỌI (symbol, ngày) trong lịch sử, dùng đúng
`lookback_days=756` kết thúc TẠI ngày đó (không nhìn về phía trước).

- Vòng hóa `enrich()` + `score_decision()` theo từng symbol × ngày rebalance
  (không cần mọi ngày giao dịch — dùng `rebalance_period=20` như null-test
  của `final_watchlist` để chi phí tính toán hợp lý trên 501 mã).
- Cột `final_score` **trùng tên chính xác** với cột mà
  `src/backtest/portfolio_backtest.py::run_portfolio_backtest` đã ưu tiên đọc
  (`score_col = "final_score" if "final_score" in merged.columns else
  "meta_score"`, dòng ~356) — nghĩa là null-test có thể tái dùng NGUYÊN
  `run_portfolio_backtest` cho panel SDE mà không cần sửa hàm đó, chỉ cần
  panel đúng schema (`symbol`, `date`, `final_score`, `value_ma20` hoặc
  tương đương cho `min_value_ma20`, `above_ma200`).
- Target residualized: tái dùng nguyên `_newey_west_mean_se`/`sector_demean`/
  `rolling_beta` từ `scratch/score_v2_ic_test.py`/`diagnose_factor_ic_robust.py`
  — không viết công thức mới.

## 2. Đối tượng test

**Dữ liệu**: `data/processed/clean_daily_ohlcv.parquet`
(`OFFICIAL_CLEAN_OHLCV_PATH`, đã sạch từ Gate #6 — xem NV1/NV2 round này) +
`data/processed/benchmark_vnindex.parquet`.

**Universe**: `trading_status == ACTIVE` — cùng quy ước đã khóa cho
`final_watchlist` (áp đồng nhất cho toàn lịch sử, không phải point-in-time
thật; Gate #3 vẫn OPEN, `PROJECT_STATE.md` mục 3). **Không giới hạn còn lại ở
16 mã đã có output** — chạy trên full universe, đúng khuyến nghị
`AUDIT_SDE_REPORT.md` mục 7 ("16 mã hiện có output là mẫu quá nhỏ và không
đại diện").

**Target**: `forward_return_20d` (khớp `mc_horizon_days=20` sẵn có trong
`config.yaml` — lựa chọn tự nhiên, không phải mốc mới bịa ra), cả hai biến
thể raw và residualized (market-residual qua rolling beta 250 phiên +
sector-demean qua `config/sector_map.csv`).

**Đối tượng chấm điểm**:
a) `final_score` — như MỘT nhân tố tổng hợp.
b) 8 sub-score riêng: `market_regime`, `trend`, `momentum`, `relative_strength`,
   `risk`, `liquidity`, `simulation`, `alpha` — **trừ 3 ngoại lệ ở mục 3**.

**Phương pháp IC**: Spearman Newey-West (maxlags=20), tính hằng ngày (không
lấy mẫu cách quãng), trên cả hai target (raw/residualized), cả hai universe
(full = `trading_status==ACTIVE`; top150 = top 150 theo `median_value_60d`,
tái cân bằng mỗi 21 phiên). **3 giai đoạn**: chia chuỗi IC hằng ngày thành 3
đoạn liên tiếp bằng nhau theo thứ tự thời gian (tertile theo index — đúng cơ
chế đã dùng cho `final_watchlist`/`alpha_score` v2, không tự chọn mốc ngày
mới).

**Null test**: percentile CAGR thật trong 2.000 danh mục ngẫu nhiên/fold
(`seed=42`, một luồng RNG liên tục — đúng máy móc
`concentration_null_test.py`/`score_v2_null_test.py`). 5 fold theo năm dương
lịch (2022-2026, đúng `FOLDS` đã dùng xuyên suốt dự án). Cấu hình
`run_portfolio_backtest`: `rebalance_period=20` (khớp `mc_horizon_days`),
`portfolio_size=10`, `max_per_sector=2` (`sector_map` từ
`config/sector_map.csv`), `transaction_cost_pct=0.0015`,
`min_value_ma20=10_000_000_000` (**đúng bằng `config.yaml`'s
`min_avg_value_20d` của chính SDE** — không bịa số mới), `require_above_ma200=True`
— giao thêm `trading_status==ACTIVE`.

**FDR**: composite + 8 sub-score − 3 loại trừ (mục 3) = 6 đối tượng × 2
universe × 2 target = 24 test IC gộp trong một bảng — báo q-value BH-FDR bên
cạnh t_NW thô, đúng CLAUDE.md mục 9 (không chỉ ngưỡng |t|>3 thủ công).

## 3. Loại khỏi test — không tái tạo lịch sử được, có lý do

| Thành phần | Vì sao loại | Xử lý thay thế |
|---|---|---|
| `simulation` (Monte Carlo target-hit probability) | Không phải nhân tố cross-sectional dự báo return — là XÁC SUẤT có điều kiện (chạm target trước stop). IC Spearman không đo đúng khái niệm ("dự báo đúng x%" khác "xếp hạng cao thì return cao"). | Round riêng, kiểu **calibration test**: trong số các lần model dự báo "p% xác suất chạm target trước stop", thực tế lịch sử có đúng ~p% các trường hợp chạm target trước không (reliability diagram / Brier score) — KHÔNG chạy trong Vòng 3 này, ghi vào backlog. |
| `alpha` sub-score's phần `backtest.profit_factor` (20/100 điểm nội bộ) | Phụ thuộc `data/signals/breakout_20d_trade_cards.parquet` — **không phải chuỗi lịch sử point-in-time**, chỉ là snapshot hiện tại (tail(1) mỗi mã). Không tái tạo "tại ngày t trong quá khứ, backtest evidence là gì" được với dữ liệu hiện có. | Test `alpha` sub-score's phần CAPM (Jensen alpha/Sharpe/Sortino/IR/Calmar, 80/100 điểm nội bộ còn lại) **riêng**, ghi rõ đây là bản rút gọn của `alpha`, không phải công thức đầy đủ đang chạy production. |
| `market_regime` | Tính hoàn toàn trên VNINDEX — MỘT chuỗi duy nhất, không có biến thiên cross-sectional (mọi mã cùng ngày nhận CÙNG một giá trị `market_regime`). IC Spearman cross-sectional bằng 0 theo định nghĩa (rank không đổi giữa các mã). | Đánh giá kiểu time-series riêng (vd. `market_regime` thấp có dự báo drawdown VNINDEX kỳ tới không) — KHÔNG chạy trong Vòng 3 này, ghi vào backlog, không tính vào bảng IC/null chính. |

**5 thành phần còn lại kiểm định đầy đủ theo mục 2**: `trend`, `momentum`,
`relative_strength`, `risk`, `liquidity`, cộng `final_score` (composite) và
`alpha` (bản rút gọn CAPM-only) = 7 đối tượng, không phải 9 như số sub-score
gốc — điều chỉnh FDR ở mục 2 theo đúng 7 đối tượng này khi chạy thật (ghi rõ
N test trong report Vòng 3, không cố định trước con số nếu bridge kỹ thuật
thay đổi phạm vi).

## 4. Cây quyết định (KHÓA TRƯỚC, áp dụng sau khi có đủ bảng)

- **Nhánh A** — `final_score` đạt (`|t_NW| > 3` đồng dấu cả 3 giai đoạn,
  target residualized, universe full — **HOẶC** null-test percentile trung
  bình > 60 và không fold nào < 10, đúng chuẩn GĐ4/`final_watchlist`) →
  **GIỮ khung 8 thành phần**, chỉ gỡ sub-score có IC âm ổn định
  (`t_NW < -3` đồng dấu âm cả 3 giai đoạn, target residualized, universe
  full) khỏi trọng số, phần còn lại giữ nguyên công thức/trọng số hiện tại.
- **Nhánh B** — `final_score` KHÔNG đạt tiêu chí Nhánh A, NHƯNG ≥1 sub-score
  đạt riêng (cùng ngưỡng `|t_NW|>3` đồng dấu 3 giai đoạn, target
  residualized, universe full) → **TÁI THIẾT** (bài học v2: ít mà chắc):
  `final_score` tính lại CHỈ từ các sub-score có bằng chứng riêng (trọng số
  phân bổ lại theo tỷ lệ thuận, không tự cộng thêm cho một thành phần cụ thể
  — đúng quy ước đã dùng khi gỡ `liquidity_score` khỏi `final_watchlist`);
  sub-score không có bằng chứng riêng → giữ cột hiển thị tham khảo, dán nhãn
  `"unvalidated"` rõ trong output, KHÔNG tính vào `final_score`.
- **Nhánh C** — không thành phần nào (kể cả composite) đạt → SDE chuyển vai
  trò thành **BẢNG DỮ KIỆN**: hiển thị các chỉ số thô có ngữ cảnh (MA, RSI,
  ATR, Sharpe, v.v. — đúng những gì `metrics`/`sub_scores` đã tính), KHÔNG
  còn `final_score` tổng hợp, KHÔNG còn `decision` (BUY CANDIDATE/WATCH/...).
  Đúng tinh thần "không xếp hạng alpha, chỉ hiển thị" mà `final_watchlist.py`
  đã áp dụng ở Nhánh C của chính nó — trung thực, dừng lại bàn với người dùng
  trước khi làm thêm.

**Vùng xám**: kết quả nằm giữa ranh giới hai nhánh (vd. đạt đúng 1/2 tiêu chí
IC/null, hoặc số sub-score "đạt riêng" ở Nhánh B chỉ 1/5 và q-value FDR sát
ngưỡng) → chọn nhánh **thận trọng hơn** trong hai nhánh liền kề (ưu tiên B
trên A, C trên B), ghi rõ lý do trong report Vòng 3.

## 5. Caveat ghi sẵn — kỳ vọng TRƯỚC khi chạy, để không bất ngờ

1. **Sàn hiệu chỉnh survivorship**: mọi số CAGR/Sharpe long-only trong report
   Vòng 3 phải trừ mức sàn `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`
   (+0.4%/+1.2%/+2.9% ở 20/60/120 ngày) trước khi diễn giải "có edge" —
   không phải điều kiện pass/fail của cây quyết định (mục 4 dùng số thô,
   đúng quy ước `final_watchlist`), nhưng PHẢI nêu cạnh mọi con số CAGR được
   trích trong report Vòng 3.
2. **Kỳ vọng thực tế, ghi trước khi chạy (không phải kết luận đã có)**:
   `AUDIT_SDE_REPORT.md` mục 3.3 đã chỉ ra `trend`/`momentum`/`relative_strength`
   (50% trọng số `final_score`) cùng họ nhân tố với `trend_score`/`momentum_score`/
   `relative_strength_score` của `final_watchlist.py` (đã đóng hồ sơ âm tính,
   `WATCHLIST_VALIDATION_REPORT.md`) và với `momentum_score`/`rs_score`/
   `trend_score` của `alpha_score` v1 (đảo dấu IC 2026,
   `SCORE_FORENSIC_REPORT.md`). **Kỳ vọng hợp lý trước khi chạy: các sub-score
   này nhiều khả năng KHÔNG đạt `|t_NW|>3` dương ổn định** — nếu kết quả thật
   sự dương và ổn định, đó là bất ngờ thật (không phải lỗi tính toán cần nghi
   ngờ trước), cần soát lại phương pháp trước khi tin, không phải bác bỏ kết
   quả vì "trái kỳ vọng". Ghi ở đây để tránh diễn giải kết quả theo hướng có
   lợi sau khi đã biết số (hindsight bias).
3. **`risk` sub-score**: nếu có bằng chứng riêng dương, khả năng cao là trùng
   cụm biến động với `realized_vol_20d` (nhân tố DUY NHẤT đã validated của dự
   án chính, `SCORE_V2_DESIGN.md`) chứ không phải thông tin độc lập — đúng
   kết luận đã rút ra cho `risk_score`/`final_watchlist`
   (`WATCHLIST_VALIDATION_REPORT.md` mục 2.3). Nếu Nhánh B kích hoạt và
   `risk` là một trong các sub-score "đạt riêng", ghi rõ caveat này trong
   report Vòng 3, không trình bày như một nguồn tin mới.
4. **Gate #3 (survivorship/point-in-time universe) vẫn OPEN** — universe
   `trading_status==ACTIVE` áp đồng nhất cho toàn lịch sử, không phải tái lập
   thật; kết quả Vòng 3 kế thừa giới hạn này y hệt mọi backtest khác trong dự
   án, không có cách bypass trong phạm vi hiện tại.

## 6. Ràng buộc kế thừa/mới

- Không tune trọng số/ngưỡng theo bất kỳ kết quả nào trong Vòng 3.
- Không thêm sub-score mới (chỉ kiểm định 8 thành phần + composite đã có,
  trừ 3 ngoại lệ mục 3).
- Một lần chạy Vòng 3. Không chạy lại để "thử" biến thể khác sau khi thấy
  kết quả sơ bộ xấu.
- Vòng 3 KHÔNG nằm trong phạm vi round này (RÀNG BUỘC gốc) — file này chỉ
  khóa kế hoạch, chưa chạy dòng test nào.
