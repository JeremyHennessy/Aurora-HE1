#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from aurora_he1.aero import aero_point
from aurora_he1.bem import solve_bem
from aurora_he1.config import load_config
from aurora_he1.geometry import solve_trapezoidal_wing
from aurora_he1.model import evaluate
from aurora_he1.polars import PolarFamily
from aurora_he1.propeller_trade import candidate_to_dict, design_seed_family, operating_point_to_dict, polar_envelope_ok, select_operating_point


DIAMETERS_M = (2.50, 2.70, 2.85, 2.90, 3.00, 3.20)
DESIGN_RPMS = (110.0, 120.0, 130.0, 140.0, 150.0)
OPERATING_RPMS = tuple(float(v) for v in range(90, 181, 10))
SPEEDS_M_S = (8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0)
TRUSTED_RE = (75000.0, 400000.0)
TRUSTED_ALPHA_DEG = (-2.0, 7.0)
SHAFT_POWER_BAND_W = (250.0, 800.0)


def theoretical_gearing(rpm: float, *, mid_drive_rpm: float, driver_teeth: int) -> dict[str, float]:
    ratio = rpm / mid_drive_rpm
    return {
        "required_final_drive_ratio": ratio,
        "theoretical_driven_teeth_for_configured_driver": driver_teeth / ratio,
    }


