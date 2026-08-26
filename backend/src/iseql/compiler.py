"""ISEQL compiler: compiles a Gea-style ISEQL event model into executable SQL.

The model JSON is the same shape the ISEQL-GUI builder consumes (intervals with
predicates, temporal operators between consecutive intervals, cross-conditions,
projections, groups, query-refs, set operations). This emitter maps it onto our
pipeline tables (VisualPerInterval/VisualParticipant/AudioPerInterval) through
the iseql.helpers temporal operators, producing one SQL query per event.

Compilation happens at detection time (compile-at-detect): operator thresholds
are resolved from the per-detect ``deltas`` dict via an optional model
``delta_map``, so the frontend's per-detect delta editing keeps working.

The interval model and temporal-operator detection are app-owned (adapted from
the ISEQL-GUI core); no vendored code is imported. Predicates and participant
classes match stored values literally: variants are written as ``∨`` ORs in the
query itself, and a predicate is treated as audio iff it is in the configured
``audio_predicates`` (from ``audio_taxonomy.classes``).
"""
from __future__ import annotations

import json
import re
from typing import Optional

from iseql.helpers import (
    ALL_PARAMS,
    OPERATOR_HELPERS,
    apply_manual_override,
    detect_operator,
    Interval,
    Predicate,
)
from utils.api_logger import get_logger

log = get_logger(__name__)

_VISUAL_SOURCE = "visual"
_AUDIO_SOURCE = "audio"


class ModelValidationError(ValueError):
    pass


# ---------------------------------------------------------------------------
# model parsing / validation
# ---------------------------------------------------------------------------

def _load_model(model_json: str | dict) -> dict:
    if isinstance(model_json, str):
        try:
            model = json.loads(model_json)
        except json.JSONDecodeError as e:
            raise ModelValidationError(f"invalid model JSON: {e}")
    elif isinstance(model_json, dict):
        model = model_json
    else:
        raise ModelValidationError("model_json must be a dict or JSON string")
    if not isinstance(model, dict):
        raise ModelValidationError("model must be a JSON object")
    return model


def validate_model(model_json: str | dict) -> dict:
    """Validate/normalize a model; raises ModelValidationError on structural errors."""
    model = _load_model(model_json)
    intervals = model.get("intervals")
    if not isinstance(intervals, list) or not intervals:
        raise ModelValidationError("model.intervals must be a non-empty list")
    for i, iv in enumerate(intervals):
        if not isinstance(iv, dict):
            raise ModelValidationError(f"interval[{i}] must be an object")
        pred = iv.get("pred")
        if not isinstance(pred, dict) or not pred.get("name"):
            raise ModelValidationError(f"interval[{i}].pred.name is required")
        for key in ("ts", "te"):
            if key in iv and not isinstance(iv[key], int):
                raise ModelValidationError(f"interval[{i}].{key} must be an integer")
    cc = model.get("cross_conditions", [])
    if not isinstance(cc, list):
        raise ModelValidationError("model.cross_conditions must be a list")
    for c in cc:
        for key in ("left_alias", "left_attr", "op", "right_alias", "right_attr"):
            if not isinstance(c, dict) or key not in c:
                raise ModelValidationError(f"cross-condition missing '{key}': {c}")
    set_operator = model.get("set_operator")
    if set_operator is not None and set_operator not in ("\\", "∪", "∩"):
        raise ModelValidationError(f"unsupported set_operator '{set_operator}'")
    has_set_side = any(iv.get("set_side") for iv in intervals)
    if set_operator and not has_set_side:
        raise ModelValidationError("set_operator present but no interval has set_side")
    return model


def _normalized_model(model: dict) -> dict:
    out = dict(model)
    out.setdefault("cross_conditions", [])
    out.setdefault("operator_overrides", [])
    out.setdefault("group_cross_conditions", {})
    out.setdefault("custom_projection", None)
    out.setdefault("left_projection", None)
    out.setdefault("right_projection", None)
    out.setdefault("set_operator", None)
    out.setdefault("delta_map", {})
    return out


# ---------------------------------------------------------------------------
# predicate -> CTE
# ---------------------------------------------------------------------------

def _predicate_source(pred_name: str, audio_predicates: set[str]) -> str:
    return _AUDIO_SOURCE if pred_name in audio_predicates else _VISUAL_SOURCE


def _selection_source(preds: list[str], audio_predicates: set[str]) -> str:
    """Source table for an interval selection that may name several predicates."""
    audio = [p for p in preds if p in audio_predicates]
    visual = [p for p in preds if p not in audio_predicates]
    if audio and visual:
        raise ModelValidationError(
            f"interval mixes audio and visual predicates: {', '.join(preds)}"
        )
    return _AUDIO_SOURCE if audio else _VISUAL_SOURCE


def _class_filter_multi(alias: str, classes: list[str]) -> str:
    """Participant class condition: the arg labels match stored Class values literally."""
    values = list(dict.fromkeys(classes))
    if len(values) == 1:
        return f"{alias}.Class = '{values[0]}'"
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{alias}.Class IN ({quoted})"


