"""Tests for the portfolio-level rebalancing backtest (audit D1)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.portfolio_backtest import run_portfolio_backtest


def _fixture_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    """Two symbols; on rebalance day T the ranking flips to BBB, but on T-1 AAA leads.

    A look-ahead backtest (deciding with day-T information) buys BBB at T;
    a correct one (deciding with T-1 information) buys AAA.
    """
    dates = pd.bdate_range("2025-01-01", periods=15)
    rebalance_period = 5
    t_index = 5  # second rebalance date (first one is skipped: no prior day)
    t_date = dates[t_index]

    rows = []
    ranking_rows = []
    for d_idx, d in enumerate(dates):
        for sym in ("AAA", "BBB"):
            rows.append({"symbol": sym, "date": d, "close": 100.0, "return_1d": 0.001})
            # AAA leads every day except exactly day T, where BBB spikes to the top.
            if d_idx == t_index:
                score = 90.0 if sym == "BBB" else 50.0
            else:
                score = 90.0 if sym == "AAA" else 50.0
            ranking_rows.append({"symbol": sym, "date": d, "final_score": score})

    features = pd.DataFrame(rows)
    ranking = pd.DataFrame(ranking_rows)
    return features, ranking, t_date


def test_rebalance_decision_uses_prior_day_information() -> None:
    features, ranking, t_date = _fixture_frames()
    result = run_portfolio_backtest(
        features=features,
        meta_ranking=ranking,
        rebalance_period=5,
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
    )
    trades = result["trades_log"]
    assert not trades.empty
    buys_at_t = trades[(trades["date"] == t_date.strftime("%Y-%m-%d")) & (trades["type"] == "BUY")]
    assert not buys_at_t.empty, "expected a rebalance trade at day T"
    assert set(buys_at_t["symbol"]) == {"AAA"}, (
        "decision must use T-1 information (AAA leads at T-1); "
        f"got {sorted(set(buys_at_t['symbol']))} — day-T spike leaked into the decision"
    )


def test_no_rebalance_on_first_day_without_prior_information() -> None:
    features, ranking, _ = _fixture_frames()
    result = run_portfolio_backtest(
        features=features,
        meta_ranking=ranking,
        rebalance_period=5,
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
    )
    trades = result["trades_log"]
    first_date = pd.bdate_range("2025-01-01", periods=1)[0].strftime("%Y-%m-%d")
    assert trades[trades["date"] == first_date].empty, "day 0 has no prior information to trade on"


def test_limit_up_symbol_is_not_bought_on_execution_day() -> None:
    """D2: a +7% (HOSE ceiling) execution-day move means the buy cannot fill."""
    dates = pd.bdate_range("2025-01-01", periods=15)
    t_index = 5
    rows, ranking_rows = [], []
    for d_idx, d in enumerate(dates):
        for sym in ("AAA", "BBB"):
            r1 = 0.001
            if sym == "AAA" and d_idx == t_index:
                r1 = 0.07  # limit-up on execution day
            rows.append({"symbol": sym, "market": "HOSE", "date": d, "close": 100.0, "return_1d": r1})
            ranking_rows.append({"symbol": sym, "date": d, "final_score": 90.0 if sym == "AAA" else 50.0})
    result = run_portfolio_backtest(
        features=pd.DataFrame(rows),
        meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=5,
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
    )
    t_date = dates[t_index].strftime("%Y-%m-%d")
    buys_at_t = result["trades_log"]
    buys_at_t = buys_at_t[(buys_at_t["date"] == t_date) & (buys_at_t["type"] == "BUY")] if not buys_at_t.empty else buys_at_t
    assert buys_at_t.empty or "AAA" not in set(buys_at_t["symbol"]), "limit-up symbol must be skipped"
    skipped = result["skipped_limit_up"]
    assert not skipped.empty and "AAA" in set(skipped["symbol"])


def test_stop_loss_exits_position_after_min_holding_sessions() -> None:
    """Phase A: a position that craters must be sold, not held to the next rebalance."""
    dates = pd.bdate_range("2025-01-01", periods=20)
    rows, ranking_rows = [], []
    for d_idx, d in enumerate(dates):
        # AAA crashes hard starting day 6 (after the 5-day rebalance); BBB is flat.
        r1 = -0.06 if 6 <= d_idx <= 9 else 0.0
        rows.append({"symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0, "return_1d": r1})
        rows.append({"symbol": "BBB", "market": "HOSE", "date": d, "close": 100.0, "return_1d": 0.0})
        ranking_rows.append({"symbol": "AAA", "date": d, "final_score": 90.0})
        ranking_rows.append({"symbol": "BBB", "date": d, "final_score": 10.0})

    result = run_portfolio_backtest(
        features=pd.DataFrame(rows),
        meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=5,  # first buy at day 5; next rebalance at day 10 -- stop-loss must act before that
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
        stop_loss_pct=-0.15,
    )
    exits = result["stop_loss_exits"]
    assert not exits.empty, "AAA's crash must trigger a stop-loss exit before the next rebalance"
    assert "AAA" in set(exits["symbol"])
    assert result["metrics"]["stop_loss_exit_count"] >= 1


def test_stop_loss_disabled_by_default_matches_prior_behavior() -> None:
    """Phase A: stop_loss_pct=None (default) must not change any existing behavior."""
    dates = pd.bdate_range("2025-01-01", periods=15)
    rows, ranking_rows = [], []
    for d_idx, d in enumerate(dates):
        r1 = -0.06 if 6 <= d_idx <= 9 else 0.0
        rows.append({"symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0, "return_1d": r1})
        ranking_rows.append({"symbol": "AAA", "date": d, "final_score": 90.0})

    result = run_portfolio_backtest(
        features=pd.DataFrame(rows),
        meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=20,
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
    )
    assert result["stop_loss_exits"].empty
    assert result["metrics"]["stop_loss_exit_count"] == 0


def test_regime_filter_deleverages_on_lagged_risk_off() -> None:
    """Phase A: risk-off regime must de-risk to cash using YESTERDAY's regime, not today's."""
    dates = pd.bdate_range("2025-01-01", periods=15)
    rows, ranking_rows, regime_rows = [], [], []
    for d_idx, d in enumerate(dates):
        # AAA crashes on day 8 onward; regime flips to Risk-off on day 7 (known by close of day 7).
        r1 = -0.10 if d_idx >= 8 else 0.001
        rows.append({"symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0, "return_1d": r1})
        ranking_rows.append({"symbol": "AAA", "date": d, "final_score": 90.0})
        regime_rows.append({"date": d, "market_regime": "Risk-off" if d_idx >= 7 else "Neutral"})

    market_regime = pd.DataFrame(regime_rows)
    # rebalance_period=3 -> first buy at day 3, well before the day-7 regime flip.
    with_filter = run_portfolio_backtest(
        features=pd.DataFrame(rows), meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=3, portfolio_size=1, allocation_method="equal_weight",
        min_value_ma20=0.0, require_above_ma200=False,
        market_regime=market_regime, regime_cash_fraction=1.0,
    )
    without_filter = run_portfolio_backtest(
        features=pd.DataFrame(rows), meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=3, portfolio_size=1, allocation_method="equal_weight",
        min_value_ma20=0.0, require_above_ma200=False,
    )
    assert not with_filter["regime_adjustments"].empty
    assert with_filter["metrics"]["final_nav"] > without_filter["metrics"]["final_nav"], (
        "de-risking ahead of the crash must preserve more NAV than staying fully invested"
    )
    # day index 8 is the first crash day; regime known at close of day 7 -> exposure
    # must already be cut by day 8 (lag correctness, not same-day look-ahead)
    adj_dates = set(with_filter["regime_adjustments"]["date"])
    assert dates[8].strftime("%Y-%m-%d") in adj_dates or dates[7].strftime("%Y-%m-%d") in adj_dates


def test_regime_filter_absent_by_default_matches_prior_behavior() -> None:
    """Phase A: market_regime=None (default) must not change any existing behavior."""
    dates = pd.bdate_range("2025-01-01", periods=10)
    rows = [{"symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0, "return_1d": 0.01} for d in dates]
    ranking_rows = [{"symbol": "AAA", "date": d, "final_score": 90.0} for d in dates]
    result = run_portfolio_backtest(
        features=pd.DataFrame(rows), meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=20, portfolio_size=1, allocation_method="equal_weight",
        min_value_ma20=0.0, require_above_ma200=False,
    )
    assert result["regime_adjustments"].empty
    assert result["metrics"]["regime_adjustment_count"] == 0


def test_take_profit_holds_winner_while_uptrend_intact() -> None:
    """New: gain >=10% must NOT be sold mechanically while above_ma20 stays True."""
    dates = pd.bdate_range("2025-01-01", periods=15)
    rows, ranking_rows = [], []
    for d_idx, d in enumerate(dates):
        # AAA grinds up +2%/day from day 6 onward, always above its MA20.
        r1 = 0.02 if d_idx >= 6 else 0.0
        rows.append({
            "symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0,
            "return_1d": r1, "above_ma20": True,
        })
        ranking_rows.append({"symbol": "AAA", "date": d, "final_score": 90.0})

    result = run_portfolio_backtest(
        features=pd.DataFrame(rows),
        meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=5,
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
        take_profit_pct=0.10,
    )
    assert result["take_profit_exits"].empty, "must not take profit while the uptrend structure is intact"


def test_take_profit_exits_only_on_trend_break_after_gain_threshold() -> None:
    """New: gain >=10% AND above_ma20 flips False -> take profit; gain alone must not."""
    dates = pd.bdate_range("2025-01-01", periods=15)
    rows, ranking_rows = [], []
    for d_idx, d in enumerate(dates):
        r1 = 0.02 if d_idx >= 6 else 0.0
        # Trend breaks (above_ma20=False) starting day 10, well after the +10% gain
        # threshold is crossed (~day 9: 4 days of +2% from day6 => ~8%, day9 ~+12%).
        above_ma20 = d_idx < 10
        rows.append({
            "symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0,
            "return_1d": r1, "above_ma20": above_ma20,
        })
        ranking_rows.append({"symbol": "AAA", "date": d, "final_score": 90.0})

    result = run_portfolio_backtest(
        features=pd.DataFrame(rows),
        meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=5,
        portfolio_size=1,
        allocation_method="equal_weight",
        min_value_ma20=0.0,
        require_above_ma200=False,
        take_profit_pct=0.10,
    )
    exits = result["take_profit_exits"]
    assert not exits.empty, "must exit once trend breaks after the gain threshold is crossed"
    assert (exits["move_since_entry"] >= 0.10).all()
    assert result["metrics"]["take_profit_exit_count"] >= 1


def test_take_profit_disabled_by_default() -> None:
    """New: take_profit_pct=None (default) must not change any existing behavior."""
    dates = pd.bdate_range("2025-01-01", periods=15)
    rows = [{"symbol": "AAA", "market": "HOSE", "date": d, "close": 100.0,
             "return_1d": 0.02, "above_ma20": False} for d in dates]
    ranking_rows = [{"symbol": "AAA", "date": d, "final_score": 90.0} for d in dates]
    result = run_portfolio_backtest(
        features=pd.DataFrame(rows), meta_ranking=pd.DataFrame(ranking_rows),
        rebalance_period=5, portfolio_size=1, allocation_method="equal_weight",
        min_value_ma20=0.0, require_above_ma200=False,
    )
    assert result["take_profit_exits"].empty
    assert result["metrics"]["take_profit_exit_count"] == 0
