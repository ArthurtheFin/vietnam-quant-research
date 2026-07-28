# PREREG DRAFT — sửa chuỗi danh mục 14 → 15 → 16

> **TRẠNG THÁI: BẢN NHÁP. CHƯA CHẠY BẤT KỲ THÍ NGHIỆM NÀO.**
> Soạn 2026-07-28 (Đợt 5 NV3). Phải được duyệt và **khoá** trước khi chạy dòng
> code đầu tiên. Mọi con số xuất hiện trong file này lúc soạn thảo đều là mô tả
> vấn đề hiện tại, không phải kết quả.

## 1. Vấn đề cần giải

`notebooks/04_watchlist_portfolio/14_portfolio_construction.ipynb` (và 15, 16 ăn
theo) tạo ra các con số Sharpe/NAV **không có giá trị dự báo**, vì ba lý do chồng
nhau:

| # | Vấn đề | Vị trí |
|---|---|---|
| 1 | `user_watchlist` ghi cứng 20 mã (11 ngân hàng) ⇒ nhánh lấy ứng viên từ trade card không bao giờ chạy | nb14 cell "Load Universe And Returns" |
| 2 | μ = trung bình lịch sử toàn mẫu, đưa thẳng vào mean-variance; có shrinkage cho Σ (0.15), **không có** cho μ | nb14 cell "Build Allocations" |
| 3 | Chọn Sharpe cao nhất trong ~53.000 ứng viên (10.000 random + ~43.000 tổ hợp 3–5 mã) đánh giá **trên chính mẫu ước lượng μ/Σ** | nb14 cells "Monte Carlo", "Concentrated Portfolios" |

Kết quả (`mc_best_concentrated_3_5`) được ghi ra file và notebook 15/16 xây tiếp,
nên bias lan xuống báo cáo rủi ro và kế hoạch vốn.

## 2. Giả thuyết tiền đăng ký

**H0**: sau khi tách fit/evaluate theo thời gian và bỏ universe hard-code, danh
mục do quy trình này chọn **không** cho Sharpe out-of-sample vượt trội so với
equal-weight trên cùng universe.

**H1**: có vượt trội, theo tiêu chí ở mục 4.

Ghi rõ trước: **kỳ vọng của người soạn là H0 không bị bác bỏ.** Ba vòng kiểm định
trước trong repo này (`WATCHLIST_VALIDATION_REPORT.md`, `SCORE_V2_REPORT.md`,
`MARKET_REGIME_STUDY`) đều kết luận âm tính, và `breakout_20d` vừa mất phần lớn
lợi thế khi mẫu tăng 6–10× (Đợt 4 NV0).

## 3. Thiết kế — khoá trước khi chạy

**Universe.** Bỏ hoàn toàn `user_watchlist`. Lấy ứng viên từ trade card
(`edge_tier ∈ {Strong, Valid, Emerging, Conditional}`) tại **ngày quyết định**,
không phải cuối mẫu.

**Tách thời gian.** Walk-forward, không phải một lần chia:
- Cửa sổ fit: 36 tháng trượt.
- Cửa sổ đánh giá: 3 tháng liền sau, **không chồng lấn**.
- Bước trượt: 3 tháng.
- Chỉ dùng dữ liệu ≤ cuối cửa sổ fit để ước lượng μ, Σ và để chọn danh mục.

**Ước lượng.** μ: Ledoit-Wolf hoặc James-Stein shrinkage (chọn **trước**, không
so hai cái rồi lấy cái đẹp hơn). Σ: giữ `shrink_covariance(0.15)` như hiện tại.

**Không gian tìm kiếm.** Giữ nguyên ~53.000 ứng viên **nhưng** mọi lựa chọn phải
xảy ra trong cửa sổ fit, và báo cáo phải kèm hiệu chỉnh multiple testing
(Deflated Sharpe Ratio, `n_trials` = số ứng viên thật đã duyệt).

**Baseline bắt buộc** (báo cáo cả ba, không được bỏ cái nào):
1. Equal-weight trên cùng universe ứng viên.
2. VNINDEX buy-and-hold.
3. Random portfolio cùng kích thước (median của 1.000 lần bốc).

**Chi phí.** 0,15%/chiều, giống `run_portfolio_backtest`. Không chạy phiên bản
không chi phí.

## 4. Tiêu chí quyết định — khoá trước

Bác bỏ H0 **chỉ khi cả ba** đồng thời đúng trên chuỗi OOS ghép:

1. **DSR > 0** với `n_trials` = tổng số ứng viên đã duyệt.
2. **t-stat Newey-West ≥ 3.0** cho chênh lệch lợi nhuận so với equal-weight
   (ngưỡng 3.0 theo tiền lệ `WATCHLIST_VALIDATION_PREREG.md`, không phải 2.0).
3. Vượt equal-weight ở **≥ 60%** số cửa sổ đánh giá.

Không đạt đủ ba ⇒ **kết luận Nhánh C**: chuỗi 14/15/16 không có alpha đã kiểm
định, chuyển sang không xếp hạng alpha (giống kết cục `final_watchlist`).

## 5. Cam kết chống data mining

- **Một lần chạy duy nhất.** Chạy lại sau khi nhìn kết quả ⇒ phải prereg mới.
- Không đổi cửa sổ, ngưỡng, universe, hay hàm shrinkage sau khi thấy số.
- Mọi tham số ở mục 3 **đóng băng** khi file này được duyệt.
- Ghi `git_commit_hash` lúc chạy vào output.
- **Kết quả âm tính vẫn phải công bố** trong `PUSH_REVIEW.md`, đúng như bốn vòng
  kiểm định trước.

## 6. Ngoài phạm vi

- Kelly sizing của notebook 16 (`win_rate` in-sample) — prereg riêng.
- Lựa chọn `stop_loss` in-sample của nb07 qua `_select_best_stop_relaxed()` —
  prereg riêng, nhưng **cùng họ vấn đề** và nên làm trước hoặc cùng lúc.
- Ngưỡng tuyệt đối cho tier watchlist (option (i) của Đợt 5 A) — prereg riêng.

## 7. Cần duyệt

- [ ] Chủ dự án duyệt mục 3 (thiết kế) và mục 4 (tiêu chí) **trước khi chạy**.
- [ ] Khoá file, ghi commit hash của bản duyệt.
- [ ] Chỉ sau đó mới viết code thí nghiệm.
