"""Companion to verify_newey_west_hac.py -- same comparison but on real
project IC series instead of synthetic AR(1) data. Run from repo root.
See docs/reports/scoring/ROBUSTNESS_REPORT.md section 2b.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from src.data.loaders import read_parquet
from statsmodels.regression.linear_model import OLS

def _newey_west_mean_se(y, maxlags):
    n = len(y)
    ybar = y.mean()
    demeaned = y - ybar
    gamma_0 = np.dot(demeaned, demeaned) / n
    variance = gamma_0
    for k in range(1, maxlags + 1):
        if k >= n:
            break
        gamma_k = np.dot(demeaned[k:], demeaned[:-k]) / n
        weight = 1.0 - k / (maxlags + 1)
        variance += 2.0 * weight * gamma_k
    return np.sqrt(variance / n)

df = read_parquet("data/signals/stealth_accumulation_history.parquet")
df["date"] = pd.to_datetime(df["date"])
MIN_ELIGIBLE = 15

def daily_ic_series(df, factor_col, target_col):
    sub = df.dropna(subset=[factor_col, target_col, "date", "symbol"])
    counts = sub.groupby("date").size()
    valid_dates = counts[counts >= MIN_ELIGIBLE].index
    sub = sub[sub["date"].isin(valid_dates)]
    return sub.groupby("date").apply(lambda g: g[factor_col].corr(g[target_col], method="spearman"))

for factor_col in ["realized_vol_20d", "value_ma20", "return_20d"]:
    if factor_col not in df.columns:
        print(factor_col, "not in columns, skipping")
        continue
    ic = daily_ic_series(df, factor_col, "forward_return_20d").dropna()
    y = ic.values
    n = len(y)
    if n < 30:
        continue
    for maxlags in [20]:
        local_se = _newey_west_mean_se(y, maxlags)
        exog = np.ones((n, 1))
        res_hac = OLS(y, exog).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
        sm_se = res_hac.bse[0]
        mean_ic = y.mean()
        local_t = mean_ic / local_se
        sm_t = mean_ic / sm_se
        print(f"factor={factor_col} n={n} maxlags={maxlags} mean_IC={mean_ic:.5f} local_SE={local_se:.6f} sm_SE={sm_se:.6f} local_t={local_t:.4f} sm_t={sm_t:.4f} rel_diff={100*(local_se-sm_se)/sm_se:.4f}%")
