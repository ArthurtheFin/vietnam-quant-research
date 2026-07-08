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
