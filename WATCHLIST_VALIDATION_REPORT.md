# WATCHLIST_VALIDATION_REPORT — first IC/null-test of final_watchlist's composite

**Kết quả của lần chạy DUY NHẤT theo `WATCHLIST_VALIDATION_PREREG.md`, khóa
trước khi chạy.** Không có tham số/tiêu chí nào bị đổi sau khi nhìn số. Scripts:
`scratch/watchlist_validation.py` (dựng panel điểm số lịch sử, tái dùng nguyên
`_score()`/`_mark_filters()`/`_merge_benchmark()` của `final_watchlist.py`),
`scratch/watchlist_validation_ic.py` (IC Newey-West), `scratch/watchlist_validation_null.py`
(null test 2,000 danh mục/fold). Kết quả thô: `data/output/watchlist_validation_ic_main.csv`,
`_ic_periods.csv`, `_null_composite.csv`, `_null_minimal_watchlist.csv`.

**Trích dẫn nguồn**: `audit/PATH_TO_100.md` mục 3, `WATCHLIST_VALIDATION_PREREG.md`,
`SCORE_V2_REPORT.md`/`SCORE_V2_DESIGN.md`, `SCORE_FORENSIC_REPORT.md`,
`SURVIVORSHIP_BIAS_ESTIMATE.md`, `audit/SECTOR_MAPPING_COVERAGE_REPORT.md`.

## Kết luận một dòng

**Nhánh C** — cả composite (`base_final_score`) lẫn "watchlist tối giản"
(`alpha_score` v2 + gate hiện hành của `final_watchlist.py`) đều KHÔNG đạt
tiêu chí đã khóa. `final_watchlist.py` chuyển sang **"không xếp hạng alpha"**
— sắp theo `value_ma20` (thanh khoản), dán nhãn rõ trong output. Đã thi hành
trong code (`src/screening/final_watchlist.py`, `ranking_mode="no_alpha_liquidity_sort"`),
đã regenerate artifact, đã cập nhật `audit/PATH_TO_100.md` mục 3.

---

## 1. Composite tổng — như một nhân tố

### 1a. IC Newey-West (maxlags=20, hằng ngày, không lấy mẫu cách quãng)

| Universe | Target | mean IC | t_naive | **t_NW** | N ngày |
|---|---|---|---|---|---|
| full (trading_status ACTIVE) | raw | +0.0038 | +0.98 | **+0.29** | 1588 |
| full | residualized | −0.0040 | −1.35 | **−0.40** | 1507 |
| top150 | raw | +0.0134 | +2.56 | **+0.75** | 1565 |
| top150 | residualized | +0.0134 | +3.45 | **+1.02** | 1507 |

**3 giai đoạn (full, residualized)**: Giai đoạn 1 (2020-06→2022-06) t_NW=−0.33,
Giai đoạn 2 (2022-06→2024-06) t_NW=−0.50, Giai đoạn 3 (2024-06→2026-06)
t_NW=+0.37 — **không cùng dấu**, không giai đoạn nào gần ngưỡng 3.

**Kết luận IC**: composite không đạt `|t_NW|>3` ở bất kỳ universe/target/giai
đoạn nào — không có bằng chứng dự báo, không phải "yếu nhưng đúng hướng", gần
như phẳng (0) và đổi dấu qua các giai đoạn.

### 1b. Null test (2,000 danh mục ngẫu nhiên/fold, seed=42, size=10, sector cap=2,
    min_value_ma20=10 tỷ, above_ma200, giao thêm `trading_status==ACTIVE`)

| Fold | Real CAGR | Null p50 | **Percentile** |
|---|---|---|---|
| 2022 | −41.4% | −43.1% | 61.6 |
| 2023 | +20.7% | +13.0% | 80.8 |
| 2024 | +20.0% | +12.5% | 77.8 |
| 2025 | +42.3% | +8.9% | 98.8 |
| **2026** | **−54.8%** | −24.4% | **0.15** |

Trung bình 5 fold: **63.8** (> 60) — nhưng **fold 2026 = 0.15 << 10** — thất
bại điều kiện "không fold nào < 10". **Cả hai vế của tiêu chí OR (IC hoặc
null) đều không đạt.**

