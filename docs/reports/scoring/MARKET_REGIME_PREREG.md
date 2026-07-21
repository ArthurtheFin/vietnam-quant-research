# MARKET_REGIME_PREREG — khóa trước khi chạy bất kỳ code kiểm định nào

**Viết và commit TRƯỚC khi có bất kỳ dòng code phân tích nào chạy.** Đây là
lần đầu tiên module regime (`market_regime`, `market_entropy_regime`) được
kiểm định độc lập như một tín hiệu dự báo — trước giờ chỉ được dùng làm
input mô tả/lọc (vd. `regime_pass` filter trong stealth screen), chưa từng
được test predictive power riêng của chính nó. Mọi lựa chọn dưới đây chốt
dựa trên bằng chứng đã có
(`docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md`, `docs/reports/scoring/FOLD_AUTOPSY_REPORT.md`,
`docs/reports/scoring/CRASH_RISK_RESEARCH_REPORT.md`) và cấu trúc dữ liệu hiện có — không có gì
trong tài liệu này được điều chỉnh sau khi nhìn kết quả NV2, vì NV2 chưa
chạy khi tài liệu này được viết. Nếu kết quả xấu: báo cáo, dừng, bàn lại —
không quay lại sửa tài liệu này rồi chạy lại. Đúng kỷ luật đã áp dụng cho
`docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`/`docs/reports/scoring/SCORE_V2_DESIGN.md` trước đây.

**Nguồn trích dẫn bắt buộc**: `data/processed/market_features.parquet`
(cột `market_regime`, `market_entropy_regime` — sinh bởi
`scripts/generate_features.py`, đã xác nhận đúng sau fix
`docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md`: `market_regime` value_counts
`Neutral 857/Risk-off 503/Risk-on 272`, `market_entropy_regime`
`Transitional 1153/Structured 230/Chaotic 228/Unknown 21`) join với
`data/processed/benchmark_vnindex.parquet` (giá/return VNINDEX thật, cột
`close`, `return_1d`, `forward_return_20d` đã có sẵn từ
`src/data/benchmark.py::prepare_index_features`).

---

## Đối tượng nghiên cứu — 2 chỉ báo, KHÔNG PHẢI 3

| Chỉ báo | Trạng thái | Đưa vào vòng này? |
|---|---|---|
| `market_entropy_regime` (Structured/Transitional/Chaotic, ngưỡng đã hiệu chỉnh 0.692/0.818) | Đầy đủ dữ liệu (1611/1632 ngày non-null cửa sổ 21d) | **Có** |
| `market_regime` (Risk-on/Neutral/Risk-off, từ `add_market_regime` có `benchmark=`) | Đầy đủ dữ liệu, đã sửa bug thiếu `Risk-on` | **Có** |
| breadth (`pct_above_ma50`) | **Không NaN** (1632/1632 non-null, xác nhận lại — khác với `breadth_support_score`/`market_support_score` trong `stealth_accumulation.py`, 2 cột KHÁC hoàn toàn đã biết all-NaN từ `docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md`, không liên quan ở đây) | **Không — loại, lý do dưới đây** |

**Lý do loại breadth (không phải vì NaN)**: `pct_above_ma50` là một biến
**liên tục**, đã là 1/5 input của công thức `classify_market_regime`
(`src/models/regime.py`) — không tồn tại sẵn một cột "breadth_regime" rời
rạc (categorical) nào trong codebase để đưa vào khung ANOVA/Kruskal-Wallis
theo nhóm như 2 chỉ báo trên. Dựng thêm ngưỡng phân nhóm mới cho breadth
(vd. tự chọn tercile/threshold) sẽ tính là **"thêm chỉ báo mới"** — bị cấm
theo RÀNG BUỘC của vòng này. Loại khỏi vòng này vì lý do thiết kế
(không có sẵn dạng categorical, không được phép tự tạo), không phải vì
thiếu dữ liệu.

**Loại trạng thái "Unknown"** khỏi mọi phép so sánh nhóm (cả H1/H2/H3, cả
2 chỉ báo) — đây là placeholder cho ngày chưa đủ cửa sổ warmup, không phải
một trạng thái thị trường thật. Áp dụng cho 21 ngày đầu chuỗi
`market_entropy_regime`. `market_regime` không có "Unknown".

---

