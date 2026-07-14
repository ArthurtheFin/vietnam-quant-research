# DISCLOSURE_PREREG_2_CLUSTER — matched-control test of the two exploratory findings

**Viết và commit TRƯỚC khi bất kỳ dòng code nào chạy thiết kế dưới đây.** Đây là
lần kiểm định XÁC NHẬN đầu tiên của hai giả thuyết được sinh ra ở
`DISCLOSURE_EVENT_STUDY_REPORT.md`'s "Exploratory addendum" — hai lát cắt đó
(cụm nhiều người nội bộ, người liên quan gia đình) **trùng với văn liệu học
thuật về insider trading** (cluster buying như một tín hiệu tin cậy hơn — vd.
Ali & Hirshleifer 2016 "opportunistic vs. routine" clustering; buying của
người liên quan gia đình như một kênh né tránh giám sát trực tiếp nhưng vẫn
mang thông tin — cả hai đều là giả thuyết đã có prior trong tài liệu insider-
trading quốc tế, không phải suy đoán tự do từ dữ liệu này). Đây là **phát súng
cuối của nhánh disclosure**: PASS hay âm tính, nhánh đóng lại sau round này theo
đúng kết quả, không mở thêm biến thể.

**Khác biệt cốt lõi so với `DISCLOSURE_EVENT_STUDY_PREREG.md`**: test trước so
CAR với 0 (không có gì làm chuẩn) — `SURVIVORSHIP_BIAS_ESTIMATE.md` cho thấy
điều đó lẫn vào một mức drift dương ~+2.9%/120 ngày không liên quan gì đến nội
dung tín hiệu, chỉ vì bản thân universe "còn sống" đã có drift dương. Round này
so với **đối chứng khớp cặp** (matched control) thay vì 0 — mọi mã đối chứng đều
chịu CÙNG mức drift đó (cùng thời điểm, cùng nhóm thanh khoản, cùng trạng thái
giao dịch), nên hiệu số `DCAR = CAR(sự kiện) − CAR(đối chứng)` triệt tiêu phần
lớn survivorship drift ở cả hai vế, còn lại phần chênh lệch (nếu có) mới thật sự
gắn với nội dung tín hiệu.

**Nguồn trích dẫn**: `DATA_BASELINE.md`, `DISCLOSURE_BASELINE.md`,
`DISCLOSURE_EVENT_STUDY_PREREG.md` + `DISCLOSURE_EVENT_STUDY_REPORT.md` (test
gốc, kết luận âm tính), `SURVIVORSHIP_BIAS_ESTIMATE.md` (lý do thiết kế đối
chứng khớp cặp thay vì so 0).

---

## Giả thuyết

- **H1 (cụm mua)**: sự kiện "cụm mua" — **≥2 người nội bộ/liên quan KHÁC NHAU**
  cùng đăng ký mua (`S1`, đúng định nghĩa `insider_registration`+`buy` đã dùng ở
  round trước) **trong cùng cửa sổ 20 ngày giao dịch, cùng mã** — có DCAR vượt
  đối chứng khớp cặp.
- **H2 (người liên quan gia đình)**: đăng ký mua mà người đứng tên giao dịch là
  người liên quan gia đình (`person_role` ∈ nhóm "Người liên quan (gia đình)" —
  đúng nguyên cách gộp nhóm `ROLE_GROUPS` đã dùng trong exploratory addendum,
  không định nghĩa lại) có DCAR vượt đối chứng khớp cặp.
- **Đối chứng H0 nội bộ**: đăng ký mua **đơn lẻ** (không thuộc nhóm cụm, không
  thuộc nhóm gia đình) — kỳ vọng theo `DISCLOSURE_EVENT_STUDY_REPORT.md`'s kết
  luận chính (test lift/CAR gốc, không điều kiện theo lát cắt, đều âm tính/không
  vượt 0): **không vượt đối chứng**. H0 không phải một giả thuyết cần "thắng" —
  vai trò của nó là kiểm tra tính hợp lệ của chính thiết kế đối chứng khớp cặp:
  nếu H0 CŨNG đạt PASS, đó là dấu hiệu thiết kế đối chứng có lỗi hệ thống (chưa
  triệt tiêu hết drift), không phải bằng chứng "mọi đăng ký mua đều có giá trị".

