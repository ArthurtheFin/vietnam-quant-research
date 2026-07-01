import pandas as pd
import numpy as np

from src.utils.math_utils import safe_log_ratio


def add_atr(
    df: pd.DataFrame,
    window: int = 14,
) -> pd.DataFrame:
    """
    Add ATR and ATR percentage.

    Output:
    - true_range
    - atr_14
    - atr_pct_14
    """
    out = df.sort_values(["symbol", "date"]).copy()

    prev_close = out.groupby("symbol")["close"].shift(1)

    high_low = out["high"] - out["low"]
    high_prev_close = (out["high"] - prev_close).abs()
    low_prev_close = (out["low"] - prev_close).abs()

    out["true_range"] = pd.concat(
        [high_low, high_prev_close, low_prev_close],
        axis=1,
    ).max(axis=1)

    out[f"atr_{window}"] = (
        out
        .groupby("symbol")["true_range"]
        .transform(lambda x: x.rolling(window).mean())
    )

    out[f"atr_pct_{window}"] = out[f"atr_{window}"] / out["close"]

    return out


def add_realized_volatility(
    df: pd.DataFrame,
    window: int = 20,
    return_col: str = "log_return_1d",
) -> pd.DataFrame:
    """
    Add realized volatility.

    Nếu chưa có log_return_1d, function sẽ tự tạo.
    """
    out = df.sort_values(["symbol", "date"]).copy()

    if return_col not in out.columns:
        out["log_return_1d"] = out.groupby("symbol")["close"].transform(lambda x: safe_log_ratio(x, x.shift(1)))
        return_col = "log_return_1d"

    out[f"realized_vol_{window}d"] = (
        out
        .groupby("symbol")[return_col]
        .transform(lambda x: x.rolling(window).std() * np.sqrt(252))
    )

    return out


def add_ewma_volatility(
    df: pd.DataFrame,
    span: int = 20,
    return_col: str = "log_return_1d",
) -> pd.DataFrame:
    """
    Add EWMA volatility.

    EWMA phản ứng nhanh hơn realized volatility thường.
    """
    out = df.sort_values(["symbol", "date"]).copy()

    if return_col not in out.columns:
        out["log_return_1d"] = out.groupby("symbol")["close"].transform(lambda x: safe_log_ratio(x, x.shift(1)))
        return_col = "log_return_1d"

    out[f"ewma_vol_{span}d"] = (
        out
        .groupby("symbol")[return_col]
        .transform(lambda x: x.ewm(span=span, adjust=False).std() * np.sqrt(252))
    )

    return out


def add_volatility_percentile(
    df: pd.DataFrame,
    vol_col: str | None = None,
    window: int = 252,
    output_col: str = "volatility_percentile",
) -> pd.DataFrame:
    """
    Add rolling volatility percentile.

    Percentile càng cao nghĩa là biến động hiện tại càng cao so với lịch sử gần đây.
    """
    out = df.sort_values(["symbol", "date"]).copy()

    if vol_col is None:
        candidates = [
            "realized_vol_20d",
            "ewma_vol_20d",
            "atr_pct_14",
        ]

        vol_col = next((c for c in candidates if c in out.columns), None)

        if vol_col is None:
            raise KeyError(
                "Không tìm thấy volatility column. "
                "Hãy chạy add_realized_volatility(), add_ewma_volatility() hoặc add_atr() trước."
            )

    def rolling_percentile(x: pd.Series) -> pd.Series:
        return x.rolling(window).apply(
            lambda arr: pd.Series(arr).rank(pct=True).iloc[-1],
            raw=False,
        )

    out[output_col] = (
        out
        .groupby("symbol")[vol_col]
        .transform(rolling_percentile)
    )

    return out


def _classify_single_volatility_percentile(percentile) -> str:
    """
    Classify one volatility percentile value.
    """
    if percentile is None or pd.isna(percentile):
        return "Unknown"

    if percentile < 0.20:
        return "Low Vol"

    if percentile < 0.50:
        return "Normal Vol"

    if percentile < 0.75:
        return "High Vol"

    if percentile < 0.90:
        return "Stress Vol"

    return "Panic Vol"


def classify_volatility_regime(
    data,
    percentile_col: str = "volatility_percentile",
    output_col: str = "volatility_regime",
):
    """
    Có thể dùng theo 2 cách:

    1. Scalar:
       classify_volatility_regime(0.72)

    2. DataFrame:
       features = classify_volatility_regime(features)
    """
    if isinstance(data, pd.DataFrame):
        out = data.copy()

        if percentile_col not in out.columns:
            raise KeyError(
                f"Không tìm thấy cột '{percentile_col}'. "
                f"Current columns: {out.columns.tolist()}"
            )

        out[output_col] = out[percentile_col].apply(
            _classify_single_volatility_percentile
        )

        return out

    return _classify_single_volatility_percentile(data)