def _relation_values(preds: list[str], source: str) -> str:
    """Predicate condition: pred names match stored RelationType/AudioClass literally."""
    column = "AudioClass" if source == _AUDIO_SOURCE else "RelationType"
    values = list(dict.fromkeys(preds))
    if len(values) == 1:
        return f"{column} = '{values[0]}'"
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def _temporal_selects(prefix: str, temporal: set[str], fps: int | str) -> list[str]:
    """SQL column expressions for the temporal columns a query actually uses.

    ``temporal`` is the set of referenced columns (sf/ef/st/et). Frame columns
    are raw ``StartFrame AS sf`` / ``EndFrame AS ef``; time columns are the
    fps-divided casts ``CAST(StartFrame AS REAL)/{fps} AS st`` etc., where fps
    is only known after video analysis (preview: ``__fps__`` placeholder).
    """
    _fps = fps if isinstance(fps, str) else max(int(fps or 1), 1)
    exprs = {
        "sf": f"{prefix}StartFrame AS sf",
        "ef": f"{prefix}EndFrame AS ef",
        "st": f"CAST({prefix}StartFrame AS REAL)/{_fps} AS st",
        "et": f"CAST({prefix}EndFrame AS REAL)/{_fps} AS et",
    }
    return [exprs[c] for c in ("sf", "ef", "st", "et") if c in temporal]


def _predicate_cte(alias: str, iv: dict, analysis_id: str,
                   audio_predicates: set[str], fps: int | str = 1,
                   temporal: set[str] = ("sf", "ef")) -> str:
    """Render one predicate interval as a CTE.

    The CTE exposes only the temporal columns the query references
    (``temporal``): frame domain ``sf``/``ef`` are raw frame columns, time
    domain ``st``/``et`` are fps-divided (``st = StartFrame/fps``).

    Intervals authored from ISEQL text carry a ``selection`` ({preds, args}, or
    {branches: [{preds, args}...]} for OR selections; each branch keeps its own
    pred + argument combination). Intervals from the model seed / GUI fall back
    to ``pred.name`` + arguments (a single conjunction via join class filters).
    """
    pred = iv["pred"]
    a = f"AND AnalysisID = '{analysis_id}'"
    _fps = fps if isinstance(fps, str) else max(int(fps or 1), 1)
    selection = iv.get("selection")
    if selection:
        branches = selection.get("branches") or [
            {"preds": list(selection.get("preds") or [pred["name"]]),
             "args": {str(k): list(v) for k, v in (selection.get("args") or {}).items()}}
        ]
        all_preds = [p for b in branches for p in (b.get("preds") or [])]
        source = _selection_source(all_preds, audio_predicates)
        slots: set[int] = set()
        for b in branches:
            for k in (b.get("args") or {}):
                slots.add(int(k))
        if source == _AUDIO_SOURCE:
            selects: list[str] = []
            maxarg = max(slots) if slots else 0
            for k in range(1, maxarg + 1):
                selects.append(f"NULL AS arg{k}")
            selects += _temporal_selects("", temporal, fps)
            conds = [_relation_values(b["preds"], source) for b in branches]
            where = "(" + " OR ".join(f"({c})" for c in conds) + ")"
            return (
                f"{alias} AS (\n"
                f"    SELECT {', '.join(selects)}\n"
                f"    FROM AudioPerInterval API\n"
                f"    WHERE {where} AND Confidence >= 0.0 {a}\n"
                f")"
            )
        selects: list[str] = []
        for k in sorted(slots):
            selects.append(f"VP_{k}.ClassID AS arg{k}")
        selects += _temporal_selects("VPI.", temporal, fps)
        joins = [f"JOIN VisualParticipant VP_{k} ON VPI.RelationID = VP_{k}.RelationID"
                 for k in sorted(slots)]
        branch_sqls = []
        for b in branches:
            conds = [_relation_values(b["preds"], source)]
            for k in sorted(slots):
                classes = (b.get("args") or {}).get(str(k))
                if classes:
                    conds.append(_class_filter_multi(f"VP_{k}", classes))
            branch_sqls.append("(" + " AND ".join(conds) + ")")
        where = "(" + " OR ".join(branch_sqls) + ")"
        joins_sql = "\n".join("    " + j for j in joins)
        return (
            f"{alias} AS (\n"
            f"    SELECT {', '.join(selects)}\n"
            f"    FROM VisualPerInterval VPI\n"
            f"{joins_sql}\n"
            f"    WHERE {where} {a}\n"
            f")"
        )

    # Non-selection path (model seed / GUI): a single conjunction expressed via
    # participant-join class filters.
    pred_name = pred["name"]
    source = _predicate_source(pred_name, audio_predicates)
    args = {k: [v] for k, v in enumerate(pred.get("arguments", []), start=1)}

    if source == _AUDIO_SOURCE:
        selects: list[str] = []
        for k in range(1, len(args) + 1):
            selects.append(f"NULL AS arg{k}")
        selects += _temporal_selects("", temporal, fps)
        return (
            f"{alias} AS (\n"
            f"    SELECT {', '.join(selects)}\n"
            f"    FROM AudioPerInterval API\n"
            f"    WHERE {_relation_values([pred_name], source)} AND Confidence >= 0.0 {a}\n"
            f")"
        )

    selects: list[str] = []
    joins = []
    for k in sorted(args):
        j_alias = f"VP_{k}"
        selects.append(f"{j_alias}.ClassID AS arg{k}")
        joins.append(
            f"JOIN VisualParticipant {j_alias} ON VPI.RelationID = {j_alias}.RelationID "
            f"AND {_class_filter_multi(j_alias, args[k])}"
        )
    selects += _temporal_selects("VPI.", temporal, fps)
    joins_sql = "\n".join("    " + j for j in joins)
    return (
        f"{alias} AS (\n"
        f"    SELECT {', '.join(selects)}\n"
        f"    FROM VisualPerInterval VPI\n"
        f"{joins_sql}\n"
        f"    WHERE {_relation_values([pred_name], source)} {a}\n"
        f")"
    )


