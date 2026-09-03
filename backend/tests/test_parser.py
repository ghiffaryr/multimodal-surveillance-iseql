"""Tests for the ISEQL text parser (``iseql.parser.parse_iseql``).

The parser turns the ISEQL-GUI text notation into a model dict.  These tests
cover the flat (single operand) form, the set-expression form, operator
thresholds, selections, cross-conditions and error handling.
"""
from __future__ import annotations

import pytest

from iseql.parser import IseqlParseError, parse_iseql

_P1 = 'π_{M1.sf, M1.ef}'
_P2 = 'π_{M1.sf, M2.ef}'


# ---------------------------------------------------------------------------
# flat (single operand)
# ---------------------------------------------------------------------------

def test_flat_single_interval():
    model = parse_iseql(f'{_P1} (σ_{{pred="running"}}(M1))', name="e")
    assert model["event_name"] == "e"
    assert model["delta_unit"] == "seconds"
    assert len(model["intervals"]) == 1
    iv = model["intervals"][0]
    assert iv["pred"]["name"] == "running"
    assert "ts" in iv and "te" in iv
    # single operand => flat model (no set_expression)
    assert model.get("set_expression") is None


def test_flat_two_intervals_with_operator():
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) SP σ_{{pred="walking"}}(M2))', name="e"
    )
    assert len(model["intervals"]) == 2
    assert model["operator_overrides"][0]["operator"] == "SP"
    # SP only uses δ, recorded with no typed value -> unbounded
    assert model["delta_map"]["0"]["delta"] is None


def test_flat_operator_thresholds():
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) DJ(δ:5, ε:10; ζ:<=, η:<, ρ:2) '
        f'σ_{{pred="walking"}}(M2))',
        name="e",
    )
    entry = model["delta_map"]["0"]
    assert entry["delta"] == 5
    assert entry["epsilon"] == 10
    assert entry["zeta"] == "<="
    assert entry["eta"] == "<"
    assert entry["rho"] == 2


def test_flat_projection_and_comment():
    model = parse_iseql(
        "-- Generated ISEQL query for e\n"
        f'{_P2} ( σ_{{pred="running"}}(M1) Bef σ_{{pred="walking"}}(M2) )',
        name="e",
    )
    assert model["custom_projection"] == ["M1.sf", "M2.ef"]
    assert model["operator_overrides"][0]["operator"] == "Bef"


# ---------------------------------------------------------------------------
# set expression (tree)
# ---------------------------------------------------------------------------

def test_set_expression_union():
    model = parse_iseql(
        f'{_P1} (σ_{{pred="running"}}(M1)) ∪ {_P1} (σ_{{pred="walking"}}(M1))',
        name="e",
    )
    assert model["set_expression"]["op"] == "∪"
    groups = [iv["group"] for iv in model["intervals"]]
    assert groups == ["s1", "s2"]
    # single-interval operands carry no temporal operators
    assert model["operator_overrides"] == []


def test_set_expression_parenthesised():
    model = parse_iseql(
        f'({_P1} (σ_{{pred="running"}}(M1)) ∪ {_P1} (σ_{{pred="walking"}}(M1))) '
        f'\\ {_P1} (σ_{{pred="carrying"}}(M1))',
        name="e",
    )
    root = model["set_expression"]
    assert root["op"] == "\\"
    assert root["children"][0]["op"] == "∪"
    groups = [iv["group"] for iv in model["intervals"]]
    assert groups == ["s1", "s2", "s3"]


# ---------------------------------------------------------------------------
# selections + cross-conditions
# ---------------------------------------------------------------------------

def test_selection_with_args_and_or():
    model = parse_iseql(
        f'{_P1} (σ_{{pred="enter_or_exit_vehicle" ∧ arg1="person" ∧ arg2="vehicle"}}(M1))',
        name="e",
    )
    iv = model["intervals"][0]
    assert iv["pred"]["arguments"] == ["person", "vehicle"]
    sel = iv["selection"]
    assert sel["preds"] == ["enter_or_exit_vehicle"]
    assert sel["args"] == {"1": ["person"], "2": ["vehicle"]}


def test_selection_or_branches():
    model = parse_iseql(
        f'{_P1} (σ_{{pred="running" ∨ pred="walking"}}(M1))', name="e"
    )
    sel = model["intervals"][0]["selection"]
    assert sel["branches"][0]["preds"] == ["running"]
    assert sel["branches"][1]["preds"] == ["walking"]


def test_cross_condition_attr():
    model = parse_iseql(
        f'{_P2} (σ_{{M1.arg1=M2.arg1}} '
        f'(σ_{{pred="running"}}(M1) SP σ_{{pred="walking"}}(M2)))',
        name="e",
    )
    cc = model["cross_conditions"][0]
    assert cc["left_alias"] == "M1"
    assert cc["left_attr"] == "arg1"
    assert cc["op"] == "="
    assert cc["right_attr"] == "arg1"


def test_cross_condition_duration():
    model = parse_iseql(
        f'{_P1} (σ_{{(M1.et − M1.st) ≥ 5}} (σ_{{pred="running"}}(M1)))',
        name="e",
    )
    cc = model["cross_conditions"][0]
    assert cc["type"] == "duration"
    assert cc["op"] == ">="
    assert cc["value"] == 5


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------

def test_error_trailing_garbage():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P1} (σ_{{pred="running"}}(M1)) gibberish', name="e")


