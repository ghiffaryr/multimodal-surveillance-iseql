"""Tests for the ISEQL facade: text <-> model compile round-trips.

These exercise ``compile_query`` (text path) and ``compile_model`` (timeline
builder path) against the stubbed config DB, verifying that the two paths agree
so timeline-built events behave like text-authored events.
"""
from __future__ import annotations

import pytest

import iseql.facade as facade

_P1 = 'π_{M1.sf, M1.ef}'
_P2 = 'π_{M1.sf, M2.ef}'


def iv(name, args, ts, te, group):
    return {"pred": {"name": name, "arguments": args}, "ts": ts, "te": te, "group": group}


def test_vocabulary(config_db):
    vocab = facade.vocabulary()
    by_name = {p["name"]: p for p in vocab["predicates"]}
    assert by_name["running"]["modality"] == "visual"
    assert by_name["running"]["args"] == [["person"]]
    assert by_name["gunshot"]["modality"] == "audio"
    assert by_name["enter_or_exit_vehicle"]["args"] == [["person"], ["vehicle"]]
    assert by_name["explosion_visible"]["args"] == [["vehicle", "object"]]
    assert "person" in vocab["participant_classes"]
    assert "object" in vocab["participant_classes"]


def test_compile_query_flat(config_db):
    res = facade.compile_query(
        'π_{M1.st, M2.et} (σ_{pred="running" ∧ arg1="person"}(M1) '
        'Bef σ_{pred="walking" ∧ arg1="person"}(M2))',
        name="e", delta_unit="seconds",
    )
    assert res["model"]["event_name"] == "e"
    assert "Bef" in res["iseql"]
    assert "st" in res["sql"] and "et" in res["sql"]


def test_compile_query_tree_roundtrip(config_db):
    q = (f'({_P1} (σ_{{pred="running" ∧ arg1="person"}}(M1)) '
         f'∪ {_P1} (σ_{{pred="gunshot"}}(M1))) '
         f'\\ {_P1} (σ_{{pred="walking" ∧ arg1="person"}}(M1))')
    res = facade.compile_query(q, name="e", delta_unit="frames")
    assert "UNION" in res["sql"] and "EXCEPT" in res["sql"]
    # text round-trip reproduces the same set structure
    again = facade.compile_query(res["iseql"], name="e", delta_unit="frames")
    assert "UNION" in again["sql"] and "EXCEPT" in again["sql"]


def test_compile_model_matches_query(config_db):
    m = {
        "event_name": "e",
        "delta_unit": "seconds",
        "intervals": [
            iv("running", ["person"], 10, 20, "g1"),
            iv("enter_or_exit_vehicle", ["person", "vehicle"], 22, 30, "g1"),
        ],
        "set_expression": {"group": "g1"},
        "operator_overrides": [{"side": "g1", "pair_idx": 1, "operator": "Bef"}],
        "delta_map": {"g1.0": {"delta": 5, "zeta": "<=", "rho": 2}},
    }
    res = facade.compile_model(m)
    assert "(M2.st - M1.et) <= 7" in res["sql"]

    # The rendered ISEQL text round-trips back to an equivalent model.
    text_res = facade.compile_query(res["iseql"], name="e", delta_unit="seconds")
    assert "(M2.st - M1.et) <= 7" in text_res["sql"]


def test_compile_query_invalid(config_db):
    with pytest.raises(Exception):
        facade.compile_query(
            f'{_P2} (σ_{{pred="running"}}(M1) not-an-operator σ_{{pred="walking"}}(M2))',
            name="e",
        )


def test_compile_query_undefined_predicate(config_db):
    with pytest.raises(Exception, match="not defined"):
        facade.compile_query(f'{_P1} (σ_{{pred="foobar"}}(M1))', name="e")


def test_compile_query_missing_args(config_db):
    with pytest.raises(Exception, match="missing|expects"):
        facade.compile_query(f'{_P1} (σ_{{pred="running"}}(M1))', name="e")


def test_compile_query_wrong_args(config_db):
    with pytest.raises(Exception, match="arg1"):
        facade.compile_query(
            f'{_P1} (σ_{{pred="running" ∧ arg1="vehicle"}}(M1))', name="e"
        )


def test_compile_query_alternatives_args(config_db):
    # explosion_visible accepts arg1 in {vehicle, object}
    res = facade.compile_query(
        f'{_P1} (σ_{{pred="explosion_visible" ∧ arg1="vehicle"}}(M1))', name="e"
    )
    assert "RelationType = 'explosion_visible'" in res["sql"]


def test_compile_query_projection_arg_out_of_range(config_db):
    with pytest.raises(Exception, match="has no arg2"):
        facade.compile_query(
            'π_{M1.arg2, M1.sf} (σ_{pred="running" ∧ arg1="person"}(M1))', name="e"
        )


def test_compile_query_projection_unknown_interval(config_db):
    with pytest.raises(Exception, match="does not exist"):
        facade.compile_query(
            'π_{M2.arg1} (σ_{pred="running" ∧ arg1="person"}(M1))', name="e"
        )


def test_compile_query_projection_unknown_attribute(config_db):
    with pytest.raises(Exception, match="unknown attribute"):
        facade.compile_query(
            'π_{M1.arg1, M1.sss} (σ_{pred="running" ∧ arg1="person"}(M1))', name="e"
        )


def test_compile_query_cross_condition_arg_out_of_range(config_db):
    with pytest.raises(Exception, match="has no arg3"):
        facade.compile_query(
            'π_{M1.arg1, M2.arg1, M1.arg2, M2.arg2} '
            '(σ_{M1.arg1≠M2.arg1 ∧ M1.arg2=M2.arg3} '
            '(σ_{pred="carrying" ∧ arg1="person" ∧ arg2="object"}(M1) '
            'SP σ_{pred="carrying" ∧ arg1="person" ∧ arg2="object"}(M2)))',
            name="e",
        )


def test_facade_validate_model(config_db):
    m = {
        "event_name": "e",
        "intervals": [iv("running", ["person"], 10, 20, "g1")],
        "set_expression": {"group": "g1"},
    }
    assert facade.validate_model(m) is not None


def test_facade_render_model(config_db):
    m = {
        "event_name": "e",
        "intervals": [iv("running", ["person"], 10, 20, "g1")],
        "set_expression": {"group": "g1"},
    }
    text = facade.render_model(m)
    assert 'pred="running"' in text


def test_facade_compile_event(config_db):
    m = {
        "event_name": "e",
        "intervals": [iv("running", ["person"], 10, 20, "g1")],
        "set_expression": {"group": "g1"},
    }
    iseql, sql = facade.compile_event(m, {}, "a1", fps=1, audio_predicates={"gunshot"})
    assert "RelationType = 'running'" in sql