# ---------------------------------------------------------------------------
# operator resolution
# ---------------------------------------------------------------------------

def _resolve(value, deltas: dict):
    """Resolve a param spec: string keys look up the resolved per-detect value."""
    if isinstance(value, str) and deltas is not None and value in deltas:
        return deltas[value]
    return value


def _operator_kwargs(helper, params: dict) -> dict:
    """Pass only the keyword params the helper actually accepts."""
    import inspect
    sig = inspect.signature(helper)
    return {name: params[name] for name in sig.parameters if name in params}


_OP_TRANSLATION = {"≠": "!=", "≤": "<=", "≥": ">=", "⩽": "<=", "⩾": ">="}


def _alias_inner_fields(fields: list[str]) -> list[str]:
    """Alias inner chain projection fields so a group CTE exposes safe columns
    (M1.arg1 -> M1_arg1). Fields already aliased are left unchanged."""
    out = []
    for f in fields:
        if " AS " in f:
            out.append(f)
        elif "." in f:
            base, col = f.split(".", 1)
            out.append(f"{f} AS {base}_{col}")
        else:
            out.append(f)
    return out


def _proj_col(ref: str, col: str | None, name: str) -> str:
    if col:
        return f"{ref}.{col}_{name}"
    if name in ("sf", "start"):
        return f'{ref}.sf AS "{ref}.sf"'
    if name in ("ef", "end"):
        return f'{ref}.ef AS "{ref}.ef"'
    if name in ("st",):
        return f'{ref}.st AS "{ref}.st"'
    if name in ("et",):
        return f'{ref}.et AS "{ref}.et"'
    return f"{ref}.{name}"


def _attr_col(alias: str, attr: str, alias_map: dict[str, tuple[str, str | None]]) -> str:
    ref, col = alias_map.get(alias, (alias, None))
    if col:
        return f"{ref}.{col}_{attr}"
    if attr in ("sf", "start", "StartFrame"):
        return f"{ref}.sf"
    if attr in ("ef", "end", "EndFrame"):
        return f"{ref}.ef"
    if attr in ("st", "StartTime"):
        return f"{ref}.st"
    if attr in ("et", "EndTime"):
        return f"{ref}.et"
    return f"{ref}.{attr}"


def _cross_condition_sql(c: dict, alias_map: dict[str, tuple[str, str | None]]) -> str:
    if c.get("type") == "duration":
        start = _attr_col(c["right_alias"], c["right_attr"], alias_map)
        end = _attr_col(c["left_alias"], c["left_attr"], alias_map)
        op = _OP_TRANSLATION.get(c["op"], c["op"])
        return f"({end} - {start}) {op} {c['value']}"
    left = _attr_col(c["left_alias"], c["left_attr"], alias_map)
    right = _attr_col(c["right_alias"], c["right_attr"], alias_map)
    op = _OP_TRANSLATION.get(c["op"], c["op"])
    return f"({left} {op} {right})"


def _domain_cols(model: dict) -> tuple[str, str]:
    """Which temporal column domain the event's authored projection uses.

    ``sf``/``ef`` => frame domain (columns ``sf``/``ef``, deltas in frames);
    ``st``/``et`` => time domain (columns ``st``/``et``, deltas in seconds).
    Mixing frame and time attributes is invalid and raises an error.
    """
    fields = (model.get("custom_projection") or
              model.get("left_projection") or
              model.get("right_projection") or [])
    if not fields:
        return ("sf", "ef")
    frame = time_ = False
    for f in fields:
        attr = f.split(".")[-1]
        if attr in ("sf", "ef"):
            frame = True
        elif attr in ("st", "et"):
            time_ = True
    if frame and time_:
        raise ModelValidationError(
            "query mixes frame (sf/ef) and time (st/et) attributes; "
            "use one domain consistently"
        )
    return ("st", "et") if time_ else ("sf", "ef")


