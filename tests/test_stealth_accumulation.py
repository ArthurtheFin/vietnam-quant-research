from pathlib import Path

import numpy as np
import pandas as pd

from src.screening.stealth_accumulation import (
    backtest_stealth_accumulation_screen,
    compare_screen_backtests,
    latest_screen_snapshot,
    load_screen_config,
    run_stealth_accumulation_screen,
)


def _build_synthetic_market():
    dates = pd.date_range("2024-01-01", periods=90, freq="D")

    aaa_close = pd.Series(np.linspace(100, 112, len(dates)) + 0.8 * np.sin(np.linspace(0, 5, len(dates))))
    aaa_open = aaa_close.shift(1).fillna(aaa_close.iloc[0] * 0.995)
    aaa_high = aaa_close * 1.010
    aaa_low = aaa_close * 0.992
    aaa_volume = pd.Series(np.linspace(210_000, 180_000, len(dates)))

    bbb_close = pd.Series(np.linspace(100, 118, len(dates)) + 4 * np.sin(np.linspace(0, 18, len(dates))))
    bbb_open = bbb_close.shift(1).fillna(bbb_close.iloc[0] * 1.01)
    bbb_high = bbb_close * (1.025 + 0.02 * (np.sin(np.linspace(0, 12, len(dates))) > 0))
    bbb_low = bbb_close * 0.965
    bbb_volume = pd.Series(np.linspace(220_000, 420_000, len(dates)))

    price_df = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "market": ["HOSE"] * len(dates) * 2,
            "date": list(dates) * 2,
            "open": aaa_open.tolist() + bbb_open.tolist(),
            "high": aaa_high.tolist() + bbb_high.tolist(),
            "low": aaa_low.tolist() + bbb_low.tolist(),
            "close": aaa_close.tolist() + bbb_close.tolist(),
            "volume": aaa_volume.tolist() + bbb_volume.tolist(),
        }
    )
    price_df["value"] = price_df["close"] * price_df["volume"]

    market_df = pd.DataFrame(
        {
            "date": dates,
            "market_regime": ["Neutral"] * 70 + ["Risk-off"] * 20,
            "up_down_volume_ratio": np.linspace(0.9, 1.2, len(dates)),
            "advance_decline_ratio": np.linspace(0.8, 1.1, len(dates)),
        }
    )
    return price_df, market_df


def test_load_screen_config_reads_yaml():
    repo_root = Path(__file__).resolve().parents[1]
    cfg = load_screen_config(repo_root / "config/screens/stealth_accumulation.yaml")
    assert cfg["name"] == "stealth_accumulation"
    assert cfg["output"]["top_n"] == 10
    assert "allowed_volatility_regimes" in cfg["filters"]
    assert cfg["sector"]["max_names_per_sector"] == 2
    assert "cost_model" in cfg["backtest"]


def test_run_stealth_accumulation_screen_creates_ranked_scores():
    price_df, market_df = _build_synthetic_market()
    config = {
        "filters": {
            "min_price": 10.0,
            "min_avg_value_20d": 5_000_000.0,
        },
        "thresholds": {
            "watchlist_min_net_score": 45.0,
            "max_fakeout_risk": 65.0,
        },
    }

    screen = run_stealth_accumulation_screen(price_df=price_df, market_df=market_df, config=config)

    required_cols = {
        "accumulation_score",
        "breakout_quality_score",
        "fakeout_risk_score",
        "net_accumulation_score",
        "accumulation_stage",
        "watchlist_flag",
        "sector_relative_strength_20d",
        "breadth_support_score",
        "sector_support_score",
    }
    assert required_cols.issubset(screen.columns)

    latest = latest_screen_snapshot(screen, only_watchlist=False, top_n=2)
    assert len(latest) >= 1
    assert latest.loc[0, "symbol"] == "AAA"
    if len(latest) > 1:
        assert latest.loc[0, "net_accumulation_score"] >= latest.loc[1, "net_accumulation_score"]


