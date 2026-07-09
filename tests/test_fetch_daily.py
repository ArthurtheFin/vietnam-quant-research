"""Regression tests for the fetch_daily.py adjustment-basis bug found in
BACKFILL_DESIGN_REPORT.md Round 2: get_daily_stock_price's raw `closeprice`
was silently mapped to `close` in the fallback path instead of the
separately-provided `closepriceadjusted`, producing a piecewise-adjusted
series with a step every ~29-day chunk boundary (confirmed on real HPG/TCB
data -- ratio to a clean re-fetch was piecewise-constant, not noise and not
a single real corporate-action date)."""
from __future__ import annotations

import logging

import pandas as pd
import pytest

from src.data.fetch_daily import _normalize_daily_ohlc_response, fetch_symbol_history


def _daily_stock_price_response(dates: list[str], raw_close: list[float], adj_close: list[float]) -> pd.DataFrame:
    """Shape a synthetic get_daily_stock_price-like response with a deliberate
    raw-vs-adjusted mismatch (mirrors the real API's field names)."""
    return pd.DataFrame({
        "tradingdate": dates,
        "symbol": ["TST"] * len(dates),
        "openprice": raw_close,
        "highestprice": [c * 1.01 for c in raw_close],
        "lowestprice": [c * 0.99 for c in raw_close],
        "closeprice": raw_close,
        "closepriceadjusted": adj_close,
        "totalmatchvol": [1_000_000] * len(dates),
        "totalmatchval": [c * 1_000_000 for c in raw_close],
    })


def _daily_ohlc_response(dates: list[str], close: list[float], market: str = "HOSE") -> pd.DataFrame:
    """Shape a synthetic get_daily_ohlc-like response (already adjusted)."""
    return pd.DataFrame({
        "tradingdate": dates,
        "symbol": ["TST"] * len(dates),
        "market": [market] * len(dates),
        "open": close,
        "high": [c * 1.01 for c in close],
        "low": [c * 0.99 for c in close],
        "close": close,
        "volume": [1_000_000] * len(dates),
        "value": [c * 1_000_000 for c in close],
    })


def test_normalize_daily_stock_price_response_uses_adjusted_close():
    """Direct unit test on the fix: closepriceadjusted must win over closeprice,
    and open/high/low must be scaled by the same factor (proportional
    back-adjustment), volume/value passed through raw (unscaled, per the
    empirically-confirmed convention that neither endpoint adjusts them)."""
    raw = _daily_stock_price_response(
        dates=["03/01/2023", "04/01/2023"],
        raw_close=[20000.0, 20200.0],   # deliberately 2x the adjusted basis
        adj_close=[10000.0, 10100.0],
    )
    normalized = _normalize_daily_ohlc_response(raw, symbol="TST")

    assert list(normalized["close"]) == pytest.approx([10000.0, 10100.0])
    # open/high/low scaled by the same adj_factor (0.5) as close, not left raw
    assert normalized["open"].iloc[0] == pytest.approx(20000.0 * 0.5)
    assert normalized["high"].iloc[0] == pytest.approx(20000.0 * 1.01 * 0.5)
    assert normalized["low"].iloc[0] == pytest.approx(20000.0 * 0.99 * 0.5)
    # volume/value are NOT split-adjusted -- raw totalmatchvol/totalmatchval pass through
    assert normalized["volume"].iloc[0] == 1_000_000
    assert normalized["value"].iloc[0] == pytest.approx(20000.0 * 1_000_000)


def test_normalize_daily_ohlc_response_unaffected_by_the_fix():
    """The primary endpoint's response (no closepriceadjusted column) must be
    completely untouched by the new adjustment-detection branch."""
    raw = _daily_ohlc_response(dates=["03/01/2023", "04/01/2023"], close=[10000.0, 10100.0])
    normalized = _normalize_daily_ohlc_response(raw, symbol="TST")
    assert list(normalized["close"]) == pytest.approx([10000.0, 10100.0])
    assert list(normalized["open"]) == pytest.approx([10000.0, 10100.0])


