from datetime import datetime, timedelta
from pathlib import Path
import logging
import time

import pandas as pd

from src.data.loaders import save_parquet, read_parquet

logger = logging.getLogger(__name__)


def _to_datetime(value):
    """
    Convert input date về datetime.
    Input có thể là string, pandas Timestamp, date hoặc datetime.
    """
    if isinstance(value, datetime):
        return value

    return pd.to_datetime(value).to_pydatetime()


def _format_fc_date(value):
    """
    SSI FCData dùng format dd/mm/yyyy.
    Ví dụ: 2020-01-01 -> 01/01/2020
    """
    return pd.to_datetime(value).strftime("%d/%m/%Y")


def _extract_response_data(response):
    """
    Bóc phần data từ response của SSI FCData.

    Response có thể là:
    - dict có key data
    - list records
    - pandas DataFrame
    - error dict như {'status': 429, 'message': ...}
    """
    if response is None:
        return []

    if isinstance(response, pd.DataFrame):
        return response

    if isinstance(response, list):
        return response

    if isinstance(response, dict):
        # Nếu API trả lỗi quota/rate limit thì không coi là data
        status = response.get("status")
        message = str(response.get("message", "")).lower()

        if status == 429 or "quota" in message or "exceeded" in message:
            return []

        for key in [
            "data",
            "dataList",
            "Data",
            "DataList",
            "items",
            "Items",
            "result",
            "Result",
        ]:
            if key in response and response[key] is not None:
                return response[key]

        return response

    return response


