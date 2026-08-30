"""Tests for the ISEQL compiler (``iseql.compiler``): model -> SQL.

These cover validation, flat/tree SQL rendering, audio vs. visual sources,
cross-conditions, and named threshold keys (which resolve per-detect and must
not leak into preview SQL).
"""
from __future__ import annotations

import pytest

from iseql.compiler import (
    ModelValidationError,
    compile_event,
    render_iseql,
    validate_model,
)

AUDIO = {"gunshot", "tire_squeal"}


def iv(name, args, ts, te, group=None):
    return {"pred": {"name": name, "arguments": args}, "ts": ts, "te": te, "group": group}


def flat_model(**overrides):
    m = {
        "event_name": "e",
        "intervals": [
            iv("running", ["person"], 10, 20, "g1"),
            iv("enter_or_exit_vehicle", ["person", "vehicle"], 22, 30, "g1"),
        ],
        "set_expression": {"group": "g1"},
        "operator_overrides": [{"side": "g1", "pair_idx": 1, "operator": "Bef"}],
        "delta_map": {"g1.0": {"delta": 5, "zeta": "<=", "rho": 2}},
    }
    m.update(overrides)
    return m


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def test_validate_model_ok():
    validate_model(flat_model())


def test_validate_model_empty_intervals():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": []})


def test_validate_model_missing_pred_name():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [{"pred": {"name": ""}}]})


def test_validate_model_bad_set_operator():
    with pytest.raises(ModelValidationError):
        validate_model(
            {"intervals": [iv("running", [], 0, 1, "g1")], "set_operator": "?"}
        )


def test_validate_model_mixes_expression_and_side():
    with pytest.raises(ModelValidationError):
        validate_model({
            "intervals": [{"pred": {"name": "running"}, "set_side": "left"}],
            "set_expression": {"group": "g1"},
        })


# ---------------------------------------------------------------------------
# SQL rendering
# ---------------------------------------------------------------------------

def test_flat_sql_bound_and_predicate():
    iseql, sql = compile_event(flat_model(), {}, "a1", fps=1, audio_predicates=AUDIO)
    assert "RelationType = 'running'" in sql
    assert "(M2.sf - M1.ef) <= 7" in sql  # delta 5 + rho 2


def test_tree_union_except_with_audio():
    m = {
        "event_name": "e",
        "intervals": [
            iv("running", ["person"], 1000, 1010, "g1"),
            iv("gunshot", [], 1000, 1010, "g2"),
            iv("walking", ["person"], 1000, 1010, "g3"),
        ],
        "set_expression": {
            "op": "\\",
            "children": [
                {"op": "∪", "children": [{"group": "g1"}, {"group": "g2"}]},
                {"group": "g3"},
            ],
        },
    }
    iseql, sql = compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)
    assert "UNION" in sql and "EXCEPT" in sql
    assert "AudioPerInterval" in sql  # gunshot is an audio predicate


def test_cross_condition_attr_and_duration():
    m = {
        "event_name": "e",
        "intervals": [
            iv("running", ["person"], 1000, 1010, "g1"),
            iv("walking", ["person"], 1012, 1020, "g1"),
        ],
        "set_expression": {"group": "g1"},
        "operator_overrides": [{"side": "g1", "pair_idx": 1, "operator": "Bef"}],
        "cross_conditions": [
            {"left_alias": "M1", "left_attr": "arg1", "op": "=",
             "right_alias": "M2", "right_attr": "arg1"},
            {"type": "duration", "left_alias": "M1", "left_attr": "ef",
             "right_alias": "M1", "right_attr": "sf", "op": ">=", "value": 5},
        ],
    }
    iseql, sql = compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)
    assert "(M1.arg1 = M2.arg1)" in sql
    assert ">= 5" in sql


def test_mixed_audio_visual_selection_raises():
    m = flat_model(
        intervals=[iv("running", [], 0, 1, "g1")],
        set_expression={"group": "g1"},
        operator_overrides=[],
        delta_map={},
    )
    # selection naming both an audio and a visual predicate
    m["intervals"][0]["selection"] = {"preds": ["running", "gunshot"]}
    with pytest.raises(ModelValidationError):
        compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)


def test_named_keys_resolve_unbounded():
    m = flat_model(
        delta_map={"g1.0": {"delta": "delta_visual_handoff", "zeta": "<=",
                            "rho": "rho_visual_handoff"}},
    )
    deltas = {"delta_visual_handoff": None, "rho_visual_handoff": None}
    iseql, sql = compile_event(m, deltas, "a1", fps=1, audio_predicates=AUDIO)
    assert "delta_visual_handoff" not in sql
    assert "rho_visual_handoff" not in sql


def test_audio_predicates_required():
    with pytest.raises(ModelValidationError):
        compile_event(flat_model(), {}, "a1", fps=1, audio_predicates=None)


# ---------------------------------------------------------------------------
# ISEQL text rendering
# ---------------------------------------------------------------------------

def test_render_iseql_flat():
    text = render_iseql(flat_model())
    assert 'pred="running"' in text
    assert "Bef" in text


