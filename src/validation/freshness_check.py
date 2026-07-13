from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from src.data.dataset_config import OFFICIAL_CLEAN_OHLCV_PATH, OFFICIAL_FEATURES_PATH, OFFICIAL_PRICE_RAW_DIR
from src.utils.pipeline_io import (
    DEFAULT_DATE_COLUMNS,
    dataframe_metadata,
    latest_timestamp,
    read_first_existing_parquet,
)


@dataclass(frozen=True)
class ArtifactSpec:
    name: str
    paths: tuple[str, ...]
    severity: str = "warning"
    required: bool = False
    date_columns: tuple[str, ...] = DEFAULT_DATE_COLUMNS


ARTIFACT_SPECS: tuple[ArtifactSpec, ...] = (
    ArtifactSpec("clean_daily_ohlcv", (OFFICIAL_CLEAN_OHLCV_PATH,), severity="error", required=True),
    ArtifactSpec("stock_features", (OFFICIAL_FEATURES_PATH,), severity="error", required=True),
    ArtifactSpec(
        "setup_signals",
        ("data/signals/setup_signals.parquet", "data/processed/setup_signals.parquet"),
        severity="error",
    ),
    ArtifactSpec("alpha_scores", ("data/signals/alpha_scores.parquet",), severity="warning"),
    ArtifactSpec("benchmark_vnindex", ("data/processed/benchmark_vnindex.parquet",), severity="warning"),
    ArtifactSpec("breakout_trade_cards", ("data/signals/breakout_20d_trade_cards.parquet",), severity="warning"),
    ArtifactSpec("stealth_latest", ("data/signals/stealth_accumulation_latest.parquet",), severity="warning"),
    ArtifactSpec(
        "meta_ranking",
        ("data/signals/meta_ranking.parquet", "data/processed/meta_ranking.parquet"),
        severity="error",
    ),
    ArtifactSpec("final_watchlist", ("data/signals/final_watchlist.parquet",), severity="warning"),
    ArtifactSpec("research_candidates", ("data/output/research_candidates.parquet",), severity="warning"),
    ArtifactSpec("trading_watchlist", ("data/output/trading_watchlist.parquet",), severity="warning"),
    ArtifactSpec("client_ready_watchlist", ("data/output/client_ready_watchlist.parquet",), severity="warning"),
)


DEPENDENCY_RULES: tuple[tuple[str, str, str], ...] = (
    ("clean_daily_ohlcv", "stock_features", "error"),
    ("stock_features", "setup_signals", "error"),
    ("stock_features", "alpha_scores", "warning"),
    ("stock_features", "benchmark_vnindex", "warning"),
    ("setup_signals", "breakout_trade_cards", "warning"),
    ("stock_features", "stealth_latest", "warning"),
    ("stock_features", "meta_ranking", "error"),
    ("meta_ranking", "final_watchlist", "warning"),
    ("meta_ranking", "trading_watchlist", "warning"),
    ("meta_ranking", "client_ready_watchlist", "warning"),
)


def inspect_artifacts(base_dir: str | Path = ".") -> dict[str, dict[str, object]]:
    base = Path(base_dir)
    inspected: dict[str, dict[str, object]] = {}

    for spec in ARTIFACT_SPECS:
        frame, resolved_path = read_first_existing_parquet(spec.paths, base_dir=base)
        latest = latest_timestamp(frame, candidates=spec.date_columns)
        inspected[spec.name] = {
            "name": spec.name,
            "required": spec.required,
            "severity": spec.severity,
            "exists": resolved_path is not None,
            "resolved_path": None if resolved_path is None else str(resolved_path),
            "latest_timestamp": latest,
            "metadata": dataframe_metadata(frame, path=resolved_path, date_candidates=spec.date_columns),
        }
    return inspected


