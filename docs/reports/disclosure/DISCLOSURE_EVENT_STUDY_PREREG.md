# DISCLOSURE_EVENT_STUDY_PREREG — locked before any disclosure×price join is run

**Viết và commit TRƯỚC khi bất kỳ dòng code nào join `data/disclosure/events.parquet`
với dữ liệu giá.** Đây là lần đầu tiên hai nguồn dữ liệu này được nhìn cùng nhau —
`docs/reports/data/DISCLOSURE_PIPELINE_DESIGN.md` Round 5 và `docs/reports/data/DISCLOSURE_BASELINE.md` đều giữ nguyên
tắc "không join cho đến khi có prereg", đúng kỷ luật đã áp dụng cho
`docs/reports/scoring/SCORE_V2_DESIGN.md` trước đây. Mọi lựa chọn dưới đây chốt dựa trên bằng chứng đã
có (`docs/reports/data/DATA_BASELINE.md`, `docs/reports/data/DISCLOSURE_BASELINE.md`, `docs/reports/scoring/EVENT_DETECTION_REPORT.md`) và
cấu trúc code hiện có — không có gì trong tài liệu này được điều chỉnh sau khi nhìn
kết quả NV2, vì NV2 chưa chạy khi tài liệu này được viết. Nếu kết quả NV2 xấu: báo
cáo, dừng, bàn lại — không quay lại sửa tài liệu này rồi chạy lại.

