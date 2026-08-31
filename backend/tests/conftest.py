"""Shared pytest fixtures for the ISEQL engine tests.

The facade (``compile_query`` / ``compile_model`` / ``vocabulary``) reads the
``relation_vocab`` and ``audio_taxonomy`` sections from a SQLite ``AppConfig``
table.  We stub an in-memory/temp config DB and monkeypatch ``_config_conn`` so
the tests run without the full application stack (torch, VLM providers, ...).
"""
from __future__ import annotations

import sqlite3

import pytest

import iseql.facade as facade

_RELATION_VOCAB = {
    "relation_classids": [
        ["running", "(PersonID)"],
        ["enter_or_exit_vehicle", "(PersonID, VehicleID)"],
        ["walking", "(PersonID)"],
        ["carrying", "(PersonID, ObjectID)"],
        ["explosion_visible", "(VehicleID∨ObjectID)"],
    ]
}

_AUDIO_TAXONOMY = {"classes": ["gunshot", "tire_squeal"]}


@pytest.fixture
def config_db(tmp_path, monkeypatch):
    """Provide a temp AppConfig DB and patch ``facade._config_conn`` to use it."""
    import json

    db_path = tmp_path / "config.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE AppConfig (key TEXT PRIMARY KEY, value_json TEXT, updated_at TEXT)"
    )
    conn.execute(
        "INSERT INTO AppConfig (key, value_json, updated_at) VALUES "
        "('relation_vocab', ?, datetime('now'))",
        (json.dumps(_RELATION_VOCAB),),
    )
    conn.execute(
        "INSERT INTO AppConfig (key, value_json, updated_at) VALUES "
        "('audio_taxonomy', ?, datetime('now'))",
        (json.dumps(_AUDIO_TAXONOMY),),
    )
    conn.commit()
    conn.close()

    def fake_conn() -> sqlite3.Connection:
        c = sqlite3.connect(str(db_path))
        c.row_factory = sqlite3.Row
        return c

    monkeypatch.setattr(facade, "_config_conn", fake_conn)
    return db_path


@pytest.fixture
def audio_predicates() -> set[str]:
    return {"gunshot", "tire_squeal"}
