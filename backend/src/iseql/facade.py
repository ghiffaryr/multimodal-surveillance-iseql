"""ISEQL compiler facade used by the service/API layers.

The actual compiler (``iseql.compiler``), parser (``iseql.parser``) and SQL
operators (``iseql.helpers``) live in the ``iseql`` domain package. This module
is the thin entry point the controllers and the detection path call.
"""
from __future__ import annotations


def _resolve_audio_predicates(conn) -> set[str]:
    """Predicates that read from AudioPerInterval = the configured audio classes."""
    from service.impl.config_store_service_impl import ConfigStoreServiceImpl
    section = ConfigStoreServiceImpl().get_section(conn, "audio_taxonomy") or {}
    classes = section.get("classes") or []
    return set(str(c) for c in classes)


def _config_conn():
    from service.impl.config_store_service_impl import _config_conn as _conn
    return _conn()


def compile_event(model_json: str | dict, deltas: dict, analysis_id: str,
                  fps: int | str = 1, audio_predicates: set[str] | None = None
                  ) -> tuple[str, str]:
    """Compile a model to (iseql_text, sql); ``fps`` converts δ/ε seconds->frames.

    ``audio_predicates`` (predicates read from AudioPerInterval) is required;
    callers resolve it from the audio taxonomy.
    """
    from iseql.compiler import compile_event as _compile
    return _compile(model_json, deltas, analysis_id, fps=fps,
                    audio_predicates=audio_predicates)


def validate_model(model_json: str | dict) -> dict:
    from iseql.compiler import validate_model as _validate
    return _validate(model_json)


def render_model(model_json: str | dict) -> str:
    """Render a model to ISEQL text (editor prefill for events without stored text)."""
    from iseql.compiler import _load_model, _normalized_model, render_iseql
    return render_iseql(_normalized_model(_load_model(model_json)))


def compile_query(query: str, name: str = "event", delta_unit: str = "seconds") -> dict:
    """Compile an ISEQL query written as text into (iseql, sql, model).

    Raises ValueError with a human-readable message on syntax/compile errors.
    ``delta_unit`` is the unit of the authored δ/ε thresholds (seconds/frames).
    Named δ/ε keys resolve per-detect; for the preview they are treated as
    unbounded (None) since no detection deltas are available.
    """
    from iseql.parser import parse_iseql
    from iseql.compiler import compile_event as _compile
    model = parse_iseql(query, name=name, delta_unit=delta_unit)
    _STRICTNESS = {"<=", "<", ">=", ">", "≤", "≥", "⩽", "⩾"}
    named = {
        v
        for entry in (model.get("delta_map") or {}).values()
        if isinstance(entry, dict)
        for v in entry.values()
        # Named δ/ε/ρ keys resolve per-detect; strictness strings are literal.
        if isinstance(v, str) and v not in _STRICTNESS
    }
    preview_deltas = {k: None for k in named}
    conn = _config_conn()
    try:
        audio_predicates = _resolve_audio_predicates(conn)
    finally:
        conn.close()
    iseql, sql = _compile(model, preview_deltas, "__analysis__", fps="__fps__",
                          audio_predicates=audio_predicates)
    from iseql.compiler import render_iseql, _normalized_model
    rendered = render_iseql(_normalized_model(model))
    return {"iseql": rendered, "sql": sql, "model": model}
