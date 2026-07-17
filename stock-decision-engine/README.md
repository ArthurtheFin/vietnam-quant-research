# Stock Decision Engine

Independent facts-table notebook for `vietnam-quant-research`.

**Nhánh C từ 2026-07-17 (`SDE_SCORING_REPORT.md`, Vòng 3)**: đây KHÔNG còn
là một công cụ khuyến nghị mua/bán. `final_score` (composite trọng số 8
thành phần) và `decision` (BUY CANDIDATE/WATCH/WEAK SETUP/AVOID/...) đã bị
gỡ bỏ hoàn toàn khỏi code -- IC Newey-West và null-test (point-in-time,
full universe, đúng phương pháp đã khóa cho `final_watchlist.py`) đều
không đạt tiêu chí đã khóa trước cho cả composite lẫn từng sub-score. Đọc
`SDE_SCORING_REPORT.md` trước khi dùng. Notebook giờ chỉ hiển thị chỉ số
thô có ngữ cảnh (MA, RSI, ATR, Sharpe, v.v.) cho một mã đã chọn -- không
điểm tổng hợp, không xếp loại.

## Structure

```text
stock-decision-engine/
  config.yaml
  notebooks/stock_buy_decision.ipynb
  src/
  outputs/
```

The engine reuses existing project data:

- `data/processed/clean_daily_ohlcv.parquet`
- `data/processed/benchmark_vnindex.parquet`
- `data/signals/*` backtest and signal outputs when available

It does not modify the legacy notebooks or SSI client.

## Run

```bash
cd path/to/vietnam-quant-research
jupyter notebook stock-decision-engine/notebooks/stock_buy_decision.ipynb
```

Edit only the first notebook cell for normal use:

```python
TICKER = "ACB"
BENCHMARK = "VNINDEX"
CONFIG_PATH = "../config.yaml"
```

Outputs are saved to `stock-decision-engine/outputs/`:

- facts summary text (`*_facts_summary.txt`, không phải khuyến nghị)
- facts CSV (`*_facts.csv`, các nhóm chỉ số thô có ngữ cảnh)
- metrics CSV (kèm lineage: dataset version, git commit hash)
- matplotlib chart PNGs

## Notes

- Requires daily OHLCV columns: `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`.
- If `value` is absent, trading value is estimated as `close * volume`.
- If VNINDEX is missing, add `data/processed/benchmark_vnindex.parquet` or `data/raw/index_ohlcv/VNINDEX.parquet`.
- Backtest evidence is included when project signal files are present; otherwise it is skipped gracefully.