def test_sector_relative_strength_and_breadth_scores_behave_as_expected():
    dates = pd.date_range("2024-01-01", periods=90, freq="D")

    def _series(start: float, end: float, wiggle: float) -> pd.Series:
        return pd.Series(np.linspace(start, end, len(dates)) + wiggle * np.sin(np.linspace(0, 8, len(dates))))

    frames = []
    specs = [
        ("AAA", "Banking", _series(100, 125, 0.6), 250_000),
        ("BBB", "Banking", _series(100, 110, 0.5), 240_000),
        ("CCC", "Retail", _series(100, 140, 0.7), 260_000),
        ("DDD", "Retail", _series(100, 136, 0.8), 255_000),
    ]
    for symbol, sector, close, volume in specs:
        open_ = close.shift(1).fillna(close.iloc[0] * 0.995)
        high = close * 1.01
        low = close * 0.992
        frame = pd.DataFrame(
            {
                "symbol": symbol,
                "sector": sector,
                "market": "HOSE",
                "date": dates,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": float(volume),
            }
        )
        frame["value"] = frame["close"] * frame["volume"]
        frames.append(frame)

    price_df = pd.concat(frames, ignore_index=True)
    market_df = pd.DataFrame(
        {
            "date": dates,
            "market_regime": ["Neutral"] * len(dates),
            "up_down_volume_ratio": np.linspace(0.85, 1.25, len(dates)),
            "advance_decline_ratio": np.linspace(0.80, 1.30, len(dates)),
        }
    )

    screen = run_stealth_accumulation_screen(
        price_df=price_df,
        market_df=market_df,
        config={
            "filters": {"min_price": 10.0, "min_avg_value_20d": 5_000_000.0},
            "thresholds": {"watchlist_min_net_score": 45.0, "max_fakeout_risk": 70.0},
        },
    )

    latest = screen[screen["date"] == screen["date"].max()].copy()
    aaa_sector_rs = latest.loc[latest["symbol"] == "AAA", "sector_relative_strength_20d"].iloc[0]
    bbb_sector_rs = latest.loc[latest["symbol"] == "BBB", "sector_relative_strength_20d"].iloc[0]

    assert aaa_sector_rs > bbb_sector_rs
    assert latest["breadth_support_score"].between(0, 100).all()
    assert latest["sector_support_score"].between(0, 100).all()


def test_latest_screen_snapshot_respects_watchlist_filter():
    price_df, market_df = _build_synthetic_market()
    config = {
        "filters": {
            "min_price": 10.0,
            "min_avg_value_20d": 5_000_000.0,
        },
        "thresholds": {
            "watchlist_min_net_score": 50.0,
            "max_fakeout_risk": 60.0,
        },
    }
    screen = run_stealth_accumulation_screen(price_df=price_df, market_df=market_df, config=config)
    latest_watchlist = latest_screen_snapshot(screen, only_watchlist=True, top_n=5)

    assert not latest_watchlist.empty
    assert latest_watchlist["watchlist_flag"].all()
    assert (latest_watchlist["symbol"] == "AAA").any()


def test_sector_aware_snapshot_caps_sector_exposure():
    screen_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC", "DDD"],
            "date": pd.to_datetime(["2024-03-01"] * 4),
            "sector": ["Banking", "Banking", "Securities", "Retail"],
            "net_accumulation_score": [90.0, 88.0, 80.0, 70.0],
            "accumulation_score": [85.0, 84.0, 78.0, 68.0],
            "screen_pass": [True, True, True, True],
            "watchlist_flag": [True, True, True, True],
        }
    )
    sector_aware = latest_screen_snapshot(
        screen_df,
        top_n=3,
        only_watchlist=True,
        sector_aware=True,
        max_names_per_sector=1,
        sector_col="sector",
    )
    assert list(sector_aware["symbol"]) == ["AAA", "CCC", "DDD"]