def _needed_temporal(model: dict) -> frozenset[str]:
    """The set of temporal columns (sf/ef/st/et) the query actually references.

    Collects from the operator domain (``_domain_cols``), the projection fields,
    the default projection (event extent uses ``sf``/``ef`` when no projection is
    authored), and every cross-condition attribute. Only these columns are
    emitted by the predicate CTEs, so ``__fps__`` casts appear exactly when the
    query operates in the time domain.
    """
    needed = set(_domain_cols(model))
    for key in ("custom_projection", "left_projection", "right_projection"):
        for f in model.get(key) or []:
            needed.update(_projection_temporal_attrs(f))
    if not (model.get("custom_projection") or
            model.get("left_projection") or
            model.get("right_projection")):
        needed.update(("sf", "ef"))
    for c in model.get("cross_conditions") or []:
        needed.update(_condition_temporal_attrs(c))
    for ccs in (model.get("group_cross_conditions") or {}).values():
        for c in ccs or []:
            needed.update(_condition_temporal_attrs(c))
    return frozenset(needed)


def _projection_temporal_attrs(field: str) -> set[str]:
    attr = field.split(".")[-1]
    return {attr} if attr in ("sf", "ef", "st", "et") else set()


def _condition_temporal_attrs(c: dict) -> set[str]:
    return {attr for attr in (c.get("left_attr"), c.get("right_attr"))
            if attr in ("sf", "ef", "st", "et")}


# ---------------------------------------------------------------------------
# projection
# ---------------------------------------------------------------------------

def _interval_arg_class(iv: dict, k: int) -> str:
    """Participant class for arg slot ``k`` of an interval (e.g. 'person')."""
    sel = iv.get("selection")
    if sel:
        args = sel.get("args")
        if args is None and sel.get("branches"):
            vals = []
            for b in sel["branches"]:
                v = (b.get("args") or {}).get(str(k))
                if v:
                    vals.extend(v)
            if vals:
                return str(vals[0])
        elif args:
            vals = args.get(str(k))
            if vals:
                return str(vals[0])
    pred = iv.get("pred") or {}
    arguments = pred.get("arguments") or []
    if 1 <= k <= len(arguments):
        return str(arguments[k - 1])
    return f"arg{k}"


_ALIAS_RE = re.compile(r"^M(\d+)$")


def _alias_index(alias: str) -> int | None:
    m = _ALIAS_RE.match(alias)
    return int(m.group(1)) - 1 if m else None


def _classify_projection_fields(fields: list[str], ivs: list[dict]) -> list[str]:
    """Alias each projected arg field with its participant class.

    ``M1.arg1`` (class person) becomes ``M1.arg1 AS M1_person``. Duplicate
    classes on the same interval get a position suffix (M1_person, M1_person2).
    sf/ef and already-aliased fields are left unchanged.
    """
    counts: dict[tuple[str, str], int] = {}
    out = []
    for f in fields:
        parts = f.split(".")
        if len(parts) == 2 and parts[0].startswith("M"):
            attr = parts[1]
            m = re.match(r"^arg(\d+)$", attr)
            if m:
                i = _alias_index(parts[0])
                if i is not None and i < len(ivs):
                    cls = _interval_arg_class(ivs[i], int(m.group(1)))
                    key = (parts[0], cls)
                    counts[key] = counts.get(key, 0) + 1
                    n = counts[key]
                    suffix = "" if n == 1 else str(n)
                    out.append(f"{f} AS {parts[0]}_{cls}{suffix}")
                    continue
        out.append(f)
    return out


def _translate_field(field: str) -> str:
    """Translate a GUI projection field (M1.arg1, M2.sf, Ref.M1.arg1, ...) to SQL.

    sf/ef map to the CTE frame aliases ``sf``/``ef`` (the projection stays
    ISEQL-consistent: ``M1.sf`` -> ``M1.sf``); argN pass through unchanged.
    """
    return field


def _default_projection(model: dict, ivs: list[dict],
                        alias_map: dict[str, tuple[str, str | None]] = None) -> list[str]:
    # Event extent: first interval's start -> last interval's end (matches the
    # hand-written queries, e.g. F.StartFrame .. S.EndFrame for a 2-chain).
    alias_map = alias_map or {f"M{i + 1}": (f"M{i + 1}", None) for i in range(len(ivs))}
    last_alias = f"M{len(ivs)}"
    fields = [f"{alias_map['M1'][0]}.sf AS StartFrame",
              f"{alias_map[last_alias][0]}.ef AS EndFrame"]
    for i, iv in enumerate(ivs):
        alias = f"M{i + 1}"
        ref, col = alias_map.get(alias, (alias, None))
        if iv.get("query_ref"):
            fields.append(f'{ref}.sf AS "{ref}.sf"')
            fields.append(f'{ref}.ef AS "{ref}.ef"')
            continue
        for k in range(1, len(iv["pred"].get("arguments", [])) + 1):
            fields.append(_proj_col(ref, col, f"arg{k}"))
        fields.append(_proj_col(ref, col, "sf"))
        fields.append(_proj_col(ref, col, "ef"))
    return fields


# ---------------------------------------------------------------------------
# chain rendering (flat + groups + query-ref)
# ---------------------------------------------------------------------------