class _FakeClient:
    """Minimal stand-in for SSIDataClient: primary (get_daily_ohlc) serves the
    first chunk on its own adjusted basis; the second chunk is deliberately
    EMPTY from get_daily_ohlc (forcing the fallback) and served by
    get_daily_stock_price with a raw close at a different scale than the
    first chunk's adjusted basis -- exactly the historical bug scenario."""

    def __init__(self, boundary_date: pd.Timestamp, scale_mismatch: float = 2.0):
        self.boundary_date = boundary_date
        self.scale_mismatch = scale_mismatch

    def get_daily_ohlc(self, symbol, from_date, to_date, page_size=1000, max_pages=1, ascending=True):
        start = pd.to_datetime(from_date, dayfirst=True)
        if start >= self.boundary_date:
            return pd.DataFrame()  # forces fallback for the second chunk
        dates = pd.bdate_range(start, pd.to_datetime(to_date, dayfirst=True))
        dates_str = [d.strftime("%d/%m/%Y") for d in dates]
        close = [10000.0 + i * 10 for i in range(len(dates))]
        return _daily_ohlc_response(dates_str, close)

    def get_daily_stock_price(self, symbol, from_date, to_date, page_size=1000, max_pages=1):
        start = pd.to_datetime(from_date, dayfirst=True)
        if start < self.boundary_date:
            return pd.DataFrame()
        dates = pd.bdate_range(start, pd.to_datetime(to_date, dayfirst=True))
        dates_str = [d.strftime("%d/%m/%Y") for d in dates]
        # Adjusted basis continues smoothly from where the primary left off
        # (~10100-ish); raw closeprice is deliberately scaled up to simulate
        # the historical mismatch.
        adj_close = [10100.0 + i * 10 for i in range(len(dates))]
        raw_close = [c * self.scale_mismatch for c in adj_close]
        return _daily_stock_price_response(dates_str, raw_close, adj_close)


def test_fetch_symbol_history_no_step_across_fallback_chunk_boundary(tmp_path):
    """End-to-end: after the fix, stitching a primary-served chunk with a
    fallback-served chunk (deliberately 2x raw/adjusted mismatch) must NOT
    produce a step in the close series -- every consecutive-day return stays
    within a sane band, unlike the pre-fix behavior which would show a ~100%
    jump at the boundary (mirroring the real HPG +58%/TCB +124.8% jumps)."""
    boundary = pd.Timestamp("2023-01-16")
    client = _FakeClient(boundary_date=boundary, scale_mismatch=2.0)

    result = fetch_symbol_history(
        client=client,
        symbol="TST",
        start_date="2023-01-02",
        end_date="2023-01-27",
        output_dir=str(tmp_path / "raw"),
        chunk_days=13,  # splits into a pre-boundary and post-boundary chunk
        request_sleep=0.0,
        market="HOSE",
    )
    result = result.sort_values("date").reset_index(drop=True)
    result["return_1d"] = result["close"].pct_change()

    max_abs_return = result["return_1d"].abs().max()
    assert max_abs_return < 0.09, (
        f"expected no step across the fallback boundary after the fix, got max |return_1d|={max_abs_return:.2%}"
    )


def test_chunk_boundary_guard_flags_large_jump(tmp_path, caplog):
    """A genuine large jump AT a chunk boundary (not an adjustment-basis bug --
    both chunks internally consistent) must still be flagged into
    quality_flag and logged as a WARNING, not written silently."""
    boundary = pd.Timestamp("2023-01-16")

    class _BigJumpClient:
        def get_daily_ohlc(self, symbol, from_date, to_date, page_size=1000, max_pages=1, ascending=True):
            start = pd.to_datetime(from_date, dayfirst=True)
            dates = pd.bdate_range(start, pd.to_datetime(to_date, dayfirst=True))
            dates_str = [d.strftime("%d/%m/%Y") for d in dates]
            base = 10000.0 if start < boundary else 15000.0  # deliberate +50% jump at the seam
            close = [base + i * 5 for i in range(len(dates))]
            return _daily_ohlc_response(dates_str, close)

        def get_daily_stock_price(self, symbol, from_date, to_date, page_size=1000, max_pages=1):
            return pd.DataFrame()

    with caplog.at_level(logging.WARNING, logger="src.data.fetch_daily"):
        result = fetch_symbol_history(
            client=_BigJumpClient(),
            symbol="TST",
            start_date="2023-01-02",
            end_date="2023-01-27",
            output_dir=str(tmp_path / "raw"),
            chunk_days=13,
            request_sleep=0.0,
            market="HOSE",
        )

    assert "quality_flag" in result.columns
    flagged = result[result["quality_flag"] == "chunk_boundary_jump"]
    assert not flagged.empty, "expected the +50% chunk-boundary jump to be flagged"
    assert any("CHUNK_BOUNDARY_JUMP" in rec.message for rec in caplog.records), (
        "expected a WARNING-level log for the chunk-boundary jump"
    )