def _build_core_universe_from_local_data(base_dir: str | Path = ".") -> pd.DataFrame:
    base = Path(base_dir)
    # OFFICIAL_PRICE_RAW_DIR (not the legacy data/raw/daily_ohlcv), per
    # audit gate #6 -- every price-reading path must trace back to the
    # one verified, bug-fixed raw source.
    raw_dir = base / OFFICIAL_PRICE_RAW_DIR
    processed_path = base / OFFICIAL_CLEAN_OHLCV_PATH

    if not raw_dir.exists() or not processed_path.exists():
        return pd.DataFrame()

    market_map_df = pd.read_parquet(processed_path, columns=["symbol", "market"])
    market_map = (
        market_map_df.dropna(subset=["symbol", "market"])
        .drop_duplicates(subset=["symbol"])
        .assign(symbol=lambda frame: frame["symbol"].astype(str).str.upper().str.strip())
        .set_index("symbol")["market"]
        .to_dict()
    )

    rows: list[dict[str, object]] = []
    for path in sorted(raw_dir.glob("*.parquet")):
        symbol = path.stem.upper()
        market = market_map.get(symbol)
        if market not in {"HOSE", "HNX", "UPCOM"}:
            continue

        try:
            df = pd.read_parquet(path, columns=["date", "close", "volume"])
        except Exception:
            continue

        if df.empty or "date" not in df.columns:
            continue

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["close"] = pd.to_numeric(df.get("close"), errors="coerce")
        df["volume"] = pd.to_numeric(df.get("volume"), errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        if df.empty:
            continue

        tail20 = df.tail(20)
        rows.append(
            {
                "symbol": symbol,
                "market": market,
                "latest_date": df["date"].iloc[-1].date().isoformat(),
                "latest_close": float(df["close"].iloc[-1]) if pd.notna(df["close"].iloc[-1]) else None,
                "latest_volume": float(df["volume"].iloc[-1]) if pd.notna(df["volume"].iloc[-1]) else None,
                "avg_value_20d": float((tail20["close"] * tail20["volume"]).mean()) if not tail20.empty else None,
                "avg_volume_20d": float(tail20["volume"].mean()) if not tail20.empty else None,
            }
        )

    if not rows:
        return pd.DataFrame()

    universe = pd.DataFrame(rows)
    universe = universe[universe["symbol"].astype(str).str.fullmatch(r"[A-Z0-9]{1,3}", na=False)].copy()

    active_mask = pd.to_datetime(universe["latest_date"]).ge(pd.Timestamp("2026-06-27"))
    tradable_mask = (
        pd.to_numeric(universe["latest_close"], errors="coerce").fillna(0.0).gt(0.0)
        & pd.to_numeric(universe["latest_volume"], errors="coerce").fillna(0.0).gt(0.0)
    )
    liquidity_mask = (
        pd.to_numeric(universe["avg_value_20d"], errors="coerce").fillna(0.0).ge(5_000_000_000.0)
        | pd.to_numeric(universe["avg_volume_20d"], errors="coerce").fillna(0.0).ge(50_000.0)
    )

    filtered = universe[active_mask & tradable_mask & liquidity_mask].copy()
    if filtered.empty:
        return filtered

    filtered = filtered.sort_values(
        ["market", "avg_value_20d", "avg_volume_20d", "symbol"],
        ascending=[True, False, False, True],
    ).reset_index(drop=True)
    filtered["reason"] = "Active + liquid market-wide core universe"
    filtered["source"] = "raw daily ohlcv scan (HOSE/HNX/UPCOM)"
    filtered["updated_at"] = "2026-07-07"
    return filtered


def ensure_core_universe(base_dir: str | Path = ".") -> list[str]:
    base = Path(base_dir)
    csv_path = base / "config/core_universe.csv"
    if not csv_path.exists():
        derived = _build_core_universe_from_local_data(base)
        if not derived.empty:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            derived.to_csv(csv_path, index=False, encoding="utf-8")
            return sorted(derived["symbol"].dropna().astype(str).unique().tolist())
    else:
        try:
            df = pd.read_csv(csv_path)
            if not df.empty and "symbol" in df.columns:
                return sorted(list(df["symbol"].dropna().astype(str).unique()))
        except Exception:
            pass

    fallback_watchlist = [
        "ACB", "BID", "CTG", "DGC", "FPT", "GAS", "GVR", "HDB", "HPG", "LPB",
        "MBB", "MSN", "MWG", "PLX", "SAB", "SHB", "SSB", "SSI", "STB", "TCB",
        "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE", "VPL",
    ]
    return fallback_watchlist


def load_market_holidays(base_dir: str | Path = ".") -> set:
    """Known VN market holidays from config/vn_market_holidays.csv (fixed solar dates only;
    lunar holidays such as Tet must be added manually — see OPERATIONS.md)."""
    path = Path(base_dir) / "config/vn_market_holidays.csv"
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path)
        return set(pd.to_datetime(df["date"], errors="coerce").dropna().dt.date)
    except Exception:
        return set()


