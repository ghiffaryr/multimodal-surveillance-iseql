"""Comprehensive error cases for user-authored ISEQL query text.

Covers the parser (syntax) errors and the semantic validation the compiler
performs against the configured predicate vocabulary, asserting both that the
error is raised and that the message is actionable.
"""
from __future__ import annotations

import pytest

import iseql.facade as facade

pytestmark = pytest.mark.usefixtures("config_db")

# Valid single-/two-interval query templates.
P0 = 'π_{M1.sf, M1.ef}'
P1 = 'π_{M1.arg1, M1.sf, M1.ef}'
P2 = 'π_{M1.arg1, M2.arg1, M1.sf, M2.ef}'


def compile_q(query: str):
    return facade.compile_query(query, name="e")


# ---------------------------------------------------------------------------
# parser (syntax) errors
# ---------------------------------------------------------------------------

def test_syntax_unterminated_paren():
    with pytest.raises(Exception, match="expected"):
        compile_q(f'{P1} (σ_{{pred="running" ∧ arg1="person"}}(M1)')


def test_syntax_unterminated_brace():
    with pytest.raises(Exception):
        compile_q(f'{P1} (σ_{{pred="running" ∧ arg1="person"(M1))')


def test_syntax_trailing_content():
    with pytest.raises(Exception, match="found 'g'"):
        compile_q(f'{P1} (σ_{{pred="running" ∧ arg1="person"}}(M1)) gibberish')


def test_syntax_unknown_operator():
    with pytest.raises(Exception, match="operator"):
        compile_q(
            f'{P2} (σ_{{pred="running" ∧ arg1="person"}}(M1) XYZ '
            f'σ_{{pred="walking" ∧ arg1="person"}}(M2))'
        )


def test_syntax_unknown_parameter():
    with pytest.raises(Exception, match="operator parameter"):
        compile_q(
            f'{P2} (σ_{{pred="running" ∧ arg1="person"}}(M1) Bef(foo:1) '
            f'σ_{{pred="walking" ∧ arg1="person"}}(M2))'
        )


def test_syntax_bad_delta_unit():
    with pytest.raises(Exception):
        facade.compile_query(f'{P1} (σ_{{pred="running" ∧ arg1="person"}}(M1))',
                             name="e", delta_unit="minutes")


def test_syntax_selection_without_pred():
    with pytest.raises(Exception, match="pred"):
        compile_q(f'{P1} (σ_{{arg1="person"}}(M1))')


def test_syntax_selection_references_other_interval():
    with pytest.raises(Exception, match="references other intervals"):
        compile_q(f'{P2} (σ_{{pred="running" ∧ M2.arg1="x"}}(M1))')


def test_syntax_or_branch_without_pred():
    with pytest.raises(Exception, match="pred"):
        compile_q(f'{P1} (σ_{{pred="running" ∨ arg1="x"}}(M1))')


def test_syntax_invalid_cross_condition():
    with pytest.raises(Exception, match="cross-condition"):
        compile_q(
            f'{P2} (σ_{{M1.arg1 ~ M2.arg1}} '
            f'(σ_{{pred="running" ∧ arg1="person"}}(M1) SP '
            f'σ_{{pred="walking" ∧ arg1="person"}}(M2)))'
        )


def test_syntax_duration_infinite_bound():
    with pytest.raises(Exception, match="finite"):
        compile_q(f'{P1} (σ_{{(M1.et − M1.st) ≥ ∞}} (σ_{{pred="running" ∧ arg1="person"}}(M1)))')


# ---------------------------------------------------------------------------
# operator threshold value errors (named keys are backend-only)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op_params", [
    "Bef(δ:k)", "Bef(ρ:f)", "DJ(δ:5, ε:epsilon_audio_handoff)",
    "Bef(δ:delta_visual_handoff)", "Bef(δ:5; ρ:rho_visual_handoff)",
    "Bef(δ:delta_audio_fight)",
])
def test_operator_rejects_named_keys(op_params):
    with pytest.raises(Exception, match="number or ∞"):
        compile_q(
            f'{P2} (σ_{{pred="running" ∧ arg1="person"}}(M1) {op_params} '
            f'σ_{{pred="walking" ∧ arg1="person"}}(M2))'
        )


def test_operator_rejects_invalid_strictness():
    with pytest.raises(Exception):
        compile_q(
            f'{P2} (σ_{{pred="running" ∧ arg1="person"}}(M1) Bef(ζ:foo) '
            f'σ_{{pred="walking" ∧ arg1="person"}}(M2))'
        )


# ---------------------------------------------------------------------------
# predicate vocabulary validation
# ---------------------------------------------------------------------------

def test_undefined_predicate():
    with pytest.raises(Exception, match="not defined"):
        compile_q(f'{P1} (σ_{{pred="foobar"}}(M1))')


def test_missing_args():
    with pytest.raises(Exception, match="expects 1 argument"):
        compile_q(f'{P1} (σ_{{pred="running"}}(M1))')


