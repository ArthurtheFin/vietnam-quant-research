"""Point-in-time trading-status table (audit PATH_TO_100.md Universe/
Eligibility item -- a first step toward a real point-in-time universe for
Gate #3, NOT a full solution: it tracks each symbol's own last-observed
trading date and a coarse status, but still can't see symbols that were
delisted/merged away before appearing in today's listed-symbol universe.

Status classification (ACTIVE/STALE_SHORT/INACTIVE_LONG, by gap-to-latest)
is the ONE source of truth the eligibility gate uses to decide "is this
symbol currently tradeable" -- audit PATH_TO_100.md's separate
zero-volume/coverage-ratio item (a rolling-window coverage proxy, see
compute_coverage_ratio/low_coverage_symbols below) is deliberately folded
into the SAME "LOW_LIQUIDITY" eligibility reason the value/volume-based
check already uses, not a second competing classification: an empirical
check against the real 2026-07-13 data found STALE_SHORT (real thin
trading) and INACTIVE_LONG symbols' 60-session coverage ratios overlap
(STALE_SHORT ranges 0.12-0.95, INACTIVE_LONG 0.0-0.40) -- coverage ratio
alone cannot reliably distinguish "thin but real" from "suspended" the way
gap_days can, so it must not drive a separate suspension verdict.

Table is append-only (SCD Type 2 style): a new row is written only when a
symbol's status actually changes (or it's seen for the first time), not on
every daily update -- so querying "what was symbol S's status as of date
D" is just "the latest row with updated_at <= D", and the table doesn't
grow unboundedly for symbols that trade every day.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.data.loaders import read_parquet, save_parquet

TRADING_STATUS_PATH = Path("data/full_history_v2/trading_status.parquet")

# Shared with src/screening/eligibility.py's coverage-ratio gate (NV6) --
# one threshold set, not two. gap_days <= ACTIVE_MAX_GAP_DAYS -> ACTIVE;
# <= STALE_SHORT_MAX_GAP_DAYS -> STALE_SHORT; else INACTIVE_LONG. Matches
# the natural break found empirically in the 2026-07-13 full_history_v2
# sync (audit/ELIGIBILITY_GATE_STALE_DATA_DIAGNOSIS.md): 42 symbols
# clustered at 3-10 days behind (real thin trading), the next symbol out
# was 12 days (genuinely long-inactive) -- nothing falls in between.
ACTIVE_MAX_GAP_DAYS = 2
STALE_SHORT_MAX_GAP_DAYS = 10

TRADING_STATUS_COLUMNS = ["symbol", "last_trading_date", "status", "gap_days", "updated_at"]


def classify_trading_status(gap_days: int) -> str:
    if gap_days <= ACTIVE_MAX_GAP_DAYS:
        return "ACTIVE"
    if gap_days <= STALE_SHORT_MAX_GAP_DAYS:
        return "STALE_SHORT"
    return "INACTIVE_LONG"


def compute_current_gaps(raw_dir: str | Path, latest_trading_date: pd.Timestamp) -> pd.DataFrame:
    """Per-symbol last trading date + gap vs. latest_trading_date, from the
    raw price tier directly (no dependency on stock_features.parquet having
    been regenerated yet)."""
    raw_dir = Path(raw_dir)
    rows = []
    for path in sorted(raw_dir.glob("*.parquet")):
        symbol = path.stem.upper()
        df = read_parquet(path)
        if df.empty or "date" not in df.columns:
            continue
        last_date = pd.to_datetime(df["date"]).max()
        gap_days = int((pd.Timestamp(latest_trading_date).normalize() - last_date.normalize()).days)
        rows.append({
            "symbol": symbol,
            "last_trading_date": last_date.normalize(),
            "gap_days": gap_days,
            "status": classify_trading_status(gap_days),
        })
    return pd.DataFrame(rows, columns=["symbol", "last_trading_date", "gap_days", "status"])


def update_trading_status_table(
    current: pd.DataFrame,
    status_path: str | Path = TRADING_STATUS_PATH,
    run_at: pd.Timestamp | None = None,
) -> dict[str, int]:
    """Append-only update: for each symbol in `current` (output of
    compute_current_gaps), append a new row only if this is the symbol's
    first-ever row or its status differs from its most recent row.
    Returns counts of new rows written vs. symbols left unchanged."""
    status_path = Path(status_path)
    run_at = run_at or pd.Timestamp.now(tz=timezone.utc)

    existing = read_parquet(status_path) if status_path.exists() else pd.DataFrame(columns=TRADING_STATUS_COLUMNS)
    latest_by_symbol: dict[str, str] = {}
    if not existing.empty:
        latest_rows = existing.sort_values("updated_at").groupby("symbol").tail(1)
        latest_by_symbol = dict(zip(latest_rows["symbol"], latest_rows["status"]))

    new_rows = []
    for _, row in current.iterrows():
        prior_status = latest_by_symbol.get(row["symbol"])
        if prior_status == row["status"]:
            continue
        new_rows.append({
            "symbol": row["symbol"],
            "last_trading_date": row["last_trading_date"],
            "status": row["status"],
            "gap_days": int(row["gap_days"]),
            "updated_at": run_at,
        })

    if new_rows:
        new_df = pd.DataFrame(new_rows, columns=TRADING_STATUS_COLUMNS)
        combined = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
        save_parquet(combined, status_path)

    return {"n_new_rows": len(new_rows), "n_unchanged": len(current) - len(new_rows)}


def latest_trading_status(status_path: str | Path = TRADING_STATUS_PATH) -> pd.DataFrame:
    """Current status per symbol (the latest row per symbol) -- what the
    eligibility gate should consult right now."""
    status_path = Path(status_path)
    if not status_path.exists():
        return pd.DataFrame(columns=TRADING_STATUS_COLUMNS)
    df = read_parquet(status_path)
    if df.empty:
        return df
    return df.sort_values("updated_at").groupby("symbol", as_index=False).tail(1).reset_index(drop=True)


def status_as_of(as_of_date: pd.Timestamp, status_path: str | Path = TRADING_STATUS_PATH) -> pd.DataFrame:
    """Point-in-time reconstruction: each symbol's status as it was known
    as of `as_of_date` (the latest row with updated_at <= as_of_date) --
    the actual point-in-time capability this table exists to provide."""
    status_path = Path(status_path)
    if not status_path.exists():
        return pd.DataFrame(columns=TRADING_STATUS_COLUMNS)
    df = read_parquet(status_path)
    if df.empty:
        return df
    as_of = pd.Timestamp(as_of_date)
    if as_of.tzinfo is not None:
        as_of = as_of.tz_localize(None)
    updated_at_naive = pd.to_datetime(df["updated_at"]).dt.tz_localize(None)
    df = df[updated_at_naive <= as_of]
    if df.empty:
        return df
    return df.sort_values("updated_at").groupby("symbol", as_index=False).tail(1).reset_index(drop=True)


DEFAULT_COVERAGE_WINDOW_SESSIONS = 60
# Calibrated against the real 2026-07-13 sync: catches most INACTIVE_LONG
# symbols (17/18 are <=0.40, most are 0.0) while only flagging the
# sparsest tail of STALE_SHORT (real, accepted thin trading per the v2
# zero-volume convention -- a low ratio here is NOT an error, it folds into
# the existing LOW_LIQUIDITY reason, same as a low value_ma20/volume_ma20).
DEFAULT_MIN_COVERAGE_RATIO = 0.30

# Precomputed snapshot, overwritten each scripts/update_prices_daily.py run
# (NOT append-only like trading_status.parquet -- coverage ratio is a
# continuously-drifting number, not a discrete point-in-time fact worth
# preserving history for). Reading this small file is what the eligibility
# gate does on every run; computing it fresh requires scanning every
# symbol's full raw price history and is too expensive to do per gate call
# (measured: ~500 file reads, seconds per call -- refresh_coverage_ratios
# is the only place that should pay that cost).
COVERAGE_RATIO_PATH = Path("data/full_history_v2/coverage_ratios.parquet")


def compute_coverage_ratio(
    raw_dir: str | Path,
    latest_trading_date: pd.Timestamp,
    window_sessions: int = DEFAULT_COVERAGE_WINDOW_SESSIONS,
) -> pd.DataFrame:
    """Per-symbol ratio of observed trading days to expected trading
    sessions (config/vn_market_holidays.csv-aware, so Tet and other real
    closures are never counted against a symbol) over the last
    `window_sessions` sessions ending at latest_trading_date. A day with no
    row is a day with no matched trade -- valid for a genuinely
    low-liquidity name per the v2 fetch convention (docs/reports/data/docs/reports/data/DATA_BASELINE.md caveat
    #3), so this is a liquidity signal, not by itself a suspension one.

    Expensive (scans every symbol's full raw price history) -- call this
    from refresh_coverage_ratios (once per daily update run), not per
    eligibility-gate invocation."""
    from src.validation.freshness_check import load_market_holidays

    raw_dir = Path(raw_dir)
    holidays = load_market_holidays()
    latest_trading_date = pd.Timestamp(latest_trading_date).normalize()
    calendar = pd.bdate_range(latest_trading_date - pd.Timedelta(days=window_sessions * 3), latest_trading_date)
    expected_sessions = [d for d in calendar if d.date() not in holidays][-window_sessions:]
    expected_set = set(expected_sessions)

    rows = []
    for path in sorted(raw_dir.glob("*.parquet")):
        symbol = path.stem.upper()
        df = read_parquet(path)
        if df.empty or "date" not in df.columns:
            rows.append({"symbol": symbol, "coverage_ratio": 0.0})
            continue
        observed = set(pd.to_datetime(df["date"]).dt.normalize())
        n_observed = sum(1 for d in expected_sessions if d in observed)
        rows.append({"symbol": symbol, "coverage_ratio": n_observed / len(expected_set) if expected_set else 0.0})
    return pd.DataFrame(rows, columns=["symbol", "coverage_ratio"])


def refresh_coverage_ratios(
    raw_dir: str | Path,
    latest_trading_date: pd.Timestamp,
    path: str | Path = COVERAGE_RATIO_PATH,
    window_sessions: int = DEFAULT_COVERAGE_WINDOW_SESSIONS,
) -> pd.DataFrame:
    """Recompute every symbol's coverage ratio and overwrite the snapshot
    file. Called once per scripts/update_prices_daily.py run."""
    coverage = compute_coverage_ratio(raw_dir, latest_trading_date, window_sessions=window_sessions)
    path = Path(path)
    save_parquet(coverage, path)
    return coverage


def low_coverage_symbols(
    path: str | Path = COVERAGE_RATIO_PATH,
    min_coverage_ratio: float = DEFAULT_MIN_COVERAGE_RATIO,
) -> set[str]:
    """Symbols whose rolling coverage ratio (from the precomputed snapshot
    at `path`) falls below the threshold -- fed into the eligibility gate's
    existing LOW_LIQUIDITY reason (not a new/competing status), per this
    module's docstring. Returns an empty set if the snapshot doesn't exist
    yet (never blocks the gate)."""
    path = Path(path)
    if not path.exists():
        return set()
    coverage = read_parquet(path)
    if coverage.empty:
        return set()
    return set(coverage.loc[coverage["coverage_ratio"] < min_coverage_ratio, "symbol"])


def excluded_symbols_by_status(
    status_path: str | Path = TRADING_STATUS_PATH,
    exclude_statuses: tuple[str, ...] = ("INACTIVE_LONG",),
) -> set[str]:
    """Symbols to exclude from the CURRENT eligible universe by status --
    not a hardcoded list, always derived from the live table."""
    current = latest_trading_status(status_path)
    if current.empty:
        return set()
    return set(current.loc[current["status"].isin(exclude_statuses), "symbol"])
