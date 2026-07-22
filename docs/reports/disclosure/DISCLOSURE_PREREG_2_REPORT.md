# DISCLOSURE_PREREG_2_REPORT — matched-control test, final round of the branch

**Kết quả của lần chạy DUY NHẤT theo `docs/reports/disclosure/DISCLOSURE_PREREG_2_CLUSTER.md`, khóa
trước khi chạy.** Không có tham số/định nghĩa cụm/cửa sổ nào bị đổi sau khi nhìn
số. Script: `scratch/disclosure_prereg2_cluster.py` (commit `02be8c0`). Kết quả
thô + lineage: `data/disclosure/prereg2_cluster_results.json`.

**Trích dẫn nguồn**: `docs/reports/data/DATA_BASELINE.md`, `docs/reports/data/DISCLOSURE_BASELINE.md`,
`docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`/`_REPORT.md` (test gốc), `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`
(lý do dùng đối chứng khớp cặp), `docs/reports/disclosure/DISCLOSURE_PREREG_2_CLUSTER.md` (thiết kế round
này, khóa trước).

## Kết luận một dòng

**Cả ba nhóm — H1 (cụm mua), H2 (gia đình), H0 (đối chứng nội bộ) — đều ÂM
TÍNH ở cả 3 mức lag.** Không nhóm nào đạt tiêu chí PASS đã khóa (CI dưới > 0
đồng thời ở cả +60 VÀ +120 ngày, VÀ dấu dương ổn định ở ≥2/3 giai đoạn). H0
cũng âm tính — xác nhận thiết kế đối chứng khớp cặp không rò rỉ false positive.
**Đây là test cuối cùng của nhánh disclosure-làm-tín-hiệu — đóng nhánh vĩnh
viễn cho mục đích tín hiệu, xem mục kết luận cuối bài.**

---

## 1. N từng nhóm (báo trước kết quả, đúng yêu cầu)

| | Lag +1 | Lag +3 | Lag +5 |
|---|---|---|---|
| Tổng sự kiện S1 đã gộp cụm | 2,318 | 2,320 | 2,320 |
| H1 (cụm, ≥2 người nội bộ khác nhau) | 1,023 | 1,023 | 1,023 |
| H2 (người liên quan gia đình) | 607 | 607 | 607 |
| H0 (đơn lẻ, không cụm không gia đình) | 946 | 948 | 948 |
| Bị loại (không có đối chứng hợp lệ) | 448 (19.3%) | 448 (19.3%) | 447 (19.3%) |
| Số đối chứng trung bình/sự kiện (trên các sự kiện giữ lại) | 4.88 | 4.88 | 4.88 |

(Tổng sự kiện thay đổi nhẹ 2,318→2,320 giữa lag +1 và +3/+5 — hiệu ứng biên của
việc dịch `available_at` làm thay đổi ranh giới gộp cụm 20-ngày cho một vài cặp
sự kiện sát biên, không phải lỗi.) **Cả ba nhóm đều vượt xa ngưỡng tối thiểu 30
sự kiện ở mọi cửa sổ** (ô nhỏ nhất: H2 ở +120 ngày, n=462–476 tùy lag) — đây
KHÔNG phải trường hợp N không đủ, tiêu chí PASS/âm tính áp dụng đầy đủ, không
rơi vào nhánh "chỉ mô tả, đóng nhánh vì thiếu lực thống kê".

## 2. Kết quả DCAR pooled (block bootstrap CI 95%, N=1000, block=60 ngày)

### H1 — cụm mua (≥2 người nội bộ khác nhau, cùng mã, cửa sổ 20 ngày)

| Lag | DCAR+20 | DCAR+60 | DCAR+120 | Verdict |
|---|---|---|---|---|
| +1 | +1.00% [−0.43%, +1.87%] (n=659) | +1.46% [−1.47%, +3.58%] (n=650) | +1.18% [−3.44%, +4.98%] (n=627) | NEGATIVE |
| +3 | +0.33% [−0.91%, +1.10%] (n=664) | +0.00% [−2.88%, +1.98%] (n=654) | −0.50% [−4.47%, +2.91%] (n=630) | NEGATIVE |
| +5 | +1.09% [−0.13%, +1.88%] (n=667) | +1.45% [−1.33%, +3.52%] (n=662) | +1.29% [−2.98%, +5.18%] (n=636) | NEGATIVE |

CI luôn chứa 0 ở cả 3 cửa sổ, cả 3 lag — không có cửa sổ nào đạt CI dưới > 0.

### H2 — người liên quan gia đình

| Lag | DCAR+20 | DCAR+60 | DCAR+120 | Verdict |
|---|---|---|---|---|
| +1 | **+1.95% [+0.43%, +2.94%]** (n=483) | **+3.60% [+1.18%, +5.70%]** (n=473) | +3.34% [−1.04%, +7.63%] (n=464) | NEGATIVE |
| +3 | +1.67% [+0.13%, +2.51%] | +2.13% [−0.04%, +3.89%] | +1.88% [−1.73%, +5.42%] | NEGATIVE |
| +5 | **+2.26% [+0.84%, +3.10%]** | **+3.39% [+0.55%, +5.39%]** | +3.73% [−0.46%, +7.42%] | NEGATIVE |