def test_too_many_args():
    with pytest.raises(Exception, match="expects 1 argument"):
        compile_q(f'{P1} (σ_{{pred="running" ∧ arg1="person" ∧ arg2="vehicle"}}(M1))')


def test_wrong_arg_class():
    with pytest.raises(Exception, match="arg1='vehicle' is invalid"):
        compile_q(f'{P1} (σ_{{pred="running" ∧ arg1="vehicle"}}(M1))')


def test_alternatives_arg_valid():
    # explosion_visible accepts arg1 in {vehicle, object}
    res = compile_q(f'{P1} (σ_{{pred="explosion_visible" ∧ arg1="vehicle"}}(M1))')
    assert "explosion_visible" in res["sql"]
    res = compile_q(f'{P1} (σ_{{pred="explosion_visible" ∧ arg1="object"}}(M1))')
    assert "explosion_visible" in res["sql"]


def test_alternatives_arg_invalid_class():
    with pytest.raises(Exception, match="arg1='person' is invalid"):
        compile_q(f'{P1} (σ_{{pred="explosion_visible" ∧ arg1="person"}}(M1))')


def test_audio_predicate_rejects_args():
    with pytest.raises(Exception, match="expects 0 argument"):
        compile_q(f'{P1} (σ_{{pred="gunshot" ∧ arg1="person"}}(M1))')


def test_visual_event_rejects_audio_predicate():
    with pytest.raises(Exception, match="audio predicate"):
        facade.compile_query(
            f'{P0} (σ_{{pred="gunshot"}}(M1))', name="e", condition="A"
        )


def test_audio_event_rejects_visual_predicate():
    with pytest.raises(Exception, match="visual predicate"):
        facade.compile_query(
            f'{P0} (σ_{{pred="running" ∧ arg1="person"}}(M1))', name="e", condition="B"
        )


def test_condition_allows_matching_modality():
    assert "running" in facade.compile_query(
        f'{P1} (σ_{{pred="running" ∧ arg1="person"}}(M1))', name="e", condition="A"
    )["sql"]
    assert "gunshot" in facade.compile_query(
        f'{P0} (σ_{{pred="gunshot"}}(M1))', name="e", condition="B"
    )["sql"]


def test_mixed_audio_visual_in_one_interval():
    with pytest.raises(Exception, match="mixes audio and visual"):
        compile_q(
            f'{P1} (σ_{{pred="running" ∧ pred="gunshot" ∧ arg1="person"}}(M1))'
        )


# ---------------------------------------------------------------------------
# projection validation
# ---------------------------------------------------------------------------

def test_projection_arg_out_of_range():
    with pytest.raises(Exception, match="has no arg2"):
        compile_q(f'π_{{M1.arg2, M1.sf}} (σ_{{pred="running" ∧ arg1="person"}}(M1))')


def test_projection_unknown_interval():
    with pytest.raises(Exception, match="does not exist"):
        compile_q(f'π_{{M2.arg1}} (σ_{{pred="running" ∧ arg1="person"}}(M1))')


def test_projection_unknown_attribute():
    with pytest.raises(Exception, match="unknown attribute"):
        compile_q(f'π_{{M1.arg1, M1.sss}} (σ_{{pred="running" ∧ arg1="person"}}(M1))')


def test_projection_valid_temporal_attributes():
    res = compile_q(f'π_{{M1.arg1, M1.st, M1.et}} (σ_{{pred="running" ∧ arg1="person"}}(M1))')
    assert "running" in res["sql"]


# ---------------------------------------------------------------------------
# cross-condition validation
# ---------------------------------------------------------------------------

def test_cross_condition_arg_out_of_range():
    with pytest.raises(Exception, match="has no arg2"):
        compile_q(
            'π_{M1.arg1, M2.arg1, M1.sf, M2.ef} '
            '(σ_{M1.arg1≠M2.arg1 ∧ M1.arg2=M2.arg1} '
            '(σ_{pred="running" ∧ arg1="person"}(M1) SP '
            'σ_{pred="walking" ∧ arg1="person"}(M2)))'
        )


def test_cross_condition_unknown_attribute():
    with pytest.raises(Exception, match="unknown attribute"):
        compile_q(
            'π_{M1.arg1, M2.arg1, M1.sf, M2.ef} '
            '(σ_{M1.arg1≠M2.sss} '
            '(σ_{pred="running" ∧ arg1="person"}(M1) SP '
            'σ_{pred="walking" ∧ arg1="person"}(M2)))'
        )


def test_cross_condition_valid():
    res = compile_q(
        'π_{M1.arg1, M2.arg1, M1.sf, M2.ef} '
        '(σ_{M1.arg1≠M2.arg1} '
        '(σ_{pred="running" ∧ arg1="person"}(M1) SP '
        'σ_{pred="walking" ∧ arg1="person"}(M2)))'
    )
    assert "M1.arg1" in res["sql"]


# ---------------------------------------------------------------------------
# structural validation
# ---------------------------------------------------------------------------

def test_empty_query():
    with pytest.raises(Exception):
        facade.compile_query("   ", name="e")
