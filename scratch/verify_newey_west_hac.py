"""Independent verification of _newey_west_mean_se (scratch/diagnose_factor_ic_robust.py
and 5 sibling scripts) against statsmodels, in response to an adversarial
review claiming the HAC standard error formula is wrong.

Imports statsmodels.regression.linear_model.OLS and
statsmodels.stats.sandwich_covariance directly (NOT statsmodels.api, which
fails to import in this environment -- scipy>=1.17 breaks
statsmodels.distributions.discrete, see requirements.txt's note).

Result (2026-07-22): matches to 0.0000% relative difference across 27
synthetic configs (n in {60,120,252}, maxlags in {5,10,20}, AR(1) phi in
{0.0,0.3,0.6}). See docs/reports/scoring/ROBUSTNESS_REPORT.md section 2b
for the real-data companion test and full writeup. Not fixed -- claim did
not hold up.
"""
import numpy as np
import pandas as pd

def _newey_west_mean_se(y: np.ndarray, maxlags: int) -> float:
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

from statsmodels.regression.linear_model import OLS
import statsmodels.stats.sandwich_covariance as sw

def sm_hac_se(y, maxlags):
    n = len(y)
    exog = np.ones((n, 1))
    res = OLS(y, exog).fit()
    # Approach A: fit(cov_type="HAC") -- what the code comment claims matches
    res_hac = OLS(y, exog).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    se_fit_hac = res_hac.bse[0]
    # Approach B: cov_hac_simple with use_correction=False (no small-sample df correction)
    cov_nocorr = sw.cov_hac_simple(res, nlags=maxlags, use_correction=False)
    se_nocorr = np.sqrt(cov_nocorr[0, 0])
    # Approach C: cov_hac_simple with use_correction=True (default)
    cov_corr = sw.cov_hac_simple(res, nlags=maxlags, use_correction=True)
    se_corr = np.sqrt(cov_corr[0, 0])
    return se_fit_hac, se_nocorr, se_corr

rng = np.random.default_rng(42)

print(f"{'n':>5} {'maxlags':>8} {'phi':>6} {'local_SE':>12} {'sm_fit_HAC':>12} {'sm_nocorr':>12} {'sm_corr':>12} {'rel_diff_fitHAC':>16}")
for n in [60, 120, 252]:
    for maxlags in [5, 10, 20]:
        for phi in [0.0, 0.3, 0.6]:
            # AR(1) process with autocorrelation phi, mean 0.02, noise scale 0.05
            eps = rng.normal(0, 0.05, size=n + 200)
            x = np.zeros(n + 200)
            for t in range(1, len(x)):
                x[t] = phi * x[t-1] + eps[t]
            y = 0.02 + x[200:]
            local_se = _newey_west_mean_se(y, maxlags)
            se_fit_hac, se_nocorr, se_corr = sm_hac_se(y, maxlags)
            rel_diff = (local_se - se_fit_hac) / se_fit_hac * 100
            print(f"{n:>5} {maxlags:>8} {phi:>6.1f} {local_se:>12.6f} {se_fit_hac:>12.6f} {se_nocorr:>12.6f} {se_corr:>12.6f} {rel_diff:>15.3f}%")
