# Stock Decision Engine

Independent decision notebook for `vietnam-quant-research`.

It answers: given a selected ticker, should I buy now, wait, watch, or avoid?

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

- decision summary text
- sub-score CSV
- metrics CSV
- matplotlib chart PNGs

## Notes

- Requires daily OHLCV columns: `symbol`, `date`, `open`, `high`, `low`, `close`, `volume`.
- If `value` is absent, trading value is estimated as `close * volume`.
- If VNINDEX is missing, add `data/processed/benchmark_vnindex.parquet` or `data/raw/index_ohlcv/VNINDEX.parquet`.
- Backtest evidence is included when project signal files are present; otherwise it is skipped gracefully.
