#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHASE 2 VALIDATION FAILED: {message}")


def main() -> None:
    polar_summary = json.loads(Path("analysis/polars/summary.json").read_text())
    bem = json.loads(Path("analysis/phase2/propeller_bem_summary.json").read_text())

    require(len(polar_summary) == 22, f"expected 22 polar cases, found {len(polar_summary)}")
    for case in polar_summary:
        require(case["converged_points"] >= 12, f"{case['airfoil']} Re={case['reynolds']} has too few points")
        require(case["alpha_min"] <= -2.0, f"{case['airfoil']} Re={case['reynolds']} lacks negative-alpha coverage")
        require(case["alpha_max"] >= 7.0, f"{case['airfoil']} Re={case['reynolds']} lacks positive-alpha coverage")
        require(case["cd_min_observed"] > 0.0, f"{case['airfoil']} Re={case['reynolds']} has non-positive Cd")
        require(case["best_section_ld_observed"] > 10.0, f"{case['airfoil']} Re={case['reynolds']} has implausibly poor section L/D")
        require(case["best_section_ld_observed"] < 250.0, f"{case['airfoil']} Re={case['reynolds']} has implausibly high section L/D")

    required_thrust = float(bem["required_aircraft_cruise_thrust_n"])
    result = bem["bem"]
    eta = float(result["propulsive_efficiency"])
    require(float(result["thrust_n"]) >= required_thrust, "BEM seed does not meet cruise thrust")
    require(0.80 <= eta <= 0.95, f"propulsive efficiency {eta:.4f} outside plausibility gate")
    require(250.0 <= float(result["shaft_power_w"]) <= 450.0, "BEM shaft power outside expected cruise range")
    require(0.5 <= float(result["disk_loading_n_m2"]) <= 15.0, "disk loading outside expected low-power propeller range")

    dae51_res = sorted(case["reynolds"] for case in polar_summary if case["airfoil"] == "dae51")
    require(dae51_res, "no DAE51 polars present")
    require(float(result["min_reynolds"]) >= min(dae51_res), "BEM minimum Re below DAE51 polar envelope")
    require(float(result["max_reynolds"]) <= max(dae51_res), "BEM maximum Re above DAE51 polar envelope")

    revised = bem["revised_system"]
    require(0.0 < float(revised["500w_battery_input_boost_climb_m_s"]) < 0.5, "boost climb result outside conservative plausibility gate")
    require(30.0 <= float(revised["one_pack_still_air_range_km"]) <= 70.0, "one-pack range outside expected envelope")

    print("PHASE 2 VALIDATION PASSED")
    print(f"polar cases: {len(polar_summary)}")
    print(f"BEM eta: {eta:.4f}")
    print(f"thrust: {result['thrust_n']:.2f} N required {required_thrust:.2f} N")
    print(f"BEM Re envelope: {result['min_reynolds']:.0f}..{result['max_reynolds']:.0f}")


if __name__ == "__main__":
    main()
