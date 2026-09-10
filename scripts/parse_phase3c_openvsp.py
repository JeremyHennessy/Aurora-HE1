#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("linear_fit requires at least two paired samples")
    xm = sum(xs) / len(xs)
    ym = sum(ys) / len(ys)
    denom = sum((x - xm) ** 2 for x in xs)
    if denom <= 0.0:
        raise ValueError("linear_fit has zero x variance")
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / denom
    return slope, ym - slope * xm


def parse_log(path: Path, case: dict) -> dict:
    case_id = case["id"]
    text = path.read_text(errors="replace")
    errors: list[str] = []
    version = None
    main_geom = None
    tail_geom = None
    cg_x = None
    complete = False
    no_tail = False
    wrapper_rc = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("PHASE3C_ERROR|") or line.startswith("PHASE3C_API_ERROR|"):
            errors.append(line)
        elif line.startswith(f"PHASE3C_VERSION|{case_id}|"):
            version = line.split("|", 2)[2].strip()
        elif line.startswith(f"PHASE3C_MAIN_GEOM|{case_id}|"):
            f = line.split("|")
            if len(f) == 6:
                main_geom = {"span_m": float(f[2]), "area_m2": float(f[3]), "root_chord_m": float(f[4]), "tip_chord_m": float(f[5])}
        elif line.startswith(f"PHASE3C_TAIL_GEOM|{case_id}|"):
            f = line.split("|")
            if len(f) == 6:
                tail_geom = {"span_m": float(f[2]), "area_m2": float(f[3]), "root_chord_m": float(f[4]), "tip_chord_m": float(f[5])}
        elif line == f"PHASE3C_NO_TAIL|{case_id}":
            no_tail = True
        elif line.startswith(f"PHASE3C_CG|{case_id}|"):
            cg_x = float(line.split("|", 2)[2])
        elif line.startswith(f"PHASE3C_WRAPPER_RC|{case_id}|"):
            wrapper_rc = int(line.split("|", 2)[2])
        elif line == f"PHASE3C_COMPLETE|{case_id}":
            complete = True
    if errors:
        raise SystemExit(f"{case_id}: explicit OpenVSP errors: {'; '.join(errors)}")
    if version is None or main_geom is None or cg_x is None or wrapper_rc is None or not complete:
        raise SystemExit(f"{case_id}: missing required Phase 3C log evidence")
    if bool(case["include_tail"]) and tail_geom is None:
        raise SystemExit(f"{case_id}: tail geometry marker missing")
    if not bool(case["include_tail"]) and not no_tail:
        raise SystemExit(f"{case_id}: wing-only marker missing")
    return {"tool_version": version, "main_geometry": main_geom, "tail_geometry": tail_geom, "cg_x_m": cg_x, "wrapper_rc": wrapper_rc}


def parse_polar(path: Path) -> list[dict[str, float]]:
    lines = path.read_text(errors="replace").splitlines()
    header = None
    start = None
    required = ("AoA", "CLtot", "CDi", "CMytot")
    for i, line in enumerate(lines):
        fields = line.split()
        if all(name in fields for name in required):
            header = fields
            start = i + 1
            break
    if header is None or start is None:
        raise SystemExit(f"{path}: native VSPAERO polar header not found")
    idx = {name: header.index(name) for name in required}
    rows: list[dict[str, float]] = []
    for line in lines[start:]:
        fields = line.split()
        if len(fields) < len(header):
            continue
        try:
            row = {
                "alpha_deg": float(fields[idx["AoA"]]),
                "cl": float(fields[idx["CLtot"]]),
                "cdi": float(fields[idx["CDi"]]),
                "cm_pitch": float(fields[idx["CMytot"]]),
            }
        except (ValueError, IndexError):
            continue
        if all(math.isfinite(v) for v in row.values()):
            rows.append(row)
    rows.sort(key=lambda row: row["alpha_deg"])
    if not rows:
        raise SystemExit(f"{path}: no finite VSPAERO polar rows parsed")
    return rows


def main() -> None:
    root = Path("analysis/phase3c")
    manifest = json.loads((root / "manifest.json").read_text())
    mac = float(manifest["main_wing"]["mean_aerodynamic_chord_m"])
    results = []

    for case in manifest["cases"]:
        cid = case["id"]
        log = parse_log(root / f"{cid}.log", case)
        points = parse_polar(root / f"{cid}.polar")
        alpha_deg = [p["alpha_deg"] for p in points]
        alpha_rad = [math.radians(x) for x in alpha_deg]
        cls = [p["cl"] for p in points]
        cms = [p["cm_pitch"] for p in points]
        cl_alpha, cl0 = linear_fit(alpha_rad, cls)
        cm_alpha, cm0_rad = linear_fit(alpha_rad, cms)
        cm_cl, cm_at_cl0 = linear_fit(cls, cms)
        static_margin = -cm_cl
        xcg = float(case["reference_cg_x_m"])
        neutral_point_x = xcg + static_margin * mac
        cm_per_deg, cm0_deg = linear_fit(alpha_deg, cms)
        zero_moment_alpha = -cm0_deg / cm_per_deg if abs(cm_per_deg) > 1e-12 else None
        results.append({
            "id": cid,
            "category": case["category"],
            "include_tail": bool(case["include_tail"]),
            "tool_version": log["tool_version"],
            "wrapper_rc": log["wrapper_rc"],
            "main_geometry": log["main_geometry"],
            "tail_geometry": log["tail_geometry"],
            "reference_cg_x_m": log["cg_x_m"],
            "cg_offset_fraction_mac": case.get("cg_offset_fraction_mac"),
            "mesh": case["mesh"],
            "tail_design": case["tail"],
            "point_count": len(points),
            "points": points,
            "derived": {
                "lift_curve_slope_per_rad": cl_alpha,
                "cl_intercept_at_alpha_0": cl0,
                "pitching_moment_slope_per_rad": cm_alpha,
                "pitching_moment_intercept_alpha_rad_0": cm0_rad,
                "dcm_dcl": cm_cl,
                "pitching_moment_at_cl_0": cm_at_cl0,
                "static_margin_fraction_mac": static_margin,
                "neutral_point_x_m": neutral_point_x,
                "zero_moment_alpha_deg_linear_fit": zero_moment_alpha,
            },
        })

    out = {
        "status": manifest["status"],
        "source_main_sha": manifest["source_main_sha"],
        "source_phase3b_head": manifest["source_phase3b_head"],
        "source_phase3b_validation_run": manifest["source_phase3b_validation_run"],
        "reference_mass": manifest["reference_mass"],
        "main_wing": manifest["main_wing"],
        "reference_tail_planform": manifest["reference_tail_planform"],
        "design_review": manifest["design_review"],
        "cases": results,
        "boundary": manifest["boundary"],
    }
    (root / "results.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"case_count": len(results), "static_margins": {r["id"]: r["derived"]["static_margin_fraction_mac"] for r in results}}, indent=2))


if __name__ == "__main__":
    main()