def expected_latest_trading_date(
    now: pd.Timestamp | None = None,
    holidays: set | None = None,
) -> pd.Timestamp:
    """Most recent HOSE session whose EOD data should exist by `now` (audit B2).

    Weekday approximation + configured holidays. Before 16:00 Asia/Ho_Chi_Minh the
    current session's EOD data may not be published yet, so the previous session
    is expected instead.
    """
    holidays = holidays or set()
    if now is None:
        now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh")
    now = pd.Timestamp(now)
    if now.tzinfo is not None:
        now = now.tz_convert("Asia/Ho_Chi_Minh").tz_localize(None)
    candidate = now.normalize()
    if now.hour < 16:
        candidate -= pd.Timedelta(days=1)
    while candidate.weekday() >= 5 or candidate.date() in holidays:
        candidate -= pd.Timedelta(days=1)
    return candidate


def trading_sessions_behind(
    baseline_date: pd.Timestamp,
    expected_date: pd.Timestamp,
    holidays: set | None = None,
) -> int:
    """Number of trading sessions strictly after baseline_date up to expected_date."""
    holidays = holidays or set()
    baseline = pd.Timestamp(baseline_date).normalize()
    expected = pd.Timestamp(expected_date).normalize()
    sessions = 0
    day = baseline + pd.Timedelta(days=1)
    while day <= expected:
        if day.weekday() < 5 and day.date() not in holidays:
            sessions += 1
        day += pd.Timedelta(days=1)
    return sessions


def _market_latest_date_from_summary(base_dir: str | Path) -> pd.Timestamp | None:
    """VNINDEX-confirmed latest market date persisted by update_daily_data (preferred over
    the weekday approximation because it reflects real sessions, including lunar holidays)."""
    import json

    path = Path(base_dir) / "data/output/update_daily_data_summary.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        raw = summary.get("market_latest_date")
        if raw:
            return pd.Timestamp(raw).normalize()
    except Exception:
        pass
    return None


def check_symbol_freshness(base_dir: str | Path, baseline_date: pd.Timestamp, scope: str = "core") -> dict[str, object]:
    base = Path(base_dir)
    ohlcv_path = base / OFFICIAL_CLEAN_OHLCV_PATH
    if not ohlcv_path.exists():
        ohlcv_path = base / OFFICIAL_FEATURES_PATH
    if not ohlcv_path.exists():
        return {
            "baseline_date": baseline_date.date().isoformat() if baseline_date else None,
            "total_symbols": 0,
            "symbols_at_baseline_date": 0,
            "stale_symbol_count": 0,
            "stale_symbol_ratio": 0.0,
            "stale_symbols_sample": [],
            "stale_client_ready_symbols": [],
            "stale_portfolio_symbols": [],
            "status": "ERROR",
            "scope": scope
        }

    df = pd.read_parquet(ohlcv_path)
    if df.empty or "date" not in df.columns or "symbol" not in df.columns:
        return {
            "baseline_date": baseline_date.date().isoformat() if baseline_date else None,
            "total_symbols": 0,
            "symbols_at_baseline_date": 0,
            "stale_symbol_count": 0,
            "stale_symbol_ratio": 0.0,
            "stale_symbols_sample": [],
            "stale_client_ready_symbols": [],
            "stale_portfolio_symbols": [],
            "status": "ERROR",
            "scope": scope
        }

    df["date"] = pd.to_datetime(df["date"])
    latest_per_symbol = df.groupby("symbol")["date"].max()

    total_symbols = int(latest_per_symbol.index.nunique())
    symbols_at_baseline = int(latest_per_symbol[latest_per_symbol == baseline_date].count())
    stale_symbols_series = latest_per_symbol[latest_per_symbol < baseline_date]
    stale_symbols = list(stale_symbols_series.index.astype(str))
    stale_symbol_count = len(stale_symbols)
    stale_symbol_ratio = float(stale_symbol_count / total_symbols) if total_symbols > 0 else 0.0

    cr_path = base / "data/output/client_ready_watchlist.parquet"
    cr_symbols = []
    if cr_path.exists():
        try:
            cr_df = pd.read_parquet(cr_path)
            if not cr_df.empty and "symbol" in cr_df.columns:
                cr_symbols = list(cr_df["symbol"].dropna().astype(str).unique())
        except Exception:
            pass

    pw_path = base / "data/output/portfolio_weights.parquet"
    pw_symbols = []
    if pw_path.exists():
        try:
            pw_df = pd.read_parquet(pw_path)
            if not pw_df.empty and "symbol" in pw_df.columns:
                pw_symbols = list(pw_df["symbol"].dropna().astype(str).unique())
        except Exception:
            pass

    stale_cr = [sym for sym in cr_symbols if sym in stale_symbols]
    stale_pw = [sym for sym in pw_symbols if sym in stale_symbols]

    core_symbols = ensure_core_universe(base)
    stale_core = [sym for sym in core_symbols if sym in stale_symbols]

    status = "OK"
    if scope == "core":
        if len(stale_core) > 0:
            status = "WARNING"
    elif scope in ("full", "tracked"):
        if stale_symbol_ratio > 0.10:
            status = "WARNING"
    elif scope == "batch":
        # batch scope relaxes full freshness count, no general stale warning
        pass

    if len(stale_cr) > 0 or len(stale_pw) > 0:
        status = "ERROR"

    return {
        "baseline_date": baseline_date.date().isoformat(),
        "total_symbols": total_symbols,
        "symbols_at_baseline_date": symbols_at_baseline,
        "stale_symbol_count": stale_symbol_count,
        "stale_symbol_ratio": stale_symbol_ratio,
        "stale_symbols_sample": sorted(stale_symbols)[:15],
        "stale_client_ready_symbols": sorted(stale_cr),
        "stale_portfolio_symbols": sorted(stale_pw),
        "stale_core_symbols": sorted(stale_core),
        "status": status,
        "scope": scope
    }


