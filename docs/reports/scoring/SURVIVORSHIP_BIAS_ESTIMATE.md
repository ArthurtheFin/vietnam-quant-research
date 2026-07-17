# SURVIVORSHIP_BIAS_ESTIMATE — exploratory drift floor, not a confirmed decomposition

**NHÃN: EXPLORATORY.** Tài liệu này ước lượng một con số, không kiểm định một giả
thuyết. Nó xuất phát từ một phát hiện phụ (không phải kết luận chính đã khóa) của
`docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md`: tín hiệu đối chứng S3 (bán, kỳ vọng CAR ≤ 0
theo H2) lại có CAR dương gần bằng S1/S2 (mua) — gợi ý một phần lớn "excess
return" đo được trong round đó không đến từ nội dung tín hiệu disclosure, mà từ
việc bản thân universe hiện tại (mọi mã đủ điều kiện phân tích) đã có drift dương
sẵn so với VNINDEX, nhiều khả năng phản ánh survivorship bias (universe = "mã còn
sống hôm nay", đã ghi ở `docs/reports/data/docs/reports/data/DATA_BASELINE.md` caveat #2 / `docs/reports/data/docs/reports/data/DISCLOSURE_BASELINE.md`
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

(Số liệu giống hệt `docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_REPORT.md` mục 4 — không tính lại,
chỉ trích dẫn để đối chiếu cạnh hai ước lượng mới bên dưới.)

### 2. Toàn bộ sự kiện disclosure gộp (S1+S2+S3, đã gộp cụm theo từng loại rồi
   nối lại — không tái gộp cụm chéo giữa các loại tín hiệu)

| Cửa sổ | CAR trung bình | CI 95% | n |
|---|---|---|---|
| +20 ngày | +0.43% | [−0.22%, +1.41%] | 6,782 |
| +60 ngày | +2.85% | [−0.43%, +4.46%] | 6,683 |
| +120 ngày | +4.71% | [−1.05%, +8.24%] | 6,520 |

### 3. Đối chiếu chéo độc lập — excess return KHÔNG điều kiện bất kỳ sự kiện nào
   (toàn bộ `(mã, ngày)` trong rổ đủ điều kiện của `docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`,
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

## Mức sàn hiệu chỉnh đề xuất (correction floor)

**Dùng con số đối chiếu chéo không điều kiện (mục 3) làm mức sàn chính** — đây
là ước lượng độc lập nhất với thiết kế disclosure event-study (không phụ thuộc
việc chọn sự kiện nào, cụm hóa ra sao), N lớn nhất, và là con số áp dụng trực
tiếp nhất cho "một mã bất kỳ trong universe hiện tại, tại một ngày bất kỳ":

| Cửa sổ backtest | Mức sàn hiệu chỉnh (trừ khi diễn giải excess return) |
|---|---|
| ~20 ngày giao dịch | **+0.4%** (làm tròn từ +0.38%, CI rộng chạm 0) |
| ~60 ngày giao dịch | **+1.2%** (làm tròn từ +1.22%) |
| ~120 ngày giao dịch | **+2.9%** (làm tròn từ +2.85%) |

**Cách dùng**: với bất kỳ backtest long-only nào trong dự án báo cáo "excess
return dương so với VNINDEX" trên cửa sổ nắm giữ gần với 20/60/120 ngày giao
dịch, trừ mức sàn tương ứng ở bảng trên trước khi diễn giải phần excess return
còn lại là "alpha thật". Nếu excess return đo được nhỏ hơn mức sàn, phần đó
**không được coi là bằng chứng của một tín hiệu/chiến lược có giá trị** — nhiều
khả năng chỉ là survivorship bias của chính universe. Đây là một heuristic diễn
giải, không phải một phép hiệu chỉnh toán học chính xác (CI của mức sàn còn
rộng, chạm 0 ở cửa sổ ngắn) — **hiệu lực cho đến khi dự án có point-in-time
universe thật (Gate #3, `audit/PATH_TO_100.md`)**, lúc đó nên đo lại survivorship
bias trực tiếp thay vì suy luận gián tiếp qua placebo như ở đây.

## Giới hạn (đọc trước khi dùng con số trên)

1. **Không phải một phép decomposition nguyên nhân** — chỉ là bằng chứng nhất
   quán với giả thuyết survivorship bias, không loại trừ được các lời giải
   thích khác (mục "Đối chiếu" ở trên).
2. **CI rộng, chạm 0 ở cửa sổ 20 ngày cho cả ba ước lượng** — mức sàn ở cửa sổ
   ngắn kém tin cậy nhất về mặt thống kê, dù điểm trung tâm vẫn dương và tăng
   dần theo cửa sổ dài hơn (mẫu hình hợp lý về mặt kinh tế cho một drift tích
   lũy theo thời gian).
3. **Không tách theo giai đoạn/nhóm thanh khoản** ở round này (khác với test
   chính đã khóa trong `docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md`) — một ước lượng gộp
   toàn kỳ duy nhất, đơn giản hóa có chủ đích cho một exploratory pass.
4. **Kế thừa mọi caveat đã có** của rổ đủ điều kiện (18 mã `INACTIVE_LONG` bị
   loại khỏi lịch sử của chính nó, `trading_status` không thực point-in-time
   trước 2026-07-13) — xem `docs/reports/disclosure/docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md` mục "Rổ đủ điều
   kiện".
5. **Đây KHÔNG phải một prereg mới, KHÔNG kiểm định lại H1/H2** — không có tiêu
   chí PASS/FAIL nào ở đây, chỉ là một con số ước lượng để dùng làm ngữ cảnh diễn
   giải cho các backtest khác.

## Lineage

`git_commit_hash`, thời điểm chạy — trong `data/disclosure/survivorship_bias_estimate.json`'s
`lineage` block (cùng cấu trúc lineage đã dùng ở `event_study_results.json`).
