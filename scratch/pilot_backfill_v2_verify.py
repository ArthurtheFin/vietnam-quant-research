"""Task 3 acceptance-gate verification (Round 3, docs/reports/data/docs/reports/data/BACKFILL_DESIGN_REPORT.md).

Compares data/pilot_backfill_v2/raw/ (fetched via the REAL production path,
fetch_symbol_history, post-fix) against data/processed/stock_features.parquet
(existing/current data) and, where useful, against data/pilot_backfill/raw/
(the original Round-1 pilot, pre-fix ad hoc fetch) to confirm the fix didn't
introduce anything new. Reads only; writes nothing back to existing data.

Acceptance gate (from the handoff, must ALL hold to proceed to Task 4):
1. HPG and TCB: exactly 1 distinct ratio value (rounded 4dp) across the full
   pilot-v2/existing overlap.
2. The other 18 symbols: still clean, matching Round 1's pilot results (no
   new anomalies introduced by the fix).
3. No new outlier days caused by the fix itself.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REFERENCE_SYMBOLS = ["HPG", "SSI", "STB", "TCB", "VPB"]
RANDOM_SYMBOLS = ["SVD", "HAS", "PTL", "AG1", "YBM", "VNE", "APG", "LIX", "SRC", "SJD",
                  "LCG", "TVC", "ITD", "HHP", "DGW"]
ALL_SYMBOLS = REFERENCE_SYMBOLS + RANDOM_SYMBOLS


def load(dir_: str, sym: str) -> pd.DataFrame:
    df = pd.read_parquet(Path(dir_) / f"{sym}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    for col in ("open", "high", "low", "close", "volume", "value"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


v2 = {sym: load("data/pilot_backfill_v2/raw", sym) for sym in ALL_SYMBOLS}
v1 = {sym: load("data/pilot_backfill/raw", sym) for sym in ALL_SYMBOLS}

existing = pd.read_parquet("data/processed/stock_features.parquet")
existing["date"] = pd.to_datetime(existing["date"])

bench = pd.read_parquet("data/processed/benchmark_vnindex.parquet")
bench["date"] = pd.to_datetime(bench["date"])
trading_calendar = sorted(bench["date"].unique())
calendar_by_year = pd.Series(trading_calendar).dt.year.value_counts().sort_index()

pd.set_option("display.width", 200)

print("=" * 80)
print("GATE CHECK 1/2 -- generalized junction check (Round 2 design):")
print("ratio = close_v2 / close_existing over full overlap, count distinct rounded(4dp) values")
print("=" * 80)
gate1_pass = True
ratio_rows = []
for sym in ALL_SYMBOLS:
    existing_sym = existing[existing["symbol"] == sym][["date", "close"]].rename(columns={"close": "close_existing"})
    overlap = v2[sym][["date", "close"]].rename(columns={"close": "close_v2"}).merge(existing_sym, on="date", how="inner")
    if overlap.empty:
        print(f"{sym}: NO OVERLAP with existing data (unexpected -- check universe/date range)")
        ratio_rows.append({"symbol": sym, "n_overlap": 0, "n_distinct_ratios": None, "ratios": None})
        continue
    overlap["ratio"] = (overlap["close_v2"] / overlap["close_existing"]).round(4)
    distinct = sorted(overlap["ratio"].unique().tolist())
    n_distinct = len(distinct)
    ratio_rows.append({"symbol": sym, "n_overlap": len(overlap), "n_distinct_ratios": n_distinct, "ratios": distinct})
    flag = ""
    if sym in ("HPG", "TCB"):
        ok = n_distinct == 1 and distinct[0] == 1.0
        flag = "  <-- GATE (must be 1 distinct value = 1.0)" if not ok else "  OK (gate symbol)"
        if not ok:
            gate1_pass = False
    print(f"{sym}: {len(overlap)} overlap rows, {n_distinct} distinct ratio value(s): {distinct}{flag}")

print(f"\nGATE 1 (HPG/TCB exactly 1 distinct ratio @ 1.0): {'PASS' if gate1_pass else 'FAIL'}")

print("\n" + "=" * 80)
print("GATE CHECK 2 -- other 18 symbols still clean (n_distinct_ratios == 1 expected, as in Round 1 controls)")
print("=" * 80)
other18 = [r for r in ratio_rows if r["symbol"] not in ("HPG", "TCB")]
bad_other = [r for r in other18 if r["n_distinct_ratios"] not in (0, 1, None)]
for r in other18:
    status = "OK" if r["n_distinct_ratios"] in (0, 1, None) else "ANOMALY"
    print(f"{r['symbol']}: n_distinct_ratios={r['n_distinct_ratios']} n_overlap={r['n_overlap']}  [{status}]")
gate2_pass = len(bad_other) == 0
print(f"\nGATE 2 (other 18 symbols clean): {'PASS' if gate2_pass else 'FAIL'} -- anomalies: {[r['symbol'] for r in bad_other]}")

print("\n" + "=" * 80)
print("GATE CHECK 3 -- no NEW outlier days introduced by the fix (v2 outliers vs v1 outliers, |return_1d|>20%, close>0 both sides)")
print("=" * 80)


def outlier_days(df: pd.DataFrame) -> set[tuple]:
    d = df.copy()
    d["prev_close"] = d["close"].shift(1)
    valid = (d["close"] > 0) & (d["prev_close"] > 0)
    d["return_1d"] = np.where(valid, d["close"] / d["prev_close"] - 1, np.nan)
    out = d[d["return_1d"].abs() > 0.20]
    return set(zip(out["date"].dt.strftime("%Y-%m-%d"), out["return_1d"].round(4)))


gate3_pass = True
new_outliers_total = 0
for sym in ALL_SYMBOLS:
    o1 = outlier_days(v1[sym])
    o2 = outlier_days(v2[sym])
    new = {d for d in o2 if d[0] not in {x[0] for x in o1}}
    resolved = {d for d in o1 if d[0] not in {x[0] for x in o2}}
    if new:
        gate3_pass = False
        new_outliers_total += len(new)
        print(f"{sym}: {len(o1)} v1 outlier(s), {len(o2)} v2 outlier(s) -- NEW: {sorted(new)}")
    elif o1 or o2:
        print(f"{sym}: {len(o1)} v1 outlier(s), {len(o2)} v2 outlier(s) -- no new outliers"
              f"{f', resolved by fix: {sorted(resolved)}' if resolved else ''}")
print(f"\nGATE 3 (no new outliers from the fix): {'PASS' if gate3_pass else 'FAIL'} -- new outlier days total: {new_outliers_total}")

print("\n" + "=" * 80)
print("INFO -- session coverage (check a) on v2 data, sanity vs Round 1")
print("=" * 80)
rows_a = []
for sym, df in v2.items():
    df_dates = set(df["date"])
    for year, n_sessions in calendar_by_year.items():
        year_calendar = [d for d in trading_calendar if d.year == year]
        n_present = sum(1 for d in year_calendar if d in df_dates)
        pct = n_present / len(year_calendar) if year_calendar else np.nan
        rows_a.append({"symbol": sym, "year": year, "pct": pct})
check_a = pd.DataFrame(rows_a)
pivot_a = check_a.pivot(index="symbol", columns="year", values="pct")
print((pivot_a * 100).round(1).to_string())

print("\n" + "=" * 80)
print("INFO -- quality_flag (chunk_boundary_jump) hits per symbol, with the flagged rows shown")
print("=" * 80)
for sym, df in v2.items():
    flagged = df[df.get("quality_flag").notna()] if "quality_flag" in df.columns else pd.DataFrame()
    if not flagged.empty:
        print(f"\n{sym}: {len(flagged)} flagged row(s)")
        print(flagged[["date", "close", "quality_flag"]].to_string(index=False))

print("\n" + "=" * 80)
print(f"OVERALL GATE: {'PASS -- proceed to Task 4' if (gate1_pass and gate2_pass and gate3_pass) else 'FAIL -- STOP, do not proceed to Task 4'}")
print("=" * 80)
