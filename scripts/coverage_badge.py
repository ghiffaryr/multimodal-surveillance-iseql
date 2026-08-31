#!/usr/bin/env python3
"""Compute combined backend + frontend line coverage and emit a shields.io
endpoint JSON used by the README coverage badge.

Usage:
    python3 scripts/coverage_badge.py [backend/coverage.xml] [frontend/coverage/lcov.info]

The JSON is written to ``coverage/coverage.json``; the README badge points a
shields.io endpoint at that committed file, so no third-party coverage service
is required.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def backend_cov(path: str) -> tuple[int, int]:
    """(total_lines, covered_lines) from a coverage.py ``coverage.xml``."""
    root = ET.parse(path).getroot()
    total = covered = 0
    for cls in root.iter("class"):
        for line in cls.iter("line"):
            hits = line.get("hits")
            if hits is None:
                continue
            total += 1
            if hits != "0":
                covered += 1
    return total, covered


def frontend_cov(path: str) -> tuple[int, int]:
    """(total_lines, covered_lines) from an lcov ``lcov.info``."""
    total = covered = 0
    lf = lh = None
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line.startswith("LF:"):
            lf = int(line[3:])
        elif line.startswith("LH:"):
            lh = int(line[3:])
        elif line == "end_of_record":
            if lf is not None and lh is not None:
                total += lf
                covered += lh
            lf = lh = None
    return total, covered


def color(pct: float) -> str:
    if pct >= 80:
        return "brightgreen"
    if pct >= 60:
        return "yellow"
    if pct >= 40:
        return "orange"
    return "red"


def main() -> None:
    backend_xml = sys.argv[1] if len(sys.argv) > 1 else "backend/coverage.xml"
    frontend_lcov = sys.argv[2] if len(sys.argv) > 2 else "frontend/coverage/lcov.info"

    total = covered = 0
    bt, bc = backend_cov(backend_xml)
    total += bt
    covered += bc
    ft, fc = frontend_cov(frontend_lcov)
    total += ft
    covered += fc

    pct = (covered / total * 100) if total else 0.0
    out_dir = Path("coverage")
    out_dir.mkdir(exist_ok=True)
    payload = {
        "schemaVersion": 1,
        "label": "coverage",
        "message": f"{pct:.1f}%",
        "color": color(pct),
    }
    (out_dir / "coverage.json").write_text(json.dumps(payload) + "\n")
    print(f"coverage: {pct:.1f}% ({covered}/{total} lines)")


if __name__ == "__main__":
    main()
