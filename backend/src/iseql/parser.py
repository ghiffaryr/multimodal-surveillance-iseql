"""Parse the ISEQL query text a user types in the event editor into a model.

The text follows the ISEQL-GUI output format:

    -- Generated ISEQL query for <name>          (optional comment header)
    π_{M1.sf, M2.ef} (                            (projection)
      σ_{pred="engine" ∨ pred="vehicle"}(M1)      (interval selection)
      SP                                        (temporal operator)
      σ_{pred="tire_squeal"}(M2))
    ∪                                           (set operator)
    π_{M1.arg1, M2.arg2, M1.sf, M2.ef} (
      σ_{M1.arg1=M2.arg1} (                      (cross-condition wrapper)
        σ_{pred="running" ∧ arg1="person"}(M1)
        SP
        σ_{pred="enter_or_exit_vehicle" ∧ arg1="person" ∧ arg2="vehicle"}(M2)))

Selections support AND (∧) and OR (∨) of ``pred="x"`` / ``argN="value"``
clauses. Operators: SP, EF, Bef, Aft, DJ, RDJ, LOJ, ROJ, optionally with
``(δ,ε; ζ,η,ρ)``. Set operators: \\ (subtract), ∪ (union), ∩ (intersect).

The parser is intentionally structural: it extracts the pieces the SQL emitter
needs (predicates, argument constraints, cross-conditions, operators, set ops,
projection) and synthesizes concrete interval positions, since the text carries
no explicit frames.
"""
from __future__ import annotations

import re

from iseql.helpers import OPERATOR_PARAMS, OPERATORS

_SET_OPS = ("\\", "∪", "∩")
_ALIAS_RE = re.compile(r"M(\d+)")
_PRED_RE = re.compile(r'pred\s*=\s*"([^"]+)"')
_ARG_RE = re.compile(r'arg(\d+)\s*=\s*"([^"]+)"')
_CROSS_OP = "="

# Intra-interval duration constraint, e.g. ``σ_{(M1.et − M1.st) ≥ 5} (...)``.
# The arithmetic (optionally parenthesised) spans two (M{n}.st|et|sf|ef) refs
# compared against a numeric literal; the subtraction operator may be ''-'' or
# the Unicode minus U+2212. Both refs are normally the same interval (self
# duration), but cross-interval spans are accepted as-is and rendered verbatim.
_DURATION_RE = re.compile(
    r"^\s*\(?\s*M(\d+)\.(sf|ef|st|et)\s*[\u2212-]\s*M(\d+)\.(sf|ef|st|et)\s*\)?\s*"
    r"(≤|<=|≥|>=|<|>|⩽|⩾|=)\s*(?:(\d+)|(inf|∞))\s*$"
)

_STRICTNESS_ALIASES = {"≤": "<=", "⩽": "<=", "≥": ">=", "⩾": ">="}

_KIND_LABEL = {"δ": "delta", "ε": "epsilon", "ρ": "rho"}


def _normalize_strictness(op: str) -> str:
    return _STRICTNESS_ALIASES.get(op, op)


def _delta_value(kind: str, raw: str):
    """Parse a δ/ε/ρ value in authored ISEQL text: a number or ∞/inf (unbounded).

    Named keys (e.g. ``delta_visual_handoff``) are backend working values only
    and must not appear in user-authored ISEQL text.
    """
    if raw in ("∞", "inf"):
        return None
    if raw.isdigit():
        return int(raw)
    raise IseqlParseError(
        f"invalid {_KIND_LABEL[kind]} value '{raw}'; expected a number or ∞"
    )


class IseqlParseError(ValueError):
    pass


def _strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("--"):
            continue
        out.append(line)
    return "\n".join(out)