**Lưu ý kỹ thuật quan trọng (không phải kết quả, một bug đã tìm và sửa trước
khi coi kết quả trên là cuối cùng)**: lần chạy null test đầu tiên cho ra
percentile=0.0 tuyệt đối ở MỌI fold cho CẢ HAI biến thể (composite và watchlist
tối giản), với phân phối null có phương sai bằng 0 — dấu hiệu rõ ràng của lỗi,
không phải kết quả thật. Truy ra nguyên nhân: panel đưa vào
`run_portfolio_backtest` mang sẵn cột `meta_score` cũ (từ bước merge
`meta_ranking.parquet` phục vụ tính `signal_score`), va chạm tên cột với
`meta_ranking` tham số truyền vào hàm — pandas tự đổi tên cả hai thành
`meta_score_x`/`meta_score_y`, khiến bước `sort_values(score_col)` bên trong
`run_portfolio_backtest` không tìm thấy cột `meta_score` nữa và **bỏ qua hoàn
toàn bước sắp xếp theo điểm** — danh mục thật và toàn bộ 2000 danh mục "ngẫu
nhiên" đều chọn đúng cùng một tập mã theo thứ tự merge mặc định, bất kể điểm số
nào được truyền vào. Xác nhận trực tiếp: real và random cho ra CHÍNH XÁC cùng
danh sách mã mua ở lần rebalance đầu tiên. Sửa bằng cách loại bỏ các cột
`meta_score`/`trade_edge_score`/`setup_quality_score`/`risk_penalty_score` còn
sót lại khỏi `features` trước khi gọi `run_portfolio_backtest`, chạy lại toàn
bộ. Bảng trên là kết quả SAU khi sửa.

## 2. Từng thành phần riêng (IC, full universe/residualized trừ khi ghi khác)

| Thành phần | t_NW (full, raw) | t_NW (full, residualized) | t_NW (top150, residualized) | 3 giai đoạn (full, resid.) |
|---|---|---|---|---|
| trend_score | +0.52 | +0.64 | +0.56 | +0.71 / −0.31 / +0.95 |
| momentum_score | −0.25 | −0.42 | +0.93 | −0.00 / −0.83 / +0.44 |
| relative_strength_score | −0.25 | −0.42 | +0.93 | −0.00 / −0.83 / +0.44 |
| **liquidity_score** | −0.06 | **−4.19** | −1.52 | **−3.85 / −0.39 / −3.38** |
| volume_score | +1.71 | +1.61 | −0.93 | +0.48 / +0.47 / +2.28 |
| **risk_score** | **+2.67** | **+4.72** | **+2.17** | +1.49 / **+2.69** / **+5.05** |
| signal_score | NaN (N=0) | NaN (N=0) | NaN (N=0) | — |

**Phát hiện đáng chú ý:**

1. **`momentum_score` và `relative_strength_score` cho ra con số Newey-West
   GIỐNG HỆT NHAU ở mọi hàng.** Không phải trùng hợp hay lỗi tính toán: cả hai
   dùng `_rank()` (hạng phần trăm cross-sectional), và
   `excess_return_Nd = return_Nd − benchmark_return_Nd` — trừ đi một hằng số
   CHUNG cho mọi mã trong cùng một ngày (lợi nhuận benchmark) không đổi thứ
   hạng cross-sectional. Hai "thành phần" này về mặt toán học là MỘT, dù khai
   báo trọng số riêng (20% + 20%) như thể độc lập. Đây là dư thừa thật trong
   công thức đang triển khai, không sửa trong round này (ngoài phạm vi khóa
   sẵn), ghi nhận cho thiết kế lại tương lai.
2. **`liquidity_score` đảo chiều có ý nghĩa thống kê** (t_NW=−4.19, đồng dấu âm
   2/3 giai đoạn rõ rệt) — chiều hiện tại (thưởng `value_ma20` CAO) đang dự báo
   SAI hướng. Xác nhận trực tiếp quyết định đã khóa sẵn trong prereg (gỡ khỏi
   ranking ở mọi nhánh) bằng bằng chứng mới, không phải chỉ suy diễn từ
   survivorship bias như lý do ban đầu.
