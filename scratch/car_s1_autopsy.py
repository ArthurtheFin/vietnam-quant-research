"""EXPLORATORY -- descriptive-only autopsy of S1 (insider/related buy
registration) CAR, cut by registration size vs ADV, registrant role,
same-symbol multi-insider clustering, and a liquidity/size proxy (no
market-cap data available in this pipeline -- see note below).

NO confidence intervals, NO significance test, NO pass/fail language.
Purpose: surface cuts worth a real pre-registered test in a future round,
nothing more. Reuses cluster_events/compute_car from
scratch/disclosure_event_study.py -- no new statistical methodology.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scratch.disclosure_event_study import (
    CAR_CLUSTER_GAP_DAYS,
    CAR_HORIZONS,
    build_eligible_panel,
    cluster_events,
    compute_car,
    load_market_holidays,
    load_price_panel,
)

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)


def load_s1_events_full(events_all: pd.DataFrame, holidays: set) -> pd.DataFrame:
    from src.data.disclosure_parser import next_trading_day  # noqa: F401 (parity with disclosure_event_study's lag=1 default)

    mask = (events_all["event_type"] == "insider_registration") & (events_all["direction"] == "buy")
    cols = ["symbol", "person_name", "person_role", "shares_registered_or_changed", "disclosure_date", "is_backfilled", "available_at"]
    sub = events_all.loc[mask, cols].copy()
    sub["available_at"] = pd.to_datetime(sub["available_at"])
    return sub.dropna(subset=["available_at"])


def assign_day_idx(df: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    td_values = trading_days.values
    out = df.copy()
    out["day_idx"] = out["available_at"].apply(lambda t: int(np.searchsorted(td_values, np.datetime64(t), side="left")))
    return out


def count_distinct_insiders_in_window(clustered: pd.DataFrame, raw_s1: pd.DataFrame, window: int = 20) -> pd.Series:
    """For each clustered (kept) event, count distinct person_name among ALL
    raw S1 events of the same symbol whose day_idx falls in
    [kept_day_idx, kept_day_idx + window) -- i.e. what cluster_events already
    merged into this kept row, made explicit for the autopsy."""
    raw_by_symbol = {s: g for s, g in raw_s1.groupby("symbol")}
    counts = []
    for _, row in clustered.iterrows():
        grp = raw_by_symbol.get(row["symbol"])
        if grp is None:
            counts.append(1)
            continue
        in_window = grp[(grp["day_idx"] >= row["day_idx"]) & (grp["day_idx"] < row["day_idx"] + window)]
        counts.append(in_window["person_name"].nunique())
    return pd.Series(counts, index=clustered.index)


ROLE_GROUPS = {
    "HĐQT (Chủ tịch/Thành viên)": ["chủ tịch hđqt", "thành viên hđqt", "phó chủ tịch hđqt", "thành viên hđqt độc lập", "thành viên hội đồng quản trị"],
    "Ban điều hành (TGĐ/Phó TGĐ/KTT/GĐTC)": ["tổng giám đốc", "phó tổng gđ", "phó tổng giám đốc", "kế toán trưởng", "giám đốc tài chính", "giám đốc"],
    "Ban kiểm soát": ["ban kiểm soát", "bks"],
    "Người liên quan (gia đình)": ["con", "vợ", "chồng", "em", "mẹ", "cha", "bố", "anh", "chị", "con gái", "con trai"],
    "Quản trị/Công bố thông tin": ["công bố thông tin", "phụ trách quản trị", "người phụ trách"],
}


def group_role(raw_role: str) -> str:
    r = (raw_role or "").strip().lower()
    if not r:
        return "Không ghi rõ"
    for group_name, keywords in ROLE_GROUPS.items():
        if any(kw == r or kw in r for kw in keywords):
            return group_name
    return "Khác"


def describe_by_cut(df: pd.DataFrame, cut_col: str, car_col: str) -> pd.DataFrame:
    rows = []
    for level, grp in df.groupby(cut_col, observed=True):
        s = grp[car_col].dropna()
        if s.empty:
            continue
        rows.append({
            "cut": level,
            "n": len(s),
            "p10": s.quantile(0.10),
            "p25": s.quantile(0.25),
            "median": s.quantile(0.50),
            "p75": s.quantile(0.75),
            "p90": s.quantile(0.90),
            "mean": s.mean(),
        })
    return pd.DataFrame(rows).sort_values("cut")


def main():
    price_panel_full = pd.read_parquet(
        "data/processed/stock_features.parquet", columns=["symbol", "date", "close", "value_ma20", "volume_ma20"]
    )
    panel = load_price_panel()
    trading_days = pd.DatetimeIndex(
        sorted(pd.read_parquet("data/raw/index_ohlcv/VNINDEX.parquet", columns=["date"])["date"].unique())
    )
    eligible = build_eligible_panel(panel, trading_days)

    events_all = pd.read_parquet(
        "data/disclosure/events.parquet",
        columns=["symbol", "event_type", "direction", "person_name", "person_role", "shares_registered_or_changed", "disclosure_date", "is_backfilled", "available_at"],
    )
    holidays = load_market_holidays()

    raw_s1 = load_s1_events_full(events_all, holidays)
    raw_s1 = assign_day_idx(raw_s1, trading_days)
    print(f"Raw S1 events: {len(raw_s1)}")

    clustered = cluster_events(raw_s1[["symbol", "disclosure_date", "is_backfilled", "available_at", "person_name", "person_role", "shares_registered_or_changed"]], CAR_CLUSTER_GAP_DAYS, trading_days)
    print(f"Clustered S1 events (first-of-cluster, used for CAR): {len(clustered)}")

    # attach CAR at each horizon
    for h in CAR_HORIZONS:
        car_df = compute_car(clustered, price_panel_full, trading_days, h).set_index(["symbol", "day_idx"])["car"]
        clustered = clustered.set_index(["symbol", "day_idx"], drop=False).assign(**{f"car_{h}d": car_df}).reset_index(drop=True)

    # attach volume_ma20 at event day for the size-vs-ADV cut
    vol_lookup = price_panel_full.set_index(["symbol", "date"])["volume_ma20"]
    clustered["adv_shares_20d"] = clustered.apply(
        lambda r: vol_lookup.get((r["symbol"], r["available_at"]), np.nan), axis=1
    )
    clustered["registration_vs_adv"] = clustered["shares_registered_or_changed"] / clustered["adv_shares_20d"]

    # attach value_ma20 at event day for the size/liquidity proxy cut
    val_lookup = price_panel_full.set_index(["symbol", "date"])["value_ma20"]
    clustered["value_ma20_at_event"] = clustered.apply(
        lambda r: val_lookup.get((r["symbol"], r["available_at"]), np.nan), axis=1
    )

    # role grouping
    clustered["role_group"] = clustered["person_role"].apply(group_role)

    # multi-insider clustering
    clustered["n_distinct_insiders_in_window"] = count_distinct_insiders_in_window(clustered, raw_s1, window=CAR_CLUSTER_GAP_DAYS)
    clustered["multi_insider_cluster"] = np.where(clustered["n_distinct_insiders_in_window"] >= 2, "2+ người nội bộ", "1 người")

    # size-vs-ADV bucket (quartiles of the event population itself)
    clustered["adv_ratio_bucket"] = pd.qcut(clustered["registration_vs_adv"], q=4, labels=["Q1 (nhỏ nhất)", "Q2", "Q3", "Q4 (lớn nhất)"], duplicates="drop")

    # value_ma20 tertile (size/liquidity proxy -- no market-cap data available)
    clustered["value_ma20_tertile"] = pd.qcut(clustered["value_ma20_at_event"], q=3, labels=["Nhỏ", "Vừa", "Lớn"], duplicates="drop")

    print("\n" + "=" * 100)
    for h in CAR_HORIZONS:
        car_col = f"car_{h}d"
        print(f"\n########## CAR +{h} ngày ##########")
        print("\n-- theo quy mô đăng ký / ADV (volume_ma20, tứ phân vị) --")
        print(describe_by_cut(clustered, "adv_ratio_bucket", car_col).to_string(index=False))
        print("\n-- theo vai trò người đăng ký --")
        print(describe_by_cut(clustered, "role_group", car_col).to_string(index=False))
        print("\n-- theo cụm nhiều người nội bộ cùng đăng ký (cửa sổ 20 ngày) --")
        print(describe_by_cut(clustered, "multi_insider_cluster", car_col).to_string(index=False))
        print("\n-- theo nhóm thanh khoản/quy mô (value_ma20 tam phân vị, proxy vốn hóa) --")
        print(describe_by_cut(clustered, "value_ma20_tertile", car_col).to_string(index=False))

    clustered.to_csv("data/disclosure/car_s1_autopsy_events.csv", index=False)
    print("\nWritten: data/disclosure/car_s1_autopsy_events.csv")


if __name__ == "__main__":
    main()
