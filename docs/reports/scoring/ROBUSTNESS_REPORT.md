# ROBUSTNESS_REPORT — GĐ5, kiểm định lại thống kê + giải 2 căng thẳng từ GĐ4

**Toàn bộ round này là KIỂM ĐỊNH LẠI cái đã có — không nhân tố mới, không đổi
trọng số/tham số nào của `alpha_score` v2 hay `final_watchlist.py`, bất kể kết
quả.** Mục đích: đo và kết luận trung thực. `audit/PATH_TO_100.md` mục 9 (4/8).

**Trích dẫn nguồn**: `docs/reports/scoring/SCORE_V2_DESIGN.md`/`docs/reports/scoring/SCORE_V2_REPORT.md`,
`docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md`, `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`,
`docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`, `docs/reports/scoring/V2_STABILITY_NOTE.md` (mục 1 dưới đây, tài
liệu riêng do nội dung dài).

---

## 1. Nghịch lý 71.0 vs 52.8 — đã giải (chi tiết đầy đủ: `docs/reports/scoring/V2_STABILITY_NOTE.md`)

Ba nghi phạm: (a) khác cỗ máy gọi `run_portfolio_backtest` — loại ngay (cùng
hàm). (b) dữ liệu mới/2 mốc khác nhau. (c) hai bộ lọc GĐ4 thêm vào
(`trading_status==ACTIVE`, `minimal_eligible` = gate đầy đủ của
`final_watchlist.py`).

Chạy lại nguyên văn `scratch/score_v2_null_test.py` trên dữ liệu hiện hành
(2026-07-15): **71.0, giống hệt bản gốc** → loại trừ (b). Chạy thêm một cấu
hình (ACTIVE-only, không `minimal_eligible`): **70.5** — gần như không đổi.

**Kết luận bằng loại trừ**: gate `minimal_eligible` (ATR/`distance_ma20`/
drawdown/giá sàn, không chỉ thanh khoản/trend) là nguyên nhân gần như toàn bộ
của chênh lệch. `docs/reports/scoring/SCORE_V2_REPORT.md`'s 71.0 đúng cho v2 kiểm tra độc lập,
nhưng lạc quan hơn thực tế nếu trích dẫn làm bằng chứng cho v2 hoạt động BÊN
TRONG pipeline đầy đủ của `final_watchlist.py`. Khuyến nghị: nếu tương lai có
quyết định dùng lại v2 làm cơ sở xếp hạng cho `final_watchlist.py`, phải kiểm
định lại trong đúng bối cảnh gate đầy đủ, không trích dẫn 71.0.

## 2. Recalibrate t_NW của v2's 2 nhân tố trên dữ liệu hiện hành

| Nhân tố | t_NW gốc (`docs/reports/scoring/SCORE_V2_DESIGN.md`) | t_NW hiện hành (full, residualized) | Δ |
|---|---|---|---|
| `realized_vol_20d` | −5.41 | **−5.48** | +0.07 (mạnh hơn nhẹ) |
| `value_ma20` | −3.33 | **−3.37** | +0.04 (mạnh hơn nhẹ) |

**Cùng dấu, cùng bậc, không suy giảm — thực tế còn nhích lên nhẹ.** Ghi xác
nhận, không đổi gì (đúng nhánh "cùng dấu, cùng bậc" đã định trước trong yêu
cầu). Nguồn: `scratch/diagnose_factor_ic_robust.py` (script FACTOR_RETEST_V2
gốc, không sửa methodology, chạy lại trên `data/signals/stealth_accumulation_history.parquet`
đã đồng bộ đến 2026-07-15 tại GĐ4).

## 2b. Xác minh triển khai Newey-West HAC SE — 2026-07-22 (đáp lại adversarial review)

Adversarial review (AI thứ 2) nghi ngờ `_newey_west_mean_se` (định nghĩa
lặp lại ở `scratch/diagnose_factor_ic_robust.py` và 5 script `scratch/*`
khác cùng công thức) tính sai standard error HAC, có thể làm mọi `t_NW`
công bố trong dự án (mục 2 ở trên, `FACTOR_RETEST_V2_REPORT.md`,
`docs/reports/scoring/SCORE_FORENSIC_REPORT.md`, v.v.) bị lệch. **Đã verify độc lập trước khi
quyết định sửa hay không, đúng yêu cầu.**