**Gần đạt nhất trong toàn bộ round này**: ở lag +1 và +5, CI dưới của DCAR+20 VÀ
DCAR+60 đều > 0 (dương có ý nghĩa riêng lẻ ở hai cửa sổ ngắn/vừa) — nhưng
**+120 ngày CI luôn chứa 0**, không thỏa điều kiện "cả +60 VÀ +120 đồng thời"
đã khóa. Xem mục 3 để hiểu vì sao +120 không giữ được dấu dương.

### H0 — đối chứng nội bộ (đơn lẻ, không cụm, không gia đình)

| Lag | DCAR+20 | DCAR+60 | DCAR+120 | Verdict |
|---|---|---|---|---|
| +1 | +1.03% [−0.01%, +1.83%] (n=829) | +2.11% [−0.05%, +4.45%] (n=807) | +0.40% [−4.00%, +4.23%] (n=772) | NEGATIVE |
| +3 | +0.54% [−0.52%, +1.25%] (n=828) | +0.39% [−1.93%, +2.63%] (n=796) | −2.09% [−6.71%, +1.12%] (n=779) | NEGATIVE |
| +5 | +0.67% [−0.43%, +1.40%] (n=845) | +0.88% [−1.38%, +2.98%] (n=801) | −0.97% [−5.10%, +2.25%] (n=774) | NEGATIVE |

**Đúng như kỳ vọng thiết kế**: H0 âm tính ở mọi lag, CI luôn chứa 0 (trừ vài
điểm chạm rất sát 0 ở +20 ngày, không có cửa sổ nào tách khỏi 0 rõ ràng) —
**xác nhận thiết kế đối chứng khớp cặp hoạt động đúng dự định, không rò rỉ
false positive.** Không cần diễn giải thận trọng thêm cho H1/H2 vì lý do thiết
kế lỗi.

## 3. Vì sao H2 không giữ được dấu dương ở +120 ngày — phân rã theo giai đoạn (lag +1)

| Giai đoạn | DCAR+60 mean (n) | DCAR+120 mean (n) |
|---|---|---|
| 2020-01→2022-03 | +7.07% (n=197) | **+11.33%** (n=198) |
| 2022-03→2024-05 | +1.70% (n=164) | −3.17% (n=165) |
| 2024-05→2026-07 | +0.27% (n=112) | −1.71% (n=101) |

Hiệu ứng dương của H2 **tập trung gần như toàn bộ ở Giai đoạn 1** (2020–2022);
Giai đoạn 2 và 3 phẳng-đến-âm ở +120 ngày. Số giai đoạn dương ở CẢ +60 VÀ +120
đồng thời: chỉ 1/3 (Giai đoạn 1) — không đạt ngưỡng ≥2/3 đã khóa, dù đã bỏ qua
tiêu chí CI. **Mẫu hình này giống hệt mẫu hình đã thấy ở H1/S1 trong
`docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`** (lift giảm mạnh qua 3 giai đoạn) — một
dấu hiệu lặp lại của hiệu ứng chỉ tồn tại trong giai đoạn dữ liệu sớm/mỏng hơn,
không phải một tín hiệu ổn định theo thời gian.

## 4. Độ nhạy lag

**Verdict không đổi cho bất kỳ nhóm nào giữa 3 mức lag** — cả ba đều NEGATIVE ở
+1/+3/+5. Không cần gắn cờ "tín hiệu mong manh với giả định trễ". Điểm DCAR và
CI dao động nhẹ theo lag (ví dụ H2 DCAR+60: +3.60% → +2.13% → +3.39%) nhưng
không đổi kết luận ở bất kỳ cửa sổ nào.

## 5. Diễn giải H0 (đã áp dụng ở mục 2)

H0 âm tính ở mọi lag/cửa sổ — **thiết kế đối chứng khớp cặp không có dấu hiệu
lỗi hệ thống.** Kết quả NEGATIVE của H1/H2 vì vậy được đọc là "thật" theo đúng
thiết kế test (không phải do đối chứng bị lệch), không cần diễn giải thận
trọng thêm như đã dự phòng trong prereg.

## 6. Caveat phương pháp luận — đây KHÔNG phải out-of-sample sạch tuyệt đối
(đáp lại adversarial review, 2026-07-22)

**Thừa nhận thẳng**: round này không phải một prereg thuần túy theo nghĩa
chặt nhất — "khám phá" (round 1 + `SURVIVORSHIP_BIAS_ESTIMATE.md` phát hiện
S3 dương bất thường, gợi ý confound survivorship) và "xác nhận" (round này,
thiết kế đối chứng khớp cặp để triệt tiêu đúng confound đó) đều chạy trên
**cùng một tập dữ liệu disclosure** (2020–2026, cùng nguồn CafeF, không phải
một mẫu mới chưa từng nhìn qua). Về mặt kỹ thuật, thiết kế của round này (khớp
cặp theo mã+ngày) đã bị THÔNG TIN bởi chính mẫu hình quan sát được ở round 1
— đây là điểm khác biệt thật so với một prereg "chưa từng thấy dữ liệu trước
khi khóa thiết kế", và adversarial review nêu đúng.

