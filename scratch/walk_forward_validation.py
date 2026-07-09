"""Phase B step 4 (one-off diagnostic, not part of the codebase): walk-forward
validation of the evidence-based composite score.

TRAIN (2020-01-01 .. 2023-12-31): compute factor IC, derive weights from
   TRAIN IC only (never look at TEST data to build the formula).
TEST (2024-01-01 .. 2026-07-06): held-out, never used to build the formula.
   Compute IC of the TRAIN-derived factors on TEST data, and backtest the
   TRAIN-derived composite score restricted to TEST dates only.

If the TRAIN-derived formula still shows real IC and a real backtest edge on
TEST, that is genuine walk-forward evidence, not curve-fitting to the whole
history (which was the honest caveat on the prior in-sample result).
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

TRAIN_END = pd.Timestamp("2023-12-31")
TEST_START = pd.Timestamp("2024-01-01")

MIN_VALUE_MA20 = 10_000_000_000.0
REBALANCE_PERIOD = 20

FACTORS = ["distance_ma20", "return_20d", "realized_vol_20d"]


def spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    both = pd.concat([x, y], axis=1).dropna()
    if len(both) < 10:
        return None
    return both.iloc[:, 0].corr(both.iloc[:, 1], method="spearman")


def compute_ic_table(features: pd.DataFrame) -> dict[str, list[float]]:
    """IC of the RAW column (no sign flip) vs forward_return_20d. A negative
    mean IC means high raw values predict LOW forward returns (factor should
    be used inverted); positive means high raw values predict HIGH forward
    returns (factor should be used as-is). Sign convention is resolved once,
    downstream, from this raw IC -- never pre-flipped here."""
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
    return records


def print_ic_table(label: str, records: dict[str, list[float]]) -> dict[str, float]:
    print(f"\n--- {label} ---")
    mean_ics = {}
    for name, values in records.items():
        if not values:
            print(f"  {name:25s} (no data)")
            continue
        arr = np.array(values)
        mean_ic = arr.mean()
        std_ic = arr.std(ddof=1) if len(arr) > 1 else np.nan
        t_stat = mean_ic / std_ic * np.sqrt(len(arr)) if std_ic and std_ic > 0 else np.nan
        print(f"  {name:25s} mean_IC={mean_ic:+.4f}  t-stat={t_stat:+.2f}  N={len(arr)}")
        mean_ics[name] = mean_ic
    return mean_ics


# --- TRAIN: derive weights from TRAIN IC only ---
train_features = features_all[features_all["date"] <= TRAIN_END].copy()
train_ic = compute_ic_table(train_features)
train_mean_ic = print_ic_table("TRAIN (2020-01-01 .. 2023-12-31)", train_ic)

abs_sum = sum(abs(v) for v in train_mean_ic.values())
weights = {name: abs(v) / abs_sum for name, v in train_mean_ic.items()}
signs = {name: (1 if train_mean_ic[name] >= 0 else -1) for name in train_mean_ic}
print("\nTRAIN-derived weights (proportional to |train IC|, sign fixed by train IC direction):")
for name in weights:
    print(f"  {name:25s} weight={weights[name]:.3f}  sign={signs[name]:+d}")

# --- TEST: check IC out-of-sample (never touched during weight derivation) ---
test_features = features_all[features_all["date"] >= TEST_START].copy()
test_ic = compute_ic_table(test_features)
print_ic_table("TEST (2024-01-01 .. 2026-07-06) -- held out, unseen during weight derivation", test_ic)


def build_score(features: pd.DataFrame) -> pd.DataFrame:
    df = features[["symbol", "date"] + FACTORS].copy()
    grouped = df.groupby("date")
    total = pd.Series(0.0, index=df.index)
    for name in FACTORS:
        # signs[name] = sign of the RAW column's TRAIN IC (+1 or -1); applied
        # directly to the raw column here -- single source of truth, no
        # double-flipping between IC computation and score construction.
        rank = grouped[name].transform(lambda s: (s * signs[name]).rank(pct=True))
        total = total + weights[name] * rank.fillna(0.5)
    df["meta_score"] = total * 100.0
    return df[["symbol", "date", "meta_score"]]


BASE = dict(
    rebalance_period=REBALANCE_PERIOD,
    portfolio_size=5,
    allocation_method="equal_weight",
    transaction_cost_pct=0.0015,
    initial_nav=1_000_000_000.0,
    min_value_ma20=10_000_000_000,
    require_above_ma200=True,
)


def show(name, r):
    m = r["metrics"]
    print(f"{name:60s} CAGR={m['cagr']:+.2%}  MaxDD={m['max_drawdown']:.2%}  Sharpe={m['sharpe_ratio']:+.2f}  final={m['final_nav']:,.0f}")


print("\n--- Out-of-sample backtest: TRAIN-derived formula, TEST period only ---")
test_score = build_score(test_features)
r_test = run_portfolio_backtest(features=test_features, meta_ranking=test_score, **BASE)
show("(A) TRAIN-derived formula, backtested on TEST period only", r_test)

# Shuffle check on the TEST-period backtest too
shuffle_cagrs = []
for seed in range(5):
    rng = np.random.default_rng(seed)
    shuf = test_score.copy()
    shuf["meta_score"] = shuf.groupby("date")["meta_score"].transform(lambda s: rng.permutation(s.values))
    r = run_portfolio_backtest(features=test_features, meta_ranking=shuf, **BASE)
    shuffle_cagrs.append(r["metrics"]["cagr"])
print(f"{'(B) SHUFFLED formula, same TEST period (avg of 5 seeds)':60s} CAGR={np.mean(shuffle_cagrs):+.2%}  (individual: {[f'{c:+.2%}' for c in shuffle_cagrs]})")

# Reference: old fallback formula on the SAME test period, for apples-to-apples
r_baseline_test = run_portfolio_backtest(
    features=test_features,
    meta_ranking=pd.DataFrame(columns=["symbol", "date", "meta_score"]),
    **BASE,
)
show("(C) Old fallback formula, same TEST period (reference)", r_baseline_test)