**Phương pháp**: cài đặt/dùng `statsmodels` (đã có sẵn 0.14.2 trong môi
trường, KHÔNG thêm vào `requirements.txt` — xem lưu ý tương thích bên dưới),
so `_newey_west_mean_se(y, maxlags)` với `sm.OLS(y, const).fit(cov_type="HAC",
cov_kwds={"maxlags": maxlags}).bse[0]` (đúng API mà comment nguồn của hàm tự
nhận là tương đương) trên 2 bộ input:
1. **Dữ liệu tổng hợp** (AR(1), 27 tổ hợp `n∈{60,120,252}` ×
   `maxlags∈{5,10,20}` × tự tương quan `φ∈{0.0,0.3,0.6}` — trải rộng đúng
   dải `n`/`maxlags=20` dùng trong các report thật).
2. **Dữ liệu thật**: chuỗi IC ngày thật của 3 nhân tố (`realized_vol_20d`,
   `value_ma20`, `return_20d` vs `forward_return_20d`, n=1592–1608 ngày,
   `maxlags=20` — đúng tham số dùng để tạo bảng mục 2 ở trên) từ
   `data/signals/stealth_accumulation_history.parquet`.

**Kết quả: KHỚP TUYỆT ĐỐI ở mọi tổ hợp** — chênh lệch tương đối 0.0000% (đến
giới hạn làm tròn số thực) giữa `local_SE` và `sm_SE`, cả `t_naive`/`t_NW`
tính từ 2 nguồn giống nhau đến 4 chữ số thập phân trên dữ liệu thật:

| Nhân tố | n | mean_IC | local_SE | statsmodels_SE | local_t | sm_t |
|---|---|---|---|---|---|---|
| `realized_vol_20d` | 1602 | −0.04019 | 0.015525 | 0.015525 | −2.5886 | −2.5886 |
| `value_ma20` | 1608 | 0.00142 | 0.017465 | 0.017465 | 0.0813 | 0.0813 |
| `return_20d` | 1592 | −0.02085 | 0.013389 | 0.013389 | −1.5573 | −1.5573 |

(27/27 tổ hợp tổng hợp cũng khớp 0.0000% — bảng đầy đủ không đưa vào đây để
tránh dài dòng, tái lập được bằng script xác minh, xem dưới.)

**Kết luận: claim của adversarial review SAI — `_newey_west_mean_se` triển
khai ĐÚNG công thức Newey-West/Bartlett-kernel chuẩn, khớp `statsmodels`
(thư viện tham chiếu độc lập) không sai lệch có hệ thống ở bất kỳ `n`,
`maxlags`, hay mức tự tương quan nào đã thử.** Không sửa code — đúng nhánh
"khớp → claim sai, không sửa" đã định trước.

**Lưu ý tương thích không đổi**: `requirements.txt` đã ghi rõ
`statsmodels.api` (top-level) hiện KHÔNG import được trong môi trường này
(`scipy>=1.17` phá vỡ `statsmodels.distributions.discrete`) — vòng xác minh
này import trực tiếp `statsmodels.regression.linear_model.OLS` và
`statsmodels.stats.sandwich_covariance` (bỏ qua `statsmodels.api`), tránh
được lỗi. Không cài thêm gói nào, không đổi `requirements.txt`.

## 3. Khám nghiệm `risk_score` — trùng cluster hay độc lập?

**Ma trận correlation (Spearman cross-sectional trung bình 1,627 ngày,
`data/output/watchlist_validation_panel.parquet`):**

| So với `risk_score` | Corr trung bình |
|---|---|
| `realized_vol_20d` | −0.870 |
| `atr_pct_14` | −0.821 |
| `volatility_percentile` | −0.758 |
| `v2_score` (`alpha_score` v2) | **+0.822** |
| `tail_ratio_60d` | −0.442 (yếu nhất trong nhóm) |

**Phân rã t=+4.72 (full, residualized) đến từ thành phần nào** (t_NW từng
thành phần con, cùng dữ liệu, cùng script `diagnose_factor_ic_robust.py`):

