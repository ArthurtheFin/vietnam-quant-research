from __future__ import annotations

import numpy as np
import pandas as pd


def safe_log_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
) -> pd.Series:
    """Compute log(numerator / denominator) only where both inputs are positive."""
    num = pd.Series(numerator, copy=False)
    den = pd.Series(denominator, copy=False)

    out = pd.Series(np.nan, index=num.index, dtype=float)
    valid = num.gt(0) & den.gt(0)
    out.loc[valid] = np.log(num.loc[valid] / den.loc[valid])
    return out
