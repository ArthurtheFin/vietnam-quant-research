"""Verification checks for the pilot backfill (Task 3 of docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md).
Reads only from data/pilot_backfill/raw/ and existing data/processed/ +
data/processed/benchmark_vnindex.parquet for comparison; writes nothing back
to existing data.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REFERENCE_SYMBOLS = ["HPG", "SSI", "STB", "TCB", "VPB"]
RANDOM_SYMBOLS = ["SVD", "HAS", "PTL", "AG1", "YBM", "VNE", "APG", "LIX", "SRC", "SJD",
                  "LCG", "TVC", "ITD", "HHP", "DGW"]
ALL_SYMBOLS = REFERENCE_SYMBOLS + RANDOM_SYMBOLS

pilot = {}
for sym in ALL_SYMBOLS:
    path = Path(f"data/pilot_backfill/raw/{sym}.parquet")
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume", "value"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    pilot[sym] = df.sort_values("date").reset_index(drop=True)

existing = pd.read_parquet("data/processed/stock_features.parquet")
existing["date"] = pd.to_datetime(existing["date"])

bench = pd.read_parquet("data/processed/benchmark_vnindex.parquet")
bench["date"] = pd.to_datetime(bench["date"])
trading_calendar = sorted(bench["date"].unique())
calendar_by_year = pd.Series(trading_calendar).dt.year.value_counts().sort_index()

print("=" * 80)
print("CHECK (a) -- % of sessions with data vs HOSE/HNX trading calendar (VNINDEX proxy)")
print("=" * 80)
rows_a = []
for sym, df in pilot.items():
    df_dates = set(df["date"])
    for year, n_sessions in calendar_by_year.items():
        year_calendar = [d for d in trading_calendar if d.year == year]
        n_present = sum(1 for d in year_calendar if d in df_dates)
        pct = n_present / len(year_calendar) if year_calendar else np.nan
        rows_a.append({"symbol": sym, "year": year, "pct_sessions_present": pct, "n_calendar": len(year_calendar)})
check_a = pd.DataFrame(rows_a)
pivot_a = check_a.pivot(index="symbol", columns="year", values="pct_sessions_present")
pd.set_option("display.width", 200)
print((pivot_a * 100).round(1).to_string())

print("\n" + "=" * 80)
print("CHECK (b) -- junction continuity: pilot's last pre-junction close vs existing data's first close")
print("=" * 80)
for sym, df in pilot.items():
    existing_sym = existing[existing["symbol"] == sym].sort_values("date")
    if existing_sym.empty:
        print(f"{sym}: no existing data at all -- nothing to junction against (pure new coverage)")
        continue
    junction_date = existing_sym["date"].min()
    existing_first_close = existing_sym.iloc[0]["close"]
    pre_junction = df[df["date"] < junction_date]
    if pre_junction.empty:
        # VPB-style: pilot and existing overlap from the start; compare full-overlap agreement instead
        overlap = df.merge(existing_sym[["date", "close"]], on="date", suffixes=("_pilot", "_existing"))
        if overlap.empty:
            print(f"{sym}: no pre-junction pilot rows and no overlap -- unexpected")
            continue
        diff = (overlap["close_pilot"] - overlap["close_existing"]).abs()
        rel_diff = (diff / overlap["close_existing"].replace(0, np.nan)).abs()
        print(f"{sym}: FULL OVERLAP (already had full history) -- {len(overlap)} rows compared, "
              f"max abs close diff={diff.max():.4f}, max relative diff={rel_diff.max():.4%}")
        continue
    pilot_last_pre = pre_junction.iloc[-1]
    day_gap = (junction_date - pilot_last_pre["date"]).days
    pct_change = existing_first_close / pilot_last_pre["close"] - 1
    print(f"{sym}: junction at {junction_date.date()}  |  pilot last pre-junction date="
          f"{pilot_last_pre['date'].date()} close={pilot_last_pre['close']:.0f}  |  "
          f"existing first close={existing_first_close:.0f}  |  calendar gap={day_gap}d  |  "
          f"pct change across junction={pct_change:+.2%}")

print("\n" + "=" * 80)
print("CHECK (c) -- magnitude sanity: HPG/SSI/STB/TCB average traded value by month, 2021 (VND)")
print("=" * 80)
for sym in ["HPG", "SSI", "STB", "TCB"]:
    df = pilot[sym]
    y2021 = df[df["date"].dt.year == 2021].copy()
    y2021["month"] = y2021["date"].dt.month
    monthly = y2021.groupby("month")["value"].mean()
    print(f"\n{sym} 2021 monthly avg traded value:")
    print(monthly.apply(lambda x: f"{x/1e9:,.1f}B VND").to_string())
    print(f"  {sym} 2021 overall mean: {y2021['value'].mean()/1e9:,.1f}B VND/day, "
          f"median: {y2021['value'].median()/1e9:,.1f}B VND/day")

print("\n" + "=" * 80)
print("CHECK (d) -- 1-day return outliers > |20%| (unadjusted; HOSE/HNX band is ~7%, so these flag likely unadjusted corp actions)")
print("=" * 80)
total_outliers = 0
for sym, df in pilot.items():
    df = df.copy()
    df["return_1d"] = df["close"].pct_change()
    outliers = df[df["return_1d"].abs() > 0.20]
    total_outliers += len(outliers)
    if not outliers.empty:
        print(f"\n{sym}: {len(outliers)} outlier day(s)")
        print(outliers[["date", "close", "return_1d"]].assign(
            return_1d=lambda d: d["return_1d"].map(lambda x: f"{x:+.1%}")
        ).to_string(index=False))
print(f"\nTotal outlier days across all 20 symbols: {total_outliers} "
      f"(these need corp-action adjustment before use, same as the existing G4 pipeline handles)")
