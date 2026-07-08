from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd


def add_returns(
    df: pd.DataFrame,
    horizons: list[int] = [1, 5, 10, 20],
    price_col: str = "close",
    flags_output_path: str | None = "data/output/corporate_action_flags.csv",
) -> pd.DataFrame:
    out = df.sort_values(["symbol", "date"]).copy()

    from src.utils.math_utils import safe_log_ratio

    # Check for positive prices to avoid division by zero/negative logs
    valid_prices = out[price_col].where(out[price_col] > 0.0)

    daily_ret = valid_prices.groupby(out["symbol"]).pct_change(1, fill_method=None)

    # G4: moves beyond the exchange price band cannot be genuine trading returns —
    # they are unadjusted corporate actions (splits/dividends) or data errors.
    # Clipping them (old behavior: clip ±15%) injected fake shocks into every
    # downstream return chain; instead we NaN them out and flag for manual review.
    from src.backtest.simulator import DEFAULT_PRICE_BAND, load_price_bands

    bands, default_band = load_price_bands()
    if "market" in out.columns:
        band_series = out["market"].astype(str).str.upper().map(bands).fillna(default_band)
    else:
        band_series = pd.Series(default_band, index=out.index)
    suspect = (daily_ret.abs() > band_series + 0.02).fillna(False)
    out["suspect_corporate_action"] = suspect
    out["return_1d"] = daily_ret.where(~suspect, np.nan)

    if suspect.any() and flags_output_path:
        events = out.loc[suspect, ["symbol", "date", price_col]].copy()
        events["raw_return"] = daily_ret[suspect]
        try:
            Path(flags_output_path).parent.mkdir(parents=True, exist_ok=True)
            events.to_csv(flags_output_path, index=False)
        except Exception as exc:
            warnings.warn(f"Could not write corporate action flags to {flags_output_path}: {exc}")
    
    for h in horizons:
        if h == 1:
            continue
        # Compound clipped daily returns to calculate multi-day returns
        out[f"return_{h}d"] = out.groupby("symbol")["return_1d"].transform(
            lambda s: (1.0 + s).rolling(h).apply(np.prod, raw=True) - 1.0
        )
        # Shift forward returns
        out[f"forward_return_{h}d"] = out.groupby("symbol")["return_1d"].transform(
            lambda s: (1.0 + s.shift(-h)).rolling(h).apply(np.prod, raw=True) - 1.0
        )
        
    out["log_return_1d"] = safe_log_ratio(out[price_col], out.groupby("symbol")[price_col].shift(1))
    return out
