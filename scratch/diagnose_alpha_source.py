"""Phase B step 1 (one-off diagnostic, not part of the codebase): does stock
SELECTION (meta_score top-5) add value beyond just market-timing (regime
filter)? Compares, all under the SAME regime-filtered exposure rule:
  (a) top-5 by meta_score (the actual system)
  (b) top-5 by a SHUFFLED meta_score (same universe/filters, random pick)
  (c) equal-weight across the entire eligible universe (no selection at all)
  (d) regime-timed VNINDEX only (no stock-picking, no diversification choice)
If (a) does not clearly beat (b) and (c), meta_score is not adding
demonstrated alpha -- all of Phase A's improvement is market timing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.validation.metrics import calculate_cagr, calculate_max_drawdown, calculate_sharpe

features = read_parquet("data/processed/stock_features.parquet")
meta_ranking = read_parquet("data/signals/meta_ranking.parquet")
market = read_parquet("data/processed/market_features.parquet")
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
if meta_ranking.empty:
    meta_ranking = features[["symbol", "date"]].copy()
    meta_ranking["meta_score"] = features["return_20d"].fillna(0.0) * 100.0

BASE = dict(
    rebalance_period=20,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
    market_regime=market,
    regime_cash_fraction=1.0,
)


def show(name, r):
    m = r["metrics"]
    print(f"{name:50s} CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}  final={m['final_nav']:,.0f}")


# (a) actual system: top-5 by real meta_score
r_actual = run_portfolio_backtest(features=features, meta_ranking=meta_ranking, portfolio_size=5, **BASE)
show("(a) top-5 by REAL meta_score", r_actual)

# (b) top-5 by a shuffled meta_score (same distribution, random assignment per date)
rng = np.random.default_rng(42)
shuffled = meta_ranking.copy()
shuffled["meta_score"] = shuffled.groupby("date")["meta_score"].transform(
    lambda s: rng.permutation(s.values)
)
r_shuffled_runs = []
for seed in range(5):
    rng_i = np.random.default_rng(seed)
    shuf = meta_ranking.copy()
    shuf["meta_score"] = shuf.groupby("date")["meta_score"].transform(
        lambda s: rng_i.permutation(s.values)
    )
    r = run_portfolio_backtest(features=features, meta_ranking=shuf, portfolio_size=5, **BASE)
    r_shuffled_runs.append(r["metrics"])
avg_cagr = np.mean([m["cagr"] for m in r_shuffled_runs])
avg_dd = np.mean([m["max_drawdown"] for m in r_shuffled_runs])
avg_sharpe = np.mean([m["sharpe_ratio"] for m in r_shuffled_runs])
print(f"{'(b) top-5 by SHUFFLED meta_score (avg of 5 seeds)':50s} CAGR={avg_cagr:+.2%}  MaxDD={avg_dd:.2%}  Sharpe={avg_sharpe:+.2f}")

# (c) equal-weight across the ENTIRE eligible universe (no selection skill exercised)
r_broad = run_portfolio_backtest(features=features, meta_ranking=meta_ranking, portfolio_size=999, **BASE)
show("(c) equal-weight ALL eligible (no selection)", r_broad)

# (d) regime-timed VNINDEX only (pure market timing, zero stock-picking)
bench = benchmark.sort_values("date").copy()
bench["date"] = pd.to_datetime(bench["date"])
if "return_1d" not in bench.columns:
    bench["return_1d"] = bench["close"].pct_change()
regime_by_date = market.set_index("date")["market_regime"]
regime_lagged = regime_by_date.shift(1)
regime_aligned = regime_lagged.reindex(bench.set_index("date").index).ffill()
exposure = (~regime_aligned.isin(["Risk-off"])).astype(float)
timed_ret = (bench.set_index("date")["return_1d"].fillna(0.0) * exposure).fillna(0.0)
timed_nav = (1 + timed_ret).cumprod() * 1_000_000_000.0
print(f"{'(d) regime-timed VNINDEX only (no stock-picking)':50s} CAGR={calculate_cagr(timed_nav):+.2%}  MaxDD={calculate_max_drawdown(timed_nav):.2%}  Sharpe={calculate_sharpe(timed_ret):+.2f}  final={timed_nav.iloc[-1]:,.0f}")

# (e) untimed VNINDEX buy-and-hold, for full context
bh_ret = bench.set_index("date")["return_1d"].fillna(0.0)
bh_nav = (1 + bh_ret).cumprod() * 1_000_000_000.0
print(f"{'(e) VNINDEX buy-and-hold (no timing, no picking)':50s} CAGR={calculate_cagr(bh_nav):+.2%}  MaxDD={calculate_max_drawdown(bh_nav):.2%}  Sharpe={calculate_sharpe(bh_ret):+.2f}  final={bh_nav.iloc[-1]:,.0f}")
