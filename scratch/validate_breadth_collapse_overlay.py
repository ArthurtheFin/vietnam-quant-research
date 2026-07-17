"""Phase C step 1 (one-off diagnostic, not part of the codebase): does an
EXTREME breadth-collapse trigger (pct_above_ma50 < threshold, far more
extreme than the legacy 0.55 cutoff used by market_regime) protect 2022
without destroying the good years the way the blunt regime filter and the
crash_severity filter both did (see docs/reports/scoring/docs/reports/scoring/STRATEGY_RESEARCH_REPORT.md section 5
and scratch/validate_crash_severity_overlay.py)?

Motivation (see scratch diagnostics run interactively): pct_above_ma50 fell
to EXACTLY 0.0 on 2022-04-27 and stayed there continuously through mid-June
-- 68 days in 2022 vs. 0 days in 2024 and 2026 (the years the validated
score does best), 15 in 2023, 17 in 2025. That's a much rarer, more specific
condition than the legacy 0.55 threshold (which occupies the majority of all
days) or the price-drawdown-based crash_severity tiers (which arrive after
much of the damage, per the report's finding).

Reuses the exact same rolling fold methodology as rolling_walk_forward.py /
validate_crash_severity_overlay.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest
from src.features.breadth import calculate_market_breadth
from src.models.regime import add_market_regime

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
benchmark = read_parquet("data/processed/benchmark_vnindex.parquet")

breadth = calculate_market_breadth(features_all)
market_all = add_market_regime(breadth, benchmark=benchmark)
market_all = market_all.sort_values("date").reset_index(drop=True)

for threshold in (0.05, 0.10, 0.15, 0.20):
    market_all[f"breadth_collapse_{threshold:.2f}"] = np.where(
        market_all["pct_above_ma50"] < threshold, "Risk-off", "Normal"
    )
# Persistence variant: require 3 consecutive days below 0.10 before firing,
# to avoid single-day noise (same spirit as add_market_regime's smoothing).
below_010 = market_all["pct_above_ma50"] < 0.10
market_all["breadth_collapse_0.10_persist3"] = np.where(
    below_010.rolling(3).sum() >= 3, "Risk-off", "Normal"
)

MIN_VALUE_MA20 = 10_000_000_000.0
REBALANCE_PERIOD = 20
FACTORS = ["distance_ma20", "return_20d", "realized_vol_20d"]

FOLDS = [
    ("2021-12-31", "2022-01-01", "2022-12-31"),
    ("2022-12-31", "2023-01-01", "2023-12-31"),
    ("2023-12-31", "2024-01-01", "2024-12-31"),
    ("2024-12-31", "2025-01-01", "2025-12-31"),
    ("2025-12-31", "2026-01-01", "2026-07-06"),
]

BASE = dict(
    rebalance_period=REBALANCE_PERIOD,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
)


def spearman_ic(x, y):
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


def compute_ic(features: pd.DataFrame) -> dict[str, float]:
    all_dates = sorted(features["date"].unique())
    rebalance_dates = all_dates[::REBALANCE_PERIOD]
    records = {name: [] for name in FACTORS}
    for idx, current_date in enumerate(rebalance_dates):
        if idx == 0:
            continue
        decision_date = all_dates[all_dates.index(current_date) - 1]
        snap = features[features["date"] == decision_date].set_index("symbol")
        if snap.empty or "forward_return_20d" not in snap.columns:
            continue
        eligible = snap.copy()
        if "value_ma20" in eligible.columns:
            eligible = eligible[eligible["value_ma20"].fillna(0) >= MIN_VALUE_MA20]
        if "above_ma200" in eligible.columns:
            eligible = eligible[eligible["above_ma200"].astype(bool)]
        if len(eligible) < 15:
            continue
        fwd = eligible["forward_return_20d"]
        for name in FACTORS:
            if name not in eligible.columns:
                continue
            ic = spearman_ic(eligible[name], fwd)
            if ic is not None:
                records[name].append(ic)
    return {name: (np.mean(v) if v else 0.0) for name, v in records.items()}


def build_score(features: pd.DataFrame, weights: dict, signs: dict) -> pd.DataFrame:
    df = features[["symbol", "date"] + FACTORS].copy()
    grouped = df.groupby("date")
    total = pd.Series(0.0, index=df.index)
    for name in FACTORS:
        rank = grouped[name].transform(lambda s: (s * signs[name]).rank(pct=True))
        total = total + weights[name] * rank.fillna(0.5)
    df["meta_score"] = total * 100.0
    return df[["symbol", "date", "meta_score"]]


VARIANTS = {
    "plain (no overlay)": {},
    "take-profit trend-break (current production overlay)": {"take_profit_pct": 0.10},
    "breadth<0.05, full cash": {"regime_col": "breadth_collapse_0.05", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0},
    "breadth<0.10, full cash": {"regime_col": "breadth_collapse_0.10", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0},
    "breadth<0.10, half cash": {"regime_col": "breadth_collapse_0.10", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 0.5},
    "breadth<0.10 persist3, full cash": {"regime_col": "breadth_collapse_0.10_persist3", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0},
    "breadth<0.15, full cash": {"regime_col": "breadth_collapse_0.15", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0},
    "breadth<0.20, full cash": {"regime_col": "breadth_collapse_0.20", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0},
    "breadth<0.10, full cash + take-profit": {"regime_col": "breadth_collapse_0.10", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0, "take_profit_pct": 0.10},
    "breadth<0.10, half cash + take-profit": {"regime_col": "breadth_collapse_0.10", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 0.5, "take_profit_pct": 0.10},
    "breadth<0.10 persist3, full cash + take-profit": {"regime_col": "breadth_collapse_0.10_persist3", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 1.0, "take_profit_pct": 0.10},
    "breadth<0.10 persist3, half cash + take-profit": {"regime_col": "breadth_collapse_0.10_persist3", "risk_off_regimes": ("Risk-off",), "regime_cash_fraction": 0.5, "take_profit_pct": 0.10},
}

fold_results: dict[str, list[dict]] = {name: [] for name in VARIANTS}

for train_end, test_start, test_end in FOLDS:
    train_end_ts, test_start_ts, test_end_ts = pd.Timestamp(train_end), pd.Timestamp(test_start), pd.Timestamp(test_end)
    train_features = features_all[features_all["date"] <= train_end_ts]
    test_features = features_all[(features_all["date"] >= test_start_ts) & (features_all["date"] <= test_end_ts)].copy()
    test_market = market_all[(market_all["date"] >= test_start_ts) & (market_all["date"] <= test_end_ts)].copy()

    train_ic = compute_ic(train_features)
    abs_sum = sum(abs(v) for v in train_ic.values()) or 1.0
    weights = {name: abs(v) / abs_sum for name, v in train_ic.items()}
    signs = {name: (1 if train_ic[name] >= 0 else -1) for name in train_ic}
    test_score = build_score(test_features, weights, signs)

    for variant_name, extra_kwargs in VARIANTS.items():
        kwargs = dict(BASE)
        kwargs.update(extra_kwargs)
        if "regime_col" in kwargs:
            kwargs["market_regime"] = test_market
        try:
            r = run_portfolio_backtest(features=test_features, meta_ranking=test_score, **kwargs)
            m = r["metrics"]
            fold_results[variant_name].append({"fold": test_start[:4], "cagr": m["cagr"], "max_dd": m["max_drawdown"], "sharpe": m["sharpe_ratio"]})
        except Exception as exc:
            fold_results[variant_name].append({"fold": test_start[:4], "cagr": np.nan, "max_dd": np.nan, "sharpe": np.nan})
            print(f"ERROR {variant_name} {test_start}: {exc}")

print(f"{'Variant':55s} " + " ".join(f"{f[1][:4]:>9s}" for f in FOLDS) + f" {'AvgCAGR':>9s} {'MedCAGR':>9s} {'WinRate':>8s}")
for variant_name, results in fold_results.items():
    cagrs = [r["cagr"] for r in results]
    row = " ".join(f"{c:+9.1%}" if not np.isnan(c) else f"{'ERR':>9s}" for c in cagrs)
    valid = [c for c in cagrs if not np.isnan(c)]
    avg = np.mean(valid) if valid else np.nan
    med = np.median(valid) if valid else np.nan
    win_rate = np.mean([c > 0 for c in valid]) if valid else np.nan
    print(f"{variant_name:55s} {row} {avg:+9.1%} {med:+9.1%} {win_rate:>8.0%}")

print("\nDays per fold where pct_above_ma50 < 0.10 (trigger frequency):")
for train_end, test_start, test_end in FOLDS:
    test_start_ts, test_end_ts = pd.Timestamp(test_start), pd.Timestamp(test_end)
    sub = market_all[(market_all["date"] >= test_start_ts) & (market_all["date"] <= test_end_ts)]
    n_trigger = (sub["pct_above_ma50"] < 0.10).sum()
    print(f"  {test_start[:4]}: {n_trigger} / {len(sub)} days")
