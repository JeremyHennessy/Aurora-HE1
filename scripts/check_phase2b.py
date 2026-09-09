#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"PHASE 2B VALIDATION FAILED: {message}")


def main() -> None:
    summary = json.loads(Path("analysis/phase2b/propeller_family_summary.json").read_text())
    grid = summary["family_grid"]
    installation = summary["installation_constraint"]
    selected = summary["selected_design"]
    selected_result = selected["result"]
    candidates = summary["candidates"]

    require(grid["candidate_count"] >= 20, f"expected broad family coverage, found {grid['candidate_count']} candidates")
    require(abs(installation["max_diameter_for_clearance_m"] - 2.9) < 1e-9, "current geometry should cap target-clearance diameter at 2.90 m")
    oversized = [c for c in candidates if c["diameter_m"] >= 3.0]
    require(oversized, "missing 3.0-3.2 m aerodynamic candidates")
    require(all(not c["ground_clearance_ok"] for c in oversized), "oversized candidates must be flagged against current ground clearance")

    require(selected["ground_clearance_ok"], "selected design violates ground-clearance target")
    require(selected["polar_envelope_ok"], "selected design leaves trusted DAE51 polar envelope")
    require(selected["power_band_ok"], "selected design leaves 250-800 W shaft-power trade band")
    require(selected_result["thrust_n"] >= 31.0, "selected design lacks design-point thrust")
    require(0.70 <= selected_result["propulsive_efficiency"] <= 0.98, "selected design efficiency outside plausible computational gate")
    require(selected_result["min_reynolds"] >= 75000.0, "selected design Reynolds below DAE51 envelope")
    require(selected_result["max_reynolds"] <= 400000.0, "selected design Reynolds above DAE51 envelope")
    require(selected_result["min_alpha_deg"] >= -2.0, "selected design alpha below trusted coverage")
    require(selected_result["max_alpha_deg"] <= 7.0, "selected design alpha above trusted coverage")
    require(selected["diameter_m"] <= installation["max_diameter_for_clearance_m"] + 1e-9, "selected diameter exceeds installation limit")

    baseline_ref = summary["baseline_reference_2p85m_130rpm"]
    require(baseline_ref is not None, "missing exact 2.85 m / 130 rpm comparison point")
    require(selected_result["shaft_power_w"] <= baseline_ref["result"]["shaft_power_w"] * 1.05, "family selection is materially worse than the Phase 2 reference")

    solved = [row for row in summary["operating_envelope"] if row["solution"] is not None]
    require(len(solved) >= 5, f"only {len(solved)} of 7 flight-speed points have trusted solutions")
    design_rows = [row for row in solved if abs(row["speed_m_s"] - 9.5) < 1e-9]
    require(design_rows, "9.5 m/s design point is not solved")
    for row in solved:
        solution = row["solution"]
        result = solution["result"]
        require(solution["polar_envelope_ok"], f"{row['speed_m_s']} m/s solution leaves trusted polar envelope")
        require(solution["thrust_margin_n"] >= 0.0, f"{row['speed_m_s']} m/s solution lacks required thrust")
        require(0.0 < result["propulsive_efficiency"] <= 1.0, f"{row['speed_m_s']} m/s efficiency invalid")
        require(result["shaft_power_w"] > 0.0, f"{row['speed_m_s']} m/s shaft power invalid")

    require(summary["static_thrust"]["supported"] is False, "static thrust must not be claimed by forward-flight BEM")
    print("PHASE 2B VALIDATION PASSED")
    print(f"family candidates: {grid['candidate_count']}")
    print(f"selected: D={selected['diameter_m']:.2f} m at {selected['design_rpm']:.0f} rpm")
    print(f"eta: {selected_result['propulsive_efficiency']:.4f}")
    print(f"shaft power: {selected_result['shaft_power_w']:.1f} W")
    print(f"trusted off-design points: {len(solved)}/7")


if __name__ == "__main__":
    main()
