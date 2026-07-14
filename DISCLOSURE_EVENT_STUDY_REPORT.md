# DISCLOSURE_EVENT_STUDY_REPORT — first test of the disclosure×price join

**Kết quả của lần chạy DUY NHẤT theo `DISCLOSURE_EVENT_STUDY_PREREG.md`, khóa
trước khi chạy.** Không có tham số/cửa sổ/ngưỡng nào bị đổi sau khi nhìn số.
Script: `scratch/disclosure_event_study.py` (commit `5f8f2b6`). Kết quả thô +
lineage đầy đủ: `data/disclosure/event_study_results.json`.

**Trích dẫn nguồn**: `DATA_BASELINE.md` (giá — `data/processed/stock_features.parquet`,
Gate #6 đã đóng), `DISCLOSURE_BASELINE.md` (disclosure — `data/disclosure/events.parquet`,
57,282 dòng), `DISCLOSURE_EVENT_STUDY_PREREG.md` (thiết kế test, khóa trước).

## Kết luận một dòng

**Test chính (lift bùng nổ): cả 3 tín hiệu đều ÂM TÍNH ở cả 3 mức lag** — không
có tín hiệu nào đạt PASS hay ỨNG VIÊN. Kết luận này ổn định qua cả 3 lag (không
cần gắn cờ "tín hiệu mong manh với giả định trễ" cho test chính). Test phụ (CAR)
cho thấy một điểm đáng chú ý làm suy yếu câu chuyện H2: tín hiệu đối chứng S3
(bán) có CAR dương tương tự S1/S2 (mua) thay vì CAR ≤ 0 như kỳ vọng — xem mục
"Diễn giải H2" bên dưới.

---

## 1. Rổ đủ điều kiện thực tế

391 mã, 351,183 dòng `(symbol, ngày giao dịch)` qua được cả hai điều kiện
(`value_ma20 >= 3 tỷ` + không phải `INACTIVE_LONG`). Sau khi loại các ngày
không tính được nhãn `event` (còn thiếu 60 ngày giao dịch tới, ví dụ cuối chuỗi
dữ liệu): **327,016 dòng có nhãn xác định**, base rate bùng nổ pooled toàn mẫu
= **10.72%**.

Khác với rủi ro đã cảnh báo trước trong prereg (dựa trên `EVENT_DETECTION_REPORT.md`'s
ngưỡng 10 tỷ cũ, nơi Giai đoạn 1 gần như không có mã đủ điều kiện): ở ngưỡng 3 tỷ
+ `full_history_v2`, **cả 3 giai đoạn đều vượt xa ngưỡng tối thiểu 30 sự kiện**
(19,974 / 9,125 / 5,972 sự kiện bùng nổ trong panel đủ điều kiện của mỗi giai
đoạn) — rủi ro "Giai đoạn 1 không đủ dữ liệu để kết luận" đã không xảy ra, cả 3
giai đoạn đều tham gia phân loại PASS/ỨNG VIÊN/âm tính.

## 2. Test chính — lift bùng nổ (pooled, block bootstrap CI 95%, N=1000, block=60 ngày)

### S1 — mua nội bộ/người liên quan (H1)

| Lag | Pooled lift | CI 95% | Giai đoạn 1 (2020-01→2022-03) | Giai đoạn 2 (2022-03→2024-05) | Giai đoạn 3 (2024-05→2026-07) | Verdict |
|---|---|---|---|---|---|---|
| +1 | 1.020 | [0.817, 1.153] | 1.137 [1.030, 1.295] | 0.840 [0.657, 1.003] | 0.314 [0.217, 0.408] | NEGATIVE |
| +3 | 1.010 | [0.808, 1.146] | 1.127 [1.031, 1.289] | 0.822 [0.653, 0.974] | 0.311 [0.213, 0.414] | NEGATIVE |
| +5 | 1.005 | [0.808, 1.139] | 1.119 [1.038, 1.287] | 0.815 [0.657, 0.966] | 0.309 [0.208, 0.426] | NEGATIVE |

