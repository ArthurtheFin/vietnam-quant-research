from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

REQUIRED_OHLCV = {"symbol", "date", "open", "high", "low", "close", "volume"}


def project_root(start: str | Path | None = None) -> Path:
    path = Path(start or Path.cwd()).resolve()
    for candidate in [path, *path.parents]:
        if (candidate / "data").exists() and (candidate / "stock-decision-engine").exists():
            return candidate
    raise FileNotFoundError("Cannot find project root containing data/ and stock-decision-engine/.")


def engine_root(root: Path | None = None) -> Path:
    root = root or project_root()
    return root / "stock-decision-engine"


def load_config(path: str | Path | None = None, root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    cfg_path = Path(path) if path else engine_root(root) / "config.yaml"
    if not cfg_path.is_absolute():
        cfg_path = (Path.cwd() / cfg_path).resolve()
        if not cfg_path.exists():
            cfg_path = (engine_root(root) / "notebooks" / path).resolve()
        if not cfg_path.exists():
            cfg_path = engine_root(root) / Path(path).name
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def _normalize(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    aliases = {
        "tradingdate": "date",
        "time": "date",
        "matchprice": "close",
        "totalmatchvol": "volume",
        "totalmatchval": "value",
        "totalval": "value",
    }
    for src, dst in aliases.items():
        if src in out.columns and dst not in out.columns:
            out = out.rename(columns={src: dst})
    out = out.loc[:, ~out.columns.duplicated()]
    if "symbol" not in out.columns and symbol:
        out["symbol"] = symbol.upper()
    if "date" in out.columns:
        out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.tz_localize(None)
    for col in ["open", "high", "low", "close", "volume", "value"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "value" not in out.columns and {"close", "volume"}.issubset(out.columns):
        out["value"] = out["close"] * out["volume"]
    if "symbol" in out.columns:
        out["symbol"] = out["symbol"].astype(str).str.upper()
    return out.dropna(subset=[c for c in ["date", "close"] if c in out.columns]).sort_values("date")


def _validate_ohlcv(df: pd.DataFrame, label: str) -> None:
    missing = sorted(REQUIRED_OHLCV - set(df.columns))
    if missing:
        raise ValueError(f"{label} is missing required OHLCV columns: {missing}")


def available_tickers(root: Path | None = None) -> list[str]:
    root = root or project_root()
    symbols: set[str] = set()
    processed = root / "data/processed/clean_daily_ohlcv.parquet"
    if processed.exists():
        df = pd.read_parquet(processed, columns=["symbol"])
        symbols.update(df["symbol"].dropna().astype(str).str.upper().unique())
    raw_dir = root / "data/raw/daily_ohlcv"
    if raw_dir.exists():
        symbols.update(p.stem.upper() for p in raw_dir.glob("*.parquet"))
    return sorted(symbols)


def load_stock_ohlcv(ticker: str, root: Path | None = None, lookback_days: int | None = None) -> pd.DataFrame:
    root = root or project_root()
    ticker = ticker.upper()
    paths = [root / "data/processed/clean_daily_ohlcv.parquet", root / f"data/raw/daily_ohlcv/{ticker}.parquet"]
    errors: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        df = _normalize(df, ticker)
        if "symbol" in df.columns:
            df = df[df["symbol"].astype(str).str.upper() == ticker]
        if df.empty:
            errors.append(f"{path.relative_to(root)} has no rows for {ticker}.")
            continue
        _validate_ohlcv(df, ticker)
        return df.tail(lookback_days).reset_index(drop=True) if lookback_days else df.reset_index(drop=True)
    tickers = ", ".join(available_tickers(root)[:80])
    raise FileNotFoundError(f"Ticker {ticker} not found. Available tickers include: {tickers}")


def load_benchmark_ohlcv(benchmark: str = "VNINDEX", root: Path | None = None, lookback_days: int | None = None) -> pd.DataFrame:
    root = root or project_root()
    symbol = benchmark.upper()
    slug = symbol.lower()
    paths = [
        root / f"data/processed/benchmark_{slug}.parquet",
        root / "data/processed/index_features.parquet",
        root / f"data/raw/index_ohlcv/{symbol}.parquet",
        root / "data/processed/clean_daily_ohlcv.parquet",
    ]
    for path in paths:
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        df = _normalize(df, symbol)
        if "symbol" in df.columns:
            df = df[df["symbol"].astype(str).str.upper().isin([symbol, slug.upper()])]
        if df.empty:
            continue
        if not {"open", "high", "low"}.issubset(df.columns):
            df["open"] = df.get("open", df["close"])
            df["high"] = df.get("high", df["close"])
            df["low"] = df.get("low", df["close"])
        df["volume"] = df.get("volume", df.get("totalmatchvol", 0.0))
        df["value"] = df.get("value", df["close"] * df["volume"])
        _validate_ohlcv(df, symbol)
        return df.tail(lookback_days).reset_index(drop=True) if lookback_days else df.reset_index(drop=True)
    raise FileNotFoundError(
        f"Benchmark {symbol} not found. Add data/processed/benchmark_{slug}.parquet "
        f"or data/raw/index_ohlcv/{symbol}.parquet."
    )


def load_backtest_evidence(ticker: str, root: Path | None = None) -> dict[str, Any]:
    root = root or project_root()
    ticker = ticker.upper()
    evidence: dict[str, Any] = {"available": False}
    cards = root / "data/signals/breakout_20d_trade_cards.parquet"
    if cards.exists():
        df = _normalize(pd.read_parquet(cards), ticker)
        if "symbol" in df.columns:
            row = df[df["symbol"].astype(str).str.upper() == ticker].sort_values("date").tail(1)
            if not row.empty:
                r = row.iloc[0]
                evidence.update(
                    available=True,
                    source=str(cards.relative_to(root)),
                    profit_factor=_num(r.get("profit_factor")),
                    average_return=_num(r.get("avg_return")),
                    median_return=_num(r.get("median_return")),
                    setup_quality_score=_num(r.get("setup_quality_score")),
                    trade_edge_score=_num(r.get("trade_edge_score")),
                    action=str(r.get("action", "")),
                )
    summary = root / "data/signals/breakout_20d_atr_stop_summary.parquet"
    if summary.exists():
        df = pd.read_parquet(summary)
        if not df.empty:
            row = df.sort_values("atr_multiple").iloc[(df["atr_multiple"] - 2.0).abs().argsort()[:1]]
            r = row.iloc[0]
            evidence.setdefault("available", True)
            evidence.setdefault("source", str(summary.relative_to(root)))
            evidence.update(
                historical_win_rate=_num(r.get("win_rate")),
                stop_hit_rate=_num(r.get("stop_rate")),
                expectancy=_num(r.get("avg_return")),
            )
    return evidence


def _num(value: Any) -> float | None:
    out = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(out) else float(out)
