"""Phase B step 3 (one-off diagnostic, not part of the codebase): build a
composite score from ONLY the factors that showed real, significant IC in
diagnose_factor_ic.py, and backtest it head-to-head against the current
fallback formula (0.4*momentum + 0.4*trend + 0.2*liquidity, which IC-tested
at -0.20, t=-5.16 -- actively anti-predictive).

New composite (weights proportional to each factor's |mean IC|):
    score = 0.39 * rank(-distance_ma20)      [avoid overextension: IC +0.339]
          + 0.32 * rank(-return_20d)         [reverse momentum: IC -0.282]
          + 0.29 * rank(-realized_vol_20d)   [low-volatility premium: IC +0.253]
Higher score = more attractive. All ranks are cross-sectional percentile
ranks computed at each date from data available AT that date (no lookahead;
run_portfolio_backtest already lags decision to T-1 per D1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest

features = read_parquet("data/processed/stock_features.parquet")
market = read_parquet("data/processed/market_features.parquet")

BASE = dict(
    rebalance_period=20,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
)


def build_evidence_based_ranking(features: pd.DataFrame) -> pd.DataFrame:
    df = features[["symbol", "date", "distance_ma20", "return_20d", "realized_vol_20d"]].copy()
    df["date"] = pd.to_datetime(df["date"])

    def _pct_rank(s: pd.Series) -> pd.Series:
        return s.rank(pct=True)

    grouped = df.groupby("date")
    rank_distance = grouped["distance_ma20"].transform(lambda s: _pct_rank(-s))
    rank_momentum_rev = grouped["return_20d"].transform(lambda s: _pct_rank(-s))
    rank_low_vol = grouped["realized_vol_20d"].transform(lambda s: _pct_rank(-s))

    df["meta_score"] = (
        0.39 * rank_distance.fillna(0.5)
        + 0.32 * rank_momentum_rev.fillna(0.5)
        + 0.29 * rank_low_vol.fillna(0.5)
    ) * 100.0
    return df[["symbol", "date", "meta_score"]]


def show(name, r):
    m = r["metrics"]
    print(f"{name:55s} CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}  final={m['final_nav']:,.0f}")


evidence_ranking = build_evidence_based_ranking(features)

# (1) Evidence-based score, WITHOUT regime filter -- isolates pure selection skill
r_selection_only = run_portfolio_backtest(features=features, meta_ranking=evidence_ranking, **BASE)
show("(1) Evidence-based score, NO regime filter", r_selection_only)

# (2) Evidence-based score, WITH regime filter -- the full candidate strategy
r_full = run_portfolio_backtest(
    features=features, meta_ranking=evidence_ranking,
    market_regime=market, regime_cash_fraction=1.0, **BASE,
)
show("(2) Evidence-based score + regime filter", r_full)

# (3) Shuffle test on the NEW score -- must NOT match (1) if it has real skill
shuffle_cagrs = []
for seed in range(5):
    rng = np.random.default_rng(seed)
    shuf = evidence_ranking.copy()
    shuf["meta_score"] = shuf.groupby("date")["meta_score"].transform(lambda s: rng.permutation(s.values))
    r = run_portfolio_backtest(features=features, meta_ranking=shuf, **BASE)
    shuffle_cagrs.append(r["metrics"]["cagr"])
print(f"{'(3) SHUFFLED evidence-based score (avg of 5 seeds), NO regime':55s} CAGR={np.mean(shuffle_cagrs):+.2%}  (individual: {[f'{c:+.2%}' for c in shuffle_cagrs]})")

# (4) Baseline for reference: old fallback-driven selection, no regime filter
r_baseline = run_portfolio_backtest(features=features, meta_ranking=pd.DataFrame(columns=["symbol", "date", "meta_score"]), **BASE)
show("(4) Baseline (old fallback formula), NO regime filter", r_baseline)

# (5) Old fallback + regime filter (Phase A result, for reference)
r_baseline_regime = run_portfolio_backtest(
    features=features, meta_ranking=pd.DataFrame(columns=["symbol", "date", "meta_score"]),
    market_regime=market, regime_cash_fraction=1.0, **BASE,
)
show("(5) Baseline (old fallback) + regime filter [Phase A]", r_baseline_regime)
