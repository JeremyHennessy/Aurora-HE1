#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def parse_log(path: Path) -> dict:
    text = path.read_text(errors="replace")
    errors = []
    version = None
    main_geom = None
    complete = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("PHASE4A_ERROR|") or line.startswith("PHASE4A_API_ERROR|"):
            errors.append(line)
        elif line.startswith("PHASE4A_VERSION|"):
            version = line.split("|", 1)[1].strip()
        elif line.startswith("PHASE4A_MAIN_GEOM|"):
            f = line.split("|")
            if len(f) == 5:
                main_geom = {
                    "span_m": float(f[1]),
                    "area_m2": float(f[2]),
                    "root_chord_m": float(f[3]),
                    "tip_chord_m": float(f[4]),
                }
        elif line == "PHASE4A_COMPLETE":
            complete = True
    if errors:
        raise SystemExit("explicit OpenVSP errors: " + "; ".join(errors))
    if version is None or main_geom is None or not complete:
        raise SystemExit("missing required Phase 4A log evidence")
    return {"tool_version": version, "main_geometry": main_geom}


def parse_lod(path: Path, requested_alphas: list[float]) -> dict[float, list[dict[str, float]]]:
    lines = path.read_text(errors="replace").splitlines()
    blocks: dict[float, list[dict[str, float]]] = {}
    current_alpha: float | None = None
    header: list[str] | None = None
    for line in lines:
        if line.startswith("AoA_"):
            current_alpha = float(line.split()[1])
            header = None
            blocks.setdefault(current_alpha, [])
            continue
        if current_alpha is not None and line.startswith("Iter"):
            header = line.split()
            continue
        if current_alpha is None or header is None:
            continue
        fields = line.split()
        if len(fields) < len(header):
            continue
        try:
            row = {name: float(value) for name, value in zip(header, fields)}
        except ValueError:
            continue
        if row.get("IsARotor", 0.0) != 0.0:
            continue
        if row.get("VortexSheet") != 1.0:
            continue
        blocks[current_alpha].append(row)

    out: dict[float, list[dict[str, float]]] = {}
    for alpha in requested_alphas:
        matching = min(blocks, key=lambda x: abs(x - alpha)) if blocks else None
        if matching is None or abs(matching - alpha) > 1e-6:
            raise SystemExit(f"missing LOD block for alpha {alpha}")
        rows = [r for r in blocks[matching] if r["Yavg"] > 0.0]
        rows.sort(key=lambda r: r["Yavg"])
        if len(rows) < 20:
            raise SystemExit(f"alpha {alpha}: too few positive-semispan rows: {len(rows)}")
        out[alpha] = rows
    return out


def main() -> None:
    root = Path("analysis/phase4a")
    manifest = json.loads((root / "manifest.json").read_text())
    requested = [float(x) for x in manifest["aero_load_shape"]["alpha_deg"]]
    log = parse_log(root / "WING_LOAD.log")
    blocks = parse_lod(root / "WING_LOAD.lod", requested)

    cases = []
    for alpha in requested:
        raw_rows = blocks[alpha]
        weighted = []
        total_raw = 0.0
        for r in raw_rows:
            raw = float(r["Cz"]) * float(r["dArea"]) * float(r["V/Vref"]) ** 2
            if not math.isfinite(raw) or raw <= 0.0:
                raise SystemExit(f"alpha {alpha}: nonpositive/nonfinite local vertical-load weight")
            total_raw += raw
            weighted.append((r, raw))
        sections = []
        centroid = 0.0
        for r, raw in weighted:
            frac = raw / total_raw
            centroid += float(r["Yavg"]) * frac
            sections.append({
                "y_m": float(r["Yavg"]),
                "z_m": float(r["Zavg"]),
                "dspan_m": float(r["dSpan"]),
                "chord_m": float(r["Chord"]),
                "darea_m2": float(r["dArea"]),
                "local_cl": float(r["Cl"]),
                "local_cz": float(r["Cz"]),
                "v_over_vref": float(r["V/Vref"]),
                "normalized_vertical_load_fraction": frac,
            })
        cases.append({
            "alpha_deg": alpha,
            "section_count": len(sections),
            "raw_vertical_load_measure": total_raw,
            "halfwing_load_centroid_y_m": centroid,
            "sections": sections,
        })

    out = {
        "status": manifest["status"],
        "tool_version": log["tool_version"],
        "main_geometry": log["main_geometry"],
        "main_wing": manifest["main_wing"],
        "aero_load_shape": manifest["aero_load_shape"],
        "cases": cases,
        "boundary": manifest["boundary"],
    }
    (root / "spanload.json").write_text(json.dumps(out, indent=2) + "\n")
    with (root / "spanload.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["alpha_deg", "y_m", "chord_m", "local_cz", "normalized_vertical_load_fraction"])
        for case in cases:
            for s in case["sections"]:
                w.writerow([case["alpha_deg"], s["y_m"], s["chord_m"], s["local_cz"], s["normalized_vertical_load_fraction"]])
    print(json.dumps({"centroids_m": {str(c["alpha_deg"]): c["halfwing_load_centroid_y_m"] for c in cases}}, indent=2))


if __name__ == "__main__":
    main()
