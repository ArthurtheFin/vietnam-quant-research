"""Automated look-ahead / leakage guards (audit D4/D5).

check_lookahead_bias/check_data_leakage/check_survivorship_bias in
bias_checks.py existed but were only ever invoked manually from a research
notebook. These guards are wired directly into the save/score call sites so
a forward-looking column cannot silently ride into a production artifact.
"""
from __future__ import annotations

import warnings

import pandas as pd


def find_forward_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if "forward" in c.lower() or "future" in c.lower()]


def assert_no_forward_columns(df: pd.DataFrame, context: str, mode: str = "raise") -> pd.DataFrame:
    """Guard against forward-looking columns leaking into a scoring/output step.

    mode="raise": scoring inputs must never contain forward_/future_ columns.
    mode="drop": output artifacts silently strip them and emit a warning instead
    of failing the whole pipeline run over a research-only column.
    """
    forward_cols = find_forward_columns(df)
    if not forward_cols:
        return df
    if mode == "raise":
        raise ValueError(
            f"{context}: forward-looking column(s) {forward_cols} must not feed a live scoring step "
            "(audit D5 — these are backtest-only labels, e.g. forward_return_Nd)."
        )
    warnings.warn(
        f"{context}: dropping forward-looking column(s) {forward_cols} before saving output (audit D5)."
    )
    return df.drop(columns=forward_cols)