def evaluate_freshness(
    base_dir: str | Path = ".",
    strict: bool = False,
    scope: str = "core",
    now: pd.Timestamp | None = None,
) -> dict[str, object]:
    inspected = inspect_artifacts(base_dir=base_dir)
    warnings: list[str] = []
    errors: list[str] = []

    baseline_ts = (
        inspected.get("clean_daily_ohlcv", {}).get("latest_timestamp")
        or inspected.get("stock_features", {}).get("latest_timestamp")
    )
    baseline_date = None if baseline_ts is None else pd.Timestamp(baseline_ts)

    # B2: compare the dataset against the real trading calendar, not against itself.
    calendar_freshness = None
    if baseline_date is not None:
        holidays = load_market_holidays(base_dir)
        market_confirmed = _market_latest_date_from_summary(base_dir)
        approx_expected = expected_latest_trading_date(now=now, holidays=holidays)
        if market_confirmed is not None and abs((market_confirmed - approx_expected).days) <= 7:
            expected = market_confirmed
            expected_source = "vnindex_confirmed"
        else:
            expected = approx_expected
            expected_source = "weekday_approximation"
        lag_sessions = trading_sessions_behind(baseline_date.normalize(), expected, holidays)
        calendar_freshness = {
            "expected_trading_date": expected.date().isoformat(),
            "expected_source": expected_source,
            "baseline_date": baseline_date.date().isoformat(),
            "lag_sessions": lag_sessions,
        }
        if lag_sessions == 1:
            warnings.append(
                f"Dataset may be frozen: latest data {baseline_date.date().isoformat()} is 1 trading "
                f"session behind expected {expected.date().isoformat()} ({expected_source})."
            )
        elif lag_sessions >= 2:
            errors.append(
                f"Dataset frozen: latest data {baseline_date.date().isoformat()} is {lag_sessions} trading "
                f"sessions behind expected {expected.date().isoformat()} ({expected_source}). "
                f"Run scripts/update_daily_data.py before trusting any output."
            )

    symbol_freshness = None
    if baseline_date is not None:
        symbol_freshness = check_symbol_freshness(base_dir, baseline_date, scope=scope)
        if symbol_freshness["status"] == "WARNING":
            if scope == "core":
                warnings.append(
                    f"Stale core symbol coverage: {len(symbol_freshness['stale_core_symbols'])} core symbol(s) stale "
                    f"({', '.join(symbol_freshness['stale_core_symbols'])})."
                )
            else:
                warnings.append(
                    f"Stale symbol coverage: {symbol_freshness['stale_symbol_ratio']:.1%} "
                    f"({symbol_freshness['stale_symbol_count']}/{symbol_freshness['total_symbols']} symbols stale)."
                )
        elif symbol_freshness["status"] == "ERROR":
            errors.append(
                f"Stale symbols detected in Client-Ready or Portfolio! "
                f"Stale Client-Ready: {symbol_freshness['stale_client_ready_symbols']}, "
                f"Stale Portfolio: {symbol_freshness['stale_portfolio_symbols']}."
            )

    if baseline_date is None:
        errors.append("No baseline artifact found. Missing clean_daily_ohlcv / stock_features.")

    for spec in ARTIFACT_SPECS:
        item = inspected[spec.name]
        if not item["exists"]:
            message = f"Missing artifact: {spec.name}"
            if spec.required or spec.severity == "error":
                errors.append(message)
            else:
                warnings.append(message)
            continue

        latest = item["latest_timestamp"]
        if latest is None:
            if spec.name == "trading_watchlist" and item.get("metadata", {}).get("rows", 0) == 0:
                item["lag_days_vs_baseline"] = None
                item["empty_allowed"] = True
                continue
            message = f"Artifact has no usable date column: {spec.name}"
            if spec.severity == "error":
                errors.append(message)
            else:
                warnings.append(message)
            continue

        if baseline_date is not None:
            lag_days = int((baseline_date.normalize() - pd.Timestamp(latest).normalize()).days)
            item["lag_days_vs_baseline"] = lag_days
            if lag_days > 0:
                message = (
                    f"{spec.name} is stale by {lag_days} day(s). "
                    f"Latest {spec.name}: {pd.Timestamp(latest).date().isoformat()}, "
                    f"baseline: {baseline_date.date().isoformat()}."
                )
                if spec.severity == "error" or strict:
                    errors.append(message)
                else:
                    warnings.append(message)
        else:
            item["lag_days_vs_baseline"] = None

    for parent_name, child_name, severity in DEPENDENCY_RULES:
        parent = inspected.get(parent_name)
        child = inspected.get(child_name)
        if not parent or not child or not parent["exists"] or not child["exists"]:
            continue
        parent_ts = parent.get("latest_timestamp")
        child_ts = child.get("latest_timestamp")
        if parent_ts is None or child_ts is None:
            continue
        if pd.Timestamp(child_ts) < pd.Timestamp(parent_ts):
            message = (
                f"{child_name} was generated from stale inputs relative to {parent_name}. "
                f"{child_name} latest = {pd.Timestamp(child_ts).date().isoformat()}, "
                f"{parent_name} latest = {pd.Timestamp(parent_ts).date().isoformat()}."
            )
            if severity == "error" or strict:
                errors.append(message)
            else:
                warnings.append(message)

    status = "OK"
    if errors:
        status = "ERROR"
    elif warnings:
        status = "WARNING"

    artifact_summary = {
        name: {
            **{
                key: value
                for key, value in item.items()
                if key not in {"latest_timestamp"}
            },
            "latest_date": None
            if item.get("latest_timestamp") is None
            else pd.Timestamp(item["latest_timestamp"]).date().isoformat(),
        }
        for name, item in inspected.items()
    }

    return {
        "status": status,
        "baseline_date": None if baseline_date is None else baseline_date.date().isoformat(),
        "warnings": warnings,
        "errors": errors,
        "artifacts": artifact_summary,
        "symbol_freshness": symbol_freshness,
        "calendar_freshness": calendar_freshness,
    }


