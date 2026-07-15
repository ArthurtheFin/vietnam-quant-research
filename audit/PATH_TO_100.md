# Path to 100/100 — What Has to Change

Nguồn: `audit/quantitative_finance_scorecard.md`, `audit/quantitative_finance_gap_matrix.csv`,
`audit/critical_findings.md`, `audit/remediation_roadmap.md` (audit ngày
2026-07-12, commit `2c3d11c`). Tài liệu này không phải audit mới — nó
sắp xếp lại đúng những phát hiện đã có, theo hướng "cần làm gì để lấy
trọn điểm", để dễ theo dõi tiến độ.

**Điểm hiện tại: 58/100 (Experimental).** Hai điều quan trọng cần hiểu
trước khi đọc phần còn lại:

1. **4 critical failure gate đang bật sẽ chặn điểm cao dù tổng điểm số
   học có đạt 100.** Theo nguyên tắc của khung audit: "A high total
   score must not override a critical failure." Nghĩa là dù cộng đủ
   100 điểm theo bảng dưới, dự án vẫn KHÔNG được xếp hạng
   production-grade cho đến khi cả 4 gate này được đóng. Đây là việc
   phải làm trước tiên, không phải việc làm sau cùng.
2. Nhiều mục "MISSING" dưới đây (đặc biệt mục 1 — point-in-time
   universe) là công việc lớn, có thể cần dữ liệu bên ngoài không
   kiểm soát được hoàn toàn. Tài liệu này liệt kê đầy đủ để bạn thấy
   toàn cảnh, không có nghĩa tất cả đều khả thi ngắn hạn.

---

## Việc phải làm TRƯỚC — 4 critical gate (bắt buộc, không đổi bằng điểm số)

Không có mục nào trong 10 mục điểm số bên dưới có ý nghĩa cho đến khi 4
việc này xong, vì chúng override toàn bộ:

### Gate #3 — Survivorship bias nghiêm trọng
- **Vấn đề**: không có nơi nào trong code dựng được universe tại một
  thời điểm lịch sử (point-in-time) — mọi backtest chạy trên 500 mã
  đang niêm yết hôm nay, chiếu ngược về 2020. Mã bị hủy niêm yết/sáp
  nhập/đình chỉ vĩnh viễn hoàn toàn vô hình.
- **Cần làm**: tìm hoặc dựng một nguồn dữ liệu lịch sử niêm yết/hủy
  niêm yết (SSI, bản tin HOSE/HNX/UPCOM, hoặc nhà cung cấp dữ liệu thứ
  ba). Việc này lớn nhất trong toàn bộ danh sách — có thể cần trả phí
  cho vendor dữ liệu.
- **Việc nhỏ hơn có thể làm ngay**: chạy `check_survivorship_bias`
  (đã có sẵn trong `src/validation/bias_checks.py` nhưng chưa từng
  chạy trên dữ liệu thật) để ít nhất định lượng được mức độ ảnh hưởng
  hiện tại, trong lúc chờ có dữ liệu đầy đủ.

### Gate #6 — Pipeline sản xuất vẫn đọc dữ liệu đã biết là lỗi
- **Vấn đề**: `scripts/build_portfolio_stack.py` đọc trực tiếp
  `data/processed/stock_features.parquet` — file mà chính
  `DATA_BASELINE.md` của dự án đã ghi rõ là còn lỗi trộn raw/adjusted
  close cho một số mã chưa xác định hết, trong khi `data/full_history_v2`
  (đã sửa lỗi) không được dùng ở bước này.
- **Cần làm**: gộp `data/full_history_v2` vào `data/processed/`
  (đúng như `DATA_BASELINE.md` đã đề xuất), hoặc trỏ thẳng
  `build_portfolio_stack.py` sang đọc `data/full_history_v2`.
- **Độ phức tạp**: M (trung bình) — không cần dữ liệu mới, chỉ cần sửa
  đường dẫn đọc dữ liệu + kiểm chứng lại.