| Thành phần con của `risk_score` | t_NW (full, residualized) |
|---|---|
| `atr_pct_14` | **−5.70** (mạnh nhất, còn hơn cả `realized_vol_20d`) |
| `realized_vol_20d` | −5.48 |
| `volatility_percentile` | −3.16 |
| `tail_ratio_60d` | **+0.98 — KHÔNG có ý nghĩa thống kê** |
| `risk_penalty_score` | không tính được (luôn NaN→0.5 trung lập, xem `docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2 phát hiện #4) |

**Kết luận: (i) risk_score ≈ cụm vol.** Cả 3 thành phần đóng góp thật
(`atr_pct_14`, `realized_vol_20d`, `volatility_percentile`) đều là biến thể
đo biến động — tương quan cực cao với `v2_score` (+0.822) và với chính
`realized_vol_20d` (−0.870, dấu âm vì `risk_score` thưởng vol THẤP).
`tail_ratio_60d` — thành phần duy nhất về mặt khái niệm khác "vol thuần" —
đóng góp t=+0.98, không có ý nghĩa. **KHÔNG soạn prereg đơn-nhân-tố riêng cho
`risk_score`** — bằng chứng của nó trùng với bằng chứng đã có của
`realized_vol_20d`/v2, không phải một nguồn thông tin độc lập mới.

## 4. FDR cho lịch sử test nhân tố (chi tiết: `data/output/fdr_correction_gd5.csv`)

Benjamini-Hochberg (q=0.05) trên 214 test gộp (192 `FACTOR_RETEST_V2` + 34
`WATCHLIST_VALIDATION` có t_NW xác định, chuyển p-value hai phía từ t_NW qua
xấp xỉ chuẩn).

| | Số sống sót |
|---|---|
| Ngưỡng thủ công `\|t_NW\|>3` | 27 |
| BH-FDR q=0.05 | **38** |

**Không có trường hợp nào đạt `\|t\|>3` mà KHÔNG sống sót qua FDR** — hai
danh sách không mâu thuẫn theo hướng đó. Nhưng **11 tổ hợp sống sót qua FDR mà
KHÔNG đạt `\|t\|>3`** (`near_pivot_score`, `atr_pct_14` raw, `dist_skew_60d`,
`pullback_from_high_20d`, `distance_to_pivot`, `volatility_dryup_score` raw,
`close_location_value`, `upper_wick_pct`, `dist_skew_60d` top150,
`realized_vol_20d` raw, `risk_score` raw — đủ danh sách trong CSV) — tức
**BH-FDR lỏng hơn ngưỡng thủ công trong trường hợp này**, ngược trực giác
thường gặp. Nguyên nhân: nhiều kết quả trong bảng có p-value rất nhỏ (cụm
điểm số ở đầu phân phối), kéo ngưỡng BH-FDR (tỷ lệ `rank/m × q`) lên cao hơn
tương ứng `\|t\|≈2.62` tại rank 38.

**Không dùng phát hiện này để nới lỏng ngưỡng `\|t\|>3` đã dùng xuyên suốt dự
án** — chỉ ghi nhận hai tiêu chí không tương đương, cả hai cần báo cùng nhau
từ nay (`CLAUDE.md` mục 9, mới thêm).

## 5. Deflated Sharpe Ratio + Bootstrap CI cho `alpha_score` v2

**Backtest chuẩn hiện hành** (cấu hình đang triển khai: `rebalance_period=20`,
`portfolio_size=10`, `sector_cap=2`, phí 0.15%, `min_value_ma20=10` tỷ,
`above_ma200`, 2022-01-01→2026-07-06, dữ liệu 2026-07-15): CAGR=+3.67%,
Sharpe(năm hoá)=0.32, MaxDD=−30.7%, N=1,120 ngày giao dịch.

**Cập nhật 2026-07-22 — đếm lại M qua TOÀN BỘ lịch sử git, không chỉ những
report đã dẫn (đáp lại adversarial review nghi ngờ M=560 đếm hẹp)**:

Quét `git log --all --diff-filter=A --name-only -- 'scratch/*.py'` — **57
script** từng được thêm vào `scratch/` xuyên suốt lịch sử dự án (không chỉ
những gì đang còn trích dẫn trong report chính thức). Phân loại từng script:
hạ tầng/data-engineering (backfill, fetch, render PDF — không tính vào M vì
không phải kiểm định giả thuyết alpha) vs. kiểm định thật (nhìn dữ liệu, thử
một giả thuyết/tổ hợp factor — tính vào M). Kết quả: **8 script/report đã
từng kiểm định nhưng CHƯA có trong bảng M cũ**, phần lớn từ giai đoạn "Phase
B" sớm hơn (trước khi các report GĐ-numbered tồn tại) và 2 report GĐ sau này
chưa được gộp vào bảng M:

| Nguồn mới phát hiện | Số tổ hợp | Ghi chú |
|---|---|---|
| `scratch/diagnose_broad_factor_ic.py` (Phase B, ~53 factor liên tục + boolean, 1 universe/target — đếm trực tiếp `CANDIDATES` dict) | 53 | Đợt factor screen SỚM HƠN, riêng biệt với `ROBUST_FACTOR_IC_REPORT`/`FACTOR_RETEST_V2` đã đếm — không lên report chính thức, chỉ còn lại trong `scratch/`. |
| `docs/reports/scoring/MARKET_REGIME_STUDY_REPORT.md` (H1/H2/H3 × 2 chỉ báo, đúng số tự công bố "0/12") | 12 | Prereg đầy đủ, kết quả âm tính — chưa từng được gộp vào M dù đã có report riêng. |
| `docs/reports/scoring/CRASH_RISK_RESEARCH_REPORT.md` (4 cấu hình overlay trong bảng kết quả chính) | 4 | |
| `docs/reports/scoring/SCORE_FORENSIC_REPORT.md` NV3 (`alpha_score` composite tự nó làm factor: 2 universe × 2 target chính + 3 giai đoạn stability — chỉ đếm hàng `alpha_score`, không đếm lại `realized_vol_20d` đã có sẵn trong M) | 8 | Lần đầu composite được test trực tiếp làm 1 factor. |
| `scratch/test_quantile_spread_analysis.py` (3 factor đã biết, lăng kính quantile-spread khác Spearman IC) | 3 | Cùng factor cũ nhưng phương pháp thống kê khác = một lần "nhìn" khác. |
| **Sửa lại dòng "portfolio construction sensitivity"**: `docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md` có bảng số thật (không cần ước lượng nữa) — **4 cấu hình** (size 5/10/20, size10+cap2), không phải 9 | **4** (thay 9 ước lượng) | Tìm thấy report gốc có bảng số chi tiết — đếm chính xác thay vì ước lượng. |

**Scenario bảo thủ (giữ nguyên bảng cũ, không đổi)**: M = **560** (như đã
công bố trước đây — coi là "sàn", chỉ tính những gì đã chính thức lên report
với bảng số rõ ràng đúng như cách đếm ban đầu).

**Scenario trung bình** (bảo thủ + 5 nguồn mới có bảng số RÕ RÀNG, sửa lại
dòng portfolio-sensitivity bằng số thật thay vì ước lượng):
560 + 53 + 12 + 4 + 8 + 3 − 5 (sửa 9→4) = **M = 635**.

**Scenario rộng** (trung bình + phần còn lại của lịch sử `scratch/` — 8 script
Phase B khác có dấu "one-off diagnostic"/"EXPLORATORY" trong docstring nhưng
KHÔNG có report chính thức đi kèm để lấy số chính xác, ước lượng thô 1-4 mỗi
script dựa trên số biến thể mô tả trong chính docstring —
`diagnose_alpha_source.py`≈2, `diagnose_backtest.py`≈3,
`test_evidence_based_score.py`≈1, `walk_forward_validation.py`≈1,
`rolling_walk_forward.py`≈4 (test nhiều overlay: stop-loss/regime/take-profit),
`test_corp_action_zerofill_alternative.py`≈1,
`validate_score_meta_ranking.py`+`_full.py`≈2, `car_s1_autopsy.py`≈1 —
tổng ≈15 — CỘNG `stock-decision-engine/SDE_SCORING_REPORT.md` Vòng 3's 28
test đã tự công bố (7 đối tượng × 2 universe × 2 target — composite KHÁC,
target KHÁC, nhưng cùng dự án/nhóm nên tính theo tinh thần "bao gồm rộng" đã
chọn từ đầu cho M):
635 + 15 + 28 = **M = 678**.

**Đây vẫn là ước lượng, KHÔNG phải số chính xác tuyệt đối** — đặc biệt
scenario rộng có 15 điểm ước lượng thô (docstring mô tả định tính, không có
bảng số). Nhưng khác với con số cứng M=560 cũ, dải 560→678 phản ánh trung
thực hơn sự không chắc chắn thật của việc đếm M từ lịch sử một dự án nghiên
cứu kéo dài nhiều tháng. Script tái lập: `scratch/recompute_dsr_m_scenarios.py`
(dùng lại nguyên vẹn `deflated_sharpe_ratio()` của `scratch/dsr_and_bootstrap_v2.py`,
chỉ đổi `n_trials`, cùng chuỗi return thật).

**Kết quả DSR theo cả 3 scenario** (công thức Bailey & López de Prado 2014;
phương sai Sharpe null giữa các thử nghiệm dùng xấp xỉ chuẩn V≈1/N do không
có phân phối Sharpe thật của từng thử nghiệm lịch sử — khai báo rõ đây là
xấp xỉ, không phải tinh chỉnh công thức gốc; SR_hat/skewness/kurtosis giống
hệt nhau ở cả 3 scenario, chỉ SR0/z/DSR đổi theo M):

| | Bảo thủ (M=560, cũ) | Trung bình (M=635) | Rộng (M=678) |
|---|---|---|---|
| SR_hat (năm hoá) | 0.319 | 0.319 | 0.319 |
| Skewness | −0.71 | −0.71 | −0.71 |
| Kurtosis (không trừ 3) | 9.82 | 9.82 | 9.82 |
| SR0 (ngưỡng kỳ vọng dưới H0) | 0.0922 (ngày) | 0.0933 (ngày) | 0.0939 (ngày) |
| z-statistic | −2.395 | −2.432 | −2.451 |
| **DSR** | **0.0083** | **0.0075** | **0.0071** |

**Kết luận không đổi ở cả 3 scenario**: DSR dao động rất hẹp (0.71%–0.83%),
đều gần như bằng 0 — **M có tăng lên tới 21% (560→678) cũng không đổi bản
chất kết luận: gần như không còn bằng chứng "kỹ năng thật" trong Sharpe quan
sát được của v2 ở cấu hình backtest chuẩn này.** Đây là một điểm mạnh của
chính DSR: hàm `Phi^-1` tăng rất chậm theo M ở vùng M lớn, nên sự không chắc
chắn thật trong việc đếm M (dải 560-678 tìm thấy ở đây) không tạo ra sự khác
biệt định tính trong kết luận cuối — không cần một con số M "chính xác tuyệt
đối" để tin vào kết quả này.

**DSR=0.71%–0.83% tuỳ scenario M (xem bảng 3 scenario ở trên) — sau khi khấu
trừ trung thực cho lịch sử đa kiểm định của dự án, gần như không còn bằng
chứng "kỹ năng thật" trong Sharpe quan sát được của v2 ở cấu hình backtest
chuẩn này, ở CẢ 3 cách đếm M.** Đây là một kết quả nghiêm túc, không phải lỗi
tính toán — z-statistic âm ở mọi scenario nghĩa là ngay cả SR_hat thô (0.32)
cũng thấp hơn ngưỡng kỳ vọng dưới giả thuyết "không có gì, chỉ đang chọn kết
quả tốt nhất trong hàng trăm lần thử" (SR0≈0.092–0.094/ngày ≈ 1.46–1.49 năm
hoá tuỳ scenario — đáng chú ý cao, phản ánh đúng bản chất DSR: càng nhiều thử
nghiệm, ngưỡng "may mắn thuần túy" càng cao).

**Bootstrap CI** (block bootstrap, block=20 ngày giao dịch, N=1,000, seed=42,
`src/simulation/bootstrap.py::block_bootstrap_returns` không sửa):

| | Điểm | CI 95% |
|---|---|---|
| CAGR | +3.67% | **[−9.58%, +19.32%]** |
| Sharpe (năm hoá) | 0.32 | **[−0.590, +1.317]** |

**Cập nhật 2026-07-21 — đã sửa lỗi tính toán ddof, KHÔNG PHẢI kết quả nghiên
cứu mới, kết luận không đổi**: `scratch/dsr_and_bootstrap_v2.py:125` dùng
`sims.std(axis=1)` trên mảng numpy — mặc định `ddof=0` của numpy (khác mặc
định `ddof=1` của pandas), phát hiện qua `docs/reports/codebase_audit/GSQUANT_REFERENCE_CHECK.md`.
Đã sửa thành `ddof=1` (khớp DSR's `sr_hat` vốn đã dùng `ddof=1` ngay trong
cùng file, khớp convention "unbiased estimator" của gs-quant/toàn dự án) và
CHẠY LẠI đúng script gốc (cùng seed=42, cùng dữ liệu, cùng cửa sổ backtest
2022-01-01→2026-07-06 — N=1,120 không đổi, xác nhận không có data drift kể
từ lần chạy gốc 2026-07-16) để lấy CI đúng thay cho CI cũ. Số CŨ (trước sửa):
CAGR CI không đổi (không dùng std, không bị ảnh hưởng); Sharpe CI CŨ =
**[−0.5907, +1.3172]**. So với CI MỚI (trong bảng trên): cận dưới dịch
+0.045%, cận trên dịch −0.045%, bề rộng CI hẹp lại 0.045% — khớp chính xác
hệ số lý thuyết `sqrt(N/(N-1))=sqrt(1120/1119)=1.000447` (mọi giá trị Sharpe
mô phỏng co lại theo đúng 1 hệ số hằng, vì mọi lần lặp bootstrap dùng cùng
`horizon_days=N=1120` — kiểm chứng bằng số thật khớp gần như tuyệt đối với
suy luận lý thuyết trước khi chạy lại). **Cả hai khoảng tin cậy (cũ và mới)
đều chứa 0 — kết luận "không thể bác bỏ giả thuyết hiệu suất thật=0" hoàn
toàn không đổi.** DSR=0.0083 không đổi (tính độc lập, đã `ddof=1` từ đầu,
không đi qua dòng bị lỗi). Đây là sửa lỗi tính toán, không phải điều chỉnh
sau khi nhìn kết quả — không tune, không mở lại kết luận.

**Cả hai khoảng tin cậy đều chứa 0** — không thể bác bỏ giả thuyết "hiệu suất
thật = 0" ở mức 95%, nhất quán với kết quả DSR.

**Chú thích cố định, áp dụng cho mọi số long-only trong tài liệu này và các
báo cáo tương lai**: mọi con số CAGR/Sharpe/excess-return long-only ở trên
CHƯA trừ mức sàn hiệu chỉnh survivorship bias đã định lượng ở
`docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md` (**+0.4%/+1.2%/+2.9%** ở cửa sổ 20/60/120
ngày giao dịch) — nếu trừ thêm, CAGR/Sharpe thật sự còn thấp hơn số đã báo ở
trên, không cao hơn.

---

## Tổng kết & không đổi gì

Theo đúng ràng buộc: **không có tham số/trọng số nào của `alpha_score` v2 hay
`final_watchlist.py` bị đổi trong round này**, bất kể DSR thấp hay CI chứa 0.
Đây là round ĐO, không phải round SỬA. Ba phát hiện đáng chú ý nhất, dành cho
quyết định của người dùng ở một round riêng có prereg:

1. **v2's DSR rất thấp (0.0083)** khi tính đến toàn bộ lịch sử thử nghiệm của
   dự án — gợi ý cân nhắc lại mức độ tin cậy đặt vào v2 làm cơ sở cho bất kỳ
   quyết định vận hành nào, dù nó vẫn là nhân tố có bằng chứng độc lập TỐT
   NHẤT trong toàn bộ danh mục đã test (t_NW cao nhất, ổn định qua thời gian
   theo GĐ2/GĐ4).
2. **71.0 không còn là con số đúng để trích dẫn cho v2 hoạt động bên trong
   `final_watchlist.py`** — dùng 52.8 (hoặc kiểm định lại) nếu có quyết định
   liên quan.
3. **`risk_score` không mang thông tin độc lập** — không cần theo đuổi thêm,
   giải phóng ưu tiên cho hướng khác nếu muốn tìm nhân tố thứ hai cho v3.

## Nghiệm thu

Full test suite chạy sau mọi thay đổi code (chỉ `CLAUDE.md` mục 9 và
`scratch/diagnose_factor_ic_robust.py`'s output-capture — không đụng code sản
xuất `src/`): 295 passed. Commit riêng từng nhiệm vụ vào `main`, không push.
