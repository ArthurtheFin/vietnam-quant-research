# SDE_SCORING_REPORT — kết quả Vòng 3, kiểm định điểm số stock-decision-engine

**Kết quả của lần chạy DUY NHẤT theo `SDE_SCORING_PREREG.md` (commit
`4b88631`), khóa trước khi chạy.** Không có tham số/tiêu chí nào bị đổi sau
khi nhìn kết quả. Scripts: `scratch/sde_prereg_round3_panel.py` (panel
point-in-time, lịch rebalance toàn cục), `scratch/sde_prereg_round3_panel_foldaligned.py`
(panel thứ hai, lịch rebalance khớp đúng từng fold — cần thiết vì
`run_portfolio_backtest` tự tính lại lịch rebalance theo từng fold, không
dùng lịch toàn cục), `scratch/sde_prereg_round3_ic_null.py` (IC Newey-West +
FDR + null test). Kết quả thô:
`data/full_history_v2/sde_round3_{panel,panel_foldaligned,ic_main,ic_periods,fdr,null_test}.{parquet,csv}`.

**Kết luận một dòng: Nhánh C** — không thành phần nào (composite
`final_score` hay từng sub-score riêng) đạt tiêu chí đã khóa trước.
`stock-decision-engine/src/scoring.py` đã gỡ bỏ hoàn toàn `final_score`
tổng hợp và `decision` label — chỉ còn bảng dữ kiện thô có ngữ cảnh, đã thi
hành trong code (commit `aa773a2`), regenerate 20 output cũ, cập nhật
README/notebook.

---

## 1. Bridge kỹ thuật đã xây (mục 1 prereg)

Vòng hóa `enrich()` + `bootstrap_monte_carlo()` + `score_decision()` (bản
gốc, trước khi gỡ) theo từng (symbol, ngày rebalance), đúng
`lookback_days=756` kết thúc TẠI ngày đó, `backtest={"available": False}`
cho mọi ngày lịch sử (trung thực — `breakout_20d_trade_cards.parquet` chỉ
là snapshot hiện tại, không có bằng chứng backtest point-in-time nào từng
tồn tại cho quá khứ, đúng caveat đã ghi ở prereg mục 3).

**Phát hiện phát sinh khi build panel, phải sửa để kiểm định đúng**:
`run_portfolio_backtest` tự tính lại lịch rebalance (`all_dates[::20]`)
TỪ CHÍNH dữ liệu đã cắt theo từng fold — khác pha với lịch rebalance toàn
cục (tính từ 2020-01-02) mà panel IC test dùng. Nếu dùng chung một panel
cho cả IC lẫn null test, hầu hết ngày quyết định nội bộ của null test sẽ
không khớp ngày nào trong panel, âm thầm rơi vào fallback mean-reversion
mặc định của `run_portfolio_backtest` thay vì dùng `final_score` thật —
lỗi cùng loại với lỗi cột trùng tên đã ghi trong
`scratch/watchlist_validation_null.py`. Xây thêm panel thứ hai
(`sde_round3_panel_foldaligned.parquet`, 18.131 dòng) chấm điểm đúng những
ngày `run_portfolio_backtest` sẽ thực sự dùng cho từng fold, dùng riêng cho
null test.

## 2. Universe & phạm vi lịch sử thực tế

