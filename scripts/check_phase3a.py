#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"PHASE 3A VALIDATION FAILED: {message}")


def relerr(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


def main() -> None:
    cfg = json.loads(Path("config/phase3a_openvsp.json").read_text())
    manifest = json.loads(Path("analysis/phase3a/geometry_manifest.json").read_text())
    results = json.loads(Path("analysis/phase3a/vspaero_results.json").read_text())
    wing = manifest["wing"]
    geom = results["openvsp_reported_geometry"]
    tol = float(cfg["validation"]["geometry_relative_tolerance"])

    require(str(results["tool_version"]).startswith(cfg["toolchain"]["openvsp_version"]), f"unexpected OpenVSP version {results['tool_version']}")
    for key in ("span_m", "area_m2", "root_chord_m", "tip_chord_m"):
        require(relerr(float(geom[key]), float(wing[key])) <= tol, f"OpenVSP {key} differs from baseline: {geom[key]} vs {wing[key]}")

    pts = results["points"]
    require(len(pts) == int(cfg["analysis"]["alpha_points"]), f"expected {cfg['analysis']['alpha_points']} alpha points, found {len(pts)}")
    require(all(math.isfinite(p["cl"]) and math.isfinite(p["cdi"]) for p in pts), "non-finite aerodynamic result")
    require(all(p["cdi"] >= 0.0 for p in pts), "negative induced drag coefficient")

    core = [p for p in pts if -2.0 <= p["alpha_deg"] <= 6.0]
    require(len(core) >= 5, "insufficient core alpha points")
    if cfg["validation"]["require_monotonic_cl_over_core_alpha_range"]:
        require(all(b["cl"] > a["cl"] for a, b in zip(core, core[1:])), "CL is not monotonic over -2..6 deg")
    slope = (core[-1]["cl"] - core[0]["cl"]) / math.radians(core[-1]["alpha_deg"] - core[0]["alpha_deg"])
    if cfg["validation"]["require_positive_lift_curve_slope"]:
        require(slope > 0.0, "lift curve slope is not positive")

    target_alpha = float(cfg["analysis"]["comparison_alpha_deg"])
    point = min(pts, key=lambda p: abs(p["alpha_deg"] - target_alpha))
    require(abs(point["alpha_deg"] - target_alpha) <= 0.51, "comparison alpha not represented")
    ar = float(wing["aspect_ratio"])
    e = 0.92
    expected_cdi = point["cl"] ** 2 / (math.pi * e * ar)
    drag_tol = float(cfg["validation"]["induced_drag_relative_tolerance_vs_elliptic_estimate"])
    require(expected_cdi > 0.0 and point["cdi"] > 0.0, "comparison point has zero induced drag")
    require(relerr(point["cdi"], expected_cdi) <= drag_tol, f"VSPAERO CDi {point['cdi']} differs too far from analytical {expected_cdi}")
    oswald_eff = point["cl"] ** 2 / (math.pi * ar * point["cdi"])
    require(0.55 <= oswald_eff <= 1.15, f"implied span efficiency is implausible: {oswald_eff}")

    summary = {
        "openvsp_version": results["tool_version"],
        "geometry": geom,
        "alpha_points": len(pts),
        "lift_curve_slope_per_rad": slope,
        "comparison": {
            "alpha_deg": point["alpha_deg"],
            "cl": point["cl"],
            "vspaero_cdi": point["cdi"],
            "analytical_cdi": expected_cdi,
            "implied_oswald_efficiency": oswald_eff,
        },
        "boundary": cfg["boundary"],
    }
    Path("analysis/phase3a/validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("PHASE 3A VALIDATION PASSED")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
