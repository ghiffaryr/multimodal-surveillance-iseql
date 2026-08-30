"""Unit tests for the ISEQL operator helpers (``iseql.helpers``).

These exercise the interval model, operator auto-detection, and every SQL
rendering function directly (they are the single source of truth the parser and
compiler share).
"""
from __future__ import annotations

import pytest

from iseql.helpers import (
    Interval,
    Predicate,
    apply_manual_override,
    detect_operator,
    iseql_after,
    iseql_before,
    iseql_dj,
    iseql_ef,
    iseql_loj,
    iseql_rdj,
    iseql_roj,
    iseql_sp,
)


def iv(ts: int, te: int) -> Interval:
    return Interval(Predicate("x"), ts, te)


# ---------------------------------------------------------------------------
# interval model
# ---------------------------------------------------------------------------

def test_interval_requires_ordered_bounds():
    with pytest.raises(ValueError):
        Interval(Predicate("x"), 10, 5)


def test_interval_accepts_equal_bounds():
    assert iv(10, 10).Ts == 10


# ---------------------------------------------------------------------------
# operator detection
# ---------------------------------------------------------------------------

def test_detect_before():
    d = detect_operator(iv(0, 10), iv(15, 25))
    assert d.operator == "Bef"
    assert d.delta == 5


def test_detect_after():
    d = detect_operator(iv(15, 25), iv(0, 10))
    assert d.operator == "Aft"
    assert d.delta == 5


def test_detect_during_join():
    d = detect_operator(iv(5, 15), iv(0, 20))
    assert d.operator == "DJ"
    assert d.delta == 5
    assert d.epsilon == 5


def test_detect_reverse_during_join():
    d = detect_operator(iv(0, 20), iv(5, 15))
    assert d.operator == "RDJ"


def test_detect_left_overlap_join():
    d = detect_operator(iv(0, 10), iv(5, 15))
    assert d.operator == "LOJ"


def test_detect_right_overlap_join():
    d = detect_operator(iv(5, 15), iv(0, 10))
    assert d.operator == "ROJ"


def test_apply_manual_override_sp():
    d = apply_manual_override("SP", iv(0, 10), iv(5, 15))
    assert d.operator == "SP"
    assert d.delta == 5


def test_apply_manual_override_ef():
    d = apply_manual_override("EF", iv(0, 20), iv(5, 15))
    assert d.operator == "EF"
    assert d.epsilon == 5


def test_apply_manual_override_falls_back():
    d = apply_manual_override("Bef", iv(0, 10), iv(15, 25))
    assert d.operator == "Bef"


# ---------------------------------------------------------------------------
# SQL rendering
# ---------------------------------------------------------------------------

def test_iseql_before_unbounded():
    sql = iseql_before("M1", "M2")
    assert sql == "(M1.ef <= (M2.sf + 0))"


def test_iseql_before_bounded():
    sql = iseql_before("M1", "M2", delta=5, zeta="<=", rho=2)
    assert "(M2.sf - M1.ef) <= 7" in sql
    assert "(M1.ef <= (M2.sf + 2)" in sql


def test_iseql_before_time_domain():
    sql = iseql_before("M1", "M2", delta=5, cols=("st", "et"))
    assert "(M2.st - M1.et) <= 5" in sql


def test_iseql_before_strict():
    sql = iseql_before("M1", "M2", zeta="<")
    assert "(M1.ef < (M2.sf + 0))" in sql


def test_iseql_before_invalid_strictness():
    with pytest.raises(ValueError):
        iseql_before("M1", "M2", zeta="?")


def test_iseql_after_is_reversed_before():
    sql = iseql_after("M1", "M2", delta=3)
    assert "(M1.sf - M2.ef) <= 3" in sql


def test_iseql_sp_bounded_and_unbounded():
    assert "(M2.sf - M1.sf)" not in iseql_sp("M1", "M2")
    sql = iseql_sp("M1", "M2", delta=4)
    assert "(M2.sf - M1.sf) <= 4" in sql


def test_iseql_ef():
    sql = iseql_ef("M1", "M2", epsilon=6)
    assert "(M1.ef - M2.ef) <= 6" in sql


def test_iseql_dj():
    sql = iseql_dj("M1", "M2", delta=2, epsilon=3)
    assert "(M1.sf - M2.sf) <= 2" in sql
    assert "(M2.ef - M1.ef) <= 3" in sql


def test_iseql_loj():
    sql = iseql_loj("M1", "M2", delta=2, epsilon=3)
    assert "(M2.sf - M1.sf) <= 2" in sql
    assert "(M2.ef - M1.ef) <= 3" in sql


def test_iseql_rdj_is_reversed_dj():
    sql = iseql_rdj("M1", "M2", delta=2, epsilon=3)
    assert sql == iseql_dj("M2", "M1", delta=2, epsilon=3)


def test_iseql_roj_is_reversed_loj():
    sql = iseql_roj("M1", "M2", delta=2, epsilon=3)
    assert sql == iseql_loj("M2", "M1", delta=2, epsilon=3)