def test_backtest_and_compare_screen_backtests_return_expected_frames():
    dates = pd.to_datetime(["2024-01-01", "2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02", "2024-01-02"])
    screen_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC", "AAA", "BBB", "CCC"],
            "date": dates,
            "sector": ["Banking", "Banking", "Securities", "Banking", "Banking", "Securities"],
            "net_accumulation_score": [90, 85, 80, 88, 84, 82],
            "accumulation_score": [85, 80, 79, 83, 79, 80],
            "screen_pass": [True] * 6,
            "watchlist_flag": [True] * 6,
            "atr_pct_14": [0.02, 0.05, 0.03, 0.02, 0.06, 0.03],
            "avg_value_20d": [40_000_000_000, 18_000_000_000, 35_000_000_000, 42_000_000_000, 16_000_000_000, 34_000_000_000],
            "volatility_regime": ["Low Vol", "Stress Vol", "Normal Vol", "Low Vol", "Panic Vol", "Normal Vol"],
            "forward_return_5d": [0.05, 0.01, 0.03, 0.04, -0.01, 0.02],
            "forward_return_10d": [0.08, 0.03, 0.05, 0.07, 0.00, 0.04],
            "forward_return_20d": [0.10, 0.05, 0.06, 0.09, 0.01, 0.05],
            "market_proxy_return_1d": [0.01, 0.01, 0.01, -0.01, -0.01, -0.01],
            "open": [100, 101, 99, 102, 103, 100],
            "close": [100, 102, 100, 103, 101, 101],
            "high": [101, 103, 101, 104, 102, 102],
            "low": [99, 100, 98, 101, 99, 99],
        }
    )
    benchmark_dates = pd.date_range("2024-01-01", periods=30, freq="D")
    benchmark_df = pd.DataFrame(
        {
            "date": benchmark_dates,
            "close": np.linspace(100.0, 110.0, len(benchmark_dates)),
        }
    )

    raw = backtest_stealth_accumulation_screen(
        screen_df,
        top_n=2,
        holding_periods=[5, 10],
        only_watchlist=False,
        benchmark_df=benchmark_df,
        cost_model={
            "round_trip_cost": 0.002,
            "base_slippage_bps": 5.0,
            "atr_slippage_weight": 0.05,
            "liquidity_target_avg_value": 25_000_000_000.0,
            "low_liquidity_penalty_bps": 10.0,
            "regime_slippage_multiplier": {"Low Vol": 0.8, "Stress Vol": 1.3, "Panic Vol": 1.5, "Normal Vol": 1.0},
        },
    )
    assert set(raw.keys()) == {"by_date", "summary", "selections"}
    assert not raw["summary"].empty
    assert (raw["selections"]["selection_type"] == "raw").all()
    assert "benchmark_return" in raw["by_date"].columns
    assert "avg_excess_return" in raw["summary"].columns
    assert "avg_net_forward_return" in raw["summary"].columns
    assert "avg_trading_cost" in raw["summary"].columns
    assert "avg_signal_to_entry_gap" in raw["summary"].columns
    assert (raw["summary"]["avg_net_forward_return"] <= raw["summary"]["avg_forward_return"]).all()
    assert (raw["summary"]["benchmark_source"] == "benchmark_df").all()

    compared = compare_screen_backtests(
        screen_df,
        top_n=2,
        holding_periods=[5, 10],
        only_watchlist=False,
        max_names_per_sector=1,
        benchmark_df=benchmark_df,
        cost_model={
            "round_trip_cost": 0.002,
            "base_slippage_bps": 5.0,
            "atr_slippage_weight": 0.05,
            "liquidity_target_avg_value": 25_000_000_000.0,
            "low_liquidity_penalty_bps": 10.0,
            "regime_slippage_multiplier": {"Low Vol": 0.8, "Stress Vol": 1.3, "Panic Vol": 1.5, "Normal Vol": 1.0},
        },
    )
    assert set(compared["summary"]["portfolio_type"]) == {"raw", "sector_aware"}
    selection_mix = compared["selections"]
    sector_aware_sel = selection_mix[selection_mix["selection_type"] == "sector_aware"]
    assert sector_aware_sel.groupby(["selection_date", "sector"]).size().max() == 1
    assert compared["summary"]["avg_benchmark_return"].notna().all()
    assert "avg_net_excess_return" in compared["summary"].columns


def test_entry_delay_uses_next_open_and_captures_gap_risk():
    dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])
    screen_df = pd.DataFrame(
        {
            "symbol": ["AAA"] * 4,
            "date": dates,
            "sector": ["Banking"] * 4,
            "net_accumulation_score": [90, 85, 80, 75],
            "accumulation_score": [85, 80, 75, 70],
            "screen_pass": [True] * 4,
            "watchlist_flag": [True] * 4,
            "atr_pct_14": [0.02] * 4,
            "avg_value_20d": [50_000_000_000] * 4,
            "volatility_regime": ["Normal Vol"] * 4,
            "market_proxy_return_1d": [0.0, 0.0, 0.0, 0.0],
            "open": [100.0, 110.0, 112.0, 113.0],
            "close": [100.0, 111.0, 113.0, 114.0],
            "high": [101.0, 112.0, 114.0, 115.0],
            "low": [99.0, 109.0, 111.0, 112.0],
        }
    )
    benchmark_df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=10, freq="D"),
            "close": np.linspace(100.0, 102.0, 10),
        }
    )

    result = backtest_stealth_accumulation_screen(
        screen_df,
        top_n=1,
        holding_periods=[2],
        benchmark_df=benchmark_df,
        entry_delay_days=1,
        entry_price_col="open",
        exit_price_col="close",
        cost_model={"round_trip_cost": 0.0, "base_slippage_bps": 0.0},
    )

    by_date = result["by_date"].sort_values("selection_date").reset_index(drop=True)
    first = by_date.iloc[0]
    expected_return = 113.0 / 110.0 - 1
    expected_gap = 110.0 / 100.0 - 1

    assert abs(first["avg_forward_return"] - expected_return) < 1e-9
    assert abs(first["avg_signal_to_entry_gap"] - expected_gap) < 1e-9


