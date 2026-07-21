"""Regression tests for the ddof=0 -> ddof=1 standardization
(docs/reports/codebase_audit/GSQUANT_REFERENCE_CHECK.md Finding #1) and the
Sharpe-ratio consolidation into a single source of truth
(src.risk.management.sharpe_ratio).

Scope matches the round that fixed this: src/risk/management.py and
stock-decision-engine/src/risk.py specifically -- NOT a blanket scan of the
whole repo. src/analytics/entropy.py:15 and scripts/build_portfolio_stack.py:98
still use ddof=0 deliberately (out of scope this round, not regressions)."""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.risk import management as risk_management

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SDE_SRC = PROJECT_ROOT / "stock-decision-engine" / "src"

if str(SDE_SRC) not in sys.path:
    sys.path.insert(0, str(SDE_SRC))

import risk as sde_risk  # noqa: E402  (stock-decision-engine/src/risk.py)


# ---------------------------------------------------------------------------
# AST scan: the two fixed files must contain zero ddof=0 -- catches any
# future reintroduction, not just today's known sites.
# ---------------------------------------------------------------------------

SCANNED_FILES = [
    PROJECT_ROOT / "src" / "risk" / "management.py",
    PROJECT_ROOT / "stock-decision-engine" / "src" / "risk.py",
]


def _find_ddof_zero_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("std", "var"):
            for kw in node.keywords:
                if kw.arg == "ddof" and isinstance(kw.value, ast.Constant) and kw.value.value == 0:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    return offenders


@pytest.mark.parametrize("path", SCANNED_FILES, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
def test_no_ddof_zero_in_fixed_files(path: Path):
    offenders = _find_ddof_zero_calls(path)
    assert not offenders, f"ddof=0 reintroduced (should be ddof=1): {offenders}"


# ---------------------------------------------------------------------------
# Snapshot tests: fixed input -> output matches the unbiased (ddof=1) formula
# computed independently via numpy, tolerance 1e-9.
# ---------------------------------------------------------------------------

RETURNS = pd.Series([0.012, -0.018, 0.006, -0.004, 0.021, -0.009, 0.003, 0.015, -0.011, 0.008, 0.0, -0.014])


def test_annualized_volatility_matches_unbiased_formula():
    expected = float(RETURNS.to_numpy().std(ddof=1) * np.sqrt(252))
    actual = risk_management.annualized_volatility(RETURNS)
    assert actual == pytest.approx(expected, abs=1e-9)


def test_sharpe_ratio_matches_unbiased_formula():
    rf = 0.02
    excess = RETURNS - rf / 252
    expected = float(excess.mean() / excess.to_numpy().std(ddof=1) * np.sqrt(252))
    actual = risk_management.sharpe_ratio(RETURNS, risk_free_rate=rf)
    assert actual == pytest.approx(expected, abs=1e-9)


def test_sharpe_ratio_differs_measurably_from_ddof0_version():
    """Confirms the fix actually changes the number (not a no-op) -- if this
    ever starts failing because the two are equal, ddof stopped mattering,
    which would itself be worth investigating."""
    rf = 0.0
    ddof1 = risk_management.sharpe_ratio(RETURNS, risk_free_rate=rf)
    ddof0_vol = RETURNS.std(ddof=0)
    ddof0_sharpe = float(RETURNS.mean() / ddof0_vol * np.sqrt(252))
    assert ddof1 != pytest.approx(ddof0_sharpe, abs=1e-9)
    assert abs(ddof1) < abs(ddof0_sharpe)  # ddof=0 always inflates Sharpe


def test_sde_downside_deviation_matches_unbiased_formula():
    downside = RETURNS[RETURNS < 0]
    expected = float(downside.to_numpy().std(ddof=1) * np.sqrt(252))
    actual = sde_risk.downside_deviation(RETURNS)
    assert actual == pytest.approx(expected, abs=1e-9)


def test_sde_ratios_vol_matches_unbiased_formula():
    # ratios() requires >=20 aligned observations (stock-decision-engine/src/risk.py:33)
    rng = np.random.default_rng(42)
    stock = pd.Series(rng.normal(0.0005, 0.015, size=30))
    bench = pd.Series(rng.normal(0.0004, 0.012, size=30))
    result = sde_risk.ratios(stock, bench)

    expected_vol = float(stock.to_numpy().std(ddof=1) * np.sqrt(252))
    expected_sharpe = float((stock.mean() * 252) / expected_vol)
    assert result["sharpe"] == pytest.approx(expected_sharpe, abs=1e-9)

    tracking = stock - bench
    expected_te = float(tracking.to_numpy().std(ddof=1) * np.sqrt(252))
    assert result["tracking_error"] == pytest.approx(expected_te, abs=1e-9)


# ---------------------------------------------------------------------------
# Sharpe consolidation: scripts/main_visual_dashboard.py must call the same
# function object as src.risk.management, not a re-typed duplicate.
# ---------------------------------------------------------------------------

def test_dashboard_script_reuses_shared_sharpe_ratio():
    dashboard = importlib.import_module("scripts.main_visual_dashboard")
    assert dashboard.sharpe_ratio is risk_management.sharpe_ratio, (
        "scripts/main_visual_dashboard.py must import sharpe_ratio from "
        "src.risk.management, not define/import a different implementation"
    )
    assert not hasattr(dashboard, "calculate_sharpe_ratio"), (
        "calculate_sharpe_ratio was removed as a duplicate -- if this fails, "
        "someone re-added a second Sharpe implementation"
    )


def test_dashboard_sharpe_matches_management_sharpe_on_same_input():
    dashboard = importlib.import_module("scripts.main_visual_dashboard")
    assert dashboard.sharpe_ratio(RETURNS) == risk_management.sharpe_ratio(RETURNS)
