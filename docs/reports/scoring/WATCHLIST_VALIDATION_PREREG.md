# WATCHLIST_VALIDATION_PREREG — first IC/null-test of the final_watchlist composite

**Viết và commit TRƯỚC mọi phép chạy.** `src/screening/final_watchlist.py`'s
composite (`weights`: trend 25 + momentum 20 + relative_strength 20 +
liquidity 10 + volume 5 + risk 10 + signal 10 = 100) đã sống trong sản xuất
qua nhiều fix từng thành phần riêng lẻ (gỡ `alpha_momentum_score`/`alpha_rs_score`
GĐ2, sửa `distance_ma20` gate) nhưng **chưa từng được kiểm định như một tổng
thể** — đúng khoảng trống `audit/PATH_TO_100.md` mục 3 đã ghi. Đây là lần đầu.
Cây quyết định, tiêu chí, và hai quyết định kèm (liquidity_score, sector
mapping) đều khóa ở đây — không đổi sau khi nhìn kết quả NV2.

**Trích dẫn nguồn**: `audit/PATH_TO_100.md` mục 3 (khoảng trống gốc),
`docs/reports/scoring/SCORE_V2_REPORT.md`/`docs/reports/scoring/SCORE_V2_DESIGN.md` (mốc so sánh v2, phương pháp IC/null
test chuẩn), `docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md` (máy móc null test gốc),
`docs/reports/scoring/SCORE_FORENSIC_REPORT.md` (lý do đã gỡ `alpha_momentum_score`/`alpha_rs_score`),
`docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md` (lý do gỡ `liquidity_score`),
`audit/SECTOR_MAPPING_COVERAGE_REPORT.md` (NV7 GĐ2, số liệu sector mapping),
`docs/reports/data/DATA_BASELINE.md`.

---

## Đối tượng test

