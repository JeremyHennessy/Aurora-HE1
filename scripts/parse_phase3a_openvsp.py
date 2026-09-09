#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def parse_native_polar(path: Path) -> list[dict[str, float]]:
    lines = path.read_text(errors="replace").splitlines()
    header = None
    header_index = None
    for i, line in enumerate(lines):
        fields = line.split()
        if "AoA" in fields and "CLtot" in fields and "CDi" in fields:
            header = fields
            header_index = i
            break
    if header is None or header_index is None:
        raise SystemExit("native VSPAERO polar is missing AoA/CLtot/CDi header")
    ia = header.index("AoA")
    icl = header.index("CLtot")
    icdi = header.index("CDi")
    points: list[dict[str, float]] = []
    for raw in lines[header_index + 1:]:
        fields = raw.split()
        if len(fields) <= max(ia, icl, icdi):
            continue
        try:
            alpha = float(fields[ia])
            cl = float(fields[icl])
            cdi = float(fields[icdi])
        except ValueError:
            continue
        points.append({"alpha_deg": alpha, "cl": cl, "cdi": cdi})
    return points


def main() -> None:
    log_path = Path("analysis/phase3a/openvsp.log")
    text = log_path.read_text(errors="replace")
    errors = []
    version = None
    geom = None
    section_spans = None
    polar_path = Path("analysis/phase3a/AURORA_HE1_phase3a.polar")
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
        elif line.startswith("PHASE3A_POLAR|"):
            polar_path = Path(line.split("|", 1)[1].strip())

    if errors:
        raise SystemExit("Phase 3A OpenVSP errors: " + "; ".join(errors))
    if version is None:
        raise SystemExit("missing PHASE3A_VERSION marker")
    if geom is None:
        raise SystemExit("missing PHASE3A_GEOM marker")
    if section_spans is None:
        raise SystemExit("missing PHASE3A_SECTION_SPANS marker")
    if not polar_path.is_file():
        raise SystemExit(f"native VSPAERO polar not found: {polar_path}")
    points = parse_native_polar(polar_path)
    if not points:
        raise SystemExit("no VSPAERO coefficient rows parsed from native polar")
    points.sort(key=lambda row: row["alpha_deg"])

    out = {
        "tool_version": version,
        "evidence_source": str(polar_path),
        "openvsp_reported_geometry": geom,
        "openvsp_section_spans_m": section_spans,
        "point_count": len(points),
        "points": points,
    }
    Path("analysis/phase3a/vspaero_results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
