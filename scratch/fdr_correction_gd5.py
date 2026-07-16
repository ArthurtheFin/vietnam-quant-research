"""GD5 NV4 -- Benjamini-Hochberg FDR (q=0.05) applied to the combined
history of t_NW-based factor tests: FACTOR_RETEST_V2 (192 factor x universe
x target combinations, scratch/diagnose_factor_ic_robust.py rerun on current
data) + WATCHLIST_VALIDATION's composite-component IC table (GD4, 38 rows,
34 with a defined t_NW). Two-sided p-value from t_NW via normal
approximation (N~1500 days per test, t-distribution ~ normal at this df).

Scope note: lift/CI-based tests (EVENT_DETECTION_REPORT.md,
DISCLOSURE_EVENT_STUDY_REPORT.md) are NOT included -- different statistical
framework (bootstrap CI on a ratio, not a t-stat/p-value), would need a
separate conversion not attempted here. Scope is explicitly the two t_NW
table sources above; see ROBUSTNESS_REPORT.md for the full accounting.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

Q = 0.05

factor_retest = pd.read_csv("data/output/factor_retest_v2_rerun_gd5.csv")
factor_retest["source"] = "FACTOR_RETEST_V2 (GD5 rerun)"

watchlist_ic = pd.read_csv("data/output/watchlist_validation_ic_main.csv")
watchlist_ic["source"] = "WATCHLIST_VALIDATION (GD4)"
watchlist_ic = watchlist_ic.dropna(subset=["t_NW"])

combined = pd.concat([
    factor_retest[["factor", "universe", "target", "t_NW", "n_days", "source"]],
    watchlist_ic[["factor", "universe", "target", "t_NW", "n_days", "source"]],
], ignore_index=True)
combined = combined.dropna(subset=["t_NW"]).reset_index(drop=True)

combined["p_value"] = 2 * (1 - stats.norm.cdf(combined["t_NW"].abs()))
combined = combined.sort_values("p_value", ascending=True).reset_index(drop=True)
m = len(combined)
combined["rank"] = np.arange(1, m + 1)
combined["bh_threshold"] = combined["rank"] / m * Q
combined["passes_bh_at_rank"] = combined["p_value"] <= combined["bh_threshold"]

# BH procedure: find largest rank k where p_(k) <= (k/m)*q; reject all ranks <= k.
passing_ranks = combined.loc[combined["passes_bh_at_rank"], "rank"]
k = int(passing_ranks.max()) if not passing_ranks.empty else 0
combined["survives_fdr"] = combined["rank"] <= k

combined["passes_manual_t3"] = combined["t_NW"].abs() > 3.0

combined.to_csv("data/output/fdr_correction_gd5.csv", index=False)

print(f"Total tests (m): {m}")
print(f"Manual |t_NW|>3 count: {combined['passes_manual_t3'].sum()}")
print(f"BH-FDR (q=0.05) survivors: {combined['survives_fdr'].sum()} (k={k})")
print()
print("=== BH-FDR survivors ===")
cols = ["factor", "universe", "target", "source", "t_NW", "p_value", "rank", "bh_threshold", "passes_manual_t3"]
print(combined.loc[combined["survives_fdr"], cols].to_string(index=False))
print()
print("=== Manual |t|>3 but NOT BH-FDR survivor (in case of divergence) ===")
divergent_a = combined[combined["passes_manual_t3"] & ~combined["survives_fdr"]]
print(divergent_a[cols].to_string(index=False) if not divergent_a.empty else "(none)")
print()
print("=== BH-FDR survivor but NOT manual |t|>3 (in case of divergence) ===")
divergent_b = combined[~combined["passes_manual_t3"] & combined["survives_fdr"]]
print(divergent_b[cols].to_string(index=False) if not divergent_b.empty else "(none)")
