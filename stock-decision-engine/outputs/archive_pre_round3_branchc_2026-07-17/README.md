# archive_pre_round3_branchc_2026-07-17 — công thức cũ (final_score/decision), trước Nhánh C

60 file (`*_decision_summary.txt`, `*_sub_scores.csv`, `*_metrics.csv` cho
20 lần chạy, 16 mã) di dời từ `stock-decision-engine/outputs/` vào đây ngày
2026-07-17, trước khi thi hành Nhánh C.

**Khác với `archive_pre_gate6_fix_2026-07-17/`** (archive trước đó, cùng
thư mục cha): các file ở ĐÓ dùng dữ liệu giá NHIỄM (trước Gate #6). Các file
ở ĐÂY dùng dữ liệu giá ĐÃ SẠCH (sau Gate #6, xem
`stock-decision-engine/GATE6_REGEN_COMPARISON.csv`) nhưng vẫn dùng CÔNG
THỨC CŨ — `final_score` (composite trọng số 8 thành phần) +
`decision` (BUY CANDIDATE/WATCH/WEAK SETUP/AVOID/...).

## Vì sao bị coi là lỗi thời (không phải "nhiễm")

`SDE_SCORING_PREREG.md` (Vòng 3, khóa trước) kiểm định `final_score` +
từng sub-score bằng IC Newey-West + null-test trên full universe,
point-in-time. Kết quả (`stock-decision-engine/SDE_SCORING_REPORT.md`):
**Nhánh C** — không thành phần nào (composite hay sub-score riêng) đạt tiêu
chí đã khóa trước. `final_score`/`decision` đã bị GỠ BỎ khỏi code (không
chỉ ẩn) — `stock-decision-engine/src/scoring.py` từ nay chỉ trả về facts
thô có ngữ cảnh, không còn điểm tổng hợp hay khuyến nghị.

## Không dùng các file này cho bất kỳ quyết định nào

Các con số `final_score`/`decision` trong các file này (kể cả khi dựa trên
dữ liệu giá sạch) **không có bằng chứng dự báo** theo kết quả Vòng 3 — giữ
lại chỉ để đối chiếu lịch sử, không phải nguồn tham khảo cho quyết định đầu
tư. Xem `stock-decision-engine/SDE_SCORING_REPORT.md` và
`stock-decision-engine/ROUND3_BRANCHC_REGEN_COMPARISON.csv`.

## Không xóa

Giữ nguyên vĩnh viễn, đúng quy ước "không xóa artifact, chỉ đánh dấu" của
dự án chính.
