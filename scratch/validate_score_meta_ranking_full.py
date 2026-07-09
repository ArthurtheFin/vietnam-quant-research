"""Follow-up to scratch/validate_score_meta_ranking.py: that script could only
test the historically-reconstructable 70% of score_meta_ranking() (momentum +
execution + stealth + risk_penalty), because trade_cards' edge_tier/
profit_factor/stop_loss columns come from a full-sample backtested-edge
lookup (breakout_20d_setup_eligibility.parquet) that looked, on the surface,
impossible to reconstruct per historical date without look-ahead.

This closes that gap: build_trade_cards() (src/reporting/trade_card_pipeline.py)
+ its inputs (ensure_breakout_features, build_non_overlap_entries,
backtest_entries_with_fixed_stop, summarize_trades_by_group,
build_setup_eligibility, build_volatility_rules -- all in
src/backtest/breakout_research.py and src/backtest/simulator.py) can be
called on features TRUNCATED to each historical decision date, since
build_non_overlap_entries already drops any entry whose forward_return_20d
isn't fully realized yet (i.e. entries too close to the truncation date are
naturally excluded, no manual handling needed). This reconstructs a genuine,
walk-forward trade_cards snapshot at each decision date -- no look-ahead,
because eligibility/edge_tier at each date is computed ONLY from breakout
signals and their outcomes that had already fully played out by that date.

Simplification vs. the real production pipeline (src/backtest/breakout_research.py
::run_breakout_research): uses a FIXED -10% stop loss (the same default used
elsewhere in this codebase -- classify_crash_severity's correction threshold,
the take-profit overlay, etc.) instead of the production pipeline's train/
validation stop-loss sweep across 5 stop levels x 3 ATR multiples. That sweep
is itself a separate validated-or-not question (audit I3); out of scope here.
This tests the intended STRUCTURE of score_meta_ranking() (does blending in
a real, non-lookahead trade_cards component change the verdict), not an
exact bit-for-bit replay of the production stop-selection logic.

Per-iteration cost measured at ~13s worst case (full 6-year history) -> ~40
iterations should take a few minutes.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from src.analytics.meta_ranking import prepare_meta_ranking_dataset, score_meta_ranking
from src.backtest import run_portfolio_backtest
from src.backtest.breakout_research import (
    build_setup_eligibility,
    build_volatility_rules,
    ensure_breakout_features,
)
from src.backtest.simulator import backtest_entries_with_fixed_stop, summarize_trades_by_group
from src.data.loaders import read_parquet
from src.reporting.trade_card_pipeline import build_trade_cards

REBALANCE_PERIOD = 20
MIN_VALUE_MA20 = 10_000_000_000.0
MIN_ELIGIBLE = 15
HOLDING_PERIOD = 20
STOP_LOSS = -0.10
COST = 0.004

features_all = read_parquet("data/signals/setup_signals.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
stealth_all = read_parquet("data/signals/stealth_accumulation_history.parquet")
stealth_all["date"] = pd.to_datetime(stealth_all["date"])


def _spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


def build_trade_cards_asof(features_upto: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward reconstruction of breakout_20d_trade_cards.parquet using
    ONLY data available as of the last date in features_upto."""
    prepared = ensure_breakout_features(features_upto)
    entries = prepared.sort_values(["symbol", "date"]).copy()
    from src.backtest.simulator import filter_non_overlapping_signals

    non_overlap = filter_non_overlapping_signals(prepared, signal_col="breakout_20d", holding_period=HOLDING_PERIOD)
    forward_col = f"forward_return_{HOLDING_PERIOD}d"
    if forward_col not in non_overlap.columns:
        return pd.DataFrame()
    non_overlap = non_overlap.dropna(subset=[forward_col]).copy()
    if non_overlap.empty:
        return pd.DataFrame()

    trades = backtest_entries_with_fixed_stop(
        entries_df=non_overlap, price_df=prepared, holding_period=HOLDING_PERIOD, stop_loss=STOP_LOSS, cost=COST
    )
    if trades.empty:
        return pd.DataFrame()

    by_symbol = summarize_trades_by_group(trades, group_col="symbol")
    by_regime = summarize_trades_by_group(trades, group_col="volatility_regime")
    eligibility = build_setup_eligibility(by_symbol, stop_loss=STOP_LOSS, holding_period=HOLDING_PERIOD, cost_assumption=COST)
    vol_rule = build_volatility_rules(by_regime, stop_loss=STOP_LOSS, holding_period=HOLDING_PERIOD)

    return build_trade_cards(features=prepared, eligibility=eligibility, vol_rule=vol_rule, signal_col="breakout_20d", latest_only=True)


