"""One-off diagnostic (not part of the codebase): quantify which levers actually
move the -22.8% CAGR / -92.7% drawdown result, using real data already in this
worktree. Not committed as a fix -- for proposal purposes only."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.validation.metrics import calculate_cagr, calculate_max_drawdown, calculate_sharpe

features = read_parquet("data/processed/stock_features.parquet")
meta_ranking = read_parquet("data/signals/meta_ranking.parquet")
market = read_parquet("data/processed/market_features.parquet")
if meta_ranking.empty:
    meta_ranking = features[["symbol", "date"]].copy()
    meta_ranking["meta_score"] = features["return_20d"].fillna(0.0) * 100.0

BASE_KWARGS = dict(
    rebalance_period=20, portfolio_size=5, allocation_method="equal_weight",
    transaction_cost_pct=0.0015, initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000, require_above_ma200=True,
)


def summarize(name, result):
    m = result["metrics"]
    print(f"{name:45s} CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}  final={m['final_nav']:,.0f}")


# 1) Baseline (current fixed code, no changes)
result = run_portfolio_backtest(features=features, meta_ranking=meta_ranking, **BASE_KWARGS)
summarize("BASELINE (current, no stop-loss/regime filter)", result)

# 2) Larger portfolio (diversification)
result2 = run_portfolio_backtest(features=features, meta_ranking=meta_ranking, **{**BASE_KWARGS, "portfolio_size": 10})
summarize("portfolio_size=10 (more diversified)", result2)

# 3) Inverse-vol allocation instead of equal-weight
result3 = run_portfolio_backtest(features=features, meta_ranking=meta_ranking, **{**BASE_KWARGS, "allocation_method": "inverse_vol"})
summarize("allocation_method=inverse_vol", result3)

# 4) Regime filter: force 100% cash whenever market_regime == 'Risk-off' at rebalance
market_regime_by_date = market.set_index("date")["market_regime"] if "market_regime" in market.columns else None


def run_with_regime_filter(risk_off_labels=("Risk-off",)):
    """Monkeypatch-free approximation: zero out days where regime is bad by
    scaling equity exposure post-hoc is NOT equivalent to not holding -- so
    instead we re-run with a synthetic 'require_above_ma200' proxy is not
    enough either. For this diagnostic, approximate by measuring what CAGR/DD
    would look like if returns on risk-off days were floored at 0 (proxy for
    'would have de-risked to cash'), which is directionally informative even
    if not a perfect simulation.
    """
    eq = result["equity_curve"].copy()
    port_ret = result["portfolio_returns"].copy()
    if market_regime_by_date is None:
        return None
    # IMPORTANT: classify_market_regime uses same-day MA/breadth features, so
    # using today's regime to gate today's return is look-ahead bias -- lag by
    # 1 day (yesterday's regime decides today's exposure) to be honest.
    regime_lagged = market_regime_by_date.shift(1)
    regime_aligned = regime_lagged.reindex(port_ret.index).ffill()
    adj_ret = port_ret.where(~regime_aligned.isin(risk_off_labels), 0.0)
    adj_nav = (1 + adj_ret).cumprod() * 1_000_000_000.0
    cagr = calculate_cagr(adj_nav)
    mdd = calculate_max_drawdown(adj_nav)
    sharpe = calculate_sharpe(adj_ret)
    return {"cagr": cagr, "max_drawdown": mdd, "sharpe_ratio": sharpe, "final_nav": adj_nav.iloc[-1]}


regime_result = run_with_regime_filter()
if regime_result:
    print(f"{'PROXY: flat (cash) on Risk-off days':45s} CAGR={regime_result['cagr']:+.2%}  MaxDD={regime_result['max_drawdown']:.2%}  Sharpe={regime_result['sharpe_ratio']:+.2f}  final={regime_result['final_nav']:,.0f}")

# 5) Regime day coverage
if market_regime_by_date is not None:
    counts = market_regime_by_date.value_counts()
    print()
    print("market_regime distribution over full history:")
    print(counts)
