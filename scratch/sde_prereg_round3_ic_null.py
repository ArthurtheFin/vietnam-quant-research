"""SDE_SCORING_PREREG.md Vòng 3, NV1 -- IC Newey-West + FDR + null test.

Reads data/full_history_v2/sde_round3_panel.parquet (built by
scratch/sde_prereg_round3_panel.py) and runs the EXACT methodology already
locked for final_watchlist.py (WATCHLIST_VALIDATION_PREREG.md): Spearman IC
Newey-West (maxlags=20), full + top150 universe, raw + residualized target,
3-tertile-period split, BH-FDR (q=0.05, scratch/fdr_correction_gd5.py's
convention), 2000-portfolio/fold null test (seed=42) via
run_portfolio_backtest reusing its final_score-priority column lookup.

Objects tested (SDE_SCORING_PREREG.md section 3): final_score, trend,
momentum, relative_strength, risk, liquidity, alpha (CAPM-only, since
backtest evidence was fed {"available": False} at panel-build time -- see
that script's docstring). simulation and market_regime excluded per the
locked reasons in section 3 of the prereg.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.loaders import read_parquet  # noqa: E402
from src.backtest import run_portfolio_backtest  # noqa: E402
from src.validation.trading_status import latest_trading_status  # noqa: E402

SEED = 42
N_ITER = 2000
MAXLAGS = 20
BETA_WINDOW = 250
TOP_N = 150
MIN_ELIGIBLE = 15
Q = 0.05

FACTORS = ["final_score", "sub_trend", "sub_momentum", "sub_relative_strength", "sub_risk", "sub_liquidity", "sub_alpha"]
FACTOR_LABELS = {
    "final_score": "final_score", "sub_trend": "trend", "sub_momentum": "momentum",
    "sub_relative_strength": "relative_strength", "sub_risk": "risk",
    "sub_liquidity": "liquidity", "sub_alpha": "alpha (CAPM-only)",
}


# ---------------------------------------------------------------------------
# Newey-West (verbatim from scratch/score_v2_ic_test.py / diagnose_factor_ic_robust.py)
# ---------------------------------------------------------------------------
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


def newey_west_tstat(ic_series: pd.Series, maxlags: int = MAXLAGS) -> tuple[float, float, float, int]:
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


def zerofill_returns(frame: pd.DataFrame, group_col: str | None, horizon: int = 20) -> pd.DataFrame:
    out = frame.copy()
    ret1d = out["return_1d"].where(~out["suspect_corporate_action"], 0.0)
    grouped = ret1d.groupby(out[group_col]) if group_col else ret1d
    out["return_1d_zf"] = ret1d
    out[f"forward_return_{horizon}d"] = grouped.transform(
        lambda s: (1.0 + s.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    ) if group_col else (1.0 + ret1d.shift(-horizon)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    return out


def sector_demean(frame: pd.DataFrame, value_col: str, eligible_mask: pd.Series) -> pd.Series:
    work = frame.loc[eligible_mask, ["date", "sector", value_col]].copy()
    sector_mean = work.groupby(["date", "sector"])[value_col].transform("mean")
    out = pd.Series(np.nan, index=frame.index)
    out.loc[eligible_mask] = work[value_col] - sector_mean
    return out


def daily_ic_series(frame: pd.DataFrame, eligible_col: str, target_col: str, factor_col: str) -> pd.Series:
    sub = frame.loc[
        frame[eligible_col] & frame[target_col].notna() & frame[factor_col].notna(),
        ["date", target_col, factor_col],
    ]
    counts = sub.groupby("date").size()
    valid_dates = counts[counts >= MIN_ELIGIBLE].index
    sub = sub[sub["date"].isin(valid_dates)]
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.groupby("date").apply(lambda g: g[factor_col].corr(g[target_col], method="spearman"), include_groups=False)


def main() -> None:
    t0 = time.time()
    panel = pd.read_parquet(PROJECT_ROOT / "data/full_history_v2/sde_round3_panel.parquet")
    panel["date"] = pd.to_datetime(panel["date"])
    print(f"SDE panel: {len(panel)} rows, {panel['symbol'].nunique()} symbols, "
          f"{panel['date'].nunique()} dates [{panel['date'].min().date()}..{panel['date'].max().date()}]")

    base = read_parquet("data/processed/stock_features.parquet")
    base["date"] = pd.to_datetime(base["date"])
    base = base.sort_values(["symbol", "date"]).reset_index(drop=True)
    bench = read_parquet("data/processed/benchmark_vnindex.parquet")
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date").reset_index(drop=True)

    base = zerofill_returns(base, "symbol", horizon=20)
    bench = zerofill_returns(bench, None, horizon=20)
    bench_by_date = bench.set_index("date")[["return_1d_zf", "forward_return_20d"]].rename(
        columns={"return_1d_zf": "index_return_1d", "forward_return_20d": "index_forward_return_20d"}
    )
    base = base.merge(bench_by_date, left_on="date", right_index=True, how="left")

    def rolling_beta(group: pd.DataFrame) -> pd.Series:
        cov = group["return_1d_zf"].rolling(BETA_WINDOW, min_periods=100).cov(group["index_return_1d"])
        var = group["index_return_1d"].rolling(BETA_WINDOW, min_periods=100).var()
        return cov / var.replace(0, np.nan)

    base["beta_250d"] = base.groupby("symbol", group_keys=False).apply(rolling_beta, include_groups=False)
    base["market_residual_20d"] = base["forward_return_20d"] - base["beta_250d"] * base["index_forward_return_20d"]

    sector_map_df = pd.read_csv("config/sector_map.csv")[["symbol", "sector"]]
    base = base.merge(sector_map_df, on="symbol", how="left", suffixes=("", "_map"))
    base["sector"] = base["sector"].fillna("UNKNOWN")

    LIQUIDITY_LOOKBACK = 60
    base["median_value_60d"] = base.groupby("symbol")["value"].transform(
        lambda s: s.rolling(LIQUIDITY_LOOKBACK, min_periods=30).median()
    )

    keep_cols = [
        "symbol", "date", "close", "above_ma200", "value_ma20", "sector",
        "market_residual_20d", "forward_return_20d", "median_value_60d",
    ]
    df = panel.merge(base[keep_cols], on=["symbol", "date"], how="inner")
    print(f"Merged panel (SDE score x stock_features): {len(df)} rows")
    if len(df) < len(panel) * 0.5:
        print(f"WARNING: merge dropped {len(panel) - len(df)}/{len(panel)} panel rows -- date/symbol mismatch")

    active_symbols = set(latest_trading_status().loc[lambda d: d["status"] == "ACTIVE", "symbol"])
    df = df[df["symbol"].isin(active_symbols)].reset_index(drop=True)

    # top150 membership computed directly at each of our own rebalance dates
    # (panel dates ARE the rebalance dates -- no forward-carry needed, unlike
    # score_v2_ic_test.py's daily panel).
    df["in_top150"] = False
    for rd, grp in df.groupby("date"):
        top = grp.dropna(subset=["median_value_60d"]).sort_values("median_value_60d", ascending=False).head(TOP_N)["symbol"]
        df.loc[(df["date"] == rd) & (df["symbol"].isin(set(top))), "in_top150"] = True

    df["eligible_full"] = True  # panel is already ACTIVE-only, >=756d history (finding #9)
    df["eligible_top150"] = df["in_top150"]

    df["target_resid_full"] = sector_demean(df, "market_residual_20d", df["eligible_full"] & df["market_residual_20d"].notna())
    df["target_resid_top150"] = sector_demean(df, "market_residual_20d", df["eligible_top150"] & df["market_residual_20d"].notna())

    UNIVERSES = {
        "full": ("eligible_full", "forward_return_20d", "target_resid_full"),
        "top150": ("eligible_top150", "forward_return_20d", "target_resid_top150"),
    }

    # ---- Main IC table --------------------------------------------------
    rows = []
    for uname, (elig_col, raw_col, resid_col) in UNIVERSES.items():
        for target_label, target_col in [("raw", raw_col), ("residualized", resid_col)]:
            for factor in FACTORS:
                ic_series = daily_ic_series(df, elig_col, target_col, factor)
                mean_ic, naive_t, nw_t, n = newey_west_tstat(ic_series)
                rows.append({
                    "factor": FACTOR_LABELS[factor], "universe": uname, "target": target_label,
                    "mean_IC": mean_ic, "t_naive": naive_t, "t_NW": nw_t, "n_days": n,
                })
    main_table = pd.DataFrame(rows)

    # ---- 3-period split (full, residualized) -----------------------------
    period_rows = []
    for factor in FACTORS:
        ic_series = daily_ic_series(df, "eligible_full", "target_resid_full", factor).sort_index()
        n = len(ic_series)
        if n < 30:
            period_rows.append({"factor": FACTOR_LABELS[factor], "period": None, "mean_IC": np.nan, "t_NW": np.nan, "n_days": n})
            continue
        bounds = [ic_series.index[0], ic_series.index[n // 3], ic_series.index[2 * n // 3], ic_series.index[-1]]
        periods = [(bounds[i], bounds[i + 1]) for i in range(3)]
        for i, (p0, p1) in enumerate(periods, start=1):
            seg = ic_series[(ic_series.index >= p0) & (ic_series.index <= p1)]
            mean_ic, _, nw_t, n_seg = newey_west_tstat(seg)
            period_rows.append({
                "factor": FACTOR_LABELS[factor], "period": i, "period_start": p0, "period_end": p1,
                "mean_IC": mean_ic, "t_NW": nw_t, "n_days": n_seg,
            })
    period_table = pd.DataFrame(period_rows)

    # same-sign-across-3-periods flag, full/residualized only (decision-tree input)
    same_sign = {}
    for factor in FACTORS:
        seg = period_table[period_table["factor"] == FACTOR_LABELS[factor]]
        signs = [np.sign(v) if pd.notna(v) else 0 for v in seg["mean_IC"]]
        same_sign[FACTOR_LABELS[factor]] = len(set(signs)) == 1 and len(signs) == 3 and 0 not in signs

    # ---- BH-FDR (scratch/fdr_correction_gd5.py convention) --------------
    fdr = main_table.dropna(subset=["t_NW"]).copy()
    fdr["p_value"] = 2 * (1 - stats.norm.cdf(fdr["t_NW"].abs()))
    fdr = fdr.sort_values("p_value", ascending=True).reset_index(drop=True)
    m = len(fdr)
    fdr["rank"] = np.arange(1, m + 1)
    fdr["bh_threshold"] = fdr["rank"] / m * Q
    fdr["passes_bh_at_rank"] = fdr["p_value"] <= fdr["bh_threshold"]
    passing_ranks = fdr.loc[fdr["passes_bh_at_rank"], "rank"]
    k = int(passing_ranks.max()) if not passing_ranks.empty else 0
    fdr["survives_fdr_q05"] = fdr["rank"] <= k
    fdr["passes_manual_t3"] = fdr["t_NW"].abs() > 3.0

    out_dir = PROJECT_ROOT / "data/full_history_v2"
    main_table.to_csv(out_dir / "sde_round3_ic_main.csv", index=False)
    period_table.to_csv(out_dir / "sde_round3_ic_periods.csv", index=False)
    fdr.to_csv(out_dir / "sde_round3_fdr.csv", index=False)

    pd.set_option("display.width", 160)
    print("\n" + "=" * 100)
    print(f"MAIN IC TABLE (m={m} tests for FDR)")
    print("=" * 100)
    print(main_table.to_string(index=False, formatters={"mean_IC": "{:+.4f}".format, "t_naive": "{:+.2f}".format, "t_NW": "{:+.2f}".format}))

    print("\n" + "=" * 100)
    print("3-PERIOD SPLIT (full universe, residualized target)")
    print("=" * 100)
    print(period_table.to_string(index=False))
    print("\nSame-sign-across-3-periods (full, residualized):")
    for f, v in same_sign.items():
        print(f"  {f}: {v}")

    print("\n" + "=" * 100)
    print(f"BH-FDR (q={Q}), k={k} survivors")
    print("=" * 100)
    print(fdr[["factor", "universe", "target", "t_NW", "p_value", "rank", "bh_threshold", "passes_manual_t3", "survives_fdr_q05"]].to_string(index=False))

    # ---- Decision-tree criterion check for final_score -------------------
    fs_full_resid = main_table[(main_table["factor"] == "final_score") & (main_table["universe"] == "full") & (main_table["target"] == "residualized")]
    fs_t_nw = float(fs_full_resid["t_NW"].iloc[0]) if not fs_full_resid.empty else np.nan
    fs_same_sign = same_sign.get("final_score", False)
    print(f"\nfinal_score: t_NW(full,residualized)={fs_t_nw:+.2f}, same-sign-3-periods={fs_same_sign}"
          f" -> IC criterion (|t_NW|>3 same sign 3 periods): {abs(fs_t_nw) > 3 and fs_same_sign}")

    # ---- Null test: final_score only, 5 folds, seed=42, 2000 iter/fold ---
    print("\n" + "=" * 100)
    print("NULL TEST -- final_score, 2000 random portfolios/fold, seed=42")
    print("=" * 100)

    sector_map = dict(zip(pd.read_csv("config/sector_map.csv")["symbol"], pd.read_csv("config/sector_map.csv")["sector"]))
    features_all = base[base["symbol"].isin(active_symbols)].copy()
    # drop any pre-existing score-name columns to avoid the exact merge
    # collision documented in scratch/watchlist_validation_null.py
    features_all = features_all.drop(columns=[c for c in ["final_score", "meta_score"] if c in features_all.columns])

    # IMPORTANT: run_portfolio_backtest recomputes its OWN rebalance
    # schedule per fold (all_dates[::20] local to that fold's sliced date
    # range), a different phase than this script's global 2020-anchored
    # schedule (`df`/panel). Using `df` here would mean most internally-
    # chosen decision dates have no matching score, silently falling back
    # to the mean-reversion default scorer. Use the fold-aligned panel
    # (scratch/sde_prereg_round3_panel_foldaligned.py) instead, scored at
    # the exact dates this null test will actually query.
    foldaligned_path = PROJECT_ROOT / "data/full_history_v2/sde_round3_panel_foldaligned.parquet"
    meta_full = pd.read_parquet(foldaligned_path)
    meta_full["date"] = pd.to_datetime(meta_full["date"])
    print(f"Fold-aligned score panel: {len(meta_full)} rows, {meta_full['date'].nunique()} dates")

    FOLDS = [
        ("2022-01-01", "2022-12-31"),
        ("2023-01-01", "2023-12-31"),
        ("2024-01-01", "2024-12-31"),
        ("2025-01-01", "2025-12-31"),
        ("2026-01-01", "2026-07-16"),
    ]
    NULL_BASE = dict(
        rebalance_period=20, portfolio_size=10, allocation_method="equal_weight",
        transaction_cost_pct=0.0015, initial_nav=1_000_000_000.0,
        min_value_ma20=10_000_000_000, require_above_ma200=True,
        benchmark_features=bench, max_per_sector=2, sector_map=sector_map,
    )

    rng = np.random.default_rng(SEED)
    null_rows = []
    for test_start, test_end in FOLDS:
        ts, te = pd.Timestamp(test_start), pd.Timestamp(test_end)
        test_features = features_all[(features_all["date"] >= ts) & (features_all["date"] <= te)].copy()
        real_meta = meta_full[(meta_full["date"] >= ts) & (meta_full["date"] <= te)].copy()
        if test_features.empty or real_meta.empty:
            null_rows.append({"fold": test_start[:4], "real_cagr": np.nan, "real_percentile_in_null": np.nan, "n_scored_symbol_dates": len(real_meta)})
            print(f"fold {test_start[:4]}: SKIP (no scored dates in this fold)")
            continue

        real_r = run_portfolio_backtest(features=test_features, meta_ranking=real_meta, **NULL_BASE)
        real_cagr = real_r["metrics"]["cagr"]

        symbols_dates = test_features[["symbol", "date"]].drop_duplicates().reset_index(drop=True)
        null_cagrs = np.empty(N_ITER)
        for i in range(N_ITER):
            rand_meta = symbols_dates.copy()
            rand_meta["final_score"] = rng.random(len(symbols_dates))
            r = run_portfolio_backtest(features=test_features, meta_ranking=rand_meta, **NULL_BASE)
            null_cagrs[i] = r["metrics"]["cagr"]

        percentile = float((null_cagrs < real_cagr).mean() * 100.0)
        pcts = np.percentile(null_cagrs, [5, 25, 50, 75, 95])
        null_rows.append({
            "fold": test_start[:4], "real_cagr": real_cagr,
            "null_p5": pcts[0], "null_p25": pcts[1], "null_p50": pcts[2], "null_p75": pcts[3], "null_p95": pcts[4],
            "real_percentile_in_null": percentile, "n_scored_symbol_dates": len(real_meta),
        })
        print(f"[{time.time()-t0:.0f}s] fold {test_start[:4]}: real_cagr={real_cagr:+.1%} percentile={percentile:.1f} n_scored={len(real_meta)}")
        sys.stdout.flush()

    null_result = pd.DataFrame(null_rows)
    null_result.to_csv(out_dir / "sde_round3_null_test.csv", index=False)
    print("\n" + "=" * 100)
    print("NULL TEST SUMMARY")
    print("=" * 100)
    print(null_result.to_string(index=False))
    valid = null_result.dropna(subset=["real_percentile_in_null"])
    avg_pctile = valid["real_percentile_in_null"].mean() if not valid.empty else np.nan
    any_below_10 = bool((valid["real_percentile_in_null"] < 10).any()) if not valid.empty else True
    print(f"\nAverage percentile: {avg_pctile:.1f}" if pd.notna(avg_pctile) else "\nAverage percentile: N/A (no valid folds)")
    print(f"Any fold < 10th percentile: {any_below_10}")
    null_criterion = pd.notna(avg_pctile) and avg_pctile > 60 and not any_below_10
    print(f"Null-test criterion (percentile avg>60, no fold<10): {null_criterion}")

    print(f"\nfinal_score Branch-A criterion overall (IC OR null): "
          f"{(abs(fs_t_nw) > 3 and fs_same_sign) or null_criterion}")

    print(f"\n[{time.time()-t0:.0f}s] all done")


if __name__ == "__main__":
    main()
