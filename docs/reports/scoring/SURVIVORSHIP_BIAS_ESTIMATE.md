# SURVIVORSHIP_BIAS_ESTIMATE — exploratory drift floor, not a confirmed decomposition

**Cập nhật 2026-07-22 — sửa cách diễn giải, đáp lại adversarial review (nghi
vấn lập luận vòng tròn)**: mục "Mức sàn hiệu chỉnh đề xuất" trước đây mô tả
+0.4/+1.2/+2.9% như một mức TRỪ CHÍNH XÁC. **Đây là mô tả không đủ chặt chẽ —
con số này là HỖN HỢP giữa survivorship bias thật (loại trừ mã đã hủy niêm
yết/ngừng giao dịch, thứ Gate #3 chưa có dữ liệu point-in-time để đo trực
tiếp) VÀ một hiệu ứng size/liquidity-tilt của chính bộ lọc "đủ điều kiện"
(thanh khoản ≥3 tỷ, không `INACTIVE_LONG`) — hai nguồn khác nhau, không tách
được bằng phương pháp round này, và bộ lọc size/liquidity không liên quan gì
tới việc công ty còn tồn tại hay không.** Đã viết lại mục "Mức sàn hiệu chỉnh
đề xuất" + "Giới hạn" bên dưới: con số này giờ dùng như **CẬN TRÊN thô** (bản
thân survivorship bias nhiều khả năng NHỎ HƠN con số này, không lớn hơn),
không phải mức trừ chính xác cho bất kỳ báo cáo nào khác — các báo cáo khác
đã trích dẫn con số này (`SCORE_V2_REPORT.md`, `PROJECT_HANDBOOK.md`, v.v.)
cũng đã sửa cách diễn giải cho nhất quán, xem PUSH_REVIEW.md round này.

**NHÃN: EXPLORATORY.** Tài liệu này ước lượng một con số, không kiểm định một giả
thuyết. Nó xuất phát từ một phát hiện phụ (không phải kết luận chính đã khóa) của
`docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`: tín hiệu đối chứng S3 (bán, kỳ vọng CAR ≤ 0
theo H2) lại có CAR dương gần bằng S1/S2 (mua) — gợi ý một phần lớn "excess
return" đo được trong round đó không đến từ nội dung tín hiệu disclosure, mà từ
việc bản thân universe hiện tại (mọi mã đủ điều kiện phân tích) đã có drift dương
sẵn so với VNINDEX, nhiều khả năng phản ánh survivorship bias (universe = "mã còn
sống hôm nay", đã ghi ở `docs/reports/data/DATA_BASELINE.md` caveat #2 / `docs/reports/data/DISCLOSURE_BASELINE.md`
caveat #2). **Không loại trừ được các nguyên nhân khác** (equity risk premium
chung của rổ đã lọc thanh khoản, độ lệch beta chưa gỡ hết dù đã trừ VNINDEX, hay
nhiễu thống kê) — con số dưới đây là một ước lượng nhất quán với giả thuyết
survivorship bias, không phải bằng chứng phân tách nguyên nhân.

**Script**: `scratch/survivorship_bias_estimate.py` (tái dùng nguyên cơ chế CAR +
block bootstrap đã kiểm chứng ở `scratch/disclosure_event_study.py`, không phát
minh phương pháp thống kê mới). Kết quả thô + lineage:
`data/disclosure/survivorship_bias_estimate.json`.

---

## Ba ước lượng độc lập, cùng bậc

### 1. Placebo S3 (bán, đối chứng H2) — CAR trung bình

| Cửa sổ | CAR trung bình | CI 95% (block bootstrap) | n |
|---|---|---|---|
| +20 ngày | +0.02% | [−0.78%, +0.97%] | 2,564 |
| +60 ngày | +2.63% | [−0.75%, +4.42%] | 2,536 |
| +120 ngày | +4.67% | [−1.02%, +8.15%] | 2,486 |

(Số liệu giống hệt `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md` mục 4 — không tính lại,
chỉ trích dẫn để đối chiếu cạnh hai ước lượng mới bên dưới.)

### 2. Toàn bộ sự kiện disclosure gộp (S1+S2+S3, đã gộp cụm theo từng loại rồi
   nối lại — không tái gộp cụm chéo giữa các loại tín hiệu)

