# STRATEGY RESEARCH REPORT — vietnam-quant-research

Nối tiếp `docs/reports/codebase_audit/docs/reports/codebase_audit/REMEDIATION_REPORT.md` (audit fix). Phạm vi: sau khi sửa xong các lỗi đo lường/logic, dùng chính hạ tầng đã sửa để trả lời câu hỏi "chiến lược hiện tại có thực sự lời không, và có thể cải thiện được không" — bằng dữ liệu thật (`data/` copy từ repo gốc, 2020-01-02 → 2026-07-06, 501 mã tracked).

---

## 1. Điểm xuất phát

Chạy notebook backtest gốc (`20_portfolio_backtester.ipynb`, code TRƯỚC fix D1) trên dữ liệu thật cho kết quả thảm hoạ:

| | Code cũ (trước fix) | Code đã fix (D1/D2/C2/G4) |
|---|---|---|
| CAGR | -13.50% | -22.80% |
| Max Drawdown | -86.34% | -92.67% |
| Sharpe | -0.41 | -0.73 |

Fix audit làm số liệu **tệ hơn**, đúng như dự đoán — vì look-ahead bias trước đó đã che giấu một chiến lược thực chất không có lời.

## 2. Phát hiện gốc rễ: công thức chấm điểm không có alpha

- Test xáo trộn (`meta_score` thật vs xáo trộn ngẫu nhiên): **kết quả giống hệt nhau** → công thức fallback (`0.4×momentum + 0.4×trend + 0.2×thanh khoản`) đang chi phối gần như toàn bộ backtest (vì `meta_ranking.parquet` chỉ có 16 ngày dữ liệu, không phủ hết lịch sử) không có khả năng phân biệt mã tốt/xấu.
- Định thời thuần VNINDEX (không chọn mã gì) cho **+8.31% CAGR** — vượt xa hệ thống chọn mã hiện tại (+0.11% có regime filter). Toàn bộ tầng chấm điểm phức tạp của dự án hiện không tạo giá trị đo được.

## 3. Nghiên cứu nhân tố (Information Coefficient) — tìm ra alpha thật

Đo IC (Spearman) giữa từng nhân tố và `forward_return_20d`, trên đúng rổ đã lọc theo thanh khoản + MA200:

| Nhân tố | IC (t-stat) | Kết luận |
|---|---|---|
| Distance MA20 thấp (không quá mua) | mạnh, có ý nghĩa (t≈+5 đến +18 tuỳ mẫu) | **Dùng được** |
| Realized vol 20d thấp | mạnh, có ý nghĩa (t≈+3 đến +8) | **Dùng được** |
| Return 20d/60d/5d (momentum) | **NGƯỢC DẤU**, có ý nghĩa (t≈-3 đến -19) | Dùng được — nhưng phải **đảo chiều** (mean-reversion, không phải momentum-chasing) |
| Thanh khoản, volume z-score | ~0, không ý nghĩa | Bỏ |

Công thức cũ đặt trọng số 0.4+0.4 lên đúng 2 thứ (momentum, trend liên quan momentum) đang có dấu SAI — giải thích vì sao nó tệ hơn ngẫu nhiên.

## 4. Walk-forward validation

- **Single-split** (train 2020-2023 → test 2024-2026, ngoài mẫu thật): CAGR **+6.82%**, Sharpe +0.27 — nhưng may mắn vì năm tệ nhất (2022) nằm trong TRAIN.
- **Rolling 5-fold** (mỗi năm 2022-2026 test độc lập, train = toàn bộ dữ liệu trước đó): lộ ra bức tranh thật — **lời 2023/2024/2025/2026, lỗ nặng -27.6% năm 2022**.

## 5. Thử các lớp bảo vệ rủi ro — hầu hết đều làm tệ hơn

| Lớp bảo vệ | Kết quả trên 5 fold | Kết luận |
|---|---|---|
| Stop-loss -10%/-15% (từng vị thế) | Avg tệ hơn plain | Cắt cả lúc sắp đảo chiều — **phá vỡ chính luận điểm mean-reversion** |
| Regime filter cũ (Risk-off, 75% thời gian) | Avg -5.3%, thắng 20% | Quá thô, dập cả năm tốt lẫn năm xấu |
| Regime filter từng phần (0.5) | Avg -1.0% | Đỡ hơn nhưng vẫn phá năm tốt |
| **Crash-severity filter (mới)** | Không cứu được 2022 | Là tín hiệu **phản ứng** (rolling drawdown), thiệt hại 2022 đã xảy ra ở giai đoạn "Correction" trước khi chạm ngưỡng "Crash" |
| **Give-back stop (bảo toàn lãi khi về breakeven)** | Avg -2.6%, thắng 40% | 2022 chưa từng lãi +15% nên chưa từng "vũ trang" → không giúp gì; lại cắt sớm nhầm năm 2024 (whipsaw) |
| **Take-profit theo phá vỡ cấu trúc (`above_ma20`)** | **Avg +0.9%, trung vị +5.3%, thắng 80%** | **Tốt nhất trong mọi tổ hợp đã thử** |

