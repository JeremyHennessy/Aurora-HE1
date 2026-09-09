from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .aero import aero_point, speed_for_best_ld, stall_speed
from .config import load_config
from .geometry import chord_at_eta, panel_length_sum, reynolds_number, solve_trapezoidal_wing
from .mass import MassItem, cg_fraction_mac, cg_x, combine_mass_and_cg, total_mass
from .propulsion import approximate_climb_rate_m_s, battery_endurance_hours, cruise_power_split, prop_rpm_from_mid_drive, propeller_advance_ratio, propeller_tip_speed_m_s


def evaluate(config: dict[str, Any]) -> dict[str, Any]:
    env = config["environment"]
    geom = config["geometry"]
    aero_cfg = config["aero"]
    prop_cfg = config["propulsion"]
    mass_cfg = config["mass"]
    wing_cfg = geom["wing"]
    wing = solve_trapezoidal_wing(wing_cfg["span_m"], wing_cfg["area_m2"], wing_cfg["taper_ratio"])
    items = [MassItem(i["name"], i["mass_kg"], i["x_m"]) for i in mass_cfg["items"]]
    empty_mass = total_mass(items)
    empty_cg = cg_x(items)
    gross_mass, gross_cg = combine_mass_and_cg(empty_mass, empty_cg, mass_cfg["reference_pilot_and_personal_gear_kg"], mass_cfg["reference_pilot_cg_x_m"])
    weight_n = gross_mass * env["gravity_m_s2"]
    cruise = aero_point(weight_n=weight_n, rho_kg_m3=env["density_kg_m3"], speed_m_s=aero_cfg["design_cruise_m_s"], wing=wing, cd0=aero_cfg["cd0_profile_plus_parasite"], oswald_efficiency=aero_cfg["oswald_efficiency"])
    vs = stall_speed(weight_n, env["density_kg_m3"], wing.area_m2, aero_cfg["cl_max_clean"])
    v_best_ld = speed_for_best_ld(weight_n, env["density_kg_m3"], wing, aero_cfg["cd0_profile_plus_parasite"], aero_cfg["oswald_efficiency"])
    split = cruise_power_split(aerodynamic_power_w=cruise.aerodynamic_power_w, propulsive_efficiency=aero_cfg["propulsive_efficiency"], human_input_w=prop_cfg["human_cruise_input_w"], final_drive_efficiency=prop_cfg["final_drive_efficiency"], motor_controller_efficiency=prop_cfg["motor_controller_efficiency"])
    endurance_h = battery_endurance_hours(prop_cfg["battery_nominal_wh"], prop_cfg["battery_usable_fraction"], split.battery_input_w)
    range_km = endurance_h * aero_cfg["design_cruise_m_s"] * 3.6
    prop = geom["propeller"]
    geared_rpm = prop_rpm_from_mid_drive(prop_cfg["mid_drive_nominal_output_rpm"], prop_cfg["driver_sprocket_teeth"], prop_cfg["prop_sprocket_teeth"])
    boost_climb = approximate_climb_rate_m_s(weight_n=weight_n, level_prop_shaft_required_w=split.prop_shaft_required_w, human_input_w=prop_cfg["human_cruise_input_w"], battery_input_w=prop_cfg["electric_boost_battery_input_w"], motor_controller_efficiency=prop_cfg["motor_controller_efficiency"], final_drive_efficiency=prop_cfg["final_drive_efficiency"], propulsive_efficiency=aero_cfg["propulsive_efficiency"])
    stations = []
    for station in wing_cfg["airfoil_stations"]:
        eta = station["eta"]
        chord = chord_at_eta(wing, eta)
        stations.append({**station, "semi_span_y_m": eta * wing.span_m / 2.0, "chord_m": chord, "reynolds": reynolds_number(env["density_kg_m3"], aero_cfg["design_cruise_m_s"], chord, env["dynamic_viscosity_pa_s"])})
    tip_speed = propeller_tip_speed_m_s(aero_cfg["design_cruise_m_s"], prop["design_rpm"], prop["diameter_m"])
    return {
        "wing": asdict(wing),
        "panel_length_sum_m": panel_length_sum(wing_cfg["panel_lengths_m"]),
        "empty_mass_kg": empty_mass,
        "empty_cg_x_m": empty_cg,
        "gross_mass_kg": gross_mass,
        "gross_cg_x_m": gross_cg,
        "gross_cg_fraction_mac": cg_fraction_mac(gross_cg, wing_cfg["root_le_x_m"], wing.mean_aerodynamic_chord_m),
        "stall_speed_m_s": vs,
        "stall_speed_km_h": vs * 3.6,
        "cruise": asdict(cruise),
        "best_ld_speed_m_s": v_best_ld,
        "best_ld_speed_km_h": v_best_ld * 3.6,
        "power_split": asdict(split),
        "battery_endurance_h": endurance_h,
        "still_air_supported_range_km": range_km,
        "final_drive_ratio": prop_cfg["driver_sprocket_teeth"] / prop_cfg["prop_sprocket_teeth"],
        "prop_rpm_from_90rpm_mid_drive": geared_rpm,
        "prop_advance_ratio_at_design": propeller_advance_ratio(aero_cfg["design_cruise_m_s"], prop["design_rpm"], prop["diameter_m"]),
        "prop_tip_speed_m_s": tip_speed,
        "prop_tip_mach": tip_speed / env["speed_of_sound_m_s"],
        "prop_ground_clearance_m": prop["shaft_center_height_m"] - prop["diameter_m"] / 2.0,
        "boost_climb_rate_estimate_m_s": boost_climb,
        "boost_climb_rate_estimate_ft_min": boost_climb * 196.850394,
        "airfoil_stations": stations
    }


def evaluate_file(path: str | Path) -> dict[str, Any]:
    return evaluate(load_config(path))