3. **`risk_score` là thành phần duy nhất có bằng chứng đứng riêng đáng chú ý**:
   t_NW=+4.72 (full, residualized), đồng dấu dương cả 3 giai đoạn (dù Giai đoạn
   1 yếu, +1.49), mạnh dần theo thời gian. Không được dùng cho ranking ở Nhánh C
   (quy tắc "không xếp hạng alpha" áp dụng đồng loạt, không có ngoại lệ cho
   từng thành phần) — nhưng đây là ứng viên tốt nhất cho một prereg đơn-nhân-tố
   trong tương lai (đúng lộ trình `SCORE_V2_DESIGN.md` đã dùng cho
   `realized_vol_20d`), không làm ở đây vì sẽ là thêm nhân tố mới giữa round.
4. **`signal_score` không tính được (N=0)**: `data/signals/meta_ranking.parquet`
   hóa ra là một **snapshot hiện tại** (mỗi mã 1 dòng, ngày riêng của từng mã —
   phần lớn 2026-07-13, một số ít là ngày giao dịch cuối cùng của các mã
   `INACTIVE_LONG`), KHÔNG PHẢI một chuỗi lịch sử như dự kiến ban đầu trong
   prereg (tài liệu đó mô tả nhầm là "22 ngày phân biệt trải dài 2022–2026,
   cập nhật kiểu as-of" — sau khi kiểm tra kỹ khi chạy NV2, hóa ra 22 chỉ là số
   giá trị NGÀY riêng biệt xuất hiện trong 500 dòng snapshot, không phải 22 lần
   cập nhật theo thời gian). Hệ quả: `risk_penalty_score` (1/5 thành phần con
   của `risk_score`) cũng không có lịch sử — nhưng vì `_rank()` tự động điền
   0.5 (trung lập) cho giá trị thiếu, `risk_score` vẫn tính được đầy đủ (chỉ bị
   pha loãng nhẹ bởi một thành phần con luôn trung lập trong lịch sử), không bị
   chặn như `signal_score`.

## 3. Mốc so sánh

### 3a. `alpha_score` v2 (trích lại, không chạy lại — `SCORE_V2_REPORT.md`)
Null avg percentile **71.0** (không fold <5); IC t_NW **+6.09** (full) /
**+5.67** (top150), residualized, đồng dấu dương cả 3 giai đoạn.

**Cập nhật (GĐ5, `V2_STABILITY_NOTE.md`)**: 71.0 này đo v2 kiểm tra ĐỘC LẬP
(chỉ qua gate thô `min_value_ma20`/`above_ma200`), không phải v2 hoạt động
bên trong gate đầy đủ của `final_watchlist.py` — mục 3b bên dưới (52.8) mới
là con số đúng cho ngữ cảnh đó. Đã xác nhận bằng loại trừ: nguyên nhân chênh
lệch là gate `minimal_eligible`, không phải dữ liệu hay universe.

### 3b. "Watchlist tối giản" = v2_score + gate hiện hành của `final_watchlist.py`
(`strict_pass` HOẶC `fallback_eligible`, tính lại trên lịch sử, universe
`trading_status==ACTIVE`) — **chạy mới cho round này:**

**IC**: full_minimal_gate/raw t_NW=+3.24; residualized t_NW=**+7.02**. 3 giai
đoạn (residualized): +2.90 / +3.03 / +8.94 — đồng dấu dương cả 3, nhưng Giai
đoạn 1 (+2.90) **không vượt ngưỡng 3.0** (thiếu 0.10).

**Null test**: 

| Fold | Real CAGR | Percentile |
|---|---|---|
| 2022 | +19.7% | 83.6 |
| 2023 | +31.0% | 36.2 |
| 2024 | +33.6% | 65.4 |
| 2025 | +20.3% | 14.2 |
| 2026 | +14.1% | 64.9 |

Trung bình: **52.8** (< 60, không đạt) — nhưng **không fold nào < 10** (tệ
nhất 14.2) — khác hẳn composite (fold 2026 sụp xuống 0.15).

