# Quy ước làm việc (mọi session phải tuân thủ)
1. Làm việc TẠI THƯ MỤC GỐC, commit thẳng vào main. Không tạo
   branch/worktree mới. Các nhánh claude/* và backup/* cũ: đóng
   băng, không đụng.
   Lưu ý: công cụ (Claude Code) có thể tự sinh worktree riêng cho
   mỗi session (vd. .claude/worktrees/<tên>) mà không do người dùng
   yêu cầu. Việc đó vô hại nếu bỏ trống — nhưng MỌI THAO TÁC ĐỌC/GHI/
   COMMIT vẫn phải nhắm vào thư mục gốc /Users/jamesb/Desktop/
   vietnam-quant-research và branch main, bất kể session được sinh
   ra ở thư mục nào. Nếu shell cwd bị tool tự động kéo về worktree,
   dùng đường dẫn tuyệt đối hoặc `git -C <path-gốc>` cho mọi lệnh
   thay vì dựa vào `cd` persist.
2. KHÔNG BAO GIỜ push — chỉ commit local. Push là quyết định của
   người dùng.
3. Đầu session: đọc PROJECT_STATE.md (cửa ngõ — trạng thái hiện tại,
   quy trình vận hành, bản đồ hồ sơ) TRƯỚC, rồi PUSH_REVIEW.md (nhật
   ký tiến độ) và audit/PATH_TO_100.md (lộ trình) trước khi làm gì.
   Nếu người dùng hỏi về vận hành hằng ngày, đọc hiểu một output cụ
   thể, hay bất cứ điều gì KHÔNG phải phát triển code: trỏ tới
   docs/PROJECT_HANDBOOK.md (sổ tay toàn thư — tài liệu GỐC cho chủ dự
   án/người ngoài từ nay, không cần đọc code; docs/PROJECT_HANDBOOK.pdf
   là bản xuất kèm) thay vì giải thích lại từ đầu.
   docs/DAILY_OPERATING_GUIDE.md vẫn còn, đã hợp nhất nội dung vào sổ
   tay Phần 0-3 — giữ làm bản rút gọn/lịch sử, không phải nguồn chính.
4. Commit theo từng nhiệm vụ, message rõ ràng. Xong việc lớn: cập
   nhật PUSH_REVIEW.md.
5. FIREWALL: không join dữ liệu disclosure với dữ liệu giá/return
   cho đến khi docs/reports/disclosure/DISCLOSURE_EVENT_STUDY_PREREG.md được commit và chạy
   theo đúng spec.
6. Mọi claim phủ định ("không còn chỗ nào khác") phải kèm bằng chứng
   liệt kê. Mọi artifact tự sinh phải có lineage metadata.
7. Trước khi sinh watchlist/report: chạy update_prices_daily.py +
   update_disclosure_daily.py.
8. Không tune tham số theo kết quả backtest. Thiết kế test chốt
   trước khi chạy.
9. Mọi bảng test đa nhân tố (nhiều tổ hợp factor × universe × target
   trong một lần chạy) phải báo kèm q-value FDR (Benjamini-Hochberg)
   bên cạnh t-stat/p-value thô, không chỉ ngưỡng thủ công (vd. |t|>3).
   Lý do: `docs/reports/scoring/ROBUSTNESS_REPORT.md` (GĐ5/NV4) — đã xảy ra trường hợp
   BH-FDR (q=0.05) trên 214 test gộp từ `FACTOR_RETEST_V2` +
   `WATCHLIST_VALIDATION` cho ra ngưỡng LỎNG HƠN |t|>3 thủ công (38
   sống sót qua FDR so với 27 qua |t|>3) — quy ước cũ không tự động
   là "thận trọng hơn", cần cả hai con số để không tự đánh lừa mình
   theo hướng nào.
10. `stock-decision-engine/` — **đã GỠ read-only từ 2026-07-17**.
    `SDE_SCORING_PREREG.md` đã chạy (Vòng 3, 2026-07-17): `final_score`/
    `decision` KHÔNG có bằng chứng dự báo (IC Newey-West + null-test đều
    không đạt) → **Nhánh C thi hành** — `final_score`/`decision` đã GỠ BỎ
    khỏi `src/scoring.py` (không phải comment/deprecate), chỉ còn bảng
    facts thô có ngữ cảnh. Đọc `stock-decision-engine/SDE_SCORING_REPORT.md`
    (kết quả cuối) trước `AUDIT_SDE_REPORT.md` (lịch sử 3 vòng) trước khi
    sửa bất cứ gì trong thư mục này. **Không thêm lại một điểm tổng hợp/
    decision label nào** cho đến khi có bằng chứng IC/null-test mới đạt
    tiêu chí tương đương — đây không còn là vùng "chưa kiểm định", mà là
    "đã kiểm định và không đạt".
11. **Đổi chữ ký hàm (thêm/bỏ/đổi tên tham số bắt buộc) của bất kỳ hàm nào
    trong `src/` mà notebook có gọi tới → PHẢI chạy
    `make check-notebooks` (hoặc `python scripts/check_notebooks.py`)
    trước khi coi thay đổi đó là xong.** Lý do:
    `docs/reports/codebase_audit/NOTEBOOK_AUDIT_FULL.md` — 3 lần liên tiếp
    một thay đổi chữ ký hàm hợp lệ trong `src/` (ví dụ: `add_market_regime`
    thêm `benchmark=`, `run_portfolio_backtest` bỏ fallback benchmark ngầm
    bắt buộc `benchmark_features=`) chỉ được phát hiện đã làm hỏng notebook
    qua audit thủ công, không phải ngay khi đổi. `check_notebooks.py` chạy
    toàn bộ notebook trong sandbox cô lập (không đụng dữ liệu thật) và báo
    lỗi ngay — không cần đợi vòng audit sau mới biết. Notebook gọi API
    sống (SSI) bị bỏ qua mặc định (`LIVE_API_NOTEBOOKS` trong script), thêm
    `--include-live` nếu cần chạy cả chúng.

12. **Consumer phải kiểm tra độ tươi của artifact nó đọc — cấm im lặng dùng
    bản cũ.** Một bước/notebook đọc file do bước KHÁC sinh ra thì không được
    chỉ kiểm tra "file có tồn tại / có rỗng không" rồi dùng luôn. Phải một
    trong hai: (a) so ngày dữ liệu bằng `assert_input_chain_fresh()` /
    `assert_derived_artifact_fresh()` và FAIL rõ ràng, hoặc (b) đọc bằng
    `load_upstream_artifact()` — hàm này luôn in ra mtime + tuổi file và gắn
    cờ `stale`. Tất cả nằm trong `src/validation/freshness_check.py`.
    Lý do (`notebooks/AUDIT_NOTEBOOKS_REPORT.md`): hai sự cố cùng một họ.
    (1) `breakout_20d_setup_eligibility.parquet` đóng băng 25 ngày mà
    `generate_trade_cards.py` vẫn đọc mỗi đêm — trade card vẫn "tươi" nên mọi
    freshness check hạ nguồn đều pass. (2) notebook 15 dùng
    `os.path.exists()` rồi đọc thẳng, nên khi guard chặn notebook 14 ghi file,
    nó im lặng xài bản cũ nhiều ngày. Cả hai đều **ồn ở chỗ ghi, im ở chỗ
    đọc** — chỗ đọc mới là nơi phải kêu.