Universe `trading_status==ACTIVE`: 462 mã. Panel chính: **17.620 dòng
scored, 438 mã, 204 ngày phân biệt, từ 2023-01-16 đến 2026-07-03**.
2.708 lượt (mã, ngày) bị loại vì chưa đủ 756 phiên lịch sử (finding #9) —
KHÔNG chấm trên cửa sổ cụt, đúng ràng buộc.

**Ngày bắt đầu hợp lệ: 2023-01-16.** Đây là hệ quả trực tiếp của
`lookback_days=756` (config gốc, không đổi) cộng với việc backfill đầy đủ
2020-2026 chỉ hoàn tất 2026-07-10 — trước đó SDE không thể có đủ 756 phiên
cho hầu hết mã. Nghĩa là SDE **về cấu trúc** chỉ có thể kiểm định trên
~3.5 năm lịch sử gần nhất, ngắn hơn nhiều so với chuỗi 2020-2026 đầy đủ mà
`alpha_score`/`final_watchlist` của dự án chính dùng.

## 3. Kết quả IC Newey-West (28 test: 7 đối tượng × 2 universe × 2 target)

7 đối tượng đúng mục 3 prereg (loại `simulation`, phần backtest của
`alpha`, `market_regime` — lý do xem prereg): `final_score`, `trend`,
`momentum`, `relative_strength`, `risk`, `liquidity`, `alpha` (CAPM-only,
tối đa 80/100 điểm nội bộ vì thiếu phần backtest).

| Factor | Universe | Target | mean_IC | t_NW | n_days |
|---|---|---|---|---|---|
| **final_score** | full | residualized | +0.0164 | **+1.28** | 43 |
| final_score | full | raw | +0.0148 | +0.95 | 43 |
| final_score | top150 | residualized | +0.0145 | +0.78 | 43 |
| final_score | top150 | raw | +0.0052 | +0.34 | 43 |
| **risk** | full | residualized | +0.0570 | **+3.96** | 43 |
| **liquidity** | full | residualized | −0.0425 | **−3.80** | 43 |
| risk | full | raw | +0.0419 | +2.56 | 43 |
| trend | full | residualized | +0.0190 | +1.16 | 43 |
| momentum | full | residualized | +0.0075 | +0.72 | 43 |
| relative_strength | full | residualized | +0.0049 | +0.44 | 43 |
| alpha (CAPM-only) | full | residualized | +0.0081 | +0.98 | 43 |

(Bảng đầy đủ 28 dòng: `data/full_history_v2/sde_round3_ic_main.csv`.)

Chỉ 43 ngày cross-section đạt `MIN_ELIGIBLE≥15` mã/ngày trong toàn bộ
2023-01→2026-07 (204 ngày panel thô, phần lớn bị loại vì cross-section quá
mỏng — hệ quả trực tiếp của universe hẹp mục 2).

## 4. 3-giai đoạn — KHÔNG TÍNH ĐƯỢC (phát hiện quan trọng, không có trong prereg)

Chia 43 ngày thành 3 giai đoạn bằng nhau (tertile) cho ra **~15 ngày/giai
đoạn** — dưới ngưỡng tối thiểu N≥30 mà `newey_west_tstat()` yêu cầu (đúng
hàm đã dùng cho toàn dự án, không nới lỏng riêng cho SDE). Kết quả: **mọi
`t_NW` theo giai đoạn đều là NaN, cho cả 7 đối tượng** — tiêu chí "đồng dấu
cả 3 giai đoạn" trong cây quyết định (mục 4 prereg) không thể xác nhận
được cho bất kỳ đối tượng nào, không phải vì bằng chứng yếu mà vì **về mặt
cấu trúc không đủ dữ liệu để tính**.

Đây là giới hạn nội tại của `lookback_days=756` kết hợp với ngày backfill
hoàn tất muộn (mục 2) — không phải lỗi thực thi vòng này, và không có cách
sửa trong phạm vi round này (nới lookback xuống sẽ vi phạm "không đổi công
thức trước khi có bằng chứng"; đợi thêm dữ liệu tương lai là lựa chọn duy
nhất hợp lý).

## 5. BH-FDR (q=0.05, m=28)

**k=2 sống sót**, cả hai đều KHÔNG phải `final_score`:

| Factor | Universe | Target | t_NW | p_value | survives_fdr_q05 |
|---|---|---|---|---|---|
| risk | full | residualized | +3.96 | 0.0001 | **True** |
| liquidity | full | residualized | −3.80 | 0.0001 | **True** |

`final_score` (rank 6/28, p=0.20) không sống sót FDR.

## 6. Null test (final_score, 2.000 danh mục/fold, seed=42)

| Fold | real_cagr | percentile | n_scored |
|---|---|---|---|
| 2022 | — | — (0 ngày scored — trước 2023-01-16) | 0 |
| 2023 | −4.6% | **0.75** | 4.179 |
| 2024 | 0.0% | 7.8 | 5.323 |
| 2025 | 0.0% | 21.1 | 5.592 |
| 2026 | 0.0% | 95.4 | 3.037 |

Trung bình 4 fold có dữ liệu: **31.2** (không >60). Fold 2023 percentile
0.75 (<10) — thất bại điều kiện "không fold nào <10". **Cả hai vế OR của
Nhánh A (IC hoặc null) đều không đạt.**

(2024/2025 `real_cagr=0.0%` khớp `n_scored` lớn nhưng portfolio rỗng ở
phần lớn ngày rebalance nội bộ — không phải lỗi tính toán, kiểm tra qua
`n_scored_symbol_dates` xác nhận vẫn có dữ liệu; số 0.0% chính xác gợi ý
gate `above_ma200`/`min_value_ma20` cắt hết candidate ở nhiều rebalance,
một hiện tượng tương tự "gate loại gần hết universe" đã ghi trong
`PROJECT_STATE.md` mục 4 cho dự án chính — không điều tra sâu hơn trong
round này, ghi lại làm quan sát.)

## 7. Áp cây quyết định (mục 4 prereg)

- **Nhánh A** (`final_score`): IC criterion = **False** (t_NW=1.28≠>3, kể
  cả bỏ qua yêu cầu 3-giai-đoạn không tính được). Null criterion =
  **False** (31.2 không >60, có fold <10). → **Nhánh A KHÔNG đạt.**
- **Nhánh B** (≥1 sub-score đạt riêng, `|t_NW|>3` đồng dấu 3 giai đoạn):
  `risk` có `t_NW=+3.96>3` và sống sót FDR trên bảng chính, NHƯNG tiêu chí
  đầy đủ đòi hỏi "đồng dấu 3 giai đoạn" — **không tính được** (mục 4).
  `liquidity` sống sót FDR nhưng ÂM (bằng chứng để LOẠI, không phải để
  xây dựng lại composite quanh nó). Không có đối tượng nào thỏa ĐẦY ĐỦ
  tiêu chí Nhánh B như đã khóa (sub-score không có lối thoát null-test
  thay thế như `final_score`). → **Nhánh B không xác nhận được đầy đủ —
  vùng xám.**
- **Vùng xám → chọn nhánh thận trọng hơn, ưu tiên C trên B** (mục 4
  prereg, khóa trước): **NHÁNH C.**

## 8. Đối chiếu với kỳ vọng đã ghi trước (mục 5 prereg) — cả hai chiều

1. **Kỳ vọng #2 (mục 5.2)**: "`trend`/`momentum`/`relative_strength` nhiều
   khả năng KHÔNG đạt `|t_NW|>3` dương ổn định" — **ĐÚNG như kỳ vọng**:
   t_NW lần lượt +1.16/+0.72/+0.44 (full, residualized), đều xa ngưỡng 3.
   Không phải bất ngờ, không cần soát lại phương pháp theo quy ước đã khóa.
2. **Kỳ vọng #3 (mục 5.3)**: "nếu `risk` có bằng chứng riêng dương, khả
   năng cao trùng cụm biến động với `realized_vol_20d`, không phải thông
   tin độc lập" — **kỳ vọng này ĐÚNG HƯỚNG**: `risk` là đối tượng duy nhất
   có t_NW dương mạnh (+3.96, sống sót FDR) trong toàn bảng, khớp với dự
   đoán "nếu có gì sống sót, sẽ là risk". Không kiểm định lại tương quan
   với `realized_vol_20d` trong round này (ngoài phạm vi one-shot đã khóa)
   nhưng ghi nhận khớp hướng dự đoán.
3. **Điều KHÔNG được ghi trước, và là phát hiện chính của round này**: kỳ
   vọng #2/#3 giả định ngầm là 3-giai-đoạn TÍNH ĐƯỢC — thực tế nó không
   tính được cho bất kỳ đối tượng nào (mục 4). Đây không phải sai lệch so
   với kỳ vọng theo hướng tốt hay xấu, mà là một GIỚI HẠN CẤU TRÚC của
   chính thiết kế SDE (`lookback_days=756`) chưa từng được nhận diện trước
   khi chạy — khiến Nhánh B không bao giờ có thể được xác nhận ĐẦY ĐỦ cho
   bất kỳ sub-score nào của SDE với dữ liệu hiện tại, bất kể bằng chứng
   trên bảng chính mạnh đến đâu.

## 9. Nhánh đã thi hành: NHÁNH C

`stock-decision-engine/src/scoring.py`: `score_decision()` (WEIGHTS,
`_hard_filters`, `_decision_label`, `_confidence`) đã **gỡ bỏ hoàn toàn**,
không phải comment/deprecate. `build_facts_table()` thay thế — vẫn tính 8
nhóm "reading" 0-100 (đếm tiêu chí TA nội bộ đạt, công thức KHÔNG đổi) làm
facts có ngữ cảnh, nhưng không cộng có trọng số thành một con số quyết
định, không còn nhãn BUY CANDIDATE/WATCH/WEAK SETUP/AVOID/GOOD STOCK BAD
ENTRY. `report.py`/`visualization.py`/notebook cập nhật theo (`facts_summary`
thay `decision_summary`, `facts_breakdown.png` thay `score_breakdown.png`).
`config.yaml`'s `score_thresholds` (chết, không còn ai đọc) đã gỡ.

20 output cũ (dùng dữ liệu đã sạch từ round trước nhưng công thức cũ) đã
regenerate trên công thức mới, cùng ngày as-of như trước
(`scratch/sde_regenerate_round3_branchc.py`). Output cũ archive tại
`stock-decision-engine/outputs/archive_pre_round3_branchc_2026-07-17/`
kèm README. Bảng đối chiếu:
`stock-decision-engine/ROUND3_BRANCHC_REGEN_COMPARISON.csv`.

## 10. Khuyến nghị sử dụng SDE từ nay

**stock-decision-engine không còn là công cụ khuyến nghị mua/bán.** Sau ba
vòng (audit → sửa dữ liệu → kiểm định điểm số), kết luận là: công thức
chấm điểm cũ chưa từng có bằng chứng dự báo thật — không phải vì dữ liệu
bẩn (đã sửa ở Vòng 2), mà vì bản thân công thức (đếm tiêu chí phân tích kỹ
thuật theo kiểu giáo trình, hard-code không hiệu chỉnh) không vượt qua
được phép kiểm định thống kê chuẩn của dự án. Notebook giờ chỉ nên dùng để
**đọc nhanh một bảng chỉ số kỹ thuật/thống kê của một mã** (MA, RSI, ATR,
Sharpe, xác suất Monte Carlo, v.v.) khi bạn đã có ý định riêng cần tra
cứu con số — không dùng nó để QUYẾT ĐỊNH mua/bán/chờ, và tuyệt đối không
diễn giải bất kỳ "reading" 0-100 nào trong bảng facts như một điểm số đã
kiểm định. Nếu muốn một công cụ có bằng chứng thống kê thật, dùng
`alpha_score` v2 của dự án chính (`docs/reports/scoring/SCORE_V2_REPORT.md`) — bản thân
nó cũng đang ở chế độ shadow-only, chưa dùng vốn thật, nhưng ít nhất đã
qua đúng loại kiểm định mà SDE vừa không vượt qua được.

---

**File này là kết quả CUỐI CÙNG của phiên tòa Vòng 3.** Không chạy lại,
không thử biến thể khác, đúng ràng buộc đã khóa.