def _slot_bounds(iv: dict) -> tuple[int, int]:
    return int(iv.get("ts", 0)), int(iv.get("te", 0))


def _slot_span(slot_ivs: list[dict]) -> tuple[int, int]:
    ts = min(_slot_bounds(iv)[0] for iv in slot_ivs)
    te = max(_slot_bounds(iv)[1] for iv in slot_ivs)
    return ts, te


def _slots(ivs: list[dict]) -> list[list[dict]]:
    """Partition intervals into slots: single intervals or contiguous group runs."""
    slots: list[list[dict]] = []
    i = 0
    n = len(ivs)
    while i < n:
        gid = ivs[i].get("group_id")
        if gid:
            j = i
            while j < n and ivs[j].get("group_id") == gid:
                j += 1
            slots.append(ivs[i:j])
            i = j
        else:
            slots.append([ivs[i]])
            i += 1
    return slots


def _delta_entry(model: dict, pair_idx: int, side: str | None = None) -> dict:
    """Resolve a delta_map entry. Set-operation sides may key entries as
    'left.<i>' / 'right.<i>' (falls back to '<i>')."""
    dm = model.get("delta_map", {})
    if side is not None:
        key = f"{side}.{pair_idx}"
        if key in dm:
            return dm[key] or {}
    return dm.get(str(pair_idx), {}) or {}


def _operators_between_slots(model: dict, ivs: list[dict], deltas: dict,
                             slot_bounds: list[tuple[int, int]],
                             slot_indices: list[int],
                             side: str | None = None,
                             fps: int | str = 1) -> list[str]:
    """Operators between consecutive slots, using each slot's span."""
    conds = []
    for k in range(len(slot_bounds) - 1):
        rts, rte = slot_bounds[k]
        sts, ste = slot_bounds[k + 1]
        r = Interval(Predicate("slot", []), rts, rte)
        s = Interval(Predicate("slot", []), sts, ste)
        res = detect_operator(r, s)
        op = res.operator
        # map a slot pair back to the underlying interval pair index for overrides
        pair_idx = slot_indices[k]
        for ov in model.get("operator_overrides", []):
            if ov.get("side") in (None, "none", side) and ov.get("pair_idx") == pair_idx + 1:
                op = ov.get("operator", op)
                if op in ("SP", "EF"):
                    res = apply_manual_override(op, r, s)
        if op == "UNKNOWN":
            raise ModelValidationError(
                f"cannot determine operator between slots {k + 1} and {k + 2}; "
                "add an operator_override"
            )
        helper, param_names = OPERATOR_HELPERS[op]
        cols = _domain_cols(model)
        params: dict[str, object] = {}
        time_domain = (cols == ("st", "et"))
        for p in ("delta", "epsilon"):
            if p in param_names:
                # res.delta/res.epsilon are in FRAME units from the synthesized
                # interval spans; for the time domain convert to seconds.
                val = res.delta if p == "delta" else res.epsilon
                if val is not None and time_domain and isinstance(fps, (int, float)):
                    val = val / fps
                params[p] = val
        params["zeta"] = "<="
        params["eta"] = "<="
        params["rho"] = 0
        entry = _delta_entry(model, pair_idx, side)
        for p in ALL_PARAMS:
            if p in entry:
                raw = entry[p]
                # Authored numeric thresholds are in the domain's own unit
                # (frames for sf/ef, seconds for st/et); named keys resolve
                # per-detect after.
                params[p] = _resolve(raw, deltas)
        a1, a2 = f"M{k + 1}", f"M{k + 2}"
        conds.append(helper(a1, a2, cols=cols, **_operator_kwargs(helper, params)))
    return conds


