from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.disclosure_parser import next_trading_day
from src.data.loaders import append_parquet, read_parquet
from src.utils.logger import get_logger

logger = get_logger(__name__)

EVENTS_PATH = Path("data/disclosure/events.parquet")
ERRORS_PATH = Path("data/disclosure/errors.parquet")
UNIVERSE_DIR = Path("data/full_history_v2/raw")

# Widened 2026-07-13 (audit PATH_TO_100.md Data Quality item, +1):
# DISCLOSURE_BASELINE.md's original key (symbol, event_type, person_name,
# disclosure_date) silently collapsed 829/57,800 parsed rows (1.4%) that
# share a natural key with at least one other row -- almost always a person
# making two genuinely distinct disclosures (different registration window,
# different share count) published the same calendar date. Adding
# direction + shares_registered_or_changed resolves 633/829 (76%) of those
# collisions on the current full-universe parse. The remaining 196 (two
# distinct registration windows, same day/direction/volume -- e.g. Vuong
# Ngoc Yen/ACE) need `dedup_seq`, a per-base-key row-order tiebreaker (see
# _assign_dedup_seq), which resolves the rest (0 collisions remaining).
NATURAL_KEY_BASE = ["symbol", "event_type", "person_name", "disclosure_date", "direction", "shares_registered_or_changed"]
NATURAL_KEY = NATURAL_KEY_BASE + ["dedup_seq"]


def _assign_dedup_seq(df: pd.DataFrame) -> pd.Series:
    """Per-NATURAL_KEY_BASE sequence number (0, 1, 2, ...) in row order --
    the final collision tiebreaker (see NATURAL_KEY's comment above). Relies
    on row order being stable across re-parses of the same immutable raw
    JSON (true in practice -- the source returns records in a consistent
    order) so the same historical event gets the same dedup_seq every time;
    not formally guaranteed by the source, so this is a best-effort
    tiebreaker, not a cryptographic identity."""
    return df.groupby(NATURAL_KEY_BASE, dropna=False).cumcount()


def load_universe_symbols(universe_dir: Path = UNIVERSE_DIR) -> set[str]:
    """Delegates to src.data.universe.tracked_universe_symbols (audit
    PATH_TO_100.md Data Quality item) -- previously defined its own symbol
    list here without applying config/excluded_symbols.csv, so an excluded
    symbol (e.g. GEE) would validate as "known" here even though it's
    excluded from the eligible universe everywhere else."""
    from src.data.universe import tracked_universe_symbols

    return set(tracked_universe_symbols(raw_dir=universe_dir))


def _compute_available_at(df: pd.DataFrame) -> pd.Series:
    """ROUND 3 point-in-time rule (DISCLOSURE_PIPELINE_DESIGN.md):
    - live rows (is_backfilled=False): available_at = max(disclosure_date, ingested_at)
    - backfilled rows (is_backfilled=True): available_at = disclosure_date + 1 trading day
      (a conservative placeholder lag, to be replaced by a measured live
      distribution once enough live rows exist -- not attempted here)."""
    disclosure_date = pd.to_datetime(df["disclosure_date"])
    ingested_at = pd.to_datetime(df["ingested_at"])
    live_available = pd.concat([disclosure_date, ingested_at], axis=1).max(axis=1)
    backfill_available = disclosure_date.apply(next_trading_day)
    is_backfilled = df["is_backfilled"].astype(bool)
    return backfill_available.where(is_backfilled, live_available)