**Không định nghĩa nhóm mới, không định nghĩa lại nhóm cũ**: ba nhóm trên dùng
đúng các cột đã tính sẵn trong `scratch/car_s1_autopsy.py`
(`multi_insider_cluster`, `role_group`) trên đúng tập 2,318 sự kiện `S1` đã gộp
cụm (theo mã, cửa sổ 20 ngày) từ round trước — không tính lại từ đầu. Ba nhóm
**không nhất thiết loại trừ lẫn nhau** giữa H1 và H2 (một sự kiện có thể vừa là
cụm vừa có người đứng tên là người liên quan gia đình) — đúng cách đã làm ở
exploratory addendum, khóa lại ở đây để tránh tạo phân vùng 3 nhóm loại trừ lẫn
nhau giả tạo. H0 = phần bù của (cụm HOẶC gia đình), tức chỉ những sự kiện không
thuộc cả hai.

**Số N đã biết trước (từ exploratory addendum, không phải kết quả mới của round
này)**: 909/2,318 sự kiện thuộc nhóm cụm (ở cửa sổ +20 ngày; 909/890 ở +60/+120
do một số sự kiện thiếu dữ liệu giá cuối chuỗi), 556/2,318 thuộc nhóm gia đình
(550/541 ở +60/+120) — **cao hơn nhiều so với dự đoán "không nhiều" trong yêu
cầu gốc của round này**. Ghi nhận trung thực ngay từ đầu: N cho H1/H2 nhiều khả
năng đủ lớn để không rơi vào nhánh "< 30 sự kiện, chỉ mô tả" — nhưng con số cuối
cùng của round này sẽ THẤP HƠN các số trên, vì thêm điều kiện "có đủ đối chứng
khớp cặp hợp lệ" có thể loại bớt một số sự kiện (xem thiết kế đối chứng bên
dưới) — không hạ thấp kỳ vọng xuống mức "chắc chắn dưới 30" chỉ vì yêu cầu gốc
dự đoán vậy, cũng không giả định N sẽ đủ lớn — để NV2 báo số thật.

## Thiết kế đối chứng khớp cặp (matched control)

Với mỗi sự kiện `(mã i, ngày t = day_idx của available_at trên lịch giao dịch
VNINDEX)`:

1. **Rổ ứng viên đối chứng**: mọi mã `j ≠ i` có `value_ma20` xác định tại ngày
   `t` (không giới hạn trong rổ "đủ điều kiện" 3 tỷ của prereg trước — dùng toàn
   bộ universe có dữ liệu giá hợp lệ tại `t`, để có rổ ứng viên đủ rộng cho việc
   khớp cặp, kể cả khi mã sự kiện `i` bản thân nằm dưới ngưỡng 3 tỷ).
2. **Cùng nhóm thanh khoản**: `value_ma20` của `j` tại `t` rơi vào cùng tam phân
   vị (tercile, tính trên toàn bộ mã có `value_ma20` xác định tại `t`, không chỉ
   rổ đủ điều kiện) với mã `i` tại `t`.
3. **Cùng `trading_status` = `ACTIVE`** tại `t` (dùng snapshot hiện tại
   `latest_trading_status()`, đúng quyết định đã khóa ở
   `DISCLOSURE_EVENT_STUDY_PREREG.md` — snapshot hiện tại áp đồng nhất cho toàn
   lịch sử, không phải tái lập point-in-time thật cho các ngày trước
   2026-07-13). Chỉ áp cho ỨNG VIÊN ĐỐI CHỨNG, không áp thêm điều kiện này cho
   mã sự kiện `i` (mã sự kiện giữ nguyên như tập đã gộp cụm từ round trước,
   không lọc thêm).