## Giả thuyết (khóa trước, đúng 3 câu, không phải "regime giúp chọn mã")

- **H1 (biến động có điều kiện)**: độ biến động thực hiện (realized
  volatility) 20 ngày TỚI của VNINDEX khác nhau có ý nghĩa giữa các trạng
  thái regime tại ngày t.
- **H2 (tính bền/persistence)**: một khi ở trạng thái X tại ngày t, xác
  suất vẫn ở X tại ngày t+5/t+10/t+20 đủ cao để dùng làm cơ sở quyết định
  vận hành (không đổi xoành xoạch mỗi ngày).
- **H3 (return có điều kiện — làm lại đúng cách)**: return trung bình 20
  ngày TỚI của VNINDEX khác nhau có ý nghĩa giữa các trạng thái regime tại
  ngày t. Đây chính là câu hỏi `docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` NV2 đã thử
  ("index-vs-own-MA200", "vol regime", "breadth-vs-own-history") và kết
  luận "no basis found ... 5 folds is too small a sample to be confident
  this isn't simply a power problem" — vòng này chạy trên **toàn bộ 1631
  ngày** thay vì 5 fold theo năm, lực thống kê lớn hơn nhiều bậc.

**KHÔNG kiểm định** trong vòng này (đúng RÀNG BUỘC): regime có cải thiện
chọn mã (null-test percentile của `alpha_score` v2, hay bất kỳ composite
nào) hay không. Đây là câu hỏi khác, cần một prereg riêng SAU vòng này —
xem "Caveat" cuối file.

---

## Định nghĩa chính xác biến mục tiêu (khóa trước)

- **`forward_return_20d`**: dùng NGUYÊN cột đã có sẵn trong
  `benchmark_vnindex.parquet` (sinh bởi `add_returns`, compounded 20-phiên
  tới: `(1+r).rolling(20).apply(prod).shift(-20) - 1`) — không tính lại.
- **`forward_vol_20d`** (biến mới, cần tính — đây là biến MỤC TIÊU của
  phép kiểm định, không phải một "chỉ báo regime" mới, không vi phạm RÀNG
  BUỘC "không thêm chỉ báo"): với mỗi ngày t,
  `forward_vol_20d[t] = std(return_1d[t+1..t+20], ddof=1) * sqrt(252)` —
  đúng công thức annualize đã dùng trong `add_realized_volatility`
  (`src/features/volatility.py`, `rolling(window).std() * sqrt(252)`),
  chỉ đổi chiều từ trailing sang forward. Dùng `return_1d` (không phải
  `log_return_1d`) — đúng convention `realized_vol_20d` hiện có.
- Ngày cuối mỗi giai đoạn thiếu đủ 20 phiên tới sẽ có `forward_vol_20d`/
  `forward_return_20d` = NaN — loại khỏi phép so sánh nhóm của giai đoạn
  đó, báo N loại rõ trong NV2 (không lùi ngày/không nội suy).

---

## Chia 3 giai đoạn (khóa trước, không nhìn kết quả)

Chia đều theo số phiên (tercile theo N, không theo lịch tùy chọn) trên
toàn bộ `market_features.parquet` (1632 dòng, 2020-01-02 → ngày mới nhất):

| Giai đoạn | Khoảng ngày | N (phiên) |
|---|---|---|
| P1 | 2020-01-02 → 2022-03-09 | 544 |
| P2 | 2022-03-10 → 2024-05-15 | 544 |
| P3 | 2024-05-16 → ngày cuối cùng có dữ liệu | 544 (± vài ngày tùy độ dài chuỗi tại thời điểm chạy) |

Ghi chú: ranh giới này trùng gần như chính xác với "biên giai đoạn cũ" đã
dùng ở `docs/reports/scoring/EVENT_DETECTION_REPORT.md`/disclosure event study (2020-01→2022-03,
2022-03→2024-05, 2024-05→2026-07) — không phải cố tình tái dùng, mà vì
cả hai đều là chia đều 3 phần một chuỗi ~6.5 năm bắt đầu cùng ngày. Khác
với báo cáo đó, KHÔNG có vấn đề thiếu coverage ở P1 cho nghiên cứu này —
`stock_count` (số mã có dữ liệu mỗi ngày, cột có sẵn trong
`market_features.parquet`) ổn định 354-471 suốt 2020-2026 (min theo năm:
2020=354, 2021=413, 2022=428, ...), khác hẳn vấn đề "chỉ 2-5 mã đủ điều
kiện thanh khoản" của báo cáo kia — đó là gate thanh khoản 3B VND cho chọn
mã cổ phiếu, không áp dụng cho tín hiệu market-wide (breadth/entropy tính
trên toàn bộ cross-section có dữ liệu, không qua gate thanh khoản).