**Nguồn trích dẫn bắt buộc**: `data/disclosure/events.parquet` (`docs/reports/data/DISCLOSURE_BASELINE.md`,
57,282 dòng, đã re-ingest 2026-07-14 với `NATURAL_KEY` mở rộng — xem
`docs/reports/data/DISCLOSURE_BASELINE.md` caveat #1 + NV0a audit) join với `data/processed/stock_features.parquet`
(`docs/reports/data/DATA_BASELINE.md`, nguồn `OFFICIAL_FEATURES_PATH` trong `src/data/dataset_config.py`,
đã rebuild từ `data/full_history_v2` — Gate #6 đã đóng, xem PUSH_REVIEW.md "Đồng bộ
full_history_v2..." vòng 3) và `data/raw/index_ohlcv/VNINDEX.parquet` (benchmark).

---

## Giả thuyết

- **H1**: `REGISTRATION` mua của nội bộ/người liên quan dự báo xác suất bùng nổ
  cao hơn base rate.
- **H2 (đối chứng dấu)**: `REGISTRATION` bán không dự báo bùng nổ (lift ≤ 1).

## Tín hiệu (định nghĩa chính xác trên `events.parquet`)

Chỉ dùng pha **REGISTRATION** (không dùng `insider_result`, không dùng
`shares_registered_or_changed`/`shares_after` sau khi thực hiện) — đây chính là
ràng buộc CẤM bên dưới, không phải một lựa chọn ngầm định.

| Tín hiệu | Điều kiện trên `events.parquet` |
|---|---|
| **S1** — mua nội bộ/liên quan | `event_type == "insider_registration"` AND `direction == "buy"` |
| **S2** — mua cổ đông lớn | `event_type == "major_shareholder_change"` AND `direction == "buy"` |
| **S3** — bán nội bộ/liên quan (đối chứng) | `event_type == "insider_registration"` AND `direction == "sell"` |

`insider_registration` đã tự gộp cả "nội bộ" và "người liên quan" theo logic parser
gốc (`src/data/disclosure_parser.py`: `is_insider = bool(person_role) or
bool(related_role)`) — không tách riêng "nội bộ" khỏi "liên quan" thành 2 tín hiệu
phụ, vì `docs/reports/data/DISCLOSURE_BASELINE.md`'s role classification (insider/major_shareholder/
related_person) là heuristic v1 áp lên bảng mô tả, không phải một cột lọc sẵn có
trên `events.parquet` — tách thêm sẽ là một lựa chọn không nằm trong 3 tín hiệu đã
chốt (S1/S2/S3), ngoài phạm vi.

**CẤM tuyệt đối** (đúng nguyên văn yêu cầu): không đọc bất kỳ trường nào thuộc pha
RESULT (`insider_result` event_type, hoặc bất kỳ field `Real*`/`execution_date`
trên một dòng `insider_registration` — dòng registration tự nó không có các field
này nên không có rủi ro rò rỉ qua schema, nhưng liệt kê rõ để chốt) và không tính
execution/registration ratio (`docs/reports/data/DISCLOSURE_BASELINE.md`'s "Execution / registration
ratio" section) làm feature hay filter dưới bất kỳ hình thức nào.

## Point-in-time: `available_at`

Đúng cột `available_at` đã có sẵn trong `events.parquet` (`src/data/disclosure_ingest.py::_compute_available_at`,
quy tắc ROUND 3): `max(disclosure_date, ingested_at)` cho dòng live, `disclosure_date
+ 1 ngày giao dịch` (placeholder) cho dòng backfilled. **Không tính lại, dùng
nguyên cột đã có.**

**Caveat quan trọng, xác nhận trước khi chạy NV2**: tính đến thời điểm viết tài
liệu này, `scripts/update_disclosure_daily.py` (nhánh live của quy tắc point-in-time)
**chưa từng được chạy theo lịch thật** (`docs/reports/data/DISCLOSURE_PIPELINE_DESIGN.md` Round 5,
NV2: "Not yet run on a real schedule this round"). Suy ra: **gần như toàn bộ (nếu
không phải 100%) 57,282 dòng trong `events.parquet` có `is_backfilled=True`**, tức
toàn bộ kết quả chính của round này phụ thuộc vào giả định lag `+1 ngày giao dịch`
— đây không phải một robustness check phụ, mà là giả định trung tâm của toàn bộ
test. Đây chính là lý do độ nhạy lag `+1/+3/+5` ở NV2 là bắt buộc, không phải
tùy chọn — nếu kết luận đổi dấu/đổi hạng giữa các lag, phải ghi rõ "tín hiệu mong
manh với giả định trễ" đúng yêu cầu gốc, không được chọn lag đẹp nhất để báo cáo.

## Cửa sổ tín hiệu ACTIVE

Cố định = **20 ngày giao dịch** kể từ `available_at`, tính theo lịch giao dịch
thật của VNINDEX (`data/raw/index_ohlcv/VNINDEX.parquet`'s `date` column, đã loại
trừ `config/vn_market_holidays.csv`) — **không dùng lịch dương lịch (calendar
days)**. Với một mã và một sự kiện tín hiệu tại `available_at = t0`, mã đó được
gắn `signal_active(S, symbol, day) = True` cho mọi ngày giao dịch `day` trong
`[t0, t0 + 19 ngày giao dịch]` (20 ngày bao gồm cả `t0`).

Nếu một mã có nhiều sự kiện cùng tín hiệu chồng cửa sổ nhau (đăng ký mới trong
lúc cửa sổ cũ chưa hết): cửa sổ `ACTIVE` là **hợp (union)** của mọi cửa sổ đang mở
— một ngày chỉ cần rơi vào ít nhất một cửa sổ là được tính active, không nhân đôi
ngày đó trong panel (mỗi (symbol, day) chỉ xuất hiện một lần trong panel).

## Rổ đủ điều kiện (eligible universe), theo ngày

Panel ở cấp `(symbol, trading_day)`. Một cặp `(symbol, day)` được đưa vào panel
chỉ khi cả hai điều kiện sau đúng tại `day`:

1. **Thanh khoản**: `value_ma20(symbol, day) >= 3,000,000,000` VND, đọc từ
   `data/processed/stock_features.parquet` (`OFFICIAL_FEATURES_PATH`) — đúng
   ngưỡng 3 tỷ đã dùng cho factor re-test trong session này (commit `b182091`),
   không phải ngưỡng mới.
2. **`trading_status`**: mã không nằm trong `excluded_symbols_by_status()`
   (tức không phải `INACTIVE_LONG` theo `src/validation/trading_status.py`).

**Giới hạn đã biết, chốt trước khi chạy**: `trading_status.parquet` là bảng
point-in-time nhưng chỉ có lịch sử thay đổi trạng thái **từ 2026-07-13 trở đi**
(lần đầu bảng được ghi — `PUSH_REVIEW.md` GĐ2 NV3). Với các ngày trước
2026-07-13 (tức gần như toàn bộ cửa sổ event-study 2020–2026),
`status_as_of(day)` trả về rỗng — **không dùng được cho tái lập point-in-time
thật**. Quyết định chốt: dùng `latest_trading_status()` (snapshot HIỆN TẠI, tại
thời điểm chạy NV2) áp dụng đồng nhất cho MỌI ngày lịch sử, không phân biệt quá
khứ/hiện tại. Hệ quả đã biết: một mã `INACTIVE_LONG` hôm nay bị loại khỏi rổ đủ
điều kiện cho **toàn bộ lịch sử của nó**, kể cả những năm nó còn giao dịch bình
thường — thu hẹp N ở giai đoạn cũ hơn mức lý tưởng, nhưng **không tạo look-ahead
bias theo hướng lạc quan** (loại trừ một mã không tương quan với việc mã đó có
`event=1` hay không tại các ngày còn active trong quá khứ của nó) — cùng bản chất
với caveat survivorship-bias đã ghi nhận ở `docs/reports/data/DATA_BASELINE.md`/`docs/reports/data/DISCLOSURE_BASELINE.md`,
không phải một nguồn thiên lệch mới.

## Nhãn sự kiện "bùng nổ" (event label)

Tái dùng nguyên định nghĩa đã pre-register và chạy trong `docs/reports/scoring/EVENT_DETECTION_REPORT.md`
(Task 1), không phát minh định nghĩa mới:

```
event(symbol, day) = 1  if  excess_return_60d_forward(symbol, day) >= +25%
```

`excess_return_60d_forward(symbol, day)` = lợi nhuận đơn (simple return) của mã từ
`day` đến `day + 60 ngày giao dịch` (điểm-đến-điểm, KHÔNG phải max trong cửa sổ),
trừ đi lợi nhuận đơn của VNINDEX cùng cửa sổ — hiệu số đơn giản, không điều chỉnh
beta (đúng convention `docs/reports/scoring/EVENT_DETECTION_REPORT.md` đã dùng). **Đây là cột forward
tính riêng cho round này** — khác với `excess_return_20d`/`excess_return_60d` sẵn
có trong `final_watchlist.py`'s pipeline, vốn là lợi nhuận trailing (nhìn về quá
khứ từ ngày hiện tại) dùng cho màn hình lọc RS, không phải nhãn dự báo. Không được
nhầm lẫn hai cột này khi viết code NV2.

Nếu `day + 60 ngày giao dịch` vượt quá dữ liệu giá hiện có (mã hết dữ liệu, hoặc
gần cuối chuỗi thời gian) → `event = NaN`, loại khỏi panel test chính (không tính
là 0).

## Test chính — lift bùng nổ

Với mỗi tín hiệu S ∈ {S1, S2, S3}, tính trên panel `(symbol, day)` đủ điều kiện:

```
P(event=1 | signal_active(S)=True)   vs.   base_rate = P(event=1)  (toàn bộ panel đủ điều kiện, không điều kiện tín hiệu)
lift(S) = P(event=1 | signal_active(S)=True) / base_rate
```

`base_rate` tính pooled trên toàn bộ panel (mọi ngày, mọi mã đủ điều kiện, không
phân biệt active hay không) — đúng convention "base rate" của
`docs/reports/scoring/EVENT_DETECTION_REPORT.md` (4.20% overall), không phải base rate riêng theo từng
ngày rồi lấy trung bình.

**Block bootstrap cho CI**: đơn vị resample là **khối 60 ngày giao dịch liên tiếp**
của panel (theo trục thời gian, không phải resample từng dòng `(symbol,day)` độc
lập — vì cửa sổ tín hiệu 20 ngày và cửa sổ nhãn 60 ngày đều tạo tự tương quan theo
thời gian giữa các dòng liền kề). Với chuỗi ngày giao dịch đủ điều kiện có độ dài
N, mỗi lần bootstrap: chọn ngẫu nhiên có hoàn lại `ceil(N/60)` khối 60-ngày (mỗi
khối = toàn bộ panel `(symbol,day)` trong 60 ngày giao dịch liên tiếp đó), nối lại
thành một panel tổng hợp cùng độ dài xấp xỉ N, tính lại `lift(S)` trên panel tổng
hợp. Lặp **≥ 1,000 lần** (đúng yêu cầu, không làm tròn xuống). CI 95% = phân vị
2.5/97.5 của phân phối `lift` bootstrap. `random_state` cố định (dùng `42`, đúng
convention seed đã lặp lại nhiều lần trong session này — `docs/reports/scoring/SCORE_V2_DESIGN.md`,
`monte_carlo`), không thử nhiều seed rồi chọn seed đẹp.

## Lát cắt: 3 giai đoạn thời gian × 2 nhóm thanh khoản

**3 giai đoạn**: tái dùng nguyên đường biên đã có trong `docs/reports/scoring/EVENT_DETECTION_REPORT.md`
(không tự chọn biên mới): Giai đoạn 1 = 2020-01 → 2022-03, Giai đoạn 2 = 2022-03 →
2024-05, Giai đoạn 3 = 2024-05 → 2026-07 (ngày cuối = ngày chạy NV2 thực tế).

**Rủi ro đã biết trước, không phải bất ngờ sau khi chạy**: `docs/reports/scoring/EVENT_DETECTION_REPORT.md`
đã ghi nhận Giai đoạn 1 gần như không có ngày nào đủ điều kiện thanh khoản đủ dùng
(median 2-5 mã đủ điều kiện/ngày ở ngưỡng 10 tỷ cũ) — ở ngưỡng 3 tỷ của round này
tình hình có thể đỡ hơn nhưng chưa được kiểm chứng trước. Nếu Giai đoạn 1 có < 30
sự kiện `event=1` trong panel đủ điều kiện, đúng quy tắc đã chốt: **lát đó chỉ mô
tả (báo số N, base rate, lift điểm), không dùng để kết luận PASS/ỨNG VIÊN/âm tính**
— tiêu chí 3 giai đoạn ở dưới tự động chỉ xét trên các giai đoạn có ≥ 30 sự kiện.

**2 nhóm thanh khoản**: chia đôi theo trung vị (median split) `value_ma20` **trong
đúng panel đủ điều kiện của từng ngày** (không phải trung vị toàn universe) — mỗi
ngày, các mã đủ điều kiện hôm đó được xếp vào "thanh khoản cao" (≥ trung vị ngày
đó) hoặc "thanh khoản thấp" (< trung vị ngày đó, nhưng vẫn ≥ 3 tỷ do đã qua gate
đủ điều kiện). Median split theo ngày, không phải một ngưỡng VND cố định thứ hai,
để tránh nhóm "thấp" co lại gần rỗng ở giai đoạn universe còn ít mã thanh khoản.

## Tiêu chí đánh giá (khóa trước, áp dụng cho S1 và S2 — kiểm định H1)

- **PASS** = CI dưới của `lift` (pooled, toàn mẫu) > 1.5 **VÀ** lift điểm > 1 ở
  **cả 3** giai đoạn đủ điều kiện kết luận (≥30 sự kiện).
- **ỨNG VIÊN** = CI dưới > 1.0 **VÀ** lift điểm > 1 ở **≥ 2/3** giai đoạn đủ điều
  kiện kết luận.
- **Còn lại** = âm tính.

Nếu chỉ có 1 hoặc 0 giai đoạn đủ ≥30 sự kiện để kết luận (rủi ro Giai đoạn 1 nêu
trên xảy ra ở mức nặng), PASS là bất khả thi về mặt cấu trúc — báo cáo đúng như
vậy (đúng tinh thần `docs/reports/scoring/EVENT_DETECTION_REPORT.md`'s Period-1 gap), không hạ tiêu
chí xuống 2 giai đoạn hay 1 giai đoạn để "cứu" một kết luận.

## Tiêu chí cho S3 (đối chứng dấu — kiểm định H2)

**Không dùng lại nguyên khối PASS/ỨNG VIÊN ở trên cho S3** (khối đó được thiết kế
cho một tín hiệu kỳ vọng lift > 1; áp thẳng vào S3 sẽ hiểu sai bản chất phép thử
đối chứng). Thay vào đó, tính **cùng một pipeline lift + CI + 3-giai-đoạn hệt
S1/S2** (không có logic riêng cho S3 trong code — khóa trước để tránh tự tạo lối
thoát khi nhìn thấy số), rồi diễn giải theo H2:

- **H2 được xác nhận** nếu CI trên của `lift(S3)` (pooled) ≤ 1.5 (tức không có
  bằng chứng S3 mạnh ngang một tín hiệu PASS) — dấu hiệu tốt nhất là CI chứa 1.0
  hoặc lift điểm ≤ 1.
- **H2 bị thách thức** nếu `lift(S3)` cũng đạt mức PASS hoặc ỨNG VIÊN như S1/S2 —
  khi đó câu chuyện "đăng ký mua mang thông tin, đăng ký bán thì không" không còn
  đứng vững; nhiều khả năng hơn là một hiệu ứng chung "có giao dịch nội bộ được
  công bố" (bất kể chiều) tương quan với biến động giá sắp tới, không phải riêng
  tín hiệu mua.

## Test phụ — CAR (Cumulative Abnormal Return)

Với mỗi tín hiệu S ∈ {S1, S2, S3}: `CAR_h(symbol, event) = ` lợi nhuận đơn cộng
dồn của mã trừ lợi nhuận đơn cộng dồn của VNINDEX, từ `available_at` đến
`available_at + h` ngày giao dịch, với `h ∈ {20, 60, 120}`.

**Gộp cụm**: nếu cùng một mã có ≥ 2 sự kiện cùng tín hiệu S cách nhau **< 20 ngày
giao dịch**, gộp thành một cụm và chỉ lấy sự kiện **đầu tiên** của cụm làm điểm
sự kiện cho CAR (tránh đếm trùng biến động giá của cùng một đợt tích lũy được báo
cáo nhiều lần). Việc gộp cụm áp dụng riêng theo từng tín hiệu S (một mã có thể có
cụm S1 và cụm S3 độc lập nhau, không gộp chéo giữa các tín hiệu).

**CI**: cùng cơ chế block bootstrap theo lịch (khối theo ngày giao dịch, không
theo sự kiện) như test chính — resample khối thời gian, tính lại `mean(CAR_h)`
trên các sự kiện (đã gộp cụm) rơi vào mỗi lần resample, ≥1,000 lần, phân vị
2.5/97.5.

**Kỳ vọng đăng ký trước (không phải kết quả)**: `CAR(S1) > 0`, `CAR(S3) <= 0` —
nếu ngược lại, báo cáo trung thực, không diễn giải lại để khớp kỳ vọng.

## Độ nhạy lag backfill (+1 / +3 / +5 ngày giao dịch)

Chạy lại toàn bộ test chính (không chạy lại CAR — ngoài phạm vi yêu cầu gốc, chỉ
nói "backfill chạy độ nhạy lag" cho test chính) với `available_at` của các dòng
`is_backfilled=True` được tính lại bằng `disclosure_date + 3 ngày giao dịch` và
`disclosure_date + 5 ngày giao dịch` thay cho placeholder `+1` mặc định — dòng
`is_backfilled=False` (live, nếu có) giữ nguyên `available_at` đã tính (không bị
lag giả định này chi phối). Báo cáo lift + CI của cả 3 lag (`+1`, `+3`, `+5`) cạnh
nhau trong bảng, cho từng tín hiệu × từng giai đoạn. Nếu PASS/ỨNG VIÊN/âm tính đổi
hạng giữa các lag → ghi rõ nguyên văn **"tín hiệu mong manh với giả định trễ"**
trong báo cáo, không chọn lag cho kết quả đẹp nhất làm kết luận chính.

---

## Caveat ghi sẵn (trước khi chạy, không phải hậu kiểm)

1. **Survivorship bias** (kế thừa `docs/reports/data/DATA_BASELINE.md` caveat #2 +
   `docs/reports/data/DISCLOSURE_BASELINE.md` caveat #2): universe là "niêm yết hôm nay, chiếu
   ngược". Một tín hiệu có lift cao có thể lạc quan giả — công ty biến mất khỏi
   universe hôm nay (hủy niêm yết/sáp nhập/đình chỉ) không được tính vào cả tử số
   lẫn mẫu số của lift, theo cả hai hướng, nên hướng thiên lệch cụ thể không suy
   diễn được một chiều — chỉ ghi nhận là giới hạn, không định lượng thêm ở round
   này.
2. **Panel disclosure lệch mã lớn/lâu đời** (`docs/reports/data/DISCLOSURE_BASELINE.md` caveat #2):
   độ sâu lịch sử disclosure tương quan với tuổi niêm yết — không chuẩn hóa theo
   period × nhóm mã trong test chính (test đã tự chia theo giai đoạn thời gian,
   nhưng KHÔNG chia theo tuổi niêm yết/vốn hóa) — nếu lift dương chủ yếu đến từ
   nhóm mã lớn/lâu đời, kết luận không tự động suy rộng ra nhóm mã trẻ/nhỏ.
3. **18 mã INACTIVE_LONG**: giữ trong lịch sử giá (không xóa) nhưng loại khỏi rổ
   đủ điều kiện ở MỌI ngày lịch sử theo quyết định chốt ở mục "Rổ đủ điều kiện"
   trên — không phải một caveat mới, chỉ nhắc lại hệ quả của lựa chọn đã khóa.
4. **`available_at` cho hầu hết dữ liệu phụ thuộc giả định lag +1 ngày giao dịch**
   (mục "Point-in-time" trên) — độ nhạy lag +1/+3/+5 là bắt buộc để diễn giải kết
   quả đúng, không phải optional robustness.
5. **Không có hiệu chỉnh đa kiểm định chính thức** (Bonferroni/FDR) cho 3 tín hiệu
   × 3 giai đoạn × 2 nhóm thanh khoản × 3 lag = nhiều phép so sánh. Tiêu chí PASS/
   ỨNG VIÊN 3 bậc đã cố ý đặt thanh cao (CI dưới > 1.5, đồng dấu 3/3 giai đoạn) để
   giảm rủi ro false positive mà không cần hiệu chỉnh formal — nhưng đây là một
   lựa chọn thiết kế, không phải một phép hiệu chỉnh thống kê thật, cần nói rõ
   trong report.

## Những gì NV2 KHÔNG được làm

- Không đổi ngưỡng thanh khoản 3 tỷ, cửa sổ 20/60/120 ngày, hay tiêu chí PASS/
  ỨNG VIÊN sau khi nhìn kết quả sơ bộ.
- Không thử thêm vai trò tín hiệu khác ngoài S1/S2/S3 (ví dụ tách riêng "nội bộ"
  khỏi "người liên quan", hay thêm `insider_result` làm tín hiệu) trong round này.
- Không dùng bất kỳ field nào thuộc pha RESULT hoặc tỷ lệ thực hiện.
- Không chọn lag (+1/+3/+5) "đẹp nhất" làm kết luận chính nếu kết quả không đồng
  nhất giữa các lag.
- Một lần chạy. Kết quả xấu → báo cáo, dừng, bàn lại (đúng ràng buộc gốc).
