"""Relation vocabulary helpers: args <-> ClassID signature conversion.

The stored relation signature is the ISEQL prompt form, e.g.
``(PersonID, VehicleID?)``. The user-facing "args" form is a comma-separated
list of participant classes, e.g. ``person, vehicle?``.

The conversion is generic (not a fixed class table): ``foo`` -> ``FooID`` and
``FooID`` -> ``foo``, so any participant class (person, vehicle, object, item,
...) round-trips. A trailing ``?`` marks an optional argument and is preserved.
"""

from __future__ import annotations


def _token_to_class(name: str) -> str:
    """Map a ClassID token to its class: 'PersonID' -> 'person',
    'PersonID1' -> 'person' (multi-arg), 'ItemID?' -> 'item'."""
    name = name.strip().rstrip("?").strip()
    base = name.rstrip("0123456789")
    if base.endswith("ID"):
        base = base[:-2]
    if not base:
        return ""
    return base[0].lower() + base[1:]


def args_to_classid(args: str) -> str:
    """'person, vehicle?' -> '(PersonID, VehicleID?)'."""
    parts: list[str] = []
    for tok in (args or "").split(","):
        tok = tok.strip()
        if not tok:
            continue
        optional = tok.endswith("?")
        base = tok[:-1] if optional else tok
        if not base:
            continue
        parts.append(base[0].upper() + base[1:] + "ID" + ("?" if optional else ""))
    return "(" + ", ".join(parts) + ")" if parts else ""


def classid_to_args(classid: str) -> str:
    """'(PersonID, VehicleID?)' -> 'person, vehicle?'."""
    inner = (classid or "").strip()
    if inner.startswith("("):
        inner = inner[1:]
    if inner.endswith(")"):
        inner = inner[:-1]
    out: list[str] = []
    for tok in inner.split(","):
        tok = tok.strip()
        if not tok:
            continue
        optional = tok.endswith("?")
        cls = _token_to_class(tok)
        if not cls:
            continue
        out.append(cls + ("?" if optional else ""))
    return ", ".join(out)


def signature_classes(signature: str) -> list[str]:
    """Participant classes of a signature: '(PersonID, VehicleID?)' ->
    ['person', 'vehicle']. Preserves order and de-duplicates."""
    inner = (signature or "").strip()
    if inner.startswith("("):
        inner = inner[1:]
    if inner.endswith(")"):
        inner = inner[:-1]
    classes: list[str] = []
    for tok in inner.split(","):
        cls = _token_to_class(tok)
        if cls and cls not in classes:
            classes.append(cls)
    return classes