Pooled CI dưới không vượt 1.0 ở lag nào → không đạt cả ngưỡng ỨNG VIÊN (cần CI
dưới > 1.0). **Mẫu hình đáng chú ý (mô tả, không phải một phần của tiêu chí
khóa)**: lift giảm mạnh đơn điệu qua 3 giai đoạn — dương nhẹ và có ý nghĩa ở
Giai đoạn 1 (CI dưới 1.03-1.04, tức *lớn hơn 1* riêng ở giai đoạn này) rồi đảo
chiều mạnh, xuống còn 0.31 (CI trên chỉ 0.41-0.43) ở Giai đoạn 3 — tức gần đây
mã có tín hiệu mua nội bộ *ít* khả năng bùng nổ hơn base rate, ngược hướng H1.
Không suy diễn nguyên nhân (thị trường hiệu quả hơn theo thời gian, thay đổi
cấu trúc universe, hay nhiễu) — chỉ ghi nhận mẫu hình.

### S2 — mua cổ đông lớn (H1)

| Lag | Pooled lift | CI 95% | Giai đoạn 1 | Giai đoạn 2 | Giai đoạn 3 | Verdict |
|---|---|---|---|---|---|---|
| +1 | 0.906 | [0.766, 1.078] | 0.943 [0.801, 1.158] | 0.750 [0.497, 0.912] | 0.666 [0.544, 0.833] | NEGATIVE |
| +3 | 0.902 | [0.764, 1.075] | 0.945 [0.804, 1.151] | 0.740 [0.491, 0.890] | 0.659 [0.528, 0.839] | NEGATIVE |
| +5 | 0.896 | [0.757, 1.068] | 0.943 [0.807, 1.145] | 0.737 [0.490, 0.873] | 0.639 [0.500, 0.845] | NEGATIVE |

Lift < 1 ở **cả 3 giai đoạn, cả 3 lag** — bằng chứng nhất quán nhất trong round
này, nhưng theo hướng ngược lại H1 hoàn toàn (mã có mua cổ đông lớn *ít* khả
năng bùng nổ hơn base rate, không phải nhiều hơn). Không có mẫu hình đảo chiều
theo thời gian như S1 — âm tính ổn định.

### S3 — bán nội bộ/người liên quan (đối chứng, H2)

| Lag | Pooled lift | CI 95% | Giai đoạn 1 | Giai đoạn 2 | Giai đoạn 3 | (diễn giải H2) |
|---|---|---|---|---|---|---|
| +1 | 1.094 | [0.970, 1.174] | 0.923 [0.841, 1.008] | 0.924 [0.688, 0.986] | 0.817 [0.483, 1.145] | phù hợp H2 |
| +3 | 1.081 | [0.966, 1.157] | 0.909 [0.835, 0.985] | 0.927 [0.683, 0.992] | 0.804 [0.476, 1.133] | phù hợp H2 |
| +5 | 1.067 | [0.956, 1.139] | 0.894 [0.825, 0.968] | 0.936 [0.688, 1.002] | 0.790 [0.460, 1.131] | phù hợp H2 |

**Theo test lift chính, H2 được xác nhận**: lift(S3) không đạt mức PASS/ỨNG VIÊN
ở bất kỳ lag/giai đoạn nào (đa số < 1, CI pooled trên chỉ vừa chớm 1.17-1.18) —
đăng ký bán không dự báo bùng nổ mạnh hơn base rate, đúng hướng H2 dự đoán. **Xem
mục 4 bên dưới**: test phụ CAR lại kể một câu chuyện khác cho cùng tín hiệu này.

### Theo nhóm thanh khoản (lag +1, mô tả — không nằm trong tiêu chí phân loại khóa)

| Tín hiệu | Thanh khoản cao | Thanh khoản thấp |
|---|---|---|
| S1 | 0.981 [0.748, 1.159] | 1.086 [0.819, 1.310] |
| S2 | 0.896 [0.726, 1.100] | 0.959 [0.803, 1.147] |
| S3 | **1.208 [1.041, 1.312]** | 0.975 [0.799, 1.109] |

