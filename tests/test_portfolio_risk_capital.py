import numpy as np
import pandas as pd

from src.capital.management import (
    allocate_capital_budget,
    align_capital_plan_to_target_weights,
    atr_based_position_plan,
    build_capital_plan,
    conviction_multiplier,
    fractional_kelly_fraction,
    kelly_scale,
    regime_multiplier,
    resolve_conviction_score,
)
from src.portfolio.construction import (
    equal_weight_allocation,
    hierarchical_risk_parity_allocation,
    inverse_volatility_allocation,
    portfolio_risk_contributions,
    risk_parity_allocation,
    shrink_covariance,
    maximize_sharpe_ratio,
    efficient_frontier,
)
from src.risk.management import (
    apply_drawdown_overlay,
    apply_symbol_caps,
    apply_volatility_target,
    build_portfolio_risk_report,
    expanding_sharpe_series,
    portfolio_nav_series,
    portfolio_return_series,
    rolling_sharpe_series,
    sharpe_stability_report,
)


def test_portfolio_allocators_sum_to_one():
    vol = pd.Series({"AAA": 0.2, "BBB": 0.1, "CCC": 0.3})
    cov = pd.DataFrame(
        [[0.04, 0.01, 0.00], [0.01, 0.02, 0.00], [0.00, 0.00, 0.09]],
        index=vol.index,
        columns=vol.index,
    )
    returns = pd.DataFrame(
        {
            "AAA": [0.01, 0.02, -0.01, 0.03],
            "BBB": [0.00, 0.01, 0.00, 0.01],
            "CCC": [0.03, -0.02, 0.02, 0.01],
        }
    )

    allocators = [
        equal_weight_allocation(vol.index),
        inverse_volatility_allocation(vol),
        risk_parity_allocation(cov),
        hierarchical_risk_parity_allocation(returns=returns),
    ]

    for weights in allocators:
        assert round(float(weights.sum()), 8) == 1.0
        assert (weights >= 0).all()


def test_portfolio_risk_contributions_report_positive():
    cov = pd.DataFrame(
        [[0.04, 0.01], [0.01, 0.09]],
        index=["AAA", "BBB"],
        columns=["AAA", "BBB"],
    )
    weights = pd.Series({"AAA": 0.5, "BBB": 0.5})
    rc = portfolio_risk_contributions(weights, cov)
    assert round(float(rc.sum()), 8) == 1.0


def test_shrink_covariance_preserves_shape():
    cov = pd.DataFrame([[0.04, 0.02], [0.02, 0.09]], index=["AAA", "BBB"], columns=["AAA", "BBB"])
    shrunk = shrink_covariance(cov, shrinkage=0.2)
    assert shrunk.shape == cov.shape
    assert shrunk.loc["AAA", "BBB"] < cov.loc["AAA", "BBB"]


def test_risk_management_series_and_report():
    returns = pd.DataFrame(
        {
            "AAA": [0.01, -0.01, 0.02, 0.00],
            "BBB": [0.00, 0.01, -0.01, 0.02],
        },
        index=pd.date_range("2024-01-01", periods=4, freq="D"),
    )
    weights = pd.Series({"AAA": 0.6, "BBB": 0.4})
    portfolio_returns = portfolio_return_series(returns, weights)
    nav = portfolio_nav_series(portfolio_returns)
    report = build_portfolio_risk_report(returns, weights)

    assert len(portfolio_returns) == 4
    assert len(nav) == 4
    assert "annual_volatility" in report
    assert "max_weight" in report
    assert "sharpe_stability_score" in report


def test_sharpe_stability_series_and_report():
    portfolio_returns = pd.Series(
        [0.01, -0.005, 0.007, 0.012, -0.003, 0.009, 0.004, -0.002, 0.006, 0.008] * 15,
        index=pd.date_range("2024-01-01", periods=150, freq="D"),
    )
    expanding = expanding_sharpe_series(portfolio_returns, min_periods=21)
    rolling = rolling_sharpe_series(portfolio_returns, window=30)
    report = sharpe_stability_report(portfolio_returns, min_periods=21, rolling_window=30)

    assert expanding.notna().sum() > 0
    assert rolling.notna().sum() > 0
    assert report["track_record_days"] == 150
    assert report["sharpe_stability_score"] >= 0