def _validate(df: pd.DataFrame, universe: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (valid_rows, error_rows). Unknown-universe symbols are
    flagged (unknown_symbol=True) but kept; negative quantities or inverted
    date ranges are rejected into the error table with a reason, per
    instruction."""
    out = df.copy()
    out["unknown_symbol"] = ~out["symbol"].str.upper().isin(universe)
    if out["unknown_symbol"].any():
        logger.warning(
            "%s row(s) reference symbol(s) outside the current universe (flagged, not rejected): %s",
            int(out["unknown_symbol"].sum()),
            sorted(out.loc[out["unknown_symbol"], "symbol"].unique()),
        )

    reasons = pd.Series([""] * len(out), index=out.index)

    neg_qty_mask = pd.to_numeric(out["shares_registered_or_changed"], errors="coerce") < 0
    reasons = reasons.where(~neg_qty_mask, reasons + "NEGATIVE_QUANTITY;")

    window_start = pd.to_datetime(out["registration_window_start"], errors="coerce")
    window_end = pd.to_datetime(out["registration_window_end"], errors="coerce")
    inverted_window_mask = window_start.notna() & window_end.notna() & (window_start > window_end)
    reasons = reasons.where(~inverted_window_mask, reasons + "INVERTED_REGISTRATION_WINDOW;")

    exec_date = pd.to_datetime(out["execution_date"], errors="coerce")
    exec_before_window_mask = exec_date.notna() & window_start.notna() & (exec_date < window_start)
    reasons = reasons.where(~exec_before_window_mask, reasons + "EXECUTION_BEFORE_REGISTRATION_START;")

    reject_mask = neg_qty_mask | inverted_window_mask | exec_before_window_mask
    error_rows = out.loc[reject_mask].copy()
    error_rows["reject_reason"] = reasons.loc[reject_mask].str.rstrip(";")
    valid_rows = out.loc[~reject_mask].copy()
    return valid_rows, error_rows


def ingest_events(
    events_df: pd.DataFrame,
    events_path: Path = EVENTS_PATH,
    errors_path: Path = ERRORS_PATH,
    universe_dir: Path = UNIVERSE_DIR,
) -> dict[str, int]:
    """Apply the point-in-time schema and validation, then append-only write.

    Natural key (symbol, event_type, person_name, disclosure_date, direction,
    shares_registered_or_changed, dedup_seq) enforces the design's "never
    update in place" rule: a later correction/amendment gets its own
    disclosure_date and becomes a new row; the old row is left exactly as
    it was.
    """
    if events_df.empty:
        return {"n_valid": 0, "n_rejected": 0, "n_unknown_symbol": 0}

    events_df = events_df.copy()
    if "dedup_seq" not in events_df.columns:
        # Not already assigned by a caller (e.g. ingest_new_events_live,
        # which must assign it on the full re-parsed batch before its
        # anti-join) -- compute fresh here for the bulk one-shot path.
        events_df["dedup_seq"] = _assign_dedup_seq(events_df)

    universe = load_universe_symbols(universe_dir)
    valid_df, error_df = _validate(events_df, universe)

    if not valid_df.empty:
        valid_df = valid_df.copy()
        valid_df["available_at"] = _compute_available_at(valid_df)
        append_parquet(valid_df, events_path, subset=NATURAL_KEY)

    if not error_df.empty:
        append_parquet(error_df, errors_path)

    return {
        "n_valid": int(len(valid_df)),
        "n_rejected": int(len(error_df)),
        "n_unknown_symbol": int(valid_df["unknown_symbol"].sum()) if not valid_df.empty else 0,
    }


def read_events(events_path: Path = EVENTS_PATH) -> pd.DataFrame:
    return read_parquet(events_path)


def read_errors(errors_path: Path = ERRORS_PATH) -> pd.DataFrame:
    return read_parquet(errors_path)


def ingest_new_events_live(
    parsed_df: pd.DataFrame,
    events_path: Path = EVENTS_PATH,
    errors_path: Path = ERRORS_PATH,
    universe_dir: Path = UNIVERSE_DIR,
) -> dict[str, int]:
    """Incremental/live counterpart to ingest_events, for the daily update
    script (scripts/update_disclosure_daily.py).

    ingest_events() re-derives is_backfilled/available_at for every row it's
    given every time -- correct for the one-shot bulk historical load, but
    wrong for a daily job that re-parses a symbol's *entire* history each
    run: re-ingesting an already-known row here would silently overwrite its
    original is_backfilled=True / available_at with today's is_backfilled=
    False and a fresh available_at, corrupting the point-in-time record of
    when it actually became knowable.

    This function instead anti-joins parsed_df against what's already in
    events_path (both valid and rejected -- a previously-rejected row should
    not be silently re-admitted just because it reappears in a fresh parse),
    ingests ONLY genuinely new rows, and forces is_backfilled=False on them --
    this is the first point where the live branch of the ROUND 3 point-in-time
    rule (available_at = max(disclosure_date, ingested_at)) actually starts
    running, as opposed to every row so far being backfilled.
    """
    if parsed_df.empty:
        return {"n_new_valid": 0, "n_new_rejected": 0, "n_new_unknown_symbol": 0}

    # Assign dedup_seq on the full re-parsed batch (before the anti-join),
    # not per-row in isolation -- it's a per-NATURAL_KEY_BASE row-order
    # tiebreaker, so it must be computed over the same full history each
    # time to keep assigning the same historical event the same value.
    parsed_df = parsed_df.copy()
    parsed_df["dedup_seq"] = _assign_dedup_seq(parsed_df)

    existing_events = read_events(events_path)
    existing_errors = read_errors(errors_path)
    known_keys: set[tuple] = set()
    if not existing_events.empty:
        known_keys |= set(map(tuple, existing_events[NATURAL_KEY].itertuples(index=False, name=None)))
    if not existing_errors.empty:
        known_keys |= set(map(tuple, existing_errors[NATURAL_KEY].itertuples(index=False, name=None)))

    row_keys = list(map(tuple, parsed_df[NATURAL_KEY].itertuples(index=False, name=None)))
    is_new_mask = pd.Series([key not in known_keys for key in row_keys], index=parsed_df.index)
    new_df = parsed_df.loc[is_new_mask].copy()

    if new_df.empty:
        return {"n_new_valid": 0, "n_new_rejected": 0, "n_new_unknown_symbol": 0}

    new_df["is_backfilled"] = False
    result = ingest_events(new_df, events_path=events_path, errors_path=errors_path, universe_dir=universe_dir)
    return {
        "n_new_valid": result["n_valid"],
        "n_new_rejected": result["n_rejected"],
        "n_new_unknown_symbol": result["n_unknown_symbol"],
    }