4. **"Sạch" trong cửa sổ**: `j` không có bất kỳ dòng nào trong
   `data/disclosure/events.parquet` (mọi `event_type`/`direction`, không riêng
   `S1`) với `available_at` (lag=1 mặc định) rơi vào `[t − 60, t + 120]` ngày
   giao dịch. Mã sự kiện `i` tự động không đạt điều kiện này cho chính cửa sổ
   của nó (vì `t` nằm trong khoảng đang xét) — không cần loại trừ thủ công.
5. **Chọn ngẫu nhiên 5 mã** từ rổ ứng viên đã lọc (điều kiện 1–4), seed cố định
   `42`, một `numpy.random.default_rng(42)` toàn cục tiến tuần tự theo thứ tự
   sự kiện đã sắp xếp `(symbol, day_idx)` — tái lập được, không thử nhiều seed.
   **Nếu ứng viên < 5**: dùng hết số ứng viên có được (báo cáo số thực tế dùng
   mỗi sự kiện, không loại sự kiện chỉ vì thiếu quân số). **Nếu ứng viên = 0**:
   loại sự kiện đó khỏi panel `DCAR` (không thể tính đối chứng) — đếm và báo cáo
   riêng số sự kiện bị loại vì lý do này.

## Thước đo

```
CAR(mã, t, h)      = lợi nhuận đơn mã từ t đến t+h ngày giao dịch
                      − lợi nhuận đơn VNINDEX cùng cửa sổ (giống hệt phương
                      pháp compute_car() ở round trước — không đổi)
DCAR(sự kiện, h)   = CAR(mã sự kiện i, t, h) − trung bình CAR(5 mã đối chứng, t, h)
```
`h ∈ {20, 60, 120}` ngày giao dịch, tính từ `available_at`. Sự kiện cụm chồng
lấn cùng mã: gộp lấy sự kiện đầu — **đúng nguyên cơ chế `cluster_events()`
(gap=20 ngày) đã dùng ở round trước, không định nghĩa cụm khác cho round này.**

## CI

Block bootstrap theo lịch: khối 60 ngày giao dịch liên tiếp (theo `day_idx` của
sự kiện, không phải của đối chứng), ≥ 1,000 lần, seed `42` — đúng cơ chế
`block_bootstrap_mean_car()` đã kiểm chứng ở round trước, áp lên chuỗi `DCAR`
thay vì `CAR`.

## Tiêu chí (khóa trước, áp dụng cơ học giống nhau cho H1, H2, VÀ H0 — không có
   nhánh logic riêng cho từng nhóm trong code)

- **PASS**: CI 95% của `DCAR` trung bình (pooled toàn mẫu) ở **CẢ +60 VÀ +120
  ngày** đều nằm hoàn toàn > 0 (CI dưới > 0 ở cả hai cửa sổ), **VÀ** dấu dương
  ổn định (điểm trung tâm DCAR > 0) ở **≥ 2/3 giai đoạn thời gian** (tái dùng
  nguyên 3 giai đoạn đã dùng ở `DISCLOSURE_EVENT_STUDY_PREREG.md`: 2020-01→
  2022-03, 2022-03→2024-05, 2024-05→2026-07 — không đổi biên).
- **Lát < 30 sự kiện**: chỉ mô tả (điểm DCAR, N), không dùng để kết luận
  PASS/âm tính ở cấp giai đoạn đó — đúng quy tắc đã dùng ở prereg trước.
- **N(nhóm) < 30 toàn mẫu (pooled, không chỉ theo giai đoạn)**: báo cáo mô tả
  (điểm DCAR + N ở mỗi cửa sổ) rồi **đóng nhánh vì không đủ lực thống kê** —
  không hạ tiêu chí PASS xuống để "cứu" kết luận, không mở rộng cửa sổ cụm/thời
  gian để tăng N.
- **Còn lại (CI không thỏa mãn cả hai điều kiện trên)**: âm tính.