def _split_top_level(text: str, delim: str) -> list[str]:
    """Split on ``delim`` only at parenthesis depth 0."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == delim and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        depth = 0
        closed = False
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    closed = i == len(s) - 1
                    break
        if not closed:
            break
        s = s[1:-1].strip()
    return s


class _Parser:
    def __init__(self, text: str) -> None:
        self.s = text
        self.i = 0

    def eof(self) -> bool:
        return self.i >= len(self.s)

    def peek(self) -> str:
        return self.s[self.i] if not self.eof() else ""

    def skip_ws(self) -> None:
        while not self.eof() and self.s[self.i] in " \t\r\n":
            self.i += 1

    def expect(self, ch: str) -> None:
        self.skip_ws()
        if self.peek() != ch:
            raise IseqlParseError(
                f"expected '{ch}' at position {self.i}, found '{self.peek() or 'EOF'}'"
            )
        self.i += 1

    def read_braced(self) -> str:
        self.skip_ws()
        if self.peek() != "{":
            raise IseqlParseError(f"expected '{{' at position {self.i}, found '{self.peek()}'")
        self.i += 1
        start = self.i
        depth = 1
        while not self.eof() and depth:
            c = self.s[self.i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            self.i += 1
        if depth:
            raise IseqlParseError("unterminated '{'")
        return self.s[start:self.i - 1]

    def read_paren(self) -> str:
        self.skip_ws()
        if self.peek() != "(":
            raise IseqlParseError(f"expected '(' at position {self.i}, found '{self.peek()}'")
        self.i += 1
        start = self.i
        depth = 1
        while not self.eof() and depth:
            c = self.s[self.i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            self.i += 1
        if depth:
            raise IseqlParseError("unterminated '('")
        return self.s[start:self.i - 1]

    def read_identifier(self) -> str:
        self.skip_ws()
        start = self.i
        while not self.eof() and (self.s[self.i].isalnum() or self.s[self.i] == "_"):
            self.i += 1
        return self.s[start:self.i]

    def read_set_op(self) -> str:
        self.skip_ws()
        c = self.peek()
        if c in _SET_OPS:
            self.i += 1
            return c
        raise IseqlParseError(
            f"expected set operator (\\ ∪ ∩) at position {self.i}, found '{c or 'EOF'}'"
        )

    # -- structure ----------------------------------------------------------

    def parse_query(self, name: str) -> dict:
        """Parse the whole query text into a model dict."""
        operands: list["Operand"] = []
        root = self._parse_set_expression(operands)
        self.skip_ws()
        if not self.eof():
            raise IseqlParseError(
                f"unexpected trailing content at position {self.i}: "
                f"'{self.s[self.i:].strip()}'"
            )
        if len(operands) == 1:
            return self._build_flat_model(operands[0], name)
        return self._build_tree_model(root, operands, name)

    def _parse_set_expression(self, operands: list["Operand"]) -> dict:
        """Set-expression tree: operands joined by \\ ∪ ∩, left-associative, with
        parenthesised sub-expressions. Leaves are {group_ref: idx} markers."""
        node = self._parse_set_primary(operands)
        while True:
            self.skip_ws()
            if self.eof() or self.peek() == ")":
                break
            op = self.read_set_op()
            right = self._parse_set_primary(operands)
            node = {"op": op, "children": [node, right]}
        return node

    def _parse_set_primary(self, operands: list["Operand"]) -> dict:
        self.skip_ws()
        if self.peek() == "(":
            self.i += 1
            node = self._parse_set_expression(operands)
            self.expect(")")
            return node
        operand = self.parse_operand()
        idx = len(operands)
        operands.append(operand)
        return {"group_ref": idx, "projection": operand.projection}

    def parse_operand(self) -> "Operand":
        self.skip_ws()
        proj: list[str] | None = None
        if self.peek() == "π":
            self.i += 1
            self.expect("_")
            content = self.read_braced()
            proj = [f.strip() for f in content.split(",") if f.strip()]
            self.expect("(")
        intervals: list[dict] = []
        ops: list[dict] = []
        ccs: list[dict] = []
        self._parse_body(intervals, ops, ccs)
        self.expect(")")
        return Operand(intervals=intervals, ops=ops, cross_conditions=ccs, projection=proj)

    def _parse_body(self, intervals: list[dict], ops: list[dict], ccs: list[dict]) -> None:
        """Parse a chain of sigma blocks separated by temporal operators."""
        while True:
            self.skip_ws()
            if self.peek() == ")":
                return
            if self.peek() != "σ":
                raise IseqlParseError(
                    f"expected 'σ' at position {self.i}, found '{self.peek() or 'EOF'}'"
                )
            self.i += 1
            self.expect("_")
            conditions = self.read_braced()
            self.expect("(")
            self.skip_ws()
            m = _ALIAS_RE.match(self.s, self.i)
            if m and m.end() < len(self.s) and self.s[m.end()] == ")":
                # interval selection: σ_{...}(M{n})
                alias = self.s[self.i:m.end()]
                self.i = m.end()
                self.expect(")")
                intervals.append(self._parse_selection(conditions, alias))
            else:
                # cross-condition wrapper: σ_{cc} ( body ); the wrapper must be
                # the whole content of this chain (its body is the actual chain).
                sub_intervals: list[dict] = []
                sub_ops: list[dict] = []
                self._parse_body(sub_intervals, sub_ops, ccs)
                self.expect(")")
                ccs.extend(self._parse_cross_conditions(conditions))
                intervals.extend(sub_intervals)
                ops.extend(sub_ops)
                self.skip_ws()
                if self.peek() != ")":
                    raise IseqlParseError(
                        "a cross-condition wrapper must wrap the whole chain "
                        "(no operator between a wrapper and another interval)"
                    )
            self.skip_ws()
            if self.peek() == ")":
                return
            ops.append(self._parse_operator())

    # -- atoms ----------------------------------------------------------------

    def _parse_selection(self, conditions: str, alias: str) -> dict:
        if _ALIAS_RE.match(conditions.strip()):
            raise IseqlParseError(f"selection for {alias} must use pred=/argN= clauses")
        if re.search(r"M\d+\.", conditions):
            raise IseqlParseError(
                f"selection for {alias} references other intervals; "
                "cross-conditions must wrap the chain, e.g. σ_{M1.arg1=M2.arg1} ( ... )"
            )
        # Split on top-level OR (∨): each branch is a conjunction of pred= and
        # argN= clauses that must be kept as its own combination in the SQL.
        branches = []
        for part in _split_top_level(conditions, "∨"):
            part = _strip_outer_parens(part)
            preds = [m.group(1) for m in _PRED_RE.finditer(part)]
            if not preds:
                raise IseqlParseError(f"selection for {alias} has an OR branch without pred=\"...\"")
            args: dict[int, list[str]] = {}
            for m in _ARG_RE.finditer(part):
                n = int(m.group(1))
                args.setdefault(n, []).append(m.group(2))
            branches.append({
                "preds": list(dict.fromkeys(preds)),
                "args": {str(k): list(dict.fromkeys(v)) for k, v in sorted(args.items())},
            })
        if len(branches) == 1:
            selection = {"preds": branches[0]["preds"], "args": branches[0]["args"]}
        else:
            selection = {"branches": branches}
        args_all: dict[int, list[str]] = {}
        for b in branches:
            for k, v in b["args"].items():
                slot = int(k)
                args_all.setdefault(slot, [])
                for c in v:
                    if c not in args_all[slot]:
                        args_all[slot].append(c)
        return {
            "pred": {"name": branches[0]["preds"][0], "arguments": self._args_to_arguments(args_all)},
            "selection": selection,
        }

    @staticmethod
    def _args_to_arguments(args: dict[int, list[str]]) -> list[str]:
        out = []
        for k in sorted(args):
            out.append(args[k][0])
        return out

    def _parse_cross_conditions(self, conditions: str) -> list[dict]:
        out: list[dict] = []
        for part in re.split(r"[∧∨]", conditions):
            part = part.strip()
            if not part:
                continue
            dm = _DURATION_RE.match(part)
            if dm:
                if dm.group(7):
                    raise IseqlParseError(
                        f"duration constraint must have a finite bound, got '{part}'"
                    )
                out.append({
                    "type": "duration",
                    "left_alias": f"M{dm.group(1)}",
                    "left_attr": dm.group(2),
                    "right_alias": f"M{dm.group(3)}",
                    "right_attr": dm.group(4),
                    "op": _normalize_strictness(dm.group(5)),
                    "value": int(dm.group(6)),
                })
                continue
            part = part.strip("()").strip()
            if not part:
                continue
            m = re.match(r"(M\d+)\.(\w+)\s*(≠|≠|<=|>=|≤|≥|<|>|=)\s*(M\d+)\.(\w+)$", part)
            if not m:
                raise IseqlParseError(f"invalid cross-condition '{part}'")
            out.append({
                "left_alias": m.group(1),
                "left_attr": m.group(2),
                "op": m.group(3),
                "right_alias": m.group(4),
                "right_attr": m.group(5),
            })
        return out

    def _parse_operator(self) -> dict:
        self.skip_ws()
        for name in OPERATORS:
            if self.s.startswith(name, self.i):
                end = self.i + len(name)
                if end < len(self.s) and self.s[end].isalnum():
                    continue
                self.i = end
                delta = epsilon = zeta = eta = rho = None
                self.skip_ws()
                if self.peek() == "(":
                    params = self.read_paren()
                    for p in re.split(r"[;,]", params):
                        p = p.strip()
                        if not p:
                            continue
                        # δ/ε/ρ: a number (frames/seconds), ∞/inf (unbounded), or a
                        # named key that resolves per-detect (e.g. delta_visual_handoff).
                        pm = re.match(r"([δε])\s*:\s*([A-Za-z_][A-Za-z0-9_]*|\d+|∞|inf)$", p)
                        zm = re.match(r"([ζη])\s*:\s*(<=|≤|<|>=|≥|>|⩽|⩾)$", p)
                        rm = re.match(r"ρ\s*:\s*([A-Za-z_][A-Za-z0-9_]*|\d+|∞|inf)$", p)
                        if pm:
                            raw = pm.group(2)
                            value = _delta_value(pm.group(1), raw)
                            if pm.group(1) == "δ":
                                delta = value
                            else:
                                epsilon = value
                        elif zm:
                            value = _normalize_strictness(zm.group(2))
                            if zm.group(1) == "ζ":
                                zeta = value
                            else:
                                eta = value
                        elif rm:
                            rho = _delta_value("ρ", rm.group(1))
                        else:
                            raise IseqlParseError(f"invalid operator parameter '{p}'")
                return {"op": name, "delta": delta, "epsilon": epsilon,
                        "zeta": zeta, "eta": eta, "rho": rho}
        raise IseqlParseError(
            f"expected temporal operator (SP EF Bef Aft DJ RDJ LOJ ROJ) at position {self.i}"
        )

    # -- model assembly --------------------------------------------------------

    def _build_flat_model(self, op: "Operand", name: str) -> dict:
        self._synthesize(op.intervals, op.ops)
        model: dict = {
            "event_name": name,
            "intervals": op.intervals,
            "cross_conditions": op.cross_conditions,
            "operator_overrides": [
                {"side": "none", "pair_idx": k + 1, "operator": o["op"]}
                for k, o in enumerate(op.ops)
            ],
        }
        if op.ops:
            # Always record each pair's thresholds: the typed value, or None for
            # bare operators so the SQL omits the numeric bound (unbounded).
            # ζ/η/ρ are only recorded when explicitly written (they have SQL
            # defaults <= / <= / 0 otherwise).
            model["delta_map"] = {}
            for k, o in enumerate(op.ops):
                entry = {p: o.get(p) for p in OPERATOR_PARAMS[o["op"]]}
                for p in ("zeta", "eta", "rho"):
                    if o.get(p) is not None:
                        entry[p] = o[p]
                model["delta_map"][str(k)] = entry
        if op.projection:
            model["custom_projection"] = op.projection
        return model

    def _build_tree_model(self, root: dict, operands: list["Operand"], name: str) -> dict:
        all_intervals: list[dict] = []
        all_ccs: list[dict] = []
        overrides: list[dict] = []
        dm: dict[str, object] = {}
        offset = 0
        for idx, op in enumerate(operands):
            gname = f"s{idx + 1}"
            self._synthesize(op.intervals, op.ops)
            all_intervals += [dict(iv, group=gname) for iv in op.intervals]
            all_ccs += self._offset_ccs(op.cross_conditions, offset)
            for i, o in enumerate(op.ops):
                overrides.append({"side": gname, "pair_idx": i + 1, "operator": o["op"]})
                entry = {p: o.get(p) for p in OPERATOR_PARAMS[o["op"]]}
                for p in ("zeta", "eta", "rho"):
                    if o.get(p) is not None:
                        entry[p] = o[p]
                dm[f"{gname}.{i}"] = entry
            offset += len(op.intervals)
        model: dict = {
            "event_name": name,
            "set_expression": self._finalize_tree(root),
            "intervals": all_intervals,
            "cross_conditions": all_ccs,
            "operator_overrides": overrides,
        }
        if dm:
            model["delta_map"] = dm
        return model

    def _finalize_tree(self, node: dict) -> dict:
        if "group_ref" in node:
            leaf: dict = {"group": f"s{node['group_ref'] + 1}"}
            if node.get("projection"):
                leaf["projection"] = node["projection"]
            return leaf
        return {
            "op": node["op"],
            "children": [self._finalize_tree(c) for c in node["children"]],
        }

    @staticmethod
    def _offset_ccs(ccs: list[dict], offset: int) -> list[dict]:
        def reb(alias: str) -> str:
            m = _ALIAS_RE.fullmatch(alias)
            if m:
                return f"M{int(m.group(1)) + offset}"
            return alias
        return [
            {**c, "left_alias": reb(c["left_alias"]), "right_alias": reb(c["right_alias"])}
            for c in ccs
        ]

    @staticmethod
    def _synthesize(intervals: list[dict], ops: list[dict]) -> None:
        """Assign concrete ts/te to intervals from the operator sequence."""
        if not intervals:
            return
        length = 100
        base = 0
        cur_ts, cur_te = base, base + length
        intervals[0]["ts"] = cur_ts
        intervals[0]["te"] = cur_te
        for i, o in enumerate(ops):
            d = o.get("delta") if isinstance(o.get("delta"), int) else None
            e = o.get("epsilon") if isinstance(o.get("epsilon"), int) else None
            a0, a1 = cur_ts, cur_te
            op = o["op"]
            if op == "Bef":
                b0 = a1
                b1 = b0 + length
            elif op == "Aft":
                b1 = a0
                b0 = b1 - length
            elif op == "SP":
                b0 = a0 + length // 2
                b1 = b0 + length
            elif op == "EF":
                b1 = a1 + length // 2
                b0 = a0
            elif op == "DJ":
                b0 = a0 - (d if d is not None else length // 4)
                b1 = a1 + (e if e is not None else length // 4)
            elif op == "RDJ":
                b0 = a0 + (d if d is not None else length // 4)
                b1 = a1 - (e if e is not None else length // 4)
            elif op == "LOJ":
                b0 = a0 + (d if d is not None else length // 4)
                b1 = a1 + (e if e is not None else length // 2)
            elif op == "ROJ":
                b0 = a0 - (d if d is not None else length // 4)
                b1 = a1 - (e if e is not None else length // 2)
            else:
                raise IseqlParseError(f"unsupported operator '{op}'")
            b0 = max(0, b0)
            if b1 <= b0:
                b1 = b0 + 1
            intervals[i + 1]["ts"] = b0
            intervals[i + 1]["te"] = b1
            cur_ts, cur_te = b0, b1


class Operand:
    __slots__ = ("intervals", "ops", "cross_conditions", "projection")

    def __init__(self, intervals, ops, cross_conditions, projection):
        self.intervals = intervals
        self.ops = ops
        self.cross_conditions = cross_conditions
        self.projection = projection


def parse_iseql(text: str, name: str = "event", delta_unit: str = "seconds") -> dict:
    """Parse ISEQL query text into a model dict (raises IseqlParseError).

    ``delta_unit`` records the unit of the authored δ/ε thresholds ("seconds"
    or "frames"); the SQL emitter converts seconds to frames per-analysis.
    """
    if delta_unit not in ("seconds", "frames"):
        raise IseqlParseError("delta_unit must be 'seconds' or 'frames'")
    stripped = _strip_comments(text)
    parser = _Parser(stripped)
    model = parser.parse_query(name)
    model["delta_unit"] = delta_unit
    model["iseql_text"] = text
    return model