**Đáng chú ý**: nhóm thanh khoản cao của S3 (bán) đạt CI dưới > 1.0 (1.041) —
mức đạt tiêu chí ỨNG VIÊN NẾU đây là một lát cắt chính thức, nhưng tiêu chí đã
khóa trong prereg chỉ dùng lát cắt theo 3 giai đoạn thời gian để phân loại
PASS/ỨNG VIÊN/âm tính, không dùng nhóm thanh khoản — nên không đổi verdict
chính thức của S3, chỉ ghi nhận như một quan sát mô tả cần theo dõi nếu có round
sau.

## 3. Độ nhạy lag backfill (+1/+3/+5)

**Kết luận (PASS/ỨNG VIÊN/âm tính) không đổi cho bất kỳ tín hiệu nào giữa 3
mức lag** — cả số lift điểm lẫn CI đều dịch chuyển rất nhẹ (ví dụ S1 pooled:
1.020 → 1.010 → 1.005). **Không cần gắn cờ "tín hiệu mong manh với giả định
trễ"** cho test chính. Cần nhắc lại giới hạn đã ghi trong prereg: gần như 100%
(57,282/57,282, xác nhận lại khi chạy NV2) dòng `events.parquet` có
`is_backfilled=True`, tức toàn bộ kết quả trên đều dựa trên giả định lag, dù
kết luận ổn định qua 3 giá trị lag đã thử.

## 4. Test phụ — CAR (Cumulative Abnormal Return), lag +1

Gộp cụm sự kiện cùng mã cách nhau < 20 ngày giao dịch (chỉ giữ sự kiện đầu mỗi
cụm): S1 9,958 → 2,318 sự kiện; S2 8,616 → 2,360; S3 10,691 → 2,762.

| Tín hiệu | CAR +20 ngày | CAR +60 ngày | CAR +120 ngày |
|---|---|---|---|
| S1 (mua nội bộ) | +0.80% [−0.01%, 2.11%] (n=2,092) | +3.64% [−0.09%, 6.08%] (n=2,067) | +5.34% [−1.43%, 9.86%] (n=2,001) |
| S2 (mua cổ đông lớn) | +0.56% [−0.07%, 1.54%] (n=2,126) | +2.33% [−0.80%, 3.42%] (n=2,080) | +4.14% [−1.20%, 7.08%] (n=2,033) |
| S3 (bán, đối chứng) | +0.02% [−0.78%, 0.97%] (n=2,564) | +2.63% [−0.75%, 4.42%] (n=2,536) | +4.67% [−1.02%, 8.15%] (n=2,486) |

## Diễn giải H2 — mâu thuẫn giữa test chính và test phụ

**H2 dự đoán CAR(S3) ≤ 0.** Số liệu thực tế: CAR(S3) dương và tăng dần theo cửa
sổ (+0.02% → +2.63% → +4.67%), **độ lớn gần tương đương S1/S2** (mua) ở cùng cửa
sổ +60/+120 ngày. CI ở cả ba cửa sổ đều chứa 0 (không có cửa sổ nào bác bỏ được
giả thuyết CAR=0 ở mức 95%), nhưng điểm trung tâm hoàn toàn không ủng hộ CAR≤0 —
nếu có gì, nó giống S1/S2 hơn là "không có hiệu ứng" hay "hiệu ứng âm".

**Kết luận trung thực, đúng như đã khóa trước trong prereg (mục "Tiêu chí cho
S3")**: đây là trường hợp **"H2 bị thách thức"**. Test lift chính (xác suất
bùng nổ nhị phân) và test CAR (lợi nhuận vượt trội trung bình) cho hai câu
chuyện khác nhau về cùng một tín hiệu S3 — lift ủng hộ H2 (bán không dự báo
*bùng nổ*), nhưng CAR gợi ý một hiệu ứng "có công bố giao dịch nội bộ, bất kể
chiều mua/bán" đi kèm với xu hướng giá dương nhẹ-vừa phải (không đạt mức "bùng
nổ" +25%/60 ngày) sau đó — khác với câu chuyện "đăng ký mua mang thông tin
riêng, đăng ký bán thì không mang thông tin" mà H1/H2 cùng giả định. Không đủ
cơ sở để kết luận nguyên nhân (hiệu ứng công bố nói chung, thiên lệch lựa chọn
thời điểm công bố, hay yếu tố khác) trong phạm vi round này.

