from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Iterable, Optional

import pandas as pd

from src.data import fcdata_config as config
from src.utils.date_utils import chunk_date_range, to_ssi_date
from src.utils.logger import get_logger

try:
    from ssi_fc_data import fc_md_client, model
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Package `ssi_fc_data` is not installed. Run: "
        "pip install /path/to/ssi_fc_data-2.2.2.tar.gz or pip install ssi-fc-data"
    ) from exc

logger = get_logger(__name__)


def _as_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    return obj


def extract_records(response: Any) -> list[dict[str, Any]]:
    """Extract tabular records from common FCData response shapes.

    FCData responses are not perfectly uniform across endpoints. This helper
    supports typical shapes such as:
    - {"data": [...]}
    - {"dataList": [...]}
    - {"dataList": [{"repeatedinfoList": [...]}]}
    - raw JSON string containing any of the above.
    """
    if response is None:
        return []
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError:
            return []
    if isinstance(response, list):
        records: list[dict[str, Any]] = []
        for item in response:
            if isinstance(item, dict):
                records.extend(extract_records(item))
        return records
    if not isinstance(response, dict):
        return []

    # Direct list fields usually used by FCData.
    for key in ("data", "dataList", "Data", "DataList"):
        if key in response and isinstance(response[key], list):
            data = response[key]
            # SecuritiesDetails often nests repeatedinfoList inside dataList.
            nested: list[dict[str, Any]] = []
            for item in data:
                if isinstance(item, dict):
                    for nested_key in ("repeatedinfoList", "repeatedInfoList", "RepeatedInfoList"):
                        if nested_key in item and isinstance(item[nested_key], list):
                            nested.extend([x for x in item[nested_key] if isinstance(x, dict)])
                    if not any(k in item for k in ("repeatedinfoList", "repeatedInfoList", "RepeatedInfoList")):
                        nested.append(item)
            return nested

    # Streaming-like response may carry Content as JSON string.
    for key in ("content", "Content"):
        if key in response:
            return extract_records(response[key])

    # If it already looks like a single record.
    metadata_keys = {"message", "status", "totalRecord", "totalrecord", "responseCode"}
    if any(k.lower() in {"symbol", "tradingdate", "date", "indexcode", "indexid"} for k in response.keys()):
        return [response]
    if not set(response.keys()).issubset(metadata_keys):
        return [response]
    return []


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize FCData's mixed casing into snake_case-like lower columns."""
    if df.empty:
        return df
    rename = {c: str(c).strip().replace(" ", "_").replace("-", "_").lower() for c in df.columns}
    return df.rename(columns=rename)