def test_error_unknown_operator():
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{pred="running"}}(M1) XYZ σ_{{pred="walking"}}(M2))', name="e"
        )


def test_error_bad_delta_unit():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P1} (σ_{{pred="running"}}(M1))', name="e", delta_unit="minutes")


def test_error_unterminated_paren():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P1} (σ_{{pred="running"}}(M1)', name="e")


# ---------------------------------------------------------------------------
# all operators + threshold edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op", ["Bef", "Aft", "SP", "EF", "DJ", "RDJ", "LOJ", "ROJ"])
def test_all_operators_parse(op):
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) {op} σ_{{pred="walking"}}(M2))', name="e"
    )
    assert model["operator_overrides"][0]["operator"] == op
    assert len(model["intervals"]) == 2
    assert "ts" in model["intervals"][1] and "te" in model["intervals"][1]


# ---------------------------------------------------------------------------
# canvas synthesis geometry (ts/te layout from text)
# ---------------------------------------------------------------------------

def _synthesized(model):
    ivs = model["intervals"]
    assert len(ivs) == 2
    a, b = ivs[0], ivs[1]
    assert a["ts"] >= 0 and a["te"] >= 0 and b["ts"] >= 0 and b["te"] >= 0
    assert a["ts"] <= a["te"] and b["ts"] <= b["te"]
    return a, b


def test_synthesize_aft_is_fully_before():
    # Aft(r, s): s lies entirely before r (reverse of Bef), not clamped to 0.
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) Aft σ_{{pred="walking"}}(M2))', name="e"
    )
    a, b = _synthesized(model)
    assert b["te"] <= a["ts"]
    assert b["te"] - b["ts"] > 1  # not a degenerate sliver


def test_synthesize_roj_overlaps_on_right():
    # ROJ(r, s): s starts before r and ends before r (right overlap), not nested.
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) ROJ σ_{{pred="walking"}}(M2))', name="e"
    )
    a, b = _synthesized(model)
    assert b["ts"] < a["ts"]
    assert b["te"] < a["te"]
    assert b["te"] > a["ts"]  # genuine overlap, not disjoint


def test_synthesize_ef_second_ends_before_first():
    # EF(r, s): s shares r's start and ends before r (r is the longer interval).
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) EF σ_{{pred="walking"}}(M2))', name="e"
    )
    a, b = _synthesized(model)
    assert b["ts"] == a["ts"]
    assert b["te"] < a["te"]


def test_synthesize_bef_honours_delta_gap():
    # Bef(δ:5): s starts δ after r ends, not touching.
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) Bef(δ:5) σ_{{pred="walking"}}(M2))', name="e"
    )
    a, b = _synthesized(model)
    assert b["ts"] == a["te"] + 5


def test_operator_unbounded_delta():
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) Bef(δ:∞) σ_{{pred="walking"}}(M2))', name="e"
    )
    assert model["delta_map"]["0"]["delta"] is None


def test_operator_unicode_strictness_aliases():
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) Bef(ζ:≤, η:≥; ρ:3) '
        f'σ_{{pred="walking"}}(M2))',
        name="e",
    )
    assert model["delta_map"]["0"]["zeta"] == "<="
    assert model["delta_map"]["0"]["eta"] == ">="


def test_error_selection_without_pred():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P1} (σ_{{arg1="person"}}(M1))', name="e")


def test_error_selection_references_other_interval():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P2} (σ_{{pred="running" ∧ M2.arg1="x"}}(M1))', name="e")


def test_error_or_branch_without_pred():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P1} (σ_{{pred="running" ∨ arg1="x"}}(M1))', name="e")


def test_error_invalid_operator_parameter():
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{pred="running"}}(M1) Bef(foo:1) σ_{{pred="walking"}}(M2))',
            name="e",
        )


def test_error_invalid_delta_value():
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{pred="running"}}(M1) Bef(δ:k; ρ:f) σ_{{pred="walking"}}(M2))',
            name="e",
        )


def test_error_named_delta_key_rejected():
    # Named per-detect keys are backend-only and must not appear in ISEQL text.
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{pred="running"}}(M1) Bef(δ:delta_visual_handoff) '
            f'σ_{{pred="walking"}}(M2))',
            name="e",
        )
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{pred="running"}}(M1) DJ(δ:5, ε:epsilon_audio_handoff) '
            f'σ_{{pred="walking"}}(M2))',
            name="e",
        )
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{pred="running"}}(M1) Bef(δ:5; ρ:rho_visual_handoff) '
            f'σ_{{pred="walking"}}(M2))',
            name="e",
        )


def test_operator_unbounded_and_number_accepted():
    model = parse_iseql(
        f'{_P2} (σ_{{pred="running"}}(M1) Bef(δ:∞; ρ:3) σ_{{pred="walking"}}(M2))',
        name="e",
    )
    assert model["delta_map"]["0"]["delta"] is None
    assert model["delta_map"]["0"]["rho"] == 3


def test_error_invalid_cross_condition():
    with pytest.raises(IseqlParseError):
        parse_iseql(
            f'{_P2} (σ_{{M1.arg1 ~ M2.arg1}} '
            f'(σ_{{pred="running"}}(M1) SP σ_{{pred="walking"}}(M2)))',
            name="e",
        )


def test_error_duration_infinite_bound():
    with pytest.raises(IseqlParseError):
        parse_iseql(f'{_P1} (σ_{{(M1.et − M1.st) ≥ ∞}} (σ_{{pred="running"}}(M1)))', name="e")