def test_risk_overlays_adjust_weights():
    cov = pd.DataFrame(
        [[0.04, 0.00], [0.00, 0.01]],
        index=["AAA", "BBB"],
        columns=["AAA", "BBB"],
    )
    weights = pd.Series({"AAA": 0.8, "BBB": 0.2})
    capped = apply_symbol_caps(weights, max_weight=0.6)
    scaled, scale = apply_volatility_target(capped, cov, target_volatility=0.10, max_gross_leverage=1.0)
    overlaid, exposure = apply_drawdown_overlay(scaled, current_drawdown=-0.12)

    assert capped.max() <= 0.75
    assert scale <= 1.0
    assert exposure == 0.75
    assert round(float((overlaid / scaled).dropna().iloc[0]), 2) == 0.75


def test_capital_management_builds_plan():
    candidates = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "close": [100.0, 50.0],
            "atr_pct_14": [0.03, 0.02],
            "trade_edge_score": [80, 0],
            "setup_quality_score": [72, 60],
            "edge_tier": ["Strong Edge", "Valid Edge"],
            "profit_factor": [2.4, 1.8],
            "win_rate": [0.60, 0.55],
            "volatility_regime": ["Low Vol", "Normal Vol"],
            "p_win": [0.60, 0.55],
            "avg_gain": [0.08, 0.05],
            "avg_loss": [0.04, 0.03],
        }
    )
    plan = build_capital_plan(
        candidates,
        nav=100_000,
        p_win_col="p_win",
        avg_gain_col="avg_gain",
        avg_loss_col="avg_loss",
        max_gross_exposure=0.80,
    )
    assert len(plan) == 2
    assert "position_value" in plan.columns
    assert (plan["quantity"] >= 0).all()
    assert (plan["risk_pct_effective"] >= 0.0025).all()
    assert (plan["gross_weight"] >= 0).all()
    assert plan["conviction_score_resolved"].iloc[1] > 0
    assert plan["position_pct_nav"].sum() <= 0.80


def test_atr_based_position_plan_and_multipliers():
    sizing = atr_based_position_plan(
        nav=100_000,
        entry=100.0,
        atr_pct=0.02,
        atr_multiple=2.0,
        base_risk_per_trade=0.01,
        conviction_score=80,
        regime="Low Vol",
    )
    assert sizing["stop_price"] == 96.0
    assert sizing["quantity"] > 0
    assert conviction_multiplier(80) > conviction_multiplier(20)
    assert regime_multiplier("Low Vol") > regime_multiplier("Panic Vol")
    assert fractional_kelly_fraction(0.60, 0.08, 0.04) > 0
    assert 0.5 <= kelly_scale(0.003, 0.01) <= 1.5


def test_resolve_conviction_score_uses_fallback_components():
    row = pd.Series(
        {
            "trade_edge_score": 0,
            "setup_quality_score": 77,
            "edge_tier": "Strong Edge",
            "win_rate": 0.62,
            "profit_factor": 3.1,
        }
    )
    resolved = resolve_conviction_score(row)
    assert resolved > 70


def test_negative_kelly_does_not_zero_out_risk_budget():
    candidates = pd.DataFrame(
        {
            "symbol": ["AAA"],
            "close": [100.0],
            "atr_pct_14": [0.03],
            "trade_edge_score": [0],
            "setup_quality_score": [70],
            "edge_tier": ["Valid Edge"],
            "profit_factor": [1.6],
            "win_rate": [0.54],
            "volatility_regime": ["Normal Vol"],
            "p_win": [0.40],
            "avg_gain": [0.02],
            "avg_loss": [0.05],
        }
    )
    plan = build_capital_plan(
        candidates,
        nav=100_000,
        p_win_col="p_win",
        avg_gain_col="avg_gain",
        avg_loss_col="avg_loss",
    )
    assert len(plan) == 1
    assert plan.loc[0, "kelly_scale"] == 1.0
    assert plan.loc[0, "risk_pct_effective"] >= 0.0025


def test_allocate_capital_budget_respects_portfolio_cap():
    plan = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "entry_price": [100.0, 50.0, 25.0],
            "quantity": [600, 1000, 2000],
            "position_value": [60_000.0, 50_000.0, 50_000.0],
            "risk_per_share": [4.0, 2.0, 1.0],
        }
    )
    adjusted = allocate_capital_budget(plan, nav=100_000, max_gross_exposure=0.90)
    assert adjusted["position_value"].sum() <= 90_000
    assert (adjusted["risk_amount_realized"] >= 0).all()


