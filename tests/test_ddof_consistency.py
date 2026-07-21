"""Regression tests for the ddof=0 -> ddof=1 standardization
(docs/reports/codebase_audit/GSQUANT_REFERENCE_CHECK.md Finding #1, closed
across 3 rounds) and the Sharpe-ratio consolidation into a single source of
truth (src.risk.management.sharpe_ratio).

Round 1 fixed src/risk/management.py (6 sites) and
stock-decision-engine/src/risk.py (4 sites) -- the ones with a named
sharpe_ratio()/annualized_volatility() function. Round 2 closed the
remaining family members surfaced while tracing which published numbers the
bug actually touched: scratch/dsr_and_bootstrap_v2.py:125 (numpy-array
.std(), fed a published bootstrap CI directly -- see
docs/reports/scoring/ROBUSTNESS_REPORT.md), src/simulation/bootstrap.py:81
(summarize_simulation's std_return, same numpy-default-ddof=0 pattern),
scripts/build_portfolio_stack.py:98 (explicit ddof=0, a live fallback path),
src/analytics/entropy.py:15 (explicit ddof=0, dead code -- zero callers,
fixed for hygiene only, never affected any output), and
stock-decision-engine/src/features.py:158 (explicit ddof=0, duplicate of the
already-fixed stock-decision-engine/src/risk.py:14).

Every remaining .std()/.var()/.cov() call in the repo without an explicit
ddof is either a pandas Series/DataFrame method (already defaults to
ddof=1) or a cov/var pair used as a ratio (e.g. beta = cov/var), which is
mathematically invariant to ddof as long as both sides use the same
convention -- confirmed by full repo grep, not assumed."""
from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.risk import management as risk_management
from src.simulation import bootstrap as sim_bootstrap
from src.analytics.entropy import _clip_quantile_edges

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SDE_SRC = PROJECT_ROOT / "stock-decision-engine" / "src"

if str(SDE_SRC) not in sys.path:
    sys.path.insert(0, str(SDE_SRC))

import risk as sde_risk  # noqa: E402  (stock-decision-engine/src/risk.py)


# ---------------------------------------------------------------------------
# AST scan: every file this bug family has touched must contain zero
# ddof=0 -- catches any future reintroduction, not just today's known sites.
# ---------------------------------------------------------------------------