def main() -> None:
    config = load_config("config/he1_baseline.json")
    baseline = evaluate(config)
    env = config["environment"]
    aero_cfg = config["aero"]
    prop_cfg = config["propulsion"]
    geom = config["geometry"]
    wing_cfg = geom["wing"]
    prop_cfg_geom = geom["propeller"]
    wing = solve_trapezoidal_wing(wing_cfg["span_m"], wing_cfg["area_m2"], wing_cfg["taper_ratio"])
    polar = PolarFamily.from_directory("analysis/polars", "dae51")

    design_speed = aero_cfg["design_cruise_m_s"]
    required_design_thrust = baseline["cruise"]["drag_n"]
    candidates, selected = design_seed_family(
        polar=polar,
        blade_count=prop_cfg_geom["blade_count"],
        diameters_m=DIAMETERS_M,
        design_rpms=DESIGN_RPMS,
        design_speed_m_s=design_speed,
        density_kg_m3=env["density_kg_m3"],
        dynamic_viscosity_pa_s=env["dynamic_viscosity_pa_s"],
        required_thrust_n=required_design_thrust,
        shaft_center_height_m=prop_cfg_geom["shaft_center_height_m"],
        minimum_ground_clearance_m=prop_cfg_geom["minimum_target_ground_clearance_m"],
        trusted_min_reynolds=TRUSTED_RE[0],
        trusted_max_reynolds=TRUSTED_RE[1],
        trusted_min_alpha_deg=TRUSTED_ALPHA_DEG[0],
        trusted_max_alpha_deg=TRUSTED_ALPHA_DEG[1],
        minimum_power_w=SHAFT_POWER_BAND_W[0],
        maximum_power_w=SHAFT_POWER_BAND_W[1],
    )
    selected_candidate, selected_stations = selected

    candidate_rows = []
    baseline_reference = None
    for candidate, _stations in candidates:
        row = candidate_to_dict(candidate)
        row.update(theoretical_gearing(
            candidate.design_rpm,
            mid_drive_rpm=prop_cfg["mid_drive_nominal_output_rpm"],
            driver_teeth=prop_cfg["driver_sprocket_teeth"],
        ))
        candidate_rows.append(row)
        if abs(candidate.diameter_m - 2.85) < 1e-9 and abs(candidate.design_rpm - 130.0) < 1e-9:
            baseline_reference = row

    operating_envelope = []
    weight_n = baseline["gross_mass_kg"] * env["gravity_m_s2"]
    for speed in SPEEDS_M_S:
        aircraft = aero_point(
            weight_n=weight_n,
            rho_kg_m3=env["density_kg_m3"],
            speed_m_s=speed,
            wing=wing,
            cd0=aero_cfg["cd0_profile_plus_parasite"],
            oswald_efficiency=aero_cfg["oswald_efficiency"],
        )
        point = select_operating_point(
            stations=selected_stations,
            polar=polar,
            blade_count=prop_cfg_geom["blade_count"],
            diameter_m=selected_candidate.diameter_m,
            speed_m_s=speed,
            rpm_values=OPERATING_RPMS,
            density_kg_m3=env["density_kg_m3"],
            dynamic_viscosity_pa_s=env["dynamic_viscosity_pa_s"],
            required_thrust_n=aircraft.drag_n,
            trusted_min_reynolds=TRUSTED_RE[0],
            trusted_max_reynolds=TRUSTED_RE[1],
            trusted_min_alpha_deg=TRUSTED_ALPHA_DEG[0],
            trusted_max_alpha_deg=TRUSTED_ALPHA_DEG[1],
            minimum_power_w=SHAFT_POWER_BAND_W[0],
            maximum_power_w=SHAFT_POWER_BAND_W[1],
        )
        operating_envelope.append({
            "speed_m_s": speed,
            "aircraft": {
                "cl": aircraft.cl,
                "drag_n": aircraft.drag_n,
                "aerodynamic_power_w": aircraft.aerodynamic_power_w,
            },
            "solution": None if point is None else operating_point_to_dict(point),
        })

    low_speed_result = solve_bem(
        stations=selected_stations,
        polar=polar,
        blade_count=prop_cfg_geom["blade_count"],
        diameter_m=selected_candidate.diameter_m,
        rpm=selected_candidate.design_rpm,
        speed_m_s=5.0,
        density_kg_m3=env["density_kg_m3"],
        dynamic_viscosity_pa_s=env["dynamic_viscosity_pa_s"],
    )
    low_speed = {
        "speed_m_s": 5.0,
        "rpm": selected_candidate.design_rpm,
        "result": asdict(low_speed_result),
        "polar_envelope_ok": polar_envelope_ok(
            low_speed_result,
            min_reynolds=TRUSTED_RE[0],
            max_reynolds=TRUSTED_RE[1],
            min_alpha_deg=TRUSTED_ALPHA_DEG[0],
            max_alpha_deg=TRUSTED_ALPHA_DEG[1],
        ),
        "interpretation": "Propeller-only low-speed diagnostic. The Phase 1 aircraft model is not valid as a level-flight requirement below stall.",
    }

    max_diameter_for_clearance = 2.0 * (
        prop_cfg_geom["shaft_center_height_m"] - prop_cfg_geom["minimum_target_ground_clearance_m"]
    )
    selected_dict = candidate_to_dict(selected_candidate)
    selected_dict.update(theoretical_gearing(
        selected_candidate.design_rpm,
        mid_drive_rpm=prop_cfg["mid_drive_nominal_output_rpm"],
        driver_teeth=prop_cfg["driver_sprocket_teeth"],
    ))

    summary = {
        "status": "PHASE 2B COMPUTATIONAL TRADE / NOT FOR CONSTRUCTION",
        "baseline_main_reference": {
            "phase1_propeller_diameter_m": prop_cfg_geom["diameter_m"],
            "phase1_design_rpm": prop_cfg_geom["design_rpm"],
            "phase1_assumed_propulsive_efficiency": aero_cfg["propulsive_efficiency"],
        },
        "family_grid": {
            "diameters_m": list(DIAMETERS_M),
            "design_rpms": list(DESIGN_RPMS),
            "operating_rpms": list(OPERATING_RPMS),
            "flight_speeds_m_s": list(SPEEDS_M_S),
            "candidate_count": len(candidate_rows),
            "trusted_dae51_reynolds": list(TRUSTED_RE),
            "trusted_alpha_deg": list(TRUSTED_ALPHA_DEG),
            "shaft_power_band_w": list(SHAFT_POWER_BAND_W),
        },
        "installation_constraint": {
            "shaft_center_height_m": prop_cfg_geom["shaft_center_height_m"],
            "minimum_ground_clearance_m": prop_cfg_geom["minimum_target_ground_clearance_m"],
            "max_diameter_for_clearance_m": max_diameter_for_clearance,
            "finding": "3.0 m and 3.2 m candidates violate the present ground-clearance target at the unchanged shaft height.",
        },
        "selected_design": selected_dict,
        "baseline_reference_2p85m_130rpm": baseline_reference,
        "candidates": candidate_rows,
        "operating_envelope": operating_envelope,
        "low_speed_propeller_only": low_speed,
        "static_thrust": {
            "supported": False,
            "reason": "The current forward-flight BEM induction formulation is singular at zero axial speed; a dedicated static formulation or actuator-disk initialization is required before static thrust is reported.",
        },
        "cautions": [
            "The selected blade remains a constant-design-alpha / linear-taper seed, not a Larrabee or circulation-optimized final propeller.",
            "Off-design solutions are accepted only when final station Reynolds numbers and angles of attack remain inside the trusted DAE51 computational envelope.",
            "Theoretical sprocket tooth counts are kinematic targets only and are not claims of commercial part availability.",
            "No result establishes propeller structural strength, aeroelastic stability, hub integrity, drivetrain durability, or flight safety.",
        ],
    }

    out = Path("analysis/phase2b")
    out.mkdir(parents=True, exist_ok=True)
    (out / "propeller_family_summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    with (out / "propeller_family_candidates.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "diameter_m", "design_rpm", "ground_clearance_m", "ground_clearance_ok",
            "target_alpha_deg", "chord_scale", "thrust_n", "shaft_power_w", "efficiency",
            "min_reynolds", "max_reynolds", "min_alpha_deg", "max_alpha_deg",
            "polar_envelope_ok", "power_band_ok", "required_final_drive_ratio",
            "theoretical_driven_teeth_for_48t_driver",
        ])
        for row in candidate_rows:
            r = row["result"]
            writer.writerow([
                row["diameter_m"], row["design_rpm"], row["ground_clearance_m"], row["ground_clearance_ok"],
                row["target_alpha_deg"], row["chord_scale"], r["thrust_n"], r["shaft_power_w"], r["propulsive_efficiency"],
                r["min_reynolds"], r["max_reynolds"], r["min_alpha_deg"], r["max_alpha_deg"],
                row["polar_envelope_ok"], row["power_band_ok"], row["required_final_drive_ratio"],
                row["theoretical_driven_teeth_for_configured_driver"],
            ])

    with (out / "selected_propeller_stations.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["radius_m", "r_over_R", "chord_m", "beta_deg"])
        radius = selected_candidate.diameter_m / 2.0
        for station in selected_stations:
            writer.writerow([station.radius_m, station.radius_m / radius, station.chord_m, station.beta_deg])

    with (out / "operating_envelope.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "speed_m_s", "aircraft_cl", "required_thrust_n", "rpm", "thrust_n", "thrust_margin_n",
            "shaft_power_w", "efficiency", "min_reynolds", "max_reynolds", "min_alpha_deg", "max_alpha_deg",
            "polar_envelope_ok", "power_band_ok",
        ])
        for row in operating_envelope:
            solution = row["solution"]
            if solution is None:
                writer.writerow([row["speed_m_s"], row["aircraft"]["cl"], row["aircraft"]["drag_n"], "", "", "", "", "", "", "", "", "", False, False])
                continue
            r = solution["result"]
            writer.writerow([
                row["speed_m_s"], row["aircraft"]["cl"], row["aircraft"]["drag_n"], solution["rpm"],
                r["thrust_n"], solution["thrust_margin_n"], r["shaft_power_w"], r["propulsive_efficiency"],
                r["min_reynolds"], r["max_reynolds"], r["min_alpha_deg"], r["max_alpha_deg"],
                solution["polar_envelope_ok"], solution["power_band_ok"],
            ])

    print(json.dumps({
        "candidate_count": len(candidate_rows),
        "selected_diameter_m": selected_candidate.diameter_m,
        "selected_design_rpm": selected_candidate.design_rpm,
        "selected_shaft_power_w": selected_candidate.result.shaft_power_w,
        "selected_efficiency": selected_candidate.result.propulsive_efficiency,
        "max_diameter_for_clearance_m": max_diameter_for_clearance,
        "off_design_solved_points": sum(1 for row in operating_envelope if row["solution"] is not None),
    }, indent=2))


if __name__ == "__main__":
    main()
