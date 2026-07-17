# V2_STABILITY_NOTE — giải nghịch lý null-test percentile 71.0 vs 52.8

**NHÃN: chẩn đoán máy đo (diagnostic của công cụ kiểm định), không phải kiểm
định tín hiệu mới.** Không đổi trọng số/tham số nào của `alpha_score` v2 hay
`final_watchlist.py` trong tài liệu này — chỉ xác định vì sao hai lần chạy
null-test cho hai con số khác nhau trên cùng một signal.

## Bối cảnh

- `docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md` (round xác nhận v2 ban đầu): null-test percentile
  trung bình **71.0**, không fold nào <5.
- `docs/reports/scoring/docs/reports/scoring/WATCHLIST_VALIDATION_REPORT.md` mục 3b (GĐ4, "watchlist tối giản" = v2_score
  + gate hiện hành của `final_watchlist.py`): percentile trung bình **52.8**,
  không fold nào <10 nhưng cũng không đạt >60.

Cùng một công thức `v2_score` (0.70×hạng nghịch đảo `realized_vol_20d` +
0.30×hạng nghịch đảo `value_ma20`), cùng seed=42, cùng N_ITER=2000, cùng
`portfolio_size=10`/`sector_cap=2`/`rebalance_period=20`/`transaction_cost=0.15%`,
cùng 5 fold (2022–2026) — vậy chênh lệch 18.2 điểm phần trăm đến từ đâu?

## Ba khác biệt cấu hình giữa hai cỗ máy (liệt kê trước khi chạy lại)

| | `score_v2_null_test.py` (71.0) | `watchlist_validation_null.py`'s minimal_watchlist (52.8) |
|---|---|---|
| Nguồn dữ liệu | `data/processed/stock_features.parquet` đọc trực tiếp lúc chạy (2026-07-09/10) | `data/output/watchlist_validation_panel.parquet` (dựng tại GĐ4, dữ liệu đến 2026-07-13) |
| Universe trước khi vào `run_portfolio_backtest` | Toàn bộ 500 mã, không lọc trước | Lọc trước còn `trading_status==ACTIVE` (441/500) |
| Gate bổ sung | Không — chỉ dựa vào `min_value_ma20`/`above_ma200` nội bộ của `run_portfolio_backtest` | Lọc thêm `minimal_eligible = strict_pass \| fallback_eligible` (gate đầy đủ của `final_watchlist.py`'s `_mark_filters()` — gồm cả ATR, `distance_ma20`, drawdown, giá sàn, không chỉ thanh khoản/trend) |

**Nghi phạm**: (a) khác cỗ máy gọi `run_portfolio_backtest` (không — cả hai
dùng chung hàm, chỉ khác input), (b) dữ liệu mới hơn/2 mốc khác nhau, (c) gate
`minimal_eligible` bổ sung.

## Chẩn đoán — chạy lại đúng cấu hình cũ trên dữ liệu hiện hành

Chạy lại nguyên văn `scratch/score_v2_null_test.py` (không sửa dòng nào, đọc
`stock_features.parquet` hiện hành, đã đồng bộ đến 2026-07-15) — script này tự
đọc dữ liệu mới nhất trên đĩa, nên "chạy lại" chỉ đơn giản là thực thi lại.

**Kết quả: trung bình 5 fold = 71.0 (giống hệt), không fold nào <5.** →
**Nghi phạm (b) — dữ liệu mới/2 mốc — BỊ LOẠI TRỪ.** Dữ liệu hiện hành không
làm percentile tụt.

## Phân tách nghi phạm (a)/(c) — bật từng khác biệt một lần

Chạy thêm MỘT cấu hình: `trading_status==ACTIVE` lọc trước (441/500 mã) +
v2_score từ panel, **KHÔNG** thêm `minimal_eligible` — mọi thứ khác giữ
nguyên (`scratch/v2_stability_toggle.py`).

**Kết quả: trung bình 5 fold = 70.5** — gần như không đổi so với 71.0 (chênh
0.5 điểm, trong biên nhiễu bình thường giữa các fold).

## Kết luận

| Cấu hình | Percentile trung bình |
|---|---|
| Không lọc gì thêm (nguyên bản `docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md`) | 71.0 |
| + `trading_status==ACTIVE` (441/500 mã) | 70.5 |
| + `trading_status==ACTIVE` **VÀ** `minimal_eligible` (GĐ4) | **52.8** |

**Bằng phép loại trừ, rõ ràng: gate `minimal_eligible` (`strict_pass \| fallback_eligible`
của `final_watchlist.py`) là nguyên nhân gần như toàn bộ của chênh lệch
71.0→52.8, không phải universe `ACTIVE` (đóng góp ~0.5 điểm, không đáng kể) và
không phải dữ liệu mới (đã loại trừ hoàn toàn).** Cơ chế hợp lý: `minimal_eligible`
lọc thêm theo ATR, `distance_ma20`, drawdown, giá sàn — một rổ đã được lọc kỹ
theo các tiêu chí này có thể làm hẹp lại khoảng biến thiên (range restriction)
mà `v2_score`'s ưu tiên "vol thấp" còn có thể khai thác, vì một phần thông tin
đó đã bị "dùng hết" bởi chính gate. Đây là suy luận hợp lý, KHÔNG được kiểm
chứng thêm trong round này (sẽ cần một phân rã riêng theo từng điều kiện con
của `_mark_filters()` nếu muốn xác nhận cơ chế chính xác).

## Khuyến nghị — v2 đang live có cần đánh giá lại trạng thái không?

**Có, một phần — không phải "v2 sai", mà "bối cảnh triển khai thực tế khắt khe
hơn bối cảnh v2 được xác nhận ban đầu".** `alpha_score` v2 hiện được tính và
lưu trữ như một trường độc lập (`data/signals/alpha_scores.parquet`), nhưng
bất cứ khi nào nó được dùng làm cơ sở xếp hạng BÊN TRONG `final_watchlist.py`
(như "watchlist tối giản" ở GĐ4 mô phỏng, và cũng là cách nó từng được cân
nhắc dùng trước khi GĐ4 chuyển sang không-xếp-hạng-alpha), nó hoạt động trong
đúng bối cảnh 52.8, không phải 71.0 — vì gate `minimal_eligible` luôn đi kèm.
**`docs/reports/scoring/docs/reports/scoring/SCORE_V2_REPORT.md`'s con số 71.0 là đúng cho v2 kiểm tra ĐỘC LẬP (chỉ qua
gate thô của `run_portfolio_backtest`), nhưng lạc quan hơn thực tế nếu diễn
giải nó như bằng chứng cho v2 hoạt động BÊN TRONG `final_watchlist.py`'s pipeline
đầy đủ.** Không đổi gì trong round này (đúng ràng buộc) — nhưng khuyến nghị: nếu
có quyết định trong tương lai về việc dùng lại v2 làm cơ sở xếp hạng cho
`final_watchlist.py` (thay vì thanh khoản thuần như hiện tại), phải kiểm định
LẠI trong đúng bối cảnh gate đầy đủ (như GĐ4 đã làm), không được trích dẫn lại
con số 71.0 làm bằng chứng — hai con số đo hai thứ khác nhau, không thể dùng
thay thế cho nhau.

## Lineage

Script: `scratch/score_v2_null_test.py` (không sửa, chạy lại),
`scratch/v2_stability_toggle.py` (mới, GĐ5). Kết quả thô:
`data/full_history_v2/score_v2_null_test.csv` (ghi đè bởi lần chạy lại),
`data/output/v2_stability_toggle_active_only.csv`. Dữ liệu: đồng bộ đến
2026-07-15 (GĐ4).
