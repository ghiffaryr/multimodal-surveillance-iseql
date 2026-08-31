"""Relation vocabulary helpers: args <-> ClassID signature conversion.

The stored relation signature is the ISEQL prompt form, e.g.
``(PersonID, VehicleID)`` or ``(VehicleID∨ObjectID)``. A ``∨`` groups
alternative classes for a *single* argument slot (``vehicle ∨ object`` means
one participant that is either a vehicle or an object), while a comma separates
distinct argument slots. A trailing ``?`` marks an optional slot.

The user-facing "args" form mirrors that notation:
``person, vehicle`` and ``vehicle ∨ object``.

The conversion is generic (not a fixed class table): ``foo`` -> ``FooID`` and
``FooID`` -> ``foo``, so any participant class (person, vehicle, object, item,
...) round-trips.
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


def _strip_parens(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("("):
        s = s[1:]
    if s.endswith(")"):
        s = s[:-1]
    return s


def args_to_classid(args: str) -> str:
    """'person, vehicle?' -> '(PersonID, VehicleID?)'; 'vehicle ∨ object' ->
    '(VehicleID∨ObjectID)'."""
    parts: list[str] = []
    for slot in (args or "").split(","):
        slot = slot.strip()
        if not slot:
            continue
        optional = slot.endswith("?")
        base = slot[:-1] if optional else slot
        classes: list[str] = []
        for tok in base.split("∨"):
            tok = tok.strip()
            if not tok:
                continue
            classes.append(tok[0].upper() + tok[1:] + "ID")
        if not classes:
            continue
        parts.append("∨".join(classes) + ("?" if optional else ""))
    return "(" + ", ".join(parts) + ")" if parts else ""


def classid_to_args(classid: str) -> str:
    """'(PersonID, VehicleID?)' -> 'person, vehicle?'; '(VehicleID∨ObjectID)' ->
    'vehicle ∨ object'."""
    inner = _strip_parens(classid)
    out: list[str] = []
    for slot in inner.split(","):
        slot = slot.strip()
        if not slot:
            continue
        optional = slot.endswith("?")
        base = slot[:-1] if optional else slot
        classes: list[str] = []
        for tok in base.split("∨"):
            cls = _token_to_class(tok)
            if cls:
                classes.append(cls)
        if not classes:
            continue
        out.append(" ∨ ".join(classes) + ("?" if optional else ""))
    return ", ".join(out)


def signature_slots(signature: str) -> list[list[str]]:
    """Argument slots of a signature, each slot a list of alternative classes.

    '(PersonID, VehicleID)' -> [['person'], ['vehicle']]
    '(VehicleID∨ObjectID)'   -> [['vehicle', 'object']]
    """
    inner = _strip_parens(signature)
    slots: list[list[str]] = []
    for slot in inner.split(","):
        slot = slot.strip()
        if not slot:
            continue
        classes: list[str] = []
        for tok in slot.split("∨"):
            cls = _token_to_class(tok)
            if cls and cls not in classes:
                classes.append(cls)
        if classes:
            slots.append(classes)
    return slots


def signature_classes(signature: str) -> list[str]:
    """Flat participant classes of a signature (alternatives collapsed).

    '(PersonID, VehicleID)' -> ['person', 'vehicle']
    '(VehicleID∨ObjectID)'   -> ['vehicle', 'object']
    Preserves order and de-duplicates.
    """
    classes: list[str] = []
    for slot in signature_slots(signature):
        for cls in slot:
            if cls not in classes:
                classes.append(cls)
    return classes
