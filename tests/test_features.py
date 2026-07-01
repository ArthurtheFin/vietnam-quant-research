import numpy as np
import pandas as pd
from src.features.returns import add_returns
from src.features.volatility import add_ewma_volatility, add_realized_volatility


def test_add_returns():
    df = pd.DataFrame({'symbol':['AAA']*3, 'date':pd.date_range('2024-01-01', periods=3), 'close':[10,11,12]})
    out = add_returns(df, horizons=[1])
    assert 'return_1d' in out.columns


def test_log_return_features_ignore_non_positive_prices():
    df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 4,
            "date": pd.date_range("2024-01-01", periods=4, freq="D"),
            "close": [10.0, 0.0, 12.0, -1.0],
        }
    )

    returns = add_returns(df, horizons=[1])
    realized = add_realized_volatility(df, window=2)
    ewma = add_ewma_volatility(df, span=2)

    assert np.isnan(returns.loc[1, "log_return_1d"])
    assert np.isnan(returns.loc[2, "log_return_1d"])
    assert np.isnan(returns.loc[3, "log_return_1d"])
    assert np.isfinite(realized["log_return_1d"].dropna()).all()
    assert np.isfinite(ewma["log_return_1d"].dropna()).all()
