#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"PHASE 3B VALIDATION FAILED: {message}")


def relerr(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


def main() -> None:
    cfg = json.loads(Path("config/phase3b_longitudinal_tail.json").read_text())
    results = json.loads(Path("analysis/phase3b/results.json").read_text())
    wing = results["main_wing"]
    fixed = results["horizontal_tail_fixed"]
    expected_ids = [c["id"] for c in cfg["horizontal_tail_family"]["candidates"]]
    cases = results["cases"]
    require([c["id"] for c in cases] == expected_ids, "candidate list/order differs from configuration")
    require(len(cases) == len(expected_ids) >= 3, "insufficient tail-family cases")

    tol = float(cfg["validation"]["geometry_relative_tolerance"])
    min_sm = float(cfg["validation"]["minimum_static_margin_fraction_mac"])
    max_sm = float(cfg["validation"]["maximum_static_margin_fraction_mac"])
    expected_points = int(cfg["analysis"]["alpha_points"])
    expected_cg = float(results["reference_mass"]["gross_cg_x_m"])
    mac = float(wing["mean_aerodynamic_chord_m"])
    tail_ac = float(fixed["aerodynamic_center_x_m"])

    summaries = []
    for case in cases:
        cid = case["id"]
        reported_version = str(case["tool_version"]).strip()
        if reported_version.startswith("OpenVSP "):
            reported_version = reported_version[len("OpenVSP "):].strip()
        require(reported_version == str(cfg["toolchain"]["openvsp_version"]).strip(), f"{cid}: unexpected OpenVSP version {case['tool_version']}")
        mg = case["main_geometry"]
        for key in ("span_m", "area_m2", "root_chord_m", "tip_chord_m"):
            require(relerr(float(mg[key]), float(wing[key])) <= tol, f"{cid}: main-wing {key} drifted: {mg[key]} vs {wing[key]}")
        tg = case["tail_geometry"]
        td = case["tail_design"]
        for key in ("span_m", "area_m2", "root_chord_m", "tip_chord_m"):
            require(relerr(float(tg[key]), float(td[key])) <= tol, f"{cid}: tail {key} differs from generated design: {tg[key]} vs {td[key]}")
        require(relerr(float(case["reference_cg_x_m"]), expected_cg) <= 1e-8, f"{cid}: CG reference drifted")
        require(abs(float(td["quarter_mac_x_m"]) - tail_ac) <= 1e-10, f"{cid}: tail quarter-MAC station drifted")
        require(abs(float(td["area_m2"]) - float(fixed["area_m2"])) <= 1e-10, f"{cid}: tail area drifted")
        require(case["point_count"] == expected_points, f"{cid}: expected {expected_points} alpha points, found {case['point_count']}")
        require(all(math.isfinite(float(p["cl"])) and math.isfinite(float(p["cdi"])) and math.isfinite(float(p["cm_pitch"])) for p in case["points"]), f"{cid}: non-finite polar value")
        require(all(float(p["cdi"]) >= 0.0 for p in case["points"]), f"{cid}: negative induced drag")

        d = case["derived"]
        cl_alpha = float(d["lift_curve_slope_per_rad"])
        cm_alpha = float(d["pitching_moment_slope_per_rad"])
        dcm_dcl = float(d["dcm_dcl"])
        sm = float(d["static_margin_fraction_mac"])
        np_x = float(d["neutral_point_x_m"])
        if cfg["validation"]["require_positive_lift_curve_slope"]:
            require(cl_alpha > 0.0, f"{cid}: lift-curve slope is not positive")
        if cfg["validation"]["require_negative_pitching_moment_slope"]:
            require(cm_alpha < 0.0, f"{cid}: pitching-moment slope is not restoring")
        require(dcm_dcl < 0.0, f"{cid}: dCm/dCL is not restoring")
        require(min_sm <= sm <= max_sm, f"{cid}: static margin {sm:.4f} outside broad computational plausibility gate {min_sm:.3f}..{max_sm:.3f}")
        require(abs(np_x - (expected_cg + sm * mac)) <= 1e-10, f"{cid}: neutral-point conversion is inconsistent")
        require(expected_cg < np_x < tail_ac, f"{cid}: neutral point {np_x:.3f} m is not between CG and tail AC")
        summaries.append(
            {
                "id": cid,
                "aspect_ratio": td["aspect_ratio"],
                "taper_ratio": td["taper_ratio"],
                "tail_span_m": td["span_m"],
                "cl_alpha_per_rad": cl_alpha,
                "cm_alpha_per_rad": cm_alpha,
                "static_margin_fraction_mac": sm,
                "neutral_point_x_m": np_x,
                "zero_moment_alpha_deg_linear_fit": d["zero_moment_alpha_deg_linear_fit"],
            }
        )

    review_lo, review_hi = [float(x) for x in cfg["design_review"]["provisional_static_margin_review_band_fraction_mac"]]
    inside = [s["id"] for s in summaries if review_lo <= s["static_margin_fraction_mac"] <= review_hi]
    ranked = sorted(summaries, key=lambda s: abs(s["static_margin_fraction_mac"] - (review_lo + review_hi) / 2.0))
    summary = {
        "status": cfg["status"],
        "source_phase3a_main_sha": results["source_phase3a_main_sha"],
        "reference_gross_cg_x_m": expected_cg,
        "wing_mac_m": mac,
        "horizontal_tail_volume_coefficient": fixed["horizontal_tail_volume_coefficient"],
        "provisional_review_band_fraction_mac": [review_lo, review_hi],
        "cases_inside_review_band": inside,
        "closest_to_review_band_midpoint_without_promotion": ranked[0]["id"],
        "cases": summaries,
        "boundary": results["boundary"],
    }
    Path("analysis/phase3b/validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("PHASE 3B VALIDATION PASSED")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
