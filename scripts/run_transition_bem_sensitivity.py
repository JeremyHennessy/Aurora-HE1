#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from aurora_he1.bem import design_constant_alpha_blade, solve_bem
from aurora_he1.config import load_config
from aurora_he1.model import evaluate
from aurora_he1.polars import PolarFamily


def envelope_ok(result, *, min_re: float, max_re: float, min_alpha: float, max_alpha: float) -> bool:
    return (
        result.min_reynolds >= min_re
        and result.max_reynolds <= max_re
        and result.min_alpha_deg >= min_alpha
        and result.max_alpha_deg <= max_alpha
    )


def system_consequences(*, shaft_power_w: float, speed_m_s: float, config: dict) -> dict[str, float]:
    prop = config["propulsion"]
    battery = config["battery"]
    final_drive = prop["final_drive_efficiency"]
    motor_controller = prop["motor_controller_efficiency"]
    human_input = prop["human_cruise_input_w"]
    human_shaft = human_input * final_drive
    electric_shaft = max(0.0, shaft_power_w - human_shaft)
    mid_drive_mechanical = electric_shaft / final_drive
    battery_input = mid_drive_mechanical / motor_controller
    usable_wh = battery["nominal_energy_wh"] * battery["usable_fraction"]
    endurance_h = usable_wh / battery_input if battery_input > 0 else float("inf")
    return {
        "human_prop_shaft_w": human_shaft,
        "electric_prop_shaft_w": electric_shaft,
        "electric_mid_drive_mechanical_w": mid_drive_mechanical,
        "battery_input_w": battery_input,
        "usable_battery_wh": usable_wh,
        "endurance_h": endurance_h,
        "still_air_range_km": endurance_h * speed_m_s * 3.6,
    }


