#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHASE 2C VALIDATION FAILED: {message}")


def main() -> None:
    cfg = json.loads(Path("config/phase2c_transition_sensitivity.json").read_text())
    summary = json.loads(Path("analysis/phase2c/transition_bem_summary.json").read_text())
    verified = json.loads(Path("viewer/data/verified_snapshot.json").read_text())
    polar_summary = json.loads(Path("analysis/phase2c/polars/summary.json").read_text())

    require(len(cfg["cases"]) == 5, "expected five transition-sensitivity cases")
    require(len(summary["cases"]) == 5, "BEM summary does not contain five cases")
    require(len(polar_summary) == 25, f"expected 25 XFOIL sensitivity polars, found {len(polar_summary)}")
    require(any("not calibrated" in text.lower() for text in summary["analysis_boundary"]), "analysis boundary must state that disturbance proxies are not calibrated physical roughness")

    clean = next(row for row in summary["cases"] if row["scenario_id"] == "clean_n9")
    clean_result = clean["fixed_130rpm"]["result"]
    phase2 = verified["phase2"]["bem"]
    require(clean["fixed_130rpm"]["polar_envelope_ok"], "clean reference leaves generated polar envelope")
    require(clean_result["thrust_n"] >= summary["source_baseline"]["required_cruise_thrust_n"], "clean reference no longer meets cruise thrust")
    require(abs(clean_result["thrust_n"] - phase2["thrust_n"]) <= 0.01 * phase2["thrust_n"], "Phase 2C clean thrust does not reproduce verified Phase 2 within 1%")
    require(abs(clean_result["shaft_power_w"] - phase2["shaft_power_w"]) <= 0.01 * phase2["shaft_power_w"], "Phase 2C clean shaft power does not reproduce verified Phase 2 within 1%")
    require(abs(clean_result["propulsive_efficiency"] - phase2["propulsive_efficiency"]) <= 0.01, "Phase 2C clean efficiency does not reproduce verified Phase 2")
    require(clean["thrust_recovery"] is not None, "clean reference has no thrust-recovery solution")

    ids = {row["scenario_id"] for row in summary["cases"]}
    require(ids == {case["id"] for case in cfg["cases"]}, "scenario IDs differ between configuration and analysis")
    for row in summary["cases"]:
        fixed = row["fixed_130rpm"]["result"]
        require(fixed["shaft_power_w"] > 0.0, f"{row['scenario_id']}: non-positive shaft power")
        require(0.0 < fixed["propulsive_efficiency"] <= 1.0, f"{row['scenario_id']}: invalid propulsive efficiency")
        require(fixed["thrust_n"] > 0.0, f"{row['scenario_id']}: non-positive thrust")
        require(row["section_re150k"]["alpha4"]["cd"] > 0.0, f"{row['scenario_id']}: invalid Re150k alpha4 CD")
        require(row["section_re150k"]["alpha6"]["cd"] > 0.0, f"{row['scenario_id']}: invalid Re150k alpha6 CD")
        recovery = row["thrust_recovery"]
        if recovery is not None:
            rr = recovery["result"]
            require(rr["thrust_n"] >= summary["source_baseline"]["required_cruise_thrust_n"], f"{row['scenario_id']}: recovery solution does not meet thrust")
            require(0.0 < rr["propulsive_efficiency"] <= 1.0, f"{row['scenario_id']}: recovery efficiency invalid")
            require(rr["shaft_power_w"] > 0.0, f"{row['scenario_id']}: recovery shaft power invalid")
            require(recovery["system"]["battery_input_w"] >= 0.0, f"{row['scenario_id']}: recovery battery input invalid")

    forced = [row for row in summary["cases"] if row["scenario_id"].startswith("forced_")]
    require(len(forced) == 2 and all(row["forced_transition"] is not None for row in forced), "forced-transition cases are not explicitly identified")
    ncrit = {row["scenario_id"]: row["ncrit"] for row in summary["cases"]}
    require(ncrit["clean_n9"] == 9.0 and ncrit["disturbed_n6"] == 6.0 and ncrit["severe_n3"] == 3.0, "Ncrit scenario values changed")

    print("PHASE 2C VALIDATION PASSED")
    for row in summary["cases"]:
        fixed = row["fixed_130rpm"]["result"]
        recovery = row["thrust_recovery"]
        print(
            f"{row['scenario_id']}: fixed eta={fixed['propulsive_efficiency']:.4f}, "
            f"thrust={fixed['thrust_n']:.2f} N, "
            f"recovery={None if recovery is None else f'{recovery['rpm']:.0f} rpm / {recovery['result']['shaft_power_w']:.1f} W'}"
        )


if __name__ == "__main__":
    main()
