# Quy ước làm việc (mọi session phải tuân thủ)
1. Làm việc TẠI THƯ MỤC GỐC, commit thẳng vào main. Không tạo
   branch/worktree mới. Các nhánh claude/* và backup/* cũ: đóng
   băng, không đụng.
2. KHÔNG BAO GIỜ push — chỉ commit local. Push là quyết định của
   người dùng.
3. Đầu session: đọc PUSH_REVIEW.md (nhật ký tiến độ) và
   audit/PATH_TO_100.md (lộ trình) trước khi làm gì.
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
