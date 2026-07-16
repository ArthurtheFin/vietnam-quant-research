# CẨM NANG VẬN HÀNH HẰNG NGÀY

**Dành cho**: chủ dự án — người dùng cuối, không cần đọc code. Nếu bạn muốn
hiểu sâu hơn một kết luận nào đó, mỗi mục dưới đây đều trích dẫn đúng report
gốc để bạn (hoặc một phiên làm việc code sau này) tra lại.

**Cập nhật lần cuối**: 2026-07-16, cùng đợt với `PROJECT_STATE.md`. Nếu tài
liệu này và report gốc lệch nhau, tin report gốc.

---

> ## 🔒 NGUYÊN TẮC XUYÊN SUỐT — đọc trước khi làm bất cứ điều gì khác
>
> 1. **Hệ thống này đang ở trạng thái NGHIÊN CỨU/SHADOW.** Chưa có thành phần
>    nào — kể cả `alpha_score` v2, thành phần có bằng chứng thống kê tốt nhất
>    đã tìm được — đủ bằng chứng để làm tín hiệu mua/bán vốn thật. Deflated
>    Sharpe Ratio của v2 chỉ **0.0083** (0.83%) sau khi tính đến toàn bộ lịch
>    sử thử nghiệm của dự án (560 lần thử), và khoảng tin cậy bootstrap cho cả
>    CAGR lẫn Sharpe của nó đều **chứa số 0** — nghĩa là không thể bác bỏ khả
>    năng "hiệu suất thật = 0, mọi thứ nhìn thấy chỉ là may mắn". Nguồn:
>    `ROBUSTNESS_REPORT.md` mục 5, `SCORE_V2_REPORT.md` mục "Trạng thái sau
>    GĐ5". Nếu hiện có bất kỳ khoản vốn thật nào đang theo watchlist/score của
>    dự án này: khuyến nghị chính thức là đưa về 0, hoặc nếu không thể ngừng
>    ngay, giới hạn ở mức "học phí" — số tiền mà mất trắng không gây tổn hại
>    tài chính thật.
> 2. **`final_watchlist` (client_ready/trading/research) là danh sách SÀNG
>    LỌC, không phải danh sách khuyến nghị mua.** Nó chỉ giữ lại các mã đủ
>    thanh khoản, dữ liệu tươi, đang thật sự giao dịch. **Thứ tự trong file là
>    xếp theo thanh khoản (`value_ma20`, giảm dần), KHÔNG phải theo độ hấp
>    dẫn đầu tư.** Mã đứng hạng 1 là mã thanh khoản cao nhất trong rổ, không
>    phải mã "tốt nhất". Đây là quyết định có chủ đích (`WATCHLIST_VALIDATION_REPORT.md`
>    — "Nhánh C"), không phải một tính năng chưa làm xong.
> 3. **Mọi quyết định đầu tư — chọn mã nào, mua bao nhiêu, lúc nào — là của
>    bạn.** Hệ thống chỉ thu hẹp vũ trụ 500 mã xuống một danh sách sạch, đủ
>    điều kiện giao dịch, và cung cấp dữ kiện thô (thanh khoản, biến động,
>    sự kiện disclosure). Nó không định giá, không đọc tin tức, không chọn
>    thời điểm, và không sinh ra ý tưởng đầu tư.

---

## 1. Quy trình buổi sáng (5-10 phút)

Làm theo thứ tự. Nếu một bước phát hiện vấn đề, dừng lại và sang mục 5 (Xử lý
sự cố) trước khi dùng bất kỳ dữ liệu nào của hôm đó.

### Bước 1 — daily_run đêm qua đã chạy chưa?

Mở file `logs/daily_run.log`, xem **dòng cuối cùng bắt đầu bằng `SUMMARY`**:

```
[2026-07-16 20:24:59] SUMMARY: 4/4 steps OK
```