def test_stealth_accumulation_trend_filters():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    
    # AAA is downtrending (close starts at 100 and drops to 50)
    aaa_close = np.linspace(100, 50, len(dates))
    # BBB is uptrending (close starts at 50 and rises to 100)
    bbb_close = np.linspace(50, 100, len(dates))
    
    price_df = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "market": ["HOSE"] * len(dates) * 2,
            "date": list(dates) * 2,
            "open": list(aaa_close) + list(bbb_close),
            "high": list(aaa_close * 1.01) + list(bbb_close * 1.01),
            "low": list(aaa_close * 0.99) + list(bbb_close * 0.99),
            "close": list(aaa_close) + list(bbb_close),
            "volume": [1_000_000] * len(dates) * 2,
        }
    )
    price_df["value"] = price_df["close"] * price_df["volume"]

    # Config with trend filters enabled
    config = {
        "filters": {
            "min_price": 10.0,
            "min_avg_value_20d": 500_000.0,
            "trend_filters": {
                "require_above_ma50": True,
                "require_above_ma200": True,
                "require_ma50_above_ma200": False,
            }
        },
        "thresholds": {
            "stage_a_min_score": 30.0,
            "stage_b_min_score": 40.0,
            "stage_c_min_score": 50.0,
            "watchlist_min_net_score": 30.0,
            "max_fakeout_risk": 90.0,
        }
    }
    
    screen = run_stealth_accumulation_screen(price_df=price_df, config=config)
    latest = screen[screen["date"] == screen["date"].max()]
    
    # AAA should fail trend_pass (since close 50 is below ma50 which is around 62)
    aaa_row = latest[latest["symbol"] == "AAA"].iloc[0]
    assert aaa_row["trend_pass"] == False
    assert aaa_row["screen_pass"] == False
    assert aaa_row["watchlist_flag"] == False
    assert aaa_row["accumulation_stage"] == "No Structure"
    
    # BBB should pass trend_pass (since close 100 is above ma50 which is around 88)
    bbb_row = latest[latest["symbol"] == "BBB"].iloc[0]
    assert bbb_row["trend_pass"] == True
    assert bbb_row["screen_pass"] == True


def test_stealth_accumulation_stage_s_squeeze():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    
    # AAA is extremely tight (close stays flat at 100 with very minor noise)
    aaa_close = [100.0 + 0.1 * np.sin(i) for i in range(len(dates))]
    
    price_df = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates),
            "market": ["HOSE"] * len(dates),
            "date": list(dates),
            "open": aaa_close,
            "high": [c + 0.2 for c in aaa_close],
            "low": [c - 0.2 for c in aaa_close],
            "close": aaa_close,
            "volume": [1_000_000] * len(dates),
        }
    )
    price_df["value"] = price_df["close"] * price_df["volume"]
    config = {
        "filters": {
            "min_price": 10.0,
            "min_avg_value_20d": 500_000.0,
            "allowed_volatility_regimes": ["Low Vol", "Normal Vol", "High Vol", "Stress Vol", "Panic Vol"],
            "trend_filters": {
                "require_above_ma50": False,
                "require_above_ma200": False,
            }
        },
        "thresholds": {
            "stage_a_min_score": 30.0,
            "stage_b_min_score": 40.0,
            "stage_c_min_score": 50.0,
            "watchlist_min_net_score": 30.0,
            "max_fakeout_risk": 90.0,
        }
    }
    
    screen = run_stealth_accumulation_screen(price_df=price_df, config=config)
    latest = screen[screen["date"] == screen["date"].max()].iloc[0]
    
    # Since AAA is extremely flat, it must trigger bb_squeeze and range_squeeze, classifying it as Stage S
    assert latest["bb_squeeze"] == True
    assert latest["range_squeeze"] == True
    assert latest["is_compressed"] == True
    assert latest["accumulation_stage"] == "Stage S: Tight Squeeze"
    assert latest["watchlist_flag"] == True

