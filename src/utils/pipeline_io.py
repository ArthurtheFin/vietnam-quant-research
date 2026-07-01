from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

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
        ),
        label="pipeline_metadata.json",
    )
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
    return payload