### Gate #12 — Kết quả không tái lập được
- **Vấn đề**: đã tự tính lại độc lập báo cáo `portfolio_risk_report.json`
  đã commit, dùng đúng phương pháp tài liệu mô tả, đúng trọng số, đúng
  file nguồn, đúng ngày cắt — không ra lại được `annual_return`,
  `annual_volatility`, `sharpe_ratio`, `max_drawdown`, thậm chí số dòng
  dữ liệu cũng khác (1317 báo cáo vs 1621 tính lại hôm nay).
- **Cần làm**: mỗi lần sinh báo cáo, lưu kèm hash/snapshot đúng phần dữ
  liệu đầu vào đã dùng (ví dụ hash nội dung file
  `stock_features.parquet` tại thời điểm chạy) để sau này có thể dựng
  lại chính xác.
- **Độ phức tạp**: M — thêm field vào `pipeline_metadata.json`/
  `write_run_snapshot`, không cần đổi công thức tính.

### Gate #17 — Một thành phần "chưa kiểm chứng" vẫn được trình bày như đã kiểm chứng
- **Vấn đề**: `final_watchlist.py`'s `relative_strength_score` vẫn
  gộp `alpha_rs_score` — đúng nhân tố mà `SCORE_FORENSIC_REPORT.md`
  của chính dự án đã kết luận là thủ phạm chính gây lỗ -59.7% trong
  một fold backtest thật (IC lật từ +0.0141 xuống -0.1060 năm 2026).
  Lỗi tương tự ở `momentum_score` đã được sửa trong phiên làm việc
  này (`517a3d0`/`327b8d4`) nhưng nhân tố song sinh này thì chưa.
- **Cần làm**: gỡ `alpha_rs_score` khỏi `relative_strength_score`,
  đúng cách đã làm với `momentum_score`.
- **Độ phức tạp**: S (nhỏ) — sửa nhanh nhất trong 4 gate, nên làm
  đầu tiên vì rẻ và rõ ràng nhất.

---

## Lộ trình lấy điểm theo từng mục (58 → 100)

### 1. Data Quality and Governance — hiện 9/15, cần +6

| Việc cần làm | Điểm ước tính |
|---|---|
| Sửa Gate #6 (đọc đúng dataset) — xem trên | phần của critical gate, không tính điểm riêng nhưng bắt buộc |
| Mở rộng `validate_ohlcv` để check đủ: `high>=max(open,close)`, `low<=min(open,close)`, khoảng trống lịch giao dịch, return bất thường, dtype/schema drift; thêm `tests/test_validators.py` | +2 |
| Thêm git commit hash + config-version vào mọi `pipeline_metadata.json`/run snapshot | +2 |
| Widen khóa tự nhiên disclosure (`NATURAL_KEY`) để không mất 829 dòng trùng khóa (1.4%) | +1 |
| Đồng bộ cơ chế loại trừ GEE giữa 2 pipeline giá và disclosure (`load_universe_symbols` vs `get_universe_symbols`) | +1 |

### 2. Universe and Eligibility — hiện 6/8, cần +2

| Việc cần làm | Điểm ước tính |
|---|---|
| Point-in-time universe reconstruction — chính là Gate #3 ở trên | phần của critical gate |
| Thêm gate tỷ lệ zero-volume (N/M phiên gần nhất không có khối lượng) làm proxy phát hiện đình chỉ giao dịch | +1 |
| Quyết định rõ: sector mapping có bắt buộc để đủ điều kiện hay chỉ để báo cáo — và làm theo quyết định đó | +1 |

### 3. Signal and Alpha Quality — hiện 4/12, cần +8 (mục cần cải thiện nhiều nhất)

