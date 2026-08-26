from __future__ import annotations

import json
import re
import sqlite3
from typing import Callable, Iterator

import pandas as pd

from utils.api_logger import get_logger
from service.events_service import EventsService, EventSpec

log = get_logger(__name__)

VALID_CONDITIONS = ("A", "B", "C")

_STRICTNESS_OPERATORS = {"<=", "<", ">=", ">"}


def _is_strictness_key(key: str) -> bool:
    return key.startswith("zeta_") or key.startswith("eta_")


def derive_delta_fields(model_json: str | dict) -> dict[str, str]:
    """Derive the EventSpec delta-parameter fields from a model's delta_map.

    The operator editor names the per-detect keys (e.g. ``delta_visual_handoff``,
    ``zeta_audio_fight``); their prefix decides which EventSpec field they belong
    to. Returns {field_name: key}.
    """
    import json as _json
    if isinstance(model_json, str):
        try:
            model = _json.loads(model_json)
        except _json.JSONDecodeError:
            return {}
    elif isinstance(model_json, dict):
        model = model_json
    else:
        return {}
    fields: dict[str, str] = {}
    prefixes = [
        ("delta_visual_", "delta_visual"), ("delta_audio_", "delta_audio"),
        ("epsilon_visual_", "epsilon_visual"), ("epsilon_audio_", "epsilon_audio"),
        ("eta_visual_", "eta_visual"), ("eta_audio_", "eta_audio"),
        ("zeta_visual_", "zeta_visual"), ("zeta_audio_", "zeta_audio"),
        ("rho_visual_", "rho_visual"), ("rho_audio_", "rho_audio"),
    ]
    for entry in (model.get("delta_map", {}) or {}).values():
        if not isinstance(entry, dict):
            continue
        for value in entry.values():
            if not isinstance(value, str):
                continue
            for prefix, field in prefixes:
                if value.startswith(prefix):
                    fields[field] = value
    return fields


_PREFIX_KIND = {
    "delta_visual_": "delta", "delta_audio_": "delta",
    "epsilon_visual_": "epsilon", "epsilon_audio_": "epsilon",
    "eta_visual_": "eta", "eta_audio_": "eta",
    "zeta_visual_": "zeta", "zeta_audio_": "zeta",
    "rho_visual_": "rho", "rho_audio_": "rho",
}
_PREFIX_MODALITY = {
    "delta_visual_": "visual", "delta_audio_": "audio",
    "epsilon_visual_": "visual", "epsilon_audio_": "audio",
    "eta_visual_": "visual", "eta_audio_": "audio",
    "zeta_visual_": "visual", "zeta_audio_": "audio",
    "rho_visual_": "visual", "rho_audio_": "audio",
}
# Named-key -> (kind, modality) so a generated delta name is stable per event.
_PREFIX_LOOKUP = {p: (_PREFIX_KIND[p], _PREFIX_MODALITY[p]) for p in _PREFIX_KIND}


