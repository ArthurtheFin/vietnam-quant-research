# MARKET_REGIME_STUDY_REPORT — kết quả kiểm định `docs/reports/scoring/MARKET_REGIME_PREREG.md`

**Chạy đúng 1 lần, không tune.** Script: `scratch/market_regime_study.py`,
commit tại thời điểm chạy `613b33f`, seed=42, N_boot=2000, block=20 phiên.
Input: `data/processed/market_features.parquet` (1632 dòng) join
`data/processed/benchmark_vnindex.parquet`. Kết quả đầy đủ (JSON, không
commit theo đúng quy ước `.gitignore` hiện có cho `data/output/`, tái lập
được 100% vì mọi bước đều xác định/seed cố định): `data/output/market_regime_study_results.json`.

**Kết luận ngắn gọn**: **0/12 tổ hợp (H1/H2/H3 × 2 chỉ báo) đạt tiêu chí
đã khóa.** Đây là kết quả âm tính toàn diện, nhất quán với
`docs/reports/scoring/FOLD_AUTOPSY_REPORT.md`'s kết luận trên 5 fold (nay xác nhận với lực
thống kê lớn hơn nhiều). Có 1 phát hiện phương pháp luận đáng chú ý (mục
"Vì sao naive test đánh lừa" bên dưới) và 1 sắc thái thật ở H2 (trạng thái
trung tâm/đa số khá bền, trạng thái cực đoan/thiểu số không bền) — cả hai
đều được báo cáo trung thực dù không đổi kết luận PASS/FAIL.

---

## 0. Đối tượng nghiên cứu (nhắc lại từ prereg)

- `market_regime` (Risk-on/Neutral/Risk-off, `src/models/regime.py`)
- `market_entropy_regime` (Structured/Transitional/Chaotic, ngưỡng đã
  hiệu chỉnh 0.692/0.818, `src/analytics/entropy.py`)
- breadth (`pct_above_ma50`) **loại khỏi vòng này** — không phải vì NaN
  (xác nhận lại: 1632/1632 non-null), mà vì không có sẵn dạng phân loại
  rời rạc (categorical) trong codebase; tự tạo ngưỡng mới sẽ tính là
  "thêm chỉ báo mới", bị cấm theo RÀNG BUỘC vòng này (xem prereg mục
  "Đối tượng nghiên cứu").

## 1. Chia giai đoạn (khóa trước, xác nhận khớp)

| Giai đoạn | Từ | Đến | N |
|---|---|---|---|
| P1 | 2020-01-02 | 2022-03-09 | 544 |
| P2 | 2022-03-10 | 2024-05-15 | 544 |
| P3 | 2024-05-16 | 2026-07-20 | 544 |

---

## 2. N mỗi trạng thái regime (báo TRƯỚC kết quả, đúng NV2)

### 2a. `market_regime`

| Phạm vi | Risk-on (thô) | Neutral (thô) | Risk-off (thô) | Risk-on hợp lệ (vol/return) | Neutral hợp lệ | Risk-off hợp lệ |
|---|---|---|---|---|---|---|
| Toàn mẫu | 272 | 857 | 503 | 272 / 272 | 846 / 846 | 494 / 475 |
| P1 | 141 | 286 | 117 | 141 / 141 | 286 / 286 | 117 / 98 |
| P2 | 68 | 228 | 248 | 68 / 68 | 228 / 228 | 248 / 248 |
| P3 | 63 | 343 | 138 | 63 / 63 | 332 / 332 | 129 / 129 |