**CẬP NHẬT 2026-07-15 (GĐ4) — `WATCHLIST_VALIDATION_PREREG.md`/`WATCHLIST_VALIDATION_REPORT.md`,
commit range `eb765e6`..`36bba52`:** kiểm định IC/null-test đầu tiên cho toàn
bộ composite `final_watchlist` đã chạy. Kết quả: composite KHÔNG đạt tiêu chí
đã khóa (IC t_NW gần 0, không cùng dấu 3 giai đoạn; null test có 1/5 fold sụp
xuống percentile 0.15). Mốc so sánh "watchlist tối giản" (v2 + gate hiện hành)
cũng không đạt, sát ngưỡng nhưng không đạt theo đúng chữ tiêu chí đã khóa. Theo
cây quyết định đã pre-register: **Nhánh C — `final_watchlist.py` chuyển sang
"không xếp hạng alpha", sắp theo thanh khoản (`value_ma20`), dán nhãn rõ**
(`ranking_mode="no_alpha_liquidity_sort"`, `src/screening/final_watchlist.py`).
Đây không phải điểm số học đạt được theo bảng dưới — là một phát hiện thật cần
sửa vận hành, đã sửa.

| Việc cần làm | Điểm ước tính | Trạng thái |
|---|---|---|
| Sửa Gate #17 (gỡ `alpha_rs_score`) — xem trên | phần của critical gate | Đã xong (GĐ trước) |
| Kiểm định IC/backtest riêng cho TOÀN BỘ composite `final_watchlist` (không chỉ 2 nhân tố của `alpha_score` v2) — hiện 75/100 điểm trọng số của composite này (trend 25 + momentum 20 + relative_strength 20 + liquidity 10) chưa từng được kiểm định ở cấp độ composite | +3 | **XONG — kết quả âm tính, xem trên. Không cộng điểm theo nghĩa "đạt", nhưng khoảng trống kiểm định đã đóng.** |
| Sửa chiều xếp hạng sai: `liquidity_score` (value_ma20, đang ngược với bằng chứng IC đã có) và `tail_ratio_60d` trong `risk_score` | +1 | `liquidity_score`: XONG (gỡ khỏi ranking hoàn toàn, không chỉ đổi chiều — `WATCHLIST_VALIDATION_REPORT.md` mục 2 xác nhận chiều hiện tại sai, t_NW=−4.19). `tail_ratio_60d` trong `risk_score`: CHƯA — ngoài phạm vi round này, vẫn mở. |
| Bổ sung trích dẫn bằng chứng cho mọi trọng số/ngưỡng trong `DEFAULT_FINAL_WATCHLIST_CONFIG` (hiện không có báo cáo nào giải thích tại sao là 25/20/20/10/5/10/10) | +1 | **XONG** — docstring `DEFAULT_FINAL_WATCHLIST_CONFIG`'s `weights` (`src/screening/final_watchlist.py`) ghi đầy đủ bằng chứng IC từng thành phần + lý do "unvalidated, giữ vì hiển thị". |
| Mở rộng `assert_no_forward_columns` sang `src/alpha/scoring.py` và `scripts/run_alpha_scoring.py` (hiện chỉ có ở 2 điểm output, không có ở nơi tính điểm) | +2 | **XONG** — commit `c0a4d82`. |
| Còn lại (~1 điểm): tuỳ mức độ kiểm định đạt được ở composite | +1 | Chưa cộng — composite không đạt kiểm định; điểm này chờ một nhân tố mới qua đúng quy trình (ứng viên: `risk_score`, t_NW=+4.72, xem `WATCHLIST_VALIDATION_REPORT.md` mục 2). |

**Phát hiện phụ, ngoài bảng điểm gốc**: `momentum_score` và
`relative_strength_score` cho IC giống hệt nhau về mặt toán học (trừ đi lợi
nhuận benchmark — hằng số theo ngày — không đổi thứ hạng cross-sectional) —
một dư thừa thật trong công thức, ghi nhận cho thiết kế lại tương lai, không
sửa trong round này.

### 4. Expected Return Model — hiện 1/8, cần +7