def default_deltas_for(model_json: str | dict, event_id: str,
                       fields: dict[str, str] | None = None) -> dict[str, object]:
    """Per-event default delta literals derived from the AUTHORED ISEQL text.

    Returns ``{ delta_name: literal }`` for every operator parameter the event's
    authored ISEQL uses. ``delta_name`` is the event's named delta key (e.g.
    ``delta_visual_handoff``) for named parameters, otherwise a generated
    ``<event>_<modality>_<kind>`` name. ``delta``/``epsilon`` unbounded defaults
    are ``inf``; unknown params fall back to the general default (delta/epsilon
    -> ``inf``, zeta/eta -> ``<=``, rho -> ``0``). ``fields`` is the event's
    delta-parameter field map ({field_name: named_key}) so column-driven named
    keys are always present. This is the single ISEQL-sourced default for the
    frontend delta editor (no hardcoded variables).
    """
    import json as _json
    if isinstance(model_json, str):
        try:
            model = _json.loads(model_json)
        except _json.JSONDecodeError:
            return {}
    elif isinstance(model_json, dict):
        model = model_json
    else:
        return {}

    def _literal(value):
        if value is None or value == "inf":
            return "inf"
        return value

    # Stored model delta_map carries the NAMED keys (e.g. `delta_audio_fight`);
    # the authored ISEQL text (parsed) carries the LITERAL defaults. Pair them
    # by operator-pair key ("0", "left.0", "right.0", ...) so each named key maps
    # to its authored literal default.
    named_dm = (model.get("delta_map") or {}) if isinstance(model, dict) else {}
    parsed_dm: dict = {}
    text = model.get("iseql_text") if isinstance(model, dict) else None
    if text:
        try:
            from iseql.parser import parse_iseql
            parsed_model = parse_iseql(text, event_id)
            parsed_dm = parsed_model.get("delta_map") or {}
        except Exception:
            parsed_dm = {}

    def _entry(dm, key):
        e = dm.get(key)
        return e if isinstance(e, dict) else {}

    def _kind_of(value):
        if isinstance(value, str):
            for prefix, (kind, _mod) in _PREFIX_LOOKUP.items():
                if value.startswith(prefix):
                    return kind
        return None

    defaults: dict[str, object] = {}
    # union of operator-pair keys across both maps (align by key)
    for key in sorted(set(named_dm) | set(parsed_dm)):
        ne = _entry(named_dm, key)
        pe = _entry(parsed_dm, key)
        for kind, named_value in ne.items():
            lit = _literal(pe.get(kind))
            if isinstance(named_value, str):
                matched = None
                for prefix, (k2, _m2) in _PREFIX_LOOKUP.items():
                    if named_value.startswith(prefix):
                        matched = (k2, named_value)
                        break
                if matched:
                    # named key present -> use its authored literal
                    defaults[named_value] = lit
                    continue
            # no named key for this param -> keep the authored literal under a
            # generated name (e.g. a literal `5` delta authored in the ISEQL).
            g = _kind_of(named_value) if isinstance(named_value, str) else kind
            gkey = f"{event_id}_{g or kind}"
            defaults[gkey] = lit

    # Ensure every EventSpec delta column's named key is present (these are the
    # keys `required_deltas` expects). Assign the general default by field kind
    # when the authored ISEQL carries no matching literal.
    _FIELD_KIND = {
        "delta_visual": "delta", "delta_audio": "delta",
        "epsilon_visual": "epsilon", "epsilon_audio": "epsilon",
        "eta_visual": "eta", "eta_audio": "eta",
        "zeta_visual": "zeta", "zeta_audio": "zeta",
        "rho_visual": "rho", "rho_audio": "rho",
    }
    _KIND_LITERAL = {"delta": "inf", "epsilon": "inf", "zeta": "<=", "eta": "<=", "rho": 0}
    for field, named_key in (fields or {}).items():
        kind = _FIELD_KIND.get(field, "delta")
        defaults.setdefault(named_key, _KIND_LITERAL.get(kind, "inf"))
    return defaults


def _require_strictness(key: str, value: str) -> str:
    """Validate a zeta/eta strictness operator; returns it unchanged."""
    if value not in _STRICTNESS_OPERATORS:
        raise ValueError(
            f"invalid strictness operator '{value}' for '{key}'; "
            f"expected one of {sorted(_STRICTNESS_OPERATORS)}"
        )
    return value


def _required_for(condition: str, conn: sqlite3.Connection) -> set[str]:
    """Delta-parameter names required by the enabled events of a condition.

    Events are user-defined in the DB registry; there are no hardcoded defaults.
    """
    if conn is None:
        raise ValueError("delta resolution requires a database connection")
    from service.impl.event_registry_service_impl import EventRegistryServiceImpl
    return EventRegistryServiceImpl().required_deltas(conn, condition)


def _require_deltas(condition: str, deltas: dict, conn: sqlite3.Connection) -> None:
    missing = _required_for(condition, conn) - set(deltas)
    if missing:
        raise ValueError(
            f"missing required delta parameter(s) for condition {condition}: "
            + ", ".join(sorted(missing))
        )