| Cửa sổ | CAR trung bình | CI 95% | n |
|---|---|---|---|
| +20 ngày | +0.43% | [−0.22%, +1.41%] | 6,782 |
| +60 ngày | +2.85% | [−0.43%, +4.46%] | 6,683 |
| +120 ngày | +4.71% | [−1.05%, +8.24%] | 6,520 |

### 3. Đối chiếu chéo độc lập — excess return KHÔNG điều kiện bất kỳ sự kiện nào
   (toàn bộ `(mã, ngày)` trong rổ đủ điều kiện của `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`,
   toàn lịch sử 2020–2026)

| Cửa sổ | Excess return trung bình | CI 95% | n |
|---|---|---|---|
| +20 ngày | +0.38% | [−0.46%, +1.38%] | 346,852 |
| +60 ngày | +1.22% | [−1.09%, +4.24%] | 338,808 |
| +120 ngày | +2.85% | [−1.68%, +8.38%] | 325,679 |

**Đây là phép đối chiếu chéo hoàn toàn độc lập với disclosure** — không nhìn
ngày nào có sự kiện, chỉ lấy trung bình excess return của MỌI ngày giao dịch mà
một mã đủ điều kiện (thanh khoản ≥ 3 tỷ + không `INACTIVE_LONG`) đang có mặt
trong rổ. N lớn hơn nhiều bậc (325k–347k so với 2.5k–6.8k) nên CI hẹp hơn tương
đối so với quy mô N, dù vẫn khá rộng do bản chất phương sai cao của lợi nhuận cổ
phiếu.

## Đối chiếu — cùng bậc, nhưng không trùng khớp tuyệt đối

| Cửa sổ | Placebo S3 | Gộp tất cả sự kiện | Không điều kiện (cross-check) |
|---|---|---|---|
| +20 ngày | +0.02% | +0.43% | +0.38% |
| +60 ngày | +2.63% | +2.85% | **+1.22%** |
| +120 ngày | +4.67% | +4.71% | **+2.85%** |

**Nhận xét trung thực**: cả ba ước lượng cùng dấu dương, cùng hình dạng tăng
theo cửa sổ (đúng "cùng bậc" như giả thuyết survivorship dự đoán), và **CI của
cả ba chồng lấn nhau đáng kể ở mọi cửa sổ** (không thể bác bỏ giả thuyết ba con
số bằng nhau về mặt thống kê, do CI rất rộng). Nhưng điểm trung tâm không khớp
tuyệt đối: ở +60/+120 ngày, ước lượng có điều kiện sự kiện (placebo S3, gộp tất
cả) chạy cao hơn ước lượng không điều kiện khoảng **1.6–2.3 lần** (2.63–2.85% so
với 1.22% ở +60 ngày; 4.67–4.71% so với 2.85% ở +120 ngày). Có thể vì: (a) nhiễu
thống kê do CI rộng, (b) một hiệu ứng nhỏ thật sự gắn với việc "có công bố
disclosure gần đây" ngoài survivorship thuần túy (không phân biệt được ở round
này), hoặc (c) hiệu ứng lựa chọn thời điểm — sự kiện disclosure không phân bố
đều theo thời gian, có thể tập trung hơn vào giai đoạn thị trường đang lên. Round
này KHÔNG có đủ cơ sở để chọn giữa 3 khả năng trên.

## Mức sàn hiệu chỉnh đề xuất (correction floor) — ĐỌC LẠI 2026-07-22

**Con số này là CẬN TRÊN thô của một hỗn hợp 2 nguồn, KHÔNG phải mức trừ
chính xác cho survivorship bias thuần túy.** Method 3 (đối chiếu chéo không
điều kiện) đo trung bình excess return của rổ "đủ điều kiện" (thanh khoản ≥3
tỷ, không `INACTIVE_LONG`) — rổ này đồng thời là:
- **(a) Rổ sống sót** — chỉ gồm mã còn niêm yết/giao dịch hôm nay, đúng định
  nghĩa survivorship bias.
- **(b) Rổ đã lọc theo thanh khoản/quy mô** — bản thân bộ lọc "thanh khoản ≥3
  tỷ" là một size/liquidity-tilt, một hiệu ứng factor THẬT nhưng KHÔNG liên
  quan gì đến việc công ty còn tồn tại hay không (một cổ phiếu thanh khoản
  thấp vẫn có thể đang giao dịch bình thường, chỉ là nhỏ/kém thanh khoản).

