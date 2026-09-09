from __future__ import annotations

from typing import Any


def validate(config: dict[str, Any], result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    wing_cfg = config["geometry"]["wing"]
    prop = config["geometry"]["propeller"]
    mass_cfg = config["mass"]
    aero_cfg = config["aero"]
    if abs(result["panel_length_sum_m"] - wing_cfg["span_m"]) > 1e-9:
        errors.append("wing panel lengths do not sum to wingspan")
    if result["empty_mass_kg"] <= 0:
        errors.append("empty mass is not positive")
    if result["gross_mass_kg"] <= result["empty_mass_kg"]:
        errors.append("gross mass must exceed empty mass")
    if result["cruise"]["speed_m_s"] < 1.15 * result["stall_speed_m_s"]:
        errors.append("design cruise is less than 1.15x clean stall speed")
    cg_lo, cg_hi = mass_cfg["provisional_cg_range_fraction_mac"]
    if not cg_lo <= result["gross_cg_fraction_mac"] <= cg_hi:
        errors.append("reference gross CG is outside provisional MAC range")
    if result["prop_ground_clearance_m"] < prop["minimum_target_ground_clearance_m"]:
        errors.append("propeller ground clearance is below target")
    if result["prop_tip_mach"] >= 0.30:
        errors.append("propeller tip Mach exceeds preliminary low-Mach design gate")
    if result["power_split"]["battery_input_w"] > config["propulsion"]["electric_boost_battery_input_w"]:
        errors.append("cruise battery demand exceeds configured short-duration boost input")
    if aero_cfg["cl_max_clean"] <= 0:
        errors.append("CLmax must be positive")
    return errors
