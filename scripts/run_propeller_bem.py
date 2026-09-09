#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from aurora_he1.bem import optimize_seed_blade
from aurora_he1.config import load_config
from aurora_he1.model import evaluate
from aurora_he1.polars import PolarFamily
from aurora_he1.propulsion import approximate_climb_rate_m_s, battery_endurance_hours, cruise_power_split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/he1_baseline.json")
    parser.add_argument("--polars", default="analysis/polars")
    parser.add_argument("--output", default="analysis/phase2")
    args = parser.parse_args()

    config = load_config(args.config)
    baseline = evaluate(config)
    env = config["environment"]
    aero_cfg = config["aero"]
    prop_cfg = config["propulsion"]
    prop = config["geometry"]["propeller"]
    polar = PolarFamily.from_directory(args.polars, "dae51")
    required_thrust = baseline["cruise"]["drag_n"]
    stations, result, controls = optimize_seed_blade(
        polar=polar,
        blade_count=prop["blade_count"],
        diameter_m=prop["diameter_m"],
        rpm=prop["design_rpm"],
        speed_m_s=aero_cfg["design_cruise_m_s"],
        density_kg_m3=env["density_kg_m3"],
        dynamic_viscosity_pa_s=env["dynamic_viscosity_pa_s"],
        required_thrust_n=required_thrust,
    )
    revised_split = cruise_power_split(
        aerodynamic_power_w=baseline["cruise"]["aerodynamic_power_w"],
        propulsive_efficiency=result.propulsive_efficiency,
        human_input_w=prop_cfg["human_cruise_input_w"],
        final_drive_efficiency=prop_cfg["final_drive_efficiency"],
        motor_controller_efficiency=prop_cfg["motor_controller_efficiency"],
    )
    endurance = battery_endurance_hours(prop_cfg["battery_nominal_wh"], prop_cfg["battery_usable_fraction"], revised_split.battery_input_w)
    revised_range = endurance * aero_cfg["design_cruise_m_s"] * 3.6
    weight_n = baseline["gross_mass_kg"] * env["gravity_m_s2"]
    boost_climb = approximate_climb_rate_m_s(
        weight_n=weight_n,
        level_prop_shaft_required_w=revised_split.prop_shaft_required_w,
        human_input_w=prop_cfg["human_cruise_input_w"],
        battery_input_w=prop_cfg["electric_boost_battery_input_w"],
        motor_controller_efficiency=prop_cfg["motor_controller_efficiency"],
        final_drive_efficiency=prop_cfg["final_drive_efficiency"],
        propulsive_efficiency=result.propulsive_efficiency,
    )
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        "status": "PHASE 2 COMPUTATIONAL ESTIMATE / NOT FOR CONSTRUCTION",
        "required_aircraft_cruise_thrust_n": required_thrust,
        "baseline_assumed_propulsive_efficiency": aero_cfg["propulsive_efficiency"],
        "bem": {
            "target_alpha_deg": controls["target_alpha_deg"],
            "chord_scale": controls["chord_scale"],
            "thrust_n": result.thrust_n,
            "torque_n_m": result.torque_n_m,
            "shaft_power_w": result.shaft_power_w,
            "propulsive_efficiency": result.propulsive_efficiency,
            "advance_ratio": result.advance_ratio,
            "disk_loading_n_m2": result.disk_loading_n_m2,
            "min_reynolds": result.min_reynolds,
            "max_reynolds": result.max_reynolds
        },
        "revised_system": {
            "prop_shaft_cruise_requirement_w": revised_split.prop_shaft_required_w,
            "battery_input_cruise_w": revised_split.battery_input_w,
            "one_pack_endurance_h": endurance,
            "one_pack_still_air_range_km": revised_range,
            "500w_battery_input_boost_climb_m_s": boost_climb,
            "500w_battery_input_boost_climb_ft_min": boost_climb * 196.850394
        },
        "caution": "BEM accuracy depends on XFOIL section polars and seed chord/twist parameterization; no structural propeller sizing or physical validation is implied."
    }
    (out / "propeller_bem_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    with (out / "propeller_stations.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["radius_m", "r_over_R", "chord_m", "beta_deg"])
        radius = prop["diameter_m"] / 2.0
        for station in stations:
            writer.writerow([f"{station.radius_m:.6f}", f"{station.radius_m/radius:.6f}", f"{station.chord_m:.6f}", f"{station.beta_deg:.6f}"])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