def _render_chain(model: dict, ivs: list[dict], analysis_id: str, deltas: dict,
                  alias_start: int = 1, side: str | None = None,
                  fps: int | str = 1, audio_predicates: set[str] | None = None
                  ) -> tuple[list[str], list[str], list[str]]:
    """Render a chain of intervals -> (ctes, projection_fields, where_conditions).

    Aliases continue from ``alias_start`` (1-based) so set-op sides don't clash.
    ``side`` prefixes delta_map lookups for set-operation operands.
    """
    slots = _slots(ivs)
    ctes: list[str] = []
    conditions: list[str] = []
    global_index = alias_start - 1
    slot_bounds: list[tuple[int, int]] = []
    slot_indices: list[int] = []
    alias_map: dict[str, tuple[str, str | None]] = {}
    temporal = _needed_temporal(model)

    for slot in slots:
        first = global_index
        if len(slot) == 1 and not slot[0].get("group_id"):
            iv = slot[0]
            alias = f"M{global_index + 1}"
            global_index += 1
            if iv.get("query_ref"):
                ref = _normalized_model(iv["query_ref"])
                ref_name = ref.get("event_name") or alias
                body = _render_flat_body(ref, ref["intervals"], analysis_id, deltas, fps=fps,
                                         audio_predicates=audio_predicates)
                ctes.append(f"{ref_name} AS ({body})")
                alias_map[alias] = (ref_name, None)
                ts, te = _slot_bounds(iv)
                slot_bounds.append((ts, te))
                slot_indices.append(first)
                continue
            ctes.append(_predicate_cte(alias, iv, analysis_id, audio_predicates, fps, temporal))
            alias_map[alias] = (alias, None)
            ts, te = _slot_bounds(iv)
            slot_bounds.append((ts, te))
            slot_indices.append(first)
        else:
            # group: nested subquery over the run; expose inner aliases as safe
            # columns (M1_arg1, M1_sf, ...) on the group CTE.
            run = slot
            gid = run[0].get("group_id")
            group_ivs = [dict(iv, group_id=None) for iv in run]
            inner_ctes, inner_fields, inner_conds = _render_chain(
                model, group_ivs, analysis_id, deltas, alias_start=global_index + 1,
                fps=fps, audio_predicates=audio_predicates)
            body = _build_select(inner_ctes, _alias_inner_fields(inner_fields), inner_conds)
            gccs = model.get("group_cross_conditions", {}).get(gid, [])
            if gccs:
                cc_cond = " AND ".join(_cross_condition_sql(c) for c in gccs)
                body = f"SELECT * FROM ({body}) WHERE {cc_cond}"
            alias = f"M{global_index + 1}"
            ctes.append(f"{alias} AS ({body})")
            for j, _iv in enumerate(run):
                inner_alias = f"M{first + j + 1}"
                alias_map[inner_alias] = (alias, inner_alias)
            ts, te = _slot_span(run)
            slot_bounds.append((ts, te))
            slot_indices.append(first)
            global_index += 1

    # operators between slots
    if len(slot_bounds) > 1:
        conditions.extend(_operators_between_slots(
            model, ivs, deltas, slot_bounds, slot_indices, side, fps))

    # cross-conditions (outer)
    for c in model.get("cross_conditions", []):
        conditions.append(_cross_condition_sql(c, alias_map))

    # projection
    projection = model.get("custom_projection")
    if projection:
        fields = [_translate_field(f) for f in projection]
    else:
        fields = _default_projection(model, ivs, alias_map)

    return ctes, fields, conditions


def _render_flat_body(model: dict, ivs: list[dict], analysis_id: str, deltas: dict,
                      side: str | None = None, fps: int | str = 1,
                      audio_predicates: set[str] | None = None) -> str:
    ctes, fields, conditions = _render_chain(model, ivs, analysis_id, deltas, side=side, fps=fps,
                                             audio_predicates=audio_predicates)
    return _build_select(ctes, fields, conditions)


def _cte_body(cte: str) -> str:
    """Extract the SELECT body from a 'alias AS (SELECT ...)' CTE string."""
    prefix = " AS (\n"
    start = cte.index(prefix) + len(prefix)
    end = cte.rindex("\n)")
    return cte[start:end]


def _build_select(ctes: list[str], fields: list[str], conditions: list[str]) -> str:
    alias_names = [c.split(" AS (", 1)[0].strip() for c in ctes]
    from_clause = ", ".join(alias_names)
    where = ""
    if conditions:
        where = "\nWHERE " + "\n  AND ".join(conditions)
    cte_block = ",\n".join(ctes)
    if cte_block:
        return f"WITH {cte_block}\nSELECT {', '.join(fields)}\nFROM {from_clause}{where}"
    return f"SELECT {', '.join(fields)}\nFROM {from_clause}{where}"


# ---------------------------------------------------------------------------
# set operations (Left op Right)
# ---------------------------------------------------------------------------

def _side_intervals(model: dict, side: str) -> list[dict]:
    return [iv for iv in model["intervals"] if iv.get("set_side") == side]


def _build_inline(ctes: list[str], fields: list[str], conditions: list[str]) -> str:
    alias_names = [c.split(" AS (", 1)[0].strip() for c in ctes]
    from_clause = ", ".join(f"({_cte_body(c)}) {name}" for c, name in zip(ctes, alias_names))
    where = "\nWHERE " + "\n  AND ".join(conditions) if conditions else ""
    return f"SELECT {', '.join(fields)}\nFROM {from_clause}{where}"


def _render_inline_body(model: dict, ivs: list[dict], analysis_id: str, deltas: dict,
                        side: str | None = None, fps: int | str = 1,
                        audio_predicates: set[str] | None = None) -> str:
    """Render a chain as a plain SELECT with inline subqueries (no WITH).

    Set-operation operands need this: SQLite rejects '(... WITH ...) UNION (...)'.
    """
    ctes, fields, conditions = _render_chain(model, ivs, analysis_id, deltas, side=side, fps=fps,
                                             audio_predicates=audio_predicates)
    return _build_inline(ctes, fields, conditions)


def _pad_fields(fields: list[str], n: int) -> list[str]:
    if len(fields) >= n:
        return fields
    return fields + [f"NULL AS __p{i}" for i in range(1, n - len(fields) + 1)]