def _normalize_daily_ohlc_response(response, symbol: str) -> pd.DataFrame:
    """
    Chuẩn hóa response từ SSI FCData về schema chuẩn:

    symbol | market | date | open | high | low | close | volume | value
    """
    data = _extract_response_data(response)

    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        try:
            df = pd.DataFrame(data)
        except Exception:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "market",
                    "date",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "value",
                ]
            )

    if df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "market",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "value",
            ]
        )

    # Chuẩn hóa tên cột
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={c: c.lower() for c in df.columns})

    # get_daily_stock_price (the fallback endpoint) is structurally different
    # from get_daily_ohlc (the primary): it returns RAW open/high/low/close
    # (openprice/highestprice/lowestprice/closeprice) plus a SEPARATE
    # closepriceadjusted field -- there is no "openpriceadjusted" etc.
    # get_daily_ohlc's own open/high/low/close are already back-adjusted.
    # Mixing the two without reconciling produces a piecewise-adjusted
    # series (confirmed on HPG/TCB: raw closeprice silently mapped to
    # "close" via the old rename_map entry, causing a ~29-day-chunk-aligned
    # step pattern -- see docs/reports/data/BACKFILL_DESIGN_REPORT.md Round 2). Detect a
    # daily_stock_price-shaped response (uniquely identified by
    # closepriceadjusted's presence -- get_daily_ohlc never has this column)
    # and derive a consistently-adjusted OHLC before the generic rename_map
    # below can touch it.
    if "closepriceadjusted" in df.columns and "closeprice" in df.columns:
        raw_close = pd.to_numeric(df["closeprice"], errors="coerce")
        adj_close = pd.to_numeric(df["closepriceadjusted"], errors="coerce")
        adj_factor = adj_close / raw_close.replace(0, pd.NA)
        df["close"] = adj_close
        if "openprice" in df.columns:
            df["open"] = pd.to_numeric(df["openprice"], errors="coerce") * adj_factor
        if "highestprice" in df.columns:
            df["high"] = pd.to_numeric(df["highestprice"], errors="coerce") * adj_factor
        if "lowestprice" in df.columns:
            df["low"] = pd.to_numeric(df["lowestprice"], errors="coerce") * adj_factor
        # volume/value are NOT split-adjusted by either endpoint (confirmed
        # empirically: get_daily_ohlc's volume/value match daily_stock_price's
        # totalmatchvol/totalmatchval exactly, both on the raw share-count
        # basis) -- map directly, no scaling. Note the OLD rename_map below
        # never actually captured these (it looked for "totalvol"/"totalval",
        # not the real field names "totalmatchvol"/"totalmatchval"), so
        # volume/value were silently None for every fallback-sourced chunk
        # even before the close-price bug -- fixed here too.
        if "totalmatchvol" in df.columns:
            df["volume"] = df["totalmatchvol"]
        if "totalmatchval" in df.columns:
            df["value"] = df["totalmatchval"]
        # Drop the raw source columns so the generic rename_map can't
        # re-clobber the adjusted values just computed.
        df = df.drop(columns=[c for c in (
            "closeprice", "openprice", "highestprice", "lowestprice",
            "totalmatchvol", "totalmatchval",
        ) if c in df.columns])

    rename_map = {
        "tradingdate": "date",
        "trading_date": "date",
        "date": "date",
        "symbol": "symbol",
        "stockcode": "symbol",
        "ticker": "symbol",
        "market": "market",
        "marketid": "market",
        "exchange": "market",
        "open": "open",
        "openprice": "open",
        "high": "high",
        "highest": "high",
        "low": "low",
        "lowest": "low",
        "close": "close",
        "closeprice": "close",
        "volume": "volume",
        "totalvol": "volume",
        "totalvolume": "volume",
        "totalqtty": "volume",
        "value": "value",
        "totalval": "value",
        "totalvalue": "value",
    }

    df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})

    if "symbol" not in df.columns:
        df["symbol"] = symbol.upper()

    if "market" not in df.columns:
        df["market"] = None

    if "date" not in df.columns:
        return pd.DataFrame(
            columns=[
                "symbol",
                "market",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "value",
            ]
        )

    # SSI trả ngày dạng dd/mm/yyyy
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=True)

    for col in ["open", "high", "low", "close", "volume", "value"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    required_cols = [
        "symbol",
        "market",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "value",
    ]

    for col in required_cols:
        if col not in df.columns:
            df[col] = None

    df = df[required_cols].copy()

    df["symbol"] = df["symbol"].astype(str).str.upper()

    df = (
        df
        .dropna(subset=["date", "close"])
        .drop_duplicates(["symbol", "date"])
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )

    return df


def _coverage_ratio(df: pd.DataFrame, columns: list[str]) -> float:
    if df.empty:
        return 0.0
    usable = [col for col in columns if col in df.columns]
    if not usable:
        return 0.0
    return float(sum(float(df[col].notna().mean()) for col in usable) / len(usable))


def _merge_daily_frames(primary: pd.DataFrame, fallback: pd.DataFrame) -> pd.DataFrame:
    if primary.empty:
        return fallback.copy()
    if fallback.empty:
        return primary.copy()

    join_cols = ["symbol", "date"]
    keep_cols = ["symbol", "market", "date", "open", "high", "low", "close", "volume", "value"]

    left = primary.copy()
    right = fallback.copy()
    merged = left.merge(
        right[[col for col in keep_cols if col in right.columns]],
        on=join_cols,
        how="outer",
        suffixes=("", "_fb"),
    )

    for col in keep_cols:
        fb_col = f"{col}_fb"
        if col not in merged.columns and fb_col in merged.columns:
            merged[col] = merged[fb_col]
        elif fb_col in merged.columns:
            merged[col] = merged[col].combine_first(merged[fb_col])

    for col in keep_cols:
        if col not in merged.columns:
            merged[col] = None

    return (
        merged[keep_cols]
        .dropna(subset=["date", "close"])
        .drop_duplicates(["symbol", "date"])
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )


def _fetch_chunk_with_fallback(
    client,
    symbol: str,
    from_date: str,
    to_date: str,
) -> tuple[pd.DataFrame, str]:
    """
    Fetch 1 chunk daily data với cơ chế fallback:

    1. Thử endpoint daily_ohlc trước
    2. Nếu empty hoặc thiếu mạnh volume/value/high/low thì fallback sang daily_stock_price

    Returns
    -------
    (df, source_label)
        source_label thuộc:
        - "daily_ohlc"
        - "daily_stock_price"
        - "empty"
    """
    raw = client.get_daily_ohlc(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        page_size=1000,
        max_pages=1,
        ascending=True,
    )
    df = _normalize_daily_ohlc_response(raw, symbol=symbol)
    liquidity_coverage = _coverage_ratio(df, ["volume", "value"])
    range_coverage = _coverage_ratio(df, ["high", "low"])
    needs_fallback = (
        df.empty
        or liquidity_coverage < 0.80
        or range_coverage < 0.80
    )
    if not needs_fallback:
        return df, "daily_ohlc"

    fallback_raw = client.get_daily_stock_price(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        page_size=1000,
        max_pages=1,
    )
    fallback_df = _normalize_daily_ohlc_response(fallback_raw, symbol=symbol)
    merged_df = _merge_daily_frames(df, fallback_df)

    if not merged_df.empty and (
        _coverage_ratio(merged_df, ["volume", "value"]) > liquidity_coverage
        or _coverage_ratio(merged_df, ["high", "low"]) > range_coverage
    ):
        return merged_df, "daily_stock_price"

    if not fallback_df.empty:
        return fallback_df, "daily_stock_price"

    if not df.empty:
        return df, "daily_ohlc_partial"

    return fallback_df, "empty"


def _check_chunk_boundary_jumps(result: pd.DataFrame, boundary_dates: list, market_hint: str | None = None) -> pd.DataFrame:
    """
    Guard against exactly the class of bug found in docs/reports/data/BACKFILL_DESIGN_REPORT.md
    Round 2: a return across a CHUNK boundary that exceeds the symbol's
    exchange price band is a strong signal of an adjustment-basis mismatch
    (or a genuine, very large corporate action) at that seam. Flags into
    `quality_flag` instead of writing silently; does not drop or alter the
    data itself.
    """
    from src.backtest.simulator import load_price_bands

    result = result.copy()
    if "quality_flag" not in result.columns:
        result["quality_flag"] = None

    if result.empty or not boundary_dates:
        return result

    bands, default_band = load_price_bands()
    # Narrowest configured band as the fallback when market is unknown for a
    # row -- erring toward MORE sensitive (catches more, not fewer) borderline
    # cases, since this is a quality guard, not a trading rule.
    fallback_band = min(bands.values()) if bands else default_band

    dated = result.sort_values("date").reset_index(drop=True)
    for boundary in boundary_dates:
        before = dated[dated["date"] <= boundary]
        after = dated[dated["date"] > boundary]
        if before.empty or after.empty:
            continue
        row_before = before.iloc[-1]
        row_after = after.iloc[0]
        close_before, close_after = row_before["close"], row_after["close"]
        if pd.isna(close_before) or pd.isna(close_after) or close_before == 0:
            continue
        pct_change = close_after / close_before - 1
        market = row_after.get("market") or row_before.get("market") or market_hint
        band = bands.get(str(market).upper(), fallback_band) if market else fallback_band
        if abs(pct_change) > band + 0.02:
            logger.warning(
                "[CHUNK_BOUNDARY_JUMP] %s: %s (close=%.2f) -> %s (close=%.2f), pct_change=%+.2f%%, "
                "exceeds band=%.0f%% + 2%% buffer -- flagging quality_flag, not silently written",
                row_after.get("symbol", "?"), row_before["date"].date(), close_before,
                row_after["date"].date(), close_after, pct_change * 100, band * 100,
            )
            idx_after = dated[dated["date"] == row_after["date"]].index
            dated.loc[idx_after, "quality_flag"] = "chunk_boundary_jump"
    return dated


def fetch_symbol_history(
    client,
    symbol: str,
    start_date: str,
    end_date: str,
    output_dir: str = "data/raw/daily_ohlcv",
    chunk_days: int = 29,
    request_sleep: float = 1.2,
    market: str | None = None,
) -> pd.DataFrame:
    """
    Fetch daily OHLCV cho 1 mã theo từng chunk nhỏ.

    Lý do:
    - SSI FCData giới hạn số ngày trong một request.
    - Test thực tế cho thấy 1 request / 1 giây là an toàn hơn.
    - Với chunk 29 ngày, page 1 đã đủ dữ liệu nên max_pages=1.

    market (optional): exchange hint (HOSE/HNX/UPCOM) used only for the
    chunk-boundary price-band guard when a row's own `market` field is
    missing (get_daily_stock_price-sourced rows don't carry it).
    """
    symbol = symbol.upper()
    start = _to_datetime(start_date)
    end = _to_datetime(end_date)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_frames = []
    boundary_dates = []
    current = start

    while current <= end:
        chunk_end = min(current + timedelta(days=chunk_days), end)
        if chunk_end < end:
            boundary_dates.append(chunk_end)

        from_date = _format_fc_date(current)
        to_date = _format_fc_date(chunk_end)

        try:
            df, source_label = _fetch_chunk_with_fallback(
                client=client,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
            )
            if not df.empty:
                all_frames.append(df)
                if source_label == "daily_stock_price":
                    print(f"[FALLBACK_OK] {symbol}: {from_date} -> {to_date}: {len(df)} rows from daily_stock_price")
                elif source_label == "daily_ohlc_partial":
                    print(f"[PARTIAL_OK] {symbol}: {from_date} -> {to_date}: {len(df)} rows from daily_ohlc but liquidity fields still partial")
                else:
                    print(f"[OK] {symbol}: {from_date} -> {to_date}: {len(df)} rows")
            else:
                print(f"[EMPTY] {symbol}: {from_date} -> {to_date} (daily_ohlc + daily_stock_price)")

        except Exception as e:
            print(f"[FAILED] {symbol}: {from_date} -> {to_date}: {e}")

        # SSI FCData có rate limit, tránh gọi liên tục quá nhanh
        time.sleep(request_sleep)

        current = chunk_end + timedelta(days=1)

    if len(all_frames) == 0:
        result = pd.DataFrame(
            columns=[
                "symbol",
                "market",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "value",
                "quality_flag",
            ]
        )
    else:
        result = pd.concat(all_frames, ignore_index=True)

        result = (
            result
            .drop_duplicates(["symbol", "date"])
            .sort_values(["symbol", "date"])
            .reset_index(drop=True)
        )
        result = _check_chunk_boundary_jumps(result, boundary_dates, market_hint=market)

    output_path = output_dir / f"{symbol}.parquet"
    save_parquet(result, output_path)

    return result


def update_symbol_history(
    client,
    symbol: str,
    start_date: str,
    end_date: str,
    output_dir: str = "data/raw/daily_ohlcv",
    chunk_days: int = 29,
    request_sleep: float = 1.2,
    force_refresh: bool = False,
    refresh_recent_days: int = 5,
    market_latest_date=None,
    market: str | None = None,
) -> pd.DataFrame:
    """
    Update dữ liệu daily OHLCV cho 1 mã.

    Nếu force_refresh=True:
        Fetch lại toàn bộ từ start_date đến end_date.

    Nếu force_refresh=False:
        Chỉ fetch phần dữ liệu mới sau ngày cuối đã lưu.

    market (optional): exchange hint (HOSE/HNX/UPCOM), passed through to
    fetch_symbol_history's chunk-boundary price-band guard.
    """
    symbol = symbol.upper()
    output_path = Path(output_dir) / f"{symbol}.parquet"

    if force_refresh or not output_path.exists():
        return fetch_symbol_history(
            client=client,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            chunk_days=chunk_days,
            request_sleep=request_sleep,
            market=market,
        )

    old = read_parquet(output_path)

    if old.empty:
        return fetch_symbol_history(
            client=client,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            chunk_days=chunk_days,
            request_sleep=request_sleep,
            market=market,
        )

    old["date"] = pd.to_datetime(old["date"])
    last_date = old["date"].max()

    if not force_refresh and market_latest_date is not None:
        market_latest_dt = pd.to_datetime(market_latest_date)
        if last_date >= market_latest_dt:
            print(f"[SKIP_UP_TO_DATE] {symbol}: data already up to date up to {market_latest_dt.strftime('%Y-%m-%d')}.")
            return old

    old["date"] = pd.to_datetime(old["date"])
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    last_date = old["date"].max()
    refresh_anchor = last_date - timedelta(days=max(refresh_recent_days - 1, 0))
    refresh_start_dt = max(start_dt, refresh_anchor)
    refresh_start = refresh_start_dt.strftime("%Y-%m-%d")

    if refresh_start_dt > end_dt:
        print(f"[SKIP] {symbol}: data already up to date.")
        return old

    new = fetch_symbol_history(
        client=client,
        symbol=symbol,
        start_date=refresh_start,
        end_date=end_date,
        output_dir=output_dir,
        chunk_days=chunk_days,
        request_sleep=request_sleep,
        market=market,
    )

    old_prefix = old[old["date"] < refresh_start_dt].copy()
    frames = [df for df in (old_prefix, new) if not df.empty]
    if not frames:
        combined = old.iloc[0:0].copy()
    else:
        combined = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates(["symbol", "date"])
            .sort_values(["symbol", "date"])
            .reset_index(drop=True)
        )

    save_parquet(combined, output_path)

    return combined
