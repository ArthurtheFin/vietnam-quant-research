"""docs/reports/scoring/SCORE_FORENSIC_REPORT.md NV2: forensic on fold 2026, the disaster fold
(docs/reports/scoring/CONCENTRATION_ANALYSIS_REPORT.md null test: percentile 0.4/2000 -- the
score actively picked worse than a random draw from the same eligible
universe). Uses portfolio_size=5 explicitly (matching the exact
configuration that was diagnosed there and in docs/reports/scoring/FOLD_AUTOPSY_REPORT.md),
NOT the new size=10 default just applied in NV1 of this round -- this
investigation is about why THAT diagnosed result happened.

Note on terminology: the user's brief mentions "accumulation/stealth
score" as a component -- that's from a DIFFERENT scoring system
(src/screening/stealth_accumulation.py), not part of alpha_score
(src/alpha/scoring.py), which is the actual composite tested in every
null-test/fold-autopsy round this session (the one at percentile 0.4 in
2026). Decomposing the real thing instead: momentum_score, rs_score,
trend_score, volume_score, volatility_score, liquidity_score (see
src/alpha/scoring.py's calculate_alpha_scores).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.alpha.scoring import calculate_alpha_scores

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
benchmark["date"] = pd.to_datetime(benchmark["date"])

COMPONENTS = ["momentum_score", "rs_score", "trend_score", "volume_score", "volatility_score", "liquidity_score"]

print("Computing deployed alpha_score + components...")
scored = calculate_alpha_scores(features_all, benchmark)
meta = scored[["symbol", "date", "alpha_score"]].rename(columns={"alpha_score": "meta_score"})

BASE = dict(
    rebalance_period=20,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
    benchmark_features=benchmark,
)

test_start_ts, test_end_ts = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-07-06")
test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
test_meta = meta[(meta["date"] >= test_start_ts) & (meta["date"] <= test_end_ts)].copy()

r = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **BASE)
buys = r["trades_log"]
buys = buys[buys["type"] == "BUY"].copy()

print("\n" + "=" * 100)
print("STEP 1 -- every stock the system selected in 2026, per rebalance, with decision-date score decomposition")
print("=" * 100)

scored_idx = scored.set_index(["symbol", "date"])
rebalance_dates = sorted(buys["date"].unique())
holding_rows = []
for i, exec_date in enumerate(rebalance_dates):
    exec_ts = pd.Timestamp(exec_date)
    # decision date = prior trading day (T-1 rule, matches the engine)
    all_dates_sorted = sorted(features_all["date"].unique())
    exec_idx = all_dates_sorted.index(exec_ts)
    decision_date = all_dates_sorted[exec_idx - 1]
    next_exec_date = pd.Timestamp(rebalance_dates[i + 1]) if i + 1 < len(rebalance_dates) else test_end_ts

    syms = buys[buys["date"] == exec_date]["symbol"].tolist()
    for sym in syms:
        try:
            row = scored_idx.loc[(sym, decision_date)]
        except KeyError:
            continue
        # holding-period return: exec_date close -> next rebalance's decision date close
        seg = features_all[(features_all["symbol"] == sym) & (features_all["date"] > exec_ts) & (features_all["date"] <= next_exec_date)]
        hold_ret = (1.0 + seg["return_1d"].fillna(0.0)).prod() - 1.0 if not seg.empty else np.nan
        holding_rows.append({
            "rebalance": exec_date, "symbol": sym, "hold_ret": hold_ret,
            "alpha_score": row.get("alpha_score"), **{c: row.get(c) for c in COMPONENTS},
        })

decomp = pd.DataFrame(holding_rows)
decomp.to_csv("data/full_history_v2/score_forensic_2026_decomposition.csv", index=False)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)
print(decomp.to_string(index=False, formatters={
    "hold_ret": "{:+.1%}".format, "alpha_score": "{:.1f}".format,
    **{c: "{:.1f}".format for c in COMPONENTS},
}))

# which component was highest (most responsible for the top rank) per pick
decomp["top_component"] = decomp[COMPONENTS].idxmax(axis=1)
print("\nWhich component was each pick's highest-scoring one (i.e. drove it up most):")
print(decomp["top_component"].value_counts().to_string())

print("\n" + "=" * 100)
print("STEP 2 -- cross-sectional Spearman IC of alpha_score AND each component vs forward_return_20d")
print("2026 fold vs. 2023-2025 (the non-disaster comparison window)")
print("=" * 100)

MIN_ELIGIBLE = 15
scored["eligible"] = scored["above_ma200"].astype(bool) & (scored["value_ma20"].fillna(0) >= 10_000_000_000.0)


def period_ic(df: pd.DataFrame, start: str, end: str, col: str) -> tuple[float, int]:
    sub = df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end)) & df["eligible"]]
    sub = sub[[col, "forward_return_20d"]].dropna()
    if sub.empty:
        return np.nan, 0
    daily = df.loc[sub.index].groupby(df.loc[sub.index, "date"]).apply(
        lambda g: g[col].corr(g["forward_return_20d"], method="spearman") if len(g) >= MIN_ELIGIBLE else np.nan,
        include_groups=False,
    )
    daily = daily.dropna()
    return (daily.mean() if not daily.empty else np.nan), len(daily)


rows_ic = []
for col in ["alpha_score"] + COMPONENTS:
    ic_2026, n_2026 = period_ic(scored, "2026-01-01", "2026-07-06", col)
    ic_2023_25, n_2325 = period_ic(scored, "2023-01-01", "2025-12-31", col)
    rows_ic.append({
        "factor": col, "IC_2026": ic_2026, "n_days_2026": n_2026,
        "IC_2023_2025": ic_2023_25, "n_days_2023_2025": n_2325,
        "flipped_sign": bool(pd.notna(ic_2026) and pd.notna(ic_2023_25) and np.sign(ic_2026) != np.sign(ic_2023_25)),
    })
ic_table = pd.DataFrame(rows_ic).sort_values("IC_2026")
print(ic_table.to_string(index=False, formatters={"IC_2026": "{:+.4f}".format, "IC_2023_2025": "{:+.4f}".format}))

print("\n" + "=" * 100)
print("STEP 3 -- momentum_score hypothesis test: high-momentum cohort vs low-momentum cohort, 2026 eligible universe")
print("(alpha_score has no 'accumulation_score' component -- momentum_score/rs_score are the closest analogues, "
      "since both reward recent price strength the way an accumulation-style score would)")
print("=" * 100)

for col in ["momentum_score", "rs_score"]:
    sub = scored[(scored["date"] >= pd.Timestamp("2026-01-01")) & (scored["date"] <= pd.Timestamp("2026-07-06")) & scored["eligible"]]
    sub = sub[[col, "forward_return_20d"]].dropna()
    sub["decile"] = pd.qcut(sub[col], 10, labels=False, duplicates="drop")
    top_decile_ret = sub[sub["decile"] == sub["decile"].max()]["forward_return_20d"].mean()
    bottom_decile_ret = sub[sub["decile"] == sub["decile"].min()]["forward_return_20d"].mean()
    print(f"{col}: top-decile avg forward_return_20d={top_decile_ret:+.2%}  "
          f"bottom-decile avg forward_return_20d={bottom_decile_ret:+.2%}  "
          f"(N={len(sub)} eligible symbol-days in 2026)")

print("\ndone")
