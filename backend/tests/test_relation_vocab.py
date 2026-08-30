"""Tests for the generic args <-> ClassID conversion helpers.

These are the user-facing representation used by the events-configuration UI
(comma-separated ``args``) vs. the stored ISEQL prompt form (``(PersonID, ...)``).
"""
from __future__ import annotations

import pytest

from service.relation_vocab import (
    args_to_classid,
    classid_to_args,
    signature_classes,
)


def test_args_to_classid_simple():
    assert args_to_classid("person") == "(PersonID)"
    assert args_to_classid("person, vehicle") == "(PersonID, VehicleID)"


def test_args_to_classid_optional():
    assert args_to_classid("vehicle?") == "(VehicleID?)"
    assert args_to_classid("vehicle?, object?") == "(VehicleID?, ObjectID?)"


def test_args_to_classid_empty_and_whitespace():
    assert args_to_classid("") == ""
    assert args_to_classid("  ") == ""
    assert args_to_classid("person,  , vehicle") == "(PersonID, VehicleID)"


def test_classid_to_args_simple():
    assert classid_to_args("(PersonID)") == "person"
    assert classid_to_args("(PersonID, VehicleID)") == "person, vehicle"


def test_classid_to_args_optional():
    assert classid_to_args("(VehicleID?)") == "vehicle?"
    assert classid_to_args("(VehicleID?, ObjectID?)") == "vehicle?, object?"


def test_classid_to_args_multi_arg_token():
    # 'PersonID1' (multi-arg) still resolves to 'person'
    assert classid_to_args("(PersonID1, VehicleID2)") == "person, vehicle"


def test_classid_to_args_without_parens():
    assert classid_to_args("PersonID, VehicleID") == "person, vehicle"


def test_roundtrip_identity():
    for args in ["person", "person, vehicle", "vehicle?", "person, object?",
                 "vehicle?, object?", "item"]:
        assert classid_to_args(args_to_classid(args)) == args


def test_signature_classes():
    assert signature_classes("(PersonID, VehicleID?)") == ["person", "vehicle"]
    assert signature_classes("(VehicleID, VehicleID?)") == ["vehicle"]  # de-duplicated


def test_signature_classes_empty():
    assert signature_classes("") == []
    assert signature_classes("()") == []


def test_invalid_optional_only():
    # A lone '?' token produces no class; it should be ignored gracefully.
    assert classid_to_args("(?)") == ""
