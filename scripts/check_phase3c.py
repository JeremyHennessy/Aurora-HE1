#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(ok: bool, message: str) -> None:
    if not ok:
        raise SystemExit(f"PHASE 3C VALIDATION FAILED: {message}")


def relerr(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


def linear_fit(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    xm = sum(xs) / len(xs)
    ym = sum(ys) / len(ys)
    denom = sum((x - xm) ** 2 for x in xs)
    require(denom > 0.0, "tail-volume regression has zero x variance")
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / denom
    intercept = ym - slope * xm
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - ym) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return slope, intercept, r2


def main() -> None:
    cfg = json.loads(Path("config/phase3c_tail_volume_trade.json").read_text())
    results = json.loads(Path("analysis/phase3c/results.json").read_text())
    cases = results["cases"]
    by_id = {c["id"]: c for c in cases}
    wing = results["main_wing"]
    mac = float(wing["mean_aerodynamic_chord_m"])
    baseline_cg = float(results["reference_mass"]["gross_cg_x_m"])
    tol = float(cfg["validation"]["geometry_relative_tolerance"])
    expected_points = int(cfg["analysis"]["alpha_points"])

    expected_sanity = ["WING_ONLY", "REF_BASE", "REF_CG_FWD", "REF_CG_AFT", "REF_FINE"]
    areas = [float(x) for x in cfg["trade_grid"]["tail_area_m2"]]
    acs = [float(x) for x in cfg["trade_grid"]["tail_ac_x_m"]]
    expected_grid = [f"GRID_A{int(round(a * 100)):03d}_X{int(round(x * 100)):03d}" for a in areas for x in acs]
    expected_ids = expected_sanity + expected_grid
    require([c["id"] for c in cases] == expected_ids, "case list/order differs from configuration")
    require(len(cases) == 20 and len(expected_grid) == 15, "Phase 3C must contain five sanity cases plus fifteen trade cases")

    for case in cases:
        cid = case["id"]
        version = str(case["tool_version"]).strip()
        if version.startswith("OpenVSP "):
            version = version[len("OpenVSP "):].strip()
        require(version == str(cfg["toolchain"]["openvsp_version"]), f"{cid}: unexpected OpenVSP version {case['tool_version']}")
        mg = case["main_geometry"]
        for key in ("span_m", "area_m2", "root_chord_m", "tip_chord_m"):
            require(relerr(float(mg[key]), float(wing[key])) <= tol, f"{cid}: main-wing {key} drifted")
        require(case["point_count"] == expected_points, f"{cid}: expected {expected_points} polar points, got {case['point_count']}")
        require(all(math.isfinite(float(p[k])) for p in case["points"] for k in ("alpha_deg", "cl", "cdi", "cm_pitch")), f"{cid}: non-finite native-polar value")
        require(all(float(p["cdi"]) >= 0.0 for p in case["points"]), f"{cid}: negative induced drag")
        require(abs(float(case["reference_cg_x_m"]) - float(next(c for c in json.loads(Path('analysis/phase3c/manifest.json').read_text())["cases"] if c["id"] == cid)["reference_cg_x_m"])) <= 1e-9, f"{cid}: CG log value differs from generated case")
        d = case["derived"]
        for key in ("lift_curve_slope_per_rad", "pitching_moment_slope_per_rad", "dcm_dcl", "static_margin_fraction_mac", "neutral_point_x_m"):
            require(math.isfinite(float(d[key])), f"{cid}: non-finite derived {key}")
        if cfg["validation"]["require_positive_lift_curve_slope"]:
            require(float(d["lift_curve_slope_per_rad"]) > 0.0, f"{cid}: lift-curve slope is not positive")
        if case["include_tail"]:
            td = case["tail_design"]
            tg = case["tail_geometry"]
            require(tg is not None, f"{cid}: tail geometry missing")
            for key in ("span_m", "area_m2", "root_chord_m", "tip_chord_m"):
                require(relerr(float(tg[key]), float(td[key])) <= tol, f"{cid}: tail {key} differs from generated geometry")
        else:
            require(case["tail_design"] is None and case["tail_geometry"] is None, f"{cid}: wing-only case unexpectedly contains a tail")

    # Wing-only anchor: do not require stability sign, only a physically local aerodynamic center.
    wing_only = by_id["WING_ONLY"]["derived"]
    wing_np = float(wing_only["neutral_point_x_m"])
    wing_root_le = float(wing["root_le_x_m"])
    require(wing_root_le - 0.2 <= wing_np <= wing_root_le + float(wing["root_chord_m"]) + 0.2, f"wing-only neutral point {wing_np:.3f} m is not local to the main wing")
    require(-0.25 <= float(wing_only["static_margin_fraction_mac"]) <= 0.25, "wing-only static margin is implausibly large")

    # Exact Phase 3B reference reproduction.
    ref = by_id["REF_BASE"]["derived"]
    expected_sm = float(cfg["validation"]["phase3b_reference_static_margin"])
    expected_np = float(cfg["validation"]["phase3b_reference_neutral_point_x_m"])
    require(abs(float(ref["static_margin_fraction_mac"]) - expected_sm) <= float(cfg["validation"]["reference_static_margin_absolute_tolerance"]), f"Phase 3B static margin did not reproduce: {ref['static_margin_fraction_mac']} vs {expected_sm}")
    require(abs(float(ref["neutral_point_x_m"]) - expected_np) <= float(cfg["validation"]["reference_neutral_point_tolerance_m"]), f"Phase 3B neutral point did not reproduce: {ref['neutral_point_x_m']} vs {expected_np}")

    # Moment-reference/sign sanity: changing only Xcg must leave neutral point invariant.
    np_tol = float(cfg["validation"]["neutral_point_cg_invariance_tolerance_fraction_mac"]) * mac
    shift_tol = float(cfg["validation"]["cg_shift_static_margin_tolerance"])
    ref_sm = float(ref["static_margin_fraction_mac"])
    ref_np = float(ref["neutral_point_x_m"])
    cg_checks = []
    for cid in ("REF_CG_FWD", "REF_CG_AFT"):
        c = by_id[cid]
        offset = float(c["cg_offset_fraction_mac"])
        d = c["derived"]
        observed_np = float(d["neutral_point_x_m"])
        observed_sm = float(d["static_margin_fraction_mac"])
        predicted_sm = ref_sm - offset
        require(abs(observed_np - ref_np) <= np_tol, f"{cid}: neutral point moved {observed_np-ref_np:+.5f} m when only Xcg changed")
        require(abs(observed_sm - predicted_sm) <= shift_tol, f"{cid}: static-margin change does not follow Xcg reference shift: observed {observed_sm:.4f}, predicted {predicted_sm:.4f}")
        cg_checks.append({"id": cid, "cg_offset_fraction_mac": offset, "static_margin": observed_sm, "neutral_point_x_m": observed_np})

    # Mesh sensitivity at the Phase 3B reference geometry.
    fine = by_id["REF_FINE"]["derived"]
    mesh_sm_delta = abs(float(fine["static_margin_fraction_mac"]) - ref_sm)
    mesh_np_delta = abs(float(fine["neutral_point_x_m"]) - ref_np)
    require(mesh_sm_delta <= float(cfg["validation"]["mesh_static_margin_absolute_tolerance"]), f"fine-mesh static margin changed by {mesh_sm_delta:.4f}")
    require(mesh_np_delta <= float(cfg["validation"]["mesh_neutral_point_tolerance_fraction_mac"]) * mac, f"fine-mesh neutral point changed by {mesh_np_delta:.5f} m")

    # Grid is evidence, not a pass/fail target. Keep only broad physical/numerical gates here.
    grid = [by_id[cid] for cid in expected_grid]
    min_sm = float(cfg["validation"]["minimum_grid_static_margin_fraction_mac"])
    max_sm = float(cfg["validation"]["maximum_grid_static_margin_fraction_mac"])
    for case in grid:
        d = case["derived"]
        sm = float(d["static_margin_fraction_mac"])
        require(min_sm <= sm <= max_sm, f"{case['id']}: grid static margin {sm:.4f} outside broad plausibility gate")
        require(float(case["tail_design"]["horizontal_tail_volume_coefficient"]) > 0.0, f"{case['id']}: non-positive tail volume")

    review_lo, review_hi = [float(x) for x in cfg["design_review"]["provisional_static_margin_review_band_fraction_mac"]]
    grid_summary = [{
        "id": c["id"],
        "tail_area_m2": float(c["tail_design"]["area_m2"]),
        "tail_ac_x_m": float(c["tail_design"]["quarter_mac_x_m"]),
        "tail_volume_coefficient": float(c["tail_design"]["horizontal_tail_volume_coefficient"]),
        "static_margin_fraction_mac": float(c["derived"]["static_margin_fraction_mac"]),
        "neutral_point_x_m": float(c["derived"]["neutral_point_x_m"]),
        "inside_review_band": review_lo <= float(c["derived"]["static_margin_fraction_mac"]) <= review_hi,
    } for c in grid]
    inside = [x for x in grid_summary if x["inside_review_band"]]
    midpoint = (review_lo + review_hi) / 2.0
    ranked = sorted(grid_summary, key=lambda x: abs(x["static_margin_fraction_mac"] - midpoint))
    slope, intercept, r2 = linear_fit([x["tail_volume_coefficient"] for x in grid_summary], [x["static_margin_fraction_mac"] for x in grid_summary])

    summary = {
        "status": cfg["status"],
        "reference_gross_cg_x_m": baseline_cg,
        "wing_mac_m": mac,
        "wing_only": {"static_margin_fraction_mac": float(wing_only["static_margin_fraction_mac"]), "neutral_point_x_m": wing_np},
        "phase3b_reference_reproduction": {"static_margin_fraction_mac": ref_sm, "neutral_point_x_m": ref_np},
        "cg_reference_checks": cg_checks,
        "mesh_sensitivity": {"fine_static_margin_fraction_mac": float(fine["static_margin_fraction_mac"]), "absolute_static_margin_delta": mesh_sm_delta, "neutral_point_delta_m": mesh_np_delta},
        "provisional_review_band_fraction_mac": [review_lo, review_hi],
        "grid_case_count": len(grid_summary),
        "cases_inside_review_band": inside,
        "closest_to_band_midpoint_without_promotion": ranked[0],
        "grid_tail_volume_regression": {"static_margin_per_tail_volume": slope, "intercept": intercept, "r_squared": r2},
        "grid": grid_summary,
        "boundary": results["boundary"],
    }
    Path("analysis/phase3c/validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print("PHASE 3C VALIDATION PASSED")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
