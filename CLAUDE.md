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
4. Commit theo từng nhiệm vụ, message rõ ràng. Xong việc lớn: cập
   nhật PUSH_REVIEW.md.
5. FIREWALL: không join dữ liệu disclosure với dữ liệu giá/return
   cho đến khi DISCLOSURE_EVENT_STUDY_PREREG.md được commit và chạy
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
   Lý do: `ROBUSTNESS_REPORT.md` (GĐ5/NV4) — đã xảy ra trường hợp
   BH-FDR (q=0.05) trên 214 test gộp từ `FACTOR_RETEST_V2` +
   `WATCHLIST_VALIDATION` cho ra ngưỡng LỎNG HƠN |t|>3 thủ công (38
   sống sót qua FDR so với 27 qua |t|>3) — quy ước cũ không tự động
   là "thận trọng hơn", cần cả hai con số để không tự đánh lừa mình
   theo hướng nào.