def test_render_iseql_tree():
    m = {
        "event_name": "e",
        "intervals": [
            iv("running", ["person"], 1000, 1010, "s1"),
            iv("walking", ["person"], 1000, 1010, "s2"),
        ],
        "set_expression": {"op": "∪", "children": [{"group": "s1"}, {"group": "s2"}]},
    }
    text = render_iseql(m)
    assert "∪" in text


def test_render_iseql_roundtrips_through_parser():
    from iseql.parser import parse_iseql
    text = render_iseql(flat_model())
    model = parse_iseql(text, name="e")
    assert model["intervals"][0]["pred"]["name"] == "running"


# ---------------------------------------------------------------------------
# legacy set_side (left/right) path
# ---------------------------------------------------------------------------

def _side_model(op: str):
    return {
        "event_name": "e",
        "intervals": [
            {"pred": {"name": "running", "arguments": ["person"]},
             "ts": 1000, "te": 1010, "set_side": "left"},
            {"pred": {"name": "walking", "arguments": ["person"]},
             "ts": 1000, "te": 1010, "set_side": "right"},
        ],
        "set_operator": op,
    }


@pytest.mark.parametrize("op, keyword", [("∪", "UNION"), ("∩", "INTERSECT"), ("\\", "EXCEPT")])
def test_set_side_left_right(op, keyword):
    iseql, sql = compile_event(_side_model(op), {}, "a1", fps=1, audio_predicates=AUDIO)
    assert keyword in sql


def test_multi_predicate_selection():
    m = flat_model(
        intervals=[iv("running", ["person"], 0, 1, "g1")],
        set_expression={"group": "g1"},
        operator_overrides=[],
        delta_map={},
    )
    m["intervals"][0]["selection"] = {"preds": ["running", "walking"]}
    iseql, sql = compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)
    assert "RelationType IN ('running', 'walking')" in sql


def test_multi_class_argument():
    m = flat_model(
        intervals=[iv("running", ["person"], 0, 1, "g1")],
        set_expression={"group": "g1"},
        operator_overrides=[],
        delta_map={},
    )
    m["intervals"][0]["selection"] = {"preds": ["running"], "args": {"1": ["person", "vehicle"]}}
    iseql, sql = compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)
    assert "Class IN ('person', 'vehicle')" in sql


def test_custom_projection_flat():
    m = flat_model(
        set_expression=None,
        custom_projection=["M1.arg1", "M1.sf", "M1.ef"],
    )
    iseql, sql = compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)
    assert "M1.arg1" in sql


def test_domain_mixing_raises():
    m = flat_model(set_expression=None, custom_projection=["M1.st", "M1.ef"])
    with pytest.raises(ModelValidationError):
        compile_event(m, {}, "a1", fps=1, audio_predicates=AUDIO)


# ---------------------------------------------------------------------------
# extra validation branches
# ---------------------------------------------------------------------------

def test_validate_bad_json_string():
    with pytest.raises(ModelValidationError):
        validate_model("not-json{")


def test_validate_non_dict():
    with pytest.raises(ModelValidationError):
        validate_model(["a", "b"])


def test_validate_interval_not_object():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": ["nope"]})


def test_validate_ts_not_int():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [{"pred": {"name": "x"}, "ts": "a", "te": 1}]})


def test_validate_bad_cross_condition():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")],
                        "cross_conditions": [{"left_alias": "M1"}]})


def test_validate_bad_group_type():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [{"pred": {"name": "x"}, "group": 5}]})


def test_render_iseql_empty():
    from iseql.compiler import render_iseql
    assert render_iseql({"intervals": []}) == "-- No intervals."


def test_render_iseql_set_side():
    from iseql.compiler import render_iseql
    text = render_iseql(_side_model("∪"))
    assert "∪" in text


def test_validate_json_non_dict():
    with pytest.raises(ModelValidationError):
        validate_model("[1, 2]")


def test_validate_cross_conditions_not_list():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")], "cross_conditions": "nope"})


def test_validate_set_operator_without_side():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")], "set_operator": "∪"})


def test_validate_expression_node_not_dict():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")], "set_expression": "x"})


def test_validate_expression_bad_group():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")], "set_expression": {"group": 5}})


def test_validate_expression_bad_projection():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")],
                        "set_expression": {"group": "g1", "projection": [1, 2]}})


def test_validate_expression_bad_op():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")],
                        "set_expression": {"op": "?", "children": [{"group": "g1"}]}})


def test_validate_expression_bad_children():
    with pytest.raises(ModelValidationError):
        validate_model({"intervals": [iv("x", [], 0, 1, "g1")],
                        "set_expression": {"op": "∪", "children": "nope"}})


def test_render_iseql_with_cross_conditions():
    m = {
        "event_name": "e",
        "intervals": [
            iv("running", ["person"], 1000, 1010, "g1"),
            iv("walking", ["person"], 1012, 1020, "g1"),
        ],
        "set_expression": {"group": "g1"},
        "operator_overrides": [{"side": "g1", "pair_idx": 1, "operator": "Bef"}],
        "cross_conditions": [
            {"left_alias": "M1", "left_attr": "arg1", "op": "=",
             "right_alias": "M2", "right_attr": "arg1"},
        ],
    }
    text = render_iseql(m)
    assert "M1.arg1=M2.arg1" in text or "M1.arg1 = M2.arg1" in text