**Dữ liệu**: `data/processed/stock_features.parquet` (`OFFICIAL_FEATURES_PATH`,
đã đồng bộ từ `full_history_v2`, Gate #6 đã đóng) + `data/processed/benchmark_vnindex.parquet`
+ `data/signals/meta_ranking.parquet` (cho `signal_score`/`risk_penalty_score`
— xem caveat riêng bên dưới, dataset này chỉ có **22 ngày phân biệt** trải dài
2022-01→2026-07, không phải chuỗi hằng ngày).

**Universe**: `trading_status == ACTIVE` (snapshot hiện tại, đúng quy ước đã
khóa ở `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md` — áp đồng nhất cho toàn lịch sử, không
phải tái lập point-in-time thật). Không thêm ngưỡng thanh khoản/xu hướng nào
khác cho universe của **test IC** (khác với các round trước từng dùng
`above_ma200 & value_ma20>=3B` — bỏ đi vì yêu cầu round này nêu rõ dùng
`trading_status`, không phải hai điều kiện đó). Test **null (portfolio
backtest)** cần thêm tham số của chính `run_portfolio_backtest` (không thể bỏ
trống) — dùng nguyên cấu hình "chuẩn hiện hành" (`min_value_ma20=10B`,
`require_above_ma200=True`, xem mục Null test bên dưới), **giao thêm** với
`trading_status == ACTIVE`.

## a) Composite tổng — như MỘT nhân tố

**Composite = `base_final_score`** (tổng có trọng số của 7 thành phần, TRƯỚC
`warning_penalty`) — không phải `final_score` (đã trừ penalty). Lý do khóa
ngay: `audit/PATH_TO_100.md` mục 3 tự mô tả đối tượng cần kiểm định là
"75/100 điểm trọng số" (trend 25 + momentum 20 + relative_strength 20 +
liquidity 10, cộng thêm volume 5 + risk 10 + signal 10 = 100) — đúng
`base_final_score`. `warning_penalty` là một lớp gắn cờ rủi ro vận hành (dữ
liệu cũ, thiếu backtest, thanh khoản thấp...) không tự nhận là một nhân tố dự
báo có trọng số — và việc tái lập nó cho lịch sử bị nhiễm bởi chính giới hạn dữ
liệu `meta_ranking.parquet` (22 ngày) nêu trên (cờ "Missing backtest evidence"
sẽ bật gần như mọi ngày ngoài 22 mốc đó, không phản ánh đúng vận hành sống).
Không kiểm định `final_score`/`warning_penalty` ở round này — ghi rõ đây là
giới hạn phạm vi, không phải bỏ sót.

Phương pháp: IC Spearman Newey-West (maxlags=20), tính hằng ngày (không lấy
mẫu cách quãng), trên **cả hai** target — raw (`forward_return_20d`) và
residualized (market-residual qua rolling beta 250 phiên + sector-demean qua
`config/sector_map.csv`, đúng nguyên hàm `_newey_west_mean_se`/`sector_demean`/
`rolling_beta` đã dùng ở `scratch/score_v2_ic_test.py`/`diagnose_factor_ic_robust.py`
— không viết lại công thức mới) — trên **cả hai** rổ: full (universe ở trên)
và top-150 (top 150 theo `median_value_60d`, tái cân bằng mỗi 21 phiên, chỉ
dùng dữ liệu quá khứ tại mỗi mốc — đúng cơ chế `top150_membership` đã có).
**3 giai đoạn**: chia chuỗi IC hằng ngày thành 3 đoạn liên tiếp bằng nhau theo
thứ tự thời gian (tertile theo index, đúng cơ chế `score_v2_ic_test.py` đã
dùng — không tự chọn mốc ngày cố định mới).

**Null test**: percentile CAGR thật trong 2,000 danh mục ngẫu nhiên/fold
(`seed=42`, một luồng RNG liên tục, đúng máy móc `docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md`/
`scratch/concentration_null_test.py`/`score_v2_null_test.py` — không viết lại).
5 fold theo năm dương lịch (2022–2026, đúng `FOLDS` đã dùng xuyên suốt session
này). Cấu hình: `rebalance_period=20`, `portfolio_size=10`, `max_per_sector=2`
với `sector_map` từ `config/sector_map.csv` (mã thiếu mapping → `UNKNOWN`, cap
như một ngành thật — **đã là hành vi mặc định của `portfolio_backtest.py` dòng
~360-365, không phải code mới**, chỉ cần đảm bảo truyền `sector_map` vào mọi
lệnh gọi ở round này), `transaction_cost_pct=0.0015`, `min_value_ma20=10B`,
`require_above_ma200=True` — nguyên cấu hình "chuẩn hiện hành" đã dùng cho xác
nhận v2 (`docs/reports/scoring/SCORE_V2_REPORT.md`), giao thêm điều kiện `trading_status==ACTIVE`.

## b) Từng thành phần riêng

7 cột: `trend_score`, `momentum_score` (đã sửa GĐ2, bỏ `alpha_momentum_score`),
`relative_strength_score` (đã sửa GĐ2, bỏ `alpha_rs_score`), `liquidity_score`,
`volume_score`, `risk_score`, `signal_score` — tính lại **chính xác theo công
thức đang chạy trong `src/screening/final_watchlist.py::_score()`** cho từng
ngày lịch sử (không phải tính riêng biệt bằng công thức khác) — cùng phương
pháp IC ở mục (a), cùng cả 2 universe, cùng cả 2 target, cùng 3 giai đoạn.

**Caveat khóa trước cho `signal_score` (và gián tiếp `risk_score`, vì
`risk_penalty_score` là 1/5 thành phần con của nó)**: cả hai phụ thuộc
`data/signals/meta_ranking.parquet`, chỉ có **22 giá trị phân biệt trải 4+
năm** (áp dụng kiểu "as-of" — giữ nguyên giá trị cũ giữa các lần cập nhật,
đúng logic `_merge_latest_meta`). Kết quả Newey-West `maxlags=20` cho
`signal_score` **phải đọc kèm cảnh báo**: tự tương quan thật của một chuỗi cập
nhật thưa (≈ mỗi 60-70 ngày lịch) có thể vượt quá 20 lag mà công thức điều
chỉnh — không tăng `maxlags` riêng cho thành phần này (giữ đồng nhất phương
pháp, không tune), chỉ **diễn giải t-stat của `signal_score` một cách thận
trọng hơn hẳn các thành phần khác trong report**, không dùng nó một mình để
quyết định gỡ/giữ nếu kết quả không rõ ràng.

## c) Mốc so sánh

- **`alpha_score` v2**: đã có kết quả (`docs/reports/scoring/SCORE_V2_REPORT.md`) — **trích lại
  nguyên số, không chạy lại**: null test avg percentile **71.0** (không fold
  nào <5, tệ nhất 20.2 năm 2025); IC Newey-West residualized t_NW **+6.09**
  (full) / **+5.67** (top150), đồng dấu dương cả 3 giai đoạn.
- **"Watchlist tối giản"** = xếp hạng thuần bằng `alpha_score` v2 **+ gate hiện
  hành của chính `final_watchlist.py`** (`strict_pass` HOẶC `fallback_eligible`
  từ `_mark_filters()` — tái lập được từ lịch sử thuần `stock_features`, không
  cần artifact cashflow/xác nhận cùng ngày vốn không tái lập point-in-time
  được cho quá khứ) làm rổ đủ điều kiện, thay cho `min_value_ma20=10B &
  above_ma200` đơn giản mà chính v2 dùng khi tự xác nhận — **đây là điểm khác
  biệt duy nhất so với (b)/mốc v2 ở trên**, đo xem gate nhiều điều kiện hơn của
  `final_watchlist.py` có làm đổi kết quả so với gate 2 điều kiện của v2 hay
  không. Chạy MỚI (không trích lại) qua đúng máy móc IC + null test ở mục (a),
  cùng universe `trading_status==ACTIVE` giao với `strict_pass|fallback_eligible`.

---

## Cây quyết định (KHÓA TRƯỚC, áp dụng sau khi có đủ bảng a/b/c)

- **Nhánh A** — composite đạt (`|t_NW| > 3` đồng dấu cả 3 giai đoạn, target
  residualized, universe full — **HOẶC** null-test percentile trung bình > 60
  và không fold nào < 10) **VÀ** không thua watchlist tối giản (percentile
  trung bình của composite ≥ percentile trung bình của watchlist tối giản, trừ
  hao 5 điểm phần trăm cho nhiễu — tức composite chỉ "thua" nếu percentile của
  nó thấp hơn watchlist tối giản quá 5 điểm) → **GIỮ composite**, chỉ gỡ thành
  phần nào có IC âm ổn định (`t_NW < -3` đồng dấu âm cả 3 giai đoạn, target
  residualized, universe full).
- **Nhánh B** — composite KHÔNG đạt tiêu chí Nhánh A, NHƯNG watchlist tối giản
  đạt (cùng ngưỡng `|t_NW|>3`/percentile>60-không-fold<10 ở trên, áp cho
  `alpha_score` v2 là thành phần xếp hạng) → **TÁI THIẾT**: watchlist xếp hạng
  bằng `alpha_score` v2; các thành phần cũ (`trend_score`,...) chỉ giữ vai trò
  gate/hiển thị NẾU có bằng chứng riêng của chính nó (`|t_NW|>3` đồng dấu 3
  giai đoạn, mục b); thành phần không có bằng chứng riêng → gỡ khỏi điểm xếp
  hạng, giữ cột hiển thị tham khảo gắn nhãn `"unvalidated"`.
- **Nhánh C** — cả composite lẫn watchlist tối giản đều không đạt → watchlist
  chuyển "không xếp hạng alpha": chỉ lọc eligibility (gate hiện hành) rồi sắp
  theo thanh khoản (`value_ma20` giảm dần — thước đo vận hành, không phải một
  nhân tố alpha đã kiểm định), dán nhãn rõ trong output là "không xếp hạng
  alpha, chỉ sắp theo thanh khoản". Báo cáo trung thực, dừng lại bàn với người
  dùng trước khi làm thêm.

**Vùng xám**: nếu kết quả nằm giữa ranh giới hai nhánh (ví dụ composite đạt
đúng 1 trong 2 tiêu chí IC/null nhưng không cả hai, hoặc chênh lệch với
watchlist tối giản nằm sát ngưỡng 5 điểm phần trăm) → chọn nhánh **thận trọng
hơn** trong hai nhánh liền kề (ưu tiên B trên A, C trên B) và ghi rõ lý do
trong report, đúng ràng buộc gốc.

---

## Quyết định kèm (khóa luôn, KHÔNG phụ thuộc kết quả cây quyết định trên)

### `liquidity_score` — gỡ khỏi điểm xếp hạng ở MỌI nhánh

Bằng chứng chiều "thưởng thanh khoản thấp" (`_rank(value_ma20)` hiện tại —
thực ra thưởng thanh khoản CAO, xem chú ý bên dưới) hay "thưởng thanh khoản
thấp" (như `alpha_score` v2's `value_ma20` component, đảo chiều) đều **nhiễm
survivorship bias đã định lượng ở `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`** (mã
nhỏ/kém thanh khoản hơn trong rổ hiện tại chính là nhóm bị phóng đại effect
mạnh nhất do sống sót đến hôm nay). Chiều ngược lại (thưởng thanh khoản cao)
cũng không có bằng chứng riêng độc lập nào đã kiểm định trong dự án. Quyết
định: **gỡ `liquidity_score` khỏi `base_final_score` ở cả 3 nhánh A/B/C** —
thanh khoản chỉ còn vai trò ELIGIBILITY (ngưỡng `min_value_ma20` + `trading_status`,
đã có sẵn trong gate) — an toàn vận hành, không đánh cược vào lát bằng chứng
bẩn nhất trong toàn bộ composite. (Chú ý kỹ thuật: cột hiện tại
`_score()`'s `out["liquidity_score"] = _rank(value_ma20) * weights["liquidity"]`
thưởng thanh khoản CAO — ngược chiều với `alpha_score` v2's `value_ma20`
component (thưởng thấp) — hai hướng mâu thuẫn nhau chưa từng được đối chiếu;
gỡ bỏ hoàn toàn tránh phải chọn giữa hai chiều đều thiếu bằng chứng sạch.)
10 điểm trọng số gỡ ra được phân bổ lại theo tỷ lệ thuận với trọng số các
thành phần còn lại trong `base_final_score` (không tự cộng thêm cho một thành
phần cụ thể nào — tránh một quyết định trọng số ngầm không có bằng chứng).

### Sector mapping — không bắt buộc eligibility, bắt buộc cho sector-cap portfolio

Chốt từ số liệu NV7 GĐ2 (`audit/SECTOR_MAPPING_COVERAGE_REPORT.md`: 96.4%
phủ, 482/500 mã; tác động thật hiện tại chỉ 4 mã, đều ở `research_candidates`,
không mã nào ở `client_ready`/`trading`) — phủ đủ tốt để dùng cho sector-cap
nhưng không đủ lý do bắt buộc 100% cho eligibility (sẽ loại oan 18 mã thiếu
mapping dù có thể vẫn là ứng viên hợp lệ về mọi mặt khác). Quyết định:
- **KHÔNG bắt buộc cho eligibility** — mã thiếu sector mapping vẫn được xét
  vào watchlist bình thường (không thêm điều kiện "phải có sector" vào
  `apply_eligibility_gate`/`_mark_filters`).
- **BẮT BUỘC cho sector-cap của portfolio**: mã thiếu mapping gộp vào bucket
  `UNKNOWN`, bucket này chịu cùng `max_per_sector=2` như một ngành thật —
  **đã đúng hành vi mặc định của `run_portfolio_backtest`/`portfolio_backtest.py`**
  (dùng cho mọi test null ở round này, không cần sửa code ở đó). Áp dụng THÊM
  vào `final_watchlist.py`'s chính output (`client_ready_watchlist`/
  `trading_watchlist`) ở NV3: một bước sector-cap (cap=2, `UNKNOWN` tính như
  một ngành) chạy SAU khi xếp hạng theo điểm, TRƯỚC khi cắt còn
  `watchlist_size`/`trading_watchlist_size` — hiện tại `final_watchlist.py`
  hoàn toàn chưa có bước này (chỉ cắt top-N theo điểm, không cap ngành) — đây
  là một thay đổi code thật ở NV3, không phải chỉ xác nhận cơ chế đã có.