Vì round này không có dữ liệu point-in-time (Gate #3) để tách riêng (a) khỏi
(b) — không có nhóm đối chứng "mã đã hủy niêm yết" để so sánh — con số
+0.4/+1.2/+2.9% đo (a)+(b) GỘP LẠI, không đo được (a) một mình. **Vì (b) là
một thành phần thật (không phải nhiễu, không phải lỗi), phần survivorship
bias THUẦN TÚY (a) nhiều khả năng NHỎ HƠN con số dưới đây, không lớn hơn** —
đây là lý do dùng nó như cận trên, không phải mức trừ đúng bằng:

| Cửa sổ backtest | Cận trên thô cho hỗn hợp survivorship + size-tilt |
|---|---|
| ~20 ngày giao dịch | **+0.4%** (làm tròn từ +0.38%, CI rộng chạm 0) |
| ~60 ngày giao dịch | **+1.2%** (làm tròn từ +1.22%) |
| ~120 ngày giao dịch | **+2.9%** (làm tròn từ +2.85%) |

**Cách dùng ĐÃ SỬA**: với bất kỳ backtest long-only nào trong dự án báo cáo
"excess return dương so với VNINDEX" trên cửa sổ nắm giữ gần với 20/60/120
ngày giao dịch:
- **KHÔNG trừ con số này ra khỏi excess return rồi coi phần còn lại là "alpha
  đã hiệu chỉnh"** — làm vậy ngụ ý con số là mức trừ chính xác cho
  survivorship thuần túy, trong khi nó lớn hơn survivorship thuần túy (vì gộp
  cả size-tilt).
- **Dùng như một ngưỡng cảnh báo cận trên**: nếu excess return đo được NHỎ
  HƠN con số này, không có cơ sở coi phần đó là bằng chứng "alpha thật" —
  hoàn toàn có thể chỉ là hỗn hợp survivorship+size-tilt của chính universe.
  Nếu excess return LỚN HƠN con số này, vẫn không suy ra được "phần vượt trên
  chắc chắn là alpha thật" — chỉ là ít có khả năng bị giải thích hết bởi hỗn
  hợp này hơn.
- **Hiệu lực cho đến khi dự án có point-in-time universe thật** (Gate #3,
  `audit/PATH_TO_100.md`), lúc đó nên đo lại survivorship bias trực tiếp
  (so sánh mã sống sót vs. mã đã hủy niêm yết tại từng thời điểm) thay vì suy
  luận gián tiếp + gộp nguồn như ở đây.

## Giới hạn (đọc trước khi dùng con số trên)

1. **Không phải một phép decomposition nguyên nhân** — chỉ là bằng chứng nhất
   quán với giả thuyết survivorship bias, không loại trừ được các lời giải
   thích khác (mục "Đối chiếu" ở trên).
2. **Là hỗn hợp survivorship bias + size/liquidity-tilt, không tách được ở
   round này (xem mục "Mức sàn hiệu chỉnh đề xuất" ngay trên) — dùng như cận
   trên thô, không phải mức trừ chính xác.** Đây là caveat quan trọng nhất
   sau khi sửa lại cách diễn giải 2026-07-22.
3. **CI rộng, chạm 0 ở cửa sổ 20 ngày cho cả ba ước lượng** — mức sàn ở cửa sổ
   ngắn kém tin cậy nhất về mặt thống kê, dù điểm trung tâm vẫn dương và tăng
   dần theo cửa sổ dài hơn (mẫu hình hợp lý về mặt kinh tế cho một drift tích
   lũy theo thời gian).
4. **Không tách theo giai đoạn/nhóm thanh khoản** ở round này (khác với test
   chính đã khóa trong `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`) — một ước lượng gộp
   toàn kỳ duy nhất, đơn giản hóa có chủ đích cho một exploratory pass.
5. **Kế thừa mọi caveat đã có** của rổ đủ điều kiện (18 mã `INACTIVE_LONG` bị
   loại khỏi lịch sử của chính nó, `trading_status` không thực point-in-time
   trước 2026-07-13) — xem `docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md` mục "Rổ đủ điều
   kiện".
6. **Đây KHÔNG phải một prereg mới, KHÔNG kiểm định lại H1/H2** — không có tiêu
   chí PASS/FAIL nào ở đây, chỉ là một con số ước lượng để dùng làm ngữ cảnh diễn
   giải cho các backtest khác.

## Lineage

`git_commit_hash`, thời điểm chạy — trong `data/disclosure/survivorship_bias_estimate.json`'s
`lineage` block (cùng cấu trúc lineage đã dùng ở `event_study_results.json`).
