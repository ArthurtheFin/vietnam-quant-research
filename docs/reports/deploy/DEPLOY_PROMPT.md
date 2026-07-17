# SUPER PROMPT — Triển khai công thức chấm điểm đã validate vào production
# (Dán nguyên văn vào Claude Code phiên mới, chạy trong repo `vietnam-quant-research`)

---

## BỐI CẢNH (đọc kỹ trước khi làm gì)

Một phiên làm việc trước đã: (1) audit toàn bộ repo và sửa 40 phát hiện (xem `docs/reports/codebase_audit/docs/reports/codebase_audit/AUDIT_REPORT.md`, `docs/reports/codebase_audit/docs/reports/codebase_audit/IMPLEMENTATION_PLAN.md`, `docs/reports/codebase_audit/docs/reports/codebase_audit/REMEDIATION_REPORT.md`), rồi (2) dùng chính hạ tầng đã sửa để nghiên cứu chiến lược thật trên dữ liệu VN 2020-2026, kết quả đầy đủ nằm ở **`docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`** — **bắt buộc đọc file này trước tiên**, nó là nguồn sự thật duy nhất cho phiên này.

Tóm tắt cực ngắn (không thay thế việc đọc file thật): công thức chấm điểm momentum-chasing hiện tại (dynamic fallback score trong `src/backtest/portfolio_backtest.py`) đã được chứng minh **không có alpha** (test xáo trộn cho kết quả giống hệt). Nghiên cứu factor IC tìm ra 3 nhân tố có tín hiệu thật, đã qua walk-forward validate (single-split + rolling 5-fold trên dữ liệu thật):

```
score = 0.39 × rank(-distance_ma20)      # ưu tiên mã KHÔNG quá mua
      + 0.32 × rank(-return_20d)         # đảo momentum (mean-reversion, không phải momentum-chasing)
      + 0.29 × rank(-realized_vol_20d)   # ưu tiên mã ÍT biến động
```

Overlay tốt nhất tìm được: `take_profit_pct=0.10` với `trend_break_col="above_ma20"` (chỉ chốt lời khi giá cắt xuống dưới MA20, không chốt cơ học). **Không dùng stop-loss, không dùng regime filter, không dùng give-back stop** — cả 3 đã thử và đều làm tệ hơn hoặc không giúp gì trên dữ liệu này.

**Giới hạn đã biết, KHÔNG thuộc phạm vi phiên này**: chiến lược vẫn lỗ nặng (-27.6%) trong kịch bản kiểu 2022 (sập toàn diện đầu năm, chưa kịp tích luỹ lãi để bảo vệ). Không cố giải bài toán này trong phiên này — đã thử 4 hướng (stop-loss, regime, crash-severity filter, give-back stop) đều thất bại, ghi rõ trong mục 7 của `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`.

---

## ĐIỂM QUAN TRỌNG NHẤT CẦN HIỂU ĐÚNG TRƯỚC KHI SỬA CODE

Công thức 3-nhân-tố ở trên **hiện chỉ tồn tại trong script nghiên cứu** (`scratch/rolling_walk_forward.py`, `scratch/walk_forward_validation.py`, `scratch/test_evidence_based_score.py`) — **chưa hề đụng vào** `src/analytics/meta_ranking.py` (công thức "chính thức" breakout/stealth/momentum/execution) hay `src/alpha/scoring.py`.

Điều đã chứng minh là KÉM: chỉ là **dynamic fallback score** viết thẳng trong `run_portfolio_backtest()` (dùng khi `ranking_indexed.loc[decision_date]` không tìm thấy ngày đó trong `meta_ranking.parquet` — xảy ra với hầu hết lịch sử vì `meta_ranking.parquet` trong lần nghiên cứu chỉ có 16 ngày dữ liệu, không phủ hết 2020-2026).

**Công thức "chính thức" trong `src/analytics/meta_ranking.py` (`score_meta_ranking()`) CHƯA TỪNG được validate tốt/xấu trong nghiên cứu này** — vì nó gần như không được backtest chạm tới do dữ liệu thưa. Đừng mặc định nó cũng tệ và thay thế ngay — hãy tự kiểm tra trước (xem Phase 0).

---

## VAI TRÒ

Bạn là Senior Quantitative Developer, tiếp tục công việc từ phiên trước. Nhiệm vụ: triển khai công thức đã validate vào pipeline production một cách an toàn, có kiểm chứng, không phá vỡ những gì đã sửa ở audit trước.

## NGUYÊN TẮC BẮT BUỘC

1. **Đọc `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md` và các script trong `scratch/` được nhắc ở đó TRƯỚC KHI viết code.** Đây là nguồn logic/công thức/trọng số chính xác — không suy luận lại từ đầu.
2. **Không sửa gì trước khi có Implementation Plan được duyệt.** Kết thúc Phase 0 bằng file `docs/reports/deploy/docs/reports/deploy/IMPLEMENTATION_PLAN_DEPLOY.md`, dừng lại chờ "APPROVED".
3. **Mọi thay đổi phải opt-in / có thể tắt được, không phá hành vi cũ theo mặc định** — đúng phong cách các tham số `stop_loss_pct=None`, `market_regime=None` đã có sẵn trong `run_portfolio_backtest`.
4. **Không tự ý mở rộng phạm vi**: không cố giải bài toán 2022 (đã ghi rõ là ngoài phạm vi), không đụng vào D3 (survivorship bias, vẫn treo), không "tiện tay" tối ưu thêm chỗ khác.
5. **Mỗi cụm thay đổi = 1 commit riêng**, message rõ ràng.
6. **Mọi công thức/trọng số đưa vào production phải có test tái tạo đúng con số đã nghiên cứu** — ví dụ: chạy công thức mới trên `data/processed/stock_features.parquet` thật (nếu có sẵn trong môi trường) hoặc trên fixture tổng hợp, đối chiếu với kết quả đã ghi trong `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`.
7. Trả lời ngắn gọn, không paste lại code dài vào chat — chỉ tóm tắt + đường dẫn file.

