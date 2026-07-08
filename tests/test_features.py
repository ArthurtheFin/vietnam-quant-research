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


def test_split_day_return_flagged_not_clipped(tmp_path):
    """G4: an unadjusted 2:1 split (-50%) must become NaN + flag, not a fake -15% return."""
    import numpy as np

    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    prices = [100.0] * 15 + [50.0] * 15  # unadjusted split on day 15
    df = pd.DataFrame({
        "symbol": ["AAA"] * len(dates),
        "market": ["HOSE"] * len(dates),
        "date": dates,
        "close": prices,
    })
    out = add_returns(df, horizons=[1, 20], flags_output_path=str(tmp_path / "ca_flags.csv"))
    split_row = out.iloc[15]
    assert bool(split_row["suspect_corporate_action"]) is True
    assert np.isnan(split_row["return_1d"]), "split-day return must be NaN, not clipped to -15%"
    # multi-day returns crossing the split window must be NaN, not poisoned
    assert np.isnan(out.iloc[20]["return_20d"])
    assert (tmp_path / "ca_flags.csv").exists()
    flags = pd.read_csv(tmp_path / "ca_flags.csv")
    assert "AAA" in set(flags["symbol"])


def test_upcom_limit_move_is_preserved():
    """G4: a legitimate +15% UPCOM ceiling move must survive intact (old code clipped at the edge)."""
    dates = pd.date_range("2025-01-01", periods=10, freq="B")
    prices = [10.0] * 5 + [11.5] + [11.5] * 4  # +15% on day 5
    df = pd.DataFrame({
        "symbol": ["UUU"] * len(dates),
        "market": ["UPCOM"] * len(dates),
        "date": dates,
        "close": prices,
    })
    out = add_returns(df, horizons=[1])
    day5 = out.iloc[5]
    assert bool(day5["suspect_corporate_action"]) is False
    assert abs(day5["return_1d"] - 0.15) < 1e-9