- **Phải là `4/4 steps OK`** và **mốc thời gian phải là tối ngày giao dịch
  gần nhất** (ví dụ hôm nay là thứ Ba thì mốc phải là tối thứ Hai, không phải
  vài ngày trước).
- Nếu dòng cuối có chữ `FAIL` (bọc trong `######` cho dễ thấy) → xem mục 5.
- Nếu không tìm thấy dòng `SUMMARY` nào gần đây → daily_run không chạy đêm
  qua → xem mục 5 ("LaunchAgent không chạy").

### Bước 2 — watchlist có tươi không?

Mở `data/output/pipeline_metadata.json`, tìm 2 trường:

- `"freshness_status"` — **phải là `"OK"`**. Nếu là `"ERROR"`, dữ liệu KHÔNG
  nên dùng cho hôm nay.
- `"lineage"` → `"lineage_generated_at"` — phải là ngày/giờ gần với lúc
  daily_run chạy đêm qua (mục 1). Đây là dấu thời gian THẬT của lần sinh dữ
  liệu, không phải ngày trên file.

Nếu cả hai đều ổn: `data/signals/final_watchlist.csv` (và các bản trong
`data/output/client_ready_watchlist.csv`/`trading_watchlist.csv`) **được
dùng cho hôm nay**. Nếu không: đó là dữ liệu **cũ, KHÔNG dùng** — chạy lại
`bash scripts/daily_run.sh` (mục 5) trước khi xem watchlist.

### Bước 3 — liếc shadow log

Mở `data/signals/alpha_score_shadow_log.parquet` (hoặc hỏi ai đó chạy nhanh
2 dòng Python — xem mục 4 để tự kiểm tra định kỳ), xác nhận **có mốc ngày
hôm qua/hôm nay**. Chuỗi liên tục không ngắt quãng chính là "bằng chứng"
đang được tích lũy cho phiên xem lại v2 (mục 6) — ngắt quãng vài ngày không
nguy hiểm ngay, nhưng ngắt quãng kéo dài làm lùi ngày phiên tòa và làm yếu
kết luận cuối cùng. Nếu ngắt quãng: xử lý ngay theo mục 5, đừng để dồn.

---

## 2. Đọc hiểu từng artifact

### 2.1. `final_watchlist` (`data/signals/final_watchlist.csv`, cũng chính là
`data/output/client_ready_watchlist.csv`/`trading_watchlist.csv`/`research_candidates.csv`)

**Nguồn**: `src/screening/final_watchlist.py`. Nhãn "Nhánh C" —
`WATCHLIST_VALIDATION_REPORT.md`.