---

## Ràng buộc kế thừa/mới

- Không tune trọng số theo bất kỳ kết quả nào trong vòng này.
- Không thêm nhân tố mới (chỉ kiểm định 7 thành phần + composite đã có).
- `assert_no_forward_columns` mở rộng vào `src/alpha/scoring.py::calculate_alpha_scores`
  (input guard, `mode="drop"` trên input trước khi tính điểm — không dùng
  `mode="raise"` vì nhiều script nghiên cứu vẫn truyền `stock_features.parquet`
  nguyên bản có cột forward cho MỤC ĐÍCH KHÁC của chính chúng, không phải lỗi)
  và `scripts/run_alpha_scoring.py` (output guard trước `save_parquet`, đúng
  pattern `final_watchlist.py::save_watchlist_outputs` đã dùng) — làm ở NV3 vì
  cùng vùng code, không phải một quyết định phụ thuộc kết quả IC/null test.
- Mọi trọng số/ngưỡng còn lại trong `DEFAULT_FINAL_WATCHLIST_CONFIG` sau khi
  thi hành nhánh: nếu không có trích dẫn bằng chứng cụ thể (report + commit) →
  dán nhãn `"unvalidated, giữ vì [lý do]"` ngay trong docstring/config comment,
  không âm thầm giữ nguyên không giải thích.
- Một lần chạy NV2. Không chạy lại để "thử" một biến thể khác sau khi thấy kết
  quả sơ bộ xấu.