---

## PHASE 0 — ĐỌC + KIỂM TRA HIỆN TRẠNG + LẬP KẾ HOẠCH (bắt buộc, chờ duyệt)

1. Đọc `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md`, `docs/reports/codebase_audit/docs/reports/codebase_audit/AUDIT_REPORT.md` (mục G1/G5/G6/D5 liên quan trực tiếp đến scoring), và toàn bộ code trong `scratch/rolling_walk_forward.py` + `scratch/walk_forward_validation.py` (đây là nơi công thức + cách tính trọng số walk-forward được implement chính xác nhất — đừng viết lại từ trí nhớ, đọc code thật).
2. **Kiểm tra hiện trạng trước khi giả định**:
   - Chạy `pytest tests/ -q` — xác nhận baseline vẫn xanh (nếu không, dừng lại báo cáo, đừng tiếp tục build trên nền gãy).
   - Đọc `src/analytics/meta_ranking.py::score_meta_ranking()` hiện tại — công thức "chính thức" có còn giống mô tả trong report không, hay đã đổi.
   - Kiểm tra `data/processed/stock_features.parquet`, `data/processed/benchmark_vnindex.parquet` có tồn tại trong môi trường phiên này không (chúng bị `.gitignore`, có thể phiên mới không có sẵn — nếu không có, cần dùng SSI credentials/`.env` để fetch lại, hoặc dùng fixture tổng hợp cho test, và **nói rõ với tôi** là không verify được bằng dữ liệu thật).
3. **Quyết định kiến trúc cần đề xuất trong plan** (không tự quyết mà không hỏi):
   - Đặt công thức 3-nhân-tố ở đâu: hàm mới trong `src/alpha/scoring.py`, hay module riêng `src/analytics/reversal_quality_score.py`? Đề xuất hướng, nêu lý do.
   - Cơ chế tính trọng số walk-forward (IC trên dữ liệu TRAIN, không phải full-history) nên là hàm tái sử dụng được, không hardcode 0.39/0.32/0.29 vĩnh viễn — thiết kế sao cho có thể chạy lại định kỳ (ví dụ mỗi quý) với cutoff date cấu hình được.
   - Có 2 điểm tích hợp cần làm rõ trong plan, xử lý TÁCH BIỆT:
     a. **Dynamic fallback score trong `run_portfolio_backtest`** (đã CHỨNG MINH tệ) — thay bằng công thức mới, đây là việc rõ ràng, nên làm.
     b. **`score_meta_ranking()` trong `meta_ranking.py`** (CHƯA validate tốt/xấu) — plan phải đề xuất: có nên (i) để nguyên, (ii) thêm công thức mới làm MỘT THÀNH PHẦN bổ sung (không thay thế), hay (iii) validate riêng công thức hiện tại bằng đúng phương pháp IC/shuffle-test trước khi quyết định — và hỏi tôi chọn hướng nào trước khi code, vì đây là quyết định kiến trúc, không phải chi tiết kỹ thuật.
   - Wiring overlay (`take_profit_pct=0.10`, `trend_break_col="above_ma20"`, không stop-loss/regime/give-back) vào đâu cho việc chạy production thực tế (notebook `20_portfolio_backtester.ipynb`? `scripts/build_portfolio_stack.py`? cả hai?) — kiểm tra code thật trước khi đề xuất, đừng đoán.
4. Viết `docs/reports/deploy/docs/reports/deploy/IMPLEMENTATION_PLAN_DEPLOY.md`: mỗi hạng mục ghi file/hàm sẽ sửa, pseudo-code trước/sau, test kèm theo, rủi ro phụ (output nào sẽ đổi).
5. **Dừng lại, chờ tôi trả lời "APPROVED"** trước khi viết bất kỳ dòng code nào.

## PHASE 1-3 — THỰC THI (chỉ sau khi được duyệt)

- Theo đúng plan đã duyệt. Mỗi phần xong: chạy `pytest tests/ -q`, báo cáo ngắn (đổi gì, test nào, commit hash).
- Nếu phát hiện điều gì ngoài dự kiến (ví dụ `score_meta_ranking()` hiện tại đã đổi khác report), dừng hạng mục đó, ghi chú, hỏi tôi thay vì tự quyết.

## PHASE 4 — VERIFY & BÁO CÁO CUỐI

1. Chạy lại `pytest tests/ -q` toàn bộ.
2. Nếu có dữ liệu thật trong môi trường: chạy lại công thức mới, đối chiếu số liệu với bảng ở mục 6 của `docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md` (CAGR/Sharpe theo từng fold) — báo cáo khớp hay lệch và vì sao.
3. Sinh file `docs/reports/deploy/docs/reports/deploy/DEPLOY_REPORT.md`: đã nối gì vào đâu, test nào chứng minh khớp nghiên cứu, còn nợ gì (ví dụ nếu quyết định KHÔNG đụng `score_meta_ranking()` thì ghi rõ đây vẫn là việc treo).

Bắt đầu Phase 0 ngay.