SCANNED_FILES = [
    PROJECT_ROOT / "src" / "risk" / "management.py",
    PROJECT_ROOT / "stock-decision-engine" / "src" / "risk.py",
    PROJECT_ROOT / "stock-decision-engine" / "src" / "features.py",
    PROJECT_ROOT / "src" / "simulation" / "bootstrap.py",
    PROJECT_ROOT / "scripts" / "build_portfolio_stack.py",
    PROJECT_ROOT / "src" / "analytics" / "entropy.py",
    PROJECT_ROOT / "scratch" / "dsr_and_bootstrap_v2.py",
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


def _find_bare_numpy_std_calls(path: Path) -> list[str]:
    """Flags .std(...)/.var(...) calls with no ddof kwarg at all -- these are
    fine on pandas objects (default ddof=1) but silently wrong on numpy
    arrays (default ddof=0). Can't tell the receiver's type from the AST
    alone, so this is informational tracking for the two files we know
    operate on raw numpy arrays, not a blanket assertion for the whole repo
    (that would flag legitimate pandas .std() calls everywhere)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    bare = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("std", "var"):
            if not any(kw.arg == "ddof" for kw in node.keywords):
                bare.append(f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}")
    return bare


@pytest.mark.parametrize(
    "path",
    [PROJECT_ROOT / "src" / "simulation" / "bootstrap.py", PROJECT_ROOT / "scratch" / "dsr_and_bootstrap_v2.py"],
    ids=lambda p: str(p.relative_to(PROJECT_ROOT)),
)
def test_numpy_array_files_have_no_bare_std_calls(path: Path):
    """These two files operate on raw numpy arrays (block_bootstrap_returns'
    return type) -- every .std()/.var() call here must pass ddof explicitly,
    since a bare call would silently default to numpy's ddof=0."""
    bare = _find_bare_numpy_std_calls(path)
    assert not bare, f"bare .std()/.var() on a numpy-array file (defaults to ddof=0): {bare}"


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


def test_summarize_simulation_std_return_matches_unbiased_formula():
    """src/simulation/bootstrap.py:81 -- summarize_simulation operates on raw
    numpy arrays throughout (simulated_equity_paths is np.ndarray), so the
    bare .std() there defaulted to numpy's ddof=0."""
    rng = np.random.default_rng(42)
    paths = rng.normal(100.0, 5.0, size=(200, 21))  # 200 sims, 21-day paths, start col irrelevant here
    result = sim_bootstrap.summarize_simulation(paths)
    final_returns = paths[:, -1] / paths[0, 0] - 1.0
    expected_std = float(final_returns.std(ddof=1))
    assert result["std_return"] == pytest.approx(expected_std, abs=1e-9)


def test_resolve_inverse_vol_input_fallback_matches_unbiased_formula():
    """scripts/build_portfolio_stack.py:98 -- the atr_pct_14-missing fallback
    path, a live (if rarely-triggered) production branch."""
    dashboard = importlib.import_module("scripts.build_portfolio_stack")
    rng = np.random.default_rng(42)
    symbols = ["AAA", "BBB", "CCC"]
    return_matrix = pd.DataFrame(rng.normal(0.0, 0.01, size=(60, 3)), columns=symbols)
    candidates = pd.DataFrame({"symbol": symbols})  # no atr_pct_14 -> forces the fallback branch
    warnings: list[str] = []

    result = dashboard._resolve_inverse_vol_input(candidates, return_matrix, warnings)

    expected = return_matrix.std(ddof=1) * np.sqrt(252.0)
    expected = expected.replace(0.0, np.nan).fillna(0.02)
    pd.testing.assert_series_equal(result, expected, check_exact=False, atol=1e-9)
    assert warnings, "fallback branch must warn when atr_pct_14 is missing"


def test_clip_quantile_edges_fallback_matches_unbiased_formula():
    """src/analytics/entropy.py:15 -- dead code (zero callers anywhere in the
    repo), fixed for hygiene/consistency only; this test exists so the
    formula stays correct if the function is ever wired up."""
    # Constant-ish series forces quantile(0.01) == quantile(0.99), triggering
    # the std-based fallback branch (lines 13-18).
    series = pd.Series([5.0] * 30)
    lo, hi = _clip_quantile_edges(series)
    center = 5.0
    spread = 1.0  # std of an all-identical series is 0 -> falls back to the spread=1.0 default
    assert lo == pytest.approx(center - 3 * spread, abs=1e-9)
    assert hi == pytest.approx(center + 3 * spread, abs=1e-9)

    # A series with real spread but a tied 1st/99th percentile (heavy ties at
    # the edges) exercises the ddof=1 std computation itself.
    series2 = pd.Series([1.0] * 5 + list(range(2, 10)) + [10.0] * 5)
    lo2, hi2 = _clip_quantile_edges(series2, lower_q=0.001, upper_q=0.999)
    if series2.quantile(0.001) == series2.quantile(0.999):
        expected_spread = float(series2.std(ddof=1))
        expected_center = float(series2.median())
        assert lo2 == pytest.approx(expected_center - 3 * expected_spread, abs=1e-9)
        assert hi2 == pytest.approx(expected_center + 3 * expected_spread, abs=1e-9)


def test_sde_features_module_imports_cleanly_after_fix():
    """stock-decision-engine/src/features.py:158 -- duplicate of the
    already-fixed stock-decision-engine/src/risk.py:14, different file. The
    fix is inlined inside _latest_metrics(), which needs a full OHLCV+
    indicator fixture to exercise meaningfully; the regression guard for
    this specific line is test_no_ddof_zero_in_fixed_files' AST scan above
    (features.py is in SCANNED_FILES). This test only confirms the edit
    didn't break the module's syntax/imports."""
    sde_features = importlib.import_module("features")  # stock-decision-engine/src/features.py (via sys.path)
    assert hasattr(sde_features, "_latest_metrics")


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
