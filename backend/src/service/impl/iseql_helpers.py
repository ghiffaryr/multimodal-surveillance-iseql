from __future__ import annotations

from typing import Optional

def iseql_before(alias1: str, alias2: str, delta: int | str, rho: int | str = 0) -> str:
    delta = int(delta)
    rho = int(rho)
    rhs = f"{alias1}.EndFrame + {rho}" if rho != 0 else f"{alias1}.EndFrame"
    return (
        f"({alias2}.StartFrame > {rhs} "
        f"AND ({alias2}.StartFrame - {alias1}.EndFrame) <= {delta})"
    )

def iseql_start_preceding(
    alias1: str, alias2: str, delta: Optional[int | str] = None
) -> str:
    base = (
        f"({alias1}.StartFrame <= {alias2}.StartFrame "
        f"AND {alias2}.StartFrame < {alias1}.EndFrame)"
    )
    if delta is not None:
        delta = int(delta)
        return f"({base} AND ({alias2}.StartFrame - {alias1}.StartFrame) <= {delta})"
    return base

def iseql_overlap(alias1: str, alias2: str) -> str:
    return (
        f"({alias1}.StartFrame <= {alias2}.EndFrame "
        f"AND {alias2}.StartFrame <= {alias1}.EndFrame)"
    )

def iseql_during(alias1: str, alias2: str) -> str:
    return (
        f"({alias1}.StartFrame >= {alias2}.StartFrame "
        f"AND {alias1}.EndFrame <= {alias2}.EndFrame)"
    )