---

## Phương pháp thống kê (khóa trước)

**Máy đo mô tả/chẩn đoán** (báo cáo đầy đủ, KHÔNG dùng làm tiêu chí
PASS/FAIL chính — xem mục Tiêu chí bên dưới):
- ANOVA một chiều (`scipy.stats.f_oneway`) và Kruskal-Wallis
  (`scipy.stats.kruskal`) cho khác biệt trung bình/phân phối giữa các
  nhóm regime, cho H1 và H3, tính riêng từng giai đoạn + toàn mẫu.
- BH-FDR (q-value) trên toàn bộ tập so sánh cặp thực hiện trong vòng này
  (đúng quy ước `CLAUDE.md` mục 9) — báo kèm t-stat/CI thô, không thay thế
  tiêu chí khóa.

**Tiêu chí quyết định chính — block bootstrap CI** (vì regime tự tương
quan theo chuỗi ngày liền kề — một ngày "Risk-off" gần như chắc chắn
theo sau bởi "Risk-off", và `forward_vol_20d`/`forward_return_20d` tự nó
đã chồng lấn 19/20 ngày giữa 2 quan sát liền kề — t-test/CI ngây thơ giả
định độc lập sẽ đánh giá thấp phương sai thật, phóng đại ý nghĩa thống
kê một cách giả tạo):

- **Block size = 20 phiên giao dịch** cho MỌI bootstrap trong vòng này
  (H1, H2, H3) — khớp đúng độ dài cửa sổ overlap của biến mục tiêu 20 ngày
  (quy tắc kinh nghiệm chuẩn: block ≥ horizon của biến chồng lấn), và nhất
  quán với 1 hằng số duy nhất cho toàn bộ nghiên cứu thay vì tune riêng
  từng test. **Giới hạn đã biết trước** (ghi rõ, không giấu): nếu H2 tự nó
  đo được regime bền vững hơn 20 ngày, block=20 có thể vẫn hơi hẹp so với
  độ dài phụ thuộc thật của regime — khi diễn giải H1/H3, đối chiếu chéo
  với kết quả persistence của H2 thay vì tin CI một cách máy móc.
- **Phương pháp**: moving block bootstrap trên chuỗi (ngày, trạng thái
  regime, biến mục tiêu) đã sắp theo thời gian trong từng giai đoạn — resample
  khối liên tiếp độ dài 20 (có hoàn lại) ghép lại thành 1 chuỗi cùng độ
  dài, tính lại chênh lệch trung bình giữa MỌI cặp nhóm trên chuỗi
  resample đó. Lặp lại **2000 lần, seed=42** (tái lập được).
- **CI**: percentile 2.5%/97.5% của phân phối 2000 lần chênh lệch resample
  → CI 95%.

**Markov / persistence (H2)**: với mỗi trạng thái X của mỗi chỉ báo, tính
2 loại số đo, cả hai trên chuỗi trạng thái theo ngày (loại "Unknown"):
1. **Persistence thực nghiệm trực tiếp** (số đo chính cho tiêu chí
   PASS/FAIL): với mọi ngày t có state(t)=X và state(t+k) quan sát được
   (k=5/10/20), tỷ lệ `state(t+k)==X` trong số đó. Block bootstrap CI
   (cùng block=20, 2000 lần, seed=42) áp trên chuỗi trạng thái để lấy cận
   dưới/cận trên.
2. **Ma trận chuyển trạng thái Markov bậc 1** (chẩn đoán/đối chiếu, không
   dùng làm tiêu chí chính): đếm tần suất chuyển state(t)→state(t+1), suy
   ra P; tính `P^5`, `P^10`, `P^20` (lũy thừa ma trận) để có xác suất bền
   vững theo giả định Markov thuần túy — báo cạnh số đo trực tiếp để so
   sánh, không phải để thay thế (số đo trực tiếp không giả định tính chất
   Markov, ổn định hơn nếu quá trình thực không phải Markov bậc 1 thuần).

---