class SSIDataClient:
    """Thin, notebook-friendly wrapper around SSI FCData MarketDataClient."""

    def __init__(self, validate_credentials: bool = True, retry_count: int = 3, retry_sleep: float = 1.5):
        if validate_credentials:
            config.validate_config()
        self.client = fc_md_client.MarketDataClient(config)
        self.retry_count = retry_count
        self.retry_sleep = retry_sleep
        self.last_call_time = 0.0

    def _validate_response(self, res: Any) -> None:
        if res is None:
            return
        parsed = None
        if isinstance(res, str):
            try:
                parsed = json.loads(res)
            except json.JSONDecodeError:
                pass
        elif isinstance(res, dict):
            parsed = res

        if isinstance(parsed, dict):
            status = parsed.get("status")
            code = parsed.get("responseCode") or parsed.get("code")
            message = str(parsed.get("message", "")).strip().lower()
            
            status_str = str(status).strip().lower() if status is not None else ""
            code_str = str(code).strip().lower() if code is not None else ""
            
            # Treat standard "no data" responses as valid empty successes
            is_no_data = (
                status_str in ("nodatafound", "nodata", "no_data", "no-data")
                or code_str in ("nodatafound", "nodata", "no_data", "no-data")
                or (status_str == "error" and ("there is no data" in message or "no data" in message))
            )
            
            if is_no_data:
                return

            if status is not None:
                if status_str not in ("success", "200", "00", "0", "true"):
                    raise RuntimeError(f"SSI API returned error status '{status}': {parsed.get('message', 'Unknown error')}")
            
            if code is not None:
                if code_str not in ("success", "200", "00", "0", "true"):
                    raise RuntimeError(f"SSI API returned error code '{code}': {parsed.get('message', 'Unknown error')}")

    def _call(self, func: Callable[[], Any]) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, self.retry_count + 1):
            # Client-side rate limiter: ensure at least 1.0 second delay between calls
            elapsed = time.time() - self.last_call_time
            if elapsed < 1.0:
                time.sleep(1.0 - elapsed)
            try:
                res = func()
                self.last_call_time = time.time()
                self._validate_response(res)
                return res
            except Exception as exc:  # pragma: no cover - depends on network/API
                self.last_call_time = time.time()
                last_error = exc
                logger.warning("FCData call failed on attempt %s/%s: %s", attempt, self.retry_count, exc)
                time.sleep(self.retry_sleep * attempt)
        raise RuntimeError(f"FCData call failed after {self.retry_count} attempts") from last_error


    def _to_frame(self, response: Any) -> pd.DataFrame:
        records = extract_records(response)
        return normalize_columns(pd.DataFrame(records))

    def _paginate(self, build_request: Callable[[int], Any], call: Callable[[Any], Any], page_size: int = 1000, max_pages: int = 10) -> pd.DataFrame:
        frames = []
        for page in range(1, max_pages + 1):
            req = build_request(page)
            response = self._call(lambda req=req: call(req))
            df = self._to_frame(response)
            if df.empty:
                break
            frames.append(df)
            if len(df) < page_size:
                break
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def get_access_token_raw(self) -> Any:
        return self._call(lambda: self.client.access_token(model.accessToken(config.consumerID, config.consumerSecret)))

    def get_securities(self, market: str = "", page_size: int = 1000, max_pages: int = 10) -> pd.DataFrame:
        return self._paginate(
            build_request=lambda page: model.securities(market, page, page_size),
            call=lambda req: self.client.securities(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_securities_details(self, market: str = "", symbol: str = "", page_size: int = 1000, max_pages: int = 10) -> pd.DataFrame:
        return self._paginate(
            build_request=lambda page: model.securities_details(market, symbol, page, page_size),
            call=lambda req: self.client.securities_details(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_index_components(self, index_code: str, page_size: int = 1000, max_pages: int = 10) -> pd.DataFrame:
        return self._paginate(
            build_request=lambda page: model.index_components(index_code, page, page_size),
            call=lambda req: self.client.index_components(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_index_list(self, exchange: str = "", page_size: int = 1000, max_pages: int = 10) -> pd.DataFrame:
        return self._paginate(
            build_request=lambda page: model.index_list(exchange, page, page_size),
            call=lambda req: self.client.index_list(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_daily_ohlc(self, symbol: str, from_date: str, to_date: str, page_size: int = 1000, max_pages: int = 10, ascending: bool = True) -> pd.DataFrame:
        from_date = to_ssi_date(from_date)
        to_date = to_ssi_date(to_date)
        df = self._paginate(
            build_request=lambda page: model.daily_ohlc(symbol, from_date, to_date, page, page_size, ascending),
            call=lambda req: self.client.daily_ohlc(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )
        if not df.empty and "symbol" not in df.columns:
            df["symbol"] = symbol.upper()
        return df

    def get_daily_ohlc_chunked(self, symbol: str, start_date: str, end_date: str, chunk_days: int = 30, page_size: int = 1000) -> pd.DataFrame:
        frames = []
        for from_date, to_date in chunk_date_range(start_date, end_date, chunk_days=chunk_days):
            logger.info("Fetching DailyOhlc %s: %s -> %s", symbol, from_date, to_date)
            df = self.get_daily_ohlc(symbol, from_date, to_date, page_size=page_size)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        out = pd.concat(frames, ignore_index=True)
        return out.drop_duplicates().reset_index(drop=True)

    def get_intraday_ohlc(self, symbol: str, from_date: str, to_date: str, resolution: int = 1, page_size: int = 1000, max_pages: int = 10, ascending: bool = True) -> pd.DataFrame:
        from_date = to_ssi_date(from_date)
        to_date = to_ssi_date(to_date)
        return self._paginate(
            build_request=lambda page: model.intraday_ohlc(symbol, from_date, to_date, page, page_size, ascending, resolution),
            call=lambda req: self.client.intraday_ohlc(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_daily_index(self, index_id: str, from_date: str, to_date: str, request_id: str = "1", page_size: int = 1000, max_pages: int = 10, order_by: str = "", order: str = "") -> pd.DataFrame:
        from_date = to_ssi_date(from_date)
        to_date = to_ssi_date(to_date)
        return self._paginate(
            build_request=lambda page: model.daily_index(request_id, index_id, from_date, to_date, page, page_size, order_by, order),
            call=lambda req: self.client.daily_index(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )

    def get_daily_index_chunked(self, index_id: str, start_date: str, end_date: str, chunk_days: int = 30, page_size: int = 1000) -> pd.DataFrame:
        frames = []
        for from_date, to_date in chunk_date_range(start_date, end_date, chunk_days=chunk_days):
            logger.info("Fetching DailyIndex %s: %s -> %s", index_id, from_date, to_date)
            df = self.get_daily_index(index_id, from_date, to_date, page_size=page_size)
            if not df.empty:
                frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True).drop_duplicates().reset_index(drop=True)

    def get_daily_stock_price(self, symbol: str, from_date: str, to_date: str, market: str = "", page_size: int = 1000, max_pages: int = 10) -> pd.DataFrame:
        from_date = to_ssi_date(from_date)
        to_date = to_ssi_date(to_date)
        return self._paginate(
            build_request=lambda page: model.daily_stock_price(symbol, from_date, to_date, page, page_size, market),
            call=lambda req: self.client.daily_stock_price(config, req),
            page_size=page_size,
            max_pages=max_pages,
        )