def _format_report(report: dict[str, object]) -> str:
    lines = [f"{report['status']}: freshness check"]
    baseline = report.get("baseline_date")
    if baseline:
        lines.append(f"Baseline date: {baseline}")
    for name, artifact in report.get("artifacts", {}).items():
        status = "FOUND" if artifact.get("exists") else "MISSING"
        lines.append(
            f"- {name}: {status}, latest_date={artifact.get('latest_date')}, "
            f"rows={artifact.get('metadata', {}).get('rows', 0)}, "
            f"symbols={artifact.get('metadata', {}).get('symbol_count', 0)}, "
            f"path={artifact.get('resolved_path')}"
        )
    for warning in report.get("warnings", []):
        lines.append(f"WARNING: {warning}")
    for error in report.get("errors", []):
        lines.append(f"ERROR: {error}")
    return "\n".join(lines)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate freshness/alignment of pipeline artifacts.")
    parser.add_argument("--base-dir", default=".", help="Project root containing data/ and src/.")
    parser.add_argument("--strict", action="store_true", help="Treat stale warning-level artifacts as errors.")
    parser.add_argument("--scope", default="core", choices=["core", "tracked", "full", "batch", "custom"], help="Update scope context.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report = evaluate_freshness(base_dir=args.base_dir, strict=args.strict, scope=args.scope)
    print(_format_report(report))
    return 1 if report["status"] == "ERROR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