| Cột | Ý nghĩa | Có bằng chứng dùng để xếp hạng không? |
|---|---|---|
| `rank` | Thứ hạng — **theo `value_ma20` giảm dần**, không phải theo điểm số | — (đây chính là cơ chế xếp hạng hiện tại) |
| `symbol` | Mã cổ phiếu | — |
| `value_ma20` | Giá trị giao dịch bình quân 20 ngày (VND) — **đây là cột quyết định thứ hạng** | Đây là thước đo vận hành (thanh khoản), không phải một nhân tố alpha đã kiểm định |
| `candidate_tier` | `Client Ready` / `Trading Watchlist` / `Research Candidate` / `Data Review` — xem giải thích tier bên dưới | — |
| `final_score`, `base_final_score` | Điểm tổng hợp 7 thành phần cũ — **CHỈ ĐỂ THAM KHẢO/NGHIÊN CỨU, KHÔNG điều khiển thứ hạng hay việc mã có vào watchlist hay không** kể từ Nhánh C | **Không** — composite này đã kiểm định và KHÔNG đạt tiêu chí (`WATCHLIST_VALIDATION_REPORT.md` mục 1, 4) |
| `trend_score`, `momentum_score`, `relative_strength_score`, `volume_score` | Thành phần con của điểm cũ | **Không** — t-stat đều yếu (`\|t_NW\|<1`), `momentum_score`≡`relative_strength_score` về mặt toán học (một sự dư thừa đã phát hiện, chưa sửa) |
| `liquidity_score` | Thành phần con cũ (thưởng `value_ma20` cao) | **Không — chiều SAI**: t_NW=−4.19, đã gỡ khỏi mọi tính toán điểm tổng, chỉ còn hiển thị |
| `risk_score` | Thành phần con đo biến động thấp | Có bằng chứng thống kê (t_NW=+4.72) nhưng **trùng lặp với `alpha_score` v2** (tương quan +0.822) — không phải nguồn thông tin mới, đã đóng hồ sơ (`ROBUSTNESS_REPORT.md` mục 3) |
| `signal_score` | Thành phần con dựa trên `meta_ranking.parquet` | **Không tính được** — file nguồn hóa ra là ảnh chụp một thời điểm, không phải chuỗi lịch sử (`WATCHLIST_VALIDATION_REPORT.md` mục 2, phát hiện #4) |
| `reason` | Câu giải thích ngắn — **luôn có tiền tố cảnh báo** `[Không xếp hạng alpha, chỉ sắp theo thanh khoản...]` | — |
| `eligibility_status`, `eligibility_reason` | Mã có qua được sàng lọc cơ bản không (thanh khoản, dữ liệu tươi, đang giao dịch) | — |
| `cashflow_data_status`, `confirmation_status`, `cashflow_verification` | Dữ liệu dòng tiền/xác nhận có sẵn sàng cùng ngày không — ảnh hưởng việc mã có được xếp `Client Ready` hay bị hạ xuống `Trading Watchlist` | — |
| `warning`, `exclusion_reason` | Cảnh báo dữ liệu (stale, thiếu backtest, thị trường yếu...) | — |
| `analysis_as_of`, `data_age_days` | Ngày dữ liệu được tính — dùng để xác nhận độ tươi (mục 1 Bước 2) | — |

**3 tier khác nhau thế nào**:
- **`Client Ready`**: qua đủ mọi gate chất lượng dữ liệu (eligibility, cashflow
  xác nhận cùng ngày, không cảnh báo) — **không có nghĩa "chất lượng đầu tư
  cao hơn"**, chỉ có nghĩa "dữ liệu về mã này sạch và mới nhất".
- **`Trading Watchlist`**: qua sàng lọc cơ bản nhưng thiếu một xác nhận nào
  đó (ví dụ cashflow board chưa build kịp hôm đó) — vẫn là mã hợp lệ, chỉ
  thiếu một lớp xác nhận phụ.
- **`Research Candidate`**: qua sàng lọc tối thiểu nhưng nằm ngoài giới hạn
  số lượng của 2 tier trên (mặc định 10 + 20 mã).
- **`Data Review`**: bị loại — xem `eligibility_reason`.

**⚠️ NHỮNG ĐIỀU KHÔNG ĐƯỢC SUY RA TỪ FILE NÀY**:
- **Mã đứng đầu ≠ mã đáng mua nhất.** Nó chỉ là mã thanh khoản nhất trong rổ.
- **`Client Ready` ≠ "hệ thống khuyến nghị mua".** Chỉ là "dữ liệu sạch nhất".
- **`final_score`/`risk_score` cao ≠ nên mua.** Các cột này chỉ để tham
  khảo/nghiên cứu, không phải căn cứ ra quyết định (xem bảng trên).
- **Có mặt trong watchlist ≠ đã được kiểm tra định giá, tin tức, hay rủi ro
  đặc thù của doanh nghiệp.** Hệ thống không làm những việc đó.

### 2.2. `reports/daily_alpha_ranking.csv` + shadow log (`alpha_score_shadow_log.parquet`)

**Đây là dữ liệu THÍ NGHIỆM đang tích lũy — đọc để theo dõi SỨC KHỎE của
thí nghiệm, KHÔNG đọc để chọn mã.** `alpha_score` (v2) có bằng chứng xếp
hạng tốt nhất trong toàn dự án, nhưng như đã nói ở khung nguyên tắc đầu
trang: bằng chứng xếp hạng tốt ≠ bằng chứng chiến lược sinh lời. Cách dùng
đúng của 2 file này: kiểm tra chuỗi có liên tục không (mục 1 Bước 3, mục 4),
không dùng điểm số trong đó để quyết định mua mã nào.

`alpha_score_shadow_v1` chạy song song chỉ để so sánh (composite cũ, đã bị
thay thế, không dùng ở đâu khác) — có mặt trong shadow log để tính điều kiện
xem lại #3 (mục 6).

### 2.3. `trading_status` + dữ liệu disclosure

**`trading_status`** (`data/full_history_v2/trading_status.parquet`,
`ACTIVE`/`STALE_SHORT`/`INACTIVE_LONG`): dùng để loại các mã đã ngừng giao
dịch thật sự (`INACTIVE_LONG`) khỏi rổ sàng lọc — đây là lý do mã "chết"
không xuất hiện trong watchlist dù còn trong universe 500 mã gốc.

**Dữ liệu disclosure** (đăng ký/kết quả giao dịch nội bộ, cổ đông lớn —
`data/disclosure/events.parquet`): dùng làm **ngữ cảnh** khi bạn tự nghiên
cứu một mã cụ thể (ai đăng ký mua/bán, khi nào, bao nhiêu) — **KHÔNG dùng
làm tín hiệu dự báo giá tự động**. Đã kiểm định 3 vòng pre-register riêng
biệt (test chính, khớp đối chứng survivorship bias, đối chứng khớp cặp cho
cụm/gia đình) — **kết quả âm tính ở cả 3 vòng**, không nhân tố disclosure
nào đạt ngưỡng ứng viên. Nguồn: `DISCLOSURE_EVENT_STUDY_REPORT.md`,
`DISCLOSURE_PREREG_2_REPORT.md`. Dữ liệu vẫn được cập nhật hằng ngày vì có
giá trị khác (dấu hiệu sớm cho hủy niêm yết — mục 6/Gate #3), không phải vì
nhánh tín hiệu này còn mở.

### 2.4. Notebook nào còn dùng được

Hầu hết notebook trong `notebooks/` (trừ thư mục `00_archive/`, đã đóng
băng) vẫn phản ánh đúng pipeline hiện tại. **3 notebook sau đã bị gắn ô cảnh
báo "⚠️ OUTDATED" ngay ở đầu — đọc ô cảnh báo đó trước khi tin bất kỳ số
liệu nào bên trong, đừng chạy lại rồi dùng kết quả như thể còn hợp lệ**:
- `notebooks/03_alpha_signals/12_meta_ranking_optimization.ipynb`
- `notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb`
- `notebooks/04_watchlist_portfolio/20_portfolio_backtester.ipynb`

Nếu một notebook KHÔNG có ô cảnh báo này ở đầu, nó chưa bị phát hiện lệch
với code hiện tại — nhưng "chưa bị phát hiện" không phải là "đã xác nhận
đúng 100%"; nếu nghi ngờ, đối chiếu với report tương ứng ở mục "Bản đồ hồ
sơ" trong `PROJECT_STATE.md`.

---

## 3. Khung ra quyết định đầu tư

**Nhắc lại**: hệ thống không chọn mã thay bạn. Khung dưới đây giúp bạn dùng
đúng cách những gì hệ thống CÓ cung cấp, và biết rõ ranh giới ở đâu.

### Bước 1 — Ý tưởng mã X đến từ đâu?

Từ **bạn** — báo chí, phân tích riêng, gợi ý từ người khác, hoặc đơn giản là
duyệt qua watchlist thấy quen. Ở trạng thái hiện tại, hệ thống không sinh ra
ý tưởng đầu tư nào cả — nó chỉ xử lý ý tưởng bạn đã có.

### Bước 2 — X có qua được sàng lọc của hệ thống không?

- X có trong `client_ready_watchlist`/`trading_watchlist`/`research_candidates`
  không? Nếu có trong `data_review` hoặc không xuất hiện đâu cả → xem
  `eligibility_reason`/`trading_status` để biết vì sao (thanh khoản quá thấp,
  dữ liệu quá cũ, hoặc đã ngừng giao dịch thật sự).
- `trading_status` của X có phải `ACTIVE` không? (kiểm tra qua
  `data/full_history_v2/trading_status.parquet`, hoặc suy ra từ việc X có
  mặt trong watchlist hay không — watchlist đã tự loại `INACTIVE_LONG`).
- Thanh khoản (`value_ma20`) của X có đủ cho quy mô lệnh bạn định đặt không?
  **Quy tắc ngón tay cái**: không đặt một lệnh chiếm quá một phần nhỏ (ví dụ
  dưới 5-10%) của `value_ma20` bình quân ngày, để tránh tự đẩy giá khi vào/ra
  lệnh. Đây là kinh nghiệm vận hành chung, không phải một con số hệ thống đã
  kiểm định riêng cho dự án này.

### Bước 3 — Dữ kiện hệ thống cung cấp về X

- **Vị trí thanh khoản**: `value_ma20`, `rank` trong watchlist (nhắc lại:
  rank chỉ phản ánh thanh khoản, không phản ánh độ hấp dẫn).
- **`realized_vol_20d` (qua `risk_score`/`liquidity_score`... trong file
  điểm)**: đây là **nhân tố duy nhất trong toàn dự án có bằng chứng xếp hạng
  ổn định qua thời gian** (t_NW ≈ −5.48, sống sót qua hiệu chỉnh đa kiểm định
  FDR — `ROBUSTNESS_REPORT.md` mục 2, 4) — mã biến động THẤP có xu hướng
  xếp hạng tốt hơn về mặt thống kê. **NHƯNG chưa có bằng chứng đây là một
  CHIẾN LƯỢC sinh lời đáng cược vốn thật** (DSR=0.0083, CI bootstrap chứa 0
  — xem khung nguyên tắc đầu trang). Dùng con số này như một dữ kiện tham
  khảo về tính chất mã, không phải một khuyến nghị mua/bán.
- **Sự kiện disclosure gần đây của X** (đăng ký mua/bán nội bộ, cổ đông
  lớn): chỉ đọc như **ngữ cảnh** ("có ai đó liên quan đang giao dịch") —
  không đọc như tín hiệu dự báo giá (đã kiểm định âm tính, mục 2.3).

### Bước 4 — Những gì hệ thống KHÔNG trả lời được

Hệ thống **không** định giá X (P/E, DCF, so sánh ngành...), **không** đọc
tin tức/sự kiện doanh nghiệp, và **không** gợi ý thời điểm vào/ra lệnh. Cả
ba việc này là của bạn.

**Quyết định mua/bán và khối lượng là của bạn.** Khi tự đánh giá một backtest
hay con số lợi nhuận long-only bất kỳ (của dự án này hoặc nơi khác dùng
universe tương tự "500 mã đang niêm yết hôm nay"), **luôn trừ thêm mức sàn
survivorship bias trước khi tin phần "vượt trội" còn lại**:

| Cửa sổ nắm giữ | Trừ thêm |
|---|---|
| ~20 ngày giao dịch | 0.4% |
| ~60 ngày giao dịch | 1.2% |
| ~120 ngày giao dịch | 2.9% |

(`SURVIVORSHIP_BIAS_ESTIMATE.md` — universe hiện tại chỉ gồm mã còn niêm yết
hôm nay, nên tự nó đã có một mức "vượt trội ảo" không liên quan gì đến chọn
mã giỏi.)

### ✅ Checklist 5 câu hỏi tự vấn trước khi đặt lệnh

1. Ý tưởng này của tôi hay của hệ thống? (Phải là của tôi — xem Bước 1.)
2. Tôi có đang nhầm "đứng đầu watchlist" với "đáng mua nhất" không? (Không
   nên — xem mục 2.1.)
3. Tôi có đang coi `final_score`/`risk_score`/thứ hạng như một khuyến nghị
   mua không? (Không nên — chưa có bằng chứng chiến lược, xem khung nguyên
   tắc.)
4. Tôi đã tự định giá/đọc tin tức/chọn thời điểm chưa, hay đang mong hệ
   thống làm việc đó? (Hệ thống không làm — Bước 4.)
5. Khối lượng lệnh của tôi có phù hợp với thanh khoản thật của mã (Bước 2)
   không, và tôi đã trừ sàn survivorship khi đánh giá bất kỳ con số backtest
   nào chưa?

---

## 4. Nhịp tuần/tháng

- **2-4 tuần/lần — liếc tính liên tục của shadow log**: mở
  `data/signals/alpha_score_shadow_log.parquet`, xác nhận không có khoảng
  trống dài (nhiều ngày liên tiếp không có dòng mới). Cách nhanh nhất:
  ```
  python3 -c "import pandas as pd; d=pd.read_parquet('data/signals/alpha_score_shadow_log.parquet'); print(sorted(d['date'].unique())[-10:])"
  ```
  Ngắt quãng kéo dài → làm lùi ngày phiên tòa v2 (mục 6), xử lý theo mục 5.
- **Định kỳ (gợi ý hằng tuần hoặc trước khi làm gì lớn) — bundle backup**:
  đảm bảo thư mục dự án được sao lưu định kỳ (Time Machine hoặc tương đương)
  — đây là dữ liệu tài chính + lịch sử nghiên cứu, không có bản sao ở nơi
  khác ngoài git log local (dự án chỉ commit local, không push — `CLAUDE.md`
  mục 2).
- **Ngày 2027-01-16 — "phiên tòa" v2**: đây là ngày điều kiện xem lại #1 của
  `alpha_score` v2 đến hạn (mục 6). Mở `PROJECT_STATE.md` mục 3, chạy điều
  kiện xem lại #4 (tính Sharpe out-of-sample thuần từ shadow log, so với
  khoảng tin cậy bootstrap `[−0.59, +1.32]` đã có) — nếu không tự làm được,
  đây là lúc nhờ một phiên làm việc code mới.

---

## 5. Xử lý sự cố

| Triệu chứng | Nguyên nhân khả dĩ | Lệnh chạy tay |
|---|---|---|
| `logs/daily_run.log` có dòng `###### FAIL ######` cho một bước | Xem đúng bước đó trong log để đọc thông báo lỗi gốc (nằm ngay phía trên dòng FAIL) | Chạy lại riêng bước đó, ví dụ `python scripts/update_prices_daily.py --universe`, rồi chạy `bash scripts/daily_run.sh --force` để làm nốt các bước còn lại |
| Watchlist trống hoặc gần trống (`client_ready=0` và `trading=0`) | Gate loại gần hết universe — thường do giá và benchmark lệch mốc ngày (quên `update_index_data.py`), giống lỗi STALE_DATA hàng loạt đã gặp trước đây (`audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md`) | `python scripts/update_index_data.py` rồi `bash scripts/daily_run.sh --force` |
| LaunchAgent không chạy (không có dòng SUMMARY mới trong `logs/daily_run.log` dù đã qua 19:00 hôm trước) | Rất có thể vẫn là chặn TCC (macOS Privacy & Security) — kiểm tra `logs/launchd_stderr.log`, nếu thấy `Operation not permitted` thì đúng | Cấp quyền: System Settings → Privacy & Security → Full Disk Access → "+" → thêm `/bin/bash` → bật toggle. Trong lúc chờ: chạy tay `bash scripts/daily_run.sh` mỗi ngày. Kiểm tra agent còn nạp không: `launchctl list \| grep vietnam-quant-research` |
| `update_prices_daily`/`update_disclosure_daily` báo `n_fetch_errors > 0` hoặc `n_updated` thấp bất thường (dưới ~400) | Lỗi mạng/API tạm thời, hoặc nhiều mã thật sự ngừng giao dịch cùng lúc (hiếm) | Chạy lại riêng script đó; nếu vẫn lỗi, chờ vài giờ rồi thử lại (script tự nối tiếp từ `max(date)` đã có, không mất dữ liệu) |
| `freshness_status` trong `data/output/pipeline_metadata.json` khác `"OK"` | Một bước trong pipeline lỗi hoặc dữ liệu quá cũ | Xem `data/output/pipeline_metadata.json`'s `"warnings"`/`"errors"`, chạy lại `bash scripts/daily_run.sh --force` |

Nếu bảng trên không khớp triệu chứng bạn gặp, hoặc chạy lại vẫn không hết:
đây là lúc mở một phiên làm việc code mới, dán nguyên nội dung
`logs/daily_run.log` (đoạn gần lỗi nhất) để được chẩn đoán kỹ hơn.

---

## 6. Điều kiện dừng/xem lại — khi nào quay lại hỏi

Bốn điều kiện dưới đây (nguyên văn từ `SCORE_V2_REPORT.md` mục "Trạng thái
sau GĐ5"/"Conditions for review") xác định khi nào trạng thái "shadow only,
không vốn thật" của `alpha_score` v2 cần được XEM LẠI — không phải tự động
đảo ngược, mà là **mở một phiên làm việc mới để đánh giá bằng chứng, giống
cách quyết định ban đầu được đưa ra**.

1. **Mốc thời gian — hạn 2027-01-16.** Sau 6 tháng shadow chạy liên tục kể
   từ khi tự động hóa có hiệu lực (2026-07-16), bất kể đang thắng hay thua —
   đủ dữ liệu out-of-sample thật để nói điều gì đó backtest không nói được.
   Nếu shadow log ngắt quãng nhiều (mục 1 Bước 3, mục 4), hạn này dời tương
   ứng — không tính máy móc theo lịch nếu dữ liệu không đủ liên tục.
2. **Drawdown tệ hơn −25%** trên một danh mục xếp theo v2 trong dữ liệu live
   (không phải backtest) — xem lại ngay, không đợi đến hạn thời gian.
3. **v2 kém hơn shadow v1 quá 10 điểm phần trăm tích lũy** trong bất kỳ cửa
   sổ 60 phiên giao dịch nào — so hai cột trong shadow log.
4. **Khi đủ 6 tháng (trùng mốc #1): tính Sharpe out-of-sample thuần** (chỉ
   dùng lợi nhuận thật ghi trong shadow log, không phải backtest) của danh
   mục v2-scored, so với khoảng tin cậy bootstrap `[−0.59, +1.32]` (năm hoá,
   `ROBUSTNESS_REPORT.md` mục 5). Nằm trong/dưới nửa dưới của khoảng này →
   xác nhận thêm quyết định "chưa đủ bằng chứng dùng vốn thật" hiện tại,
   không cần làm gì khác. Vượt hẳn lên trên (đặc biệt gần/vượt +1.32) → đáng
   mở một round xem xét lại — vẫn cần review có pre-register riêng, **không
   tự động chuyển sang vốn thật chỉ vì một mốc số liệu tốt**.

Bất kỳ điều kiện nào trong 4 điều trên xảy ra trước → đó là lúc quay lại (mở
một phiên làm việc code mới, hoặc tự bạn đọc kỹ report liên quan) để bàn
tiếp — không phải lúc tự ý đổi quyết định "không vốn thật" một mình.

---

*Tài liệu này nằm trong bản đồ hồ sơ của `PROJECT_STATE.md`. Nếu có gì ở đây
mâu thuẫn với report gốc đã trích dẫn, report gốc luôn đúng hơn.*