## Tiêu chí PASS/FAIL (khóa trước, không đổi sau khi thấy kết quả)

**H1 và H3** (biến động/return có điều kiện): PASS cho một chỉ báo nếu tồn
tại **ít nhất 1 trong 3 cặp so sánh nhóm** (regime có 3 trạng thái → 3 cặp)
mà CI 95% (block bootstrap) của chênh lệch trung bình **không chứa 0** VÀ
**cùng dấu** ở **CẢ 3 giai đoạn** (P1, P2, P3) riêng lẻ — không phải chỉ
trên toàn mẫu gộp. Không đạt ở dù chỉ 1 giai đoạn (CI chứa 0 hoặc đổi dấu)
→ cặp đó không tính; nếu không cặp nào đạt cả 3 giai đoạn → chỉ báo đó
FAIL cho giả thuyết đó.

**H2** (tính bền): PASS cho một chỉ báo nếu **MỌI trạng thái** (không phải
chỉ 1 trong số nhiều) của chỉ báo đó có **cận dưới của CI persistence tại
lag=5 ngày > 60%**, tính trên **toàn mẫu** VÀ ở **cả 3 giai đoạn** riêng
lẻ. Đây là tiêu chí chặt nhất có thể diễn giải rõ ràng từ câu hỏi gốc
("regime đủ bền để dùng vận hành" ngụ ý mọi trạng thái đều phải đáng tin,
không chỉ trạng thái phổ biến nhất).

**Không có tiêu chí "gộp"** giữa H1/H2/H3 — báo cáo riêng từng giả thuyết,
từng chỉ báo, không tính điểm tổng hợp.

---

## Cấm / giới hạn phạm vi (đúng nguyên văn RÀNG BUỘC)

- **Không kiểm định regime × chọn mã** trong vòng này (không join với
  `stock_features.parquet` ở cấp độ từng mã, không tính null-test
  percentile của bất kỳ composite/score nào cùng regime). Nếu H1 PASS,
  bước tiếp theo là MỘT prereg riêng, ngoài vòng này, để test "regime có
  cải thiện null-test percentile của v2 không" — không tự động suy ra,
  không làm trong vòng này.
- **Không thêm chỉ báo regime mới** — chỉ dùng 2 chỉ báo đã có sẵn trong
  `market_features.parquet` như liệt kê ở trên.
- **Không tune tham số theo kết quả** — block size, percentile ngưỡng
  giai đoạn, N bootstrap, seed đều khóa TRƯỚC ở tài liệu này.
- **Kết quả âm tính = kết quả** — nếu H1/H2/H3 FAIL cho cả 2 chỉ báo,
  không thử thêm định nghĩa trạng thái khác (vd. tự chia lại ngưỡng
  entropy, tự đổi ngưỡng `market_regime`) trong vòng này. Báo cáo, đóng,
  hoặc chờ yêu cầu prereg mới.

---

## Kế hoạch báo cáo (NV2/NV3)

1. **Báo N mỗi trạng thái regime TRƯỚC khi báo bất kỳ kết quả nào** — cả 2
   chỉ báo, cả 3 giai đoạn + toàn mẫu, tách riêng N thô (số ngày ở trạng
   thái đó) và N hợp lệ (có đủ `forward_vol_20d`/`forward_return_20d`
   không NaN) — đây là bước đầu tiên của NV2, quyết định có đủ dữ liệu để
   tin kết quả hay không trước khi đọc tiếp.
2. Chạy đúng 1 lần (`scratch/market_regime_study.py`), không tune, xuất
   kết quả có lineage (git commit hash, ngày chạy, snapshot input) ra
   `data/output/market_regime_study_results.json` (hoặc tương đương).
3. `docs/reports/scoring/MARKET_REGIME_STUDY_REPORT.md` — đúng cấu trúc H1/H2/H3
   × 2 chỉ báo × 3 giai đoạn, trích `docs/reports/codebase_audit/MARKET_REGIME_AUDIT.md` cho
   context. Nếu có kết luận đóng/mở rõ ràng (PASS hoặc FAIL nhất quán),
   thêm 1 dòng mới vào bảng "5.2. Bảng hồ sơ đã đóng"
   (`docs/PROJECT_HANDBOOK.md`) theo đúng format 5 cột hiện có (#, Giả
   thuyết, Kết luận, Bằng chứng, Điều kiện mở lại).
