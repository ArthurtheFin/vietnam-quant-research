"""GD4 NV2 part 2 -- IC Newey-West test for composite + 7 components + v2_score
+ minimal-watchlist ranking, on the panel written by scratch/watchlist_validation.py.
Reuses daily_ic_series/newey_west_tstat verbatim from scratch/score_v2_ic_test.py.
"""
from __future__ import annotations

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


def daily_ic_series(frame: pd.DataFrame, eligible_col: str, target_col: str, factor_col: str, min_eligible: int = 15) -> pd.Series:
    sub = frame.loc[frame[eligible_col] & frame[target_col].notna() & frame[factor_col].notna(),
                     ["date", target_col, factor_col]]
    counts = sub.groupby("date").size()
    valid_dates = counts[counts >= min_eligible].index
    sub = sub[sub["date"].isin(valid_dates)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("date").apply(lambda g: g[factor_col].corr(g[target_col], method="spearman"), include_groups=False)


def newey_west_tstat(ic_series: pd.Series, maxlags: int = 20):
    ic_series = ic_series.dropna()
    n = len(ic_series)
    if n < 30:
        return np.nan, np.nan, np.nan, n
    y = ic_series.values
    mean_ic = y.mean()
    naive_t = mean_ic / y.std(ddof=1) * np.sqrt(n) if y.std(ddof=1) > 0 else np.nan
    nw_se = _newey_west_mean_se(y, maxlags=maxlags)
    nw_t = mean_ic / nw_se if nw_se > 0 else np.nan
    return mean_ic, naive_t, nw_t, n


def three_period_split(ic_series: pd.Series, maxlags: int = 20):
    ic_series = ic_series.sort_index()
    n = len(ic_series)
    if n < 90:
        return []
    bounds = [ic_series.index[0], ic_series.index[n // 3], ic_series.index[2 * n // 3], ic_series.index[-1]]
    periods = [(bounds[i], bounds[i + 1]) for i in range(3)]
    rows = []
    for i, (p0, p1) in enumerate(periods, start=1):
        seg = ic_series[(ic_series.index >= p0) & (ic_series.index <= p1)]
        mean_ic, _, nw_t, n_seg = newey_west_tstat(seg, maxlags=maxlags)
        rows.append({"period": i, "start": p0, "end": p1, "mean_IC": mean_ic, "t_NW": nw_t, "n": n_seg})
    return rows


def main():
    panel = pd.read_parquet("data/output/watchlist_validation_panel.parquet")
    panel["date"] = pd.to_datetime(panel["date"])

    FACTORS = ["base_final_score", "trend_score", "momentum_score", "relative_strength_score",
               "liquidity_score", "volume_score", "risk_score", "signal_score", "v2_score"]
    UNIVERSES = {
        "full": ("eligible_full", "forward_return_20d", "target_resid_full"),
        "top150": ("eligible_top150", "forward_return_20d", "target_resid_top150"),
    }

    rows = []
    period_rows = []
    for uname, (elig_col, raw_col, resid_col) in UNIVERSES.items():
        for target_label, target_col in [("raw", raw_col), ("residualized", resid_col)]:
            for factor in FACTORS:
                ic_series = daily_ic_series(panel, elig_col, target_col, factor)
                mean_ic, naive_t, nw_t, n = newey_west_tstat(ic_series, maxlags=20)
                rows.append({"factor": factor, "universe": uname, "target": target_label,
                             "mean_IC": mean_ic, "t_naive": naive_t, "t_NW": nw_t, "n_days": n})
                if uname == "full" and target_label == "residualized":
                    for pr in three_period_split(ic_series, maxlags=20):
                        pr.update({"factor": factor})
                        period_rows.append(pr)

    # minimal watchlist ranking: v2_score restricted to minimal_eligible mask
    elig_col, raw_col, resid_col = UNIVERSES["full"]
    for target_label, target_col in [("raw", raw_col), ("residualized", resid_col)]:
        combined_elig = panel[elig_col] & panel["minimal_eligible"].fillna(False)
        panel["_tmp_elig"] = combined_elig
        ic_series = daily_ic_series(panel, "_tmp_elig", target_col, "v2_score")
        mean_ic, naive_t, nw_t, n = newey_west_tstat(ic_series, maxlags=20)
        rows.append({"factor": "v2_score_minimal_watchlist", "universe": "full_minimal_gate", "target": target_label,
                     "mean_IC": mean_ic, "t_naive": naive_t, "t_NW": nw_t, "n_days": n})
        if target_label == "residualized":
            for pr in three_period_split(ic_series, maxlags=20):
                pr.update({"factor": "v2_score_minimal_watchlist"})
                period_rows.append(pr)

    result = pd.DataFrame(rows)
    period_result = pd.DataFrame(period_rows)
    result.to_csv("data/output/watchlist_validation_ic_main.csv", index=False)
    period_result.to_csv("data/output/watchlist_validation_ic_periods.csv", index=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_rows", 100)
    print("=" * 100)
    print("MAIN IC TABLE")
    print("=" * 100)
    print(result.to_string(index=False, formatters={"mean_IC": "{:+.4f}".format, "t_naive": "{:+.2f}".format, "t_NW": "{:+.2f}".format}))
    print("\n" + "=" * 100)
    print("3-PERIOD SPLIT (full universe, residualized target)")
    print("=" * 100)
    print(period_result.to_string(index=False, formatters={"mean_IC": "{:+.4f}".format, "t_NW": "{:+.2f}".format}))


if __name__ == "__main__":
    main()