## Phân loại tổng hợp

| Tín hiệu | Test chính (lift) | Test phụ (CAR) |
|---|---|---|
| S1 (mua nội bộ/liên quan) | **NEGATIVE** — không PASS/ỨNG VIÊN ở lag/giai đoạn nào; mẫu hình đảo chiều theo thời gian (dương → âm) | CAR dương, tăng theo cửa sổ, CI luôn gần chạm 0 — hướng khớp H1 nhưng không có cửa sổ nào loại trừ được CAR=0 |
| S2 (mua cổ đông lớn) | **NEGATIVE** — lift < 1 nhất quán cả 3 giai đoạn, cả 3 lag | CAR dương nhỏ, tương tự S1, cùng mức không loại trừ được CAR=0 |
| S3 (bán, đối chứng H2) | Lift < 1 phần lớn giai đoạn — **phù hợp hướng H2** theo test chính | CAR dương, độ lớn ngang S1/S2 — **thách thức H2** |

## Caveat (kế thừa từ prereg, xác nhận vẫn hiệu lực sau khi chạy)

1. **Survivorship bias** — không định lượng thêm ở round này, vẫn là giới hạn
   đã biết (`DATA_BASELINE.md`, `DISCLOSURE_BASELINE.md`).
2. **Panel disclosure lệch mã lớn/lâu đời** — test chính không chuẩn hóa theo
   tuổi niêm yết/vốn hóa, chỉ theo giai đoạn thời gian + nhóm thanh khoản.
3. **18 mã `INACTIVE_LONG`** bị loại khỏi rổ đủ điều kiện ở MỌI ngày lịch sử
   (kể cả khi còn active) — quyết định đã khóa trong prereg, không phải phát
   hiện mới.
4. **`trading_status` không thực sự point-in-time cho các ngày trước
   2026-07-13** — dùng snapshot hiện tại áp đồng nhất cho toàn lịch sử, đúng
   như đã khóa.
5. **Không có hiệu chỉnh đa kiểm định chính thức** cho 3 tín hiệu × 3 giai đoạn
   × 2 nhóm thanh khoản × 3 lag — tiêu chí 3 bậc (CI dưới > 1.5, đồng dấu 3/3
   giai đoạn cho PASS) là hàng rào thiết kế, không phải một phép hiệu chỉnh
   thống kê chính thức.
6. **Bug đã sửa trong lúc chạy NV2 (không phải tune kết quả)**: 387 dòng
   `stock_features.parquet` có `close <= 0` (lỗi dữ liệu đã biết, không thuộc
   phạm vi round này) khiến CAR ban đầu ra `inf`/`nan` cho một số sự kiện S1 —
   sửa bằng đúng convention loại giá không dương đã có sẵn ở
   `src/features/returns.py::add_returns`, chạy lại toàn bộ một lần nữa trước
   khi coi là kết quả cuối cùng.

## Lineage

`git_commit_hash`, hash + số dòng của mọi input (`events.parquet`,
`stock_features.parquet`, `benchmark_vnindex.parquet`, `trading_status.parquet`,
`VNINDEX.parquet`), hash của chính `DISCLOSURE_EVENT_STUDY_PREREG.md`, và thời
điểm chạy — đầy đủ trong `data/disclosure/event_study_results.json`'s `lineage`
block.

---

## Kết luận & dừng lại (đúng ràng buộc gốc)

**Một lần chạy — kết quả không đạt PASS/ỨNG VIÊN cho H1 ở cả 3 tín hiệu chính,
và H2 bị thách thức bởi test phụ.** Theo đúng ràng buộc đã nêu ở đầu round này:
**báo cáo, dừng lại, không thử thêm cửa sổ/ngưỡng/vai trò mới, không tune.**
Không có gợi ý "thử ngưỡng khác" hay "thử vai trò tín hiệu khác" nào được thực
hiện sau khi nhìn kết quả trên. Quyết định tiếp theo (có đáng thử một thiết kế
event-study khác trong một round hoàn toàn mới, có prereg riêng, hay dừng hẳn
hướng "insider disclosure dự báo bùng nổ" ở đây) dành cho người dùng, không tự
quyết trong round này.