## 6. Tổ hợp cuối cùng được chọn

**Công thức chấm điểm** (thay thế hoàn toàn công thức momentum-chasing cũ):

```
score = 0.39 × rank(-distance_ma20)      # ưu tiên mã KHÔNG quá mua
      + 0.32 × rank(-return_20d)         # ưu tiên mã vừa ĐIỀU CHỈNH (đảo momentum)
      + 0.29 × rank(-realized_vol_20d)   # ưu tiên mã ÍT biến động
```
(Trọng số tỷ lệ với |IC| đo trên toàn lịch sử; dấu `-` nghĩa là ưu tiên giá trị THẤP của cột gốc.)

**+ Take-profit theo cấu trúc**: `take_profit_pct=0.10`, `trend_break_col="above_ma20"` — không stop-loss, không regime filter, không give-back stop.

**Hiệu suất kỳ vọng** (rolling walk-forward, 5 năm độc lập 2022-2026):

| | 2022 | 2023 | 2024 | 2025 | 2026 | TB | Trung vị | % năm lời |
|---|---|---|---|---|---|---|---|---|
| **Tổ hợp cuối** | -27.6% | +13.1% | +2.0% | +11.6% | +5.3% | **+0.9%** | **+5.3%** | **80%** |

## 7. Giới hạn còn tồn tại — quan trọng, chưa giải quyết

1. **Rủi ro sập toàn diện kiểu 2022 (-27.6%) chưa có lời giải.** Mọi cơ chế bảo vệ đã thử (stop-loss, regime, crash-filter, give-back) hoặc không giúp được, hoặc phá luôn phần lời của các năm tốt. Đây là hạn chế thật của chiến lược, không phải lỗi triển khai.
2. **Chưa nối vào pipeline sản xuất.** Công thức 3-nhân-tố này hiện **chỉ tồn tại trong script nghiên cứu** (`scratch/rolling_walk_forward.py`, `scratch/walk_forward_validation.py`) — **chưa được viết vào `src/analytics/meta_ranking.py` hay bất kỳ script sản xuất nào**. Muốn dùng thật cần một bước triển khai riêng (tách khỏi phạm vi nghiên cứu này).
3. **Mẫu train nhỏ**: 9-38 kỳ tái cân bằng tuỳ giai đoạn — đủ để có ý nghĩa thống kê (t-stat cao) nhờ đo cắt ngang hàng trăm mã, nhưng số năm lịch sử vẫn ít.
4. **Survivorship bias (D3, từ audit cũ)** vẫn chưa xử lý — áp dụng cho toàn bộ nghiên cứu này.
5. **Chỉ dùng dữ liệu kỹ thuật** (giá/khối lượng) — chưa có yếu tố cơ bản (báo cáo tài chính).
6. Trọng số công thức nên được **hiệu chỉnh lại định kỳ** (walk-forward thật, không cố định vĩnh viễn) khi có thêm dữ liệu mới.

## 8. Đã làm gì với code (tách bạch nghiên cứu vs sản xuất)

**Đã vào codebase chính, có test, đã commit** (26 commit kể từ audit):
- `src/backtest/portfolio_backtest.py`: thêm `market_regime`/`stop_loss_pct`/`take_profit_pct`/`giveback_arm_gain` — đều **opt-in, mặc định tắt**, không đổi hành vi cũ nếu không truyền.
- `src/models/regime.py`: `classify_crash_severity`, `classify_breakout_signal`, sửa bug `index_above_ma50/200` luôn `False`.
- `scripts/generate_features.py`: nối VNINDEX thật vào bước tính regime.
- 187 test pass (`pytest tests/ -q`).

**Chỉ là script nghiên cứu, chưa sản xuất** (thư mục `scratch/`, không ảnh hưởng pipeline thật):
`diagnose_backtest.py`, `diagnose_alpha_source.py`, `diagnose_factor_ic.py`, `test_evidence_based_score.py`, `walk_forward_validation.py`, `rolling_walk_forward.py`, `validate_crash_severity_overlay.py`.

## 9. Đề xuất nếu muốn đi tiếp (chưa làm, cần bạn quyết định hướng)

- Viết công thức 3-nhân-tố vào `src/analytics/meta_ranking.py` thật (thay thế/bổ sung công thức hiện tại) kèm cơ chế hiệu chỉnh trọng số định kỳ.
- Nghiên cứu thêm nhân tố khác biệt (không chỉ kỹ thuật) để có tín hiệu bảo vệ SỚM hơn cho rủi ro kiểu 2022 (ví dụ vĩ mô, thanh khoản hệ thống).
- Giải quyết D3 (dữ liệu delisted) để loại survivorship bias khỏi mọi con số trên.