def _resolve_deltas(
    condition: str, deltas: dict, conn: sqlite3.Connection
) -> dict[str, int | str | None]:
    _require_deltas(condition, deltas, conn)
    resolved: dict[str, int | str | None] = {}
    for key in _required_for(condition, conn):
        value = deltas[key]
        if _is_strictness_key(key):
            resolved[key] = _require_strictness(key, value)
        elif value in ("inf", "∞"):
            resolved[key] = None
        else:
            resolved[key] = int(value)
    return resolved


def _compile_event_sql(
    spec: EventSpec, d: dict, condition: str, analysis_id: str, fps: int = 1,
    audio_predicates: set[str] | None = None,
) -> str | None:
    """Compile one event to SQL from its user-defined ISEQL builder model
    (compile-at-detect). Events without a model cannot be compiled."""
    if not spec.model_json:
        return None
    from iseql.facade import compile_event
    _, sql = compile_event(spec.model_json, d, analysis_id, fps=fps,
                           audio_predicates=audio_predicates)
    return sql


def _result_column_labels(model: dict) -> list[str] | None:
    """Ordered result column labels for an event model's projection.

    Mirrors the projection SELECT order so duplicate ``argN`` columns can be
    renamed to class-based labels (``M1.person``-style, SQLite-safe as
    ``M1_person``) without aliasing the emitted SQL. ``sf``/``ef`` become
    ``M1.sf``/``M1.ef`` (frames). Returns ``None`` when the projection can't be
    resolved (fall back to the raw DataFrame columns).
    """
    from iseql.compiler import _interval_arg_class, _translate_field

    ivs = model.get("intervals", [])
    if not ivs:
        return None
    if any(iv.get("set_side") for iv in ivs):
        fields = model.get("left_projection")
    else:
        fields = model.get("custom_projection")
    if not fields:
        return None

    iv_by_alias: dict[str, dict] = {}
    for i, iv in enumerate(ivs):
        iv_by_alias[f"M{i + 1}"] = iv

    labels: list[str] = []
    counts: dict[tuple[str, str], int] = {}
    for f in fields:
        parts = f.split(".")
        if len(parts) == 2 and parts[0].startswith("M"):
            attr = parts[1]
            iv = iv_by_alias.get(parts[0])
            if attr in ("sf", "ef"):
                labels.append(f"{parts[0]}.{attr}")
                continue
            m = re.match(r"^arg(\d+)$", attr)
            if m and iv is not None:
                cls = _interval_arg_class(iv, int(m.group(1)))
                key = (parts[0], cls)
                counts[key] = counts.get(key, 0) + 1
                n = counts[key]
                suffix = "" if n == 1 else str(n)
                labels.append(f"{parts[0]}_{cls}{suffix}")
                continue
            labels.append(_translate_field(f))
            continue
        labels.append(_translate_field(f))
    return labels


def _rename_result_columns(df, model: dict):
    """Rename duplicate/ambiguous query result columns to class labels."""
    labels = _result_column_labels(model)
    if labels is None:
        return df
    if len(labels) == len(df.columns):
        df = df.copy()
        df.columns = labels
    return df


def _events_from_db(conn: sqlite3.Connection, condition: str) -> list[EventSpec]:
    from service.impl.event_registry_service_impl import EventRegistryServiceImpl
    return EventRegistryServiceImpl().list_events(conn, condition=condition)


def _resolve_audio_predicates(conn: sqlite3.Connection) -> set[str]:
    """Predicates read from AudioPerInterval = the configured audio classes."""
    from service.impl.config_store_service_impl import ConfigStoreServiceImpl
    section = ConfigStoreServiceImpl().get_section(conn, "audio_taxonomy") or {}
    classes = section.get("classes") or []
    return set(str(c) for c in classes)


# ---------------------------------------------------------------------------
# Condition C = multimodal events authored in the registry like A and B.
# ---------------------------------------------------------------------------