def test_align_capital_plan_to_target_weights_respects_weight_and_risk_caps():
    plan = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC"],
            "entry_price": [100.0, 50.0, 25.0],
            "quantity": [700, 1200, 1600],
            "position_value": [70_000.0, 60_000.0, 40_000.0],
            "risk_per_share": [4.0, 2.0, 1.0],
            "conviction_score_resolved": [85.0, 70.0, 60.0],
        }
    )
    target_weights = pd.Series({"AAA": 0.50, "BBB": 0.30, "CCC": 0.20})

    aligned = align_capital_plan_to_target_weights(
        plan,
        target_weights=target_weights,
        nav=100_000,
        max_gross_exposure=0.90,
    )

    assert len(aligned) == 3
    assert aligned["position_value"].sum() <= 90_000
    assert (aligned["position_value"] <= aligned["target_position_value"] + 1e-9).all()
    assert (aligned["position_value"] <= aligned["risk_cap_position_value"] + 1e-9).all()
    assert round(float(aligned["gross_weight"].sum()), 8) == 1.0


def test_mean_variance_optimization_and_frontier():
    cov = pd.DataFrame(
        [[0.04, 0.01, 0.02],
         [0.01, 0.09, 0.01],
         [0.02, 0.01, 0.16]],
        index=["AAA", "BBB", "CCC"],
        columns=["AAA", "BBB", "CCC"]
    )
    er = pd.Series([0.15, 0.20, 0.25], index=["AAA", "BBB", "CCC"])
    
    # Test Max Sharpe
    weights = maximize_sharpe_ratio(er, cov, risk_free_rate=0.02, max_weight=0.50)
    assert len(weights) == 3
    assert round(float(weights.sum()), 6) == 1.0
    assert (weights >= 0).all()
    assert (weights <= 0.50 + 1e-9).all()
    
    # Test Efficient Frontier
    frontier = efficient_frontier(er, cov, points=5, max_weight=0.50)
    assert len(frontier) > 0
    for pt in frontier:
        assert "target_return" in pt
        assert "volatility" in pt
        assert "weights" in pt
        assert round(float(pt["weights"].sum()), 6) == 1.0



def test_kelly_disabled_when_avg_loss_input_is_not_a_loss():
    """H3: passing a positive return stat (e.g. median_return) as avg_loss must not drive Kelly."""
    from src.capital.management import build_capital_plan

    candidates = pd.DataFrame(
        [
            {
                "symbol": "AAA", "close": 25000.0, "atr_pct_14": 0.03,
                "trade_edge_score": 80.0, "volatility_regime": "Normal Vol",
                "win_rate": 0.60, "avg_return": 0.05, "median_return": 0.03,
            }
        ]
    )
    plan = build_capital_plan(
        candidates,
        nav=1_000_000_000,
        p_win_col="win_rate",
        avg_gain_col="avg_return",
        avg_loss_col="median_return",  # mis-wired: a positive return stat
    )
    row = plan.iloc[0]
    assert row["kelly_scale"] == 1.0, "Kelly must be disabled on non-loss avg_loss input"
    assert "kelly_note" in plan.columns and "non-negative" in str(row["kelly_note"])


def test_kelly_active_with_true_loss_statistic():
    """H3 control: a genuine negative avg_loss keeps Kelly sizing functional."""
    from src.capital.management import build_capital_plan

    candidates = pd.DataFrame(
        [
            {
                "symbol": "BBB", "close": 25000.0, "atr_pct_14": 0.03,
                "trade_edge_score": 80.0, "volatility_regime": "Normal Vol",
                "win_rate": 0.60, "avg_gain": 0.06, "avg_loss": -0.03,
            }
        ]
    )
    plan = build_capital_plan(
        candidates,
        nav=1_000_000_000,
        p_win_col="win_rate",
        avg_gain_col="avg_gain",
        avg_loss_col="avg_loss",
    )
    row = plan.iloc[0]
    assert row["kelly_scale"] != 1.0, "true loss stats should engage Kelly overlay"
