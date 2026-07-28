"""A watchlist must say what its membership rests on, not just how long it is.

AUDIT_NOTEBOOKS_REPORT.md Đợt 5 (A). With ranking_mode="no_alpha_liquidity_sort"
-- the live default since WATCHLIST_VALIDATION_REPORT.md's Nhánh C found no
validated alpha factor -- client_score_ok is forced True, so the configured
client_ready_threshold (60.0) is bypassed and rows are ordered by value_ma20.

Controlled experiment, 2026-07-28: zeroing every meta/alpha score still returned
10 client-ready names (final_score 13.7-70.1). Only deleting the artifacts
outright collapsed the tier to 0. The tier gates on artifact PRESENCE, not on
evidence STRENGTH -- so a reader seeing "10 names" learns nothing.

These tests pin the disclosure, not the selection. Option (i), an absolute floor,
would change selection and needs its own pre-registration.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.screening.final_watchlist import build_evidence_summary


def _tier(scores: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"symbol": [f"S{i}" for i in range(len(scores))],
                         "final_score": scores})


def test_summary_reports_split_when_threshold_is_bypassed():
    summary = build_evidence_summary(
        _tier([65.0, 24.5, 6.9]), tier_name="client_ready",
        client_threshold=60.0, no_alpha_mode=True,
    )
    assert summary["count"] == 3
    assert summary["n_meeting_configured_threshold"] == 1
    assert summary["n_liquidity_rank_only"] == 2
    assert summary["score_threshold_applied"] is False
    assert "thanh khoản" in summary["headline"]


def test_summary_is_explicit_when_nothing_qualifies():
    """The zero-signal case: the artifact must say so rather than look normal."""
    summary = build_evidence_summary(
        _tier([]), tier_name="client_ready", client_threshold=60.0, no_alpha_mode=True,
    )
    assert summary["count"] == 0
    assert "0 mã" in summary["headline"]


def test_all_weak_names_are_reported_as_rank_only():
    """Every name below the configured bar must be counted as such -- this is the
    state that used to be invisible (GEX at final_score 6.91 labelled Medium-High)."""
    summary = build_evidence_summary(
        _tier([10.3, 6.9, 18.6]), tier_name="client_ready",
        client_threshold=60.0, no_alpha_mode=True,
    )
    assert summary["n_meeting_configured_threshold"] == 0
    assert summary["n_liquidity_rank_only"] == 3
    assert "0 đạt ngưỡng" in summary["headline"]


def test_summary_says_so_when_the_threshold_really_is_applied():
    summary = build_evidence_summary(
        _tier([88.0, 72.0]), tier_name="client_ready",
        client_threshold=60.0, no_alpha_mode=False,
    )
    assert summary["score_threshold_applied"] is True
    assert "tất cả đạt ngưỡng" in summary["headline"]


@pytest.mark.parametrize("scores,expected", [
    ([65.0], "Medium-High"),
    ([75.0], "High"),
    ([6.91], "Liquidity-Only"),
])
def test_confidence_label_stops_flattering_weak_names(scores, expected):
    """confidence_label used to depend only on tier membership, so anything in the
    client tier got at least "Medium-High" -- including a 6.91/100 name."""
    import numpy as np

    client_threshold = 60.0
    score = pd.Series(scores)
    label = np.select(
        [score.ge(70.0), score.ge(client_threshold)],
        ["High", "Medium-High"],
        default="Liquidity-Only",
    )
    assert label[0] == expected
