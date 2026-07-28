# Quarantine — feature file mồ côi (2026-07-27, Đợt 4 NV1)

Hai file dưới `data/processed/` **không có producer nào** trong `src/` hay
`scripts/`, nhưng vẫn được notebook 13/14 đọc. Chuyển vào đây thay vì xoá —
chúng bị gitignore, xoá là mất hẳn.

| File | Ngày dữ liệu | Ai từng ghi | Ai đọc (trước Đợt 4) |
|---|---|---|---|
| `stock_features_volatility.parquet` | **2026-06-24** | Không ai — kể cả ở commit đầu tiên | nb13, nb14 |
| `stock_features_distribution.parquet` | 2026-07-20 | nb04, nhưng nb04 nay ghi sang `notebooks/outputs/` | nb13 |

## Truy nguyên `stock_features_volatility.parquet`

`git log -S "stock_features_volatility"` chỉ trúng các file *đọc* nó, không có
file nào *ghi*. Ở commit đầu tiên `4313f2d` (2026-07-01), `05_volatility_regime.ipynb`
đã ghi ra `stock_features.parquet` — **không phải** `_volatility`. Ngày dữ liệu
của file là 2026-06-24, tức **trước cả commit đầu tiên**.

⇒ Kết luận: tàn dư của một phiên chạy tay trước khi repo vào git. Chưa bao giờ
có producer trong code được version.

## Có tái tạo được không? Có — `stock_features.parquet` là tập cha

| | cột | ngày dữ liệu mới nhất |
|---|---|---|
| `stock_features_volatility.parquet` (mồ côi) | 25 | 2026-06-24 |
| `stock_features.parquet` (pipeline hiện hành) | **49** | **2026-07-27** |

Cột duy nhất có ở file mồ côi mà thiếu ở bản hiện hành là `forward_return_1d` —
`add_returns()` cố ý bỏ qua `h == 1` (`src/features/returns.py:50`), và đó là cột
nhìn về tương lai, không notebook nào ở đây dùng.

## ⚠️ Đính chính bản audit đầu tiên

`notebooks/AUDIT_NOTEBOOKS_REPORT.md` (phần gốc) ghi hai notebook này nhận
"**NaN im lặng** cho mọi ngày sau 2026-06-24". **Sai.** Kiểm tra lại:
`setup_signals.parquet` đã mang sẵn cả 6 cột enrich
(`volatility_regime`, `volatility_percentile`, `atr_pct_14`, `dist_skew_60d`,
`dist_kurt_60d`, `tail_ratio_60d`). Cả nb13 lẫn nb14 đều chỉ merge những cột
**chưa có** (`col not in analysis_df.columns` / `col not in signals.columns`) —
điều kiện đó luôn rỗng, nên **lệnh merge chưa bao giờ chạy**.

Tức hai file này là **I/O thừa tạo cảm giác có phụ thuộc**, không phải nguồn
NaN. Vì vậy việc gỡ chúng khỏi nb13/nb14 **không đổi một con số nào**.

## Nếu cần dùng lại

Đừng đọc từ đây. Dùng `data/processed/stock_features.parquet`
(`python scripts/generate_features.py`) — tập cha, cập nhật hằng đêm.
