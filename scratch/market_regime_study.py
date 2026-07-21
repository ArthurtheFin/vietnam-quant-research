"""Runs docs/reports/scoring/MARKET_REGIME_PREREG.md exactly once. Every design
choice here (hypotheses, target-variable formulas, period boundaries,
block-bootstrap methodology, PASS/FAIL criteria) was locked in that document
BEFORE this script was written. No tuning after seeing results -- if this
script needs a second run because of a bug, the bug fix is logged, not the
statistical design.

First independent predictive-power test of market_regime/market_entropy_regime
-- previously only used as descriptive filters (e.g. stealth screen's
regime_pass), never IC/predictive tested on their own. Does NOT test
regime x stock-picking (out of scope this round, see prereg).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

SEED = 42
N_BOOT = 2000
BLOCK_SIZE = 20
LAGS = [5, 10, 20]
PERSISTENCE_LAG_FOR_CRITERION = 5
PERSISTENCE_THRESHOLD = 0.60

INDICATORS: dict[str, list[str]] = {
    "market_regime": ["Risk-on", "Neutral", "Risk-off"],
    "market_entropy_regime": ["Structured", "Transitional", "Chaotic"],
}


# ---------------------------------------------------------------------------
# Data loading + target construction
# ---------------------------------------------------------------------------

def load_frame() -> pd.DataFrame:
    market = pd.read_parquet(PROJECT_ROOT / "data/processed/market_features.parquet")
    bench = pd.read_parquet(PROJECT_ROOT / "data/processed/benchmark_vnindex.parquet")
    market["date"] = pd.to_datetime(market["date"])
    bench["date"] = pd.to_datetime(bench["date"])
    bench = bench.sort_values("date").reset_index(drop=True)

    # forward_vol_20d[t] = std(return_1d[t+1..t+20], ddof=1) * sqrt(252) -- forward
    # mirror of add_realized_volatility's trailing convention (src/features/volatility.py).
    r = bench["return_1d"].to_numpy(dtype=float)
    n = len(r)
    fwd_vol = np.full(n, np.nan)
    for i in range(n - 20):
        window = r[i + 1 : i + 21]
        if len(window) == 20 and np.isfinite(window).all():
            fwd_vol[i] = float(np.std(window, ddof=1) * np.sqrt(252))
    bench["forward_vol_20d"] = fwd_vol

    df = market[["date", "market_regime", "market_entropy_regime"]].merge(
        bench[["date", "forward_return_20d", "forward_vol_20d"]], on="date", how="inner"
    )
    df = df.sort_values("date").reset_index(drop=True)
    return df


def assign_periods(df: pd.DataFrame) -> tuple[pd.Series, dict]:
    """Equal-tercile split by row count over the full merged frame -- locked
    in the prereg before any result was seen."""
    n = len(df)
    b1 = n // 3
    b2 = 2 * n // 3
    period = pd.Series("P3", index=df.index)
    period.iloc[:b1] = "P1"
    period.iloc[b1:b2] = "P2"
    boundaries = {
        "P1": (str(df["date"].iloc[0].date()), str(df["date"].iloc[b1 - 1].date()), int(b1)),
        "P2": (str(df["date"].iloc[b1].date()), str(df["date"].iloc[b2 - 1].date()), int(b2 - b1)),
        "P3": (str(df["date"].iloc[b2].date()), str(df["date"].iloc[-1].date()), int(n - b2)),
    }
    return period, boundaries


# ---------------------------------------------------------------------------
# Block bootstrap primitives
# ---------------------------------------------------------------------------

def _circular_block_resample(n: int, block_size: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = int(np.ceil(n / block_size))
    starts = rng.integers(0, n, size=n_blocks)
    idx = np.concatenate([(np.arange(s, s + block_size) % n) for s in starts])
    return idx[:n]


def block_bootstrap_group_diff(
    states: np.ndarray, values: np.ndarray, group_a: str, group_b: str,
    block_size: int = BLOCK_SIZE, n_boot: int = N_BOOT, seed: int = SEED,
) -> np.ndarray:
    n = len(values)
    rng = np.random.default_rng(seed)
    diffs = np.full(n_boot, np.nan)
    for b in range(n_boot):
        idx = _circular_block_resample(n, block_size, rng)
        rs_states = states[idx]
        rs_values = values[idx]
        a_vals = rs_values[rs_states == group_a]
        b_vals = rs_values[rs_states == group_b]
        if len(a_vals) == 0 or len(b_vals) == 0:
            continue
        diffs[b] = a_vals.mean() - b_vals.mean()
    return diffs


def block_bootstrap_mean(
    indicator: np.ndarray, block_size: int = BLOCK_SIZE, n_boot: int = N_BOOT, seed: int = SEED,
) -> np.ndarray:
    n = len(indicator)
    if n == 0:
        return np.full(n_boot, np.nan)
    rng = np.random.default_rng(seed)
    means = np.full(n_boot, np.nan)
    for b in range(n_boot):
        idx = _circular_block_resample(n, block_size, rng)
        means[b] = indicator[idx].mean()
    return means


def ci_from_draws(draws: np.ndarray) -> tuple[float, float]:
    clean = draws[~np.isnan(draws)]
    if len(clean) == 0:
        return (np.nan, np.nan)
    lo, hi = np.percentile(clean, [2.5, 97.5])
    return float(lo), float(hi)


# ---------------------------------------------------------------------------
# H1 / H3 -- group-mean difference tests (vol, return)
# ---------------------------------------------------------------------------

def pairwise_combos(groups: list[str]) -> list[tuple[str, str]]:
    return [(groups[i], groups[j]) for i in range(len(groups)) for j in range(i + 1, len(groups))]


def group_diff_test(sub: pd.DataFrame, indicator_col: str, target_col: str, groups: list[str]) -> dict:
    """Diagnostic ANOVA/KW + locked block-bootstrap CI for every pairwise combo."""
    clean = sub.dropna(subset=[target_col])
    clean = clean[clean[indicator_col].isin(groups)]
    states = clean[indicator_col].to_numpy()
    values = clean[target_col].to_numpy(dtype=float)

    n_per_group = {g: int((states == g).sum()) for g in groups}
    arrays = [values[states == g] for g in groups]
    non_empty = [a for a in arrays if len(a) >= 2]
    if len(non_empty) >= 2:
        f_stat, f_p = stats.f_oneway(*non_empty)
        h_stat, h_p = stats.kruskal(*non_empty)
        anova = {"f_stat": float(f_stat), "p": float(f_p)}
        kw = {"h_stat": float(h_stat), "p": float(h_p)}
    else:
        anova, kw = None, None

    pairs = {}
    for a, b in pairwise_combos(groups):
        if n_per_group.get(a, 0) == 0 or n_per_group.get(b, 0) == 0:
            pairs[f"{a} - {b}"] = {"status": "insufficient_data", "n_a": n_per_group.get(a, 0), "n_b": n_per_group.get(b, 0)}
            continue
        observed = float(values[states == a].mean() - values[states == b].mean())
        draws = block_bootstrap_group_diff(states, values, a, b)
        lo, hi = ci_from_draws(draws)
        pairs[f"{a} - {b}"] = {
            "observed_diff": observed,
            "ci_lo": lo,
            "ci_hi": hi,
            "excludes_zero": bool(lo > 0 or hi < 0) if np.isfinite(lo) and np.isfinite(hi) else False,
            "sign": "+" if observed > 0 else ("-" if observed < 0 else "0"),
            "n_a": n_per_group[a],
            "n_b": n_per_group[b],
        }

    return {
        "n_valid": int(len(clean)),
        "n_per_group": n_per_group,
        "anova": anova,
        "kruskal_wallis": kw,
        "pairs": pairs,
    }


def evaluate_pass_h1_h3(period_results: dict, groups: list[str]) -> dict:
    """PASS if >=1 pair has CI excluding 0 with the SAME sign in ALL 3 periods."""
    combos = pairwise_combos(groups)
    combo_verdicts = {}
    for a, b in combos:
        key = f"{a} - {b}"
        per_period = []
        for p in ("P1", "P2", "P3"):
            entry = period_results[p]["pairs"].get(key, {})
            per_period.append(entry)
        excludes_zero_all = all(e.get("excludes_zero", False) for e in per_period)
        signs = {e.get("sign") for e in per_period}
        same_sign = len(signs) == 1 and "0" not in signs
        combo_verdicts[key] = {
            "excludes_zero_all_3_periods": excludes_zero_all,
            "same_sign_all_3_periods": same_sign,
            "pass": bool(excludes_zero_all and same_sign),
            "per_period": per_period,
        }
    overall_pass = any(v["pass"] for v in combo_verdicts.values())
    return {"overall_pass": overall_pass, "combos": combo_verdicts}


# ---------------------------------------------------------------------------
# H2 -- persistence (direct empirical + Markov cross-check)
# ---------------------------------------------------------------------------

def persistence_indicator_series(states_full: pd.Series, state_x: str, lag: int) -> np.ndarray:
    """indicator[i] = 1.0 if states_full[i]==state_x and states_full[i+lag]==state_x,
    restricted to positions i where states_full[i]==state_x and states_full[i+lag]
    is defined (not NaN/'Unknown'). Positional (trading-day) lag, not calendar-day."""
    n = len(states_full)
    vals = states_full.to_numpy(dtype=object)
    out = []
    for i in range(n - lag):
        if vals[i] != state_x:
            continue
        future = vals[i + lag]
        if future is None or (isinstance(future, float) and np.isnan(future)) or future == "Unknown":
            continue
        out.append(1.0 if future == state_x else 0.0)
    return np.array(out, dtype=float)


def markov_transition_matrix(states_full: pd.Series, groups: list[str]) -> np.ndarray:
    vals = states_full.to_numpy(dtype=object)
    idx = {g: i for i, g in enumerate(groups)}
    counts = np.zeros((len(groups), len(groups)))
    for i in range(len(vals) - 1):
        a, b = vals[i], vals[i + 1]
        if a in idx and b in idx:
            counts[idx[a], idx[b]] += 1
    row_sums = counts.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    return counts / row_sums


def h2_for_scope(states_full: pd.Series, groups: list[str], label: str) -> dict:
    P = markov_transition_matrix(states_full, groups)
    markov_persist_at_lag = {}
    for lag in LAGS:
        Pk = np.linalg.matrix_power(P, lag)
        markov_persist_at_lag[str(lag)] = {g: float(Pk[i, i]) for i, g in enumerate(groups)}

    empirical = {}
    for g in groups:
        empirical[g] = {}
        for lag in LAGS:
            indicator = persistence_indicator_series(states_full, g, lag)
            n_valid = len(indicator)
            point = float(indicator.mean()) if n_valid > 0 else float("nan")
            draws = block_bootstrap_mean(indicator) if n_valid > 0 else np.full(N_BOOT, np.nan)
            lo, hi = ci_from_draws(draws)
            empirical[g][str(lag)] = {"n_valid": n_valid, "point": point, "ci_lo": lo, "ci_hi": hi}

    return {
        "scope": label,
        "transition_matrix": {groups[i]: {groups[j]: float(P[i, j]) for j in range(len(groups))} for i in range(len(groups))},
        "markov_implied_persistence": markov_persist_at_lag,
        "empirical_persistence": empirical,
    }


def evaluate_pass_h2(h2_full_sample: dict, h2_periods: dict, groups: list[str]) -> dict:
    """PASS iff EVERY state has ci_lo > 60% at lag=5, on the full sample AND
    in all 3 periods individually."""
    lag_key = str(PERSISTENCE_LAG_FOR_CRITERION)
    per_state = {}
    for g in groups:
        full_ci_lo = h2_full_sample["empirical_persistence"][g][lag_key]["ci_lo"]
        full_ok = np.isfinite(full_ci_lo) and full_ci_lo > PERSISTENCE_THRESHOLD
        period_oks = {}
        for p in ("P1", "P2", "P3"):
            ci_lo = h2_periods[p]["empirical_persistence"][g][lag_key]["ci_lo"]
            period_oks[p] = bool(np.isfinite(ci_lo) and ci_lo > PERSISTENCE_THRESHOLD)
        state_pass = bool(full_ok and all(period_oks.values()))
        per_state[g] = {"full_sample_ci_lo": full_ci_lo, "full_sample_pass": full_ok, "period_pass": period_oks, "pass": state_pass}
    overall_pass = all(v["pass"] for v in per_state.values())
    return {"overall_pass": overall_pass, "per_state": per_state}


# ---------------------------------------------------------------------------
# BH-FDR (diagnostic, not the locked criterion) -- manual implementation,
# same convention as scratch/fdr_correction_gd5.py.
# ---------------------------------------------------------------------------

def benjamini_hochberg(pvalues: list[float], q: float = 0.05) -> list[bool]:
    m = len(pvalues)
    order = np.argsort(pvalues)
    sorted_p = np.array(pvalues)[order]
    thresh = (np.arange(1, m + 1) / m) * q
    passes_sorted = sorted_p <= thresh
    if passes_sorted.any():
        k = np.max(np.where(passes_sorted)[0]) + 1
    else:
        k = 0
    result = np.zeros(m, dtype=bool)
    result[order[:k]] = True
    return result.tolist()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def n_report(df: pd.DataFrame, period: pd.Series, indicator_col: str, groups: list[str]) -> dict:
    report = {}
    scopes = {"full_sample": df.index}
    for p in ("P1", "P2", "P3"):
        scopes[p] = period.index[period == p]
    for scope_name, idx in scopes.items():
        sub = df.loc[idx]
        raw_counts = sub[indicator_col].value_counts(dropna=False).to_dict()
        valid_vol = sub.dropna(subset=["forward_vol_20d"])
        valid_ret = sub.dropna(subset=["forward_return_20d"])
        report[scope_name] = {
            "n_total": int(len(sub)),
            "raw_counts_by_state": {str(k): int(v) for k, v in raw_counts.items()},
            "n_valid_forward_vol_20d": {g: int((valid_vol[indicator_col] == g).sum()) for g in groups},
            "n_valid_forward_return_20d": {g: int((valid_ret[indicator_col] == g).sum()) for g in groups},
        }
    return report


def main():
    df = load_frame()
    period, boundaries = assign_periods(df)

    print("=== Period boundaries (locked, equal-tercile by row count) ===")
    for p, (start, end, n) in boundaries.items():
        print(f"  {p}: {start} -> {end} (n={n})")

    results = {"boundaries": boundaries, "indicators": {}}

    for indicator_col, groups in INDICATORS.items():
        print(f"\n{'=' * 70}\nIndicator: {indicator_col}\n{'=' * 70}")
        n_rep = n_report(df, period, indicator_col, groups)
        print("\n--- N report (BEFORE any results) ---")
        print(json.dumps(n_rep, indent=2, ensure_ascii=False))

        # H1: forward_vol_20d
        h1_periods = {}
        for p in ("P1", "P2", "P3"):
            sub = df.loc[period.index[period == p]]
            h1_periods[p] = group_diff_test(sub, indicator_col, "forward_vol_20d", groups)
        h1_full = group_diff_test(df, indicator_col, "forward_vol_20d", groups)
        h1_verdict = evaluate_pass_h1_h3(h1_periods, groups)

        # H3: forward_return_20d
        h3_periods = {}
        for p in ("P1", "P2", "P3"):
            sub = df.loc[period.index[period == p]]
            h3_periods[p] = group_diff_test(sub, indicator_col, "forward_return_20d", groups)
        h3_full = group_diff_test(df, indicator_col, "forward_return_20d", groups)
        h3_verdict = evaluate_pass_h1_h3(h3_periods, groups)

        # H2: persistence
        states_full = df[indicator_col]
        h2_full = h2_for_scope(states_full, groups, "full_sample")
        h2_periods = {}
        for p in ("P1", "P2", "P3"):
            sub_states = df.loc[period.index[period == p], indicator_col].reset_index(drop=True)
            h2_periods[p] = h2_for_scope(sub_states, groups, p)
        h2_verdict = evaluate_pass_h2(h2_full, h2_periods, groups)

        results["indicators"][indicator_col] = {
            "n_report": n_rep,
            "h1_volatility": {"full_sample": h1_full, "periods": h1_periods, "verdict": h1_verdict},
            "h2_persistence": {"full_sample": h2_full, "periods": h2_periods, "verdict": h2_verdict},
            "h3_return": {"full_sample": h3_full, "periods": h3_periods, "verdict": h3_verdict},
        }

        print(f"\nH1 (vol) overall_pass: {h1_verdict['overall_pass']}")
        print(f"H2 (persistence) overall_pass: {h2_verdict['overall_pass']}")
        print(f"H3 (return) overall_pass: {h3_verdict['overall_pass']}")

    # BH-FDR across every pairwise CI-based test performed for H1+H3 (diagnostic only)
    pvalue_records = []
    for indicator_col, groups in INDICATORS.items():
        for hyp_key, target_col in (("H1_vol", "forward_vol_20d"), ("H3_return", "forward_return_20d")):
            for p in ("P1", "P2", "P3"):
                sub = df.loc[period.index[period == p]]
                clean = sub.dropna(subset=[target_col])
                clean = clean[clean[indicator_col].isin(groups)]
                states = clean[indicator_col].to_numpy()
                values = clean[target_col].to_numpy(dtype=float)
                for a, b in pairwise_combos(groups):
                    a_vals = values[states == a]
                    b_vals = values[states == b]
                    if len(a_vals) < 2 or len(b_vals) < 2:
                        continue
                    _, p_val = stats.mannwhitneyu(a_vals, b_vals, alternative="two-sided")
                    pvalue_records.append(
                        {"indicator": indicator_col, "hypothesis": hyp_key, "period": p, "pair": f"{a} - {b}", "p_value": float(p_val)}
                    )
    if pvalue_records:
        pvals = [r["p_value"] for r in pvalue_records]
        fdr_flags = benjamini_hochberg(pvals, q=0.05)
        for rec, flag in zip(pvalue_records, fdr_flags):
            rec["survives_fdr_q05"] = bool(flag)
    results["bh_fdr_diagnostic"] = {
        "note": "Mann-Whitney U p-values across all pairwise H1/H3 comparisons, BH-FDR q=0.05 -- diagnostic only, NOT the locked PASS/FAIL criterion (that criterion is the block-bootstrap CI rule in the prereg).",
        "records": pvalue_records,
        "n_survive_fdr": int(sum(r["survives_fdr_q05"] for r in pvalue_records)),
        "n_total": len(pvalue_records),
    }

    git_hash = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True).stdout.strip()
    results["lineage"] = {
        "prereg": "docs/reports/scoring/MARKET_REGIME_PREREG.md",
        "git_commit_at_run": git_hash,
        "seed": SEED,
        "n_boot": N_BOOT,
        "block_size": BLOCK_SIZE,
        "run_date": pd.Timestamp.now().isoformat(),
        "market_features_rows": int(len(df)),
        "market_features_path": "data/processed/market_features.parquet",
        "benchmark_path": "data/processed/benchmark_vnindex.parquet",
    }

    out_path = PROJECT_ROOT / "data/output/market_regime_study_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