**Vai trò của H0 như cơ chế giảm nhẹ rủi ro này (không phải xóa bỏ hoàn
toàn)**: H0 (đối chứng nội bộ, đơn lẻ/không cụm/không gia đình) được khóa
TRƯỚC khi chạy trong CÙNG round này, và bản thân H0 cũng rút từ đúng tập dữ
liệu "đã khám phá" đó. Nếu toàn bộ thiết kế round 2 chỉ đơn thuần đang tái tạo
lại pattern dương giả từ việc "đã nhìn thấy dữ liệu", một cách hợp lý ta sẽ kỳ
vọng H0 CŨNG dương giả theo cùng cơ chế (cùng universe, cùng loại drift). H0
ra ÂM TÍNH sạch (mục 2, mục 5) là bằng chứng gián tiếp thiết kế khớp cặp đang
thực sự triệt tiêu confound, không chỉ đang tình cờ khớp lại với dữ liệu đã
xem — nhưng đây là một lập luận GIÁN TIẾP, không phải bằng chứng trực tiếp
tương đương một mẫu out-of-sample thật.

**Mức độ tin cậy nên đọc thấp hơn một bậc**: kết luận NEGATIVE của round này
nên được đọc với độ tin cậy THẤP HƠN một prereg thuần túy chưa từng thấy dữ
liệu trước khi khóa thiết kế (ví dụ round 1 gốc, `DISCLOSURE_EVENT_STUDY_PREREG.md`,
vốn không có bước "khám phá" nào đi trước) — dù H0 âm tính có phần trấn an,
nó không nâng độ tin cậy round này lên NGANG BẰNG một prereg sạch tuyệt đối.
**Điều này KHÔNG làm thay đổi kết luận đóng nhánh** (mục "Kết luận & đóng
nhánh" bên dưới) — kết quả âm tính vẫn giữ nguyên, và một round kiểm định
"explore-rồi-confirm cùng dataset" có bằng chứng H0 sạch vẫn là một lý do
chính đáng để đóng nhánh, chỉ là nên tự nhận thức rằng đây không phải mức
bằng chứng mạnh nhất có thể có (mức mạnh nhất sẽ cần dữ liệu disclosure hoàn
toàn mới, chưa từng được nhìn qua ở bất kỳ round nào trước).

---

## Kết luận & đóng nhánh (đúng ràng buộc gốc)

**Không nhóm nào (H1, H2, H0) đạt PASS ở bất kỳ lag nào.** Đây là test cuối
cùng đã pre-register của nhánh "disclosure như tín hiệu dự báo bùng nổ/vượt
trội" — theo đúng ràng buộc đã khóa trong `docs/reports/disclosure/DISCLOSURE_PREREG_2_CLUSTER.md`:
**kết quả âm tính → đóng nhánh vĩnh viễn cho mục đích tín hiệu.**

**Tổng kết toàn bộ hành trình nhánh disclosure** (3 round, `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`
→ `docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`/exploratory addendum → `docs/reports/disclosure/DISCLOSURE_PREREG_2_CLUSTER.md`):
- Test chính (lift bùng nổ, so 0): âm tính cho cả 3 tín hiệu cơ bản.
- Phát hiện phụ (CAR, so 0): dương nhưng hóa ra phần lớn là survivorship drift
  của chính universe, không phải nội dung tín hiệu (`docs/reports/scoring/SURVIVORSHIP_BIAS_ESTIMATE.md`).
- Hai giả thuyết có prior học thuật (cụm mua, gia đình), kiểm định đúng cách
  bằng đối chứng khớp cặp để triệt tiêu drift: **vẫn âm tính**, kể cả sau khi đã
  loại bỏ đúng confound đã tìm ra ở round trước.

**Không có nhân tố disclosure nào đạt ngưỡng ứng viên qua toàn bộ 3 round kiểm
định có pre-register.** Không mở thêm biến thể nào sau kết quả này (không đổi
định nghĩa cụm, không đổi số lượng đối chứng, không đổi cửa sổ) — đúng ràng
buộc "một lần chạy, kết quả nào cũng là kết thúc".

**Pipeline dữ liệu disclosure GIỮ NGUYÊN chạy live** — kết luận âm tính của toàn
bộ nhánh tín hiệu không làm dữ liệu vô giá trị: vẫn là nguồn tiềm năng cho
point-in-time universe (tin hủy niêm yết/đình chỉ, Gate #3) và cho bất kỳ hướng
nghiên cứu không liên quan đến "dự báo bùng nổ giá" nào trong tương lai. Chi
tiết đóng nhánh: `PUSH_REVIEW.md`.
