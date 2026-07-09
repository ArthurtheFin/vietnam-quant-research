"""Phase B step 5 (one-off diagnostic, not part of the codebase): (a) rolling
(multi-fold) walk-forward validation of the evidence-based composite score,
and (b) test which risk overlay (stop-loss / regime filter / take-profit)
actually complements it -- recalibrated per fold, not reusing the OLD
momentum-strategy's regime settings which were shown to HURT this new score.

Folds: expanding train window (anchored at the start of history), single
calendar-year test window, rolled forward year by year. Each fold computes
factor IC and weights from TRAIN ONLY, then backtests exclusively on that
fold's TEST year -- the formula never sees test data before being evaluated
on it, and each fold is a materially different market regime (2022 bear,
2023 chop, 2024-2026 recent).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.data.loaders import read_parquet
from src.backtest import run_portfolio_backtest

features_all = read_parquet("data/processed/stock_features.parquet")
features_all["date"] = pd.to_datetime(features_all["date"])
market_all = read_parquet("data/processed/market_features.parquet")
market_all["date"] = pd.to_datetime(market_all["date"])

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


def spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
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


def build_score(features: pd.DataFrame, weights: dict[str, float], signs: dict[str, float]) -> pd.DataFrame:
    df = features[["symbol", "date"] + FACTORS].copy()
    grouped = df.groupby("date")
    total = pd.Series(0.0, index=df.index)
    for name in FACTORS:
        rank = grouped[name].transform(lambda s: (s * signs[name]).rank(pct=True))
        total = total + weights[name] * rank.fillna(0.5)
    df["meta_score"] = total * 100.0
    return df[["symbol", "date", "meta_score"]]


VARIANTS = {
    "plain": {},
    "stop -10%": {"stop_loss_pct": -0.10},
    "stop -15%": {"stop_loss_pct": -0.15},
    "regime full": {"market_regime": "USE_MARKET", "regime_cash_fraction": 1.0},
    "regime partial 0.5": {"market_regime": "USE_MARKET", "regime_cash_fraction": 0.5},
    "take-profit trend-break": {"take_profit_pct": 0.10},
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
        kwargs.update({k: v for k, v in extra_kwargs.items() if k not in ("market_regime",)})
        if extra_kwargs.get("market_regime") == "USE_MARKET":
            kwargs["market_regime"] = test_market
        try:
            r = run_portfolio_backtest(features=test_features, meta_ranking=test_score, **kwargs)
            m = r["metrics"]
            fold_results[variant_name].append({
                "fold": f"{test_start[:4]}", "cagr": m["cagr"], "max_dd": m["max_drawdown"], "sharpe": m["sharpe_ratio"],
            })
        except Exception as exc:
            fold_results[variant_name].append({"fold": f"{test_start[:4]}", "cagr": np.nan, "max_dd": np.nan, "sharpe": np.nan, "error": str(exc)})

print(f"{'Variant':28s} " + " ".join(f"{f[1][:4]:>9s}" for f in FOLDS) + f" {'AvgCAGR':>9s} {'MedCAGR':>9s} {'WinRate':>8s}")
for variant_name, results in fold_results.items():
    cagrs = [r["cagr"] for r in results]
    row = " ".join(f"{c:+9.1%}" if not np.isnan(c) else f"{'ERR':>9s}" for c in cagrs)
    valid = [c for c in cagrs if not np.isnan(c)]
    avg = np.mean(valid) if valid else np.nan
    med = np.median(valid) if valid else np.nan
    win_rate = np.mean([c > 0 for c in valid]) if valid else np.nan
    print(f"{variant_name:28s} {row} {avg:+9.1%} {med:+9.1%} {win_rate:>8.0%}")

print()
print("Per-fold detail (plain variant, no overlay):")
for r in fold_results["plain"]:
    print(f"  {r['fold']}: CAGR={r['cagr']:+.2%}  MaxDD={r['max_dd']:.2%}  Sharpe={r['sharpe']:+.2f}")
