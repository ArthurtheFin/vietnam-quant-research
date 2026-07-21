"""GD5 NV5 -- Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) for
alpha_score v2's standard backtest config, + block-bootstrap CI for
CAGR/Sharpe (reusing src/simulation/bootstrap.py::block_bootstrap_returns
unmodified).

DSR formula:
  DSR = Phi( (SR_hat - SR_0) * sqrt(N-1) / sqrt(1 - g3*SR_hat + (g4-1)/4*SR_hat^2) )
  SR_0 = sqrt(V) * [ (1-gamma_EM)*Phi^-1(1-1/M) + gamma_EM*Phi^-1(1-1/(M*e)) ]

V (variance of Sharpe ratios across the M trials) is not separately available
(no repo tracks a Sharpe ratio per historical trial) -- uses the standard
simplifying assumption V ~= 1/N (each trial's Sharpe under the null, with
N iid returns and true SR=0, has variance ~= 1/N), explicitly disclosed as
an approximation, not a refinement of the formula itself.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.simulation.bootstrap import block_bootstrap_returns

EULER_MASCHERONI = 0.5772156649015329


def compute_v2_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    def _score_day(g):
        vol_score = (1.0 - g["realized_vol_20d"].rank(pct=True, na_option="keep")) * 100.0
        liq_score = (1.0 - g["value_ma20"].rank(pct=True, na_option="keep")) * 100.0
        g["v2_score"] = 0.70 * vol_score.fillna(50.0) + 0.30 * liq_score.fillna(50.0)
        return g

    return out.groupby("date", group_keys=False).apply(_score_day, include_groups=True)


def deflated_sharpe_ratio(daily_returns: np.ndarray, n_trials: int) -> dict:
    n = len(daily_returns)
    sr_hat = daily_returns.mean() / daily_returns.std(ddof=1)
    g3 = stats.skew(daily_returns, bias=False)
    g4 = stats.kurtosis(daily_returns, fisher=False, bias=False)  # non-excess (normal=3)

    v_sr_trials = 1.0 / n  # standard simplifying assumption, see module docstring
    if n_trials > 1:
        sr0 = np.sqrt(v_sr_trials) * (
            (1 - EULER_MASCHERONI) * stats.norm.ppf(1 - 1.0 / n_trials)
            + EULER_MASCHERONI * stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
        )
    else:
        sr0 = 0.0

    denom = np.sqrt(max(1 - g3 * sr_hat + (g4 - 1) / 4 * sr_hat**2, 1e-12))
    z = (sr_hat - sr0) * np.sqrt(n - 1) / denom
    dsr = stats.norm.cdf(z)

    return {
        "n_obs": n, "sr_hat_daily": sr_hat, "sr_hat_annualized": sr_hat * np.sqrt(252),
        "skew": g3, "kurtosis": g4, "n_trials_assumed": n_trials,
        "sr0_threshold_daily": sr0, "z_stat": z, "dsr": dsr,
    }


def main():
    features_all = read_parquet("data/processed/stock_features.parquet")
    features_all["date"] = pd.to_datetime(features_all["date"])
    benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")
    benchmark["date"] = pd.to_datetime(benchmark["date"])
    sector_df = pd.read_csv("config/sector_map.csv")
    sector_map = dict(zip(sector_df["symbol"], sector_df["sector"]))

    print("Computing v2_score on current data...")
    scored = compute_v2_score(features_all)
    v2_meta = scored[["symbol", "date", "v2_score"]].rename(columns={"v2_score": "meta_score"})

    BASE = dict(
        rebalance_period=20, portfolio_size=10, allocation_method="equal_weight",
        transaction_cost_pct=0.0015, initial_nav=1_000_000_000.0,
        min_value_ma20=10_000_000_000, require_above_ma200=True,
        benchmark_features=benchmark, max_per_sector=2, sector_map=sector_map,
    )

    test_start, test_end = pd.Timestamp("2022-01-01"), pd.Timestamp("2026-07-06")
    test_features = features_all[(features_all["date"] >= test_start) & (features_all["date"] <= test_end)].copy()
    test_meta = v2_meta[(v2_meta["date"] >= test_start) & (v2_meta["date"] <= test_end)].copy()

    print("Running standard v2 backtest (single run, current config, 2022-01-01..2026-07-06)...")
    result = run_portfolio_backtest(features=test_features, meta_ranking=test_meta, **BASE)
    metrics = result["metrics"]
    print(f"CAGR={metrics['cagr']:+.2%} Sharpe={metrics.get('sharpe_ratio', float('nan')):.3f} "
          f"MaxDD={metrics.get('max_drawdown', float('nan')):.2%}")

    port_ret = result["portfolio_returns"]
    if isinstance(port_ret, pd.DataFrame):
        ret_col = "return" if "return" in port_ret.columns else port_ret.columns[-1]
        daily_returns = port_ret[ret_col].dropna().to_numpy(dtype=float)
    else:
        daily_returns = pd.Series(port_ret).dropna().to_numpy(dtype=float)
    print(f"Daily return series length: {len(daily_returns)}")

    # Trial count estimate -- see docs/reports/scoring/ROBUSTNESS_REPORT.md for the itemized tally
    # this number is drawn from (report-by-report counts already on record in
    # this repo's own docs, not a fresh count invented here).
    N_TRIALS_ESTIMATE = 560

    dsr_result = deflated_sharpe_ratio(daily_returns, N_TRIALS_ESTIMATE)
    print("\n=== Deflated Sharpe Ratio ===")
    for k, v in dsr_result.items():
        print(f"  {k}: {v}")

    print("\n=== Block bootstrap CI (block=20 trading days, 1000 sims, seed=42) ===")
    n = len(daily_returns)
    sims = block_bootstrap_returns(
        pd.Series(daily_returns), horizon_days=n, block_size=20, n_simulations=1000, random_state=42
    )
    sim_cagr = (1.0 + sims).prod(axis=1) ** (252.0 / n) - 1.0
    sim_sharpe = sims.mean(axis=1) / sims.std(axis=1, ddof=1) * np.sqrt(252)
    cagr_ci = np.percentile(sim_cagr, [2.5, 97.5])
    sharpe_ci = np.percentile(sim_sharpe, [2.5, 97.5])
    print(f"  CAGR point={metrics['cagr']:+.2%}  bootstrap CI=[{cagr_ci[0]:+.2%}, {cagr_ci[1]:+.2%}]")
    print(f"  Sharpe(ann) point={dsr_result['sr_hat_annualized']:.3f}  bootstrap CI=[{sharpe_ci[0]:.3f}, {sharpe_ci[1]:.3f}]")

    out = {
        "metrics": metrics,
        "dsr": dsr_result,
        "bootstrap_cagr_ci": cagr_ci.tolist(),
        "bootstrap_sharpe_ci": sharpe_ci.tolist(),
    }
    import json
    with open("data/output/dsr_bootstrap_v2_gd5.json", "w") as f:
        json.dump(out, f, indent=2, default=str)
    print("\nWritten: data/output/dsr_bootstrap_v2_gd5.json")


if __name__ == "__main__":
    main()