**Đọc theo tiêu chí đã khóa**: `|t_NW|>3 cùng dấu cả 3 giai đoạn` — SÁT nhưng
KHÔNG đạt (Giai đoạn 1 thiếu 0.10). `null avg>60, không fold<10` — vế thứ hai
đạt, vế thứ nhất KHÔNG đạt (thiếu 7.2 điểm). **Theo đúng chữ của tiêu chí đã
khóa, watchlist tối giản KHÔNG đạt** — dù rõ ràng khỏe hơn nhiều so với
composite ở mọi thước đo (không fold thảm họa, đồng dấu dương ổn định, IC gần
sát ngưỡng).

## 4. Áp dụng cây quyết định

- Nhánh A (composite đạt): **KHÔNG** — cả IC lẫn null đều không đạt, không mơ
  hồ (composite: t_NW gần 0 không cùng dấu; null có 1 fold sụp xuống 0.15).
- Nhánh B (composite không đạt, watchlist tối giản đạt): **KHÔNG** — watchlist
  tối giản, theo đúng chữ của tiêu chí đã khóa trong prereg, cũng không đạt
  (null avg 52.8<60; IC giai đoạn 1 2.90<3.0).
- **→ Nhánh C.**

**Ghi nhận trung thực về vùng xám**: kết quả của watchlist tối giản RẤT SÁT
ngưỡng B (period 1 thiếu 0.10 trên thang t-stat; null avg thiếu 7.2 điểm phần
trăm trên thang percentile — không nhỏ nhưng cũng không lớn). Đây đúng là loại
tình huống RÀNG BUỘC gốc dự phòng ("nếu kết quả rơi vào vùng xám… chọn nhánh
thận trọng hơn") — áp dụng đúng như đã khóa: **chọn C (thận trọng hơn B)**,
không tự nới lỏng ngưỡng để "cứu" B dù về mặt trực giác watchlist tối giản có
vẻ là một tín hiệu thật (và `alpha_score` v2 của chính nó ĐÃ được xác nhận
riêng, qua một bài test khác, ở `SCORE_V2_REPORT.md`, với ngưỡng chấp nhận
lỏng hơn round này). Không coi đây là mâu thuẫn — hai bài test có tiêu chí khác
nhau theo thiết kế (round này cố tình đặt thanh cao hơn cho việc XẾP HẠNG bên
trong `final_watchlist.py`), và pipeline vẫn tiếp tục dùng `alpha_score` v2
nguyên trạng ở các nơi khác (không bị round này rút lại).

## 5. Thi hành Nhánh C (`src/screening/final_watchlist.py`)

- `DEFAULT_FINAL_WATCHLIST_CONFIG["ranking_mode"] = "no_alpha_liquidity_sort"`.
- `_redistribute_after_gate`: khi ở chế độ này, xếp hạng và chọn
  `client_ready_watchlist`/`trading_watchlist` theo `value_ma20` giảm dần
  (thay `final_score`); bỏ điều kiện `final_score >= ngưỡng` khỏi việc chọn
  vào tier (giữ nguyên mọi gate cấu trúc/chất lượng dữ liệu khác: eligibility,
  cashflow, confirmation, warning-block — không liên quan alpha score).
- Nhãn rõ trong cột `reason` của mọi dòng:
  `"[Không xếp hạng alpha, chỉ sắp theo thanh khoản -- xem WATCHLIST_VALIDATION_REPORT.md]"`.
- `liquidity_score` gỡ khỏi `base_final_score` (khóa sẵn, không phụ thuộc
  nhánh) — 10 điểm phân bổ lại tỷ lệ thuận cho 6 thành phần còn lại
  (trend 27.78, momentum 22.22, relative_strength 22.22, volume 5.56,
  risk 11.11, signal 11.11 — tổng 100). `base_final_score`/`final_score` vẫn
  được TÍNH và HIỂN THỊ (tham khảo/nghiên cứu) nhưng không còn điều khiển việc
  chọn/xếp hạng candidate nào.
- Sector cap (max 2/ngành, `UNKNOWN` tính như một ngành thật) — thêm mới vào
  chính `client_ready_watchlist`/`trading_watchlist` (trước đây hoàn toàn
  không có cơ chế này, chỉ cắt top-N theo điểm).
- `assert_no_forward_columns` mở rộng vào `src/alpha/scoring.py::calculate_alpha_scores`
  (input, `mode="drop"`) và `scripts/run_alpha_scoring.py` (output, trước
  `save_parquet`) — khóa sẵn, không phụ thuộc nhánh.
- 2 bug thật tìm thấy và sửa trong lúc thi hành/regenerate (không phải tune
  theo kết quả): (a) cột `value_ma20` bị `_ensure_watchlist_output_columns`
  cắt khỏi output vì chưa có trong `FINAL_WATCHLIST_COLUMNS`, làm
  `apply_post_cashflow_overlay`'s lần gọi `_redistribute_after_gate` thứ hai
  trong cùng một lần chạy pipeline bị `KeyError` — thêm `value_ma20` vào schema
  cố định; (b) nhãn "không xếp hạng alpha" bị chèn lặp đôi vì
  `_redistribute_after_gate` chạy 2 lần/pipeline (một lần trong
  `build_watchlist_tiers`, một lần trong `apply_post_cashflow_overlay`) — sửa
  thành idempotent (kiểm tra tiền tố trước khi chèn).

## 6. Regenerate + so sánh (NV4)

Chạy lại toàn bộ pipeline (`scripts/update_prices_daily.py` → `update_disclosure_daily.py`
→ `update_index_data.py` → `scripts/run_daily_pipeline.py --offline`) trên dữ
liệu vừa đồng bộ đến 2026-07-15.

**`data/signals/final_watchlist.csv` (client_ready top-10, artifact duy nhất có
bản "trước" trong git để so sánh — `data/output/*.csv` bị gitignore, không có
bản nền để đối chiếu `trading_watchlist`)**:

| Hạng | Cũ (xếp theo điểm, dữ liệu 2026-07-13) | Mới (xếp theo thanh khoản, dữ liệu 2026-07-15) |
|---|---|---|
| 1 | VIC | VHM |
| 2 | MSB | VIC |
| 3 | ABB | SHB |
| 4 | MST | VIX |
| 5 | BVS | TCB |
| 6 | CTS | HPG |
| 7 | KLB | SSI |
| 8 | BMP | GEX |
| 9 | NAB | MWG |
| 10 | HDB | BSR |

**Trùng lặp: 1/10 (VIC).** Đúng như dự kiến — đổi hẳn tiêu chí xếp hạng (điểm
tổng hợp 7 thành phần → thanh khoản thuần) tạo ra một danh sách gần như khác
hoàn toàn, không phải dấu hiệu lỗi. Xác nhận độc lập: `value_ma20` của top-10
mới giảm dần tuyệt đối (không còn `final_score` chi phối thứ tự). **Hai hiệu
ứng bị trộn lẫn trong so sánh này, không tách bạch được**: (a) đổi cơ chế xếp
hạng (hiệu ứng chính, chủ đích của round này) và (b) dữ liệu mới hơn 2 ngày
lịch (hiệu ứng phụ, không tránh được vì đây là đường sản xuất thật, không phải
một hạ tầng so sánh đông lạnh dữ liệu) — không tuyên bố tách được hai hiệu ứng
này, ghi nhận rõ giới hạn của phép so sánh.

Kết quả cuối: `client_ready=10, trading=20, research=180, data_review=290`.

---

## Kết luận & bước tiếp theo

`final_watchlist.py` từ nay **không xếp hạng theo alpha score đã kiểm định**
— sắp theo thanh khoản, dán nhãn rõ, cho đến khi có một nhân tố mới qua đúng
quy trình pre-register + kiểm định (ứng viên rõ nhất: `risk_score` đứng riêng,
xem mục 2). Đây là kết quả trung thực của round kiểm định đầu tiên cho composite
này kể từ khi triển khai — không phải một thất bại cần "sửa cho ra kết quả
đẹp", mà là đúng mục đích của việc kiểm định: phát hiện một cơ chế xếp hạng
chưa từng có bằng chứng, trước khi nó tiếp tục được trình bày như đã kiểm định.
