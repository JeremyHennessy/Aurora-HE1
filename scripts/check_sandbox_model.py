#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"SANDBOX VALIDATION FAILED: {message}")


def close(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def main() -> None:
    cfg = json.loads(Path("config/he1_baseline.json").read_text())
    out = json.loads(Path("outputs/design_summary.json").read_text())
    snap = json.loads(Path("viewer/data/verified_snapshot.json").read_text())
    model = json.loads(Path("viewer/data/sandbox_model.json").read_text())

    require(model["meta"]["source_main_commit"] == "1a244282d3fc6b84ee9df5c62ee32efe3c03ec24", "sandbox source checkpoint changed unexpectedly")
    require(close(model["environment"]["density_kg_m3"], cfg["environment"]["density_kg_m3"]), "density differs from baseline config")
    require(close(model["environment"]["gravity_m_s2"], cfg["environment"]["gravity_m_s2"]), "gravity differs from baseline config")
    require(close(model["wing"]["span_m"], out["wing"]["span_m"]), "wing span differs from tracked output")
    require(close(model["wing"]["area_m2"], out["wing"]["area_m2"]), "wing area differs from tracked output")
    require(close(model["wing"]["aspect_ratio"], out["wing"]["aspect_ratio"]), "aspect ratio differs from tracked output")
    require(close(model["wing"]["mean_aerodynamic_chord_m"], out["wing"]["mean_aerodynamic_chord_m"]), "MAC differs from tracked output")
    require(close(model["mass"]["empty_mass_kg"], out["empty_mass_kg"]), "empty mass differs from tracked output")
    require(close(model["mass"]["empty_cg_x_m"], out["empty_cg_x_m"]), "empty CG differs from tracked output")
    require(close(model["aero"]["oswald_efficiency"], cfg["aero"]["oswald_efficiency"]), "Oswald efficiency differs from baseline")
    require(close(model["aero"]["cd0"], cfg["aero"]["cd0_profile_plus_parasite"]), "CD0 differs from baseline")
    require(close(model["aero"]["cl_max_clean"], cfg["aero"]["cl_max_clean"]), "CLmax differs from baseline")
    require(close(model["propulsion"]["final_drive_efficiency"], cfg["propulsion"]["final_drive_efficiency"]), "final-drive efficiency differs from baseline")
    require(close(model["propulsion"]["motor_controller_efficiency"], cfg["propulsion"]["motor_controller_efficiency"]), "motor/controller efficiency differs from baseline")

    phase2 = next(p for p in model["propulsion"]["configurations"] if p["id"] == "phase2_reference")
    require(close(phase2["propulsive_efficiency"], snap["phase2"]["bem"]["propulsive_efficiency"]), "Phase 2 efficiency differs from verified snapshot")
    phase2b = next(p for p in model["propulsion"]["configurations"] if p["id"] == "phase2b_candidate")
    require(close(phase2b["propulsive_efficiency"], snap["phase2b"]["selected_design"]["result"]["propulsive_efficiency"]), "Phase 2B efficiency differs from verified snapshot")
    require(close(phase2b["diameter_m"], snap["phase2b"]["selected_design"]["diameter_m"]), "Phase 2B diameter differs from verified snapshot")

    d = model["defaults"]
    em = model["mass"]["empty_mass_kg"]
    ex = model["mass"]["empty_cg_x_m"]
    gross = em + d["pilot_and_gear_kg"] + d["extra_mass_kg"]
    cg_x = (em * ex + d["pilot_and_gear_kg"] * d["pilot_cg_x_m"] + d["extra_mass_kg"] * d["extra_mass_x_m"]) / gross
    cg_frac = (cg_x - model["wing"]["root_le_x_m"]) / model["wing"]["mean_aerodynamic_chord_m"]
    rho = model["environment"]["density_kg_m3"]
    g = model["environment"]["gravity_m_s2"]
    speed = d["speed_m_s"]
    area = model["wing"]["area_m2"]
    weight = gross * g
    q = 0.5 * rho * speed**2
    cl = weight / (q * area)
    k = 1.0 / (math.pi * model["aero"]["oswald_efficiency"] * model["wing"]["aspect_ratio"])
    cdi = k * cl**2
    cd = model["aero"]["cd0"] + cdi
    drag = q * area * cd
    aero_power = drag * speed
    stall = math.sqrt(2.0 * weight / (rho * area * model["aero"]["cl_max_clean"]))
    eta = phase2["propulsive_efficiency"]
    fd = model["propulsion"]["final_drive_efficiency"]
    mc = model["propulsion"]["motor_controller_efficiency"]
    shaft = aero_power / eta
    human_shaft = d["human_input_w"] * fd
    electric_shaft = max(0.0, shaft - human_shaft)
    battery_input = electric_shaft / fd / mc
    endurance = d["usable_battery_wh"] / battery_input
    range_km = endurance * speed * 3.6
    available_shaft = (d["human_input_w"] + d["boost_battery_input_w"] * mc) * fd
    climb = max(0.0, available_shaft - shaft) * eta / weight

    ref = model["reference_results"]
    checks = {
        "gross mass": (gross, ref["gross_mass_kg"]),
        "gross CG x": (cg_x, ref["gross_cg_x_m"]),
        "gross CG fraction": (cg_frac, ref["gross_cg_fraction_mac"]),
        "stall speed": (stall, ref["stall_speed_m_s"]),
        "drag": (drag, ref["drag_n"]),
        "L/D": (weight / drag, ref["lift_to_drag"]),
        "aero power": (aero_power, ref["aerodynamic_power_w"]),
        "shaft power": (shaft, ref["prop_shaft_required_w"]),
        "battery input": (battery_input, ref["battery_input_w"]),
        "endurance": (endurance, ref["battery_endurance_h"]),
        "range": (range_km, ref["still_air_range_km"]),
        "climb": (climb, ref["boost_climb_m_s"]),
        "climb fpm": (climb * 196.850394, ref["boost_climb_ft_min"]),
    }
    for name, (actual, expected) in checks.items():
        require(close(actual, expected, 1e-8), f"default scenario {name} mismatch: {actual} != {expected}")

    require(Path("viewer/sandbox.html").is_file() and Path("viewer/sandbox.html").stat().st_size > 5000, "sandbox page missing or unexpectedly small")
    html = Path("viewer/sandbox.html").read_text()
    require("UNVERIFIED SCENARIO" in html, "sandbox lacks required unverified-scenario warning")
    require("sandbox_model.json" in html, "sandbox does not load provenance-locked model")
    require("Verified engineering viewer" in html, "sandbox lacks return path to verified viewer")

    print("SANDBOX VALIDATION PASSED")
    print(f"default gross mass: {gross:.1f} kg")
    print(f"default drag: {drag:.4f} N")
    print(f"default shaft power: {shaft:.3f} W")
    print(f"default range: {range_km:.3f} km")
    print(f"default climb: {climb * 196.850394:.3f} ft/min")


if __name__ == "__main__":
    main()