def queries_for_condition(
    condition: str, deltas: dict, analysis_id: str,
    conn: sqlite3.Connection | None = None, fps: int = 1,
) -> dict[str, str]:
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"unknown condition '{condition}'; expected A | B | C")
    close = False
    if conn is None:
        from service.impl.event_registry_service_impl import _registry_conn
        conn = _registry_conn()
        close = True
    try:
        d = _resolve_deltas(condition, deltas, conn)
        audio_predicates = _resolve_audio_predicates(conn)
        queries: dict[str, str] = {}
        for e in _events_from_db(conn, condition):
            sql = _compile_event_sql(e, d, condition, analysis_id, fps=fps,
                                     audio_predicates=audio_predicates)
            if sql:
                queries[e.id] = sql
        return queries
    finally:
        if close:
            conn.close()


def events_for_condition(
    condition: str, conn: sqlite3.Connection | None = None
) -> list[EventSpec]:
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"unknown condition '{condition}'; expected A | B | C")
    close = False
    if conn is None:
        from service.impl.event_registry_service_impl import _registry_conn
        conn = _registry_conn()
        close = True
    try:
        return _events_from_db(conn, condition)
    finally:
        if close:
            conn.close()


def run_sql_detection(
    conn,
    event_type: str,
    deltas: dict,
    analysis_id: str,
    condition: str = "A",
    log: Callable[[str], None] = log.info,
    fps: int = 1,
) -> Iterator[str]:
    queries = queries_for_condition(condition, deltas, analysis_id, conn=conn, fps=fps)
    if event_type not in queries:
        yield f"ERROR: unknown event type '{event_type}' for condition {condition}"
        return
    sql = queries[event_type]
    log(f"Running SQL detection for '{event_type}' (condition {condition}) with deltas {deltas}")
    try:
        df = pd.read_sql_query(sql, conn)
        log(f"--- {len(df)} results ---")
        if df.empty:
            yield "No events of this type were detected."
        else:
            model = None
            for e in _events_from_db(conn, condition):
                if e.id == event_type and e.model_json:
                    try:
                        model = json.loads(e.model_json)
                    except Exception:
                        model = None
                    break
            if model is not None:
                df = _rename_result_columns(df, model)
            yield f"__RESULT__:{df.to_json(orient='records')}"
    except Exception as e:
        yield f"ERROR executing query: {e}"


def register_events(conn: sqlite3.Connection, models: list[dict]) -> int:
    """Upsert user-defined event definitions into the registry.

    Used by the experiment harness / notebooks to define events as data. Each
    ``model`` is: {"id", "condition", "model_json", and optional
    delta/eta/zeta/rho keys}.
    """
    from service.impl.event_registry_service_impl import EventRegistryServiceImpl
    reg = EventRegistryServiceImpl()
    count = 0
    for m in models:
        spec = _spec_from_model(m)
        existing = reg.get_event(conn, spec.id, spec.condition)
        if existing is None:
            reg.create_event(conn, spec)
        else:
            reg.update_event(conn, spec.id, spec.condition, {"model_json": spec.model_json})
        count += 1
    return count


def _spec_from_model(m: dict) -> EventSpec:
    import json as _json
    missing = [k for k in ("id", "condition", "model_json") if k not in m]
    if missing:
        raise ValueError(f"event model missing field(s): {', '.join(missing)}")
    model = m["model_json"]
    if isinstance(model, (dict, list)):
        model = _json.dumps(model)
    return EventSpec(
        id=m["id"],
        condition=m["condition"],
        model_json=model,
    )


class EventsServiceImpl(EventsService):
    def queries_for_condition(self, condition: str, deltas: dict, analysis_id: str,
                              fps: int = 1) -> dict[str, str]:
        return queries_for_condition(condition, deltas, analysis_id, fps=fps)

    def events_for_condition(self, condition: str) -> list[EventSpec]:
        return events_for_condition(condition)

    def run_sql_detection(
        self,
        conn,
        event_type: str,
        deltas: dict,
        analysis_id: str,
        condition: str = "A",
        log: Callable[[str], None] = None,
        fps: int = 1,
    ) -> Iterator[str]:
        return run_sql_detection(conn, event_type, deltas, analysis_id, condition, log or log.info, fps)
