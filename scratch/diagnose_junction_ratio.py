"""Round 2, Task 1 of docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md: "constant ratio" signature
test for the HPG/TCB junction anomaly found in the pilot backfill.

Computes ratio = close_pilot / close_existing over the pilot/existing
overlap for HPG, TCB (anomalous) and VPB, SSI, STB (clean controls).
Read-only: data/pilot_backfill/raw/ (already fetched) vs.
data/processed/stock_features.parquet (existing, untouched).
"""
from __future__ import annotations

import pandas as pd

existing = pd.read_parquet("data/processed/stock_features.parquet")
existing["date"] = pd.to_datetime(existing["date"])


def ratio_series(symbol: str) -> pd.DataFrame:
    pilot = pd.read_parquet(f"data/pilot_backfill/raw/{symbol}.parquet")
    pilot["date"] = pd.to_datetime(pilot["date"])
    ex = existing[existing["symbol"] == symbol][["date", "close"]].rename(columns={"close": "close_existing"})
    p = pilot[["date", "close"]].rename(columns={"close": "close_pilot"})
    merged = p.merge(ex, on="date", how="inner").sort_values("date").reset_index(drop=True)
    merged["close_pilot"] = pd.to_numeric(merged["close_pilot"])
    merged["ratio"] = (merged["close_pilot"] / merged["close_existing"]).round(4)
    return merged


print("=== Summary: overlap size and ratio distinctness, all checked symbols ===")
for sym in ["HPG", "TCB", "VPB", "SSI", "STB"]:
    m = ratio_series(sym)
    print(f"{sym}: overlap={len(m)} rows, distinct ratios={m['ratio'].nunique()}, "
          f"range=[{m['ratio'].min():.4f}, {m['ratio'].max():.4f}]")

print("\n=== Step-change dates for the two anomalous symbols ===")
for sym in ["HPG", "TCB"]:
    m = ratio_series(sym)
    m["changed"] = m["ratio"].diff().abs() > 0.0005
    changes = m[m["changed"]]
    print(f"\n{sym}: {len(changes)} step changes, unique ratio levels = {sorted(m['ratio'].unique())}")
    for idx in changes.index:
        print(f"  {m.loc[idx, 'date'].date()}: {m.loc[idx-1, 'ratio']:.4f} -> {m.loc[idx, 'ratio']:.4f}")
