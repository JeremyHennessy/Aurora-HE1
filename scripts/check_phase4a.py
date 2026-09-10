#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise SystemExit(f"PHASE 4A VALIDATION FAILED: {msg}")


def relerr(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


def main() -> None:
    cfg = json.loads(Path("config/phase4a_structural_loads.json").read_text())
    span = json.loads(Path("analysis/phase4a/spanload.json").read_text())
    results = json.loads(Path("analysis/phase4a/structural_results.json").read_text())
    wing = span["main_wing"]
    log_geom = span["main_geometry"]
    tol = float(cfg["validation"]["geometry_relative_tolerance"])

    reported_version = str(span["tool_version"]).replace("OpenVSP ", "").strip()
    require(reported_version == str(cfg["toolchain"]["openvsp_version"]), f"unexpected OpenVSP version {span['tool_version']}")
    for key in ("span_m", "area_m2", "root_chord_m", "tip_chord_m"):
        require(relerr(float(log_geom[key]), float(wing[key])) <= tol, f"wing {key} drift: {log_geom[key]} vs {wing[key]}")

    expected_alphas = [float(x) for x in cfg["aero_load_shape"]["alpha_deg"]]
    got_alphas = [float(c["alpha_deg"]) for c in span["cases"]]
    require(got_alphas == expected_alphas, f"alpha blocks differ: {got_alphas} vs {expected_alphas}")
    centroids = []
    for c in span["cases"]:
        fracs = [float(s["normalized_vertical_load_fraction"]) for s in c["sections"]]
        require(len(fracs) >= 20, f"alpha {c['alpha_deg']}: too few load sections")
        require(all(math.isfinite(x) and x > 0 for x in fracs), f"alpha {c['alpha_deg']}: invalid load fractions")
        require(abs(sum(fracs) - 1.0) <= 1e-10, f"alpha {c['alpha_deg']}: normalized load does not sum to 1")
        ys = [float(s["y_m"]) for s in c["sections"]]
        require(all(0.0 < y <= float(wing["semi_span_m"]) + 1e-6 for y in ys), f"alpha {c['alpha_deg']}: y outside semispan")
        centroids.append(float(c["halfwing_load_centroid_y_m"]))
    sensitivity = abs(max(centroids) - min(centroids)) / max(centroids)
    require(sensitivity <= float(cfg["validation"]["maximum_root_moment_shape_sensitivity_fraction"]), f"4/6 degree root-moment shape sensitivity too large: {sensitivity:.4%}")

    cases = {c["id"]: c for c in results["load_cases"]}
    required = {"POS_1G_CANTILEVER", "POS_2P5G_CANTILEVER", "POS_2P5G_BRACED_ILLUSTRATIVE", "NEG_1G_CANTILEVER"}
    require(required.issubset(cases), "missing structural load cases")
    pos = cases["POS_2P5G_CANTILEVER"]
    br = cases["POS_2P5G_BRACED_ILLUSTRATIVE"]
    neg = cases["NEG_1G_CANTILEVER"]

    root_m = abs(float(pos["root"]["bending_moment_nm"]))
    require(float(cfg["validation"]["minimum_positive_limit_root_moment_nm"]) <= root_m <= float(cfg["validation"]["maximum_positive_limit_root_moment_nm"]), f"+2.5g root moment outside broad screening range: {root_m}")
    require(abs(float(br["root"]["bending_moment_nm"])) < root_m, "illustrative brace does not reduce root bending moment")
    require(not neg["brace_model_active"] and abs(float(neg["brace"]["axial_tension_limit_n"])) < 1e-12, "negative case incorrectly loads lower tension brace")

    expected_tension = float(cfg["validation"]["expected_pdr_brace_tension_limit_n"])
    actual_tension = float(br["brace"]["axial_tension_limit_n"])
    require(relerr(actual_tension, expected_tension) <= float(cfg["validation"]["pdr_brace_tension_relative_tolerance"]), f"brace limit tension no longer reproduces PDR ~3.1 kN: {actual_tension}")
    require(abs(float(br["brace"]["axial_tension_ultimate_n"]) - actual_tension * float(cfg["structural_concept"]["ultimate_factor_on_limit"])) <= 1e-8, "brace ultimate scaling inconsistent")

    joints = [float(x) for x in cfg["structural_concept"]["panel_joint_semispan_y_m"]]
    require(all(0 < y < float(wing["semi_span_m"]) for y in joints), "joint station outside semispan")
    require(float(cfg["structural_concept"]["brace_station_semispan_y_m"]) in joints, "brace station is not a tracked panel-joint station")
    for case in results["load_cases"]:
        for s in case["stations"]:
            for key in ("shear_n", "bending_moment_nm", "effective_spar_depth_m", "idealized_cap_axial_force_n"):
                require(math.isfinite(float(s[key])), f"{case['id']} y={s['y_m']}: nonfinite {key}")
            require(float(s["effective_spar_depth_m"]) > 0.0, f"{case['id']} y={s['y_m']}: nonpositive spar depth")
            areas = s["required_single_cap_area_mm2_by_effective_stress"]
            require(all(math.isfinite(float(v)) and float(v) >= 0.0 for v in areas.values()), f"{case['id']} y={s['y_m']}: invalid cap area sensitivity")

    require(str(results["status"]).startswith("PHASE 4A PRELIMINARY"), "status boundary missing")
    require(any("not structural adequacy" in x.lower() for x in results["boundary"]), "structural-adequacy boundary missing")

    summary = {
        "shape_centroids_m": centroids,
        "shape_sensitivity_fraction": sensitivity,
        "positive_2p5g_cantilever_root_moment_nm": root_m,
        "positive_2p5g_braced_root_moment_nm": abs(float(br["root"]["bending_moment_nm"])),
        "brace_tension_limit_n": actual_tension,
        "brace_tension_ultimate_n": float(br["brace"]["axial_tension_ultimate_n"]),
        "root_moment_reduction_fraction": float(results["headline"]["brace_root_moment_reduction_fraction"]),
    }
    Path("analysis/phase4a/validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("PHASE 4A VALIDATION PASSED")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
