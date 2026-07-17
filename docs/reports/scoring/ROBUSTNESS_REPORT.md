# ROBUSTNESS_REPORT — GĐ5, kiểm định lại thống kê + giải 2 căng thẳng từ GĐ4

**Toàn bộ round này là KIỂM ĐỊNH LẠI cái đã có — không nhân tố mới, không đổi
trọng số/tham số nào của `alpha_score` v2 hay `final_watchlist.py`, bất kể kết
quả.** Mục đích: đo và kết luận trung thực. `audit/PATH_TO_100.md` mục 9 (4/8).

**Trích dẫn nguồn**: `docs/reports/scoring/docs/reports/scoring/SCORE_V2_DESIGN.md`/`docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md`,
`docs/reports/scoring/docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md`, `docs/reports/scoring/docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md`,
`docs/reports/scoring/docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`, `docs/reports/scoring/docs/reports/scoring/V2_STABILITY_NOTE.md` (mục 1 dưới đây, tài
liệu riêng do nội dung dài).

---

## 1. Nghịch lý 71.0 vs 52.8 — đã giải (chi tiết đầy đủ: `docs/reports/scoring/docs/reports/scoring/V2_STABILITY_NOTE.md`)

Ba nghi phạm: (a) khác cỗ máy gọi `run_portfolio_backtest` — loại ngay (cùng
hàm). (b) dữ liệu mới/2 mốc khác nhau. (c) hai bộ lọc GĐ4 thêm vào
(`trading_status==ACTIVE`, `minimal_eligible` = gate đầy đủ của
`final_watchlist.py`).

Chạy lại nguyên văn `scratch/score_v2_null_test.py` trên dữ liệu hiện hành
(2026-07-15): **71.0, giống hệt bản gốc** → loại trừ (b). Chạy thêm một cấu
hình (ACTIVE-only, không `minimal_eligible`): **70.5** — gần như không đổi.

**Kết luận bằng loại trừ**: gate `minimal_eligible` (ATR/`distance_ma20`/
drawdown/giá sàn, không chỉ thanh khoản/trend) là nguyên nhân gần như toàn bộ
của chênh lệch. `docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md`'s 71.0 đúng cho v2 kiểm tra độc lập,
nhưng lạc quan hơn thực tế nếu trích dẫn làm bằng chứng cho v2 hoạt động BÊN
TRONG pipeline đầy đủ của `final_watchlist.py`. Khuyến nghị: nếu tương lai có
quyết định dùng lại v2 làm cơ sở xếp hạng cho `final_watchlist.py`, phải kiểm
định lại trong đúng bối cảnh gate đầy đủ, không trích dẫn 71.0.

## 2. Recalibrate t_NW của v2's 2 nhân tố trên dữ liệu hiện hành

| Nhân tố | t_NW gốc (`docs/reports/scoring/docs/reports/scoring/SCORE_V2_DESIGN.md`) | t_NW hiện hành (full, residualized) | Δ |
|---|---|---|---|
| `realized_vol_20d` | −5.41 | **−5.48** | +0.07 (mạnh hơn nhẹ) |
| `value_ma20` | −3.33 | **−3.37** | +0.04 (mạnh hơn nhẹ) |