def main() -> None:
    phase_cfg = json.loads(Path("config/phase2c_transition_sensitivity.json").read_text())
    config = load_config("config/he1_baseline.json")
    baseline = evaluate(config)
    env = config["environment"]
    pref = phase_cfg["propeller_reference"]
    speed = float(pref["design_speed_m_s"])
    diameter = float(pref["diameter_m"])
    design_rpm = float(pref["design_rpm"])
    blade_count = int(pref["blade_count"])
    required_thrust = baseline["cruise"]["drag_n"]
    min_re = float(min(phase_cfg["analysis_reynolds"]))
    max_re = float(max(phase_cfg["analysis_reynolds"]))
    min_alpha = float(phase_cfg["required_alpha_min_deg"])
    max_alpha = float(phase_cfg["required_alpha_max_deg"])

    stations = design_constant_alpha_blade(
        diameter_m=diameter,
        speed_m_s=speed,
        rpm=design_rpm,
        target_alpha_deg=float(pref["target_alpha_deg"]),
        chord_scale=float(pref["chord_scale"]),
    )

    rows = []
    for case in phase_cfg["cases"]:
        case_id = case["id"]
        polar = PolarFamily.from_directory(Path("analysis/phase2c/polars") / case_id, phase_cfg["airfoil"])
        fixed = solve_bem(
            stations=stations,
            polar=polar,
            blade_count=blade_count,
            diameter_m=diameter,
            rpm=design_rpm,
            speed_m_s=speed,
            density_kg_m3=env["density_kg_m3"],
            dynamic_viscosity_pa_s=env["dynamic_viscosity_pa_s"],
        )
        recovery_candidates = []
        sweep = []
        for rpm in pref["rpm_recovery_sweep"]:
            result = solve_bem(
                stations=stations,
                polar=polar,
                blade_count=blade_count,
                diameter_m=diameter,
                rpm=float(rpm),
                speed_m_s=speed,
                density_kg_m3=env["density_kg_m3"],
                dynamic_viscosity_pa_s=env["dynamic_viscosity_pa_s"],
            )
            valid_envelope = envelope_ok(result, min_re=min_re, max_re=max_re, min_alpha=min_alpha, max_alpha=max_alpha)
            point = {
                "rpm": float(rpm),
                "thrust_n": result.thrust_n,
                "shaft_power_w": result.shaft_power_w,
                "propulsive_efficiency": result.propulsive_efficiency,
                "min_reynolds": result.min_reynolds,
                "max_reynolds": result.max_reynolds,
                "min_alpha_deg": result.min_alpha_deg,
                "max_alpha_deg": result.max_alpha_deg,
                "polar_envelope_ok": valid_envelope,
                "meets_required_thrust": result.thrust_n >= required_thrust,
            }
            sweep.append(point)
            if valid_envelope and result.thrust_n >= required_thrust and result.shaft_power_w > 0 and result.propulsive_efficiency > 0:
                recovery_candidates.append((result.shaft_power_w, -result.propulsive_efficiency, float(rpm), result))
        recovery = None
        if recovery_candidates:
            recovery_candidates.sort(key=lambda x: (x[0], x[1], x[2]))
            _, _, rpm, result = recovery_candidates[0]
            recovery = {
                "rpm": rpm,
                "result": asdict(result),
                "system": system_consequences(shaft_power_w=result.shaft_power_w, speed_m_s=speed, config=config),
            }
        c4 = polar.coefficients(150000.0, 4.0)
        c6 = polar.coefficients(150000.0, 6.0)
        rows.append({
            "scenario_id": case_id,
            "label": case["label"],
            "interpretation": case["interpretation"],
            "ncrit": case["ncrit"],
            "forced_transition": case["forced_transition"],
            "section_re150k": {
                "alpha4": {"cl": c4.cl, "cd": c4.cd, "ld": c4.cl / c4.cd},
                "alpha6": {"cl": c6.cl, "cd": c6.cd, "ld": c6.cl / c6.cd},
            },
            "fixed_130rpm": {
                "result": asdict(fixed),
                "polar_envelope_ok": envelope_ok(fixed, min_re=min_re, max_re=max_re, min_alpha=min_alpha, max_alpha=max_alpha),
                "thrust_margin_n": fixed.thrust_n - required_thrust,
            },
            "thrust_recovery": recovery,
            "rpm_sweep": sweep,
        })

    clean = next(row for row in rows if row["scenario_id"] == "clean_n9")
    clean_fixed = clean["fixed_130rpm"]["result"]
    clean_recovery = clean["thrust_recovery"]
    for row in rows:
        fixed = row["fixed_130rpm"]["result"]
        row["fixed_vs_clean"] = {
            "thrust_change_pct": 100.0 * (fixed["thrust_n"] / clean_fixed["thrust_n"] - 1.0),
            "shaft_power_change_pct": 100.0 * (fixed["shaft_power_w"] / clean_fixed["shaft_power_w"] - 1.0),
            "efficiency_change_points": 100.0 * (fixed["propulsive_efficiency"] - clean_fixed["propulsive_efficiency"]),
        }
        if row["thrust_recovery"] and clean_recovery:
            rr = row["thrust_recovery"]
            cr = clean_recovery
            row["recovery_vs_clean"] = {
                "rpm_change": rr["rpm"] - cr["rpm"],
                "shaft_power_change_w": rr["result"]["shaft_power_w"] - cr["result"]["shaft_power_w"],
                "shaft_power_change_pct": 100.0 * (rr["result"]["shaft_power_w"] / cr["result"]["shaft_power_w"] - 1.0),
                "battery_input_change_w": rr["system"]["battery_input_w"] - cr["system"]["battery_input_w"],
                "range_change_km": rr["system"]["still_air_range_km"] - cr["system"]["still_air_range_km"],
            }
        else:
            row["recovery_vs_clean"] = None

    summary = {
        "status": phase_cfg["status"],
        "source_baseline": {
            "required_cruise_thrust_n": required_thrust,
            "design_speed_m_s": speed,
            "fixed_blade_geometry": {
                "diameter_m": diameter,
                "design_rpm": design_rpm,
                "target_alpha_deg": pref["target_alpha_deg"],
                "chord_scale": pref["chord_scale"],
                "station_count": len(stations),
            },
        },
        "analysis_boundary": phase_cfg["validation_boundary"],
        "cases": rows,
    }
    out_dir = Path("analysis/phase2c")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "transition_bem_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({
        "required_thrust_n": required_thrust,
        "cases": [
            {
                "id": row["scenario_id"],
                "fixed_eta": row["fixed_130rpm"]["result"]["propulsive_efficiency"],
                "fixed_thrust_n": row["fixed_130rpm"]["result"]["thrust_n"],
                "recovery_rpm": None if row["thrust_recovery"] is None else row["thrust_recovery"]["rpm"],
                "recovery_power_w": None if row["thrust_recovery"] is None else row["thrust_recovery"]["result"]["shaft_power_w"],
            }
            for row in rows
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
