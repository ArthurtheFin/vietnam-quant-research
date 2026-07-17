"""NV1 (volatility-cluster examination), follow-up to docs/reports/scoring/docs/reports/scoring/FACTOR_RETEST_V2_REPORT.md's
21/192 passing IC combinations. Before touching deployed scoring
(src/alpha/scoring.py), determine whether these 21 combinations represent
independent signals or one (or a few) underlying signal(s) wearing
different names.

Reuses the exact eligible_full mask and target construction from
scratch/diagnose_factor_ic_robust.py (not re-derived, not re-tuned).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet

df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

MIN_VALUE_MA20 = 3_000_000_000.0

df["eligible_full"] = df["above_ma200"].astype(bool) & (df["value_ma20"].fillna(0) >= MIN_VALUE_MA20)

FACTORS_21 = [
    "atr_pct_14", "realized_vol_20d", "volatility_dryup_score", "dist_kurt_60d",
    "accumulation_score", "tight_range_score", "bb_width", "net_accumulation_score",
    "value_ma20", "liquidity_score", "volatility_support_score", "volatility_percentile",
    "pullback_from_high_20d",
]

PASSING_21 = [
    ("atr_pct_14", "top150", "residualized", -0.0755, -5.76),
    ("atr_pct_14", "full", "residualized", -0.0785, -5.65),
    ("realized_vol_20d", "full", "residualized", -0.0758, -5.41),
    ("realized_vol_20d", "top150", "residualized", -0.0734, -5.41),
    ("volatility_dryup_score", "full", "residualized", +0.0622, +4.97),
    ("volatility_dryup_score", "top150", "residualized", +0.0598, +4.95),
    ("dist_kurt_60d", "full", "residualized", +0.0582, +4.47),
    ("accumulation_score", "top150", "residualized", +0.0551, +4.34),
    ("tight_range_score", "full", "residualized", +0.0485, +3.84),
    ("accumulation_score", "full", "residualized", +0.0516, +3.80),
    ("tight_range_score", "top150", "residualized", +0.0455, +3.68),
    ("dist_kurt_60d", "top150", "residualized", +0.0501, +3.63),
    ("bb_width", "full", "residualized", -0.0409, -3.56),
    ("net_accumulation_score", "top150", "residualized", +0.0444, +3.44),
    ("value_ma20", "full", "residualized", -0.0413, -3.33),
    ("liquidity_score", "full", "residualized", -0.0413, -3.33),
    ("bb_width", "top150", "residualized", -0.0372, -3.22),
    ("volatility_support_score", "full", "residualized", +0.0326, +3.15),
    ("volatility_percentile", "full", "residualized", -0.0355, -3.12),
    ("pullback_from_high_20d", "full", "residualized", +0.0370, +3.11),
    ("net_accumulation_score", "full", "residualized", +0.0413, +3.06),
]

print("=" * 90)
print("STEP 1 -- the 21 passing combinations (all on residualized target -- confirmed below)")
print("=" * 90)
tbl = pd.DataFrame(PASSING_21, columns=["factor", "universe", "target", "mean_IC", "t_NW"])
print(tbl.to_string(index=False, formatters={"mean_IC": "{:+.4f}".format, "t_NW": "{:+.2f}".format}))
n_raw = (tbl["target"] == "raw").sum()
print(f"\nCombinations on RAW target: {n_raw} of 21 -- "
      f"{'signal lives ONLY on residualized target' if n_raw == 0 else 'some survive on raw too'}")
print("Interpretation: since NONE of the 21 pass on the raw target (only after removing "
      "market-beta and sector-mean effects), this is evidence AGAINST a beta-proxy artifact, "
      "not for one -- a pure beta/sector proxy would show up strongest on raw and weaken or "
      "vanish after residualizing, the opposite of what's observed here.")

print("\n" + "=" * 90)
print("STEP 2 -- cross-sectional Spearman correlation between the 13 distinct factors "
      "(eligible_full universe, daily, averaged across days)")
print("=" * 90)

elig = df[df["eligible_full"]]
daily_corrs = {f1: {f2: [] for f2 in FACTORS_21} for f1 in FACTORS_21}
dates = sorted(elig["date"].unique())
for d in dates:
    snap = elig[elig["date"] == d][FACTORS_21]
    if len(snap) < 15:
        continue
    corr = snap.corr(method="spearman")
    for f1 in FACTORS_21:
        for f2 in FACTORS_21:
            v = corr.loc[f1, f2]
            if pd.notna(v):
                daily_corrs[f1][f2].append(v)

avg_corr = pd.DataFrame(
    {f1: {f2: np.mean(daily_corrs[f1][f2]) if daily_corrs[f1][f2] else np.nan for f2 in FACTORS_21} for f1 in FACTORS_21}
)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 20)
print(avg_corr.round(2).to_string())

out_path = "data/full_history_v2/vol_cluster_correlation.csv"
avg_corr.round(4).to_csv(out_path)
print(f"\nSaved to {out_path}")

print("\n" + "=" * 90)
print("STEP 3 -- cluster grouping (|avg cross-sectional Spearman corr| > 0.7)")
print("=" * 90)
high_corr_pairs = []
for i, f1 in enumerate(FACTORS_21):
    for f2 in FACTORS_21[i + 1:]:
        c = avg_corr.loc[f1, f2]
        if pd.notna(c) and abs(c) > 0.7:
            high_corr_pairs.append((f1, f2, c))
high_corr_pairs.sort(key=lambda x: -abs(x[2]))
for f1, f2, c in high_corr_pairs:
    print(f"  {f1:28s} <-> {f2:28s}  corr={c:+.2f}")
print(f"\n{len(high_corr_pairs)} pairs with |corr|>0.7 out of {len(FACTORS_21)*(len(FACTORS_21)-1)//2} total pairs")