def _render_set_operation(model: dict, analysis_id: str, deltas: dict, fps: int | str = 1,
                          audio_predicates: set[str] | None = None) -> str:
    set_op = model.get("set_operator") or "\\"
    left = _side_intervals(model, "left")
    right = _side_intervals(model, "right")
    if not left:
        raise ModelValidationError("set operation requires a 'left' side interval")
    if not right:
        raise ModelValidationError("set operation requires a 'right' side interval")

    left_model = dict(model, intervals=left, set_side=None,
                      custom_projection=model.get("left_projection"),
                      cross_conditions=_side_cross_conditions(model, len(left), 0))
    right_model = dict(model, intervals=right, set_side=None,
                       custom_projection=model.get("right_projection"),
                       cross_conditions=_side_cross_conditions(model, len(right), len(left)))
    left_ctes, left_fields, left_conds = _render_chain(
        left_model, left, analysis_id, deltas, side="left", fps=fps,
        audio_predicates=audio_predicates)
    right_ctes, right_fields, right_conds = _render_chain(
        right_model, right, analysis_id, deltas, side="right", fps=fps,
        audio_predicates=audio_predicates)
    n = max(len(left_fields), len(right_fields))
    left_body = _build_inline(left_ctes, _pad_fields(left_fields, n), left_conds)
    right_body = _build_inline(right_ctes, _pad_fields(right_fields, n), right_conds)
    sql_keyword = {"\\": "EXCEPT", "∪": "UNION", "∩": "INTERSECT"}[set_op]
    return f"{left_body}\n{sql_keyword}\n{right_body}"


def _side_cross_conditions(model: dict, n_intervals: int, offset: int = 0) -> list[dict]:
    """Cross-conditions whose aliases are both within this set-op side.

    ``offset`` is the number of intervals on earlier set-op sides; the side's
    intervals sit at global aliases M{1+offset}..M{n_intervals+offset} and are
    rebound to local M1..Mn in the operand model.
    """
    out = []
    for c in model.get("cross_conditions", []):
        la, ra = c["left_alias"], c["right_alias"]
        if not (isinstance(la, str) and isinstance(ra, str)
                and la.startswith("M") and la[1:].isdigit()
                and ra.startswith("M") and ra[1:].isdigit()):
            continue
        ln, rn = int(la[1:]), int(ra[1:])
        if offset < ln <= offset + n_intervals and offset < rn <= offset + n_intervals:
            out.append({**c, "left_alias": f"M{ln - offset}", "right_alias": f"M{rn - offset}"})
    return out


def compile_event(model_json: str | dict, deltas: dict, analysis_id: str,
                  fps: int | str = 1, audio_predicates: set[str] | None = None
                  ) -> tuple[str, str]:
    """Compile a model to (iseql_text, sql). Raises ModelValidationError on invalid input.

    ``fps`` converts authored δ/ε in seconds to frames (``delta_unit`` = seconds).
    ``audio_predicates`` is the set of predicate names that read from
    AudioPerInterval (from the configured audio taxonomy); None is not allowed
    (no silent defaults) - callers must resolve it.
    """
    if audio_predicates is None:
        raise ModelValidationError(
            "audio_predicates is required (resolve audio_taxonomy.classes)"
        )
    audio_predicates = set(audio_predicates)
    model = validate_model(model_json)
    model = _normalized_model(model)
    has_set_side = any(iv.get("set_side") for iv in model["intervals"])
    if has_set_side:
        sql = _render_set_operation(model, analysis_id, deltas, fps=fps,
                                    audio_predicates=audio_predicates)
    else:
        sql = _render_flat_body(model, model["intervals"], analysis_id, deltas, fps=fps,
                                audio_predicates=audio_predicates)
    return model.get("iseql_text") or "", sql


# ---------------------------------------------------------------------------
# ISEQL text rendering (model -> ISEQL notation). App-owned; used to prefill
# the editor for events whose stored model has no ``iseql_text``.
# ---------------------------------------------------------------------------

def _render_selection(iv: dict, alias: str) -> str:
    pred = iv["pred"]
    sel = iv.get("selection")
    if sel:
        branches = sel.get("branches") or [{
            "preds": sel.get("preds") or [pred["name"]],
            "args": sel.get("args") or {},
        }]
        parts = []
        for b in branches:
            conds = [f'pred="{p}"' for p in (b.get("preds") or [])]
            for k in sorted((b.get("args") or {}), key=int):
                vals = b["args"][k]
                conds.append(" ∨ ".join(f'arg{k}="{v}"' for v in vals))
            parts.append(" ∧ ".join(conds))
        expr = " ∨ ".join(f"({p})" for p in parts) if len(parts) > 1 else parts[0]
        return f"σ_{{{expr}}}({alias})"
    conds = [f'pred="{pred["name"]}"']
    for k, arg in enumerate(pred.get("arguments", []), start=1):
        conds.append(f'arg{k}="{arg}"')
    return f"σ_{{{' ∧ '.join(conds)}}}({alias})"


