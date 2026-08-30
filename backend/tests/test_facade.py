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
    assert by_name["running"]["args"] == ["person"]
    assert by_name["gunshot"]["modality"] == "audio"
    assert by_name["enter_or_exit_vehicle"]["args"] == ["person", "vehicle"]
    assert "person" in vocab["participant_classes"]


def test_compile_query_flat(config_db):
    res = facade.compile_query(
        'π_{M1.st, M2.et} (σ_{pred="running"}(M1) Bef σ_{pred="walking"}(M2))',
        name="e", delta_unit="seconds",
    )
    assert res["model"]["event_name"] == "e"
    assert "Bef" in res["iseql"]
    assert "st" in res["sql"] and "et" in res["sql"]


def test_compile_query_tree_roundtrip(config_db):
    q = (f'({_P1} (σ_{{pred="running"}}(M1)) ∪ {_P1} (σ_{{pred="gunshot"}}(M1))) '
         f'\\ {_P1} (σ_{{pred="walking"}}(M1))')
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
    assert "(M2.sf - M1.ef) <= 7" in res["sql"]

    # The rendered ISEQL text round-trips back to an equivalent model.
    text_res = facade.compile_query(res["iseql"], name="e", delta_unit="frames")
    assert "(M2.sf - M1.ef) <= 7" in text_res["sql"]


def test_compile_query_invalid(config_db):
    with pytest.raises(Exception):
        facade.compile_query(
            f'{_P2} (σ_{{pred="running"}}(M1) not-an-operator σ_{{pred="walking"}}(M2))',
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