**Cùng dấu, cùng bậc, không suy giảm — thực tế còn nhích lên nhẹ.** Ghi xác
nhận, không đổi gì (đúng nhánh "cùng dấu, cùng bậc" đã định trước trong yêu
cầu). Nguồn: `scratch/diagnose_factor_ic_robust.py` (script FACTOR_RETEST_V2
gốc, không sửa methodology, chạy lại trên `data/signals/stealth_accumulation_history.parquet`
đã đồng bộ đến 2026-07-15 tại GĐ4).

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
| `risk_penalty_score` | không tính được (luôn NaN→0.5 trung lập, xem `docs/reports/scoring/docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 2 phát hiện #4) |

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

**Số lượng "thử nghiệm" (M) trong mẫu số DSR — khai báo cách đếm** (cộng dồn
số tổ hợp/cấu hình đã kiểm định trong lịch sử dự án, mỗi dòng lấy nguyên số đã
tự công bố trong chính report đó, không tự đếm lại):

| Nguồn | Số tổ hợp |
|---|---|
| `docs/reports/scoring/docs/reports/scoring/ROBUST_FACTOR_IC_REPORT.md` (44 nhân tố × 2 universe × 2 target) | 176 |
| `docs/reports/scoring/docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md` (48 nhân tố × 2 universe × 2 target — tái chạy trên dữ liệu sạch, tính là một đợt thử riêng) | 192 |
| `docs/reports/scoring/docs/reports/scoring/EVENT_DETECTION_REPORT.md` (factor-direction, lift-based) | 88 |
| `docs/reports/scoring/docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` (7 thành phần composite × ~4 cấu hình + v2/watchlist tối giản) | 38 |
| `docs/reports/scoring/docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` (tổ hợp holding-period) | 30 |
| Portfolio construction sensitivity (size 5/10/20 × sector cap, ước lượng từ commit `7c791d7`, không có bảng số chi tiết để đếm chính xác — ước lượng 3×3) | 9 (ước lượng) |
| `docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md` round 1 (3 tín hiệu × 3 lag × {test chính, CAR}) | 18 |
| `docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_PREREG_2_CLUSTER.md` (3 nhóm × 3 lag) | 9 |
| **Tổng M** | **560** |

**Đây là ước lượng công khai, không phải số chính xác** — đặc biệt dòng
"portfolio construction sensitivity" thiếu bảng số gốc để đếm chính xác, và
việc có nên tính `EVENT_DETECTION_REPORT`/disclosure event-study (kiểm định
biến khác, không phải trực tiếp v2) vào cùng mẫu số DSR của v2 là một lựa
chọn có thể tranh luận — chọn hướng BAO GỒM (đếm rộng) theo đúng tinh thần
DSR: mọi lần "nhìn vào dữ liệu và thử một giả thuyết" bởi cùng một dự án/nhóm
đều làm tăng rủi ro data-snooping chung, không chỉ riêng những gì trực tiếp
dẫn đến v2.

**Kết quả DSR** (công thức Bailey & López de Prado 2014; phương sai Sharpe
null giữa các thử nghiệm dùng xấp xỉ chuẩn V≈1/N do không có phân phối Sharpe
thật của từng thử nghiệm lịch sử — khai báo rõ đây là xấp xỉ, không phải tinh
chỉnh công thức gốc):

| | Giá trị |
|---|---|
| SR_hat (năm hoá) | 0.319 |
| Skewness | −0.71 |
| Kurtosis (không trừ 3) | 9.82 |
| SR0 (ngưỡng kỳ vọng dưới H0, M=560) | 0.092 (ngày) |
| z-statistic | −2.40 |
| **DSR** | **0.0083** |

**DSR=0.83% — sau khi khấu trừ trung thực cho lịch sử đa kiểm định của dự án,
gần như không còn bằng chứng "kỹ năng thật" trong Sharpe quan sát được của v2
ở cấu hình backtest chuẩn này.** Đây là một kết quả nghiêm túc, không phải lỗi
tính toán — z-statistic âm nghĩa là ngay cả SR_hat thô (0.32) cũng thấp hơn
ngưỡng kỳ vọng dưới giả thuyết "không có gì, chỉ đang chọn kết quả tốt nhất
trong 560 lần thử" (SR0≈0.092/ngày ≈ 1.46 năm hoá — đáng chú ý cao, phản ánh
đúng bản chất DSR: càng nhiều thử nghiệm, ngưỡng "may mắn thuần túy" càng cao).

**Bootstrap CI** (block bootstrap, block=20 ngày giao dịch, N=1,000, seed=42,
`src/simulation/bootstrap.py::block_bootstrap_returns` không sửa):

| | Điểm | CI 95% |
|---|---|---|
| CAGR | +3.67% | **[−9.58%, +19.32%]** |
| Sharpe (năm hoá) | 0.32 | **[−0.59, +1.32]** |

**Cả hai khoảng tin cậy đều chứa 0** — không thể bác bỏ giả thuyết "hiệu suất
thật = 0" ở mức 95%, nhất quán với kết quả DSR.

**Chú thích cố định, áp dụng cho mọi số long-only trong tài liệu này và các
báo cáo tương lai**: mọi con số CAGR/Sharpe/excess-return long-only ở trên
CHƯA trừ mức sàn hiệu chỉnh survivorship bias đã định lượng ở
`docs/reports/scoring/docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md` (**+0.4%/+1.2%/+2.9%** ở cửa sổ 20/60/120
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
