"""One-off diagnostic (not part of the codebase): does score_meta_ranking()
(the LIVE client-watchlist formula in src/analytics/meta_ranking.py) actually
carry alpha, using the same IC + shuffle-test rigor already applied to the
old momentum fallback and the new 3-factor score?

Structural caveat, read before interpreting results: score_meta_ranking()
blends 4 components (breakout/stealth/momentum/execution) from 3 input
sources. Only 2 of those 3 sources have genuine multi-date history without
look-ahead:
  - "features" (technical) -> data/signals/setup_signals.parquet, full
    2020-2026 daily history.
  - "stealth"              -> data/signals/stealth_accumulation_history.parquet,
    full 2020-2026 daily history.
  - "trade_cards"          -> only ever exists as a ~16-day LIVE snapshot
    (breakout_20d_trade_cards.parquet), because its edge_tier/profit_factor/
    stop_loss columns come from a full-sample backtested-edge lookup
    (breakout_20d_setup_eligibility.parquet) that cannot be reconstructed
    per historical date without look-ahead (the edge summary itself is
    computed FROM the full history).

So this script tests the historically-reconstructable PART of the formula
(momentum + execution + stealth + risk_penalty components; breakout_
component_score is a constant across symbols when trade_cards is absent --
verified below -- so it cannot bias the cross-sectional ranking, it just
mutes 30% of the intended weight) across the full 2020-2026 history, AND
separately checks IC on the real, complete formula (with real trade_cards)
over the ~16 live production dates where all 3 sources actually coexist.
Neither substitutes for the other; both are reported.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.analytics.meta_ranking import prepare_meta_ranking_dataset, score_meta_ranking
from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest

REBALANCE_PERIOD = 20
MIN_VALUE_MA20 = 10_000_000_000.0
MIN_ELIGIBLE = 15

features_all = read_parquet("data/signals/setup_signals.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
stealth_all = read_parquet("data/signals/stealth_accumulation_history.parquet")
stealth_all["date"] = pd.to_datetime(stealth_all["date"])


def _spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


all_dates = sorted(features_all["date"].unique())
rebalance_dates = all_dates[::REBALANCE_PERIOD]

ic_records: list[float] = []
history_rows: list[pd.DataFrame] = []

print(f"Reconstructing score_meta_ranking() at {len(rebalance_dates) - 1} historical decision dates "
      f"(this recomputes the full formula per date, may take a minute)...")

for idx, current_date in enumerate(rebalance_dates):
    if idx == 0:
        continue
    decision_date = all_dates[all_dates.index(current_date) - 1]

    feat_asof = features_all[features_all["date"] <= decision_date]
    stealth_asof = stealth_all[stealth_all["date"] <= decision_date]
    if feat_asof.empty:
        continue

    prepared = prepare_meta_ranking_dataset(
        features=feat_asof,
        trade_cards=None,
        stealth=stealth_asof,
        signal_col="breakout_20d",
    )
    if prepared.empty:
        continue
    ranked = score_meta_ranking(prepared, signal_col="breakout_20d")

    eligible = ranked.copy()
    if "value_ma20" in eligible.columns:
        eligible = eligible[eligible["value_ma20"].fillna(0) >= MIN_VALUE_MA20]
    if "above_ma200" in eligible.columns:
        eligible = eligible[eligible["above_ma200"].astype(bool)]
    if "forward_return_20d" not in eligible.columns or len(eligible) < MIN_ELIGIBLE:
        continue

    ic = _spearman_ic(eligible["meta_score"], eligible["forward_return_20d"])
    if ic is not None:
        ic_records.append(ic)

    history_rows.append(pd.DataFrame({
        "symbol": ranked["symbol"],
        "date": decision_date,
        "meta_score": ranked["meta_score"],
    }))

arr = np.array(ic_records)
mean_ic = arr.mean() if len(arr) else float("nan")
std_ic = arr.std(ddof=1) if len(arr) > 1 else float("nan")
t_stat = mean_ic / std_ic * np.sqrt(len(arr)) if std_ic and std_ic > 0 else float("nan")
print(f"\n--- score_meta_ranking() reconstructed IC vs forward_return_20d, {len(arr)} rebalance dates, "
      f"2020-2026 (trade_cards absent -- see module docstring) ---")
print(f"  mean_IC={mean_ic:+.4f}  t-stat={t_stat:+.2f}  N={len(arr)}  median={np.median(arr):+.4f}  "
      f"pct_positive={(arr > 0).mean():.0%}")

# Sanity check: with trade_cards absent, breakout_component_score must be a
# CONSTANT across symbols at each date (it would otherwise silently bias the
# ranking with a component that isn't actually being tested).
last_prepared = prepared
last_ranked = score_meta_ranking(last_prepared, signal_col="breakout_20d")
n_unique_breakout_score = last_ranked["breakout_component_score"].nunique()
print(f"  sanity check: breakout_component_score unique values on last date = {n_unique_breakout_score} "
      f"(expected 1 -- confirms it cannot bias this reconstruction)")

meta_ranking_history = pd.concat(history_rows, ignore_index=True) if history_rows else pd.DataFrame(columns=["symbol", "date", "meta_score"])

BASE = dict(
    rebalance_period=REBALANCE_PERIOD,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=MIN_VALUE_MA20,
    require_above_ma200=True,
)


def show(name, r):
    m = r["metrics"]
    print(f"{name:65s} CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}  final={m['final_nav']:,.0f}")


print("\n--- Backtest: reconstructed score_meta_ranking() history ---")
r_real = run_portfolio_backtest(features=features_all, meta_ranking=meta_ranking_history, **BASE)
show("(A) Reconstructed score_meta_ranking() (partial formula, full history)", r_real)

N_SEEDS = 20
shuffle_cagrs = []
for seed in range(N_SEEDS):
    rng = np.random.default_rng(seed)
    shuf = meta_ranking_history.copy()
    shuf["meta_score"] = shuf.groupby("date")["meta_score"].transform(lambda s: rng.permutation(s.values))
    r = run_portfolio_backtest(features=features_all, meta_ranking=shuf, **BASE)
    shuffle_cagrs.append(r["metrics"]["cagr"])
shuffle_arr = np.array(shuffle_cagrs)
print(f"{'(B) SHUFFLED reconstructed score (avg of ' + str(N_SEEDS) + ' seeds)':65s} "
      f"CAGR={shuffle_arr.mean():+.2%}  std={shuffle_arr.std(ddof=1):.2%}  "
      f"min={shuffle_arr.min():+.2%}  max={shuffle_arr.max():+.2%}  "
      f"pct_seeds_beaten_by_real={(shuffle_arr < r_real['metrics']['cagr']).mean():.0%}")

# --- Rolling 5-fold breakdown, SAME fold boundaries as the validated
# 3-factor score's rolling_walk_forward.py, for a direct apples-to-apples
# comparison against docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md section 6's table. ---
FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-06"),
]
print("\n--- Rolling per-year fold breakdown (reconstructed score_meta_ranking(), same folds as report section 6) ---")
fold_cagrs = []
for start, end in FOLDS:
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    fold_features = features_all[(features_all["date"] >= start_ts) & (features_all["date"] <= end_ts)]
    fold_ranking = meta_ranking_history[(meta_ranking_history["date"] >= start_ts) & (meta_ranking_history["date"] <= end_ts)]
    if fold_features.empty:
        continue
    try:
        r = run_portfolio_backtest(features=fold_features, meta_ranking=fold_ranking, **BASE)
        m = r["metrics"]
        fold_cagrs.append(m["cagr"])
        print(f"  {start[:4]}: CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}")
    except Exception as exc:
        print(f"  {start[:4]}: ERROR {exc}")
if fold_cagrs:
    fold_arr = np.array(fold_cagrs)
    print(f"  AvgCAGR={fold_arr.mean():+.2%}  MedCAGR={np.median(fold_arr):+.2%}  WinRate={(fold_arr > 0).mean():.0%}")
    print("  (compare to docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md section 6: 3-factor score got "
          "AvgCAGR=+0.9%, MedCAGR=+5.3%, WinRate=80%)")

# --- Secondary check: the REAL, complete formula (with real trade_cards),
# over the sparse ~16 live production dates where it actually exists. ---
print("\n--- Secondary check: REAL score_meta_ranking() output (with real trade_cards), live production window ---")
real_meta_ranking = read_parquet("data/signals/meta_ranking.parquet")
if real_meta_ranking.empty:
    print("  data/signals/meta_ranking.parquet is empty in this environment -- skipped.")
else:
    real_meta_ranking = real_meta_ranking.copy()
    real_meta_ranking["date"] = pd.to_datetime(real_meta_ranking["date"])
    fwd_lookup = features_all.set_index(["symbol", "date"])["forward_return_20d"]
    joined = real_meta_ranking.join(fwd_lookup, on=["symbol", "date"])
    real_dates = sorted(joined["date"].unique())
    ic_real = []
    for d in real_dates:
        snap = joined[joined["date"] == d]
        if len(snap) < MIN_ELIGIBLE:
            continue
        ic = _spearman_ic(snap["meta_score"], snap["forward_return_20d"])
        if ic is not None:
            ic_real.append(ic)
    if ic_real:
        arr_real = np.array(ic_real)
        mean_real = arr_real.mean()
        std_real = arr_real.std(ddof=1) if len(arr_real) > 1 else float("nan")
        t_real = mean_real / std_real * np.sqrt(len(arr_real)) if std_real and std_real > 0 else float("nan")
        print(f"  mean_IC={mean_real:+.4f}  t-stat={t_real:+.2f}  N={len(arr_real)} dates "
              f"(thin sample -- interpret with caution)")
    else:
        print(f"  No date in meta_ranking.parquet had >= {MIN_ELIGIBLE} symbols with a matching "
              f"forward_return_20d -- likely too close to the end of history for a full 20d forward window.")