*Cột "hợp lệ" = có `forward_vol_20d` / `forward_return_20d` không NaN
(loại ngày cuối mỗi giai đoạn thiếu đủ 20 phiên tới). P1's Risk-off:
117 thô nhưng chỉ 98 hợp lệ cho return — do 19 ngày rơi đúng vào phần
cuối chuỗi lịch sử benchmark tại thời điểm join thiếu `forward_return_20d`
(khác `forward_vol_20d` vì cách tính forward-vol của nghiên cứu này dùng
đúng 20 `return_1d` tới, trong khi `forward_return_20d` có sẵn từ
`benchmark_vnindex.parquet` áp dụng thêm 1 lớp làm sạch dữ liệu riêng
(`_clean_index_return_series`) — 2 cột forward khác nhau về nguồn tính,
không phải lỗi.*

**N nhỏ nhất đáng chú ý**: Risk-on ở P2/P3 (68/63 ngày) — vẫn đủ cho
block bootstrap (≥3 khối/20 ngày) nhưng là nhóm mỏng nhất, cần thận trọng
khi diễn giải CI của các so sánh liên quan đến Risk-on.

### 2b. `market_entropy_regime`

| Phạm vi | Structured (thô) | Transitional (thô) | Chaotic (thô) | Unknown | Structured hợp lệ | Transitional hợp lệ | Chaotic hợp lệ |
|---|---|---|---|---|---|---|---|
| Toàn mẫu | 230 | 1153 | 228 | 21 | 230 | 1133 | 228 |
| P1 | 82 | 390 | 51 | 21 | 82 | 390 | 51 |
| P2 | 27 | 418 | 99 | 0 | 27 | 418 | 99 |
| P3 | 121 | 345 | 78 | 0 | 121 | 325 | 78 |

**N nhỏ nhất đáng chú ý**: Chaotic ở P1 (51 ngày), **Structured ở P2 chỉ
27 ngày** — nhóm mỏng nhất toàn nghiên cứu. Kết quả liên quan đến
Structured ở P2 cần đọc với mức thận trọng cao nhất (ít khối bootstrap
độc lập nhất: 27/20 ≈ 1-2 khối).

---

## 3. H1 — Biến động có điều kiện (`forward_vol_20d`)

**Chẩn đoán toàn mẫu (KHÔNG phải tiêu chí quyết định)**: ANOVA
`market_regime` p=1.45e-16, `market_entropy_regime` p=1.89e-05 — cả hai
"cực kỳ có ý nghĩa" theo kiểm định ngây thơ trên toàn mẫu gộp.

**Tiêu chí quyết định — block bootstrap CI, khóa trước**: PASS nếu ≥1 cặp
loại trừ 0 VÀ cùng dấu ở CẢ 3 giai đoạn.

### 3a. `market_regime` — 3 cặp

| Cặp | P1 (dấu, CI) | P2 (dấu, CI) | P3 (dấu, CI) | PASS? |
|---|---|---|---|---|
| Risk-on − Neutral | − [-0.021, 0.021] | − [-0.031, 0.016] | − [-0.052, 0.023] | Không (không cặp nào loại trừ 0) |
| Risk-on − Risk-off | − [-0.144, 0.017] | **− [-0.120, -0.017]** | − [-0.050, 0.044] | Không (chỉ P2 loại trừ 0) |
| Neutral − Risk-off | − [-0.138, 0.011] | **− [-0.108, -0.019]** | + [-0.022, 0.047] | Không (đổi dấu P3, chỉ P2 loại trừ 0) |

**FAIL cho `market_regime`.** Đáng chú ý: "Risk-on − Risk-off" cùng dấu
âm (Risk-on có vol thấp hơn Risk-off) ở cả 3 giai đoạn — hướng hợp lý về
mặt kinh tế — nhưng chỉ P2 đủ mạnh để CI loại trừ 0; P1/P3 CI vẫn chứa 0.
Không đạt tiêu chí "loại trừ 0 ở CẢ 3 giai đoạn" đã khóa.

### 3b. `market_entropy_regime` — 3 cặp

| Cặp | P1 (dấu, CI) | P2 (dấu, CI) | P3 (dấu, CI) | PASS? |
|---|---|---|---|---|
| Structured − Transitional | + [-0.021, 0.064] | − [-0.085, 0.004] | + [-0.022, 0.051] | Không (đổi dấu P2, không cặp nào loại trừ 0) |
| Structured − Chaotic | **+ [0.0000, 0.134]** | − [-0.064, 0.041] | + [-0.026, 0.079] | Không (đổi dấu P2) |
| Transitional − Chaotic | **+ [0.006, 0.084]** | + [-0.008, 0.064] | + [-0.026, 0.050] | Không (cùng dấu 3/3! nhưng chỉ P1 loại trừ 0) |

**FAIL cho `market_entropy_regime`.** "Transitional − Chaotic" là cặp gần
đạt nhất trong toàn nghiên cứu: cùng dấu dương ở cả 3 giai đoạn (Chaotic
có vol thấp hơn Transitional — phản trực giác so với tên gọi, xem giải
thích ở mục 6), nhưng chỉ P1 đủ mạnh để CI loại trừ 0 (P2 gần sát,
CI=[-0.008, 0.064]; P3 xa hơn). Không đạt tiêu chí.

---

## 4. H2 — Tính bền (persistence)

**Tiêu chí quyết định, khóa trước**: PASS cho một chỉ báo nếu MỌI trạng
thái có cận dưới CI persistence tại lag=5 > 60%, trên toàn mẫu VÀ ở cả 3
giai đoạn riêng lẻ.

### 4a. `market_regime`

| Trạng thái | Persistence lag=5 (điểm ước lượng) | lag=10 | lag=20 | Cận dưới CI lag=5 (toàn mẫu) | full pass? | P1/P2/P3 pass? |
|---|---|---|---|---|---|---|
| Risk-on | 37.9% | 32.4% | 29.0% | 0.320 | Không | Không/Không/Không |
| Neutral | 66.6% | 62.7% | 58.4% | 0.618 | **Có** | Không/Không/**Có** |
| Risk-off | 72.7% | 63.4% | 49.8% | 0.631 | **Có** | Không/**Có**/Không |

**FAIL cho `market_regime`** (cần MỌI trạng thái pass, chỉ 0/3 đạt cả
toàn mẫu lẫn cả 3 giai đoạn riêng lẻ). Nhưng có sắc thái thật: `Neutral`
(trạng thái đa số, 857/1632 ngày) và `Risk-off` đều vượt 60% ở mức toàn
mẫu — chỉ không đạt vì tiêu chí đòi hỏi ổn định ở TỪNG giai đoạn riêng
lẻ, và một trong ba giai đoạn luôn hụt với mỗi trạng thái. `Risk-on` thì
hụt hoàn toàn, mọi phạm vi — thị trường rời trạng thái Risk-on nhanh hơn
đáng kể so với 2 trạng thái còn lại (điểm ước lượng chỉ 37.9% ở lag=5,
còn giảm tiếp xuống 29.0% ở lag=20).

### 4b. `market_entropy_regime`

| Trạng thái | Persistence lag=5 | lag=10 | lag=20 | Cận dưới CI lag=5 (toàn mẫu) | full pass? | P1/P2/P3 pass? |
|---|---|---|---|---|---|---|
| Structured | 45.7% | 30.9% | 13.0% | 0.330 | Không | Không/Không/Không |
| Transitional | 76.9% | 73.8% | 71.8% | 0.723 | **Có** | **Có/Có/Có** |
| Chaotic | 33.3% | 23.7% | 14.5% | 0.254 | Không | Không/Không/Không |

**FAIL cho `market_entropy_regime`** (cần MỌI trạng thái, chỉ 1/3 đạt).
Sắc thái rõ nhất toàn nghiên cứu: `Transitional` (trạng thái đa số,
1153/1632 ngày, ~70%) **đạt tiêu chí >60% một cách dứt khoát và ổn định**
ở MỌI phạm vi (toàn mẫu + cả 3 giai đoạn riêng lẻ), kể cả ở lag=20 vẫn
71.8%. Ngược lại, `Structured` và `Chaotic` (2 trạng thái cực đoan) rã rất
nhanh — Chaotic chỉ còn 14.5% ở lag=20, tức gần như chắc chắn đã đổi
trạng thái trong vòng 1 tháng. Diễn giải vận hành: "thị trường đang
Chaotic/Structured" là thông tin thật nhưng KHÔNG đủ bền để làm cơ sở
quyết định giữ nguyên vị thế qua nhiều tuần — nó nhiều khả năng chỉ là
một cú chớp ngắn hạn.

**Cross-check Markov (chẩn đoán, không phải tiêu chí)**: ma trận chuyển
bậc-1 lũy thừa `P^5`/`P^10`/`P^20` cho kết quả cùng chiều hướng định tính
với số đo trực tiếp ở trên (trạng thái đa số bền hơn trạng thái thiểu số)
— không mâu thuẫn với kết luận persistence trực tiếp. Chi tiết đầy đủ
trong JSON, không lặp lại bảng ở đây vì không đổi kết luận.

> **QUAN SÁT (không phải kết luận, không đổi verdict FAIL của H2)**: cả
> 2 chỉ báo cho cùng một hình dạng — trạng thái CỰC TRỊ (Risk-on,
> Structured, Chaotic) rã nhanh về gần ngẫu nhiên trong vài tuần
> (persistence lag=20: 29.0%/13.0%/14.5%), còn trạng thái TRUNG TÂM
> (Neutral, Transitional) dính >60%+ ở phần lớn phạm vi đo. Nếu tương
> lai có ai xây một regime overlay, đây là một gợi ý đáng cân nhắc: CHỈ
> hành động khi thị trường ở trạng thái cực trị (tín hiệu hiếm nhưng có
> vẻ bền hơn để tin), không hành động dựa trên trạng thái trung tâm (phổ
> biến nhưng không phân biệt được gì — đúng là trạng thái "mặc định").
> **Đây CHƯA phải cơ sở để dùng** — quan sát này không đến từ một giả
> thuyết đã pre-register (H1/H2/H3 đều FAIL, kể cả cho các trạng thái cực
> trị này), chỉ là một hình dạng dữ liệu nhận thấy sau khi nhìn kết quả.
> Cần một prereg riêng, khóa trước, nếu muốn theo đuổi hướng này.

---

## 5. H3 — Return có điều kiện (`forward_return_20d`) — làm lại câu hỏi FOLD_AUTOPSY

**Chẩn đoán toàn mẫu**: KW `market_regime` p=8.07e-04, `market_entropy_regime`
p=1.50e-02 — theo kiểm định ngây thơ, "có vẻ" có ý nghĩa (`market_regime`
đặc biệt thấp).

**Tiêu chí quyết định**: cùng quy tắc H1.

### 5a. `market_regime` — 3 cặp

| Cặp | P1 (dấu, CI) | P2 (dấu, CI) | P3 (dấu, CI) | PASS? |
|---|---|---|---|---|
| Risk-on − Neutral | − [-0.019, 0.009] | + [-0.021, 0.029] | + [-0.003, 0.055] | Không (đổi dấu P1→P2, không cặp nào loại trừ 0) |
| Risk-on − Risk-off | + [-0.063, 0.097] | + [-0.037, 0.046] | − [-0.054, 0.022] | Không (đổi dấu P3, không cặp nào loại trừ 0) |
| Neutral − Risk-off | + [-0.055, 0.098] | + [-0.025, 0.032] | **− [-0.062, -0.020]** | Không (đổi dấu P3, chỉ P3 loại trừ 0) |

### 5b. `market_entropy_regime` — 3 cặp

| Cặp | P1 (dấu, CI) | P2 (dấu, CI) | P3 (dấu, CI) | PASS? |
|---|---|---|---|---|
| Structured − Transitional | + [-0.016, 0.030] | − [-0.049, 0.024] | + [-0.006, 0.050] | Không (đổi dấu P2, không cặp nào loại trừ 0) |
| Structured − Chaotic | + [-0.022, 0.043] | − [-0.078, 0.008] | **+ [0.004, 0.065]** | Không (đổi dấu P2, chỉ P3 loại trừ 0) |
| Transitional − Chaotic | − [-0.025, 0.030] | − [-0.046, 0.000] | + [-0.011, 0.035] | Không (đổi dấu P3, không cặp nào loại trừ 0) |

**FAIL cho cả 2 chỉ báo — KHÔNG một cặp nào (trong cả 6 cặp) giữ cùng dấu
qua cả 3 giai đoạn**
(khác hẳn H1, nơi ít nhất "Risk-on − Risk-off" và "Transitional − Chaotic"
giữ cùng dấu). Đây **xác nhận đúng kết luận của
`docs/reports/scoring/FOLD_AUTOPSY_REPORT.md` NV2** ("Neither label cleanly separates the
disasters... this cross-tab has essentially no statistical power regardless
of what it shows") — nhưng giờ với N=1631 ngày thay vì 5 fold theo năm,
đây không còn là vấn đề thiếu lực thống kê. Bảng chẩn đoán ANOVA/KW toàn
mẫu "có ý nghĩa" ở trên là một minh chứng trực tiếp cho lý do vì sao thiết
kế prereg này bắt buộc dùng block bootstrap (xem mục 6) — nếu chỉ nhìn
p-value ngây thơ, kết luận sẽ SAI theo hướng dương tính giả.

---

## 6. Vì sao naive test đánh lừa — phát hiện phương pháp luận

So sánh trực tiếp trên đúng 36 tổ hợp (2 chỉ báo × {H1,H3} × 3 giai đoạn
× 3 cặp): Mann-Whitney U + BH-FDR q=0.05 (đúng quy ước `CLAUDE.md` mục 9,
chỉ để chẩn đoán, KHÔNG phải tiêu chí khóa) → **17/36 (47%) "sống sót"**
qua FDR. CI block-bootstrap (phương pháp đã khóa) trên ĐÚNG 36 tổ hợp đó
chỉ loại trừ 0 ở **6/36 (17%)** — chưa tới 1/3 số lượng "phát hiện" của
test ngây thơ, dù đã qua FDR. Quan trọng hơn cả tỷ lệ: **0/12 combo-cặp**
(6 cặp regime × 2 giả thuyết, mỗi combo cần đạt ở CẢ 3/3 giai đoạn) đạt
tiêu chí đầy đủ đã khóa — 6 lần loại-trừ-0 kể trên nằm rải rác, không lần
nào rơi đủ cả 3 giai đoạn của cùng một cặp.

Ví dụ cụ thể, rõ nhất: `market_regime` "Risk-on − Risk-off", H1, giai đoạn
P1 — Mann-Whitney U p=**2.99e-08** (sống sót FDR dễ dàng), nhưng CI
block-bootstrap cho ĐÚNG cặp/giai đoạn này là **[-0.144, 0.017]** — CHỨA
0, không có ý nghĩa theo phương pháp đã khóa. Nguyên nhân: `market_regime`
tự tương quan rất mạnh theo ngày liền kề (một ngày Risk-off gần như chắc
chắn theo sau bởi Risk-off — persistence lag=1 implied bởi bảng mục 4a),
cộng thêm `forward_vol_20d` tự nó chồng lấn 19/20 ngày giữa 2 quan sát
liền kề — cả hai làm ~544 "quan sát" per giai đoạn trên thực tế chỉ tương
đương ~20-30 khối độc lập thật sự. Test ngây thơ coi 544 quan sát là độc
lập, phóng đại ý nghĩa thống kê theo đúng cơ chế prereg đã cảnh báo trước
khi chạy (không phải diễn giải sau khi thấy kết quả).

**Bài học cho dự án**: đây là bằng chứng thực nghiệm trực tiếp (không chỉ
lý thuyết) cho lý do `CLAUDE.md` mục 9 (BH-FDR bên cạnh t-stat thô) và kỷ
luật "không t-test ngây thơ cho dữ liệu tự tương quan theo chuỗi" cần áp
dụng NGHIÊM cho bất kỳ nghiên cứu regime/chuỗi thời gian nào trong tương
lai — kể cả FDR cũng không đủ nếu đơn vị kiểm định gốc (naive p-value)
đã sai từ bước tính phương sai.

---

## 7. Kết luận tổng thể

| Giả thuyết | `market_regime` | `market_entropy_regime` |
|---|---|---|
| H1 (vol có điều kiện) | **FAIL** (near-miss: Risk-on−Risk-off cùng dấu 3/3, loại trừ 0 chỉ 1/3) | **FAIL** (near-miss: Transitional−Chaotic cùng dấu 3/3, loại trừ 0 chỉ 1/3) |
| H2 (bền vững) | **FAIL** (Neutral/Risk-off pass toàn mẫu nhưng không đủ 3/3 giai đoạn; Risk-on fail hoàn toàn) | **FAIL** (chỉ Transitional pass đầy đủ; Structured/Chaotic fail hoàn toàn) |
| H3 (return có điều kiện) | **FAIL** (không cặp nào cùng dấu 3 giai đoạn) | **FAIL** (không cặp nào cùng dấu 3 giai đoạn) |

**0/12 combo đạt tiêu chí đã khóa.** Đây là kết quả âm tính theo đúng quy
trình pre-register — không phải "chưa tìm ra", là một kết luận, đúng
RÀNG BUỘC "kết quả âm tính = kết quả, không thử thêm định nghĩa trạng
thái khác".

**Điều regime module THẬT SỰ làm tốt (không phải câu hỏi H1/H2/H3, quan
sát phụ đáng ghi lại)**: kiểm định ANOVA/KW toàn mẫu (chẩn đoán) cho thấy
CÓ khác biệt vol trung bình rất rõ giữa các nhóm regime (p rất nhỏ) —
regime state RÕ RÀNG có tương quan đồng thời (contemporaneous) với mức độ
biến động, điều này không có gì bất ngờ vì `market_regime`/`market_entropy_regime`
một phần được TÍNH TỪ chính dữ liệu vol/breadth hiện tại. Câu hỏi H1 khó
hơn nhiều: liệu trạng thái QUAN SÁT ĐƯỢC HÔM NAY có dự báo được vol 20
NGÀY TỚI theo cách đủ ổn định qua thời gian — và câu trả lời khóa-trước là
KHÔNG, dù có 2 near-miss đáng theo dõi (không phải kết luận, chỉ là ghi
nhận cho tương lai).

---

## 8. Caveat (đúng nguyên văn prereg)

Đây là kết quả về regime của **INDEX (VNINDEX)**, không tự động suy ra
ích lợi/vô ích cho chọn mã cổ phiếu — **không được kiểm định trong vòng
này**. Nếu ai đó muốn hỏi "regime có cải thiện null-test percentile của
`alpha_score` v2 không", đó là MỘT prereg riêng, hoàn toàn khác, chưa làm.
Với kết quả H1/H3 âm tính (dù near-miss ở H1), một prereg regime×chọn-mã
tiếp theo nên cân nhắc kỹ có đáng làm không — nhưng quyết định đó không
thuộc phạm vi báo cáo này.

---

## 9. Cập nhật hồ sơ

Thêm dòng #9 vào "5.2. Bảng hồ sơ đã đóng"
(`docs/PROJECT_HANDBOOK.md`) — xem commit riêng cho thay đổi đó.

*Báo cáo hoàn thành 2026-07-21. Không có tune tham số nào sau khi thấy
kết quả. Không kiểm định regime × chọn mã. Không thêm chỉ báo mới. Đúng
RÀNG BUỘC đã cho.*