all_dates = sorted(features_all["date"].unique())
rebalance_dates = all_dates[::REBALANCE_PERIOD]

ic_records: list[float] = []
history_rows: list[pd.DataFrame] = []
n_with_trade_cards = 0

print(f"Reconstructing FULL score_meta_ranking() (with walk-forward trade_cards) at "
      f"{len(rebalance_dates) - 1} historical decision dates...")
t_start = time.time()

for idx, current_date in enumerate(rebalance_dates):
    if idx == 0:
        continue
    decision_date = all_dates[all_dates.index(current_date) - 1]

    feat_asof = features_all[features_all["date"] <= decision_date]
    stealth_asof = stealth_all[stealth_all["date"] <= decision_date]
    if feat_asof.empty:
        continue

    trade_cards_asof = build_trade_cards_asof(feat_asof)
    if not trade_cards_asof.empty:
        n_with_trade_cards += 1

    prepared = prepare_meta_ranking_dataset(
        features=feat_asof,
        trade_cards=trade_cards_asof if not trade_cards_asof.empty else None,
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

    if idx % 10 == 0:
        print(f"  ...{idx}/{len(rebalance_dates) - 1} dates done, {time.time() - t_start:.0f}s elapsed")

print(f"Done in {time.time() - t_start:.0f}s. Dates with a non-empty reconstructed trade_cards: "
      f"{n_with_trade_cards}/{len(rebalance_dates) - 1}")

arr = np.array(ic_records)
mean_ic = arr.mean() if len(arr) else float("nan")
std_ic = arr.std(ddof=1) if len(arr) > 1 else float("nan")
t_stat = mean_ic / std_ic * np.sqrt(len(arr)) if std_ic and std_ic > 0 else float("nan")
print(f"\n--- FULL score_meta_ranking() (real walk-forward trade_cards) IC vs forward_return_20d, "
      f"{len(arr)} rebalance dates ---")
print(f"  mean_IC={mean_ic:+.4f}  t-stat={t_stat:+.2f}  N={len(arr)}  median={np.median(arr):+.4f}  "
      f"pct_positive={(arr > 0).mean():.0%}")

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


print("\n--- Backtest: FULL reconstructed score_meta_ranking() history ---")
r_real = run_portfolio_backtest(features=features_all, meta_ranking=meta_ranking_history, **BASE)
show("(A) FULL reconstructed score_meta_ranking() (real trade_cards)", r_real)

N_SEEDS = 20
shuffle_cagrs = []
for seed in range(N_SEEDS):
    rng = np.random.default_rng(seed)
    shuf = meta_ranking_history.copy()
    shuf["meta_score"] = shuf.groupby("date")["meta_score"].transform(lambda s: rng.permutation(s.values))
    r = run_portfolio_backtest(features=features_all, meta_ranking=shuf, **BASE)
    shuffle_cagrs.append(r["metrics"]["cagr"])
shuffle_arr = np.array(shuffle_cagrs)
print(f"{'(B) SHUFFLED (avg of ' + str(N_SEEDS) + ' seeds)':65s} "
      f"CAGR={shuffle_arr.mean():+.2%}  std={shuffle_arr.std(ddof=1):.2%}  "
      f"pct_seeds_beaten_by_real={(shuffle_arr < r_real['metrics']['cagr']).mean():.0%}")

FOLDS = [
    ("2022-01-01", "2022-12-31"),
    ("2023-01-01", "2023-12-31"),
    ("2024-01-01", "2024-12-31"),
    ("2025-01-01", "2025-12-31"),
    ("2026-01-01", "2026-07-06"),
]
print("\n--- Rolling per-year fold breakdown (FULL formula, real trade_cards) ---")
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
