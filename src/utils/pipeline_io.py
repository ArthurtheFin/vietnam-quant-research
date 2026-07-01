from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from src.data.loaders import read_parquet


DEFAULT_DATE_COLUMNS: tuple[str, ...] = (
    "analysis_date",
    "date",
    "trade_card_date",
    "stealth_date",
)


@dataclass(frozen=True)
class WatchlistSource:
    source_name: str
    source_path: Path | None
    data: pd.DataFrame
    latest_date: pd.Timestamp | None
    symbols: list[str]

    @property
    def is_empty(self) -> bool:
        return self.data.empty

    def metadata(self) -> dict[str, object]:
        return {
            "source_name": self.source_name,
            "source_path": str(self.source_path) if self.source_path is not None else None,
            "source_latest_date": None if self.latest_date is None else self.latest_date.date().isoformat(),
            "symbols": self.symbols,
            "symbol_count": len(self.symbols),
            "generated_at": utc_now_iso(),
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def latest_timestamp(
    df: pd.DataFrame,
    candidates: Iterable[str] = DEFAULT_DATE_COLUMNS,
) -> pd.Timestamp | None:
    if df.empty:
        return None
    for column in candidates:
        if column not in df.columns:
            continue
        values = pd.to_datetime(df[column], errors="coerce").dropna()
        if not values.empty:
            return values.max()
    return None


def unique_symbols(df: pd.DataFrame, symbol_col: str = "symbol") -> list[str]:
    if df.empty or symbol_col not in df.columns:
        return []
    return sorted(
        {
            str(symbol).strip().upper()
            for symbol in df[symbol_col].dropna().tolist()
            if str(symbol).strip()
        }
    )


def dataframe_metadata(
    df: pd.DataFrame,
    path: str | Path | None = None,
    date_candidates: Iterable[str] = DEFAULT_DATE_COLUMNS,
    symbol_col: str = "symbol",
) -> dict[str, object]:
    latest = latest_timestamp(df, candidates=date_candidates)
    return {
        "path": None if path is None else str(Path(path)),
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "symbol_count": int(df[symbol_col].nunique()) if symbol_col in df.columns else 0,
        "latest_date": None if latest is None else latest.date().isoformat(),
    }


def read_first_existing_parquet(
    paths: Iterable[str | Path],
    base_dir: str | Path = ".",
) -> tuple[pd.DataFrame, Path | None]:
    base = Path(base_dir)
    for relative_path in paths:
        candidate = base / relative_path
        if candidate.exists():
            return read_parquet(candidate), candidate
    return pd.DataFrame(), None


def resolve_watchlist_source(
    base_dir: str | Path = ".",
    source_candidates: Iterable[tuple[str, str]] | None = None,
) -> WatchlistSource:
    candidates = list(
        source_candidates
        or [
            ("client_ready_watchlist", "data/output/client_ready_watchlist.parquet"),
            ("trading_watchlist", "data/output/trading_watchlist.parquet"),
            ("final_watchlist", "data/signals/final_watchlist.parquet"),
        ]
    )
    base = Path(base_dir)
    for source_name, relative_path in candidates:
        path = base / relative_path
        if not path.exists():
            continue
        df = read_parquet(path)
        if df.empty:
            continue
        symbols = unique_symbols(df)
        if not symbols:
            continue
        return WatchlistSource(
            source_name=source_name,
            source_path=path,
            data=df.copy(),
            latest_date=latest_timestamp(df),
            symbols=symbols,
        )

    return WatchlistSource(
        source_name="missing_watchlist_source",
        source_path=None,
        data=pd.DataFrame(),
        latest_date=None,
        symbols=[],
    )


def write_json(payload: dict[str, object], path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def relative_path(path: str | Path | None, base_dir: str | Path = ".") -> str | None:
    if path is None:
        return None
    candidate = Path(path)
    base = Path(base_dir).resolve()
    try:
        return str(candidate.resolve().relative_to(base))
    except Exception:
        return str(candidate)


def _validate_required_keys(payload: dict[str, object], required_keys: Iterable[str], label: str) -> None:
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"{label} is missing required key(s): {', '.join(missing)}")


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_absolute_path(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_absolute_path(item) for item in value)
    if isinstance(value, str):
        try:
            return Path(value).is_absolute()
        except Exception:
            return False
    return False


def _validate_no_absolute_paths(payload: dict[str, object], label: str) -> None:
    if _contains_absolute_path(payload):
        raise ValueError(f"{label} must not contain absolute filesystem paths")


def validate_pipeline_metadata(payload: dict[str, object]) -> dict[str, object]:
    _validate_required_keys(
        payload,
        required_keys=(
            "run_timestamp",
            "run_mode",
            "freshness_status",
            "benchmark_status",
            "generated_files",
            "watchlist_counts",
            "portfolio_stack",
            "online_update",
            "sector_board",
            "cashflow_board",
            "research_notes",
        ),
        label="pipeline_metadata.json",
    )
    _validate_no_absolute_paths(payload, "pipeline_metadata.json")
    return payload


def validate_portfolio_stack_metadata(payload: dict[str, object]) -> dict[str, object]:
    _validate_required_keys(
        payload,
        required_keys=(
            "generated_at",
            "source_watchlist",
            "source_file",
            "symbols_used",
            "missing_symbols",
            "generated_files",
            "status",
            "warnings",
        ),
        label="portfolio_stack_metadata.json",
    )
    _validate_no_absolute_paths(payload, "portfolio_stack_metadata.json")
    return payload


def validate_sector_board_metadata(payload: dict[str, object]) -> dict[str, object]:
    _validate_required_keys(
        payload,
        required_keys=(
            "generated_at",
            "status",
            "latest_date",
            "n_sectors",
            "sector_map_source",
            "sector_map_rows",
            "sector_map_template",
            "mapping_coverage",
            "unknown_ratio",
            "total_symbols",
            "mapped_symbols",
            "missing_symbols",
            "warnings",
            "generated_files",
        ),
        label="sector_board_metadata.json",
    )
    _validate_no_absolute_paths(payload, "sector_board_metadata.json")
    return payload


def build_run_snapshot(metadata: dict[str, object], base_dir: str | Path = ".") -> dict[str, object]:
    base = Path(base_dir)
    trading_df = read_parquet(base / "data/output/trading_watchlist.parquet")
    client_ready_df = read_parquet(base / "data/output/client_ready_watchlist.parquet")
    portfolio_df = pd.DataFrame()
    if metadata.get("portfolio_stack", {}).get("enabled"):
        portfolio_df, _ = read_first_existing_parquet(
            [
                "data/output/portfolio_weights.parquet",
                "data/output/portfolio_candidates.parquet",
                "data/output/capital_plan.parquet",
            ],
            base_dir=base,
        )
    return {
        "run_timestamp": metadata.get("run_timestamp"),
        "run_mode": metadata.get("run_mode"),
        "flags_used": metadata.get("flags_used", []),
        "freshness_status": metadata.get("freshness_status"),
        "benchmark_latest_date": metadata.get("benchmark_status", {}).get("benchmark_latest_date"),
        "stock_latest_date": metadata.get("latest_stock_date"),
        "watchlist_counts": metadata.get("watchlist_counts", {}),
        "trading_watchlist_symbols": unique_symbols(trading_df),
        "client_ready_symbols": unique_symbols(client_ready_df),
        "portfolio_symbols": unique_symbols(portfolio_df),
        "warnings": metadata.get("warnings", []),
        "errors": metadata.get("errors", []),
        "generated_files": metadata.get("generated_files", []),
    }


def write_run_snapshot(metadata: dict[str, object], base_dir: str | Path = ".") -> Path:
    snapshot = build_run_snapshot(metadata, base_dir=base_dir)
    timestamp = pd.to_datetime(snapshot["run_timestamp"], utc=True, errors="coerce")
    if pd.isna(timestamp):
        filename = "run_unknown.json"
    else:
        filename = f"run_{timestamp.tz_convert(None).strftime('%Y-%m-%d_%H%M%S')}.json"
    output_path = Path(base_dir) / "data/output/run_history" / filename
    write_json(snapshot, output_path)
    return output_path


def load_run_snapshots(base_dir: str | Path = ".", limit: int | None = None) -> list[dict[str, object]]:
    run_history_dir = Path(base_dir) / "data/output/run_history"
    if not run_history_dir.exists():
        return []
    paths = sorted(run_history_dir.glob("run_*.json"))
    if limit is not None:
        paths = paths[-limit:]
    snapshots: list[dict[str, object]] = []
    for path in paths:
        snapshots.append(json.loads(path.read_text(encoding="utf-8")))
    return snapshots


def compare_run_snapshots(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    previous_client = set(previous.get("client_ready_symbols", []))
    current_client = set(current.get("client_ready_symbols", []))
    previous_portfolio = set(previous.get("portfolio_symbols", []))
    current_portfolio = set(current.get("portfolio_symbols", []))
    previous_counts = previous.get("watchlist_counts", {})
    current_counts = current.get("watchlist_counts", {})

    def _count_delta(name: str) -> dict[str, int]:
        prev_rows = int(previous_counts.get(name, {}).get("rows", 0))
        curr_rows = int(current_counts.get(name, {}).get("rows", 0))
        return {"previous": prev_rows, "current": curr_rows, "delta": curr_rows - prev_rows}

    return {
        "current_run_timestamp": current.get("run_timestamp"),
        "previous_run_timestamp": previous.get("run_timestamp"),
        "client_ready_added": sorted(current_client - previous_client),
        "client_ready_removed": sorted(previous_client - current_client),
        "portfolio_added": sorted(current_portfolio - previous_portfolio),
        "portfolio_removed": sorted(previous_portfolio - current_portfolio),
        "watchlist_count_changes": {
            "research_candidates": _count_delta("research_candidates"),
            "trading_watchlist": _count_delta("trading_watchlist"),
            "client_ready_watchlist": _count_delta("client_ready_watchlist"),
        },
        "freshness_status_changed": previous.get("freshness_status") != current.get("freshness_status"),
        "freshness_status_previous": previous.get("freshness_status"),
        "freshness_status_current": current.get("freshness_status"),
        "benchmark_date_changed": previous.get("benchmark_latest_date") != current.get("benchmark_latest_date"),
        "benchmark_latest_date_previous": previous.get("benchmark_latest_date"),
        "benchmark_latest_date_current": current.get("benchmark_latest_date"),
    }
