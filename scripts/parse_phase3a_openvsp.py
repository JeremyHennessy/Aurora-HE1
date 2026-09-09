#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    log_path = Path("analysis/phase3a/openvsp.log")
    text = log_path.read_text(errors="replace")
    errors = []
    version = None
    geom = None
    section_spans = None
    count = None
    points = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("PHASE3A_ERROR|") or line.startswith("PHASE3A_API_ERROR|"):
            errors.append(line)
        elif line.startswith("PHASE3A_VERSION|"):
            version = line.split("|", 1)[1].strip()
        elif line.startswith("PHASE3A_GEOM|"):
            fields = line.split("|")
            if len(fields) == 5:
                geom = {
                    "span_m": float(fields[1]),
                    "area_m2": float(fields[2]),
                    "root_chord_m": float(fields[3]),
                    "tip_chord_m": float(fields[4]),
                }
        elif line.startswith("PHASE3A_SECTION_SPANS|"):
            fields = line.split("|")
            if len(fields) == 5:
                section_spans = [float(x) for x in fields[1:]]
        elif line.startswith("PHASE3A_COUNT|"):
            count = int(float(line.split("|", 1)[1]))
        elif line.startswith("PHASE3A_POINT|"):
            fields = line.split("|")
            if len(fields) == 4:
                points.append({"alpha_deg": float(fields[1]), "cl": float(fields[2]), "cdi": float(fields[3])})

    if errors:
        raise SystemExit("Phase 3A OpenVSP errors: " + "; ".join(errors))
    if version is None:
        raise SystemExit("missing PHASE3A_VERSION marker")
    if geom is None:
        raise SystemExit("missing PHASE3A_GEOM marker")
    if section_spans is None:
        raise SystemExit("missing PHASE3A_SECTION_SPANS marker")
    if count is None:
        raise SystemExit("missing PHASE3A_COUNT marker")
    if count != len(points):
        raise SystemExit(f"VSPAERO point count mismatch: marker={count}, parsed={len(points)}")
    if not points:
        raise SystemExit("no VSPAERO points parsed")

    points.sort(key=lambda row: row["alpha_deg"])
    out = {
        "tool_version": version,
        "openvsp_reported_geometry": geom,
        "openvsp_section_spans_m": section_spans,
        "point_count": count,
        "points": points,
    }
    Path("analysis/phase3a/vspaero_results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