def _render_operator(model: dict, ivs: list[dict], pair_idx: int, side: str | None,
                     lits: dict | None = None) -> str:
    r = Interval(Predicate("slot", []), *_slot_bounds(ivs[pair_idx]))
    s = Interval(Predicate("slot", []), *_slot_bounds(ivs[pair_idx + 1]))
    res = detect_operator(r, s)
    op = res.operator
    for ov in model.get("operator_overrides", []):
        if ov.get("side") in (None, "none", side) and ov.get("pair_idx") == pair_idx + 1:
            op = ov.get("operator", op)
            if op in ("SP", "EF"):
                res = apply_manual_override(op, r, s)
    entry = _delta_entry(model, pair_idx, side)
    lits = lits or {}

    def lit(v):
        """Resolve a stored param value to a literal for display."""
        if isinstance(v, str) and v not in ("<=", "<", ">=", ">"):
            return lits.get(v)
        return v

    param_names = _OPERATOR_FULL_PARAMS.get(op, ("delta", "zeta", "rho"))
    distance = []
    strict = []
    for p in param_names:
        raw = entry.get(p)
        v = lit(raw)
        if p == "delta":
            part = "δ:∞" if v is None else f"δ:{v}"
        elif p == "epsilon":
            part = "ε:∞" if v is None else f"ε:{v}"
        elif p == "zeta":
            part = f"ζ:{v if v in ('<', '<=', '>', '>=') else '<='}"
        elif p == "eta":
            part = f"η:{v if v in ('<', '<=', '>', '>=') else '<='}"
        elif p == "rho":
            part = f"ρ:{v if v not in (None, 'inf') else 0}"
        else:
            continue
        if p in ("delta", "epsilon"):
            distance.append(part)
        else:
            strict.append(part)
    inner = ", ".join(distance) + ("; " + ", ".join(strict) if strict else "")
    return f"{op}({inner})" if (distance or strict) else op


_OPERATOR_FULL_PARAMS = {
    "Bef": ("delta", "zeta", "rho"),
    "Aft": ("delta", "zeta", "rho"),
    "SP": ("delta", "zeta", "rho"),
    "EF": ("epsilon", "eta", "rho"),
    "DJ": ("delta", "epsilon", "zeta", "eta", "rho"),
    "RDJ": ("delta", "epsilon", "zeta", "eta", "rho"),
    "LOJ": ("delta", "epsilon", "zeta", "eta", "rho"),
    "ROJ": ("delta", "epsilon", "zeta", "eta", "rho"),
}


def _render_projection(model: dict, ivs: list[dict]) -> str:
    proj = model.get("custom_projection")
    if proj:
        return ", ".join(proj)
    fields = []
    for i, iv in enumerate(ivs, start=1):
        alias = f"M{i}"
        for k in range(1, len(iv["pred"].get("arguments", [])) + 1):
            fields.append(f"{alias}.arg{k}")
        fields.append(f"{alias}.sf")
        fields.append(f"{alias}.ef")
    return ", ".join(fields)


def _render_operand(model: dict, ivs: list[dict], side: str | None, offset: int,
                    lits: dict | None = None) -> str:
    body = []
    for i, iv in enumerate(ivs):
        if i > 0:
            body.append(_render_operator(model, ivs, i - 1, side, lits))
        body.append(_render_selection(iv, f"M{i + 1}"))
    proj = _render_projection(model, ivs)
    ccs = _side_cross_conditions(model, len(ivs), offset)
    if ccs:
        def _cc_text(c):
            if c.get("type") == "duration":
                return (f"({c['left_alias']}.{c['left_attr']} \u2212 "
                        f"{c['right_alias']}.{c['right_attr']}) {c['op']} {c['value']}")
            return f"{c['left_alias']}.{c['left_attr']}{c['op']}{c['right_alias']}.{c['right_attr']}"
        cond = " ∧ ".join(_cc_text(c) for c in ccs)
        lines = [f"π_{{{proj}}} ("]
        lines.append(f"  σ_{{{cond}}} (")
        for line in body:
            lines.append("    " + line)
        lines.append("  ))")
        return "\n".join(lines)
    lines = [f"π_{{{proj}}} ("]
    for line in body:
        lines.append("  " + line)
    lines.append(")")
    return "\n".join(lines)


def render_iseql(model: dict, lits: dict | None = None) -> str:
    """Render a model dict to ISEQL text (round-trips through the parser).

    ``lits`` maps named delta keys (e.g. ``rho_audio_fight``) to their literal
    values so the rendered operators always show explicit δ/ε/ζ/η/ρ.
    """
    model = _normalized_model(model)
    ivs = model["intervals"]
    if not ivs:
        return "-- No intervals."
    if any(iv.get("set_side") for iv in ivs):
        left = [iv for iv in ivs if iv.get("set_side") == "left"]
        right = [iv for iv in ivs if iv.get("set_side") == "right"]
        op = {"\\": "\\", "∪": "∪", "∩": "∩"}.get(model.get("set_operator"), "∪")
        return (f"{_render_operand(model, left, 'left', 0, lits)}\n{op}\n"
                f"{_render_operand(model, right, 'right', len(left), lits)}")
    return _render_operand(model, ivs, None, 0, lits)