**Diễn giải H0**: áp đúng cơ chế PASS/âm tính ở trên cho nhóm H0, nhưng đọc kết
quả khác — nếu H0 âm tính (kỳ vọng): thiết kế đối chứng hoạt động đúng như dự
định. Nếu H0 PASS: **gắn cờ rủi ro thiết kế** (đối chứng khớp cặp có thể chưa
triệt tiêu hết drift, hoặc còn một confound khác chưa kiểm soát) — khi đó kết
quả PASS của H1/H2 (nếu có) phải diễn giải thận trọng hơn, không coi là bằng
chứng sạch.

## Độ nhạy lag (+1/+3/+5 ngày giao dịch)

Kế thừa nguyên cơ chế `recompute_available_at()` từ round trước: `available_at`
của mọi dòng `is_backfilled=True` (100% dữ liệu hiện tại, đã xác nhận ở round
trước) được tính lại bằng `disclosure_date + N ngày giao dịch` cho `N ∈
{1, 3, 5}`. Lag ảnh hưởng đến CẢ vị trí sự kiện `t` LẪN cửa sổ "sạch"
`[t−60, t+120]` dùng để lọc đối chứng — chạy lại toàn bộ pipeline (khớp cặp +
DCAR + bootstrap) cho cả 3 giá trị lag, báo cạnh nhau. Nếu PASS/âm tính đổi giữa
các lag → ghi rõ **"tín hiệu mong manh với giả định trễ"**, không chọn lag đẹp
nhất.

## Ràng buộc kế thừa (không lặp lại chi tiết, chỉ khóa lại)

- `available_at` point-in-time, không đổi cơ chế tính (trừ lag sensitivity ở
  trên).
- **CẤM tuyệt đối** mọi field thuộc pha RESULT hoặc tỷ lệ thực hiện — chỉ dùng
  `insider_registration`/`major_shareholder_change` REGISTRATION, đúng như
  round trước.
- Caveat panel lệch mã lớn/lâu đời (`DISCLOSURE_BASELINE.md` caveat #2) vẫn hiệu
  lực — không chuẩn hóa thêm theo tuổi niêm yết ở round này.
- 18 mã `INACTIVE_LONG` giữ trong lịch sử giá nhưng không được chọn làm đối
  chứng (điều kiện `trading_status = ACTIVE` ở trên tự động loại chúng).
- Không có hiệu chỉnh đa kiểm định chính thức cho 3 nhóm (H1/H2/H0) × 3 giai
  đoạn × 3 lag — tiêu chí 2 cửa sổ đồng thời + 2/3 giai đoạn là hàng rào thiết
  kế, không phải phép hiệu chỉnh thống kê chính thức, đúng tinh thần round
  trước.

## Những gì round này KHÔNG được làm

- Không thử định nghĩa cụm khác (vd. đổi cửa sổ 20 ngày, đổi ngưỡng số người).
- Không thử thước đo đối chứng khác (vd. đổi tercile thành ngũ phân vị, đổi số
  lượng đối chứng từ 5 sang số khác) sau khi thấy N hoặc kết quả sơ bộ.
- Không hạ tiêu chí PASS nếu N(nhóm) < 30 — đóng nhánh theo đúng quy tắc đã
  khóa, không tìm cách "cứu" bằng cách nới lỏng.
- Không chọn lag đẹp nhất làm kết luận chính nếu kết quả không đồng nhất.
- Một lần chạy. Đây là **test cuối cùng của nhánh disclosure-làm-tín-hiệu** —
  PASS thì mở nhân tố ứng viên đầu tiên cho vòng sau; âm tính hoặc N không đủ
  thì đóng nhánh vĩnh viễn cho mục đích tín hiệu (pipeline dữ liệu vẫn chạy live
  phục vụ mục đích khác — point-in-time universe, các round không liên quan).
  Không thử thêm biến thể sau khi có kết quả, bất kể kết quả là gì.