| Việc cần làm | Điểm ước tính |
|---|---|
| Quyết định: có cần mô hình expected-return thật (không phải rank score) trong pipeline sản xuất không? Nếu không cần theo thiết kế (hệ thống thuần risk-based), phải nói rõ trong tài liệu — hiện code có sẵn (`src/portfolio/returns.py`, `src/portfolio/optimization.py`) nhưng chết (dead code), không dùng | quyết định trước, +2 nếu chỉ cần tài liệu hoá rõ ràng |
| Nếu quyết định CẦN: nối `estimate_expected_returns` (hoặc mô hình tốt hơn — factor model, Bayesian shrinkage) thật sự vào `build_portfolio_stack.py`, kiểm định out-of-sample | +5 nếu làm đầy đủ |

*(Đây là mục có khoảng trống lớn nhất theo tỷ lệ — vì hiện gần như
không có gì chạy thật trong sản xuất. Cân nhắc: có thể dự án này chủ
đích là risk-based, không cần expected-return — nếu vậy, nói rõ trong
`DEPLOY_REPORT.md`/`README.md` vẫn lấy được phần lớn điểm mà không cần
xây mô hình mới.)*

### 5. Covariance, Correlation, Portfolio Risk — hiện 8/12, cần +4

| Việc cần làm | Điểm ước tính |
|---|---|
| Sửa Gate #12 (reproducibility) — xem trên, đây là phần lớn nhất của mục này | phần của critical gate |
| Thay `shrink_covariance` (hiện là fixed-intensity 0.15, không phải Ledoit-Wolf/OAS thật) bằng `sklearn.covariance.LedoitWolf` (đã có sẵn trong requirements.txt) | +2 |
| Thêm `min_periods` cho `calculate_covariance_matrix` + eigenvalue-based PSD repair cho `_sanitize_covariance` | +1 |
| Tính thật các field đã khai báo nhưng chưa tính: `tracking_error`, `information_ratio`, `active_share`, `alpha`, `r_squared` (hiện chỉ là placeholder 0.0/1.0 trong template rỗng) | +1 |

### 6. Portfolio Construction and Optimization — hiện 9/12, cần +3

| Việc cần làm | Điểm ước tính |
|---|---|
| Hợp nhất 2 mô hình transaction cost đang lệch nhau (0.15% ở `portfolio_backtest.py` vs 0.4% ở `simulator.py`) — cần xác minh với biểu phí/thuế VN thật | +1 |
| Cho `run_portfolio_backtest` dùng lại helper đã test (`equal_weight_allocation`, v.v.) thay vì viết tay trùng lặp | +1 |
| Thống nhất 2 cơ chế sector-cap (đếm số mã vs giới hạn trọng số) thành một | +1 |

### 7. Monte Carlo and Random Portfolio Search — hiện 3/5, cần +2

| Việc cần làm | Điểm ước tính |
|---|---|
| Thêm `random_state` cho `generate_random_weights`/`generate_random_portfolios` (hiện không seed, khác với module song sinh `src/models/monte_carlo.py` đã seed đúng) | +1 |
| Sửa cách trình bày "best random Sharpe" trong notebook 14 — báo cáo dải phân vị (percentile range) thay vì một con số "tối ưu" duy nhất từ hàng nghìn mẫu ngẫu nhiên trong mẫu (đã được chính `AUDIT_REPORT.md` H5 gắn cờ DEFERRED từ trước) | +1 |

### 8. Backtesting and Validation — hiện 10/15, cần +5

| Việc cần làm | Điểm ước tính |
|---|---|
| Sửa Gate #3 (survivorship bias trong backtest) — xem trên | phần của critical gate |
| Thực thi board lot size (`lot_size: 100` đã khai báo trong config nhưng grep xác nhận không dùng ở đâu cả) | +1 |
| Phân rã mô hình chi phí giao dịch: commission + thuế bán (0.1% VN, cần xác minh bên ngoài) + phí sàn + spread/slippage, thay vì một tỷ lệ phẳng | +1 |
| Thêm giới hạn quy mô lệnh theo thanh khoản thực tế (participation-rate cap theo ADV), ngoài bộ lọc thanh khoản đủ điều kiện hiện có | +1 |
| Tăng số lượng walk-forward fold (hiện chỉ 5 fold theo năm — quá ít, mọi thống kê trung bình đều có sai số chuẩn lớn) bằng cách chuyển sang cửa sổ rolling theo tháng/quý | +2 |

