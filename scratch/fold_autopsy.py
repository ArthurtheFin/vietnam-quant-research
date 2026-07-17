"""docs/reports/scoring/docs/reports/scoring/FOLD_AUTOPSY_REPORT.md evidence. Diagnosis-only round -- no scoring
changes, no tuning, no new factor tests. Uses the CURRENT (already-applied)
deployed alpha_score (src/alpha/scoring.py) and the same 5 walk-forward
folds as scratch/rolling_walk_forward.py / scratch/scoring_before_after.py.

Important pre-existing quirk in src/backtest/portfolio_backtest.py: its own
returned `benchmark_curve` silently falls back to the alphabetically-first
symbol in `features` ("A32") when "VNINDEX" isn't a row in that dataframe
(it never is -- VNINDEX lives in data/processed/benchmark_vnindex.parquet,
a separate file). NOT fixed here (out of scope, diagnosis only) -- worked
around by pulling the real VNINDEX series independently for every
excess-return and regime-label computation below.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.alpha.scoring import calculate_alpha_scores
from src.validation.metrics import calculate_cagr, calculate_max_drawdown

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])
benchmark = benchmark.sort_values("date").reset_index(drop=True)
benchmark["ma200"] = benchmark["close"].rolling(200, min_periods=20).mean()
benchmark["realized_vol_60d"] = benchmark["return_1d"].rolling(60, min_periods=30).std() * np.sqrt(252)

print("Computing deployed (NEW) alpha_score...")
scored = calculate_alpha_scores(features_all, benchmark)
meta = scored[["symbol", "date", "alpha_score"]].rename(columns={"alpha_score": "meta_score"})

FOLDS = [
    ("2021-12-31", "2022-01-01", "2022-12-31"),
    ("2022-12-31", "2023-01-01", "2023-12-31"),
    ("2023-12-31", "2024-01-01", "2024-12-31"),
    ("2024-12-31", "2025-01-01", "2025-12-31"),
    ("2025-12-31", "2026-01-01", "2026-07-06"),
]
BASE = dict(
    rebalance_period=20,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
)


def vnindex_cagr(start: pd.Timestamp, end: pd.Timestamp) -> float:
    seg = benchmark[(benchmark["date"] >= start) & (benchmark["date"] <= end)]
    if len(seg) < 2:
        return np.nan
    nav = (1.0 + seg["return_1d"].fillna(0.0)).cumprod()
    return calculate_cagr(pd.Series(nav.values, index=seg["date"].values))


def vnindex_maxdd(start: pd.Timestamp, end: pd.Timestamp) -> float:
    seg = benchmark[(benchmark["date"] >= start) & (benchmark["date"] <= end)]
    if len(seg) < 2:
        return np.nan
    nav = (1.0 + seg["return_1d"].fillna(0.0)).cumprod()
    return calculate_max_drawdown(pd.Series(nav.values, index=seg["date"].values))


def regime_label(fold_start: pd.Timestamp) -> dict:
    """As-of the last trading day strictly BEFORE fold_start -- no look-ahead."""
    prior = benchmark[benchmark["date"] < fold_start]
    if prior.empty:
        return {"above_ma200": None, "vol_regime": None, "close": None, "ma200": None, "vol_60d": None, "vol_median_to_date": None}
    last = prior.iloc[-1]
    vol_hist_median = prior["realized_vol_60d"].median()
    above = bool(last["close"] > last["ma200"]) if pd.notna(last["ma200"]) else None
    vol_high = bool(last["realized_vol_60d"] > vol_hist_median) if pd.notna(last["realized_vol_60d"]) and pd.notna(vol_hist_median) else None
    return {
        "above_ma200": above,
        "vol_regime": ("high" if vol_high else "low") if vol_high is not None else None,
        "close": last["close"], "ma200": last["ma200"],
        "vol_60d": last["realized_vol_60d"], "vol_median_to_date": vol_hist_median,
    }


rows = []
for train_end, test_start, test_end in FOLDS:
    test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
    test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
    test_meta = meta[(meta["date"] >= test_start_ts) & (meta["date"] <= test_end_ts)].copy()

    r = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **BASE)
    m = r["metrics"]
    trades = r["trades_log"]

    # avg names selected per rebalance (proxy for avg portfolio size actually held)
    buys = trades[trades["type"] == "BUY"] if not trades.empty else pd.DataFrame()
    if not buys.empty:
        names_per_rebalance = buys.groupby("date")["symbol"].nunique()
        avg_names = names_per_rebalance.mean()
    else:
        avg_names = np.nan

    # turnover: total traded $ value / number of rebalances / initial_nav, as a %
    total_traded = trades["size_amount"].sum() if not trades.empty else 0.0
    n_rebalances = trades["date"].nunique() if not trades.empty else 0
    turnover_pct_per_rebalance = (total_traded / n_rebalances / BASE["initial_nav"]) if n_rebalances else np.nan

    idx_cagr = vnindex_cagr(test_start_ts, test_end_ts)
    idx_maxdd = vnindex_maxdd(test_start_ts, test_end_ts)
    excess_cagr = m["cagr"] - idx_cagr if pd.notna(idx_cagr) else np.nan

    reg = regime_label(test_start_ts)

    rows.append({
        "fold": test_start[:4], "period": f"{test_start}..{test_end}",
        "cagr": m["cagr"], "max_dd": m["max_drawdown"], "sharpe": m["sharpe_ratio"],
        "avg_names": avg_names, "turnover_pct_per_rebal": turnover_pct_per_rebalance,
        "n_trades": len(trades), "vnindex_cagr": idx_cagr, "vnindex_maxdd": idx_maxdd,
        "excess_cagr": excess_cagr,
        "pre_fold_above_ma200": reg["above_ma200"], "pre_fold_vol_regime": reg["vol_regime"],
        "pre_fold_vol_60d": reg["vol_60d"], "pre_fold_vol_median_to_date": reg["vol_median_to_date"],
    })

result = pd.DataFrame(rows).sort_values("cagr")
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)

print("\n" + "=" * 90)
print("NHIEM VU 1 -- fold table, sorted by CAGR ascending")
print("=" * 90)
print(result[["fold", "period", "cagr", "max_dd", "avg_names", "turnover_pct_per_rebal", "n_trades",
              "vnindex_cagr", "vnindex_maxdd", "excess_cagr"]].to_string(
    index=False,
    formatters={"cagr": "{:+.1%}".format, "max_dd": "{:.1%}".format, "avg_names": "{:.1f}".format,
                "turnover_pct_per_rebal": "{:.1%}".format, "vnindex_cagr": "{:+.1%}".format,
                "vnindex_maxdd": "{:.1%}".format, "excess_cagr": "{:+.1%}".format}))

disaster = result[result["cagr"] < -0.30]
print(f"\nDisaster folds (CAGR < -30%): {disaster['fold'].tolist()}")
for _, row in disaster.iterrows():
    verdict = "RODE BETA DOWN (excess ~0)" if abs(row["excess_cagr"]) < 0.10 else (
        "STOCK-PICKING LOSS (worse than index)" if row["excess_cagr"] < -0.10 else "OUTPERFORMED INDEX (still lost)")
    print(f"  {row['fold']}: portfolio={row['cagr']:+.1%} vnindex={row['vnindex_cagr']:+.1%} "
          f"excess={row['excess_cagr']:+.1%} -> {verdict}")

print("\n" + "=" * 90)
print("NHIEM VU 2 -- regime cross-tab (pre-fold state, no look-ahead)")
print("=" * 90)
print(result[["fold", "pre_fold_above_ma200", "pre_fold_vol_regime", "pre_fold_vol_60d",
              "pre_fold_vol_median_to_date", "cagr", "max_dd"]].to_string(
    index=False,
    formatters={"cagr": "{:+.1%}".format, "max_dd": "{:.1%}".format,
                "pre_fold_vol_60d": "{:.1%}".format, "pre_fold_vol_median_to_date": "{:.1%}".format}))

for group_col in ["pre_fold_above_ma200", "pre_fold_vol_regime"]:
    print(f"\nCross-tab by {group_col}:")
    grp = result.groupby(group_col).agg(
        avg_cagr=("cagr", "mean"), pct_negative=("cagr", lambda s: (s < 0).mean()),
        avg_maxdd=("max_dd", "mean"), n_folds=("cagr", "size"),
    )
    print(grp.to_string(formatters={"avg_cagr": "{:+.1%}".format, "pct_negative": "{:.0%}".format, "avg_maxdd": "{:.1%}".format}))

print("\n" + "=" * 90)
print("NHIEM VU 3 -- transaction cost sensitivity (0x / 1x / 2x baseline 0.0015)")
print("=" * 90)
for cost_mult, cost_label in [(0.0, "0x"), (1.0, "1x (baseline)"), (2.0, "2x")]:
    cagrs = []
    for train_end, test_start, test_end in FOLDS:
        test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
        test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
        test_meta = meta[(meta["date"] >= test_start_ts) & (meta["date"] <= test_end_ts)].copy()
        kwargs = dict(BASE)
        kwargs["transaction_cost_pct"] = 0.0015 * cost_mult
        r = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **kwargs)
        cagrs.append(r["metrics"]["cagr"])
    avg_cagr = np.mean(cagrs)
    print(f"  cost={cost_label:16s} transaction_cost_pct={0.0015*cost_mult:.4f}  "
          f"per-fold CAGR={[f'{c:+.1%}' for c in cagrs]}  avg={avg_cagr:+.1%}")

print("\ndone")
