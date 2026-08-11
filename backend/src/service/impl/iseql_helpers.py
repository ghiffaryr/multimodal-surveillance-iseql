from __future__ import annotations

from typing import Optional


def iseql_before(r: str, s: str, delta: int | str) -> str:
    """ISEQL Before (Bef): 0 < s.Ts - r.Te <= delta. s starts strictly after r ends."""
    delta = int(delta)
    return (
        f"({s}.StartFrame > {r}.EndFrame "
        f"AND ({s}.StartFrame - {r}.EndFrame) <= {delta})"
    )


def iseql_loj(
    r: str,
    s: str,
    delta: Optional[int | str] = None,
    epsilon: Optional[int | str] = None,
) -> str:
    """ISEQL Left Overlap Join (LOJ): 0 <= s.Ts - r.Ts <= delta and 0 <= s.Te - r.Te <= epsilon.
    s lags r in both start and end; the intervals must overlap (s.StartFrame <= r.EndFrame);
    unbounded when delta/epsilon omitted."""
    parts = [
        f"{s}.StartFrame >= {r}.StartFrame",
        f"{s}.StartFrame <= {r}.EndFrame",
        f"{s}.EndFrame >= {r}.EndFrame",
    ]
    if delta is not None:
        delta = int(delta)
        parts.append(f"({s}.StartFrame - {r}.StartFrame) <= {delta}")
    if epsilon is not None:
        epsilon = int(epsilon)
        parts.append(f"({s}.EndFrame - {r}.EndFrame) <= {epsilon}")
    return f"({' AND '.join(parts)})"


def iseql_sp(r: str, s: str, delta: Optional[int | str] = None) -> str:
    """ISEQL Start Preceding (SP): 0 <= s.Ts - r.Ts <= delta and r.Te - s.Ts >= 0.
    r starts no later than s and the intervals overlap (s.StartFrame <= r.EndFrame)."""
    parts = [
        f"{s}.StartFrame >= {r}.StartFrame",
        f"{s}.StartFrame <= {r}.EndFrame",
    ]
    if delta is not None:
        delta = int(delta)
        parts.append(f"({s}.StartFrame - {r}.StartFrame) <= {delta}")
    return f"({' AND '.join(parts)})"


def iseql_dj(
    r: str,
    s: str,
    delta: Optional[int | str] = None,
    epsilon: Optional[int | str] = None,
) -> str:
    """ISEQL During Join (DJ): 0 <= r.Ts - s.Ts <= delta and 0 <= s.Te - r.Te <= epsilon.
    r is contained within s (s.StartFrame <= r.StartFrame and r.EndFrame <= s.EndFrame)."""
    parts = [
        f"{r}.StartFrame >= {s}.StartFrame",
        f"{r}.EndFrame <= {s}.EndFrame",
    ]
    if delta is not None:
        delta = int(delta)
        parts.append(f"({r}.StartFrame - {s}.StartFrame) <= {delta}")
    if epsilon is not None:
        epsilon = int(epsilon)
        parts.append(f"({s}.EndFrame - {r}.EndFrame) <= {epsilon}")
    return f"({' AND '.join(parts)})"


def iseql_ef(r: str, s: str, epsilon: Optional[int | str] = None) -> str:
    """ISEQL End Following (EF): 0 <= r.Te - s.Te <= epsilon and s.Te - r.Ts >= 0.
    r ends no earlier than s and the intervals overlap (s.EndFrame >= r.StartFrame).
    Per ICSC 2016, EF uses the end-offset tolerance epsilon (not delta)."""
    parts = [
        f"{s}.EndFrame <= {r}.EndFrame",
        f"{s}.EndFrame >= {r}.StartFrame",
    ]
    if epsilon is not None:
        epsilon = int(epsilon)
        parts.append(f"({r}.EndFrame - {s}.EndFrame) <= {epsilon}")
    return f"({' AND '.join(parts)})"


def iseql_roj(
    r: str,
    s: str,
    delta: Optional[int | str] = None,
    epsilon: Optional[int | str] = None,
) -> str:
    """ISEQL Right Overlap Join (ROJ): s.Ts <= r.Ts < s.Te <= r.Te — reverse of LOJ."""
    return iseql_loj(s, r, delta, epsilon)


def iseql_rdj(
    r: str,
    s: str,
    delta: Optional[int | str] = None,
    epsilon: Optional[int | str] = None,
) -> str:
    """ISEQL Reverse During Join (RDJ): r.Ts <= s.Ts and s.Te <= r.Te — reverse of DJ."""
    return iseql_dj(s, r, delta, epsilon)


def iseql_after(r: str, s: str, delta: int | str) -> str:
    """ISEQL After (Aft): r starts after s ends, gap <= delta — reverse of Bef."""
    return iseql_before(s, r, delta)