### 9. Robustness, Overfitting, Statistical Validity — hiện 4/8, cần +4

| Việc cần làm | Điểm ước tính |
|---|---|
| Tính Deflated Sharpe Ratio cho điểm số sản xuất (`alpha_score` v2) | +1 |
| Áp dụng hiệu chỉnh đa kiểm định chính thức (Benjamini-Hochberg FDR hoặc Bonferroni) cho 192 tổ hợp nhân tố đã test trong `FACTOR_RETEST_V2_REPORT.md` — hiện chỉ có ngưỡng `\|t\|>3` không chính thức | +1 |
| Dùng `src/simulation/bootstrap.py` (đã có, đã seed đúng) để tính khoảng tin cậy bootstrap cho CAGR/Sharpe chính, không chỉ để vẽ biểu đồ khách hàng | +1 |
| Tách riêng dữ liệu holdout cho việc chọn tham số portfolio construction (size/sector cap), không dùng chung 5 fold với fold dùng để báo cáo hiệu suất | +1 |

### 10. Engineering, Reproducibility, Production Readiness — hiện 4/5, cần +1

| Việc cần làm | Điểm ước tính |
|---|---|
| Pin chính xác phiên bản dependency (`requirements.txt` hiện chỉ `>=`) hoặc thêm lockfile | +0.3 |
| Bổ sung ngày Tết âm lịch vào `config/vn_market_holidays.csv` (hiện tự nhận trong code là chỉ có ngày dương lịch cố định) | +0.3 |
| Thêm cơ chế ghi file an toàn (temp-file + rename) thay vì ghi trực tiếp | +0.2 |
| Xác minh lại `run_all_notebooks.sh` có báo lỗi đúng khi notebook thật sự lỗi hay không (đã nghi vấn từ `AUDIT_REPORT.md` J1, chưa kiểm chứng lại bằng cách chạy thật) | +0.2 |

---

## Thứ tự làm gợi ý (không phải bắt buộc, nhưng hợp lý theo chi phí/lợi ích)

1. **Trước tiên — rẻ và có tác động critical-gate lớn nhất**: gỡ
   `alpha_rs_score` (Gate #17, việc nhỏ S), trỏ lại
   `build_portfolio_stack.py` sang `full_history_v2` (Gate #6, việc M),
   thêm hash/snapshot dữ liệu vào metadata (Gate #12, việc M). Ba việc
   này đóng 3/4 gate với chi phí thấp.
2. **Sau đó**: các việc P1 rẻ (S/M) ở mục Data Quality, Signal/Alpha,
   Engineering — phần lớn là thêm test, thêm field, sửa hướng xếp
   hạng — không cần dữ liệu mới.
3. **Song song, chạy dài hạn**: khảo sát nguồn dữ liệu point-in-time
   universe (Gate #3) — đây là việc lớn nhất, nên bắt đầu sớm vì tốn
   thời gian nhất, dù không chặn các việc khác.
4. **Cuối cùng**: robustness thống kê (DSR, FDR, bootstrap CI, tăng số
   fold) — cần dữ liệu/backtest đã ổn định trước, làm sau khi các mục
   trên xong sẽ có ý nghĩa hơn (tránh phải làm lại nếu dataset đổi).

**Lưu ý quan trọng**: đạt 100/100 theo bảng điểm không tự động nghĩa là
sẵn sàng dùng vốn thật — đó là ngưỡng "Production-grade candidate"
(90-100) với điều kiện "no critical failures exist". Việc đóng 4 gate ở
đầu tài liệu này quan trọng hơn nhiều so với việc kiếm nốt vài điểm nhỏ
ở mục Engineering hay Monte Carlo.
