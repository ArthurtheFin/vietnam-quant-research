# `config/delisted_symbols.csv` — hạt giống, CHƯA ĐẦY ĐỦ

Tạo 2026-07-27 (Đợt 3 NV3). Trước đó file này **không tồn tại**, nên cell
"Run Leakage Verification" của `notebooks/04_watchlist_portfolio/19_validation_and_stress_test.ipynb`
rơi vào nhánh `else` và in "SKIPPED: ... survivorship bias is not being measured"
— tức repo **chưa bao giờ đo** survivorship bias.

## Nguồn và cách sinh

20 mã `INACTIVE_LONG` trong `data/full_history_v2/trading_status.parquet`
(`gap_days > STALE_SHORT_MAX_GAP_DAYS = 10`), tại ngày dữ liệu 2026-07-27.
(Vòng phân loại trước đếm được 18 mã; con số tăng lên 20 khi dữ liệu chạy tiếp
tới 2026-07-27 — cùng cách tính, không phải cách khác.)

## ⚠️ Ba hạn chế phải đọc trước khi dùng

**1. `INACTIVE_LONG` KHÔNG đồng nghĩa "đã hủy niêm yết".** Ngưỡng
`gap_days > 10` được hiệu chuẩn cho *eligibility gate* (loại mã thanh khoản
mỏng khỏi watchlist), không phải để nhận diện hủy niêm yết. Cột `confidence`
tách thô theo `gap_days >= 90`:

| confidence | n | Ý nghĩa |
|---|---|---|
| `likely_delisted` | 10 | Không có phiên nào ≥ 1 quý (75–1634 ngày). Nhiều khả năng đã ngừng niêm yết thật. |
| `inactive_unverified` | 10 | Chỉ hở 12–19 ngày. **Nhiều khả năng chỉ là thanh khoản mỏng hoặc tạm ngừng**, không phải hủy niêm yết. |

Chưa đối chiếu với công bố hủy niêm yết chính thức của HOSE/HNX/UPCoM. Cần làm
điều đó trước khi coi danh sách này là dữ kiện.

**2. Danh sách bị chặn trên bởi chính universe hiện tại.** Nó chỉ liệt kê được
mã **có trong** `full_history_v2`. Mã bị hủy niêm yết trước khi dataset bắt đầu
thì không có mặt ở bất kỳ đâu để mà liệt kê — đó chính là phần survivorship bias
nghiêm trọng nhất, và danh sách này **không chạm tới được**.

**3. Vì (2), phép đo hiện tại gần như tuần hoàn.** `check_survivorship_bias()`
tính `missing_delisted = delisted_set - active_set`. 19/20 mã trong file này
**nằm trong** universe 500 mã của `setup_signals.parquet`, nên theo định nghĩa
chúng không thể "missing". Chỉ `GEE` nằm ngoài. Nghĩa là con số check trả về
hầu như phản ánh cách dựng danh sách, không phải mức survivorship bias thật.

## Liên hệ Gate #3

Cùng họ với khoảng trống phủ dữ liệu ở Gate #3
(`audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md`): cả hai đều bắt nguồn từ việc
`trading_status` chỉ mô tả được các mã đã có trong dataset. Muốn đo survivorship
bias cho ra số có nghĩa thì phải nạp danh sách hủy niêm yết lịch sử từ nguồn
ngoài, không phải suy ra từ dữ liệu đang có.

## Cập nhật

```bash
python -c "
import sys; sys.path.insert(0,'.')
from src.validation.trading_status import latest_trading_status
print(latest_trading_status().query(\"status=='INACTIVE_LONG'\"))"
```
